"""The takeover through the API, with the coordinator really running on the byte-level fake bus (16_ 7.2, 7.4, 7.5).

Covers: rounds acquired and reported through GET /acquisition/status, the live overview and the event stream;
stopping releases the port and the lock; a global halt, a port that cannot be opened and an unfinished
maintenance session are reported as V1.0.3 reports them; configuration writes go only to the alpha's own files.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from par_app.database import ParDatabase
from tests.acquisition.conftest import Alpha, bind_clock, call, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    found = []
    for block in body.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "event" in lines:
            found.append((lines["event"], json.loads(lines["data"])))
    return found


def _start(alpha: Alpha, monkeypatch: pytest.MonkeyPatch, devices: dict[int, FakeDevice]) -> FakeSerial:
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    return FakeSerial(clock, devices)


def _stop(alpha: Alpha, port: FakeSerial) -> None:
    coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
    port.release = lambda: not coordinator._running
    assert alpha.post("/api/v0/acquisition/stop").status_code == 202
    pump(lambda: alpha.takeover() == "released")
    assert coordinator.isFinished()


def test_rounds_are_reported_by_status_live_overview_and_events(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice(), 2: FakeDevice(mode="silent")})
    port.hold_at = 400
    alpha.enable_tier_1()
    stream: dict[str, str] = {}
    reader = threading.Thread(target=lambda: stream.update(body=alpha.client.get("/api/v0/events").text))
    reader.start()
    pump(lambda: alpha.context.events.subscriber_count == 1)
    with wired(port):
        started = alpha.post("/api/v0/acquisition/start")
        assert started.status_code == 202 and started.json()["takeover"] == "running" and started.json()["lock_held"]
        pump(port.held.is_set)
        status = alpha.get("/api/v0/acquisition/status").json()
        north, south = status["devices"]
        bus = status["bus"]
        assert (bus["level"], bus["message"]) == ("ok", "总线已连接") and status["halt"] is None
        assert bus["notice"]["event_id"]  # the bus line is a numbered run event (#136)
        assert (north["position"], north["online"], north["level"]) == ("p1", True, "ok")
        assert north["latest_record_id"] >= 2 and north["status_text"].startswith("North（地址 1）· 采集成功")
        assert (south["online"], south["level"]) == (False, "warning") and south["failures"] >= 2
        run = status["run_status"]  # issue #73: V1.0.3's top-bar block
        assert run["bus"]["text"] == "总线：已连接" and run["acquisition"]["text"] == "采集运行中：部分设备异常"
        assert len(run["failures"]) == 1 and "South（地址 2）  连续第 " in run["failures"][0]
        assert run["failures"][0].endswith("（未启用失败停止，将继续按周期重试）")
        tier = alpha.get("/api/v0/tier").json()
        assert tier["text"] == "采集模式 · 正在采集" and tier["lock_held"]
        live = alpha.get("/api/v0/acquisition/devices/p1/latest").json()
        assert live["source"] == "live" and live["display_record"]["id"] == north["latest_record_id"]
        assert f"#{north['latest_record_id']}" in live["status"]["text"] and "采集已暂停" not in live["status"]["text"]
        assert not live["paused"] and live["poll_cycle_seconds"] == 40.0
        _stop(alpha, port)
    assert port.closed >= 1 and not alpha.host.lock.held
    assert alpha.get("/api/v0/acquisition/status").json()["bus"]["message"] == "未在采集：未连接设备"
    alpha.context.events.close()
    reader.join(10)
    names = [name for name, _ in _events(stream["body"])]
    assert names[0] == "takeover_state" and "acquisition_saved" in names and "device_state" in names
    assert "bus_state" in names and names[-1] == "takeover_state"
    states = [data["state"] for name, data in _events(stream["body"]) if name == "takeover_state"]
    assert states == ["starting", "running", "stopping", "released"]


def test_no_enabled_device_answering_reads_bus_abnormal_on_a_running_bus(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #131: the port opens, both devices stay silent: 总线：异常 although the bus message says it connected."""
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice(mode="silent"), 2: FakeDevice(mode="silent")})
    alpha.enable_tier_1()
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202

        def both_failed() -> bool:
            devices = alpha.context.acquisition.cache.snapshot()["devices"]
            return len(devices) == 2 and all(device["failures"] >= 1 for device in devices)

        pump(both_failed)
        run = alpha.get("/api/v0/acquisition/status").json()["run_status"]
        assert (run["bus"]["text"], run["bus"]["level"], run["bus"]["devices_silent"]) == ("总线：异常", "error", True)
        assert run["acquisition"]["text"] == "采集运行中：等待设备响应" and len(run["failures"]) == 2
        _stop(alpha, port)


