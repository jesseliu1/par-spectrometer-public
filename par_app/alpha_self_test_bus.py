"""Tier-1 check of the packaged alpha's self-test: a SYNTHETIC loopback Modbus TCP gateway, no real device or port.

PAR_Spectrometer_2.exe --alpha-self-test (main_v2.py) hands `Level1Kit` to par_shell/self_test.py, which runs it in
the self-test process, never in the service: the service child is the unchanged par_app.service_main, with no "fake
bus" switch of any kind (16_ 7.8). The kit

  * writes the alpha's tier-1 configuration into the self-test's temporary data directory (V1.0.3's format through
    V1.0.3's AppConfigStore, as tests/acquisition/conftest.write_config does): ONE device on transport "tcp", host
    127.0.0.1, at the port of the gateway below, its database under <data dir>/data/devices. No serial port is
    named, so the coordinator can only open a loopback TCP socket (R-4-7: no device, no network);
  * runs `SelfTestGateway` on 127.0.0.1: it answers Modbus TCP requests (functions 3, 4, 6, 16) from a minimal
    register model, a subset of tests/support/fake_bus.FakeDevice (status, spectrum, MCU clock, time-sync
    handshake, stop/resume, identity block). Values are made up; they are not measurements;
  * probes V1.0.3's single-instance lock exactly as the alpha takes it (acquisition_host.instance_lock), so the
    self-test can see it held during the takeover and free afterwards;
  * reports the Qt binding of this process (PySide6, internal notes), its version and the version of the QtCore
    library actually loaded (the lock's native name depends on Qt, 16_ 2.2).

Importing it imports par_app.acquisition_host (PySide6's QtCore, the coordinator, pymodbus, pyserial): the packaged
build must contain them (16_ 8.2, 18_).
"""

from __future__ import annotations

import shutil
import socket
import struct
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .acquisition_host import host as _host  # noqa: F401  (the takeover's modules must be in the package)
from .acquisition_host.instance_lock import InstanceLock
from .app_config import AppConfigStore
from .models import AppConfig, BusConfig, DeviceConfig
from .qt_compat import BINDING, BINDING_VERSION, qVersion

LOOPBACK = "127.0.0.1"
DEVICE_NAME = "SELF-TEST"
SLAVE_ID = 1
MBAP_BYTES = 7
EXCEPTION_FLAG = 0x80
ILLEGAL_FUNCTION = 0x01
READ_HOLDING = 3
READ_INPUT = 4
WRITE_SINGLE = 6
WRITE_MULTIPLE = 16
REGISTER_MASK = 0xFFFF
STOP_REGISTER = 25
"""Holding 25: stop (1) / resume (0) acquisition, as tests/support/fake_bus.FakeDevice."""
CLOCK_START = 32
CLOCK_WORDS = 4
SYNC_REGISTER = 36
SYNC_ANSWERS = {1: 2, 3: 0}
"""Time-sync handshake of FakeDevice: a request (1) is answered as done (2), an acknowledgement (3) clears it."""
STATUS_REGISTER = 58
COEFFICIENT = 3
"""Spectral coefficient in the high byte of input 58 (made up, within V1.0.x's range; FakeDevice uses the same)."""
OPTICS = {452: 0, 453: 1, 454: 1, 455: 1, 458: 20000, 474: 0, 475: 0}
"""Optics status words of FakeDevice; 475 = 0: no power-cycle request, so the coordinator never halts."""
SPECTRUM_START = 1000
SPECTRUM_POINTS = 701
SPECTRUM_BASE = 1000
SPECTRUM_PERIOD = 97
"""Made-up spectrum: SPECTRUM_BASE + (index mod SPECTRUM_PERIOD), the same shape as FakeDevice."""
IDENTITY_START = 2047
IDENTITY = (0x5678, 0x1234, 3)
"""Serial number (low, high word) and device type in the identity block, made up."""
ACCEPT_BACKLOG = 4


