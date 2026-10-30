"""The verification state machine of 17_ section 5 (S0-S6), on the real coordinator and the fake bus.

States are read the way the page reads them (GET /maintenance/state and v1_reads); every transition the alpha starts
or observes is driven through the API. D-167's conservative cells (a pending write blocks resume also when its device
is disabled or removed; a verified one does not, D-131; restarting keeps maintenance) are decided by V1.0.3's code,
which these tests only observe.
"""

from __future__ import annotations

import pytest

from par_app.acquisition_host import v1_reads
from par_app.acquisition_host import v1_texts as texts
from tests.acquisition.conftest import Alpha, pump
from tests.acquisition.maintenance_support import (
    STATE,
    controller,
    enter,
    fake_port,
    form,
    open_page,
    save_registration,
    start,
    wait_idle,
)
from tests.support.fake_bus import FakeDevice, FakeSerial, wired

pytestmark = pytest.mark.qt
PENDING_TEXT = "写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"


def _session(alpha: Alpha) -> dict[str, object]:
    c = controller(alpha)
    return v1_reads.session_state(c.session_of("North"))


def _restart(alpha: Alpha) -> None:
    assert alpha.post("/api/v0/acquisition/stop").status_code == 202
    pump(lambda: alpha.takeover() == "released")
    assert alpha.post("/api/v0/acquisition/start").status_code == 202
    pump(lambda: controller(alpha).hub is not None)


def _pending(alpha: Alpha, devices: dict[int, FakeDevice], new: int = 5) -> None:
    """S0 -> S1 -> S2 -> S3 -> S4 with a verification that fails (the device is silent on its new address)."""
    open_page(alpha, tab=2)
    state = enter(alpha)
    assert state["maintenance"] and _session(alpha) == {"pending": None, "verified": None, "baseline": None}  # S2
    assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
    wait_idle(alpha)
    assert _session(alpha)["baseline"] is not None  # S3
    devices[1].mute_after_move = True
    assert alpha.confirmed("/api/v0/maintenance/comm/write", form(new=new)).status_code == 200
    state = wait_idle(alpha)
    assert _session(alpha)["pending"] is not None  # S4: the automatic verification failed, still pending
    assert state["communication"]["state"].startswith("操作失败：")
    assert state["communication"]["verify_enabled"] and not state["communication"]["read_enabled"]
    assert state["target_locked"] and not state["footer"]["resume_enabled"]


