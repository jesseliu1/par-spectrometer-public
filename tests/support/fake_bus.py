"""Byte-level fake RS-485 bus with PAR register models (16_ 7.1; R-3-4: only the wire is replaced).

`FakeSerial` stands in for serial.Serial (patched as par_app.protocol.serial.Serial). Every frame written is
recorded with the clock's monotonic time; each slave address on the line has a `FakeDevice` that answers with
CRC-correct RTU frames from a small register model: status (input 0..58, 400..475), spectrum (1000..1700),
photometric values (1701..1754), the MCU clock (holding 32..35) and the time-sync handshake (holding 36), stop/resume
(holding 25). For tier-2 maintenance (17_ 10.1) also: the diagnostic block (input 2006..2057: error counters, MCU
temperature, identity, which is also what read_device_identity reads at 2047..2057), the communication parameters
(holding 29..31; after a write the device answers only at its new address, baud rate and parity) and the
calibration object (command holding 39/40, status input 244..250, values holding 39..66). Everything above the
wire - ParModbusClient, the coordinator, CommunicationMaintenance, budgets, retries, freeze/resume, time sync,
failure counting, the halt - is product code.

Scenarios: a device can be `silent` (answers nothing), report `need_power_cycle` (the coordinator halts every
device), or the port can refuse to open (`open_error`). `hold_at` blocks the n-th write until `release()`
is true (default: never; at most HOLD_LIMIT_SECONDS), so a test can ask for a stop while the coordinator is in
the middle of a transaction, at the same frame on every path (16_ 7.2 step 4). Maintenance scenarios: a
test sets `mode = "power_cycle"` while the coordinator is in maintenance (no polling) so the next maintenance read
halts, `calibration_error` (the calibration object reports status 4 with an error code) and `close_error` (the
port's close() raises, DEF-06). Every open is recorded with its line settings (`opens`), since each maintenance
transaction opens its own connection.
"""

from __future__ import annotations

import struct
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import patch

import serial

from par_app.domain.clock import Clock

SPECTRUM_START = 1000
SPECTRUM_POINTS = 701
PARAMS_START = 1701
PARAMS_COUNT = 54
COEFFICIENT = 3
HOLD_POLL_SECONDS = 0.001
HOLD_LIMIT_SECONDS = 60.0
BAUDRATES = (4800, 9600, 14400, 19200, 38400, 57600, 115200, 256000)
PARITIES = ("N", "O", "E")
DIAG_START = 2006
DIAG_COUNT = 52
CALIBRATION_START = 39
CALIBRATION_WORDS = 28
CALIBRATION_STATUS_START = 244
CALIBRATION_READ = 66
CALIBRATION_WRITE = 88
DEFAULT_CALIBRATION = (380.0, 780.0, 450.0, 550.0, 650.0, 0.01, -0.02, 0.0, 0.015, -0.01, 0.98, -0.2, 0.2)
"""x_min, x_max, x1..x3, y0..y4, k_global, limit_min, limit_max of a fake device (a valid readback)."""
"""A held write gives up after this long (real time), so a test that never releases fails instead of hanging."""


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _framed(body: bytes) -> bytes:
    crc = crc16(body)
    return body + bytes((crc & 0xFF, crc >> 8))


