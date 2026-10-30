"""The pages read only the alpha's own device databases (issue #82).

History, spectrum calculation, export, DLI and the settings page's device summary read the databases of the devices
registered in the alpha's own tier-1 configuration (<data dir>/data/devices), read only, while the acquisition
writes them; imported snapshots are no longer shown; tier 0 lists no device and the pages are empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.app_config import AppConfigStore
from par_app.application.own_devices import TIER_0_EMPTY
from par_app.application.paths import AlphaPaths
from par_app.database import ParDatabase
from par_app.domain.clock import FakeClock
from par_app.models import AppConfig, DeviceConfig

from .conftest import (
    AUTH,
    DAY,
    HOST,
    NOW,
    TOKEN,
    ConfigOnlyBackend,
    error_of,
    import_snapshot,
    record,
    register_device,
    v1_database,
)

pytestmark = pytest.mark.unit
LIST = "/api/v0/devices/p1/acquisitions"
DEVICE_ROUTES = (
    (LIST, DAY),
    ("/api/v0/devices/p1/dli", None),
    ("/api/v0/devices/p1/summary", None),
    ("/api/v0/devices/p1/latest", None),
    ("/api/v0/operation-sources/p1/spectra", None),
    ("/api/v0/devices/p1/export/count", None),
)


def test_tier_0_lists_no_device_and_every_page_is_empty(client: TestClient) -> None:
    items = client.get("/api/v0/devices").json()["items"]
    assert [item["configured"] for item in items] == [False] * 4
    sources = client.get("/api/v0/operation-sources").json()
    assert (sources["items"], sources["initial_a"], sources["initial_b"]) == ([], None, None)
    assert [row["configured"] for row in client.get("/api/v0/settings").json()["devices"]] == [False] * 4
    for path, params in DEVICE_ROUTES:
        response = client.get(path, params=params)
        assert response.status_code == 404, (path, response.text)
        error = error_of(response)
        assert error["code"] == "device_not_found" and TIER_0_EMPTY in error["message"] + (error["detail"] or "")


def test_an_imported_snapshot_is_not_shown(client: TestClient, tmp_path: Path) -> None:
    import_snapshot(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    assert [item["configured"] for item in client.get("/api/v0/devices").json()["items"]] == [False] * 4
    assert client.get(LIST, params=DAY).status_code == 404


def test_a_new_record_shows_without_any_import(client: TestClient, tmp_path: Path) -> None:
    """Acceptance 1: the acquisition saves a record into the device's database; history lists it at once."""
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    assert len(client.get(LIST, params=DAY).json()["items"]) == 1
    assert client.get("/api/v0/devices").json()["tier"] == 1
    database = ParDatabase(Path(device["path"]))  # what the coordinator does while acquiring (WAL, kept open)
    with database.connect():
        database.save_acquisition(record("2026-10-01T12:05:00.000"))
        body = client.get(LIST, params=DAY).json()
    assert [item["acquired_at"] for item in body["items"]] == ["2026-10-01T12:05:00.000", "2026-10-01T12:00:00.000"]
    assert body["snapshot_id"] == device["id"] and body["source"] == "live_ro"
    detail = client.get(f"{LIST}/{body['items'][0]['id']}").json()
    assert detail["success"] and detail["spectrum_state"] == "ok"


def test_a_registered_device_without_records_is_empty_not_an_error(client: TestClient, tmp_path: Path) -> None:
    register_device(client, v1_database(tmp_path / "v1" / "empty.sqlite3", []))
    assert client.get(LIST, params=DAY).json()["items"] == []
    assert client.get("/api/v0/devices/p1/dli").status_code == 200
    assert client.get("/api/v0/devices/p1/summary").json()["total"] == 0
    assert client.get("/api/v0/operation-sources/p1/spectra").json()["items"] == []
    assert client.get("/api/v0/devices/p1/export/count", params={"formats": ["csv"]}).json()["count"] == 0
    latest = client.get("/api/v0/devices/p1/latest")
    assert latest.status_code == 200 and latest.json()["display_record"] is None


def test_nothing_acquiring_reads_as_paused(client: TestClient, tmp_path: Path) -> None:
    """Not taken over (or maintenance, a halt): DLI and the overview say 采集已暂停, as the live overview (D-213)."""
    register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]), acquiring=False)
    assert client.get("/api/v0/devices/p1/dli").json()["paused"] is True
    register_device(client, v1_database(tmp_path / "v1" / "par2.sqlite3", [record()]), acquiring=True)
    assert client.get("/api/v0/devices/p1/dli").json()["paused"] is False


