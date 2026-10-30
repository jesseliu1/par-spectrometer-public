"""The alpha's tier-1 configuration: <data dir>/config/app_config.json, V1.0.3's format (16_ 3.1, 3.2).

Read and written only through V1.0.3's AppConfigStore(root=<alpha data dir>) and DeviceHub.apply, so the format is
unchanged (red line 3). The page view reads the JSON itself and opens no database: AppConfigStore.load() would
"repair" paths and run PRAGMA journal_mode=WAL on candidate databases, and load_for_startup() opens each database.

Hard rule (D-212 question 3): every device database must resolve into <data dir>/data/devices/. The service never
takes a database path from a client: a new device gets DeviceHub.apply's default path (data/devices/<name>.sqlite3
under the alpha data directory); a device may keep only a path the alpha configuration already holds, or, when its
row asks for it (`reuse_existing`, D-215), the database of the same default name already in the alpha's devices
folder (V1.0.3 asks to choose that file explicitly; the browser has no file dialog).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..app_config import AppConfigStore, ensure_device_count
from ..application.errors import ConfigUnavailable, InvalidArgument
from ..application.paths import OUTSIDE_ALPHA
from ..coordinator import MAX_CONSECUTIVE_FAILURES
from ..maintenance import BAUDRATES
from ..models import (
    DEFAULT_DEVICE_DATABASE_DIR,
    MAX_DEVICES,
    MAX_POLL_CYCLE_SECONDS,
    MIN_POLL_CYCLE_SECONDS,
    AppConfig,
    BusConfig,
    DeviceConfig,
)

NO_DATABASE_TO_REUSE = "数据目录中没有同名库 {name}，无法沿用；取消“沿用数据目录中的同名库”即可新建"
REUSE_LABEL = "沿用数据目录中的同名库"
REUSE_TOOLTIP = (
    "该设备的默认库（按设备名称）已在数据目录中时勾选，继续使用这个库；只能沿用本软件数据目录 data/devices 中的库"
)
SLAVE_ID_RANGE = (1, 247)
"""V1.0.3's settings page: id_spin.setRange(1, 247) (DeviceHub.apply checks the same range)."""
TCP_PORT_RANGE = (1, 65535)
"""V1.0.3's settings page: tcp_port.setRange(1, 65535)."""
POLL_DECIMALS = 1
"""V1.0.3's settings page: interval.setDecimals(1)."""
RECONFIGURE_TITLE = "配置或数据库不可用"
RECONFIGURE_TEXT = (
    "为保护历史数据，本软件不会自动创建或替换上述数据库，也不会开始采集。\n"
    "建议恢复原文件/磁盘后再点“开始采集”；或以空配置重新登记设备（可勾选“沿用数据目录中的同名库”继续使用原库）。\n"
    "选择重新配置后，原配置暂不修改；明确保存新配置时会先备份原配置。\n"
    "若原设备有通信写入待核对，请先恢复原数据库，不要用新库绕过核对。\n\n"
    "是否以空配置重新配置？"
)
"""V1.0.3's question (main.create_startup_hub) for the alpha: no "进入设置" (the form is already the settings page),
and the original file is backed up as V1.0.3 does it (D-141, CONF-010; D-220)."""
RECONFIGURE_LABEL = "以空配置重新配置…"
RECONFIGURE_HINT = (
    "正在以空配置重新配置：保存时先备份原配置文件（app_config.before_recovery_<时间>.json），不需要先开始采集。"
)
APPLY_FAILED_TEXT = (
    "上次保存的配置未生效：正在采集的仍是原配置。配置文件中已是新配置，停止后再开始采集会按新配置开始。"
    "可修改后重新保存。"
)
"""After a failed background apply (D-178 B rollback; D-221): V1.0.3 keeps its save button disabled (DEF-31)."""