def test_global_halt_is_reported_with_v103_text_and_no_clear_action(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice(mode="power_cycle"), 2: FakeDevice()})
    alpha.enable_tier_1()
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        pump(lambda: alpha.context.acquisition.cache.snapshot()["halt"] is not None)
        status = alpha.get("/api/v0/acquisition/status").json()
        halt = status["halt"]
        assert halt["name"] == "North" and halt["slave_id"] == 1 and halt["need_power_cycle"] is True
        assert "请为该设备重新上电，然后点“停止采集”，再点“开始采集”。" in halt["text"]
        assert halt["text"].endswith("点击“确认”只关闭提示，不恢复采集；保存配置也不能解除停止。")
        assert status["bus"]["level"] == "error" and all(d["level"] == "power" for d in status["devices"])
        assert status["run_status"]["bus"]["text"] == "总线：已停止（硬件异常）"
        assert status["run_status"]["acquisition"] == {
            "text": halt["message"],
            "level": "error",
            "notice": halt["notice"],
        }
        assert status["run_status"]["bus"]["notice"] == halt["notice"] and halt["notice"]["event_id"]  # #136
        assert alpha.get("/api/v0/tier").json()["text"] == "采集模式 · 采集已停止（锁停），见提示"
        live = alpha.get("/api/v0/acquisition/devices/p2/latest").json()
        assert live["paused"] is True
        frames = len(port.written())
        alpha.clock.advance(3600)
        pump(lambda: True)
        assert len(port.written()) == frames  # halted: no frame until stopped and started again
        _stop(alpha, port)


def test_port_that_cannot_open_is_a_bus_error_and_acquisition_keeps_trying(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice()})
    port.open_error = "could not open port 'COM7': FileNotFoundError"
    alpha.enable_tier_1()
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        seen: list[dict[str, str]] = []
        # the bus message as it was when the error was reported: the coordinator retries about every second of
        # its (fast virtual) clock and shows "正在连接 …" again, so a later read may already see the retry
        pump(lambda: seen.append(alpha.context.acquisition.cache.snapshot()["bus"]) or seen[-1]["level"] == "error")
        assert seen[-1]["message"] == "总线连接失败：could not open port 'COM7': FileNotFoundError"
        status = alpha.get("/api/v0/acquisition/status").json()
        assert status["takeover"] == "running" and status["halt"] is None
        pump(lambda: alpha.context.acquisition.cache.snapshot()["devices"][0]["failures"] >= 2)
        run = alpha.get("/api/v0/acquisition/status").json()["run_status"]  # issue #73 criterion 2
        assert run["acquisition"] == {"text": "采集运行中：等待设备响应", "level": "warn", "notice": None}
        assert run["failure_notices"] and all(notice["event_id"] for notice in run["failure_notices"])  # #136
        assert "North（地址 1）  连续第 " in run["failures"][0] and "次尝试失败：总线连接失败：" in run["failures"][0]
        assert run["failures"][0].endswith("（未启用失败停止，将继续按周期重试）")
        port.open_error = None
        pump(lambda: alpha.context.acquisition.cache.snapshot()["bus"]["level"] == "ok")
        port.hold_at = len(port.written()) + 5
        pump(port.held.is_set)
        _stop(alpha, port)


def test_unfinished_maintenance_session_pauses_acquisition(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    stored = write_config(alpha.data_dir, two_devices())
    with ParDatabase(stored.devices[0].database_path).connect() as connection:
        connection.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('communication_maintenance',?,?)",
            (json.dumps({"pending": {"slave_id": 5}, "verified": None}), "2026-10-18T09:00:00.000"),
        )
    port = _start(alpha, monkeypatch, {1: FakeDevice(), 2: FakeDevice()})
    alpha.enable_tier_1()
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        status = alpha.get("/api/v0/acquisition/status").json()
        assert status["takeover"] == "running" and status["maintenance"] is True
        alpha.clock.advance(1)
        pump(lambda: True)
        assert port.opened == 0 and port.written() == []
        alpha.post("/api/v0/acquisition/stop")
        pump(lambda: alpha.takeover() == "released")


