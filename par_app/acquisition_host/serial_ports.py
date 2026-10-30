"""The settings page's 计算机串口 list and 刷新串口 (#74): V1.0.3's MainWindow.refresh_serial_ports for the alpha.

Only `serial.tools.list_ports.comports()` is called: the operating system's port list, in the order it gives it
(V1.0.3's settings page does not sort it), no port is opened (MAINT-051) and nothing is chosen or switched for the
user (POLL-032). Each entry is V1.0.3's item: the text "<device> — <description>" ("未知设备" without a
description) and the device name as the value that is saved. The hint is V1.0.3's tooltip after a refresh.

The enumeration is injected so tests never ask the real system (R-4-7).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol

from serial.tools import list_ports

from ..application.errors import ApplicationError
from . import v1_texts


class PortInfo(Protocol):
    """What V1.0.3 reads of a `serial.tools.list_ports_common.ListPortInfo`."""

    device: str
    description: str | None


Enumerate = Callable[[], Iterable[PortInfo]]


class PortListFailed(ApplicationError):
    """The operating system could not list its serial ports; the page keeps the last list and may retry (R-1-5)."""

    code = "internal"
    retryable = True


def system_ports() -> Iterable[PortInfo]:
    ports: Iterable[PortInfo] = list_ports.comports()
    return ports


def listing(enumerate_ports: Enumerate = system_ports) -> dict[str, Any]:
    """{"ports": [{"value", "label"}], "hint"}: V1.0.3's items and tooltip; raises PortListFailed on OSError."""
    try:
        ports = list(enumerate_ports())
    except OSError as error:
        raise PortListFailed(v1_texts.SERIAL_PORTS_FAILED.format(error=error), repr(error)) from error
    items = [
        {
            "value": port.device,
            "label": v1_texts.SERIAL_PORT_LABEL.format(
                device=port.device, description=port.description or v1_texts.SERIAL_PORT_UNKNOWN
            ),
        }
        for port in ports
    ]
    hint = v1_texts.SERIAL_PORTS_FOUND.format(count=len(items)) if items else v1_texts.SERIAL_PORTS_NONE
    return {"ports": items, "hint": hint}
