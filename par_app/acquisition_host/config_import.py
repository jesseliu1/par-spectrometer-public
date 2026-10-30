"""Import a copy of a V1.0.3 configuration as the starting point of the alpha's own (16_ 3.3; D-214).

Read only, writes nothing anywhere (the page saves the result through PUT /acquisition-config):

1. the source is V1.0.3's program directory or its config/app_config.json; the file is read with open(..., "rb"),
   json.loads and AppConfig.from_dict, the structure check of load_for_startup(). Never AppConfigStore(<V1 dir>):
   its load() rewrites V1.0.3's configuration and _migrate_legacy() reads V1.0.3's old database;
2. size, modification time and SHA-256 of the file are compared before and after the read: a change is busy;
3. the bus and the registration (names, addresses, enabled, fail-stop) are kept, every database path is cleared,
   so the alpha builds its own databases under its data directory;
4. a device whose V1.0.3 database holds an unfinished communication maintenance session (the app_settings row
   `communication_maintenance` that CommunicationMaintenance.unfinished reads) cannot be imported: a new database
   would skip D-131's verification. The database is read as a snapshot import reads it (at rest: mode=ro and
   immutable=1; with -wal / -journal beside it: a byte copy in the alpha's data/staging/ is read), so nothing ever
   appears beside the source.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..app_config import ensure_device_count
from ..application.errors import Busy, InvalidArgument
from ..application.paths import AlphaPaths
from ..application.readonly import connect_read_only
from ..application.snapshots import ReadMode, fingerprint, read_mode
from ..application.snapshots import _journals as journals
from ..application.snapshots import _stage as stage
from ..application.snapshots import _staging_folder as staging_folder
from ..models import AppConfig

CONFIG_RELATIVE = Path("config") / "app_config.json"
NOT_FOUND = "找不到 V1.0.3 的配置文件"
UNREADABLE = "V1.0.3 的配置文件无法读取"
CHANGED = "V1.0.3 的配置文件在读取过程中发生变化（V1.0.3 可能正在保存配置），请稍后重试"
PENDING_MAINTENANCE = "该设备在 V1.0.3 中有通信参数写入待核对，请先在 V1.0.3 完成核对，再导入"
MAINTENANCE_UNREADABLE = "无法读取该设备在 V1.0.3 中的维护记录，未导入：{error}"
NOTE = (
    "只读取 V1.0.3 的配置文件和设备库，不改动它们。导入的是总线参数和设备登记（名称、从站地址、启用、失败停止）；"
    "数据库一律改用本软件数据目录下的新库，V1.0.3 的历史记录不带过来（可用历史库快照查看）。"
    "放入表单后请核对，再点“保存并应用全部配置”才生效。"
)


def _config_file(source: str) -> Path:
    text = source.strip()
    if not text:
        raise InvalidArgument(NOT_FOUND, "请填写 V1.0.3 的程序目录或其中的 config/app_config.json")
    path = Path(text).expanduser()
    candidate = path / CONFIG_RELATIVE if path.is_dir() else path
    if not candidate.is_file():
        raise InvalidArgument(NOT_FOUND, str(candidate))
    return candidate.resolve()


def _read_config(path: Path) -> AppConfig:
    try:
        before = fingerprint(path)
        with path.open("rb") as handle:
            raw = handle.read()
        after = fingerprint(path)
    except OSError as error:
        raise InvalidArgument(UNREADABLE, f"{path}：{error}") from error
    if before != after:
        raise Busy(CHANGED, str(path))
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("配置根节点必须是对象")
        return AppConfig.from_dict(payload)
    except (UnicodeDecodeError, ValueError, TypeError, AttributeError, OverflowError) as error:
        raise InvalidArgument(UNREADABLE, f"{path}：{error}") from error


def _unfinished(connection: sqlite3.Connection) -> bool:
    tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "app_settings" not in tables:
        return False
    row = connection.execute("SELECT value_json FROM app_settings WHERE key='communication_maintenance'").fetchone()
    if row is None:
        return False
    saved = json.loads(row[0])
    return bool(saved.get("pending") or saved.get("verified"))  # CommunicationMaintenance.unfinished


def _maintenance_problem(database: Path, paths: AlphaPaths) -> str | None:
    """PENDING_MAINTENANCE when the V1.0.3 database holds an unfinished session; None when it does not or does not
    exist (V1.0.3 never ran that device: nothing to verify)."""
    if not database.is_file():
        return None
    try:
        if read_mode(database) is ReadMode.AT_REST:
            with connect_read_only(database, immutable=True) as connection:
                unfinished = _unfinished(connection)
        else:
            with staging_folder(paths) as folder:
                staged = stage([database, *journals(database)], folder)
                with connect_read_only(staged) as connection:
                    unfinished = _unfinished(connection)
    except (OSError, sqlite3.Error, ValueError, TypeError, AttributeError) as error:
        return MAINTENANCE_UNREADABLE.format(error=f"{type(error).__name__}: {error}")
    return PENDING_MAINTENANCE if unfinished else None


def preview(paths: AlphaPaths, source: str) -> dict[str, Any]:
    """The draft the settings page puts into its form; writes no file (16_ 3.3)."""
    path = _config_file(source)
    config = _read_config(path)
    root = path.parent.parent  # V1.0.3's AppConfigStore root: relative database paths are under it
    devices = []
    importable = []
    for index, device in enumerate(config.devices):
        database = Path(device.resolved_database_path(index))
        database = (database if database.is_absolute() else root / database).resolve()
        problem = _maintenance_problem(database, paths)
        devices.append(
            {
                "name": device.name,
                "slave_id": device.slave_id,
                "enabled": device.enabled,
                "auto_stop_on_failure": device.auto_stop_on_failure,
                "source_database_path": str(database),
                "importable": problem is None,
                "problem": problem,
            }
        )
        if problem is None:
            device.database_path = ""
            importable.append(device)
    draft = AppConfig(bus=config.bus, devices=importable, configured=config.configured)
    return {
        "source_path": str(path),
        "bus": draft.bus.to_dict(),
        "devices": devices,
        "rows": _rows(draft),
        "note": NOTE,
    }


def _rows(draft: AppConfig) -> list[dict[str, Any]]:
    """Four form rows: the imported devices (no database yet, the alpha names it when saving), then blank drafts."""
    shown = []
    for index, device in enumerate(ensure_device_count(draft)):
        shown.append(
            {
                "name": device.name,
                "slave_id": device.slave_id,
                "enabled": device.enabled,
                "auto_stop_on_failure": device.auto_stop_on_failure,
                "database_path": "",
                "database_name": None,
                "registered": index < len(draft.devices),
            }
        )
    return shown
