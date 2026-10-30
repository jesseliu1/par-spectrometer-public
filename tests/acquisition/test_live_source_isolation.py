"""The tier-1 live overview opens only databases under the alpha's own data directory (PR #54 review, blocker 1).

Starting a takeover and saving the configuration already refuse a database outside <data dir>/data/devices
(16_ 3.2 check 2). The live overview (GET /acquisition/devices/{key}/latest) read the configured path directly, so a
hand-edited or copied alpha configuration that names V1.0.3's own database made the alpha open it with mode=ro and
without immutable=1: on a WAL database SQLite may then create or change -wal/-shm beside V1.0.3's file, which the
approval (owner 2026-10-18, section 8; 15_ section 5) forbids. Now every live read checks the resolved path first, and
no read creates a file outside the alpha's data directory.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from par_app.application import readonly
from tests.acquisition.conftest import Alpha, two_devices, write_config

pytestmark = pytest.mark.qt


def _outside(root: Path, alpha_dir: Path) -> dict[str, str]:
    """Every file under `root` except the alpha's data directory, with its SHA-256 (directory monitor)."""
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.resolve().is_relative_to(alpha_dir.resolve()):
            found[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    real = sqlite3.connect

    def spy(database: str, *args: object, **kwargs: object) -> sqlite3.Connection:
        seen.append(str(database))
        return real(database, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(readonly.sqlite3, "connect", spy)
    return seen


def _foreign_alpha_config(alpha: Alpha, tmp_path: Path) -> Path:
    """The alpha's tier-1 configuration copied from V1.0.3's: its databases are V1.0.3's own (WAL mode)."""
    v1_root = tmp_path / "V1.0.3"
    v1_config = write_config(v1_root, two_devices())
    target = alpha.data_dir / "config" / "app_config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(v1_config.to_dict(), ensure_ascii=False), encoding="utf-8")
    return v1_root


def test_live_overview_refuses_a_database_outside_the_alpha_directory(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    v1_root = _foreign_alpha_config(alpha, tmp_path)
    alpha.enable_tier_1()
    before = _outside(tmp_path, alpha.data_dir)
    opened = _opened(monkeypatch)
    for key in ("p1", "p2"):
        refused = alpha.get(f"/api/v0/acquisition/devices/{key}/latest")
        assert refused.status_code == 409, refused.text
        error = refused.json()["error"]
        assert error["code"] == "config_unavailable"
        assert "只能使用本软件数据目录下的设备库" in error["message"]
    assert not any(str(v1_root.resolve()) in uri or "V1.0.3" in uri for uri in opened), opened
    assert _outside(tmp_path, alpha.data_dir) == before


def test_no_read_creates_a_file_outside_the_alpha_directory(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Directory monitor: every tier-1 read (tier, status, configuration, import preview, live overview of both
    positions) leaves every file outside the alpha's data directory as it was, and creates none there."""
    v1_root = _foreign_alpha_config(alpha, tmp_path)
    alpha.enable_tier_1()
    before = _outside(tmp_path, alpha.data_dir)
    for path in (
        "/api/v0/tier",
        "/api/v0/acquisition/status",
        "/api/v0/acquisition-config",
        "/api/v0/acquisition/devices/p1/latest",
        "/api/v0/acquisition/devices/p2/latest",
    ):
        alpha.get(path)
    preview = alpha.post("/api/v0/acquisition-config/import-preview", {"source_path": str(v1_root)})
    assert preview.status_code == 200, preview.text
    assert _outside(tmp_path, alpha.data_dir) == before


def test_live_overview_still_reads_the_alpha_own_database(alpha: Alpha) -> None:
    write_config(alpha.data_dir, two_devices())
    alpha.enable_tier_1()
    live = alpha.get("/api/v0/acquisition/devices/p1/latest")
    assert live.status_code == 200, live.text
    assert live.json()["device"]["database_path"].startswith(str(alpha.data_dir))
