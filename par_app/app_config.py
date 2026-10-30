"""应用级配置（总线 + 设备登记）的持久化与旧版本迁移。

多设备改造后，配置不再存放在单个 SQLite 库的 app_settings 表中，而是独立
保存在 <程序目录>/config/app_config.json：
    一条总线共享参数（BusConfig） + 最多 4 台设备登记（DeviceConfig）。

首次启动若发现旧版本遗留的 data/par_spectrometer.sqlite3，会读取其
app_settings['connection'] 作为待确认配置，保留原库历史数据。
用户提交配置之前不开始采集。
"""

from __future__ import annotations

import json
import math
import sqlite3
import shutil
from datetime import datetime
from copy import deepcopy
from pathlib import Path

from .models import AppConfig, BusConfig, DeviceConfig, DeviceStatus  # noqa: F401  (DeviceStatus 便于统一导入)
from .models import ConnectionConfig, MAX_DEVICES
from .runtime_paths import application_root


CONFIG_DIR_NAME = "config"
CONFIG_FILE_NAME = "app_config.json"
LEGACY_DATABASE_RELATIVE = Path("data") / "par_spectrometer.sqlite3"
# 旧版单设备迁移实际读取的 connection 字段（D-164 只校验这些；database_path 不用）。
_LEGACY_MIGRATED_FIELDS = (
    "transport",
    "serial_port",
    "host",
    "tcp_port",
    "slave_id",
    "baudrate",
    "parity",
    "timeout_seconds",
    "acquisition_interval_seconds",
)


class StartupConfigurationError(ValueError):
    pass


