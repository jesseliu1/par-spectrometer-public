"""The bus trace (issue #136 steps 2 and 3; owner's R-4-2 approval of 2026-10-29, scope one, recorded in #132).

Checked: the traced port changes nothing on the line (the same frames at the same moments with and without it, and
an untraced client gets the port itself); a device failure or a halt keeps the last stretch under its record number,
an ok message does not, and the kept windows are bounded; each exchange is summarised with its step, timing, frames
and verdict (the field case of #132: a late echo in front of a status reply), and per transaction the first problem
is told apart from the one during the resume; no payload (spectrum, identity, serial number) leaves memory.
"""

from __future__ import annotations

import json
import struct
from datetime import datetime

import pytest

from par_app.application.acquisition import StatusCache
from par_app.application.bus_trace import KEPT_FAILURES, KEPT_HALTS, RECEIVED, SENT, BusTrace, Entry, TappedPort
from par_app.application.bus_trace_summary import crc16_modbus, exchanges, transactions
from par_app.application.run_events import RunEventLog
from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_app.models import ConnectionConfig
from par_app.protocol import ParModbusClient
from par_app.protocol import crc16_modbus as protocol_crc
from par_app.rtu_frames import PORT_TAP
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.unit.test_rtu_late_echo import Device, ScriptedPort, _client, _echo, _reply, _status_words

pytestmark = [pytest.mark.unit, pytest.mark.spec("ACQ-025 ACQ-026")]


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 29, 9, 0, tzinfo=BEIJING_TZ))


def _transaction(traced: bool) -> tuple[ScriptedPort, BusTrace]:
    client, clock = _client()
    port = ScriptedPort(clock, Device(client, reply_delay=0.55, echo_delay=0.35))  # device 4's failing round, #132
    trace = BusTrace(clock)  # type: ignore[arg-type]
    client._serial = trace.wrap(port, clock) if traced else port  # noqa: SLF001 (what connect() gets from PORT_TAP)
    with client.acquisition_budget(40.0):
        client.read_spectrum_transaction()
    return port, trace


def _failing(traced: bool) -> tuple[ScriptedPort, BusTrace]:
    """The spectrum read gets half a reply, the resume's second status read nothing: 恢复采集未确认."""
    client, clock = _client(timeout=0.3)
    device = Device(client, reply_delay=0.05, echo_delay=0.08)
    seen = {"spectrum": False}

    def respond(frame: bytes) -> list[tuple[float, bytes]]:
        address = struct.unpack(">H", frame[2:4])[0]
        if frame[1] == 4 and address == 1000:
            seen["spectrum"] = True
            return [(0.05, _reply(client, [0] * 10)[:20])]
        if seen["spectrum"] and frame[1] == 4 and address == 400:
            return []
        return device(frame)

    port = ScriptedPort(clock, respond)
    trace = BusTrace(clock)  # type: ignore[arg-type]
    client._serial = trace.wrap(port, clock) if traced else port  # noqa: SLF001
    with pytest.raises(Exception, match="恢复采集未确认"), client.acquisition_budget(40.0):
        client.read_spectrum_transaction()
    return port, trace


def test_a_failure_and_its_resume_send_the_same_frames_at_the_same_moments_traced_or_not() -> None:
    traced, _ = _failing(traced=True)
    plain, _ = _failing(traced=False)
    assert traced.frames == plain.frames and traced.sent_at == pytest.approx(plain.sent_at, abs=1e-9)


def test_through_connect_the_same_frames_go_out_at_the_same_moments_traced_or_not() -> None:
    """connect() opens the port through PORT_TAP; a full transaction on the fake bus, with and without the trace."""

    def run(install: bool) -> list[tuple[float, bytes]]:
        clock = _clock()
        port = FakeSerial(clock, {3: FakeDevice()})
        trace = BusTrace(clock)
        client = ParModbusClient(ConnectionConfig(slave_id=3), clock=clock)
        with wired(port):
            if install:
                trace.install()
            try:
                assert client.connect()
                with client.acquisition_budget(40.0):
                    client.read_spectrum_transaction()
            finally:
                trace.uninstall()
        assert bool(trace.current().entries) == install
        return port.written()

    assert run(install=True) == run(install=False)


