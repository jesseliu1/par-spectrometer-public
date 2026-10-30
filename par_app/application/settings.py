"""Settings view of the alpha (设置与导出 page; API-26, API-15; D-209, its snapshot part superseded by issue #82).

The devices are those of the alpha's own configuration (own_devices.py); tier 0 lists none. In tier 1 the page
edits the configuration itself (acquisition-config, 16_ 3.1); this view only lists the devices for the export and
gives the device status area (UI-080) from the device's own database, read only:
  * the database file name and its current size (UI-077, as V1.0.3 database_summary_text);
  * the record total and last acquisition (ParDatabase.acquisition_summary, UI-080);
  * the device identity V1.0.3 stored in app_settings (par_device_identity, UI-081);
  * the poll cycle recorded with the latest successful record (quality_json.poll_cycle_seconds, the D-206 rule).
In tier 1 it also gives V1.0.3's "设备状态与最近日志" (MainWindow.refresh_settings_console, issue #107): the status
line from the coordinator's device state in the takeover's StatusCache (16_ 1.4: never the coordinator itself), and
the device log from the database's diagnostics table, which V1.0.3's code writes while the alpha acquires.
Nothing here saves, applies or writes anything, and nothing asks the device for anything (UI-101).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from ..database import format_beijing_time
from ..services import settings_display as texts
from .dli import poll_cycle
from .errors import DatabaseUnavailable
from .own_devices import DeviceDatabase, DeviceSlot, OwnDevices
from .readonly import Row, SnapshotDiagnostics, SnapshotDli, SnapshotExport

NO_CONFIG = "只读模式不读取配置"
READ_ONLY_TEXT = "只读模式：不连接、不写设备，不保存、不应用配置；开启采集模式后在这里登记设备并采集。"
CONFIG_NOTE = (
    "总线参数和设备登记（从站地址、启用采集、失败停止）保存在本软件的配置文件里；只读模式不读取它，"
    "也不显示任何设备的数据。"
)
TOOLTIP = "设备库：{path}"
UNREADABLE = "设备库不在本软件的数据目录中，不能读取"
"""A registered device whose database lies outside <data dir>/data/devices (16_ 3.2): not offered for export."""
STATUS_TEXT = "{name} · 本机 2.0 采集的设备库"
NO_SERIAL = "设备序列号：库中没有记录"
LATEST_EVER = "9999-12-31T23:59:59.999"
"""Upper bound that lets the D-206 query look at every record (stored times are ISO text below it)."""
CYCLE_RECORDED = "{seconds:g} 秒（取自 {recorded_at} 的采集记录）"
CYCLE_UNUSABLE = "{recorded_at} 的采集记录中没有可用的轮询周期"
CYCLE_NO_RECORD = "库中没有成功的采集记录"
NOT_TAKEN_OVER = "未在采集：未连接设备"
"""The status line while the alpha has not taken over (V1.0.3 always acquires): the bus line the takeover host shows
after a stop (acquisition_host.host.RELEASED_BUS)."""


@dataclass(frozen=True)
class DeviceRow:
    slot: DeviceSlot

    @property
    def database(self) -> DeviceDatabase | None:
        return self.slot.database

    @property
    def tooltip(self) -> str | None:
        database = self.database
        return None if database is None else TOOLTIP.format(path=database.path)


@dataclass(frozen=True)
class DeviceSummary:
    device: DeviceDatabase
    total: int
    latest: str | None
    records_text: str
    database_name: str
    database_size_text: str
    database_text: str
    serial_text: str
    status_text: str
    poll_cycle_text: str


@dataclass(frozen=True)
class LogEntry:
    id: int | None
    occurred_at: str | None
    time_text: str
    level: str | None
    category: str
    category_text: str
    category_tooltip: str
    message: str
    result_text: str
    result_tooltip: str
    details: str | None
    error: bool
    details_text: str


@dataclass(frozen=True)
class DeviceStatusLine:
    text: str
    level: str
    tone: str
    tooltip: str


@dataclass(frozen=True)
class DeviceLog:
    device: DeviceDatabase
    status: DeviceStatusLine
    entries: list[LogEntry]


def file_name(path: str) -> str:
    """The last part of a stored path, whichever system wrote it (a Windows path read on another system too)."""
    return PurePath(path.replace("\\", "/")).name


def serial_text(identity: Any) -> str:  # noqa: ANN401 - the stored JSON as decoded
    """SERIAL_TEXT of the stored identity; anything V1.0.3 could not format reads as "not recorded"."""
    if isinstance(identity, dict):
        try:
            return texts.SERIAL_TEXT.format(serial=int(identity["serial_number"]))
        except (KeyError, TypeError, ValueError, OverflowError):
            return NO_SERIAL
    return NO_SERIAL


def _size(path: Path) -> int:
    """The database file's size now (V1.0.3 database_summary_text); the summary has just read the file."""
    try:
        return path.stat().st_size
    except OSError as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error


