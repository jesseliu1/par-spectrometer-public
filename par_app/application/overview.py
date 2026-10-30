"""Read-only overview of one of the alpha's own device databases (实时概览; API-09; docs/design/ui-v2-pages.md 2.6;
issue #82). The page itself shows the live answer (live_overview.py) in tier 1; this one answers the same
question for /devices/{key}/latest.

MainWindow.refresh_overview (V1.0.3) is followed step by step on the database, through the same services:
  1. the newest record (recent_acquisitions(1)) and the newest successful record with a spectrum
     (latest_successful_spectrum; readonly.SnapshotOverview repeats both SQL statements);
  2. the status line of the shown record, or "最近采集失败 <time>" when only failures exist (UI-053..UI-055);
  3. the six KPI cards one card at a time (metrics.iter_overview_kpi_texts, #38): when a stored value cannot be
     formatted, the cards before it keep their text and the rest stay "—", exactly as V1.0.3 leaves them; then
     the core card, the spectrum, the 24 entries for the in-chart card and the hidden table.
What V1.0.3 does differently is decided as below (D-211, adopted as recommended under owner's standing approval of
2026-10-18; its snapshot parts superseded by issue #82):
  * "距今" is measured from the service clock now;
  * the poll cycle for "暂无新记录" (two cycles, at least 120 s) is the one the records hold
    (quality_json.poll_cycle_seconds of the shown record first; when it has none, the D-206 rule: the latest
    successful record by acquisition time; 60 s when that is missing too); "采集已暂停" shows while nothing
    acquires into the database (not taken over, maintenance or a halt; D-213);
  * a value that stops the KPI cards, the core card or the entries does not abort the answer: what V1.0.3 had
    already drawn when it raised is returned as it left it (cards before the bad value show their text, the rest
    "—"; the spectrum only when the failure came after it), and `metrics_error` says which record could not be
    read (R-1-5: no fake success). V1.0.3 raises out of refresh_overview at that point and logs it;
  * a spectrum that is not 701 numbers, or not valid JSON, is reported as "invalid" with no curve, and the KPI
    cards and the in-chart values of the record are still shown; V1.0.3 raises before drawing anything;
  * a non-finite entry (nan, inf) shows "—" in the in-chart card and the table (D-179, decided 2026-10-18).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np

from ..database import format_beijing_time
from ..domain.clock import Clock
from ..math_ops import WAVELENGTHS
from ..services import history as history_service
from ..services import metrics as metric_service
from ..services import overview_display as display
from .dli import PollCycle, poll_cycle, recorded_poll_cycle
from .history import Spectrum
from .own_devices import DeviceDatabase, OwnDevices
from .readonly import Row, SnapshotDli, SnapshotOverview
from .settings import LATEST_EVER

SOURCE_TEXT = "数据来自本机 2.0 采集的设备库；“距今”按本机当前时间计算"
POLL_CYCLE_SHOWN = (
    "超过 {stale_after:g} 秒无新记录时提示“暂无新记录”（显示记录 #{id} 中的轮询周期 {seconds:g} 秒 ×2，至少 120 秒）"
)
POLL_CYCLE_RECORDED = (
    "超过 {stale_after:g} 秒无新记录时提示“暂无新记录”"
    "（显示记录中没有可用的轮询周期，按库中 {recorded_at} 的采集记录中的 {seconds:g} 秒 ×2，至少 120 秒）"
)
POLL_CYCLE_DEFAULT = (
    "超过 {stale_after:g} 秒无新记录时提示“暂无新记录”"
    "（快照记录中没有可用的轮询周期，按默认 {seconds:g} 秒 ×2，至少 120 秒）"
)
METRICS_UNREADABLE = "记录 #{id} 的指标数据无法解析，指标只显示到出错之前"
SPECTRUM_POINTS = len(WAVELENGTHS)

SpectrumState = Literal["ok", "none", "invalid"]


@dataclass(frozen=True)
class PageTexts:
    """Fixed texts of the page (the copies in par_app.services.overview_display), gathered here so that the API layer
    never reads services itself (route C section 4, import contract "API layer reaches services only through the
    application layer"; same as settings_page.page_content)."""

    page_title: str
    summary_title: str
    summary_context: str
    details_button: str
    metrics_toggle: str
    spectrum_title: str
    x_label: str
    y_label: str
    empty_heading: str
    empty_detail: str
    invalid_spectrum: str
    details_columns: tuple[str, ...]
    details_close: str


PAGE_TEXTS = PageTexts(
    page_title=display.PAGE_TITLE,
    summary_title=display.SUMMARY_TITLE,
    summary_context=display.SUMMARY_CONTEXT,
    details_button=display.DETAILS_BUTTON,
    metrics_toggle=display.METRICS_TOGGLE,
    spectrum_title=display.SPECTRUM_TITLE,
    x_label=display.X_LABEL,
    y_label=display.Y_LABEL,
    empty_heading=display.EMPTY_HEADING,
    empty_detail=display.EMPTY_DETAIL,
    invalid_spectrum=display.INVALID_SPECTRUM,
    details_columns=tuple(display.DETAILS_COLUMNS),
    details_close=display.DETAILS_CLOSE,
)
X_TICKS = tuple(display.X_TICKS)
"""Wavelength ticks of the spectrum axis (V1.0.3 TICKS_WIDE)."""


@dataclass(frozen=True)
class Kpi:
    key: str
    title: str
    text: str


@dataclass(frozen=True)
class MetricsError:
    message: str
    detail: str


@dataclass(frozen=True)
class OverviewChart:
    title: str
    """The chart's title: "最新光谱" once a spectrum is drawn, else the empty chart's title (UI-054)."""
    spectrum_state: SpectrumState
    spectrum: Spectrum | None
    y_max: float | None
    overlay: list[list[tuple[str, str]]]


@dataclass(frozen=True)
class ShownRecord:
    """The record the page shows (UI-053) with its texts; `row` is the stored acquisitions row."""

    row: Row
    acquired_at_text: str
    age_seconds: float | None
    age_text: str
    exposure_text: str
    elapsed_text: str
    review_text: str
    details_title: str


@dataclass(frozen=True)
class Attempt:
    """The newest record by id, failed or not (UI-055: "本轮失败")."""

    row: Row
    acquired_at_text: str


@dataclass(frozen=True)
class Overview:
    device: DeviceDatabase
    snapshot_text: str
    shown: ShownRecord | None
    attempt: Attempt | None
    stale: bool | None
    poll_cycle: PollCycle
    stale_after_seconds: float
    poll_cycle_text: str
    status: display.StatusLine
    kpis: list[Kpi]
    core_metrics: list[tuple[str, str]]
    table: list[tuple[str, list[tuple[str, str]]]]
    chart: OverviewChart
    details_enabled: bool
    metrics_error: MetricsError | None


@dataclass(frozen=True)
class _Metrics:
    """What refresh_overview had produced from the record's metrics when it finished or raised."""

    kpis: dict[str, str]
    core: list[tuple[str, str]]
    secondary: list[tuple[str, str]]
    table: list[tuple[str, list[tuple[str, str]]]]
    drawn: bool
    """The spectrum is drawn after the KPI and core cards and before the entries."""
    error: MetricsError | None


def _spectrum(row: Row, raw: object) -> tuple[SpectrumState, Spectrum | None, np.ndarray | None]:
    """The plotted values raw / 10^coefficient (refresh_overview), or "invalid" when the stored text is not a JSON
    array of exactly 701 numbers (V1.0.3 raises on such a record)."""
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else None
    except (ValueError, RecursionError):
        decoded = None
    if (
        not isinstance(decoded, list)
        or len(decoded) != SPECTRUM_POINTS
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in decoded)
    ):
        return "invalid", None, None
    coefficient = row.get("spectral_coefficient")
    try:
        values = history_service.spectrum_values(decoded, coefficient)
    except (TypeError, ValueError, OverflowError):
        return "invalid", None, None
    spectrum = Spectrum(
        wavelength_start=history_service.SPECTRUM_START_NM,
        wavelength_step=history_service.SPECTRUM_STEP_NM,
        spectral_coefficient=coefficient,
        points=list(decoded),
        values=values,
    )
    return "ok", spectrum, np.asarray(values, dtype=float)


