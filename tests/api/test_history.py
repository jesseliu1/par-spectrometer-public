"""History replay contract (API-03 devices, API-05 list, API-06 detail, API-07 spectrum) on imported snapshots.

Expected texts are written by hand from the specs (UI-018/030/033/036/048/052, D-154) or compared with the
services layer; the V1.0.3 window parity lives in tests/api/test_history_parity.py.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.services import metrics as metric_service
from tests.api.conftest import (
    DAY,
    RAW_FLAT,
    assert_read_only,
    error_of,
    failed_record,
    legacy_database,
    record,
    register_device,
    v1_database,
)

pytestmark = pytest.mark.unit
LIST = "/api/v0/devices/{key}/acquisitions"
EMPTY_DEVICE = {
    "configured": False,
    "enabled": False,
    "name": "",
    "address_text": None,
    "display_state": "unconfigured",
    "database_name": None,
    "database_path": None,
    "snapshot_id": None,
    "imported_at": None,
}


def _imported(client: TestClient, tmp_path: Path, records: list[dict[str, Any]], **body: object) -> dict[str, Any]:
    return register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", records), **body)


def _page(client: TestClient, key: str = "p1", **params: object) -> httpx.Response:
    return client.get(LIST.format(key=key), params={**DAY, **params})


# ---------------------------------------- API-03 devices


@pytest.mark.spec("UI-255")
def test_devices_are_four_unconfigured_positions_in_tier_0(client: TestClient) -> None:
    body = client.get("/api/v0/devices").json()
    assert (body["tier"], body["source"]) == (0, "live_ro")
    assert [item["key"] for item in body["items"]] == ["p1", "p2", "p3", "p4"]
    for position, item in enumerate(body["items"], start=1):
        assert item == {"key": f"p{position}", "position": position, **EMPTY_DEVICE}


@pytest.mark.spec("UI-255")
def test_each_position_shows_its_registered_database(client: TestClient, tmp_path: Path) -> None:
    first = _imported(client, tmp_path, [record()], name="西区", position=2)
    newest = _imported(client, tmp_path, [record()], name="西区新", position=2)
    items = client.get("/api/v0/devices").json()["items"]
    assert items[1] == {
        "key": "p2",
        "position": 2,
        "configured": True,
        "enabled": True,
        "name": "西区新",
        "address_text": None,
        "display_state": "normal",
        "database_name": Path(newest["path"]).name,
        "database_path": newest["path"],
        "snapshot_id": newest["id"],
        "imported_at": None,
    }
    assert newest["id"] != first["id"]  # another database at the same position: another id (D-208)
    assert [item["configured"] for item in items] == [True, True, False, False]  # p1: the placeholder
    assert (items[0]["name"], items[0]["enabled"]) == ("占位1", False)


# ---------------------------------------- API-05 list


@pytest.mark.spec("UI-020 UI-052")
def test_list_rows_match_the_v1_history_table(client: TestClient, tmp_path: Path) -> None:
    legacy_quality = json.dumps({"confirmed": True})
    snapshot = _imported(
        client,
        tmp_path,
        [
            record("2026-10-01T08:00:00.000", exposure_status=2),  # new single capture, under-exposed
            failed_record("2026-10-01T08:01:00.000"),
            record("2026-10-01T08:02:00.000", exposure_status=1, quality_json=legacy_quality),  # old double read
            record("2026-10-01T08:03:00.000", exposure_status=None, quality_json=None),
        ],
    )
    response = _page(client)
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_id"] == snapshot["id"]
    assert body["range"] == DAY
    assert (body["limit"], body["offset"], body["limit_reached"], body["next_offset"]) == (500, 0, False, None)
    rows = [
        (i["seq"], i["id"], i["acquired_at_text"], i["result_text"], i["exposure_text"], i["exposure_style"])
        for i in body["items"]
    ]
    assert rows == [
        (1, 4, "2026-10-01 08:03:00.000", "成功", "未知", "warn"),
        (2, 3, "2026-10-01 08:02:00.000", "成功", "过曝光", "warn"),
        (3, 2, "2026-10-01 08:01:00.000", "失败", "正常", "normal"),
        (4, 1, "2026-10-01 08:00:00.000", "成功", "欠曝光", "normal"),  # D-154: single capture keeps normal colour
    ]
    assert body["items"][0]["acquired_at"] == "2026-10-01T08:03:00.000"
    assert [i["success"] for i in body["items"]] == [True, True, False, True]
    assert [i["exposure_status"] for i in body["items"]] == [None, 1, 0, 2]


@pytest.mark.spec("UI-048")
def test_range_bounds_are_inclusive_and_passed_on_unchanged(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record(DAY["start"]), record(DAY["end"]), record("2026-10-02T00:00:00.000")])
    body = _page(client).json()
    assert [item["id"] for item in body["items"]] == [2, 1]


def test_empty_range_is_an_empty_list_not_an_error(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    response = _page(client, start="2026-09-01T00:00:00.000", end="2026-09-01T23:59:59.999")
    assert response.status_code == 200
    assert (response.json()["items"], response.json()["limit_reached"]) == ([], False)


def test_empty_database_is_an_empty_list(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [])
    assert _page(client).json()["items"] == []


@pytest.mark.spec("UI-048")
def test_more_than_500_records_fill_one_page_and_report_the_limit(client: TestClient, tmp_path: Path) -> None:
    times = [f"2026-10-01T10:{minute:02d}:{second:02d}.000" for minute in range(9) for second in range(60)]
    _imported(client, tmp_path, [record(at) for at in times[:501]])

    first = _page(client).json()
    assert len(first["items"]) == 500
    assert (first["limit_reached"], first["next_offset"]) == (True, 500)
    assert [first["items"][0]["id"], first["items"][-1]["id"]] == [501, 2]
    assert first["items"][-1]["seq"] == 500

    second = _page(client, offset=500).json()
    assert [(item["seq"], item["id"]) for item in second["items"]] == [(501, 1)]
    assert (second["limit_reached"], second["next_offset"]) == (False, None)

    exactly = _page(client, limit=501)
    assert exactly.status_code == 400
    assert error_of(exactly)["message"] == "参数错误：limit"


def test_exactly_500_records_do_not_report_the_limit(client: TestClient, tmp_path: Path) -> None:
    times = [f"2026-10-01T11:{minute:02d}:{second:02d}.000" for minute in range(9) for second in range(60)]
    _imported(client, tmp_path, [record(at) for at in times[:500]])
    body = _page(client).json()
    assert (len(body["items"]), body["limit_reached"]) == (500, False)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"start": "2026-10-02T00:00:00.000", "end": "2026-10-01T00:00:00.000"}, "开始时间不能晚于结束时间"),
        ({"start": "2026-10-01 00:00:00"}, "参数 start 格式错误"),
        ({"end": "yesterday"}, "参数 end 格式错误"),
        ({"start": "2026-02-30T00:00:00.000"}, "参数 start 不是有效时间"),
        ({"limit": 0}, "参数错误：limit"),
        ({"limit": "many"}, "参数错误：limit"),
        ({"offset": -1}, "参数错误：offset"),
    ],
)
def test_bad_query_parameters_are_invalid_arguments(
    client: TestClient, tmp_path: Path, params: dict[str, Any], message: str
) -> None:
    _imported(client, tmp_path, [record()])
    response = _page(client, **params)
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "invalid_argument" and error["retryable"] is False
    assert error["message"].startswith(message)


def test_missing_range_is_an_invalid_argument(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    response = client.get(LIST.format(key="p1"))
    assert response.status_code == 400
    assert error_of(response)["message"] == "参数错误：start、end"


def test_unknown_position_and_position_without_snapshot(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    invalid = _page(client, key="p5")
    assert invalid.status_code == 400
    missing = _page(client, key="p2")
    assert missing.status_code == 404
    assert error_of(missing)["code"] == "device_not_found"


@pytest.mark.spec("UI-316")
@pytest.mark.parametrize("damage", ["delete", "garbage"])
def test_unreadable_copy_is_unavailable_not_empty(client: TestClient, tmp_path: Path, damage: str) -> None:
    copy = Path(_imported(client, tmp_path, [record()])["path"])
    if damage == "delete":
        copy.unlink()
    else:
        copy.write_bytes(b"\0" * 4096)
    for url in (LIST.format(key="p1"), "/api/v0/devices/p1/acquisitions/1"):
        response = client.get(url, params=DAY)
        assert response.status_code == 503
        error = error_of(response)
        assert (error["code"], error["retryable"]) == ("database_unavailable", True)
        assert str(copy) in error["message"]


def test_the_device_database_is_never_written_by_queries(client: TestClient, tmp_path: Path) -> None:
    database = Path(_imported(client, tmp_path, [record(), failed_record()])["path"])
    before = database.read_bytes()
    _page(client)
    client.get("/api/v0/devices/p1/acquisitions/1")
    client.get("/api/v0/devices/p1/acquisitions/1/spectrum")
    assert_read_only(database, before)


# ---------------------------------------- API-06 detail


@pytest.mark.spec("UI-018 UI-036")
def test_detail_of_a_successful_record(client: TestClient, tmp_path: Path) -> None:
    snapshot = _imported(client, tmp_path, [record()], name="东区")
    response = client.get("/api/v0/devices/p1/acquisitions/1")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_id"] == snapshot["id"]
    assert body["device"] == {"key": "p1", "name": "东区"}
    assert body["header"] == {
        "title": "记录详情 · 东区 · #1",
        "time_text": "2026-10-01 12:00:00.000（北京时间）",
        "status_text": "采集成功 · 单次读取完成",
        "status_level": "ok",
        "exposure_text": "正常",
    }
    assert (body["success"], body["elapsed_text"], body["review_text"]) == (True, "5464.7", "单次读取完成")
    assert [group["title"] for group in body["groups"]] == [
        "常用光量",
        "波段光子通量",
        "光谱比例",
        "光色与峰值",
        "扩展波段光量",
        "特殊显色指数",
        "色度与三刺激值",
    ]
    items = {item["key"]: item for group in body["groups"] for item in group["items"]}
    assert len(items) == 54
    stored = _stored_row(Path(snapshot["path"]))
    assert {key: item["text"] for key, item in items.items()} == metric_service.record_metric_values(stored)
    assert items["lux"] == {"key": "lux", "label": "照度", "unit": "lx", "text": "1234.5"}
    assert items["cct"]["text"] == "5321"
    assert items["x"]["text"] == "0.3300"
    assert items["r1"]["text"] == "—"
    assert body["record"]["exposure_time_us"] == 20000
    assert body["record"]["quality_json"] == stored["quality_json"]


@pytest.mark.spec("UI-030")
def test_detail_of_a_failed_record_clears_metrics_but_keeps_elapsed_and_review(
    client: TestClient, tmp_path: Path
) -> None:
    _imported(client, tmp_path, [failed_record()])
    body = client.get("/api/v0/devices/p1/acquisitions/1").json()
    assert (body["success"], body["elapsed_text"], body["review_text"]) == (False, "10012.5", "未完成采集")
    assert body["header"]["status_text"] == "采集失败"
    assert body["header"]["status_level"] == "error"
    assert {item["text"] for group in body["groups"] for item in group["items"]} == {"—"}
    assert (body["spectrum_state"], body["spectrum"]) == ("none", None)
    assert body["record"]["error_detail"] == "读取超时"


@pytest.mark.spec("UI-037 UI-057")
def test_detail_and_spectrum_carry_the_701_points(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    detail = client.get("/api/v0/devices/p1/acquisitions/1").json()
    spectrum = client.get("/api/v0/devices/p1/acquisitions/1/spectrum").json()
    assert detail["spectrum_state"] == "ok"
    assert spectrum["spectrum"] == detail["spectrum"]
    data = detail["spectrum"]
    assert (data["wavelength_start"], data["wavelength_step"], data["spectral_coefficient"]) == (350, 1, 3)
    assert len(data["points"]) == len(data["values"]) == 701
    assert data["points"] == [float(v) for v in RAW_FLAT]
    assert data["values"] == [1.0] * 701


def test_spectrum_of_a_record_without_one_is_not_found(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [failed_record()])
    response = client.get("/api/v0/devices/p1/acquisitions/1/spectrum")
    assert response.status_code == 404
    assert error_of(response) == {
        "code": "record_not_found",
        "message": "记录 #1 没有可用光谱",
        "retryable": False,
        "detail": "无光谱",
    }


@pytest.mark.parametrize("acquisition_id", ["999", "0", "-3"])
def test_unknown_record_is_not_found(client: TestClient, tmp_path: Path, acquisition_id: str) -> None:
    _imported(client, tmp_path, [record()])
    response = client.get(f"/api/v0/devices/p1/acquisitions/{acquisition_id}")
    assert response.status_code == 404
    assert error_of(response)["code"] == "record_not_found"


def test_non_numeric_record_id_is_an_invalid_argument(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    assert client.get("/api/v0/devices/p1/acquisitions/abc").status_code == 400


def test_legacy_database_without_new_columns(client: TestClient, tmp_path: Path) -> None:
    register_device(client, legacy_database(tmp_path / "v1" / "old.sqlite3"))
    listing = _page(client, start="2026-10-01T00:00:00.000", end="2026-10-02T00:00:00.000").json()
    assert [(i["id"], i["acquired_at_text"], i["exposure_style"]) for i in listing["items"]] == [
        (2, "2026-10-01 16:05:00.000", "warn"),  # old UTC time shown in Beijing time; NULL exposure is 未知
        (1, "2026-10-01 16:00:00.000", "warn"),  # 欠曝光 on an old (not single-capture) record keeps the warning
    ]
    body = client.get("/api/v0/devices/p1/acquisitions/1").json()
    assert body["review_text"] == "未记录"
    assert body["header"]["status_level"] == "warn"
    assert (body["record"]["quality_json"], body["record"]["dli_eligible"]) == (None, None)
    assert {item["key"]: item["text"] for g in body["groups"] for item in g["items"]}["cct"] == "4100"


@pytest.mark.parametrize(
    ("quality", "eligible", "review"),
    [
        (json.dumps({"confirmed": False}), None, "复核未完成"),
        (json.dumps({"confirmed": True}), None, "已完成"),
        (json.dumps({"confirmed": True}), 0, "复核未完成"),
        (None, None, "未记录"),
        ("{not json", None, "未记录"),  # V1.0.3 raised here; D-202
        ("[1, 2]", None, "未记录"),  # V1.0.3 raised here; D-202
    ],
)
def test_review_text_of_legacy_double_read_records(
    client: TestClient, tmp_path: Path, quality: str | None, eligible: int | None, review: str
) -> None:
    _imported(client, tmp_path, [record(quality_json=quality, dli_eligible=eligible)])
    assert client.get("/api/v0/devices/p1/acquisitions/1").json()["review_text"] == review


def test_a_record_with_broken_metrics_is_an_error_and_the_service_keeps_running(
    client: TestClient, tmp_path: Path
) -> None:
    copy = Path(_imported(client, tmp_path, [record(), record("2026-10-01T12:05:00.000")])["path"])
    con = sqlite3.connect(copy)
    con.execute("UPDATE acquisitions SET software_metrics_json='{broken' WHERE id=1")
    con.commit()
    con.close()
    broken = client.get("/api/v0/devices/p1/acquisitions/1")
    assert broken.status_code == 500
    assert error_of(broken)["code"] == "internal"
    assert client.get("/api/v0/devices/p1/acquisitions/2").status_code == 200


def test_a_spectrum_that_is_not_json_is_reported_invalid(client: TestClient, tmp_path: Path) -> None:
    copy = Path(_imported(client, tmp_path, [record()])["path"])
    con = sqlite3.connect(copy)
    con.execute("UPDATE spectra SET raw_points_json='[1,2' WHERE acquisition_id=1")
    con.commit()
    con.close()
    body = client.get("/api/v0/devices/p1/acquisitions/1").json()
    assert (body["spectrum_state"], body["spectrum"]) == ("invalid", None)
    response = client.get("/api/v0/devices/p1/acquisitions/1/spectrum")
    assert response.status_code == 404
    assert error_of(response)["detail"] == "光谱数据无法解析"


def _stored_row(path: Path) -> dict[str, Any]:
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return dict(con.execute("SELECT * FROM acquisitions WHERE id=1").fetchone())
    finally:
        con.close()


def test_an_unexpected_error_is_500_internal_and_logged(
    context: ServiceContext, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from par_app.api.app import create_app
    from tests.api.conftest import AUTH, HOST, TOKEN

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(context.devices, "devices", explode)
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}", headers=AUTH, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v0/devices")
        assert response.status_code == 500
        assert error_of(response) == {
            "code": "internal",
            "message": "服务内部错误，请重试",
            "retryable": True,
            "detail": "RuntimeError",
        }
        assert test_client.get("/api/v0/snapshots").status_code == 200
    assert "unexpected error while serving a request" in caplog.text


# ---------------------------------------- review follow-ups (PR #45 independent review)


def _update_copy(snapshot: dict[str, Any], sql: str) -> None:
    con = sqlite3.connect(snapshot["path"])
    try:
        con.execute(sql)
        con.commit()
    finally:
        con.close()


def test_stored_values_of_an_unexpected_type_are_passed_through(client: TestClient, tmp_path: Path) -> None:
    """Review N-1: SQLite is dynamically typed; a REAL or TEXT in an INTEGER column must not make the detail 500."""
    snapshot = _imported(client, tmp_path, [record()])
    _update_copy(snapshot, "UPDATE acquisitions SET exposure_time_us=12.5, stop_status='n/a' WHERE id=1")
    response = client.get("/api/v0/devices/p1/acquisitions/1")
    assert response.status_code == 200, response.text
    stored = response.json()["record"]
    assert (stored["exposure_time_us"], stored["stop_status"], stored["mcu_time_ms"]) == (12.5, "n/a", 123456)
    assert isinstance(stored["mcu_time_ms"], int)


def test_a_record_the_response_model_cannot_carry_is_unreadable_not_retryable(
    client: TestClient, tmp_path: Path
) -> None:
    """Review N-1: a value no field type accepts (a BLOB) is 500 internal with retryable false, like broken JSON."""
    snapshot = _imported(client, tmp_path, [record(), record("2026-10-01T12:05:00.000")])
    _update_copy(snapshot, "UPDATE acquisitions SET error_detail=X'00FF' WHERE id=1")
    response = client.get("/api/v0/devices/p1/acquisitions/1")
    assert response.status_code == 500
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("internal", False)
    assert client.get("/api/v0/devices/p1/acquisitions/2").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "/api/v0/devices/p1/acquisitions/99999999999999999999",
        "/api/v0/devices/p1/acquisitions/9223372036854775808/spectrum",
        f"{LIST.format(key='p1')}?start={DAY['start']}&end={DAY['end']}&offset=99999999999999999999",
        f"{LIST.format(key='p1')}?start={DAY['start']}&end={DAY['end']}&offset=1e20",
    ],
)
def test_ids_and_offsets_beyond_sqlite_integers_are_invalid_arguments(
    client: TestClient, tmp_path: Path, url: str
) -> None:
    """Review N-2: values past SQLite's 64-bit integer range used to raise OverflowError (500, retryable)."""
    _imported(client, tmp_path, [record()])
    response = client.get(url)
    assert response.status_code == 400
    assert error_of(response)["code"] == "invalid_argument"


