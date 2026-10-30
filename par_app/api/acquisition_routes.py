"""Tier, takeover and event-stream endpoints (16_ section 5; api-contract-v0 API-04/API-09 in tier 1, API-17).

Tier 0 answers every acquisition endpoint and every configuration write with 403 feature_disabled. Handlers that
reach the takeover are plain `def` (FastAPI's thread pool): they wait for the Qt main thread through the gateway
and must not block the event loop. The event stream is `async` and only waits on its own queue.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Request, Response
from starlette.responses import StreamingResponse

from ..application.acquisition import TierState
from ..application.events import CLOSED, Event
from ..application.live_overview import live_overview
from ..application.overview import X_TICKS
from ..application.own_devices import database_id
from . import acquisition_models as models
from .models import ErrorResponse, Spectrum
from .overview_models import (
    MetricRow,
    OverviewAttempt,
    OverviewChart,
    OverviewError,
    OverviewKpi,
    OverviewRecord,
    OverviewStatus,
    OverviewTableGroup,
)
from .overview_routes import TEXTS
from .routes import API_PREFIX, ERRORS, Key, _context, _stored_row

TIER_ERRORS: dict[int | str, dict[str, Any]] = {
    int(HTTPStatus.FORBIDDEN): {"model": ErrorResponse, "description": "feature_disabled：档位 0；或 forbidden_origin"},
    int(HTTPStatus.CONFLICT): {
        "model": ErrorResponse,
        "description": "instance_locked / confirmation_required / config_unavailable / not_running / busy",
    },
}
router = APIRouter(prefix=API_PREFIX, responses={**ERRORS, **TIER_ERRORS})


def _tier(state: TierState) -> models.TierState:
    return models.TierState(**vars(state))


@router.get("/tier", response_model=models.TierState, summary="档位与接管状态（状态栏常显的一块）")
def tier(request: Request) -> models.TierState:
    return _tier(_context(request).acquisition.state())


@router.post(
    "/tier/confirmations",
    response_model=models.Confirmation,
    status_code=HTTPStatus.CREATED,
    summary="开启档位 1 的二次确认：返回确认号（60 秒内有效、只能用一次）与两层确认的全文",
)
def confirm(request: Request, body: models.ConfirmationRequest) -> models.Confirmation:
    issued = _context(request).acquisition.confirm(body.tier)
    return models.Confirmation(
        confirmation_id=issued.id,
        tier=issued.tier,
        expires_at=issued.expires_at,
        notice=issued.notice,
        confirmation=issued.confirmation,
    )


@router.put(
    "/tier",
    response_model=models.TierState,
    responses={int(HTTPStatus.ACCEPTED): {"model": models.TierState, "description": "正在接管：先停止，结果见事件"}},
    summary="切换档位：0→1 需要有效确认号；1→0 不需要，正在接管时先停止采集（202）",
)
def set_tier(request: Request, body: models.TierRequest, response: Response) -> models.TierState:
    acquisition = _context(request).acquisition
    if not acquisition.set_tier(body.tier, body.confirmation_id):
        response.status_code = HTTPStatus.ACCEPTED
    return _tier(acquisition.state())


@router.get(
    "/acquisition-config",
    response_model=models.AcquisitionConfig,
    summary="alpha 自己的档位 1 配置（总线与设备登记；格式同 V1.0.3，文件在 alpha 数据目录）",
)
def read_config(request: Request) -> models.AcquisitionConfig:
    context = _context(request)
    return models.AcquisitionConfig(as_of=context.now(), **context.acquisition.config())


@router.put(
    "/acquisition-config",
    response_model=models.AcquisitionConfig,
    summary="保存并应用档位 1 配置（V1.0.3 DeviceHub.apply；只写 alpha 的配置与库；需正在接管）",
)
def save_config(request: Request, body: models.ConfigRequest) -> models.AcquisitionConfig:
    context = _context(request)
    context.acquisition.save_config(body.model_dump())
    return models.AcquisitionConfig(as_of=context.now(), **context.acquisition.config())


@router.post(
    "/acquisition-config/import-preview",
    response_model=models.ImportPreview,
    summary="从 V1.0.3 配置导入副本（预览）：只读 V1.0.3 的配置与库，库路径清空，待核对维护的设备不能导入；不写文件",
)
def import_preview(request: Request, body: models.ImportRequest) -> models.ImportPreview:
    context = _context(request)
    return models.ImportPreview(as_of=context.now(), **context.acquisition.import_preview(body.source_path))


@router.get(
    "/acquisition-config/serial-ports",
    response_model=models.SerialPorts,
    responses={
        int(HTTPStatus.INTERNAL_SERVER_ERROR): {
            "model": ErrorResponse,
            "description": "internal（可重试）：操作系统未能列出串口（“串口枚举失败：<原因>”）；页面保留上次的列表",
        }
    },
    summary="本机串口列表（V1.0.3 设置页“刷新串口”）：只枚举 serial.tools.list_ports.comports()，不打开任何串口",
)
def serial_ports(request: Request) -> models.SerialPorts:
    context = _context(request)
    found = context.acquisition.serial_ports()
    return models.SerialPorts(
        as_of=context.now(), ports=[models.SerialPort(**port) for port in found["ports"]], hint=found["hint"]
    )


def _status(request: Request) -> models.AcquisitionStatus:
    return models.AcquisitionStatus(**_context(request).acquisition.status())


@router.post(
    "/acquisition/start",
    response_model=models.AcquisitionStatus,
    status_code=HTTPStatus.ACCEPTED,
    summary="开始采集（接管）：取 V1.0.3 的单实例锁，建立 V1.0.3 的 DeviceHub 并启动协调器",
)
def start(request: Request) -> models.AcquisitionStatus:
    _context(request).acquisition.start()
    return _status(request)


@router.post(
    "/acquisition/stop",
    response_model=models.AcquisitionStatus,
    status_code=HTTPStatus.ACCEPTED,
    summary="停止采集：coordinator.stop()（最长约一个采集事务 40 秒），然后释放锁；结果见 takeover_state 事件",
)
def stop(request: Request) -> models.AcquisitionStatus:
    _context(request).acquisition.stop()
    return _status(request)


@router.get("/acquisition/status", response_model=models.AcquisitionStatus, summary="接管与采集状态（状态缓存）")
def status(request: Request) -> models.AcquisitionStatus:
    return _status(request)


def _rows(rows: list[tuple[str, str]]) -> list[MetricRow]:
    return [MetricRow(label=label, text=text) for label, text in rows]


@router.get(
    "/acquisition/devices/{key}/latest",
    response_model=models.LiveOverview,
    summary="实时概览（档位 1，source=live）：alpha 自己设备库中的最新记录，只读连接；“全部指标”用 API-06 读同一库",
)
def live_latest(request: Request, key: Key) -> models.LiveOverview:
    context = _context(request)
    source = context.acquisition.live_source(key)
    found = live_overview(source, context.clock.now())
    shown, attempt, chart = found.shown, found.attempt, found.chart
    return models.LiveOverview(
        as_of=context.now(),
        snapshot_id=database_id(key, source.database_path),
        device=models.LiveDevice(key=key, name=source.name, database_path=str(source.database_path)),
        texts=TEXTS,
        display_record=None
        if shown is None
        else OverviewRecord(
            id=int(shown.row["id"]),
            acquired_at=shown.row.get("acquired_at"),
            acquired_at_text=shown.acquired_at_text,
            age_seconds=shown.age_seconds,
            age_text=shown.age_text,
            exposure_text=shown.exposure_text,
            elapsed_text=shown.elapsed_text,
            review_text=shown.review_text,
            details_title=shown.details_title,
        ),
        latest_attempt=None
        if attempt is None
        else OverviewAttempt(
            id=int(attempt.row["id"]),
            success=bool(attempt.row.get("success")),
            acquired_at=attempt.row.get("acquired_at"),
            acquired_at_text=attempt.acquired_at_text,
        ),
        record=_stored_row(shown.row) if shown is not None else None,
        status=OverviewStatus(text=found.status.text, level=found.status.level),
        paused=source.paused,
        stale=found.stale,
        stale_after_seconds=found.stale_after_seconds,
        poll_cycle_seconds=source.poll_cycle_seconds,
        kpis=[OverviewKpi(key=kpi.key, title=kpi.title, text=kpi.text) for kpi in found.kpis],
        core_metrics=_rows(found.core_metrics),
        table=[OverviewTableGroup(title=title, rows=_rows(rows)) for title, rows in found.table],
        chart=OverviewChart(
            title=chart.title,
            spectrum_state=chart.spectrum_state,
            spectrum=Spectrum(**vars(chart.spectrum)) if chart.spectrum is not None else None,
            y_max=chart.y_max,
            x_ticks=list(X_TICKS),
            overlay=[_rows(column) for column in chart.overlay],
        ),
        details_enabled=found.details_enabled,
        metrics_error=None
        if found.metrics_error is None
        else OverviewError(message=found.metrics_error.message, detail=found.metrics_error.detail),
    )


@router.get(
    "/events",
    summary="事件流（SSE，text/event-stream）：令牌放请求头，不放地址；事件只是提示，状态以 GET 接口为准",
    response_class=StreamingResponse,
)
async def events(request: Request) -> StreamingResponse:
    hub = _context(request).events
    subscription = hub.subscribe(asyncio.get_running_loop())

    async def stream() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"
            while True:
                event = await subscription.next()
                if event is CLOSED:
                    return
                if event is None:
                    event = Event(None, "heartbeat", {"as_of": _context(request).now()})
                yield event.encode()
        finally:
            subscription.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
