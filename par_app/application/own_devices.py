"""The devices whose data the pages show: those of the alpha's own tier-1 configuration (issue #82).

History, spectrum calculation, export, DLI, the settings page's device summary and the overview read the device
databases the alpha acquires itself (<data dir>/data/devices/, 16_ 3.2), one per position of the alpha's own
tier-1 configuration, read only (mode=ro, readonly.py). Imported snapshots are no longer shown (S-3 and the snapshot
parts of D-203–D-215 superseded, owner 2026-10-26); the copies stay on disk until #83.

Tier 0 reads no configuration at all (the acquisition service refuses it), so every position is empty there and
the pages show nothing (owner 2026-10-26: tier 0 may simply be empty). A configuration that cannot be read lists
no device either; the settings page names the problem (D-220) and a device request names it too.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import MAX_DEVICES
from .errors import DeviceNotFound, InvalidArgument
from .tier import TAKEOVER_TIER

if TYPE_CHECKING:  # acquisition imports live_overview -> overview -> this module
    from .acquisition import AcquisitionService

DEVICE_POSITIONS = tuple(f"p{position}" for position in range(1, MAX_DEVICES + 1))

DATABASE_ID_DIGITS = 16
"""Hex digits of the path hash in a database id: enough to tell the databases of one position apart."""
TIER_0_EMPTY = "只读模式不读取设备数据：开启采集模式并采集后，这里显示本软件采集的数据"


@dataclass(frozen=True)
class DeviceDatabase:
    """One registered device's database, as a page reads it."""

    id: str
    """Identifies this database of this position: another database at the same position (the configuration was
    changed) has another id, so an answer prepared on the old one is refused (D-208, EXP-052)."""
    key: str
    position: int
    name: str
    path: str
    file_name: str
    paused: bool
    """Nothing acquires into it now: not taken over, maintenance or a halt (as the live overview, D-213)."""


@dataclass(frozen=True)
class DeviceSlot:
    key: str
    position: int
    database: DeviceDatabase | None
    enabled: bool
    readable: bool = True
    """False when the configured database lies outside the alpha's devices folder: the device is listed (as a
    fault, so the configuration problem shows) but no page offers it, and reading it is refused (16_ 3.2)."""

    @property
    def usable(self) -> bool:
        return self.database is not None and self.readable


def database_id(key: str, path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:DATABASE_ID_DIGITS]
    return f"{key}-{digest}"


def device_position(key: str) -> int:
    """p1..p4 -> 1..4; any other key is an invalid argument (the same answer the snapshot positions gave)."""
    if key not in DEVICE_POSITIONS:
        raise InvalidArgument(f"设备位置无效：{key}（应为 {'、'.join(DEVICE_POSITIONS)}）")
    return DEVICE_POSITIONS.index(key) + 1


class OwnDevices:
    def __init__(self, acquisition: AcquisitionService) -> None:
        self.acquisition = acquisition

    def devices(self) -> list[DeviceSlot]:
        """The four positions; a position holds a database when the alpha's configuration registers a device there."""
        registered: list[dict[str, object]] = []
        # without a takeover backend (python -m par_app.api, D-213) there is no configuration to read either
        if self.acquisition.tier() >= TAKEOVER_TIER and self.acquisition.backend is not None:
            registered = list(self.acquisition.config()["devices"])
        paused = self.acquisition.paused()
        slots = []
        for index, key in enumerate(DEVICE_POSITIONS):
            if index >= len(registered):
                slots.append(DeviceSlot(key, index + 1, None, False))
                continue
            device = registered[index]
            path = Path(str(device["database_path"]))
            database = DeviceDatabase(
                database_id(key, path), key, index + 1, str(device["name"]), str(path), path.name, paused
            )
            readable = bool(device.get("inside_alpha")) and self.acquisition.paths.holds_device_database(path)
            slots.append(DeviceSlot(key, index + 1, database, bool(device["enabled"]), readable))
        return slots

    def database_for(self, key: str) -> DeviceDatabase:
        """The database of the device at `key`; refused outside the alpha's devices folder (16_ 3.2)."""
        position = device_position(key)
        if self.acquisition.tier() < TAKEOVER_TIER:
            raise DeviceNotFound(TIER_0_EMPTY, key)
        name, path = self.acquisition.device_database(key)
        return DeviceDatabase(
            database_id(key, path), key, position, name, str(path), path.name, self.acquisition.paused()
        )
