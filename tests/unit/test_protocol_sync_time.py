"""MCU time-sync handshake of `ParModbusClient.sync_time` on a FakeClock (POLL-049, POLL-086; R-1-6, R-3-3).

Holding register 36 drives the handshake: the host writes the stamp to 32-35 and 1 to 36, waits for the MCU to
report 2 (stamp frozen, waiting for confirmation), writes a fresh stamp and 3, then waits for 0 (done). Both waits
poll every 30 ms against one 2-second deadline. The MCUs here take virtual time to answer, so the tests see
which wall time the second stamp carries and when each timeout fires; nothing touches a device.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_app.models import ConnectionConfig
from par_app.protocol import CommunicationCancelled, ParModbusClient, ProtocolError, uint64_from_low_words

pytestmark = [pytest.mark.unit, pytest.mark.spec("POLL-049"), pytest.mark.spec("POLL-086")]

START_WALL = datetime(2026, 10, 17, 9, 30, tzinfo=BEIJING_TZ)
START_WALL_EPOCH_MS = int(datetime(2026, 10, 17, 1, 30, tzinfo=UTC).timestamp() * 1000)
UPTIME_SECONDS = 7200.0
SYNC_TIMEOUT_SECONDS = 2.0  # ParModbusClient.sync_time default
POLL_SECONDS = 0.03  # sync_time waits this long between two reads of register 36
SYNC_COMMAND_REGISTER = 36
STANDARD_TIME_REGISTER = 32


class SlowMcu:
    """Answers register 36 like the MCU, but only after `confirm_reads` / `done_reads` reads (None: never)."""

    def __init__(self, confirm_reads: int | None, done_reads: int | None = 0) -> None:
        self.confirm_reads = confirm_reads
        self.done_reads = done_reads
        self.state = 0
        self.reads_in_state = 0
        self.stamps: list[int] = []
        self.status_reads = 0
        self.on_read: Callable[[int], None] = lambda reads: None

    def write_registers(self, address: int, values: list[int]) -> None:
        assert address == STANDARD_TIME_REGISTER
        self.stamps.append(uint64_from_low_words(values))

    def write_register(self, address: int, value: int) -> None:
        assert address == SYNC_COMMAND_REGISTER
        assert value in (1, 3)
        self.state, self.reads_in_state = value, 0

    def read_holding(self, address: int, count: int) -> list[int]:
        assert (address, count) == (SYNC_COMMAND_REGISTER, 1)
        self.status_reads += 1
        self.on_read(self.status_reads)
        if self.state == 1 and self.confirm_reads is not None and self.reads_in_state >= self.confirm_reads:
            self.state = 2
        elif self.state == 3 and self.done_reads is not None and self.reads_in_state >= self.done_reads:
            self.state = 0
        self.reads_in_state += 1
        return [self.state]


def client_on(clock: FakeClock, mcu: SlowMcu, monkeypatch: pytest.MonkeyPatch) -> ParModbusClient:
    client = ParModbusClient(ConnectionConfig(), clock=clock)
    monkeypatch.setattr(client, "_write_registers", mcu.write_registers)
    monkeypatch.setattr(client, "_write_register", mcu.write_register)
    monkeypatch.setattr(client, "_read_holding", mcu.read_holding)
    return client


def ms_after_start(milliseconds: int) -> int:
    return START_WALL_EPOCH_MS + milliseconds


def test_second_stamp_is_the_wall_time_when_the_mcu_confirms(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCU needs three 30 ms polls to confirm; the stamp written with command 3 is 90 ms later than the first."""
    clock = FakeClock(START_WALL, monotonic=UPTIME_SECONDS)
    mcu = SlowMcu(confirm_reads=3, done_reads=2)
    stamp = client_on(clock, mcu, monkeypatch).sync_time()
    assert mcu.stamps == [ms_after_start(0), ms_after_start(90)]
    assert stamp == ms_after_start(90)
    assert clock.now() - START_WALL == timedelta(milliseconds=150)  # + two 30 ms polls until done


def test_mcu_that_never_confirms_fails_after_the_two_second_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock(START_WALL, monotonic=UPTIME_SECONDS)
    mcu = SlowMcu(confirm_reads=None)
    with pytest.raises(ProtocolError, match="MCU 对时未进入确认状态 2"):
        client_on(clock, mcu, monkeypatch).sync_time()
    assert mcu.stamps == [ms_after_start(0)]  # no confirmation, so no second stamp and no command 3
    assert mcu.status_reads == 67  # reads at 0, 0.03, ..., 1.98 s; the next one would be past the deadline
    assert clock.monotonic() - UPTIME_SECONDS == pytest.approx(2.01, abs=1e-9)


def test_mcu_that_confirms_but_never_finishes_fails_after_the_same_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock(START_WALL, monotonic=UPTIME_SECONDS)
    mcu = SlowMcu(confirm_reads=10, done_reads=None)
    with pytest.raises(ProtocolError, match="^MCU 对时超时$"):
        client_on(clock, mcu, monkeypatch).sync_time()
    assert mcu.stamps == [ms_after_start(0), ms_after_start(300)]
    # one deadline for both waits, counted from the first command: 11 reads up to the confirmation at 0.30 s,
    # then 57 more at 0.30, 0.33, ..., 1.98 s
    assert mcu.status_reads == 68
    assert clock.monotonic() - UPTIME_SECONDS == pytest.approx(2.01, abs=1e-9)


def test_communication_budget_cuts_the_handshake_at_its_own_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inside the coordinator's 2-second budget (POLL-049) the budget, not sync_time, ends a silent handshake."""
    clock = FakeClock(START_WALL, monotonic=UPTIME_SECONDS)
    mcu = SlowMcu(confirm_reads=None)
    client = client_on(clock, mcu, monkeypatch)
    with pytest.raises(ProtocolError, match="已用完本次访问预算"), client.communication_budget(SYNC_TIMEOUT_SECONDS):
        client.sync_time()
    assert clock.monotonic() - UPTIME_SECONDS == pytest.approx(SYNC_TIMEOUT_SECONDS, abs=1e-9)


def test_cancel_during_the_handshake_stops_it(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock(START_WALL, monotonic=UPTIME_SECONDS)
    mcu = SlowMcu(confirm_reads=None)
    cancelled: list[bool] = []

    def cancel_on_fifth_read(reads: int) -> None:
        if reads == 5:
            cancelled.append(True)

    mcu.on_read = cancel_on_fifth_read
    client = client_on(clock, mcu, monkeypatch)
    with (
        pytest.raises(CommunicationCancelled),
        client.communication_budget(SYNC_TIMEOUT_SECONDS, lambda: bool(cancelled)),
    ):
        client.sync_time()
    assert mcu.status_reads == 5
    assert mcu.stamps == [ms_after_start(0)]
    assert clock.monotonic() - UPTIME_SECONDS < 5 * POLL_SECONDS
