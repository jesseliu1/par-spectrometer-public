"""Routes of the first read-only batch (api-contract-v0 API-01, API-03, API-05..07, API-10, API-19..21).

Handlers are plain `def`: FastAPI runs them in its thread pool, so SQLite reads never block the event loop
(13_ appendix A). Each handler only converts between the application layer and the response models.
"""

from __future__ import annotations

import os
from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..application.dli import DliDay, DliMetric, DliSummary
from ..application.errors import RecordUnreadable
from ..application.history import PAGE_LIMIT, HistoryPage, RecordDetail
from ..application.history import Spectrum as SpectrumData
from ..application.own_devices import DeviceSlot
from ..application.readonly import SQLITE_MAX_INTEGER
from ..application.reference_curves import reference_curves
from ..application.snapshots import Snapshot
from ..application.timefmt import beijing_iso
from . import models
from .context import ServiceContext
from .security import error_response

API_PREFIX = "/api/v0"
HEALTH_PATH = f"{API_PREFIX}/health"
BUILD_COMMIT_ENV = "PAR_BUILD_COMMIT"
ERRORS: dict[int | str, dict[str, Any]] = {
    int(status): {"model": models.ErrorResponse, "description": text}
    for status, text in (
        (HTTPStatus.BAD_REQUEST, "invalid_argument：参数缺失或格式错误"),
        (HTTPStatus.UNAUTHORIZED, "unauthenticated：缺少或错误的令牌"),
        (HTTPStatus.FORBIDDEN, "forbidden_origin：Host/Origin 校验失败"),
        (HTTPStatus.NOT_FOUND, "device_not_found / record_not_found"),
        (HTTPStatus.SERVICE_UNAVAILABLE, "database_unavailable：设备库不可访问（可重试）"),
    )
}
router = APIRouter(prefix=API_PREFIX, responses=ERRORS)

Key = Annotated[str, Path(description="设备位置 p1–p4", examples=["p1"])]
AcquisitionId = Annotated[int, Path(le=SQLITE_MAX_INTEGER, description="采集记录 ID（acquisitions.id）")]


def _context(request: Request) -> ServiceContext:
    context: ServiceContext = request.app.state.context
    return context


def _snapshot(snapshot: Snapshot) -> models.SnapshotModel:
    return models.SnapshotModel(
        id=snapshot.id,
        name=snapshot.name,
        key=snapshot.key,
        position=snapshot.position,
        file_name=snapshot.file_name,
        path=snapshot.path,
        source_path=snapshot.source_path,
        imported_at=snapshot.imported_at,
        record_count=snapshot.record_count,
        source_before=models.Fingerprint(**vars(snapshot.source_before)),
        source_after=models.Fingerprint(**vars(snapshot.source_after)),
        source_changed_during_import=snapshot.source_changed_during_import,
    )


def _display_state(slot: DeviceSlot) -> models.DisplayState:
    """UI-259: a disabled device reads 停用 (grey); a database outside the alpha's folder is a fault (16_ 3.2)."""
    if slot.database is None:
        return "unconfigured"
    if not slot.readable:
        return "fault"
    return "normal" if slot.enabled else "disabled"


def _device(slot: DeviceSlot) -> models.Device:
    database = slot.database
    return models.Device(
        key=slot.key,
        position=slot.position,
        configured=database is not None,
        enabled=slot.enabled,
        name=database.name if database else "",
        display_state=_display_state(slot),
        database_name=database.file_name if database else None,
        database_path=database.path if database else None,
        snapshot_id=database.id if database else None,
        imported_at=None,
    )


def _stored_row(row: dict[str, Any]) -> models.AcquisitionRow:
    """The stored row as the response carries it; a value no field accepts (e.g. a BLOB) makes this one record
    unreadable (500 internal, not retryable), like broken metrics JSON (review N-1)."""
    try:
        return models.AcquisitionRow(**row)
    except ValidationError as error:
        raise RecordUnreadable(f"记录 #{row.get('id')} 的字段无法读取", str(error).splitlines()[0]) from error


