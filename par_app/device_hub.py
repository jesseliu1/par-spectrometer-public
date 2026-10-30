"""多设备 UI 适配层。

界面绝大多数代码仍然围绕"当前设备"访问 ``self.database`` 与 ``self.service``。
本模块把 :class:`PollingCoordinator`（一条总线 + 最多 4 台设备）适配成这组旧接口：

* :class:`DeviceHub`           —— 持有配置、调度器与"当前选中设备"；
* :class:`ActiveDeviceService` —— 把调度器的多设备信号过滤/转换成单设备信号。

这样 UI 只需在切换设备时重新绑定 ``database``，其余逻辑无需改动。
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from copy import deepcopy
from pathlib import Path

from par_app.qt_compat import QObject, pyqtSignal

from .app_config import AppConfigStore
from .coordinator import PollingCoordinator, device_keys
from .database import ParDatabase
from .models import AppConfig, ConnectionConfig


class PlaceholderDatabaseError(OSError):
    """未登记设备时无法在系统临时目录建占位空库（D-163）；与程序目录、配置和登记库无关。"""


def _database_path_key(path: Path) -> str:
    """按 Windows/macOS 默认文件系统语义（不区分大小写）比较数据库路径的键。"""
    return os.path.normcase(str(path)).casefold()


def _shares_database(path: Path, registered: dict[str, Path]) -> bool:
    """路径与已登记的库只差大小写，或与已存在的库是同一个文件（硬链接、短文件名等别名）。"""
    if _database_path_key(path) in registered:
        return True
    return path.exists() and any(other.exists() and os.path.samefile(path, other) for other in registered.values())


class ActiveDeviceService(QObject):
    """面向"当前设备"的服务门面，信号签名与旧版 AcquisitionService 一致。"""

    status_changed = pyqtSignal(str, str)              # level, message
    communication_alert = pyqtSignal(int, str)         # failures, detail
    acquisition_saved = pyqtSignal(int, int)           # 占位, record_id
    task_finished = pyqtSignal(str, bool, object)      # kind, ok, payload

    def __init__(self, hub: "DeviceHub"):
        super().__init__()
        self._hub = hub
        coordinator = hub.coordinator
        coordinator.bus_state_changed.connect(self.status_changed.emit)
        coordinator.device_alert.connect(self._on_alert)
        coordinator.acquisition_saved.connect(self._on_saved)
        coordinator.task_finished.connect(self._on_task)

    # ------------------------------------------------------------ 旧接口

    @property
    def config(self) -> ConnectionConfig:
        return self._hub.active_connection()

    def queue_task(self, kind: str, payload: object = None) -> None:
        self._hub.coordinator.queue_task(self._hub.active_key, kind, payload)

    def stop(self) -> None:
        self._hub.coordinator.stop()

    # ------------------------------------------------------------ 信号转发

    def _on_alert(self, key: str, name: str, detail: str) -> None:
        if key != self._hub.active_key:
            return
        state = self._hub.coordinator.state(key)
        failures = state.failures if state is not None else 0
        self.communication_alert.emit(failures, detail)

    def _on_saved(self, key: str, record_id: int) -> None:
        if key == self._hub.active_key:
            self.acquisition_saved.emit(0, record_id)

    def _on_task(self, key: str, kind: str, ok: bool, payload: object) -> None:
        if key == self._hub.active_key:
            self.task_finished.emit(kind, ok, payload)


class DeviceHub(QObject):
    """配置 + 调度器 + 当前设备选择。"""

    devices_changed = pyqtSignal()                     # 设备登记发生变化
    active_changed = pyqtSignal(str)                   # 当前设备标识

    def __init__(self, store: AppConfigStore, parent: QObject | None = None, *, initial_config: AppConfig | None = None):
        super().__init__(parent)
        self.store = store
        self.config: AppConfig = store.load() if initial_config is None else initial_config
        self._fallback_database: ParDatabase | None = None
        self._placeholder_directory: tempfile.TemporaryDirectory[str] | None = None
        self.coordinator = PollingCoordinator(self.config, parent)
        self._databases = {state.key: state.database for state in self.coordinator.states()}
        self.service = ActiveDeviceService(self)
        self.active_key: str = self._first_key()
        self.coordinator.bus_config_changed.connect(self._persist_bus)
        self.coordinator.config_applied.connect(self._on_config_applied)

    # ------------------------------------------------------------ 设备列表

    def keys(self) -> list[str]:
        return device_keys(self.config.devices)

    def active_index(self) -> int:
        keys = self.keys()
        return keys.index(self.active_key) if self.active_key in keys else 0

    def device_at(self, key: str):
        keys = self.keys()
        if key in keys:
            return self.config.devices[keys.index(key)]
        return None

    def _first_key(self) -> str:
        keys = self.keys()
        for key, device in zip(keys, self.config.devices, strict=True):
            if device.enabled:
                return key
        return keys[0] if keys else ""

    # ------------------------------------------------------------ 当前设备

    def active_connection(self) -> ConnectionConfig:
        index = self.active_index()
        devices = self.config.devices
        slave_id = devices[index].slave_id if index < len(devices) else 1
        return self.config.bus.to_connection(slave_id)

    def idle_status(self) -> dict[str, str]:
        """当前设备尚无采集状态时，设置页连接状态显示的内容。

        旧库连接配置因内容无法读取而跳过回填、且用户尚未保存新配置时，说明原因（D-164）。
        """
        note = self.store.legacy_migration_note
        if note and not self.config.configured:
            return {"level": "warning", "message": f"旧版连接配置无法读取，已跳过回填：{note}"}
        return {"level": "idle", "message": "等待本次采集"}

    def database_for(self, key: str) -> ParDatabase | None:
        return self._databases.get(key)

    @property
    def database(self) -> ParDatabase:
        return self.database_for(self.active_key) or self._unregistered_database()

    def has_registered_database(self) -> bool:
        """当前设备有登记库；为假时界面用的是未登记回退库（旧版默认库或临时空库）。"""
        return self.database_for(self.active_key) is not None

    def uses_placeholder_database(self) -> bool:
        """界面当前用的是临时空库占位（D-163 (1)）。"""
        if self.has_registered_database():
            return False
        self._unregistered_database()
        return self._placeholder_directory is not None

    def _unregistered_database(self) -> ParDatabase:
        """未登记设备时界面仍需一个库：旧版默认库存在才打开；缺失时用临时空库，不在程序目录新建（CONF-006）。

        临时空库是迁移期占位（D-163 已裁决 2026-10-17），UI 重构时改为不建库、显示空状态。
        已登记的该库损坏时仍会被初始化改写（DEF-26，未修）。
        """
        if self._fallback_database is None:
            legacy = self.store.legacy_database_path
            if legacy.is_file():
                self._fallback_database = ParDatabase(legacy)
            else:
                self._fallback_database = self._open_placeholder_database()
        return self._fallback_database

    def _open_placeholder_database(self) -> ParDatabase:
        """在系统临时目录建占位空库；失败时报告临时目录本身，不让提示指向程序目录（R-1-5）。

        临时目录只探测一次：找不到任何可用目录时 gettempdir() 本身就会抛错，提示里不能再调用它。
        """
        location = "未找到可用的系统临时目录"
        try:
            location = tempfile.gettempdir()
            directory = tempfile.TemporaryDirectory(
                prefix="par_unregistered_", dir=location, ignore_cleanup_errors=True
            )
            database = ParDatabase(Path(directory.name) / "unregistered.sqlite3")
        except (OSError, sqlite3.Error) as exc:
            raise PlaceholderDatabaseError(
                f"系统临时目录不可用：{location}\n"
                f"未登记设备时，界面需要在该目录建一个临时空库占位。\n原因：{exc}"
            ) from exc
        self._placeholder_directory = directory
        return database

    def set_active(self, key: str) -> None:
        if key and key != self.active_key and key in self.keys():
            self.active_key = key
            self.active_changed.emit(self.active_key)

    # ------------------------------------------------------------ 配置应用

    def apply(self, app_config: AppConfig) -> None:
        """保存独立配置快照，交由后台线程在事务结束后切换。"""
        config = deepcopy(app_config)
        if not 1 <= len(config.devices) <= 4 or not config.enabled_devices():
            raise ValueError("请至少登记并启用一台设备，最多四台。")
        if config.bus.transport == "rtu" and not config.bus.serial_port.strip():
            raise ValueError("请选择串口。")
        addresses: set[int] = set()
        paths: dict[str, Path] = {}
        names: set[str] = set()
        for index, device in enumerate(config.devices):
            device.name = device.name.strip()
            if not device.name or device.name in names:
                raise ValueError("设备名称不能为空或重复。")
            names.add(device.name)
            if not 1 <= device.slave_id <= 247 or device.slave_id in addresses:
                raise ValueError("设备 ID 必须在 1~247 之间，且不能重复。")
            addresses.add(device.slave_id)
            path = Path(device.resolved_database_path(index))
            path = (path if path.is_absolute() else self.store.root / path).resolve()
            if _shares_database(path, paths):
                raise ValueError("不同设备不能共用同一个数据库。")
            if not device.database_path.strip() and path.exists():
                raise ValueError(f"默认数据库文件已存在：{path.name}。请明确选择该文件以继续使用，或为新设备选择其它文件。")
            paths[_database_path_key(path)] = path
            device.database_path = str(path)
        for device in config.devices:
            ParDatabase(device.database_path)
        config.configured = True
        self.store.save(config)
        self.coordinator.apply_config(config)

    def _on_config_applied(self, app_config: AppConfig) -> None:
        self.config = app_config
        self._databases = {state.key: state.database for state in self.coordinator.states()}
        if self.active_key not in self.keys():
            self.active_key = self._first_key()
        self.devices_changed.emit()
        self.active_changed.emit(self.active_key)

    def _persist_bus(self, bus) -> None:
        self.config.bus = bus
        self.store.save(self.config)
