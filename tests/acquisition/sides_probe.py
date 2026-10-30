"""A probe side module for the time budgets of the parity runs (#66, review rv-70e); not a parity test.

Not collected by default (sides_*.py). tests/acquisition/test_takeover_parity.py runs it through run_sides, or as its
own pytest session, with PROBE_* set: PROBE_COUNT tests per side, each sleeping PROBE_SLEEP seconds (slow but
progressing); PROBE_FIXTURE_SLEEP puts that much sleep into one module fixture (the parent's `recorded` fixture runs
every side inside one test's setup); PROBE_STUCK makes the first test never end."""

from __future__ import annotations

import os
import time

import pytest

from tests.support.parity_sides import record

pytestmark = pytest.mark.watchdog(seconds=float(os.environ.get("PROBE_WATCHDOG", "0")) or None)
COUNT = int(os.environ.get("PROBE_COUNT", "0"))
SLEEP = float(os.environ.get("PROBE_SLEEP", "0"))
FIXTURE_SLEEP = float(os.environ.get("PROBE_FIXTURE_SLEEP", "0"))
STUCK = bool(os.environ.get("PROBE_STUCK"))


@pytest.fixture(scope="module")
def slow_setup() -> None:
    time.sleep(FIXTURE_SLEEP)


@pytest.mark.parametrize("index", range(COUNT))
@pytest.mark.parametrize("side", [pytest.param("V1.0.3", marks=pytest.mark.qt_binding("PyQt5")), "alpha"])
def test_side(side: str, index: int, slow_setup: None) -> None:
    if STUCK:
        time.sleep(3600)
    time.sleep(SLEEP)
    record(f"{side}-{index}", {"index": index})
