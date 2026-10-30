"""Display rules of the DLI page (光积累计算) for the ui-v2 local service (stage two, route C).

These are copies, not moves: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2), so
the V1.0.x window keeps its own code and this module repeats the same texts for the API. The numbers themselves
(totals, coverage, state) are not computed here: they come from par_app.services.dli.integrate, the code V1.0.3
itself runs. tests/api/test_dli_parity.py runs the V1.0.3 MainWindow and the API on the same database and compares
every text, so the two copies cannot drift apart unnoticed.

Origin in par_app/ui.py (V1.0.3):
  MainWindow.refresh_diagnostics (chart list, period label, tooltip) -> METRIC_TITLES, period_text, location_text
  DliCanvas._duration                                              -> duration_text
  DliCanvas._update_header                                         -> header
  DliCanvas.plot_dli (y limit)                                     -> y_axis_max
  DliCanvas._layout_plot (x ticks)                                 -> axis_ticks
Not copied: the chart colours (the web page takes them from its design tokens, R-1-5) and the midnight label
staggering of _layout_plot (UI-185), which depends on rendered label widths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from .dli import DLI_METRICS, STATE_PARTIAL, DliSummary

METRIC_TITLES: dict[str, str] = dict(
    zip(
        DLI_METRICS,
        ("PPFD-DLI（400–700 nm）", "McCree YPFD-DLI", "叶绿素 A 加权日光积分", "叶绿素 B 加权日光积分"),
        strict=True,
    )
)
"""Chart titles in chart order, as MainWindow.refresh_diagnostics passes them to plot_dli."""
EM_DASH = "—"
UNIT = "mol·m⁻²"
PAUSED_SUFFIX = " · 采集已暂停"
Y_AXIS_HEADROOM = 1.15
"""plot_dli: the y axis ends 15 % above the total ..."""
Y_AXIS_MINIMUM_TOP = 0.001
"""... and never below 0.001 mol·m⁻², so an all-zero curve still has an axis (UI-184: the axis starts at 0)."""
TICK_HOURS_WIDE = 3
TICK_HOURS_NARROW = 6
"""_layout_plot: an inner tick every 3 h on a chart at least 700 px wide, else every 6 h (UI-183)."""
TICK_MIN_DISTANCE_SECONDS = 7200
"""_layout_plot: inner ticks closer than 2 h to either end are left out."""

StateLevel = Literal["ok", "warn", "muted"]


@dataclass(frozen=True)
class DliHeader:
    """The texts above one DLI chart (UI-180, UI-181, DLI-034..037, DLI-043, DLI-044, DLI-053)."""

    total_text: str
    state_text: str
    state_level: StateLevel
    """V1.0.3 colours: muted grey without coverage, amber when partial, paused or stale, otherwise green."""
    times_text: str
    coverage_text: str
    coverage_tooltip: str


@dataclass(frozen=True)
class AxisTick:
    at: datetime
    text: str
    narrow: bool
    """Also a tick when the chart is narrower than 700 px (6 h spacing); False: only on wide charts (3 h)."""


def period_text(start: datetime, end: datetime) -> str:
    return f"积分周期：{start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M}（北京时间，日出起算，固定24小时）"


def coordinates_text(location: tuple[float, float]) -> str:
    latitude, longitude = location
    return f"纬度 {latitude:.4f} °N，经度 {longitude:.4f} °E"


def location_text(location: tuple[float, float], enabled_at_text: str) -> str:
    """Tooltip of the period line; `enabled_at_text` is format_beijing_time of the enable time."""
    return f"已保存位置：{coordinates_text(location)}\nDLI启用时间：{enabled_at_text}"


def duration_text(seconds: float) -> str:
    minutes, remaining = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}时{minutes:02d}分{remaining:02d}秒"


def _clock(moment: datetime | None) -> str:
    return moment.strftime("%m-%d %H:%M:%S") if moment else EM_DASH


def _state(summary: DliSummary) -> tuple[str, StateLevel]:
    state = summary.state
    if summary.paused:
        state = (STATE_PARTIAL if summary.covered_seconds > 0 else state) + PAUSED_SUFFIX
    if summary.stale:
        state += f" · 数据未更新（{duration_text(summary.tail_seconds)}）"
    level: StateLevel = "warn" if summary.paused or summary.stale or summary.state == STATE_PARTIAL else "ok"
    if summary.covered_seconds == 0:
        level = "muted"
    return state, level


def header(summary: DliSummary) -> DliHeader:
    total = f"{summary.total:.3f}" if summary.covered_seconds > 0 else EM_DASH
    state, level = _state(summary)
    times = f"首个有效：{_clock(summary.first_valid)}　累计截至：{_clock(summary.integrated_until)}"
    if summary.last_valid != summary.integrated_until:
        times += f"　最新有效：{_clock(summary.last_valid)}"
    coverage = (
        f"有效 {duration_text(summary.covered_seconds)}　未覆盖 {duration_text(summary.missing_seconds)}"
        f"　覆盖率 {summary.coverage:.1%}"
    )
    tooltip = (
        f"截至 {summary.cutoff:%Y-%m-%d %H:%M:%S}（北京时间）\n"
        f"起始未覆盖：{duration_text(summary.head_seconds)}\n"
        f"内部未覆盖：{duration_text(summary.internal_seconds)}\n"
        f"尾部未覆盖：{duration_text(summary.tail_seconds)}"
    )
    return DliHeader(f"已累计：{total} {UNIT}", state, level, times, coverage, tooltip)


def y_axis_max(total: float) -> float:
    return max(total * Y_AXIS_HEADROOM, Y_AXIS_MINIMUM_TOP)


def _ticks(start: datetime, end: datetime, hours: int) -> list[datetime]:
    ticks = [start]
    midnight = datetime.combine(start.date() + timedelta(days=1), datetime.min.time())
    candidate = datetime.combine(start.date(), datetime.min.time())
    while candidate < end:
        distance = min((candidate - start).total_seconds(), (end - candidate).total_seconds())
        if start < candidate < end and distance >= TICK_MIN_DISTANCE_SECONDS:
            ticks.append(candidate)
        candidate += timedelta(hours=hours)
    if start < midnight < end and midnight not in ticks:
        ticks.append(midnight)
    return sorted([*ticks, end])


def axis_ticks(start: datetime, end: datetime) -> list[AxisTick]:
    """X-axis ticks of a period: both ends and the midnight inside it show month-day and time, the others the
    time only (UI-183)."""
    midnight = datetime.combine(start.date() + timedelta(days=1), datetime.min.time())
    narrow = set(_ticks(start, end, TICK_HOURS_NARROW))
    return [
        AxisTick(
            stamp,
            stamp.strftime("%m-%d\n%H:%M") if stamp in (start, end, midnight) else stamp.strftime("%H:%M"),
            stamp in narrow,
        )
        for stamp in _ticks(start, end, TICK_HOURS_WIDE)
    ]
