"""Races around the tier and the takeover (PR #54 review M1-M3; 16_ 1.5, 4; owner 2026-10-18: tier 0 by default).

* M1: the tier check and the move to "starting" are one step under the tier lock, and the main thread checks the tier
  again before it takes the lock; a tier written to 0 at any point before that leaves no takeover. The `then` of a
  stop (writing tier 0) runs while the takeover still reads "stopping", so no start can slip in between.
* M2: a running takeover can always be seen and stopped, even when the tier reads 0 (settings file changed or
  unreadable); PUT /tier {0} then stops it instead of answering 200 at once.
* M3: a shutdown that arrives while "开始采集" is being handled on the main thread (a signal handler runs between
  bytecodes) leaves no coordinator running and the lock free; the signal handler itself only queues the shutdown.
"""

from __future__ import annotations

import signal
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from par_app import service_main
from par_app.application.errors import ApplicationError
from par_app.application.tier import SETTINGS_FILE_NAME, Takeover
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt
WAIT_SECONDS = 30.0


def _port(monkeypatch: pytest.MonkeyPatch) -> FakeSerial:
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    return FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})


def _stop(alpha: Alpha, port: FakeSerial) -> None:
    coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
    port.release = lambda: not coordinator._running
    assert alpha.post("/api/v0/acquisition/stop").status_code == 202
    pump(lambda: alpha.takeover() == "released")


def _no_takeover(alpha: Alpha, port: FakeSerial) -> None:
    assert alpha.takeover() == "released" and alpha.host.hub is None
    assert not alpha.host.lock.held and port.opened == 0


def test_tier_0_written_before_the_main_thread_starts_leaves_no_takeover(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    alpha.enable_tier_1()
    outcome: dict[str, Any] = {}
    with wired(port):
        worker = threading.Thread(target=lambda: outcome.update(r=alpha.client.post("/api/v0/acquisition/start")))
        worker.start()
        deadline = time.monotonic() + WAIT_SECONDS
        while alpha.takeover() != "starting":  # the request reserved the takeover; the main thread has not run yet
            assert time.monotonic() < deadline
            time.sleep(0.001)
        alpha.context.acquisition.tiers.write(0)  # e.g. the `then` of a stop that lowered the tier
        pump(lambda: not worker.is_alive())
    response = outcome["r"]
    assert response.status_code == 403 and response.json()["error"]["code"] == "feature_disabled"
    _no_takeover(alpha, port)


def test_put_tier_0_racing_a_start_never_leaves_tier_0_acquiring(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    port.hold_at = 60
    alpha.enable_tier_1()
    acquisition = alpha.context.acquisition
    original = acquisition.cache.begin
    lowered: dict[str, Any] = {}

    def lower() -> None:
        try:
            lowered["result"] = acquisition.set_tier(0, None)
        except ApplicationError as error:
            lowered["error"] = error.code

    def racing_begin(expected: Takeover, new: Takeover) -> bool:
        if new == "starting":  # a PUT /tier {0} arrives between the tier check and the move to "starting"
            racer = threading.Thread(target=lower)
            racer.start()
            racer.join(1.0)
        return original(expected, new)

    monkeypatch.setattr(acquisition.cache, "begin", racing_begin)
    with wired(port):
        started = alpha.post("/api/v0/acquisition/start")
        pump(lambda: bool(lowered))
        tier = acquisition.tier()
        if alpha.takeover() == "running":
            assert started.status_code == 202 and tier == 1 and lowered == {"error": "busy"}
            pump(port.held.is_set)
            _stop(alpha, port)
        else:
            assert tier == 0 and started.status_code == 403, (tier, started.text, lowered, alpha.takeover())
            _no_takeover(alpha, port)


def test_the_stop_that_lowers_the_tier_writes_it_before_the_takeover_reads_released(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    port.hold_at = 60
    alpha.enable_tier_1()
    acquisition = alpha.context.acquisition
    original = acquisition.tiers.write
    seen: list[tuple[str, bool]] = []

    def recording_write(tier: int) -> None:
        seen.append((alpha.takeover(), alpha.host.lock.held))
        original(tier)

    monkeypatch.setattr(acquisition.tiers, "write", recording_write)
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(port.held.is_set)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        assert alpha.put("/api/v0/tier", {"tier": 0}).status_code == 202
        pump(lambda: alpha.takeover() == "released")
    assert seen == [("stopping", False)]  # lock already released, no start possible before tier 0 is on disk
    assert acquisition.tier() == 0


@pytest.mark.parametrize("settings", ['{"device_write_tier": 0}', '{"device_write_tier": 1'])
@pytest.mark.parametrize("how", ["stop", "tier_0"])
def test_a_running_takeover_stays_visible_and_stoppable_when_the_tier_reads_0(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch, settings: str, how: str
) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    port.hold_at = 60
    alpha.enable_tier_1()
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(port.held.is_set)
        (alpha.data_dir / "config" / SETTINGS_FILE_NAME).write_text(settings, encoding="utf-8")
        assert alpha.context.acquisition.tier() == 0
        status = alpha.get("/api/v0/acquisition/status")
        assert status.status_code == 200 and status.json()["takeover"] == "running"
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        if how == "stop":
            response = alpha.post("/api/v0/acquisition/stop")
        else:
            response = alpha.put("/api/v0/tier", {"tier": 0})
        assert response.status_code == 202, response.text
        pump(lambda: alpha.takeover() == "released")
    assert coordinator.isFinished() and not alpha.host.lock.held
    assert alpha.context.acquisition.tier() == 0
    refused = alpha.get("/api/v0/acquisition/status")  # nothing running any more: tier 0 refuses again
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "feature_disabled"
    assert alpha.post("/api/v0/acquisition/stop").status_code == 403


def test_shutdown_during_start_leaves_no_coordinator_and_no_lock(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    port = _port(monkeypatch)
    alpha.enable_tier_1()
    host = alpha.host
    original = host._build_and_start

    def interrupted() -> None:
        host.shutdown()  # a signal handler running between bytecodes after the lock was taken
        original()

    monkeypatch.setattr(host, "_build_and_start", interrupted)
    with wired(port):
        refused = alpha.post("/api/v0/acquisition/start")
        pump(lambda: True)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "busy"
    _no_takeover(alpha, port)
    assert alpha.post("/api/v0/acquisition/start").status_code == 409  # a host that shut down never starts again
    assert port.opened == 0


def test_the_signal_handler_only_queues_the_shutdown(qt_app: object) -> None:
    names = [name for name in ("SIGTERM", "SIGINT", "SIGBREAK") if hasattr(signal, name)]
    saved = {name: signal.getsignal(getattr(signal, name)) for name in names}
    calls: list[str] = []
    runner = SimpleNamespace(request_shutdown=lambda: calls.append("shutdown"))
    try:
        service_main._install_signals(runner)  # type: ignore[arg-type]
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        handler(signal.SIGTERM, None)
        assert calls == []  # not inside whatever the main thread was doing
        pump(lambda: calls == ["shutdown"], WAIT_SECONDS)
    finally:
        for name, previous in saved.items():
            signal.signal(getattr(signal, name), previous)
