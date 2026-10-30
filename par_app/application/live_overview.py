"""Live overview of a device the alpha acquires itself (API-09 in tier 1, `source` = live; 16_ section 5).

The same steps as the snapshot overview (overview.py, which follows MainWindow.refresh_overview), on the alpha's own
device database while the coordinator writes it: read-only connection with mode=ro and without immutable=1, since
the file is changing. What differs from the snapshot answer, as V1.0.3 does it for a live database:
  * the poll cycle behind "暂无新记录" is the running configuration's (as V1.0.3), not the one in the record;
  * "采集已暂停" shows during maintenance or after a halt (MainWindow.refresh_overview reads the same two states),
    and also while the alpha has not taken over (nothing acquires then; D-213);
  * there is no snapshot text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..database import format_beijing_time
from ..services import metrics as metric_service
from ..services import overview_display as display
from .errors import DatabaseUnavailable
from .overview import Attempt, Kpi, MetricsError, OverviewChart, ShownRecord, _chart, _kpis, _metrics, _shown
from .readonly import SnapshotOverview


@dataclass(frozen=True)
class LiveSource:
    name: str
    database_path: Path
    poll_cycle_seconds: float
    paused: bool


@dataclass(frozen=True)
class LiveOverview:
    source: LiveSource
    shown: ShownRecord | None
    attempt: Attempt | None
    stale: bool | None
    stale_after_seconds: float
    status: display.StatusLine
    kpis: list[Kpi]
    core_metrics: list[tuple[str, str]]
    table: list[tuple[str, list[tuple[str, str]]]]
    chart: OverviewChart
    details_enabled: bool
    metrics_error: MetricsError | None


def live_overview(source: LiveSource, now: datetime) -> LiveOverview:
    path = source.database_path
    if not path.is_file():
        raise DatabaseUnavailable(str(path), "设备库尚未建立（保存配置后由采集建立）")
    database = SnapshotOverview(path)
    latest = database.latest()
    item = database.latest_successful()
    attempt = None if latest is None else Attempt(latest, format_beijing_time(latest.get("acquired_at")))
    stale_after = display.stale_after(source.poll_cycle_seconds)
    if item is None:
        return LiveOverview(
            source=source,
            shown=None,
            attempt=attempt,
            stale=None,
            stale_after_seconds=stale_after,
            status=display.EMPTY_STATUS if attempt is None else display.failed_status_line(attempt.acquired_at_text),
            kpis=_kpis({key: metric_service.EM_DASH for key, _title in display.KPI_TITLES}),
            core_metrics=[],
            table=[],
            chart=OverviewChart(
                display.NO_SPECTRUM_CHART_TITLE if attempt is None else display.FAILED_CHART_TITLE,
                "none",
                None,
                None,
                [],
            ),
            details_enabled=False,
            metrics_error=None,
        )
    row, raw = item
    shown = _shown(row, display.record_age(row, now))
    stale = display.is_stale(shown.age_seconds, source.poll_cycle_seconds)
    found = _metrics(row)
    status = display.status_line(
        row, latest, shown.age_seconds, stale=stale, paused=source.paused, time_text=shown.acquired_at_text
    )
    return LiveOverview(
        source=source,
        shown=shown,
        attempt=attempt,
        stale=stale,
        stale_after_seconds=stale_after,
        status=status,
        kpis=_kpis(found.kpis),
        core_metrics=found.core,
        table=found.table,
        chart=_chart(row, raw, found),
        details_enabled=True,  # V1.0.3 enables 全部指标 before it writes the cards (UI-013)
        metrics_error=found.error,
    )
