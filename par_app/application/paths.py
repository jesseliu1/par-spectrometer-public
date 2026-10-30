"""Where the alpha keeps its own files (internal notes section 5).

Layout under the data directory:
  config/            alpha's own configuration (app_config_v2.json, not written yet)
  data/imported/     history snapshot copies (<name>-<time>.sqlite) and their sidecar descriptions (.json)
  data/staging/      temporary byte copies of a source left with a -wal / -journal (removed after each import)
  exports/           spectrum calculation exports, one new folder per export (D-207)
  logs/              service log
  service.json       port and token of the running service (mode 600)
The V1.0.x program directory, config and databases are never inside it and never written.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..alpha_info import APP_NAME

DATA_DIR_ENV = "PAR_ALPHA_DATA_DIR"
"""Overrides the data directory (development and tests must not write the real %LOCALAPPDATA%, 15_ 5.6)."""
PRODUCT_DIR_NAME = APP_NAME
V103_PROGRAM_MARKERS: tuple[tuple[str, ...], ...] = (("_internal",), ("PAR_Spectrometer.exe",), ("main.py", "par_app"))
"""What makes a folder a V1.0.x program folder: the packaged build's _internal folder or its exe
(PAR_Spectrometer.spec), or main.py with par_app/ when run from source. V1.0.x keeps config/ and data/devices/
relative to that folder, the same layout as the alpha's data directory (review Q2, D-215)."""
OUTSIDE_ALPHA = "只能使用本软件数据目录下的设备库：{path} 不在 {directory} 之下"
"""Refusal when a tier-1 database is not under <data dir>/data/devices (16_ 3.2 check 2; PR #54 review B1)."""


def v103_program_marker(folder: Path) -> str | None:
    """The marker names when `folder` is a V1.0.x program folder, else None; the alpha must not use it as its data
    directory, or it would read and write V1.0.x's configuration and device databases."""
    for names in V103_PROGRAM_MARKERS:
        if all((folder / name).exists() for name in names):
            return " + ".join(names)
    return None


def default_data_dir() -> Path:
    """$PAR_ALPHA_DATA_DIR, else %LOCALAPPDATA%\\PAR_Spectrometer_2 (Windows), else ~/.local/share/<same name>."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / PRODUCT_DIR_NAME
    return Path.home() / ".local" / "share" / PRODUCT_DIR_NAME


@dataclass(frozen=True)
class AlphaPaths:
    data_dir: Path

    @property
    def imported_dir(self) -> Path:
        return self.data_dir / "data" / "imported"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "data" / "staging"

    @property
    def exports_dir(self) -> Path:
        """Where exports are written: the alpha has no folder dialog yet, so nothing is written elsewhere (D-207)."""
        return self.data_dir / "exports"

    @property
    def devices_dir(self) -> Path:
        """Tier-1 device databases: V1.0.3's data/devices layout (models.DEFAULT_DEVICE_DATABASE_DIR) under the
        alpha's data directory. The only place a live read may open a database (PR #54 review B1)."""
        return self.data_dir / "data" / "devices"

    def holds_device_database(self, path: Path) -> bool:
        """`path`, symlinks and `..` resolved, lies under devices_dir."""
        return path.resolve().is_relative_to(self.devices_dir.resolve())

    @property
    def config_dir(self) -> Path:
        return self.data_dir / "config"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def service_file(self) -> Path:
        return self.data_dir / "service.json"

    def ensure(self) -> None:
        for path in (self.imported_dir, self.config_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)
