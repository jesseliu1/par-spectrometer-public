"""Contract tests of API-10 GET /api/v0/devices/{key}/dli (api-contract-v0 sections 2 and 5).

Normal answer, empty period, a period boundary (sunrise) and a past period, interruptions, an unreadable snapshot,
wrong parameters and a missing token. Every database is synthetic (R-4-7). Expected totals are closed-form
(constant values) so they do not come from the code under test; the services/golden comparison is in
test_golden_dli_api.py and the V1.0.3 window comparison in test_dli_parity.py.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.application.paths import AlphaPaths
from par_app.database import ParDatabase
from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_app.math_ops import software_metrics
from par_app.services import dli as dli_service

from .conftest import (
    AUTH,
    HOST,
    NOW,
    RAW_FLAT,
    TOKEN,
    assert_read_only,
    error_of,
    failed_record,
    legacy_database,
    record,
    register_device,
    v1_database,
)

pytestmark = pytest.mark.unit
URL = "/api/v0/devices/p1/dli"
LOCAL_NOW = NOW.replace(tzinfo=None)  # 2026-10-18 09:30 Beijing
BEIJING = (39.9042, 116.4074)
PERIOD_START, PERIOD_END = dli_service.dli_period(LOCAL_NOW, BEIJING)  # 10-18 06:26:30 → 10-19 06:26:30
FLAT_PPFD = software_metrics(RAW_FLAT, 3)["ppfd"]
ENABLED_AT = "2026-10-01T00:00:00.000"
METRICS = ["ppfd", "mccree_ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd"]


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def minutes(first: datetime, count: int) -> list[str]:
    return [stamp(first + timedelta(minutes=index)) for index in range(count)]


def source_db(
    path: Path, records: list[dict[str, Any]], *, enabled_at: str | None = ENABLED_AT, **settings: str
) -> Path:
    v1_database(path, records)
    database = ParDatabase(path)
    with database.connect() as con:
        if enabled_at is not None:
            con.execute(
                "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',?,?)",
                (json.dumps(enabled_at), enabled_at),
            )
        for key, value in settings.items():
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES(?,?,?)", (key, value, ENABLED_AT))
    return path


def interrupt(path: Path, occurred_at: str, reason: str) -> None:
    with ParDatabase(path).connect() as con:
        con.execute("INSERT INTO dli_interruptions(occurred_at,reason) VALUES(?,?)", (occurred_at, reason))


def thirty_minutes(tmp_path: Path, *, enabled_at: str | None = ENABLED_AT, **settings: str) -> Path:
    """30 flat records one minute apart from 07:00, all inside the current period."""
    first = datetime(2026, 10, 18, 7, 0)
    return source_db(
        tmp_path / "v1" / "温室.sqlite3", [record(t) for t in minutes(first, 30)], enabled_at=enabled_at, **settings
    )


@pytest.mark.spec("DLI-008 DLI-010 DLI-015 DLI-022 DLI-031 DLI-032 DLI-034 DLI-037 DLI-039 DLI-040 DLI-044 UI-178")
def test_normal_answer_has_every_field_and_the_v103_numbers(client: TestClient, tmp_path: Path) -> None:
    register_device(client, thirty_minutes(tmp_path), name="东区")
    response = client.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "live_ro" and body["as_of"] == "2026-10-18T09:30:00.000"
    assert body["device"] == {"key": "p1", "name": "东区"} and body["requested_date"] is None
    assert body["period"] == {
        "start": stamp(PERIOD_START),
        "end": stamp(PERIOD_END),
        "date": "2026-10-18",
        "current": True,
        "text": f"积分周期：{PERIOD_START:%Y-%m-%d %H:%M} → {PERIOD_END:%Y-%m-%d %H:%M}"
        "（北京时间，日出起算，固定24小时）",
    }
    assert PERIOD_END - PERIOD_START == timedelta(days=1)
    assert body["location"] == {
        "latitude": 39.9042,
        "longitude": 116.4074,
        "stored": False,
        "coordinates_text": "纬度 39.9042 °N，经度 116.4074 °E",
        "text": "已保存位置：纬度 39.9042 °N，经度 116.4074 °E\nDLI启用时间：2026-10-01 00:00:00.000",
    }
    assert body["enabled"] == {"at": ENABLED_AT, "stored": True, "text": "2026-10-01 00:00:00.000"}
    assert (body["observed_until"], body["poll_cycle_seconds"], body["max_gap_seconds"]) == (
        "2026-10-18T09:30:00.000",
        60.0,
        120.0,
    )
    assert body["paused"] is False and body["interruptions"] == []
    assert [metric["key"] for metric in body["metrics"]] == METRICS
    ppfd = body["metrics"][0]
    assert ppfd["title"] == "PPFD-DLI（400–700 nm）"
    expected = FLAT_PPFD * 29 * 60 / 1e6  # closed form: constant value over 29 one-minute intervals
    summary = ppfd["summary"]
    assert math.isclose(summary["total"], expected, rel_tol=1e-12)
    assert summary["covered_seconds"] == 29 * 60
    assert summary["first_valid"] == "2026-10-18T07:00:00.000"
    assert summary["integrated_until"] == summary["last_valid"] == "2026-10-18T07:29:00.000"
    assert summary["cutoff"] == "2026-10-18T09:30:00.000"
    elapsed = (LOCAL_NOW - PERIOD_START).total_seconds()
    assert math.isclose(summary["coverage"], 29 * 60 / elapsed, rel_tol=1e-12)
    assert (summary["state"], summary["stale"]) == ("部分累计", True)  # head gap > 120 s, then no data for 2 h
    assert ppfd["header"]["total_text"] == f"已累计：{expected:.3f} mol·m⁻²"
    assert ppfd["header"]["state_text"] == "部分累计 · 数据未更新（2时01分00秒）"
    assert ppfd["header"]["state_level"] == "warn"
    assert ppfd["header"]["times_text"] == "首个有效：10-18 07:00:00　累计截至：10-18 07:29:00"
    assert math.isclose(ppfd["y_max"], summary["total"] * 1.15, rel_tol=1e-12)
    series = ppfd["series"]
    assert series["times"] == minutes(datetime(2026, 10, 18, 7, 0), 30)
    assert series["offsets_seconds"][0] == (datetime(2026, 10, 18, 7, 0) - PERIOD_START).total_seconds()
    assert series["cumulative"][0] == 0.0 and math.isclose(series["cumulative"][-1], expected, rel_tol=1e-12)
    ticks = body["ticks"]
    assert ticks[0]["offset_seconds"] == 0.0 and ticks[-1]["offset_seconds"] == 86400.0
    assert [tick["text"] for tick in ticks if "\n" in tick["text"]] == [
        f"{PERIOD_START:%m-%d\n%H:%M}",
        "10-19\n00:00",
        f"{PERIOD_END:%m-%d\n%H:%M}",
    ]


@pytest.mark.spec("DLI-034 DLI-035")
def test_period_without_records_is_200_with_no_data_states(client: TestClient, tmp_path: Path) -> None:
    source = source_db(tmp_path / "v1" / "空.sqlite3", [record("2026-10-10T12:00:00.000")])
    register_device(client, source)
    body = client.get(URL).json()
    assert body["interruptions"] == []
    for metric in body["metrics"]:
        assert metric["summary"]["state"] == "有效数据不足"
        assert metric["summary"]["covered_seconds"] == 0
        assert metric["header"]["total_text"] == "已累计：— mol·m⁻²"
        assert (metric["header"]["state_text"], metric["header"]["state_level"]) == ("有效数据不足", "muted")
        assert metric["series"] == {"times": [], "offsets_seconds": [], "cumulative": []}
        assert metric["y_max"] == 0.001


@pytest.mark.spec("DLI-015 DLI-016 DLI-033")
def test_records_across_sunrise_belong_to_their_own_period(client: TestClient, tmp_path: Path) -> None:
    """Records every minute 05:30–07:29 on 10-18: the current period starts at 06:26:30, the past period of 10-17
    ends there. The date parameter picks the period in progress at the end of that day."""
    stamps = minutes(datetime(2026, 10, 18, 5, 30), 120)
    register_device(client, source_db(tmp_path / "v1" / "跨.sqlite3", [record(t) for t in stamps]))
    current = client.get(URL).json()["metrics"][0]["series"]["times"]
    assert current == [t for t in stamps if t >= stamp(PERIOD_START)]
    past = client.get(URL, params={"date": "2026-10-17"}).json()
    start, end = dli_service.dli_period(datetime(2026, 10, 17, 23, 59, 59, 999000), BEIJING)
    assert (past["period"]["start"], past["period"]["end"]) == (stamp(start), stamp(end))
    assert (past["period"]["date"], past["period"]["current"], past["requested_date"]) == (
        "2026-10-17",
        False,
        "2026-10-17",
    )
    summary = past["metrics"][0]["summary"]
    assert summary["cutoff"] == stamp(end)  # a finished period counts up to its end
    assert past["metrics"][0]["series"]["times"] == [t for t in stamps if t < stamp(end)]
    assert summary["coverage"] == pytest.approx(summary["covered_seconds"] / 86400, rel=1e-12)
    today = client.get(URL, params={"date": "2026-10-18"}).json()
    assert today["period"] == client.get(URL).json()["period"]


NEW_YORK = (40.7128, -74.006)  # sunrise about 19:08 Beijing time
DUNEDIN = (-45.8788, 170.5028)  # sunrise about 01:30 Beijing time


def _client_at(tmp_path: Path, wall: datetime) -> TestClient:
    context = ServiceContext(AlphaPaths(tmp_path / "alpha"), FakeClock(wall.replace(tzinfo=BEIJING_TZ)))
    return TestClient(create_app(context, token=TOKEN, allowed_hosts=(HOST,)), base_url=f"http://{HOST}", headers=AUTH)


def _located(tmp_path: Path, location: tuple[float, float]) -> Path:
    stored = json.dumps({"latitude": location[0], "longitude": location[1]})
    return thirty_minutes(tmp_path, dli_location=stored)


@pytest.mark.spec("DLI-015 DLI-022")
@pytest.mark.parametrize(
    ("location", "wall"),
    [
        (BEIJING, datetime(2026, 10, 18, 3, 0)),  # before today's sunrise in Beijing
        (NEW_YORK, datetime(2026, 10, 18, 12, 0)),  # far west: today's "sunrise" is in the Beijing evening
        (DUNEDIN, datetime(2026, 10, 18, 1, 0)),  # far east: today's sunrise is just after Beijing midnight
    ],
)
def test_date_today_is_the_period_in_progress_now_even_before_sunrise(
    tmp_path: Path, location: tuple[float, float], wall: datetime
) -> None:
    """PR #47 review M-1: date=today must not give the period that starts at a later sunrise today (a future
    period shown as ended and empty); today is read at the present moment, like no date."""
    with _client_at(tmp_path, wall) as client:
        register_device(client, _located(tmp_path, location))
        today = client.get(URL, params={"date": wall.date().isoformat()}).json()
        current = client.get(URL).json()
    start, end = dli_service.dli_period(wall, location)
    assert start <= wall < end
    assert today["period"] == current["period"]
    assert (today["period"]["start"], today["period"]["current"]) == (stamp(start), True)
    assert today["metrics"][0]["summary"]["cutoff"] == stamp(wall)


@pytest.mark.spec("DLI-015 DLI-022")
@pytest.mark.parametrize("location", [NEW_YORK, DUNEDIN])
def test_past_date_at_a_far_longitude_is_the_period_in_progress_at_the_end_of_that_day(
    tmp_path: Path, location: tuple[float, float]
) -> None:
    wall = datetime(2026, 10, 18, 12, 0)
    with _client_at(tmp_path, wall) as client:
        register_device(client, _located(tmp_path, location))
        past = client.get(URL, params={"date": "2026-10-16"}).json()
    start, end = dli_service.dli_period(datetime(2026, 10, 16, 23, 59, 59, 999000), location)
    assert start.date().isoformat() == "2026-10-16"  # that day's sunrise, also in the Beijing evening
    assert (past["period"]["start"], past["period"]["end"], past["period"]["current"]) == (
        stamp(start),
        stamp(end),
        False,
    )


@pytest.mark.spec("DLI-005 DLI-011 DLI-012 DLI-046 DLI-049")
def test_interruptions_are_listed_and_break_the_curve(client: TestClient, tmp_path: Path) -> None:
    source = thirty_minutes(tmp_path)
    interrupt(source, "2026-10-18T07:10:30.000", "恢复命令未确认")
    interrupt(source, "2026-10-17T07:10:30.000", "上一周期")
    interrupt(source, "2026-09-30T07:10:30.000", "启用前")
    ParDatabase(source).save_acquisition(failed_record("2026-10-18T07:20:30.000"))
    register_device(client, source)
    body = client.get(URL).json()
    assert body["interruptions"] == [
        {
            "occurred_at": "2026-10-18T07:10:30.000",
            "occurred_at_text": "2026-10-18 07:10:30.000",
            "reason": "恢复命令未确认",
        }
    ]
    ppfd = body["metrics"][0]
    assert ppfd["series"]["cumulative"].count(None) == 2  # the interruption row and the failed record
    assert ppfd["summary"]["state"] == "部分累计"
    # 29 intervals minus 07:10–07:11 (interruption) and 07:20–07:21 (failed record); the rest adds up (DLI-011)
    assert math.isclose(ppfd["summary"]["total"], FLAT_PPFD * 27 * 60 / 1e6, rel_tol=1e-12)


@pytest.mark.spec("DLI-014 DLI-046")
def test_interruption_inside_the_period_but_before_the_enable_time_is_not_listed(
    client: TestClient, tmp_path: Path
) -> None:
    """ParDatabase bounds interruptions by the enable time as well as the period; so must the snapshot read
    (PR #47 review N-3 survivor 1: the period bound alone would also pass the older tests)."""
    source = thirty_minutes(tmp_path, enabled_at="2026-10-18T07:05:00.000")
    interrupt(source, "2026-10-18T07:00:30.000", "周期内，启用前")  # after the 06:26:30 period start
    interrupt(source, "2026-10-18T07:10:30.000", "启用后")
    register_device(client, source)
    body = client.get(URL).json()
    assert [row["reason"] for row in body["interruptions"]] == ["启用后"]
    assert body["metrics"][0]["summary"]["first_valid"] == "2026-10-18T07:05:00.000"


@pytest.mark.spec("DLI-037 DLI-043")
def test_lone_valid_record_after_a_long_gap_shows_the_newest_valid_time(client: TestClient, tmp_path: Path) -> None:
    """A valid record more than the allowed gap after the previous one moves last_valid but not integrated_until,
    so the header gains the 最新有效 time (PR #47 review N-3 survivor 4)."""
    first = datetime(2026, 10, 18, 7, 0)
    records = [record(t) for t in minutes(first, 30)] + [record("2026-10-18T09:25:00.000")]
    register_device(client, source_db(tmp_path / "v1" / "孤点.sqlite3", records))
    ppfd = client.get(URL).json()["metrics"][0]
    assert ppfd["summary"]["last_valid"] == "2026-10-18T09:25:00.000"
    assert ppfd["summary"]["integrated_until"] == "2026-10-18T07:29:00.000"
    assert (
        ppfd["header"]["times_text"] == "首个有效：10-18 07:00:00　累计截至：10-18 07:29:00　最新有效：10-18 09:25:00"
    )


@pytest.mark.spec("UI-153 DLI-026")
def test_stored_location_moves_the_period(client: TestClient, tmp_path: Path) -> None:
    shanghai = (31.2304, 121.4737)
    location = json.dumps({"latitude": shanghai[0], "longitude": shanghai[1]})
    register_device(client, thirty_minutes(tmp_path, dli_location=location))
    body = client.get(URL).json()
    start, _ = dli_service.dli_period(LOCAL_NOW, shanghai)
    assert body["period"]["start"] == stamp(start) != stamp(PERIOD_START)
    assert body["location"]["stored"] is True
    assert body["location"]["text"].startswith("已保存位置：纬度 31.2304 °N，经度 121.4737 °E")


def _stored_enable_rows(path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        return [
            tuple(row)
            for row in con.execute("SELECT value_json, updated_at FROM app_settings WHERE key='dli_enabled_at'")
        ]


def _schema(path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        return [tuple(row) for row in con.execute("SELECT name, sql FROM sqlite_master ORDER BY name")]


@pytest.mark.spec("DLI-014 DLI-024")
def test_missing_enable_time_is_stored_once_as_v103_does(client: TestClient, tmp_path: Path) -> None:
    """D-228 A (owner 2026-10-27): the first DLI read of a registered device whose database holds no enable time
    stores "now" with V1.0.3's INSERT (ParDatabase.load_dli_enabled_at); nothing else in the database changes."""
    device = register_device(client, thirty_minutes(tmp_path, enabled_at=None))
    path = Path(device["path"])
    schema = _schema(path)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        before_rows = con.execute("SELECT * FROM acquisitions ORDER BY id").fetchall()
        before_settings = con.execute("SELECT * FROM app_settings WHERE key<>'dli_enabled_at' ORDER BY key").fetchall()
    body = client.get(URL).json()
    assert body["enabled"] == {"at": "2026-10-18T09:30:00.000", "stored": True, "text": "2026-10-18 09:30:00.000"}
    assert all(
        metric["summary"]["state"] == "有效数据不足" for metric in body["metrics"]
    )  # earlier records not counted
    assert _stored_enable_rows(path) == [(json.dumps("2026-10-18T09:30:00.000"), "2026-10-18T09:30:00.000")]
    assert ParDatabase(path).peek_dli_enabled_at() == "2026-10-18T09:30:00.000"  # V1.0.3 reads it back the same
    assert _schema(path) == schema
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        assert con.execute("SELECT * FROM acquisitions ORDER BY id").fetchall() == before_rows
        assert (
            con.execute("SELECT * FROM app_settings WHERE key<>'dli_enabled_at' ORDER BY key").fetchall()
            == before_settings
        )


@pytest.mark.spec("DLI-014")
def test_a_stored_enable_time_is_never_replaced(client: TestClient, tmp_path: Path) -> None:
    device = register_device(client, thirty_minutes(tmp_path, enabled_at=None))
    path = Path(device["path"])
    client.get(URL)
    first = _stored_enable_rows(path)
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    context.clock.advance(2 * 3600)  # type: ignore[attr-defined]
    body = client.get(URL).json()
    assert _stored_enable_rows(path) == first and body["enabled"]["at"] == "2026-10-18T09:30:00.000"


def test_a_locked_database_reads_as_now_and_the_next_read_stores(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-1-5: the coordinator holds the write lock past SQLite's wait; the day is shown with "now", nothing is
    written, and the read after the lock is released stores the enable time."""
    from par_app.application import dli_enable

    monkeypatch.setattr(dli_enable, "BUSY_TIMEOUT_SECONDS", 0.05)
    device = register_device(client, thirty_minutes(tmp_path, enabled_at=None))
    path = Path(device["path"])
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")  # what a writer in the middle of a transaction holds
    try:
        response = client.get(URL)
        assert response.status_code == 200, response.text
        assert response.json()["enabled"] == {
            "at": "2026-10-18T09:30:00.000",
            "stored": False,
            "text": "2026-10-18 09:30:00.000",
        }
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert _stored_enable_rows(path) == []
    assert client.get(URL).json()["enabled"]["stored"] is True
    assert _stored_enable_rows(path) == [(json.dumps("2026-10-18T09:30:00.000"), "2026-10-18T09:30:00.000")]


def test_records_after_the_stored_enable_time_count(client: TestClient, tmp_path: Path) -> None:
    """After the first read, records the acquisition saves later are counted (acceptance of #82: DLI on 2.0's data)."""
    device = register_device(client, thirty_minutes(tmp_path, enabled_at=None))
    path = Path(device["path"])
    client.get(URL)
    database = ParDatabase(path)
    for moment in minutes(datetime(2026, 10, 18, 9, 31), 30):
        database.save_acquisition(record(moment))
    context: ServiceContext = client.app.state.context  # type: ignore[attr-defined]
    context.clock.advance(31 * 60)  # type: ignore[attr-defined]
    body = client.get(URL).json()
    assert body["enabled"]["stored"] is True
    assert any(metric["summary"]["state"] != "有效数据不足" for metric in body["metrics"]), body["metrics"]


def test_v100_database_without_dli_tables_or_columns(client: TestClient, tmp_path: Path) -> None:
    register_device(client, legacy_database(tmp_path / "v1" / "old.sqlite3"))
    response = client.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"]["stored"] is False and body["location"]["stored"] is False
    assert body["interruptions"] == [] and body["metrics"][0]["series"]["times"] == []


def test_unreadable_snapshot_is_503_not_an_empty_answer(client: TestClient, tmp_path: Path) -> None:
    snapshot = register_device(client, thirty_minutes(tmp_path))
    Path(snapshot["path"]).unlink()
    response = client.get(URL)
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "database_unavailable" and error["retryable"] is True
    assert snapshot["path"] in error["message"]


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"dli_enabled_at": "{not json"}, "库中保存的 DLI 启用时间无法读取"),
        ({"dli_location": '{"latitude": NaN, "longitude": 116.4}'}, "库中保存的 DLI 位置无法计算日出"),
    ],
    ids=["enable_time", "location_nan"],
)
def test_unusable_stored_settings_are_500_not_retryable(
    client: TestClient, tmp_path: Path, settings: dict[str, str], message: str
) -> None:
    enabled = None if "dli_enabled_at" in settings else ENABLED_AT
    register_device(client, thirty_minutes(tmp_path, enabled_at=enabled, **settings))
    response = client.get(URL)
    assert response.status_code == 500
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("internal", False)
    assert error["message"].startswith(message)


@pytest.mark.spec("DLI-014")
def test_enable_time_stored_as_sql_null_is_500_like_the_v103_failure(client: TestClient, tmp_path: Path) -> None:
    """A dli_enabled_at row whose value_json is SQL NULL cannot come from V1.0.x (the column is NOT NULL there),
    but a snapshot is an arbitrary uploaded file. V1.0.3 peek_dli_enabled_at raises on it (json.loads(None)), so
    the alpha must not silently read it as "missing enable time" (PR #47 review N-4)."""
    source = thirty_minutes(tmp_path, enabled_at=None)
    with sqlite3.connect(source) as con:
        con.executescript(
            "DROP TABLE app_settings;"
            "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT);"
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',NULL,'x');"
        )
    register_device(client, source)
    response = client.get(URL)
    assert response.status_code == 500
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("internal", False)
    assert error["message"].startswith("库中保存的 DLI 启用时间无法读取")


@pytest.mark.parametrize("value", ["2026-1-01", "2026-02-30", "20261018", "2026-10-19", "0001-01-02", ""])
def test_wrong_date_is_400(client: TestClient, tmp_path: Path, value: str) -> None:
    register_device(client, thirty_minutes(tmp_path))
    response = client.get(URL, params={"date": value})
    assert response.status_code == 400, response.text
    assert error_of(response)["code"] == "invalid_argument"


def test_unknown_and_unconfigured_devices(client: TestClient, tmp_path: Path) -> None:
    register_device(client, thirty_minutes(tmp_path))
    unconfigured = client.get("/api/v0/devices/p2/dli")
    assert unconfigured.status_code == 404 and error_of(unconfigured)["code"] == "device_not_found"
    unknown = client.get("/api/v0/devices/p9/dli")  # not a position at all: a wrong parameter, as for history
    assert unknown.status_code == 400 and error_of(unknown)["code"] == "invalid_argument"


def test_token_is_required(anonymous: TestClient) -> None:
    response = anonymous.get(URL)
    assert response.status_code == 401
    assert error_of(response)["code"] == "unauthenticated"


@pytest.mark.spec("DLI-050 DLI-055 DLI-056")
def test_reading_dli_writes_no_database(client: TestClient, tmp_path: Path) -> None:
    source = thirty_minutes(tmp_path)
    device = register_device(client, source)
    database = Path(device["path"])
    before = hashlib.sha256(source.read_bytes()).hexdigest(), database.read_bytes()
    assert client.get(URL).status_code == 200
    assert client.get(URL, params={"date": "2026-10-17"}).status_code == 200
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before[0]
    assert_read_only(database, before[1])