def test_the_largest_sqlite_integer_is_still_a_valid_id(client: TestClient, tmp_path: Path) -> None:
    _imported(client, tmp_path, [record()])
    response = client.get("/api/v0/devices/p1/acquisitions/9223372036854775807")
    assert response.status_code == 404
    assert error_of(response)["code"] == "record_not_found"


@pytest.mark.spec("UI-030")
def test_a_failed_record_that_carries_metrics_still_shows_dashes(client: TestClient, tmp_path: Path) -> None:
    """Review N-4 (mutant M17): V1.0.3 shows "—" for every value of a failed record, whatever JSON it carries."""
    _imported(client, tmp_path, [record(success=0)])
    body = client.get("/api/v0/devices/p1/acquisitions/1").json()
    assert body["record"]["software_metrics_json"] is not None
    assert {item["text"] for group in body["groups"] for item in group["items"]} == {"—"}


def test_raw_spectrum_points_keep_their_stored_type(client: TestClient, tmp_path: Path) -> None:
    """Review N-8: integer raw values are serialised as integers ("as stored"), not as 1000.0."""
    _imported(client, tmp_path, [record(raw_points=[1000] * 700 + [12.5])])
    points = client.get("/api/v0/devices/p1/acquisitions/1/spectrum").json()["spectrum"]["points"]
    assert isinstance(points[0], int) and points[0] == 1000
    assert points[-1] == 12.5


@pytest.mark.parametrize(
    "value",
    ["2026-10-01T00:00:00", "2026-10-01T00:00:00.5", "2026-10-01T00:00:00.50", "2026-10-01T00:00:00.000000"],
)
def test_query_times_need_exactly_three_millisecond_digits(client: TestClient, tmp_path: Path, value: str) -> None:
    """Review N-9: the stored times end in .mmm and are compared as text, so the query must use the same form."""
    _imported(client, tmp_path, [record()])
    response = _page(client, end=value)
    assert response.status_code == 400
    assert error_of(response)["message"].startswith("参数 end 格式错误")
