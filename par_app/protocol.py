from __future__ import annotations

import struct
from contextlib import contextmanager
from dataclasses import asdict
from typing import Callable, Sequence

import serial
from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from .domain.clock import Clock, SystemClock
from .models import ConnectionConfig, DeviceStatus, PHOTOMETRIC_NAMES
from .rtu_frames import PORT_TAP, LateEchoes, count_slave_frames


class ProtocolError(RuntimeError):
    pass


class HardwareStateError(ProtocolError):
    def __init__(self, status: DeviceStatus):
        self.status = status
        reasons = []
        if not status.initialized:
            reasons.append("探头未初始化")
        if status.need_power_cycle:
            reasons.append("探头要求重新上电")
        super().__init__("；".join(reasons))


class CommunicationTimeout(ProtocolError):
    pass


class CommunicationCancelled(ProtocolError):
    pass


class AcquisitionResumeError(ProtocolError):
    pass


class _DeadlineTcpClient(ModbusTcpClient):
    remaining: Callable[[], float] | None = None

    def _limit_wait(self):
        if self.remaining is not None:
            timeout = self.remaining()
            self.comm_params.timeout_connect = timeout
            if self.socket:
                self.socket.settimeout(timeout)

    def recv(self, size):
        self._limit_wait()
        result = super().recv(size)
        self._limit_wait()
        return result

    def send(self, request, addr=None):
        self._limit_wait()
        return super().send(request, addr)


def float_from_low_high(low: int, high: int) -> float:
    return struct.unpack("<f", struct.pack("<HH", low & 0xFFFF, high & 0xFFFF))[0]


def float_to_low_high(value: float) -> list[int]:
    return list(struct.unpack("<HH", struct.pack("<f", value)))


def uint64_from_low_words(words: Sequence[int]) -> int:
    return sum((int(word) & 0xFFFF) << (16 * index) for index, word in enumerate(words[:4]))


def uint64_to_low_words(value: int) -> list[int]:
    return [(value >> (16 * i)) & 0xFFFF for i in range(4)]


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


