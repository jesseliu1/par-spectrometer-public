"""Routes of the settings page (api-contract-v0 API-26 read-only view, API-15 device summary, API-16 device log and
status line, API-22 export count, API-23 export) on the alpha's own device databases (issue #82): read only except
for the export files written into the alpha's own output folder (D-210). No route here saves or applies a
configuration, talks to a device or writes a database (D-209); the tier-1 configuration has its own routes
(acquisition_routes.py).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Query, Request

from ..application import acquisition_export as use_case
from ..application import settings as settings_use_case
from ..application import settings_page
from . import settings_models as models
from .models import DeviceRef
from .operation_models import ExportFormat
from .operation_routes import EXPORT_ERRORS
from .routes import API_PREFIX, ERRORS, Key, _context

router = APIRouter(prefix=API_PREFIX, responses=ERRORS)
EXPORT_NOTE = (
    "本软件不弹出目录选择框：文件写到下面的输出目录，按“设备\\格式\\采集日期\\文件”分目录存放；"
    "同一条记录再次导出会覆盖同名文件。设备库不会被改动。"
)


def _export_texts(directory: str) -> models.ExportTexts:
    page = settings_page.page_content().export
    return models.ExportTexts(
        title=page.title,
        device_label=page.device_label,
        range_label=page.range_label,
        start_label=page.start_label,
        end_label=page.end_label,
        count_label=page.count_label,
        content_label=page.content_label,
        formats_label=page.formats_label,
        ranges=[models.RangeOption(key=key, label=label) for key, label in page.ranges],
        default_range=page.default_range,
        formats=[
            ExportFormat(key=key, label=label, checked=checked)  # type: ignore[arg-type]
            for key, label, checked in page.formats
        ],
        content_note=page.content_note,
        content_tooltip=page.content_tooltip,
        button_label=page.button_label,
        counting_text=page.counting_text,
        no_device_text=page.no_device_text,
        done_title=page.done_title,
        failed_title=page.failed_title,
        directory=directory,
        note=EXPORT_NOTE,
    )


def _device(row: settings_use_case.DeviceRow) -> models.SettingsDevice:
    database = row.database
    if database is None or not row.slot.readable:  # not offered for export: reading it is refused (16_ 3.2)
        return models.SettingsDevice(
            key=row.slot.key,
            position=row.slot.position,
            configured=False,
            state_text=settings_page.UNCONFIGURED if database is None else settings_use_case.UNREADABLE,
            name="",
            slave_id_text=None,
            enabled_text=None,
            fail_stop_text=None,
            database_name=None,
            database_path=None,
            snapshot_path=None,
            snapshot_id=None,
            imported_at=None,
            tooltip=None,
        )
    return models.SettingsDevice(
        key=row.slot.key,
        position=row.slot.position,
        configured=True,
        state_text=None,
        name=database.name,
        slave_id_text=None,
        enabled_text=None,
        fail_stop_text=None,
        database_name=database.file_name,
        database_path=database.path,
        snapshot_path=None,
        snapshot_id=database.id,
        imported_at=None,
        tooltip=row.tooltip,
    )


@router.get(
    "/settings",
    response_model=models.SettingsView,
    summary="设置与导出页：登记的设备（档位 0 无）与导出区文字；档位 1 的配置见 /acquisition-config",
)
def settings(request: Request) -> models.SettingsView:
    context = _context(request)
    page = settings_page.page_content()
    return models.SettingsView(
        as_of=context.now(),
        tier=context.acquisition.tier(),  # the tier now, as /health and /tier say (PR #95 review)
        title=page.title,
        groups=list(page.groups),
        read_only_text=settings_use_case.READ_ONLY_TEXT,
        config_text=settings_use_case.NO_CONFIG,
        config_note=settings_use_case.CONFIG_NOTE,
        bus=[models.BusField(label=label, text=settings_use_case.NO_CONFIG) for label in page.bus_fields],
        device_columns=list(page.device_columns),
        devices=[_device(row) for row in context.settings.rows()],
        export=_export_texts(str(context.paths.exports_dir)),
    )


@router.get(
    "/devices/{key}/summary",
    response_model=models.DeviceSummaryResponse,
    summary="设备状态区：记录总数与最近采集、库文件与大小、序列号、记录中的轮询周期（设备库）",
)
def summary(request: Request, key: Key) -> models.DeviceSummaryResponse:
    context = _context(request)
    found = context.settings.summary(key)
    return models.DeviceSummaryResponse(
        as_of=context.now(),
        snapshot_id=found.device.id,
        device=DeviceRef(key=found.device.key, name=found.device.name),
        total=found.total,
        latest=found.latest,
        records_text=found.records_text,
        database_name=found.database_name,
        database_size_text=found.database_size_text,
        database_text=found.database_text,
        serial_text=found.serial_text,
        status_text=found.status_text,
        poll_cycle_text=found.poll_cycle_text,
    )


@router.get(
    "/devices/{key}/logs",
    response_model=models.DeviceLogResponse,
    summary="设备状态与最近日志：调度器的设备状态（档位 1 已接管时）与设备库最近日志（只读，UI-078）",
)
def logs(request: Request, key: Key) -> models.DeviceLogResponse:
    context = _context(request)
    found = context.settings.log(key)
    status = found.status
    return models.DeviceLogResponse(
        as_of=context.now(),
        snapshot_id=found.device.id,
        device=DeviceRef(key=found.device.key, name=found.device.name),
        status=models.DeviceStatusLineModel(
            text=status.text, level=status.level, tone=status.tone, tooltip=status.tooltip
        ),
        columns=list(settings_page.LOG_COLUMNS),
        details_title=settings_page.LOG_DETAILS_TITLE,
        copy_label=settings_page.LOG_COPY_LABEL,
        items=[models.LogEntryModel(**vars(entry)) for entry in found.entries],
    )


def _range(found: use_case.ExportRange) -> models.ExportRangeModel:
    return models.ExportRangeModel(
        mode=found.mode,
        start=found.start_value,
        end=found.end_value,
        start_text=found.start_text,
        end_text=found.end_text,
        editable=found.editable,
    )


@router.get(
    "/devices/{key}/export/count",
    response_model=models.ExportCount,
    summary="导出条数预览：预设范围按此刻北京时间重算，含结束秒（EXP-011、EXP-050、EXP-051）",
)
def export_count(
    request: Request,
    key: Key,
    range: Annotated[str, Query(description="1h、2h、4h、8h、24h 或 custom")] = settings_page.DEFAULT_RANGE,  # noqa: A002
    start: Annotated[str | None, Query(description="custom 时必填：YYYY-MM-DDTHH:MM:SS（北京时间）")] = None,
    end: Annotated[str | None, Query(description="custom 时必填：YYYY-MM-DDTHH:MM:SS（北京时间）")] = None,
    formats: Annotated[list[str] | None, Query(description="勾选的格式 csv、xlsx（可不选）")] = None,
) -> models.ExportCount:
    context = _context(request)
    exports = context.acquisition_export
    preview = exports.preview(key, exports.resolve(range, start, end), formats or [])
    confirm = preview.confirm
    return models.ExportCount(
        as_of=context.now(),
        snapshot_id=preview.device.id,
        device=DeviceRef(key=preview.device.key, name=preview.device.name),
        range=_range(preview.range),
        formats=preview.kinds,
        count=preview.count,
        files=preview.files,
        text=preview.text,
        can_export=preview.can_export,
        notice=preview.notice,
        confirm=None
        if confirm is None
        else models.ExportConfirmation(
            title=confirm.title, text=confirm.text, records=confirm.records, files=confirm.files
        ),
    )


@router.post(
    "/devices/{key}/export",
    response_model=models.ExportDoneResponse,
    status_code=HTTPStatus.CREATED,
    responses={
        **EXPORT_ERRORS,
        int(HTTPStatus.CONFLICT): {
            "model": EXPORT_ERRORS[int(HTTPStatus.CONFLICT)]["model"],
            "description": "snapshot_changed：确认后该位置换了设备库（配置已改）；busy：另一次导出正在进行",
        },
    },
    summary="导出采集记录：每条记录每种格式一个文件，写到 alpha 输出目录的 设备/格式/日期 下（V1.0.3 格式）",
)
def export(request: Request, key: Key, body: models.ExportRequest) -> models.ExportDoneResponse:
    context = _context(request)
    done = context.acquisition_export.export(key, body.start, body.end, body.formats, body.snapshot_id, body.records)
    return models.ExportDoneResponse(
        as_of=context.now(),
        directory=done.directory,
        device_folder=done.device_folder,
        records=done.records,
        files=done.files,
        text=done.text,
    )
