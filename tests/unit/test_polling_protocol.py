"""Polling protocol, deadline and config checks migrated from verify_polling.py (R-3-4).

These cases exercise ParModbusClient, ParDatabase and the config models only; none of them needs Qt.
The coordinator cases live in tests/qt/test_polling.py and tests/qt/test_polling_maintenance.py.
Migration map: tests/migration/verify_polling.md.

Mocks (R-3-4): the frozen-read cases patch ParModbusClient's register helpers (`set_stop`, `wait_stop`,
`_read_input_chunked`, `_read_input`, `read_status`) or the transport (`_rtu_read_registers`, the pymodbus
client, a fake serial port). The assertions are about the transaction ordering, budgets and cleanup that
ParModbusClient itself implements on top of those helpers, so replacing the wire I/O does not weaken them.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from par_app.database import ParDatabase
from par_app.models import AppConfig, ConnectionConfig, DeviceConfig, DeviceStatus
from par_app.protocol import (
    CommunicationCancelled,
    CommunicationTimeout,
    HardwareStateError,
    ParModbusClient,
    ProtocolError,
)
from tests.virtual_clock import virtual_clock

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("stage", ["send", "confirm", "spectrum", "parameters", "cancel"])
def test_freeze_failures_never_read_unconfirmed_data_and_always_resume(stage: str) -> None:
    client = ParModbusClient(ConnectionConfig(baudrate=19200))
    commands: list[bool] = []
    failure: Exception = CommunicationCancelled("cancelled") if stage == "cancel" else ProtocolError(stage)

    def stop(desired: bool) -> None:
        commands.append(desired)
        if desired and stage == "send":
            raise failure

    def confirm(desired: int) -> DeviceStatus:
        if desired and stage == "confirm":
            raise failure
        return DeviceStatus(initialized=True, stop_status=desired)

    with (
        patch.object(client, "set_stop", side_effect=stop),
        patch.object(client, "wait_stop", side_effect=confirm) as wait,
        patch.object(
            client,
            "_read_input_chunked",
            return_value=[1] * 701,
            side_effect=failure if stage in ("spectrum", "cancel") else None,
        ) as spectrum,
        patch.object(
            client, "_read_input", return_value=[0] * 54, side_effect=failure if stage == "parameters" else None
        ) as parameters,
    ):
        with pytest.raises(type(failure)) as caught:
            client.read_spectrum_transaction()
        assert caught.value is failure
        assert commands == [True, False]
        assert wait.call_args.args == (0,)
        if stage in ("send", "confirm"):
            spectrum.assert_not_called()
            parameters.assert_not_called()


def test_cancelled_acquisition_still_confirms_resume() -> None:
    client = ParModbusClient(ConnectionConfig(baudrate=19200))
    cancelled = False
    commands: list[bool] = []

    def read(*args: object) -> None:
        nonlocal cancelled
        cancelled = True
        client._check_budget()

    def stop(desired: bool) -> None:
        client._check_budget()
        commands.append(desired)

    with (
        patch.object(client, "set_stop", side_effect=stop),
        patch.object(
            client,
            "wait_stop",
            side_effect=lambda desired: client._check_budget() or DeviceStatus(initialized=True, stop_status=desired),
        ),
        patch.object(client, "_read_input_chunked", side_effect=read),
    ):
        with pytest.raises(CommunicationCancelled):
            with client.acquisition_budget(10, lambda: cancelled):
                client.read_spectrum_transaction()
    assert commands == [True, False]
    assert client._cancelled is None
    assert client._deadline is None
    assert not client._finish_packet


@pytest.mark.parametrize(("baudrate", "chunk_size"), [(9600, 64), (19200, 64), (115200, 125)])
def test_stop_status_confirmation_and_chunk_sizes(baudrate: int, chunk_size: int) -> None:
    client = ParModbusClient(ConnectionConfig(baudrate=baudrate))
    with (
        patch.object(
            client,
            "read_status",
            side_effect=[DeviceStatus(initialized=True, stop_status=0), DeviceStatus(initialized=True, stop_status=1)],
        ),
        patch.object(client, "_delay"),
    ):
        assert client.wait_stop(1).stop_status == 1
    with patch.object(
        client, "_read_input", side_effect=lambda address, count: list(range(address, address + count))
    ) as read:
        assert client._read_input_chunked(1000, 701) == list(range(1000, 1701))
        assert [call.args for call in read.call_args_list] == [
            (1000 + offset, min(chunk_size, 701 - offset)) for offset in range(0, 701, chunk_size)
        ]


@pytest.mark.parametrize(
    ("transport", "baudrate"), [("rtu", 1200), ("rtu", 9600), ("rtu", 19200), ("rtu", 115200), ("tcp", 19200)]
)
def test_all_transports_freeze_before_read_and_confirm_resume(transport: str, baudrate: int) -> None:
    client = ParModbusClient(ConnectionConfig(transport=transport, baudrate=baudrate))
    events: list[tuple[object, ...]] = []
    frozen = DeviceStatus(initialized=True, stop_status=1, spectral_coefficient=7)

    def wait(desired: int) -> DeviceStatus:
        events.append(("confirm", desired))
        return frozen if desired else DeviceStatus(initialized=True, stop_status=0)

    def read(address: int, count: int) -> list[int]:
        events.append(("read", address, count))
        return [42] * count if address == 1000 else [0] * count

    with (
        patch.object(client, "set_stop", side_effect=lambda desired: events.append(("stop", desired))),
        patch.object(client, "wait_stop", side_effect=wait),
        patch.object(client, "_read_input_chunked", side_effect=read),
        patch.object(client, "_read_input", side_effect=read),
    ):
        status, points, parameters = client.read_spectrum_transaction()
    assert status is frozen
    assert points == [42] * 701
    assert len(parameters) == 27
    assert events == [
        ("stop", True),
        ("confirm", 1),
        ("read", 1000, 701),
        ("read", 1701, 54),
        ("stop", False),
        ("confirm", 0),
    ]


@pytest.mark.spec("DLI-021")
def test_quality_schema_upgrade_preserves_old_records(tmp_path: Path) -> None:
    path = tmp_path / 'legacy.sqlite3'
    database = ParDatabase(path)
    database.save_acquisition(
        dict(
            acquired_at='2026-09-18T00:00:00',
            success=1,
            elapsed_ms=1,
            raw_points=[42] * 701,
            software_metrics_json='{"ppfd":9000}',
        )
    )
    with database.connect() as connection:
        connection.execute('ALTER TABLE acquisitions DROP COLUMN quality_json')
        connection.execute('ALTER TABLE acquisitions DROP COLUMN dli_eligible')
    upgraded = ParDatabase(path)
    row, points = upgraded.get_spectrum(1)
    assert points == [42] * 701
    assert row['quality_json'] is None
    assert row['dli_eligible'] is None
    assert row['software_metrics_json'] == '{"ppfd":9000}'
    assert upgraded.dli_samples('2026-09-18', '2026-09-19', '2026-09-17')[0]['eligible'] == 1


def test_tcp_acquisition_packet_has_finite_independent_timeout() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(transport='tcp', timeout_seconds=1), clock=clock)

    def response(**kwargs: object) -> MagicMock:
        clock.sleep(0.4)
        # unittest assertAlmostEqual(places=7), spelled out so the tolerance is unchanged.
        assert round(abs(client._io_timeout() - 0.6), 7) == 0
        return MagicMock(registers=[42], isError=lambda: False)

    with (
        patch.object(client.client, 'read_input_registers', side_effect=response) as read,
    ):
        with client.acquisition_budget(10):
            clock.sleep(9.9)
            assert client._read_input(1000, 1) == [42]
            with pytest.raises(CommunicationTimeout):
                client._read_input(1001, 1)
        assert read.call_count == 1


def test_acquisition_thaws_after_budget_exhaustion() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(baudrate=115200), clock=clock)
    commands: list[bool] = []

    def read(*args: object) -> None:
        clock.sleep(10.2)
        client._check_budget()

    with (
        patch.object(client, 'set_stop', side_effect=commands.append),
        patch.object(
            client, 'wait_stop', side_effect=lambda *args: client._delay(0.1) or DeviceStatus(initialized=True)
        ),
        patch.object(client, '_read_input_chunked', side_effect=read),
    ):
        with pytest.raises(CommunicationTimeout):
            with client.acquisition_budget(10):
                client.read_spectrum_transaction()
    assert commands == [True, False]
    assert clock.monotonic() < 12
    assert client._deadline is None
    assert not client._finish_packet


@pytest.mark.parametrize(("silent", "cancel"), [(False, False), (False, True), (True, False), (True, True)])
def test_rtu_finishes_or_drains_before_next_device(silent: bool, cancel: bool) -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(timeout_seconds=0.5), clock=clock)
    response = client._rtu_frame(4, bytes([2, 0, 42]))

    class Port:
        in_waiting = 0
        writes = 0
        late_drained = False
        timeout: float  # set by ParModbusClient before each read

        def write(self, frame: bytes) -> int:
            self.writes += 1
            return len(frame)

        def read(self, count: int) -> bytes:
            if not silent:
                clock.sleep(0.3)
                return response
            clock.sleep(self.timeout)
            if clock.monotonic() >= 10.5 and not self.late_drained:
                self.late_drained = True
                return response
            return b''

    port = Port()
    client._serial = port
    expected = CommunicationCancelled if cancel else CommunicationTimeout
    with pytest.raises(expected):
        with client.acquisition_budget(10, lambda: cancel and clock.monotonic() >= 10):
            clock.sleep(9.9)
            values = client._read_input(1000, 1)
            assert values == [42]
            client.set_slave_id(2)
            client._read_input(1000, 1)
    assert port.writes == 1
    assert clock.monotonic() <= 11
    assert port.late_drained == silent


def test_acquisition_finishes_current_packet_only() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(timeout_seconds=1.5), clock=clock)

    def response(*args: object) -> list[int]:
        client._delay(0.4)
        return [7]

    with (
        patch.object(client, '_rtu_read_registers', side_effect=response) as read,
    ):
        with client.acquisition_budget(10):
            clock.sleep(9.9)
            assert client._read_input(1000, 1) == [7]
            # unittest assertAlmostEqual(places=7), spelled out so the tolerance is unchanged.
            assert round(abs(clock.monotonic() - 10.3), 7) == 0
            with pytest.raises(CommunicationTimeout):
                client._read_input(1001, 1)
        assert read.call_count == 1
    assert not client._finish_packet
    assert client._deadline is None


def test_cleanup_failure_does_not_mask_hardware_state() -> None:
    client = ParModbusClient(ConnectionConfig(baudrate=115200))
    status = DeviceStatus(initialized=True, need_power_cycle=True)
    with (
        patch.object(client, 'set_stop', side_effect=[None, ProtocolError('cleanup failed')]),
        patch.object(client, 'wait_stop', side_effect=HardwareStateError(status)),
        patch.object(client, '_read_input_chunked') as read,
    ):
        with pytest.raises(HardwareStateError):
            with client.communication_budget(10):
                client.read_spectrum_transaction()
        read.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [DeviceStatus(), DeviceStatus(initialized=True, need_power_cycle=True)],
    ids=["not_initialized", "need_power_cycle"],
)
def test_hardware_state_stops_before_spectrum_read(status: DeviceStatus) -> None:
    client = ParModbusClient(ConnectionConfig())
    with (
        patch.object(client, 'set_stop'),
        patch.object(client, 'read_status', return_value=status),
        patch.object(client, '_read_input_chunked') as read,
    ):
        with pytest.raises(HardwareStateError):
            client.read_spectrum_transaction()
        read.assert_not_called()


def test_failure_exit_switch_config_round_trip() -> None:
    """开关写入配置并能读回；旧配置缺少该键时按默认（不退出采集）处理。"""
    config = AppConfig(
        configured=True,
        devices=[
            DeviceConfig(name='On', slave_id=1, auto_stop_on_failure=True),
            DeviceConfig(name='Off', slave_id=2, auto_stop_on_failure=False),
        ],
    )
    restored = AppConfig.from_dict(config.to_dict())
    assert restored.devices[0].auto_stop_on_failure
    assert not restored.devices[1].auto_stop_on_failure
    assert restored.to_dict()['devices'][0]['auto_stop_on_failure'] is True
    legacy = AppConfig.from_dict({'bus': {}, 'devices': [{'name': 'Legacy', 'slave_id': 3}], 'configured': True})
    assert not legacy.devices[0].auto_stop_on_failure
    assert DeviceConfig().auto_stop_on_failure is False


def test_tcp_receive_budget_is_shared() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(transport='tcp', timeout_seconds=4), clock=clock)

    def receive(*args: object) -> bytes:
        clock.sleep(client.client.comm_params.timeout_connect)
        return b'partial'

    with (
        patch('par_app.protocol.ModbusTcpClient.recv', side_effect=receive),
    ):
        with pytest.raises(CommunicationTimeout):
            with client.communication_budget(10):
                client.client.recv(None)
                client.client.recv(None)
                client.client.recv(None)
    assert clock.monotonic() == 10


def test_serial_reads_share_budget() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(timeout_seconds=1.5), clock=clock)

    class SilentPort:
        in_waiting = 0
        timeout = 0.02
        write_timeout = 1.5

        def write(self, frame: bytes) -> int:
            return len(frame)

        def read(self, count: int) -> bytes:
            clock.sleep(self.timeout)
            return b''

    client._serial = SilentPort()
    with pytest.raises(CommunicationTimeout):
        with client.communication_budget(10):
            while True:
                try:
                    client._read_input(1000, 64)
                except CommunicationTimeout:
                    raise
                except ProtocolError:
                    pass
    assert abs(clock.monotonic() - 10) <= 0.001


def test_freeze_failure_attempts_resume_within_budget() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(baudrate=115200), clock=clock)
    commands: list[bool] = []

    def read(*args: object) -> None:
        client._delay(12)

    with (
        patch.object(client, 'set_stop', side_effect=commands.append),
        patch.object(client, 'wait_stop', return_value=DeviceStatus(initialized=True)),
        patch.object(client, '_read_input_chunked', side_effect=read),
    ):
        with pytest.raises(CommunicationTimeout):
            with client.communication_budget(10):
                client.read_spectrum_transaction()
    assert commands == [True, False]
    assert clock.monotonic() <= 10


def test_shared_deadline_and_cancellation() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(), clock=clock)
    with pytest.raises(CommunicationTimeout):
        with client.communication_budget(10):
            client._delay(7)
            client._delay(7)
    assert clock.monotonic() == 10
    assert client._deadline is None
    with pytest.raises(CommunicationCancelled):
        with client.communication_budget(10, lambda: True):
            # unittest self.fail() raised AssertionError; kept so the exception type is unchanged.
            raise AssertionError('Cancelled operation executed')


def test_retry_cannot_extend_deadline() -> None:
    clock = virtual_clock()
    client = ParModbusClient(ConnectionConfig(), clock=clock)

    def no_response(*args: object) -> list[int]:
        client._delay(4)
        raise ProtocolError('no response')

    with (
        patch.object(client, '_rtu_read_registers', side_effect=no_response),
    ):
        with pytest.raises(CommunicationTimeout):
            with client.communication_budget(10):
                client._read_input(1000, 64)
    assert clock.monotonic() == 10


@pytest.mark.parametrize("count", range(1, 5))
@pytest.mark.parametrize(("requested", "expected"), [(1, 40), (40, 40), (3600, 3600), (7200, 3600)])
def test_fixed_cycle_limits(count: int, requested: int, expected: int) -> None:
    config = AppConfig(devices=[DeviceConfig(slave_id=index + 1) for index in range(count)])
    config.bus.poll_cycle_seconds = requested
    assert config.effective_poll_cycle_seconds() == expected