def test_saving_the_configuration_applies_it_and_writes_only_alpha_files(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice(), 2: FakeDevice(), 3: FakeDevice()})
    port.hold_at = 300
    alpha.enable_tier_1()
    config = alpha.get("/api/v0/acquisition-config").json()
    assert config["path"] == str(alpha.data_dir / "config" / "app_config.json")
    body = {
        "bus": config["bus"],
        "devices": [
            {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
            for d in config["devices"]
        ]
        + [{"name": "West", "slave_id": 3, "enabled": True}],
    }
    assert alpha.put("/api/v0/acquisition-config", body).json()["error"]["code"] == "not_running"
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        saved = alpha.put("/api/v0/acquisition-config", body)
        assert saved.status_code == 200, saved.text
        west = saved.json()["devices"][2]
        assert west["database_path"] == str(alpha.data_dir / "data" / "devices" / "West.sqlite3")
        assert west["database_exists"] and west["inside_alpha"]
        pump(lambda: len(alpha.context.acquisition.cache.snapshot()["devices"]) == 3)
        refused = alpha.put("/api/v0/acquisition-config", body)  # West again as a new device: its file exists now
        assert refused.status_code == 400
        assert refused.json()["error"]["message"].startswith("默认数据库文件已存在：West.sqlite3。")  # V1.0.3's text
        pump(port.held.is_set)
        _stop(alpha, port)


def test_database_outside_the_alpha_directory_is_refused(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    v1_root = tmp_path / "V1.0.3"
    v1_config = write_config(v1_root, two_devices())
    alpha_config = alpha.data_dir / "config" / "app_config.json"
    alpha_config.parent.mkdir(parents=True, exist_ok=True)
    alpha_config.write_text(json.dumps(v1_config.to_dict(), ensure_ascii=False), encoding="utf-8")
    port = _start(alpha, monkeypatch, {1: FakeDevice()})
    alpha.enable_tier_1()
    with wired(port):
        refused = alpha.post("/api/v0/acquisition/start")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "config_unavailable"
    assert "只能使用本软件数据目录下的设备库" in refused.json()["error"]["message"]
    assert port.opened == 0 and not alpha.host.lock.held and alpha.takeover() == "released"
    write_config(alpha.data_dir, two_devices())
    port.hold_at = 100
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        foreign = {
            "bus": two_devices().bus.to_dict(),
            "devices": [
                {"name": "North", "slave_id": 1, "enabled": True, "database_path": v1_config.devices[0].database_path}
            ],
        }
        response = alpha.put("/api/v0/acquisition-config", foreign)
        assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_argument"
        pump(port.held.is_set)
        _stop(alpha, port)


def test_events_need_the_token_and_same_origin(alpha: Alpha) -> None:
    assert call(lambda: alpha.client.get("/api/v0/events", headers={"X-PAR-Token": "wrong"})).status_code == 401
    other = call(lambda: alpha.client.get("/api/v0/events", headers={"Origin": "http://evil.example"}))
    assert other.status_code == 403


def _tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_v103_directory_is_byte_for_byte_unchanged(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """16_ 7.4: a V1.0.3 program directory (config and both databases, one with a -wal beside it) next to the alpha
    is not written while the alpha acquires with the same registration, saves its configuration and stops."""
    v1_root = tmp_path / "V1.0.3"
    stored = write_config(v1_root, two_devices())
    wal = Path(stored.devices[0].database_path + "-wal")
    wal.write_bytes(b"")
    before = _tree(v1_root)
    write_config(alpha.data_dir, two_devices())
    port = _start(alpha, monkeypatch, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 500
    alpha.enable_tier_1()
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        config = alpha.get("/api/v0/acquisition-config").json()
        body = {
            "bus": config["bus"],
            "devices": [
                {
                    "name": d["name"],
                    "slave_id": d["slave_id"],
                    "enabled": d["enabled"],
                    "database_path": d["database_path"],
                }
                for d in config["devices"]
            ],
        }
        assert alpha.put("/api/v0/acquisition-config", body).status_code == 200
        pump(port.held.is_set)
        live = alpha.get("/api/v0/acquisition/devices/p1/latest").json()
        assert live["device"]["database_path"].startswith(str(alpha.data_dir))
        _stop(alpha, port)
    assert _tree(v1_root) == before


def test_first_run_waits_for_devices_with_the_delivered_bus_defaults(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    """负责人 2026-10-27: a new installation acquires at once, so without an enabled device the mode reads 等待登记设备,
    not 正在采集, until a configuration is saved; the blank form is the delivered probes' bus (57600, no
    parity, 40 s)."""
    port = _start(alpha, monkeypatch, {1: FakeDevice(), 2: FakeDevice(), 3: FakeDevice(), 4: FakeDevice()})
    port.hold_at = 300
    alpha.enable_tier_1()
    config = alpha.get("/api/v0/acquisition-config").json()
    assert not config["exists"] and not config["configured"]
    for bus in (config["bus"], config["blank_bus"]):
        assert (bus["baudrate"], bus["parity"], bus["poll_cycle_seconds"]) == (57600, "N", 40.0)
    assert config["poll_cycle_seconds"] == 40.0 and [row["slave_id"] for row in config["rows"]] == [1, 2, 3, 4]
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(lambda: alpha.takeover() == "running")
        tier = alpha.get("/api/v0/tier").json()
        assert (tier["text"], tier["level"]) == ("采集模式 · 等待登记设备（请到“设置与导出”登记并保存）", "info")
        bus = {**config["bus"], "serial_port": "COM7"}
        none = alpha.put("/api/v0/acquisition-config", {"bus": bus, "devices": []})
        assert none.json()["error"]["message"] == "请至少登记并启用一台设备，最多四台。"  # V1.0.3 saves none
        four = [{"name": f"P{n}", "slave_id": n, "enabled": True} for n in range(1, 5)]
        saved = alpha.put("/api/v0/acquisition-config", {"bus": bus, "devices": four})
        assert saved.status_code == 200, saved.text
        pump(lambda: len(alpha.context.acquisition.cache.snapshot()["devices"]) == 4)
        assert alpha.get("/api/v0/tier").json()["text"] == "采集模式 · 正在采集"
        saved_bus = json.loads((alpha.data_dir / "config" / "app_config.json").read_text(encoding="utf-8"))["bus"]
        assert (saved_bus["baudrate"], saved_bus["parity"], saved_bus["poll_cycle_seconds"]) == (57600, "N", 40.0)
        pump(port.held.is_set)
        _stop(alpha, port)
