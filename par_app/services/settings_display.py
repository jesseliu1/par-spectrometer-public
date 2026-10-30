"""Texts and small rules of the V1.0.3 设置与导出 page that the alpha's read-only settings view and its
acquisition-record export repeat (stage two, route C; docs/design/ui-v2-pages.md 2.5).

Copied out of the frozen par_app/ui.py (MainWindow._build_settings, update_export_range, _current_export_range,
refresh_export_count, export_acquisitions, refresh_database_summary) and par_app/ui_unconfigured.py
(database_summary_text); tests/api/test_acquisition_export_parity.py compares them with the real window.
The files themselves are written by par_app.services.export, unchanged.

No clock is read here (R-1-6): the caller passes the moment a preset range ends at.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

PAGE_TITLE = "设置与导出"
"""UI-124: the page's name in the main navigation."""
COMM_GROUP = "通信设置"
DEVICE_GROUP = "设备登记"
EXPORT_GROUP = "采集记录导出"
ACTIVITY_GROUP = "设备状态与最近日志"
GROUPS = (COMM_GROUP, DEVICE_GROUP, EXPORT_GROUP, ACTIVITY_GROUP)
"""UI-075: the section titles (the fifth, 关于与技术支持, is not part of the alpha view)."""
BUS_FIELDS = ("连接方式", "计算机串口", "波特率", "奇偶校验", "TCP 主机", "TCP 端口", "全总线轮询周期")
"""The 通信设置 rows of _build_settings (UI-090, UI-135)."""
DEVICE_COLUMNS = ("设备名称", "从站地址", "启用采集", "失败停止", "数据库文件")
"""UI-099: the device registration table's columns, in this order."""
UNCONFIGURED = "未配置"
"""UI-261: an unregistered position."""

# --- 采集记录导出 (MainWindow._build_settings) ---------------------------------------------------------------------
EXPORT_DEVICE_LABEL = "导出设备"
EXPORT_RANGE_LABEL = "导出范围"
EXPORT_START_LABEL = "开始时间"
EXPORT_END_LABEL = "结束时间"
EXPORT_COUNT_LABEL = "预计记录数"
EXPORT_CONTENT_LABEL = "内容"
EXPORT_FORMATS_LABEL = "导出格式"
EXPORT_PRESET_HOURS = (1, 2, 4, 8, 24)
"""EXP-048, EXP-068: 最近 1/2/4/8/24 小时; the first is the default."""
CUSTOM_RANGE = "custom"
CUSTOM_RANGE_LABEL = "自定义时间"
EXPORT_CONTENT_NOTE = "每条记录一个文件，包含指标与 701 点原始光谱。"
EXPORT_CONTENT_TOOLTIP = "包含状态、软件指标和硬件光度参数；按设备、格式、采集日期分目录存放。"
EXPORT_FORMATS: tuple[tuple[str, str, bool], ...] = (("csv", "CSV", True), ("xlsx", "Excel (.xlsx)", False))
"""EXP-014: the two format check boxes; CSV is ticked at first."""
EXPORT_BUTTON = "导出采集记录"
COUNTING_TEXT = "正在统计记录数…"
COUNT_TEXT = "预计 {count} 条记录，将导出为 {files} 个文件"
"""EXP-011: records × chosen formats."""
NO_DEVICE_TEXT = "尚未配置导出设备"

# --- export_acquisitions -------------------------------------------------------------------------------------------
EXPORT_TITLE = "导出"
NO_SOURCE_TEXT = "请先选择已登记的导出设备。"
RANGE_TITLE = "导出范围"
END_BEFORE_START_TEXT = "结束时间不能早于开始时间。"
NO_RECORDS_TEXT = "所选时间范围内没有采集记录。"
CONFIRM_TITLE = "确认导出"
CONFIRM_TEXT = (
    "导出设备：{device}\n时间范围：{start} 至 {end}\n"
    "共 {records} 条采集记录，将导出为 {files} 个文件（{formats}）。\n"
    "目录结构：{folder}\\格式\\采集日期\\文件\n\n"
    "目标文件夹：{target}\n\n是否继续？"
)
"""EXP-053, EXP-059: the one confirmation before writing."""
FAILED_TITLE = "导出失败"
RECORD_FAILED_TEXT = "记录 ID {id} 导出失败：\n{error}"
PARTIAL_TEXT = "导出结束：成功 {success} 个文件，失败 {failed} 个文件。"
DONE_TEXT = "已导出 {count} 个文件到：\n{folder}"

# --- status area (refresh_database_summary, database_summary_text) ------------------------------------------------
RECORDS_TEXT = "最近采集：{latest} · 共 {total} 条"
"""UI-080: last acquisition time and total."""
DATABASE_TEXT = "数据库：{name} · 文件大小：{size}"
"""UI-077."""
BYTES_PER_MB = 1_000_000
"""UI-077: 1 MB = 1,000,000 bytes (ui_unconfigured.BYTES_PER_MB)."""
SERIAL_TEXT = "设备序列号：0x{serial:08X}"
"""UI-081: the serial number in the status line's tooltip."""

RANGE_TEXT_FORMAT = "%Y-%m-%d %H:%M:%S"
"""How the start/end editors show a time (QDateTimeEdit display format yyyy-MM-dd HH:mm:ss)."""
QUERY_START_FORMAT = "%Y-%m-%dT%H:%M:%S"
"""EXP-050: the start bound is the whole start second."""
QUERY_END_FORMAT = "%Y-%m-%dT%H:%M:%S.999"
"""EXP-050, #11: the end bound includes the whole end second."""


def range_options() -> list[tuple[str, str]]:
    """(key, label) of the 导出范围 box in order: the presets, then 自定义时间."""
    return [(f"{hours}h", f"最近 {hours} 小时") for hours in EXPORT_PRESET_HOURS] + [(CUSTOM_RANGE, CUSTOM_RANGE_LABEL)]


