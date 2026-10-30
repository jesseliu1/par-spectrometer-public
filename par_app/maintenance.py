from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

from .database import beijing_now
from .models import AppConfig, ConnectionConfig, DeviceConfig
from .protocol import HardwareStateError, ParModbusClient, ProtocolError


BAUDRATES = (4800, 9600, 14400, 19200, 38400, 57600, 115200, 256000)
PARITIES = ("N", "O", "E")
REJOIN_VERIFICATION_MESSAGE = ("该设备库中有未完成的通信维护（待核对写入或核对后未恢复），完成核对前不参与采集；"
                               "请在“设备维护”中进入通信维护，完成核对后选择“退出维护并恢复采集”")
REJOIN_WRITE_BLOCKED_MESSAGE = ("该设备库中有未完成的通信维护（待核对写入或核对后未恢复），"
                                "完成核对前禁止写入校准或通信参数；"
                                "请在“设备维护”中进入通信维护，完成核对后选择“退出维护并恢复采集”")
MANUAL_WRITE_TASKS = ("calibration_write", "comm_write")


class CommunicationMaintenance:
    def __init__(self, database, name: str):
        self.database = database
        self.name = name
        self.baseline = None
        self.pending = None
        self.verified = None
        self.deferred = False
        with database.connect() as connection:
            row = connection.execute("SELECT value_json FROM app_settings WHERE key='communication_maintenance'").fetchone()
        if row:
            saved = json.loads(row[0])
            self.pending, self.verified = saved.get("pending"), saved.get("verified")
            self.deferred = bool(saved.get("deferred")) and self.verified is not None

    def _save(self, pending, verified, deferred: bool = False) -> None:
        saved = {"pending": pending, "verified": verified}
        if deferred:
            saved["deferred"] = True
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO app_settings(key,value_json,updated_at) VALUES('communication_maintenance',?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                (json.dumps(saved, ensure_ascii=False), beijing_now()),
            )
        self.deferred = deferred

    @property
    def unfinished(self) -> bool:
        """库中保存有待核对写入，或核对已通过但尚未明确恢复。"""
        return bool(self.pending or self.verified)

    @property
    def blocks_startup(self) -> bool:
        """MAINT-125/126：重启即进入维护停止。已明确恢复采集、仅因设备停用或移出登记而暂缓的核对结果不算（D-131、D-132）。"""
        return self.unfinished and not self.deferred

    def finish(self) -> None:
        self._save(None, None)
        self.baseline = self.verified = None

    def finish_after_resume(self, config: AppConfig) -> None:
        """恢复采集后收尾。D-131：已停用或已移出登记的设备不清除核对结果（标为暂缓，重启不再因它停止），重新启用或重新登记时仍须先完成核对。"""
        if self.verified is not None and self._active_device(config) is None:
            self._save(None, self.verified, deferred=True)
            self.baseline = None
            return
        self.finish()

    def _active_device(self, config: AppConfig) -> DeviceConfig | None:
        device = next((device for device in config.devices
                       if Path(device.resolved_database_path()).resolve() == self.database.path.resolve()), None)
        return device if device is not None and device.enabled else None

    @staticmethod
    def connection(values: dict) -> ConnectionConfig:
        config = ConnectionConfig.from_dict(values)
        if config.transport != "rtu" or not config.serial_port.strip():
            raise ProtocolError("维护仅支持手动指定 RTU 串口")
        if not 1 <= config.slave_id <= 247 or config.baudrate not in BAUDRATES or config.parity not in PARITIES:
            raise ProtocolError("通信参数无效")
        config.timeout_seconds = 1.0
        return config

    @staticmethod
    def parameters(config: ConnectionConfig) -> dict:
        return {"slave_id": config.slave_id, "baudrate_index": BAUDRATES.index(config.baudrate),
                "parity_index": PARITIES.index(config.parity)}

    def execute(self, kind: str, payload: dict, cancelled) -> dict:
        if kind not in ("maintenance_read", "maintenance_write", "maintenance_verify"):
            raise ProtocolError("未知维护任务")
        if kind == "maintenance_read" and self.pending:
            raise ProtocolError("已有待核对的写入，请先使用新参数核对")
        if kind == "maintenance_write" and (not self.baseline or self.pending):
            raise ProtocolError("请先读取并确认目标设备")
        if kind == "maintenance_verify" and not self.pending:
            raise ProtocolError("没有待核对的通信参数写入")
        config = self.connection(payload["connection"] if kind != "maintenance_verify" else self.pending["new"])
        new_config = self.connection(payload["new"]) if kind == "maintenance_write" else None
        if kind == "maintenance_write":
            if not payload.get("isolated") or config.to_dict() != self.baseline["connection"]:
                raise ProtocolError("当前连接参数已变化，或尚未确认只连接目标设备")
            if new_config.serial_port != config.serial_port:
                raise ProtocolError("写入不能改变电脑串口")
        self.database.diagnostic("INFO", "communication_maintenance", "开始维护操作",
                                 device_name=self.name, action=kind, connection=config.to_dict())
        client = ParModbusClient(config)
        closed = False
        try:
            with client.communication_budget(10.0, cancelled):
                if not client.connect():
                    raise ProtocolError("维护连接失败，请核对指定串口及参数")
                status = client.read_status()
                if not status.initialized or status.need_power_cycle:
                    raise HardwareStateError(status)
                identity = client.read_device_identity()
                parameters = client.read_mcu_comm()
                if parameters != self.parameters(config):
                    raise ProtocolError("回读通信参数与指定连接参数不一致")
                result = {"connection": config.to_dict(), "identity": identity, "parameters": parameters}
                if kind == "maintenance_write":
                    if identity != self.baseline["identity"]:
                        raise ProtocolError("设备身份与此前读取不一致，禁止写入")
                    self.pending = {"old": config.to_dict(), "new": new_config.to_dict(), "identity": deepcopy(identity)}
                    self.verified = None
                    self._save(self.pending, None)
                    self.database.diagnostic("WARNING", "communication_maintenance", "准备写入，结果必须使用新参数核对",
                                             device_name=self.name, **self.pending)
                    client.change_mcu_comm(new_config.slave_id, BAUDRATES.index(new_config.baudrate), PARITIES.index(new_config.parity))
                elif kind == "maintenance_verify":
                    if identity != self.pending["identity"]:
                        raise ProtocolError("新参数下设备身份不一致，核对失败")
            client.close()
            closed = True
            self.database.diagnostic("INFO", "communication_maintenance", "维护操作完成",
                                     device_name=self.name, action=kind, result=result)
            if kind == "maintenance_verify":
                self._save(None, result)
                self.verified = result
                self.pending = None
            elif kind == "maintenance_read":
                self.baseline = result
            return result
        except Exception as exc:
            try:
                self.database.diagnostic("ERROR", "communication_maintenance", str(exc), device_name=self.name, action=kind)
            except Exception:
                pass
            raise
        finally:
            exception_active = sys.exc_info()[0] is not None
            try:
                if not closed:
                    client.close()
            except Exception:
                if not exception_active:
                    raise

    def check_resume(self, config) -> None:
        if self.pending:
            raise ProtocolError("写入结果尚未核对，不能恢复采集；请在维护窗口使用新参数核对")
        if self.verified is not None:
            expected = self.verified["connection"]
            device = self._active_device(config)
            if device is None:
                return
            if (config.bus.transport, config.bus.serial_port, config.bus.baudrate, config.bus.parity, device.slave_id) != (
                    "rtu", expected["serial_port"], expected["baudrate"], expected["parity"], expected["slave_id"]):
                raise ProtocolError("请先在常规设置中手动更新该设备 ID 和总线连接参数，或禁用该设备，再恢复采集")


def check_manual_task(
    kind: str, enabled: bool, sessions: dict[Path, CommunicationMaintenance], database_path: Path
) -> None:
    """普通（非维护）设备任务的前置检查。

    停用设备只可查看历史记录；裁决 43：维护会话未完成（重新启用或登记后尚未核对）的设备，
    完成核对前禁止手动写入校准或通信参数，读取不受限。
    """
    if kind in ("diagnostics_read", "calibration_read", "calibration_write") and not enabled:
        raise ProtocolError("设备已停用，仅可查看历史记录")
    session = sessions.get(Path(database_path).resolve())
    if kind in MANUAL_WRITE_TASKS and session is not None and session.unfinished:
        raise ProtocolError(REJOIN_WRITE_BLOCKED_MESSAGE)
