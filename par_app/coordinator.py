"""多设备串行调度器：单条 Modbus 链路上分时轮询最多 4 台光谱仪。

设计要点
--------
1. **单线程串行**：RS-485 / RTU 是同一条半双工总线，同一时刻只能有一个
   "请求—响应"事务，因此不做多线程并发读取，而是用一个后台线程按顺序
   遍历启用设备，天然满足分时读取要求。
2. **每台独立数据库**：每台设备持有自己的 ParDatabase，数据完全隔离。
3. **失效隔离**：每周期尝试一次；勾选“失败停止”的设备连续十次失败后退出本次采集
   （默认不勾选，按轮询周期持续重试并在恢复后自动继续），不影响其它设备。
4. **分别对时**：每个设备各自下发对时，结果写入各自的库。
"""

from __future__ import annotations

import json
import queue
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from par_app.qt_compat import QThread, pyqtSignal

from .database import ParDatabase, beijing_now, format_beijing_time
from .domain.clock import Clock, SystemClock
from .math_ops import software_metrics
from .maintenance import REJOIN_VERIFICATION_MESSAGE, CommunicationMaintenance, check_manual_task
from .models import MAX_DEVICES, AppConfig, BusConfig, ConnectionConfig, DeviceConfig, DeviceStatus
from .protocol import AcquisitionResumeError, CommunicationCancelled, CommunicationTimeout, HardwareStateError, ParModbusClient, ProtocolError


DEVICE_TRANSACTION_BUDGET_SECONDS = 10.0
ACQUISITION_TRANSACTION_BUDGET_SECONDS = 40.0
MAX_CONSECUTIVE_FAILURES = 10
BUS_RETRY_INTERVAL_SECONDS = 5.0  # 总线级重连间隔（秒）。
TIME_SYNC_INTERVAL_SECONDS = 3600.0  # 对时节流（秒）：沿用原单设备实现的小时级节奏。


@dataclass
class DeviceRuntimeState:
    """单台设备的运行时状态（内存态），供调度器与 UI 共同读取。"""

    key: str
    config: DeviceConfig
    connection: ConnectionConfig
    database: ParDatabase
    online: bool = False
    level: str = "idle"
    message: str = "尚未采集"
    failures: int = 0
    excluded: bool = False
    last_failure_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    last_elapsed_ms: float = 0.0
    last_sync_at: float | None = None  # 上次对时的单调时钟时刻；None＝本次运行尚未对时（旧仓库 #5）
    latest_points: list[int] | None = None
    latest_metrics: dict | None = None
    latest_status: DeviceStatus | None = None
    latest_record_id: int | None = None
    device_identity: dict | None = None
    resume_pending: bool = False  # D-101：上次冻结事务整次无应答，下一次采集先补发一次恢复命令
    tags: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        """返回给 UI 的轻量快照（不含 701 点光谱本身）。"""
        return {
            "key": self.key, "name": self.config.name, "slave_id": self.config.slave_id, "enabled": self.config.enabled,
            "online": self.online, "level": self.level, "message": self.message, "failures": self.failures,
            "excluded": self.excluded, "last_failure_at": self.last_failure_at, "last_success_at": self.last_success_at,
            "last_error": self.last_error, "last_elapsed_ms": self.last_elapsed_ms,
            "latest_record_id": self.latest_record_id,
            "exposure_status": self.latest_status.exposure_status if self.latest_status is not None else None,
            "database_path": str(self.database.path), "identity": self.device_identity}


def device_keys(devices: list[DeviceConfig]) -> list[str]:
    """设备标识：默认用设备名；若重名则追加从站地址保证唯一。"""
    counts: dict[str, int] = {}
    for device in devices:
        counts[device.name] = counts.get(device.name, 0) + 1
    keys: list[str] = []
    for device in devices:
        keys.append(device.name if counts[device.name] == 1 else f"{device.name}#{device.slave_id}")
    return keys


def _frame_timeout(budget: float) -> float:
    """把 10 秒设备预算折算成单帧超时，避免一台缺失设备拖满整轮。"""
    return max(0.8, min(1.5, budget / 4.0))


