"""DLI use case (API-10, 光积累计算) on the alpha's own device database (own_devices.py, #82), read only except for
the enable time (D-228 A, below).

The computation is V1.0.3's own: par_app.services.dli (dli_period, max_gap_seconds, build_series, integrate) on the
rows ParDatabase.dli_samples would return (readonly.SnapshotDli repeats that SQL on the read-only copy). Texts come
from par_app.services.dli_display (copies of the V1.0.3 DLI page texts) and par_app.database.format_beijing_time.
MainWindow.refresh_diagnostics is followed step by step; what the alpha decides on its own is below (D-204, decided
by owner 2026-10-18 as recommended; its snapshot parts superseded by issue #82):
  * period: without `date` the period in progress now (= V1.0.3); with `date` the period in progress at the end of
    that Beijing day, i.e. the one that starts at that day's sunrise for domestic longitudes; for today the
    period in progress now (the end of today has not come yet);
  * allowed gap: the poll cycle is the one the records hold (D-204 question 1 decided D; boundaries D-206):
    quality_json.poll_cycle_seconds of the latest successful record of the period up to the cutoff, or of the
    latest one before the period when the period has none (V1.0.2+ writes effective_poll_cycle_seconds() into
    every successful record). A missing or unusable value falls back to the default configuration's cycle, 60 s
    (option A). V1.0.3 uses its configuration at drawing time instead, so a cycle changed after the last record of
    the period is not seen here; one allowed gap applies to the whole period, as in V1.0.3;
  * "采集已暂停": shown while nothing acquires into the database (not taken over, maintenance or a halt), as the
    live overview (D-213); V1.0.3 marks maintenance and a halt;
  * cutoff ("统计截至"): the service clock now, as V1.0.3 uses its clock (DLI-044).
The location is only read from the database's app_settings. The enable time is stored as V1.0.3 stores it (D-228
option A, owner 2026-10-27): the first time a registered device's DLI is read and its database holds none, "now" is
written (dli_enable.store_enabled_at, that one row only) and from then on only later records count. When it cannot
be written (no app_settings table, the file busy past SQLite's wait) the day is shown with "now", as V1.0.3 shows an
unregistered device (D-163), and the next read tries again (R-1-5).
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from ..database import format_beijing_time
from ..domain.clock import Clock
from ..models import MAX_POLL_CYCLE_SECONDS, MIN_POLL_CYCLE_SECONDS, AppConfig
from ..services import dli as dli_service
from ..services import dli_display
from ..services.dli import DliSummary as DliSummary  # re-exported: the API maps it and never reads services (route C 4)
from .dli_enable import store_enabled_at, store_location
from .errors import DatabaseUnavailable, FeatureDisabled, InvalidArgument, RecordUnreadable
from .own_devices import DeviceDatabase, OwnDevices
from .readonly import Row, SnapshotDli
from .tier import TAKEOVER_TIER
from .timefmt import beijing_iso

LOG = logging.getLogger(__name__)
LATITUDE_RANGE = (-89.9, 89.9)
LONGITUDE_RANGE = (-180.0, 180.0)
"""MainWindow's DLI spin boxes: setRange(-89.9, 89.9) and setRange(-180.0, 180.0), four decimals (UI-178, DLI-024)."""
LOCATION_DECIMALS = 4
SAVE_LOCATION_TIER_0 = "只读模式不保存位置：请在“设置与导出”开启采集模式"

DEFAULT_LOCATION = (39.9042, 116.4074)
"""ParDatabase.load_dli_location: Beijing when no location is stored or it cannot be read (UI-153)."""
QUERY_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
END_OF_DAY = time(23, 59, 59, 999000)
EARLIEST_DATE = date.min + timedelta(days=3)
"""dli_period looks at the sunrises of days d-2..d+1; earlier days cannot be represented."""
GAP_TEXT_RECORDED = "允许间隔 {max_gap:g} 秒（按轮询周期 {poll_cycle:g} 秒计，取自 {recorded_at} 的采集记录）"
GAP_TEXT_UNUSABLE = (
    "允许间隔 {max_gap:g} 秒（按默认轮询周期 {poll_cycle:g} 秒计：{recorded_at} 的采集记录中没有可用的轮询周期）"
)
GAP_TEXT_NO_RECORD = "允许间隔 {max_gap:g} 秒（按默认轮询周期 {poll_cycle:g} 秒计：本周期及之前没有成功的采集记录）"
SOURCE_TEXT = "数据来自本机 2.0 采集的设备库：{path}"