ALPHA_TEXTS: dict[str, str] = {
    # alpha-only texts (D-214): the port is picked from the computer's list (V1.0.3's 刷新串口, #74) or typed;
    # no file dialog in the browser, so new databases are named by the program; saving needs a running takeover
    # (16_ section 5)
    "serial_port_hint": "可从列表中选择本机串口，也可手动填写（如 COM3）；软件不自动搜索或切换端口。",
    "new_database_text": "保存时在数据目录新建",
    "save_requires_running": "保存会立即应用到正在运行的采集，需先在“实时概览”点“开始采集”。",
    "reuse_label": REUSE_LABEL,
    "reuse_tooltip": REUSE_TOOLTIP,
    "reconfigure_title": RECONFIGURE_TITLE,
    "reconfigure_text": RECONFIGURE_TEXT,
    "reconfigure_label": RECONFIGURE_LABEL,
    "reconfigure_hint": RECONFIGURE_HINT,
    "apply_failed_text": APPLY_FAILED_TEXT,
}
"""Texts of the alpha only (D-214, D-215, D-220, D-221), added to V1.0.3's form."""


def form() -> dict[str, Any]:
    """V1.0.3's settings-page form (MainWindow._build_settings_page, _refresh_interval_range, save_local_settings):
    labels, choices, ranges, hints and tooltips word for word (except the restart sentence of the 失败停止 tooltip),
    so the page renders it and writes no rule itself."""
    return {
        "labels": [
            {"key": "transport", "label": "连接方式"},
            {"key": "serial_port", "label": "计算机串口"},
            {"key": "baudrate", "label": "波特率"},
            {"key": "parity", "label": "奇偶校验"},
            {"key": "host", "label": "TCP 主机"},
            {"key": "tcp_port", "label": "TCP 端口"},
            {"key": "poll_cycle_seconds", "label": "全总线轮询周期"},
        ],
        "transports": [
            {"value": "rtu", "label": "Modbus RTU（串口）"},
            {"value": "tcp", "label": "Modbus TCP 客户端（网口）"},
        ],
        "baudrates": list(BAUDRATES),
        "parities": [
            {"value": "N", "label": "无校验"},
            {"value": "O", "label": "奇校验"},
            {"value": "E", "label": "偶校验"},
        ],
        "parity_tooltip": "8 数据位、1 停止位（8N1 / 8O1 / 8E1），总线设备共用",
        "poll_min": MIN_POLL_CYCLE_SECONDS,
        "poll_max": MAX_POLL_CYCLE_SECONDS,
        "poll_decimals": POLL_DECIMALS,
        "poll_hint": (
            f"下限 {MIN_POLL_CYCLE_SECONDS:.0f} s；上限 {MAX_POLL_CYCLE_SECONDS:.0f} s（60 分钟），不随设备数量变化。"
        ),
        "poll_tooltip": "轮询周期40至3600秒，与设备数量无关",
        "slave_min": SLAVE_ID_RANGE[0],
        "slave_max": SLAVE_ID_RANGE[1],
        "tcp_port_min": TCP_PORT_RANGE[0],
        "tcp_port_max": TCP_PORT_RANGE[1],
        "device_columns": ["设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"],
        "name_placeholders": [f"光谱仪{row + 1}" for row in range(MAX_DEVICES)],
        "enabled_tooltip": "勾选后参与总线轮询采集",
        "fail_stop_tooltip": (
            # V1.0.3 says "需重启软件后重新尝试": in the alpha a new coordinator comes from stopping and starting
            # again (D-215 question 5; spec review M-2)
            f"勾选：连续 {MAX_CONSECUTIVE_FAILURES} 次通信失败后自动退出本次采集，"
            "需在“实时概览”停止采集后再开始采集，重新尝试；\n"
            "取消（默认）：按轮询周期持续重试，不自动退出，故障排除后自动恢复采集。\n"
            "硬件异常（探头未初始化或要求重新上电）的全局停止不受本开关影响。"
        ),
        "save_label": "保存并应用全部配置",
        "save_tooltip": "仅保存软件连接参数和设备登记，不写入设备硬件",
        "saved_text": "配置已保存，等待当前事务结束后应用。",
        "error_title": "配置未应用",
        **ALPHA_TEXTS,
    }