@dataclass
class FakeDevice:
    """Register model of one PAR spectrometer."""

    mode: str = "ok"  # ok | silent | power_cycle | mute_on_resume (confirms the stop, then never answers again)
    stop: int = 0
    sync_state: int = 0
    clock_words: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    spectrum_base: int = 1000
    serial_number: int = 0x12345678
    device_type: int = 3
    name: str = "PAR-FAKE"
    errors: list[int] = field(default_factory=lambda: [0] * 22)
    """8 communication then 14 PAR error counters (diagnostic block)."""
    temperature_c: float = 31.5
    comm: list[int] | None = None
    """Holding 29..31 (address, baud index, parity index); None: the address it was wired at, 19200 bps, N."""
    calibration: list[float] = field(default_factory=lambda: list(DEFAULT_CALIBRATION))
    calibration_status: list[int] = field(
        default_factory=lambda: [0, 0, 1_760_000_000 & 0xFFFF, 1_760_000_000 >> 16, 0x15, 0, 0]
    )
    mute_after_move: bool = False
    """After its communication parameters were written, the device answers nothing (a verification that fails)."""
    calibration_error: int = 0
    """When set, the calibration object answers a read/write command with status 4 and this error code."""
    _staged: list[int] = field(default_factory=lambda: [3, 0] + [0] * (CALIBRATION_WORDS - 2))

    def input_register(self, address: int) -> int:
        if address == 58:
            return self.stop | (COEFFICIENT << 8)
        optics = {452: 0, 453: 1, 454: 1, 455: 1, 458: 20000, 474: 0, 475: int(self.mode == "power_cycle")}
        if address in optics:
            return optics[address]
        if SPECTRUM_START <= address < SPECTRUM_START + SPECTRUM_POINTS:
            return self.spectrum_base + (address - SPECTRUM_START) % 97
        if DIAG_START <= address < DIAG_START + DIAG_COUNT:
            return self._diagnostic_word(address - DIAG_START)
        if CALIBRATION_STATUS_START <= address < CALIBRATION_STATUS_START + len(self.calibration_status):
            return self.calibration_status[address - CALIBRATION_STATUS_START]
        return 0

    def _diagnostic_word(self, offset: int) -> int:
        temperature = struct.unpack("<HH", struct.pack("<f", self.temperature_c))
        name = self.name.encode("ascii")[:16].ljust(16, b"\0")
        words = (
            self.errors[:8]
            + [0] * 5
            + self.errors[8:22]
            + [0] * 10
            + list(temperature)
            + [0, 0]
            + [self.serial_number & 0xFFFF, self.serial_number >> 16, self.device_type]
            + [name[i] | name[i + 1] << 8 for i in range(0, 16, 2)]
        )
        return words[offset]

    def holding_register(self, address: int) -> int:
        if 32 <= address < 36:
            return self.clock_words[address - 32]
        if address == 36:
            return self.sync_state
        if 29 <= address < 32 and self.comm is not None:
            return self.comm[address - 29]
        if CALIBRATION_START <= address < CALIBRATION_START + CALIBRATION_WORDS:
            words = [3, 0]
            for value in self.calibration:
                words.extend(struct.unpack("<HH", struct.pack("<f", value)))
            return words[address - CALIBRATION_START]
        return 0

    def write_single(self, address: int, value: int) -> None:
        if address == 25:
            self.stop = value
            if value == 0 and self.mode == "mute_on_resume":
                self.mode = "silent"
        elif address == 36:
            self.sync_state = {1: 2, 3: 0}.get(value, value)
        elif address == CALIBRATION_START + 1:
            self._calibration_command(value)

    def _calibration_command(self, command: int) -> None:
        if self.calibration_error:
            self.calibration_status[0], self.calibration_status[1] = 4, self.calibration_error
        elif command == CALIBRATION_READ:
            self.calibration_status[0], self.calibration_status[1] = 1, 0
        elif command == CALIBRATION_WRITE:
            words = self._staged[2:]
            self.calibration = [
                struct.unpack("<f", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, len(words), 2)
            ]
            self.calibration_status[0], self.calibration_status[1] = 3, 0

    def write_multiple(self, address: int, words: list[int]) -> None:
        if address == 32 and len(words) == 4:
            self.clock_words = words
        elif address == 29 and len(words) == 3 and self.comm is not None:
            self.moved_to = list(words)
        elif address == CALIBRATION_START and len(words) == CALIBRATION_WORDS:
            self._staged = list(words)

    moved_to: list[int] | None = None
    """New communication parameters written to holding 29..31; FakeSerial applies them after the reply."""

    def line(self) -> tuple[int, str]:
        assert self.comm is not None
        return BAUDRATES[self.comm[1]], PARITIES[self.comm[2]]

    def answer(self, frame: bytes) -> bytes | None:
        if self.mode == "silent" or len(frame) < 8 or crc16(frame[:-2]) != (frame[-2] | frame[-1] << 8):
            return None
        slave, function = frame[0], frame[1]
        address, value = struct.unpack(">HH", frame[2:6])
        if function in (3, 4):
            read = self.input_register if function == 4 else self.holding_register
            registers = [read(address + offset) & 0xFFFF for offset in range(value)]
            body = bytes((slave, function, value * 2)) + b"".join(struct.pack(">H", r) for r in registers)
            return _framed(body)
        if function == 6:
            self.write_single(address, value)
            return None if self.mode == "silent" else frame[:8]
        if function == 16:
            words = [struct.unpack(">H", frame[7 + i * 2 : 9 + i * 2])[0] for i in range(value)]
            self.write_multiple(address, words)
            return _framed(frame[:6])
        return None


