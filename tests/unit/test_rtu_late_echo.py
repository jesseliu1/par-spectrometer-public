"""A late write echo in front of the reply that was asked for (issue #132; owner's R-4-2 approval, 2026-10-29).

RTU stop/resume is FC6 on register 25, sent without waiting for its echo (ACQ-025). On the site's slower devices
(3 and 4) that echo arrived after the next request had gone out, in front of its reply: 131 bytes where a 123-byte
status reply was expected. The whole buffer was checked as one frame, the CRC failed, the read was retried, and the
retry spent the 2-second resume budget: 恢复采集未确认, a global halt.

`_rtu_exchange` now separates such an echo: only bytes equal to a frame this client sent without waiting (so its
slave, function, payload and CRC all match), at the front of the reply or straight after it, and never when the
request itself is that frame. The reply is then checked as before (length, CRC, slave, function). Not changed:
commands, their order, retries, frame timeouts, the 100 ms spacing, the resume budget and the halt rule; the
frames written are the same as when the echo is on time.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

import pytest

from par_app.models import ConnectionConfig
from par_app.protocol import AcquisitionResumeError, CommunicationTimeout, ParModbusClient, ProtocolError
from tests.virtual_clock import virtual_clock

pytestmark = [pytest.mark.unit, pytest.mark.spec("ACQ-025 ACQ-026")]

Arrivals = list[tuple[float, bytes]]
"""(seconds after the write, bytes) that reach the port for one written frame."""


class ScriptedPort:
    """A serial port whose bytes arrive at set times after each write; a read returns what has arrived by then."""

    def __init__(self, clock, respond: Callable[[bytes], Arrivals]) -> None:  # noqa: ANN001 (a FakeClock)
        self.clock, self.respond = clock, respond
        self.timeout = 0.02
        self.write_timeout = 1.0
        self.frames: list[bytes] = []
        self.sent_at: list[float] = []
        self._coming: list[tuple[float, bytes]] = []
        self._arrived = bytearray()

    def _collect(self) -> None:
        now = self.clock.monotonic()
        self._coming.sort(key=lambda item: item[0])
        while self._coming and self._coming[0][0] <= now:
            self._arrived += self._coming.pop(0)[1]

    @property
    def in_waiting(self) -> int:
        self._collect()
        return len(self._arrived)

    def write(self, frame: bytes) -> int:
        self.frames.append(bytes(frame))
        now = self.clock.monotonic()
        self.sent_at.append(now)
        self._coming += [(now + delay, data) for delay, data in self.respond(bytes(frame))]
        return len(frame)

    def read(self, size: int = 1) -> bytes:
        self._collect()
        if not self._arrived:
            next_at = min((at for at, _ in self._coming), default=None)
            wait = self.timeout if next_at is None else min(self.timeout, next_at - self.clock.monotonic())
            self.clock.sleep(max(1e-9, wait))
            self._collect()
        data = bytes(self._arrived[:size])
        del self._arrived[:size]
        return data


def _client(slave_id: int = 3, timeout: float = 1.5) -> tuple[ParModbusClient, object]:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(slave_id=slave_id, timeout_seconds=timeout), clock=clock)
    return client, clock


def _reply(client: ParModbusClient, words: list[int], slave_id: int | None = None) -> bytes:
    payload = bytes([len(words) * 2]) + b"".join(struct.pack(">H", word) for word in words)
    frame = client._rtu_frame(4, payload)  # noqa: SLF001
    return frame if slave_id is None else bytes([slave_id]) + frame[1:-2] + _crc(bytes([slave_id]) + frame[1:-2])


def _crc(body: bytes) -> bytes:
    from par_app.protocol import crc16_modbus

    return crc16_modbus(body).to_bytes(2, "little")


def _echo(client: ParModbusClient, stop: bool) -> bytes:
    return client._rtu_frame(6, struct.pack(">HH", 25, int(stop)))  # noqa: SLF001 (an FC6 echo is the request)


def _status_words(address: int, count: int, stop: int) -> list[int]:
    words = [0] * count
    if address == 0 and count == 59:
        words[58] = stop  # stop_status in the low byte, spectral coefficient 0
    if address == 400 and count == 76:
        words[53] = 1  # initialized; need_power_cycle (75) stays 0
    return words


class Device:
    """Answers every read after `reply_delay`; echoes each FC6 write `echo_delay` after it (None: on time, before
    the next request; the request then finds it already in the port and discards it, as today)."""

    def __init__(self, client: ParModbusClient, reply_delay: float, echo_delay: float | None) -> None:
        self.client, self.reply_delay, self.echo_delay = client, reply_delay, echo_delay
        self.stop = 0

    def __call__(self, frame: bytes) -> Arrivals:
        function = frame[1]
        if function == 6:
            self.stop = frame[5]
            return [(0.0 if self.echo_delay is None else self.echo_delay, bytes(frame))]
        address, count = struct.unpack(">HH", frame[2:6])
        return [(self.reply_delay, _reply(self.client, _status_words(address, count, self.stop)))]


def _read_after_unanswered_write(arrivals: Arrivals, *, count: int = 59, timeout: float = 1.5) -> tuple:
    """set_stop(True) goes out unanswered, then a read whose bytes arrive as `arrivals` (relative to the read)."""
    client, clock = _client(timeout=timeout)
    echo = _echo(client, True)
    sent: list[bytes] = []

    def respond(frame: bytes) -> Arrivals:
        sent.append(frame)
        return [] if frame[1] == 6 else arrivals

    port = ScriptedPort(clock, respond)
    client._serial = port  # noqa: SLF001
    client.set_stop(True)
    return client, clock, port, echo


def test_an_echo_in_front_of_the_reply_in_one_chunk_is_split_off() -> None:
    """The field case: 8 + 123 bytes in one read, the echo first."""
    client, clock, port, echo = _read_after_unanswered_write([])
    reply = _reply(client, _status_words(0, 59, 1))
    assert len(echo + reply) == 131  # what the site's trace showed
    port.respond = lambda frame: [(0.3, echo + reply)]
    frames_before = client._valid_frames  # noqa: SLF001
    assert client._read_input(0, 59) == _status_words(0, 59, 1)  # noqa: SLF001
    assert len(port.frames) == 2  # the stop and one read: no retry
    assert client._valid_frames - frames_before == 2  # noqa: SLF001 (the echo and the reply: D-101 counts both)


def test_an_echo_and_a_reply_arriving_in_pieces_are_split() -> None:
    client, clock, port, echo = _read_after_unanswered_write([])
    reply = _reply(client, _status_words(0, 59, 1))
    port.respond = lambda frame: [(0.10, echo[:3]), (0.12, echo[3:]), (0.30, reply[:60]), (0.35, reply[60:])]
    assert client._read_input(0, 59) == _status_words(0, 59, 1)  # noqa: SLF001
    assert len(port.frames) == 2


def test_an_echo_straight_after_the_reply_is_split_off() -> None:
    client, clock, port, echo = _read_after_unanswered_write([])
    reply = _reply(client, _status_words(0, 59, 1))
    port.respond = lambda frame: [(0.30, reply + echo)]
    assert client._read_input(0, 59) == _status_words(0, 59, 1)  # noqa: SLF001
    assert len(port.frames) == 2


def test_an_echo_then_part_of_the_reply_is_still_incomplete() -> None:
    client, clock, port, echo = _read_after_unanswered_write([], timeout=0.5)
    reply = _reply(client, _status_words(0, 59, 1))
    port.respond = lambda frame: [(0.10, echo + reply[:100])]
    with pytest.raises(ProtocolError, match="不完整"):
        client._read_input(0, 59)  # noqa: SLF001


@pytest.mark.parametrize(
    "case", ["bad crc", "other slave", "other value", "other register"], ids=lambda case: case.replace(" ", "-")
)
def test_bytes_that_are_not_exactly_a_frame_this_client_sent_stay_and_fail_as_before(case: str) -> None:
    """Only an exact copy of an unanswered frame is separated; anything else in front is checked as today."""
    client, clock, port, echo = _read_after_unanswered_write([], timeout=0.5)
    reply = _reply(client, _status_words(0, 59, 1))
    if case == "bad crc":
        front = echo[:-1] + bytes([echo[-1] ^ 0xFF])
    elif case == "other slave":
        body = bytes([4]) + echo[1:-2]
        front = body + _crc(body)
    elif case == "other value":
        front = _echo(client, False)
    else:
        body = client._rtu_frame(6, struct.pack(">HH", 26, 1))[:-2]  # noqa: SLF001
        front = body + _crc(body)
    port.respond = lambda frame: [(0.10, front + reply)]
    with pytest.raises(ProtocolError, match="CRC|不符|连续失败"):
        client._read_input(0, 59)  # noqa: SLF001
    assert len(port.frames) == 1 + 3  # the stop, then the three reads _read_registers always tried


def test_a_damaged_reply_behind_a_separated_echo_still_fails_its_crc() -> None:
    """review of the fix: the echo is separated, the reply behind it is checked as before and fails."""
    client, clock, port, echo = _read_after_unanswered_write([], timeout=0.5)
    reply = bytearray(_reply(client, _status_words(0, 59, 1)))
    reply[10] ^= 0xFF  # one data byte changed on the line
    port.respond = lambda frame: [(0.10, (echo if len(port.frames) == 2 else b"") + bytes(reply))]
    with pytest.raises(ProtocolError, match="连续失败.*CRC"):
        client._read_input(0, 59)  # noqa: SLF001
    assert len(port.frames) == 1 + 3  # the three reads _read_registers always tried


def test_a_reply_from_another_slave_behind_the_echo_is_still_refused() -> None:
    client, clock, port, echo = _read_after_unanswered_write([], timeout=0.5)
    other = _reply(client, _status_words(0, 59, 1), slave_id=4)
    port.respond = lambda frame: [(0.10, (echo if len(port.frames) == 2 else b"") + other)]  # the echo comes once
    with pytest.raises(ProtocolError, match="连续失败.*从站地址不符"):
        client._read_input(0, 59)  # noqa: SLF001


def test_a_write_that_waits_for_its_own_echo_is_not_mistaken_for_a_late_one() -> None:
    """The same FC6 frame sent once without waiting and once waiting: the first 8 bytes answer the waiting one."""
    client, clock, port, echo = _read_after_unanswered_write([])
    port.respond = lambda frame: [(0.10, bytes(frame))]
    client.config.transport = "rtu"
    client._rtu_write_single(25, 1)  # noqa: SLF001
    assert len(port.frames) == 2


@pytest.mark.parametrize(("arrives_at", "accepted"), [(1.49, True), (1.51, False)])
def test_a_correct_reply_behind_an_echo_at_the_frame_timeout_edge(arrives_at: float, accepted: bool) -> None:
    """The frame timeout (1.5 s here) is unchanged: echo and reply inside it are accepted, after it not."""
    client, clock, port, echo = _read_after_unanswered_write([])
    reply = _reply(client, _status_words(0, 59, 1))
    port.respond = lambda frame: [(arrives_at, echo + reply)]
    with client.acquisition_budget(40.0):
        if accepted:
            assert client._read_input(0, 59) == _status_words(0, 59, 1)  # noqa: SLF001
        else:
            with pytest.raises((ProtocolError, CommunicationTimeout)):
                client._read_input(0, 59)  # noqa: SLF001


def _transaction(reply_delay: float, echo_delay: float | None) -> tuple[ParModbusClient, ScriptedPort, object]:
    client, clock = _client()
    port = ScriptedPort(clock, Device(client, reply_delay, echo_delay))
    client._serial = port  # noqa: SLF001
    with client.acquisition_budget(40.0):
        status, points, _ = client.read_spectrum_transaction()
    assert status.initialized and len(points) == 701
    return client, port, clock


def test_the_field_timings_now_confirm_the_resume_and_send_the_same_frames() -> None:
    """Device 4's failing round (#132): replies about 0.55 s after each request, the echo of every stop/resume
    command 0.35 s after it, behind the next request. Before: CRC error, a retry, and the 2-second resume budget
    ran out (恢复采集未确认). Now the same frames go out as when the echo is on time."""
    _, late, _ = _transaction(reply_delay=0.55, echo_delay=0.35)
    _, on_time, _ = _transaction(reply_delay=0.55, echo_delay=None)
    assert late.frames == on_time.frames  # same commands, same order, no extra read


def test_frame_spacing_and_send_times_are_the_same_with_a_late_echo() -> None:
    """The echo arrives just after the next request went out (the 100 ms spacing has passed): every frame goes out
    at the same moment as when the echo is on time, so the spacing and the timing are unchanged."""
    _, late, _ = _transaction(reply_delay=0.05, echo_delay=0.12)
    _, on_time, _ = _transaction(reply_delay=0.05, echo_delay=None)
    assert late.frames == on_time.frames
    assert late.sent_at == pytest.approx(on_time.sent_at, abs=1e-6)


@pytest.mark.parametrize(("reply_delay", "confirmed"), [(0.80, True), (0.90, False)])
def test_a_correct_resume_confirmation_behind_an_echo_at_the_resume_budget_edge(
    reply_delay: float, confirmed: bool
) -> None:
    """The 2-second resume budget is unchanged (independent review of the fix). The resume confirmation is the
    100 ms wait after the unanswered resume command, two status reads (the first with the resume's late echo in
    front), each followed by the 100 ms wait that is still there (its place is not part of this fix): replies
    0.80 s after each request end inside the budget and the resume is confirmed; 0.90 s ends outside it and the
    transaction halts as before."""
    client, clock = _client()
    client._serial = ScriptedPort(clock, Device(client, reply_delay, echo_delay=0.5))  # noqa: SLF001
    with client.acquisition_budget(40.0):
        if confirmed:
            assert client.read_spectrum_transaction()[0].initialized
        else:
            with pytest.raises(AcquisitionResumeError, match="恢复采集未确认"):
                client.read_spectrum_transaction()


def test_a_failed_read_then_a_failed_resume_still_halts_as_before() -> None:
    """The first error (no spectrum reply), then the resume confirmation gets no status reply: the device did answer
    in this transaction, so 恢复采集未确认 (D-101 unchanged); the late echoes do not change that."""
    client, clock = _client(timeout=0.3)
    device = Device(client, reply_delay=0.05, echo_delay=0.08)
    reads = {"after spectrum": False}

    def respond(frame: bytes) -> Arrivals:
        if frame[1] == 4 and struct.unpack(">H", frame[2:4])[0] == 1000:
            reads["after spectrum"] = True
            return []  # the spectrum read gets nothing
        if reads["after spectrum"] and frame[1] == 4:
            return []  # nor does the resume confirmation
        return device(frame)

    client._serial = ScriptedPort(clock, respond)  # noqa: SLF001
    with pytest.raises(AcquisitionResumeError, match="恢复采集未确认"):
        with client.acquisition_budget(40.0):
            client.read_spectrum_transaction()
