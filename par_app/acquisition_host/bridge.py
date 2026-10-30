"""Event bridge: the coordinator's public signals -> state cache and event stream (16_ 1.4, section 5; D-212 q. 5).

Every signal is connected with Qt.QueuedConnection to a slot of this object, which lives on the service's main
thread, exactly as V1.0.3's window receives them on its GUI thread. No new code runs on the coordinator thread. A
slot reads the coordinator only through the public methods V1.0.3's window uses (states(), status_text(),
bus_message(), halt_reason()), updates the cache and publishes a JSON-safe event. A slot never lets an exception
out (PyQt5 aborts the process on an uncaught exception in a slot): it is logged with its traceback instead.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from ..application.acquisition import StatusCache, halt_text
from ..coordinator import PollingCoordinator
from ..models import AppConfig, BusConfig
from ..qt_compat import QObject, Qt, pyqtSlot

LOG = logging.getLogger(__name__)
Publish = Callable[[str, dict[str, Any]], object]
Action = Callable[[], object]


def jsonable(value: object) -> Any:  # noqa: ANN401 (JSON: any of dict, list, str, number, bool, None)
    """`value` with dataclasses as dicts and anything else unknown as its text (logged once per type)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if type(value) not in _LOGGED:
        _LOGGED.add(type(value))
        LOG.info("event value of type %s sent as text", type(value).__name__)
    return str(value)


_LOGGED: set[type] = set()


def device_entry(coordinator: PollingCoordinator, key: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = jsonable(snapshot)
    entry["status_text"] = coordinator.status_text(key)
    return entry


def device_entries(coordinator: PollingCoordinator) -> list[dict[str, Any]]:
    return [device_entry(coordinator, state.key, state.snapshot()) for state in coordinator.states()]


class EventBridge(QObject):
    def __init__(self, coordinator: PollingCoordinator, cache: StatusCache, publish: Publish) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.cache = cache
        self.publish = publish
        self._connections = [
            (coordinator.bus_state_changed, self._on_bus_state),
            (coordinator.bus_config_changed, self._on_bus_config),
            (coordinator.config_applied, self._on_config_applied),
            (coordinator.device_state_changed, self._on_device_state),
            (coordinator.device_alert, self._on_device_alert),
            (coordinator.acquisition_saved, self._on_saved),
            (coordinator.acquisition_halted, self._on_halted),
            (coordinator.maintenance_changed, self._on_maintenance),
            (coordinator.task_finished, self._on_task_finished),
        ]
        for signal, slot in self._connections:
            # the PyQt5 stubs omit connect()'s connection-type argument
            signal.connect(slot, Qt.ConnectionType.QueuedConnection)

    def detach(self) -> None:
        """Disconnect this bridge's slots (after the coordinator has stopped and the queue was drained); V1.0.3's own
        connections (DeviceHub, ActiveDeviceService) stay as they are."""
        connections, self._connections = self._connections, []
        for signal, slot in connections:
            signal.disconnect(slot)

    def _guarded(self, what: str, action: Action) -> None:
        try:
            action()
        except Exception:
            LOG.exception("event bridge failed on %s; the coordinator keeps running", what)

    @pyqtSlot(str, str)
    def _on_bus_state(self, level: str, message: str) -> None:
        def run() -> None:
            self.cache.set_bus(level, message)
            self.publish("bus_state", {"level": level, "message": message})

        self._guarded("bus_state", run)

    @pyqtSlot(object)
    def _on_bus_config(self, bus: object) -> None:
        def run() -> None:
            self.publish("bus_config", jsonable(bus.to_dict() if isinstance(bus, BusConfig) else bus))

        self._guarded("bus_config", run)

    @pyqtSlot(object)
    def _on_config_applied(self, config: object) -> None:
        def run() -> None:
            poll = config.effective_poll_cycle_seconds() if isinstance(config, AppConfig) else None
            devices = device_entries(self.coordinator)
            configured = config.configured if isinstance(config, AppConfig) else None
            self.cache.set_devices(devices, poll, configured)  # None when unknown, never a 0.0 placeholder (R-1-6)
            self.publish("config_applied", {"keys": [d["key"] for d in devices], "configured": configured})

        self._guarded("config_applied", run)

    @pyqtSlot(str, dict)
    def _on_device_state(self, key: str, snapshot: dict[str, Any]) -> None:
        def run() -> None:
            entry = device_entry(self.coordinator, key, snapshot)
            self.cache.set_device(entry)
            self.publish("device_state", entry)

        self._guarded("device_state", run)

    @pyqtSlot(str, str, str)
    def _on_device_alert(self, key: str, name: str, detail: str) -> None:
        self._guarded(
            "device_alert", lambda: self.publish("device_alert", {"key": key, "name": name, "detail": detail})
        )

    @pyqtSlot(str, int)
    def _on_saved(self, key: str, record_id: int) -> None:
        def run() -> None:
            state = self.coordinator.state(key)
            if state is not None:
                self.cache.set_device(device_entry(self.coordinator, key, state.snapshot()))
            self.publish("acquisition_saved", {"key": key, "record_id": record_id})

        self._guarded("acquisition_saved", run)

    @pyqtSlot(dict)
    def _on_halted(self, reason: dict[str, Any]) -> None:
        def run() -> None:
            entry: dict[str, Any] = jsonable(reason)
            entry["text"] = halt_text(reason)
            self.cache.set_halt(entry)
            self.publish("acquisition_halted", entry)

        self._guarded("acquisition_halted", run)

    @pyqtSlot(bool)
    def _on_maintenance(self, maintenance: bool) -> None:
        def run() -> None:
            self.cache.set_maintenance(maintenance)
            self.publish("maintenance_changed", {"maintenance": maintenance})

        self._guarded("maintenance_changed", run)

    @pyqtSlot(str, str, bool, object)
    def _on_task_finished(self, key: str, kind: str, ok: bool, result: object) -> None:
        data = {"key": key, "kind": kind, "ok": ok, "result": None}
        self._guarded("task_finished", lambda: self.publish("task_finished", {**data, "result": jsonable(result)}))
