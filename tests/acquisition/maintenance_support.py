"""Helpers of the tier-2 maintenance tests (17_ section 10): the alpha on the byte-level fake bus, taken over, with a
maintenance page open, and waits that pump the Qt main thread until the controller has settled."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from par_app.acquisition_host.maintenance_host import MaintenanceController
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

STATE = "/api/v0/maintenance/state"


def form(
    old: int = 1,
    new: int | None = None,
    baudrate: int = 19200,
    new_baudrate: int | None = None,
    parity: str = "N",
    port: str = "COM7",
    isolated: bool = True,
) -> dict[str, Any]:
    """The communication tab's fields as the page sends them."""
    return {
        "serial_port": port,
        "old": {"slave_id": old, "baudrate": baudrate, "parity": parity},
        "new": {"slave_id": old if new is None else new, "baudrate": new_baudrate or baudrate, "parity": parity},
        "isolated": isolated,
    }


def fake_port(monkeypatch: pytest.MonkeyPatch, devices: dict[int, FakeDevice] | None = None) -> FakeSerial:
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    return FakeSerial(clock, devices if devices is not None else {1: FakeDevice(), 2: FakeDevice()})


def switch_between_transactions(
    port: FakeSerial, devices: dict[int, FakeDevice], address: int, mode: str, *, other: int
) -> None:
    """Set the `mode` of the device at `address` while the coordinator sends a frame to `other`, i.e. between two of
    `address`'s transactions. The coordinator polls on its own thread all the time; a device that goes silent, or
    answers again, in the middle of its freeze -> read -> resume transaction leaves the resume unconfirmed after
    valid frames and halts every device (AcquisitionResumeError, D-101) - product behaviour, not what a test of a
    silent or recovered device means."""
    done = threading.Event()

    def at_other(frame: bytes) -> bool:
        if frame[0] == other and not done.is_set():
            devices[address].mode = mode
            done.set()
        return False  # never held

    port.hold_when = at_other  # left in place: clearing it races with FakeSerial.write on the coordinator thread
    pump(done.is_set)


def controller(alpha: Alpha) -> MaintenanceController:
    return alpha.host.maintenance


def settled(alpha: Alpha) -> Callable[[], bool]:
    """No maintenance task in flight and no enter pending."""
    return lambda: controller(alpha).hub is not None and controller(alpha).idle()


def start(alpha: Alpha, online: bool = True) -> None:
    """Tier 2, then 开始采集; waits until every enabled device has answered once (calibration needs it online)."""
    write_config(alpha.data_dir, two_devices())
    alpha.enable_tier_2()
    response = alpha.post("/api/v0/acquisition/start")
    assert response.status_code == 202, response.text
    if online:
        pump(lambda: all(s.get("online") for s in controller(alpha).device_status.values()))


def wait_idle(alpha: Alpha) -> dict[str, Any]:
    pump(settled(alpha))
    state = alpha.get(STATE)
    assert state.status_code == 200, state.text
    return dict(state.json())


def open_page(alpha: Alpha, tab: int = 0) -> dict[str, Any]:
    response = alpha.post("/api/v0/maintenance/page", {"tab": tab})
    assert response.status_code == 200, response.text
    return wait_idle(alpha)


def enter(alpha: Alpha) -> dict[str, Any]:
    response = alpha.confirmed("/api/v0/maintenance/enter")
    assert response.status_code == 200, response.text
    pump(lambda: controller(alpha).maintenance() and not controller(alpha).window.entering)
    return wait_idle(alpha)


def error_code(response: Any) -> str:  # noqa: ANN401 (httpx.Response)
    return str(response.json()["error"]["code"])


def save_registration(
    alpha: Alpha,
    slave_ids: dict[str, int] | None = None,
    enabled: dict[str, bool] | None = None,
    bus: dict[str, Any] | None = None,
    removed: tuple[str, ...] = (),
) -> None:
    """Change the alpha's registration through tier 1's configuration editor (DeviceHub.apply on the service);
    the devices named in `removed` are deleted from it."""
    config = alpha.get("/api/v0/acquisition-config").json()
    devices = [
        {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
        for d in config["devices"]
        if d["name"] not in removed
    ]
    for device in devices:
        device["slave_id"] = (slave_ids or {}).get(device["name"], device["slave_id"])
        device["enabled"] = (enabled or {}).get(device["name"], device["enabled"])
    saved = alpha.put("/api/v0/acquisition-config", {"bus": {**config["bus"], **(bus or {})}, "devices": devices})
    assert saved.status_code == 200, saved.text


@dataclass
class Running:
    alpha: Alpha
    port: FakeSerial
    devices: dict[int, FakeDevice]
    calls: list[str]

    def spy(self) -> None:
        hub = self.alpha.host.hub
        assert hub is not None
        coordinator = hub.coordinator
        original = coordinator.queue_task

        def queue_task(key: str, kind: str, payload: object = None) -> None:
            self.calls.append(kind)
            original(key, kind, payload)

        coordinator.queue_task = queue_task  # type: ignore[method-assign]

    def refused(self, response: Any, status: int, code: str, message: str | None = None) -> None:  # noqa: ANN401
        assert response.status_code == status, response.text
        assert error_code(response) == code, response.text
        if message is not None:
            assert response.json()["error"]["message"] == message
        assert self.calls == [], self.calls


def running_alpha(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    """The `running` fixture of the rejection tests: tier 2, taken over, a page open on the communication tab."""
    devices = {1: FakeDevice(), 2: FakeDevice(serial_number=0x0BADCAFE)}
    port = fake_port(monkeypatch, devices)
    with wired(port):
        start(alpha)
        open_page(alpha, tab=2)
        case = Running(alpha, port, devices, [])
        case.spy()
        yield case


def maintenance_endpoints(alpha: Alpha) -> list[tuple[str, str]]:
    paths = alpha.get("/api/v0/openapi.json").json()["paths"]
    return [
        (path, method)
        for path, item in paths.items()
        for method in item
        if (path.startswith("/api/v0/maintenance") or path.endswith("/comm/read"))
    ]


def send(alpha: Alpha, path: str, method: str) -> Any:  # noqa: ANN401 (httpx.Response)
    path = path.replace("{key}", "p1")
    body: dict[str, Any] = form() if "/comm/" in path and not path.endswith("devices/p1/comm/read") else {}
    if path.endswith("/tab") or path.endswith("/page") and method == "post":
        body = {"tab": 0}
    if path.endswith("/target"):
        body = {"key": "North"}
    if path.endswith("/draft"):
        body = {"field": "y0", "value": 1.0}
    if method == "get":
        return alpha.get(path)
    if method == "delete":
        return alpha.delete(path)
    if method == "put":
        return alpha.put(path, body)
    if method == "patch":
        return alpha.patch(path, body)
    return alpha.post(path, body)