class FakeSerial:
    """The serial port on one RS-485 line. An unanswered read costs its timeout on the clock (as a real port)."""

    def __init__(self, clock: Clock, devices: dict[int, FakeDevice]) -> None:
        self.clock = clock
        self.devices = devices
        for address, device in devices.items():
            if device.comm is None:
                device.comm = [address, BAUDRATES.index(19200), 0]
        self.opens: list[tuple[int | None, str | None]] = []
        """(baud rate, parity) of every open, in order; None where the opener did not say."""
        self.settings: tuple[int | None, str | None] = (None, None)
        self.close_error: str | None = None
        """When set, close() raises (once per value set) as a port whose handle cannot be released (DEF-06)."""
        self.lock = threading.Lock()
        self.frames: list[tuple[float, bytes]] = []
        self.sent_at: list[datetime] = []
        """The virtual wall time (clock.now()) each frame of `frames` was written at."""
        self.opened = 0
        self.closed = 0
        self.open_error: str | None = None
        self.timeout = 0.02
        self.write_timeout = 1.5
        self.hold_at: int | None = None
        self.hold_when: Callable[[bytes], bool] | None = None
        """Like hold_at, but for the first frame this predicate accepts (then cleared)."""
        self.hold_reply_at: int | None = None
        """The n-th write goes out (recorded, the device acts on it), then its answer is held until `release()`: a
        stop that comes while the request is on the line and the answer is not yet back (#66, rv-70 item 2). The
        hold is real time only; the coordinator is blocked in the write meanwhile, so no virtual time passes."""
        self.reply_lost = False
        """With hold_reply_at: after the release the held answer is lost (the read then times out on the clock)."""
        self.lost_at: int | None = None
        """Index of the write whose answer was lost (FakeGateway sends nothing for it)."""
        self.release: Callable[[], bool] = lambda: False
        self.held = threading.Event()
        self._pending = bytearray()

    # -- what the test controls
    def open(self, baudrate: int | None = None, parity: str | None = None) -> FakeSerial:
        if self.open_error is not None:
            raise serial.SerialException(self.open_error)
        self.opened += 1
        self.settings = (baudrate, parity)
        self.opens.append(self.settings)
        return self

    def _hears(self, device: FakeDevice) -> bool:
        baudrate, parity = self.settings
        line = device.line()
        return (baudrate is None or baudrate == line[0]) and (parity is None or parity == line[1])

    def written(self) -> list[tuple[float, bytes]]:
        with self.lock:
            return list(self.frames)

    # -- serial.Serial API used by par_app.protocol
    @property
    def in_waiting(self) -> int:
        return len(self._pending)

    def write(self, frame: bytes) -> int:
        held = self.hold_when is not None and self.hold_when(bytes(frame))
        if held:
            self.hold_when = None
        if held or (self.hold_at is not None and len(self.frames) == self.hold_at):
            self._wait_for_release()
        with self.lock:
            index = len(self.frames)
            self.frames.append((self.clock.monotonic(), bytes(frame)))
            self.sent_at.append(self.clock.now())
        device = self.devices.get(frame[0])
        reply = device.answer(bytes(frame)) if device is not None and self._hears(device) else None
        if self.hold_reply_at is not None and index == self.hold_reply_at:
            self._wait_for_release()
            if self.reply_lost:
                reply, self.lost_at = None, index
        if reply:
            self._pending += reply
        if device is not None and device.moved_to is not None:  # the new parameters take effect after the reply
            device.comm, device.moved_to = device.moved_to, None
            if device.mute_after_move:
                device.mode = "silent"
            del self.devices[frame[0]]
            self.devices[device.comm[0]] = device
        return len(frame)

    def _wait_for_release(self) -> None:
        self.held.set()
        give_up = time.monotonic() + HOLD_LIMIT_SECONDS
        while not self.release() and time.monotonic() < give_up:
            time.sleep(HOLD_POLL_SECONDS)  # real time: the test thread asks for the stop meanwhile

    def read(self, count: int = 1) -> bytes:
        if not self._pending:
            self.clock.sleep(self.timeout)
            return b""
        data = bytes(self._pending[:count])
        del self._pending[:count]
        return data

    def reset_input_buffer(self) -> None:
        self._pending.clear()

    def setDTR(self, value: bool) -> None:  # noqa: N802 (pyserial's name)
        pass

    def setRTS(self, value: bool) -> None:  # noqa: N802 (pyserial's name)
        pass

    def close(self) -> None:
        if self.close_error is not None:
            error, self.close_error = self.close_error, None
            raise OSError(error)
        self.closed += 1


@contextmanager
def wired(port: FakeSerial) -> Iterator[FakeSerial]:
    """Patch serial.Serial as par_app.protocol uses it; every open returns `port` (or raises open_error)."""

    def open_port(*args: object, **kwargs: object) -> FakeSerial:
        baudrate = args[1] if len(args) > 1 else kwargs.get("baudrate")
        parity = kwargs.get("parity")
        return port.open(baudrate if isinstance(baudrate, int) else None, parity if isinstance(parity, str) else None)

    with patch("par_app.protocol.serial.Serial", side_effect=open_port):
        yield port


def first_difference(left: list[tuple[float, bytes]], right: list[tuple[float, bytes]]) -> str:
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if a != b:
            return f"frame {index}: {a[0]:.6f} {a[1].hex()} != {b[0]:.6f} {b[1].hex()}"
    return f"lengths differ: {len(left)} != {len(right)}"
