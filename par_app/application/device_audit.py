"""Read-only access to the alpha's own device databases for the support features (D-226): the maintenance log and the
diagnostics bundle.

Which databases: the devices of the alpha's tier-1 configuration (alpha_info.TIER1_CONFIG_FILE_NAME in
<data dir>/config, V1.0.3's format), in registration order p1..p4, with V1.0.3's path rule (relative paths under
the data directory, an empty path is data/devices/<name>.sqlite3). The file is read as JSON here, as
par_app.acquisition_host.config_io.view reads it: AppConfigStore.load() would repair paths and touch databases.
Nothing is written.

A database outside <data dir>/data/devices is never opened (16_ 3.2, PR #54 review B1: a mode=ro connection
may create -wal/-shm beside another program's WAL database); it is reported instead. Every connection is
`file:<path>?mode=ro` (readonly.connect_read_only), the same as the live overview of tier 1: SQLite refuses any
write to the database, and on these WAL databases it may leave empty -wal/-shm files beside them inside the alpha's
own folder, as the coordinator does.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar

from ..alpha_info import TIER1_CONFIG_FILE_NAME
from ..models import MAX_DEVICES, AppConfig
from .acquisition import DEVICE_POSITIONS
from .errors import ConfigUnavailable, DatabaseUnavailable, DeviceNotFound
from .paths import AlphaPaths
from .readonly import Row, connect_read_only

UNREADABLE_CONFIG = "无法读取采集配置：{path}"
OUTSIDE_TEXT = "设备库不在本软件数据目录 data/devices 之下，未打开"
MISSING_TEXT = "设备库尚未建立（未采集过）"
UNKNOWN_DEVICE = "采集配置中没有位置 {key} 的设备"

State = Literal["ok", "missing", "outside", "unavailable"]
T = TypeVar("T")


@dataclass(frozen=True)
class DeviceDatabase:
    key: str
    position: int
    name: str
    path: Path
    inside: bool

    @property
    def readable(self) -> bool:
        return self.inside and self.path.is_file()

    def state(self) -> tuple[State, str | None]:
        """What the page says about a database that is not read: outside the alpha folder or not created yet."""
        if not self.inside:
            return "outside", OUTSIDE_TEXT
        if not self.path.is_file():
            return "missing", MISSING_TEXT
        return "ok", None


def config_path(paths: AlphaPaths) -> Path:
    return paths.config_dir / TIER1_CONFIG_FILE_NAME


def read_config(paths: AlphaPaths) -> AppConfig | None:
    """The configuration as stored; None when there is none yet; ConfigUnavailable when it cannot be read."""
    path = config_path(paths)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("配置根节点必须是对象")
        return AppConfig.from_dict(payload)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError) as error:
        raise ConfigUnavailable(UNREADABLE_CONFIG.format(path=path), str(error)) from error


def device_databases(paths: AlphaPaths) -> list[DeviceDatabase]:
    """The registered devices of the alpha configuration and their databases (V1.0.3's path rule)."""
    config = read_config(paths)
    found = []
    for index, device in enumerate((config.devices if config else [])[:MAX_DEVICES]):
        path = Path(device.resolved_database_path(index))
        path = (path if path.is_absolute() else paths.data_dir / path).resolve()
        found.append(
            DeviceDatabase(
                key=DEVICE_POSITIONS[index],
                position=index + 1,
                name=device.name,
                path=path,
                inside=paths.holds_device_database(path),
            )
        )
    return found


def device_database(paths: AlphaPaths, key: str) -> DeviceDatabase:
    for device in device_databases(paths):
        if device.key == key:
            return device
    raise DeviceNotFound(UNKNOWN_DEVICE.format(key=key), key)


def tables(con: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def rows(con: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[Row]:
    return [dict(row) for row in con.execute(sql, parameters)]


def read(device: DeviceDatabase, reader: Callable[[sqlite3.Connection], T]) -> T:
    """Run `reader` on a read-only connection; refuses a database outside the alpha folder before opening it."""
    if not device.inside:
        raise DatabaseUnavailable(str(device.path), OUTSIDE_TEXT)
    if not device.path.is_file():
        raise DatabaseUnavailable(str(device.path), MISSING_TEXT)
    with connect_read_only(device.path) as con:
        return reader(con)
