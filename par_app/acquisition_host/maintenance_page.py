"""The maintenance page's view model (17_ 9 GET /maintenance/state) and the communication tab's state line.

`view` gathers what V1.0.3's DeviceMaintenanceDialog, MaintenanceDialog and MainWindow show and enable, computed with
V1.0.3's conditions; the page renders it and computes nothing (13_ appendix D item 4). `update_comm` is
MaintenanceDialog.update_controls together with the part of DeviceMaintenanceDialog.update_controls that overrides
the communication tab's state line outside maintenance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..maintenance import BAUDRATES, PARITIES
from . import v1_reads
from . import v1_texts as texts
from .maintenance_calibration import field_rows
from .maintenance_state import CommTab
from .maintenance_view import diagnostics_view, event_rows, identity_lines

if TYPE_CHECKING:
    from .maintenance_host import MaintenanceController

POSITIONS = ("p1", "p2", "p3", "p4")
SETTINGS_STALE = "以下为上次成功读取的值，本次未能确认"
"""D-219 (review M3, R-1-5): not a V1.0.3 text; V1.0.3 clears the values instead."""


def fresh_comm(c: MaintenanceController) -> CommTab:
    """A new MaintenanceDialog for the target (DeviceMaintenanceDialog.rebuild_communication)."""
    tab = CommTab()
    session = c.session_of(c.window.target)
    tab.verification_passed = bool(session and session.verified)
    if c.maintenance():
        tab.mode_changed(True)
    return tab


def follow_registration(c: MaintenanceController) -> None:
    """DeviceMaintenanceDialog.rebuild_devices (connected to devices_changed): once the hub has taken a new
    registration, the target falls back to the first registered device if it was deleted, and the communication tab
    is rebuilt for the target (rebuild_communication), whether the target changed or not (#58, D-224).

    V1.0.3 runs this synchronously when the hub takes the registration; here the hub's devices_changed reaches the
    controller queued, and a request may read or act on the page before that, so every view, action and confirmation
    follows the registration first. While a task of the page is in flight (a save is refused then, but one may be
    started between the save and the hub taking it) the rebuild waits for the task to end, so its result still finds
    the tab and the target it was sent for."""
    hub = c.hub
    if hub is None or hub.config is c.registration or not c.idle():
        return
    c.registration = hub.config
    if c.window.target not in hub.keys():
        c.window.target = next(iter(hub.keys()), "")
    c.comm = fresh_comm(c)


def acquisition_state(c: MaintenanceController) -> tuple[str, str]:
    """MainWindow._refresh_communication_events: the acquisition state line and its level."""
    hub, _ = c.parts()
    halt = c.halt()
    if halt is not None:
        return str(halt["message"]), "error"
    if c.maintenance():
        return texts.ACQUISITION_MAINTENANCE, "error"
    if c.window.entering:
        return texts.ACQUISITION_ENTERING, "warn"
    if not hub.config.configured:
        return texts.ACQUISITION_UNCONFIGURED, "muted"
    snapshots = [c.snapshot(key) for key in hub.keys() if c.device(key).enabled]
    if not snapshots or all(snapshot.get("excluded", False) for snapshot in snapshots):
        return texts.ACQUISITION_NONE, "error"
    failing = any(snapshot.get("failures", 0) for snapshot in snapshots)
    if any(snapshot.get("online", False) for snapshot in snapshots):
        return (texts.ACQUISITION_PARTIAL if failing else texts.ACQUISITION_OK), "ok"
    return texts.ACQUISITION_WAITING, "warn"


def show_verified(c: MaintenanceController) -> None:
    """MaintenanceDialog._show_verified_state."""
    hub, coordinator = c.parts()
    halt = c.halt()
    reason = ""
    if halt:
        reason = str(halt["message"])
    else:
        try:
            for session in v1_reads.sessions(coordinator):
                session.check_resume(hub.config)
        except Exception as error:  # ProtocolError: its text is the reason
            reason = str(error)
    if not reason:
        reason = c.resume_gate().reason
    if reason:
        c.comm.set_state(texts.STATE_VERIFIED_BLOCKED.format(reason=reason), attention=True)
    else:
        c.comm.set_state(texts.STATE_VERIFIED)


def update_comm(c: MaintenanceController) -> None:
    tab = c.comm
    maintenance, halt = c.maintenance(), c.halt()
    session = c.session_of(c.window.target)
    pending = session.pending if session else None
    if pending:
        if not tab.busy and not tab.operation_result:
            tab.set_state(texts.STATE_PENDING, attention=True)
        tab.identity = identity_lines(pending)
    elif tab.verification_passed and maintenance and not tab.busy:
        show_verified(c)
    if halt:
        tab.set_state(str(halt["message"]), attention=True)
    if not maintenance and not halt:
        state = acquisition_state(c)[0]
        entering = c.window.entering
        tab.set_state(
            texts.ACQUISITION_ENTERING if entering else texts.NOT_IN_MAINTENANCE.format(state=state), entering
        )


def _header(c: MaintenanceController) -> dict[str, Any]:
    """DeviceMaintenanceDialog.update_controls: address, communication level and the state line (MAINT-059)."""
    window, device = c.window, c.device(c.window.target)
    snapshot = c.snapshot(window.target)
    level = str(snapshot.get("level", "idle"))
    level_text = texts.LEVEL_TEXTS.get(level, level)
    if c.halt():
        level_text = texts.LEVEL_HALTED
    elif c.maintenance():
        level_text = texts.LEVEL_MAINTENANCE
    elif window.entering:
        level_text = texts.LEVEL_ENTERING
    state, state_level = acquisition_state(c)
    halt = c.halt()
    if halt:
        state, state_level = str(halt["message"]), "error"
    elif window.diagnostics_busy:
        state, state_level = texts.STATE_DIAGNOSTICS, "busy"
    elif window.entering:
        state, state_level = texts.STATE_ENTERING, "busy"
    elif window.calibration_task is not None:
        write = window.calibration_task == "calibration_write"
        state, state_level = (texts.STATE_CALIBRATION_WRITE if write else texts.STATE_CALIBRATION_READ), "busy"
    elif not c.idle():
        state, state_level = texts.STATE_TASK, "busy"
    elif c.maintenance():
        state_level = "maintenance"
    return {
        "address": texts.ADDRESS_TEXT.format(slave_id=device.slave_id) if device else texts.NO_ADDRESS,
        "communication": texts.COMMUNICATION_TEXT.format(level=level_text) if device else texts.UNREGISTERED,
        "state": state,
        "state_level": state_level,
    }


def _diagnostics(c: MaintenanceController) -> dict[str, Any]:
    key = c.window.target
    path = c.database_path(key)
    name = str(path) if path else ""
    data = c.window.snapshots.get(name)
    shown = diagnostics_view(data, c.window.failures.get(name), c.maintenance())
    reason = c.diagnostics_reason()
    device = c.device(key)
    events = c.events.rows.get(name, [])  # read on the worker thread (D-219, review M2); no I/O here
    return {
        **shown,
        "refresh_enabled": not reason,
        "read_reason": reason if c.idle() else "",
        "export_text": texts.EXPORT_SNAPSHOT if data else texts.EXPORT_EVENTS,
        "export_enabled": device is not None and c.idle() and not c.window.exporting,
        "events": event_rows(events, device.name if device else "", name),
    }


def _calibration(c: MaintenanceController) -> dict[str, Any]:
    window, draft = c.window, c.draft
    available = c.calibration_available()
    idle = c.idle()
    editable = c.editable()
    preview = c.calibration_preview() if draft.shown else None
    status = window.calibration_status
    return {
        "fields": field_rows(draft, editable),
        "read_enabled": available and idle,
        "write_enabled": editable,
        "discard_enabled": draft.dirty and idle,
        "editable": editable,
        "dirty": draft.dirty,
        "version": draft.version,
        "value_state": window.calibration_state,
        "value_state_error": window.calibration_state_error,
        "history": window.calibration_history,
        "note": window.calibration_note,
        "note_error": window.calibration_note_error,
        "status": status.get("status", "校准状态：未读取"),
        "status_tooltip": status.get("status_tooltip", ""),
        "error": status.get("error", "错误状态：未读取"),
        "error_tooltip": status.get("error_tooltip", ""),
        "version_text": status.get("version", "版本 / 节点数：—"),
        "time": status.get("time", "—"),
        "curve": preview,
        "out_of_order": draft.shown and preview is None,
        "out_of_order_text": texts.CALIBRATION_OUT_OF_ORDER,
        "unavailable_reason": "" if available else CALIBRATION_HINT,
    }


CALIBRATION_HINT = "需为已启用、已配置、在线且无故障的设备，且不在维护或锁停中"


def _connection(values: dict[str, Any]) -> dict[str, Any]:
    return {"slave_id": values["slave_id"], "baudrate": values["baudrate"], "parity": values["parity"]}


def _communication(c: MaintenanceController) -> dict[str, Any]:
    hub, _ = c.parts()
    tab, device = c.comm, c.device(c.window.target)
    maintenance, halt = c.maintenance(), c.halt()
    session = c.session_of(c.window.target)
    pending = session.pending if session else None
    ready = maintenance and not halt and not tab.busy
    bus = hub.config.bus
    defaults = {"slave_id": device.slave_id if device else 1, "baudrate": bus.baudrate, "parity": bus.parity}
    form = {"serial_port": bus.serial_port, "old": dict(defaults), "new": dict(defaults)}
    if pending:
        form = {
            "serial_port": pending["old"]["serial_port"],
            "old": _connection(pending["old"]),
            "new": _connection(pending["new"]),
        }
    return {
        "enter_visible": not maintenance,
        "enter_enabled": not c.diagnostics_reason() and not c.draft.dirty,
        "state": tab.state,
        "attention": tab.attention,
        "busy": tab.busy,
        "form_enabled": bool(ready and not pending),
        "isolation_enabled": bool(ready and not pending),
        "isolated": tab.isolated,
        "read_enabled": bool(ready and not pending),
        "write_enabled": bool(ready and session and session.baseline and not pending),
        "verify_enabled": bool(ready and pending),
        "pending": bool(pending),
        "form": form,
        "form_locked": bool(pending),
        "identity": list(tab.identity),
        "target": texts.TARGET_TEXT.format(name=device.name, slave_id=device.slave_id) if device else "",
        "fixed_parameters": texts.FIXED_PARAMETERS,
        "baudrates": list(BAUDRATES),
        "parities": [
            {"value": value, "label": label} for value, label in zip(PARITIES, texts.PARITY_LABELS, strict=True)
        ],
    }


def _footer(c: MaintenanceController) -> dict[str, Any]:
    gate = c.resume_gate()
    maintenance = c.maintenance()
    window = c.window
    return {
        "resume_visible": maintenance,
        "resume_enabled": gate.allowed,
        "resume_reason": gate.reason,
        "close_text": texts.CLOSE_IN_MAINTENANCE if maintenance else texts.CLOSE,
        "close_enabled": c.idle(),
        "result": window.result,
        "result_error": window.result_error,
        "exported_file": window.exported_file,
    }


def view(c: MaintenanceController) -> dict[str, Any]:
    if c.hub is None:
        return {"available": False, "reason": "当前未在采集：开始采集后才能使用设备维护", "version": c.version}
    hub = c.hub
    devices = [
        {
            "key": key,
            "label": hub.device_at(key).name + ("（停用）" if not hub.device_at(key).enabled else ""),
            "position": POSITIONS[index] if index < len(POSITIONS) else None,
        }
        for index, key in enumerate(hub.keys())
    ]
    halt = c.halt()
    return {
        "available": True,
        "reason": "",
        "version": c.version,
        "session": c.session is not None,
        "tab": c.tab,
        "maintenance": c.maintenance(),
        "entering": c.window.entering,
        "halt": None if halt is None else {"message": str(halt["message"])},
        "busy": not c.idle(),
        "devices": devices,
        "target": c.window.target,
        "target_locked": c.locked(),
        "header": _header(c),
        "diagnostics": _diagnostics(c) if c.window.target else None,
        "calibration": _calibration(c),
        "communication": _communication(c),
        "footer": _footer(c),
        "notice": c.window.notice,
        "settings": {key: settings_view(c, key) for key in c.settings},
    }


def settings_view(c: MaintenanceController, key: str) -> dict[str, Any]:
    """MainWindow._render_comm_values for one device (expected values: the alpha's saved bus configuration)."""
    hub, _ = c.parts()
    watch = c.settings.get(key)
    device = c.device(key)
    source = device.name if device else texts.COMM_UNREGISTERED
    status = watch.status if watch else texts.COMM_STATES["unread"]
    values = watch.readback if watch else None
    expected = (None, hub.config.bus.baudrate, PARITIES.index(hub.config.bus.parity))
    items = []
    for index in (1, 2):
        mismatch = values is not None and values[index] != expected[index]
        text = "—" if values is None else (str(values[index]) if index == 1 else texts.PARITY_TEXTS[values[index]])
        items.append({"text": text, "mismatch": mismatch, "tooltip": texts.COMM_MISMATCH if mismatch else text})
    address = "—" if values is None else str(values[0])
    stale = bool(watch and watch.stale and values is not None)
    return {
        "key": key,
        "source": texts.COMM_SOURCE.format(source=source, status=status),
        "error": bool(watch and watch.error),
        "tooltip": watch.tooltip if watch else "",
        "stale": stale,
        "stale_text": SETTINGS_STALE if stale else "",
        "values": [{"text": address, "mismatch": False, "tooltip": address}, *items],
    }
