"""Byte-level fake Modbus TCP gateway on the loopback interface (16_ 7.1-7.2; PR #54 review M3).

The TCP path of par_app.protocol (pymodbus ModbusTcpClient behind _DeadlineTcpClient) runs unchanged: it opens a
real socket to 127.0.0.1:<port> and sends Modbus TCP frames (MBAP header + PDU). This gateway stands where a
Modbus TCP -> RS-485 gateway stands in the field: each request becomes the RTU frame the gateway would put on the
line and goes to the same `FakeSerial` line model as the RTU tests (same FakeDevice register models, same `hold_at`
/ `release` to stop at a given frame of a transaction). A device that does not answer makes the gateway answer
with exception 0x0B ("gateway target device failed to respond"), as a gateway does; the client counts that as no
valid frame from the slave (D-101), the same as RTU silence.

A request that becomes the held line frame (`hold_at`) is held on the client side, before it leaves the client's
socket (#66): pymodbus waits for an answer in real time (select, at most the frame timeout), so a request held inside
the gateway timed the client out whenever the test thread took longer than that to ask for the stop, and the client
retried 0.25 virtual seconds later. Held before it is sent, the request costs no time on either clock, as the fake
RTU port's held write does.

A request whose answer is held (`FakeSerial.hold_reply_at`, rv-70 item 2) has been sent and is on the line when
the stop comes; the client's wait for the answer then runs on the virtual clock: pymodbus's select and time in
pymodbus.client.tcp are replaced (test only) by `FakeGateway.select` / `clock_time`, which wait (real time) for the
gateway to deliver the held answer late, or, when it is lost, let the client's timeout pass on the virtual clock
(as the fake RTU port's read does). Answers that are not held arrive at once, so select returns as before.

Recorded: every Modbus TCP request exactly as received (`written()`, bytes including the transaction id), with the
virtual send time; connections accepted and closed. Only the loopback interface is used (R-4-7: no network).
"""

from __future__ import annotations

import select
import socket
import struct
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from par_app.domain.clock import Clock
from tests.support.fake_bus import HOLD_LIMIT_SECONDS, HOLD_POLL_SECONDS, FakeDevice, FakeSerial, crc16

LOOPBACK = "127.0.0.1"
MBAP_LENGTH = 7
GATEWAY_TARGET_FAILED = 0x0B


