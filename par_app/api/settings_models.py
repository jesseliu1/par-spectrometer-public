"""Request and response models of the settings page endpoints (api-contract-v0 API-15, API-22, API-23, API-26).

Every text the page shows comes from the service (contract 1.2); the page computes no time range, count or file
name. Tier 0: the settings are read only and nothing on the page writes except the export files (D-209, D-210).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import DATABASE_ID_TEXT, DeviceRef, Source
from .operation_models import ExportFormat


class BusField(BaseModel):
    label: str
    text: str = Field(description="档位 0 恒为“只读快照不含配置”（D-209）")


class SettingsDevice(BaseModel):
    key: str
    position: int
    configured: bool
    state_text: str | None = Field(description="未登记设备的位置为“未配置”（UI-261）；已登记为 null")
    name: str
    slave_id_text: str | None
    enabled_text: str | None
    fail_stop_text: str | None
    database_name: str | None = Field(description="设备库文件名")
    database_path: str | None = Field(description="设备库完整路径")
    snapshot_path: str | None = Field(description="恒为 null（快照时代的副本路径，#83 移除）")
    snapshot_id: str | None = Field(description=DATABASE_ID_TEXT)
    imported_at: str | None = Field(description="恒为 null（快照时代的导入时间，#83 移除）")
    tooltip: str | None = Field(description="悬停全文：设备库路径（EXP-066）")


class RangeOption(BaseModel):
    key: str
    label: str


class ExportTexts(BaseModel):
    title: str
    device_label: str
    range_label: str
    start_label: str
    end_label: str
    count_label: str
    content_label: str
    formats_label: str
    ranges: list[RangeOption] = Field(description="最近 1/2/4/8/24 小时与自定义时间（EXP-068）")
    default_range: str = Field(description="首次进入时的范围（EXP-048）")
    formats: list[ExportFormat]
    content_note: str
    content_tooltip: str
    button_label: str
    counting_text: str
    no_device_text: str
    done_title: str
    failed_title: str
    directory: str = Field(description="导出的父目录：alpha 数据目录 exports/（D-210，同 D-207）")
    note: str


class SettingsView(BaseModel):
    as_of: str
    source: Source = "live_ro"
    tier: int
    title: str
    groups: list[str]
    read_only_text: str
    config_text: str
    config_note: str
    bus: list[BusField]
    device_columns: list[str]
    devices: list[SettingsDevice]
    export: ExportTexts


class DeviceSummaryResponse(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    total: int
    latest: str | None = Field(description="最近一条记录的采集时间（库中原样）")
    records_text: str = Field(description="“最近采集：… · 共 N 条”（UI-080）")
    database_name: str
    database_size_text: str = Field(description="导入时源库文件大小，1 MB = 1,000,000 字节（UI-077）")
    database_text: str
    serial_text: str = Field(description="快照 app_settings 中的设备序列号（UI-081）")
    status_text: str
    poll_cycle_text: str = Field(description="最近一条成功记录采集时的轮询周期（quality_json，D-206 的取值规则）")


class ExportRangeModel(BaseModel):
    mode: str
    start: str = Field(description="开始时间（整秒，北京时间 YYYY-MM-DDTHH:MM:SS）；导出时原样传回")
    end: str = Field(description="结束时间（整秒）；查询含整个结束秒（.999，EXP-050）")
    start_text: str
    end_text: str
    editable: bool = Field(description="自定义时间可编辑；预设范围的起止显示为禁用（EXP-071）")


class ExportConfirmation(BaseModel):
    title: str
    text: str = Field(description="V1.0.3 确认框全文（EXP-053）；目标文件夹为 alpha 输出目录")
    records: int
    files: int


class ExportCount(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    range: ExportRangeModel
    formats: list[str]
    count: int
    files: int
    text: str = Field(description="“预计 N 条记录，将导出为 M 个文件”（EXP-011）")
    can_export: bool = Field(description="记录数与格式数都大于 0 时才可导出（EXP-049）")
    confirm: ExportConfirmation | None = Field(description="此刻点击导出时的确认内容；无记录或未选格式时为 null")
    notice: str | None = Field(
        description="此刻点击导出时 V1.0.3 给出的提示（结束早于开始、范围内没有记录）；有确认内容或未选格式时为 null"
    )


class ExportRequest(BaseModel):
    start: str = Field(description="确认时的开始时间（ExportCount.range.start）")
    end: str = Field(description="确认时的结束时间（ExportCount.range.end）")
    formats: list[str] = Field(description="csv、xlsx 中的一种或两种（EXP-014）")
    snapshot_id: str | None = Field(
        default=None, description="确认时的设备库标识；该位置换了设备库时 409 snapshot_changed"
    )
    records: int | None = Field(
        default=None,
        ge=0,
        description="确认框中的记录数（ExportConfirmation.records）；采集在进行，范围内的记录数与之不同时 409 "
        "snapshot_changed，须重新确认（EXP-052）",
    )


class ExportDoneResponse(BaseModel):
    as_of: str
    directory: str
    device_folder: str
    records: int
    files: int
    text: str = Field(description="“已导出 N 个文件到：…”")


class DeviceStatusLineModel(BaseModel):
    text: str = Field(
        description="状态区第一行（V1.0.3 connection_status_label）：采集正常时“设备名 · 在线 · 采集正常 · "
        "曝光：…”，否则“设备名 · 原因”；未接管时“设备名 · 未在采集：未连接设备”（UI-080）"
    )
    level: str = Field(description="调度器的设备状态级别（ok、warning、error、power、idle…）；未接管时 idle")
    tone: str = Field(description="文字颜色：normal（ok）、warning、error（error、power）、muted（其余）")
    tooltip: str = Field(description="悬停全文：设备名与设备序列号（UI-081）")


class LogEntryModel(BaseModel):
    id: int | None
    occurred_at: str | None = Field(description="库中原样")
    time_text: str
    level: str | None
    category: str = Field(description="库中类别原名")
    category_text: str = Field(description="中文类别，未知类别为“其他”（UI-079）")
    category_tooltip: str
    message: str = Field(description="原始完整消息")
    result_text: str = Field(description="结果列文字")
    result_tooltip: str = Field(description="悬停：完整消息，有详情时另起一行附详情（UI-280）")
    details: str | None = Field(description="details_json 原文")
    error: bool = Field(description="ERROR、WARNING、CRITICAL 行标红（UI-279）")
    details_text: str = Field(description="“日志详情”弹窗的纯文本全文（UI-100、UI-104）")


class DeviceLogResponse(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    status: DeviceStatusLineModel
    columns: list[str] = Field(description="时间、类别、结果")
    details_title: str
    copy_label: str
    items: list[LogEntryModel] = Field(
        description="最近 300 条日志中去掉自动读取通信参数的重复成功消息后，最新在前最多 50 条（UI-076、UI-078）"
    )
