"""In-memory state of the maintenance page, as V1.0.3's windows keep it (17_ 3.4). Plain data, no Qt.

WindowState: DeviceMaintenanceDialog (target, diagnostics busy, entering, snapshots and failures per database, the
bottom result) plus MainWindow's calibration task flag and its "无法恢复采集" message box. CommTab: the embedded
MaintenanceDialog of the target (busy, the operation-result and verification flags, the state line and the identity
summary). SettingsComm: MainWindow's "通信参数当前值" for one device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import v1_texts as texts


@dataclass
class WindowState:
    target: str = ""
    diagnostics_busy: bool = False
    entering: bool = False
    calibration_task: str | None = None
    """"calibration_read" / "calibration_write" while one is in flight (MainWindow._calibration_busy/_task)."""
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    result: str = ""
    result_error: bool = False
    exported_file: str | None = None
    exporting: bool = False
    """A diagnostics export is being written on the worker thread (D-219, review M2)."""
    calibration_state: str = ""
    """MainWindow.calibration_value_state ("" hidden, 待写入修改, 回读未确认, 回读参数无效)."""
    calibration_state_error: bool = False
    calibration_note: str = texts.CALIBRATION_NOT_READ
    calibration_note_error: bool = False
    calibration_status: dict[str, str] = field(default_factory=dict)
    calibration_history: bool = False
    """D-157 (DEF-23): the last whole read failed; the values shown are the previous ones."""
    notice: dict[str, str] | None = None
    """A message box V1.0.3 would show ("无法恢复采集"), until the page closes it."""

    def set_result(self, text: str, error: bool = False) -> None:
        self.result, self.result_error, self.exported_file = text, error, None


@dataclass
class CommTab:
    busy: bool = False
    task: str | None = None
    operation_result: bool = False
    verification_passed: bool = False
    state: str = texts.STATE_NOT_ENTERED
    attention: bool = False
    identity: list[str] = field(default_factory=lambda: [texts.IDENTITY_NOT_READ])
    isolated: bool = False
    """MaintenanceDialog.isolated as this window holds it: ticked by a read or write sent from it. A pending write
    disables the box with its tick kept, so a verification checks this, not the request (D-218 question 1 = V1.0.3;
    a reopened window starts empty and cannot verify by hand, #57)."""

    def set_state(self, text: str, attention: bool = False) -> None:
        self.state, self.attention = text, attention

    def mode_changed(self, active: bool) -> None:
        """MaintenanceDialog.mode_changed."""
        self.operation_result = False
        if not active:
            self.verification_passed = False
        if active:
            self.set_state(texts.STATE_MAINTENANCE, attention=True)
        else:
            self.set_state(texts.STATE_LEFT)

    @property
    def identity_text(self) -> str:
        """MaintenanceDialog._identity_text (the plain lines, used in the write confirmation)."""
        return "\n".join(self.identity)


@dataclass
class SettingsComm:
    status: str = texts.COMM_STATES["unread"]
    error: bool = False
    readback: tuple[int, int, int] | None = None
    tooltip: str = ""
    pending: bool = False
    stale: bool = False
    """`readback` is the last valid value, not confirmed by the latest request (R-1-5; D-219, review M3)."""

    def show(self, status: str, error: bool, readback: tuple[int, int, int] | None = None, tooltip: str = "") -> None:
        self.status, self.error, self.tooltip = status, error, tooltip
        if readback is not None:
            self.readback = readback
