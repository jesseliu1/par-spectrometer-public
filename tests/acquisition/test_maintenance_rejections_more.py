"""Rejection table rows R12-R22 of 17_ 10.4 (R1-R11 and the meta test: test_maintenance_rejections.py)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from par_app.acquisition_host import maintenance_actions as actions
from par_app.acquisition_host import v1_texts as texts
from par_app.application.errors import InvalidArgument
from par_app.database import ParDatabase
from par_app.maintenance import REJOIN_WRITE_BLOCKED_MESSAGE
from par_app.services.maintenance import TASK_BUSY
from tests.acquisition.conftest import Alpha, pump, two_devices, write_config
from tests.acquisition.maintenance_support import (
    STATE,
    Running,
    controller,
    enter,
    error_code,
    fake_port,
    form,
    maintenance_endpoints,
    open_page,
    running_alpha,
    save_registration,
    send,
    wait_idle,
)
from tests.support.fake_bus import wired

pytestmark = pytest.mark.qt
WRITES = (
    "/api/v0/maintenance/enter",
    "/api/v0/maintenance/leave",
    "/api/v0/maintenance/calibration/write",
)


@pytest.fixture
def running(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    yield from running_alpha(alpha, monkeypatch)


@pytest.mark.rejection("R12")
def test_r12_communication_conditions(running: Running) -> None:
    alpha = running.alpha
    running.refused(
        alpha.post("/api/v0/maintenance/comm/read", form()), 409, "precondition_failed", actions.NOT_IN_MAINTENANCE
    )
    enter(alpha)
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/comm/read", form(isolated=False)),
        409,
        "precondition_failed",
        texts.ISOLATION_TEXT,
    )
    running.refused(
        alpha.post("/api/v0/maintenance/comm/write/confirmations", form(new=5)),
        409,
        "precondition_failed",
        actions.COMM_NO_BASELINE,
    )
    running.refused(
        alpha.post("/api/v0/maintenance/comm/verify", form()), 409, "precondition_failed", actions.COMM_NO_PENDING
    )
    running.devices[1].mute_after_move = True
    assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
    wait_idle(alpha)
    assert alpha.confirmed("/api/v0/maintenance/comm/write", form(new=5)).status_code == 200
    state = wait_idle(alpha)  # the automatic verification fails: the write stays pending
    assert state["communication"]["pending"] and state["communication"]["verify_enabled"]
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/comm/read", form()), 409, "precondition_failed", actions.COMM_PENDING
    )
    running.refused(
        alpha.post("/api/v0/maintenance/comm/write/confirmations", form(new=5)),
        409,
        "precondition_failed",
        actions.COMM_PENDING,
    )


@pytest.mark.rejection("R13")
def test_r13_session_checks_fail_the_task_with_their_own_text(running: Running) -> None:
    alpha = running.alpha
    enter(alpha)
    assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
    wait_idle(alpha)
    changed = form(new=5)
    changed["old"] = {**changed["old"], "baudrate": 9600}  # not the parameters the device was read with
    assert alpha.confirmed("/api/v0/maintenance/comm/write", changed).status_code == 200
    state = wait_idle(alpha)
    assert state["communication"]["state"].startswith("操作失败：当前连接参数已变化，或尚未确认只连接目标设备")
    running.devices[1].serial_number = 0x55555555
    assert alpha.confirmed("/api/v0/maintenance/comm/write", form(new=5)).status_code == 200
    state = wait_idle(alpha)
    assert state["communication"]["state"].startswith("操作失败：设备身份与此前读取不一致，禁止写入")
    assert running.devices[1].comm == [1, 3, 0]  # nothing was written
    out_of_range = alpha.post("/api/v0/maintenance/comm/read", form(old=300))
    assert out_of_range.status_code == 400 and error_code(out_of_range) == "invalid_argument"


@pytest.mark.rejection("R14")
def test_r14_unfinished_session_device_gets_no_calibration_task(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling 43/48: a device whose database holds an unfinished (deferred) session is kept out of polling until
    verified, so it is never online and V1.0.3's window offers neither read nor write; nor does the alpha."""
    stored = write_config(alpha.data_dir, two_devices())
    database = ParDatabase(Path(stored.devices[0].database_path))
    verified = {"connection": {"serial_port": "COM7", "slave_id": 1, "baudrate": 19200, "parity": "N"}}
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('communication_maintenance',?,?)",
            (json.dumps({"pending": None, "verified": verified, "deferred": True}), "2026-10-18T00:00:00+08:00"),
        )
    port = fake_port(monkeypatch)
    with wired(port):
        alpha.enable_tier_2()
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(lambda: controller(alpha).snapshot("South").get("online", False))
        open_page(alpha, tab=0)
        case = Running(alpha, port, {}, [])
        case.spy()
        assert controller(alpha).snapshot("North").get("message") == texts_rejoin()
        case.refused(
            alpha.post("/api/v0/maintenance/calibration/read", {}),
            409,
            "precondition_failed",
            actions.CALIBRATION_UNAVAILABLE,
        )
        case.refused(alpha.post("/api/v0/maintenance/calibration/write/confirmations", {}), 409, "precondition_failed")
    assert REJOIN_WRITE_BLOCKED_MESSAGE  # the coordinator's own refusal stays in place behind it (unchanged)


