"""Every rejection condition of tier 2 (17_ 10.4, R1-R22), through the HTTP API on the fake bus.

Each case asserts the HTTP status and error code, the message (V1.0.3's own text where V1.0.3 has one), and that the
coordinator received no task (a spy on queue_task, which enter/leave_maintenance also go through); where the
condition is the coordinator's or the session's own, that the task failed with its text. A meta test checks that
the R numbers of the table and the `rejection` markers below match one to one.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from par_app.acquisition_host import maintenance_actions as actions
from par_app.acquisition_host import v1_texts as texts
from tests.acquisition.conftest import Alpha, pump, two_devices, write_config
from tests.acquisition.maintenance_support import (
    STATE,
    Running,
    controller,
    enter,
    error_code,
    form,
    maintenance_endpoints,
    running_alpha,
    save_registration,
    send,
    switch_between_transactions,
    wait_idle,
)

pytestmark = pytest.mark.qt
ROWS = [f"R{number}" for number in range(1, 23)]
WRITES = (
    "/api/v0/maintenance/enter",
    "/api/v0/maintenance/leave",
    "/api/v0/maintenance/calibration/write",
)


# ------------------------------------------------------------------------------------------------------- tier
@pytest.mark.rejection("R1")
def test_r1_tier_0_and_1_refuse_every_maintenance_endpoint(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    for raise_to_1 in (False, True):
        if raise_to_1:
            alpha.enable_tier_1()
        for path, method in maintenance_endpoints(alpha):
            response = send(alpha, path, method)
            assert response.status_code == 403 and error_code(response) == "feature_disabled", (path, method)


@pytest.fixture
def running(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    yield from running_alpha(alpha, monkeypatch)


@pytest.mark.rejection("R2")
def test_r2_tier_2_needs_a_running_takeover(alpha: Alpha) -> None:
    write_config(alpha.data_dir, two_devices())
    alpha.enable_tier_2()
    response = alpha.post("/api/v0/maintenance/page", {"tab": 0})
    assert response.status_code == 409 and error_code(response) == "not_running"
    cache = alpha.context.acquisition.cache
    for state in ("starting", "stopping"):
        cache.set_takeover(state, False)  # type: ignore[arg-type]
        response = alpha.post("/api/v0/maintenance/page", {"tab": 0})
        assert response.status_code == 409 and error_code(response) == "busy", state
    cache.set_takeover("released", False)
    alpha.context.acquisition.closing = True
    response = alpha.post("/api/v0/maintenance/page", {"tab": 0})
    assert response.status_code == 409 and error_code(response) == "busy"


@pytest.mark.rejection("R3")
def test_r3_page_session(running: Running) -> None:
    alpha = running.alpha
    second = alpha.post("/api/v0/maintenance/page", {"tab": 0})
    running.refused(second, 409, "busy")
    assert alpha.delete("/api/v0/maintenance/page").status_code == 200
    for path in ("/api/v0/maintenance/diagnostics/read", "/api/v0/maintenance/enter/confirmations"):
        running.refused(alpha.post(path, {}), 409, "no_session")


@pytest.mark.rejection("R4")
def test_r4_one_maintenance_task_at_a_time(running: Running) -> None:
    alpha = running.alpha
    running.port.hold_when = lambda frame: frame[1] == 4 and frame[2:4] == b"\x07\xd6"  # diagnostics block
    held = {"done": False}
    running.port.release = lambda: held["done"]
    assert alpha.post("/api/v0/maintenance/diagnostics/read").status_code == 200
    pump(running.port.held.is_set)
    running.calls.clear()
    for path, body in (
        ("/api/v0/maintenance/diagnostics/read", {}),
        ("/api/v0/maintenance/enter/confirmations", {}),
        ("/api/v0/maintenance/calibration/read", {}),
    ):
        running.refused(alpha.post(path, body), 409, "busy")
    running.refused(alpha.put("/api/v0/maintenance/target", {"key": "South"}), 409, "precondition_failed")
    held["done"] = True
    wait_idle(alpha)


@pytest.mark.rejection("R5")
def test_r5_halt_refuses_every_device_operation(running: Running) -> None:
    alpha = running.alpha
    running.devices[2].mode = "power_cycle"
    pump(lambda: controller(alpha).halt() is not None)
    message = controller(alpha).halt()["message"]  # type: ignore[index]
    running.calls.clear()
    for path in (
        "/api/v0/maintenance/diagnostics/read",
        "/api/v0/maintenance/calibration/read",
        "/api/v0/maintenance/enter/confirmations",
        "/api/v0/maintenance/leave/confirmations",
    ):
        running.refused(alpha.post(path, {}), 409, "halted", message)
    state = alpha.get(STATE).json()
    assert state["header"]["state"] == message and state["communication"]["state"] == message  # MAINT-059


# ------------------------------------------------------------------------------------- V1.0.3 window conditions
@pytest.mark.rejection("R6")
def test_r6_diagnostics_conditions(running: Running) -> None:
    alpha = running.alpha
    save_registration(alpha, enabled={"South": False})
    pump(lambda: not controller(alpha).device("South").enabled)
    assert alpha.put("/api/v0/maintenance/target", {"key": "South"}).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/diagnostics/read"), 409, "precondition_failed", texts.READ_UNREGISTERED
    )
    assert alpha.put("/api/v0/maintenance/target", {"key": "North"}).status_code == 200
    wait_idle(alpha)
    enter(alpha)
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/diagnostics/read"), 409, "precondition_failed", texts.READ_IN_MAINTENANCE
    )


@pytest.mark.rejection("R7")
def test_r7_calibration_needs_an_online_healthy_device(running: Running) -> None:
    alpha = running.alpha
    switch_between_transactions(running.port, running.devices, 1, "silent", other=2)
    pump(lambda: controller(alpha).faulty("North"))
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/calibration/read", {}),
        409,
        "precondition_failed",
        actions.CALIBRATION_UNAVAILABLE,
    )
    switch_between_transactions(running.port, running.devices, 1, "ok", other=2)
    pump(lambda: not controller(alpha).faulty("North"))
    enter(alpha)
    running.calls.clear()
    running.refused(alpha.post("/api/v0/maintenance/calibration/read", {}), 409, "precondition_failed")


@pytest.mark.rejection("R8")
def test_r8_calibration_write_needs_this_devices_valid_readback(running: Running) -> None:
    alpha = running.alpha
    confirm = "/api/v0/maintenance/calibration/write/confirmations"
    running.refused(alpha.post(confirm, {}), 409, "precondition_failed", texts.NOT_READ_TEXT)
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "x1", "value": 700}).status_code == 200
    running.refused(alpha.post(confirm, {}), 409, "precondition_failed", texts.INVALID_TEXT)
    assert alpha.post("/api/v0/maintenance/calibration/discard").status_code == 200
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "limit_min", "value": 25}).status_code == 200
    running.refused(alpha.post(confirm, {}), 409, "precondition_failed", texts.INVALID_TEXT)
    assert alpha.post("/api/v0/maintenance/calibration/discard").status_code == 200
    # another device's readback: changing the target forgets it
    assert alpha.put("/api/v0/maintenance/target", {"key": "South"}).status_code == 200
    wait_idle(alpha)
    controller(alpha).draft.device_key = "North"
    running.calls.clear()
    running.refused(alpha.post(confirm, {}), 409, "precondition_failed", texts.NOT_READ_TEXT)
    # an invalid readback (node wavelengths out of order) is not applied and allows no write (MAINT-101)
    running.devices[2].calibration[2] = 900.0
    assert alpha.post("/api/v0/maintenance/calibration/read", {}).status_code == 200
    state = wait_idle(alpha)
    assert state["calibration"]["note"] == texts.CALIBRATION_INVALID_NOTE
    running.calls.clear()
    running.refused(alpha.post(confirm, {}), 409, "precondition_failed", texts.NOT_READ_TEXT)


@pytest.mark.rejection("R9")
def test_r9_reread_over_unwritten_edits_needs_a_confirmation(running: Running) -> None:
    alpha = running.alpha
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
    wait_idle(alpha)
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y0", "value": 2}).status_code == 200
    running.calls.clear()
    running.refused(alpha.post("/api/v0/maintenance/calibration/read", {}), 409, "confirmation_required")
    issued = alpha.post("/api/v0/maintenance/calibration/read/confirmations", {}).json()
    assert issued["text"] == texts.REREAD_TEXT
    reread = alpha.post("/api/v0/maintenance/calibration/read", {"confirmation_id": issued["confirmation_id"]})
    assert reread.status_code == 200 and running.calls == ["calibration_read"]
    wait_idle(alpha)


@pytest.mark.rejection("R10")
def test_r10_write_confirmations_are_bound_and_single_use(running: Running) -> None:
    alpha = running.alpha
    enter_path = "/api/v0/maintenance/enter"
    running.refused(alpha.post(enter_path, {}), 409, "confirmation_required")
    running.refused(alpha.post(enter_path, {"confirmation_id": "made-up"}), 409, "confirmation_required")
    issued = alpha.post(f"{enter_path}/confirmations", {}).json()
    alpha.clock.advance(61.0)
    running.refused(
        alpha.post(enter_path, {"confirmation_id": issued["confirmation_id"]}), 409, "confirmation_required"
    )
    issued = alpha.post(f"{enter_path}/confirmations", {}).json()
    other = alpha.post("/api/v0/maintenance/calibration/read", {"confirmation_id": issued["confirmation_id"]})
    assert other.status_code == 200  # a read needs no confirmation; the id is simply not used
    wait_idle(alpha)
    running.calls.clear()
    issued = alpha.post(f"{enter_path}/confirmations", {}).json()
    wrong_kind = alpha.post("/api/v0/maintenance/leave", {"confirmation_id": issued["confirmation_id"]})
    assert wrong_kind.status_code == 409  # not in maintenance: resume_gate refuses before the id is looked at
    issued = alpha.post(f"{enter_path}/confirmations", {}).json()
    assert alpha.put("/api/v0/maintenance/target", {"key": "South"}).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    running.refused(
        alpha.post(enter_path, {"confirmation_id": issued["confirmation_id"]}),
        409,
        "confirmation_required",
        "确认的内容与本次请求不一致（操作、设备、参数或校准草稿已变化），请重新确认",
    )
    issued = alpha.post(f"{enter_path}/confirmations", {}).json()
    assert alpha.post(enter_path, {"confirmation_id": issued["confirmation_id"]}).status_code == 200
    pump(lambda: controller(alpha).maintenance())
    wait_idle(alpha)
    running.calls.clear()
    reused = alpha.post(enter_path, {"confirmation_id": issued["confirmation_id"]})
    assert reused.status_code == 409
    _r10_body_and_draft_are_bound(running)


def _r10_body_and_draft_are_bound(running: Running) -> None:
    alpha = running.alpha
    leave = alpha.post("/api/v0/maintenance/leave/confirmations", {}).json()
    # body bound: a communication write confirmed for one address cannot write another
    assert alpha.post("/api/v0/maintenance/comm/read", form(old=2)).status_code == 200
    wait_idle(alpha)
    running.calls.clear()
    confirmation = alpha.post("/api/v0/maintenance/comm/write/confirmations", form(old=2, new=5)).json()
    running.refused(
        alpha.post(
            "/api/v0/maintenance/comm/write", {**form(old=2, new=6), "confirmation_id": confirmation["confirmation_id"]}
        ),
        409,
        "confirmation_required",
    )
    # draft version bound: a calibration write confirmed before an edit cannot write the edited draft
    used = alpha.post("/api/v0/maintenance/leave", {"confirmation_id": leave["confirmation_id"]})
    assert used.status_code == 200
    pump(lambda: not controller(alpha).maintenance())
    pump(lambda: controller(alpha).snapshot("South").get("online", False))
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200  # reads by itself
    assert wait_idle(alpha)["calibration"]["write_enabled"]
    issued = alpha.post("/api/v0/maintenance/calibration/write/confirmations", {}).json()
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y0", "value": 3}).status_code == 200
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/calibration/write", {"confirmation_id": issued["confirmation_id"]}),
        409,
        "confirmation_required",
    )


@pytest.mark.rejection("R11")
def test_r11_enter_conditions(running: Running) -> None:
    alpha = running.alpha
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
    wait_idle(alpha)
    assert alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y0", "value": 2}).status_code == 200
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/enter/confirmations", {}), 409, "precondition_failed", actions.ENTER_DIRTY
    )
    assert alpha.post("/api/v0/maintenance/calibration/discard").status_code == 200
    enter(alpha)
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/enter/confirmations", {}),
        409,
        "precondition_failed",
        actions.ENTER_IN_MAINTENANCE,
    )


# ----------------------------------------------------------------------------------------------------- meta
def test_every_rejection_row_has_exactly_one_test() -> None:
    marked = []
    files = (Path(__file__), Path(__file__).with_name("test_maintenance_rejections_more.py"))
    for node in (node for file in files for node in ast.parse(file.read_text(encoding="utf-8")).body):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "rejection"
                ):
                    marked.append(decorator.args[0].value)  # type: ignore[attr-defined]
    assert sorted(marked, key=lambda r: int(r[1:])) == ROWS
    design = (Path(__file__).resolve().parents[2] / "docs" / "process" / "17_alpha_2级维护设计.md").read_text(
        encoding="utf-8"
    )
    assert [row for row in ROWS if f"| {row} |" not in design] == []