def _unreadable(row: Row, error: Exception) -> MetricsError:
    return MetricsError(METRICS_UNREADABLE.format(id=row["id"]), f"{type(error).__name__}: {error}")


def _metrics(row: Row) -> _Metrics:
    """KPI cards one at a time (#38), the core card, then the 24 entries; stops at the first value that cannot be
    read, keeping what was produced before it, as V1.0.3 leaves its page when refresh_overview raises."""
    kpis = {key: metric_service.EM_DASH for key, _title in display.KPI_TITLES}
    core: list[tuple[str, str]] = []
    drawn = False
    try:
        parameters, metrics = metric_service.decode_record_metrics(row)
        for key, text in metric_service.iter_overview_kpi_texts(metrics, parameters):
            kpis[key] = text  # one card at a time, as V1.0.3 sets them
        core = metric_service.overview_core_metrics(metrics, parameters)
        drawn = True
        entries = metric_service.overview_metric_entries(metrics, parameters)
        texts = [(label, display.entry_text(value)) for label, value in entries]
    except (TypeError, ValueError, AttributeError, OverflowError, RecursionError) as failure:
        return _Metrics(kpis, core, [], [], drawn, _unreadable(row, failure))
    secondary = [
        (label.replace(display.UNITLESS_SUFFIX, ""), text)
        for label, text in texts
        if label not in metric_service.OVERVIEW_FIXED_LABELS
    ]
    return _Metrics(kpis, core, secondary, display.table_groups(texts), drawn, None)