def test_another_database_at_the_same_position_has_another_id(client: TestClient, tmp_path: Path) -> None:
    first = register_device(client, v1_database(tmp_path / "v1" / "a.sqlite3", [record()]))
    second = register_device(client, v1_database(tmp_path / "v1" / "b.sqlite3", [record()]))
    assert first["id"] != second["id"]
    body = {"a": {"source": "p1", "id": 1, "snapshot_id": first["id"]}, "b": None}
    response = client.post("/api/v0/operations/inputs", json=body)
    assert response.status_code == 409 and error_of(response)["code"] == "snapshot_changed"


def test_a_database_outside_the_alpha_folder_is_refused(client: TestClient, tmp_path: Path) -> None:
    register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    outside = v1_database(tmp_path / "elsewhere" / "par.sqlite3", [record()])
    AppConfigStore(context.paths.data_dir).save(
        AppConfig(devices=[DeviceConfig(name="外部", database_path=str(outside))], configured=True)
    )
    response = client.get(LIST, params=DAY)
    assert response.status_code == 409 and error_of(response)["code"] == "config_unavailable"


def test_the_data_is_still_there_after_an_upgrade(client: TestClient, tmp_path: Path) -> None:
    """Acceptance 7: a new alpha version starts on the same data directory and reads the same records."""
    register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    before = client.get(LIST, params=DAY).json()["items"]
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    restarted = ServiceContext(AlphaPaths(context.paths.data_dir), FakeClock(NOW))
    restarted.acquisition.attach(ConfigOnlyBackend(context.paths.data_dir))  # type: ignore[arg-type]
    app = create_app(restarted, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}", headers=AUTH) as again:
        assert again.get(LIST, params=DAY).json()["items"] == before


def test_a_disabled_device_reads_disabled_and_an_outside_database_a_fault(client: TestClient, tmp_path: Path) -> None:
    """UI-259: a registered but disabled device is grey 停用; a database outside the alpha's folder is listed as a
    fault, not offered as a calculation source or export device, and reading it is refused (PR #95 review)."""
    register_device(client, v1_database(tmp_path / "v1" / "a.sqlite3", [record()]))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    inside = context.paths.devices_dir / "a.sqlite3"
    outside = v1_database(tmp_path / "elsewhere" / "b.sqlite3", [record()])
    AppConfigStore(context.paths.data_dir).save(
        AppConfig(
            devices=[
                DeviceConfig(name="停用的", slave_id=1, enabled=False, database_path=str(inside)),
                DeviceConfig(name="外部", slave_id=2, database_path=str(outside)),
            ],
            configured=True,
        )
    )
    items = client.get("/api/v0/devices").json()["items"]
    assert [(item["display_state"], item["enabled"]) for item in items[:2]] == [("disabled", False), ("fault", True)]
    assert [item["key"] for item in client.get("/api/v0/operation-sources").json()["items"]] == ["p1"]
    rows = client.get("/api/v0/settings").json()["devices"]
    assert (rows[0]["configured"], rows[1]["configured"]) == (True, False)
    assert rows[1]["state_text"] == "设备库不在本软件的数据目录中，不能读取"
    assert client.get("/api/v0/devices/p2/acquisitions", params=DAY).status_code == 409


def test_the_live_source_reads_the_configuration_once(client: TestClient, tmp_path: Path) -> None:
    """Name, database and poll cycle come from one read, so a save in between cannot mix them (PR #95 review)."""
    register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    backend = context.acquisition.backend
    assert isinstance(backend, ConfigOnlyBackend)
    reads: list[int] = []
    original = backend.read_config
    backend.read_config = lambda: reads.append(1) or original()  # type: ignore[method-assign]
    source = context.acquisition.live_source("p1")
    assert len(reads) == 1 and source.name == "par" and source.poll_cycle_seconds == 60.0


def test_an_export_refuses_a_range_that_gained_records_after_the_confirmation(
    client: TestClient, tmp_path: Path
) -> None:
    """EXP-052 on a growing database: the acquisition saves a record into the confirmed range before 是 is clicked;
    the export is refused (409) instead of writing a record the confirmation did not count (PR #95 review)."""
    device = register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    body = {
        "start": "2026-10-01T00:00:00",
        "end": "2026-10-01T23:59:59",
        "formats": ["csv"],
        "snapshot_id": device["id"],
        "records": 1,
    }
    ParDatabase(Path(device["path"])).save_acquisition(record("2026-10-01T12:05:00.000"))
    refused = client.post("/api/v0/devices/p1/export", json=body)
    assert refused.status_code == 409 and error_of(refused)["code"] == "snapshot_changed"
    assert "重新确认" in error_of(refused)["message"]
    done = client.post("/api/v0/devices/p1/export", json={**body, "records": 2})
    assert done.status_code == 201 and done.json()["records"] == 2
