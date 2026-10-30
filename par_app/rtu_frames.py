"""在一段 Modbus RTU 字节流里找某个从站的有效应答帧（D-101 静默判据，POLL-007）。

RTU 冻结/恢复命令发出后不等待回显（ACQ-025），回显可能在下一帧发送前被清掉、混进下一帧的应答，
或在包超时后清空串口时才读到；这些字节里本从站 CRC 正确的应答帧同样说明设备有应答。纯函数，不做 I/O。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any

# 网关代答“目标设备无响应”的 Modbus 异常码：网关替设备回的，不算该设备的帧（阶段一裁决 37）
GATEWAY_NO_RESPONSE_CODES = (0x0A, 0x0B)
WRITE_ECHO_BYTES = 8  # FC6 写单寄存器的回显：从站、功能码、寄存器、值、CRC，与请求帧逐字节相同
REMEMBERED_FRAMES = 2  # 记住最近几帧不等回显发出的帧：补发恢复后紧跟停止时为两帧（D-101）
EXCEPTION_REPLY_BYTES = 5  # 异常应答：从站、功能码|0x80、异常码、CRC


def count_slave_frames(data: bytes, slave_id: int, crc16: Callable[[bytes], int]) -> int:
    """data 中地址为 slave_id、CRC 正确的应答帧个数（FC3/4 读、FC6/16 写、异常应答），网关代答的异常帧不计。

    data 整体就是一帧（地址、CRC 都对）时按一帧计，与正常收到一帧应答时的计数一致；否则逐字节找帧。
    """
    if _is_slave_frame(data, slave_id, crc16):
        return int(not (data[1] & 0x80 and data[2] in GATEWAY_NO_RESPONSE_CODES))
    count = index = 0
    while index + 5 <= len(data):
        function = data[index + 1]
        if function & 0x80:
            length = 5
        elif function in (3, 4):
            length = 5 + data[index + 2]
        else:
            length = 8 if function in (6, 16) else 0
        frame = bytes(data[index : index + length])
        if length > 0 and len(frame) == length and _is_slave_frame(frame, slave_id, crc16):
            count += not (function & 0x80 and frame[2] in GATEWAY_NO_RESPONSE_CODES)
            index += length
        else:
            index += 1
    return count


def _is_slave_frame(frame: bytes, slave_id: int, crc16: Callable[[bytes], int]) -> bool:
    return (
        len(frame) >= 5
        and frame[0] == slave_id & 0xFF
        and crc16(bytes(frame[:-2])) == int.from_bytes(frame[-2:], "little")
    )


class LateEchoes:
    """#132（负责人 2026-10-29 书面批准，R-4-2）：不等回显发出的停止/恢复命令（ACQ-025），回显可能在下一帧请求发出后
    才到，排在它的应答前面，或紧跟在应答后面。只有与本客户端不等回显发出的某一帧逐字节相同（从站、功能码、内容、CRC
    都一致）的字节才算回显，从应答里分出；正在等应答的请求本身不算，它的回显就是它的应答。应答照旧校验长度、CRC、
    从站和功能码；命令、顺序、重试、超时与预算不变。分出的回显仍计入 D-101 的有效帧。"""

    def __init__(self) -> None:
        self._unanswered: deque[bytes] = deque(maxlen=REMEMBERED_FRAMES)
        self._request = b""
        self._taken = bytearray()

    def unanswered(self, frame: bytes) -> bytes:
        """记下一帧不等回显发出的帧，原样返回。"""
        self._unanswered.append(frame)
        return frame

    def asked(self, request: bytes) -> bytes:
        """开始一次等应答的交换：记下请求，清掉上次分出的回显，原样返回请求。"""
        self._request, self._taken = request, bytearray()
        return request

    def complete(self, response: bytearray, expected_len: int) -> bool:
        """先分出排在前面的回显，再看应答是否已收完（异常应答 5 字节，否则 expected_len）；收完时分出紧跟其后的回显。
        前面的字节正是某个回显的开头时还不算收完，接着收。"""
        while len(response) >= WRITE_ECHO_BYTES and self._take(bytes(response[:WRITE_ECHO_BYTES])):
            del response[:WRITE_ECHO_BYTES]
        if self._begins_echo(bytes(response)):
            return False
        exception = len(response) >= EXCEPTION_REPLY_BYTES and response[1] & 0x80
        length = EXCEPTION_REPLY_BYTES if exception else expected_len
        if len(response) < length:
            return False
        tail = bytes(response[length:])
        if tail and (self._take(tail) or self._begins_echo(tail)):
            del response[length:]  # 只到了开头的回显，其余字节下一次交换前清掉
        return True

    def heard(self, response: bytes | bytearray) -> bytes:
        """本次交换收到的全部字节：分出的回显在前，应答在后（D-101 按这些字节数有效帧）。"""
        return bytes(self._taken) + bytes(response)

    def _echoes(self) -> list[bytes]:
        return [frame for frame in self._unanswered if frame != self._request]

    def _take(self, frame: bytes) -> bool:
        if frame not in self._echoes():
            return False
        self._unanswered.remove(frame)
        self._taken += frame
        return True

    def _begins_echo(self, data: bytes) -> bool:
        return 0 < len(data) < WRITE_ECHO_BYTES and any(echo.startswith(data) for echo in self._echoes())


class PortTap:
    """#136 第二、三步（负责人 2026-10-29 书面批准，R-4-2 范围一）：串口收发记录的接入点。没有记录器时原样返回端口，
    什么也不做（V1.0.3 桌面程序就是这样）；alpha 服务装上记录器后，打开的串口由记录器包一层，记录器只把写出和读到的
    字节连同时刻复制进内存，不改字节、顺序和时间，也不在通信线程上写盘。"""

    def __init__(self) -> None:
        self.recorder: Callable[[Any, Any], Any] | None = None

    def wrap(self, port: Any, clock: Any) -> Any:  # noqa: ANN401 (a serial port and the client's clock)
        return port if self.recorder is None else self.recorder(port, clock)


PORT_TAP = PortTap()
