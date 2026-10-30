"""DLI computation: sunrise, integration period, row eligibility, trapezoid integration, coverage and state.

Moved unchanged out of par_app/ui.py (R-8-1 stage one "logic extraction"; MainWindow and DliCanvas keep thin
wrappers with unchanged signatures):
  MainWindow._sunrise                     -> sunrise
  MainWindow._dli_period                  -> dli_period (the caller passes "now"; R-1-6)
  MainWindow.refresh_diagnostics (inline) -> DLI_METRICS, max_gap_seconds, build_series
  DliCanvas.plot_dli (computation part)   -> integrate (returns the summary and the plotted cumulative series)
Specs: see the 代码锚点 of DLI-001/008/011/012/015/018/022/028/029/030/033/038/040/046/047/048/051 and the
others listed in docs/spec/ui-migration-tracker.md. Rules and states are V1.0.2 status quo; known quirks are
reported for separate fix PRs, not changed here. Fixes that landed on the moved code during the release/v1.0.3
integration: dli_period picks the latest sunrise at or before now (PR #26, DLI-015) and _accumulate zips with
strict=True (PR #28, refs #2).

No clock is read here: the UI passes the Beijing wall-clock time it read before (R-1-6). No database is read:
the UI passes the rows of ParDatabase.dli_samples (services contract in pyproject.toml).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

# Metrics integrated on the DLI page, in chart order (software_metrics_json keys).
DLI_METRICS = ("ppfd", "mccree_ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd")
MIN_MAX_GAP_SECONDS = 120.0
"""Two samples further apart than the max gap are not bridged (DLI-010): at least 120 s ..."""
POLL_CYCLE_GAP_MARGIN_SECONDS = 60.0
"""... or one effective poll cycle plus 60 s, whichever is larger."""

STATE_INTEGRATING = "积分中"
STATE_PARTIAL = "部分累计"
STATE_NO_DATA = "有效数据不足"


@dataclass(frozen=True)
class DliSummary:
    """Per-chart DLI summary; field order is the key order of the dict the canvas exposes as dli_summary."""

    total: float
    covered_seconds: float
    missing_seconds: float
    coverage: float
    first_valid: datetime | None
    last_valid: datetime | None
    integrated_until: datetime | None
    head_seconds: float
    internal_seconds: float
    tail_seconds: float
    cutoff: datetime
    state: str
    stale: bool
    paused: bool

    def as_dict(self) -> dict[str, object]:
        """The summary as the dict DliCanvas has always exposed (same keys, same values, same order)."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True)
class DliIntegration:
    """Summary plus the series the chart draws, both from the same pass so the curve matches the totals.

    `cumulative` holds the running total in mol·m⁻² at each `plot_times` entry; NaN marks a break (invalid
    sample or a gap longer than the max gap), which the chart draws as an interruption."""

    summary: DliSummary
    plot_times: list[datetime]
    cumulative: list[float]


def sunrise(local_day: date, latitude: float, longitude: float) -> datetime:
    """NOAA 近似日出时刻；采用北京时间 UTC+8，不依赖网络服务。"""
    day_number = local_day.timetuple().tm_yday
    gamma = 2 * np.pi / 365 * (day_number - 1)
    equation = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    cos_hour_angle = np.cos(np.deg2rad(90.833)) / (np.cos(np.deg2rad(latitude)) * np.cos(declination)) - np.tan(
        np.deg2rad(latitude)
    ) * np.tan(declination)
    hour_angle = np.rad2deg(np.arccos(np.clip(cos_hour_angle, -1.0, 1.0)))
    minutes = 720 - 4 * (longitude + hour_angle) - equation + 480
    return datetime.combine(local_day, datetime.min.time()) + timedelta(minutes=float(minutes))


def dli_period(now: datetime, location: tuple[float, float]) -> tuple[datetime, datetime]:
    """24 h period starting at the latest sunrise at or before now (DLI-015, D-165; PR #26, old audit #23).

    `now` is naive Beijing wall-clock time read by the caller. sunrise() converts with a fixed UTC+8 offset, so
    far from 120°E the sunrise "of day d" lands on d-1..d+1; the candidates are days d-2..d+1. V1.0.2 chose only
    between today's and yesterday's sunrise (unchanged for domestic longitudes). When no candidate is at or before
    now (a corrupt stored longitude) the V1.0.2 choice, yesterday's sunrise, is kept instead of raising (R-6-3)."""
    latitude, longitude = location
    sunrises = [sunrise(now.date() + timedelta(days=k), latitude, longitude) for k in (-2, -1, 0, 1)]
    start = max((s for s in sunrises if s <= now), default=sunrises[1])
    return start, start + timedelta(days=1)


def max_gap_seconds(effective_poll_cycle_seconds: float) -> float:
    """Longest interval that is still integrated: max(120 s, effective poll cycle + 60 s)."""
    return max(MIN_MAX_GAP_SECONDS, effective_poll_cycle_seconds + POLL_CYCLE_GAP_MARGIN_SECONDS)


# A row of ParDatabase.dli_samples: timestamp, software_metrics_json, eligible. Values are passed on as stored;
# Any is deliberate (R-1-3) so old and odd rows behave exactly as they did inside the UI.
SampleRow = Mapping[str, Any]


