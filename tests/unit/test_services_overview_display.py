"""Display rules of the overview page copied from ui.py (par_app/services/overview_display.py).

Expected values are written out by hand from the rules (UI-012, UI-055, UI-059, UI-060, UI-170, UI-171; D-179);
tests/api/test_overview_parity.py separately compares the copies with the running V1.0.3 window.
"""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pytest

from par_app.domain.clock import BEIJING_TZ
from par_app.services import overview_display as display

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("UI-012 UI-053 UI-054 UI-055 UI-059 UI-060 UI-170 UI-171 UI-174 UI-175"),
]
NOW = datetime(2026, 10, 18, 9, 30, 0, tzinfo=BEIJING_TZ)
SINGLE = json.dumps({"strategy": "single_capture"})
T = "2026-10-18 09:29:00.000"
NAN = float("nan")
INF = float("inf")


def _record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 7,
        "success": 1,
        "acquired_at": "2026-10-18T09:29:00.000",
        "exposure_status": 0,
        "elapsed_ms": 5464.66,
        "quality_json": SINGLE,
        "dli_eligible": 1,
    }
    base.update(overrides)
    return base


def test_kpi_cards_in_the_v1_order_with_their_titles() -> None:
    assert [key for key, _title in display.KPI_TITLES] == [
        "lux",
        "irradiance",
        "ppfd",
        "ypfd",
        "chlorophyll_a_ypfd",
        "chlorophyll_b_ypfd",
    ]
    assert dict(display.KPI_TITLES)["irradiance"] == "350–1050 nm 总辐照度"
    assert dict(display.KPI_TITLES)["chlorophyll_b_ypfd"] == "叶绿素 B 加权光子通量"


def test_age_text_and_stale() -> None:
    assert display.record_age(_record(), NOW) == pytest.approx(60.0)
    assert display.age_text(60.4) == "距今 60 秒"
    assert display.age_text(0.0) == "距今 0 秒"
    assert display.age_text(-0.5) == "记录时间晚于本机"
    assert display.age_text(None) == "记录时间不可用"
    # UI-171: two poll cycles, at least 120 s; a record more than 1 s in the future is stale too
    assert display.stale_after(30.0) == 120.0
    assert display.stale_after(300.0) == 600.0
    assert display.is_stale(120.0, 60.0) is False
    assert display.is_stale(120.5, 60.0) is True
    assert display.is_stale(-1.0, 60.0) is False
    assert display.is_stale(-1.5, 60.0) is True
    assert display.is_stale(None, 60.0) is True


def test_record_age_reads_naive_times_as_beijing_and_keeps_zoned_ones() -> None:
    assert display.record_age(_record(acquired_at="2026-10-18T01:29:00+00:00"), NOW) == pytest.approx(60.0)
    assert display.record_age(_record(acquired_at="not a time"), NOW) is None
    assert display.record_age(_record(acquired_at=None), NOW) is None
    assert display.record_age({"id": 1}, NOW) is None


def test_status_line_of_a_fresh_single_capture() -> None:
    record = _record()
    line = display.status_line(record, record, 60.0, stale=False, paused=False, time_text=T)
    assert (
        line.text
        == "● 采集成功 · 单次读取完成　显示 #7　2026-10-18 09:29:00.000　距今 60 秒　曝光：正常　耗时：5464.7 ms"
    )
    assert line.level == "ok"


def test_status_line_failed_round_keeps_the_shown_record() -> None:
    record = _record(exposure_status=2)
    latest = {"id": 8, "success": 0}
    line = display.status_line(record, latest, 700.0, stale=True, paused=False, time_text=T)
    assert line.text.startswith("● 本轮失败 · 保留最近有效数据 · 暂无新记录 · 单次读取完成　显示 #7")
    assert "曝光：欠曝光" in line.text
    assert line.level == "error"


