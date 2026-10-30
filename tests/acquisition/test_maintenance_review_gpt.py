"""PR #55 cross-model review (review, 2026-10-18; D-219): B1, M1, M2, M3 of that review.

B1: a calibration draft and every write confirmation belong to one device identity (key, address, line settings,
database) within one takeover, one configuration and one page session; a configuration change voids them, and a write
re-checks the identity before anything is queued. M1: a coordinator or hub signal that was queued before the takeover
ended (or before a new one began) does nothing. M2: the maintenance view's database query and the diagnostics export
run on a worker thread; the Qt main thread (stop, maintenance results) is never blocked by them. M3: the settings
page keeps the last valid "通信参数当前值" when a later read fails, marked as the previous value (R-1-5).
"""

from __future__ import annotations

import sys
import threading
import traceback
from collections.abc import Iterator
from types import TracebackType
from typing import Any

import pytest

from par_app.database import ParDatabase
from par_app.device_hub import DeviceHub
from par_app.qt_compat import QCoreApplication
from tests.acquisition.conftest import Alpha, pump
from tests.acquisition.maintenance_support import (
    STATE,
    Running,
    controller,
    error_code,
    fake_port,
    open_page,
    save_registration,
    start,
    switch_between_transactions,
    wait_idle,
)
from tests.support.fake_bus import CALIBRATION_START, FakeDevice, wired

pytestmark = pytest.mark.qt
WRITE = "/api/v0/maintenance/calibration/write"
SETTINGS_READ = "/api/v0/acquisition/devices/p1/comm/read"
OTHER_ADDRESS = 9


