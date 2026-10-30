"""Virtual clock for deadline tests (R-3-3, R-1-6).

Tests inject `virtual_clock()` into the objects under test (`PollingCoordinator(..., clock=clock)`,
`ParModbusClient(config, clock=clock)`), so budgets and timeouts advance instantly and deterministically.
This replaces the old test-only `Clock` (migrated from verify_polling.py lines 22-30), which tests patched in
as `par_app.protocol.time.monotonic` / `time.sleep`. That patch replaced the shared `time` module attributes,
so it reached the coordinator and the bus client alike; injecting the same FakeClock into both keeps that.
FakeClock counts whole nanoseconds, as the old `round(.., 9)` did, and every positive sleep moves it by at
least 1 ns, so a `_delay` loop with a sub-nanosecond remainder still ends.
"""

from __future__ import annotations

import time
from datetime import datetime

from par_app.domain.clock import BEIJING_TZ, FakeClock


def virtual_clock() -> FakeClock:
    """FakeClock whose monotonic time starts at 0 and moves only when the code or the test sleeps."""
    return FakeClock(datetime(2026, 9, 18, tzinfo=BEIJING_TZ))


class YieldingClock(FakeClock):
    """FakeClock for a coordinator that runs on its own QThread: every sleep also yields the GIL (time.sleep(0)), so
    an idle loop that only sleeps on the virtual clock does not starve the Qt main thread. Virtual time, and so
    every frame and its send time, is exactly as with FakeClock."""

    def sleep(self, seconds: float) -> None:
        super().sleep(seconds)
        time.sleep(0)


def yielding_clock() -> YieldingClock:
    return YieldingClock(datetime(2026, 9, 18, tzinfo=BEIJING_TZ))
