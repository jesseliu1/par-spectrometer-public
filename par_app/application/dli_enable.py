"""The two DLI settings the alpha writes into its own device databases, as V1.0.3 writes them.

The enable time (D-228 option A; owner's written approval of 2026-10-27):

V1.0.3 stores "now" as app_settings.dli_enabled_at the first time its DLI page shows a registered device
(ParDatabase.load_dli_enabled_at, through ui_unconfigured.dli_enabled_at) and from then on counts only the records
after it. The alpha does the same on its own device databases, and only that: one app_settings row with V1.0.3's
INSERT, never a schema change. ParDatabase is not used because its constructor writes (CREATE TABLE, ALTER TABLE,
journal_mode=WAL). The file must already exist (mode=rw never creates it) and hold V1.0.3's app_settings table;
otherwise nothing is written and the caller reads "now" as before. A value already stored is never replaced.

The location (issue #116;负责人的 written approval of 2026-10-27): "保存经纬度并重置周期" stores the latitude and
longitude with ParDatabase.save_dli_location's own statement (an upsert of app_settings.dli_location), nothing else.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

from .errors import DatabaseUnavailable
from .readonly import BUSY_TIMEOUT_SECONDS, MISSING_FILE, file_uri

DLI_ENABLED_AT_KEY = "dli_enabled_at"
NO_SETTINGS_TABLE = "设备库中没有设置表（app_settings），未保存位置"


class SettingsTableMissing(DatabaseUnavailable):
    """The database has no app_settings table: the alpha does not create it, so trying again cannot help."""

    retryable = False


def read_write_uri(path: Path) -> str:
    """file: URI with mode=rw: SQLite may write the file but refuses to create it."""
    return f"{file_uri(path.resolve())}?mode=rw"


def store_enabled_at(path: Path, now: str) -> bool:
    """Store `now` (Beijing YYYY-MM-DDTHH:MM:SS.mmm, as beijing_now) unless an enable time is already stored.

    True when this call wrote it. The check and the INSERT run in one IMMEDIATE transaction, so a value written
    meanwhile by another connection (the coordinator writes the same file) is kept, as V1.0.3's own check keeps it.
    """
    if not path.is_file():
        raise DatabaseUnavailable(str(path), MISSING_FILE)
    try:
        con = sqlite3.connect(read_write_uri(path), uri=True, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    try:
        con.execute("BEGIN IMMEDIATE")
        tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "app_settings" not in tables:
            con.execute("ROLLBACK")
            return False
        present = con.execute("SELECT 1 FROM app_settings WHERE key=?", (DLI_ENABLED_AT_KEY,)).fetchone()
        if present is not None:
            con.execute("ROLLBACK")
            return False
        con.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',?,?)", (json.dumps(now), now)
        )
        con.execute("COMMIT")
        return True
    except sqlite3.Error as error:
        if con.in_transaction:
            with contextlib.suppress(sqlite3.Error):  # the original error is the one to report
                con.execute("ROLLBACK")
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    finally:
        con.close()


def store_location(path: Path, latitude: float, longitude: float, now: str) -> None:
    """ParDatabase.save_dli_location on an existing database: the same JSON value and the same upsert, with `now`
    (beijing_now's form) as updated_at. A database without app_settings is refused: the alpha never creates tables."""
    if not path.is_file():
        raise DatabaseUnavailable(str(path), MISSING_FILE)
    value = json.dumps({"latitude": latitude, "longitude": longitude})
    try:
        con = sqlite3.connect(read_write_uri(path), uri=True, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    try:
        con.execute("BEGIN IMMEDIATE")
        tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "app_settings" not in tables:
            con.execute("ROLLBACK")
            raise SettingsTableMissing(str(path), NO_SETTINGS_TABLE)
        con.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_location',?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (value, now),
        )
        con.execute("COMMIT")
    except sqlite3.Error as error:
        if con.in_transaction:
            with contextlib.suppress(sqlite3.Error):  # the original error is the one to report
                con.execute("ROLLBACK")
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    finally:
        con.close()
