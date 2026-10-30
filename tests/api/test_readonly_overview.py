"""readonly.SnapshotOverview reads what ParDatabase reads for the V1.0.3 overview (refresh_overview).

Both run against the same synthetic database (ParDatabase on the original, the read-only class on a byte copy):
the newest record (recent_acquisitions(1)) and the newest successful record with a spectrum
(latest_successful_spectrum) must be identical, including when the newest records failed or have no spectrum.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from par_app.application.errors import DatabaseUnavailable
from par_app.application.readonly import SnapshotOverview
from par_app.database import ParDatabase

from .conftest import RAW_FLAT, failed_record, legacy_database, record, v1_database

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-053 UI-054 UI-055")]

CASES = {
    "empty": [],
    "failures only": [failed_record("2026-10-01T08:00:00.000"), failed_record("2026-10-01T08:01:00.000")],
    "success then failure": [record("2026-10-01T08:00:00.000"), failed_record("2026-10-01T08:01:00.000")],
    "newest success has no spectrum": [
        record("2026-10-01T08:00:00.000"),
        record("2026-10-01T08:01:00.000", raw_points=None),
    ],
    # ids, not times, decide what is newest (ORDER BY id DESC), as in V1.0.3
    "later id with an earlier time": [record("2026-10-01T09:00:00.000"), record("2026-10-01T08:00:00.000")],
    # save_acquisition keeps the spectrum of a failed round when raw_points are given: only successes are shown
    "newest failure has a spectrum": [
        record("2026-10-01T08:00:00.000"),
        {**failed_record("2026-10-01T08:01:00.000"), "raw_points": RAW_FLAT},
    ],
}


def _pair(tmp_path: Path, records: list[dict[str, object]]) -> tuple[ParDatabase, SnapshotOverview]:
    original = v1_database(tmp_path / "v1.sqlite3", records)
    copy = tmp_path / "copy.sqlite3"
    shutil.copyfile(original, copy)
    return ParDatabase(original), SnapshotOverview(copy)


@pytest.mark.parametrize("name", CASES)
def test_latest_rows_equal_parDatabase(tmp_path: Path, name: str) -> None:
    v1, snapshot = _pair(tmp_path, CASES[name])
    rows = v1.recent_acquisitions(1)
    assert snapshot.latest() == (rows[0] if rows else None)
    expected = v1.latest_successful_spectrum()
    found = snapshot.latest_successful()
    if expected is None:
        assert found is None
    else:
        assert found is not None
        assert found[0] == expected[0]
        assert json.loads(found[1]) == expected[1]


def test_legacy_database_without_review_columns(tmp_path: Path) -> None:
    source = legacy_database(tmp_path / "legacy.sqlite3")
    snapshot = SnapshotOverview(source)
    latest = snapshot.latest()
    assert latest is not None and latest["id"] == 2 and latest["success"] == 0
    found = snapshot.latest_successful()
    assert found is not None and found[0]["id"] == 1 and "quality_json" not in found[0]


def test_missing_copy_is_database_unavailable(tmp_path: Path) -> None:
    with pytest.raises(DatabaseUnavailable):
        SnapshotOverview(tmp_path / "gone.sqlite3").latest()