def test_s0_to_s5_and_back_to_s0(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    with wired(fake_port(monkeypatch, devices)):
        start(alpha)
        _pending(alpha, devices)
        devices[5].mode = "ok"
        assert alpha.post("/api/v0/maintenance/comm/verify", form(new=5)).status_code == 200
        state = wait_idle(alpha)
        assert _session(alpha)["pending"] is None and _session(alpha)["verified"] is not None  # S5
        assert state["communication"]["state"].startswith("设备身份和新参数核对通过，但暂不能恢复采集")
        assert state["communication"]["read_enabled"]  # S5 -> S3 is allowed (a new round)
        save_registration(alpha, {"North": 5})
        pump(lambda: controller(alpha).resume_gate().allowed)
        assert alpha.confirmed("/api/v0/maintenance/leave").status_code == 200
        pump(lambda: not controller(alpha).maintenance())  # S0
        assert _session(alpha) == {"pending": None, "verified": None, "baseline": None}
        assert alpha.get(STATE).json()["communication"]["state"].startswith("未进入通信维护；")


def test_s4_survives_a_restart_and_s1_failure_returns_to_s0(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    port: FakeSerial = fake_port(monkeypatch, devices)
    with wired(port):
        start(alpha)
        _pending(alpha, devices)
        _restart(alpha)  # MAINT-126: the stored pending write stops acquisition at once
        pump(lambda: controller(alpha).maintenance())
        state = open_page(alpha, tab=2)
        assert state["target"] == "North" and state["communication"]["pending"]  # G7: the pending device first
        assert state["communication"]["state"] == texts.STATE_PENDING
        assert state["footer"]["resume_reason"] == PENDING_TEXT
        # stopping in maintenance says what stays behind (17_ section 7)
        assert "下次开始采集会先进入维护停止" in alpha.get("/api/v0/tier").json()["stop_text"]


def test_enter_failure_is_s1_to_s0(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    port = fake_port(monkeypatch, devices)
    with wired(port):
        start(alpha)
        open_page(alpha, tab=2)
        port.close_error = "handle busy"
        assert alpha.confirmed("/api/v0/maintenance/enter").status_code == 200
        pump(lambda: not controller(alpha).window.entering)
        state = wait_idle(alpha)
        assert not state["maintenance"] and state["communication"]["enter_visible"]


@pytest.mark.parametrize("change", ["disabled", "removed"])
def test_d167_pending_still_blocks_and_verified_lets_through(
    change: str, alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    with wired(fake_port(monkeypatch, devices)):
        start(alpha)
        _pending(alpha, devices)
        _change(alpha, change)
        assert controller(alpha).resume_gate().reason == PENDING_TEXT  # D-167 1A
        _change(alpha, "back")
        devices[5].mode = "ok"
        # V1.0.3 rebuilds the communication tab on every saved registration (rebuild_devices, #58, D-224): the
        # isolation tick is gone whether the device was disabled or removed
        if change == "removed":
            assert alpha.delete("/api/v0/maintenance/page").status_code == 200
            assert open_page(alpha, tab=2)["target"] == "North"  # reopening finds the pending device (G7)
        refused = alpha.post("/api/v0/maintenance/comm/verify", form(new=5))
        assert refused.status_code == 409 and refused.json()["error"]["message"] == texts.ISOLATION_TEXT  # D-218
        controller(alpha).comm.isolated = True  # stands for #57's fix; the D-167 gate below is the subject here
        assert alpha.post("/api/v0/maintenance/comm/verify", form(new=5)).status_code == 200
        wait_idle(alpha)
        _change(alpha, change)
        pump(lambda: controller(alpha).resume_gate().allowed)  # D-131: verified and not active
        assert alpha.confirmed("/api/v0/maintenance/leave").status_code == 200
        pump(lambda: not controller(alpha).maintenance())
        _restart(alpha)  # the verified result is deferred, so it no longer stops a restart (D-131, D-132)
        pump(lambda: bool(controller(alpha).device_status))
        assert not controller(alpha).maintenance()


def _change(alpha: Alpha, change: str) -> None:
    hub = alpha.host.hub
    assert hub is not None
    if change == "disabled":
        save_registration(alpha, enabled={"North": False})
        pump(lambda: not hub.config.devices[0].enabled)
    elif change == "removed":
        config = alpha.get("/api/v0/acquisition-config").json()
        keep = [
            {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
            for d in config["devices"]
            if d["name"] != "North"
        ]
        assert alpha.put("/api/v0/acquisition-config", {"bus": config["bus"], "devices": keep}).status_code == 200
        pump(lambda: [d.name for d in hub.config.devices] == ["South"])
    else:
        config = alpha.get("/api/v0/acquisition-config").json()
        devices = [
            {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
            for d in config["devices"]
        ]
        if not any(d["name"] == "North" for d in devices):
            devices.insert(0, {"name": "North", "slave_id": 1, "enabled": True, "reuse_existing": True})
        for device in devices:
            device["enabled"] = True
        assert alpha.put("/api/v0/acquisition-config", {"bus": config["bus"], "devices": devices}).status_code == 200
        pump(lambda: [d.name for d in hub.config.devices][:1] == ["North"] and hub.config.devices[0].enabled)


def test_halt_is_s6_and_non_target_events_change_nothing(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    with wired(fake_port(monkeypatch, devices)):
        start(alpha)
        open_page(alpha, tab=2)
        before = alpha.get(STATE).json()["communication"]
        hub = alpha.host.hub
        assert hub is not None
        hub.coordinator.task_finished.emit("South", "maintenance_read", True, {"identity": {}})  # MAINT-032/103
        hub.coordinator.task_finished.emit("North", "time_sync", True, None)
        pump(lambda: controller(alpha).version > 0)
        assert alpha.get(STATE).json()["communication"]["state"] == before["state"]
        enter(alpha)
        devices[1].mode = "power_cycle"
        assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
        pump(lambda: controller(alpha).halt() is not None)
        state = wait_idle(alpha)
        assert state["halt"] is not None and not state["communication"]["read_enabled"]  # S6
        assert not state["footer"]["resume_enabled"]
        assert alpha.post("/api/v0/acquisition/stop").status_code == 202
        pump(lambda: alpha.takeover() == "released")
        assert alpha.get(STATE).json()["available"] is False  # stopping cleared the page's memory
