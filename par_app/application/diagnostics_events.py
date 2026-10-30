"""The run events in the diagnostics bundle (issue #136 step 4): events/events.jsonl, events/events.csv and
events/integrity.json.

The guarantee (owner 2026-10-28): a bundle exported successfully holds every notice the pages showed at export time;
when the log lost or cut records, the bundle says so. So the export first takes the state cache's snapshot, then
records its own event, whose number is the cut (later events of this run are left out, earlier runs go in whole):
every notice in the snapshot was numbered before it, so none is after the cut. It waits a bounded time for the
writer; every notice shown is looked up among the events read back, and one the file lacks (dropped, failed, cut) is
written into the bundle from the snapshot, which holds its number, time and text.

Both event files come from the same reduced records: each line is parsed, cut to the known fields (the details
through the Redactor's key and text rules) and then written as JSON and as a CSV row, so the two never differ. CSV
cells that a spreadsheet would read as a formula get a leading apostrophe.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from . import bundle_schema as schema
from . import diagnostics_content as content
from .acquisition import AcquisitionService
from .run_events import EVENTS_FILE, FILE_BACKUPS, RunEvent

FOLDER = "events"
FLUSH_SECONDS = 2.0
"""How long the export waits for the writer to empty its queue before reading the files back."""
CUT_TEXT = "导出诊断包：此条之后的记录不在本包中"
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")
CSV_COLUMNS = ("记录号", "序号", "运行会话", "时间", "类别", "级别", "设备", "地址", "消息", "详情")
INCOMPLETE_PROBLEM = "运行事件记录不完整：{reasons}（见包内 events/integrity.json）"
EVENT = schema.Object(
    {
        "schema": schema.INT,
        "event_id": schema.STR,
        "session": schema.STR,
        "sequence": schema.INT,
        "occurred_at": schema.STR,
        "kind": schema.STR,
        "level": schema.STR,
        "message": schema.STR,
        "device_key": schema.STR,
        "device_name": schema.STR,
        "slave_id": schema.INT,
        "details": schema.Opaque(),
        "source": schema.STR,
    }
)
"""One event as it goes into the bundle; `source` is "memory" for a shown notice the file lacked."""


@dataclass
class EventFiles:
    records: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    unreadable_lines: int = 0
    errors: list[str] = field(default_factory=list)


def shown_notices(snapshot: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    """Every notice a page shows from this state cache snapshot, with where it is shown and its text."""
    bus = snapshot.get("bus") or {}
    yield {"where": "总线", "kind": "bus", "notice": bus.get("notice"), "message": bus.get("message")}
    halt = snapshot.get("halt")
    if halt is not None:
        yield {
            "where": "锁停",
            "kind": "halt",
            "notice": halt.get("notice"),
            "message": halt.get("message"),
            "device_name": halt.get("name"),
            "slave_id": halt.get("slave_id"),
        }
    if snapshot.get("error") is not None:
        yield {
            "where": "开始采集",
            "kind": "takeover",
            "notice": snapshot.get("error_notice"),
            "message": snapshot.get("error"),
        }
    for device in snapshot.get("devices") or []:
        yield {
            "where": f"设备 {device.get('name')}",
            "kind": "device",
            "notice": device.get("notice"),
            "message": device.get("message"),
            "device_name": device.get("name"),
            "slave_id": device.get("slave_id"),
        }


def read_events(directory: Any, cut: RunEvent) -> EventFiles:  # noqa: ANN401 (a Path)
    """The event files, oldest first, each at most LOG_TAIL_BYTES from its end; this run's events after `cut` left
    out. A line that is not an event (cut in half, damaged) is counted, not guessed."""
    found = EventFiles()
    seen: set[object] = set()
    names = [f"events.{index}.jsonl" for index in range(FILE_BACKUPS, 0, -1)] + [EVENTS_FILE]
    for name in names:
        path = directory / name
        if not path.is_file():
            continue
        try:
            text, cut_file = content.log_tail(path)
            size = path.stat().st_size
        except OSError as error:  # one unreadable file is named; the rest still goes in
            found.errors.append(f"{name}：{type(error).__name__}: {error}")
            continue
        found.files.append({"name": name, "bytes": size, "cut": cut_file})
        for line in text.splitlines():
            try:
                record = json.loads(line)
            except (ValueError, RecursionError):  # damaged or absurdly nested: counted, the export goes on
                found.unreadable_lines += 1
                continue
            if not _is_event(record):
                found.unreadable_lines += 1
                continue
            if record.get("session") == cut.session and record["sequence"] > cut.sequence:
                continue
            if record.get("event_id") in seen:  # a notice still shown, carried into the next file on rotation
                continue
            seen.add(record.get("event_id"))
            found.records.append(record)
    return found


def _is_event(record: object) -> bool:
    """A line whose number fields are what an event has; any other is counted as unreadable (review, PR #144)."""
    if not isinstance(record, dict):
        return False
    sequence = record.get("sequence")
    numbered = isinstance(sequence, int) and not isinstance(sequence, bool)
    return numbered and isinstance(record.get("event_id"), str) and isinstance(record.get("session"), str)


def _csv_value(value: object) -> object:
    if isinstance(value, str) and value.startswith(FORMULA_STARTS):
        return "'" + value
    return value


CSV_FIELDS = ("event_id", "sequence", "session", "occurred_at", "kind", "level", "device_name", "slave_id", "message")


def write_events(out: content.BundleWriter, acquisition: AcquisitionService, problems: list[str]) -> None:
    log = acquisition.run_events
    snapshot = acquisition.cache.snapshot()  # before the cut, so every notice it shows is numbered before it
    cut = log.record("export", "info", CUT_TEXT, None)
    flushed = log.flush(FLUSH_SECONDS)
    health = log.health()
    found = read_events(log.directory, cut)
    shown, missing = check_shown(snapshot, {record.get("event_id") for record in found.records})
    reduced = []
    for record in in_order([*found.records, *missing]):
        try:
            reduced.append(schema.allow(record, EVENT, out.redact.structure))
        except RecursionError:
            found.unreadable_lines += 1
    out.raw(f"{FOLDER}/events.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in reduced))
    out.csv(
        f"{FOLDER}/events.csv",
        CSV_COLUMNS,
        (
            [_csv_value(item.get(name)) for name in CSV_FIELDS]
            + [_csv_value(json.dumps(item.get("details") or {}, ensure_ascii=False))]
            for item in reduced
        ),
    )
    reasons = incomplete(flushed, health, found, len(missing))
    cut_fields = {
        "event_id": cut.event_id,
        "session": cut.session,
        "sequence": cut.sequence,
        "occurred_at": cut.occurred_at,
    }
    integrity = {
        "complete": not reasons,
        "reasons": reasons,
        "cut": cut_fields,
        "flushed": flushed,
        "health": health,
        "files": found.files,
        "records": len(reduced),
        "unreadable_lines": found.unreadable_lines,
        "shown": shown,
        "from_memory": len(missing),
    }
    out.json(f"{FOLDER}/integrity.json", integrity, INTEGRITY)
    if reasons:
        problems.append(INCOMPLETE_PROBLEM.format(reasons="；".join(reasons)))


def in_order(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs in the order they first appear in the files, each by its sequence: a notice written from memory takes
    its place among the events of its run instead of trailing them (review, PR #144)."""
    rank: dict[object, int] = {}
    for record in records:
        rank.setdefault(record.get("session"), len(rank))
    return sorted(records, key=lambda record: (rank[record.get("session")], _sequence(record)))


def _sequence(record: Mapping[str, Any]) -> int:
    sequence = record.get("sequence")
    return sequence if isinstance(sequence, int) else 0


def check_shown(snapshot: Mapping[str, Any], known: set[object]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Each shown notice and whether the file holds it; the ones it lacks as records made from the snapshot."""
    shown, missing = [], []
    for item in shown_notices(snapshot):
        notice = item["notice"]
        if notice is None:
            continue
        present = notice.get("event_id") in known
        shown.append({"where": item["where"], "event_id": notice.get("event_id"), "in_file": present})
        if not present:
            session, _, sequence = str(notice.get("event_id")).rpartition("-")
            missing.append(
                {
                    "session": session or None,
                    "sequence": int(sequence) if sequence.isdigit() else None,
                    "event_id": notice.get("event_id"),
                    "occurred_at": notice.get("occurred_at"),
                    "message": item["message"],
                    "device_name": item.get("device_name"),
                    "slave_id": item.get("slave_id"),
                    "kind": item["kind"],
                    "source": "memory",
                }
            )
    return shown, missing


def incomplete(flushed: bool, health: Mapping[str, Any], found: EventFiles, missing: int) -> list[str]:
    """Why the bundle's events are not the whole record; empty when they are."""
    reasons = []
    if not flushed:
        reasons.append(f"导出时仍有记录未写完（等待 {FLUSH_SECONDS:g} 秒）")
    if health["dropped"]:
        reasons.append(f"{health['dropped']} 条因写盘排满未写入")
    if health["failed"]:
        reasons.append(f"{health['failed']} 条写盘失败（{health['last_error']}）")
    if any(item["cut"] for item in found.files):
        reasons.append(f"日志文件超过 {content.LOG_TAIL_BYTES} 字节，只收录最后部分")
    reasons.extend(f"读不出 {item}" for item in found.errors)
    if found.unreadable_lines:
        reasons.append(f"{found.unreadable_lines} 行无法解析")
    if missing:
        reasons.append(f"{missing} 条当前提示不在文件中，已从内存补上")
    return reasons


INTEGRITY = schema.Object(
    {
        "complete": schema.BOOL,
        "reasons": schema.ListOf(schema.STR),
        "cut": schema.Object(
            {"event_id": schema.STR, "session": schema.STR, "sequence": schema.INT, "occurred_at": schema.STR}
        ),
        "flushed": schema.BOOL,
        "health": schema.Object(
            {
                "session": schema.STR,
                "written": schema.INT,
                "last_written_sequence": schema.INT,
                "dropped": schema.INT,
                "failed": schema.INT,
                "first_error": schema.STR,
                "last_error": schema.STR,
            }
        ),
        "files": schema.ListOf(schema.Object({"name": schema.STR, "bytes": schema.INT, "cut": schema.BOOL})),
        "records": schema.INT,
        "unreadable_lines": schema.INT,
        "shown": schema.ListOf(schema.Object({"where": schema.STR, "event_id": schema.STR, "in_file": schema.BOOL})),
        "from_memory": schema.INT,
    }
)
