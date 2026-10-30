"""保存经纬度并重置周期 (issue #116;负责人的 written approval of 2026-10-27).

Only app_settings.dli_location is written, with ParDatabase.save_dli_location's own statement; the period is computed
again from the new location; the enable time, the records and the schema stay as they were; tier 0 and a database
outside the alpha's devices folder are refused.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.app_config import AppConfigStore
from par_app.application.tier import FACTORY_TIER
from par_app.database import ParDatabase
from par_app.models import AppConfig, DeviceConfig

from .conftest import error_of, record, register_device, v1_database

pytestmark = pytest.mark.unit
URL = "/api/v0/devices/p1/dli"
SHANGHAI = {"latitude": 31.2304, "longitude": 121.4737}


def _rows(path: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        return {
            "schema": con.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall(),
            "acquisitions": con.execute("SELECT * FROM acquisitions ORDER BY id").fetchall(),
            "settings": dict(con.execute("SELECT key, value_json FROM app_settings").fetchall()),
        }


def test_saving_writes_only_the_location_and_the_period_follows(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    path = Path(device["path"])
    before = client.get(URL).json()  # stores the enable time (D-228 A)
    rows = _rows(path)
    assert before["location"]["stored"] is False
    saved = client.put(f"{URL}/location", json=SHANGHAI)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["location"]["stored"] is True
    assert (body["location"]["latitude"], body["location"]["longitude"]) == (31.2304, 121.4737)
    assert body["period"]["start"] != before["period"]["start"]  # 重置周期: sunrise of the new place
    assert body["enabled"] == before["enabled"]  # the enable time is not reset (DLI-024)
    after = _rows(path)
    assert after["schema"] == rows["schema"] and after["acquisitions"] == rows["acquisitions"]
    changed = {key for key in after["settings"] if after["settings"][key] != rows["settings"].get(key)}
    assert changed == {"dli_location"}
    assert client.get(URL).json()["period"] == body["period"]  # kept: the next read uses the saved place


def test_the_stored_value_is_what_v103_writes(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    reference = tmp_path / "v103.sqlite3"
    ParDatabase(reference).save_dli_location(31.2304, 121.4737)
    assert client.put(f"{URL}/location", json={"latitude": 31.23041, "longitude": 121.47369}).status_code == 200
    ours = _rows(Path(device["path"]))["settings"]["dli_location"]
    assert ours == _rows(reference)["settings"]["dli_location"]  # four decimals, as V1.0.3's spin boxes
    assert ParDatabase(Path(device["path"])).load_dli_location() == (31.2304, 121.4737)
    assert json.loads(ours) == SHANGHAI


def test_saving_again_replaces_the_location(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    client.put(f"{URL}/location", json=SHANGHAI)
    client.put(f"{URL}/location", json={"latitude": -33.8688, "longitude": -70.6693})
    stored = json.loads(_rows(Path(device["path"]))["settings"]["dli_location"])
    assert stored == {"latitude": -33.8688, "longitude": -70.6693}  # south and west are negative (DLI-026)


def test_read_only_mode_refuses_and_writes_nothing(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    rows = _rows(Path(device["path"]))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    context.acquisition.tiers.write(FACTORY_TIER)
    refused = client.put(f"{URL}/location", json=SHANGHAI)
    assert refused.status_code == 403 and error_of(refused)["code"] == "feature_disabled"
    assert "只读模式" in error_of(refused)["message"]
    assert _rows(Path(device["path"])) == rows


def test_a_database_outside_the_data_folder_is_refused(client: TestClient, tmp_path: Path) -> None:
    register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    outside = v1_database(tmp_path / "elsewhere" / "par.sqlite3", [record()])
    AppConfigStore(context.paths.data_dir).save(
        AppConfig(devices=[DeviceConfig(name="外部", database_path=str(outside))], configured=True)
    )
    rows = _rows(outside)
    refused = client.put(f"{URL}/location", json=SHANGHAI)
    assert refused.status_code == 409 and error_of(refused)["code"] == "config_unavailable"
    assert _rows(outside) == rows


@pytest.mark.parametrize(
    "body",
    [{"latitude": 90, "longitude": 0}, {"latitude": 0, "longitude": 180.5}, {"latitude": -89.95, "longitude": 0}],
)
def test_values_outside_v103_ranges_are_refused(client: TestClient, tmp_path: Path, body: dict[str, float]) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    rows = _rows(Path(device["path"]))
    refused = client.put(f"{URL}/location", json=body)
    assert refused.status_code == 400 and error_of(refused)["code"] == "invalid_argument"
    assert _rows(Path(device["path"])) == rows


def test_a_refused_date_writes_nothing(client: TestClient, tmp_path: Path) -> None:
    """Review of PR #117: the date of the period shown afterwards is checked before the location is written."""
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    rows = _rows(Path(device["path"]))
    refused = client.put(f"{URL}/location", params={"date": "2099-01-01"}, json=SHANGHAI)
    assert refused.status_code == 400 and error_of(refused)["code"] == "invalid_argument"
    assert _rows(Path(device["path"])) == rows


@pytest.mark.parametrize(
    "body", [{"latitude": "31.5", "longitude": 121.0}, {"latitude": 31.5, "longitude": True}, {"latitude": 31.5}]
)
def test_only_numbers_are_accepted(client: TestClient, tmp_path: Path, body: dict[str, Any]) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    rows = _rows(Path(device["path"]))
    refused = client.put(f"{URL}/location", json=body)
    assert refused.status_code == 400 and error_of(refused)["code"] == "invalid_argument"
    assert _rows(Path(device["path"])) == rows


def test_a_database_without_the_settings_table_is_refused_and_not_changed(tmp_path: Path) -> None:
    from par_app.application.dli_enable import SettingsTableMissing, store_location

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE acquisitions (id INTEGER PRIMARY KEY)")
    before = path.read_bytes()
    with pytest.raises(SettingsTableMissing) as refused:
        store_location(path, 31.2304, 121.4737, "2026-10-27T09:30:00.000")
    assert refused.value.retryable is False  # no table is created, so trying again cannot help
    assert path.read_bytes() == before


def test_a_whole_number_is_stored_as_v103_stores_it(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    reference = tmp_path / "v103.sqlite3"
    ParDatabase(reference).save_dli_location(31.0, 121.0)  # QDoubleSpinBox.value() is always a float
    assert client.put(f"{URL}/location", json={"latitude": 31, "longitude": 121}).status_code == 200
    assert _rows(Path(device["path"]))["settings"]["dli_location"] == _rows(reference)["settings"]["dli_location"]
