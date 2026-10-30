"""The bus trace in the diagnostics bundle (issue #136 steps 2 and 3): bus_trace/.

A device failure keeps the trace under its record number, so the same number finds the notice in events/ and what
was on the line in bus_trace/<number>.jsonl; the whole ring at export is bus_trace/current.jsonl; index.json lists
them. Built from memory on the export's thread; no payload bytes in the bundle.
"""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.application.bus_trace import RECEIVED, SENT, Entry
from par_app.models import ConnectionConfig
from par_app.protocol import ParModbusClient

pytestmark = pytest.mark.unit
EXPORT = "/api/v0/support/diagnostics-bundle"


def _lines(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in archive.read(name).decode("utf-8").splitlines()]


def test_a_failure_window_and_the_current_ring_go_into_the_bundle(client: TestClient, context: ServiceContext) -> None:
    context.paths.ensure()
    acquisition = context.acquisition
    frames = ParModbusClient(ConnectionConfig(slave_id=4))
    request = frames._rtu_frame(4, struct.pack(">HH", 1000, 3))  # noqa: SLF001
    reply = frames._rtu_frame(4, bytes([6]) + struct.pack(">HHH", 0x1357, 0x2468, 0x0ACE))  # noqa: SLF001
    acquisition.bus_trace.add(Entry(0.0, SENT, request))
    acquisition.bus_trace.add(Entry(0.2, RECEIVED, reply))
    acquisition.cache.set_device(
        {
            "key": "p4",
            "name": "South",
            "slave_id": 4,
            "enabled": True,
            "level": "warning",
            "message": "连续第 1 次尝试失败：设备通信超时",
        }
    )
    notice = acquisition.cache.snapshot()["devices"][0]["notice"]
    response = client.post(EXPORT)
    assert response.status_code == 201, response.text
    with zipfile.ZipFile(Path(response.json()["path"])) as archive:
        names = archive.namelist()
        index = json.loads(archive.read("bus_trace/index.json"))
        kept = _lines(archive, f"bus_trace/{notice['event_id']}.jsonl")
        current = _lines(archive, "bus_trace/current.jsonl")
        events = archive.read("events/events.jsonl").decode("utf-8")
        text = "".join(archive.read(name).decode("utf-8") for name in names if name.startswith("bus_trace/"))
    assert notice["event_id"] in events  # the same number in events/ and in bus_trace/
    assert [item["file"] for item in index["windows"]] == [f"{notice['event_id']}.jsonl", "current.jsonl"]
    assert kept[0] == {**kept[0], "type": "window", "kind": "device", "message": "连续第 1 次尝试失败：设备通信超时"}
    exchange = next(line for line in kept if line["type"] == "exchange")
    assert (exchange["slave"], exchange["step"], exchange["verdict"]) == (4, "光谱 1000:3", "正常")
    assert exchange["received_bytes"] == len(reply) and exchange["first_byte_ms"] == 200.0
    assert current[0]["kind"] == "export" and current[0]["entries"] == 2
    for value in (0x1357, 0x2468, 0x0ACE):  # spectrum words never leave memory
        assert str(value) not in text and f"{value:04X}" not in text.upper()


def test_an_empty_trace_still_says_what_it_holds(client: TestClient, context: ServiceContext) -> None:
    context.paths.ensure()
    response = client.post(EXPORT)
    with zipfile.ZipFile(Path(response.json()["path"])) as archive:
        index = json.loads(archive.read("bus_trace/index.json"))
    assert index["installed"] is False and index["windows"][0]["entries"] == 0
    assert not [item for item in response.json()["problems"] if "串口收发记录" in item]


def test_a_local_folder_in_the_kept_message_is_redacted(client: TestClient, context: ServiceContext) -> None:
    context.paths.ensure()
    acquisition = context.acquisition
    acquisition.bus_trace.add(Entry(0.0, SENT, b"\x04\x04\x00\x00\x00\x3b\x00\x00"))
    folder = context.paths.data_dir / "data" / "devices" / "South.sqlite3"
    acquisition.cache.set_device(
        {
            "key": "p4",
            "name": "South",
            "slave_id": 4,
            "enabled": True,
            "level": "error",
            "message": f"无法打开 {folder}",
        }
    )
    notice = acquisition.cache.snapshot()["devices"][0]["notice"]
    response = client.post(EXPORT)
    with zipfile.ZipFile(Path(response.json()["path"])) as archive:
        text = archive.read(f"bus_trace/{notice['event_id']}.jsonl").decode("utf-8")
        index = archive.read("bus_trace/index.json").decode("utf-8")
    assert str(context.paths.data_dir) not in text + index and "<DATA_DIR>" in text
