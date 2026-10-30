"""Snapshot import and listing (API-20, API-21; 13_ 2.4 A, 15_ section 5, S-3).

The source database must come out byte for byte unchanged, with no file added beside it, and must only ever be
opened through a read-only SQLite URI.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from tests.api.conftest import error_of, failed_record, import_snapshot, legacy_database, record, v1_database

pytestmark = pytest.mark.unit
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")


def _state(source: Path) -> tuple[str, list[str]]:
    """SHA-256 of the source file and the names of every file beside it."""
    return hashlib.sha256(source.read_bytes()).hexdigest(), sorted(os.listdir(source.parent))


def _rows(path: Path) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT a.*, s.raw_points_json FROM acquisitions a "
            "LEFT JOIN spectra s ON s.acquisition_id=a.id ORDER BY a.id"
        ).fetchall()
    finally:
        con.close()


def test_import_copies_the_database_and_leaves_the_source_untouched(client: TestClient, tmp_path: Path) -> None:
    source = v1_database(tmp_path / "v1" / "东区 1号.sqlite3", [record(), failed_record()])
    before = _state(source)

    snapshot = import_snapshot(client, source)

    assert _state(source) == before
    assert snapshot["name"] == "东区 1号"
    assert snapshot["key"] == "p1" and snapshot["position"] == 1
    assert snapshot["id"] == "东区 1号-20261018-093000"
    assert snapshot["file_name"] == "东区 1号-20261018-093000.sqlite"
    assert snapshot["imported_at"] == "2026-10-18T09:30:00.000"
    assert snapshot["record_count"] == 2
    assert snapshot["source_path"] == str(source.resolve())
    assert snapshot["source_before"] == snapshot["source_after"]
    assert snapshot["source_before"]["sha256"] == before[0]
    assert snapshot["source_changed_during_import"] is False
    copy = Path(snapshot["path"])
    assert copy.parent == tmp_path / "alpha" / "data" / "imported"
    assert _rows(copy) == _rows(source)
    assert sorted(os.listdir(copy.parent)) == sorted(
        [copy.name, copy.with_suffix(".json").name]
    )  # no partial file left


@POSIX_ONLY
def test_import_needs_no_write_access_to_the_source(client: TestClient, tmp_path: Path) -> None:
    """Read-only file in a read-only folder (e.g. a protected share): the import still works and adds nothing."""
    folder = tmp_path / "readonly"
    source = v1_database(folder / "par.sqlite3", [record()])
    before = _state(source)
    source.chmod(0o444)
    folder.chmod(0o555)
    try:
        snapshot = import_snapshot(client, source)
    finally:
        folder.chmod(0o755)
        source.chmod(0o644)
    assert snapshot["record_count"] == 1
    assert _state(source) == before


def test_legacy_rollback_journal_database_is_imported_unchanged(client: TestClient, tmp_path: Path) -> None:
    source = legacy_database(tmp_path / "v1" / "old.sqlite3")
    before = _state(source)
    snapshot = import_snapshot(client, source, name="旧库", position=3)
    assert _state(source) == before
    assert (snapshot["key"], snapshot["record_count"]) == ("p3", 2)


def test_live_wal_database_is_copied_with_its_uncheckpointed_records(client: TestClient, tmp_path: Path) -> None:
    """V1.0.3 running: records still in the -wal file are part of the copy; database and -wal stay unchanged."""
    source = v1_database(tmp_path / "v1" / "live.sqlite3", [record()])
    writer = sqlite3.connect(source)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T13:00:00.000', 0, 1.0)"
        )
        writer.commit()
        wal = source.with_name(source.name + "-wal")
        main_before, wal_before = source.read_bytes(), wal.read_bytes()

        snapshot = import_snapshot(client, source)

        assert source.read_bytes() == main_before
        assert wal.read_bytes() == wal_before
        assert snapshot["record_count"] == 2
    finally:
        writer.close()


def test_source_is_only_opened_through_a_read_only_uri(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    calls: list[tuple[str, dict[str, object]]] = []
    real_connect: Callable[..., sqlite3.Connection] = sqlite3.connect

    def spy(database: str | Path, *args: object, **kwargs: object) -> sqlite3.Connection:
        calls.append((str(database), kwargs))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy)
    import_snapshot(client, source)

    on_source = [(target, kwargs) for target, kwargs in calls if source.name in target and "imported" not in target]
    assert on_source, calls
    assert all(kwargs.get("uri") is True and "?mode=ro" in target for target, kwargs in on_source), on_source


def test_a_source_changed_during_an_at_rest_copy_is_refused(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """immutable=1 skips locking, so a change seen afterwards discards the copy (busy, retryable)."""
    import par_app.application.snapshots as snapshots

    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    real_copy = snapshots._copy

    def copy_then_v1_writes(src: Path, target: Path) -> int:
        count = real_copy(src, target)
        v1_database(src, [record("2026-10-01T14:00:00.000")])
        return count

    monkeypatch.setattr(snapshots, "_copy", copy_then_v1_writes)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})

    assert response.status_code == 409
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("busy", True)
    imported = tmp_path / "alpha" / "data" / "imported"
    assert os.listdir(imported) == []


def test_imported_copy_is_a_single_file_database(client: TestClient, tmp_path: Path) -> None:
    snapshot = import_snapshot(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
    con = sqlite3.connect(snapshot["path"])
    try:
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        con.close()


@pytest.mark.parametrize("path", ["", "   ", "does/not/exist.sqlite3"])
def test_missing_source_is_an_invalid_argument(client: TestClient, path: str) -> None:
    response = client.post("/api/v0/snapshots", json={"source_path": path})
    assert response.status_code == 400
    assert error_of(response)["code"] == "invalid_argument"


def test_directory_as_source_is_an_invalid_argument(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/v0/snapshots", json={"source_path": str(tmp_path)})
    assert response.status_code == 400


def test_a_file_that_is_not_sqlite_is_unavailable_and_unchanged(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "v1" / "notes.sqlite3"
    source.parent.mkdir()
    source.write_text("not a database", encoding="utf-8")
    before = _state(source)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "database_unavailable" and error["retryable"] is True
    assert str(source.resolve()) in error["message"]
    assert _state(source) == before
    assert os.listdir(tmp_path / "alpha" / "data" / "imported") == []


def test_a_sqlite_file_without_history_tables_is_refused(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "v1" / "other.sqlite3"
    source.parent.mkdir()
    con = sqlite3.connect(source)
    con.execute("CREATE TABLE notes(id INTEGER)")
    con.close()
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 400
    assert "acquisitions" in error_of(response)["message"]


@pytest.mark.parametrize("body", [{"position": 0}, {"position": 5}, {"position": "p1"}, {"name": "x" * 101}, {}])
def test_bad_import_parameters_are_invalid_arguments(client: TestClient, tmp_path: Path, body: dict[str, Any]) -> None:
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    payload = {"source_path": str(source), **body} if body else {}
    response = client.post("/api/v0/snapshots", json=payload)
    assert response.status_code == 400
    assert error_of(response)["code"] == "invalid_argument"


def test_a_second_import_while_one_runs_is_busy(client: TestClient, context: ServiceContext, tmp_path: Path) -> None:
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    lock: threading.Lock = context.snapshots._import_lock
    with lock:
        response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 409
    assert error_of(response) == {
        "code": "busy",
        "message": "已有快照导入正在进行，请稍后重试",
        "retryable": True,
        "detail": None,
    }


def test_list_is_empty_before_any_import(client: TestClient) -> None:
    response = client.get("/api/v0/snapshots")
    assert response.status_code == 200
    assert response.json() == {"as_of": "2026-10-18T09:30:00.000", "source": "snapshot", "items": []}


def test_list_shows_every_import_newest_first(client: TestClient, context: ServiceContext, tmp_path: Path) -> None:
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    first = import_snapshot(client, source, name="东区")
    context.clock.advance(60)  # type: ignore[attr-defined]
    second = import_snapshot(client, source, name="东区")
    third = import_snapshot(client, source, name="东区")  # same second: the file name gets a counter

    assert third["id"] == "东区-20261018-093100-2"
    items = client.get("/api/v0/snapshots").json()["items"]
    assert [item["id"] for item in items] == [third["id"], second["id"], first["id"]]
    assert items[0] == third


def test_name_is_made_safe_for_a_file_name(client: TestClient, tmp_path: Path) -> None:
    snapshot = import_snapshot(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]), name='a/b:c*?"<>|')
    assert snapshot["name"] == 'a/b:c*?"<>|'
    assert snapshot["file_name"] == "a_b_c_-20261018-093000.sqlite"
    sidecar = Path(snapshot["path"]).with_suffix(".json")
    assert json.loads(sidecar.read_text(encoding="utf-8"))["name"] == 'a/b:c*?"<>|'


def _crashed_wal_database(folder: Path) -> Path:
    """What V1.0.3 leaves after a crash, a forced stop or a power cut: the database and its -wal, no -shm.

    The -wal holds one committed record that was never checkpointed into the database file.
    """
    live = v1_database(folder.parent / f"{folder.name}-live" / "par.sqlite3", [record()])
    writer = sqlite3.connect(live)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO acquisitions(acquired_at, success, elapsed_ms) VALUES('2026-10-01T13:00:00.000', 0, 1.0)"
        )
        writer.commit()
        folder.mkdir(parents=True)
        for suffix in ("", "-wal"):
            (folder / f"par.sqlite3{suffix}").write_bytes(live.with_name(live.name + suffix).read_bytes())
    finally:
        writer.close()
    return folder / "par.sqlite3"


def _wal_state(source: Path) -> tuple[str, str, list[str]]:
    wal = source.with_name(source.name + "-wal")
    return (
        hashlib.sha256(source.read_bytes()).hexdigest(),
        hashlib.sha256(wal.read_bytes()).hexdigest(),
        sorted(os.listdir(source.parent)),
    )


def test_crash_leftover_wal_is_copied_without_adding_a_file_beside_the_source(
    client: TestClient, tmp_path: Path
) -> None:
    """Review M-2: -wal without -shm means no program has the database open; nothing may appear beside it."""
    source = _crashed_wal_database(tmp_path / "v1")
    before = _wal_state(source)
    assert before[2] == ["par.sqlite3", "par.sqlite3-wal"]

    snapshot = import_snapshot(client, source)

    assert _wal_state(source) == before
    assert snapshot["record_count"] == 2  # the uncheckpointed record is part of the copy
    assert snapshot["source_changed_during_import"] is False
    alpha = tmp_path / "alpha" / "data"
    assert sorted(os.listdir(alpha / "imported")) == sorted([snapshot["file_name"], f"{snapshot['id']}.json"])
    assert not (alpha / "staging").exists() or os.listdir(alpha / "staging") == []


@POSIX_ONLY
def test_crash_leftover_wal_in_a_read_only_folder_is_imported(client: TestClient, tmp_path: Path) -> None:
    """Review M-2: the same leftovers on a read-only share used to answer 503 although the data is readable."""
    source = _crashed_wal_database(tmp_path / "v1")
    before = _wal_state(source)
    folder = source.parent
    for path in folder.iterdir():
        path.chmod(0o444)
    folder.chmod(0o555)
    try:
        snapshot = import_snapshot(client, source)
    finally:
        folder.chmod(0o755)
        for path in folder.iterdir():
            path.chmod(0o644)
    assert snapshot["record_count"] == 2
    assert _wal_state(source) == before


def test_empty_leftover_wal_adds_no_file_beside_the_source(client: TestClient, tmp_path: Path) -> None:
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    source.with_name(source.name + "-wal").write_bytes(b"")
    before = _wal_state(source)
    snapshot = import_snapshot(client, source)
    assert _wal_state(source) == before
    assert snapshot["record_count"] == 1


def test_leftover_wal_changed_while_it_is_copied_is_refused(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V1.0.3 started while the leftovers were copied: the file copy may be torn, so it is discarded (busy)."""
    import par_app.application.snapshots as snapshots

    source = _crashed_wal_database(tmp_path / "v1")
    wal = source.with_name(source.name + "-wal")
    real_stage = snapshots._stage

    def stage_then_v1_writes(files: list[Path], folder: Path) -> Path:
        staged = real_stage(files, folder)
        with wal.open("ab") as handle:
            handle.write(b"\0" * 16)
        return staged

    monkeypatch.setattr(snapshots, "_stage", stage_then_v1_writes)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})

    assert response.status_code == 409
    assert error_of(response)["code"] == "busy"
    alpha = tmp_path / "alpha" / "data"
    assert os.listdir(alpha / "imported") == []
    assert not (alpha / "staging").exists() or os.listdir(alpha / "staging") == []


