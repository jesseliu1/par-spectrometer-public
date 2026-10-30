"""Clock interface (R-1-6): the contract coordinator and protocol rely on since step 2.

Monotonic and Beijing wall time are separate, the wall clock is Beijing time regardless of the host zone,
`sleep` waits on the monotonic clock, and FakeClock moves only when the code sleeps or a test tells it to
(including wall-clock jumps, R-3-3), in whole nanoseconds so many small waits add up exactly.
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime, timedelta

import pytest

from par_app.domain import clock as clock_module
from par_app.domain.clock import BEIJING_TZ, Clock, FakeClock, SystemClock

pytestmark = pytest.mark.unit

EIGHT_HOURS = timedelta(hours=8)
START = datetime(2026, 10, 17, 9, 30, tzinfo=BEIJING_TZ)


def test_both_clocks_satisfy_the_protocol() -> None:
    assert isinstance(SystemClock(), Clock)
    assert isinstance(FakeClock(START), Clock)


def test_system_monotonic_is_the_process_monotonic_clock() -> None:
    clock = SystemClock()
    before = time.monotonic()
    value = clock.monotonic()
    after = time.monotonic()
    assert before <= value <= after


SLEEP_SECONDS = 0.05
"""Long against any monotonic tick (Windows: 15.625 ms), so a sleep that returned at once is still caught."""
WINDOWS_TICK_SECONDS = 0.015625
"""time.get_clock_info("monotonic").resolution on Windows with Python 3.11 (GetTickCount64, 64 ticks a second)."""


def _sleep_is_seen_on_the_monotonic_clock(clock: SystemClock, resolution: float) -> None:
    """A clock that only moves in steps of `resolution` can show up to one step less than the time really slept
    (issue #66: sleep(0.01) on Windows read the same monotonic value before and after)."""
    before = clock.monotonic()
    clock.sleep(SLEEP_SECONDS)
    assert clock.monotonic() - before >= SLEEP_SECONDS - resolution


def test_system_sleep_waits_on_the_monotonic_clock() -> None:
    _sleep_is_seen_on_the_monotonic_clock(SystemClock(), time.get_clock_info("monotonic").resolution)


class _TickingTime:
    """Stands in for the time module with a monotonic clock that only moves in Windows ticks; sleep advances it
    exactly (deterministic, so the test does not depend on where in a tick it starts)."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return math.floor(self.now / WINDOWS_TICK_SECONDS) * WINDOWS_TICK_SECONDS

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_system_sleep_check_holds_with_a_windows_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check above with the coarse clock of Windows simulated: sleep(0.01) there shows 0.0 (the old assertion
    failed), SLEEP_SECONDS against one tick of tolerance passes."""
    ticking = _TickingTime()
    monkeypatch.setattr(clock_module, "time", ticking)
    clock = SystemClock()
    before = clock.monotonic()
    clock.sleep(0.01)
    assert clock.monotonic() - before == 0.0  # what Windows showed (#66)
    _sleep_is_seen_on_the_monotonic_clock(clock, WINDOWS_TICK_SECONDS)


def test_system_wall_clock_is_aware_beijing_time(utc_host: None) -> None:
    clock = SystemClock()
    before = datetime.now(UTC)
    value = clock.now()
    after = datetime.now(UTC)
    assert value.utcoffset() == EIGHT_HOURS
    assert before <= value <= after


def test_fake_clock_starts_where_told_and_stands_still() -> None:
    clock = FakeClock(START, monotonic=100.0)
    assert clock.monotonic() == 100.0
    assert clock.now() == START
    assert clock.now().utcoffset() == EIGHT_HOURS
    assert clock.monotonic() == 100.0


def test_fake_clock_advance_moves_both_clocks_by_exactly_the_same_amount() -> None:
    clock = FakeClock(START)
    clock.advance(35.0)
    clock.advance(5.25)
    assert clock.monotonic() == 40.25
    assert clock.now() - START == timedelta(seconds=40.25)


def test_fake_clock_sleep_returns_at_once_and_moves_both_clocks() -> None:
    clock = FakeClock(START, monotonic=600.0)
    clock.sleep(0.05)
    clock.sleep(0)
    assert clock.monotonic() == 600.05
    assert clock.now() - START == timedelta(seconds=0.05)


def test_fake_clock_small_steps_add_up_exactly() -> None:
    """Budget loops wait in 0.02 s slices; 2000 of them must land on 40.0, not 39.99999999999.."""
    clock = FakeClock(START)
    for _ in range(2000):
        clock.sleep(0.02)
    assert clock.monotonic() == 40.0
    for _ in range(3):
        clock.sleep(0.1)
    assert clock.monotonic() == 40.3


@pytest.mark.parametrize("step", ["advance", "sleep"])
def test_fake_wall_clock_keeps_sub_microsecond_steps(step: str) -> None:
    """10,000 waits of 100 ns are 1 ms on both clocks, also as the epoch milliseconds sent to the MCU.

    A wall clock that rounds every step to whole microseconds would stay where it was (review of #35, major 1).
    """
    clock = FakeClock(START, monotonic=7.0)
    for _ in range(10_000):
        getattr(clock, step)(1e-7)
    assert clock.monotonic() == 7.001
    assert clock.now() - START == timedelta(milliseconds=1)
    assert int(clock.now().timestamp() * 1000) == int(START.timestamp() * 1000) + 1


def test_fake_wall_clock_moves_by_the_same_nanoseconds_as_monotonic() -> None:
    """Both clocks take the same whole-nanosecond step; the wall clock shows the last whole microsecond passed."""
    clock = FakeClock(START, monotonic=7.0)
    clock.advance(1.5e-6)
    assert clock.now() - START == timedelta(microseconds=1)
    clock.advance(0.5e-6)
    assert clock.monotonic() - 7.0 == pytest.approx(2e-6, abs=1e-12)
    assert clock.now() - START == timedelta(microseconds=2)


def test_fake_wall_clock_jump_restarts_sub_microsecond_counting() -> None:
    clock = FakeClock(START)
    clock.advance(9e-7)
    jump = START + timedelta(hours=1)
    clock.set_wall(jump)
    assert clock.now() == jump
    clock.advance(2e-7)
    assert clock.now() == jump  # 200 ns after the jump, not 1.1 us


@pytest.mark.parametrize("step", ["advance", "sleep"])
@pytest.mark.parametrize("seconds", [1e-10, 4e-10, 1.4e-9])
def test_fake_clock_positive_step_always_moves_monotonic_time(step: str, seconds: float) -> None:
    """A wait shorter than the 1 ns resolution still moves the clock (at least 1 ns), so a loop such as
    `while monotonic() < until: sleep(until - monotonic())` cannot spin forever on a sub-ns remainder."""
    clock = FakeClock(START, monotonic=4.69)
    before = clock.monotonic()
    getattr(clock, step)(seconds)
    assert clock.monotonic() > before
    assert clock.monotonic() - before < 3e-9
    moved = clock.monotonic()
    getattr(clock, step)(0)
    assert clock.monotonic() == moved  # a zero step still does not move it


@pytest.mark.parametrize("bad", [-0.001, math.nan, math.inf])
@pytest.mark.parametrize("step", ["advance", "sleep"])
def test_fake_clock_refuses_to_run_backwards_or_to_non_finite_values(bad: float, step: str) -> None:
    clock = FakeClock(START, monotonic=7.0)
    with pytest.raises(ValueError):
        getattr(clock, step)(bad)
    assert clock.monotonic() == 7.0
    assert clock.now() == START


def test_fake_wall_clock_jump_leaves_monotonic_untouched() -> None:
    """R-3-3: a wall-clock jump (NTP, manual change, DST elsewhere) must not move the monotonic clock."""
    clock = FakeClock(START, monotonic=12.0)
    for jump in (START - timedelta(hours=3), START + timedelta(days=1)):
        clock.set_wall(jump)
        assert clock.now() == jump
        assert clock.monotonic() == 12.0


def test_fake_clock_normalises_other_zones_to_beijing() -> None:
    utc = datetime(2026, 10, 17, 1, 30, tzinfo=UTC)
    clock = FakeClock(utc)
    assert clock.now() == START
    assert clock.now().utcoffset() == EIGHT_HOURS


def test_fake_clock_rejects_naive_wall_times() -> None:
    naive = START.replace(tzinfo=None)
    with pytest.raises(ValueError):
        FakeClock(naive)
    clock = FakeClock(START)
    with pytest.raises(ValueError):
        clock.set_wall(naive)
    assert clock.now() == START


def test_fake_clock_rejects_non_finite_monotonic_start() -> None:
    with pytest.raises(ValueError):
        FakeClock(START, monotonic=math.nan)


@pytest.mark.parametrize(
    ("wall", "monotonic", "step"),
    [
        (datetime.max.replace(tzinfo=BEIJING_TZ), 7.0, 1.0),  # wall clock already at the calendar limit
        (START, 7.0, 1e300),  # finite step far beyond the calendar range
    ],
)
def test_fake_clock_failed_advance_leaves_both_clocks_unchanged(wall: datetime, monotonic: float, step: float) -> None:
    """An advance that cannot be applied to both clocks is applied to neither (no half-updated state)."""
    clock = FakeClock(wall, monotonic=monotonic)
    with pytest.raises((OverflowError, ValueError)):
        clock.advance(step)
    assert clock.monotonic() == monotonic
    assert math.isfinite(clock.monotonic())
    assert clock.now() == wall