def texts_rejoin() -> str:
    from par_app.maintenance import REJOIN_VERIFICATION_MESSAGE

    return REJOIN_VERIFICATION_MESSAGE


@pytest.mark.rejection("R15")
def test_r15_target_is_locked_while_edits_are_unwritten(running: Running) -> None:
    alpha = running.alpha
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
    wait_idle(alpha)
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y0", "value": 2}).status_code == 200
    running.calls.clear()
    running.refused(
        alpha.put("/api/v0/maintenance/target", {"key": "South"}), 409, "precondition_failed", actions.TARGET_LOCKED
    )


@pytest.mark.rejection("R16")
def test_r16_resume_gate(running: Running) -> None:
    alpha = running.alpha
    leave = "/api/v0/maintenance/leave/confirmations"
    running.refused(alpha.post(leave, {}), 409, "precondition_failed", actions.NOT_IN_MAINTENANCE)
    enter(alpha)
    running.calls.clear()
    controller(alpha).comm.busy = True  # a task in flight (injected)
    running.refused(alpha.post(leave, {}), 409, "precondition_failed", TASK_BUSY)
    controller(alpha).comm.busy = False
    running.devices[1].mute_after_move = True
    assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
    wait_idle(alpha)
    assert alpha.confirmed("/api/v0/maintenance/comm/write", form(new=5)).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    running.refused(
        alpha.post(leave, {}), 409, "precondition_failed", "写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"
    )
    save_registration(alpha, enabled={"North": False})  # D-167 1A: a disabled pending device still blocks
    pump(lambda: not controller(alpha).device("North").enabled)
    running.calls.clear()  # the configuration save (apply_config)
    running.refused(
        alpha.post(leave, {}), 409, "precondition_failed", "写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"
    )
    save_registration(alpha, enabled={"North": True})
    running.devices[5].mode = "ok"
    pump(lambda: controller(alpha).device("North").enabled)
    # each saved registration rebuilt the communication tab as V1.0.3 does (#58, D-224): the tick is gone (D-218)
    running.calls.clear()  # the configuration saves (apply_config)
    verify = alpha.post("/api/v0/maintenance/comm/verify", form(new=5))
    running.refused(verify, 409, "precondition_failed", texts.ISOLATION_TEXT)
    controller(alpha).comm.isolated = True  # stands for #57's fix; the resume gate is the subject here
    assert alpha.post("/api/v0/maintenance/comm/verify", form(new=5)).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    running.refused(
        alpha.post(leave, {}),
        409,
        "precondition_failed",
        "请先在常规设置中手动更新该设备 ID 和总线连接参数，或禁用该设备，再恢复采集",
    )
    save_registration(alpha, enabled={"North": False})  # D-131: a disabled verified device lets resume through
    pump(lambda: controller(alpha).resume_gate().allowed)
    assert alpha.post(leave, {}).status_code == 201


