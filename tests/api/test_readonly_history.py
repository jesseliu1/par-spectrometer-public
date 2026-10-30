"""The read-only history queries return what ParDatabase returns for the same database (15_ 5.3).

SnapshotHistory repeats the SQL of ParDatabase.recent_acquisitions / get_spectrum on a mode=ro connection. Both
run here against the same synthetic V1.0.x database; a second database file is used for ParDatabase because it
writes on open.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

from par_app.application.errors import DatabaseUnavailable
from par_app.application.readonly import SnapshotHistory, connect_read_only, read_only_uri
from par_app.database import ParDatabase
from tests.api.conftest import failed_record, record, v1_database

pytestmark = pytest.mark.unit
RANGES = [
    ("2026-10-01T00:00:00.000", "2026-10-01T23:59:59.999"),
    ("2026-10-01T12:00:30.000", "2026-10-01T12:02:00.000"),
    ("2026-10-01T12:01:00.000", "2026-10-01T12:01:00.000"),
    ("2026-09-01T00:00:00.000", "2026-09-02T00:00:00.000"),
]


@pytest.fixture
def databases(tmp_path: Path) -> tuple[SnapshotHistory, ParDatabase]:
    rows = [record(f"2026-10-01T12:0{minute}:00.000") for minute in range(4)]
    rows.insert(2, failed_record("2026-10-01T12:01:00.000"))
    source = v1_database(tmp_path / "a" / "par.sqlite3", rows)
    twin = tmp_path / "b" / "par.sqlite3"
    twin.parent.mkdir()
    shutil.copyfile(source, twin)
    return SnapshotHistory(source), ParDatabase(twin)


@pytest.mark.parametrize(("start", "end"), RANGES)
@pytest.mark.parametrize("limit", [1, 2, 500])
def test_first_page_equals_recent_acquisitions(
    databases: tuple[SnapshotHistory, ParDatabase], start: str, end: str, limit: int
) -> None:
    snapshot, v1 = databases
    assert snapshot.acquisitions(start, end, limit, 0) == v1.recent_acquisitions(limit, start, end)


def test_later_pages_continue_where_the_first_stops(databases: tuple[SnapshotHistory, ParDatabase]) -> None:
    snapshot, v1 = databases
    start, end = RANGES[0]
    pages = [snapshot.acquisitions(start, end, 2, offset) for offset in (0, 2, 4)]
    assert [row for page in pages for row in page] == v1.recent_acquisitions(500, start, end)


def test_record_and_spectrum_equal_get_spectrum(databases: tuple[SnapshotHistory, ParDatabase]) -> None:
    snapshot, v1 = databases
    for acquisition_id in range(1, 6):
        expected = v1.get_spectrum(acquisition_id)
        row = snapshot.acquisition(acquisition_id)
        assert row is not None
        if expected is None:
            assert snapshot.spectrum(acquisition_id) is None
        else:
            assert (row, snapshot.spectrum(acquisition_id)) == expected
    assert snapshot.acquisition(99) is None


def test_read_only_connection_refuses_writes(tmp_path: Path) -> None:
    path = v1_database(tmp_path / "par.sqlite3", [record()])
    before = path.read_bytes()
    with pytest.raises(DatabaseUnavailable) as raised, connect_read_only(path) as con:
        con.execute("DELETE FROM acquisitions")
    assert raised.value.path == str(path)
    assert "readonly" in (raised.value.detail or "")
    assert path.read_bytes() == before


def test_read_only_connection_does_not_create_a_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(DatabaseUnavailable), connect_read_only(missing):
        pass
    assert not missing.exists()


UNUSUAL_NAMES = ["东区 #1 %25 &;=,.sqlite3"]
"""Characters a URI must escape (#, %, space, &, ;, =, ",", non-ASCII) that Windows allows in a file name."""
if sys.platform != "win32":
    UNUSUAL_NAMES.append("东区 #1?.sqlite3")  # "?" ends a URI path; Windows does not allow it in a file name (#66)


@pytest.mark.parametrize("name", UNUSUAL_NAMES)
def test_uri_escapes_unusual_names(tmp_path: Path, name: str) -> None:
    path = v1_database(tmp_path / name, [record()])
    assert read_only_uri(path).endswith("?mode=ro")
    assert read_only_uri(path, immutable=True).endswith("?mode=ro&immutable=1")
    con = sqlite3.connect(read_only_uri(path), uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM acquisitions").fetchone()[0] == 1
    finally:
        con.close()
