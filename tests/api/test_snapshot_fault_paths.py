"""Fault paths of snapshot import and listing, from the review of PR #45 (B-1, M-1, M-3).

B-1: the read mode is decided once; whatever V1.0.3 does right after (exiting, writing), no file may ever appear
beside the source database, which is why only a source at rest is opened through SQLite at all.
M-1: an unreadable or corrupt snapshot description is an explicit 503 naming the file, never an empty list, an
unconfigured device or a 404 (R-1-5).
M-3: a failure inside the online backup cannot be attributed to the source or the copy, so it names neither
(ruling 47).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import error_of, import_snapshot, record, v1_database
from tests.api.test_snapshots import _crashed_wal_database

pytestmark = pytest.mark.unit
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")


def test_v103_closing_right_after_the_mode_check_adds_no_file_beside_the_source(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B-1: the mode is decided once. If V1.0.3's last connection exits right after (checkpointing and
    deleting -wal/-shm), the import must still never open the source through SQLite without immutable=1, which
    would recreate -wal/-shm beside it. The whole import is watched: every sqlite3.connect is recorded, and only
    an sqlite3 connection on the source could create files there."""
    import par_app.application.snapshots as snapshots

    source = v1_database(tmp_path / "v1" / "live.sqlite3", [record()])
    writer = sqlite3.connect(source, check_same_thread=False)  # the hook below runs in the handler's thread
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T13:00:00.000', 0, 1.0)"
        )
        writer.commit()
        assert sorted(os.listdir(source.parent)) == ["live.sqlite3", "live.sqlite3-shm", "live.sqlite3-wal"]

        connected: list[str] = []
        real_connect: Callable[..., sqlite3.Connection] = sqlite3.connect

        def spy(database: str | Path, *args: object, **kwargs: object) -> sqlite3.Connection:
            connected.append(str(database))
            return real_connect(database, *args, **kwargs)

        real_read_mode = snapshots.read_mode

        def read_mode_then_v1_exits(path: Path) -> snapshots.ReadMode:
            mode = real_read_mode(path)
            writer.close()  # the checkpoint on close removes -wal and -shm beside the source
            return mode

        monkeypatch.setattr(sqlite3, "connect", spy)
        monkeypatch.setattr(snapshots, "read_mode", read_mode_then_v1_exits)
        response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    finally:
        writer.close()

    assert response.status_code == 201, response.text
    assert response.json()["snapshot"]["record_count"] == 2
    assert os.listdir(source.parent) == ["live.sqlite3"]  # nothing recreated beside the source
    assert not [call for call in connected if str(source.parent) in call], connected


def _in_use_files(folder: Path) -> Path:
    """A byte copy of a live V1.0.3 database's three files (db, -wal, -shm): what read_mode calls IN_USE."""
    live = v1_database(folder.parent / f"{folder.name}-live" / "par.sqlite3", [record()])
    writer = sqlite3.connect(live)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T13:00:00.000', 0, 1.0)"
        )
        writer.commit()
        folder.mkdir(parents=True)
        for suffix in ("", "-wal", "-shm"):
            (folder / f"par.sqlite3{suffix}").write_bytes(live.with_name(live.name + suffix).read_bytes())
    finally:
        writer.close()
    return folder / "par.sqlite3"


@POSIX_ONLY
def test_in_use_files_in_a_read_only_folder_are_imported(client: TestClient, tmp_path: Path) -> None:
    """Review B-1: db + -wal + -shm on a read-only share (e.g. copied from a machine where V1.0.3 runs): the
    import reads a staged byte copy, so it works without write access and adds nothing beside the source."""
    source = _in_use_files(tmp_path / "v1")
    folder = source.parent
    names = sorted(os.listdir(folder))
    for path in folder.iterdir():
        path.chmod(0o444)
    folder.chmod(0o555)
    try:
        snapshot = import_snapshot(client, source)
    finally:
        folder.chmod(0o755)
        for path in folder.iterdir():
            path.chmod(0o644)
    assert snapshot["record_count"] == 2  # the record still in the -wal is part of the copy
    assert sorted(os.listdir(folder)) == names


