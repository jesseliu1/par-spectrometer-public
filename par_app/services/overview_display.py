"""Display rules of the 实时概览 page for the ui-v2 local service (stage two, route C; ui-v2-pages.md 2.6).

These are copies, not moves: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2), so
the V1.0.x window keeps its own code and this module repeats the same texts and rules for the API. The metric
values themselves are not formatted here: the KPI cards, the core card and the 24 overview entries come from
par_app.services.metrics (#38 extracted them, the code V1.0.3 itself runs). tests/api/test_overview_parity.py runs
the V1.0.3 MainWindow and the API on the same database and compares every text, so the copies cannot drift apart.

Origin in par_app/ui.py (V1.0.3):
  MainWindow._build_overview (titles, KPI card titles, group titles)  -> the *_TITLE texts, KPI_TITLES, TABLE_GROUPS
  MainWindow._update_overview_status                                  -> record_age, age_text, is_stale, status_line
  MainWindow.refresh_overview (failed-only status, chart titles, overlay, table layout)
                                                                      -> failed_status_line, *_CHART_TITLE,
                                                                         overlay_columns, table_groups
  MainWindow._plot_selected_spectrum (x ticks, realtime y range)      -> X_TICKS, y_max
  SpectrumCanvas._draw_core_metrics_card (secondary or core card, columns)  -> overlay_columns
  MainWindow._show_overview_metric_details (dialog title and columns) -> details_title, DETAILS_COLUMNS
Deliberate difference (decided): entry_text shows a non-finite value as "—" (D-179, option 1, owner 2026-10-18,
"阶段二随新界面实现"); V1.0.3's format_entry_value, which the old window keeps, shows "nan"/"inf".
Not copied: colours (the page takes them from its design tokens, R-1-5) and the Matplotlib layout.

No clock is read here (R-1-6): the caller passes "now".
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import numpy as np

from ..domain.clock import BEIJING_TZ
from . import history as history_service
from .metrics import EM_DASH, format_entry_value
from .operation_display import TICKS_WIDE, spectrum_y_limits

JsonObject = Mapping[str, Any]
Row = tuple[str, str]
StatusLevel = Literal["ok", "warn", "error", "none"]

PAGE_TITLE = "实时概览"
"""UI-124: the page's name in the main navigation."""
SUMMARY_TITLE = "实时摘要"
SUMMARY_CONTEXT = "当前设备的最近一条有效采集记录"
DETAILS_BUTTON = "全部指标"
"""UI-009, UI-013."""
METRICS_TOGGLE = "显示指标"
"""UI-061: checked at start, not stored."""
SPECTRUM_TITLE = "最新光谱"
NO_SPECTRUM_CHART_TITLE = "当前设备暂无可显示光谱"
FAILED_CHART_TITLE = "最近采集失败，无新光谱"
"""UI-054: the chart titles refresh_overview gives the empty chart (no record at all / failures only)."""
EMPTY_HEADING = "暂无可显示的光谱"
EMPTY_DETAIL = "选择有效采集记录后将在此显示曲线"
INVALID_SPECTRUM = "光谱数据无法解析"
"""D-211 question 5: the shown record's spectrum JSON is unusable (V1.0.3 raises instead; same text as API-07)."""
"""SpectrumCanvas.plot defaults inside an empty chart."""
X_LABEL = "波长 (nm)"
Y_LABEL = "功率 (mW/nm)"
X_TICKS = TICKS_WIDE
"""_plot_selected_spectrum: set_xticks((350, 400, 500, …, 1000, 1050)), the same tuple as the calculation page's
wide charts; the overview is fixed to 350–1050 nm with no band choice (UI-057)."""
DETAILS_COLUMNS = ("指标", "数值", "单位")
"""_show_overview_metric_details: the dialog's columns; the rows are the history detail's 7 groups / 54 values."""
DETAILS_CLOSE = "关闭"

