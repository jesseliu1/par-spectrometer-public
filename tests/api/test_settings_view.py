"""Contract tests of the settings view (api-contract-v0 API-26, API-15; D-209; issue #82).

The devices are those of the alpha's own tier-1 configuration; tier 0 reads no configuration and lists none, and its
bus fields say "只读模式不读取配置". The device status area comes from the device's own database: the record
summary, the file and its current size, the device identity V1.0.3 stored in app_settings, and the poll cycle
recorded with the latest successful record (the D-206 rule). Nothing on the page can save, apply or write.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.database import ParDatabase

from .conftest import error_of, failed_record, record, register_device, v1_database

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("UI-073 UI-075 UI-077 UI-080 UI-081 UI-099 UI-261 EXP-044 EXP-046 EXP-047 EXP-066"),
]
NO_CONFIG = "只读模式不读取配置"


def _quality(poll_cycle: object) -> str:
    return json.dumps(
        {"strategy": "single_capture", "acquisition_status": "completed", "poll_cycle_seconds": poll_cycle}
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = v1_database(
        tmp_path / "v1" / "east.sqlite3",
        [
            record("2026-10-18T08:00:00.000", quality_json=_quality(300)),
            failed_record("2026-10-18T08:05:00.000"),
        ],
    )
    ParDatabase(path).save_par_device_identity(0x1234ABCD, 2, "PAR-01")
    return path


def test_settings_view_in_tier_0_lists_no_device(client: TestClient) -> None:
    body = client.get("/api/v0/settings").json()
    assert body["title"] == "设置与导出"
    assert body["tier"] == 0 and body["source"] == "live_ro"
    assert [group for group in body["groups"]] == ["通信设置", "设备登记", "采集记录导出", "设备状态与最近日志"]
    assert [item["label"] for item in body["bus"]] == [
        "连接方式",
        "计算机串口",
        "波特率",
        "奇偶校验",
        "TCP 主机",
        "TCP 端口",
        "全总线轮询周期",
    ]
    assert {item["text"] for item in body["bus"]} == {NO_CONFIG}
    assert body["config_text"] == NO_CONFIG
    assert body["device_columns"] == ["设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"]  # UI-099
    assert [row["configured"] for row in body["devices"]] == [False] * 4
    assert {row["state_text"] for row in body["devices"]} == {"未配置"}  # UI-261
    assert "只读模式" in body["read_only_text"]


def test_settings_view_lists_the_registered_devices(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name="东区", position=2)
    body = client.get("/api/v0/settings").json()
    assert body["tier"] == 1  # the tier now, as /health says (PR #95 review)
    rows = body["devices"]
    assert [row["key"] for row in rows] == ["p1", "p2", "p3", "p4"]
    east = rows[1]
    assert east["configured"] is True and east["name"] == "东区"
    assert (east["slave_id_text"], east["enabled_text"], east["fail_stop_text"]) == (None,) * 3
    assert east["database_name"] == Path(device["path"]).name  # the device's own database
    assert east["database_path"] == device["path"]
    assert (east["snapshot_path"], east["imported_at"], east["snapshot_id"]) == (None, None, device["id"])
    assert east["tooltip"] == f"设备库：{device['path']}"
    assert rows[0]["configured"] is True and rows[0]["name"] == "占位1"  # positions have no gaps (V1.0.3)
    assert rows[2]["configured"] is False and rows[2]["state_text"] == "未配置"


def test_device_summary(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name="东区", position=1)
    response = client.get("/api/v0/devices/p1/summary")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["latest"]) == (2, "2026-10-18T08:05:00.000")
    assert body["records_text"] == "最近采集：2026-10-18 08:05:00.000 · 共 2 条"  # UI-080
    database = Path(device["path"])
    size = database.stat().st_size
    assert body["database_name"] == database.name
    assert body["database_size_text"] == f"{size / 1_000_000:.2f} MB"  # UI-077: 1 MB = 1,000,000 bytes
    assert body["database_text"] == f"数据库：{database.name} · 文件大小：{size / 1_000_000:.2f} MB"  # as V1.0.3
    assert body["serial_text"] == "设备序列号：0x1234ABCD"  # UI-081, from the database's app_settings
    assert body["status_text"] == "东区 · 本机 2.0 采集的设备库"
    assert body["poll_cycle_text"] == "300 秒（取自 2026-10-18 08:00:00.000 的采集记录）"


def test_device_summary_of_an_empty_old_database(client: TestClient, tmp_path: Path) -> None:
    path = v1_database(tmp_path / "v1" / "empty.sqlite3", [])
    register_device(client, path, name="空库", position=1)
    body = client.get("/api/v0/devices/p1/summary").json()
    assert (body["total"], body["latest"]) == (0, None)
    assert body["records_text"] == "最近采集：— · 共 0 条"
    assert body["serial_text"] == "设备序列号：库中没有记录"
    assert body["poll_cycle_text"] == "库中没有成功的采集记录"


def test_device_summary_with_unusable_identity_or_cycle(client: TestClient, tmp_path: Path) -> None:
    path = v1_database(tmp_path / "v1" / "odd.sqlite3", [record("2026-10-18T08:00:00.000", quality_json="[1]")])
    con = sqlite3.connect(path)
    con.execute("INSERT INTO app_settings VALUES('par_device_identity', 'not json', '2026-10-18T08:00:00.000')")
    con.commit()
    con.close()
    register_device(client, path, name="异常", position=1)
    body = client.get("/api/v0/devices/p1/summary").json()
    assert body["serial_text"] == "设备序列号：库中没有记录"  # load_par_device_identity reads it as None
    assert body["poll_cycle_text"] == "2026-10-18 08:00:00.000 的采集记录中没有可用的轮询周期"


def test_device_summary_errors(client: TestClient, source: Path) -> None:
    assert client.get("/api/v0/devices/p1/summary").status_code == 404
    snapshot = register_device(client, source, name="东区", position=1)
    Path(snapshot["path"]).unlink()
    response = client.get("/api/v0/devices/p1/summary")
    assert response.status_code == 503
    assert error_of(response)["code"] == "database_unavailable"


def test_no_write_route_exists(client: TestClient) -> None:
    """The write routes are exactly these: the tier switch and the tier-1 takeover (16_), and the tier-2 maintenance
    routes (17_; owner 2026-10-18), which answer 403 feature_disabled below tier 2
    (tests/acquisition/test_maintenance_rejections.py R1). No route reads the identity alone, writes the
    communication parameters outside maintenance or clears a halt (D-216 question 3, R21, R22)."""
    paths: dict[str, Any] = client.get("/api/v0/openapi.json").json()["paths"]
    writes = {(path, method) for path, item in paths.items() for method in item if method != "get"}
    assert writes == {
        ("/api/v0/snapshots", "post"),
        ("/api/v0/operations/inputs", "post"),
        ("/api/v0/operations/compute", "post"),
        ("/api/v0/operations/export", "post"),
        ("/api/v0/devices/{key}/export", "post"),
        ("/api/v0/tier/confirmations", "post"),
        ("/api/v0/tier", "put"),
        ("/api/v0/acquisition-config", "put"),
        ("/api/v0/acquisition-config/import-preview", "post"),  # reads V1.0.3's files, writes nothing (D-214)
        ("/api/v0/acquisition/start", "post"),
        ("/api/v0/acquisition/stop", "post"),
        ("/api/v0/support/diagnostics-bundle", "post"),  # API-27: writes one zip into the alpha's exports (D-226)
        ("/api/v0/shutdown", "post"),  # API-19: stops the service, shell only (no Origin), writes no data (PR #50)
        ("/api/v0/devices/{key}/dli/location", "put"),  # #116: dli_location only, as V1.0.3 (owner's approval)
        *MAINTENANCE_WRITES,
    }


MAINTENANCE_WRITES = {
    ("/api/v0/maintenance/page", "post"),
    ("/api/v0/maintenance/page", "delete"),
    ("/api/v0/maintenance/page/close/confirmations", "post"),
    ("/api/v0/maintenance/tab", "post"),
    ("/api/v0/maintenance/target", "put"),
    ("/api/v0/maintenance/diagnostics/read", "post"),
    ("/api/v0/maintenance/diagnostics/export", "post"),
    ("/api/v0/maintenance/calibration/read", "post"),
    ("/api/v0/maintenance/calibration/read/confirmations", "post"),
    ("/api/v0/maintenance/calibration/draft", "patch"),
    ("/api/v0/maintenance/calibration/discard", "post"),
    ("/api/v0/maintenance/calibration/write", "post"),
    ("/api/v0/maintenance/calibration/write/confirmations", "post"),
    ("/api/v0/maintenance/enter", "post"),
    ("/api/v0/maintenance/enter/confirmations", "post"),
    ("/api/v0/maintenance/comm/read", "post"),
    ("/api/v0/maintenance/comm/write", "post"),
    ("/api/v0/maintenance/comm/write/confirmations", "post"),
    ("/api/v0/maintenance/comm/verify", "post"),
    ("/api/v0/maintenance/leave", "post"),
    ("/api/v0/maintenance/leave/confirmations", "post"),
    ("/api/v0/maintenance/notice/dismiss", "post"),
    ("/api/v0/acquisition/devices/{key}/comm/read", "post"),
    ("/api/v0/acquisition/devices/comm/read", "delete"),  # leaving the settings page stops the re-read (D-218)
}