def _chart(row: Row, raw: object, found: _Metrics) -> OverviewChart:
    state, spectrum, values = _spectrum(row, raw)
    if not found.drawn or spectrum is None or values is None:
        return OverviewChart(
            display.NO_SPECTRUM_CHART_TITLE,
            state if found.drawn else "none",
            None,
            None,
            display.overlay_columns(found.secondary, found.core),
        )
    return OverviewChart(
        display.SPECTRUM_TITLE,
        state,
        spectrum,
        display.y_max(values),
        display.overlay_columns(found.secondary, found.core),
    )


def _kpis(texts: dict[str, str]) -> list[Kpi]:
    return [Kpi(key, title, texts[key]) for key, title in display.KPI_TITLES]


def _shown(row: Row, age: float | None) -> ShownRecord:
    time_text = format_beijing_time(row.get("acquired_at"))
    return ShownRecord(
        row=row,
        acquired_at_text=time_text,
        age_seconds=age,
        age_text=display.age_text(age),
        exposure_text=history_service.exposure_text(row),
        elapsed_text=history_service.elapsed_text(row),
        review_text=history_service.review_text(row),
        details_title=display.details_title(int(row["id"]), time_text),
    )


def source_text(_device: DeviceDatabase) -> str:
    return SOURCE_TEXT


def poll_cycle_text(cycle: PollCycle, stale_after: float, shown_id: int | None) -> str:
    if cycle.source != "record":
        return POLL_CYCLE_DEFAULT.format(stale_after=stale_after, seconds=cycle.seconds)
    if shown_id is not None:
        return POLL_CYCLE_SHOWN.format(stale_after=stale_after, id=shown_id, seconds=cycle.seconds)
    recorded_at = format_beijing_time(cycle.record_at) if cycle.record_at is not None else ""
    return POLL_CYCLE_RECORDED.format(stale_after=stale_after, recorded_at=recorded_at, seconds=cycle.seconds)


