"""ParModbusClient._delay on an injected FakeClock always ends (R-3-3, R-1-6).

`_delay(seconds)` waits until `monotonic() >= start + seconds` in slices of at most 0.02 s. When `start + seconds`
is not a whole nanosecond, the last remainder can be below the FakeClock's 1 ns resolution; if such a sleep did
not move the clock, the loop would spin forever instead of failing. The (start, delay) pairs below are the ones an
independent review found spinning; the sleep counter turns a regression into a failure instead of a hang.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_app.models import ConnectionConfig
from par_app.protocol import ParModbusClient

pytestmark = pytest.mark.unit

MAX_SLEEPS = 10_000  # a 1.12 s delay needs 57 slices of 0.02 s; anything near this bound is a spin


class _CountingClock(FakeClock):
    def __init__(self, monotonic: float) -> None:
        super().__init__(datetime(2026, 9, 18, tzinfo=BEIJING_TZ), monotonic=monotonic)
        self.sleeps = 0

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.sleeps > MAX_SLEEPS:
            raise AssertionError(f"_delay spun {self.sleeps} times at monotonic {self.monotonic()!r}")
        super().sleep(seconds)


@pytest.mark.parametrize(("start", "delay"), [(4.69, 0.15), (1.45, 1.12), (0.0, 0.1), (600.0, 0.05)])
def test_delay_on_fake_clock_ends_after_the_requested_time(start: float, delay: float) -> None:
    clock = _CountingClock(start)
    client = ParModbusClient(ConnectionConfig(), clock=clock)
    client._delay(delay)
    assert clock.monotonic() >= start + delay
    assert clock.monotonic() - (start + delay) < 1e-6
    assert clock.sleeps <= delay / 0.02 + 3
