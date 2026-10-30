"""readonly.SnapshotExport reads what ParDatabase reads for the settings page (V1.0.3).

Both run against the same synthetic database (ParDatabase on the original, the read-only class on a byte copy):
the export count, the export rows (failed records and records without a spectrum included, time order), the record
summary and the stored device identity must be identical.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from par_app.application.readonly import SnapshotExport
from par_app.database import ParDatabase

from .conftest import failed_record, record, v1_database

pytestmark = [pytest.mark.unit, pytest.mark.spec("EXP-003 EXP-006 EXP-011 EXP-050 UI-080 UI-081")]

RANGES = [
    ("2026-10-01T00:00:00", "2026-10-01T23:59:59.999"),
    ("2026-10-01T08:00:00", "2026-10-01T08:00:00.999"),
    ("2026-10-01T08:00:01", "2026-10-01T08:00:00.999"),  # end before start
    ("2026-10-02T00:00:00", "2026-10-02T23:59:59.999"),
    ("0001-01-01T00:00:00", "9999-12-31T23:59:59.999"),
]


def _mixed(path: Path) -> Path:
    v1_database(
        path,
        [
            record("2026-10-01T08:00:00.000"),  # 1
            record("2026-10-01T08:00:00.500"),  # 2: same second
            failed_record("2026-10-01T07:59:59.999"),  # 3: earlier time, larger id
            record("2026-10-01T00:00:00+00:00"),  # 4: legacy UTC text (compared as text, like V1.0.3)
            record("2026-10-01T12:00:00.000", raw_points=None),  # 5: success without a spectrum row
        ],
    )
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[ParDatabase, SnapshotExport]:
    original = _mixed(tmp_path / "v1.sqlite3")
    copy = tmp_path / "copy.sqlite3"
    shutil.copyfile(original, copy)
    return ParDatabase(original), SnapshotExport(copy)


@pytest.mark.parametrize(("start", "end"), RANGES)
def test_count_and_rows_equal_parDatabase(pair: tuple[ParDatabase, SnapshotExport], start: str, end: str) -> None:
    v1, snapshot = pair
    assert snapshot.count(start, end) == v1.acquisition_export_count(start, end)
    assert snapshot.rows(start, end) == v1.acquisitions_for_export(start, end)
    assert snapshot.row_count(start, end) == len(v1.acquisitions_for_export(start, end))


def test_rows_are_in_time_order_with_failures(pair: tuple[ParDatabase, SnapshotExport]) -> None:
    _, snapshot = pair
    rows = snapshot.rows(*RANGES[0])
    assert [row["id"] for row in rows] == [4, 3, 1, 2, 5]
    assert rows[1]["raw_points_json"] is None and rows[4]["raw_points_json"] is None


def test_summary_and_identity_equal_parDatabase(pair: tuple[ParDatabase, SnapshotExport], tmp_path: Path) -> None:
    v1, snapshot = pair
    assert snapshot.summary() == v1.acquisition_summary()
    assert snapshot.identity() == v1.load_par_device_identity() is None
    v1.save_par_device_identity(305419896, 3, "PAR")
    shutil.copyfile(v1.path, snapshot.path)
    assert (
        snapshot.identity()
        == v1.load_par_device_identity()
        == {
            "serial_number": 305419896,
            "device_type": 3,
            "device_name": "PAR",
        }
    )
    con = sqlite3.connect(v1.path)
    con.execute("UPDATE app_settings SET value_json='[' WHERE key='par_device_identity'")
    con.commit()
    con.close()  # the last connection checkpoints the WAL into the file that is copied
    shutil.copyfile(v1.path, snapshot.path)
    assert snapshot.identity() is None and v1.load_par_device_identity() is None


def test_old_database_without_app_settings(tmp_path: Path) -> None:
    """A V1.0.0-era file has no app_settings table; ParDatabase would add it on open, the copy reads None."""
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE acquisitions (id INTEGER PRIMARY KEY, acquired_at TEXT NOT NULL, success INTEGER NOT NULL);"
        "CREATE TABLE spectra (acquisition_id INTEGER PRIMARY KEY, raw_points_json TEXT NOT NULL);"
        "INSERT INTO acquisitions VALUES (1, '2026-10-01T08:00:00+00:00', 1);"
    )
    con.commit()
    con.close()
    snapshot = SnapshotExport(path)
    assert snapshot.identity() is None
    assert snapshot.summary() == {"total": 1, "latest": "2026-10-01T08:00:00+00:00"}