def test_the_traced_port_sends_the_same_frames_at_the_same_moments() -> None:
    traced, trace = _transaction(traced=True)
    plain, _ = _transaction(traced=False)
    assert traced.frames == plain.frames and traced.sent_at == pytest.approx(plain.sent_at, abs=1e-9)
    window = trace.current()
    assert [entry.data for entry in window.entries if entry.direction == SENT] == traced.frames


def test_connect_wraps_the_port_only_while_the_trace_is_installed() -> None:
    clock = _clock()
    port = FakeSerial(clock, {3: FakeDevice()})
    trace = BusTrace(clock)
    client = ParModbusClient(ConnectionConfig(slave_id=3), clock=clock)
    with wired(port):
        trace.install()
        try:
            assert client.connect() and isinstance(client._serial, TappedPort)  # noqa: SLF001
            client._serial.timeout = 0.5  # noqa: SLF001 (set on the real port)
            assert port.timeout == 0.5
        finally:
            trace.uninstall()
        assert PORT_TAP.recorder is None
        assert client.connect() and client._serial is port  # noqa: SLF001


def test_the_summary_crc_is_the_protocols() -> None:
    frame = bytes.fromhex("0304000000 3b".replace(" ", ""))
    assert crc16_modbus(frame) == protocol_crc(frame)


def _window(trace: BusTrace) -> list[dict]:
    return list(exchanges(trace.current()))


def test_the_field_case_reads_as_a_late_echo_in_front_of_a_correct_reply() -> None:
    _, trace = _transaction(traced=True)
    records = _window(trace)
    steps = [record["step"] for record in records]
    assert steps[:3] == ["冻结", "状态基础段", "状态光学段"] and steps[-3:] == ["恢复", "状态基础段", "状态光学段"]
    base = records[1]
    assert base["verdict"] == "正常" and base["received_bytes"] == 8 + 123
    assert [frame.get("late_echo", False) for frame in base["frames"]] == [True, False]
    assert base["first_byte_ms"] == pytest.approx(250.0, abs=25) and base["last_byte_ms"] >= base["first_byte_ms"]
    assert all(record["verdict"] in ("正常", "不等回显") for record in records)
    (transaction,) = transactions(records)
    assert transaction["slave"] == 3 and transaction["first_problem"] is None and transaction["resumed"]


def test_the_first_problem_and_the_one_during_the_resume_are_told_apart() -> None:
    _, trace = _failing(traced=True)
    (transaction,) = transactions(_window(trace))
    assert transaction["first_problem"]["step"].startswith("光谱 1000:")
    assert transaction["first_problem"]["verdict"] == "应答不完整"
    assert transaction["resume_problem"] == {**transaction["resume_problem"], "step": "状态光学段", "verdict": "无应答"}


def test_each_reply_is_judged_as_the_protocol_would() -> None:
    """Independent and review of the trace: 正常 only for exactly the expected frame (an echo straight after it
    excepted); a right-CRC frame with stray bytes, a wrong byte count or another slave is named for what it is."""
    client, clock = _client()
    trace = BusTrace(clock)  # type: ignore[arg-type]
    request = client._rtu_frame(4, struct.pack(">HH", 0, 59))  # noqa: SLF001
    good = _reply(client, _status_words(0, 59, 1))
    damaged = bytearray(good)
    damaged[10] ^= 0xFF
    short_count = _reply(client, _status_words(0, 58, 1))
    cases = {
        "CRC 不符": bytes(damaged),
        "从站或功能码不符": _reply(client, _status_words(0, 59, 1), slave_id=4),
        "应答后有多余字节": good + b"\x00\x00",
        "应答不完整": good[:100],
        "字节数不符": short_count + b"\x00\x00",
        "无应答": None,
        "正常": good,
    }
    for t, reply in enumerate(cases.values()):
        trace.add(Entry(float(t), SENT, request))
        if reply is not None:
            trace.add(Entry(t + 0.1, RECEIVED, reply))
    assert [record["verdict"] for record in _window(trace)] == list(cases)
    assert {record["valid_frames"] for record in _window(trace)} >= {0, 1}
    assert all(record["sent_bytes"] == 8 for record in _window(trace))