class SettingsQueries:
    def __init__(self, devices: OwnDevices) -> None:
        self.devices = devices

    def rows(self) -> list[DeviceRow]:
        return [DeviceRow(slot) for slot in self.devices.devices()]

    def summary(self, key: str) -> DeviceSummary:
        device = self.devices.database_for(key)
        path = Path(device.path)
        database = SnapshotExport(path)
        summary = database.summary()
        latest = summary["latest"]
        name = device.file_name
        size = texts.size_text(_size(path))
        cycle = poll_cycle(SnapshotDli(path).poll_cycle_record(LATEST_EVER, LATEST_EVER))
        if cycle.record_at is None:
            cycle_text = CYCLE_NO_RECORD
        elif cycle.source == "record":
            cycle_text = CYCLE_RECORDED.format(seconds=cycle.seconds, recorded_at=format_beijing_time(cycle.record_at))
        else:
            cycle_text = CYCLE_UNUSABLE.format(recorded_at=format_beijing_time(cycle.record_at))
        return DeviceSummary(
            device=device,
            total=int(summary["total"]),
            latest=None if latest is None else str(latest),
            records_text=texts.RECORDS_TEXT.format(latest=format_beijing_time(latest), total=summary["total"]),
            database_name=name,
            database_size_text=size,
            database_text=texts.DATABASE_TEXT.format(name=name, size=size),
            serial_text=serial_text(database.identity()),
            status_text=STATUS_TEXT.format(name=device.name),
            poll_cycle_text=cycle_text,
        )

    def log(self, key: str) -> DeviceLog:
        """设备状态与最近日志 of the device at `key` (tier 1; tier 0 has no device, 404 as every device read)."""
        device = self.devices.database_for(key)
        return device_log(device, self.devices.acquisition.cache.snapshot())


def _same_file(left: str, right: str) -> bool:
    return Path(left).resolve() == Path(right).resolve()


def device_state(snapshot: dict[str, Any], device: DeviceDatabase) -> dict[str, Any] | None:
    """The coordinator's state of this device while the alpha acquires: the cache entry at its position, if it is of
    the same database (a saved configuration not applied yet may have put another one there); else None."""
    for entry in snapshot["devices"]:
        if entry.get("position") == device.key and _same_file(str(entry.get("database_path")), device.path):
            return dict(entry)
    return None


def identity_serial_text(identity: Any) -> str:  # noqa: ANN401 - the stored JSON as decoded
    """refresh_settings_console's serial line; an identity V1.0.3 could not format reads as not read yet."""
    if identity:
        text = serial_text(identity)
        if text != NO_SERIAL:
            return text
    return texts.NO_IDENTITY_TEXT


def status_line(snapshot: dict[str, Any], device: DeviceDatabase, identity: Any) -> DeviceStatusLine:  # noqa: ANN401
    """V1.0.3's connection_status_label for `device`: its state, or DeviceHub.idle_status() before it has one; while
    nothing is taken over the alpha says so instead."""
    if snapshot["takeover"] != "running":
        level, text = texts.IDLE_LEVEL, texts.HEADLINE.format(name=device.name, message=NOT_TAKEN_OVER)
    else:
        state = device_state(snapshot, device) or {"level": texts.IDLE_LEVEL, "message": texts.IDLE_MESSAGE}
        level = str(state.get("level"))
        text = texts.status_headline(device.name, level, str(state.get("message")), state.get("exposure_status"))
    return DeviceStatusLine(
        text=text,
        level=level,
        tone=texts.LEVEL_TONES.get(level, texts.MUTED_TONE),
        tooltip=texts.STATUS_TOOLTIP.format(name=device.name, serial=identity_serial_text(identity)),
    )


def _text(value: object) -> str:
    """str(value or "—"), as refresh_settings_console reads category and message."""
    return str(value or texts.MISSING)


def log_entry(event: Row, name: str, database: Path) -> LogEntry:
    """One row of the log table with its tooltips and the 日志详情 snapshot (refresh_settings_console)."""
    category, message = _text(event.get("category")), _text(event.get("message"))
    category_text = texts.CATEGORY_NAMES.get(category, texts.OTHER_CATEGORY)
    raw = event.get("details_json")
    details = str(raw or "")
    time_text = format_beijing_time(event.get("occurred_at"))
    level = event.get("level")
    return LogEntry(
        id=None if event.get("id") is None else int(event["id"]),
        occurred_at=None if event.get("occurred_at") is None else str(event["occurred_at"]),
        time_text=time_text,
        level=None if level is None else str(level),
        category=category,
        category_text=category_text,
        category_tooltip=f"{category_text}\n{category}",
        message=message,
        result_text=texts.MESSAGE_NAMES.get(message, message),
        result_tooltip=message + (f"\n{details}" if details and details != "{}" else ""),
        details=None if raw is None else str(raw),
        error=level in texts.ERROR_LEVELS,
        details_text=texts.DETAILS_TEXT.format(
            name=name,
            database=database.resolve(),
            time=time_text,
            level=level or texts.MISSING,
            category_text=category_text,
            category=category,
            message=message,
            details=details or texts.MISSING,
        ),
    )


def device_log(device: DeviceDatabase, snapshot: dict[str, Any]) -> DeviceLog:
    path = Path(device.path)
    events = SnapshotDiagnostics(path).recent(texts.LOG_SCAN_ROWS)  # read first: a failed read keeps the page as is
    identity = SnapshotExport(path).identity()
    shown = [event for event in events if texts.log_shown(event)][: texts.LOG_SHOWN_ROWS]
    return DeviceLog(
        device=device,
        status=status_line(snapshot, device, identity),
        entries=[log_entry(event, device.name, path) for event in shown],
    )
