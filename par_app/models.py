from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Transport = Literal["rtu", "tcp"]

# 多设备支持：单机最多 4 台光谱仪挂在同一条 Modbus 链路上，靠从站地址区分。
MAX_DEVICES = 4
DEVICE_TIMEOUT_SECONDS = 10.0
MIN_POLL_CYCLE_SECONDS = 40.0
MAX_POLL_CYCLE_SECONDS = 3600.0
DEFAULT_BAUDRATE = 19200
DEFAULT_DEVICE_DATABASE_DIR = Path("data") / "devices"


@dataclass(slots=True)
class ConnectionConfig:
    """单设备连接参数；保留原有语义，供协议层与旧版配置迁移使用。"""

    transport: Transport = "rtu"
    serial_port: str = "COM1"
    host: str = "127.0.0.1"
    tcp_port: int = 502
    slave_id: int = 1
    baudrate: int = DEFAULT_BAUDRATE
    parity: str = "N"
    timeout_seconds: float = 0.8
    acquisition_interval_seconds: float = 2.0
    database_path: str = "data/par_spectrometer.sqlite3"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectionConfig":
        allowed = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        return cls(**allowed)


@dataclass(slots=True)
class BusConfig:
    """整条 Modbus 链路共享的通信参数。

    波特率、校验位、数据位、停止位是物理总线级参数，4 台设备必须完全一致，
    因此软件只保留这一处设置，不再允许按设备单独设置。
    """

    transport: Transport = "rtu"
    serial_port: str = "COM1"
    host: str = "127.0.0.1"
    tcp_port: int = 502
    baudrate: int = DEFAULT_BAUDRATE
    parity: str = "N"
    timeout_seconds: float = DEVICE_TIMEOUT_SECONDS
    poll_cycle_seconds: float = 60.0

    def to_connection(self, slave_id: int = 1, database_path: str = "") -> ConnectionConfig:
        """按指定从站地址生成本次事务使用的单设备连接参数。"""
        return ConnectionConfig(
            transport=self.transport,
            serial_port=self.serial_port,
            host=self.host,
            tcp_port=self.tcp_port,
            slave_id=int(slave_id),
            baudrate=self.baudrate,
            parity=self.parity,
            timeout_seconds=self.timeout_seconds,
            acquisition_interval_seconds=self.poll_cycle_seconds,
            database_path=database_path,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "BusConfig":
        allowed = {key: value for key, value in (data or {}).items() if key in cls.__dataclass_fields__}
        config = cls(**allowed)
        config.baudrate = int(config.baudrate)
        config.poll_cycle_seconds = float(config.poll_cycle_seconds)
        if not math.isfinite(config.poll_cycle_seconds):
            # NaN 无大小关系，40~3600 秒钳位对它无效，首轮后会永久停采（DEF-01）。
            # NaN、±Infinity 及溢出值一律按坏配置拒绝（与 D-141 配置不可读同一流程）：
            # 启动时转为 StartupConfigurationError 弹窗；有限越界值仍按原钳位处理。
            raise ValueError("总线参数 poll_cycle_seconds（轮询周期）必须是有限数值")
        config.timeout_seconds = float(config.timeout_seconds)
        return config


# 设备名转文件名（CONF-030；D-140 缺陷修复部分，旧仓库 #11）：单段文件名上限，远低于
# Windows/常见文件系统的 255，给 ".sqlite3" 后缀和导出子目录留出余量。
MAX_SAFE_FILENAME_LENGTH = 100
# Windows 保留设备名（不区分大小写，带扩展名也算保留，如 COM1.sqlite3）。
WINDOWS_RESERVED_FILE_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{port}{digit}" for port in ("COM", "LPT") for digit in "123456789¹²³"}
)


# 被新增规则改动的名称在末尾加“_”和 V1.0.2 结果的摘要（十六进制位数），使新规则不把 V1.0.2
# 下不同的文件名合成同一个（导出目录同名会互相覆盖），V1.0.2 下已相同的仍然相同（D-140）。
FILENAME_DIGEST_LENGTH = 8
_V102_UNSAFE_CHARACTERS = r'[\\/:*?"<>|\r\n\t]+'
_UNSAFE_CHARACTERS = r'[\\/:*?"<>|\x00-\x1f\x7f]+'


def _is_reserved_on_windows(filename: str) -> bool:
    return filename.partition(".")[0].rstrip(" ").upper() in WINDOWS_RESERVED_FILE_STEMS


def _clean_filename(name: str) -> str:
    legacy = re.sub(_V102_UNSAFE_CHARACTERS, "_", str(name or "")).strip(" .")
    cleaned = re.sub(_UNSAFE_CHARACTERS, "_", legacy).strip(" .")
    if cleaned == legacy and len(cleaned) <= MAX_SAFE_FILENAME_LENGTH and not _is_reserved_on_windows(cleaned):
        return cleaned
    if not cleaned:
        return ""
    stem, dot, rest = cleaned.partition(".")
    if dot and _is_reserved_on_windows(cleaned):
        cleaned = f"{stem}_{dot}{rest}"
    digest = hashlib.sha256(legacy.encode("utf-8")).hexdigest()[:FILENAME_DIGEST_LENGTH]
    body = cleaned[: MAX_SAFE_FILENAME_LENGTH - FILENAME_DIGEST_LENGTH - 1].rstrip(" .")
    return f"{body}_{digest}"


