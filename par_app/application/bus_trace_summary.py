"""One record per exchange from a bus trace window (issue #136 steps 2 and 3), for the diagnostics bundle.

An exchange is a frame written and the bytes read until the next write. Each record says which step it was,
read from the request (冻结, 恢复, 状态基础段, 状态光学段, 光谱, 光度参数, 对时, ...), its target slave, when
the first and the last byte came (ms after the write), how many bytes, which frames they held (slave, function,
length, CRC right or not, and whether a frame is a late write echo of an earlier unanswered command, #132), the
bytes no frame explains, and a verdict. Per transaction (a 冻结 to the next one) the first problem and the first
problem after 恢复 are named, so the earliest error and the one during the resume are told apart.

Only the request's slave, function, register and count (or the value of a single-register write) and the lengths of
what came back leave memory: no spectrum, parameters, identity or serial number.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from typing import Any

from ..database import format_beijing_time
from .bus_trace import RECEIVED, SENT, Entry, Window

STOP_REGISTER = 25
"""ACQ-025: FC6 on register 25, 1 freezes the frame, 0 resumes; sent without waiting for its echo."""
STEPS = {(4, 0, 59): "状态基础段", (4, 400, 76): "状态光学段", (4, 1701, 54): "光度参数", (4, 2047, 11): "设备身份"}
SPECTRUM = range(1000, 1701)
TIME_REGISTERS = (32, 36)
OK = ("正常", "不等回显")
ECHO_BYTES = 8
STATUS_STEPS = ("状态基础段", "状态光学段")
"""After 恢复 the status reads confirm the resume; anything else for that slave is outside the transaction."""
"""An FC6 echo: the request itself, byte for byte."""
GATEWAY_CODES = (0x0A, 0x0B)
"""A gateway answering for a silent device (阶段一裁决 37): not the device's frame."""
REQUEST_FIELDS = ("slave", "step", "function", "address", "count", "value")


def crc16_modbus(data: bytes) -> int:
    """CRC-16/Modbus, as par_app.protocol computes it (the application layer may not import the protocol)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _request(frame: bytes) -> dict[str, Any]:
    """The request's slave, function, register, count or value, the step it is and the reply it waits for."""
    if len(frame) < 8:
        return {"slave": frame[0] if frame else None, "function": None, "step": "无法识别的请求", "expect": None}
    slave, function = frame[0], frame[1]
    address, word = struct.unpack(">HH", frame[2:6])
    found: dict[str, Any] = {"slave": slave, "function": function, "address": address}
    if function == 6:
        found["value"] = word
        if address == STOP_REGISTER:
            return found | {"step": "冻结" if word else "恢复", "expect": None}
        step = "对时" if address in TIME_REGISTERS else f"写寄存器 {address}"
        return found | {"step": step, "expect": 8}
    found["count"] = word
    if function in (3, 4):
        named = STEPS.get((function, address, word))
        if named is None:
            named = f"光谱 {address}:{word}" if function == 4 and address in SPECTRUM else f"读 {address}:{word}"
        return found | {"step": named, "expect": 5 + 2 * word}
    step = "对时" if function == 16 and address in TIME_REGISTERS else f"功能码 {function} {address}:{word}"
    return found | {"step": step, "expect": 8}


def _frames(data: bytes, unanswered: list[bytes]) -> tuple[list[dict[str, Any]], int]:
    """The CRC-correct RTU frames in `data` (any slave) and how many bytes none of them explains."""
    frames: list[dict[str, Any]] = []
    index = unparsed = 0
    while index < len(data):
        frame = _frame_at(data, index)
        if frame is None:
            unparsed += 1
            index += 1
            continue
        found: dict[str, Any] = {"slave": frame[0], "function": frame[1], "bytes": len(frame)}
        if frame[1] & 0x80:
            found["exception"] = frame[2]
        if frame in unanswered:
            found["late_echo"] = True
        frames.append(found)
        index += len(frame)
    return frames, unparsed


def _frame_at(data: bytes, index: int) -> bytes | None:
    """A CRC-correct RTU frame starting at `index`, or None."""
    if index + 5 > len(data):
        return None
    function = data[index + 1]
    if function & 0x80:
        length = 5
    elif function in (3, 4):
        length = 5 + data[index + 2]
    elif function in (6, 16):
        length = 8
    else:
        return None
    frame = bytes(data[index : index + length])
    return frame if len(frame) == length and _crc_right(frame) else None