def test_live_wal_changed_while_it_is_copied_is_refused(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B-1: V1.0.3 wrote while the live database's files were byte-copied: the copy may be torn, so it is
    discarded (busy, retry)."""
    import par_app.application.snapshots as snapshots

    source = v1_database(tmp_path / "v1" / "live.sqlite3", [record()])
    writer = sqlite3.connect(source, check_same_thread=False)  # the hook below runs in the handler's thread
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T13:00:00.000', 0, 1.0)"
        )
        writer.commit()
        real_stage = snapshots._stage

        def stage_then_v1_writes(files: list[Path], folder: Path) -> Path:
            staged = real_stage(files, folder)
            writer.execute(
                "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T14:00:00.000', 1, 1.0)"
            )
            writer.commit()
            return staged

        monkeypatch.setattr(snapshots, "_stage", stage_then_v1_writes)
        response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    finally:
        writer.close()

    assert response.status_code == 409
    assert error_of(response)["code"] == "busy"
    alpha = tmp_path / "alpha" / "data"
    assert os.listdir(alpha / "imported") == []
    assert not (alpha / "staging").exists() or os.listdir(alpha / "staging") == []


@POSIX_ONLY
def test_a_backup_write_failure_carries_no_path(client: TestClient, tmp_path: Path) -> None:
    """Review M-3: a failure inside the online backup (e.g. the copy's disk full) can be reading the source or
    writing the copy; the 503 names neither (ruling 47: no path when the failing file is unknown)."""
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    partial = tmp_path / "alpha" / "data" / "imported" / "par-20261018-093000.sqlite.partial"
    partial.parent.mkdir(parents=True)
    partial.touch(mode=0o444)  # the backup's first write fails: "attempt to write a readonly database"

    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})

    assert response.status_code == 503
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("database_unavailable", True)
    assert error["message"] == "数据库不可访问"
    assert str(source) not in error["message"] and str(source.resolve()) not in error["message"]
    assert "readonly database" in (error["detail"] or "")
    assert os.listdir(partial.parent) == []  # the unfinished copy is removed


@POSIX_ONLY
def test_a_backup_write_failure_on_a_staged_copy_carries_no_path(client: TestClient, tmp_path: Path) -> None:
    """Review M-3: the staged (crash leftover) path must not blame the source for a copy-write failure either."""
    source = _crashed_wal_database(tmp_path / "v1")
    partial = tmp_path / "alpha" / "data" / "imported" / "par-20261018-093000.sqlite.partial"
    partial.parent.mkdir(parents=True)
    partial.touch(mode=0o444)

    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})

    assert response.status_code == 503
    error = error_of(response)
    assert error["message"] == "数据库不可访问"
    assert str(source) not in error["message"] and str(source.resolve()) not in error["message"]
    alpha = tmp_path / "alpha" / "data"
    assert os.listdir(alpha / "imported") == []
    assert not (alpha / "staging").exists() or os.listdir(alpha / "staging") == []


def test_an_unreadable_description_is_an_error_not_an_empty_list(client: TestClient, tmp_path: Path) -> None:
    """Review M-1 (R-1-5): a description file that cannot be read is an explicit 503 naming the file, never a
    silently shorter list (import writes every description atomically, so a broken one is a fault, not noise)."""
    import_snapshot(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    broken = tmp_path / "alpha" / "data" / "imported" / "broken.json"
    broken.write_text("{", encoding="utf-8")
    response = client.get("/api/v0/snapshots")
    assert response.status_code == 503
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("database_unavailable", True)
    assert str(broken) in error["message"]


def test_a_broken_description_is_an_error_of_the_snapshot_list_only(client: TestClient, tmp_path: Path) -> None:
    """Review M-1 (R-1-5): success -> description fault -> recovery. While a description is unreadable, the
    (deprecated) snapshot list answers 503 naming the file; no page reads snapshots any more (issue #82), so the
    device list is not affected."""
    snapshot = import_snapshot(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    sidecar = Path(snapshot["path"]).with_suffix(".json")
    good = sidecar.read_text(encoding="utf-8")
    assert [item["id"] for item in client.get("/api/v0/snapshots").json()["items"]] == [snapshot["id"]]

    sidecar.write_text('{"id": 1', encoding="utf-8")
    response = client.get("/api/v0/snapshots")
    assert response.status_code == 503, response.text
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("database_unavailable", True)
    assert str(sidecar) in error["message"]
    assert client.get("/api/v0/devices").status_code == 200

    sidecar.write_text(good, encoding="utf-8")
    assert [item["id"] for item in client.get("/api/v0/snapshots").json()["items"]] == [snapshot["id"]]
