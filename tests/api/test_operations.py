"""Contract tests of the spectrum calculation endpoints (api-contract-v0 API-11..14, API-24, API-25; 13_ section 5).

Two synthetic V1.0.x databases (written by ParDatabase) are imported as the snapshots of p1 and p2. Every expected
number is written out by hand or follows from the raw counts (raw / 10^3); texts are the V1.0.3 texts (copied in
par_app/services/operation_display.py, compared with the real window in test_operations_parity.py).
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.database import format_beijing_time
from par_app.math_ops import combine
from par_app.services import export as export_service
from par_app.services import operation_display as display

from .conftest import NOW, error_of, failed_record, legacy_database, record, register_device, v1_database

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec(
        "UI-155 UI-156 UI-157 UI-197 UI-198 UI-200 UI-207 UI-208 UI-209 UI-211 UI-216 UI-218 UI-219 UI-220 "
        "UI-221 UI-222 UI-268 UI-269 UI-288 MATH-008 MATH-009 MATH-010 MATH-011 MATH-014 MATH-015 MATH-020 "
        "MATH-021 EXP-005 EXP-010 EXP-015 EXP-016 EXP-017 EXP-018 EXP-019 EXP-020 EXP-022 EXP-024 EXP-025 "
        "EXP-026 EXP-027"
    ),
]
RAW_A = [1000 + index for index in range(701)]  # 1.000 … 1.700 mW/nm after / 10^3
RAW_B = [2000] * 701  # 2.000 mW/nm
EAST, WEST = "东区", "西区"


def spectrum_record(at: str, raw: list[int], **overrides: object) -> dict[str, Any]:
    return record(at, raw_points=raw, **overrides)


def east_records() -> list[dict[str, Any]]:
    return [
        spectrum_record("2026-10-01T08:00:00.000", RAW_A),  # id 1
        failed_record("2026-10-01T08:01:00.000"),  # id 2: failed, never a candidate
        spectrum_record("2026-10-01T08:02:00.000", [5] * 700),  # id 3: 700 points, not usable
        spectrum_record("2026-10-01T08:03:00.000", [3000] * 701),  # id 4
    ]


def west_records() -> list[dict[str, Any]]:
    return [
        spectrum_record("2026-10-01T07:59:00.000", RAW_B),  # id 1
        spectrum_record("2026-10-01T08:01:00.000", RAW_B),  # id 2
        spectrum_record("2026-10-01T08:05:00.000", [0] * 701),  # id 3: all zero
    ]


@pytest.fixture
def sources(client: TestClient, tmp_path: Path) -> dict[str, dict[str, Any]]:
    east = v1_database(tmp_path / "v1" / "east.sqlite3", east_records())
    west = v1_database(tmp_path / "v1" / "west.sqlite3", west_records())
    return {
        "p1": register_device(client, east, name=EAST, position=1),
        "p2": register_device(client, west, name=WEST, position=2),
    }


def ref(key: str, record_id: int, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"source": key, "id": record_id}
    if snapshot is not None:
        body["snapshot_id"] = snapshot["id"]
    return body


def values(raw: list[int]) -> list[float]:
    return [value / 1000 for value in raw]


# --- API-25 page texts ------------------------------------------------------------------------------------------


def test_page_gives_the_v1_operations_texts_axis_guide_and_the_export_folder(
    client: TestClient, context: ServiceContext
) -> None:
    body = client.get("/api/v0/operations/page").json()
    assert body["title"] == "光谱计算"  # UI-167
    assert body["operations"] == [
        {"key": "add", "label": "加法 A+B"},
        {"key": "subtract", "label": "减法 A-B"},
        {"key": "divide", "label": "比值 A/B"},
    ]
    assert body["default_operation"] == "add"
    texts = body["texts"]
    assert texts["auto_match_label"] == "B 匹配 A 的最近时间"
    assert "最近不代表同步" in texts["auto_match_tooltip"]
    assert texts["swap_tooltip"] == "交换光谱 A 与 B"  # UI-314
    assert texts["no_spectrum"] == "无可用光谱"
    assert (texts["waiting_heading"], texts["missing_heading"]) == ("等待执行计算", "缺少有效的 A/B 光谱")
    assert body["axis"] == {
        "start_nm": 350,
        "end_nm": 1050,
        "ticks_wide": [350, 400, 500, 600, 700, 800, 900, 1000, 1050],
        "ticks_narrow": [350, 500, 600, 700, 800, 900, 1050],
        "narrow_below_px": 680,
    }
    guide = body["guide"]
    assert guide["title"] == "光谱计算应用说明"  # UI-229
    assert [item["head"] for item in guide["summary"]] == [
        "加法 A+B · 补光组合：",
        "减法 A−B · 补光增量：",
        "比值 A/B · 温室综合透光评估：",
        "比值 A/B · 叶片光谱透射比较：",
    ]  # UI-226
    anchors = {section["anchor"] for section in guide["sections"]}
    assert [item["anchor"] for item in guide["navigation"]] == ["lighting", "greenhouse", "leaf", "display"]
    assert {"lighting", "greenhouse", "leaf", "display"} <= anchors  # UI-231
    links = [link["url"] for section in guide["sections"] for link in section["links"]]
    assert len(links) == 4 and all(url.startswith("https://www.rp-photonics.com/") for url in links)  # UI-250
    assert guide["dialog"] == {"width_px": 960, "height_px": 760, "screen_fraction": 0.9}  # UI-232
    export = body["export"]
    assert [(item["key"], item["label"], item["checked"]) for item in export["formats"]] == [
        ("csv", "CSV", True),
        ("xlsx", "Excel (.xlsx)", False),
    ]
    assert export["directory"] == str(context.paths.exports_dir)  # D-207: the alpha's own output folder


# --- API-11 sources ---------------------------------------------------------------------------------------------


def test_sources_are_the_imported_positions_with_a_first_and_b_second(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.get("/api/v0/operation-sources").json()
    assert [(item["key"], item["device_name"]) for item in body["items"]] == [("p1", EAST), ("p2", WEST)]
    first = body["items"][0]
    assert first["snapshot_id"] == sources["p1"]["id"]
    assert first["source_path"] == sources["p1"]["source_path"]  # UI-265: full path on hover
    assert first["database_path"] == sources["p1"]["path"]
    assert sources["p1"]["source_path"] in first["tooltip"] and sources["p1"]["path"] in first["tooltip"]
    assert (body["initial_a"], body["initial_b"]) == ("p1", "p2")  # UI-156


def test_one_source_gives_a_and_b_the_same_database_and_none_gives_null(client: TestClient, tmp_path: Path) -> None:
    empty = client.get("/api/v0/operation-sources").json()
    assert (empty["items"], empty["initial_a"], empty["initial_b"]) == ([], None, None)
    register_device(client, v1_database(tmp_path / "only.sqlite3", east_records()), name=EAST)
    body = client.get("/api/v0/operation-sources").json()
    assert (body["initial_a"], body["initial_b"]) == ("p1", "p1")


# --- API-12 candidates ------------------------------------------------------------------------------------------


def test_candidates_are_successful_complete_spectra_newest_first(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.get("/api/v0/operation-sources/p1/spectra").json()
    assert body["snapshot_id"] == sources["p1"]["id"]
    assert body["limit"] == 500
    assert [item["id"] for item in body["items"]] == [4, 1]  # failed #2 and 700-point #3 left out
    assert body["items"][0]["label"] == "#4 | 2026-10-01 08:03:00.000"
    assert body["items"][0]["acquired_at"] == "2026-10-01T08:03:00.000"
    assert body["empty_text"] == "无可用光谱"


def test_candidates_stop_at_500_and_keep_an_older_selected_record(client: TestClient, tmp_path: Path) -> None:
    rows = [record(f"2026-10-01T{minute // 60:02d}:{minute % 60:02d}:00.000") for minute in range(503)]
    register_device(client, v1_database(tmp_path / "many.sqlite3", rows), name=EAST)
    listed = client.get("/api/v0/operation-sources/p1/spectra").json()["items"]
    assert len(listed) == 500 and listed[0]["id"] == 503 and listed[-1]["id"] == 4
    kept = client.get("/api/v0/operation-sources/p1/spectra", params={"keep": 2}).json()["items"]
    assert [item["id"] for item in kept[-2:]] == [4, 2]  # UI-204: the selected older record stays listed
    again = client.get("/api/v0/operation-sources/p1/spectra", params={"keep": 600}).json()["items"]
    assert len(again) == 500  # a record that does not exist is not added


def test_candidates_of_a_database_without_usable_spectra_are_empty(client: TestClient, tmp_path: Path) -> None:
    register_device(client, v1_database(tmp_path / "failed.sqlite3", [failed_record()]), name=EAST)
    body = client.get("/api/v0/operation-sources/p1/spectra").json()
    assert body["items"] == []  # UI-269: the page shows 无可用光谱 and cannot calculate


def test_candidates_errors(client: TestClient, sources: dict[str, dict[str, Any]]) -> None:
    assert error_of(client.get("/api/v0/operation-sources/p9/spectra"))["code"] == "invalid_argument"
    assert error_of(client.get("/api/v0/operation-sources/p4/spectra"))["code"] == "device_not_found"
    assert client.get("/api/v0/operation-sources/p1/spectra", params={"keep": "x"}).status_code == 400
    Path(sources["p2"]["path"]).unlink()
    response = client.get("/api/v0/operation-sources/p2/spectra")
    assert response.status_code == 503
    assert error_of(response)["code"] == "database_unavailable"  # never an empty list for a broken copy


# --- API-13 nearest ---------------------------------------------------------------------------------------------


def test_nearest_searches_the_whole_database_and_takes_the_earlier_one_on_a_tie(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.get("/api/v0/operation-sources/p2/nearest", params={"acquired_at": "2026-10-01T08:00:00.000"}).json()
    match = body["match"]
    assert (match["id"], match["label"]) == (1, "#1 | 2026-10-01 07:59:00.000")  # 07:59 and 08:01 tie: earlier
    assert match["time_difference_seconds"] == -60.0
    later = client.get("/api/v0/operation-sources/p2/nearest", params={"acquired_at": "2026-10-01T08:04:00.000"})
    assert later.json()["match"]["id"] == 3


def test_nearest_beyond_the_newest_500_and_with_legacy_utc_times(client: TestClient, tmp_path: Path) -> None:
    rows = [record(f"2026-10-02T{minute // 60:02d}:{minute % 60:02d}:00.000") for minute in range(502)]
    register_device(client, v1_database(tmp_path / "many.sqlite3", rows), name=WEST, position=2)
    old = client.get("/api/v0/operation-sources/p2/nearest", params={"acquired_at": "2026-10-02T00:00:20.000"})
    assert old.json()["match"]["id"] == 1  # UI-198: not limited to the list's 500
    register_device(client, legacy_database(tmp_path / "legacy.sqlite3"), name=EAST, position=1)
    # the legacy record is 08:00 UTC = 16:00 Beijing (UI-197)
    legacy = client.get("/api/v0/operation-sources/p1/nearest", params={"acquired_at": "2026-10-01T15:59:00.000"})
    assert legacy.json()["match"]["id"] == 1
    assert legacy.json()["match"]["time_difference_seconds"] == 60.0


def test_nearest_without_candidates_or_with_an_unreadable_time_is_null(client: TestClient, tmp_path: Path) -> None:
    register_device(client, v1_database(tmp_path / "failed.sqlite3", [failed_record()]), name=EAST)
    empty = client.get("/api/v0/operation-sources/p1/nearest", params={"acquired_at": "2026-10-01T08:00:00.000"})
    assert empty.status_code == 200 and empty.json()["match"] is None
    register_device(client, v1_database(tmp_path / "ok.sqlite3", east_records()), name=WEST, position=2)
    odd = client.get("/api/v0/operation-sources/p2/nearest", params={"acquired_at": "not a time"})
    assert odd.status_code == 200 and odd.json()["match"] is None  # = V1.0.3: no implicit fallback (UI-288)
    assert client.get("/api/v0/operation-sources/p2/nearest").status_code == 400


# --- API-14 inputs ----------------------------------------------------------------------------------------------


def test_inputs_show_both_spectra_on_a_common_axis_with_the_time_difference(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.post(
        "/api/v0/operations/inputs", json={"a": ref("p1", 1, sources["p1"]), "b": ref("p2", 2, sources["p2"])}
    ).json()
    assert body["valid"] is True
    a, b = body["a"], body["b"]
    assert (a["title"], b["title"]) == (f"光谱 A：{EAST} · #1", f"光谱 B：{WEST} · #2")
    assert (a["legend"], b["legend"]) == ("光谱 A", "光谱 B")
    assert a["values"] == values(RAW_A)  # UI-211: not normalised
    assert b["values"] == values(RAW_B)
    expected = (0.0, 2.0 / 0.618)  # union of 0…1.7/0.618 and 0…2/0.618 (UI-209)
    assert a["y_range"] == pytest.approx(expected) and b["y_range"] == pytest.approx(expected)
    assert body["time_difference"]["seconds"] == 60.0
    assert body["time_difference"]["text"] == "采集时间差：B 比 A 晚 60.000 秒"
    assert "不是同步采集" in body["time_difference"]["tooltip"]
    assert body["placeholder"] == {"heading": "等待执行计算", "detail": ""}


def test_inputs_with_a_missing_or_unusable_side_are_not_valid(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.post("/api/v0/operations/inputs", json={"a": ref("p1", 2), "b": None}).json()
    assert body["valid"] is False
    assert (body["a"]["title"], body["b"]["title"]) == ("光谱 A：未选择记录", "光谱 B：未选择记录")
    assert body["a"]["values"] is None and body["a"]["y_range"] is None
    assert body["time_difference"]["text"] == "采集时间差：不可用"
    assert body["placeholder"] == {"heading": "缺少有效的 A/B 光谱", "detail": "A、B 均需成功且完整的光谱记录"}
    one = client.post("/api/v0/operations/inputs", json={"a": ref("p1", 1), "b": ref("p2", 99)}).json()
    assert one["a"]["valid"] is True and one["a"]["y_range"] == pytest.approx((0.0, 1.7 / 0.618))


def test_same_id_in_two_databases_and_same_record_on_both_sides(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    body = client.post("/api/v0/operations/inputs", json={"a": ref("p1", 1), "b": ref("p2", 1)}).json()
    assert (body["a"]["device_name"], body["b"]["device_name"]) == (EAST, WEST)  # UI-157
    same = client.post("/api/v0/operations/inputs", json={"a": ref("p1", 1), "b": ref("p1", 1)}).json()
    assert same["valid"] is True and same["time_difference"]["text"] == "采集时间差：A 与 B 相同"


def test_a_replaced_snapshot_is_reported_not_silently_used(
    client: TestClient, sources: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    stale = ref("p1", 1, sources["p1"])
    register_device(client, v1_database(tmp_path / "newer.sqlite3", east_records()), name=EAST, position=1)
    for path, body in (
        ("/api/v0/operations/inputs", {"a": stale, "b": ref("p2", 1)}),
        ("/api/v0/operations/compute", {"a": stale, "b": ref("p2", 1), "operation": "add"}),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 409
        error = error_of(response)
        assert (error["code"], error["retryable"]) == ("snapshot_changed", False)


# --- API-14 compute ---------------------------------------------------------------------------------------------


def compute(client: TestClient, a: dict[str, Any], b: dict[str, Any], operation: str) -> dict[str, Any]:
    response = client.post("/api/v0/operations/compute", json={"a": a, "b": b, "operation": operation})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_add_and_subtract_are_plotted_whole_with_a_zero_baseline(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    added = compute(client, ref("p1", 1), ref("p2", 2), "add")["result"]
    assert added["values"] == pytest.approx([a + 2.0 for a in values(RAW_A)])
    assert added["plotted"] == added["values"]  # MATH-021: no display filter
    assert (added["title"], added["legend"], added["y_label"]) == ("计算结果：加法 A+B", "计算结果", "功率 (mW/nm)")
    assert added["y_range"] == pytest.approx((0.0, 3.7 * 2))  # UI-221: all positive, peak at half height
    assert added["ratio"] is False and added["reference_line"] is False and added["threshold"] is None
    assert added["ratio_note"] is None and added["empty_text"] is None
    below = compute(client, ref("p1", 1), ref("p2", 2), "subtract")["result"]
    assert below["values"] == pytest.approx([a - 2.0 for a in values(RAW_A)])
    assert below["y_range"] == pytest.approx((-1.0 * 2, 0.0))  # all negative: −1.0 … −0.3
    crossing = compute(client, ref("p1", 4), ref("p2", 2), "subtract")["result"]  # 3 − 2 = 1 everywhere
    assert crossing["y_range"] == pytest.approx((0.0, 2.0))
    flat = compute(client, ref("p2", 3), ref("p2", 3), "add")["result"]
    assert flat["y_range"] == [-1.0, 1.0]


def test_ratio_hides_low_signal_points_keeps_values_and_marks_invalid_ones_null(
    client: TestClient, tmp_path: Path
) -> None:
    raw_a = [0, 10, 1000, 2000, 50000] + [1000] * 696
    raw_b = [100, 1000, 0, 1000, 1000] + [2000] * 696
    rows = [spectrum_record("2026-10-01T08:00:00.000", raw_a), spectrum_record("2026-10-01T08:01:00.000", raw_b)]
    register_device(client, v1_database(tmp_path / "ratio.sqlite3", rows), name=EAST)
    body = compute(client, ref("p1", 1), ref("p1", 2), "divide")
    result = body["result"]
    assert result["values"][:5] == [0.0, 0.01, None, 2.0, 50.0]  # MATH-008, MATH-010, MATH-009 (no capping)
    assert result["values"][5] == 0.5
    threshold = 0.02 * 50.0  # 2 % of the larger peak of both spectra, 350–1050 nm (MATH-015)
    assert result["threshold"] == pytest.approx(threshold)
    # plotted only where A ≥ T and B ≥ T (MATH-014): 0/0.1 and 0.01/1 fail, 1/0 is invalid, 2/1 and 50/1 pass
    assert result["plotted"][:6] == [None, None, None, 2.0, 50.0, 0.5]
    assert result["ratio"] is True and result["y_label"] == "比值（A/B）"
    assert result["title"] == "计算结果：比值 A/B" and result["ratio_note"] == display.RATIO_NOTE
    padding = max((50.0 - 0.5) * 0.25, 50.0 * 0.1)
    assert result["y_range"] == pytest.approx((max(0.0, 0.5 - padding), 50.0 + padding))
    assert result["reference_line"] is True  # 1 lies inside the range
    assert result["empty_text"] is None


def test_ratio_without_any_passing_point_says_so(client: TestClient, sources: dict[str, dict[str, Any]]) -> None:
    result = compute(client, ref("p2", 3), ref("p2", 3), "divide")["result"]  # all zero: 0/0 is NaN
    assert set(result["values"]) == {None}
    assert result["empty_text"] == "无满足阈值的比值数据"  # UI-219
    assert result["y_range"] == [0.0, 1.0]
    assert result["reference_line"] is False


def test_compute_refuses_bad_input(client: TestClient, sources: dict[str, dict[str, Any]]) -> None:
    bad = client.post("/api/v0/operations/compute", json={"a": ref("p1", 1), "b": ref("p2", 1), "operation": "mul"})
    assert error_of(bad)["code"] == "invalid_argument"
    missing = client.post("/api/v0/operations/compute", json={"a": ref("p1", 2), "b": ref("p2", 1), "operation": "add"})
    assert missing.status_code == 404 and error_of(missing)["code"] == "record_not_found"
    assert "光谱 A" in error_of(missing)["message"]
    no_b = client.post("/api/v0/operations/compute", json={"a": ref("p1", 1), "operation": "add"})
    assert no_b.status_code == 400


def test_compute_answers_503_when_the_snapshot_cannot_be_read(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    Path(sources["p2"]["path"]).write_bytes(b"not a database")
    response = client.post(
        "/api/v0/operations/compute", json={"a": ref("p1", 1), "b": ref("p2", 1), "operation": "add"}
    )
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "database_unavailable" and sources["p2"]["path"] in error["message"]


# --- API-24 export ----------------------------------------------------------------------------------------------


def export(client: TestClient, formats: list[str], operation: str = "divide", **extra: Any) -> Any:  # noqa: ANN401
    body = {"a": ref("p1", 1), "b": ref("p2", 2), "operation": operation, "formats": formats, **extra}
    return client.post("/api/v0/operations/export", json=body)


def _stored(path: str, record_id: int) -> tuple[dict[str, Any], list[int]]:
    """ParDatabase.get_spectrum's answer, read from the snapshot copy without opening anything for writing."""
    with sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        row = dict(
            con.execute(
                "SELECT a.*,s.raw_points_json FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id WHERE a.id=?",
                (record_id,),
            ).fetchone()
        )
    return row, json.loads(row.pop("raw_points_json"))


