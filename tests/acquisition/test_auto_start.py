"""The automatic start (issue #92, overturns D-212 question 2; owner 2026-10-27, option A).

Tier 1 (or 2) on: AcquisitionService.auto_start, which service_main queues on the Qt main thread when the service
starts, takes the lock and starts the coordinator exactly as "开始采集" does. Tier 0 opens nothing. A held lock (V1.0.3
running) refuses it: no port is opened, the takeover stays released and the status keeps the refusal for the page.
The service process test (tests/acquisition/test_service_process.py) covers the call from service_main.
"""

from __future__ import annotations

import pytest

from par_app.acquisition_host.host import LOCKED_MESSAGE
from par_app.acquisition_host.instance_lock import InstanceLock
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt


def _port(monkeypatch: pytest.MonkeyPatch) -> FakeSerial:
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 50
    return port


def _stop(alpha: Alpha, port: FakeSerial) -> None:
    coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
    port.release = lambda: not coordinator._running
    assert alpha.post("/api/v0/acquisition/stop").status_code == 202
    pump(lambda: alpha.takeover() == "released")


def test_tier_0_does_not_start(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    with wired(port):
        assert alpha.context.acquisition.auto_start() is False
    assert port.opened == 0 and alpha.host.hub is None and alpha.takeover() == "released"
    assert not alpha.host.lock.held


@pytest.mark.parametrize("tier", [1, 2])
def test_tier_1_or_2_starts_acquiring_without_a_click(alpha: Alpha, monkeypatch: pytest.MonkeyPatch, tier: int) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    alpha.enable_tier_1() if tier == 1 else alpha.enable_tier_2()
    with wired(port):
        assert alpha.context.acquisition.auto_start() is True
        assert alpha.takeover() == "running" and alpha.host.lock.held
        pump(port.held.is_set)  # the coordinator talks to the bus as after "开始采集"
        status = alpha.get("/api/v0/acquisition/status").json()
        assert status["takeover"] == "running" and status["error"] is None
        assert alpha.get("/api/v0/tier").json()["text"] == ("采集模式" if tier == 1 else "维护模式") + " · 正在采集"
        _stop(alpha, port)
    assert not alpha.host.lock.held


def test_lock_held_by_v103_refuses_and_tells_the_page(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    alpha.enable_tier_1()
    holder = InstanceLock(alpha.host.lock.key)  # stands in for a running V1.0.3 (the same key, held elsewhere)
    assert holder.acquire()
    try:
        with wired(port):
            assert alpha.context.acquisition.auto_start() is False
        assert port.opened == 0 and alpha.host.hub is None and alpha.takeover() == "released"
        status = alpha.get("/api/v0/acquisition/status").json()
        assert status["error"] == LOCKED_MESSAGE and not status["lock_held"]
    finally:
        holder.release()
    with wired(port):  # V1.0.3 gone: the user's "开始采集" works and clears the reason
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        assert alpha.get("/api/v0/acquisition/status").json()["error"] is None
        _stop(alpha, port)