def test_failed_integrity_check_names_the_copy(tmp_path: Path) -> None:
    """Review N-4 (mutant M15): a copy whose quick_check is not "ok" is refused, naming the copy (ruling 47)."""
    import par_app.application.snapshots as snapshots
    from par_app.application.errors import DatabaseUnavailable

    class Result:
        def __init__(self, value: object) -> None:
            self.value = value

        def fetchone(self) -> tuple[object]:
            return (self.value,)

    class Copy:
        def execute(self, sql: str) -> Result:
            return Result("*** in database main ***\nPage 2: btree page corrupt" if "quick_check" in sql else 1)

    target = tmp_path / "copy.sqlite.partial"
    with pytest.raises(DatabaseUnavailable) as raised:
        snapshots._finish_copy(Copy(), target)  # type: ignore[arg-type]
    assert raised.value.path == str(target)
    assert "完整性" in (raised.value.detail or "")


def test_a_failure_to_move_the_copy_in_place_names_the_copy(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review N-3: the 503 message names the file that failed (ruling 47), here alpha's own copy, not the source."""
    import par_app.application.snapshots as snapshots

    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])

    def refuse(_src: object, _dst: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(snapshots.os, "replace", refuse)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 503
    message = error_of(response)["message"]
    assert str(tmp_path / "alpha" / "data" / "imported") in message
    assert str(source) not in message


def test_an_unwritable_data_directory_is_unavailable_with_its_path(client: TestClient, tmp_path: Path) -> None:
    """Review N-3: paths.ensure() failing used to be an unexplained 500."""
    (tmp_path / "alpha").write_text("a file where the data directory should be", encoding="utf-8")
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 503
    assert str(tmp_path / "alpha") in error_of(response)["message"]


def test_a_failure_to_write_the_description_leaves_no_copy(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review N-3: the sidecar write failing is a 503 naming the sidecar, and the copy without it is removed."""
    import par_app.application.snapshots as snapshots

    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    real_write_text = Path.write_text

    def refuse_sidecar(self: Path, data: str, encoding: str | None = None) -> int:
        if self.parent.name == "imported":
            raise OSError(28, "No space left on device")
        return real_write_text(self, data, encoding=encoding)

    monkeypatch.setattr(snapshots.Path, "write_text", refuse_sidecar)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source)})
    assert response.status_code == 503
    assert ".json" in error_of(response)["message"]
    assert os.listdir(tmp_path / "alpha" / "data" / "imported") == []


def test_crash_leftover_rollback_journal_is_rolled_back_in_the_copy_only(client: TestClient, tmp_path: Path) -> None:
    """A V1.0.0-era database left with a hot -journal: the copy holds the state before the unfinished transaction,
    the source and its -journal stay as they are."""
    live = legacy_database(tmp_path / "live" / "old.sqlite3")
    con = sqlite3.connect(live, isolation_level=None)
    try:
        con.execute("PRAGMA cache_size=1")  # spill to the database file, so the -journal is needed to roll back
        con.execute("BEGIN IMMEDIATE")
        for number in range(2000):
            con.execute("INSERT INTO spectra VALUES(?, ?)", (100 + number, "x" * 500))
        con.execute("DELETE FROM acquisitions WHERE id=2")
        folder = tmp_path / "v1"
        folder.mkdir()
        for name in os.listdir(live.parent):
            (folder / name).write_bytes((live.parent / name).read_bytes())
        con.execute("ROLLBACK")
    finally:
        con.close()
    source = folder / "old.sqlite3"
    journal = source.with_name(source.name + "-journal")
    before = (hashlib.sha256(source.read_bytes()).hexdigest(), hashlib.sha256(journal.read_bytes()).hexdigest())
    assert sorted(os.listdir(folder)) == ["old.sqlite3", "old.sqlite3-journal"]

    snapshot = import_snapshot(client, source)

    assert sorted(os.listdir(folder)) == ["old.sqlite3", "old.sqlite3-journal"]
    assert (hashlib.sha256(source.read_bytes()).hexdigest(), hashlib.sha256(journal.read_bytes()).hexdigest()) == before
    assert snapshot["record_count"] == 2
    assert _rows(Path(snapshot["path"])) == _rows(legacy_database(tmp_path / "fresh" / "old.sqlite3"))


def test_a_name_already_used_by_another_position_is_refused(client: TestClient, tmp_path: Path) -> None:
    """D-210 question 5: V1.0.3 refuses duplicate device names (device_hub: 设备名称不能为空或重复。); two positions
    with one name would export into one device folder and overwrite each other's files. Re-importing a position
    under its own name stays allowed."""
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    import_snapshot(client, source, name="东区", position=1)
    import_snapshot(client, source, name="东区", position=1)  # the same position again
    response = client.post("/api/v0/snapshots", json={"source_path": str(source), "name": " 东区 ", "position": 2})
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "invalid_argument"
    assert error["message"] == "设备名称“东区”已用于位置 1，不同位置不能同名（同 V1.0.3：设备名称不能为空或重复。）"
    unnamed = client.post("/api/v0/snapshots", json={"source_path": str(source), "position": 2})  # stem "par" is free
    assert unnamed.status_code == 201
    assert len(client.get("/api/v0/snapshots").json()["items"]) == 3


@pytest.mark.parametrize(
    ("first", "second", "folder"),
    [("A/B", "A?B", "A_B"), ("East", "east", "East"), ("东区.", "东区", "东区")],
    ids=["same-after-safe-filename", "differs-only-in-case", "trailing-dot"],
)
def test_names_that_share_an_export_folder_are_refused(
    client: TestClient, tmp_path: Path, first: str, second: str, folder: str
) -> None:
    """D-210 question 5 (review #52 item 6): the export folder is the name after safe_database_filename, and
    Windows compares folder names without case, so two different names can still write into one device folder and
    overwrite each other's files. The import refuses a name whose folder another position already uses."""
    source = v1_database(tmp_path / "v1" / "par.sqlite3", [record()])
    import_snapshot(client, source, name=first, position=1)
    response = client.post("/api/v0/snapshots", json={"source_path": str(source), "name": second, "position": 2})
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "invalid_argument"
    assert error["message"] == (
        f"设备名称“{second}”与位置 1 的“{first}”导出到同一个设备目录“{folder}”，"
        "不同位置不能共用设备目录（同 V1.0.3：设备名称不能为空或重复。）"
    )


@pytest.mark.parametrize("name", ["东区", "A/B", "  ", "COM1", "东区.", "x" * 300])
def test_the_folder_checked_at_import_is_the_folder_the_export_writes(name: str) -> None:
    from par_app.application.snapshots import export_folder
    from par_app.services.export import device_folder

    assert export_folder(name) == device_folder(name)
