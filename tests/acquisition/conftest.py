"""Fixtures of the takeover tests: the alpha service assembled in-process the way par_app.service_main assembles it.

The Qt main thread is the test's own thread: the test pumps Qt events while an HTTP request runs on a helper
thread (`call`), which is what the service's QCoreApplication loop does while uvicorn serves. Every directory is a
tmp_path folder (R-4-7); every serial port is the byte-level fake of tests/support/fake_bus.py; the coordinator's
clock is a FakeClock injected by replacing par_app.device_hub.PollingCoordinator with the same class bound to that
clock, on the V1.0.3 path and the alpha path alike (16_ 7.1). The alpha's single-instance lock uses a key of its own per
test (`isolated_lock_key`): V1.0.3's key is one QSharedMemory segment for the whole machine, so with it two test runs at
the same time (another worktree, another agent) refused each other's takeover with instance_locked. The tests of the
lock itself (test_instance_lock.py) put V1.0.3's key back.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest
from fastapi.testclient import TestClient

from par_app.acquisition_host.faults import TakeoverFaults
from par_app.acquisition_host.gateway import MainThreadGateway
from par_app.acquisition_host.host import AcquisitionHost, HostBackend, MaintenanceBackend
from par_app.acquisition_host.instance_lock import INSTANCE_LOCK_KEY, InstanceLock
from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.app_config import AppConfigStore
from par_app.application.paths import AlphaPaths
from par_app.coordinator import PollingCoordinator
from par_app.database import ParDatabase
from par_app.domain.clock import FakeClock
from par_app.models import AppConfig, BusConfig, DeviceConfig
from par_app.qt_compat import QCoreApplication
from tests.virtual_clock import virtual_clock

T = TypeVar("T")
TOKEN = "takeover-test-token"
HOST = "testserver"
AUTH = {"X-PAR-Token": TOKEN}
WAIT_SECONDS = 60.0
"""Real-time limit for one wait in these tests (a hang fails the test instead of blocking the suite)."""


def isolated_lock_key() -> str:
    """A single-instance lock key no other process uses (test-only; the product key is not changed)."""
    return f"{INSTANCE_LOCK_KEY}.test.{os.getpid()}.{uuid.uuid4().hex}"


def pump(condition: Callable[[], bool], timeout: float = WAIT_SECONDS) -> None:
    """Run the Qt main loop until `condition()` holds."""
    deadline = time.monotonic() + timeout
    while not condition():
        QCoreApplication.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        time.sleep(0.002)
    QCoreApplication.processEvents()


def call(function: Callable[[], T], timeout: float = WAIT_SECONDS) -> T:
    """Run `function` (an HTTP request) on a helper thread while the main thread serves Qt events."""
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["value"] = function()
        except BaseException as error:  # handed back to the test thread
            outcome["error"] = error

    worker = threading.Thread(target=run, name="test-http")
    worker.start()
    pump(lambda: not worker.is_alive(), timeout)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]  # type: ignore[no-any-return]


def bind_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """DeviceHub builds PollingCoordinator(config, parent) without a clock; give every one built from now on
    `clock` (same class, same code)."""

    class ClockedCoordinator(PollingCoordinator):
        def __init__(self, app_config: AppConfig, parent: object = None) -> None:
            super().__init__(app_config, parent, clock=clock)

    monkeypatch.setattr("par_app.device_hub.PollingCoordinator", ClockedCoordinator)


def two_devices() -> AppConfig:
    return AppConfig(
        bus=BusConfig(serial_port="COM7", poll_cycle_seconds=40.0),
        devices=[DeviceConfig(name="North", slave_id=1), DeviceConfig(name="South", slave_id=2)],
        configured=True,
    )


def write_config(root: Path, config: AppConfig) -> AppConfig:
    """Save `config` as <root>/config/app_config.json with a new database per device under <root>/data/devices,
    as V1.0.3 leaves them after the settings page saved it."""
    stored = AppConfig.from_dict(config.to_dict())
    for index, device in enumerate(stored.devices):
        path = (root / device.resolved_database_path(index)).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        ParDatabase(path)
        device.database_path = str(path)
    AppConfigStore(root).save(stored)
    return stored


@dataclass
class Alpha:
    context: ServiceContext
    host: AcquisitionHost
    client: TestClient
    clock: FakeClock
    data_dir: Path
    faults: TakeoverFaults
    """What service_main installs as sys.excepthook (D-225 item 1); also the gateway's `unexpected`."""

    def get(self, path: str) -> httpx.Response:
        return call(lambda: self.client.get(path))

    def post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return call(lambda: self.client.post(path, json=body))

    def put(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return call(lambda: self.client.put(path, json=body))

    def patch(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return call(lambda: self.client.patch(path, json=body))

    def delete(self, path: str) -> httpx.Response:
        return call(lambda: self.client.delete(path))

    def enable_tier_1(self) -> None:
        issued = self.post("/api/v0/tier/confirmations", {"tier": 1})
        assert issued.status_code == 201, issued.text
        changed = self.put("/api/v0/tier", {"tier": 1, "confirmation_id": issued.json()["confirmation_id"]})
        assert changed.status_code == 200, changed.text

    def enable_tier_2(self) -> None:
        """0 -> 1 -> 2, each with its own confirmation (17_ 6.1)."""
        self.enable_tier_1()
        issued = self.post("/api/v0/tier/confirmations", {"tier": 2})
        assert issued.status_code == 201, issued.text
        changed = self.put("/api/v0/tier", {"tier": 2, "confirmation_id": issued.json()["confirmation_id"]})
        assert changed.status_code == 200, changed.text

    def confirmed(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        """A maintenance write: ask for its confirmation, then send it with the id (17_ 6.2)."""
        issued = self.post(f"{path}/confirmations", body or {})
        assert issued.status_code == 201, issued.text
        return self.post(path, {**(body or {}), "confirmation_id": issued.json()["confirmation_id"]})

    def takeover(self) -> str:
        return str(self.context.acquisition.cache.takeover)


@pytest.fixture
def alpha(qt_app: object, tmp_path: Path) -> Iterator[Alpha]:
    data_dir = (tmp_path / "alpha data").resolve()
    paths = AlphaPaths(data_dir)
    paths.ensure()
    clock = virtual_clock()
    context = ServiceContext(paths, clock)
    acquisition = context.acquisition
    host = AcquisitionHost(
        data_dir,
        acquisition.cache,
        context.events.publish,
        acquisition.publish_state,
        clock=clock,
        lock=InstanceLock(isolated_lock_key()),
    )
    gateway = MainThreadGateway()
    acquisition.attach(HostBackend(host, gateway), MaintenanceBackend(host, gateway))
    faults = TakeoverFaults(host, acquisition, gateway)
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}", headers=AUTH) as client:
        try:
            yield Alpha(context, host, client, clock, data_dir, faults)
        finally:
            host.shutdown()
            context.events.close()
