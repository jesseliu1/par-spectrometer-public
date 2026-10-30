"""Tier 1 "接管采集" use cases (内部文档; D-212, D-213).

This layer holds the rules that need no Qt: the tier and its second confirmation, which requests the tier allows,
the takeover state the status bar shows, and the state cache the HTTP side reads. The takeover itself (V1.0.3's
single-instance lock, DeviceHub, PollingCoordinator) runs in par_app.acquisition_host on the service's Qt main
thread and is reached only through the `TakeoverBackend` protocol below; the HTTP side never touches a Qt object
or the coordinator (16_ 1.4).

Tier 0 refuses every acquisition request and every configuration write with 403 feature_disabled before anything
else is looked at.
"""

from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from ..database import format_beijing_time
from ..domain.clock import Clock
from .bus_trace import BusTrace
from .errors import (
    ApplicationError,
    Busy,
    ConfigUnavailable,
    ConfirmationRequired,
    DeviceNotFound,
    FeatureDisabled,
    InvalidArgument,
    NotRunning,
)
from .events import EventHub
from .faults import FaultLog
from .live_overview import LiveSource
from .paths import OUTSIDE_ALPHA, AlphaPaths
from .run_actions import (
    CONFIG_APPLIED,
    HALT_DETAILS,
    MAINTENANCE_TEXTS,
    applied_config,
    recorded,
    saved_devices,
)
from .run_events import RunEventLog
from .run_status import run_status
from .status_notices import CacheNotices
from .tier import (
    FACTORY_TIER,
    MAINTENANCE_TIER,
    TAKEOVER_TIER,
    Confirmation,
    Level,
    Takeover,
    TierConfirmations,
    TierStore,
    status_text,
)
from .timefmt import beijing_iso

if TYPE_CHECKING:
    from .maintenance import MaintenancePort

LOG = logging.getLogger(__name__)
DEVICE_POSITIONS = ("p1", "p2", "p3", "p4")
"""Positions of the registered devices in configuration order (the same keys as the tier-0 pages)."""
NO_BACKEND = "本服务入口不含采集功能（开发用的只读入口），请用 alpha 程序启动服务"
TIER_TOO_LOW = "当前为只读模式，未开启采集：请在“设置与导出”开启采集模式"
HALT_GUIDANCE_RESUME = (
    "恢复命令或运行状态未确认，所有设备的后台采集已停止，硬件实际状态尚不确定。\n"
    "请检查通信及设备运行状态，必要时重新上电，然后点“停止采集”，再点“开始采集”。\n\n"
)
HALT_GUIDANCE_HARDWARE = (
    "所有设备已停止采集，避免异常探头未采集而未被察觉。\n请为该设备重新上电，然后点“停止采集”，再点“开始采集”。\n\n"
)
HALT_CLOSING = "点击“确认”只关闭提示，不恢复采集；保存配置也不能解除停止。"
HALT_LOG_ERRORS = "\n\n部分停止记录未能写入数据库：\n"
STOP_CONFIRM = "停止采集后，本软件释放串口；正在进行的采集事务会先结束（最长约 40 秒）。确定停止采集？"
DOWN_CONFIRM = "切回只读模式后本软件不再连接设备。正在采集时会先停止采集并释放串口（最长约 40 秒）。确定切回只读模式？"
DOWN_TO_1_CONFIRM = (
    "关闭维护模式后维护页的设备操作全部关闭，尚未写入的校准修改会被丢弃；通信维护如未完成，采集保持暂停，"
    "恢复采集需要重新开启维护模式。确定关闭维护模式？"
)
"""17_ 6.1 (D-216 question 8): 2 -> 1 keeps maintenance as it is."""
STOP_IN_MAINTENANCE = "当前处于通信维护中，停止后维护状态与待核对写入保存在设备库中，下次开始采集会先进入维护停止。"
STOP_WHILE_WRITING = "设备写入正在进行，停止会中断本次通信，写入结果需在下次开始采集后核对。"
"""17_ section 7: added to the stop confirmation (stopping is always allowed, as quitting V1.0.3 is)."""
NOT_FROM_ZERO = "请先开启采集模式，再开启维护模式"
MAINTENANCE_BUSY = "设备维护任务尚未结束，暂不能关闭维护模式；请等待任务结束"
STOP_AFTER_HALT_NOTE = (
    "停止后再开始采集，等同于重新启动软件，不会改变设备的硬件状态。请先按下面的提示处理，"
    "必要时为设备重新上电，然后再开始采集。"
)
"""Added to the stop confirmation while a halt is shown (review Q1; D-212 q8 is the equivalence owner confirms)."""
BUSY_STOPPING = "正在开始或停止采集，请稍候再保存"
NOT_RUNNING_SAVE = "请先开始采集再保存配置：保存会立即应用到正在运行的采集"
RECONFIGURE_WAY_OUT = "。可在“设置与导出”的采集配置中恢复原文件后重试，或选择“以空配置重新配置…”"
"""Appended to a start refused with config_unavailable: the way out V1.0.3 offers at startup (D-220)."""
APPLY_FAILED_PREFIX = "应用配置失败："
"""PollingCoordinator.run() shows a failed apply_config (ConfigApplyError, D-178 B) as "应用配置失败：<原因>"."""


