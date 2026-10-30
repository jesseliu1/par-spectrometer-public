"""Contract tests of the settings page's 设备状态与最近日志 (api-contract-v0 API-16; issue #107).

Tier 1 only: the status line comes from the coordinator's device state in the takeover's StatusCache while the
alpha acquires, the log from the device database's diagnostics table (read only, mode=ro). Tier 0 has no device, so
the request is 404 like every device read. The texts are V1.0.3's (MainWindow.refresh_settings_console);
test_settings_logs_parity.py compares them with the real window.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.acquisition_host.host import RELEASED_BUS
from par_app.api.context import ServiceContext
from par_app.application.settings import NOT_TAKEN_OVER
from par_app.database import ParDatabase

from .conftest import assert_read_only, error_of, record, register_device, v1_database

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("UI-076 UI-078 UI-079 UI-080 UI-081 UI-100 UI-101 UI-104 UI-279 UI-280"),
]
EAST = "东区"
SERIAL = 0x1234ABCD


def add_log(path: Path, rows: list[tuple[str, str | None, str, str, str | None]]) -> None:
    """Insert (occurred_at, level, category, message, details_json) rows in this order (oldest first)."""
    con = sqlite3.connect(path)
    con.executemany("INSERT INTO diagnostics(occurred_at,level,category,message,details_json) VALUES(?,?,?,?,?)", rows)
    con.commit()
    con.close()


LOG_ROWS: list[tuple[str, str | None, str, str, str | None]] = [
    ("2026-10-18T08:00:00.000", "INFO", "connection", "总线已连接", "{}"),
    ("2026-10-18T08:01:00.000", "INFO", "connection", "已读取设备当前通信参数", "{}"),  # hidden (UI-076)
    ("2026-10-18T08:02:00.000", "WARNING", "communication", "设备无应答", json.dumps({"failures": 1})),
    ("2026-10-18T08:03:00.000", "INFO", "communication_recovery", "通信已恢复", "{}"),
    ("2026-10-18T08:04:00.000", "INFO", "diagnostics_read", "已读取设备维护诊断", None),
    ("2026-10-18T08:05:00.000", "ERROR", "something_new", "未知类别", "<html>raw & not JSON</html>"),
    ("2026-10-18T08:06:00.000", "WARNING", "connection", "已读取设备当前通信参数", "{}"),  # not INFO: shown
]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = v1_database(tmp_path / "v1" / "east.sqlite3", [record("2026-10-18T08:00:00.000")])
    ParDatabase(path).save_par_device_identity(SERIAL, 2, "PAR-01")
    add_log(path, LOG_ROWS)
    return path


def _state(device: dict[str, Any], **overrides: object) -> dict[str, Any]:
    """The coordinator's device snapshot as the event bridge puts it into the cache (DeviceRuntimeState.snapshot)."""
    base = {
        "key": EAST,
        "name": EAST,
        "slave_id": 1,
        "online": True,
        "level": "ok",
        "message": "采集正常",
        "exposure_status": 0,
        "database_path": device["path"],
    }
    return {**base, **overrides}


def _set_state(client: TestClient, state: dict[str, Any]) -> None:
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    context.acquisition.cache.set_device(state)


def test_logs_in_tier_0_are_not_found(client: TestClient) -> None:
    response = client.get("/api/v0/devices/p1/logs")
    assert response.status_code == 404
    assert error_of(response)["code"] == "device_not_found"


def test_log_table_follows_v1(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name=EAST, position=1)
    _set_state(client, _state(device))
    response = client.get("/api/v0/devices/p1/logs")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["columns"] == ["时间", "类别", "结果"]
    assert (body["details_title"], body["copy_label"]) == ("日志详情", "复制全部")
    assert body["device"] == {"key": "p1", "name": EAST} and body["snapshot_id"] == device["id"]
    items = body["items"]
    assert [item["occurred_at"][11:16] for item in items] == ["08:06", "08:05", "08:04", "08:03", "08:02", "08:00"]
    assert [(item["category_text"], item["result_text"], item["error"]) for item in items] == [
        ("连接", "通信参数读取成功", True),
        ("其他", "未知类别", True),  # UI-079: unknown category
        ("设备诊断", "设备诊断读取成功", False),
        ("通信恢复", "通信已恢复", False),
        ("通信异常", "设备无应答", True),  # UI-279: WARNING in red
        ("连接", "总线已连接", False),
    ]
    assert items[0]["time_text"] == "2026-10-18 08:06:00.000"
    assert items[4]["category_tooltip"] == "通信异常\ncommunication"
    assert items[4]["result_tooltip"] == '设备无应答\n{"failures": 1}'  # UI-280
    assert items[5]["result_tooltip"] == "总线已连接"  # "{}" adds nothing
    assert items[2]["details"] is None and items[2]["result_tooltip"] == "已读取设备维护诊断"
    database = Path(device["path"]).resolve()
    assert items[1]["details_text"] == (  # UI-100, UI-104: plain text, the raw details kept
        f"设备：{EAST}\n数据库：{database}\n时间：2026-10-18 08:05:00.000\n级别：ERROR\n类别：其他（something_new）\n\n"
        "消息：\n未知类别\n\n详情：\n<html>raw & not JSON</html>"
    )
    assert items[2]["details_text"].endswith("详情：\n—")