def _spectrum(spectrum: SpectrumData) -> models.Spectrum:
    return models.Spectrum(**vars(spectrum))


@router.get("/health", response_model=models.Health, summary="健康检查（无需令牌）")
def health(request: Request) -> models.Health:
    context = _context(request)
    commit = context.build_commit or os.environ.get(BUILD_COMMIT_ENV) or None
    return models.Health(
        version=context.version, build_commit=commit, tier=context.acquisition.tier(), started_at=context.started_at
    )


@router.post(
    "/shutdown",
    response_model=models.ShutdownAccepted,
    status_code=HTTPStatus.ACCEPTED,
    summary="停止本机服务（API-19，只供桌面外壳：带令牌、不带 Origin）",
    description="服务处理完进行中的请求后正常退出（退出码 0）并删除 service.json。带 Origin 头（网页发出）的请求为 "
    "403 forbidden_origin；服务未启用停止接口时为 404。",
)
def shutdown(request: Request) -> models.ShutdownAccepted | JSONResponse:
    # The shell's stop request (review of PR #50, major 1): a windowed exe has no stdin on Windows, so the end of
    # the pipe cannot reach it. A browser always sends Origin with a POST, so the page itself cannot stop the service.
    if "origin" in request.headers:
        return error_response(HTTPStatus.FORBIDDEN, "forbidden_origin", "网页不能停止本机服务", False)
    request_stop = getattr(request.app.state, "request_stop", None)
    if request_stop is None:
        raise StarletteHTTPException(HTTPStatus.NOT_FOUND, "本服务未启用停止接口")
    request_stop()
    return models.ShutdownAccepted()


@router.get(
    "/snapshots",
    response_model=models.SnapshotList,
    summary="已导入的历史库快照（新导入在前）；页面不再使用（#82），#83 移除",
    deprecated=True,
)
def list_snapshots(request: Request) -> models.SnapshotList:
    context = _context(request)
    return models.SnapshotList(as_of=context.now(), items=[_snapshot(s) for s in context.snapshots.snapshots()])


@router.post(
    "/snapshots",
    response_model=models.SnapshotImported,
    status_code=HTTPStatus.CREATED,
    responses={int(HTTPStatus.CONFLICT): {"model": models.ErrorResponse, "description": "busy：已有导入在进行"}},
    summary="导入历史库快照（源库只读打开，SQLite 在线备份到 alpha 数据目录）；导入后任何页面都不显示（#82），#83 移除",
    deprecated=True,
)
def import_snapshot(request: Request, body: models.SnapshotImportRequest) -> models.SnapshotImported:
    context = _context(request)
    snapshot = context.snapshots.import_snapshot(body.source_path, body.name, body.position)
    context.events.publish("snapshot_imported", {"id": snapshot.id, "key": snapshot.key, "name": snapshot.name})
    return models.SnapshotImported(as_of=context.now(), snapshot=_snapshot(snapshot))


@router.get(
    "/devices",
    response_model=models.DeviceList,
    summary="设备列表（固定 4 个位置；alpha 自己档位 1 配置中登记的设备，档位 0 全部未配置）",
)
def devices(request: Request) -> models.DeviceList:
    context = _context(request)
    items = [_device(slot) for slot in context.devices.devices()]
    return models.DeviceList(as_of=context.now(), tier=context.acquisition.tier(), items=items)


