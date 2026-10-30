"""D-126 / DEF-14: legacy records marked "复核未完成" are not counted toward DLI (DLI-007, DLI-021).

Rule (docs/spec/pending-decisions.md D-126, owner 2026-10-17): a legacy record (dli_eligible IS NULL) whose
quality_json says the review is incomplete (`confirmed` is JSON false, not a single-capture record) is not
counted; a legacy record without any review information is counted as before; new records follow
dli_eligible. "Review incomplete" is decided the same way as MainWindow._show_history_details shows
"复核未完成". The filter applies only when the samples are read; stored rows are never rewritten (R-4-2).

Both DLI sampling paths in product code are covered: ParDatabase.dli_samples (the DLI page) and
ParDatabase.dli_minute_metrics.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from par_app.database import ParDatabase

pytestmark = pytest.mark.unit

# quality_json content as the V1.0.x dual-capture coordinator wrote it for an unconfirmed round
# (the old repository `_capture_once`: confirmed=False, verification_status='incomplete'). The cases below store it
# with dli_eligible NULL, which is constructed by hand: the known V1.0.x coordinators wrote quality_json and
# dli_eligible in the same INSERT (an unconfirmed round got dli_eligible=0), so no known version produced this
# combination. It can arise only from manual edits or an unknown build (D-126 scope, see docs/CHANGELOG.md).
DUAL_CAPTURE_UNCONFIRMED = json.dumps(
    dict(
        round_started_at="2026-09-30T07:46:00",
        groups=[dict(group=1, started_at="2026-09-30T07:46:00", finished_at="2026-09-30T07:46:08", ppfd=812.5)],
        selected_group=1,
        confirmed=False,
        third_reason=None,
        fallback_reason="设备通信超时，已用完本次访问预算",
        attempted_groups=2,
        timed_out=True,
        completed_groups=1,
        first_ppfd=812.5,
        second_ppfd=None,
        verification_status="incomplete",
        selected_started_at="2026-09-30T07:46:00",
        selected_finished_at="2026-09-30T07:46:08",
        poll_cycle_seconds=60.0,
    ),
    ensure_ascii=False,
)

# id: (success, dli_eligible, quality_json, expected eligible)
CASES: dict[str, tuple[int, int | None, str | None, int]] = {
    # legacy, no review information -> counted as before (D-126 "没有任何复核信息的旧记录照旧计入")
    "legacy_no_quality": (1, None, None, 1),
    "legacy_empty_string": (1, None, "", 1),
    "legacy_malformed_json": (1, None, '{"confirmed": false', 1),
    "legacy_json_null": (1, None, "null", 1),
    "legacy_json_array": (1, None, "[false]", 1),
    "legacy_no_confirmed_key": (1, None, '{"selected_group": 1}', 1),
    "legacy_confirmed_null": (1, None, '{"confirmed": null}', 1),
    "legacy_confirmed_zero": (1, None, '{"confirmed": 0}', 1),
    "legacy_confirmed_string": (1, None, '{"confirmed": "false"}', 1),
    "legacy_confirmed_true": (1, None, '{"confirmed": true}', 1),
    # legacy, marked review incomplete -> not counted
    "legacy_confirmed_false": (1, None, '{"confirmed": false}', 0),
    "legacy_dual_capture_unconfirmed": (1, None, DUAL_CAPTURE_UNCONFIRMED, 0),
    "legacy_confirmed_false_with_nan": (1, None, '{"confirmed": false, "poll_cycle_seconds": NaN}', 0),
    # single-capture records never show "复核未完成" (ACQ-006), so the flag does not apply to them
    "legacy_single_capture_confirmed_false": (1, None, '{"strategy": "single_capture", "confirmed": false}', 1),
    # failed records never count
    "legacy_failed": (0, None, None, 0),
    "legacy_failed_confirmed_true": (0, None, '{"confirmed": true}', 0),
    # new records follow dli_eligible only
    "new_eligible_confirmed_false": (1, 1, '{"confirmed": false}', 1),
    "new_ineligible_confirmed_true": (1, 0, '{"confirmed": true}', 0),
    "new_ineligible_no_quality": (1, 0, None, 0),
}

DAY = ("2026-09-18", "2026-09-19", "2026-09-17")


def _save(database: ParDatabase, stamp: str, success: int, eligible: int | None, quality: str | None) -> None:
    database.save_acquisition(
        dict(
            acquired_at=f"2026-09-18T{stamp}",
            success=success,
            elapsed_ms=1,
            dli_eligible=eligible,
            quality_json=quality,
            software_metrics_json='{"ppfd": 100}',
        )
    )


@pytest.mark.spec("DLI-007 DLI-021")
@pytest.mark.parametrize("case", list(CASES))
def test_dli_samples_eligibility_of_legacy_and_new_records(tmp_path: Path, case: str) -> None:
    success, eligible, quality, expected = CASES[case]
    database = ParDatabase(tmp_path / "par.sqlite3")
    _save(database, "08:00:00", success, eligible, quality)
    rows = database.dli_samples(*DAY)
    assert [row["eligible"] for row in rows] == [expected]


@pytest.mark.spec("DLI-007 DLI-021")
@pytest.mark.parametrize("case", list(CASES))
def test_dli_minute_metrics_uses_the_same_eligibility(tmp_path: Path, case: str) -> None:
    success, eligible, quality, expected = CASES[case]
    database = ParDatabase(tmp_path / "par.sqlite3")
    _save(database, "08:00:00", success, eligible, quality)
    _save(database, "08:00:30", 1, 1, None)  # a new eligible record in the same minute
    minutes = database.dli_minute_metrics(*DAY)
    assert [row["samples"] for row in minutes] == [1 + expected]


@pytest.mark.spec("DLI-007 DLI-012 DLI-021")
def test_unconfirmed_legacy_record_cuts_the_segment_in_order(tmp_path: Path) -> None:
    database = ParDatabase(tmp_path / "par.sqlite3")
    _save(database, "08:00:00", 1, None, None)
    _save(database, "08:01:00", 1, None, DUAL_CAPTURE_UNCONFIRMED)
    _save(database, "08:02:00", 1, None, '{"confirmed": true}')
    _save(database, "08:03:00", 1, 1, None)
    rows = database.dli_samples(*DAY)
    assert [(row["timestamp"][11:], row["eligible"]) for row in rows] == [
        ("08:00:00", 1),
        ("08:01:00", 0),
        ("08:02:00", 1),
        ("08:03:00", 1),
    ]


def _dump(path: Path) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with sqlite3.connect(path) as con:
        schema = con.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name").fetchall()
        rows = con.execute("SELECT * FROM acquisitions ORDER BY id").fetchall()
    return schema, rows


@pytest.mark.spec("DLI-007 DLI-021 CONF-025")
def test_filter_does_not_rewrite_history_or_schema(tmp_path: Path) -> None:
    """R-4-2 (3): quality_json and dli_eligible of old records stay exactly as stored; no schema change."""
    path = tmp_path / "par.sqlite3"
    database = ParDatabase(path)
    for index, (success, eligible, quality, _expected) in enumerate(CASES.values()):
        _save(database, f"08:{index:02d}:00", success, eligible, quality)
    before = _dump(path)
    database.dli_samples(*DAY)
    database.dli_minute_metrics(*DAY)
    ParDatabase(path).dli_samples(*DAY)  # reopening (initialize) must not touch the rows either
    assert _dump(path) == before