PollCycleSource = Literal["record", "default"]


@dataclass(frozen=True)
class PollCycle:
    """The poll cycle the allowed gap is computed from (D-204 question 1 = D, D-206)."""

    seconds: float
    source: PollCycleSource
    record_at: str | None
    """acquired_at (as stored) of the record consulted; None when the database has no successful record up to the
    cutoff. Set also when its value was unusable and the default applies."""


@dataclass(frozen=True)
class DliSeries:
    times: list[str]
    offsets_seconds: list[float]
    """Seconds since the period start, the x position on the chart."""
    cumulative: list[float | None]
    """Running total in mol·m⁻²; None where the curve breaks (DLI-012, DLI-029, DLI-049)."""


@dataclass(frozen=True)
class DliMetric:
    key: str
    title: str
    summary: dli_service.DliSummary
    header: dli_display.DliHeader
    y_max: float
    series: DliSeries


@dataclass(frozen=True)
class DliInterruption:
    occurred_at: str
    occurred_at_text: str
    reason: str


@dataclass(frozen=True)
class DliDay:
    device: DeviceDatabase
    date: str | None
    period_start: datetime
    period_end: datetime
    current: bool
    period_text: str
    location: tuple[float, float]
    location_stored: bool
    location_text: str
    coordinates_text: str
    enabled_at: str
    enabled_at_stored: bool
    enabled_at_text: str
    observed_until: datetime
    poll_cycle_seconds: float
    poll_cycle_source: PollCycleSource
    poll_cycle_record_at: str | None
    max_gap_seconds: float
    gap_text: str
    snapshot_text: str
    paused: bool
    metrics: list[DliMetric]
    interruptions: list[DliInterruption]
    ticks: list[dli_display.AxisTick]


def parse_location(value: str | None) -> tuple[tuple[float, float], bool]:
    """ParDatabase.load_dli_location on the stored text; the bool says whether a readable location was stored."""
    if value is None:
        return DEFAULT_LOCATION, False
    try:
        decoded = json.loads(value)
        return (float(decoded["latitude"]), float(decoded["longitude"])), True
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return DEFAULT_LOCATION, False


def parse_enabled_at(stored: tuple[bool, str | None]) -> str | None:
    """ParDatabase.peek_dli_enabled_at on the stored row (SnapshotDli.enabled_at_value). V1.0.3 raises on an
    undecodable value, including a row holding SQL NULL (json.loads(None) is a TypeError; review N-4); here that
    one database is unreadable for DLI (500, not retryable) and every other page keeps working."""
    present, value = stored
    if not present:
        return None
    try:
        if value is None:  # present but SQL NULL: what json.loads(None) raises in peek_dli_enabled_at
            raise TypeError("value_json 为 SQL NULL")
        return str(json.loads(value))
    except (TypeError, ValueError) as error:
        raise RecordUnreadable("库中保存的 DLI 启用时间无法读取", f"{type(error).__name__}: {error}") from error