def rows(store: AppConfigStore, config: AppConfig) -> list[dict[str, Any]]:
    """The four registration rows V1.0.3's settings page shows (ensure_device_count): registered devices with the
    database they use, then blank drafts on free addresses, not enabled, without a database."""
    registered = len(config.devices)
    shown = []
    for index, device in enumerate(ensure_device_count(config)):
        path = resolved_path(store, device, index) if index < registered else None
        shown.append(
            {
                "name": device.name,
                "slave_id": device.slave_id,
                "enabled": device.enabled,
                "auto_stop_on_failure": device.auto_stop_on_failure,
                "database_path": "" if path is None else str(path),
                "database_name": None if path is None else path.name,
                "registered": index < registered,
                "reuse_existing": False,
            }
        )
    return shown


def devices_dir(store: AppConfigStore) -> Path:
    return (store.root / DEFAULT_DEVICE_DATABASE_DIR).resolve()


def resolved_path(store: AppConfigStore, device: DeviceConfig, index: int) -> Path:
    """Where DeviceHub.apply / load_for_startup put this device's database (relative paths: under store.root)."""
    path = Path(device.resolved_database_path(index))
    return (path if path.is_absolute() else store.root / path).resolve()


def inside_alpha(store: AppConfigStore, path: Path) -> bool:
    return path.resolve().is_relative_to(devices_dir(store))


def read_file(store: AppConfigStore) -> AppConfig | None:
    """The configuration as stored, None when there is none yet; ConfigUnavailable when it cannot be read."""
    if not store.path.exists():
        return None
    try:
        payload = json.loads(store.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("配置根节点必须是对象")
        return AppConfig.from_dict(payload)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError) as error:
        raise ConfigUnavailable(f"无法读取采集配置：{store.path}", str(error)) from error


def check_paths(store: AppConfigStore, config: AppConfig | None) -> None:
    """16_ 3.2 check 2: before the lock is taken, every database must be under the alpha's devices directory."""
    for index, device in enumerate(config.devices if config else []):
        path = resolved_path(store, device, index)
        if not inside_alpha(store, path):
            raise ConfigUnavailable(OUTSIDE_ALPHA.format(path=path, directory=devices_dir(store)))


DELIVERY_BAUDRATE = 57600
DELIVERY_PARITY = "N"
DELIVERY_POLL_CYCLE_SECONDS = 40.0
"""The bus the probes are delivered with (owner 2026-10-27: 57600, no parity, 40 s); V1.0.3 starts at 19200 / 60 s."""


def empty() -> AppConfig:
    """The configuration V1.0.3 starts with after "重新配置" (main.create_startup_hub) and on first use, with the
    delivered probes' baud rate, parity and poll cycle instead of V1.0.3's."""
    return AppConfig(
        bus=BusConfig(
            serial_port="",
            host="",
            baudrate=DELIVERY_BAUDRATE,
            parity=DELIVERY_PARITY,
            poll_cycle_seconds=DELIVERY_POLL_CYCLE_SECONDS,
        )
    )


def problem(store: AppConfigStore) -> ConfigUnavailable | None:
    """What the start would refuse before opening any database: the file cannot be read, or a database is outside
    the alpha's folder (16_ 3.2). Databases that fail V1.0.3's startup check are known only from a start."""
    try:
        check_paths(store, read_file(store))
    except ConfigUnavailable as error:
        return error
    return None