KPI_TITLES: tuple[tuple[str, str], ...] = (
    ("lux", "照度"),
    ("irradiance", "350–1050 nm 总辐照度"),
    ("ppfd", "PPFD"),
    ("ypfd", "McCree-YPFD"),
    ("chlorophyll_a_ypfd", "叶绿素 A 加权光子通量"),
    ("chlorophyll_b_ypfd", "叶绿素 B 加权光子通量"),
)
"""UI-012: the six summary cards in order; keys and order are those of metrics.OVERVIEW_KPI_SOURCES."""
TABLE_GROUPS = ("常用光量", "波段光子通量", "植物光谱配比", "光色与光谱特征")
TABLE_GROUP_SIZE = 6
"""refresh_overview fills the 6-row table column pair by column pair: entries 6·g … 6·g+5 belong to group g."""
UNITLESS_SUFFIX = "（无量纲）"
"""UI-059: dropped from the in-chart labels (ratios and indices keep their other units)."""
OVERLAY_COLUMN_BREAK = 8
"""UI-060: the in-chart card lists 8 band values on the left and the 12 others on the right."""

STATUS_SUCCESS = "采集成功"
STATUS_FAILED_ROUND = "本轮失败 · 保留最近有效数据"
"""UI-055."""
SUFFIX_PAUSED = " · 采集已暂停"
SUFFIX_STALE = " · 暂无新记录"
"""UI-171 and D-149: paused wins over stale."""
SUFFIX_SINGLE = " · 单次读取完成"
SUFFIX_UNREVIEWED = " · 复核未完成"
STATUS_TEMPLATE = "● {status}　显示 #{id}　{time}　{age}　曝光：{exposure}　耗时：{elapsed} ms"
FAILED_TEMPLATE = "最近采集失败　{time}"
"""UI-054: no successful spectrum yet, only failures."""
AGE_TEMPLATE = "距今 {age:.0f} 秒"
AGE_FUTURE = "记录时间晚于本机"
AGE_UNAVAILABLE = "记录时间不可用"
STALE_MINIMUM_SECONDS = 120.0
STALE_POLL_CYCLES = 2
"""UI-171: a record older than two poll cycles, and at least 120 s, is "暂无新记录"."""
FUTURE_TOLERANCE_SECONDS = 1.0
"""_update_overview_status: a record more than 1 s ahead of the clock is stale as well."""
ELAPSED_DEFAULT = 0
"""record.get('elapsed_ms', 0): a row without the column shows 0.0 ms."""
DETAILS_TITLE = "全部指标 · #{id} · {time}"


@dataclass(frozen=True)
class StatusLine:
    text: str
    level: StatusLevel
    """V1.0.3 colours: error = red (#dc2626), warn = amber (#b45309), ok = green (#16a34a); none = no status."""


EMPTY_STATUS = StatusLine("", "none")


def record_age(record: JsonObject, now: datetime) -> float | None:
    """Seconds from the record's acquired_at to `now` (aware); a plain time is Beijing time, a zone-suffixed one is
    read in its own zone. None when the time is missing or unreadable."""
    try:
        acquired = datetime.fromisoformat(record["acquired_at"])
        if acquired.tzinfo is None:
            acquired = acquired.replace(tzinfo=BEIJING_TZ)
        return (now - acquired).total_seconds()
    except (ValueError, TypeError, KeyError):
        return None


def age_text(age: float | None) -> str:
    """UI-170: '距今 N 秒', or '记录时间晚于本机' for a record ahead of the clock."""
    if age is None:
        return AGE_UNAVAILABLE
    return AGE_TEMPLATE.format(age=age) if age >= 0 else AGE_FUTURE


def stale_after(poll_cycle_seconds: float) -> float:
    return max(STALE_MINIMUM_SECONDS, poll_cycle_seconds * STALE_POLL_CYCLES)


def is_stale(age: float | None, poll_cycle_seconds: float) -> bool:
    """UI-171: older than two poll cycles (at least 120 s) or more than 1 s in the future; unreadable times too."""
    if age is None:
        return True
    return age > stale_after(poll_cycle_seconds) or age < -FUTURE_TOLERANCE_SECONDS