def test_transactions_are_kept_per_slave_and_end_after_the_resume_is_confirmed() -> None:
    """Device 3's transaction, then a time sync for it (outside the transaction), then device 4's."""
    client, clock = _client()
    trace = BusTrace(clock)  # type: ignore[arg-type]

    def frame(slave: int, function: int, address: int, word: int) -> bytes:
        body = bytes([slave, function]) + struct.pack(">HH", address, word)
        return body + crc16_modbus(body).to_bytes(2, "little")

    plan = [
        frame(3, 6, 25, 1),
        frame(3, 4, 0, 59),
        frame(3, 6, 25, 0),
        frame(3, 4, 0, 59),
        frame(3, 4, 400, 76),
        frame(3, 16, 32, 4),
        frame(4, 6, 25, 1),
        frame(4, 4, 0, 59),
    ]
    for t, request in enumerate(plan):
        trace.add(Entry(float(t), SENT, request))  # nothing comes back: every read is 无应答
    found = transactions(_window(trace))
    assert [(item["slave"], item["first_problem"]["step"]) for item in found] == [(3, "状态基础段"), (4, "状态基础段")]
    assert found[0]["resume_problem"]["step"] == "状态基础段"  # the 对时 afterwards is not the resume's problem


def test_no_payload_leaves_memory() -> None:
    """Spectrum words and an identity reply with a serial number: the summary holds lengths and frame kinds only."""
    client, clock = _client()
    trace = BusTrace(clock)  # type: ignore[arg-type]
    identity = client._rtu_frame(4, struct.pack(">HH", 2047, 11))  # noqa: SLF001
    serial_words = [0xBEEF, 0x0ACE] + [0x4241] * 9
    trace.add(Entry(0.0, SENT, identity))
    trace.add(Entry(0.1, RECEIVED, _reply(client, serial_words)))
    text = json.dumps(_window(trace), ensure_ascii=False)
    assert _window(trace)[0]["step"] == "设备身份" and _window(trace)[0]["verdict"] == "正常"
    for secret in (str(0xBEEF), str(0x0ACE0BEEF), "BEEF", "beef", "AB"):
        assert secret not in text


def _cache(tmp_path) -> tuple[StatusCache, BusTrace, RunEventLog]:  # noqa: ANN001
    clock = _clock()
    trace = BusTrace(clock)
    log = RunEventLog(tmp_path, clock, session="cafe0136")
    return StatusCache(clock, log, trace), trace, log


def _device(message: str, level: str) -> dict:
    return {"key": "p4", "name": "South", "slave_id": 4, "enabled": True, "level": level, "message": message}


def test_a_device_failure_or_a_halt_keeps_the_trace_under_its_record_number(tmp_path) -> None:  # noqa: ANN001
    cache, trace, log = _cache(tmp_path)
    trace.add(Entry(0.0, SENT, _echo(ParModbusClient(ConnectionConfig(slave_id=4)), True)))
    cache.set_device(_device("采集成功 #12，正常，单次读取完成", "ok"))
    assert trace.kept() == []  # an ok message keeps nothing
    cache.set_device(_device("连续第 1 次尝试失败：设备通信超时", "warning"))
    notice = cache.snapshot()["devices"][0]["notice"]
    cache.set_halt({"source_key": "p4", "message": "恢复采集未确认：设备通信超时", "resume_unconfirmed": True})
    halt = cache.snapshot()["halt"]["notice"]
    kept = trace.kept()
    assert [(window.event_id, window.kind) for window in kept] == [
        (notice["event_id"], "device"),
        (halt["event_id"], "halt"),
    ]
    assert kept[0].message == "连续第 1 次尝试失败：设备通信超时" and len(kept[0].entries) == 1
    log.close()


def test_kept_windows_are_bounded(tmp_path) -> None:  # noqa: ANN001
    cache, trace, log = _cache(tmp_path)
    trace.add(Entry(0.0, SENT, b"\x04\x04\x00\x00\x00\x3b\x00\x00"))
    for count in range(1, KEPT_FAILURES + 4):
        cache.set_device(_device(f"连续第 {count} 次尝试失败：设备通信超时", "warning"))
    for count in range(KEPT_HALTS + 2):
        trace.keep(f"cafe0136-90000{count}", "halt", "锁停")
    kinds = [window.kind for window in trace.kept()]
    assert kinds.count("device") == KEPT_FAILURES and kinds.count("halt") == KEPT_HALTS
    assert trace.windows_dropped == 3 + 2
    log.close()
