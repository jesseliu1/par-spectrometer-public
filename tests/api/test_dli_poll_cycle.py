"""Allowed gap of API-10 from the snapshot's own poll cycle (D-204 question 1 decided D; boundaries D-206).

V1.0.3 integrates with max(120 s, poll cycle + 60 s) where the poll cycle is the configuration in effect when the
page is drawn (DLI-010, DLI-013). Tier 0 does not read the V1.0.x configuration; every successful record written by
V1.0.2 and later carries the cycle in effect when it was acquired (quality_json.poll_cycle_seconds, written by
PollingCoordinator from effective_poll_cycle_seconds()). The API takes it from the latest successful record of the
period up to the cutoff, or the latest one before the period when the period has none; a missing or unusable value
(V1.0.0-era records, non-numbers, values outside 40–3600 s) falls back to the default 60 s of option A.

Expected totals are closed forms of constant values, never taken from the code under test.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.math_ops import software_metrics

from .conftest import RAW_FLAT, failed_record, legacy_database, record, register_device
from .test_dli import PERIOD_START, URL, source_db, stamp

pytestmark = [pytest.mark.unit, pytest.mark.spec("DLI-010 DLI-013")]
FLAT_PPFD = software_metrics(RAW_FLAT, 3)["ppfd"]
MORNING = datetime(2026, 10, 18, 7, 0)  # inside the current period (06:26:30 → next day), NOW is 09:30


def quality(poll_cycle: object = None, **extra: object) -> str:
    content: dict[str, Any] = {"strategy": "single_capture", "acquisition_status": "completed", **extra}
    if poll_cycle is not None:
        content["poll_cycle_seconds"] = poll_cycle
    return json.dumps(content)


def every(first: datetime, seconds: int, count: int, poll_cycle: object = None) -> list[dict[str, Any]]:
    return [
        record(stamp(first + timedelta(seconds=seconds * index)), quality_json=quality(poll_cycle))
        for index in range(count)
    ]


def dli(client: TestClient, tmp_path: Path, records: list[dict[str, Any]], **params: str) -> dict[str, Any]:
    register_device(client, source_db(tmp_path / "v1" / "长周期.sqlite3", records))
    response = client.get(URL, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ppfd(body: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = body["metrics"][0]["summary"]
    return summary


def test_long_cycle_site_is_integrated_not_reported_as_gaps(client: TestClient, tmp_path: Path) -> None:
    """A site polling every 300 s: 13 records 5 minutes apart. With the default 60 s every interval (300 s) would
    exceed the 120 s allowed gap and the page would show "有效数据不足"; V1.0.3 at that site allows 360 s."""
    body = dli(client, tmp_path, every(MORNING, 300, 13, poll_cycle=300.0))
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"]) == (300.0, 360.0)
    assert body["poll_cycle_source"] == "record"
    assert body["poll_cycle_record_at"] == "2026-10-18T08:00:00.000"
    assert body["gap_text"] == "允许间隔 360 秒（按轮询周期 300 秒计，取自 2026-10-18 08:00:00.000 的采集记录）"
    summary = ppfd(body)
    assert summary["covered_seconds"] == 12 * 300
    assert math.isclose(summary["total"], FLAT_PPFD * 3600 / 1e6, rel_tol=1e-12)
    assert summary["state"] == "部分累计"  # the head gap 06:26:30 → 07:00 and the 1.5 h tail stay gaps
    assert body["metrics"][0]["series"]["cumulative"].count(None) == 0


def test_records_without_the_field_fall_back_to_60_seconds(client: TestClient, tmp_path: Path) -> None:
    """V1.0.0-era records carry no poll cycle: the default 60 s (option A) applies, so 300 s spacing is no data."""
    body = dli(client, tmp_path, every(MORNING, 300, 13))
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"], body["poll_cycle_source"]) == (60.0, 120.0, "default")
    assert body["poll_cycle_record_at"] == "2026-10-18T08:00:00.000"
    assert body["gap_text"] == (
        "允许间隔 120 秒（按默认轮询周期 60 秒计：2026-10-18 08:00:00.000 的采集记录中没有可用的轮询周期）"
    )
    assert (ppfd(body)["covered_seconds"], ppfd(body)["state"]) == (0, "有效数据不足")


@pytest.mark.parametrize(
    "value",
    [
        "300",  # a string, not a number as V1.0.x writes it
        True,
        0,
        -300,
        39.9,  # below MIN_POLL_CYCLE_SECONDS: V1.0.x never writes it
        3600.5,  # above MAX_POLL_CYCLE_SECONDS
        float("nan"),  # json.dumps writes NaN, json.loads reads it back
        float("inf"),
        [300],
        10**400,  # a valid JSON integer too large for float(): OverflowError must fall back, not 500 (review M-1)
    ],
    ids=["string", "bool", "zero", "negative", "below-min", "above-max", "nan", "inf", "list", "huge-int"],
)
def test_unusable_recorded_values_fall_back_to_60_seconds(client: TestClient, tmp_path: Path, value: object) -> None:
    records = every(MORNING, 300, 12, poll_cycle=300.0) + every(MORNING + timedelta(hours=1), 60, 1, poll_cycle=value)
    body = dli(client, tmp_path, records)
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"]) == (60.0, "default")
    assert body["poll_cycle_record_at"] == "2026-10-18T08:00:00.000"


@pytest.mark.parametrize("stored", [None, "{not json", json.dumps([1, 2]), json.dumps("300")])
def test_unreadable_quality_json_falls_back_to_60_seconds(
    client: TestClient, tmp_path: Path, stored: str | None
) -> None:
    records = every(MORNING, 300, 12, poll_cycle=300.0)
    records.append(record("2026-10-18T08:00:00.000", quality_json=stored, dli_eligible=1))
    body = dli(client, tmp_path, records)
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"]) == (60.0, "default")


@pytest.mark.parametrize("value", [40, 3600.0], ids=["min", "max"])
def test_bounds_of_the_recorded_cycle_are_accepted(client: TestClient, tmp_path: Path, value: float) -> None:
    body = dli(client, tmp_path, every(MORNING, 60, 2, poll_cycle=value))
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"]) == (float(value), max(120.0, value + 60.0))


def test_mixed_cycles_use_the_latest_record_for_the_whole_period(client: TestClient, tmp_path: Path) -> None:
    """60 s at first, then the site switched to 300 s: like V1.0.3 drawing with the configuration now in effect,
    one allowed gap (360 s) applies to the whole period, so both parts are integrated without a break."""
    first = every(MORNING, 60, 31, poll_cycle=60.0)  # 07:00–07:30
    later = every(MORNING + timedelta(minutes=35), 300, 6, poll_cycle=300.0)  # 07:35–08:00
    body = dli(client, tmp_path, first + later)
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"]) == (300.0, 360.0)
    summary = ppfd(body)
    assert summary["covered_seconds"] == 30 * 60 + 300 + 5 * 300
    assert body["metrics"][0]["series"]["cumulative"].count(None) == 0


def test_mixed_cycles_switched_back_to_60_seconds_break_the_long_intervals(client: TestClient, tmp_path: Path) -> None:
    """300 s first, then 60 s: the latest record says 60 s, so the earlier 300 s intervals exceed 120 s and are
    not integrated, as V1.0.3 does once the configuration is 60 s again."""
    first = every(MORNING, 300, 7, poll_cycle=300.0)  # 07:00–07:30
    later = every(MORNING + timedelta(minutes=31), 60, 30, poll_cycle=60.0)  # 07:31–08:00
    body = dli(client, tmp_path, first + later)
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"]) == (60.0, 120.0)
    summary = ppfd(body)
    assert summary["covered_seconds"] == 60 + 29 * 60  # 07:30 → 07:31, then the 60 s part
    assert summary["state"] == "部分累计"


def test_failed_records_and_records_after_the_cutoff_are_not_consulted(client: TestClient, tmp_path: Path) -> None:
    records = every(MORNING, 300, 13, poll_cycle=300.0)
    records.append(failed_record("2026-10-18T08:30:00.000"))  # success = 0: not a poll cycle source
    records.append(record("2026-10-18T10:00:00.000", quality_json=quality(60.0)))  # after NOW (09:30)
    body = dli(client, tmp_path, records)
    assert (body["poll_cycle_seconds"], body["poll_cycle_record_at"]) == (300.0, "2026-10-18T08:00:00.000")


def test_past_period_uses_its_own_latest_record(client: TestClient, tmp_path: Path) -> None:
    """A past period is judged with the cycle recorded inside it, not with a later change of the site."""
    yesterday = every(datetime(2026, 10, 17, 8, 0), 300, 13, poll_cycle=300.0)
    today = every(MORNING, 60, 10, poll_cycle=60.0)
    body = dli(client, tmp_path, yesterday + today, date="2026-10-17")
    assert (body["poll_cycle_seconds"], body["poll_cycle_record_at"]) == (300.0, "2026-10-17T09:00:00.000")
    assert ppfd(body)["covered_seconds"] == 12 * 300
    current = client.get(URL).json()
    assert (current["poll_cycle_seconds"], current["poll_cycle_record_at"]) == (60.0, "2026-10-18T07:09:00.000")


def test_period_without_records_uses_the_latest_record_before_it(client: TestClient, tmp_path: Path) -> None:
    body = dli(client, tmp_path, every(datetime(2026, 10, 16, 12, 0), 300, 3, poll_cycle=600.0))
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"]) == (600.0, 660.0)
    assert body["poll_cycle_record_at"] == "2026-10-16T12:10:00.000"
    assert stamp(PERIOD_START) > body["poll_cycle_record_at"]


def test_snapshot_without_any_successful_record_uses_the_default(client: TestClient, tmp_path: Path) -> None:
    body = dli(client, tmp_path, [failed_record("2026-10-18T07:00:00.000")])
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"], body["poll_cycle_record_at"]) == (
        60.0,
        "default",
        None,
    )
    assert body["gap_text"] == "允许间隔 120 秒（按默认轮询周期 60 秒计：本周期及之前没有成功的采集记录）"


def test_v100_database_without_quality_json_uses_the_default(client: TestClient, tmp_path: Path) -> None:
    register_device(client, legacy_database(tmp_path / "v1" / "old.sqlite3"))
    body = client.get(URL).json()
    assert (body["poll_cycle_seconds"], body["max_gap_seconds"], body["poll_cycle_source"]) == (60.0, 120.0, "default")