def _elapsed(record: JsonObject) -> str:
    value = record.get("elapsed_ms", ELAPSED_DEFAULT)
    try:
        return f"{value:.1f}"
    except (TypeError, ValueError):
        return EM_DASH  # not a number (impossible in V1.0.x's NOT NULL REAL column); V1.0.3 would raise


def status_line(
    record: JsonObject,
    latest: JsonObject | None,
    age: float | None,
    *,
    stale: bool,
    paused: bool,
    time_text: str,
) -> StatusLine:
    """The status line of the shown record (UI-055, UI-170, UI-171; UI-002 colours). `time_text` is the record's
    acquired_at through database.format_beijing_time (the caller formats it: services do not import storage)."""
    exposure = history_service.exposure_text(record)
    failed = latest is not None and not latest.get("success")
    status = STATUS_FAILED_ROUND if failed else STATUS_SUCCESS
    if paused:
        status += SUFFIX_PAUSED
    elif stale:
        status += SUFFIX_STALE
    single = history_service.is_single_capture(record)
    if single and record.get("success"):
        status += SUFFIX_SINGLE
    elif record.get("dli_eligible") == 0:
        status += SUFFIX_UNREVIEWED
    text = STATUS_TEMPLATE.format(
        status=status,
        id=record["id"],
        time=time_text,
        age=age_text(age),
        exposure=exposure,
        elapsed=_elapsed(record),
    )
    warn = (
        paused
        or stale
        or (not single and (exposure != history_service.EXPOSURE_NORMAL or record.get("dli_eligible") == 0))
    )
    return StatusLine(text, "error" if failed else "warn" if warn else "ok")


def failed_status_line(time_text: str) -> StatusLine:
    """UI-054: the latest record's time (database.format_beijing_time) when no successful spectrum exists."""
    return StatusLine(FAILED_TEMPLATE.format(time=time_text), "error")


def entry_text(value: float | str | None) -> str:
    """Overview table / in-chart text of one entry: format_entry_value, except that a non-finite number shows "—"
    (D-179 option 1) instead of "nan"/"inf"."""
    if isinstance(value, str) or value is None:
        return format_entry_value(value)
    return EM_DASH if not math.isfinite(float(value)) else format_entry_value(value)


def overlay_columns(secondary: Sequence[Row], core: Sequence[Row]) -> list[list[Row]]:
    """The in-chart card as SpectrumCanvas._draw_core_metrics_card draws it: the secondary rows split after
    OVERLAY_COLUMN_BREAK (UI-060), or, while there are none, the core card's rows alternating between two columns."""
    if secondary:
        return [list(secondary[:OVERLAY_COLUMN_BREAK]), list(secondary[OVERLAY_COLUMN_BREAK:])]
    if core:
        return [list(core[::2]), list(core[1::2])]
    return []


def table_groups(entries: Iterable[Row]) -> list[tuple[str, list[Row]]]:
    """The 24 entries as the overview table holds them: four titled groups of six."""
    rows = list(entries)
    return [
        (title, rows[index * TABLE_GROUP_SIZE : (index + 1) * TABLE_GROUP_SIZE])
        for index, title in enumerate(TABLE_GROUPS)
    ]


def y_max(values: np.ndarray) -> float:
    """Top of the y axis the first time a spectrum is drawn (_plot_selected_spectrum with realtime=True): the upper
    limit SpectrumCanvas.plot gives the spectrum, from 0 (UI-175: the axis grows at once). The later shrink rule
    (UI-174, 30 s and a new record) needs a stream of records and does not apply to a snapshot."""
    return spectrum_y_limits(values)[1]


def details_title(record_id: int, time_text: str) -> str:
    """UI-009: the "全部指标" dialog title of the shown record."""
    return DETAILS_TITLE.format(id=record_id, time=time_text)
