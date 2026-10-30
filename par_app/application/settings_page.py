"""Fixed content of the settings page (API-26): section titles, the 通信设置 rows, the device table's columns and
the 采集记录导出 texts.

The values are the copies in par_app.services.settings_display; this module only gathers them so that the API layer
maps a finished value into its response model and never reads services itself (route C section 4, import contract
"API layer reaches services only through the application layer").
"""

from __future__ import annotations

from dataclasses import dataclass

from ..services import settings_display as texts

__all__ = [
    "DEFAULT_RANGE",
    "LOG_COLUMNS",
    "LOG_COPY_LABEL",
    "LOG_DETAILS_TITLE",
    "UNCONFIGURED",
    "PageExport",
    "SettingsPageContent",
    "page_content",
]

DEFAULT_RANGE = texts.DEFAULT_RANGE
"""EXP-048: the 导出范围 box starts at 最近 1 小时."""
UNCONFIGURED = texts.UNCONFIGURED
"""UI-261: an unregistered position."""
LOG_COLUMNS = texts.LOG_COLUMNS
"""The device log table's columns (设备状态与最近日志)."""
LOG_DETAILS_TITLE = texts.DETAILS_TITLE
LOG_COPY_LABEL = texts.COPY_ALL


@dataclass(frozen=True)
class PageExport:
    """Field for field the API's ExportTexts, except the directory and note the route adds."""

    title: str
    device_label: str
    range_label: str
    start_label: str
    end_label: str
    count_label: str
    content_label: str
    formats_label: str
    ranges: tuple[tuple[str, str], ...]
    """(key, label), presets first, then 自定义时间"""
    default_range: str
    formats: tuple[tuple[str, str, bool], ...]
    """(key, label, checked by default)"""
    content_note: str
    content_tooltip: str
    button_label: str
    counting_text: str
    no_device_text: str
    done_title: str
    failed_title: str


@dataclass(frozen=True)
class SettingsPageContent:
    title: str
    groups: tuple[str, ...]
    bus_fields: tuple[str, ...]
    device_columns: tuple[str, ...]
    export: PageExport


def page_content() -> SettingsPageContent:
    return SettingsPageContent(
        title=texts.PAGE_TITLE,
        groups=texts.GROUPS,
        bus_fields=texts.BUS_FIELDS,
        device_columns=texts.DEVICE_COLUMNS,
        export=PageExport(
            title=texts.EXPORT_GROUP,
            device_label=texts.EXPORT_DEVICE_LABEL,
            range_label=texts.EXPORT_RANGE_LABEL,
            start_label=texts.EXPORT_START_LABEL,
            end_label=texts.EXPORT_END_LABEL,
            count_label=texts.EXPORT_COUNT_LABEL,
            content_label=texts.EXPORT_CONTENT_LABEL,
            formats_label=texts.EXPORT_FORMATS_LABEL,
            ranges=tuple(texts.range_options()),
            default_range=texts.DEFAULT_RANGE,
            formats=texts.EXPORT_FORMATS,
            content_note=texts.EXPORT_CONTENT_NOTE,
            content_tooltip=texts.EXPORT_CONTENT_TOOLTIP,
            button_label=texts.EXPORT_BUTTON,
            counting_text=texts.COUNTING_TEXT,
            no_device_text=texts.NO_DEVICE_TEXT,
            done_title=texts.EXPORT_TITLE,
            failed_title=texts.FAILED_TITLE,
        ),
    )