def halt_text(reason: Mapping[str, Any]) -> str:
    """V1.0.3's hardware-stop message (MainWindow._show_hardware_stop) word for word, except that "然后退出并重新启动
    软件" reads "然后点“停止采集”，再点“开始采集”" (alpha.5 wording): stopping and starting builds a new coordinator,
    which on the bus is the same as restarting V1.0.3 (D-212 question 8). Nothing here clears the halt."""
    guidance = HALT_GUIDANCE_RESUME if reason.get("resume_unconfirmed") else HALT_GUIDANCE_HARDWARE
    text = (
        f"{format_beijing_time(reason.get('occurred_at'))}\n"
        f"设备“{reason.get('name')}”（地址 {reason.get('slave_id')}）：{reason.get('reason')}。\n\n"
        f"{guidance}{HALT_CLOSING}"
    )
    errors = reason.get("log_errors")
    if errors:
        text += HALT_LOG_ERRORS + "\n".join(str(item) for item in errors)
    return text


def stop_text(halt: Mapping[str, Any] | None, maintenance: bool = False, writing: bool = False) -> str:
    """The "停止采集" confirmation; with a halt it repeats the halt text (review Q1), in maintenance and while a device
    write runs it says what stopping leaves behind (17_ section 7). Nothing here clears the halt."""
    text = STOP_CONFIRM
    if maintenance:
        text += f"\n\n{STOP_IN_MAINTENANCE}"
    if writing:
        text += f"\n\n{STOP_WHILE_WRITING}"
    if halt is None:
        return text
    return f"{text}\n\n{STOP_AFTER_HALT_NOTE}\n\n{halt_text(halt)}"