class ParModbusClient:
    """仅包含已确认的 PAR 专用寄存器协议。地址均为 0-based PDU 地址。"""

    _READ_RETRY_COUNT = 3
    _READ_RETRY_DELAY_SECONDS = 0.25
    # 当前 LoRa 透明链路实测：96寄存器稳定，完整事务中 100ms 帧间隔更稳。
    _INTER_REQUEST_DELAY_SECONDS = 0.10

    def __init__(self, config: ConnectionConfig, clock: Clock | None = None):
        self.config = config
        self._clock: Clock = clock if clock is not None else SystemClock()  # 唯一时间来源（R-1-6）；测试注入 FakeClock
        self.client = self._build_client(config)
        self._serial: serial.Serial | None = None
        self.last_connection_error = ""
        self._deadline: float | None = None
        self._cancelled: Callable[[], bool] | None = None
        self._finish_packet = False
        self._next_request_at, self._echoes = 0.0, LateEchoes()  # 不等回显发出的帧，回显可能晚到（#132）
        self._valid_frames = 0  # 本从站有效应答帧计数（D-101 静默判据；0x0A/0x0B 由网关代答，不计）
        self.last_transaction_silent = False
        self._resume_first = False
        if isinstance(self.client, _DeadlineTcpClient):
            self.client.remaining = self._io_timeout

    @contextmanager
    def communication_budget(self, seconds: float, cancelled: Callable[[], bool] | None = None):
        previous = self._deadline, self._cancelled
        deadline = self._clock.monotonic() + seconds
        self._deadline = min(deadline, previous[0]) if previous[0] is not None else deadline
        self._cancelled = cancelled if cancelled is not None else previous[1]
        try:
            self._check_budget()
            yield
            if not self._finish_packet:
                self._check_budget()
        finally:
            self._deadline, self._cancelled = previous

    @contextmanager
    def acquisition_budget(self, seconds: float, cancelled: Callable[[], bool] | None = None):
        previous = self._finish_packet
        self._finish_packet = True
        try:
            with self.communication_budget(seconds, cancelled):
                yield
                if self._cancelled is not None and self._cancelled():
                    raise CommunicationCancelled('通信已取消')
        finally:
            self._finish_packet = previous

    @contextmanager
    def _packet_budget(self):
        if not self._finish_packet:
            yield
            return
        self._delay(max(0.0, self._next_request_at - self._clock.monotonic()))
        previous = self._deadline, self._cancelled
        self._deadline = self._clock.monotonic() + max(.001, self.config.timeout_seconds)
        self._cancelled = None
        try:
            yield
        except (ProtocolError, OSError):
            self._drain_late_response()
            raise
        finally:
            self._deadline, self._cancelled = previous
            self._next_request_at = self._clock.monotonic() + self._INTER_REQUEST_DELAY_SECONDS
            if self._cancelled is not None and self._cancelled():
                raise CommunicationCancelled('通信已取消')

    def _drain_late_response(self) -> None:
        if self.config.transport == 'tcp':
            self.client.close()
            return
        if self._serial is None:
            return
        deadline = self._clock.monotonic() + max(.001, self.config.timeout_seconds) + self._INTER_REQUEST_DELAY_SECONDS
        drained = bytearray()
        while self._clock.monotonic() < deadline:
            self._serial.timeout = min(.02, max(.0001, deadline - self._clock.monotonic()))
            drained += self._serial.read(max(1, self._serial.in_waiting))
        self._valid_frames += count_slave_frames(drained, self.config.slave_id, crc16_modbus)  # D-101：迟到的应答

    def _check_budget(self) -> None:
        if self._cancelled is not None and self._cancelled():
            raise CommunicationCancelled("通信已取消")
        if self._deadline is not None and self._clock.monotonic() >= self._deadline:
            raise CommunicationTimeout("设备通信超时，已用完本次访问预算")

    def _io_timeout(self) -> float:
        self._check_budget()
        timeout = max(0.001, float(self.config.timeout_seconds))
        remaining = self._deadline - self._clock.monotonic() if self._deadline is not None else timeout
        if remaining <= 0:
            raise CommunicationTimeout("设备通信超时，已用完本次访问预算")
        return min(timeout, remaining)

    def _delay(self, seconds: float) -> None:
        until = self._clock.monotonic() + seconds
        while self._clock.monotonic() < until:
            self._check_budget()
            remaining = until - self._clock.monotonic()
            if self._deadline is not None:
                remaining = min(remaining, self._deadline - self._clock.monotonic())
            self._clock.sleep(max(0.0, min(0.02, remaining)))
        self._check_budget()

    def set_slave_id(self, slave_id: int, resume_first: bool = False) -> None:
        """同一物理链路上分时切换目标从站，避免为每台设备重复打开串口。

        波特率/校验位等总线参数由 BusConfig 统一，只有从站地址随设备变化。
        """
        self.config.slave_id = int(slave_id)
        self.last_transaction_silent = False
        self._resume_first = resume_first  # D-101：该从站上次冻结事务整次无应答，本次冻结前先补发一次恢复命令

    @staticmethod
    def _build_client(config: ConnectionConfig):
        if config.transport == "tcp":
            return _DeadlineTcpClient(host=config.host, port=config.tcp_port, timeout=config.timeout_seconds, retries=0)
        return ModbusSerialClient(port=config.serial_port, baudrate=config.baudrate, parity=config.parity,
                                  stopbits=1, bytesize=8, timeout=config.timeout_seconds)

    def connect(self) -> bool:
        self.last_connection_error = ""
        if self.config.transport == "tcp":
            return bool(self.client.connect())
        try:
            self._serial = PORT_TAP.wrap(serial.Serial(self.config.serial_port, self.config.baudrate, bytesize=8,
                                         parity=self.config.parity, stopbits=1, timeout=0.02,
                                         write_timeout=max(1.0, self.config.timeout_seconds)), self._clock)
            # 当前 CP210x + LoRa 透明链路不使用硬件流控/控制线；DTR/RTS 置位会导致链路偶发无响应。
            self._serial.setDTR(False)
            self._serial.setRTS(False)
            # CP210x/LoRa 重新打开后立即发首帧会偶发无响应；先留出链路稳定时间。
            self._clock.sleep(1.0)
            self._serial.reset_input_buffer()
            return True
        except serial.SerialException as exc:
            self.last_connection_error = str(exc)
            if self._serial is not None:
                try:
                    self._serial.close()
                except serial.SerialException:
                    pass
                self._serial = None
            return False
        except Exception:
            # POLL-074（DEF-05）：POSIX 下控制线/清缓冲失败抛 OSError 或 termios.error，先释放句柄再原样抛出。
            if self._serial is not None:
                handle, self._serial = self._serial, None
                try:
                    handle.close()
                except OSError:  # 关闭失败不得覆盖原始异常
                    pass
            raise

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
        else:
            self.client.close()

    def _read_input(self, address: int, count: int) -> list[int]:
        return self._read_registers("输入", address, count, self.client.read_input_registers)

    def _read_input_chunked(self, address: int, count: int) -> list[int]:
        """遵守 Modbus 帧长度与光谱仪 19200 bps 串口缓冲区的共同限制。"""
        values: list[int] = []
        # 125 个寄存器对应 255 字节 RTU 响应，当前 LoRa 链路实测会稳定丢尾；
        # 64 个寄存器响应帧约 133 字节，嵌入完整应用事务后比 96 更稳。
        chunk_limit = 64 if self.config.transport == "rtu" and self.config.baudrate <= 19200 else 125
        while len(values) < count:
            chunk_count = min(chunk_limit, count - len(values))
            values.extend(self._read_input(address + len(values), chunk_count))
        return values

    def _read_holding(self, address: int, count: int) -> list[int]:
        return self._read_registers("保持", address, count, self.client.read_holding_registers)

    def _read_registers(self, register_type: str, address: int, count: int, request) -> list[int]:
        """RTU 从站忙于采集或刚完成发送时，仅重试幂等的读请求。"""
        last_error: Exception | None = None
        for attempt in range(self._READ_RETRY_COUNT):
            try:
                self._check_budget()
                with self._packet_budget():
                    if self.config.transport == "rtu":
                        values = self._rtu_read_registers(4 if register_type == "输入" else 3, address, count)
                    else:
                        response = request(address=address, count=count, device_id=self.config.slave_id)
                        self._valid_frames += getattr(response, "exception_code", 0) not in (0x0A, 0x0B)
                        if response.isError():
                            raise ProtocolError(f"读{register_type}寄存器 {address}:{count} 失败：{response}")
                        values = list(response.registers)
                    if len(values) != count:
                        raise ProtocolError(f'寄存器响应长度不完整：{len(values)}/{count}')
                if self.config.transport == "rtu" and not self._finish_packet:
                    self._delay(self._INTER_REQUEST_DELAY_SECONDS)
                if not self._finish_packet:
                    self._check_budget()
                return values
            except (CommunicationTimeout, CommunicationCancelled):
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self._READ_RETRY_COUNT:
                    self._delay(self._READ_RETRY_DELAY_SECONDS * (attempt + 1))
        raise ProtocolError(f"读{register_type}寄存器 {address}:{count} 连续失败：{last_error}") from last_error

    def _write_register(self, address: int, value: int) -> None:
        self._check_budget()
        with self._packet_budget():
            if self.config.transport == "rtu":
                self._rtu_write_single(address, value)
            else:
                response = self.client.write_register(address=address, value=value, device_id=self.config.slave_id)
                self._valid_frames += getattr(response, "exception_code", 0) not in (0x0A, 0x0B)
                if response.isError():
                    raise ProtocolError(f"写保持寄存器 {address} 失败：{response}")
        if self.config.transport == "rtu" and not self._finish_packet:
            self._delay(self._INTER_REQUEST_DELAY_SECONDS)

    def _write_registers(self, address: int, values: list[int]) -> None:
        self._check_budget()
        if self.config.transport == "rtu":
            self._rtu_write_multiple(address, values)
            self._delay(self._INTER_REQUEST_DELAY_SECONDS)
            return
        response = self.client.write_registers(address=address, values=values, device_id=self.config.slave_id)
        if response.isError():
            raise ProtocolError(f"批量写保持寄存器 {address}:{len(values)} 失败：{response}")

    def _rtu_frame(self, function: int, payload: bytes) -> bytes:
        body = bytes((self.config.slave_id & 0xFF, function & 0xFF)) + payload
        crc = crc16_modbus(body)
        return body + bytes((crc & 0xFF, (crc >> 8) & 0xFF))

    def _rtu_send_without_waiting_response(self, function: int, payload: bytes) -> None:
        if self._serial is None:
            raise ProtocolError("串口尚未打开")
        port = self._serial
        with self._packet_budget():
            port.write_timeout = self._io_timeout()
            if port.in_waiting:
                self._valid_frames += count_slave_frames(port.read(port.in_waiting), self.config.slave_id, crc16_modbus)
            port.write(self._echoes.unanswered(self._rtu_frame(function, payload)))
        if not self._finish_packet:
            self._delay(self._INTER_REQUEST_DELAY_SECONDS)

    def _rtu_exchange(self, function: int, payload: bytes, expected_len: int) -> bytes:
        if self._serial is None:
            raise ProtocolError("串口尚未打开")
        port = self._serial
        timeout = self._io_timeout()
        port.write_timeout = timeout
        if port.in_waiting:  # D-101：清掉的字节（如不等待的冻结/恢复回显）里本从站的有效帧同样计数
            self._valid_frames += count_slave_frames(port.read(port.in_waiting), self.config.slave_id, crc16_modbus)
        deadline = self._clock.monotonic() + timeout
        response = bytearray()
        try:
            port.write(self._echoes.asked(self._rtu_frame(function, payload)))
            while self._clock.monotonic() < deadline:
                self._check_budget()
                port.timeout = max(0.0001, min(0.02, deadline - self._clock.monotonic()))
                waiting = port.in_waiting
                if waiting:
                    response.extend(port.read(waiting))
                else:
                    chunk = port.read(1)
                    if chunk:
                        response.extend(chunk)
                if self._echoes.complete(response, expected_len):  # #132：先分出晚到的写回显
                    break
            self._check_budget()
            if len(response) < 5:
                raise ProtocolError(f"RTU 无响应或响应过短：{len(response)}/{expected_len}")
            if len(response) < expected_len and not (response[1] & 0x80):
                raise ProtocolError(f"RTU 响应不完整：{len(response)}/{expected_len}")
            got_crc = response[-2] | (response[-1] << 8)
            want_crc = crc16_modbus(bytes(response[:-2]))
            if got_crc != want_crc:
                raise ProtocolError(f"RTU CRC 错误：got=0x{got_crc:04X} want=0x{want_crc:04X}")
            if response[0] != (self.config.slave_id & 0xFF):
                raise ProtocolError(f"RTU 从站地址不符：{response[0]}")
        finally:  # D-101：成功或失败都按收到的字节计本从站有效帧（失败时可能混有迟到的回显；0x0A/0x0B 不计）
            self._valid_frames += count_slave_frames(self._echoes.heard(response), self.config.slave_id, crc16_modbus)
        if response[1] & 0x80:
            raise ProtocolError(f"RTU 异常响应：功能码={function} 异常码={response[2]}")
        if response[1] != function:
            raise ProtocolError(f"RTU 功能码不符：{response[1]}")
        return bytes(response)

    def _rtu_read_registers(self, function: int, address: int, count: int) -> list[int]:
        payload = struct.pack(">HH", address & 0xFFFF, count & 0xFFFF)
        expected_len = 1 + 1 + 1 + count * 2 + 2
        response = self._rtu_exchange(function, payload, expected_len)
        if response[2] != count * 2:
            raise ProtocolError(f"RTU 字节数不符：{response[2]} != {count * 2}")
        return [int.from_bytes(response[3 + i * 2: 5 + i * 2], "big") for i in range(count)]

    def _rtu_write_single(self, address: int, value: int) -> None:
        payload = struct.pack(">HH", address & 0xFFFF, value & 0xFFFF)
        response = self._rtu_exchange(6, payload, 8)
        if response[2:6] != payload:
            raise ProtocolError("RTU 写单寄存器回显不符")

    def _rtu_write_multiple(self, address: int, values: list[int]) -> None:
        register_bytes = b"".join(struct.pack(">H", value & 0xFFFF) for value in values)
        payload = struct.pack(">HHB", address & 0xFFFF, len(values) & 0xFFFF, len(register_bytes)) + register_bytes
        response = self._rtu_exchange(16, payload, 8)
        expected_echo = struct.pack(">HH", address & 0xFFFF, len(values) & 0xFFFF)
        if response[2:6] != expected_echo:
            raise ProtocolError("RTU 写多寄存器回显不符")

    def read_status(self) -> DeviceStatus:
        # LoRa 模块在短响应帧上偶发不回传；连续大帧会触发流式转发，实测更稳定。
        base = self._read_input(0, 59)
        optics = self._read_input(400, 76)
        stop_word = base[58]
        exposure_words = optics[58:62]
        return DeviceStatus(
            initialized=bool(optics[53]), need_power_cycle=bool(optics[75]),
            raw_data_valid=bool(optics[54]), calculate_data_valid=bool(optics[55]),
            stop_status=stop_word & 0xFF, spectral_coefficient=(stop_word >> 8) & 0xFF,
            exposure_status=int(optics[52]), exposure_time_us=uint64_from_low_words(exposure_words),
            exposure_mode=int(optics[74]),
        )

    def verify_par_signature(self) -> bool:
        """以 PAR 专用输入寄存器布局进行只读身份校验，不向候选串口写任何内容。"""
        base = self._read_input(0, 59)
        optics = self._read_input(400, 76)
        stop_word = base[58]
        exposure_time = uint64_from_low_words(optics[58:62])
        return (
            (stop_word & 0xFF) in (0, 1)
            and 0 <= (stop_word >> 8) <= 15
            and optics[52] in (0, 1, 2)
            and optics[53] in (0, 1)
            and optics[54] in (0, 1)
            and optics[55] in (0, 1)
            and optics[74] in (0, 1)
            and 0 <= exposure_time <= 120_000_000
        )

    def read_device_identity(self) -> dict[str, int | str]:
        """读取 MCU 输入寄存器 2047–2057：32 位序列号、设备类型及设备名称。"""
        registers = self._read_input(2047, 11)
        serial_number = (registers[0] & 0xFFFF) | ((registers[1] & 0xFFFF) << 16)
        name_bytes = bytearray()
        for word in registers[3:]:
            name_bytes.extend((word & 0xFF, (word >> 8) & 0xFF))
        device_name = name_bytes.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()
        return {"serial_number": serial_number, "device_type": registers[2] & 0xFFFF, "device_name": device_name}

    def read_diagnostics(self) -> dict:
        status = self.read_status()
        if not status.initialized or status.need_power_cycle:
            raise HardwareStateError(status)
        registers = self._read_input(2006, 52)
        name_bytes = b"".join(struct.pack("<H", word) for word in registers[44:52])
        return {
            "status": asdict(status),
            "mcu_temperature_c": float_from_low_high(*registers[37:39]),
            "communication_errors": registers[:8],
            "par_errors": registers[13:27],
            "identity": {
                "serial_number": registers[41] | (registers[42] << 16),
                "device_type": registers[43],
                "device_name": name_bytes.split(b"\0", 1)[0].decode("ascii", errors="replace").strip(),
            },
        }

    def set_stop(self, stop: bool) -> None:
        if self.config.transport == "rtu":
            # LoRa 当前链路对 8 字节写回显偶发不转发；该命令后续由 read_status 大帧确认。
            payload = struct.pack(">HH", 25, 1 if stop else 0)
            self._rtu_send_without_waiting_response(6, payload)
            return
        self._write_register(25, 1 if stop else 0)

    def wait_stop(self, desired: int, timeout_seconds: float = 2.0) -> DeviceStatus:
        deadline = self._clock.monotonic() + timeout_seconds
        last: DeviceStatus | None = None
        while self._clock.monotonic() < deadline:
            last = self.read_status()
            if not last.initialized or last.need_power_cycle:
                raise HardwareStateError(last)
            if last.stop_status == desired:
                return last
            self._delay(0.04)
        raise ProtocolError(f"等待停止状态 {desired} 超时，最后状态={last.stop_status if last else '未读取'}")

    def read_spectrum_transaction(self) -> tuple[DeviceStatus, list[int], dict[str, float]]:
        """冻结 MCU 帧以避免两个曝光周期混读；finally 中尽力恢复。D-101：未确认停止且整次事务没有收到本从站任何有效帧
        即为静默设备，置 last_transaction_silent；恢复失败时不报“恢复采集未确认”，原始通信异常照常抛出。"""
        stopped = stop_confirmed = False
        hardware_error = None
        frames_before = self._valid_frames
        self.last_transaction_silent = False
        try:
            available = self._deadline - self._clock.monotonic() if self._deadline is not None else 10.0
            with self.communication_budget(max(0.0, available - 2.0)):
                stopped = True
                if self.config.transport == "rtu" and self._serial is not None and self._serial.in_waiting:
                    self._serial.read(self._serial.in_waiting)  # 裁决 37：开始前已在串口里的字节属更早的交换，不计
                if self._resume_first:
                    self.set_stop(False)
                self.set_stop(True)
                status = self.wait_stop(1)
                stop_confirmed = True
                if not status.initialized or status.need_power_cycle:
                    raise HardwareStateError(status)
                raw_points = self._read_input_chunked(1000, 701)
                params = self._read_input(1701, 54)
                values = {name: float_from_low_high(params[i * 2], params[i * 2 + 1]) for i, name in enumerate(PHOTOMETRIC_NAMES)}
                return status, raw_points, values
        except HardwareStateError as exc:
            hardware_error = exc
            raise
        finally:
            if stopped:
                previous = self._deadline, self._finish_packet
                try:
                    self._deadline = None
                    self._finish_packet = False
                    with self.communication_budget(2.0, lambda: False):
                        self.set_stop(False)
                        self.wait_stop(0)
                except HardwareStateError:
                    if hardware_error is None:
                        raise
                except Exception as exc:
                    self.last_transaction_silent = not stop_confirmed and self._valid_frames == frames_before
                    if hardware_error is None and not self.last_transaction_silent:
                        raise AcquisitionResumeError(f"恢复采集未确认：{exc}") from exc
                finally:
                    self._deadline, self._finish_packet = previous

    def sync_time(self, timeout_seconds: float = 2.0) -> int:
        now_ms = int(self._clock.now().timestamp() * 1000)
        self._write_registers(32, uint64_to_low_words(now_ms))
        self._write_register(36, 1)
        deadline = self._clock.monotonic() + timeout_seconds
        while self._clock.monotonic() < deadline:
            if self._read_holding(36, 1)[0] == 2:
                # MCU 已冻结 standard_time_ms；以尽量接近提交时刻的本机时间刷新它。
                now_ms = int(self._clock.now().timestamp() * 1000)
                self._write_registers(32, uint64_to_low_words(now_ms))
                self._write_register(36, 3)
                break
            self._delay(0.03)
        else:
            raise ProtocolError("MCU 对时未进入确认状态 2")
        while self._clock.monotonic() < deadline:
            if self._read_holding(36, 1)[0] == 0:
                return now_ms
            self._delay(0.03)
        raise ProtocolError("MCU 对时超时")

    def read_standard_time(self) -> int:
        """读取已由 MCU 时间基准维护的 Unix 毫秒时间。"""
        return uint64_from_low_words(self._read_holding(32, 4))

    def read_mcu_comm(self) -> dict[str, int]:
        """读取 MCU 当前生效的 Modbus 从站地址、波特率索引和校验位索引。"""
        slave_id, baudrate_index, parity_index = self._read_holding(29, 3)
        if not 1 <= slave_id <= 247 or not 0 <= baudrate_index <= 7 or not 0 <= parity_index <= 2:
            raise ProtocolError("MCU 返回了无效的通信参数")
        return {"slave_id": slave_id, "baudrate_index": baudrate_index, "parity_index": parity_index}

    def read_calibration(self) -> tuple[dict[str, float | int], dict[str, int]]:
        self._write_register(39, 3)
        self._write_register(40, 66)
        status = self._wait_calibration((1, 4))
        if status["status"] != 1:
            raise ProtocolError(f"读取校准失败，错误码={status['error']}")
        regs = self._read_holding(39, 28)
        names = ("x_min", "x_max", "x1", "x2", "x3", "y0", "y1", "y2", "y3", "y4", "k_global", "limit_min", "limit_max")
        data: dict[str, float | int] = {"sensor_id": regs[0]}
        for index, name in enumerate(names):
            offset = 2 + index * 2
            data[name] = float_from_low_high(regs[offset], regs[offset + 1])
        return data, status

    def write_calibration(self, data: dict[str, float]) -> dict[str, int]:
        names = ("x_min", "x_max", "x1", "x2", "x3", "y0", "y1", "y2", "y3", "y4", "k_global", "limit_min", "limit_max")
        values = [3, 0]
        for name in names:
            values.extend(float_to_low_high(float(data[name])))
        self._write_registers(39, values)
        self._write_register(40, 88)
        status = self._wait_calibration((3, 4), timeout_seconds=2.0)
        if status["status"] != 3 or status["error"] != 0:
            raise ProtocolError(f"写入校准失败，状态={status['status']} 错误={status['error']}")
        return status

    def _wait_calibration(self, accepted: tuple[int, ...], timeout_seconds: float = 2.0) -> dict[str, int]:
        deadline = self._clock.monotonic() + timeout_seconds
        while self._clock.monotonic() < deadline:
            regs = self._read_input(244, 7)
            result = {"status": regs[0], "error": regs[1], "timestamp": regs[2] | (regs[3] << 16),
                      "version_nodes": regs[4], "custom_constraint": regs[5], "custom_content": regs[6]}
            if result["status"] in accepted:
                return result
            self._delay(0.04)
        raise ProtocolError("等待校准 MCU 状态超时")

    def change_mcu_comm(self, new_slave_id: int, baudrate_index: int, parity_index: int) -> None:
        self._write_registers(29, [new_slave_id, baudrate_index, parity_index])
