"""Synthetic alpha device databases for the support endpoints (D-226): the rows V1.0.3's code writes when it writes
a device, written here through ParDatabase's own methods (save_calibration, diagnostic, save_time_sync) with the
messages and detail keys of PollingCoordinator and CommunicationMaintenance (tests/acquisition/test_maintenance_flow.py
checks the same log on rows the real code wrote over the fake bus). Everything under tmp_path (R-4-7).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from par_app.database import ParDatabase
from par_app.models import AppConfig, BusConfig, DeviceConfig

OLD = {"transport": "rtu", "serial_port": "COM7", "slave_id": 1, "baudrate": 9600, "parity": "N"}
NEW = {**OLD, "slave_id": 7}
IDENTITY = {"device_name": "PAR-FAKE", "serial_number": 305419896, "device_type": 1}
CAL_OLD = {"sensor_id": 1, "x_min": 350.0, "y1": -0.0123}
CAL_NEW = {"x_min": 350.0, "y1": -0.015}
CAL_READBACK = {"sensor_id": 1, "x_min": 350.0, "y1": -0.014999999664723873}


def write_config(data_dir: Path, names: list[str], database_paths: dict[str, str] | None = None) -> Path:
    """The alpha's tier-1 configuration (V1.0.3 format) registering `names` with the default database paths."""
    devices = [
        DeviceConfig(name=name, slave_id=index + 1, enabled=True, database_path=(database_paths or {}).get(name, ""))
        for index, name in enumerate(names)
    ]
    config = AppConfig(bus=BusConfig(serial_port="COM7"), devices=devices, configured=True)
    path = data_dir / "config" / "app_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def device_database(data_dir: Path, name: str) -> ParDatabase:
    return ParDatabase(data_dir / "data" / "devices" / f"{name}.sqlite3")


def _at(database: ParDatabase, row_sql: str, when: str) -> None:
    """Give the last row of a table a fixed time (the methods stamp beijing_now())."""
    with database.connect() as con:
        con.execute(row_sql, (when,))


def calibration_write(database: ParDatabase, when: str) -> None:
    database.save_calibration(
        action="write",
        success=1,
        old=CAL_OLD,
        new=CAL_NEW,
        readback=CAL_READBACK,
        status=3,
        error=0,
        detail="写入并回读光谱仪校准",
    )
    _at(database, "UPDATE calibration_audit SET occurred_at=? WHERE id=(SELECT MAX(id) FROM calibration_audit)", when)


def calibration_read(database: ParDatabase, when: str) -> None:
    database.save_calibration(action="read", success=1, readback=CAL_OLD, status=1, error=0, detail="读取当前校准")
    _at(database, "UPDATE calibration_audit SET occurred_at=? WHERE id=(SELECT MAX(id) FROM calibration_audit)", when)


def diagnostic(database: ParDatabase, when: str, level: str, category: str, message: str, **details: object) -> None:
    database.diagnostic(level, category, message, **details)
    _at(database, "UPDATE diagnostics SET occurred_at=? WHERE id=(SELECT MAX(id) FROM diagnostics)", when)


def comm_write(database: ParDatabase, when: str, *, error: str | None = None, prepared: bool = True) -> None:
    """CommunicationMaintenance.execute('maintenance_write'): start, prepare (pending saved), finished or error."""
    category = "communication_maintenance"
    diagnostic(
        database,
        when,
        "INFO",
        category,
        "开始维护操作",
        device_name="North",
        action="maintenance_write",
        connection=OLD,
    )
    if prepared:
        diagnostic(
            database,
            when,
            "WARNING",
            category,
            "准备写入，结果必须使用新参数核对",
            device_name="North",
            old=OLD,
            new=NEW,
            identity=IDENTITY,
        )
    if error is None:
        diagnostic(
            database,
            when,
            "INFO",
            category,
            "维护操作完成",
            device_name="North",
            action="maintenance_write",
            result={"connection": OLD, "identity": IDENTITY},
        )
    else:
        diagnostic(database, when, "ERROR", category, error, device_name="North", action="maintenance_write")


def comm_verify(database: ParDatabase, when: str, *, error: str | None = None) -> None:
    category = "communication_maintenance"
    diagnostic(
        database,
        when,
        "INFO",
        category,
        "开始维护操作",
        device_name="North",
        action="maintenance_verify",
        connection=NEW,
    )
    if error is None:
        result = {
            "connection": NEW,
            "identity": IDENTITY,
            "parameters": {"slave_id": 7, "baudrate_index": 1, "parity_index": 0},
        }
        diagnostic(
            database,
            when,
            "INFO",
            category,
            "维护操作完成",
            device_name="North",
            action="maintenance_verify",
            result=result,
        )
    else:
        diagnostic(database, when, "ERROR", category, error, device_name="North", action="maintenance_verify")


def time_sync(database: ParDatabase, when: str, success: bool = True) -> None:
    database.save_time_sync(success, 1760837400000 if success else None, "设备对时完成" if success else "超时")
    _at(database, "UPDATE time_sync_events SET occurred_at=? WHERE id=(SELECT MAX(id) FROM time_sync_events)", when)


def acquisitions(database: ParDatabase, count: int) -> None:
    for index in range(count):
        database.save_acquisition(
            {
                "acquired_at": f"2026-10-19T08:{index // 60:02d}:{index % 60:02d}.000",
                "success": 1,
                "elapsed_ms": 5000.0,
                "software_metrics_json": json.dumps({"ppfd": 123.4}),
                "raw_points": [1000] * 701,
            }
        )


def fingerprint(folder: Path) -> dict[str, str]:
    """SHA-256 of every *.sqlite3 main file under `folder` (the -wal/-shm of a read-only reader are not data)."""
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*.sqlite3"))
    }


def close_wal(path: Path) -> None:
    """Checkpoint, so the main file holds every row before it is fingerprinted."""
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()
