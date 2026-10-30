"""Tier switch and tier-0 refusals (16_ 4, 7.5; owner 2026-10-18: default tier 0, tier 1 explicit and confirmed twice).

* Tier 0 (factory) refuses every acquisition request and every configuration write with 403 feature_disabled,
  builds no DeviceHub, opens no port and takes no lock.
* 0 -> 1 needs a confirmation id this service issued, unexpired, unused, for tier 1; otherwise 409.
* 1 -> 0 while acquiring stops first (202), then writes tier 0.
"""

from __future__ import annotations

import json

import pytest

from par_app.application.acquisition import DOWN_CONFIRM, STOP_AFTER_HALT_NOTE, STOP_CONFIRM
from par_app.application.tier import CONFIRMATION_SECONDS, SETTINGS_FILE_NAME, status_text
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt

TIER_ONE_REQUESTS = [
    ("get", "/api/v0/acquisition/status", None),
    ("get", "/api/v0/acquisition-config", None),
    ("put", "/api/v0/acquisition-config", {"bus": {}, "devices": []}),
    ("post", "/api/v0/acquisition/start", None),
    ("post", "/api/v0/acquisition/stop", None),
    ("get", "/api/v0/acquisition/devices/p1/latest", None),
    ("post", "/api/v0/acquisition-config/import-preview", {"source_path": "V1.0.3"}),
]


def _request(alpha: Alpha, method: str, path: str, body: dict[str, object] | None) -> tuple[int, dict[str, object]]:
    if method == "get":
        response = alpha.get(path)
    elif method == "post":
        response = alpha.post(path, body)
    else:
        response = alpha.put(path, body or {})
    return response.status_code, response.json()


def test_factory_tier_is_0_and_refuses_every_acquisition_request(alpha: Alpha) -> None:
    write_config(alpha.data_dir, two_devices())
    port = FakeSerial(yielding_clock(), {1: FakeDevice()})
    state = alpha.get("/api/v0/tier").json()
    assert state["tier"] == 0 and state["takeover"] == "released" and not state["lock_held"]
    assert state["text"] == "只读模式（不连接设备）" and state["level"] == "muted"
    assert alpha.get("/api/v0/health").json()["tier"] == 0
    with wired(port):
        for method, path, body in TIER_ONE_REQUESTS:
            status, payload = _request(alpha, method, path, body)
            valid_body = path != "/api/v0/acquisition-config" or method != "put"
            assert status == (403 if valid_body else 400), (method, path, payload)
            if valid_body:
                assert payload["error"]["code"] == "feature_disabled"  # type: ignore[index]
    assert alpha.host.hub is None and not alpha.host.lock.held and port.opened == 0


def test_valid_config_write_in_tier_0_is_403(alpha: Alpha) -> None:
    body = {"bus": two_devices().bus.to_dict(), "devices": [{"name": "A", "slave_id": 1, "enabled": True}]}
    response = alpha.put("/api/v0/acquisition-config", body)
    assert response.status_code == 403 and response.json()["error"]["code"] == "feature_disabled"
    assert not (alpha.data_dir / "config" / "app_config.json").exists()


def test_tier_1_needs_a_valid_unused_unexpired_confirmation(alpha: Alpha) -> None:
    settings = alpha.data_dir / "config" / SETTINGS_FILE_NAME
    missing = alpha.put("/api/v0/tier", {"tier": 1})
    assert missing.status_code == 409 and missing.json()["error"]["code"] == "confirmation_required"
    forged = alpha.put("/api/v0/tier", {"tier": 1, "confirmation_id": "made-up"})
    assert forged.status_code == 409
    # the page shows this text as it is (TierPanel): alpha.5 wording, no "档位"
    assert forged.json()["error"]["message"].startswith("开启采集模式需要先在确认框中确认")
    assert "档位" not in forged.json()["error"]["message"]
    assert alpha.post("/api/v0/tier/confirmations", {"tier": 0}).status_code == 400
    issued = alpha.post("/api/v0/tier/confirmations", {"tier": 1}).json()
    assert "其他软件不能使用该串口" in issued["notice"] and "自动开始采集" in issued["notice"]
    assert "V1.0.3" not in issued["notice"]  # issue #119: no V1.0.3 on the page
    assert "内部试用" not in issued["notice"]  # UAT: no internal-trial wording
    alpha.clock.advance(CONFIRMATION_SECONDS)
    expired = alpha.put("/api/v0/tier", {"tier": 1, "confirmation_id": issued["confirmation_id"]})
    assert expired.status_code == 409 and "过期" in expired.json()["error"]["message"]
    assert not settings.exists()
    issued = alpha.post("/api/v0/tier/confirmations", {"tier": 1}).json()
    accepted = alpha.put("/api/v0/tier", {"tier": 1, "confirmation_id": issued["confirmation_id"]})
    assert accepted.status_code == 200 and accepted.json()["tier"] == 1
    assert accepted.json()["text"] == "采集模式 · 未在采集（可点“开始采集”）"
    assert json.loads(settings.read_text(encoding="utf-8")) == {"device_write_tier": 1}
    alpha.put("/api/v0/tier", {"tier": 0})
    reused = alpha.put("/api/v0/tier", {"tier": 1, "confirmation_id": issued["confirmation_id"]})
    assert reused.status_code == 409 and alpha.get("/api/v0/tier").json()["tier"] == 0