class ConfigApplyError(RuntimeError):
    """应用配置失败且已恢复原配置（D-178 B）；run() 原样显示其文本，不加“调度异常”前缀。"""


class PollingCoordinator(QThread):
    """按轮询周期串行采集所有启用设备。"""

    bus_state_changed = pyqtSignal(str, str)              # level, message
    bus_config_changed = pyqtSignal(object)
    config_applied = pyqtSignal(object)
    acquisition_halted = pyqtSignal(dict)
    maintenance_changed = pyqtSignal(bool)
    device_state_changed = pyqtSignal(str, dict)          # key, snapshot
    device_alert = pyqtSignal(str, str, str)              # key, name, detail
    acquisition_saved = pyqtSignal(str, int)              # key, record_id
    task_finished = pyqtSignal(str, str, bool, object)    # key, kind, ok, result

    def __init__(self, app_config: AppConfig, parent=None, *, clock: Clock | None = None):
        super().__init__(parent)
        self._clock: Clock = clock if clock is not None else SystemClock()  # 唯一时间来源，也传给总线客户端（R-1-6）
        self._config = deepcopy(app_config)
        self._running = True
        self._halt_reason: dict | None = None
        self._maintenance = False
        self._maintenance_sessions = {}
        self._states: dict[str, DeviceRuntimeState] = {}
        self._order: list[str] = []
        self._cycle_index = 0
        self._retired_states: dict[Path, DeviceRuntimeState] = {}
        self._tasks: queue.Queue[tuple[str, str, object]] = queue.Queue()
        self._client: ParModbusClient | None = None
        self._unreleased: dict[ParModbusClient, str] = {}  # close() 失败、尚未释放的连接及原因（DEF-06）
        self._next_cycle_at = 0.0
        self._next_bus_retry_at = 0.0
        self._pause_until = 0.0  # 维护任务（写入设备通信参数等）执行前暂停轮询，避免总线时序被打断。
        self._bus_message = "尚未连接"
        self._bus_level = "idle"
        self._rebuild_states()
        self._maintenance = any(session.blocks_startup for session in self._maintenance_sessions.values())

    def pause_polling(self, seconds: float) -> None:
        self._pause_until = max(self._pause_until, self._clock.monotonic() + float(seconds))
        self._next_cycle_at = self._pause_until

    # ---------------------------------------------------------------- 生命周期
    def stop(self) -> None:
        self._running = False
        self.wait()

    def enter_maintenance(self) -> None:
        self.queue_task("", "maintenance_enter")

    def leave_maintenance(self) -> None:
        self.queue_task("", "maintenance_leave")

    def run(self) -> None:
        while self._running:
            try:
                self._process_tasks()
                if not self._running:
                    break
                if self._maintenance or self._halt_reason or not self._config.configured or not self._config.enabled_devices():
                    self._clock.sleep(0.05)
                    continue
                if self._clock.monotonic() < self._pause_until:
                    self._clock.sleep(0.1)
                    continue
                now = self._clock.monotonic()
                if now >= self._next_cycle_at:
                    round_cycle, restart_at_once = self._cycle_seconds(), False  # 本轮配置的周期（DEF-02）
                    self._ensure_bus_connected()  # 连接时抛异常不进入本轮，照 V1.0.2 约 1 秒后重试（DEF-28 ②）
                    try:  # 异常结束的一轮（含轮内 apply_config 失败）也从本轮开始计满周期，不补跑
                        restart_at_once = self._poll_all_devices()  # apply_config 中断本轮则下一轮立即开始
                    finally:
                        if not restart_at_once:
                            self._next_cycle_at = max(now + round_cycle, self._clock.monotonic())
                self._clock.sleep(0.05)
            except Exception as exc:  # 调度层自身异常绝不允许终止线程
                self._set_bus_state("error", str(exc) if isinstance(exc, ConfigApplyError) else f"调度异常：{exc}")
                self._disconnect_bus()
                self._clock.sleep(1.0)
        self._disconnect_bus()

    # ------------------------------------------------------------ 配置与状态
    def apply_config(self, app_config: AppConfig) -> None:
        self.queue_task("", "apply_config", deepcopy(app_config))

    def _apply_config(self, app_config: AppConfig) -> None:
        """应用新的总线/设备登记；设备增删或库路径变化时重建运行时状态。重建失败则恢复原配置（D-178 B）。"""
        previous, self._config = self._config, app_config
        self._disconnect_bus()
        try:
            self._rebuild_states()  # 失败时运行时状态未被改动
        except Exception as exc:
            self._config = previous
            raise ConfigApplyError(f"应用配置失败：{exc}") from exc
        self._next_cycle_at = self._next_bus_retry_at = 0.0
        self.config_applied.emit(deepcopy(app_config))

    def _rebuild_states(self) -> None:
        """先为新配置建好全部状态（可能抛错，此时不改任何现有对象），再一并提交（D-178）。"""
        retired = {**self._retired_states, **{state.database.path.resolve(): state for state in self._states.values()}}
        keys = device_keys(self._config.devices)
        states: dict[str, DeviceRuntimeState] = {}
        reused: list[tuple[DeviceRuntimeState, str, DeviceConfig, ConnectionConfig]] = []
        sessions: dict[Path, CommunicationMaintenance] = {}
        for index, (key, device) in enumerate(zip(keys, self._config.devices, strict=True)):
            database_path, connection = device.resolved_database_path(index), self._connection_for(index, device)
            if (existing := retired.get(Path(database_path).resolve())) is not None:
                states[key] = existing
                reused.append((existing, key, device, connection))
                continue
            state = states[key] = DeviceRuntimeState(key=key, config=device, database=ParDatabase(database_path),
                                                     connection=connection)
            # D-132：只加载登记设备的会话；D-131：重新登记时会话未完成仍须先核对。
            if (session := CommunicationMaintenance(state.database, device.name)).unfinished:
                sessions[state.database.path.resolve()] = session
        for existing, key, device, connection in reused:  # 以下不再抛错
            existing.key, existing.config, existing.connection = key, device, connection
            if existing.excluded and not device.auto_stop_on_failure:
                # 取消“失败停止”即解除本次退出状态，按周期重试、无需重启；失败计数与历史日志保留。
                existing.excluded, existing.level = False, "warning"
                existing.message = "已取消“失败停止”，恢复按周期重试"
                try:
                    existing.database.set_runtime_status(existing.level, existing.message)
                except Exception:
                    pass
        self._retired_states, self._states, self._order = retired, states, keys  # zip(strict) 保证 keys 即顺序
        self._maintenance_sessions.update(sessions)

    def _connection_for(self, index: int, device: DeviceConfig) -> ConnectionConfig:
        connection = self._config.bus.to_connection(device.slave_id, device.resolved_database_path(index))
        connection.timeout_seconds = _frame_timeout(self._transaction_budget())
        return connection

    def _transaction_budget(self) -> float:
        """维护/诊断/身份等常规事务预算（保持原 10 秒不变）。"""
        return DEVICE_TRANSACTION_BUDGET_SECONDS

    def _acquisition_budget(self) -> float:
        """采集轮预算：须容纳两组（必要时三组）完整读取 + 每组后的 MCU 时钟读取。"""
        return ACQUISITION_TRANSACTION_BUDGET_SECONDS

    def _cycle_seconds(self) -> float:
        return self._config.effective_poll_cycle_seconds()

    def state(self, key: str) -> DeviceRuntimeState | None:
        return self._states.get(key)

    def states(self) -> list[DeviceRuntimeState]:
        return [self._states[key] for key in self._order if key in self._states]

    def database(self, key: str) -> ParDatabase | None:
        state = self._states.get(key)
        return state.database if state else None

    def bus_message(self) -> tuple[str, str]:
        return self._bus_level, self._bus_message

    def halt_reason(self) -> dict | None:
        return deepcopy(self._halt_reason)

    def _halt_acquisition(self, source: DeviceRuntimeState, error: HardwareStateError | AcquisitionResumeError) -> None:
        if self._halt_reason is not None:
            return
        hardware_status = error.status if isinstance(error, HardwareStateError) else None
        if hardware_status is not None:
            source.latest_status = hardware_status
        reason = {
            "name": source.config.name, "slave_id": source.config.slave_id,
            "occurred_at": beijing_now(), "reason": str(error),
            "initialized": hardware_status.initialized if hardware_status is not None else None,
            "need_power_cycle": hardware_status.need_power_cycle if hardware_status is not None else None,
            "resume_unconfirmed": isinstance(error, AcquisitionResumeError), "cycle": self._cycle_index}
        message = f"采集停止中：{source.config.name}（地址 {source.config.slave_id}）{error}；所有设备的后台采集已停止"
        reason["message"] = message
        self._halt_reason = reason
        self._disconnect_bus()
        log_errors = []
        for state in self.states():
            if not state.config.enabled:
                continue
            state.online, state.level, state.message = False, "power", message
            for action in (
                lambda: state.database.diagnostic("ERROR", "acquisition_halted", message,
                                                  **{key: value for key, value in reason.items() if key != "message"}),
                lambda: state.database.set_runtime_status("power", message),
                lambda: state.database.save_dli_interruption(message)):
                try:
                    action()
                except Exception as exc:
                    log_errors.append(f"{state.config.name}：{exc}")
            self._emit_state(state)
        reason["log_errors"] = log_errors
        self._set_bus_state("error", message)
        self.acquisition_halted.emit(deepcopy(reason))

    def queue_task(self, key: str, kind: str, payload: object = None) -> None:
        self._tasks.put((key, kind, payload))

    # ---------------------------------------------------------------- 总线连接
    def _set_bus_state(self, level: str, message: str) -> None:
        self._bus_level, self._bus_message = level, message
        self.bus_state_changed.emit(level, message)

    def _disconnect_bus(self) -> str:  # 返回关闭失败原因，空串表示全部已释放；失败的连接保留，下次再关（DEF-06）
        pending, self._client, self._unreleased = [*self._unreleased, self._client], None, {}
        for client in filter(None, pending):
            try:
                client.close()
            except Exception as exc:
                self._unreleased[client] = str(exc) or type(exc).__name__
        for state in self._states.values():
            if state.online:
                state.online, state.level, state.message = False, "offline", "总线已断开"
                self._emit_state(state)
        return "；".join(self._unreleased.values())

    def _enter_maintenance(self, key: str, kind: str) -> None:  # MAINT-080/107：连接释放后才进入维护
        if error := self._disconnect_bus():
            self.task_finished.emit(key, kind, False, f"采集连接关闭失败：{error}")
            return
        self._maintenance = True
        self._set_bus_state("warning", "维护模式：采集、对时和自动重连已停止")
        self.maintenance_changed.emit(True)

    def _ensure_bus_connected(self) -> bool:
        if self._maintenance or self._halt_reason is not None:
            return False
        if self._states and not any(state.config.enabled and not state.excluded for state in self.states()):
            return False
        if self._client is not None:
            return True
        if self._clock.monotonic() < self._next_bus_retry_at:
            return False
        bus = self._config.bus
        self._set_bus_state("warning", f"正在连接 {bus.serial_port if bus.transport == 'rtu' else f'{bus.host}:{bus.tcp_port}'} …")
        client = ParModbusClient(self._bus_connection(), clock=self._clock)
        if client.connect():
            self._client = client
            self._set_bus_state("ok", "总线已连接")
            return True
        client.close()
        self._next_bus_retry_at = self._clock.monotonic() + BUS_RETRY_INTERVAL_SECONDS
        detail = getattr(client, "last_connection_error", "")
        message = f"总线连接失败：{detail}" if isinstance(detail, str) and detail else "总线连接失败，稍后自动重试"
        self._set_bus_state("error", message)
        return False

    def _bus_connection(self) -> ConnectionConfig:
        first = self._config.devices[0].slave_id if self._config.devices else 1
        connection = self._config.bus.to_connection(first)
        connection.timeout_seconds = _frame_timeout(self._transaction_budget())
        return connection

    # ---------------------------------------------------------------- 轮询
    def _poll_all_devices(self) -> bool:
        """串行采集一轮再对时；返回 True 表示本轮因 apply_config 中断，下一轮应立即开始。"""
        if self._maintenance or self._halt_reason is not None:
            return False
        self._cycle_index += 1
        config = self._config
        for key in list(self._order):
            if self._handle_tasks_between_devices(config):
                return self._config is not config
            state = self._states.get(key)
            if state is None or not state.config.enabled or state.excluded or self._awaiting_verification(state):
                continue
            self._poll_one(state)
        for state in self.states():
            if self._handle_tasks_between_devices(config):
                return self._config is not config
            if state.config.enabled and not state.excluded and state.online:
                self._sync_time_if_due(state)
        if self._states and not any(state.online for state in self.states() if state.config.enabled):
            self._disconnect_bus()
        return False

    def _handle_tasks_between_devices(self, config: AppConfig) -> bool:
        self._process_tasks()  # 副作用：就地执行排队任务（硬件 I/O、apply_config、维护）；返回 True 即中断本轮
        return not self._running or self._halt_reason is not None or self._maintenance or self._config is not config

    def _poll_one(self, state: DeviceRuntimeState) -> None:
        if self._maintenance or self._halt_reason or state.excluded or not state.config.enabled:
            return
        if self._client is None:
            detail = self._bus_message if self._bus_level == "error" else "总线未连接"
            self._mark_failed(state, detail)
            return
        client = self._client
        client.set_slave_id(state.config.slave_id, resume_first=state.resume_pending)
        started = self._clock.monotonic()
        try:
            captured = self._capture_once(state)
            elapsed = self._clock.monotonic() - started
            if captured:
                self._mark_ok(state, elapsed)
        except CommunicationCancelled:
            return
        except (HardwareStateError, AcquisitionResumeError) as exc:
            self._halt_acquisition(state, exc)
        except Exception as exc:
            self._mark_failed(state, str(exc))  # 含 D-101 静默设备：按普通通信失败计数、按周期重试
        finally:
            state.resume_pending = client.last_transaction_silent

    def _awaiting_verification(self, state: DeviceRuntimeState) -> bool:
        """D-131：重新启用或登记的设备库中维护会话未完成时，核对前不参与采集，并提示一次。"""
        session = self._maintenance_sessions.get(state.database.path.resolve())
        if session is None or not session.unfinished:
            return False
        if state.message != REJOIN_VERIFICATION_MESSAGE:
            state.online, state.level, state.message = False, "warning", REJOIN_VERIFICATION_MESSAGE
            self._emit_state(state)
            state.database.diagnostic("WARNING", "communication_maintenance", REJOIN_VERIFICATION_MESSAGE,
                                      device_name=state.config.name, pending=bool(session.pending))
        return True

    def _mark_ok(self, state: DeviceRuntimeState, elapsed: float) -> None:
        if state.excluded:
            return
        if state.failures:
            state.database.diagnostic("INFO", "communication_recovery", "通信已恢复", name=state.config.name,
                                      slave_id=state.config.slave_id, previous_failures=state.failures, cycle=self._cycle_index)
        state.online = True
        state.failures = 0
        state.last_failure_at = None
        state.last_elapsed_ms = elapsed * 1000
        state.last_error = None
        state.database.set_runtime_status(state.level, state.message)
        self._emit_state(state)

    def _mark_failed(self, state: DeviceRuntimeState, detail: str) -> None:
        if state.excluded:
            return
        if state.failures == 0:  # 首次失败记录为 DLI 中断，保持与原单设备实现一致的统计口径。
            try:
                state.database.save_dli_interruption(detail)
            except Exception:
                pass
        state.failures += 1
        state.last_failure_at = beijing_now()
        # 只有显式勾选“失败停止”的设备才在达到上限后退出本次采集；否则一直重试。
        stop_on_failure = bool(state.config.auto_stop_on_failure)
        state.excluded = stop_on_failure and state.failures >= MAX_CONSECUTIVE_FAILURES
        state.online = False
        state.last_error = detail
        state.level = "error" if state.excluded else "warning"
        if stop_on_failure:
            state.message = f"连续第 {state.failures}/{MAX_CONSECUTIVE_FAILURES} 次尝试失败：{detail}"
            if state.excluded:
                state.message += "；已退出本次采集，重启软件后重新尝试"
        else:
            state.message = f"连续第 {state.failures} 次尝试失败：{detail}（未启用失败停止，将继续按周期重试）"
        try:
            state.database.set_runtime_status(state.level, state.message)
            state.database.diagnostic("ERROR" if state.excluded else "WARNING", "communication", state.message,
                                      name=state.config.name, slave_id=state.config.slave_id,
                                      attempt=state.failures, cycle=self._cycle_index, excluded=state.excluded,
                                      attempted_at=state.last_failure_at, reason=detail)
        except Exception as exc:
            state.message += f"；异常日志写库失败：{exc}"
        self._emit_state(state)

    def _emit_state(self, state: DeviceRuntimeState) -> None:
        self.device_state_changed.emit(state.key, state.snapshot())

    def _capture_once(self, state: DeviceRuntimeState) -> bool:
        """单次完整采集；曝光状态仅记录，不触发复采或决定 DLI 资格。"""
        assert self._client is not None
        client = self._client
        database = state.database
        started = self._clock.monotonic()
        acquired_at = beijing_now()
        quality = dict(strategy='single_capture', acquisition_status='incomplete', round_started_at=acquired_at,
                       groups=[], selected_group=None, attempted_groups=0, completed_groups=0, timed_out=False)
        try:
            mcu_time_ms = None
            try:
                with client.acquisition_budget(self._acquisition_budget(), lambda: not self._running):
                    client._check_budget()
                    quality['attempted_groups'] = 1
                    acquired_at = beijing_now()
                    status, points, params = client.read_spectrum_transaction()
                    if not status.initialized or status.need_power_cycle:
                        raise HardwareStateError(status)
                    if len(points) != 701:
                        raise ProtocolError('光谱点数不完整')
                    group_finished_at = beijing_now()
                    metrics = software_metrics(points, status.spectral_coefficient)
                    quality['groups'].append(dict(group=1, started_at=acquired_at, finished_at=group_finished_at))
                    quality.update(completed_groups=1, selected_group=1)
                    mcu_time_ms = client.read_standard_time()
            except (ProtocolError, OSError) as exc:  # 光谱已读完后读时钟失败或软件停止：保存光谱（D-155）
                if not quality['completed_groups'] or isinstance(exc, (HardwareStateError, AcquisitionResumeError)):
                    raise
                if mcu_time_ms is None:
                    quality['groups'][0]['clock_error'] = str(exc) if self._running else '软件停止'
                quality['timed_out'] |= isinstance(exc, CommunicationTimeout)
            quality['acquisition_status'] = 'completed'
            quality['selected_started_at'] = acquired_at
            quality['selected_finished_at'] = group_finished_at
            quality['poll_cycle_seconds'] = self._config.effective_poll_cycle_seconds()
            state.latest_status = status
            elapsed = (self._clock.monotonic() - started) * 1000
            record_id = database.save_acquisition({
                "acquired_at": acquired_at, "mcu_time_ms": mcu_time_ms, "success": 1,
                "initialized": int(status.initialized), "need_power_cycle": int(status.need_power_cycle),
                "raw_data_valid": int(status.raw_data_valid), "calculate_data_valid": int(status.calculate_data_valid),
                "stop_status": status.stop_status, "spectral_coefficient": status.spectral_coefficient,
                "exposure_status": status.exposure_status, "exposure_time_us": status.exposure_time_us,
                "software_metrics_json": json.dumps(metrics), "mcu_params_json": json.dumps(params),
                "error_stage": None, "error_detail": None, "elapsed_ms": elapsed, "raw_points": points,
                "quality_json": json.dumps(quality, ensure_ascii=False), "dli_eligible": 1})
            state.latest_points = list(points)
            state.latest_metrics = metrics
            state.latest_record_id = record_id
            state.last_success_at = acquired_at
            exposure = "正常" if status.exposure_status == 0 else ("过曝光" if status.exposure_status == 1 else "欠曝光")
            state.level = "ok"
            state.message = f"采集成功 #{record_id}，{exposure}，单次读取完成"
            state.last_elapsed_ms = elapsed
            self.acquisition_saved.emit(state.key, record_id)
            return True
        except (CommunicationCancelled, HardwareStateError, AcquisitionResumeError):
            raise
        except Exception as exc:
            if not self._running and isinstance(exc, (ProtocolError, OSError)):
                raise CommunicationCancelled('通信已取消') from exc
            quality['timed_out'] |= isinstance(exc, CommunicationTimeout)
            quality['acquisition_status'] = 'incomplete'
            elapsed = (self._clock.monotonic() - started) * 1000
            database.save_acquisition({"acquired_at": acquired_at, "success": 0, "error_stage": "acquisition",
                                       "error_detail": str(exc), "elapsed_ms": elapsed,
                                       "quality_json": json.dumps(quality, ensure_ascii=False), "dli_eligible": 0})
            database.diagnostic("ERROR", "acquisition", "采集失败", error=str(exc))
            raise

    def _sync_time_if_due(self, state: DeviceRuntimeState) -> None:
        if self._maintenance or self._halt_reason is not None:
            return
        if state.last_sync_at is not None and self._clock.monotonic() - state.last_sync_at < TIME_SYNC_INTERVAL_SECONDS:
            return
        assert self._client is not None
        try:
            self._client.set_slave_id(state.config.slave_id)
            with self._client.communication_budget(2.0, lambda: not self._running):
                stamp = self._client.sync_time()
            state.last_sync_at = self._clock.monotonic()
            state.database.save_time_sync(True, stamp, "设备对时完成")
        except CommunicationCancelled:
            return
        except Exception as exc:
            state.last_sync_at = self._clock.monotonic()
            state.database.save_time_sync(False, None, str(exc))
            state.database.diagnostic("WARNING", "time_sync", "设备对时失败", error=str(exc))

    # ---------------------------------------------------------------- 任务处理
    def _process_tasks(self) -> None:
        while self._running and not self._tasks.empty():
            key, kind, payload = self._tasks.get_nowait()
            if kind == "maintenance_enter":
                self._enter_maintenance(key, kind)
                continue
            if kind == "maintenance_leave":
                try:
                    if self._halt_reason:
                        raise ProtocolError("硬件异常停止仍有效，请重新上电并重启软件")
                    for session in self._maintenance_sessions.values():
                        session.check_resume(self._config)
                    for session in self._maintenance_sessions.values():
                        session.finish_after_resume(self._config)
                except Exception as exc:
                    self.task_finished.emit(key, kind, False, str(exc))
                    continue
                self._maintenance = False
                self._next_cycle_at = 0.0
                self._set_bus_state("idle", "维护已结束，等待连接")
                self.maintenance_changed.emit(False)
                continue
            if kind == "apply_config" and isinstance(payload, AppConfig):
                self._apply_config(payload)
                continue
            if self._maintenance and kind in ("maintenance_read", "maintenance_write", "maintenance_verify"):
                state = self._states.get(key)
                try:
                    if self._halt_reason or state is None or state.excluded:
                        raise ProtocolError("设备不可维护：未登记、已退出或硬件异常停止；请检查后重启软件")
                    path = state.database.path.resolve()
                    if path not in self._maintenance_sessions:
                        self._maintenance_sessions[path] = CommunicationMaintenance(state.database, state.config.name)
                    session = self._maintenance_sessions[path]
                    result = session.execute(kind, payload, lambda: not self._running)
                    self.task_finished.emit(key, kind, True, result)
                except HardwareStateError as exc:
                    self._halt_acquisition(state, exc)
                    self.task_finished.emit(key, kind, False, str(exc))
                except Exception as exc:
                    self.task_finished.emit(key, kind, False, str(exc))
                continue
            if self._maintenance:
                self.task_finished.emit(key, kind, False, "维护模式下禁止普通硬件任务")
                continue
            if self._halt_reason is not None:
                self.task_finished.emit(key, kind, False, "所有设备采集已停止，请为异常探头重新上电并重启软件。")
                continue
            if not self._config.configured:
                self.task_finished.emit(key, kind, False, "尚未提交设备配置")
                continue
            state = self._states.get(key)
            if state is None:
                self.task_finished.emit(key, kind, False, "设备未登记")
                continue
            if state.excluded:
                self.task_finished.emit(key, kind, False, "该设备已退出本次采集，重启软件后重新尝试。")
                continue
            try:
                check_manual_task(kind, state.config.enabled, self._maintenance_sessions, state.database.path)
                if kind == "read_identity":
                    self.task_finished.emit(key, kind, True, self._read_identity(state))
                    continue
                if self._client is None:
                    raise ProtocolError("总线未连接；请检查总线设置后重试。")
                assert self._client is not None
                self._client.set_slave_id(state.config.slave_id)
                if kind == "diagnostics_read":
                    with self._client.communication_budget(self._transaction_budget(), lambda: not self._running):
                        data = self._client.read_diagnostics()
                    state.database.diagnostic("INFO", kind, "已读取设备维护诊断", **data)
                    self.task_finished.emit(key, kind, True, data)
                elif kind == "calibration_read":
                    with self._client.communication_budget(self._transaction_budget(), lambda: not self._running):
                        data, status = self._client.read_calibration()
                    state.database.save_calibration(action="read", success=1, readback=data, status=status["status"], error=status["error"], detail="读取当前校准")
                    data["_mcu_status"] = status
                    self.task_finished.emit(key, kind, True, data)
                elif kind == "comm_read":
                    with self._client.communication_budget(self._transaction_budget(), lambda: not self._running):
                        data = self._client.read_mcu_comm()
                    state.database.diagnostic("INFO", "connection", "已读取设备当前通信参数", **data)
                    self.task_finished.emit(key, kind, True, data)
                elif kind == "comm_write":
                    self._write_device_comm(state, payload)  # type: ignore[arg-type]
                    self.task_finished.emit(key, kind, True, None)
                elif kind == "calibration_write":
                    with self._client.communication_budget(self._transaction_budget(), lambda: not self._running):
                        old, _ = self._client.read_calibration()
                        status = self._client.write_calibration(payload)  # type: ignore[arg-type]
                        readback, _ = self._client.read_calibration()
                    state.database.save_calibration(action="write", success=1, old=old, new=payload, readback=readback,
                                                    status=status["status"], error=status["error"], detail="写入并回读光谱仪校准")
                    readback["_mcu_status"] = status
                    self.task_finished.emit(key, kind, True, readback)
                else:
                    self.task_finished.emit(key, kind, False, f"未知任务：{kind}")
            except HardwareStateError as exc:
                self._halt_acquisition(state, exc)
                self.task_finished.emit(key, kind, False, str(exc))
            except CommunicationCancelled as exc:
                self.task_finished.emit(key, kind, False, str(exc))
            except Exception as exc:
                detail = str(exc)
                try:
                    state.database.diagnostic("ERROR", kind, detail)
                except Exception as log_error:
                    detail += f"；日志写入失败：{log_error}"
                self.task_finished.emit(key, kind, False, detail)

    def _read_identity(self, state: DeviceRuntimeState) -> dict:
        if self._client is None:
            raise ProtocolError("总线未连接")
        self._client.set_slave_id(state.config.slave_id)
        with self._client.communication_budget(self._transaction_budget(), lambda: not self._running):
            identity = self._client.read_device_identity()
        state.database.save_par_device_identity(int(identity["serial_number"]), int(identity["device_type"]), str(identity["device_name"]))
        state.device_identity = identity
        return identity

    def _write_device_comm(self, state: DeviceRuntimeState, payload: dict | None) -> None:
        raise ProtocolError("常规采集禁止写入通信参数，请使用独立的设备维护窗口。")

    # ---------------------------------------------------------------- 兼容旧 UI
    def status_text(self, key: str) -> str:
        """供状态栏使用的一行摘要。"""
        state = self._states.get(key)
        if state is None:
            return "未登记"
        latest = format_beijing_time(state.last_success_at)
        return f"{state.config.name}（地址 {state.config.slave_id}）· {state.message} · 最近采集：{latest}"


def build_databases(app_config: AppConfig) -> dict[str, ParDatabase]:
    """按登记表建立各设备数据库（供导出等只读用途直接批量访问）。"""
    keys = device_keys(app_config.devices[:MAX_DEVICES])
    result: dict[str, ParDatabase] = {}
    for index, (key, device) in enumerate(zip(keys, app_config.devices[:MAX_DEVICES], strict=True)):
        result[key] = ParDatabase(device.resolved_database_path(index))
    return result