def test_status_line_levels_of_old_records() -> None:
    old = _record(quality_json=None, exposure_status=1)
    assert (
        display.status_line(old, old, 10.0, stale=False, paused=False, time_text=T).level == "warn"
    )  # UI-002: old record
    unreviewed = _record(quality_json=json.dumps({"confirmed": False}), dli_eligible=0)
    line = display.status_line(unreviewed, unreviewed, 10.0, stale=False, paused=False, time_text=T)
    assert "· 复核未完成" in line.text and line.level == "warn"
    single_under = _record(exposure_status=2)
    assert display.status_line(single_under, single_under, 10.0, stale=False, paused=False, time_text=T).level == "ok"
    paused = display.status_line(single_under, single_under, 900.0, stale=True, paused=True, time_text=T)
    assert "· 采集已暂停" in paused.text and "暂无新记录" not in paused.text and paused.level == "warn"


def test_status_line_elapsed_missing_and_odd() -> None:
    record = _record()
    del record["elapsed_ms"]
    assert display.status_line(record, None, 1.0, stale=False, paused=False, time_text=T).text.endswith("耗时：0.0 ms")
    odd = _record(elapsed_ms="slow")
    assert display.status_line(odd, None, 1.0, stale=False, paused=False, time_text=T).text.endswith("耗时：— ms")


def test_failed_only_and_empty_status() -> None:
    line = display.failed_status_line("2026-10-18 09:00:00.000")
    assert (line.text, line.level) == ("最近采集失败　2026-10-18 09:00:00.000", "error")
    assert (display.EMPTY_STATUS.text, display.EMPTY_STATUS.level) == ("", "none")


def test_entry_text_shows_non_finite_values_as_a_dash() -> None:
    """D-179 (decided 2026-10-18: option 1, implemented with the new UI): nan/inf read "—" like the KPI cards."""
    assert display.entry_text(NAN) == "—"
    assert display.entry_text(INF) == "—"
    assert display.entry_text(-INF) == "—"
    assert display.entry_text(None) == "—"
    assert display.entry_text("6992") == "6992"
    assert display.entry_text(1.17949) == "1.179"
    assert display.entry_text(0) == "0.000"


def test_overlay_rows_take_the_secondary_metrics_or_else_the_core_card() -> None:
    secondary = [(f"s{index}", "1.000") for index in range(20)]
    core = [("照度（lx）", "1.0"), ("b", "2"), ("c", "3"), ("d", "4")]
    columns = display.overlay_columns(secondary, core)
    assert [len(column) for column in columns] == [8, 12]  # UI-060: 8 band values left, 12 on the right
    assert columns[0][0] == ("s0", "1.000") and columns[1][0] == ("s8", "1.000")
    assert display.overlay_columns([], core) == [[core[0], core[2]], [core[1], core[3]]]
    assert display.overlay_columns([], []) == []


def test_table_groups_six_entries_each() -> None:
    entries = [(f"e{index}", str(index)) for index in range(24)]
    groups = display.table_groups(entries)
    assert [title for title, _ in groups] == ["常用光量", "波段光子通量", "植物光谱配比", "光色与光谱特征"]
    assert [len(rows) for _, rows in groups] == [6, 6, 6, 6]
    assert groups[3][1][5] == ("e23", "23")


def test_y_max_puts_the_peak_at_0_618_and_never_below_the_negative_padding() -> None:
    values = np.zeros(701)
    values[100] = 0.618
    assert display.y_max(values) == pytest.approx(1.0)
    negative = np.linspace(-1.0, 1.0, 701)
    assert display.y_max(negative) == pytest.approx(1.0 + 2.0 * 0.08)
    assert display.y_max(np.full(701, NAN)) == pytest.approx(1.0 / 0.618)
    assert display.y_max(np.zeros(701)) == pytest.approx(1e-9)


def test_axis_ticks_and_texts() -> None:
    assert display.X_TICKS == (350, 400, 500, 600, 700, 800, 900, 1000, 1050)
    assert display.details_title(7, "2026-10-18 09:29:00.000") == "全部指标 · #7 · 2026-10-18 09:29:00.000"
    assert display.STALE_MINIMUM_SECONDS == 120.0
