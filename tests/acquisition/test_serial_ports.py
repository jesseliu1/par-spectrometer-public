"""计算机串口 list and 刷新串口 of the tier-1 settings form (#74): V1.0.3's MainWindow.refresh_serial_ports.

* the items are V1.0.3's: "<device> — <description>" ("未知设备" without a description), the device name as the
  value, in the order the operating system gives them (V1.0.3's settings page does not sort);
* the hint is V1.0.3's tooltip after a refresh (检测到 N 个串口… / 未检测到串口…);
* only the enumeration is called: no port is opened (MAINT-051), nothing is chosen for the user (POLL-032);
* GET /acquisition-config/serial-ports is gated like GET /acquisition-config: 403 in tier 0;
* an enumeration error is 500 internal, retryable, with V1.0.3's "串口枚举失败：" text (R-1-5).

Every port here is a fake list injected into the backend; the real system is never asked (R-4-7).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

import pytest

from par_app.acquisition_host import serial_ports
from par_app.acquisition_host.host import HostBackend
from tests.acquisition.conftest import Alpha

PATH = "/api/v0/acquisition-config/serial-ports"


@dataclass
class Port:
    device: str
    description: str | None


PORTS = [
    Port("COM7", "USB-SERIAL CH340"),
    Port("COM3", "Prolific USB-to-Serial"),
    Port("COM10", None),
    Port("COM1", ""),
]


def _fixed(ports: list[Port]) -> serial_ports.Enumerate:
    def enumerate_ports() -> Iterable[serial_ports.PortInfo]:
        return list(ports)

    return enumerate_ports


@pytest.mark.unit
@pytest.mark.spec("UI-135 MAINT-051 POLL-032")
def test_listing_is_v103_settings_page_items_in_system_order() -> None:
    found = serial_ports.listing(_fixed(PORTS))
    assert found["ports"] == [
        {"value": "COM7", "label": "COM7 — USB-SERIAL CH340"},
        {"value": "COM3", "label": "COM3 — Prolific USB-to-Serial"},
        {"value": "COM10", "label": "COM10 — 未知设备"},
        {"value": "COM1", "label": "COM1 — 未知设备"},
    ]
    assert found["hint"] == "检测到 4 个串口，请手动选择；不会自动搜索或切换端口。"


@pytest.mark.unit
def test_no_port_found_says_so() -> None:
    assert serial_ports.listing(_fixed([])) == {"ports": [], "hint": "未检测到串口；请确认 USB 线、驱动和设备电源。"}


@pytest.mark.unit
def test_enumeration_error_is_retryable_with_v103_text() -> None:
    def broken() -> Iterable[serial_ports.PortInfo]:
        raise OSError("SetupDiGetClassDevs failed")

    with pytest.raises(serial_ports.PortListFailed) as raised:
        serial_ports.listing(broken)
    assert raised.value.message == "串口枚举失败：SetupDiGetClassDevs failed"
    assert raised.value.retryable is True


def _inject(alpha: Alpha, enumerate_ports: serial_ports.Enumerate) -> None:
    cast(HostBackend, alpha.context.acquisition.backend).ports = enumerate_ports


@pytest.mark.qt
@pytest.mark.spec("UI-135 MAINT-051")
def test_endpoint_lists_ports_in_tier_1_only_and_opens_none(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a serial port was opened")

    monkeypatch.setattr("serial.Serial.open", no_open)
    calls: list[int] = []

    def counted() -> Iterable[serial_ports.PortInfo]:
        calls.append(1)
        return list(PORTS[:2])

    _inject(alpha, counted)
    refused = alpha.get(PATH)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "feature_disabled"
    assert calls == []  # tier 0 asks nothing of the system
    alpha.enable_tier_1()
    answer = alpha.get(PATH)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["ports"] == [
        {"value": "COM7", "label": "COM7 — USB-SERIAL CH340"},
        {"value": "COM3", "label": "COM3 — Prolific USB-to-Serial"},
    ]
    assert body["hint"] == "检测到 2 个串口，请手动选择；不会自动搜索或切换端口。"
    assert body["as_of"]
    assert alpha.get(PATH).status_code == 200  # 刷新串口 asks again
    assert calls == [1, 1]
    assert alpha.takeover() == "released"  # listing takes no lock and starts nothing


@pytest.mark.qt
def test_endpoint_failure_is_retryable_500(alpha: Alpha) -> None:
    def broken() -> Iterable[serial_ports.PortInfo]:
        raise OSError("access denied")

    _inject(alpha, broken)
    alpha.enable_tier_1()
    answer = alpha.get(PATH)
    assert answer.status_code == 500
    error = answer.json()["error"]
    assert error["code"] == "internal" and error["retryable"] is True
    assert error["message"] == "串口枚举失败：access denied"
    assert alpha.context.acquisition.tier() == 1  # an enumeration error stops nothing and keeps the tier