DEFAULT_RANGE = range_options()[0][0]


def preset_hours(key: str) -> int | None:
    """Hours of a preset key ("1h" … "24h"), None for 自定义时间 or anything else (_current_export_range)."""
    return {f"{hours}h": hours for hours in EXPORT_PRESET_HOURS}.get(key)


def preset_range(hours: int, now: datetime) -> tuple[datetime, datetime]:
    """EXP-051: a preset ends at the given Beijing time and starts `hours` earlier."""
    return now - timedelta(hours=hours), now


def query_bounds(start: datetime, end: datetime) -> tuple[str, str]:
    """[start second .000, end second .999] as compared with the stored text (refresh_export_count, EXP-050)."""
    return f"{start:{QUERY_START_FORMAT}}", f"{end:{QUERY_END_FORMAT}}"


def count_text(count: int, formats: int) -> str:
    return COUNT_TEXT.format(count=count, files=count * formats)


def format_names(kinds: Sequence[str]) -> str:
    """ "CSV、Excel" in the confirmation (export_service.format_label of each chosen kind)."""
    return "、".join("CSV" if kind == "csv" else "Excel" for kind in kinds)


def confirm_text(
    device: str, start: datetime, end: datetime, records: int, kinds: Sequence[str], folder: str, target: str
) -> str:
    return CONFIRM_TEXT.format(
        device=device,
        start=f"{start:{RANGE_TEXT_FORMAT}}",
        end=f"{end:{RANGE_TEXT_FORMAT}}",
        records=records,
        files=records * len(kinds),
        formats=format_names(kinds),
        folder=folder,
        target=target,
    )


def size_text(size_bytes: int) -> str:
    return f"{size_bytes / BYTES_PER_MB:.2f} MB"


# --- 设备状态与最近日志 (MainWindow.refresh_settings_console, _show_settings_log_details) ----------------------------
LOG_SCAN_ROWS = 300
"""UI-078: the newest 300 diagnostics rows are read (ParDatabase.recent_diagnostics(300)) ..."""
LOG_SHOWN_ROWS = 50
"""... and at most 50 of them are shown after the filter."""
HIDDEN_LOG = ("INFO", "connection", "已读取设备当前通信参数")
"""UI-076: (level, category, message) of the repeated automatic parameter read that the table leaves out."""
LOG_COLUMNS = ("时间", "类别", "结果")
CATEGORY_NAMES = {
    "connection": "连接",
    "time_sync": "设备对时",
    "communication": "通信异常",
    "communication_recovery": "通信恢复",
    "acquisition": "采集异常",
    "acquisition_halted": "采集停止",
    "device": "设备",
    "read_identity": "设备身份",
    "diagnostics_read": "设备诊断",
    "comm_read": "通信参数",
    "comm_write": "通信参数",
    "communication_maintenance": "通信维护",
    "maintenance_read": "通信参数",
    "maintenance_write": "通信参数",
    "maintenance_verify": "参数核对",
    "calibration_read": "校准读取",
    "calibration_write": "校准写入",
}
"""UI-079: the category column in Chinese; any other category reads OTHER_CATEGORY."""
OTHER_CATEGORY = "其他"
MESSAGE_NAMES = {"已读取设备维护诊断": "设备诊断读取成功", "已读取设备当前通信参数": "通信参数读取成功"}
"""The result column shows these two messages under another name; every other message as stored."""
ERROR_LEVELS = frozenset({"ERROR", "WARNING", "CRITICAL"})
"""UI-279: rows of these levels are shown in red."""
MISSING = "—"
DETAILS_TITLE = "日志详情"
COPY_ALL = "复制全部"
DETAILS_TEXT = (
    "设备：{name}\n数据库：{database}\n"
    "时间：{time}\n"
    "级别：{level}\n类别：{category_text}（{category}）\n\n"
    "消息：\n{message}\n\n详情：\n{details}"
)
"""UI-100, UI-104: the snapshot the 日志详情 dialog shows, plain text."""
HEADLINE_OK = "{name} · 在线 · 采集正常"
HEADLINE = "{name} · {message}"
EXPOSURE_SUFFIX = " · 曝光：{exposure}"
EXPOSURE_NAMES: dict[object, str] = {0: "正常", 1: "过曝光", 2: "欠曝光"}
UNKNOWN_EXPOSURE = "未知"
IDLE_LEVEL = "idle"
IDLE_MESSAGE = "等待本次采集"
"""DeviceHub.idle_status(): the status line before the device has a state."""
NO_IDENTITY_TEXT = "设备序列号：尚未读取"
"""UI-081: the tooltip when no device identity is stored."""
STATUS_TOOLTIP = "{name}\n{serial}"
LEVEL_TONES = {"ok": "normal", "warning": "warning", "error": "error", "power": "error"}
"""The status line's colour by level (ok in the normal text colour); any other level is muted."""
MUTED_TONE = "muted"


def log_shown(event: Mapping[str, object]) -> bool:
    """UI-076: False only for the repeated automatic read of the communication parameters."""
    return (event.get("level"), event.get("category"), event.get("message")) != HIDDEN_LOG


def status_headline(name: str, level: str, message: str, exposure_status: object) -> str:
    """The first line of the status area for a device state (level, message, exposure of the latest record)."""
    if level != "ok":
        return HEADLINE.format(name=name, message=message)
    headline = HEADLINE_OK.format(name=name)
    if exposure_status is not None:
        exposure = EXPOSURE_NAMES.get(exposure_status, UNKNOWN_EXPOSURE)
        headline += EXPOSURE_SUFFIX.format(exposure=exposure)
    return headline