class AppConfigStore:
    """读写 <程序目录>/config/app_config.json。"""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else application_root()
        self.preserve_before_save = False
        # 最近一次旧库迁移被跳过的原因（None 表示未跳过）；本类不写旧库。设置页连接状态据此提示（D-164）。
        self.legacy_migration_note: str | None = None

    def load_for_startup(self) -> AppConfig:
        if not self.path.exists():
            return self._migrate_legacy() or AppConfig(bus=BusConfig(serial_port='', host=''))
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict) or not isinstance(payload.get('bus', {}), dict):
                raise ValueError('配置根节点和总线参数必须是对象')
            devices = payload.get('devices', [])
            if not isinstance(devices, list) or any(not isinstance(device, dict) for device in devices):
                raise ValueError('设备登记必须是对象列表')
            config = AppConfig.from_dict(payload)
        except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise StartupConfigurationError(f'无法读取配置文件：{self.path}\n原因：{exc}') from exc
        for index, device in enumerate(config.devices):
            path = Path(device.resolved_database_path(index))
            path = (path if path.is_absolute() else self.root / path).resolve()
            try:
                if not path.is_file():
                    raise FileNotFoundError('数据库文件不存在，可能已移动或所在磁盘不可用')
                connection = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=1)
                try:
                    if connection.execute('PRAGMA quick_check').fetchone() != ('ok',):
                        raise sqlite3.DatabaseError('数据库完整性检查未通过')
                finally:
                    connection.close()
            except (OSError, sqlite3.Error) as exc:
                raise StartupConfigurationError(
                    f'设备：{device.name}\n数据库：{path}\n原因：{exc}\n配置文件：{self.path}') from exc
            device.database_path = str(path)
        return config

    @property
    def path(self) -> Path:
        return self.root / CONFIG_DIR_NAME / CONFIG_FILE_NAME

    @property
    def legacy_database_path(self) -> Path:
        return self.root / LEGACY_DATABASE_RELATIVE

    def load(self) -> AppConfig:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                config = AppConfig.from_dict(payload)
                if self._repair_stale_database_paths(config):
                    # Persist only a deterministic local-path repair. Existing
                    # valid custom paths and device data are left untouched.
                    self.save(config)
                return config
            except (OSError, ValueError, TypeError):
                # 配置损坏时回退到默认值，不阻断启动。
                pass
        migrated = self._migrate_legacy()
        if migrated is not None:
            return migrated
        return AppConfig()

    def _repair_stale_database_paths(self, config: AppConfig) -> bool:
        """Relink databases left behind by moving the project directory.

        Older development configurations stored absolute paths. When such a
        path is no longer available, a same-named database in this project's
        standard device-data directory is an unambiguous local replacement.
        """
        changed = False
        device_dir = self.root / "data" / "devices"
        for device in config.devices:
            configured = Path(str(device.database_path or "").strip())
            if not configured or self._database_path_usable(configured):
                continue
            candidates = (device_dir / configured.name, self.root / "data" / configured.name)
            candidate = next((item for item in candidates if self._database_path_usable(item)), None)
            if candidate is not None:
                device.database_path = str(candidate)
                changed = True
        return changed

    @staticmethod
    def _database_path_usable(path: Path) -> bool:
        """Check that SQLite can open the database in the requested mode."""
        if not path.exists() or not path.is_file():
            return False
        try:
            connection = sqlite3.connect(str(path), timeout=1)
            try:
                connection.execute("PRAGMA journal_mode=WAL").fetchone()
            finally:
                connection.close()
            return True
        except (OSError, sqlite3.Error):
            return False

    def save(self, config: AppConfig) -> None:
        config.normalised()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        if self.preserve_before_save and self.path.exists():
            backup = self.path.with_name(f'app_config.before_recovery_{datetime.now():%Y%m%d_%H%M%S_%f}.json')
            shutil.copy2(self.path, backup)
        temporary.replace(self.path)
        self.preserve_before_save = False

    def _migrate_legacy(self) -> AppConfig | None:
        """旧版本单设备配置 → 总线 + 一台设备（指向原数据库，历史数据不丢）。"""
        self.legacy_migration_note = None
        legacy = self.legacy_database_path
        if not legacy.exists():
            return None
        payload = self._read_legacy_connection_json(legacy)
        if payload is not None and not isinstance(payload, dict):
            # 合法但非对象的 JSON（列表、字符串、数字等）视为无可迁移配置，不让启动崩溃。
            self.legacy_migration_note = f"旧库 connection 不是 JSON 对象（{type(payload).__name__}）"
            return None
        if not payload:
            return None
        try:
            old = self._typed_legacy_connection(payload)
        except ValueError as exc:
            # D-164 已裁决：对象但字段类型错误时同样跳过迁移，进入未配置状态，原因交设置页提示。
            self.legacy_migration_note = str(exc)
            return None
        bus = BusConfig(
            transport=old.transport,
            serial_port=old.serial_port,
            host=old.host,
            tcp_port=old.tcp_port,
            baudrate=old.baudrate,
            parity=old.parity,
            timeout_seconds=max(old.timeout_seconds, 10.0),
            poll_cycle_seconds=max(60.0, old.acquisition_interval_seconds),
        )
        device = DeviceConfig(
            name="光谱仪1",
            slave_id=old.slave_id,
            enabled=True,
            database_path=str(legacy),
        )
        return AppConfig(bus=bus, devices=[device]).normalised()

    @staticmethod
    def _typed_legacy_connection(payload: dict) -> ConnectionConfig:
        """按迁移用到的 ConnectionConfig 字段默认值类型校验并转换旧库 connection；不符时抛 ValueError（D-164）。

        database_path 不参与迁移（设备直接指向旧库），不校验，其类型错误不影响回填。
        """
        old = ConnectionConfig.from_dict(payload)
        defaults = ConnectionConfig().to_dict()
        for name in _LEGACY_MIGRATED_FIELDS:
            default = defaults[name]
            value = getattr(old, name)
            if isinstance(default, str):
                converted = value if isinstance(value, str) else None
            else:
                converted = AppConfigStore._legacy_number(value, type(default))
            if converted is None:
                kind = "文本" if isinstance(default, str) else "整数" if isinstance(default, int) else "数字"
                raise ValueError(f"旧库 connection 字段 {name} 的值 {value!r} 不是{kind}")
            setattr(old, name, converted)
        return old

    @staticmethod
    def _legacy_number(value: object, kind: type) -> int | float | None:
        """转换为 kind；非有限值、超出浮点范围、或整数字段收到非整数浮点（不截断，3.9 不变成 3）时返回 None。"""
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return None
        try:
            if not math.isfinite(float(value)):
                return None
            if kind is int and isinstance(value, float) and not value.is_integer():
                return None
            return kind(value)
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _read_legacy_connection_json(database_path: Path) -> object:
        try:
            con = sqlite3.connect(str(database_path), timeout=5)
            try:
                row = con.execute("SELECT value_json FROM app_settings WHERE key='connection'").fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            return None
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None


def ensure_device_count(config: AppConfig, count: int = MAX_DEVICES) -> list[DeviceConfig]:
    """生成独立的登记表草稿，不修改运行配置。"""
    config = deepcopy(config)
    used_ids = {device.slave_id for device in config.devices}
    while len(config.devices) < count:
        candidate = next((value for value in range(1, MAX_DEVICES + 1) if value not in used_ids), len(config.devices) + 1)
        used_ids.add(candidate)
        config.devices.append(DeviceConfig(name="", slave_id=candidate, enabled=False))
    return config.devices