@pytest.fixture
def running(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    """Tier 2, taken over, the page open on the calibration tab with a valid readback of North (address 1); a
    different probe answers at address 9."""
    devices = {1: FakeDevice(), 2: FakeDevice(), OTHER_ADDRESS: FakeDevice(serial_number=0x09090909)}
    port = fake_port(monkeypatch, devices)
    with wired(port):
        start(alpha)
        state = open_page(alpha, tab=1)
        assert state["calibration"]["write_enabled"], state["calibration"]
        case = Running(alpha, port, devices, [])
        case.spy()
        yield case


def _edit(alpha: Alpha) -> None:
    edited = alpha.patch("/api/v0/maintenance/calibration/draft", {"field": "y1", "value": -1.234})
    assert edited.status_code == 200, edited.text
    assert edited.json()["calibration"]["dirty"]


def _calibration_frames(running: Running, address: int) -> list[bytes]:
    """FC16 frames to `address` (the calibration write is the FC16 at holding 39; R-4-2 item 1)."""
    return [frame for _, frame in running.port.written() if frame[0] == address and frame[1] == 16]


# ------------------------------------------------------------------------------------------- B1
def test_b1_address_change_voids_the_draft_and_the_confirmation(running: Running) -> None:
    alpha = running.alpha
    _edit(alpha)
    issued = alpha.post(f"{WRITE}/confirmations", {})
    assert issued.status_code == 201, issued.text
    assert "地址 1" in issued.json()["text"]

    save_registration(alpha, {"North": OTHER_ADDRESS})  # same name, same database, the address is now 9
    pump(lambda: controller(alpha).device("North").slave_id == OTHER_ADDRESS)
    wait_idle(alpha)
    running.calls.clear()

    stale = alpha.post(WRITE, {"confirmation_id": issued.json()["confirmation_id"]})
    assert stale.status_code in (409, 428), stale.text
    assert error_code(stale) in ("confirmation_required", "precondition_failed"), stale.text
    state = alpha.get(STATE).json()
    assert not state["calibration"]["dirty"] and not state["calibration"]["write_enabled"]  # the draft is void
    again = alpha.post(f"{WRITE}/confirmations", {})
    assert again.status_code == 409 and error_code(again) == "precondition_failed", again.text
    wait_idle(alpha)
    assert "calibration_write" not in running.calls
    assert _calibration_frames(running, OTHER_ADDRESS) == []
    assert running.devices[OTHER_ADDRESS].calibration == FakeDevice().calibration


def test_b1_write_rechecks_the_identity_it_was_confirmed_for(running: Running) -> None:
    """Even with a confirmation that is still on file, a write whose device identity changed is refused."""
    alpha = running.alpha
    c = controller(alpha)
    _edit(alpha)
    issued = alpha.post(f"{WRITE}/confirmations", {})
    assert issued.status_code == 201, issued.text
    hub = alpha.host.hub
    assert hub is not None
    device = hub.device_at("North")
    original = device.slave_id
    device.slave_id = OTHER_ADDRESS  # the registration changed under the controller without a signal
    try:
        refused = alpha.post(WRITE, {"confirmation_id": issued.json()["confirmation_id"]})
        assert refused.status_code in (409, 428), refused.text
    finally:
        device.slave_id = original
    assert running.calls == []
    assert c.window.calibration_task is None


def test_b1_bus_change_and_a_new_page_session_void_confirmations(running: Running) -> None:
    alpha = running.alpha
    _edit(alpha)
    issued = alpha.post(f"{WRITE}/confirmations", {})
    assert issued.status_code == 201, issued.text
    save_registration(alpha, bus={"poll_cycle_seconds": 45.0})
    wait_idle(alpha)
    running.calls.clear()
    refused = alpha.post(WRITE, {"confirmation_id": issued.json()["confirmation_id"]})
    assert refused.status_code in (409, 428), refused.text
    assert running.calls == []
    assert all(int.from_bytes(frame[2:4], "big") != CALIBRATION_START for frame in _calibration_frames(running, 1))


def test_b1_unchanged_identity_still_writes(running: Running) -> None:
    """Control: without a change the confirmed write goes out to address 1."""
    alpha = running.alpha
    _edit(alpha)
    written = alpha.confirmed(WRITE)
    assert written.status_code == 200, written.text
    wait_idle(alpha)
    assert running.calls == ["calibration_write"]
    assert any(int.from_bytes(f[2:4], "big") == CALIBRATION_START for f in _calibration_frames(running, 1))


# ------------------------------------------------------------------------------------------- M1
class _Uncaught:
    def __init__(self) -> None:
        self.errors: list[BaseException] = []
        self.functions: list[set[str]] = []
        """Per error, the names of the functions its traceback passed through."""

    def __call__(self, kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
        self.errors.append(error)
        self.functions.append({frame.name for frame in traceback.extract_tb(trace)})

    def raised_in(self, function: str) -> list[BaseException]:
        return [error for error, names in zip(self.errors, self.functions, strict=True) if function in names]


def test_m1_a_signal_queued_before_detach_does_nothing(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    uncaught = _Uncaught()
    monkeypatch.setattr(sys, "excepthook", uncaught)
    with wired(fake_port(monkeypatch)):
        start(alpha)
        c = controller(alpha)
        hub = alpha.host.hub
        assert hub is not None
        hub.devices_changed.emit()  # queued to the controller's slot
        hub.coordinator.device_state_changed.emit("North", {"online": True})
        c.detach()
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        assert uncaught.errors == []
        assert c.hub is None and c.device_status == {}
        c.attach(hub)  # the host still runs: give the controller back for the fixture's shutdown


def test_m1_a_signal_of_the_previous_takeover_does_not_reach_the_next(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    uncaught = _Uncaught()
    monkeypatch.setattr(sys, "excepthook", uncaught)
    with wired(fake_port(monkeypatch)):
        start(alpha)
        c = controller(alpha)
        old = alpha.host.hub
        assert old is not None
        newer = DeviceHub(alpha.host.store, initial_config=alpha.host.store.load_for_startup())
        try:
            old.devices_changed.emit()
            old.coordinator.device_state_changed.emit("North", {"online": False, "marker": "old"})
            c.detach()
            c.attach(newer)
            QCoreApplication.processEvents()
            QCoreApplication.processEvents()
            assert uncaught.errors == []
            assert c.snapshot("North").get("marker") is None
        finally:
            c.detach()
            c.attach(old)


def test_m1_real_slot_errors_are_not_swallowed(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard for stale signals, not a blanket except: an error in a current signal still reaches the hook.

    The coordinator keeps polling on its own thread, so other current signals (device_state_changed,
    bus_state_changed, ...) may be queued before the test's devices_changed; one is queued first on purpose. The error
    is raised where every current devices_changed passes (_bus_refresh), not behind state another slot can change:
    the earlier version raised from fresh_comm for an unknown target, and any slot that ran first reset the target
    (_changed -> _refresh), so the devices_changed slot raised nothing and the wait timed out."""
    uncaught = _Uncaught()
    monkeypatch.setattr(sys, "excepthook", uncaught)
    with wired(fake_port(monkeypatch)):
        start(alpha)
        c = controller(alpha)
        hub = alpha.host.hub
        assert hub is not None

        def broken() -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(c, "_bus_refresh", broken)
        hub.coordinator.device_state_changed.emit("North", c.snapshot("North"))  # a poll result queued first
        hub.devices_changed.emit()
        pump(lambda: bool(uncaught.raised_in("_on_devices_changed")))
        error = uncaught.raised_in("_on_devices_changed")[0]
        assert isinstance(error, RuntimeError) and str(error) == "boom"


# ------------------------------------------------------------------------------------------- M3 (settings)
def test_m3_a_failed_read_keeps_the_last_valid_values(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    devices = {1: FakeDevice(), 2: FakeDevice()}
    port = fake_port(monkeypatch, devices)
    with wired(port):
        start(alpha)
        c = controller(alpha)
        assert alpha.post(SETTINGS_READ).status_code == 200
        pump(lambda: not c.settings["North"].pending)
        first = alpha.get(STATE).json()["settings"]["North"]
        assert [v["text"] for v in first["values"]] == ["1", "19200", "无校验"]
        assert not first["stale"]

        switch_between_transactions(port, devices, 1, "silent", other=2)  # mid-transaction halts (D-101)
        assert alpha.post(SETTINGS_READ).status_code == 200
        pump(lambda: not c.settings["North"].pending)
        failed = alpha.get(STATE).json()["settings"]["North"]
        assert failed["error"] and "读取失败" in failed["source"]
        assert [v["text"] for v in failed["values"]] == ["1", "19200", "无校验"]  # kept (R-1-5)
        assert failed["stale"] and failed["stale_text"]

        switch_between_transactions(port, devices, 1, "ok", other=2)
        pump(lambda: c.snapshot("North").get("online", False) or True)
        assert alpha.post(SETTINGS_READ).status_code == 200
        pump(lambda: not c.settings["North"].pending)
        pump(lambda: not alpha.get(STATE).json()["settings"]["North"]["error"])
        again = alpha.get(STATE).json()["settings"]["North"]
        assert not again["stale"] and [v["text"] for v in again["values"]] == ["1", "19200", "无校验"]


# ------------------------------------------------------------------------------------------- M2 (worker thread)
class _SlowDatabase:
    """ParDatabase.recent_diagnostics held until released; records the threads it ran on."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.release = threading.Event()
        self.entered = threading.Event()
        self.threads: list[threading.Thread] = []
        original = ParDatabase.recent_diagnostics

        def slow(database: ParDatabase, limit: int = 300) -> list[dict[str, Any]]:
            self.threads.append(threading.current_thread())
            self.entered.set()
            self.release.wait(30)
            return original(database, limit)

        monkeypatch.setattr(ParDatabase, "recent_diagnostics", slow)


def test_m2_the_view_query_runs_off_the_main_thread_and_stop_is_not_delayed(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    with wired(fake_port(monkeypatch)):
        start(alpha)
        slow = _SlowDatabase(monkeypatch)
        response = alpha.post("/api/v0/maintenance/page", {"tab": 0})
        assert response.status_code == 200, response.text
        assert slow.entered.wait(10)
        state = alpha.get(STATE)  # answered while the query is held
        assert state.status_code == 200, state.text
        stopped = alpha.post("/api/v0/acquisition/stop")
        assert stopped.status_code == 202, stopped.text
        pump(lambda: alpha.takeover() == "released", timeout=10)
        slow.release.set()
        main = threading.main_thread()
        assert slow.threads and all(thread is not main for thread in slow.threads)


def test_m2_export_writes_on_a_worker_and_reports_back(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    with wired(fake_port(monkeypatch)):
        start(alpha)
        open_page(alpha, tab=0)
        pump(lambda: controller(alpha).events_loaded())
        slow = _SlowDatabase(monkeypatch)
        exported = alpha.post("/api/v0/maintenance/diagnostics/export")
        assert exported.status_code == 200, exported.text
        assert slow.entered.wait(10)
        state = alpha.get(STATE).json()
        assert not state["diagnostics"]["export_enabled"]  # one export at a time
        assert state["footer"]["exported_file"] is None
        slow.release.set()
        pump(lambda: controller(alpha).window.exported_file is not None)
        state = alpha.get(STATE).json()
        assert state["footer"]["exported_file"] and not state["footer"]["result_error"]
        main = threading.main_thread()
        assert all(thread is not main for thread in slow.threads)
