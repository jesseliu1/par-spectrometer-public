"""PR #55 review: tier 1 makes no maintenance call (17_ 3.2 tier table; review M1, M2) and the configuration is not
saved while a maintenance task runs (review Q2; D-218).

M1: the settings page's "通信参数当前值" re-reads the device on a reconnect only while the settings page is shown at
tier 2 (V1.0.3 ui.py re-reads only while the settings tab is current). M2: the tier check and the action are one step
on the main thread (a 2 -> 1 that ran between the HTTP gate and the main thread refuses the action) and the write
confirmations issued at tier 2 do not survive a drop to tier 1.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from par_app.application.errors import Busy, FeatureDisabled
from tests.acquisition.conftest import Alpha, pump
from tests.acquisition.maintenance_support import Running, controller, error_code, running_alpha

pytestmark = pytest.mark.qt
SETTINGS_READ = "/api/v0/acquisition/devices/p1/comm/read"
SETTINGS_LEAVE = "/api/v0/acquisition/devices/comm/read"


@pytest.fixture
def running(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    yield from running_alpha(alpha, monkeypatch)


def _settings_read(running: Running) -> None:
    alpha = running.alpha
    response = alpha.post(SETTINGS_READ)
    assert response.status_code == 200, response.text
    pump(lambda: not controller(alpha).settings["North"].pending)
    assert running.calls == ["comm_read"]
    running.calls.clear()


def _bus_flap(running: Running) -> None:
    """The bus goes error -> ok (MainWindow._on_bus_state re-reads on the reconnect). V1.0.3 and the alpha decide
    "connected" from the coordinator's client when they handle the signal (D-222), so the client is gone while the
    error is handled and back for the ok; the coordinator thread waits on a poll frame meanwhile."""
    alpha, port = running.alpha, running.port
    hub = alpha.host.hub
    assert hub is not None
    coordinator = hub.coordinator
    released = threading.Event()
    port.held.clear()
    port.release = released.is_set
    port.hold_when = lambda _frame: True
    pump(port.held.is_set)
    client, coordinator._client = coordinator._client, None
    try:
        signal = coordinator.bus_state_changed
        signal.emit("error", "串口断开")
        pump(lambda: controller(alpha).bus_level == "error")
        assert not controller(alpha).bus_connected
        coordinator._client = client
        signal.emit("ok", "")
        pump(lambda: controller(alpha).bus_level == "ok")
    finally:
        coordinator._client = client
        released.set()


def test_m1_reconnect_rereads_only_while_the_settings_page_is_shown(running: Running) -> None:
    alpha = running.alpha
    _settings_read(running)
    _bus_flap(running)  # control: the settings page is shown at tier 2, so V1.0.3 re-reads
    pump(lambda: running.calls == ["comm_read"])
    pump(lambda: not controller(alpha).settings["North"].pending)
    running.calls.clear()
    left = alpha.delete(SETTINGS_LEAVE)
    assert left.status_code == 204, left.text
    _bus_flap(running)
    assert running.calls == []


def test_m1_tier_1_makes_no_automatic_settings_read(running: Running) -> None:
    alpha = running.alpha
    _settings_read(running)
    assert alpha.put("/api/v0/tier", {"tier": 1}).status_code == 200
    _bus_flap(running)
    assert running.calls == []
    assert controller(alpha).settings_watch is None


def test_m2_a_drop_to_tier_1_between_the_gate_and_the_main_thread_refuses_the_action(running: Running) -> None:
    alpha = running.alpha
    issued = alpha.post("/api/v0/maintenance/enter/confirmations", {})
    assert issued.status_code == 201, issued.text
    maintenance = controller(alpha)
    maintenance.lowered()  # the 2 -> 1 request's main-thread step ran before this request's
    with pytest.raises(FeatureDisabled):
        maintenance.act("enter", {}, issued.json()["confirmation_id"])
    with pytest.raises(FeatureDisabled):
        maintenance.act("calibration_read", {}, None)  # writes registers 39/40 (ruling 48), needs no confirmation
    with pytest.raises(FeatureDisabled):
        maintenance.confirm("enter", {})
    with pytest.raises(FeatureDisabled):
        maintenance.settings_comm(0)
    assert running.calls == []
    assert not maintenance.maintenance()


def test_m2_lowering_is_refused_on_the_main_thread_while_a_task_runs(running: Running) -> None:
    maintenance = controller(running.alpha)
    maintenance.window.diagnostics_busy = True  # a task in flight (injected)
    with pytest.raises(Busy):
        maintenance.lowered()
    maintenance.window.diagnostics_busy = False
    maintenance.lowered()


def test_m2_confirmations_do_not_survive_a_drop_to_tier_1(running: Running) -> None:
    alpha = running.alpha
    issued = alpha.post("/api/v0/maintenance/enter/confirmations", {})
    assert issued.status_code == 201, issued.text
    assert alpha.put("/api/v0/tier", {"tier": 1}).status_code == 200
    again = alpha.post("/api/v0/tier/confirmations", {"tier": 2})
    assert alpha.put("/api/v0/tier", {"tier": 2, "confirmation_id": again.json()["confirmation_id"]}).status_code == 200
    running.refused(
        alpha.post("/api/v0/maintenance/enter", {"confirmation_id": issued.json()["confirmation_id"]}),
        409,
        "confirmation_required",
    )
    assert alpha.confirmed("/api/v0/maintenance/enter").status_code == 200  # tier 2 again: maintenance works
    pump(lambda: controller(alpha).maintenance())


def test_q2_configuration_is_not_saved_while_a_maintenance_task_runs(running: Running) -> None:
    alpha = running.alpha
    config = alpha.get("/api/v0/acquisition-config").json()
    devices = [
        {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
        for d in config["devices"]
    ]
    controller(alpha).window.diagnostics_busy = True  # a task in flight (injected)
    controller(alpha)._changed()
    response = alpha.put("/api/v0/acquisition-config", {"bus": config["bus"], "devices": devices[:1]})
    assert response.status_code == 409 and error_code(response) == "busy", response.text
    hub = alpha.host.hub
    assert hub is not None and len(hub.keys()) == 2
    controller(alpha).window.diagnostics_busy = False
    controller(alpha)._changed()