def _expected_csv(sources: dict[str, dict[str, Any]], tmp_path: Path, operation: str) -> bytes:
    """The file V1.0.3's writer produces for the same records (export_service.write_operation_file)."""
    a_row, a_points = _stored(sources["p1"]["path"], 1)
    b_row, b_points = _stored(sources["p2"]["path"], 2)
    a_row.update(source_device=EAST, source_database=sources["p1"]["source_path"])
    b_row.update(source_device=WEST, source_database=sources["p2"]["source_path"])
    a, b = np.asarray(a_points, float) / 1000, np.asarray(b_points, float) / 1000
    target = tmp_path / "expected.csv"
    export_service.write_operation_file(
        target,
        "csv",
        (a, b, combine(a, b, operation), operation, a_row, b_row),
        exported_at=NOW,
        format_time=format_beijing_time,
        time_difference=display.time_difference,
    )
    return target.read_bytes()


def test_export_writes_one_new_folder_in_the_alpha_output_directory(
    client: TestClient, context: ServiceContext, sources: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    before = {key: Path(item["source_path"]).read_bytes() for key, item in sources.items()}
    response = export(client, ["xlsx", "csv"])
    assert response.status_code == 201, response.text
    body = response.json()
    directory = Path(body["directory"])
    assert directory.parent == context.paths.exports_dir  # D-207
    assert directory.name == f"A1_ratio_B2_{NOW:%Y%m%d_%H%M%S_%f}"  # EXP-024
    assert body["files"] == ["A1_ratio_B2.csv", "A1_ratio_B2.xlsx"]  # EXP-025, EXP-026: one file per format
    assert sorted(path.name for path in directory.iterdir()) == body["files"]
    assert body["text"] == f"已保存 2 个文件：\n{directory}"
    assert before == {key: Path(item["source_path"]).read_bytes() for key, item in sources.items()}  # MATH-020
    # EXP-005/010/015..019: field for field the V1.0.3 file of the same records, sources named as in V1.0.3 (D-208)
    assert (directory / "A1_ratio_B2.csv").read_bytes() == _expected_csv(sources, tmp_path, "divide")
    rows = list(csv.reader(io.StringIO((directory / "A1_ratio_B2.csv").read_text(encoding="utf-8-sig"))))
    assert ["光谱 A 来源数据库", sources["p1"]["source_path"]] in rows
    assert ["光谱 B 来源设备", WEST] in rows


def test_a_second_export_in_the_same_microsecond_gets_a_numbered_folder(
    client: TestClient, sources: dict[str, dict[str, Any]]
) -> None:
    first = Path(export(client, ["csv"], operation="add").json()["directory"])
    second = Path(export(client, ["csv"], operation="add").json()["directory"])
    assert second.name == f"{first.name}_1"  # EXP-027: never overwrite
    assert (first / "A1_add_B2.csv").is_file() and (second / "A1_add_B2.csv").is_file()


def test_export_refuses_no_or_unknown_formats_without_writing(
    client: TestClient, context: ServiceContext, sources: dict[str, dict[str, Any]]
) -> None:
    for formats in ([], ["pdf"]):
        response = export(client, formats)
        assert response.status_code == 400 and error_of(response)["code"] == "invalid_argument"
    assert not context.paths.exports_dir.exists() or not any(context.paths.exports_dir.iterdir())


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="POSIX permissions, not as root")
def test_a_write_failure_names_the_folder_and_the_files_already_written(
    client: TestClient, context: ServiceContext, sources: dict[str, dict[str, Any]]
) -> None:
    context.paths.exports_dir.mkdir(parents=True)
    context.paths.exports_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        response = export(client, ["csv"])
    finally:
        context.paths.exports_dir.chmod(stat.S_IRWXU)
    assert response.status_code == 500
    error = error_of(response)
    assert (error["code"], error["retryable"], error["message"]) == ("export_failed", True, "导出失败")
    assert f"保存目录：{context.paths.exports_dir}" in error["detail"]  # EXP-020
    assert "已完成：无" in error["detail"]


