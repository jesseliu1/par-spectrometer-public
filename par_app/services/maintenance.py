"""One set of resume-blocking conditions for both "resume acquisition" entries (D-110, DEF-12).

V1.0.2 has two entries that both end in MainWindow.resume_after_maintenance: the settings-page button
(maintenance_resume_action, enabled by MainWindow._refresh_communication_events) and the button in the device
maintenance window (DeviceMaintenanceDialog.update_controls). Their conditions differed: the settings page did not
check "calibration changes not handled" nor a running calibration read/write, so acquisition could be resumed from
there past the maintenance-window check. owner's ruling on D-110 (2026-10-17) keeps both entries and makes both use
the maintenance-window set, which resume_gate below holds, unchanged in order and wording.

Specs: MAINT-067, MAINT-068, MAINT-129. This only decides whether the button may be pressed; leaving maintenance
itself (PollingCoordinator.leave_maintenance / maintenance_leave, check_resume, the hardware latch) is untouched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from par_app.models import AppConfig
from par_app.protocol import ProtocolError

TASK_BUSY = "任务尚未结束，暂不能恢复采集。"
CALIBRATION_DIRTY = "校准修改尚未处理，暂不能恢复采集。"


class ResumeCheck(Protocol):
    """A communication-maintenance session (par_app.maintenance.CommunicationMaintenance)."""

    def check_resume(self, config: AppConfig) -> None: ...


@dataclass(frozen=True)
class ResumeGate:
    allowed: bool
    reason: str  # why resume is refused; "" when allowed or when not in maintenance


def resume_gate(
    *,
    maintenance: bool,
    halt: Mapping[str, object] | None,
    task_busy: bool,
    calibration_dirty: bool,
    sessions: Iterable[ResumeCheck],
    config: AppConfig,
) -> ResumeGate:
    """Whether "退出维护并恢复采集" may be pressed, and why not (first matching condition wins).

    task_busy: a maintenance-window task (diagnostics read, entering maintenance, communication read/write) or a
    calibration read/write is still running. sessions are checked in order; the first ProtocolError is the reason.
    """
    if not maintenance:
        return ResumeGate(False, "")
    if halt is not None:
        return ResumeGate(False, str(halt["message"]))
    if task_busy:
        return ResumeGate(False, TASK_BUSY)
    if calibration_dirty:
        return ResumeGate(False, CALIBRATION_DIRTY)
    try:
        for session in sessions:
            session.check_resume(config)
    except ProtocolError as exc:
        return ResumeGate(False, str(exc))
    return ResumeGate(True, "")
