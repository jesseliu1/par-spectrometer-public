"""Route of API-09: the newest record of one of the alpha's own device databases, read only (issue #82).

The overview page itself shows the live answer in tier 1 (acquisition_routes.py, `live`); tier 0 has no device.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..application import overview as use_case
from . import overview_models as models
from .models import DeviceRef, Spectrum
from .routes import API_PREFIX, ERRORS, Key, _context, _stored_row

router = APIRouter(prefix=API_PREFIX, responses=ERRORS)

_PAGE = use_case.PAGE_TEXTS
TEXTS = models.OverviewTexts(
    page_title=_PAGE.page_title,
    summary_title=_PAGE.summary_title,
    summary_context=_PAGE.summary_context,
    details_button=_PAGE.details_button,
    metrics_toggle=_PAGE.metrics_toggle,
    spectrum_title=_PAGE.spectrum_title,
    x_label=_PAGE.x_label,
    y_label=_PAGE.y_label,
    empty_heading=_PAGE.empty_heading,
    empty_detail=_PAGE.empty_detail,
    invalid_spectrum=_PAGE.invalid_spectrum,
    details_columns=list(_PAGE.details_columns),
    details_close=_PAGE.details_close,
)


def _rows(rows: list[tuple[str, str]]) -> list[models.MetricRow]:
    return [models.MetricRow(label=label, text=text) for label, text in rows]


def _record(found: use_case.Overview) -> models.OverviewRecord | None:
    shown = found.shown
    if shown is None:
        return None
    return models.OverviewRecord(
        id=int(shown.row["id"]),
        acquired_at=shown.row.get("acquired_at"),
        acquired_at_text=shown.acquired_at_text,
        age_seconds=shown.age_seconds,
        age_text=shown.age_text,
        exposure_text=shown.exposure_text,
        elapsed_text=shown.elapsed_text,
        review_text=shown.review_text,
        details_title=shown.details_title,
    )


def _attempt(found: use_case.Overview) -> models.OverviewAttempt | None:
    attempt = found.attempt
    if attempt is None:
        return None
    return models.OverviewAttempt(
        id=int(attempt.row["id"]),
        success=bool(attempt.row.get("success")),
        acquired_at=attempt.row.get("acquired_at"),
        acquired_at_text=attempt.acquired_at_text,
    )


@router.get(
    "/devices/{key}/latest",
    response_model=models.Overview,
    summary="实时概览（只读设备库）：最近一条成功光谱记录的摘要卡、状态行、光谱与图内指标（V1.0.3 文字）",
)
def latest(request: Request, key: Key) -> models.Overview:
    context = _context(request)
    found = context.overview.latest(key)
    chart = found.chart
    return models.Overview(
        as_of=context.now(),
        snapshot_id=found.device.id,
        device=DeviceRef(key=found.device.key, name=found.device.name),
        snapshot_text=found.snapshot_text,
        texts=TEXTS,
        display_record=_record(found),
        latest_attempt=_attempt(found),
        record=_stored_row(found.shown.row) if found.shown is not None else None,
        status=models.OverviewStatus(text=found.status.text, level=found.status.level),
        stale=found.stale,
        stale_after_seconds=found.stale_after_seconds,
        poll_cycle_seconds=found.poll_cycle.seconds,
        poll_cycle_source=found.poll_cycle.source,
        poll_cycle_text=found.poll_cycle_text,
        kpis=[models.OverviewKpi(key=kpi.key, title=kpi.title, text=kpi.text) for kpi in found.kpis],
        core_metrics=_rows(found.core_metrics),
        table=[models.OverviewTableGroup(title=title, rows=_rows(rows)) for title, rows in found.table],
        chart=models.OverviewChart(
            title=chart.title,
            spectrum_state=chart.spectrum_state,
            spectrum=Spectrum(**vars(chart.spectrum)) if chart.spectrum is not None else None,
            y_max=chart.y_max,
            x_ticks=list(use_case.X_TICKS),
            overlay=[_rows(column) for column in chart.overlay],
        ),
        details_enabled=found.details_enabled,
        metrics_error=None
        if found.metrics_error is None
        else models.OverviewError(message=found.metrics_error.message, detail=found.metrics_error.detail),
    )