@router.get("/devices/{key}/acquisitions", response_model=models.HistoryPage, summary="按时间范围查询历史记录（分页）")
def acquisitions(
    request: Request,
    key: Key,
    start: Annotated[str, Query(description="开始时间（含），北京时间 YYYY-MM-DDTHH:MM:SS.mmm")],
    end: Annotated[str, Query(description="结束时间（含），北京时间 YYYY-MM-DDTHH:MM:SS.mmm")],
    limit: Annotated[int, Query(ge=1, le=PAGE_LIMIT, description=f"每页条数，1–{PAGE_LIMIT}")] = PAGE_LIMIT,
    offset: Annotated[
        int,
        Query(
            ge=0,
            le=SQLITE_MAX_INTEGER,
            description="跳过的条数（按 ID 从新到旧；实验性，按 D-201 裁决历史回放页只用 0）；0 即 V1.0.x 历史列表",
        ),
    ] = 0,
) -> models.HistoryPage:
    context = _context(request)
    page: HistoryPage = context.history.page(key, start, end, limit, offset)
    return models.HistoryPage(
        as_of=context.now(),
        snapshot_id=page.device.id,
        range=models.TimeRange(start=page.start, end=page.end),
        limit=page.limit,
        offset=page.offset,
        limit_reached=page.limit_reached,
        next_offset=page.offset + len(page.items) if page.limit_reached else None,
        items=[models.HistoryItem(**vars(item)) for item in page.items],
    )


@router.get(
    "/devices/{key}/acquisitions/{acquisition_id}",
    response_model=models.AcquisitionDetail,
    summary="单条记录详情：54 项指标、采集校验、701 点光谱",
)
def acquisition(request: Request, key: Key, acquisition_id: AcquisitionId) -> models.AcquisitionDetail:
    context = _context(request)
    detail: RecordDetail = context.history.detail(key, acquisition_id)
    return models.AcquisitionDetail(
        as_of=context.now(),
        snapshot_id=detail.device.id,
        device=models.DeviceRef(key=detail.device.key, name=detail.device.name),
        header=models.DetailHeader(
            title=detail.title,
            time_text=detail.time_text,
            status_text=detail.status_text,
            status_level=detail.status_level,
            exposure_text=detail.exposure_text,
        ),
        success=detail.success,
        elapsed_text=detail.elapsed_text,
        review_text=detail.review_text,
        groups=[
            models.MetricGroup(title=group.title, items=[models.MetricItem(**vars(item)) for item in group.items])
            for group in detail.groups
        ],
        record=_stored_row(detail.row),
        spectrum_state=detail.spectrum_state,
        spectrum=_spectrum(detail.spectrum) if detail.spectrum else None,
    )


@router.get(
    "/devices/{key}/acquisitions/{acquisition_id}/spectrum",
    response_model=models.SpectrumResponse,
    summary="单条光谱；记录无光谱时 404 record_not_found",
)
def spectrum(request: Request, key: Key, acquisition_id: AcquisitionId) -> models.SpectrumResponse:
    context = _context(request)
    device, data = context.history.spectrum(key, acquisition_id)
    return models.SpectrumResponse(
        as_of=context.now(), snapshot_id=device.id, id=acquisition_id, spectrum=_spectrum(data)
    )


@router.get(
    "/reference-curves",
    response_model=models.ReferenceCurvesResponse,
    summary="光谱图的四条参考曲线与按波长着色（内容固定，可长期缓存）",
)
def reference_curves_route() -> models.ReferenceCurvesResponse:
    content = reference_curves()
    return models.ReferenceCurvesResponse(
        curves=[
            models.ReferenceCurveModel(
                key=curve.key,  # type: ignore[arg-type]
                label=curve.label,
                line=curve.line,  # type: ignore[arg-type]
                width=curve.width,
                x=list(curve.x),
                y=list(curve.y),
            )
            for curve in content.curves
        ],
        axis_label=content.axis_label,
        axis_max=content.axis_max,
        fill_start=content.fill_start,
        fill_colors=[list(color) for color in content.fill_colors],
        fill_opacity=content.fill_opacity,
    )


def _optional_time(moment: datetime | None) -> str | None:
    return beijing_iso(moment) if moment else None


