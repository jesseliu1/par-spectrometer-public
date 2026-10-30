"""Tier 1 when the alpha's configuration or a database it names cannot be used (spec review M-1; D-220).

V1.0.3 (main.create_startup_hub; CONF-008, CONF-010, D-141): the startup check fails, the user may cancel or confirm
"重新配置"; confirmed, the program starts with an empty configuration and the original file is backed up
(app_config.before_recovery_<time>.json) when the new configuration is first saved. Before this fix the alpha had no
way out: 开始采集 answered 409 config_unavailable and saving answered 409 not_running ("先开始采集").

Now, while nothing is taken over and the configuration is unusable (the file cannot be read, a database is outside
the alpha's folder, or the last 开始采集 failed with config_unavailable), a save that asks for `reconfigure` is
applied from an empty configuration through V1.0.3's DeviceHub.apply, with AppConfigStore.preserve_before_save set as
V1.0.3 sets it. No lock is taken and no port is opened. Afterwards 开始采集 works as usual.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt
BUS = {
    "transport": "rtu",
    "serial_port": "COM7",
    "host": "",
    "tcp_port": 502,
    "baudrate": 9600,
    "parity": "N",
    "timeout_seconds": 1.0,
    "poll_cycle_seconds": 40.0,
}


def _body(*devices: dict[str, Any], reconfigure: bool = True) -> dict[str, Any]:
    return {"bus": BUS, "devices": list(devices), "reconfigure": reconfigure}


def _port(monkeypatch: pytest.MonkeyPatch) -> FakeSerial:
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    return FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})


def _backups(alpha: Alpha) -> list[Path]:
    return sorted((alpha.data_dir / "config").glob("app_config.before_recovery_*.json"))


def _stop(alpha: Alpha, port: FakeSerial) -> None:
    coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
    port.release = lambda: not coordinator._running
    assert alpha.post("/api/v0/acquisition/stop").status_code == 202
    pump(lambda: alpha.takeover() == "released")


def test_an_unreadable_configuration_is_reconfigured_from_empty_without_a_takeover(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = alpha.data_dir / "config" / "app_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_bytes(b"{not json")
    port = _port(monkeypatch)
    alpha.enable_tier_1()

    view = alpha.get("/api/v0/acquisition-config")
    assert view.status_code == 200, view.text  # the page can still show the form (was 409)
    problem = view.json()["problem"]
    assert problem is not None and str(config_file) in problem["message"]
    form = view.json()["form"]
    assert "是否以空配置重新配置" in form["reconfigure_text"] and "先备份原配置" in form["reconfigure_text"]
    assert [row["name"] for row in view.json()["blank_rows"]] == ["", "", "", ""]

    with wired(port):
        refused = alpha.post("/api/v0/acquisition/start")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "config_unavailable"
    plain = alpha.put(
        "/api/v0/acquisition-config", _body({"name": "North", "slave_id": 1, "enabled": True}, reconfigure=False)
    )
    assert plain.status_code == 409 and plain.json()["error"]["code"] == "not_running"

    saved = alpha.put("/api/v0/acquisition-config", _body({"name": "North", "slave_id": 1, "enabled": True}))
    assert saved.status_code == 200, saved.text
    assert saved.json()["problem"] is None
    assert [device["name"] for device in saved.json()["devices"]] == ["North"]
    assert saved.json()["devices"][0]["database_path"] == str(alpha.data_dir / "data" / "devices" / "North.sqlite3")
    backups = _backups(alpha)
    assert len(backups) == 1 and backups[0].read_bytes() == b"{not json"  # CONF-010 / D-141: backed up first
    assert port.opened == 0 and not alpha.host.lock.held and alpha.takeover() == "released"
    assert alpha.host.hub is None

    port.hold_at = 60
    with wired(port):
        started = alpha.post("/api/v0/acquisition/start")
        assert started.status_code == 202, started.text
        pump(port.held.is_set)
        _stop(alpha, port)


def test_a_database_that_failed_the_start_check_is_reconfigured(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    north = alpha.data_dir / "data" / "devices" / "North.sqlite3"
    north.unlink()
    original = (alpha.data_dir / "config" / "app_config.json").read_bytes()
    port = _port(monkeypatch)
    alpha.enable_tier_1()
    assert alpha.get("/api/v0/acquisition-config").json()["problem"] is None  # the view opens no database

    with wired(port):
        refused = alpha.post("/api/v0/acquisition/start")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "config_unavailable"
    assert "以空配置重新配置" in refused.json()["error"]["message"]  # says where the way out is
    problem = alpha.get("/api/v0/acquisition-config").json()["problem"]
    assert problem is not None and "North.sqlite3" in (problem["detail"] or "")

    north_row = {"name": "North", "slave_id": 1, "enabled": True}
    south_row = {"name": "South", "slave_id": 2, "enabled": True}
    exists = alpha.put("/api/v0/acquisition-config", _body(north_row, south_row))
    assert exists.status_code == 400  # V1.0.3's own check: South's default database is still there
    assert exists.json()["error"]["message"].startswith("默认数据库文件已存在：South.sqlite3。")
    assert _backups(alpha) == []  # nothing saved, nothing backed up

    saved = alpha.put("/api/v0/acquisition-config", _body(north_row, {**south_row, "reuse_existing": True}))
    assert saved.status_code == 200, saved.text
    assert saved.json()["problem"] is None and north.is_file()
    assert [backup.read_bytes() for backup in _backups(alpha)] == [original]
    assert port.opened == 0 and not alpha.host.lock.held


def test_reconfigure_is_only_for_an_unusable_configuration(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    before = (alpha.data_dir / "config" / "app_config.json").read_bytes()
    body = _body({"name": "West", "slave_id": 3, "enabled": True})
    assert alpha.put("/api/v0/acquisition-config", body).status_code == 403  # tier 0: feature_disabled first
    alpha.enable_tier_1()
    refused = alpha.put("/api/v0/acquisition-config", body)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_running"
    assert (alpha.data_dir / "config" / "app_config.json").read_bytes() == before and _backups(alpha) == []


def test_a_successful_start_clears_the_recorded_problem(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    north = alpha.data_dir / "data" / "devices" / "North.sqlite3"
    moved = north.with_suffix(".away")
    north.rename(moved)
    port = _port(monkeypatch)
    alpha.enable_tier_1()
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 409
    assert alpha.get("/api/v0/acquisition-config").json()["problem"] is not None
    moved.rename(north)  # the user restored the file (V1.0.3's first suggestion)
    port.hold_at = 60
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        assert alpha.get("/api/v0/acquisition-config").json()["problem"] is None
        pump(port.held.is_set)
        _stop(alpha, port)
    stored = json.loads((alpha.data_dir / "config" / "app_config.json").read_text(encoding="utf-8"))
    assert [device["name"] for device in stored["devices"]] == ["North", "South"]