def _crc_right(frame: bytes) -> bool:
    return crc16_modbus(frame[:-2]) == int.from_bytes(frame[-2:], "little")


def _target(data: bytes, request: dict[str, Any], unanswered: list[bytes]) -> bytes:
    """The bytes after the late echoes in front: where the reply to this request should be."""
    while data[:ECHO_BYTES] in unanswered and len(data) >= ECHO_BYTES:
        data = data[ECHO_BYTES:]
    return data


def _verdict(request: dict[str, Any], frames: list[dict[str, Any]], target: bytes, unanswered: list[bytes]) -> str:
    """As _rtu_exchange would judge it: the reply is exactly the expected frame, nothing more."""
    if request["expect"] is None:
        return "不等回显"
    if not target and not frames:
        return "无应答"
    if len(target) >= 5 and target[0] == request["slave"] and target[1] & 0x80 and _crc_right(target[:5]):
        return "异常应答"
    if len(target) < request["expect"]:
        return "应答不完整"
    reply, rest = target[: request["expect"]], target[request["expect"] :]
    if not _crc_right(reply):
        return "CRC 不符"
    if reply[0] != request["slave"] or reply[1] != request["function"]:
        return "从站或功能码不符"
    if request["function"] in (3, 4) and reply[2] != 2 * request["count"]:
        return "字节数不符"
    rest_is_echo = any(echo.startswith(rest) for echo in unanswered)  # a late echo straight after it (#132)
    return "正常" if not rest or rest_is_echo else "应答后有多余字节"


def _valid_frames(frames: list[dict[str, Any]], slave: object) -> int:
    """This slave's frames, as D-101 counts them: a gateway's 0x0A/0x0B answer is not the device's."""
    return sum(frame["slave"] == slave and frame.get("exception") not in GATEWAY_CODES for frame in frames)


def exchanges(window: Window) -> Iterator[dict[str, Any]]:
    """One record per write in `window`, with what came back before the next write."""
    entries = list(window.entries)
    unanswered: list[bytes] = []
    for index, entry in enumerate(entries):
        if entry.direction != SENT:
            continue
        replies = _replies(entries, index)
        data = b"".join(reply.data for reply in replies)
        request = _request(entry.data)
        frames, unparsed = _frames(data, unanswered)
        record: dict[str, Any] = {"at": format_beijing_time(window.wall(entry.at))}
        record.update((name, request[name]) for name in REQUEST_FIELDS if name in request)
        record |= {
            "sent_bytes": len(entry.data),
            "received_bytes": len(data),
            "first_byte_ms": _ms(replies[0].at - entry.at) if replies else None,
            "last_byte_ms": _ms(replies[-1].at - entry.at) if replies else None,
            "frames": frames,
            "valid_frames": _valid_frames(frames, request["slave"]),
            "unparsed_bytes": unparsed,
            "verdict": _verdict(request, frames, _target(data, request, unanswered), unanswered),
        }
        if request["expect"] is None:
            unanswered = [*unanswered[-1:], entry.data]
        yield record


def _replies(entries: list[Entry], index: int) -> list[Entry]:
    replies = []
    for entry in entries[index + 1 :]:
        if entry.direction != RECEIVED:
            break
        replies.append(entry)
    return replies


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def transactions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each 冻结 to that slave's next one: its slave, start, the first problem, and the first problem after 恢复.
    Kept per slave, so devices sharing the bus are never mixed up."""
    found: list[dict[str, Any]] = []
    open_by_slave: dict[object, dict[str, Any]] = {}
    for record in records:
        slave = record["slave"]
        if record["step"] == "冻结":
            opened: dict[str, Any] = {
                "slave": slave,
                "started_at": record["at"],
                "ended_at": record["at"],
                "first_problem": None,
                "resume_problem": None,
                "resumed": False,
            }
            found.append(opened)
            open_by_slave[slave] = opened
            continue
        current = open_by_slave.get(slave)
        if current is None:
            continue
        if current["resumed"] and record["step"] not in STATUS_STEPS:  # the resume was confirmed: it ended
            del open_by_slave[slave]
            continue
        current["ended_at"] = record["at"]
        if record["step"] == "恢复":
            current["resumed"] = True
            continue
        if record["verdict"] in OK:
            continue
        problem = {"at": record["at"], "step": record["step"], "verdict": record["verdict"]}
        if current["first_problem"] is None:
            current["first_problem"] = problem
        if current["resumed"] and current["resume_problem"] is None:
            current["resume_problem"] = problem
    return found