class StatusCache(CacheNotices):
    """What the HTTP side may know about the takeover. Written on the Qt main thread (the event bridge and the
    host), read from any thread; every read is a deep copy (16_ 1.4: HTTP reads the cache, never the coordinator).

    Every message the pages show passes through here, so this is where it becomes a numbered run event (#136): a new
    bus line, a device message that changed, a halt or a refused start is recorded once, and the entry keeps the
    event's `notice` ({event_id, occurred_at}) until its message changes again. The same message arriving again
    (a repeated snapshot) keeps the notice it had."""

    def __init__(self, clock: Clock, events: RunEventLog | None = None, trace: BusTrace | None = None) -> None:
        self._clock = clock
        self._events = events
        self._trace = trace
        self._lock = threading.Lock()
        self._takeover: Takeover = "released"
        self._lock_held = False
        self._error: str | None = None
        self._error_notice: dict[str, Any] | None = None
        self._bus: dict[str, Any] = {"level": "idle", "message": "未在采集", "notice": None}
        self._halt: dict[str, Any] | None = None
        self._maintenance = False
        self._devices: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._poll_cycle_seconds: float | None = None
        self._apply_error: str | None = None
        self._configured: bool | None = None

    @property
    def takeover(self) -> Takeover:
        with self._lock:
            return self._takeover

    def begin(self, expected: Takeover, new: Takeover) -> bool:
        """Move from `expected` to `new` atomically; False when the takeover is in another state."""
        with self._lock:
            if self._takeover != expected:
                return False
            self._moved(new)
            self._takeover = new
            return True

    def set_takeover(self, state: Takeover, lock_held: bool, error: str | None = None) -> None:
        with self._lock:
            if error is not None and error != self._error:
                self._error_notice = self._notice("takeover", "error", error, None, "error", state=state)
            elif error is None:
                self._error_notice = None
                self._pin("error")
            self._moved(state)
            self._takeover, self._lock_held, self._error = state, lock_held, error

    def reset(
        self, bus: tuple[str, str], devices: list[dict[str, Any]], maintenance: bool, poll: float, configured: bool
    ) -> None:
        with self._lock:
            self._set_bus(*bus)
            self._halt, self._maintenance, self._apply_error = None, maintenance, None
            self._pin("halt")
            self._configured = configured
            self._replace_devices(devices)
            self._poll_cycle_seconds = poll
            # the configuration a start runs with is in effect too (no config_applied at a start; review, PR #144)
            self._notice("config", "info", CONFIG_APPLIED, None, **applied_config(devices, poll, configured))

    def set_bus(self, level: str, message: str) -> None:
        """The bus line; a failed apply_config is also kept as `config_apply_error` until a configuration is applied
        or the next start (D-221: the page says the saved configuration has not taken effect)."""
        with self._lock:
            self._set_bus(level, message)
            if level == "error" and message.startswith(APPLY_FAILED_PREFIX):
                self._apply_error = message

    def set_devices(self, devices: list[dict[str, Any]], poll: float | None, configured: bool | None = None) -> None:
        """A configuration was applied (config_applied); `poll` and `configured` are None when unknown (R-1-6)."""
        with self._lock:
            self._configured = configured
            self._replace_devices(devices)
            self._poll_cycle_seconds = poll
            self._apply_error = None
            self._notice("config", "info", CONFIG_APPLIED, None, **applied_config(devices, poll, configured))

    def set_device(self, device: dict[str, Any]) -> None:
        with self._lock:
            key = str(device["key"])
            if key not in self._order:
                self._order.append(key)
            self._devices[key] = self._with_notice(device, self._devices.get(key))

    def set_halt(self, reason: dict[str, Any]) -> None:
        with self._lock:
            halt = copy.deepcopy(reason)
            details = {name: halt.get(name) for name in HALT_DETAILS}
            device = {"key": None, "name": halt.get("name"), "slave_id": halt.get("slave_id")}
            halt["notice"] = self._notice("halt", "error", str(halt.get("message")), device, "halt", **details)
            self._halt = halt

    # ------------------------------------------------------------------ run events (#136)
    def set_maintenance(self, maintenance: bool) -> None:
        with self._lock:
            if maintenance != self._maintenance:
                self._notice("maintenance", "warning" if maintenance else "info", MAINTENANCE_TEXTS[maintenance], None)
            self._maintenance = maintenance

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            devices = [self._devices[key] for key in self._order if key in self._devices]
            return copy.deepcopy(
                {
                    "takeover": self._takeover,
                    "lock_held": self._lock_held,
                    "error": self._error,
                    "error_notice": self._error_notice,
                    "bus": self._bus,
                    "halt": self._halt,
                    "maintenance": self._maintenance,
                    "poll_cycle_seconds": self._poll_cycle_seconds,
                    "config_apply_error": self._apply_error,
                    "configured": self._configured,
                    "devices": [
                        {**device, "position": DEVICE_POSITIONS[index] if index < len(DEVICE_POSITIONS) else None}
                        for index, device in enumerate(devices)
                    ],
                    "as_of": beijing_iso(self._clock.now()),
                }
            )


class TakeoverBackend(Protocol):
    """The Qt side (par_app.acquisition_host.HostBackend). Every method is safe to call from an HTTP thread."""

    def start(self, allowed: Callable[[], None]) -> None:
        """Start acquiring once the takeover reads "starting" (AcquisitionService.start moved it there): on the main
        thread call `allowed()` (raises when the tier no longer allows it), take the lock, build and start; raises
        InstanceLocked / ConfigUnavailable / Busy / FeatureDisabled, and the takeover then reads "released"."""

    def request_stop(self, then: Callable[[], None] | None = None) -> None:
        """Ask for the takeover to stop; returns at once. `then` runs on the main thread once the lock is released."""

    def apply_config(self, payload: Mapping[str, Any]) -> None:
        """DeviceHub.apply on the main thread; raises InvalidArgument (V1.0.3's own message) or NotRunning."""

    def reconfigure(self, payload: Mapping[str, Any]) -> None:
        """Save from an empty configuration with nothing taken over (D-220): V1.0.3's DeviceHub.apply with the
        original file backed up first; no lock, no port. Raises InvalidArgument, ConfigUnavailable or Busy."""

    def read_config(self) -> dict[str, Any]:
        """The alpha's tier-1 configuration file as the page shows it; never opens a database."""

    def import_preview(self, source: str) -> dict[str, Any]:
        """A draft from a V1.0.3 configuration (16_ 3.3); reads only, writes no file."""

    def serial_ports(self) -> dict[str, Any]:
        """The computer's serial ports as V1.0.3's settings page lists them ({"ports": [{value, label}], "hint"});
        enumerates only, opens no port (MAINT-051, #74)."""

    def shutdown(self) -> None:
        """Stop the takeover, if any, and wait for it (main thread only: service shutdown)."""


