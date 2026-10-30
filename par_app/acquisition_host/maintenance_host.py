"""Tier 2 device maintenance on the service's Qt main thread (internal notes).

`MaintenanceController` is what V1.0.3's DeviceMaintenanceDialog, its embedded MaintenanceDialog and the
maintenance parts of MainWindow are, without widgets: the same window conditions (17_ 1.3, G1-G10, decided with
par_app.services' functions), the same in-memory state (17_ 3.4), the same reactions to the coordinator's signals and
the same tasks with the same payloads. It reaches the coordinator only through `queue_task`, `enter_maintenance`
and `leave_maintenance` (17_ 3.2; checked by tests/unit/test_architecture.py) and reads its private maintenance
fields only through v1_reads. Red-line code (protocol, coordinator, CommunicationMaintenance) is not touched.

Every public method runs on the main thread (HostBackend carries HTTP calls here through the gateway). A refusal
raises one of the application errors of 17_ section 9 before anything is queued; a coordinator-side refusal comes
back through `task_finished` and is shown word for word. Nothing here clears a hardware latch.

D-219 (review of PR #55): a calibration draft and every write confirmation are bound to one device
identity (`identity`: key, address, line settings, database, takeover and configuration epoch) and one page
session; attaching, detaching, a saved configuration, a new page session and a maintenance change void them (B1). A
signal queued by a coordinator or hub this controller is no longer attached to does nothing (M1). The view's
database query and the diagnostics export run on one worker thread; only their results come back to the main
thread (M2).
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..application.acquisition import MAINTENANCE_BUSY
from ..application.errors import Busy, FeatureDisabled, InvalidArgument
from ..application.maintenance import (
    TIER_TOO_LOW,
    Halted,
    MaintenanceConfirmations,
    NoSession,
    PreconditionFailed,
    WriteConfirmation,
)
from ..coordinator import PollingCoordinator
from ..device_hub import DeviceHub
from ..domain.clock import Clock
from ..qt_compat import QObject, Qt, pyqtSlot
from ..services import calibration as calibration_service
from ..services import maintenance as maintenance_service
from . import maintenance_actions, maintenance_page, v1_reads
from . import v1_texts as texts
from .maintenance_calibration import CalibrationDraft, curve_view
from .maintenance_io import Events, Worker
from .maintenance_state import CommTab, SettingsComm, WindowState
from .maintenance_view import comm_values

LOG = logging.getLogger(__name__)
Publish = Callable[[str, dict[str, Any]], object]
TABS = (0, 1, 2)
"""设备状态与诊断, 光谱校准, 通信参数维护 (V1.0.3's tab order; MAINT-014: the first one opens by default)."""
SESSION_OPEN = "设备维护页已在另一个窗口打开（同一时间只能有一个维护页）"
UNKNOWN_DEVICE = "设备未登记"
Identity = tuple[object, ...]


class MaintenanceController(QObject):
    """Main-thread object; `flags` may be read from any thread (a tuple swapped in one assignment)."""

    def __init__(self, clock: Clock, publish: Publish, confirmations: MaintenanceConfirmations, exports: Path) -> None:
        super().__init__()
        self.epoch = 0
        """Bumped by attach, detach and every saved configuration: part of every identity (D-219)."""
        self.worker = Worker(lambda: self.epoch)
        self.events = Events()
        self.clock = clock
        self.publish = publish
        self.confirmations = confirmations
        self.exports = exports
        self.hub: DeviceHub | None = None
        self.coordinator: PollingCoordinator | None = None
        self._connections: list[tuple[Any, Any]] = []
        self.flags: tuple[bool, bool] = (False, False)
        """(a maintenance task is in flight or maintenance is being entered, a device write is in flight)"""
        self.version = 0
        self.enabled = True
        """False from a 2 -> 1 until the next 1 -> 2 (review M2): checked on this thread before anything is queued, so a
        request that passed the HTTP-side tier check just before the drop is refused here. The HTTP side checks the tier
        itself first, so True only means "not lowered since the last raise"."""
        self._clear()

    # ------------------------------------------------------------------ lifecycle
    def _clear(self) -> None:
        """Everything V1.0.3 keeps in its windows' memory; quitting V1.0.3 (= stopping the takeover) drops it."""
        self.session: str | None = None
        self.tab = 0
        self.window = WindowState()
        self.draft = CalibrationDraft()
        self.comm = CommTab()
        self.registration: object | None = None  # the hub configuration the page follows (follow_registration)
        self.settings: dict[str, SettingsComm] = {}
        self.settings_watch: str | None = None
        self.device_status: dict[str, dict[str, Any]] = {}
        self.bus_level = "idle"
        self.bus_connected = False
        """MainWindow._settings_bus_connected: connected as last seen when a signal was handled (see _bus_seen)."""
        self.events.clear()
        self.confirmations.clear()

    def attach(self, hub: DeviceHub) -> None:
        self.detach()
        self.epoch += 1
        self.hub, self.coordinator = hub, hub.coordinator
        self.device_status = {state.key: state.snapshot() for state in hub.coordinator.states()}
        self.bus_level = hub.coordinator.bus_message()[0]
        coordinator = hub.coordinator
        self.bus_connected = self._connected_now(coordinator)
        self._connections = [
            (coordinator.task_finished, self._on_task_finished),
            (coordinator.maintenance_changed, self._on_maintenance_changed),
            (coordinator.acquisition_halted, self._on_halted),
            (coordinator.device_state_changed, self._on_device_state),
            (coordinator.bus_state_changed, self._on_bus_state),
            (hub.devices_changed, self._on_devices_changed),
        ]
        for signal, slot in self._connections:
            signal.connect(slot, Qt.ConnectionType.QueuedConnection)
        self._changed(publish=False)

    def detach(self) -> None:
        """After the coordinator stopped: the takeover ended, so does everything the page held (17_ 3.4)."""
        connections, self._connections = self._connections, []
        for signal, slot in connections:
            signal.disconnect(slot)  # a call already queued still arrives: the slots check _current (M1)
        self.epoch += 1
        self.hub = self.coordinator = None
        self._clear()
        self._changed(publish=False)

    def close(self) -> None:
        """The service is closing (the worker thread takes no new job)."""
        self.worker.close()

    def config_changed(self) -> None:
        """A configuration was saved (DeviceHub.apply; D-219, B1): every confirmation and the calibration draft
        were made for the registration before it, so they are void; the draft has to be read again."""
        self.epoch += 1
        self.confirmations.clear()
        if self.draft.baseline is not None or self.draft.device_key is not None:
            maintenance_actions.reset_calibration(self)
            self.window.calibration_note, self.window.calibration_note_error = maintenance_actions.DRAFT_VOIDED, True
        self._changed()

    def _current(self) -> bool:
        """The signal being handled comes from the hub and coordinator attached now (M1): a call queued before
        `detach`, or by the previous takeover's objects, is dropped. Qt reports no sender for a call whose
        connection was removed after it was queued, so a missing sender counts as stale too (the slots are only
        reached through these signals)."""
        if self.hub is None:
            return False
        sender = self.sender()
        return sender is not None and (sender is self.hub or sender is self.coordinator)

    def lowered(self) -> None:
        """Tier 2 -> 1 (17_ 6.1): unwritten calibration edits are dropped; maintenance stays as it is.

        Refused while a maintenance task runs, decided here on the main thread so that no task can be queued between
        the check and the drop (review M2). From now on nothing is queued, entered or left until `raised`: the
        confirmations issued at tier 2 are void and the settings page's automatic re-read stops (review M1)."""
        if not self.idle():
            raise Busy(MAINTENANCE_BUSY)
        self.enabled = False
        self.confirmations.clear()
        self.settings_watch = None
        if self.draft.dirty:
            self.draft.discard()
        self._changed()

    def raised(self) -> None:
        """Tier 1 -> 2 (17_ 6.1)."""
        self.enabled = True
        self._changed()

    def require_enabled(self) -> None:
        if not self.enabled:
            raise FeatureDisabled(TIER_TOO_LOW)

    # ------------------------------------------------------------------ facts (as V1.0.3's window reads them)
    def parts(self) -> tuple[DeviceHub, PollingCoordinator]:
        if self.hub is None or self.coordinator is None:
            raise NoSession("当前未在采集")
        return self.hub, self.coordinator

    def maintenance(self) -> bool:
        return self.coordinator is not None and v1_reads.maintenance(self.coordinator)

    def halt(self) -> dict[str, Any] | None:
        return self.coordinator.halt_reason() if self.coordinator is not None else None

    def device(self, key: str) -> Any:  # noqa: ANN401 (V1.0.3's DeviceConfig or None)
        return self.hub.device_at(key) if self.hub is not None and key else None

    def database_path(self, key: str) -> Path | None:
        database = self.hub.database_for(key) if self.hub is not None else None
        return database.path.resolve() if database is not None else None

    def identity(self, key: str) -> Identity | None:
        """What a draft or a confirmation is bound to (D-219, B1): the device's registration and line settings, its
        database, and the takeover and configuration it was read or confirmed under."""
        device = self.device(key)
        if self.hub is None or device is None:
            return None
        bus = self.hub.config.bus
        return (
            key,
            device.slave_id,
            device.enabled,
            bus.serial_port,
            bus.baudrate,
            bus.parity,
            str(self.database_path(key)),
            self.epoch,
        )

    def _binding(self) -> str:
        """The `key` a confirmation is issued and checked for: target, its identity and the page session."""
        return repr((self.window.target, self.identity(self.window.target), self.session))

    def session_of(self, key: str) -> Any:  # noqa: ANN401 (V1.0.3's CommunicationMaintenance or None)
        path = self.database_path(key)
        return v1_reads.session_for(self.coordinator, path) if self.coordinator and path else None

    def snapshot(self, key: str) -> dict[str, Any]:
        return self.device_status.get(key, {})

    def calibration_busy(self) -> bool:
        return self.window.calibration_task is not None

    def other_busy(self) -> bool:
        """DeviceMaintenanceDialog.other_busy."""
        return self.window.diagnostics_busy or self.window.entering or self.comm.busy

    def idle(self) -> bool:
        return not self.other_busy() and not self.calibration_busy()

    def locked(self) -> bool:
        """DeviceMaintenanceDialog.locked (G7)."""
        pending = self.coordinator is not None and v1_reads.any_pending(self.coordinator)
        return not self.idle() or self.draft.dirty or pending

    def faulty(self, key: str) -> bool:
        """MainWindow._device_is_faulty."""
        snapshot = self.snapshot(key)
        return bool(
            snapshot.get("failures")
            or snapshot.get("excluded")
            or snapshot.get("level") in ("error", "power", "offline")
        )

    def calibration_available(self) -> bool:
        """MainWindow._calibration_available (G2) for the maintenance target."""
        hub, _ = self.parts()
        device = self.device(self.window.target)
        return calibration_service.calibration_available(
            device_enabled=bool(device and device.enabled),
            configured=hub.config.configured,
            online=self.snapshot(self.window.target).get("online"),
            faulty=self.faulty(self.window.target),
            maintenance=self.maintenance(),
            halted=bool(self.halt()),
        )

    def calibration_preview(self) -> dict[str, Any] | None:
        return curve_view(self.draft.values)

    def editable(self) -> bool:
        """MainWindow._update_calibration_controls: the write button, the boxes and the preview."""
        return self.calibration_available() and self.idle() and self.draft.device_key == self.window.target

    def diagnostics_reason(self) -> str:
        """DeviceMaintenanceDialog.update_controls: why 刷新 is disabled (G1), "" when it is enabled."""
        hub, _ = self.parts()
        device = self.device(self.window.target)
        halt = self.halt()
        if halt:
            return str(halt["message"])
        if self.maintenance():
            return texts.READ_IN_MAINTENANCE
        if self.window.entering:
            return texts.READ_ENTERING
        if not self.idle():
            return texts.READ_BUSY
        if not device or not device.enabled:
            return texts.READ_UNREGISTERED
        if not hub.config.configured:
            return texts.READ_UNCONFIGURED
        if self.snapshot(self.window.target).get("excluded"):
            return texts.READ_EXCLUDED
        return ""

    def resume_gate(self) -> maintenance_service.ResumeGate:
        """D-110: both resume entries use the maintenance window's conditions, with the service's draft (G8)."""
        hub, coordinator = self.parts()
        return maintenance_service.resume_gate(
            maintenance=self.maintenance(),
            halt=self.halt(),
            task_busy=not self.idle(),
            calibration_dirty=self.draft.dirty,
            sessions=v1_reads.sessions(coordinator),
            config=hub.config,
        )

    # ------------------------------------------------------------------ change handling
    def _refresh(self) -> None:
        """What V1.0.3's update_controls / _update_calibration_controls do besides enabling widgets."""
        if self.hub is None:
            return
        maintenance_page.follow_registration(self)
        if not self.calibration_available():
            self.draft.device_key = None
        maintenance_page.update_comm(self)

    def _changed(self, publish: bool = True) -> None:
        """Recompute the flags; publish `maintenance_state` (attaching and detaching do not: takeover_state says it)."""
        self._refresh()
        writing = self.window.calibration_task == "calibration_write" or self.comm.task == "maintenance_write"
        self.flags = (not self.idle(), writing)
        self.events.load(self)
        self.published(publish)

    def published(self, publish: bool = True) -> None:
        self.version += 1
        if publish and (self.session is not None or self.settings):  # nobody shows it otherwise (tier 1 stays quiet)
            self.publish("maintenance_state", {"version": self.version})

    def view(self) -> dict[str, Any]:
        self._refresh()
        return maintenance_page.view(self)

    def events_loaded(self) -> bool:
        path = self.database_path(self.window.target)
        return self.events.loaded(str(path) if path else None)

    # ------------------------------------------------------------------ signals (queued, main thread)
    @pyqtSlot(str, str, bool, object)
    def _on_task_finished(self, key: str, kind: str, ok: bool, payload: object) -> None:
        if not self._current():
            return
        try:
            maintenance_actions.task_finished(self, key, kind, ok, payload)
        except Exception:
            LOG.exception("maintenance page failed on task_finished %s %s", key, kind)
        self._changed()

    @pyqtSlot(bool)
    def _on_maintenance_changed(self, active: bool) -> None:
        if not self._current():
            return
        self.confirmations.clear()  # a maintenance change voids every confirmation (D-219)
        self.comm.mode_changed(active)
        self.window.entering = False
        self._bus_refresh()
        self._changed()

    @pyqtSlot(dict)
    def _on_halted(self, reason: dict[str, Any]) -> None:
        if not self._current():
            return
        self.comm.set_state(str(reason.get("message", "")), attention=True)
        self._bus_refresh()
        self._changed()

    @pyqtSlot(str, dict)
    def _on_device_state(self, key: str, snapshot: dict[str, Any]) -> None:
        if not self._current():
            return
        was_online = self.snapshot(key).get("online", False)
        self.device_status[key] = snapshot
        self._bus_refresh()
        watch = self.settings.get(key)
        if (
            key == self.settings_watch
            and snapshot.get("online")
            and not was_online
            and watch is not None
            and (watch.readback is None or watch.stale)
            and not watch.pending
        ):
            self._settings_request(key)
        self._changed()

    @pyqtSlot(str, str)
    def _on_bus_state(self, level: str, message: str) -> None:
        if not self._current():
            return
        self.bus_level = level
        self._bus_seen(level, message)
        self._changed()

    def _connected_now(self, coordinator: PollingCoordinator) -> bool:
        return v1_reads.bus_connected(coordinator) and not self.maintenance() and self.halt() is None

    def _bus_seen(self, level: str, message: str) -> None:
        """MainWindow._on_bus_state's settings part. "Connected" is the coordinator's state now, not the level the
        signal carried: a warning -> ok the main thread handles after the reconnect has finished changes nothing, as
        in V1.0.3, instead of queueing one more comm_read (static review item 2; D-222). V1.0.3 runs it on every
        refresh of the communication events, so the slots of the signals that refresh them call it too
        (device_state_changed, devices_changed, acquisition_halted, maintenance_changed) with the current level."""
        if self.coordinator is None:
            return
        connected = self._connected_now(self.coordinator)
        was_connected, self.bus_connected = self.bus_connected, connected
        watch = self.settings.get(self.settings_watch or "")
        if watch is not None and was_connected and not connected:
            watch.show(texts.COMM_STATES["disconnected"], level == "error", None, message)
        if watch is not None and connected and not was_connected and self.settings_watch:
            self._settings_request(self.settings_watch)

    def _bus_refresh(self) -> None:
        """MainWindow._refresh_communication_events: _on_bus_state with the coordinator's current level."""
        if self.coordinator is not None:
            self._bus_seen(*self.coordinator.bus_message())

    @pyqtSlot()
    def _on_devices_changed(self) -> None:
        if not self._current():
            return
        _, coordinator = self.parts()
        self.device_status = {state.key: state.snapshot() for state in coordinator.states()}
        self._bus_refresh()
        self._changed()  # _refresh -> follow_registration

    # ------------------------------------------------------------------ page session
    def open_page(self, tab: int) -> dict[str, Any]:
        self.require_enabled()
        hub, coordinator = self.parts()
        if self.session is not None:
            raise Busy(SESSION_OPEN)
        self.session = secrets.token_urlsafe(8)
        self.confirmations.clear()
        self.window.snapshots.clear()  # D-134 A (DEF-17): "本次新增" counts from this page session
        self.window.failures.clear()
        pending = v1_reads.pending_paths(coordinator)
        if pending and not self.other_busy() and not self.calibration_busy():
            for key in hub.keys():
                if self.database_path(key) in pending:
                    self.window.target = key
                    self.draft.reset()
                    break
        if not self.locked():
            self.window.target = hub.active_key
            self.draft.reset()
        self.comm = maintenance_page.fresh_comm(self)
        self.tab = tab if tab in TABS else 0
        maintenance_actions.page_changed(self, self.tab)
        self._changed()
        return self.view()

    def close_page(self, confirmation_id: str | None) -> dict[str, Any]:
        """DeviceMaintenanceDialog.reject (G10)."""
        self.require_session()
        if self.other_busy() or self.calibration_busy():
            raise Busy(texts.READ_BUSY)
        if self.draft.dirty:
            self.check(confirmation_id, "close_discard", {}, self.draft.version)
            maintenance_actions.discard(self)
        self.session = None
        self.confirmations.clear()
        self._changed()
        return self.view()

    def require_session(self) -> tuple[DeviceHub, PollingCoordinator]:
        parts = self.parts()
        if self.session is None:
            raise NoSession("设备维护页未打开")
        return parts

    def ready(self, busy_ok: bool = False) -> tuple[DeviceHub, PollingCoordinator]:
        """Public preconditions of every device operation after the tier and takeover (17_ section 4)."""
        parts = self.require_session()
        if not busy_ok and not self.idle():
            raise Busy(texts.READ_BUSY)
        halt = self.halt()
        if halt:
            raise Halted(str(halt["message"]))
        return parts

    # ------------------------------------------------------------------ actions
    def act(self, action: str, body: Mapping[str, Any], confirmation_id: str | None) -> dict[str, Any]:
        self.require_enabled()
        handler = maintenance_actions.ACTIONS.get(action)
        if handler is None:
            raise InvalidArgument(f"未知的维护操作：{action}")
        maintenance_page.follow_registration(self)  # as V1.0.3 shows it after the save (#58)
        handler(self, body, confirmation_id)
        self._changed()
        return self.view()

    def confirm(self, action: str, body: Mapping[str, Any]) -> WriteConfirmation:
        self.require_enabled()
        builder = maintenance_actions.CONFIRMATIONS.get(action)
        if builder is None:
            raise InvalidArgument(f"该操作不需要确认：{action}")
        maintenance_page.follow_registration(self)
        title, text, version = builder(self, body)
        return self.confirmations.issue(action, self._binding(), body, version, title, text)

    def check(self, confirmation_id: str | None, action: str, body: Mapping[str, Any], version: int = 0) -> None:
        """The confirmation was issued for this action, body and draft version, on this target with the same
        identity and in this page session (D-219, B1)."""
        self.confirmations.consume(confirmation_id, action, self._binding(), body, version)

    # -- the only calls into the coordinator (17_ 3.2 whitelist; tests/unit/test_architecture.py)
    def queue(self, key: str, kind: str, payload: object = None) -> None:
        self.require_enabled()
        _, coordinator = self.parts()
        if kind not in QUEUED_TASKS:
            raise InvalidArgument(f"不允许的设备任务：{kind}")
        coordinator.queue_task(key, kind, payload)

    def enter(self) -> None:
        self.require_enabled()
        _, coordinator = self.parts()
        coordinator.enter_maintenance()

    def leave(self) -> None:
        self.require_enabled()
        _, coordinator = self.parts()
        coordinator.leave_maintenance()

    # ------------------------------------------------------------------ settings page "通信参数当前值" (G9)
    def settings_comm(self, position: int) -> dict[str, Any]:
        self.require_enabled()
        hub, _ = self.parts()
        keys = hub.keys()
        if not 0 <= position < len(keys):
            raise PreconditionFailed(UNKNOWN_DEVICE)
        key = keys[position]
        self.settings_watch = key
        self._settings_request(key)
        self._changed()
        return maintenance_page.settings_view(self, key)

    def settings_left(self) -> None:
        """The settings page is no longer shown: V1.0.3 re-reads on a reconnect only while its settings tab is the
        current one (ui.py, review M1), so the automatic re-read stops; the last values stay for the next visit."""
        self.settings_watch = None

    def _settings_request(self, key: str) -> None:
        """MainWindow._request_settings_comm: the display state, and comm_read only when V1.0.3 would send it."""
        if not self.enabled:  # tier 1 makes no maintenance call (17_ 3.2; review M1)
            return
        hub, coordinator = self.parts()
        watch = self.settings.setdefault(key, SettingsComm())
        watch.stale = watch.readback is not None  # shown as the previous value until this request succeeds (review M3)
        state = coordinator.state(key)
        device = self.device(key)
        if device is None or not hub.config.configured:
            watch.show(texts.COMM_STATES["unconfigured"], False)
        elif self.halt() is not None:
            watch.show(texts.COMM_STATES["halted"], True)
        elif self.maintenance():
            watch.show(texts.COMM_STATES["maintenance"], False)
        elif state is None or not state.config.enabled or state.excluded:
            watch.show(texts.COMM_STATES["excluded"], False)
        elif not v1_reads.bus_connected(coordinator):  # MainWindow: `coordinator._client is None`
            level, message = coordinator.bus_message()
            watch.show(texts.COMM_STATES["disconnected"], level == "error", None, message)
        else:
            watch.show(texts.COMM_STATES["reading"], False)
            if not watch.pending:
                watch.pending = True
                self.queue(key, "comm_read")

    def settings_accept(self, key: str, ok: bool, payload: object) -> None:
        """MainWindow._accept_settings_comm, except that a failed read keeps the last valid values, marked as such
        (R-1-5; D-219, review M3; V1.0.3 clears them)."""
        watch = self.settings.setdefault(key, SettingsComm())
        try:
            if not ok:
                raise ValueError(str(payload))
            readback = comm_values(payload)
        except ValueError as error:
            watch.stale = watch.readback is not None
            watch.show(texts.COMM_STATES["failed"], True, None, str(error))
        else:
            watch.readback, watch.stale = readback, False
            watch.show(texts.COMM_STATES["read"], False, readback)


QUEUED_TASKS = (
    "diagnostics_read",
    "calibration_read",
    "calibration_write",
    "comm_read",
    "maintenance_read",
    "maintenance_write",
    "maintenance_verify",
)
"""17_ 3.2: the task names tier 2 may queue (with enter_maintenance and leave_maintenance); read_identity,
comm_write and apply_config are never queued from here."""