def test_log_reads_300_rows_and_shows_at_most_50(client: TestClient, tmp_path: Path) -> None:
    path = v1_database(tmp_path / "v1" / "busy.sqlite3", [])
    shown = [(f"2026-10-18T07:{index:02d}:00.000", "INFO", "connection", f"连接 {index}", "{}") for index in range(60)]
    hidden = [("2026-10-18T08:00:00.000", "INFO", "connection", "已读取设备当前通信参数", "{}")] * 260
    add_log(path, shown + hidden)
    register_device(client, path, name=EAST, position=1)
    items = client.get("/api/v0/devices/p1/logs").json()["items"]
    assert [item["message"] for item in items] == [f"连接 {index}" for index in range(59, 19, -1)]  # 300 - 260 = 40
    add_log(path, [("2026-10-18T09:00:00.000", "INFO", "time_sync", f"对时 {index}", "{}") for index in range(70)])
    register_device(client, path, name=EAST, position=1)
    items = client.get("/api/v0/devices/p1/logs").json()["items"]
    assert len(items) == 50 and items[0]["message"] == "对时 69" and items[0]["category_text"] == "设备对时"


@pytest.mark.parametrize(
    ("overrides", "text", "tone"),
    [
        ({}, f"{EAST} · 在线 · 采集正常 · 曝光：正常", "normal"),
        ({"exposure_status": 1}, f"{EAST} · 在线 · 采集正常 · 曝光：过曝光", "normal"),
        ({"exposure_status": 2}, f"{EAST} · 在线 · 采集正常 · 曝光：欠曝光", "normal"),
        ({"exposure_status": 7}, f"{EAST} · 在线 · 采集正常 · 曝光：未知", "normal"),
        ({"exposure_status": None}, f"{EAST} · 在线 · 采集正常", "normal"),
        ({"level": "warning", "message": "正在连接设备…"}, f"{EAST} · 正在连接设备…", "warning"),
        ({"level": "error", "message": "通信失败：设备无应答"}, f"{EAST} · 通信失败：设备无应答", "error"),
        ({"level": "power", "message": "需要重新上电"}, f"{EAST} · 需要重新上电", "error"),
        ({"level": "idle", "message": "尚未采集"}, f"{EAST} · 尚未采集", "muted"),
    ],
)
def test_status_line_follows_the_device_state(
    client: TestClient, source: Path, overrides: dict[str, object], text: str, tone: str
) -> None:
    device = register_device(client, source, name=EAST, position=1)
    _set_state(client, _state(device, **overrides))
    status = client.get("/api/v0/devices/p1/logs").json()["status"]
    assert (status["text"], status["tone"]) == (text, tone)
    assert status["tooltip"] == f"{EAST}\n设备序列号：0x1234ABCD"  # UI-081


def test_status_line_before_the_device_has_a_state(client: TestClient, source: Path, tmp_path: Path) -> None:
    device = register_device(client, source, name=EAST, position=1)
    status = client.get("/api/v0/devices/p1/logs").json()["status"]
    assert (status["text"], status["level"], status["tone"]) == (f"{EAST} · 等待本次采集", "idle", "muted")
    _set_state(client, _state(device, database_path=str(tmp_path / "other.sqlite3")))  # another database there
    assert client.get("/api/v0/devices/p1/logs").json()["status"]["text"] == f"{EAST} · 等待本次采集"


def test_status_line_while_nothing_is_taken_over(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name=EAST, position=1, acquiring=False)
    _set_state(client, _state(device))  # the last state of a stopped takeover stays in the cache
    body = client.get("/api/v0/devices/p1/logs").json()
    assert body["status"]["text"] == f"{EAST} · 未在采集：未连接设备"
    assert (body["status"]["level"], body["status"]["tone"]) == ("idle", "muted")
    assert len(body["items"]) == 6  # the log already in the database is still shown
    assert NOT_TAKEN_OVER == RELEASED_BUS[1]


def test_status_tooltip_without_identity(client: TestClient, tmp_path: Path) -> None:
    path = v1_database(tmp_path / "v1" / "new.sqlite3", [])
    register_device(client, path, name=EAST, position=1)
    body = client.get("/api/v0/devices/p1/logs").json()
    assert body["status"]["tooltip"] == f"{EAST}\n设备序列号：尚未读取"
    assert body["items"] == []


def test_database_without_log_table(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "v1" / "old.sqlite3"
    path.parent.mkdir(parents=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE acquisitions (id INTEGER PRIMARY KEY, acquired_at TEXT)")
    con.commit()
    con.close()
    register_device(client, path, name=EAST, position=1)
    body = client.get("/api/v0/devices/p1/logs").json()
    assert body["items"] == [] and body["status"]["tooltip"] == f"{EAST}\n设备序列号：尚未读取"


def test_reading_the_log_writes_nothing(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name=EAST, position=1)
    database = Path(device["path"])
    before = database.read_bytes()
    assert client.get("/api/v0/devices/p1/logs").status_code == 200
    assert_read_only(database, before)


def test_missing_database_is_unavailable(client: TestClient, source: Path) -> None:
    device = register_device(client, source, name=EAST, position=1)
    Path(device["path"]).unlink()
    response = client.get("/api/v0/devices/p1/logs")
    assert response.status_code == 503
    assert error_of(response)["code"] == "database_unavailable"
