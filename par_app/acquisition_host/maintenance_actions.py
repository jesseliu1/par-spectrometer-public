"""The maintenance page's actions and the controller's reactions to finished tasks (17_ sections 4 and 5).

Each action is what one V1.0.3 button does, with V1.0.3's window conditions checked first (17_ 1.3) and, for a
write, the confirmation id the service issued with V1.0.3's dialog text (17_ 6.2); then exactly the task V1.0.3
queues, with the same payload. `task_finished` is MainWindow._device_task_finished, DeviceMaintenanceDialog.
task_finished and MaintenanceDialog.task_finished in that order (their connection order in V1.0.3), including the
automatic verification after a write (MAINT-005, 058).
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..application.errors import Busy, InvalidArgument
from ..application.maintenance import Halted, PreconditionFailed
from ..domain.clock import BEIJING_TZ
from ..maintenance import BAUDRATES, PARITIES
from ..services import calibration as calibration_service
from . import maintenance_page as page
from . import v1_texts as texts
from .maintenance_view import EVENT_LIMIT, identity_lines, snapshot_entry

if TYPE_CHECKING:
    from ..database import ParDatabase
    from .maintenance_host import MaintenanceController

Action = Callable[["MaintenanceController", Mapping[str, Any], "str | None"], None]
Confirmation = Callable[["MaintenanceController", Mapping[str, Any]], tuple[str, str, int]]
MAX_SLAVE_ID = 247
"""MaintenanceDialog._fields: address.setRange(1, 247)."""
SAFE_NAME = re.compile(r"[^\w.-]+")

CALIBRATION_UNAVAILABLE = "当前维护设备不能读取或编辑校准：须为已启用、已配置、在线且无故障的设备，且不在维护或锁停中"
CALIBRATION_NOT_EDITABLE = "请先读取当前设备校准参数，再编辑"
ENTER_IN_MAINTENANCE = "已处于通信维护中"
ENTER_DIRTY = "校准修改尚未处理（写入或放弃后）才能进入通信维护"
NOT_IN_MAINTENANCE = "未处于通信维护中"
COMM_PENDING = "已有待核对的写入，请先使用新参数核对"
COMM_NO_BASELINE = "请先读取并确认目标设备"
COMM_NO_PENDING = "没有待核对的通信参数写入"
TARGET_LOCKED = "维护目标已锁定：任务进行中、校准修改未处理或有待核对的通信参数写入时不能更换设备"
DRAFT_VOIDED = "设备登记或通信配置已变更，原校准草稿和确认已作废；请重新读取当前设备校准参数"
IDENTITY_CHANGED = "设备登记或通信配置已与读取校准时不同，本次未写入；请重新读取当前设备校准参数后再写入"
"""D-219 (review of PR #55, B1): not V1.0.3 texts; V1.0.3 has no such check."""


# ------------------------------------------------------------------------------- shared steps
def page_changed(c: MaintenanceController, index: int) -> None:
    """DeviceMaintenanceDialog.page_changed: the result line clears; diagnostics and calibration read themselves."""
    c.tab = index
    c.window.set_result("")
    if index == 0:
        refresh_diagnostics(c, explicit=False)
    elif index == 1 and not c.draft.dirty and not c.calibration_busy():
        read_calibration(c, None, explicit=False)


def reset_calibration(c: MaintenanceController) -> None:
    """MainWindow._reset_calibration."""
    c.draft.reset()
    window = c.window
    window.calibration_state, window.calibration_state_error = "", False
    window.calibration_note, window.calibration_note_error = texts.CALIBRATION_NOT_READ, False
    window.calibration_status = {}
    window.calibration_history = False


def discard(c: MaintenanceController) -> None:
    """MainWindow.discard_calibration."""
    if c.calibration_busy():
        return
    if c.draft.baseline is not None:
        c.draft.discard()
        c.window.calibration_state, c.window.calibration_note = "", ""


def _ready(c: MaintenanceController) -> None:
    c.ready()


# ------------------------------------------------------------------------------- diagnostics
def refresh_diagnostics(c: MaintenanceController, explicit: bool = True) -> None:
    """DeviceMaintenanceDialog.refresh_diagnostics (G1)."""
    reason = c.diagnostics_reason()
    if reason:
        if not explicit:
            return
        halt = c.halt()
        if halt:
            raise Halted(str(halt["message"]))
        if not c.idle():
            raise Busy(texts.READ_BUSY)
        raise PreconditionFailed(reason)
    c.window.diagnostics_busy = True
    c.window.set_result("")
    c.queue(c.window.target, "diagnostics_read")


def _diagnostics(c: MaintenanceController, _body: Mapping[str, Any], _confirmation: str | None) -> None:
    _ready(c)
    refresh_diagnostics(c)


def _export(c: MaintenanceController, _body: Mapping[str, Any], _confirmation: str | None) -> None:
    """DeviceMaintenanceDialog.export_diagnostics, written to the alpha's exports folder (D-216 question 11). The
    page's state is taken here; the database query and the file are done on the worker thread (D-219, review M2)."""
    c.require_session()
    if not c.idle() or c.window.exporting:
        raise Busy(texts.READ_BUSY)
    key = c.window.target
    device, path = c.device(key), c.database_path(key)
    if device is None or path is None or c.hub is None:
        raise PreconditionFailed(texts.UNREGISTERED)
    database = c.hub.database_for(key)
    assert database is not None
    snapshot = c.window.snapshots.get(str(path))
    now = c.clock.now()
    data = {
        "device_name": device.name,
        "slave_id": device.slave_id,
        "database": str(path),
        "report_kind": "diagnostic_snapshot" if snapshot else "software_events_only",
        "exported_at": now.astimezone(BEIJING_TZ).isoformat(timespec="seconds"),
        "snapshot": snapshot,
        "last_read_error": c.window.failures.get(str(path)),
        "runtime": c.snapshot(key),
    }
    name = f"{SAFE_NAME.sub('_', device.name)}_{now:%Y%m%d-%H%M%S}_{texts.EXPORT_FILE_NAME}"
    target = c.exports / name
    window = c.window
    window.exporting = True

    def done(future: Future[object]) -> None:
        window.exporting = False
        try:
            future.result()
        except (OSError, sqlite3.Error) as error:  # D-158: shown in the result line, kept until the next operation
            window.set_result(f"{texts.EXPORT_FAILED_TITLE}：{error}", error=True)
        else:
            window.set_result(texts.EXPORTED_SNAPSHOT if snapshot else texts.EXPORTED_EVENTS)
            window.exported_file = str(target)
        c.published()

    c.worker.execute(lambda: _write_export(database, data, target), done)


def _write_export(database: ParDatabase, data: dict[str, Any], target: Path) -> None:
    """On the worker thread: the software events, then the file (the same content as before D-219)."""
    data["software_events"] = database.recent_diagnostics(EVENT_LIMIT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ------------------------------------------------------------------------------- calibration
def read_calibration(c: MaintenanceController, confirmation: str | None, explicit: bool = True) -> None:
    """MainWindow.read_calibration (G2, G4: unwritten edits are only overwritten after a confirmation)."""
    if not (c.calibration_available() and c.idle()):
        if explicit:
            raise PreconditionFailed(CALIBRATION_UNAVAILABLE)
        return
    if c.draft.dirty:
        if not explicit:
            return
        c.check(confirmation, "calibration_reread", {}, c.draft.version)
    c.window.calibration_task = "calibration_read"
    c.window.calibration_note, c.window.calibration_note_error = "", False
    c.queue(c.window.target, "calibration_read")


def _calibration_read(c: MaintenanceController, _body: Mapping[str, Any], confirmation: str | None) -> None:
    _ready(c)
    read_calibration(c, confirmation)


def _number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise InvalidArgument(f"{what}须为有限数值")
    return float(value)


def _calibration_edit(c: MaintenanceController, body: Mapping[str, Any], _confirmation: str | None) -> None:
    """A box edited (`field`, `value` as shown) or a preview node dragged (`node`, `x`, `y`; MAINT-038)."""
    _ready(c)
    if not c.calibration_available():
        raise PreconditionFailed(CALIBRATION_UNAVAILABLE)
    if c.draft.device_key != c.window.target:
        raise PreconditionFailed(CALIBRATION_NOT_EDITABLE)
    if "node" in body:
        index = body["node"]
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(calibration_service.NODE_FIELDS)
        ):
            raise InvalidArgument("节点序号须为 0–4")
        if c.calibration_preview() is None:
            raise PreconditionFailed(texts.CALIBRATION_OUT_OF_ORDER)
        c.draft.drag(index, _number(body.get("x"), "波长"), _number(body.get("y"), "修正值"))
    else:
        name = body.get("field")
        if name not in calibration_service.CALIBRATION_FIELDS:
            raise InvalidArgument("未知的校准字段")
        value = _number(body.get("value"), str(name))
        limit = calibration_service.FIELD_LIMIT * calibration_service.field_scale(str(name))
        if not -limit <= value <= limit:
            raise InvalidArgument(f"{name} 须在 {-limit:g} 到 {limit:g} 之间")
        if not c.draft.edit(str(name), value):
            return
    dirty = c.draft.dirty  # MainWindow._refresh_calibration_plots
    c.window.calibration_state = texts.CALIBRATION_PENDING if dirty else ""
    c.window.calibration_state_error = dirty


def _calibration_discard(c: MaintenanceController, _body: Mapping[str, Any], _confirmation: str | None) -> None:
    c.require_session()
    if c.calibration_busy() or not c.idle():
        raise Busy(texts.READ_BUSY)
    discard(c)


def _calibration_write_check(c: MaintenanceController) -> None:
    """MainWindow.write_calibration's checks (G2, G3)."""
    _ready(c)
    if not c.calibration_available():
        raise PreconditionFailed(CALIBRATION_UNAVAILABLE)
    if c.draft.device_key != c.window.target:
        raise PreconditionFailed(texts.NOT_READ_TEXT)
    if not calibration_service.is_writable(c.draft.values):
        raise PreconditionFailed(texts.INVALID_TEXT)
    if c.draft.identity is None or c.draft.identity != c.identity(c.window.target):
        raise PreconditionFailed(IDENTITY_CHANGED)  # D-219 (B1): the target is not the device that was read


def _calibration_write_confirmation(c: MaintenanceController, _body: Mapping[str, Any]) -> tuple[str, str, int]:
    _calibration_write_check(c)
    device = c.device(c.window.target)
    changes = calibration_service.change_lines(c.draft.baseline, c.draft.values)
    text = texts.CALIBRATION_WRITE_TEXT.format(name=device.name, slave_id=device.slave_id, changes=changes)
    return texts.CALIBRATION_WRITE_TITLE, text, c.draft.version


def _calibration_write(c: MaintenanceController, body: Mapping[str, Any], confirmation: str | None) -> None:
    _calibration_write_check(c)
    c.check(confirmation, "calibration_write", body, c.draft.version)
    c.window.calibration_task = "calibration_write"
    c.queue(c.window.target, "calibration_write", dict(c.draft.values))


def _reread_confirmation(c: MaintenanceController, _body: Mapping[str, Any]) -> tuple[str, str, int]:
    _ready(c)
    if not (c.calibration_available() and c.idle()):
        raise PreconditionFailed(CALIBRATION_UNAVAILABLE)
    return texts.DISCARD_TITLE, texts.REREAD_TEXT, c.draft.version


def _close_confirmation(c: MaintenanceController, _body: Mapping[str, Any]) -> tuple[str, str, int]:
    c.require_session()
    if not c.idle():
        raise Busy(texts.READ_BUSY)
    return texts.DISCARD_TITLE, texts.CLOSE_TEXT, c.draft.version


# ------------------------------------------------------------------------------- communication maintenance
def _enter_check(c: MaintenanceController) -> None:
    """DeviceMaintenanceDialog.update_controls: the enter button (G5)."""
    _ready(c)
    if c.maintenance():
        raise PreconditionFailed(ENTER_IN_MAINTENANCE)
    if c.draft.dirty:
        raise PreconditionFailed(ENTER_DIRTY)
    reason = c.diagnostics_reason()
    if reason:
        raise PreconditionFailed(reason)


def _enter_confirmation(c: MaintenanceController, _body: Mapping[str, Any]) -> tuple[str, str, int]:
    _enter_check(c)
    return texts.ENTER_TITLE, texts.ENTER_TEXT, 0


def _enter(c: MaintenanceController, body: Mapping[str, Any], confirmation: str | None) -> None:
    """DeviceMaintenanceDialog.enter_communication."""
    _enter_check(c)
    c.check(confirmation, "enter", body)
    c.window.entering = True
    c.enter()


def comm_payload(body: Mapping[str, Any]) -> dict[str, Any]:
    """MaintenanceDialog.values for both field groups, keys in V1.0.3's order (17_ 3.3)."""
    port = body.get("serial_port")
    if not isinstance(port, str):
        raise InvalidArgument("电脑串口须为文字")

    def values(name: str) -> dict[str, Any]:
        fields = body.get(name)
        if not isinstance(fields, Mapping):
            raise InvalidArgument(f"缺少 {name} 参数")
        slave_id, baudrate, parity = fields.get("slave_id"), fields.get("baudrate"), fields.get("parity")
        if not isinstance(slave_id, int) or isinstance(slave_id, bool) or not 1 <= slave_id <= MAX_SLAVE_ID:
            raise InvalidArgument(f"从站 ID 须在 1–{MAX_SLAVE_ID} 之间")
        if baudrate not in BAUDRATES or parity not in PARITIES:
            raise InvalidArgument("波特率或奇偶校验不在可选项中")
        return {
            "transport": "rtu",
            "serial_port": port.strip(),
            "slave_id": slave_id,
            "baudrate": baudrate,
            "parity": parity,
        }

    return {"connection": values("old"), "new": values("new"), "isolated": body.get("isolated") is True}


def _comm_check(c: MaintenanceController, kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """MaintenanceDialog.update_controls and submit (G6)."""
    _ready(c)
    if not c.maintenance():
        raise PreconditionFailed(NOT_IN_MAINTENANCE)
    session = c.session_of(c.window.target)
    pending = session.pending if session else None
    if kind == "maintenance_read" and pending:
        raise PreconditionFailed(COMM_PENDING)
    if kind == "maintenance_write" and pending:
        raise PreconditionFailed(COMM_PENDING)
    if kind == "maintenance_write" and not (session and session.baseline):
        raise PreconditionFailed(COMM_NO_BASELINE)
    if kind == "maintenance_verify" and not pending:
        raise PreconditionFailed(COMM_NO_PENDING)
    payload = comm_payload(body)
    if pending:  # the box is disabled: its kept tick counts, not the request (D-218 question 1)
        payload["isolated"] = c.comm.isolated
    if not payload["isolated"]:
        raise PreconditionFailed(texts.ISOLATION_TEXT)
    return payload


def _submit(c: MaintenanceController, kind: str, payload: dict[str, Any]) -> None:
    tab = c.comm
    tab.isolated = True  # only a ticked box gets here
    tab.busy, tab.task = True, kind
    tab.operation_result = tab.verification_passed = False
    tab.set_state(texts.SUBMIT_TEXTS.get(kind, texts.SUBMIT_OTHER), attention=True)
    c.queue(c.window.target, kind, payload)


def _comm(kind: str) -> Action:
    def run(c: MaintenanceController, body: Mapping[str, Any], confirmation: str | None) -> None:
        payload = _comm_check(c, kind, body)
        if kind == "maintenance_write":
            c.check(confirmation, "comm_write", body)
        _submit(c, kind, payload)

    return run


def _comm_write_confirmation(c: MaintenanceController, body: Mapping[str, Any]) -> tuple[str, str, int]:
    payload = _comm_check(c, "maintenance_write", body)
    device = c.device(c.window.target)
    target = texts.TARGET_TEXT.format(name=device.name, slave_id=device.slave_id)
    text = texts.COMM_WRITE_TEXT.format(
        target=target, identity=c.comm.identity_text, new=json.dumps(payload["new"], ensure_ascii=False)
    )
    return texts.COMM_WRITE_TITLE, text, 0


def _leave_check(c: MaintenanceController) -> None:
    """MainWindow.resume_after_maintenance; both entries (maintenance page, settings page) use resume_gate (G8)."""
    c.parts()
    halt = c.halt()
    if halt:
        raise Halted(str(halt["message"]))
    gate = c.resume_gate()
    if not gate.allowed:
        raise PreconditionFailed(gate.reason or NOT_IN_MAINTENANCE)


def _leave_confirmation(c: MaintenanceController, _body: Mapping[str, Any]) -> tuple[str, str, int]:
    _leave_check(c)
    return texts.RESUME_TITLE, texts.RESUME_TEXT, 0


def _leave(c: MaintenanceController, body: Mapping[str, Any], confirmation: str | None) -> None:
    _leave_check(c)
    c.check(confirmation, "leave", body)
    c.leave()


# ------------------------------------------------------------------------------- page
def _tab(c: MaintenanceController, body: Mapping[str, Any], _confirmation: str | None) -> None:
    c.require_session()
    index = body.get("tab")
    if index not in (0, 1, 2):
        raise InvalidArgument("页签须为 0、1 或 2")
    page_changed(c, int(index))


def _target(c: MaintenanceController, body: Mapping[str, Any], _confirmation: str | None) -> None:
    """DeviceMaintenanceDialog.change_device (G7)."""
    hub, _ = c.require_session()
    key = body.get("key")
    if key not in hub.keys():
        raise InvalidArgument(texts.UNREGISTERED)
    if key == c.window.target:
        return
    if c.locked():
        raise PreconditionFailed(TARGET_LOCKED)
    c.window.target = str(key)
    c.window.set_result("")
    reset_calibration(c)
    c.comm = page.fresh_comm(c)
    page_changed(c, c.tab)


def _dismiss(c: MaintenanceController, _body: Mapping[str, Any], _confirmation: str | None) -> None:
    c.window.notice = None


# ------------------------------------------------------------------------------- finished tasks
def task_finished(c: MaintenanceController, key: str, kind: str, ok: bool, payload: object) -> None:
    _main_window(c, key, kind, ok, payload)
    window = c.window
    if kind == "maintenance_enter" and not ok:  # MAINT-107 / D-162: not entered, the reason stays shown
        window.entering = False
        window.set_result(texts.NOT_ENTERED.format(reason=payload), error=True)
    if key == window.target and kind == "diagnostics_read":
        window.diagnostics_busy = False
        path = str(c.database_path(key))
        if ok and isinstance(payload, dict):
            window.snapshots[path] = snapshot_entry(payload, window.snapshots.get(path), c.clock.now())
            window.failures.pop(path, None)
            window.set_result("")
        else:
            window.failures[path] = str(payload)
            window.set_result(texts.READ_FAILED.format(reason=payload), error=True)
    if key == window.target and kind.startswith("maintenance_"):
        _communication_finished(c, key, kind, ok, payload)


def _main_window(c: MaintenanceController, key: str, kind: str, ok: bool, payload: object) -> None:
    """MainWindow._device_task_finished (settings page values, the resume message box, the calibration)."""
    window = c.window
    if kind == "comm_read":
        watch = c.settings.get(key)
        if watch is not None:
            watch.pending = False
            c.settings_accept(key, ok, payload)
    elif kind.startswith("maintenance_"):
        watch = c.settings.get(key)
        if watch is not None and kind in ("maintenance_read", "maintenance_verify"):
            c.settings_accept(key, ok, payload.get("parameters") if ok and isinstance(payload, dict) else payload)
        elif watch is not None and kind == "maintenance_write":
            watch.readback, watch.stale = None, False  # the device has new parameters: the old values are not it
            watch.show(texts.COMM_STATES["verifying" if ok else "unverified"], not ok)
        if kind == "maintenance_leave" and not ok:
            window.notice = {"title": texts.RESUME_FAILED_TITLE, "text": str(payload)}
    elif kind.startswith("calibration") and key == window.target:
        window.calibration_task = None
        if not ok:
            c.draft.device_key = None
            window.calibration_state, window.calibration_state_error = texts.CALIBRATION_UNCONFIRMED, True
            window.calibration_note = texts.CALIBRATION_FAILED.format(reason=payload)
            window.calibration_note_error = True
            window.calibration_history = kind == "calibration_read" and c.draft.shown  # D-157
        elif isinstance(payload, dict):
            _calibration_applied(c, payload)


def _calibration_applied(c: MaintenanceController, payload: Mapping[str, Any]) -> None:
    """MainWindow._task_finished for a calibration readback."""
    window = c.window
    if c.draft.apply_readback(payload):
        c.draft.accepted(window.target, c.identity(window.target))
        window.calibration_state, window.calibration_state_error = "", False
        window.calibration_note, window.calibration_note_error = "", False
        window.calibration_history = False
    else:
        c.draft.device_key = None
        window.calibration_state, window.calibration_state_error = texts.CALIBRATION_INVALID_STATE, True
        window.calibration_note, window.calibration_note_error = texts.CALIBRATION_INVALID_NOTE, True
    status = calibration_service.status_texts(payload.get("_mcu_status", {}), BEIJING_TZ)
    window.calibration_status = {
        "status": status.status,
        "error": status.error,
        "status_tooltip": status.status_tooltip,
        "error_tooltip": status.error_tooltip,
        "version": status.version,
        "time": status.time,
    }


def _communication_finished(c: MaintenanceController, key: str, kind: str, ok: bool, payload: object) -> None:
    """MaintenanceDialog.task_finished, with the automatic verification after a write (MAINT-005, 058)."""
    tab = c.comm
    tab.busy, tab.task = False, None
    tab.verification_passed = ok and kind == "maintenance_verify"
    page.update_comm(c)
    if ok:
        session = c.session_of(key)
        shown = session.pending if session and session.pending else payload
        tab.identity = identity_lines(shown if isinstance(shown, Mapping) else {})
        tab.set_state(texts.FINISHED_TEXTS.get(kind, "操作完成"))
        if tab.verification_passed:
            page.show_verified(c)
        if kind == "maintenance_write" and session and session.pending:
            tab.busy, tab.task = True, "maintenance_verify"
            page.update_comm(c)
            tab.set_state(texts.AUTO_VERIFY, attention=True)
            c.queue(key, "maintenance_verify", {})
    else:
        tab.set_state(texts.OPERATION_FAILED.format(reason=payload), attention=True)
    tab.operation_result = True


ACTIONS: dict[str, Action] = {
    "tab": _tab,
    "target": _target,
    "diagnostics_read": _diagnostics,
    "diagnostics_export": _export,
    "calibration_read": _calibration_read,
    "calibration_edit": _calibration_edit,
    "calibration_discard": _calibration_discard,
    "calibration_write": _calibration_write,
    "enter": _enter,
    "comm_read": _comm("maintenance_read"),
    "comm_write": _comm("maintenance_write"),
    "comm_verify": _comm("maintenance_verify"),
    "leave": _leave,
    "dismiss_notice": _dismiss,
}
CONFIRMATIONS: dict[str, Confirmation] = {
    "enter": _enter_confirmation,
    "comm_write": _comm_write_confirmation,
    "calibration_write": _calibration_write_confirmation,
    "leave": _leave_confirmation,
    "calibration_reread": _reread_confirmation,
    "close_discard": _close_confirmation,
}