def test_export_with_a_replaced_snapshot_is_refused(
    client: TestClient, sources: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    register_device(client, v1_database(tmp_path / "newer.sqlite3", west_records()), name=WEST, position=2)
    response = export(client, ["csv"], b=ref("p2", 2, sources["p2"]))
    assert response.status_code == 409 and error_of(response)["code"] == "snapshot_changed"


def test_the_new_endpoints_need_the_token(anonymous: TestClient) -> None:
    for method, path in (
        ("GET", "/api/v0/operations/page"),
        ("GET", "/api/v0/operation-sources"),
        ("GET", "/api/v0/operation-sources/p1/spectra"),
        ("GET", "/api/v0/operation-sources/p1/nearest?acquired_at=x"),
        ("POST", "/api/v0/operations/inputs"),
        ("POST", "/api/v0/operations/compute"),
        ("POST", "/api/v0/operations/export"),
    ):
        assert anonymous.request(method, path).status_code == 401, path


def test_reading_never_writes_the_snapshot(client: TestClient, sources: dict[str, dict[str, Any]]) -> None:
    copies = {key: Path(item["path"]).read_bytes() for key, item in sources.items()}
    client.get("/api/v0/operation-sources/p1/spectra")
    client.get("/api/v0/operation-sources/p2/nearest", params={"acquired_at": "2026-10-01T08:00:00.000"})
    compute(client, ref("p1", 1), ref("p2", 2), "divide")
    assert copies == {key: Path(item["path"]).read_bytes() for key, item in sources.items()}
    for item in sources.values():
        with sqlite3.connect(item["path"]) as con:
            assert con.execute("SELECT COUNT(*) FROM acquisitions").fetchone()[0] in (3, 4)


def test_nan_and_infinity_never_reach_the_json(client: TestClient, sources: dict[str, dict[str, Any]]) -> None:
    body = client.post(
        "/api/v0/operations/compute", json={"a": ref("p2", 3), "b": ref("p2", 3), "operation": "divide"}
    ).text
    assert "NaN" not in body and "Infinity" not in body
    assert json.loads(body)["result"]["values"][0] is None