def _dli_summary(summary: DliSummary) -> models.DliSummaryModel:
    return models.DliSummaryModel(
        total=summary.total,
        covered_seconds=summary.covered_seconds,
        missing_seconds=summary.missing_seconds,
        coverage=summary.coverage,
        first_valid=_optional_time(summary.first_valid),
        last_valid=_optional_time(summary.last_valid),
        integrated_until=_optional_time(summary.integrated_until),
        head_seconds=summary.head_seconds,
        internal_seconds=summary.internal_seconds,
        tail_seconds=summary.tail_seconds,
        cutoff=beijing_iso(summary.cutoff),
        state=summary.state,  # type: ignore[arg-type]  # one of the three services.dli STATE_* texts
        stale=summary.stale,
        paused=summary.paused,
    )


def _dli_metric(metric: DliMetric) -> models.DliMetric:
    return models.DliMetric(
        key=metric.key,
        title=metric.title,
        summary=_dli_summary(metric.summary),
        header=models.DliHeader(**vars(metric.header)),
        y_max=metric.y_max,
        series=models.DliSeries(**vars(metric.series)),
    )


@router.get(
    "/devices/{key}/dli",
    response_model=models.DliDay,
    summary="DLI：一个积分周期的四项累计曲线、累计值、覆盖率、状态与中断（V1.0.3 口径；首次写启用时间，D-228）",
)
def dli(
    request: Request,
    key: Key,
    date: Annotated[
        str | None,
        Query(
            description="北京日期 YYYY-MM-DD：取该日结束时正在进行的周期（国内经度即该日日出起算；"
            "今天取当前时刻的周期）；不给为当前周期"
        ),
    ] = None,
) -> models.DliDay:
    context = _context(request)
    day: DliDay = context.dli.day(key, date)
    start = day.period_start
    return models.DliDay(
        as_of=context.now(),
        snapshot_id=day.device.id,
        device=models.DeviceRef(key=day.device.key, name=day.device.name),
        requested_date=day.date,
        period=models.DliPeriod(
            start=beijing_iso(start),
            end=beijing_iso(day.period_end),
            date=start.date().isoformat(),
            current=day.current,
            text=day.period_text,
        ),
        location=models.DliLocation(
            latitude=day.location[0],
            longitude=day.location[1],
            stored=day.location_stored,
            coordinates_text=day.coordinates_text,
            text=day.location_text,
        ),
        enabled=models.DliEnabled(at=day.enabled_at, stored=day.enabled_at_stored, text=day.enabled_at_text),
        observed_until=beijing_iso(day.observed_until),
        poll_cycle_seconds=day.poll_cycle_seconds,
        poll_cycle_source=day.poll_cycle_source,
        poll_cycle_record_at=day.poll_cycle_record_at,
        max_gap_seconds=day.max_gap_seconds,
        gap_text=day.gap_text,
        snapshot_text=day.snapshot_text,
        paused=day.paused,
        metrics=[_dli_metric(metric) for metric in day.metrics],
        interruptions=[models.DliInterruption(**vars(item)) for item in day.interruptions],
        ticks=[
            models.DliTick(
                offset_seconds=(tick.at - start).total_seconds(),
                at=beijing_iso(tick.at),
                text=tick.text,
                narrow=tick.narrow,
            )
            for tick in day.ticks
        ],
    )


@router.put(
    "/devices/{key}/dli/location",
    response_model=models.DliDay,
    summary="保存经纬度并重置周期（issue #116）：只写该设备库 app_settings.dli_location（V1.0.3 同一条语句），"
    "再按新位置返回所示周期；只读模式 403",
)
def save_dli_location(
    request: Request,
    key: Key,
    body: models.DliLocationRequest,
    date: Annotated[str | None, Query(description="同 GET：保存后返回该日期的周期；不给为当前周期")] = None,
) -> models.DliDay:
    _context(request).dli.save_location(key, body.latitude, body.longitude, date)
    return dli(request, key, date)
