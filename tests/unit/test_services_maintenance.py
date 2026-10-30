"""par_app.services.maintenance.resume_gate: one set of resume-blocking conditions (D-110, DEF-12).

Expected values are written by hand from docs/spec/maint.md (MAINT-067, MAINT-068, MAINT-129) and the D-110 ruling:
the maintenance-window set, in its V1.0.2 order (severe hardware stop, a running task, unhandled calibration
changes, then each maintenance session's own check), with the window's wording. Sessions are stand-ins that record
calls and raise ProtocolError on demand; no Qt, no device, no database.
"""

from __future__ import annotations

import pytest

from par_app.models import AppConfig
from par_app.protocol import CommunicationTimeout, ProtocolError
from par_app.services.maintenance import CALIBRATION_DIRTY, TASK_BUSY, ResumeGate, resume_gate

pytestmark = pytest.mark.unit
CONFIG = AppConfig()
HALT = {"message": "采集停止中：东（地址 1）需要重新上电；所有设备的后台采集已停止", "reason": "x"}


class Session:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[AppConfig] = []

    def check_resume(self, config: AppConfig) -> None:
        self.calls.append(config)
        if self.error is not None:
            raise self.error


def gate(**changes: object) -> ResumeGate:
    facts: dict[str, object] = dict(
        maintenance=True, halt=None, task_busy=False, calibration_dirty=False, sessions=[], config=CONFIG
    )
    facts.update(changes)
    return resume_gate(**facts)  # type: ignore[arg-type]


@pytest.mark.spec("MAINT-007 MAINT-067 MAINT-068 MAINT-129")
def test_allowed_only_in_maintenance_with_nothing_blocking() -> None:
    first, second = Session(), Session()
    assert gate(sessions=[first, second]) == ResumeGate(True, "")
    assert first.calls == [CONFIG] and second.calls == [CONFIG]


@pytest.mark.spec("MAINT-068 MAINT-129")
def test_not_in_maintenance_is_refused_without_a_reason_and_checks_nothing() -> None:
    session = Session()
    assert gate(maintenance=False, sessions=[session]) == ResumeGate(False, "")
    assert gate(maintenance=False, halt=HALT, task_busy=True, calibration_dirty=True) == ResumeGate(False, "")
    assert session.calls == []


@pytest.mark.spec("MAINT-068 MAINT-129")
def test_unhandled_calibration_changes_refuse_with_the_window_wording() -> None:
    session = Session()
    assert gate(calibration_dirty=True, sessions=[session]) == ResumeGate(False, "校准修改尚未处理，暂不能恢复采集。")
    assert CALIBRATION_DIRTY == "校准修改尚未处理，暂不能恢复采集。"
    assert session.calls == []


@pytest.mark.spec("MAINT-007 MAINT-067 MAINT-068")
def test_a_running_task_refuses_with_the_window_wording() -> None:
    assert gate(task_busy=True) == ResumeGate(False, "任务尚未结束，暂不能恢复采集。")
    assert TASK_BUSY == "任务尚未结束，暂不能恢复采集。"


@pytest.mark.spec("MAINT-007 MAINT-067")
def test_severe_stop_refuses_with_its_own_message() -> None:
    assert gate(halt=HALT) == ResumeGate(False, HALT["message"])


@pytest.mark.spec("MAINT-007 MAINT-067 MAINT-068")
def test_first_condition_in_window_order_wins() -> None:
    failing = Session(ProtocolError("写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"))
    everything = dict(halt=HALT, task_busy=True, calibration_dirty=True, sessions=[failing])
    assert gate(**everything).reason == HALT["message"]
    assert gate(**dict(everything, halt=None)).reason == TASK_BUSY
    assert gate(**dict(everything, halt=None, task_busy=False)).reason == CALIBRATION_DIRTY
    assert gate(**dict(everything, halt=None, task_busy=False, calibration_dirty=False)) == ResumeGate(
        False, "写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"
    )
    assert len(failing.calls) == 1


@pytest.mark.spec("MAINT-007 MAINT-067")
def test_first_failing_session_gives_the_reason_and_later_sessions_are_not_checked() -> None:
    ok = Session()
    mismatch = Session(ProtocolError("请先在常规设置中手动更新该设备 ID 和总线连接参数，或禁用该设备，再恢复采集"))
    pending = Session(ProtocolError("写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对"))
    result = gate(sessions=[ok, mismatch, pending])
    assert result == ResumeGate(False, "请先在常规设置中手动更新该设备 ID 和总线连接参数，或禁用该设备，再恢复采集")
    assert ok.calls == [CONFIG] and mismatch.calls == [CONFIG] and pending.calls == []


@pytest.mark.spec("MAINT-007 MAINT-067")
def test_protocol_error_subclasses_refuse_and_other_errors_propagate() -> None:
    assert gate(sessions=[Session(CommunicationTimeout("超时"))]) == ResumeGate(False, "超时")
    with pytest.raises(ValueError, match="bug"):
        gate(sessions=[Session(ValueError("bug"))])
