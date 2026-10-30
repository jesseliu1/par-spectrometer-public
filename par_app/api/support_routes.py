"""Support routes for the field acceptance of 2.0.0-alpha.2 (D-226): 导出诊断包 (API-27) and 维护记录 (API-28).

Every tier: neither contacts a device, writes a device database or changes a configuration. The bundle writes one
zip into the alpha's output folder (as the other exports, D-207/D-210; the API takes no path); the log reads the
alpha's device databases read only.
"""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Query, Request

from ..application import maintenance_log as log_texts
from ..application.diagnostics_bundle import ServiceInfo
from . import support_models as models
from .operation_routes import EXPORT_ERRORS
from .routes import API_PREFIX, BUILD_COMMIT_ENV, ERRORS, _context

router = APIRouter(prefix=API_PREFIX, responses=ERRORS)


@router.post(
    "/support/diagnostics-bundle",
    response_model=models.DiagnosticsExported,
    status_code=HTTPStatus.CREATED,
    responses={
        **EXPORT_ERRORS,
        int(HTTPStatus.CONFLICT): {
            "model": EXPORT_ERRORS[int(HTTPStatus.CONFLICT)]["model"],
            "description": "busy：另一次诊断包导出正在进行",
        },
    },
    summary="导出诊断包：日志、版本、alpha 配置、状态快照与设备库审计表打成一个 zip，写到 alpha 输出目录（只读设备库）",
)
def diagnostics_export(request: Request) -> models.DiagnosticsExported:
    context = _context(request)
    service = ServiceInfo(
        version=context.version,
        build_commit=context.build_commit or os.environ.get(BUILD_COMMIT_ENV) or None,
        started_at=context.started_at,
    )
    done = context.diagnostics.export(service)
    return models.DiagnosticsExported(
        as_of=context.now(),
        path=done.path,
        directory=done.directory,
        file_name=done.file_name,
        size=done.size,
        files=done.files,
        problems=done.problems,
        text=done.text,
    )


@router.get(
    "/support/maintenance-log",
    response_model=models.MaintenanceLogResponse,
    responses={
        int(HTTPStatus.CONFLICT): {
            "model": EXPORT_ERRORS[int(HTTPStatus.CONFLICT)]["model"],
            "description": "config_unavailable：alpha 的档位 1 配置无法读取",
        },
    },
    summary="维护记录：设备库中记录的每一次设备写入（校准写入、通信参数写入与核对、对时），最新在前（只读）",
)
def maintenance_log(
    request: Request,
    device: Annotated[str | None, Query(description="设备位置 p1–p4；不给为全部设备")] = None,
    limit: Annotated[int, Query(description=f"1–{log_texts.MAX_LIMIT}")] = log_texts.DEFAULT_LIMIT,
    time_sync: Annotated[bool, Query(description="是否包含设备对时（每台设备每小时一条）")] = False,
) -> models.MaintenanceLogResponse:
    context = _context(request)
    found = context.maintenance_log.log(device, limit, time_sync)
    return models.MaintenanceLogResponse(
        as_of=context.now(),
        devices=[
            models.MaintenanceLogDevice(
                key=item.key,
                position=item.position,
                name=item.name,
                database_name=item.database_name,
                state=item.state,
                problem=item.problem,
            )
            for item in found.devices
        ],
        items=[
            models.MaintenanceLogItem(
                device_key=item.device_key,
                device_name=item.device_name,
                occurred_at=item.occurred_at,
                occurred_at_text=item.occurred_at_text,
                kind=item.kind,
                kind_text=item.kind_text,
                before_text=item.before_text,
                after_text=item.after_text,
                readback_text=item.readback_text,
                result=item.result,
                result_text=item.result_text,
                detail=item.detail,
                source=item.source,
            )
            for item in found.items
        ],
        limit=found.limit,
        limit_reached=found.limit_reached,
        time_sync=found.time_sync,
        scan_limited=found.scan_limited,
        texts=models.MaintenanceLogTexts(
            title=log_texts.TITLE,
            note=log_texts.NOTE,
            columns=list(log_texts.COLUMNS),
            empty_text=log_texts.EMPTY_TEXT,
            no_devices_text=log_texts.NO_DEVICES_TEXT,
            time_sync_label=log_texts.TIME_SYNC_LABEL,
            limit_text=log_texts.LIMIT_TEXT.format(limit=found.limit),
            scan_limited_text=log_texts.SCAN_LIMITED_TEXT.format(rows=log_texts.SCAN_ROWS),
        ),
    )
