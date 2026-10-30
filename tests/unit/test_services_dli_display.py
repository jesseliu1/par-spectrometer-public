"""par_app.services.dli_display: the copied display expressions of the frozen DliCanvas (PR #47 review N-3).

These pin what a mutation spot-check found uncovered. The expected texts and levels are read off ui.py
(DliCanvas._update_header colours, _layout_plot tick distances), not off the code under test. The stale term of the
state colour needs a hand-made summary: integrate() itself always turns a stale summary into 部分累计, but the copy
must keep the whole V1.0.3 expression, so it is locked here as a pure function.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from par_app.services import dli_display
from par_app.services.dli import STATE_INTEGRATING, DliSummary

pytestmark = [pytest.mark.unit, pytest.mark.spec("DLI-034 DLI-037 DLI-043 DLI-044 UI-183")]


def summary(**overrides: object) -> DliSummary:
    """A continuous one-hour summary (积分中, not stale, not paused); tests override single fields."""
    values: dict[str, object] = {
        "total": 1.0,
        "covered_seconds": 3600.0,
        "missing_seconds": 0.0,
        "coverage": 1.0,
        "first_valid": datetime(2026, 10, 18, 7, 0),
        "last_valid": datetime(2026, 10, 18, 8, 0),
        "integrated_until": datetime(2026, 10, 18, 8, 0),
        "head_seconds": 0.0,
        "internal_seconds": 0.0,
        "tail_seconds": 0.0,
        "cutoff": datetime(2026, 10, 18, 8, 0),
        "state": STATE_INTEGRATING,
        "stale": False,
        "paused": False,
    }
    values.update(overrides)
    return DliSummary(**values)  # type: ignore[arg-type]


def test_integrating_and_fresh_is_green() -> None:
    header = dli_display.header(summary())
    assert (header.state_text, header.state_level) == ("积分中", "ok")
    assert header.times_text == "首个有效：10-18 07:00:00　累计截至：10-18 08:00:00"


def test_stale_alone_turns_the_level_amber_like_v103() -> None:
    """ui.py _update_header: `summary['stale']` alone makes the colour #b45309 (amber), even when the state text
    is 积分中; the copied expression must keep that term (review N-3 survivor 3)."""
    header = dli_display.header(summary(stale=True, tail_seconds=150.0, cutoff=datetime(2026, 10, 18, 8, 2, 30)))
    assert header.state_text == "积分中 · 数据未更新（0时02分30秒）"
    assert header.state_level == "warn"


def test_newest_valid_time_is_shown_when_integration_stopped_earlier() -> None:
    """ui.py _update_header appends 最新有效 whenever last_valid differs from integrated_until (survivor 4)."""
    header = dli_display.header(summary(last_valid=datetime(2026, 10, 18, 9, 25)))
    assert header.times_text == "首个有效：10-18 07:00:00　累计截至：10-18 08:00:00　最新有效：10-18 09:25:00"


def test_inner_ticks_keep_two_hours_from_both_ends() -> None:
    """_layout_plot drops inner ticks closer than 7200 s to either end: a period starting 07:30 has no 09:00 tick
    (5400 s after the start) and no 06:00 tick the next day (5400 s before the end) (review N-3 survivor 5)."""
    start = datetime(2026, 10, 18, 7, 30)
    ticks = dli_display.axis_ticks(start, start + timedelta(days=1))
    wide = [tick.at for tick in ticks]
    assert wide == [
        start,
        datetime(2026, 10, 18, 12, 0),
        datetime(2026, 10, 18, 15, 0),
        datetime(2026, 10, 18, 18, 0),
        datetime(2026, 10, 18, 21, 0),
        datetime(2026, 10, 19, 0, 0),
        datetime(2026, 10, 19, 3, 0),
        start + timedelta(days=1),
    ]
    assert datetime(2026, 10, 18, 9, 0) not in wide and datetime(2026, 10, 19, 6, 0) not in wide
    narrow = [tick.at for tick in ticks if tick.narrow]
    assert narrow == [
        start,
        datetime(2026, 10, 18, 12, 0),
        datetime(2026, 10, 18, 18, 0),
        datetime(2026, 10, 19, 0, 0),
        start + timedelta(days=1),
    ]
