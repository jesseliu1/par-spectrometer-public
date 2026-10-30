"""The takeover: V1.0.3's lock, DeviceHub and PollingCoordinator on the service's Qt main thread (16_ 1.3-1.5, 2, 3).

`AcquisitionHost` does what V1.0.3's main.py does, in the same order, but only when asked (D-212 questions 1, 2):
take the single-instance lock, build DeviceHub(store, initial_config=store.load_for_startup()) on the main thread
and call coordinator.start(); to stop, call coordinator.stop() on the main thread (the method V1.0.3 connects to
aboutToQuit), let the queued signals reach V1.0.3's slots and the bridge, then release the lock. A stopped
coordinator cannot be restarted (`stop()` leaves `_running` False), so every start builds a new DeviceHub, which on
the bus is the same as restarting V1.0.3. Only start(), stop() and DeviceHub.apply() are ever called: no
queue_task, so none of V1.0.3's page-triggered reads (comm_read, calibration_read) are sent (D-212 question 6).

`HostBackend` is the thread-safe face the application layer uses (TakeoverBackend): it checks and moves the state in
the cache, then carries the call onto the main thread through the gateway.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from ..app_config import AppConfigStore, StartupConfigurationError
from ..application.acquisition import StatusCache
from ..application.errors import Busy, ConfigUnavailable, InstanceLocked, InvalidArgument, NotRunning
from ..application.maintenance import MaintenanceConfirmations, WriteConfirmation
from ..application.paths import AlphaPaths
from ..device_hub import DeviceHub
from ..domain.clock import Clock, SystemClock
from ..qt_compat import QCoreApplication
from . import config_import, config_io, serial_ports, v1_reads
from .bridge import EventBridge, Publish, device_entries
from .gateway import MainThreadGateway
from .instance_lock import InstanceLock
from .maintenance_host import MaintenanceController

LOG = logging.getLogger(__name__)
START_TIMEOUT_SECONDS = 30.0
"""How long an HTTP request waits for the main thread to take the lock and start the coordinator."""
APPLY_TIMEOUT_SECONDS = 30.0
"""How long an HTTP request waits for DeviceHub.apply on the main thread (it creates databases)."""
MAINTENANCE_TIMEOUT_SECONDS = 30.0
"""How long an HTTP request waits for the maintenance controller on the main thread (17_ 3.2; it only queues)."""
LOCKED_MESSAGE = "串口正被其他程序占用（例如旧版光谱仪软件），本次未开始采集。请先关闭该程序，再点“开始采集”。"
NOT_RUNNING_MESSAGE = "当前未在采集"
BUSY_MESSAGE = "正在开始或停止采集，请稍候"
MAINTENANCE_SAVE_BUSY = "设备维护任务尚未结束，暂不能保存配置；请等待任务结束后再保存"
RELEASED_BUS = ("idle", "未在采集：未连接设备")
CLOSED_MESSAGE = "服务正在关闭，本次未开始采集"


class AcquisitionHost:
    """Main-thread object; every method except `store` must run on the Qt main thread."""

    def __init__(
        self,
        data_dir: Path,
        cache: StatusCache,
        publish: Publish,
        changed: Callable[[], None],
        lock: InstanceLock | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.store = AppConfigStore(data_dir)
        self.paths = AlphaPaths(data_dir)
        self.cache = cache
        self.publish = publish
        self.changed = changed
        self.lock = lock if lock is not None else InstanceLock()
        self.hub: DeviceHub | None = None
        self.bridge: EventBridge | None = None
        self._stopping = False
        self._closed = False
        """Set by shutdown(): a start that was interrupted by the shutdown, or comes after it, never starts."""
        self._after_stop: list[Callable[[], None]] = []
        clock = clock if clock is not None else SystemClock()
        self.maintenance = MaintenanceController(
            clock, publish, MaintenanceConfirmations(clock), self.paths.exports_dir
        )

    def _set(self, state: str, error: str | None = None) -> None:
        self.cache.set_takeover(state, self.lock.held, error)  # type: ignore[arg-type]
        self.changed()

    def start(self, allowed: Callable[[], None] | None = None) -> None:
        """`allowed` raises when the takeover may no longer start (tier lowered, service closing; review M1)."""
        if self.hub is not None or self._stopping:
            raise Busy("已在采集或正在停止")
        self._set("starting")
        try:
            self._check_open()
            if allowed is not None:
                allowed()
            config_io.check_paths(self.store, config_io.read_file(self.store))
            if not self.lock.acquire():
                raise InstanceLocked(LOCKED_MESSAGE)
            self._build_and_start()
        except Exception as error:
            if self.bridge is not None:
                self.bridge.detach()
            self.maintenance.detach()
            self.hub = self.bridge = None
            self.lock.release()
            self._set("released", getattr(error, "message", str(error)))
            raise
        self._set("running")

    def _build_and_start(self) -> None:
        try:
            config = self.store.load_for_startup()
            hub = DeviceHub(self.store, initial_config=config)
        except StartupConfigurationError as error:
            raise ConfigUnavailable("采集配置或设备库不可用，本次未开始采集", str(error)) from error
        except (OSError, ValueError, sqlite3.Error) as error:
            raise ConfigUnavailable("无法打开设备库，本次未开始采集", str(error)) from error
        coordinator = hub.coordinator
        self.bridge = EventBridge(coordinator, self.cache, self.publish)
        maintenance = v1_reads.maintenance(coordinator)  # read as V1.0.3's MainWindow reads it (no public accessor)
        self.cache.reset(
            coordinator.bus_message(),
            device_entries(coordinator),
            maintenance,
            config.effective_poll_cycle_seconds(),
            config.configured,
        )
        self.hub = hub
        self._check_open()  # a shutdown that ran while this start was under way (signal; review M3)
        self.maintenance.attach(hub)
        coordinator.start()

    def _check_open(self) -> None:
        if self._closed:
            raise Busy(CLOSED_MESSAGE)

    def apply(self, payload: Mapping[str, Any]) -> None:
        hub = self.hub
        if hub is None:
            raise NotRunning(NOT_RUNNING_MESSAGE)
        if not self.maintenance.idle():  # V1.0.3's modal maintenance window blocks the settings page (review Q2)
            raise Busy(MAINTENANCE_SAVE_BUSY)
        try:
            saved = config_io.read_file(self.store)
        except ConfigUnavailable:
            saved = None  # the running configuration still decides which databases may be kept
        config = config_io.build(self.store, hub.config, payload, saved)
        try:
            hub.apply(config)
        except ValueError as error:
            raise InvalidArgument(str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise ConfigUnavailable("设备库无法建立或打开，配置未保存", str(error)) from error
        finally:
            # at once, before any queued request (D-219, B1): drafts and confirmations of the old registration are void
            self.maintenance.config_changed()

    def reconfigure(self, payload: Mapping[str, Any]) -> None:
        """Save from an empty configuration while nothing is taken over (D-220): what V1.0.3 does after "重新配置"
        (main.create_startup_hub: DeviceHub(store, initial_config=AppConfig(...)), store.preserve_before_save = True;
        the first save backs the original file up, CONF-010, D-141). The DeviceHub is built only to run V1.0.3's
        DeviceHub.apply (checks, new databases in the alpha's folder, the save); its coordinator is never started,
        so no lock is taken and no port or connection is opened. The caller checked that the configuration is
        unusable; this runs on the main thread, so a start cannot be under way at the same time."""
        if self.hub is not None or self._stopping or self.cache.takeover != "released":
            raise Busy("已在采集或正在开始、停止采集；重新配置只在未采集时进行")
        self._check_open()
        store = AppConfigStore(self.paths.data_dir)
        store.preserve_before_save = True
        blank = config_io.empty()
        config = config_io.build(store, blank, payload)
        hub = DeviceHub(store, initial_config=blank)
        try:
            hub.apply(config)
        except ValueError as error:
            raise InvalidArgument(str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise ConfigUnavailable("设备库无法建立或打开，配置未保存", str(error)) from error
        finally:
            hub.coordinator.deleteLater()  # never started: nothing to stop
            hub.deleteLater()

    def stop(self, then: Callable[[], None] | None = None) -> None:
        """Stop and release; `then` runs once the lock is released (also when a stop is already under way)."""
        if then is not None:
            self._after_stop.append(then)
        if self._stopping:
            return  # a nested request (signal during the stop): the running stop finishes and runs `then`
        hub, bridge = self.hub, self.bridge
        if hub is not None:
            self._stopping = True
            self._set("stopping")
            try:
                hub.coordinator.stop()
            finally:
                QCoreApplication.processEvents()  # queued signals reach V1.0.3's slots and the bridge, as on quit
                if bridge is not None:
                    bridge.detach()
                self.maintenance.detach()
                self.hub = self.bridge = None
                self.lock.release()
                self.cache.set_bus(*RELEASED_BUS)
                self._stopping = False
        # `then` runs after the lock was released but before the takeover reads "released", so a start cannot be
        # accepted in between (review M1: the tier-0 write of a lowering stop happens first)
        callbacks, self._after_stop = self._after_stop, []
        try:
            for callback in callbacks:
                callback()
        finally:
            self._set("released")

    def shutdown(self) -> None:
        self._closed = True
        try:
            self.stop()
        finally:
            self.maintenance.close()


class HostBackend:
    """TakeoverBackend for the application layer; safe to call from HTTP threads."""

    def __init__(
        self,
        host: AcquisitionHost,
        gateway: MainThreadGateway,
        ports: serial_ports.Enumerate = serial_ports.system_ports,
    ) -> None:
        self.host = host
        self.gateway = gateway
        self.cache = host.cache
        self.ports = ports
        """The serial-port enumeration (tests inject a fake list; the service the operating system's)."""

    def start(self, allowed: Callable[[], None]) -> None:
        """The takeover already reads "starting" (AcquisitionService.start); the main thread does the rest."""
        try:
            self.gateway.call(lambda: self.host.start(allowed), START_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise Busy("服务主线程繁忙，开始采集请求未在时限内处理；请查看状态后重试") from error

    def request_stop(self, then: Callable[[], None] | None = None) -> None:
        if not self.cache.begin("running", "stopping"):
            raise NotRunning(NOT_RUNNING_MESSAGE) if self.cache.takeover == "released" else Busy(BUSY_MESSAGE)
        self.gateway.post(lambda: self.host.stop(then))

    def apply_config(self, payload: Mapping[str, Any]) -> None:
        takeover = self.cache.takeover
        if takeover != "running":
            raise NotRunning("请先开始采集再保存配置") if takeover == "released" else Busy(BUSY_MESSAGE)
        try:
            self.gateway.call(lambda: self.host.apply(payload), APPLY_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise Busy("服务主线程繁忙，配置未在时限内应用；请查看状态后重试") from error

    def reconfigure(self, payload: Mapping[str, Any]) -> None:
        if self.cache.takeover != "released":
            raise Busy(BUSY_MESSAGE)
        try:
            self.gateway.call(lambda: self.host.reconfigure(payload), APPLY_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise Busy("服务主线程繁忙，配置未在时限内保存；请查看配置后重试") from error

    def read_config(self) -> dict[str, Any]:
        return config_io.view(self.host.store)

    def import_preview(self, source: str) -> dict[str, Any]:
        return config_import.preview(self.host.paths, source)

    def serial_ports(self) -> dict[str, Any]:
        """V1.0.3's 刷新串口 on the HTTP thread: lists the ports, opens none, touches no Qt object (#74)."""
        return serial_ports.listing(self.ports)

    def shutdown(self) -> None:
        self.host.shutdown()


class MaintenanceBackend:
    """MaintenancePort for the application layer: each call runs on the main thread through the gateway; `busy` and
    `writing` read the controller's flags without waiting for the main thread (GET /tier must not block)."""

    def __init__(self, host: AcquisitionHost, gateway: MainThreadGateway) -> None:
        self.controller = host.maintenance
        self.gateway = gateway

    def _call(self, function: Callable[[], Any]) -> Any:  # noqa: ANN401 (the controller's answer)
        try:
            return self.gateway.call(function, MAINTENANCE_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise Busy("服务主线程繁忙，维护请求未在时限内处理；请查看状态后重试") from error

    def view(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._call(self.controller.view))

    def open_page(self, tab: str) -> dict[str, Any]:
        index = int(tab) if tab.isdigit() else 0
        return cast(dict[str, Any], self._call(lambda: self.controller.open_page(index)))

    def close_page(self, confirmation_id: str | None) -> dict[str, Any]:
        return cast(dict[str, Any], self._call(lambda: self.controller.close_page(confirmation_id)))

    def confirm(self, action: str, body: Mapping[str, Any]) -> WriteConfirmation:
        return cast(WriteConfirmation, self._call(lambda: self.controller.confirm(action, body)))

    def act(self, action: str, body: Mapping[str, Any], confirmation_id: str | None) -> dict[str, Any]:
        return cast(dict[str, Any], self._call(lambda: self.controller.act(action, body, confirmation_id)))

    def settings_comm(self, key: str) -> dict[str, Any]:
        positions = ("p1", "p2", "p3", "p4")
        if key not in positions:
            raise InvalidArgument(f"没有位置 {key} 的设备")
        index = positions.index(key)
        return cast(dict[str, Any], self._call(lambda: self.controller.settings_comm(index)))

    def busy(self) -> bool:
        return self.controller.flags[0]

    def writing(self) -> bool:
        return self.controller.flags[1]

    def settings_left(self) -> None:
        self._call(self.controller.settings_left)

    def lowered(self) -> None:
        self._call(self.controller.lowered)

    def raised(self) -> None:
        self._call(self.controller.raised)