def overview_poll_cycle(shown: Row | None, snapshot_cycle: Callable[[], PollCycle]) -> tuple[PollCycle, int | None]:
    """D-211 question 2 (supplement): the shown record's own quality_json.poll_cycle_seconds first (the record whose
    age is judged); when it has no usable value, the D-206 pick (latest successful record by acquisition time, then
    the 60 s default). Returns the cycle and the shown record's id when the cycle came from it."""
    recorded = None if shown is None else recorded_poll_cycle(shown.get("quality_json"))
    if shown is not None and recorded is not None:
        return PollCycle(recorded, "record", str(shown["acquired_at"])), int(shown["id"])
    return snapshot_cycle(), None


@dataclass(frozen=True)
class _Context:
    device: DeviceDatabase
    latest: Row | None
    attempt: Attempt | None
    cycle: PollCycle
    stale_after: float
    cycle_from_shown: int | None


def _without_spectrum(context: _Context) -> Overview:
    """No successful record with a spectrum: empty chart, "—" cards, the failed-only status (UI-013, UI-054)."""
    attempt = context.attempt
    return Overview(
        device=context.device,
        snapshot_text=source_text(context.device),
        shown=None,
        attempt=attempt,
        stale=None,
        poll_cycle=context.cycle,
        stale_after_seconds=context.stale_after,
        poll_cycle_text=poll_cycle_text(context.cycle, context.stale_after, context.cycle_from_shown),
        status=display.EMPTY_STATUS if attempt is None else display.failed_status_line(attempt.acquired_at_text),
        kpis=_kpis({key: metric_service.EM_DASH for key, _title in display.KPI_TITLES}),
        core_metrics=[],
        table=[],
        chart=OverviewChart(
            display.NO_SPECTRUM_CHART_TITLE if attempt is None else display.FAILED_CHART_TITLE, "none", None, None, []
        ),
        details_enabled=False,
        metrics_error=None,
    )


def _with_record(context: _Context, row: Row, raw: object, now: datetime) -> Overview:
    shown = _shown(row, display.record_age(row, now))
    stale = display.is_stale(shown.age_seconds, context.cycle.seconds)
    found = _metrics(row)
    status = display.status_line(
        row,
        context.latest,
        shown.age_seconds,
        stale=stale,
        paused=context.device.paused,
        time_text=shown.acquired_at_text,
    )
    return Overview(
        device=context.device,
        snapshot_text=source_text(context.device),
        shown=shown,
        attempt=context.attempt,
        stale=stale,
        poll_cycle=context.cycle,
        stale_after_seconds=context.stale_after,
        poll_cycle_text=poll_cycle_text(context.cycle, context.stale_after, context.cycle_from_shown),
        status=status,
        kpis=_kpis(found.kpis),
        core_metrics=found.core,
        table=found.table,
        chart=_chart(row, raw, found),
        details_enabled=True,  # V1.0.3 enables 全部指标 before it writes the cards (UI-013)
        metrics_error=found.error,
    )


class OverviewQueries:
    def __init__(self, devices: OwnDevices, clock: Clock) -> None:
        self.devices = devices
        self.clock = clock

    def latest(self, key: str) -> Overview:
        device = self.devices.database_for(key)
        path = Path(device.path)
        database = SnapshotOverview(path)
        latest = database.latest()
        item = database.latest_successful()
        cycle, from_shown = overview_poll_cycle(
            None if item is None else item[0],
            lambda: poll_cycle(SnapshotDli(path).poll_cycle_record(LATEST_EVER, LATEST_EVER)),
        )
        attempt = None if latest is None else Attempt(latest, format_beijing_time(latest.get("acquired_at")))
        context = _Context(device, latest, attempt, cycle, display.stale_after(cycle.seconds), from_shown)
        if item is None:
            return _without_spectrum(context)
        row, raw = item
        return _with_record(context, row, raw, self.clock.now())