@pytest.mark.rejection("R17")
def test_r17_coordinator_refusal_of_resume_is_shown(running: Running) -> None:
    alpha = running.alpha
    enter(alpha)
    hub = alpha.host.hub
    assert hub is not None
    hub.coordinator.task_finished.emit("", "maintenance_leave", False, "硬件异常停止仍有效，请重新上电并重启软件")
    pump(lambda: controller(alpha).window.notice is not None)
    notice = alpha.get(STATE).json()["notice"]
    assert notice == {"title": "无法恢复采集", "text": "硬件异常停止仍有效，请重新上电并重启软件"}
    assert controller(alpha).maintenance()
    assert alpha.post("/api/v0/maintenance/notice/dismiss").json()["notice"] is None


@pytest.mark.rejection("R18")
def test_r18_enter_fails_when_the_connection_cannot_be_released(running: Running) -> None:
    alpha = running.alpha
    running.port.close_error = "handle busy"
    assert alpha.confirmed("/api/v0/maintenance/enter").status_code == 200
    pump(lambda: not controller(alpha).window.entering)
    state = wait_idle(alpha)
    assert not state["maintenance"]
    assert (
        state["footer"]["result"] == "未进入通信维护，采集连接关闭失败：handle busy" and state["footer"]["result_error"]
    )


@pytest.mark.rejection("R19")
def test_r19_tier_changes(running: Running) -> None:
    alpha = running.alpha
    controller(alpha).window.diagnostics_busy = True  # a task in flight (injected)
    controller(alpha)._changed()
    response = alpha.put("/api/v0/tier", {"tier": 1})
    assert response.status_code == 409 and error_code(response) == "busy"
    controller(alpha).window.diagnostics_busy = False
    controller(alpha)._changed()
    assert alpha.put("/api/v0/tier", {"tier": 1}).status_code == 200
    assert alpha.put("/api/v0/tier", {"tier": 0}).status_code == 202
    pump(lambda: alpha.takeover() == "released")
    response = alpha.post("/api/v0/tier/confirmations", {"tier": 2})
    assert response.status_code == 409 and error_code(response) == "confirmation_required"
    response = alpha.put("/api/v0/tier", {"tier": 2, "confirmation_id": None})
    assert response.status_code == 409 and error_code(response) == "confirmation_required"


@pytest.mark.rejection("R20")
def test_r20_closing_the_page(running: Running) -> None:
    alpha = running.alpha
    controller(alpha).window.diagnostics_busy = True
    running.refused(alpha.delete("/api/v0/maintenance/page"), 409, "busy")
    controller(alpha).window.diagnostics_busy = False
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
    wait_idle(alpha)
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y0", "value": 2}).status_code == 200
    running.calls.clear()  # the tab's own calibration read
    running.refused(alpha.delete("/api/v0/maintenance/page"), 409, "confirmation_required")
    issued = alpha.post("/api/v0/maintenance/page/close/confirmations", {}).json()
    assert issued["text"] == texts.CLOSE_TEXT
    closed = alpha.delete(f"/api/v0/maintenance/page?confirmation_id={issued['confirmation_id']}")
    assert closed.status_code == 200 and not closed.json()["session"] and not closed.json()["calibration"]["dirty"]


@pytest.mark.rejection("R21")
def test_r21_only_whitelisted_tasks_are_ever_queued(running: Running) -> None:
    alpha = running.alpha
    for kind in ("read_identity", "comm_write", "apply_config", "anything"):
        with pytest.raises(InvalidArgument):
            controller(alpha).queue("North", kind)
    paths = alpha.get("/api/v0/openapi.json").json()["paths"]
    assert not [
        path for path in paths if "identity" in path or path.endswith("/comm/write") and "maintenance" not in path
    ]
    assert running.calls == []


@pytest.mark.rejection("R22")
def test_r22_no_endpoint_clears_the_halt(running: Running) -> None:
    alpha = running.alpha
    paths = alpha.get("/api/v0/openapi.json").json()["paths"]
    assert not [p for p in paths if any(word in p for word in ("halt", "latch", "clear", "reset", "unlock"))]
    running.devices[2].mode = "power_cycle"
    pump(lambda: controller(alpha).halt() is not None)
    for path, method in maintenance_endpoints(alpha):
        send(alpha, path, method)
    hub = alpha.host.hub
    assert hub is not None and hub.coordinator.halt_reason() is not None
    assert alpha.get("/api/v0/acquisition/status").json()["halt"] is not None
