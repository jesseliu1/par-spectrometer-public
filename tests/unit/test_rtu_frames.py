"""Finding one slave's valid RTU frames in a byte stream (D-101 silent criterion, ruling 37, POLL-007)."""

from __future__ import annotations

import pytest

from par_app.protocol import crc16_modbus
from par_app.rtu_frames import count_slave_frames

pytestmark = pytest.mark.unit

STOP_ECHO = bytes.fromhex("01060019000199cd")  # slave 1, FC6 register 25 := 1, independently encoded


def _frame(body: bytes) -> bytes:
    crc = crc16_modbus(body)
    return body + bytes((crc & 0xFF, crc >> 8))


def _count(data: bytes, slave: int = 1) -> int:
    return count_slave_frames(data, slave, crc16_modbus)


@pytest.mark.spec("POLL-007")
def test_a_whole_reply_counts_once() -> None:
    assert _count(STOP_ECHO) == 1
    assert _count(_frame(bytes((1, 4, 4, 0, 1, 0, 2)))) == 1
    assert _count(_frame(bytes((1, 0x84, 0x04)))) == 1  # the device's own exception reply is an answer


@pytest.mark.spec("POLL-007")
def test_echo_followed_by_part_of_a_read_reply_still_counts_the_echo() -> None:
    read_reply = _frame(bytes((1, 4, 4, 0, 1, 0, 2)))
    assert _count(STOP_ECHO + read_reply[:5]) == 1
    assert _count(b"\x00\xff" + STOP_ECHO + read_reply) == 2


@pytest.mark.spec("POLL-007", "POLL-071", "POLL-082")
@pytest.mark.parametrize(
    "data",
    [
        _frame(bytes((1, 0x86, 0x0A))),
        _frame(bytes((1, 0x84, 0x0B))) + _frame(bytes((1, 0x86, 0x0B))),
        STOP_ECHO[:-1] + bytes((STOP_ECHO[-1] ^ 0xFF,)),
        STOP_ECHO[:6],
        b"",
    ],
    ids=["gateway-0x0A", "gateway-0x0B-twice", "bad-crc", "truncated", "empty"],
)
def test_bytes_that_are_no_frame_from_the_device_count_zero(data: bytes) -> None:
    assert _count(data) == 0


@pytest.mark.spec("POLL-007", "POLL-071", "POLL-082")
def test_frames_from_another_slave_do_not_count() -> None:
    assert _count(STOP_ECHO, slave=2) == 0
    assert _count(_frame(bytes((2, 6, 0, 25, 0, 0))) + STOP_ECHO, slave=2) == 1