def test_tier_1_does_not_take_over_by_itself(alpha: Alpha) -> None:
    write_config(alpha.data_dir, two_devices())
    port = FakeSerial(yielding_clock(), {1: FakeDevice()})
    with wired(port):
        alpha.enable_tier_1()
        assert alpha.get("/api/v0/acquisition/status").json()["takeover"] == "released"
    assert port.opened == 0 and alpha.host.hub is None and not alpha.host.lock.held


def test_unreadable_settings_file_counts_as_tier_0(alpha: Alpha) -> None:
    settings = alpha.data_dir / "config" / SETTINGS_FILE_NAME
    settings.write_text('{"device_write_tier": 1', encoding="utf-8")
    state = alpha.get("/api/v0/tier").json()
    assert state["tier"] == 0 and state["settings_problem"]
    settings.write_text('{"device_write_tier": 3}', encoding="utf-8")  # 2 is a tier since 17_
    assert alpha.get("/api/v0/tier").json()["tier"] == 0


def test_the_product_reads_tier_1_without_a_usable_settings_file(alpha: Alpha) -> None:
    """Issue #119 (owner 2026-10-27): with the product's default (service_main --first-run-tier 1), a missing,
    unreadable or invalid settings file all read tier 1, and the problem is still reported to the page."""
    tiers = alpha.context.acquisition.tiers
    tiers.default = 1
    settings = alpha.data_dir / "config" / SETTINGS_FILE_NAME
    assert not settings.exists() and alpha.get("/api/v0/tier").json()["tier"] == 1
    settings.write_text('{"device_write_tier": 1', encoding="utf-8")
    state = alpha.get("/api/v0/tier").json()
    assert state["tier"] == 1 and state["settings_problem"]
    settings.write_text('{"device_write_tier": 3}', encoding="utf-8")
    state = alpha.get("/api/v0/tier").json()
    assert state["tier"] == 1 and "模式值 3 无效" in state["settings_problem"]
    settings.write_text('{"device_write_tier": 0}', encoding="utf-8")  # a tier 0 written earlier is kept
    assert alpha.get("/api/v0/tier").json()["tier"] == 0


