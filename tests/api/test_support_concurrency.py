"""The support reads while the coordinator keeps writing (D-226; PR #63 review major 4, re-review item 3).

1. test_writer_commits_while_a_read_snapshot_is_open: synchronised with events. The bundle export is held inside its
   first chunk read with the SELECT open (read snapshot open); the writer (ParDatabase's own connection, busy
   timeout 10 s) commits a row there and runs a PASSIVE checkpoint: the commit succeeds, the checkpoint reports
   busy=0 but cannot copy past the reader (checkpointed < log). The export is then held between two chunks: a
   TRUNCATE checkpoint there returns (0, 0, 0), which proves no read snapshot is held across chunks (each chunk is a
   fresh, fully fetched SELECT). After the export another TRUNCATE returns (0, 0, 0) and every committed row is there.
2. test_reads_and_exports_while_the_coordinator_writes: load. A writer thread commits rows continuously (with
   checkpoints) while the log is read and the bundle exported; the writer's progress between the first read and the
   last answer is measured (> 0), it never meets an exception, and every row it committed is in the database.

What mode=ro does not promise, and these tests do not claim: a reader still holds a read snapshot while its SELECT
runs, so a checkpoint cannot copy frames past it (PASSIVE skips them, TRUNCATE/RESTART wait up to the busy timeout
and then report busy without failing); the reader's -wal/-shm files may be touched; and the busy timeout does not
bound a SELECT's duration (each chunk SELECT is short instead: FETCH_ROWS rows by rowid).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.application import diagnostics_content
from par_app.database import ParDatabase
from tests.api import support_data as data

pytestmark = pytest.mark.unit
LOG = "/api/v0/support/maintenance-log"
EXPORT = "/api/v0/support/diagnostics-bundle"
WAIT_SECONDS = 20
CHECKPOINT_TIMEOUT = 2.0


def _checkpoint(path: Path, mode: str) -> tuple[int, int, int]:
    con = sqlite3.connect(path, timeout=CHECKPOINT_TIMEOUT)
    try:
        busy, log, done = con.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        return int(busy), int(log), int(done)
    finally:
        con.close()


def _count(path: Path, sql: str) -> int:
    con = sqlite3.connect(path)
    try:
        return int(con.execute(sql).fetchone()[0])
    finally:
        con.close()


def _twenty_calibration_writes(data_dir: Path) -> ParDatabase:
    data.write_config(data_dir, ["North"])
    north = data.device_database(data_dir, "North")
    for minute in range(20):
        data.calibration_write(north, f"2026-10-19T09:{minute:02d}:00.000")
    assert _checkpoint(north.path, "TRUNCATE") == (0, 0, 0)
    return north


def test_writer_commits_while_a_read_snapshot_is_open(
    client: TestClient, context: ServiceContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    north = _twenty_calibration_writes(context.paths.data_dir)
    monkeypatch.setattr(diagnostics_content, "FETCH_ROWS", 5)

    snapshot_open, committed, between, checkpointed = (threading.Event() for _ in range(4))
    results: dict[str, Any] = {}
    errors: list[BaseException] = []
    original = diagnostics_content.fetch_chunk
    calls: list[int] = []

    def held(con: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        calls.append(1)
        if len(calls) == 1:  # first chunk of calibration_audit: hold the SELECT open
            cursor = con.execute(sql, parameters)
            head = cursor.fetchmany(1)
            snapshot_open.set()
            assert committed.wait(WAIT_SECONDS)
            rest = cursor.fetchall()
            cursor.close()
            return [tuple(row) for row in head + rest]
        rows = original(con, sql, parameters)
        if len(calls) == 2:  # between two chunks: nothing open
            between.set()
            assert checkpointed.wait(WAIT_SECONDS)
        return rows

    def writer() -> None:
        try:
            database = ParDatabase(north.path)
            assert snapshot_open.wait(WAIT_SECONDS)
            results["before"] = _count(north.path, "SELECT COUNT(*) FROM diagnostics")
            database.diagnostic("ERROR", "communication", "通信异常", during="snapshot")
            results["passive"] = _checkpoint(north.path, "PASSIVE")
            results["after"] = _count(north.path, "SELECT COUNT(*) FROM diagnostics")
            committed.set()
            assert between.wait(WAIT_SECONDS)
            results["truncate_between_chunks"] = _checkpoint(north.path, "TRUNCATE")
            checkpointed.set()
        except BaseException as error:  # noqa: BLE001 (reported by the test)
            errors.append(error)
            committed.set()
            checkpointed.set()

    monkeypatch.setattr(diagnostics_content, "fetch_chunk", held)
    thread = threading.Thread(target=writer)
    thread.start()
    response = client.post(EXPORT)
    thread.join(timeout=WAIT_SECONDS)
    assert not thread.is_alive() and errors == [], errors
    assert response.status_code == 201, response.text
    assert len(calls) >= 4  # 20 rows in chunks of 5
    assert results["after"] == results["before"] + 1  # committed while the reader's snapshot was open
    busy, log, done = results["passive"]
    assert busy == 0 and log > 0 and done < log  # the open snapshot keeps the checkpoint from passing it
    assert results["truncate_between_chunks"] == (0, 0, 0)  # no snapshot held between chunks
    assert _checkpoint(north.path, "TRUNCATE") == (0, 0, 0)  # and none after the export
    assert _count(north.path, "SELECT COUNT(*) FROM diagnostics WHERE details_json LIKE '%snapshot%'") == 1
    assert _count(north.path, "SELECT COUNT(*) FROM calibration_audit") == 20


def _writer(path: Path, stop: threading.Event, started: threading.Event, done: list[int], errors: list[Any]) -> None:
    database = ParDatabase(path)
    checkpoints: list[tuple[int, int, int]] = []
    try:
        index = 0
        while not stop.is_set():
            database.diagnostic("ERROR", "communication", "通信异常", index=index)
            database.save_time_sync(True, 1760837400000 + index, "设备对时完成")
            done.append(index)
            started.set()
            if index % 25 == 0:
                checkpoints.append(_checkpoint(path, "PASSIVE"))
            index += 1
        checkpoints.append(_checkpoint(path, "TRUNCATE"))
        assert all(busy == 0 for busy, _, _ in checkpoints[:-1]), checkpoints
        assert checkpoints[-1] == (0, 0, 0), checkpoints[-1]
    except BaseException as error:  # noqa: BLE001 (the test reports anything the writer met)
        errors.append(error)


def test_reads_and_exports_while_the_coordinator_writes(client: TestClient, context: ServiceContext) -> None:
    data_dir = context.paths.data_dir
    data.write_config(data_dir, ["North"])
    north = data.device_database(data_dir, "North")
    data.calibration_write(north, "2026-10-19T09:01:00.000")
    data.comm_write(north, "2026-10-19T09:02:00.000")
    stop, started, done, errors = threading.Event(), threading.Event(), [], []
    writer = threading.Thread(target=_writer, args=(north.path, stop, started, done, errors))
    writer.start()
    try:
        assert started.wait(WAIT_SECONDS)
        at_start = len(done)
        answers = []
        for round_ in range(6):
            answers.append(client.get(LOG, params={"time_sync": "true", "limit": 1000}).status_code)
            answers.append(client.get(LOG, params={"device": "p1"}).status_code)
            if round_ % 2 == 0:
                answers.append(client.post(EXPORT).status_code)
        progress = len(done) - at_start
    finally:
        stop.set()
        writer.join(timeout=60)
    assert not writer.is_alive()
    assert errors == [], errors
    assert answers and set(answers) <= {200, 201}, answers
    assert progress > 0, "the writer must commit between the first read and the last answer"
    con = sqlite3.connect(north.path)
    try:
        written = con.execute("SELECT COUNT(*) FROM diagnostics WHERE category='communication'").fetchone()[0]
        synced = con.execute("SELECT COUNT(*) FROM time_sync_events").fetchone()[0]
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()
    assert written == len(done) and synced == len(done)
