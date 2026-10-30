"""Device-write tier of the alpha (13_ 2.5; 16_ section 4; 17_ section 8; owner 2026-10-18 approved tiers 1 and 2 for
internal trial).

The tier says how far the alpha may go; it is not the takeover itself. It is stored in the alpha's own settings file
<data dir>/config/app_config_v2.json (never in a V1.0.x file) and is 0 from the factory, when the file is missing,
and when the file cannot be read: reading never raises the tier. 0 -> 1 and 1 -> 2 each need a second confirmation
that this service issued less than CONFIRMATION_SECONDS ago for that very tier and that has not been used; a hidden
button is not a confirmation (16_ 4.2, 17_ 6.1). 0 -> 2 is refused (tier 1 first). Lowering needs none.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from ..domain.clock import Clock
from .errors import ConfirmationRequired, InvalidArgument
from .timefmt import beijing_iso

LOG = logging.getLogger(__name__)
SETTINGS_FILE_NAME = "app_config_v2.json"
TIER_KEY = "device_write_tier"
FACTORY_TIER = 0
TAKEOVER_TIER = 1
"""Tier 1: the alpha may take over acquisition (16_)."""
MAINTENANCE_TIER = 2
"""Tier 2: on top of tier 1, the device maintenance page may read and write the device (17_)."""
ALLOWED_TIERS = (FACTORY_TIER, TAKEOVER_TIER, MAINTENANCE_TIER)
MODE_NAMES = {FACTORY_TIER: "只读模式", TAKEOVER_TIER: "采集模式", MAINTENANCE_TIER: "维护模式"}
"""What the pages call tiers 0, 1 and 2 since alpha.5 (UAT wording, user manual appendix A)."""
CONFIRMATION_SECONDS = 60.0
"""How long a second confirmation stays valid (16_ 4.2)."""
CONFIRMATION_ID_BYTES = 16

Takeover = Literal["released", "starting", "running", "stopping"]
Level = Literal["muted", "info", "warn", "error", "maintenance"]

FIRST_NOTICE = (
    "开启采集模式之后：\n"
    "· 开启后每次打开本软件都会自动开始采集，也可以手动“开始采集”“停止采集”；"
    "开始采集时本软件会打开串口或网关，向设备发送冻结/恢复、读取光谱和对时命令；\n"
    "· 采集期间其他软件不能使用该串口；串口被其他程序占用时本软件不开始采集；\n"
    "· 采集记录只写入本软件自己的数据目录。"
)
SECOND_CONFIRMATION = "我已了解上述影响，开启采集模式。开启后每次打开本软件都会自动开始采集；串口被占用时不开始采集。"
FIRST_NOTICE_2 = (
    "开启维护模式之后：\n"
    "· 设备维护页可以读取诊断、读写光谱校准、进入通信维护并改写探头的从站地址、波特率和校验位，"
    "供工程人员使用；\n"
    "· 进入通信维护会停止全部设备的采集，必须经核对和“退出维护并恢复采集”才会恢复；\n"
    "· 写入结果以设备回读和核对为准，软件不会自动修改连接配置。"
)
SECOND_CONFIRMATION_2 = "我已了解上述影响，开启维护模式。每一次写入设备之前仍会再次确认。"
NOTICES = {
    TAKEOVER_TIER: (FIRST_NOTICE, SECOND_CONFIRMATION),
    MAINTENANCE_TIER: (FIRST_NOTICE_2, SECOND_CONFIRMATION_2),
}
STATUS_TEXTS: dict[str, tuple[str, Level]] = {
    "tier0": ("只读模式（不连接设备）", "muted"),
    "released": ("采集模式 · 未在采集（可点“开始采集”）", "info"),
    "starting": ("采集模式 · 正在开始采集…", "warn"),
    "running": ("采集模式 · 正在采集", "warn"),
    "stopping": ("采集模式 · 正在停止采集…", "warn"),
    "halted": ("采集模式 · 采集已停止（锁停），见提示", "error"),
    "unregistered": ("采集模式 · 等待登记设备（请到“设置与导出”登记并保存）", "info"),
}
""""unregistered": running before any device is registered, so nothing is being acquired (owner 2026-10-27)."""
MAINTENANCE_RUNNING_2: tuple[str, Level] = ("维护模式 · 通信维护中，采集已暂停", "maintenance")
MAINTENANCE_RUNNING_1: tuple[str, Level] = ("采集模式 · 维护未完成，采集暂停；恢复需要开启维护模式", "maintenance")
"""17_ 6.1: tier 2 lowered to 1 keeps maintenance; tier 1 cannot leave it."""


def status_text(
    tier: int, takeover: Takeover, halted: bool, maintenance: bool = False, unregistered: bool = False
) -> tuple[str, Level]:
    """The fixed status-bar block (16_ 4.4; 17_ 6.1: tier 2 reads "档位 2" and shows maintenance). `unregistered`:
    the running configuration was never saved, so no device is registered (V1.0.3 saves none without one enabled)."""
    if tier < TAKEOVER_TIER and takeover == "released":
        return STATUS_TEXTS["tier0"]
    if halted and takeover == "running":
        text, level = STATUS_TEXTS["halted"]
    elif maintenance and takeover == "running":
        return MAINTENANCE_RUNNING_2 if tier >= MAINTENANCE_TIER else MAINTENANCE_RUNNING_1
    elif unregistered and takeover == "running":
        text, level = STATUS_TEXTS["unregistered"]
    else:
        text, level = STATUS_TEXTS[takeover]
    if tier >= MAINTENANCE_TIER:
        text = text.replace("采集模式", "维护模式", 1)
    return text, level


class TierStore:
    """Reads and writes the tier in app_config_v2.json; other keys in that file are kept as they are."""

    def __init__(self, config_dir: Path, default: int = FACTORY_TIER) -> None:
        self.path = config_dir / SETTINGS_FILE_NAME
        self.default = default
        """The tier without a usable settings file. The product service reads tier 1 there (issue #119, owner
        2026-10-27: a new installation acquires at once, as V1.0.3); the API alone and the tests keep tier 0."""
        self.problem: str | None = None
        """Why the file could not be used the last time it was read (the default tier is then used), else None."""

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("设置文件的根节点不是对象")
        return payload

    def tier(self) -> int:
        try:
            value = self._read().get(TIER_KEY, self.default)
        except (OSError, ValueError) as error:
            self.problem = f"{self.path}：{error}"
            LOG.warning("alpha settings unreadable, tier %d is used: %s", self.default, self.problem)
            return self.default
        self.problem = None
        if isinstance(value, bool) or value not in ALLOWED_TIERS:
            self.problem = f"{self.path}：模式值 {value!r} 无效"
            return self.default
        return int(value)

    def write(self, tier: int) -> None:
        if tier not in ALLOWED_TIERS:
            raise InvalidArgument(f"档位只能是 {', '.join(map(str, ALLOWED_TIERS))}")
        try:
            payload = self._read()
        except (OSError, ValueError):
            payload = {}  # an unreadable file counted as the default tier; writing the tier replaces it
        payload[TIER_KEY] = tier
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        self.problem = None


@dataclass(frozen=True)
class Confirmation:
    id: str
    tier: int
    expires_at: str
    notice: str
    confirmation: str


class TierConfirmations:
    """Second confirmations issued by this service process; each can be used once, until it expires."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._issued: dict[str, tuple[int, float]] = {}

    def issue(self, tier: int) -> Confirmation:
        if tier not in NOTICES:
            raise InvalidArgument("只有开启采集模式或维护模式需要确认")
        identifier = secrets.token_urlsafe(CONFIRMATION_ID_BYTES)
        expires = self._clock.monotonic() + CONFIRMATION_SECONDS
        wall: datetime = self._clock.now() + timedelta(seconds=CONFIRMATION_SECONDS)
        with self._lock:
            self._issued = {key: item for key, item in self._issued.items() if item[1] > self._clock.monotonic()}
            self._issued[identifier] = (tier, expires)
        notice, confirmation = NOTICES[tier]
        return Confirmation(identifier, tier, beijing_iso(wall), notice, confirmation)

    def consume(self, identifier: str | None, tier: int) -> None:
        with self._lock:
            issued = self._issued.pop(identifier, None) if identifier else None
        if issued is None:
            raise ConfirmationRequired(f"开启{MODE_NAMES[tier]}需要先在确认框中确认（确认无效或已使用，请重新开启）")
        if issued[0] != tier:
            raise ConfirmationRequired("确认的模式与请求的模式不一致")
        if self._clock.monotonic() >= issued[1]:
            raise ConfirmationRequired("确认已过期，请重新确认")