def build_series(
    rows: Iterable[SampleRow], metrics: Sequence[str] = DLI_METRICS
) -> tuple[dict[str, list[datetime]], dict[str, list[float]]]:
    """Per-metric (timestamps, values) from sample rows, in row order.

    A row whose timestamp does not parse is skipped. An ineligible row, or one whose metrics JSON does not decode
    to an object, keeps its timestamp with NaN for every metric; so does a missing or non-numeric metric value.
    NaN later breaks the integration segment (DLI-012)."""
    series_times: dict[str, list[datetime]] = {metric: [] for metric in metrics}
    series: dict[str, list[float]] = {metric: [] for metric in series_times}
    for row in rows:
        try:
            timestamp = datetime.fromisoformat(row['timestamp'])
        except (TypeError, ValueError):
            continue
        decoded: Any  # whatever the stored JSON holds; only a dict is used below
        try:
            decoded = json.loads(row['software_metrics_json'] or '{}') if row['eligible'] else {}
        except (TypeError, ValueError):
            decoded = {}
        if not isinstance(decoded, dict):
            decoded = {}
        for metric in series:
            try:
                value = float(decoded.get(metric))  # None and non-numeric strings raise and become NaN
            except (TypeError, ValueError):
                value = float('nan')
            series_times[metric].append(timestamp)
            series[metric].append(value)
    return series_times, series


@dataclass
class _Pass:
    """Running state of one pass over the samples (internal, mutable)."""

    total: float = 0.0
    covered_seconds: float = 0.0
    first_valid: datetime | None = None
    last_valid: datetime | None = None
    integrated_until: datetime | None = None
    partial: bool = False
    plot_times: list[datetime] = field(default_factory=list)
    cumulative: list[float] = field(default_factory=list)


def _accumulate(
    timestamps: Sequence[datetime],
    values: Sequence[float],
    period_start: datetime,
    period_end: datetime,
    cutoff: datetime,
    max_gap_seconds: float,
) -> _Pass:
    """Trapezoid sum over the samples in [period_start, cutoff] that are before period_end, in input order."""
    run = _Pass()
    previous: tuple[datetime, float] | None = None
    for timestamp, value in zip(timestamps, values, strict=True):
        if timestamp < period_start or timestamp > cutoff or timestamp >= period_end:
            continue
        if not np.isfinite(value) or value < 0:
            previous = None
            run.partial = True
            run.plot_times.append(timestamp)
            run.cumulative.append(float('nan'))
            continue
        if run.first_valid is None:
            run.first_valid = timestamp
        run.last_valid = timestamp
        if previous is not None:
            seconds = (timestamp - previous[0]).total_seconds()
            if 0 <= seconds <= max_gap_seconds:
                run.total += (previous[1] + value) * seconds / 2_000_000.0
                run.covered_seconds += seconds
                if seconds > 0:
                    run.integrated_until = timestamp
            else:
                run.partial = True
                run.plot_times.append(timestamp)
                run.cumulative.append(float('nan'))
        run.plot_times.append(timestamp)
        run.cumulative.append(run.total)
        previous = timestamp, value
    return run


def integrate(
    timestamps: Sequence[datetime],
    values: Sequence[float],
    period_start: datetime,
    period_end: datetime,
    observed_until: datetime,
    max_gap_seconds: float = MIN_MAX_GAP_SECONDS,
    *,
    paused: bool = False,
) -> DliIntegration:
    """Trapezoid DLI with coverage, gaps and state for one metric.

    cutoff = observed_until clamped into [period_start, period_end]; samples count when period_start <= t <= cutoff
    and t < period_end. A non-finite or negative value, or an interval outside [0, max_gap_seconds], is not
    integrated and breaks the curve; zero is a valid value. Units: values µmol·m⁻²·s⁻¹, total mol·m⁻², durations
    seconds."""
    cutoff = min(max(observed_until, period_start), period_end)
    run = _accumulate(timestamps, values, period_start, period_end, cutoff, max_gap_seconds)
    covered_seconds, first_valid, last_valid = run.covered_seconds, run.first_valid, run.last_valid
    elapsed_seconds = (cutoff - period_start).total_seconds()
    head_seconds = (first_valid - period_start).total_seconds() if first_valid else elapsed_seconds
    tail_seconds = (cutoff - last_valid).total_seconds() if last_valid else 0.0
    internal_seconds = (
        max(0.0, (last_valid - first_valid).total_seconds() - covered_seconds) if first_valid and last_valid else 0.0
    )
    stale = last_valid is not None and tail_seconds > max_gap_seconds
    if covered_seconds == 0:
        state = STATE_NO_DATA
    elif run.partial or head_seconds > max_gap_seconds or stale:
        state = STATE_PARTIAL
    else:
        state = STATE_INTEGRATING
    summary = DliSummary(
        total=run.total,
        covered_seconds=covered_seconds,
        missing_seconds=max(0.0, elapsed_seconds - covered_seconds),
        coverage=covered_seconds / elapsed_seconds if elapsed_seconds > 0 else 0.0,
        first_valid=first_valid,
        last_valid=last_valid,
        integrated_until=run.integrated_until,
        head_seconds=head_seconds,
        internal_seconds=internal_seconds,
        tail_seconds=tail_seconds,
        cutoff=cutoff,
        state=state,
        stale=stale,
        paused=paused,
    )
    return DliIntegration(summary=summary, plot_times=run.plot_times, cumulative=run.cumulative)
