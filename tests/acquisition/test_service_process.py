"""The service process with the takeover running: shutdown leaves nothing behind (16_ 1.5, 7.6).

The real par_app.service_main runs as a subprocess on the loopback interface with the byte-level fake bus
(tests/support/fake_bus_service.py) and the real clock. After acquiring for real (records saved, event stream
delivering them), it is stopped by the shell's way (end of stdin) or by SIGTERM: exit code 0, service.json removed,
the port closed, no non-daemon thread left, V1.0.3's lock free again. A killed service (crash) leaves the lock to
V1.0.3 too.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from par_app.acquisition_host.instance_lock import InstanceLock
from par_app.application.tier import SETTINGS_FILE_NAME, TIER_KEY
from par_app.service_main import SERVICE_STOPPED
from tests.acquisition.conftest import two_devices, write_config
from tests.acquisition.test_instance_lock import PROBE, PROBE_SECONDS

pytestmark = pytest.mark.qt
ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "tests" / "support" / "fake_bus_service.py"
START_SECONDS = 30.0
RECORD_SECONDS = 30.0
STOP_SECONDS = 60.0
"""At least one acquisition transaction budget (40 s) plus margin, as the shell must wait (16_ 1.5)."""


class Service:
    def __init__(self, process: subprocess.Popen[bytes], info: dict[str, Any], data_dir: Path) -> None:
        self.process = process
        self.info = info
        self.data_dir = data_dir
        self.client = httpx.Client(
            base_url=info["base_url"], headers={"Authorization": f"Bearer {info['token']}"}, timeout=10.0
        )

    def enable_tier_1(self) -> None:
        issued = self.client.post("/api/v0/tier/confirmations", json={"tier": 1}).json()
        assert self.client.put(
            "/api/v0/tier", json={"tier": 1, "confirmation_id": issued["confirmation_id"]}
        ).is_success

    def wait_for(self, check: Callable[[], bool], seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not check():
            assert self.process.poll() is None, "service exited"
            assert time.monotonic() < deadline, "not reached in time"
            time.sleep(0.1)


def _launch(data_dir: Path, product_tier: bool = False) -> Service:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    if product_tier:
        environment["PAR_TEST_PRODUCT_TIER"] = "1"  # the product's first-run tier (issue #119), not the tests' 0
    process = subprocess.Popen(
        [sys.executable, str(SERVICE), "--port", "0", "--data-dir", str(data_dir), "--stop-on-stdin-eof"],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    service_file = data_dir / "service.json"
    deadline = time.monotonic() + START_SECONDS
    info: dict[str, Any] | None = None
    while info is None and process.poll() is None and time.monotonic() < deadline:
        try:
            info = json.loads(service_file.read_text(encoding="utf-8"))
            httpx.get(f"{info['base_url']}/api/v0/health", timeout=1.0).raise_for_status()
        except (OSError, ValueError, httpx.HTTPError):
            info = None
            time.sleep(0.05)
    if info is None:
        process.kill()
        pytest.fail(f"service did not start: {process.communicate()[1].decode(errors='replace')}")
    return Service(process, info, data_dir)


def _serve(data_dir: Path, product_tier: bool = False) -> Iterator[Service]:
    probe = InstanceLock()
    if not probe.acquire():
        pytest.skip("V1.0.3's lock is held on this machine (a V1.0.3 is running)")
    probe.release()
    running = _launch(data_dir, product_tier)
    try:
        yield running
    finally:
        running.client.close()
        if running.process.poll() is None:
            running.process.kill()
            running.process.communicate()


@pytest.fixture
def service(qt_app: object, tmp_path: Path) -> Iterator[Service]:
    data_dir = (tmp_path / "alpha data").resolve()
    write_config(data_dir, two_devices())
    yield from _serve(data_dir)


@pytest.fixture
def new_installation(qt_app: object, tmp_path: Path) -> Iterator[Service]:
    """A data directory without a settings file (a new installation), started as the product starts it."""
    data_dir = (tmp_path / "alpha data").resolve()
    write_config(data_dir, two_devices())
    assert not (data_dir / "config" / SETTINGS_FILE_NAME).exists()
    yield from _serve(data_dir, product_tier=True)


@pytest.fixture
def tier_1_service(qt_app: object, tmp_path: Path) -> Iterator[Service]:
    """Tier 1 was switched on in an earlier run (its settings file is there) before this service starts."""
    data_dir = (tmp_path / "alpha data").resolve()
    write_config(data_dir, two_devices())
    (data_dir / "config" / SETTINGS_FILE_NAME).write_text(json.dumps({TIER_KEY: 1}), encoding="utf-8")
    yield from _serve(data_dir)


def _acquire(service: Service) -> list[str]:
    """Start the takeover and wait for a saved record; return the SSE event names seen meanwhile."""
    seen: list[str] = []
    done = threading.Event()

    def read_events() -> None:
        with service.client.stream("GET", "/api/v0/events", timeout=None) as stream:
            for line in stream.iter_lines():
                if line.startswith("event: "):
                    seen.append(line.removeprefix("event: "))
                if "acquisition_saved" in seen:
                    done.set()
                    return

    reader = threading.Thread(target=read_events, daemon=True)
    reader.start()
    service.enable_tier_1()
    started = service.client.post("/api/v0/acquisition/start")
    assert started.status_code == 202 and started.json()["lock_held"], started.text

    def recorded() -> bool:
        devices = service.client.get("/api/v0/acquisition/status").json()["devices"]
        return bool(devices and devices[0]["latest_record_id"])

    service.wait_for(recorded, RECORD_SECONDS)
    assert done.wait(RECORD_SECONDS)
    assert not InstanceLock().acquire()  # the service holds V1.0.3's lock while acquiring
    return seen


SIGTERM_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="graceful stop by SIGTERM is POSIX-only: on Windows send_signal(SIGTERM) is TerminateProcess (exit 1); "
    "the shell stops the service by the request, stdin or CTRL_BREAK there (#66)",
)


@pytest.mark.parametrize("how", ["stdin", pytest.param("sigterm", marks=SIGTERM_POSIX_ONLY), "request"])
def test_stopping_the_service_stops_acquisition_and_leaves_nothing(service: Service, how: str) -> None:
    seen = _acquire(service)
    assert seen[:3] == ["tier_changed", "takeover_state", "takeover_state"] and "bus_state" in seen
    if how == "sigterm":
        service.process.send_signal(signal.SIGTERM)
        service.process.wait(STOP_SECONDS)  # stdin still open: only the signal stops it
    if how == "request":  # the packaged shell's stop path (API-19; the windowed exe has no stdin on Windows)
        assert service.client.post("/api/v0/shutdown").status_code == 202
        service.process.wait(STOP_SECONDS)  # stdin still open: only the request stops it
    output, errors = service.process.communicate(timeout=STOP_SECONDS)  # closes stdin: the shell's stop
    assert service.process.returncode == 0, errors.decode(errors="replace")
    lines = output.decode().splitlines()
    port_line = next(line for line in lines if line.startswith("PORT "))
    assert "opened=1 closed=1" in port_line
    assert lines[-1] == "THREADS MainThread"
    assert not (service.data_dir / "service.json").exists()
    lock = InstanceLock()
    assert lock.acquire()
    lock.release()
    assert "Traceback" not in errors.decode(errors="replace")
    log = (service.data_dir / "logs" / "service.log").read_text(encoding="utf-8").splitlines()
    assert log[-1].endswith(f"{SERVICE_STOPPED} non-daemon threads left: none")  # what the packaged self-test reads


def test_a_killed_service_leaves_the_lock_to_v103(service: Service) -> None:
    _acquire(service)
    service.process.kill()
    service.process.communicate(timeout=STOP_SECONDS)
    probe = subprocess.run(
        [sys.executable, str(PROBE), "probe"],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=PROBE_SECONDS,
    )
    assert probe.stdout.splitlines() == ["STARTED", "EXIT 1"], probe.stderr


def test_with_tier_1_on_the_service_starts_acquiring_by_itself(tier_1_service: Service) -> None:
    """Issue #92: no "开始采集" request; the service takes the lock and records as V1.0.3 does when opened."""
    service = tier_1_service

    def recorded() -> bool:
        status = service.client.get("/api/v0/acquisition/status").json()
        return status["takeover"] == "running" and bool(status["devices"] and status["devices"][0]["latest_record_id"])

    service.wait_for(recorded, START_SECONDS + RECORD_SECONDS)
    assert not InstanceLock().acquire()  # the service holds V1.0.3's lock
    output, errors = service.process.communicate(timeout=STOP_SECONDS)  # the shell's stop
    assert service.process.returncode == 0, errors.decode(errors="replace")
    log = (service.data_dir / "logs" / "service.log").read_text(encoding="utf-8")
    assert "acquisition started automatically (tier 1)" in log


def test_a_new_installation_acquires_without_any_confirmation(new_installation: Service) -> None:
    """Issue #119 (owner 2026-10-27): no settings file -> tier 1, no confirmation, the service acquires by itself."""
    service = new_installation

    def recorded() -> bool:
        status = service.client.get("/api/v0/acquisition/status").json()
        return status["takeover"] == "running" and bool(status["devices"] and status["devices"][0]["latest_record_id"])

    service.wait_for(recorded, START_SECONDS + RECORD_SECONDS)
    tier = service.client.get("/api/v0/tier").json()
    assert (tier["tier"], tier["text"]) == (1, "采集模式 · 正在采集")
    assert not (service.data_dir / "config" / SETTINGS_FILE_NAME).exists()  # nothing was confirmed or written
    output, errors = service.process.communicate(timeout=STOP_SECONDS)
    assert service.process.returncode == 0, errors.decode(errors="replace")