def safe_database_filename(name: str, fallback: str = "spectrometer") -> str:
    """把用户自定义的设备名转换为可用于文件名的安全字符串。

    V1.0.2 规则：\\ / : * ? " < > | 及换行、制表符替换为“_”，去除首尾空格和点；结果不超过
    MAX_SAFE_FILENAME_LENGTH、不含其他控制字符、不是 Windows 保留名时原样返回（与 V1.0.2 相同）。
    否则另把控制字符替换为“_”，保留名主干后加“_”（仅带扩展名时需要），截断后接“_”和
    V1.0.2 结果的 SHA-256 前 FILENAME_DIGEST_LENGTH 位（COM1 → COM1_xxxxxxxx）。
    """
    return _clean_filename(name) or _clean_filename(fallback) or "spectrometer"


def default_device_database_path(name: str, index: int = 0, root: Path | str | None = None) -> str:
    """设备未指定库路径时的默认位置：data/devices/<设备名>.sqlite3。"""
    base = Path(root) if root is not None else Path(".")
    filename = f"{safe_database_filename(name, f'device{index + 1}')}.sqlite3"
    return str(base / DEFAULT_DEVICE_DATABASE_DIR / filename)


@dataclass(slots=True)
class DeviceConfig:
    """单台光谱仪的登记信息；用户预先登记，最多 MAX_DEVICES 台。"""

    name: str = ""
    slave_id: int = 1
    enabled: bool = True
    database_path: str = ""
    # 连续通信失败达到上限后是否自动退出本次采集。默认关闭：无人值守时按轮询周期
    # 持续重试，排除故障后自动恢复；需要“失败即停”保护时在设备登记表内逐台勾选。
    auto_stop_on_failure: bool = False

    def resolved_database_path(self, index: int = 0, root: Path | str | None = None) -> str:
        path = str(self.database_path or "").strip()
        if path:
            return path
        return default_device_database_path(self.name, index, root)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "DeviceConfig":
        allowed = {key: value for key, value in (data or {}).items() if key in cls.__dataclass_fields__}
        device = cls(**allowed)
        device.slave_id = int(device.slave_id)
        device.enabled = bool(device.enabled)
        device.name = str(device.name or "")
        device.database_path = str(device.database_path or "")
        # 旧版配置无此键时保持默认（不自动退出采集），不因缺字段改变现场采集节奏。
        device.auto_stop_on_failure = bool(device.auto_stop_on_failure)
        return device


@dataclass(slots=True)
class AppConfig:
    """应用级配置：一条总线 + 最多 4 台已登记设备。"""

    bus: BusConfig = field(default_factory=BusConfig)
    devices: list[DeviceConfig] = field(default_factory=list)
    configured: bool = False

    def enabled_devices(self) -> list[DeviceConfig]:
        return [device for device in self.devices if device.enabled]

    def min_poll_cycle_seconds(self) -> float:
        """设备数量不改变总采集周期下限。"""
        return MIN_POLL_CYCLE_SECONDS

    def effective_poll_cycle_seconds(self) -> float:
        lower = self.min_poll_cycle_seconds()
        return min(max(float(self.bus.poll_cycle_seconds), lower), MAX_POLL_CYCLE_SECONDS)

    def clamp_poll_cycle(self) -> None:
        self.bus.poll_cycle_seconds = self.effective_poll_cycle_seconds()

    def normalised(self) -> "AppConfig":
        """裁剪到 4 台以内、补齐默认设备名，并纠正轮询周期范围。"""
        devices: list[DeviceConfig] = []
        for index, device in enumerate(self.devices[:MAX_DEVICES]):
            if not device.name.strip():
                device.name = f"光谱仪{index + 1}"
            devices.append(device)
        self.devices = devices
        self.clamp_poll_cycle()
        return self

    def to_dict(self) -> dict:
        return {"bus": self.bus.to_dict(), "devices": [device.to_dict() for device in self.devices], "configured": self.configured}

    @classmethod
    def from_dict(cls, data: dict | None) -> "AppConfig":
        payload = data or {}
        devices = [DeviceConfig.from_dict(item) for item in payload.get("devices") or []]
        config = cls(bus=BusConfig.from_dict(payload.get("bus")), devices=devices, configured=payload.get("configured") is True)
        return config.normalised()


@dataclass(slots=True)
class DeviceStatus:
    initialized: bool = False
    need_power_cycle: bool = False
    raw_data_valid: bool = False
    calculate_data_valid: bool = False
    stop_status: int = 0
    spectral_coefficient: int = 0
    exposure_status: int = 0
    exposure_time_us: int = 0
    exposure_mode: int = 1


PHOTOMETRIC_NAMES = (
    "cct", "lux", "ee", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8",
    "r9", "r10", "r11", "r12", "r13", "r14", "r15", "ra", "X", "Y", "Z",
    "duv", "u", "v", "x", "y",
)
