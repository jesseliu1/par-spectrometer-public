"""Tier 2 end to end on the fake bus, through the HTTP API (17_ sections 4, 5): the whole chain of the e2e test
("开 2 级 → 进入维护 → 读校准 → 改值 → 写入 → 核对 → 退出维护并恢复采集") plus the diagnostics read, checked on the
device model and in the device database."""

from __future__ import annotations

import json
import sqlite3

import pytest

from tests.acquisition.conftest import Alpha, pump
from tests.acquisition.maintenance_support import (
    STATE,
    controller,
    enter,
    fake_port,
    form,
    open_page,
    save_registration,
    start,
    wait_idle,
)
from tests.support.fake_bus import FakeDevice, wired

pytestmark = pytest.mark.qt


def test_diagnostics_calibration_and_communication_round(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    north = FakeDevice(errors=[0, 2] + [0] * 20)
    port = fake_port(monkeypatch, {1: north, 2: FakeDevice()})
    with wired(port):
        start(alpha)
        state = open_page(alpha)  # the diagnostics tab reads once by itself (MAINT-025)
        diagnostics = state["diagnostics"]
        assert diagnostics["identity"].startswith("设备身份：PAR-FAKE    序列号：305419896 (0x12345678)")
        assert [row["count"] for row in diagnostics["rows"]][:2] == ["0", "2"]
        assert diagnostics["rows"][1]["delta"] == "—"  # first read of this page session (D-134 A)
        north.errors[1] = 5
        assert alpha.post("/api/v0/maintenance/diagnostics/read").status_code == 200
        state = wait_idle(alpha)
        assert state["diagnostics"]["rows"][1]["delta"] == "3"

        # calibration: the tab reads by itself, an edit is rounded like V1.0.3's box, the write reads back
        assert alpha.post("/api/v0/maintenance/tab", {"tab": 1}).status_code == 200
        state = wait_idle(alpha)
        assert state["calibration"]["write_enabled"] and not state["calibration"]["dirty"]
        edited = alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y1", "value": -1.234})
        assert edited.status_code == 200, edited.text
        fields = {row["name"]: row for row in edited.json()["calibration"]["fields"]}
        assert fields["y1"]["text"] == "-1.23" and edited.json()["calibration"]["value_state"] == "待写入修改"
        written = alpha.confirmed("/api/v0/maintenance/calibration/write")
        assert written.status_code == 200, written.text
        state = wait_idle(alpha)
        assert (
            not state["calibration"]["dirty"] and state["calibration"]["status"] == "校准状态码：3"
        )  # the write status (MAINT-041)
        assert north.calibration[6] == pytest.approx(-0.0123)

        _communication(alpha, north)
    _check_databases(alpha)
    _check_maintenance_log(alpha)


def _communication(alpha: Alpha, north: FakeDevice) -> None:
    """Enter, read, write a new address, automatic verification, update the registration, resume."""
    assert alpha.post("/api/v0/maintenance/tab", {"tab": 2}).status_code == 200
    state = enter(alpha)
    assert state["maintenance"] and state["communication"]["read_enabled"]
    assert alpha.post("/api/v0/maintenance/comm/read", form(old=1)).status_code == 200
    state = wait_idle(alpha)
    assert state["communication"]["write_enabled"], state["communication"]["state"]
    written = alpha.confirmed("/api/v0/maintenance/comm/write", form(old=1, new=7))
    assert written.status_code == 200, written.text
    state = wait_idle(alpha)
    assert north.comm == [7, 3, 0]
    assert state["communication"]["state"].startswith("设备身份和新参数核对通过")
    assert not state["footer"]["resume_enabled"]  # the registration still says address 1 (MAINT-003)
    assert "请先在常规设置中手动更新" in state["footer"]["resume_reason"]

    # the operator updates the registration (tier 1's configuration editor), then resumes
    save_registration(alpha, {"North": 7})
    pump(lambda: controller(alpha).resume_gate().allowed)
    resumed = alpha.confirmed("/api/v0/maintenance/leave")
    assert resumed.status_code == 200, resumed.text
    pump(lambda: not controller(alpha).maintenance())
    state = alpha.get(STATE).json()
    assert not state["maintenance"]


def _check_databases(alpha: Alpha) -> None:
    database = sqlite3.connect(alpha.data_dir / "data" / "devices" / "North.sqlite3")
    try:
        saved_state = database.execute(
            "SELECT value_json FROM app_settings WHERE key='communication_maintenance'"
        ).fetchone()
        audits = database.execute("SELECT action FROM calibration_audit ORDER BY id").fetchall()
    finally:
        database.close()
    assert json.loads(saved_state[0]) == {"pending": None, "verified": None}
    assert [row[0] for row in audits][-2:] == ["read", "write"]


def _check_maintenance_log(alpha: Alpha) -> None:
    """维护记录 (API-28, D-226) on the rows the real code wrote: the calibration write with its readback, the
    address write verified with the new parameters; nothing pending, nothing failed."""
    response = alpha.get("/api/v0/support/maintenance-log?device=p1")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [(item["kind"], item["result_text"]) for item in items] == [
        ("comm_verify", "成功"),
        ("comm_write", "成功"),
        ("calibration_write", "成功"),
    ]
    verify, write, calibration = items
    assert write["before_text"].startswith("地址 1 · ") and write["after_text"].startswith("地址 7 · ")
    assert write["detail"].startswith("已用新参数核对通过")
    assert verify["readback_text"].startswith("地址 7 · ") and "PAR-FAKE" in verify["readback_text"]
    assert "y1=-0.0123" in calibration["after_text"] and "y1=-0.0123" in calibration["readback_text"]
    assert "未记录" not in calibration["before_text"]