@dataclass(frozen=True)
class TierState:
    tier: int
    takeover: Takeover
    lock_held: bool
    text: str
    level: Level
    settings_path: str
    settings_problem: str | None
    stop_text: str
    down_text: str
    down_to_1_text: str
    maintenance: bool
    fault: dict[str, Any] | None


class AcquisitionService:
    def __init__(self, paths: AlphaPaths, clock: Clock, events: EventHub) -> None:
        self.paths = paths
        self.clock = clock
        self.events = events
        self.tiers = TierStore(paths.config_dir)
        self.confirmations = TierConfirmations(clock)
        self.run_events = RunEventLog(paths.logs_dir, clock)
        self.bus_trace = BusTrace(clock)  # installed by the service (service_main); #136 steps 2 and 3
        self.cache = StatusCache(clock, self.run_events, self.bus_trace)
        self.faults = FaultLog(clock, events)
        self.backend: TakeoverBackend | None = None
        self.maintenance: MaintenancePort | None = None
        self.closing = False
        self._tier_lock = threading.Lock()
        self._unavailable: ConfigUnavailable | None = None
        """The last start refused with config_unavailable (a database failed V1.0.3's startup check, which only a
        start runs); cleared by a successful start or reconfiguration (D-220)."""

    def attach(self, backend: TakeoverBackend, maintenance: MaintenancePort | None = None) -> None:
        self.backend = backend
        self.maintenance = maintenance

    # ------------------------------------------------------------------ tier
    def tier(self) -> int:
        return self.tiers.tier()

    def state(self) -> TierState:
        snapshot = self.cache.snapshot()
        tier = self.tier()
        maintenance = bool(snapshot["maintenance"]) and snapshot["takeover"] == "running"
        unregistered = snapshot["configured"] is False  # None (unknown) keeps "正在采集"
        text, level = status_text(tier, snapshot["takeover"], snapshot["halt"] is not None, maintenance, unregistered)
        writing = self.maintenance.writing() if self.maintenance is not None else False
        return TierState(
            tier=tier,
            takeover=snapshot["takeover"],
            lock_held=bool(snapshot["lock_held"]),
            text=text,
            level=level,
            settings_path=str(self.tiers.path),
            settings_problem=self.tiers.problem,
            stop_text=stop_text(snapshot["halt"], maintenance, writing),
            down_text=DOWN_CONFIRM,
            down_to_1_text=DOWN_TO_1_CONFIRM,
            maintenance=maintenance,
            fault=self.faults.last(),
        )

    def publish_state(self, name: str = "takeover_state") -> None:
        state = self.state()
        data = {"tier": state.tier, "state": state.takeover, "lock_held": state.lock_held, "text": state.text}
        if name == "takeover_state":
            data["error"] = self.cache.snapshot()["error"]
        self.events.publish(name, data)

    def confirm(self, tier: int) -> Confirmation:
        self._writable()
        if tier == MAINTENANCE_TIER and self.tier() < TAKEOVER_TIER:
            raise ConfirmationRequired(NOT_FROM_ZERO)  # 17_ 6.1: only 1 -> 2
        return self.confirmations.issue(tier)

    def set_tier(self, tier: int, confirmation_id: str | None) -> bool:
        """True when the tier is written now; False when a running takeover is stopped first (202)."""
        return bool(recorded(self.run_events, "set_tier", partial(self._set_tier, tier, confirmation_id), tier=tier))

    def _set_tier(self, tier: int, confirmation_id: str | None) -> bool:
        """`set_tier` without its run events.

        Lowering to 0 stops a running takeover first, also when the tier already reads 0 (settings file changed or
        unreadable while acquiring; review M2): tier 0 with a takeover running is never left as it is."""
        self._writable()
        with self._tier_lock:
            current = self.tier()
            if tier == current and (tier != FACTORY_TIER or self.cache.takeover == "released"):
                return True
            if tier == MAINTENANCE_TIER:
                if current < TAKEOVER_TIER:
                    raise ConfirmationRequired(NOT_FROM_ZERO)
                self.confirmations.consume(confirmation_id, tier)
                if self.maintenance is not None:
                    self.maintenance.raised()
                self._write_tier(tier)
                return True
            if tier == TAKEOVER_TIER and current == MAINTENANCE_TIER:
                self._lower_to_1()
                return True
            if tier == TAKEOVER_TIER:
                self.confirmations.consume(confirmation_id, tier)
                self._write_tier(tier)
                return True
            if tier != FACTORY_TIER:
                raise InvalidArgument("档位只能是 0、1 或 2")
            takeover = self.cache.takeover
            if takeover == "released":
                self._write_tier(tier)
                return True
            if takeover != "running" or self.backend is None:
                raise Busy("正在开始或停止采集，请稍后再切换模式")
            self.backend.request_stop(then=self._lowered)
            return False

    def _lower_to_1(self) -> None:
        """2 -> 1 (17_ 6.1): refused while a maintenance task runs; otherwise the draft goes and maintenance stays.
        `lowered` decides "busy" again on the main thread and stops every maintenance call there before the tier is
        written (review M2)."""
        if self.maintenance is not None:
            if self.maintenance.busy():
                raise Busy(MAINTENANCE_BUSY)
            self.maintenance.lowered()
        self._write_tier(TAKEOVER_TIER)

    def _lowered(self) -> None:
        """`then` of the stop asked by set_tier(0): runs on the main thread after the lock was released and while the
        takeover still reads "stopping", so no start can be accepted before tier 0 is written (review M1)."""
        with self._tier_lock:
            self._write_tier(FACTORY_TIER)

    def lower_after_fault(self) -> None:
        """`then` of the stop that follows an unexpected error on the main thread (D-225 item 1). Since issue #119
        (负责人 2026-10-27) the tier stays as it is: acquisition is only stopped, "开始采集" starts it again and the
        next start of the service acquires as usual. Kept as the stop's `then` so the page reads the state again."""
        self.publish_state("tier_changed")

    def _write_tier(self, tier: int) -> None:
        self.tiers.write(tier)
        self.publish_state("tier_changed")

    def _writable(self) -> None:
        if self.closing:
            raise Busy("服务正在关闭")

    # ----------------------------------------------------------- takeover
    def _backend(self, while_taken_over: bool = False) -> TakeoverBackend:
        """The backend when the tier allows the request. `while_taken_over`: stopping and reading the status are
        also allowed in tier 0 while a takeover is not released (they only lower what the alpha does; review M2),
        so a takeover can always be seen and stopped; with nothing taken over tier 0 refuses them as before."""
        if self.tier() < TAKEOVER_TIER and not (while_taken_over and self.cache.takeover != "released"):
            raise FeatureDisabled(TIER_TOO_LOW)
        if self.backend is None:
            raise ConfigUnavailable(NO_BACKEND)
        return self.backend

    def _allowed(self) -> None:
        """Checked again on the main thread right before the lock is taken (review M1)."""
        if self.closing:
            raise Busy("服务正在关闭")
        if self.tier() < TAKEOVER_TIER:
            raise FeatureDisabled(TIER_TOO_LOW)

    def start(self) -> None:
        recorded(self.run_events, "start", self._start)

    def _start(self) -> None:
        self._writable()
        with self._tier_lock:  # the tier check and the move to "starting" are one step (review M1)
            backend = self._backend()
            if not self.cache.begin("released", "starting"):
                raise Busy("已在采集" if self.cache.takeover == "running" else "正在开始或停止采集，请稍候")
        try:
            backend.start(self._allowed)
        except ConfigUnavailable as error:
            self._unavailable = error
            raise ConfigUnavailable(error.message + RECONFIGURE_WAY_OUT, error.detail) from error
        self._unavailable = None

    def auto_start(self) -> bool:
        """Issue #92 (overturns D-212 question 2): once tier 1 is on, the service starts the takeover when it starts,
        as V1.0.3 acquires as soon as it is opened. Tier 0 stays read-only. A refusal (V1.0.3 holds the lock, the
        configuration is unavailable, ...) is left on the status exactly as a refused "开始采集" leaves it; the
        service goes on and the user can start by hand. True when the takeover started."""
        if self.tier() < TAKEOVER_TIER:
            return False
        try:
            recorded(self.run_events, "auto_start", self._start)
        except ApplicationError as error:
            LOG.info("automatic start refused: %s", error.message)
            return False
        return True

    def stop(self) -> None:
        def run() -> None:
            self._writable()
            self._backend(while_taken_over=True).request_stop()

        recorded(self.run_events, "stop", run)

    def status(self) -> dict[str, Any]:
        self._backend(while_taken_over=True)
        snapshot = self.cache.snapshot()
        snapshot["run_status"] = run_status(snapshot)  # the top bar's V1.0.3 block (issue #73); read only
        snapshot["event_log"] = self.run_events.health()  # the page says when records were lost (#136)
        return snapshot

    def config(self) -> dict[str, Any]:
        """The configuration view; `problem` also names a database the last start found unusable (D-220)."""
        view = self._backend().read_config()
        recorded = self._unavailable
        if view.get("problem") is None and recorded is not None:
            view["problem"] = {"message": recorded.message, "detail": recorded.detail}
        return view

    def import_preview(self, source: str) -> dict[str, Any]:
        return self._backend().import_preview(source)

    def serial_ports(self) -> dict[str, Any]:
        """For the 计算机串口 list of the configuration form: gated like `config()` (tier 1 or 2, 403 in tier 0)."""
        return self._backend().serial_ports()

    def save_config(self, payload: Mapping[str, Any]) -> None:
        name = "reconfigure" if payload.get("reconfigure") is True else "save_config"
        recorded(self.run_events, name, partial(self._save_config, payload), devices=saved_devices(payload))

    def _save_config(self, payload: Mapping[str, Any]) -> None:
        self._writable()
        backend = self._backend()
        takeover = self.cache.takeover
        if takeover == "released":
            # D-220: with the configuration unusable, `reconfigure` saves from an empty configuration (V1.0.3's
            # "重新配置", the original file backed up first) without a takeover; otherwise a save needs one (D-214 q5)
            if payload.get("reconfigure") is not True or self.config().get("problem") is None:
                raise NotRunning(NOT_RUNNING_SAVE)
            backend.reconfigure(payload)
            self._unavailable = None
            return
        if takeover != "running":
            raise Busy(BUSY_STOPPING)  # 16_ 7.5: other writes are busy while starting or stopping
        backend.apply_config(payload)

    def device_database(self, key: str, config: Mapping[str, Any] | None = None) -> tuple[str, Path]:
        """Name and database of the device at position `key` of the alpha's configuration (`config`, or the one read
        now); refused when the database is outside the alpha's devices folder, before anything is opened (review
        B1)."""
        config = self.config() if config is None else config
        devices = config["devices"]
        if key not in DEVICE_POSITIONS or DEVICE_POSITIONS.index(key) >= len(devices):
            problem = config.get("problem")
            if problem is not None and not devices:  # the file cannot be read: say so, not "no such device"
                raise ConfigUnavailable(str(problem["message"]), problem.get("detail"))
            raise DeviceNotFound(f"采集配置中没有位置 {key} 的设备", key)
        device = devices[DEVICE_POSITIONS.index(key)]
        path = Path(str(device["database_path"]))
        if not (device.get("inside_alpha") and self.paths.holds_device_database(path)):
            # The live read opens with mode=ro, not immutable=1: on another program's WAL database SQLite may create
            # -wal/-shm beside it. Refused before anything is opened, as start and save refuse it (review B1).
            raise ConfigUnavailable(OUTSIDE_ALPHA.format(path=path, directory=self.paths.devices_dir))
        return str(device["name"]), path

    def paused(self) -> bool:
        """Nothing acquires now: as V1.0.3's overview reads it (maintenance or a halt), and also while the alpha has
        not taken over (D-213)."""
        snapshot = self.cache.snapshot()
        return snapshot["takeover"] != "running" or bool(snapshot["maintenance"]) or snapshot["halt"] is not None

    def live_source(self, key: str) -> LiveSource:
        """The device at position `key` of the alpha's configuration, paused as `paused` says."""
        config = self.config()  # one read: the name, the database and the poll cycle belong together (PR #95 review)
        name, path = self.device_database(key, config)
        return LiveSource(name, path, float(config["poll_cycle_seconds"]), self.paused())