@dataclass
class SelfTestGateway:
    """Modbus TCP server on 127.0.0.1:<free port> answering for slave SLAVE_ID; counts requests and connections."""

    stop_flag: int = 0
    sync_state: int = 0
    clock: list[int] = field(default_factory=lambda: [0] * CLOCK_WORDS)
    requests: int = 0
    opened: int = 0
    closed: int = 0
    port: int = 0
    _server: socket.socket | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> int:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((LOOPBACK, 0))
        server.listen(ACCEPT_BACKLOG)
        self._server = server
        self.port = int(server.getsockname()[1])
        threading.Thread(target=self._accept, name="self-test-gateway", daemon=True).start()
        return self.port

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    def counts(self) -> tuple[int, int, int]:
        with self._lock:
            return self.requests, self.opened, self.closed

    def _accept(self) -> None:
        server = self._server
        while server is not None:
            try:
                connection, _address = server.accept()
            except OSError:
                return
            with self._lock:
                self.opened += 1
            threading.Thread(target=self._serve, args=(connection,), name="self-test-gateway-conn", daemon=True).start()

    def _serve(self, connection: socket.socket) -> None:
        try:
            while True:
                header = _receive(connection, MBAP_BYTES)
                if header is None:
                    return
                transaction, protocol, length, unit = struct.unpack(">HHHB", header)
                pdu = _receive(connection, length - 1)
                if pdu is None:
                    return
                with self._lock:
                    self.requests += 1
                    body = self._answer(unit, pdu)
                if body is None:  # another slave address: a gateway would time out on the line
                    continue
                connection.sendall(struct.pack(">HHHB", transaction, protocol, len(body) + 1, unit) + body)
        except OSError:
            return
        finally:
            connection.close()
            with self._lock:
                self.closed += 1

    def _answer(self, unit: int, pdu: bytes) -> bytes | None:
        if unit != SLAVE_ID:
            return None
        function = pdu[0]
        address, value = struct.unpack(">HH", pdu[1:5])
        if function in (READ_HOLDING, READ_INPUT):
            read = self._input if function == READ_INPUT else self._holding
            words = [read(address + offset) & REGISTER_MASK for offset in range(value)]
            return bytes((function, value * 2)) + b"".join(struct.pack(">H", word) for word in words)
        if function == WRITE_SINGLE:
            if address == STOP_REGISTER:
                self.stop_flag = value
            elif address == SYNC_REGISTER:
                self.sync_state = SYNC_ANSWERS.get(value, value)
            return pdu[:5]
        if function == WRITE_MULTIPLE:
            words = [struct.unpack(">H", pdu[6 + 2 * i : 8 + 2 * i])[0] for i in range(value)]
            if address == CLOCK_START and len(words) == CLOCK_WORDS:
                self.clock = words
            return pdu[:5]
        return bytes((function | EXCEPTION_FLAG, ILLEGAL_FUNCTION))

    def _input(self, address: int) -> int:
        if address == STATUS_REGISTER:
            return self.stop_flag | (COEFFICIENT << 8)
        if address in OPTICS:
            return OPTICS[address]
        if SPECTRUM_START <= address < SPECTRUM_START + SPECTRUM_POINTS:
            return SPECTRUM_BASE + (address - SPECTRUM_START) % SPECTRUM_PERIOD
        if IDENTITY_START <= address < IDENTITY_START + len(IDENTITY):
            return IDENTITY[address - IDENTITY_START]
        return 0

    def _holding(self, address: int) -> int:
        if CLOCK_START <= address < CLOCK_START + CLOCK_WORDS:
            return self.clock[address - CLOCK_START]
        if address == SYNC_REGISTER:
            return self.sync_state
        return 0


def _receive(connection: socket.socket, size: int) -> bytes | None:
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return bytes(data)


class Level1Kit:
    """What par_shell/self_test.py needs for its tier-1 steps (it imports nothing from par_app itself)."""

    def __init__(self) -> None:
        self.gateway = SelfTestGateway()

    def prepare(self, data_dir: Path, seed: Path) -> str:
        """Start the gateway and write the one-device TCP configuration into `data_dir`, with a byte copy of `seed`
        (the synthetic V1.0.x-format database) as the device's database; returns a description."""
        port = self.gateway.start()
        device = DeviceConfig(name=DEVICE_NAME, slave_id=SLAVE_ID)
        config = AppConfig(
            bus=BusConfig(transport="tcp", serial_port="", host=LOOPBACK, tcp_port=port),
            devices=[device],
            configured=True,
        )
        database = (data_dir / device.resolved_database_path(0)).resolve()
        database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, database)
        device.database_path = str(database)
        AppConfigStore(data_dir).save(config)
        return f"1 device, Modbus TCP {LOOPBACK}:{port} (synthetic gateway), no serial port"

    @staticmethod
    def lock_free() -> bool:
        """True if V1.0.3's lock could be taken (and was released again at once)."""
        lock = InstanceLock()
        if not lock.acquire():
            return False
        lock.release()
        return True

    def counts(self) -> tuple[int, int, int]:
        """(requests answered, connections opened, connections closed) of the gateway."""
        return self.gateway.counts()

    @staticmethod
    def qt_versions() -> dict[str, str]:
        """The binding of this process, its version and the version of the QtCore library actually loaded (qVersion(),
        not the Qt the binding was compiled against, which would not reveal a different library)."""
        return {"binding": BINDING, "version": BINDING_VERSION, "qt": str(qVersion())}

    def close(self) -> None:
        self.gateway.close()