def recorded_poll_cycle(quality_json: object) -> float | None:
    """quality_json.poll_cycle_seconds as V1.0.2+ writes it (a JSON number, effective_poll_cycle_seconds(), so
    within 40–3600 s), None when it is missing or unusable: undecodable JSON, not an object, not a number (strings
    and booleans included), not finite, beyond float range (a huge JSON integer), or outside the configurable range
    (not clamped: such a value was not written by V1.0.x; D-206)."""
    if not isinstance(quality_json, str):
        return None
    try:
        decoded = json.loads(quality_json)
    except ValueError:
        return None
    value = decoded.get("poll_cycle_seconds") if isinstance(decoded, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        seconds = float(value)
    except OverflowError:  # a JSON integer beyond float range (e.g. 10**400): out of range, not a 500 (review M-1)
        return None
    if not math.isfinite(seconds) or not MIN_POLL_CYCLE_SECONDS <= seconds <= MAX_POLL_CYCLE_SECONDS:
        return None
    return seconds


def poll_cycle(row: Row | None) -> PollCycle:
    """The recorded cycle of the consulted record, else the default configuration's (MainWindow.refresh_diagnostics
    calls effective_poll_cycle_seconds(); 60 s by default)."""
    record_at = None if row is None else str(row["acquired_at"])
    recorded = None if row is None else recorded_poll_cycle(row["quality_json"])
    if recorded is not None:
        return PollCycle(recorded, "record", record_at)
    return PollCycle(AppConfig().effective_poll_cycle_seconds(), "default", record_at)


def gap_text(cycle: PollCycle, max_gap: float) -> str:
    if cycle.record_at is None:
        template = GAP_TEXT_NO_RECORD
    else:
        template = GAP_TEXT_RECORDED if cycle.source == "record" else GAP_TEXT_UNUSABLE
    recorded_at = format_beijing_time(cycle.record_at) if cycle.record_at is not None else ""
    return template.format(max_gap=max_gap, poll_cycle=cycle.seconds, recorded_at=recorded_at)


def _stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


def query_date(value: str | None, today: date) -> date | None:
    if value is None:
        return None
    if not QUERY_DATE.match(value):
        raise InvalidArgument(f"参数 date 格式错误：{value}（应为 YYYY-MM-DD，北京时间）")
    try:
        day = date.fromisoformat(value)
    except ValueError as error:
        raise InvalidArgument(f"参数 date 不是有效日期：{value}", str(error)) from error
    if day > today:
        raise InvalidArgument(f"参数 date 不能晚于今天（{today.isoformat()}）：{value}")
    if day < EARLIEST_DATE:
        raise InvalidArgument(f"参数 date 太早：{value}")
    return day


def period_reference(day: date | None, now: datetime) -> datetime:
    """The moment whose period is shown: now without a date (= V1.0.3); otherwise the end of that Beijing day, but
    never later than now, so today is always the period in progress (before today's sunrise that is the one that
    began yesterday, not a future one; PR #47 review M-1)."""
    if day is None:
        return now
    return min(datetime.combine(day, END_OF_DAY), now)


def _period(reference: datetime, location: tuple[float, float]) -> tuple[datetime, datetime]:
    try:
        return dli_service.dli_period(reference, location)
    except (ValueError, OverflowError) as error:
        raise RecordUnreadable(
            f"库中保存的 DLI 位置无法计算日出：纬度 {location[0]}，经度 {location[1]}",
            f"{type(error).__name__}: {error}",
        ) from error


def _series(result: dli_service.DliIntegration, start: datetime) -> DliSeries:
    return DliSeries(
        times=[beijing_iso(stamp) for stamp in result.plot_times],
        offsets_seconds=[(stamp - start).total_seconds() for stamp in result.plot_times],
        cumulative=[value if math.isfinite(value) else None for value in result.cumulative],
    )


def _metrics(
    rows: list[Row], start: datetime, end: datetime, now: datetime, max_gap: float, paused: bool
) -> list[DliMetric]:
    """MainWindow.refresh_diagnostics: one build_series over the rows, then integrate per metric with the same
    cutoff (DLI-031) and allowed gap."""
    series_times, series = dli_service.build_series(rows)
    metrics = []
    for metric, title in dli_display.METRIC_TITLES.items():
        result = dli_service.integrate(series_times[metric], series[metric], start, end, now, max_gap, paused=paused)
        summary = result.summary
        metrics.append(
            DliMetric(
                metric,
                title,
                summary,
                dli_display.header(summary),
                dli_display.y_axis_max(summary.total),
                _series(result, start),
            )
        )
    return metrics


class DliQueries:
    def __init__(self, devices: OwnDevices, clock: Clock) -> None:
        self.devices = devices
        self.clock = clock

    @staticmethod
    def _enable(path: Path, now: str, database: SnapshotDli) -> tuple[bool, str | None]:
        """Store the enable time (D-228 A) and read back what the database holds now; on a failed write the
        database is left as it was and the day is computed as before (read "missing")."""
        try:
            store_enabled_at(path, now)
        except DatabaseUnavailable as error:
            LOG.warning("DLI enable time not stored in %s: %s", path, error.detail)
            return False, None
        return database.enabled_at_value()

    def save_location(self, key: str, latitude: float, longitude: float, requested: str | None = None) -> None:
        """ "保存经纬度并重置周期" (issue #116, as MainWindow._save_dli_location): only in tier 1 or 2 and only for a
        registered device whose database lies in the alpha's devices folder (database_for refuses the rest). The
        values are V1.0.3's spin box values: inside its ranges, rounded to four decimals. The next day() reads the
        new location, so the period is computed again; the enable time and the records are not touched. Everything
        the answer depends on (`requested`, the date of the period shown after saving) is checked before anything is
        written, so a refused request never leaves a saved location behind (review of PR #117)."""
        if self.devices.acquisition.tier() < TAKEOVER_TIER:
            raise FeatureDisabled(SAVE_LOCATION_TIER_0)
        now = self.clock.now().replace(tzinfo=None)
        query_date(requested, now.date())
        checked = []
        for name, value, (low, high) in (("纬度", latitude, LATITUDE_RANGE), ("经度", longitude, LONGITUDE_RANGE)):
            if isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
                raise InvalidArgument(f"{name}应在 {low} 到 {high} 之间")
            checked.append(round(float(value), LOCATION_DECIMALS))  # a spin box value: 31 is stored as 31.0
        device = self.devices.database_for(key)
        store_location(Path(device.path), checked[0], checked[1], beijing_iso(now))

    def day(self, key: str, requested: str | None = None) -> DliDay:
        now = self.clock.now().replace(tzinfo=None)  # naive Beijing wall time, as MainWindow passes it
        day = query_date(requested, now.date())
        device = self.devices.database_for(key)
        database = SnapshotDli(Path(device.path))
        location, location_stored = parse_location(database.location_value())
        stored = database.enabled_at_value()
        if not stored[0] and Path(device.path).is_file():
            stored = self._enable(Path(device.path), beijing_iso(now), database)
        stored_enabled_at = parse_enabled_at(stored)
        enabled_at = stored_enabled_at if stored_enabled_at is not None else beijing_iso(now)
        start, end = _period(period_reference(day, now), location)
        bounds = (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))
        cutoff = min(max(now, start), end)  # integrate()'s cutoff: records after it are not consulted either
        cycle = poll_cycle(database.poll_cycle_record(bounds[1], _stamp(cutoff)))
        max_gap = dli_service.max_gap_seconds(cycle.seconds)
        metrics = _metrics(database.samples(*bounds, enabled_at), start, end, now, max_gap, device.paused)
        interruptions = [
            DliInterruption(str(row["occurred_at"]), format_beijing_time(row["occurred_at"]), str(row["reason"]))
            for row in database.interruptions(*bounds, enabled_at)
        ]
        enabled_at_text = format_beijing_time(enabled_at)
        return DliDay(
            device=device,
            date=requested,
            period_start=start,
            period_end=end,
            current=start <= now < end,
            period_text=dli_display.period_text(start, end),
            location=location,
            location_stored=location_stored,
            location_text=dli_display.location_text(location, enabled_at_text),
            coordinates_text=dli_display.coordinates_text(location),
            enabled_at=enabled_at,
            enabled_at_stored=stored_enabled_at is not None,
            enabled_at_text=enabled_at_text,
            observed_until=now,
            poll_cycle_seconds=cycle.seconds,
            poll_cycle_source=cycle.source,
            poll_cycle_record_at=cycle.record_at,
            max_gap_seconds=max_gap,
            gap_text=gap_text(cycle, max_gap),
            snapshot_text=SOURCE_TEXT.format(path=device.path),
            paused=device.paused,
            metrics=metrics,
            interruptions=interruptions,
            ticks=dli_display.axis_ticks(start, end),
        )
