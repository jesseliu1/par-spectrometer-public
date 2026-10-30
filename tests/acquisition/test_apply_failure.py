"""A saved configuration that the coordinator fails to apply (spec review Q-1; D-221).

V1.0.3 (PR #43, D-178 B): DeviceHub.apply writes the file, then the coordinator rebuilds its states; when that fails it
keeps the previous configuration running and reports "应用配置失败：<原因>" on the bus line. V1.0.3's settings page
then keeps its save button disabled (DEF-31). The alpha instead says that the saved configuration has not taken
effect (the status carries `config_apply_error` until the next configuration is applied or the next start), and
saving again is allowed at once (a deliberate deviation from DEF-31). The file is not written back (follows D-183).
"""

from __future__ import annotations

from typing import Any

import pytest

from par_app.acquisition_host.bridge import EventBridge
from par_app.application.acquisition import StatusCache
from par_app.coordinator import PollingCoordinator
from par_app.models import AppConfig, BusConfig
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import virtual_clock, yielding_clock

pytestmark = pytest.mark.qt


def _body(config: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    keep = ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")
    return {"bus": config["bus"], "devices": [{k: d[k] for k in keep} for d in config["devices"]] + list(extra)}


def test_a_failed_apply_is_reported_as_not_in_effect_and_saving_again_is_allowed(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice(), 3: FakeDevice()})
    port.hold_at = 400
    alpha.enable_tier_1()
    config = alpha.get("/api/v0/acquisition-config").json()
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        assert alpha.get("/api/v0/acquisition/status").json()["config_apply_error"] is None
        rebuild = coordinator._rebuild_states

        def broken() -> None:
            raise OSError("disk went away")

        monkeypatch.setattr(coordinator, "_rebuild_states", broken)
        saved = alpha.put("/api/v0/acquisition-config", _body(config, {"name": "West", "slave_id": 3, "enabled": True}))
        assert saved.status_code == 200, saved.text
        pump(lambda: alpha.context.acquisition.cache.snapshot()["config_apply_error"] is not None)
        status = alpha.get("/api/v0/acquisition/status").json()
        assert status["config_apply_error"].startswith("应用配置失败：")
        assert [device["name"] for device in status["devices"]] == ["North", "South"]  # the old one still runs
        assert [device["name"] for device in alpha.get("/api/v0/acquisition-config").json()["devices"]] == [
            "North",
            "South",
            "West",
        ]  # the file holds the new one (D-183 decides whether it is written back)
        form = alpha.get("/api/v0/acquisition-config").json()["form"]
        assert "未生效" in form["apply_failed_text"]

        monkeypatch.setattr(coordinator, "_rebuild_states", rebuild)
        again = alpha.put("/api/v0/acquisition-config", _body(saved.json()))  # the form as shown: the file
        assert again.status_code == 200, again.text  # retried at once, West keeps its new database (not DEF-31)
        pump(lambda: len(alpha.context.acquisition.cache.snapshot()["devices"]) == 3)
        assert alpha.get("/api/v0/acquisition/status").json()["config_apply_error"] is None
        pump(port.held.is_set)
        port.release = lambda: not coordinator._running
        assert alpha.post("/api/v0/acquisition/stop").status_code == 202
        pump(lambda: alpha.takeover() == "released")


def test_bridge_keeps_an_unknown_poll_cycle_as_none_and_tracks_apply_failures(qt_app: object) -> None:
    coordinator = PollingCoordinator(AppConfig(bus=BusConfig(serial_port="", host="")), clock=virtual_clock())
    cache = StatusCache(virtual_clock())
    events: list[tuple[str, dict[str, Any]]] = []
    bridge = EventBridge(coordinator, cache, lambda name, data: events.append((name, data)))
    try:
        bridge._on_config_applied(object())  # not an AppConfig: the cycle is unknown, not 0.0 (R-1-6; nit 2)
        assert cache.snapshot()["poll_cycle_seconds"] is None
        bridge._on_bus_state("error", "应用配置失败：x")
        assert cache.snapshot()["config_apply_error"] == "应用配置失败：x"
        bridge._on_bus_state("info", "正在连接…")
        assert cache.snapshot()["config_apply_error"] == "应用配置失败：x"  # kept until a configuration is applied
        bridge._on_config_applied(AppConfig(bus=BusConfig(serial_port="", host="")))
        assert cache.snapshot()["config_apply_error"] is None
        bridge._on_bus_state("error", "调度异常：x")
        assert cache.snapshot()["config_apply_error"] is None  # other errors are bus errors, not apply failures
    finally:
        bridge.detach()