def test_tier_0_while_acquiring_stops_first_then_writes_tier_0(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 60
    with wired(port):
        alpha.enable_tier_1()
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(port.held.is_set)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        response = alpha.put("/api/v0/tier", {"tier": 0})
        assert response.status_code == 202 and response.json()["tier"] == 1
        pump(lambda: alpha.get("/api/v0/tier").json()["tier"] == 0)
    state = alpha.get("/api/v0/tier").json()
    assert state["takeover"] == "released" and not state["lock_held"]
    assert coordinator.isFinished() and port.closed >= 1
    assert alpha.post("/api/v0/acquisition/start").status_code == 403


def test_confirmation_texts_come_from_the_service_and_repeat_a_halt(alpha: Alpha) -> None:
    """The stop and 1 -> 0 confirmations are the service's texts (review nit: no fixed copy in the page). With a halt
    the stop confirmation repeats the halt text and says power-cycling comes first: stop then start builds a new
    coordinator, which is the same as restarting V1.0.3 and clears nothing on the device (review Q1, D-212 q8)."""
    alpha.enable_tier_1()
    state = alpha.get("/api/v0/tier").json()
    assert state["stop_text"] == STOP_CONFIRM and "最长约 40 秒" in state["stop_text"]
    assert state["down_text"] == DOWN_CONFIRM
    alpha.context.acquisition.cache.set_halt(
        {"occurred_at": "2026-10-18 09:00:00", "name": "North", "slave_id": 1, "reason": "探头要求重新上电"}
    )
    halted = alpha.get("/api/v0/tier").json()["stop_text"]
    assert halted.startswith(STOP_CONFIRM) and STOP_AFTER_HALT_NOTE in halted
    assert "设备“North”（地址 1）：探头要求重新上电。" in halted


def test_other_writes_are_busy_while_the_takeover_stops(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    """16_ 7.5: while stopping, the other write requests are 409 busy (not not_running)."""
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 60
    body = {"bus": two_devices().bus.to_dict(), "devices": [{"name": "North", "slave_id": 1, "enabled": True}]}
    with wired(port):
        alpha.enable_tier_1()
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(port.held.is_set)
        alpha.context.acquisition.cache.set_takeover("stopping", True)  # as the stop request leaves it
        saved = alpha.put("/api/v0/acquisition-config", body)
        assert saved.status_code == 409 and saved.json()["error"]["code"] == "busy"
        again = alpha.post("/api/v0/acquisition/stop")
        assert again.status_code == 409 and again.json()["error"]["code"] == "busy"
        alpha.context.acquisition.cache.set_takeover("running", True)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        assert alpha.post("/api/v0/acquisition/stop").status_code == 202
        pump(lambda: alpha.takeover() == "released")


def test_tier_2_is_confirmed_twice_on_top_of_tier_1(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    """17_ 6.1: only 1 -> 2, with the service's own notice and second layer; 2 -> 1 keeps nothing else."""
    refused = alpha.post("/api/v0/tier/confirmations", {"tier": 2})
    assert refused.status_code == 409 and refused.json()["error"]["message"] == "请先开启采集模式，再开启维护模式"
    alpha.enable_tier_1()
    issued = alpha.post("/api/v0/tier/confirmations", {"tier": 2}).json()
    assert issued["notice"].startswith("开启维护模式之后：") and "内部试用" not in issued["notice"]
    used_for_1 = alpha.put("/api/v0/tier", {"tier": 2, "confirmation_id": "x"})
    assert used_for_1.status_code == 409
    state = alpha.put("/api/v0/tier", {"tier": 2, "confirmation_id": issued["confirmation_id"]}).json()
    assert state["tier"] == 2 and state["text"] == "维护模式 · 未在采集（可点“开始采集”）"
    assert state["down_to_1_text"].startswith("关闭维护模式后")
    write_config(alpha.data_dir, two_devices())
    port = FakeSerial(yielding_clock(), {1: FakeDevice(), 2: FakeDevice()})
    bind_clock(monkeypatch, port.clock)  # type: ignore[arg-type]
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        assert alpha.get("/api/v0/tier").json()["text"] == "维护模式 · 正在采集"
        lowered = alpha.put("/api/v0/tier", {"tier": 1})
        assert lowered.status_code == 200 and lowered.json()["tier"] == 1 and lowered.json()["takeover"] == "running"
        alpha.post("/api/v0/acquisition/stop")
        pump(lambda: alpha.takeover() == "released")


def test_waiting_for_devices_shows_only_while_running_without_halt_or_maintenance() -> None:
    """负责人 2026-10-27: 等待登记设备 replaces 正在采集 alone; a halt, maintenance and the other states keep theirs."""
    waiting = "采集模式 · 等待登记设备（请到“设置与导出”登记并保存）"
    assert status_text(1, "running", False, unregistered=True) == (waiting, "info")
    assert status_text(2, "running", False, unregistered=True) == (waiting.replace("采集模式", "维护模式"), "info")
    assert status_text(1, "running", True, unregistered=True)[0] == "采集模式 · 采集已停止（锁停），见提示"
    assert status_text(1, "running", False, True, unregistered=True)[1] == "maintenance"
    for state in ("released", "starting", "stopping"):
        assert status_text(1, state, False, unregistered=True) == status_text(1, state, False)