def view(store: AppConfigStore) -> dict[str, Any]:
    """The page's view; an unreadable file is shown as an empty form with its `problem` (D-220), not refused."""
    found = problem(store)
    try:
        config = read_file(store)
    except ConfigUnavailable:
        config = None
    current = config or empty()
    devices = []
    for index, device in enumerate(current.devices):
        path = resolved_path(store, device, index)
        devices.append(
            {
                "name": device.name,
                "slave_id": device.slave_id,
                "enabled": device.enabled,
                "auto_stop_on_failure": device.auto_stop_on_failure,
                "database_path": str(path),
                "database_name": path.name,
                "database_exists": path.is_file(),
                "inside_alpha": inside_alpha(store, path),
            }
        )
    return {
        "path": str(store.path),
        "exists": store.path.exists(),
        "configured": current.configured,
        "bus": current.bus.to_dict(),
        "poll_cycle_seconds": current.effective_poll_cycle_seconds(),
        "devices": devices,
        "devices_dir": str(devices_dir(store)),
        "rows": rows(store, current),
        "blank_bus": empty().bus.to_dict(),
        "blank_rows": rows(store, empty()),
        "problem": None if found is None else {"message": found.message, "detail": found.detail},
        "form": form(),
    }


def _form_rows(registered: int, items: list[Any]) -> list[tuple[DeviceConfig, bool]]:
    """MainWindow.devices_from_form / _device_row_config: a row counts when it was registered, is enabled, has a
    name or a database; a blank name becomes 光谱仪N (N = row number). Each with its `reuse_existing` choice."""
    chosen = []
    for row, item in enumerate(items):
        fields = dict(item)
        device = DeviceConfig.from_dict(fields)
        if row < registered or device.enabled or device.name.strip() or device.database_path.strip():
            device.name = device.name.strip() or f"光谱仪{row + 1}"
            chosen.append((device, fields.get("reuse_existing") is True))
    return chosen


def build(
    store: AppConfigStore, current: AppConfig, payload: Mapping[str, Any], saved: AppConfig | None = None
) -> AppConfig:
    """The AppConfig to hand to DeviceHub.apply, taken from the page's rows as V1.0.3's app_config_from_form() takes
    them from its form. DeviceHub.apply itself checks names, addresses, duplicates and the "默认数据库文件已存在"
    case with V1.0.3's messages; this only guards where the databases go (16_ 3.2 check 1).

    A row may keep a database of the running configuration (`current`) or of the alpha's configuration file
    (`saved`): after a failed background apply the file holds the new configuration while the old one runs, and the
    page shows the file (D-221), so a retry keeps the databases DeviceHub.apply already created."""
    kept = {
        str(resolved_path(store, device, index))
        for config in (current, saved)
        if config is not None
        for index, device in enumerate(config.devices)
    }
    try:
        bus = BusConfig.from_dict(dict(payload.get("bus") or {}))
        rows = _form_rows(len(current.devices), list(payload.get("devices") or []))
    except (ValueError, TypeError, OverflowError) as error:
        raise InvalidArgument("配置参数无效", str(error)) from error
    devices = [device for device, _reuse in rows]
    for device in devices:
        given = device.database_path.strip()
        if given and str(Path(given).resolve()) not in kept:
            raise InvalidArgument("设备库路径只能沿用配置中已有的库；新设备留空，由程序在数据目录中建立", given)
        device.database_path = str(Path(given).resolve()) if given else ""
    config = AppConfig(bus=bus, devices=devices, configured=True).normalised()  # as app_config_from_form()
    for index, (device, reuse) in enumerate(zip(config.devices, [reuse for _device, reuse in rows], strict=True)):
        if reuse and not device.database_path:
            same_name = resolved_path(store, device, index)
            if not (inside_alpha(store, same_name) and same_name.is_file()):
                raise InvalidArgument(NO_DATABASE_TO_REUSE.format(name=same_name.name))
            device.database_path = str(same_name)  # the explicit choice V1.0.3 asks for, limited to the alpha folder
    for index, device in enumerate(config.devices):
        path = resolved_path(store, device, index)
        if not inside_alpha(store, path):
            raise InvalidArgument(OUTSIDE_ALPHA.format(path=path, directory=devices_dir(store)))
    return config
