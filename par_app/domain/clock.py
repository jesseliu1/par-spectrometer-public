"""Time sources for product code (R-1-6).

Product code reads time only through a `Clock`: `SystemClock` in production, `FakeClock` in tests.
Two clocks are kept apart on purpose:
  * `monotonic()` measures durations, budgets and timeouts. It never jumps and has no calendar meaning.
  * `now()` is the business wall clock: an aware datetime in Beijing time (UTC+8), independent of the host
    time zone. It may jump (NTP, manual change) and must not be used to measure durations.
`sleep()` waits on the same clock that `monotonic()` reads, so a FakeClock moves when the code under test waits.
"Never happened" is `None`, not a 0.0 sentinel (old repository issue #5).

internal notes section 2: step 1 added these types; step 2 switched
`par_app.coordinator` and `par_app.protocol` to an injected Clock. `par_app/ui.py` (deferred to the UI refactor)
and `par_app.database` (`beijing_now`, and its own `BEIJING_TZ` for the same zone) still read the time directly.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

BEIJING_UTC_OFFSET_HOURS = 8  # hours; business time zone for every stored and displayed time (UTC+8, no DST)
BEIJING_TZ = timezone(timedelta(hours=BEIJING_UTC_OFFSET_HOURS), name="CST")


@runtime_checkable
class Clock(Protocol):
    """Where product code gets the time from."""

    def monotonic(self) -> float:
        """Seconds on a clock that never goes backwards; only differences are meaningful."""
        ...

    def now(self) -> datetime:
        """Current business wall time: aware datetime in Beijing time."""
        ...

    def sleep(self, seconds: float) -> None:
        """Block for `seconds` of monotonic time."""
        ...


class SystemClock:
    """The real clocks of this process."""

    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(BEIJING_TZ)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def _beijing(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FakeClock needs an aware datetime; naive times are ambiguous about their zone")
    return value.astimezone(BEIJING_TZ)


def _finite(value: float, what: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return value


NANOSECONDS_PER_SECOND = 1_000_000_000  # FakeClock resolution: steps are rounded to whole nanoseconds
NANOSECONDS_PER_MICROSECOND = 1_000  # FakeClock wall clock: datetime resolution is one microsecond


def _nanoseconds(seconds: float) -> int:
    return round(seconds * NANOSECONDS_PER_SECOND)


def _step_nanoseconds(seconds: float) -> int:
    """Length of a forward step: rounded to whole nanoseconds, but never 0 for a positive step.

    A wait loop such as `while monotonic() < until: sleep(until - monotonic())` can be left with a remainder
    below 0.5 ns when `until` is not a whole nanosecond; rounding that to 0 would never move the clock and the
    loop would spin forever instead of finishing.
    """
    nanoseconds = _nanoseconds(seconds)
    return max(1, nanoseconds) if seconds > 0 else nanoseconds


class FakeClock:
    """Virtual clock for tests (R-3-3): time moves only when the code calls `sleep` or the test calls `advance`
    or `set_wall`.

    Monotonic time is kept in whole nanoseconds, so thousands of 0.02 s waits add up to exactly 40.0 instead of
    drifting by float rounding; tests can compare deadlines and cycle starts with `==`. Every positive step moves
    it by at least 1 ns, so waiting out a sub-nanosecond remainder still ends. The wall clock takes the same
    whole-nanosecond steps, counted from the last `set_wall`, and shows the last whole microsecond passed (a
    datetime holds microseconds; `datetime.now()` also rounds down), so many sub-microsecond waits still add up.
    """

    def __init__(self, wall: datetime, monotonic: float = 0.0) -> None:
        self._wall_origin = _beijing(wall)
        self._wall_elapsed_ns = 0
        self._monotonic_ns = _nanoseconds(_finite(monotonic, "monotonic start"))

    def monotonic(self) -> float:
        return self._monotonic_ns / NANOSECONDS_PER_SECOND

    def now(self) -> datetime:
        return self._wall_after(self._wall_elapsed_ns)

    def _wall_after(self, elapsed_ns: int) -> datetime:
        return self._wall_origin + timedelta(microseconds=elapsed_ns // NANOSECONDS_PER_MICROSECOND)

    def sleep(self, seconds: float) -> None:
        """A wait in the code under test: returns at once, `seconds` later on both clocks."""
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        """Let `seconds` pass on both clocks. Negative or non-finite steps are refused.

        Both new values are computed before either is stored, so a step that overflows the calendar
        (OverflowError) or the float range (ValueError/OverflowError) leaves both clocks unchanged.
        """
        _finite(seconds, "advance step")
        if seconds < 0:
            raise ValueError(f"monotonic time cannot go backwards, got {seconds!r} s")
        step_ns = _step_nanoseconds(seconds)
        new_wall_elapsed_ns = self._wall_elapsed_ns + step_ns
        self._wall_after(new_wall_elapsed_ns)  # raises OverflowError past the calendar range
        new_monotonic_ns = self._monotonic_ns + step_ns
        _finite(new_monotonic_ns / NANOSECONDS_PER_SECOND, "monotonic time after advance")
        self._monotonic_ns = new_monotonic_ns
        self._wall_elapsed_ns = new_wall_elapsed_ns

    def set_wall(self, wall: datetime) -> None:
        """Jump the wall clock (either direction) without moving the monotonic clock."""
        self._wall_origin = _beijing(wall)
        self._wall_elapsed_ns = 0
