"""readonly.SnapshotOperations reads what ParDatabase reads for the spectrum calculation page (V1.0.3).

Both run against the same synthetic database (ParDatabase on the original, the read-only class on a byte copy):
the candidate list (success, valid JSON, exactly 701 points, newest id first, the limit), the nearest-time search
(whole database, legacy zone-suffixed times, ties, unreadable times) and the stored record must be identical.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from par_app.application.readonly import SnapshotOperations
from par_app.database import ParDatabase

from .conftest import failed_record, record, v1_database

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-197 UI-198 UI-200 UI-288")]


def _mixed(path: Path) -> Path:
    rows = [
        record("2026-10-01T08:00:00.000"),  # 1
        failed_record("2026-10-01T08:01:00.000"),  # 2
        record("2026-10-01T08:02:00.000", raw_points=[1] * 700),  # 3: 700 points
        record("2026-10-01T00:03:00+00:00"),  # 4: legacy UTC = 08:03 Beijing
        record("2026-10-01T08:04:00.000"),  # 5: will hold invalid JSON
        record("2026-10-01T08:06:00.000"),  # 6
        record("2026-10-01T08:06:00.000"),  # 7: same time as 6
        record("not a time"),  # 8: unreadable time, never matched
        record("2026-10-01T08:10:00.000", success=0),  # 9: failed but with a spectrum
    ]
    v1_database(path, rows)
    with ParDatabase(path).connect() as con:
        con.execute("UPDATE spectra SET raw_points_json='[1,2,' WHERE acquisition_id=5")
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[ParDatabase, SnapshotOperations]:
    original = _mixed(tmp_path / "v1.sqlite3")
    copy = tmp_path / "copy.sqlite3"
    shutil.copyfile(original, copy)
    return ParDatabase(original), SnapshotOperations(copy)


def test_candidates_equal_operation_spectra(pair: tuple[ParDatabase, SnapshotOperations]) -> None:
    v1, snapshot = pair
    for limit in (500, 3, 1):
        assert snapshot.spectra(limit) == v1.operation_spectra(limit)
    assert [row["id"] for row in snapshot.spectra(500)] == [8, 7, 6, 4, 1]


@pytest.mark.parametrize(
    "acquired_at",
    [
        "2026-10-01T08:00:00.000",
        "2026-10-01T08:03:00.000",
        "2026-10-01T08:03:00+08:00",
        "2026-10-01T00:03:00Z",
        "2026-10-01T08:05:00.000",  # 4 and 6 are one minute away each: the earlier time (4) wins
        "2026-10-01T08:07:00.000",  # 6 and 7 share a time: the smaller id
        "2030-01-01T00:00:00.000",
        "not a time",
        "",
    ],
)
def test_nearest_equals_nearest_operation_spectrum(
    pair: tuple[ParDatabase, SnapshotOperations], acquired_at: str
) -> None:
    v1, snapshot = pair
    assert snapshot.nearest(acquired_at) == v1.nearest_operation_spectrum(acquired_at)


def test_record_equals_get_spectrum(pair: tuple[ParDatabase, SnapshotOperations]) -> None:
    v1, snapshot = pair
    for record_id in (1, 3, 4, 9):
        found = snapshot.record(record_id)
        assert found is not None
        row, stored = found
        assert (row, json.loads(stored)) == v1.get_spectrum(record_id)
    assert snapshot.record(2) is None and v1.get_spectrum(2) is None  # a failed record without a spectrum row
    assert snapshot.record(99) is None and v1.get_spectrum(99) is None
