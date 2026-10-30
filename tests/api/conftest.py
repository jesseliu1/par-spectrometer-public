"""Fixtures of the local-service contract tests (api-contract-v0 section 5).

Every database is synthetic and lives under tmp_path (R-4-7). V1.0.x-style source databases are written by
ParDatabase itself, i.e. exactly the files a V1.0.3 installation produces; the alpha data directory is a separate
tmp_path folder, so a test never writes a real %LOCALAPPDATA% (15_ 5.6).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from par_app.acquisition_host import config_io
from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.app_config import AppConfigStore
from par_app.application.paths import AlphaPaths
from par_app.application.tier import TAKEOVER_TIER
from par_app.database import ParDatabase
from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_app.math_ops import software_metrics
from par_app.models import AppConfig, DeviceConfig

TOKEN = "test-token-not-secret"
HOST = "testserver"
AUTH = {"X-PAR-Token": TOKEN}
NOW = datetime(2026, 10, 18, 9, 30, 0, tzinfo=BEIJING_TZ)
DAY = {"start": "2026-10-01T00:00:00.000", "end": "2026-10-01T23:59:59.999"}
RAW_FLAT = [1000] * 701
SINGLE_CAPTURE = json.dumps({"strategy": "single_capture", "acquisition_status": "completed"})


def record(acquired_at: str = "2026-10-01T12:00:00.000", **overrides: object) -> dict[str, Any]:
    """A successful V1.0.3 single-capture record with a flat spectrum; keyword overrides replace fields."""
    metrics = software_metrics(RAW_FLAT, 3)
    base: dict[str, Any] = {
        "acquired_at": acquired_at,
        "mcu_time_ms": 123456,
        "success": 1,
        "initialized": 1,
        "need_power_cycle": 0,
        "raw_data_valid": 1,
        "calculate_data_valid": 1,
        "stop_status": 0,
        "spectral_coefficient": 3,
        "exposure_status": 0,
        "exposure_time_us": 20000,
        "software_metrics_json": json.dumps(metrics),
        "mcu_params_json": json.dumps({"lux": 1234.5, "cct": 5321.4, "ra": 91.25, "duv": 0.0031, "x": 0.33}),
        "elapsed_ms": 5464.66,
        "raw_points": RAW_FLAT,
        "quality_json": SINGLE_CAPTURE,
        "dli_eligible": 1,
    }
    base.update(overrides)
    return base


def failed_record(acquired_at: str = "2026-10-01T12:01:00.000") -> dict[str, Any]:
    return record(
        acquired_at,
        success=0,
        software_metrics_json=None,
        mcu_params_json=None,
        raw_points=None,
        error_stage="read_spectrum",
        error_detail="读取超时",
        elapsed_ms=10012.5,
        dli_eligible=0,
    )


def v1_database(path: Path, records: list[Mapping[str, Any]]) -> Path:
    """A V1.0.x history database written by ParDatabase (WAL header; -wal/-shm removed on the last close)."""
    database = ParDatabase(path)
    for item in records:
        database.save_acquisition(dict(item))
    return path


def legacy_database(path: Path) -> Path:
    """A V1.0.0-era database: no quality_json / dli_eligible columns, rollback journal, one success and one failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE acquisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, acquired_at TEXT NOT NULL, mcu_time_ms INTEGER,
            success INTEGER NOT NULL, initialized INTEGER, need_power_cycle INTEGER, raw_data_valid INTEGER,
            calculate_data_valid INTEGER, stop_status INTEGER, spectral_coefficient INTEGER, exposure_status INTEGER,
            exposure_time_us INTEGER, software_metrics_json TEXT, mcu_params_json TEXT, error_stage TEXT,
            error_detail TEXT, elapsed_ms REAL NOT NULL
        );
        CREATE TABLE spectra (acquisition_id INTEGER PRIMARY KEY, raw_points_json TEXT NOT NULL);
    """)
    metrics = json.dumps(software_metrics(RAW_FLAT, 3))
    con.execute(
        "INSERT INTO acquisitions(acquired_at,success,spectral_coefficient,exposure_status,software_metrics_json,"
        "mcu_params_json,elapsed_ms) VALUES(?,?,?,?,?,?,?)",
        ("2026-10-01T08:00:00+00:00", 1, 3, 2, metrics, json.dumps({"cct": 4100}), 9000.0),
    )
    con.execute("INSERT INTO spectra VALUES(1, ?)", (json.dumps(RAW_FLAT),))
    con.execute(
        "INSERT INTO acquisitions(acquired_at,success,elapsed_ms,error_stage) VALUES(?,?,?,?)",
        ("2026-10-01T08:05:00+00:00", 0, 10000.0, "freeze"),
    )
    con.commit()
    con.close()
    return path


@pytest.fixture
def context(tmp_path: Path) -> ServiceContext:
    return ServiceContext(AlphaPaths(tmp_path / "alpha"), FakeClock(NOW))


@pytest.fixture
def client(context: ServiceContext) -> Iterator[TestClient]:
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}", headers=AUTH) as test_client:
        yield test_client


@pytest.fixture
def anonymous(context: ServiceContext) -> Iterator[TestClient]:
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}") as test_client:
        yield test_client


class ConfigOnlyBackend:
    """The takeover backend as far as the pages need it: the configuration view (config_io.view, which opens no
    database). Nothing is taken over; starting would fail, which these tests never do."""

    def __init__(self, data_dir: Path) -> None:
        self.store = AppConfigStore(data_dir)

    def read_config(self) -> dict[str, Any]:
        return config_io.view(self.store)


def _registered(context: ServiceContext) -> dict[int, DeviceConfig]:
    found: dict[int, DeviceConfig] = getattr(context, "_test_devices", {})
    context._test_devices = found  # type: ignore[attr-defined]
    return found


def register_device(
    client: TestClient, source: Path, name: str | None = None, position: int = 1, *, acquiring: bool = True
) -> dict[str, Any]:
    """Put a copy of `source` into the alpha's devices folder and register it at `position` of the alpha's own
    configuration, in tier 1 (issue #82: the pages read the alpha's own device databases). A second registration
    at the same position puts a new database there, as a changed configuration would. Positions before `position`
    that hold nothing get a disabled placeholder device with an empty database, since V1.0.3's configuration has
    no gaps. `acquiring`: the takeover reads "running" (what V1.0.3 does while its pages show), else "released"
    (nothing acquires: the pages say 采集已暂停). Returns the /devices item of that position."""
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    acquisition = context.acquisition
    acquisition.tiers.write(TAKEOVER_TIER)
    if acquisition.backend is None:
        acquisition.attach(ConfigOnlyBackend(context.paths.data_dir))  # type: ignore[arg-type]
    acquisition.cache.set_takeover("running" if acquiring else "released", lock_held=acquiring)
    devices = _registered(context)
    folder = context.paths.devices_dir
    folder.mkdir(parents=True, exist_ok=True)
    label = name or source.stem
    target = folder / source.name  # the same file name as the source, as a parity check compares it
    if target.exists():
        target = folder / f"p{position}-{len(list(folder.glob('*')))}-{source.name}"
    shutil.copy2(source, target)
    for suffix in ("-wal", "-journal"):
        companion = source.with_name(source.name + suffix)
        if companion.exists():
            shutil.copy2(companion, target.with_name(target.name + suffix))
    devices[position] = DeviceConfig(name=label, slave_id=position, database_path=str(target))
    for missing in range(1, position):
        if missing not in devices:
            placeholder = folder / f"placeholder-{missing}.sqlite3"
            ParDatabase(placeholder)
            devices[missing] = DeviceConfig(
                name=f"占位{missing}", slave_id=missing, enabled=False, database_path=str(placeholder)
            )
    ordered = [devices[index] for index in sorted(devices)]
    AppConfigStore(context.paths.data_dir).save(AppConfig(devices=ordered, configured=True))
    response = client.get("/api/v0/devices")
    assert response.status_code == 200, response.text
    item: dict[str, Any] = response.json()["items"][position - 1]
    assert item["configured"] and item["name"] == label, item
    return {**item, "id": item["snapshot_id"], "path": item["database_path"], "source_path": item["database_path"]}


def assert_read_only(database: Path, before: bytes) -> None:
    """Reading left `database` as it was: the file unchanged, and of SQLite's companions only an empty -wal and the
    -shm index a read-only connection to a WAL database creates in the alpha's own devices folder (16_ 3.2)."""
    assert database.read_bytes() == before
    wal = database.with_name(database.name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    allowed = {database.name, wal.name, database.name + "-shm"}
    assert {path.name for path in database.parent.iterdir() if path.name.startswith(database.name)} <= allowed


def import_snapshot(client: TestClient, source: Path, **body: object) -> dict[str, Any]:
    """The deprecated snapshot import (API-20, kept until #83); no page shows what it imports."""
    response = client.post("/api/v0/snapshots", json={"source_path": str(source), **body})
    assert response.status_code == 201, response.text
    snapshot: dict[str, Any] = response.json()["snapshot"]
    return snapshot


def error_of(response: httpx.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message", "retryable", "detail"}, body
    return dict(body["error"])
