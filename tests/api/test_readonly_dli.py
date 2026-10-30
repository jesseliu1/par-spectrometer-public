"""readonly.SnapshotDli and the setting parsers of application.dli read what ParDatabase reads (V1.0.3).

Both run against the same synthetic database: the eligibility predicate (D-126), the interruption rows, the bounds
(period, enable time, zone-suffixed legacy times) and the ordering must give identical rows; the stored location
and enable time must decode identically, including the fallbacks.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from par_app.application.dli import DEFAULT_LOCATION, parse_enabled_at, parse_location
from par_app.application.errors import RecordUnreadable
from par_app.application.readonly import SnapshotDli
from par_app.database import ParDatabase

from .conftest import failed_record, legacy_database, record, v1_database

pytestmark = [pytest.mark.unit, pytest.mark.spec("DLI-007 DLI-012 DLI-014 DLI-021")]
START, END, ENABLED = "2026-10-14T06:19:00", "2026-10-15T06:19:00", "2026-10-14T08:00:00"
UNCONFIRMED = json.dumps({"selected_group": 1, "confirmed": False})


def _mixed(path: Path) -> Path:
    records = [
        record("2026-10-14T07:59:00.000"),  # before the enable time
        record("2026-10-14T08:00:00.000"),
        failed_record("2026-10-14T08:01:00.000"),
        record("2026-10-14T08:02:00.000", dli_eligible=0),
        record("2026-10-14T08:03:00.000", dli_eligible=None, quality_json=UNCONFIRMED),  # D-126: not counted
        record("2026-10-14T08:04:00.000", dli_eligible=None, quality_json=json.dumps({"confirmed": True})),
        record("2026-10-14T08:05:00.000", dli_eligible=None, quality_json=None),
        record("2026-10-14T08:06:00.000", dli_eligible=None, quality_json="{not json"),
        record("2026-10-14T08:07:00+08:00"),  # zone suffix: ignored
        record("2026-10-14T08:08:00.000", software_metrics_json=json.dumps({"ppfd": "abc"})),
        record("2026-10-15T06:19:00.000"),  # the period end itself is excluded
    ]
    v1_database(path, records)
    with ParDatabase(path).connect() as con:
        # the last two are out of bounds: before the period, and inside the period but before the enable time
        for at in (
            "2026-10-14T08:04:00.000",
            "2026-10-14T08:04:00.000",
            "2026-10-13T09:00:00.000",
            "2026-10-14T07:00:00.000",
        ):
            con.execute("INSERT INTO dli_interruptions(occurred_at,reason) VALUES(?,?)", (at, "t"))
    return path


def test_samples_equal_par_database_dli_samples(tmp_path: Path) -> None:
    path = _mixed(tmp_path / "v1.sqlite3")
    copy = tmp_path / "copy.sqlite3"
    shutil.copyfile(path, copy)
    expected = ParDatabase(path).dli_samples(START, END, ENABLED)
    rows = SnapshotDli(copy).samples(START, END, ENABLED)
    assert rows == expected
    assert [row["eligible"] for row in rows] == [1, 0, 0, 0, 0, 0, 1, 1, 1, 1]


def test_interruptions_use_the_same_bounds(tmp_path: Path) -> None:
    path = _mixed(tmp_path / "v1.sqlite3")
    rows = SnapshotDli(path).interruptions(START, END, ENABLED)
    assert rows == [{"occurred_at": "2026-10-14T08:04:00.000", "reason": "t"}] * 2


def test_v100_database_reads_missing_columns_and_tables_as_null(tmp_path: Path) -> None:
    path = legacy_database(tmp_path / "old.sqlite3")
    database = SnapshotDli(path)
    assert database.samples("2026-10-01T00:00:00", "2026-10-02T00:00:00", "2026-01-01T00:00:00") == []
    assert database.interruptions("2026-10-01T00:00:00", "2026-10-02T00:00:00", "2026-01-01T00:00:00") == []
    assert (database.location_value(), database.enabled_at_value()) == (None, (False, None))
    # what V1.0.3 would read after migrating the same file (ALTER TABLE adds the two columns as NULL)
    migrated = tmp_path / "migrated.sqlite3"
    shutil.copyfile(path, migrated)
    assert ParDatabase(migrated).dli_samples("2026-10-01T00:00:00", "2026-10-02T00:00:00", "2026-01-01T00:00:00") == []


@pytest.mark.spec("DLI-010 DLI-013")
def test_poll_cycle_record_is_the_latest_success_before_the_bounds(tmp_path: Path) -> None:
    """D-204 question 1 (D): the latest successful record before the period end and at or before the cutoff,
    zone-suffixed times excluded as in dli_samples; a period without one looks further back."""
    path = v1_database(
        tmp_path / "v1.sqlite3",
        [
            record("2026-10-13T12:00:00.000", quality_json='{"poll_cycle_seconds": 600.0}'),
            record("2026-10-14T08:00:00.000", quality_json='{"poll_cycle_seconds": 300.0}'),
            failed_record("2026-10-14T08:05:00.000"),
            record("2026-10-14T08:06:00+08:00", quality_json='{"poll_cycle_seconds": 90.0}'),
            record("2026-10-14T09:00:00.000", quality_json='{"poll_cycle_seconds": 120.0}'),
            record("2026-10-15T06:19:00.000", quality_json='{"poll_cycle_seconds": 40.0}'),  # the period end
        ],
    )
    database = SnapshotDli(path)
    assert database.poll_cycle_record(END, "2026-10-14T08:59:59.999") == {
        "acquired_at": "2026-10-14T08:00:00.000",
        "quality_json": '{"poll_cycle_seconds": 300.0}',
    }
    assert database.poll_cycle_record(END, END)["acquired_at"] == "2026-10-14T09:00:00.000"
    assert database.poll_cycle_record(START, START)["acquired_at"] == "2026-10-13T12:00:00.000"
    assert database.poll_cycle_record("2026-10-13T00:00:00", "2026-10-13T00:00:00") is None


def test_poll_cycle_record_of_a_v100_database_reads_quality_as_null(tmp_path: Path) -> None:
    path = legacy_database(tmp_path / "old.sqlite3")
    database = SnapshotDli(path)
    assert database.poll_cycle_record("2026-10-02T00:00:00", "2026-10-02T00:00:00") is None  # zone-suffixed only
    con = sqlite3.connect(path)
    with con:
        con.execute("INSERT INTO acquisitions(acquired_at,success,elapsed_ms) VALUES('2026-10-01T09:00:00',1,1.0)")
    con.close()
    row = database.poll_cycle_record("2026-10-02T00:00:00", "2026-10-02T00:00:00")
    assert row == {"acquired_at": "2026-10-01T09:00:00", "quality_json": None}


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        (None, False),
        (json.dumps({"latitude": 31.2304, "longitude": 121.4737}), True),
        (json.dumps({"latitude": "31.5", "longitude": 121}), True),
        (json.dumps({"latitude": 31.2}), False),
        (json.dumps([1, 2]), False),
        ("{not json", False),
        (json.dumps({"latitude": None, "longitude": 1}), False),
    ],
)
@pytest.mark.spec("UI-153")
def test_location_parses_like_load_dli_location(tmp_path: Path, value: str | None, stored: bool) -> None:
    database = ParDatabase(tmp_path / "v1.sqlite3")
    if value is not None:
        with database.connect() as con:
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_location',?,'x')", (value,))
    location, readable = parse_location(SnapshotDli(database.path).location_value())
    assert location == database.load_dli_location()
    assert readable is stored
    if not stored:
        assert location == DEFAULT_LOCATION


@pytest.mark.parametrize("value", [None, json.dumps("2026-10-14T08:00:00"), json.dumps(12)])
def test_enable_time_parses_like_peek_dli_enabled_at(tmp_path: Path, value: str | None) -> None:
    database = ParDatabase(tmp_path / "v1.sqlite3")
    if value is not None:
        with database.connect() as con:
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',?,'x')", (value,))
    assert parse_enabled_at(SnapshotDli(database.path).enabled_at_value()) == database.peek_dli_enabled_at()


def test_enable_time_stored_as_sql_null_raises_like_v103(tmp_path: Path) -> None:
    """A dli_enabled_at row holding SQL NULL (impossible in V1.0.x's own NOT NULL schema, possible in an uploaded
    file): peek_dli_enabled_at raises, so the alpha parser must not read it as "missing" (review N-4)."""
    path = tmp_path / "v1.sqlite3"
    sqlite3.connect(path).executescript(
        "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT);"
        "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',NULL,'x');"
    )
    database = ParDatabase(path)
    with pytest.raises(TypeError):
        database.peek_dli_enabled_at()
    stored = SnapshotDli(path).enabled_at_value()
    assert stored == (True, None)
    with pytest.raises(RecordUnreadable):
        parse_enabled_at(stored)