class FakeGateway:
    def __init__(self, clock: Clock, devices: dict[int, FakeDevice]) -> None:
        self.line = FakeSerial(clock, devices)
        self.frames: list[tuple[float, bytes]] = []
        self.opened = 0
        self.closed = 0
        self._lock = threading.Lock()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((LOOPBACK, 0))
        self._server.listen()
        self.port: int = self._server.getsockname()[1]
        self._threads: list[threading.Thread] = []
        self._stopping = False
        self.reply_state: str | None = None
        """"pending" from the client sending the request whose answer is held until the gateway "answered" it or the
        answer was "lost"; None otherwise."""
        accept = threading.Thread(target=self._accept, name="fake-gateway-accept", daemon=True)
        accept.start()
        self._threads.append(accept)

    # -- the same controls as FakeSerial (stop at a frame of a transaction)
    @property
    def hold_at(self) -> int | None:
        return self.line.hold_at

    @hold_at.setter
    def hold_at(self, value: int | None) -> None:
        self.line.hold_at = value

    @property
    def release(self) -> Callable[[], bool]:
        return self.line.release

    @release.setter
    def release(self, value: Callable[[], bool]) -> None:
        self.line.release = value

    @property
    def held(self) -> threading.Event:
        return self.line.held

    def written(self) -> list[tuple[float, bytes]]:
        with self._lock:
            return list(self.frames)

    def before_send(self) -> None:
        """Client side, before a request is sent: mark a request whose answer will be held, then hold a request
        that is itself held (`hold_before_send`)."""
        line = self.line
        held_reply = line.hold_reply_at is not None and len(line.frames) == line.hold_reply_at
        self.reply_state = "pending" if held_reply else None
        self.hold_before_send()

    def clock_time(self) -> float:
        """pymodbus.client.tcp's time.time(): the virtual clock (its read loop only takes differences)."""
        return self.line.clock.monotonic()

    def select(self, rlist: list[Any], wlist: list[Any], xlist: list[Any], timeout: float) -> tuple[list[Any], ...]:
        """pymodbus.client.tcp's select.select: waits for a held answer to be delivered or lost; a lost answer costs
        the client's timeout on the virtual clock (at least 1 ns, so pymodbus's read loop ends)."""
        give_up = time.monotonic() + HOLD_LIMIT_SECONDS
        while self.reply_state == "pending" and time.monotonic() < give_up:
            time.sleep(HOLD_POLL_SECONDS)
        if self.reply_state == "lost":
            self.line.clock.sleep(max(timeout, 1e-9))
            return [], [], []
        return select.select(rlist, wlist, xlist, timeout)

    def _send_reply(self, connection: socket.socket, reply: bytes) -> None:
        connection.sendall(reply)

    def hold_before_send(self) -> None:
        """Client side, before a request is sent: if it will be the held line frame, wait here until `release()`
        (real time, as FakeSerial.write; the line then lets it through at once)."""
        line = self.line
        if line.hold_at is None or len(line.frames) != line.hold_at:
            return
        line.held.set()
        give_up = time.monotonic() + HOLD_LIMIT_SECONDS
        while not line.release() and time.monotonic() < give_up:
            time.sleep(HOLD_POLL_SECONDS)

    def close(self) -> None:
        self._stopping = True
        self._server.close()
        for thread in self._threads:
            thread.join(5)

    # -- the gateway
    def _accept(self) -> None:
        while not self._stopping:
            try:
                connection, _address = self._server.accept()
            except OSError:
                return
            with self._lock:
                self.opened += 1
            worker = threading.Thread(target=self._serve, args=(connection,), name="fake-gateway-conn", daemon=True)
            worker.start()
            self._threads.append(worker)

    def _serve(self, connection: socket.socket) -> None:
        try:
            while True:
                header = _receive(connection, MBAP_LENGTH)
                if header is None:
                    return
                transaction, protocol, length, unit = struct.unpack(">HHHB", header)
                pdu = _receive(connection, length - 1)
                if pdu is None:
                    return
                rtu = bytes((unit,)) + pdu
                crc = crc16(rtu)
                self.line.write(rtu + bytes((crc & 0xFF, crc >> 8)))  # records, holds at hold_at, answers
                written = self.line.written()
                with self._lock:
                    self.frames.append((written[-1][0], header + pdu))
                answer = bytes(self.line._pending)
                self.line.reset_input_buffer()
                held_reply = len(written) - 1 == self.line.hold_reply_at
                if held_reply and self.line.lost_at == len(written) - 1:  # the held answer is lost: none comes back
                    self.reply_state = "lost"
                    continue
                body = answer[1:-2] if answer else bytes((pdu[0] | 0x80, GATEWAY_TARGET_FAILED))
                reply = struct.pack(">HHHB", transaction, protocol, len(body) + 1, unit) + body
                if held_reply:
                    # set before the answer goes out; only the held request's own answer changes reply_state (#66,
                    # Windows: after any other answer the client may already have sent the held request, "pending")
                    self.reply_state = "answered"
                self._send_reply(connection, reply)
        except OSError:
            return
        finally:
            connection.close()
            with self._lock:
                self.closed += 1


def _receive(connection: socket.socket, size: int) -> bytes | None:
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return bytes(data)


class _ClientSocket(socket.socket):
    """The client's socket to the gateway: a request to be held waits before it is sent (see the module text)."""

    gateway: FakeGateway

    def send(self, data: Any, flags: int = 0) -> int:  # noqa: ANN401 (socket.send's buffer)
        self.gateway.before_send()
        return super().send(data, flags)

    def sendall(self, data: Any, flags: int = 0) -> None:  # noqa: ANN401 (socket.sendall's buffer)
        self.gateway.before_send()
        super().sendall(data, flags)


@contextmanager
def tracked_clients(monkeypatch: pytest.MonkeyPatch, gateway: FakeGateway) -> Iterator[list[socket.socket]]:
    """Every client socket opened to `gateway` (pymodbus opens them with socket.create_connection), so a test can
    check on the client side that each was closed at a given moment; each one holds the held request before sending
    it (`FakeGateway.hold_before_send`)."""
    opened: list[socket.socket] = []
    real = socket.create_connection

    def create_connection(address: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
        made = real(address, *args, **kwargs)  # type: ignore[arg-type]
        if tuple(address)[1] != gateway.port:
            return made
        timeout = made.gettimeout()
        client = _ClientSocket(made.family, made.type, made.proto, fileno=made.detach())
        client.gateway = gateway
        client.settimeout(timeout)
        opened.append(client)
        return client

    with monkeypatch.context() as patched:
        patched.setattr(socket, "create_connection", create_connection)
        patched.setattr("pymodbus.client.tcp.select", SimpleNamespace(select=gateway.select))
        patched.setattr("pymodbus.client.tcp.time", SimpleNamespace(time=gateway.clock_time))
        yield opened
