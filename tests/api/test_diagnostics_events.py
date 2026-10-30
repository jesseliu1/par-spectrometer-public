"""Run events in the diagnostics bundle (issue #136 step 4): events/events.jsonl, events/events.csv and
events/integrity.json.

The guarantee (owner 2026-10-28): a bundle exported successfully holds every notice the pages showed at export time;
when the log lost records the bundle says so. Checked: shown notices found in the file, a notice the file lacks
written from memory and the bundle marked incomplete, the cut, the same reduced records in JSONL and CSV, formula
cells, redaction, and the raw event files kept out of logs/.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.application.diagnostics_events import read_events
from par_app.application.redaction import DATA_DIR_MARK
from par_app.application.run_events import RunEventLog

pytestmark = pytest.mark.unit
EXPORT = "/api/v0/support/diagnostics-bundle"


def _device(name: str, slave_id: int, message: str, **changes: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "key": name,
        "name": name,
        "slave_id": slave_id,
        "enabled": True,
        "level": "warning",
        "message": message,
        "failures": 1,
        "online": False,
        "excluded": False,
        **changes,
    }


def _export(client: TestClient) -> tuple[dict[str, Any], zipfile.ZipFile]:
    response = client.post(EXPORT)
    assert response.status_code == 201, response.text
    body = response.json()
    return body, zipfile.ZipFile(Path(body["path"]))


def _events(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    return [json.loads(line) for line in archive.read("events/events.jsonl").decode("utf-8").splitlines()]


def _csv(archive: zipfile.ZipFile) -> list[list[str]]:
    return list(csv.reader(io.StringIO(archive.read("events/events.csv").decode("utf-8-sig"))))


def test_every_shown_notice_is_in_the_bundle_and_the_bundle_says_it_is_complete(
    client: TestClient, context: ServiceContext
) -> None:
    context.paths.ensure()
    cache = context.acquisition.cache
    cache.set_bus("ok", "总线已连接")
    cache.set_device(_device("North", 3, "连续第 1 次尝试失败：设备通信超时"))
    snapshot = cache.snapshot()
    body, archive = _export(client)
    with archive:
        events = _events(archive)
        integrity = json.loads(archive.read("events/integrity.json"))
        rows = _csv(archive)
        names = archive.namelist()
    ids = {event["event_id"] for event in events}
    assert snapshot["bus"]["notice"]["event_id"] in ids and snapshot["devices"][0]["notice"]["event_id"] in ids
    assert integrity["complete"] is True and integrity["reasons"] == [] and integrity["from_memory"] == 0
    assert {item["where"] for item in integrity["shown"]} == {"总线", "设备 North"}
    assert all(item["in_file"] for item in integrity["shown"])
    assert events[-1]["event_id"] == integrity["cut"]["event_id"] and events[-1]["kind"] == "export"
    assert [row[0] for row in rows[1:]] == [event["event_id"] for event in events]  # the same records, same order
    assert not [name for name in names if name.startswith("logs/events")]  # only the reduced copy under events/
    assert not [item for item in body["problems"] if "运行事件" in item]


def test_a_notice_the_file_lacks_comes_from_memory_and_the_bundle_says_so(
    client: TestClient, context: ServiceContext
) -> None:
    context.paths.ensure()
    log = context.acquisition.run_events

    def broken(path: Path) -> Any:  # noqa: ANN401 (an opener)
        raise PermissionError("disk is read-only")

    log._open = broken  # noqa: SLF001 (a disk that refuses every write)
    cache = context.acquisition.cache
    cache.set_device(_device("South", 4, "连续第 2 次尝试失败：设备通信超时"))
    notice = cache.snapshot()["devices"][0]["notice"]
    body, archive = _export(client)
    with archive:
        events = _events(archive)
        integrity = json.loads(archive.read("events/integrity.json"))
    recovered = next(event for event in events if event["event_id"] == notice["event_id"])
    assert recovered["source"] == "memory" and recovered["message"] == "连续第 2 次尝试失败：设备通信超时"
    assert recovered["kind"] == "device"  # the event's kind, not where it is shown
    assert (recovered["device_name"], recovered["slave_id"]) == ("South", 4)
    assert recovered["session"] == notice["event_id"].rsplit("-", 1)[0]  # in its place among its run's events
    assert recovered["sequence"] == int(notice["event_id"].rsplit("-", 1)[1])
    sequences = [event["sequence"] for event in events if event["session"] == recovered["session"]]
    assert sequences == sorted(sequences)
    assert integrity["complete"] is False and integrity["health"]["failed"] >= 1
    assert any("写盘失败" in reason for reason in integrity["reasons"])
    assert any(item.startswith("运行事件记录不完整") for item in body["problems"])
    assert "运行事件记录不完整" in body["text"]  # the page shows it with the export result


def test_formula_cells_are_quoted_and_local_folders_are_redacted(client: TestClient, context: ServiceContext) -> None:
    context.paths.ensure()
    data_dir = context.paths.data_dir
    cache = context.acquisition.cache
    cache.set_device(_device("=HYPERLINK(1)", 1, "+连续失败", last_error=f"无法打开 {data_dir}/data/devices/x.sqlite3"))
    _, archive = _export(client)
    with archive:
        rows = _csv(archive)
        text = archive.read("events/events.jsonl").decode("utf-8")
    row = next(row for row in rows if row[8] == "'+连续失败")
    assert row[6] == "'=HYPERLINK(1)"
    assert str(data_dir) not in text and DATA_DIR_MARK in text


def test_this_runs_events_after_the_cut_stay_out_and_damaged_lines_are_counted(tmp_path: Path) -> None:
    from datetime import datetime

    from par_app.domain.clock import BEIJING_TZ, FakeClock

    log = RunEventLog(tmp_path, FakeClock(datetime(2026, 10, 28, 16, 0, tzinfo=BEIJING_TZ)), session="cafe0001")
    log.record("bus", "ok", "总线已连接")
    cut = log.record("export", "info", "截点")
    log.record("bus", "error", "之后的记录")
    assert log.flush(5.0)
    log.close()
    older = {"event_id": "beef0002-000009", "session": "beef0002", "sequence": 9, "message": "上一次运行"}
    damaged = {**older, "event_id": ["beef0002", 10], "sequence": 10}  # valid JSON, a number that is not one
    lines = [json.dumps(older), "{半行", json.dumps(damaged), json.dumps({**older, "session": None})]
    (tmp_path / "events.1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    found = read_events(tmp_path, cut)
    assert [record["message"] for record in found.records] == ["上一次运行", "总线已连接", "截点"]
    assert found.unreadable_lines == 3 and [item["name"] for item in found.files] == ["events.1.jsonl", "events.jsonl"]


def test_carried_copies_are_read_once_and_absurd_nesting_is_an_unreadable_line(tmp_path: Path) -> None:
    """review of PR #144: a deeply nested line must not stop the export; a notice carried into the next file
    on rotation appears once."""
    from datetime import datetime

    from par_app.domain.clock import BEIJING_TZ, FakeClock

    log = RunEventLog(tmp_path, FakeClock(datetime(2026, 10, 28, 16, 0, tzinfo=BEIJING_TZ)), session="cafe0003")
    first = log.record("bus", "ok", "总线已连接")
    cut = log.record("export", "info", "截点")
    assert log.flush(5.0)
    log.close()
    current = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    carried = json.dumps({**json.loads(current.splitlines()[0]), "carried_over": True}, ensure_ascii=False)
    (tmp_path / "events.1.jsonl").write_text(current.splitlines()[0] + "\n" + "[" * 100_000 + "\n", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text(carried + "\n" + current.splitlines()[1] + "\n", encoding="utf-8")
    found = read_events(tmp_path, cut)
    assert [record["event_id"] for record in found.records] == [first.event_id, cut.event_id]
    assert found.unreadable_lines == 1


def test_a_notice_shown_when_the_export_starts_is_before_the_cut(client: TestClient, context: ServiceContext) -> None:
    """review of PR #144: the snapshot is taken before the cut, so a notice it shows is never one the cut
    leaves out and then written back from memory."""
    context.paths.ensure()
    cache = context.acquisition.cache
    cache.set_bus("ok", "总线已连接")
    log = context.acquisition.run_events
    record = log.record

    def change_then_record(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if args and args[0] == "export":
            cache.set_bus("error", "总线已断开")  # changes after the snapshot, before the cut
        return record(*args, **kwargs)

    log.record = change_then_record  # type: ignore[method-assign]
    _, archive = _export(client)
    with archive:
        events = _events(archive)
        integrity = json.loads(archive.read("events/integrity.json"))
    assert events[-1]["kind"] == "export" and integrity["from_memory"] == 0 and integrity["complete"] is True
    assert [item["in_file"] for item in integrity["shown"] if item["where"] == "总线"] == [True]
    assert not [event for event in events if event.get("source") == "memory"]
