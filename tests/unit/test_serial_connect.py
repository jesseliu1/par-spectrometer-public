"""ParModbusClient.connect releases the opened serial handle on any failure (POLL-074, DEF-05).

pyserial's POSIX backend raises OSError (ioctl) or termios.error (tcflush) from setDTR/setRTS/
reset_input_buffer; neither is a SerialException. The serial port is faked in memory, no device is opened.
"""

from __future__ import annotations

import pytest

from par_app import protocol
from par_app.models import ConnectionConfig
from tests.virtual_clock import virtual_clock

try:
    import termios

    TCFLUSH_ERROR: type[Exception] = termios.error
except ImportError:  # Windows: pyserial's Win32 backend does not raise from these calls
    TCFLUSH_ERROR = OSError

pytestmark = pytest.mark.unit


class FakeSerial:
    """In-memory stand-in for serial.Serial; `fail_on` names the post-open step that raises."""

    instances: list[FakeSerial] = []

    def __init__(self, *args: object, fail_on: str = "", error: Exception | None = None, **kwargs: object) -> None:
        self.fail_on = fail_on
        self.error = error
        self.close_calls = 0
        FakeSerial.instances.append(self)

    def _step(self, name: str) -> None:
        if name == self.fail_on and self.error is not None:
            raise self.error

    def setDTR(self, value: bool) -> None:
        self._step("setDTR")

    def setRTS(self, value: bool) -> None:
        self._step("setRTS")

    def reset_input_buffer(self) -> None:
        self._step("reset_input_buffer")

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture
def fake_port(monkeypatch: pytest.MonkeyPatch) -> list[FakeSerial]:
    FakeSerial.instances = []
    return FakeSerial.instances


@pytest.mark.spec("POLL-074")
@pytest.mark.parametrize(
    ("step", "error"),
    [
        ("setDTR", OSError(5, "Input/output error")),
        ("setRTS", OSError(25, "Inappropriate ioctl for device")),
        ("reset_input_buffer", TCFLUSH_ERROR(5, "Input/output error")),
    ],
)
def test_non_serial_exception_after_open_closes_handle_and_reraises(
    monkeypatch: pytest.MonkeyPatch, fake_port: list[FakeSerial], step: str, error: Exception
) -> None:
    monkeypatch.setattr(protocol.serial, "Serial", lambda *a, **kw: FakeSerial(*a, fail_on=step, error=error, **kw))
    client = protocol.ParModbusClient(ConnectionConfig(transport="rtu", serial_port="/dev/fake"), clock=virtual_clock())

    with pytest.raises(type(error)) as raised:
        client.connect()

    assert raised.value is error  # original exception is preserved, not wrapped
    assert len(fake_port) == 1
    assert fake_port[0].close_calls == 1
    client.close()  # handle already released: a later close must not touch it again
    assert fake_port[0].close_calls == 1


@pytest.mark.spec("POLL-074")
def test_successful_connect_keeps_handle_open(monkeypatch: pytest.MonkeyPatch, fake_port: list[FakeSerial]) -> None:
    monkeypatch.setattr(protocol.serial, "Serial", FakeSerial)
    client = protocol.ParModbusClient(ConnectionConfig(transport="rtu", serial_port="/dev/fake"), clock=virtual_clock())

    assert client.connect() is True
    assert fake_port[0].close_calls == 0
    client.close()
    assert fake_port[0].close_calls == 1


@pytest.mark.spec("POLL-074")
def test_close_failure_does_not_mask_original_error(
    monkeypatch: pytest.MonkeyPatch, fake_port: list[FakeSerial]
) -> None:
    original = OSError(5, "Input/output error")

    class ClosingFails(FakeSerial):
        def close(self) -> None:
            self.close_calls += 1
            raise OSError(9, "Bad file descriptor")

    monkeypatch.setattr(
        protocol.serial, "Serial", lambda *a, **kw: ClosingFails(*a, fail_on="setDTR", error=original, **kw)
    )
    client = protocol.ParModbusClient(ConnectionConfig(transport="rtu", serial_port="/dev/fake"), clock=virtual_clock())

    with pytest.raises(OSError) as raised:
        client.connect()

    assert raised.value is original
    assert fake_port[0].close_calls == 1
    client.close()  # the handle was dropped even though closing it failed
    assert fake_port[0].close_calls == 1
