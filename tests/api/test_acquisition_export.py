"""Contract tests of the acquisition-record export (api-contract-v0 API-22, API-23, API-26 `export`; 13_ section 5).

A synthetic V1.0.x database (written by ParDatabase) is imported as the snapshot of p1. The service clock is a
FakeClock at 2026-10-18 09:30:00.000 Beijing time. Expected counts, ranges, folder and file names are written out
by hand from the V1.0.3 rules (EXP-008, EXP-011..014, EXP-048..051, EXP-068, EXP-071; fixes #11 end second .999,
#12 rolling presets, #15 PAR ×10 (D-166), #31 UV 350–399); the files themselves are compared with the real V1.0.3
window in test_acquisition_export_parity.py.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
import stat
import sys
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.domain.clock import FakeClock
from par_app.services import settings_display as texts

from .conftest import error_of, failed_record, record, register_device, v1_database

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec(
        "EXP-001 EXP-002 EXP-003 EXP-006 EXP-007 EXP-008 EXP-011 EXP-012 EXP-013 EXP-014 EXP-041 EXP-043 EXP-048 "
        "EXP-049 EXP-050 EXP-051 EXP-052 EXP-053 EXP-054 EXP-057 EXP-058 EXP-059 EXP-068 EXP-069 EXP-070 "
        "EXP-071 EXP-072 MATH-007 MATH-022"
    ),
]
EAST = "东区"
CSV_ONLY = {"range": "1h", "formats": ["csv"]}


def records() -> list[dict[str, Any]]:
    """ids 1..6 around the FakeClock's 09:30:00.000 (conftest NOW)."""
    return [
        record("2026-10-18T07:00:00.000"),  # 1: 2.5 h before: only in 4h / 8h / 24h
        record("2026-10-18T08:29:59.999"),  # 2: just before the 1h window (starts 08:30:00)
        record("2026-10-18T08:30:00.000"),  # 3: first second of the 1h window
        failed_record("2026-10-18T09:00:00.000"),  # 4: failed, exported with the one-line spectrum note
        record("2026-10-18T09:30:00.800"),  # 5: inside the end second (#11: the end second is .999)
        record("2026-10-18T09:30:01.000"),  # 6: after the end second
    ]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return v1_database(tmp_path / "v1" / "east.sqlite3", records())


@pytest.fixture
def east(client: TestClient, source: Path) -> dict[str, Any]:
    return register_device(client, source, name=EAST, position=1)


def count(client: TestClient, key: str = "p1", **params: object) -> dict[str, Any]:
    response = client.get(f"/api/v0/devices/{key}/export/count", params=params or CSV_ONLY)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def export(client: TestClient, key: str = "p1", **body: object) -> httpx.Response:
    return client.post(f"/api/v0/devices/{key}/export", json=body)


def csv_rows(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


# --- page texts (API-26 `export`) ----------------------------------------------------------------------------------


def test_page_texts_are_the_v1_settings_export_group(client: TestClient, context: ServiceContext) -> None:
    page = client.get("/api/v0/settings").json()["export"]
    assert page["title"] == "采集记录导出"
    assert [item["key"] for item in page["ranges"]] == ["1h", "2h", "4h", "8h", "24h", "custom"]  # EXP-068
    assert [item["label"] for item in page["ranges"]][:2] == ["最近 1 小时", "最近 2 小时"]
    assert page["ranges"][-1]["label"] == "自定义时间"
    assert page["default_range"] == "1h"  # EXP-048
    assert [(item["key"], item["label"], item["checked"]) for item in page["formats"]] == [
        ("csv", "CSV", True),
        ("xlsx", "Excel (.xlsx)", False),
    ]  # EXP-014
    assert page["button_label"] == "导出采集记录"
    assert page["content_note"] == "每条记录一个文件，包含指标与 701 点原始光谱。"
    assert page["directory"] == str(context.paths.exports_dir)  # D-210: the alpha's output folder (as D-207)
    assert page["no_device_text"] == "尚未配置导出设备"


# --- count preview (API-22) -----------------------------------------------------------------------------------------


@pytest.mark.usefixtures("east")
def test_default_preset_counts_the_last_hour_up_to_the_end_second(client: TestClient) -> None:
    body = count(client)
    assert body["range"] == {
        "mode": "1h",
        "start": "2026-10-18T08:30:00",
        "end": "2026-10-18T09:30:00",
        "start_text": "2026-10-18 08:30:00",
        "end_text": "2026-10-18 09:30:00",
        "editable": False,  # EXP-071: preset times are shown disabled
    }
    # ids 3, 4, 5: 08:30:00.000 counts, 08:29:59.999 does not; 09:30:00.800 is inside the end second (#11)
    assert (body["count"], body["files"], body["can_export"]) == (3, 3, True)
    assert body["text"] == "预计 3 条记录，将导出为 3 个文件"
    assert body["device"] == {"key": "p1", "name": EAST}


@pytest.mark.usefixtures("east")
def test_file_count_is_records_times_formats(client: TestClient) -> None:
    both = count(client, range="1h", formats=["csv", "xlsx"])
    assert (both["count"], both["files"]) == (3, 6)  # EXP-011
    assert both["text"] == "预计 3 条记录，将导出为 6 个文件"
    none = count(client, range="1h")
    assert (none["count"], none["files"], none["can_export"]) == (3, 0, False)  # no format: button disabled
    assert none["text"] == "预计 3 条记录，将导出为 0 个文件"


@pytest.mark.usefixtures("east")
def test_presets_roll_with_the_clock(client: TestClient, context: ServiceContext) -> None:
    """#12 (EXP-051, D-129): a preset is recomputed from the clock at every count, not once when chosen."""
    assert count(client, range="4h", formats=["csv"])["count"] == 5  # ids 1..5 (07:00 is inside 05:30–09:30)
    assert isinstance(context.clock, FakeClock)
    context.clock.advance(2 * 3600)  # 11:30:00: 4h starts 07:30, the 1h window holds nothing
    later = count(client, range="4h", formats=["csv"])
    assert later["range"]["start"] == "2026-10-18T07:30:00" and later["range"]["end"] == "2026-10-18T11:30:00"
    assert later["count"] == 5  # ids 2..6
    empty = count(client, range="1h", formats=["csv"])
    assert (empty["count"], empty["can_export"]) == (0, False)  # EXP-049


@pytest.mark.usefixtures("east")
@pytest.mark.parametrize(("mode", "expected"), [("2h", 4), ("8h", 5), ("24h", 5)])
def test_every_preset(client: TestClient, mode: str, expected: int) -> None:
    assert count(client, range=mode, formats=["csv"])["count"] == expected


@pytest.mark.usefixtures("east")
def test_custom_range_is_used_as_given_with_whole_seconds(client: TestClient) -> None:
    """EXP-050: [start.000, end.999]; the clock does not move a custom range."""
    body = count(client, range="custom", start="2026-10-18T08:29:59", end="2026-10-18T09:30:00", formats=["csv"])
    assert body["range"] == {
        "mode": "custom",
        "start": "2026-10-18T08:29:59",
        "end": "2026-10-18T09:30:00",
        "start_text": "2026-10-18 08:29:59",
        "end_text": "2026-10-18 09:30:00",
        "editable": True,
    }
    assert body["count"] == 4  # ids 2..5


@pytest.mark.usefixtures("east")
def test_custom_end_before_start_counts_nothing(client: TestClient) -> None:
    """V1.0.3 counts 0 (the button is disabled); exporting such a range is refused (EXP-050)."""
    body = count(client, range="custom", start="2026-10-18T10:00:00", end="2026-10-18T09:00:00", formats=["csv"])
    assert (body["count"], body["can_export"], body["confirm"]) == (0, False, None)
    assert body["notice"] == "结束时间不能早于开始时间。"
    empty = count(client, range="custom", start="2026-10-17T00:00:00", end="2026-10-17T01:00:00", formats=["csv"])
    assert (empty["notice"], empty["confirm"]) == ("所选时间范围内没有采集记录。", None)
    assert count(client, range="1h")["notice"] is None  # no format: V1.0.3 does nothing
    assert count(client)["notice"] is None


@pytest.mark.usefixtures("east")
@pytest.mark.parametrize(
    "params",
    [
        {"range": "3h", "formats": ["csv"]},
        {"range": "custom", "formats": ["csv"]},
        {"range": "custom", "start": "2026-10-18 08:00:00", "end": "2026-10-18T09:00:00", "formats": ["csv"]},
        {"range": "custom", "start": "2026-10-18T08:00:00.000", "end": "2026-10-18T09:00:00"},
        {"range": "custom", "start": "2026-02-30T08:00:00", "end": "2026-10-18T09:00:00"},
        {"range": "1h", "formats": ["pdf"]},
    ],
)
def test_invalid_count_arguments_are_400(client: TestClient, params: dict[str, Any]) -> None:
    response = client.get("/api/v0/devices/p1/export/count", params=params)
    assert response.status_code == 400, response.text
    assert error_of(response)["code"] == "invalid_argument"


def test_unknown_or_unconfigured_device(client: TestClient) -> None:
    assert error_of(client.get("/api/v0/devices/p9/export/count", params=CSV_ONLY))["code"] == "invalid_argument"
    response = client.get("/api/v0/devices/p2/export/count", params=CSV_ONLY)
    assert response.status_code == 404 and error_of(response)["code"] == "device_not_found"


def test_unreadable_snapshot_is_503_not_zero(client: TestClient, east: dict[str, Any]) -> None:
    Path(east["path"]).unlink()
    response = client.get("/api/v0/devices/p1/export/count", params=CSV_ONLY)
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "database_unavailable" and error["retryable"] is True
    assert east["path"] in error["message"]


@pytest.mark.usefixtures("east")
def test_count_gives_the_v1_confirmation(client: TestClient, context: ServiceContext) -> None:
    """EXP-053, EXP-059: one confirmation with device, range, records, files, structure and target folder."""
    body = count(client, range="1h", formats=["csv", "xlsx"])
    assert body["confirm"]["title"] == "确认导出"
    assert body["confirm"]["text"] == (
        f"导出设备：{EAST}\n时间范围：2026-10-18 08:30:00 至 2026-10-18 09:30:00\n"
        "共 3 条采集记录，将导出为 6 个文件（CSV、Excel）。\n"
        f"目录结构：{EAST}\\格式\\采集日期\\文件\n\n"
        f"目标文件夹：{context.paths.exports_dir}\n\n是否继续？"
    )
    assert count(client, range="1h")["confirm"] is None  # no format chosen: nothing to confirm


# --- export (API-23) ------------------------------------------------------------------------------------------------


def test_export_writes_device_format_date_folders_into_the_alpha_output(
    client: TestClient, context: ServiceContext, east: dict[str, Any], source: Path
) -> None:
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot_before = hashlib.sha256(Path(east["path"]).read_bytes()).hexdigest()
    response = export(
        client,
        start="2026-10-18T08:30:00",
        end="2026-10-18T09:30:00",
        formats=["xlsx", "csv"],
        snapshot_id=east["id"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    root = context.paths.exports_dir
    assert body["directory"] == str(root)
    assert (body["records"], body["files"]) == (3, 6)
    assert body["text"] == f"已导出 6 个文件到：\n{root}"
    # as_posix: the expected names use "/", str() gives backslashes on Windows (same files; #66)
    written = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    assert written == sorted(
        f"{EAST}/{folder}/2026-10-18/PAR_{stamp}_#{record_id}.{kind}"
        for folder, kind in (("CSV", "csv"), ("Excel", "xlsx"))
        for stamp, record_id in (("20261018_083000", 3), ("20261018_090000", 4), ("20261018_093000", 5))
    )  # EXP-008, EXP-012, EXP-013, EXP-072
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before  # the V1.0.x database is never written
    assert hashlib.sha256(Path(east["path"]).read_bytes()).hexdigest() == snapshot_before


@pytest.mark.usefixtures("east")
def test_exported_csv_keeps_the_v1_structure_and_fixed_values(client: TestClient, context: ServiceContext) -> None:
    """4 header rows + 69 fields + blank + 701 points (EXP-003, EXP-006); PAR ×10 (#15, D-166); UV 350–399 (#31)."""
    assert export(client, start="2026-10-18T08:30:00", end="2026-10-18T08:30:00", formats=["csv"]).status_code == 201
    rows = csv_rows(context.paths.exports_dir / EAST / "CSV" / "2026-10-18" / "PAR_20261018_083000_#3.csv")
    assert rows[0] == ["文件来源", "PAR 光谱仪专用软件 - 采集记录导出"]
    assert rows[1] == ["导出时间（北京时间）", "2026-10-18 09:30:00.000"]  # the service clock
    assert rows[2:4] == [["采集记录 ID", "3"], ["采集时间（北京时间）", "2026-10-18 08:30:00.000"]]
    fields = {row[0]: row[2] for row in rows[4:73]}
    assert len(rows[4:73]) == 69 and rows[73] == []
    assert float(fields["PAR波段辐照度(W/m²)"]) == pytest.approx(301.0)  # stored 30.1 × 10 (flat 1 W/m²/nm)
    assert float(fields["扩展PAR辐照度(400–750)"]) == pytest.approx(351.0)
    assert "紫外PFD(350–399)" in fields and "扩展紫外PFD(350–399)" in fields
    assert fields["相关色温(K)"] == "5321.4"  # EXP-057: the hardware CCT as stored
    assert rows[74] == ["波长（nm）", "原始光谱值"] and len(rows[75:]) == 701
    assert rows[75] == ["350.0", "1000.0"]


@pytest.mark.usefixtures("east")
def test_failed_record_exports_the_one_line_spectrum_note(client: TestClient, context: ServiceContext) -> None:
    assert export(client, start="2026-10-18T09:00:00", end="2026-10-18T09:00:00", formats=["csv"]).status_code == 201
    rows = csv_rows(context.paths.exports_dir / EAST / "CSV" / "2026-10-18" / "PAR_20261018_090000_#4.csv")
    assert len(rows) == 4 + 69 + 2  # D-127: header, fields, blank line, one note line
    assert rows[-1] == ["光谱数据区", "本记录无原始光谱数据（采集失败或未保存光谱）。"]


@pytest.mark.usefixtures("east")
def test_export_includes_the_end_second(client: TestClient, context: ServiceContext) -> None:
    body = export(client, start="2026-10-18T09:30:00", end="2026-10-18T09:30:00", formats=["csv"]).json()
    assert body["records"] == 1  # id 5 at 09:30:00.800 (#11)
    assert (context.paths.exports_dir / EAST / "CSV" / "2026-10-18" / "PAR_20261018_093000_#5.csv").is_file()


@pytest.mark.usefixtures("east")
def test_export_refusals_write_nothing(client: TestClient, context: ServiceContext) -> None:
    cases = [
        (
            {"start": "2026-10-18T10:00:00", "end": "2026-10-18T09:00:00", "formats": ["csv"]},
            400,
            "invalid_argument",
            "结束时间不能早于开始时间。",
        ),
        (
            {"start": "2026-10-17T00:00:00", "end": "2026-10-17T23:59:59", "formats": ["csv"]},
            404,
            "record_not_found",
            "所选时间范围内没有采集记录。",
        ),
        ({"start": "2026-10-18T08:00:00", "end": "2026-10-18T09:00:00", "formats": []}, 400, "invalid_argument", None),
        (
            {"start": "2026-10-18T08:00:00", "end": "2026-10-18T09:00:00", "formats": ["pdf"]},
            400,
            "invalid_argument",
            None,
        ),
        (
            {"start": "2026-10-18T08:00", "end": "2026-10-18T09:00:00", "formats": ["csv"]},
            400,
            "invalid_argument",
            None,
        ),
    ]
    for body, status, code, message in cases:
        response = export(client, **body)
        assert response.status_code == status, (body, response.text)
        error = error_of(response)
        assert error["code"] == code
        if message is not None:
            assert error["message"] == message
    assert not context.paths.exports_dir.exists() or not any(context.paths.exports_dir.rglob("*"))


def test_export_with_a_replaced_snapshot_is_refused(
    client: TestClient, context: ServiceContext, east: dict[str, Any], source: Path
) -> None:
    """The confirmation counted one copy; a newer import of the same position must not be exported instead."""
    register_device(client, source, name=EAST, position=1)
    response = export(
        client, start="2026-10-18T08:30:00", end="2026-10-18T09:30:00", formats=["csv"], snapshot_id=east["id"]
    )
    assert response.status_code == 409
    assert error_of(response)["code"] == "snapshot_changed"
    assert not context.paths.exports_dir.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
@pytest.mark.usefixtures("east")
def test_write_failure_is_export_failed_with_the_completed_count(client: TestClient, context: ServiceContext) -> None:
    """EXP-020-like: V1.0.3 stops at the first failing record and reports it and the files already written."""
    day = context.paths.exports_dir / EAST / "Excel" / "2026-10-18"
    day.mkdir(parents=True)
    day.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        response = export(client, start="2026-10-18T08:30:00", end="2026-10-18T09:30:00", formats=["csv", "xlsx"])
    finally:
        day.chmod(stat.S_IRWXU)
    assert response.status_code == 500
    error = error_of(response)
    assert (error["code"], error["retryable"], error["message"]) == ("export_failed", True, "导出失败")
    detail = error["detail"]
    assert detail.startswith("记录 ID 3 导出失败：\n")
    assert "导出结束：成功 1 个文件，失败 1 个文件。" in detail  # the CSV of #3 was written first
    assert str(context.paths.exports_dir) in detail


@pytest.mark.usefixtures("east")
def test_a_second_export_while_one_runs_is_busy(client: TestClient, context: ServiceContext) -> None:
    """V1.0.3 ignores a click while exporting (_exporting); the service answers busy instead of running twice."""
    lock: threading.Lock = context.acquisition_export.lock
    assert lock.acquire(blocking=False)
    try:
        response = export(client, start="2026-10-18T08:30:00", end="2026-10-18T09:30:00", formats=["csv"])
    finally:
        lock.release()
    assert response.status_code == 409
    error = error_of(response)
    assert (error["code"], error["retryable"]) == ("busy", True)
    assert not context.paths.exports_dir.exists()


@pytest.mark.usefixtures("east")
def test_exporting_again_overwrites_the_same_files(client: TestClient, context: ServiceContext) -> None:
    """V1.0.3 writes into the chosen folder without a per-export folder; the same range again gives the same
    names, which are rewritten (D-210)."""
    body = {"start": "2026-10-18T08:30:00", "end": "2026-10-18T08:30:00", "formats": ["csv"]}
    assert export(client, **body).status_code == 201
    assert isinstance(context.clock, FakeClock)
    context.clock.advance(60)
    assert export(client, **body).status_code == 201
    files = list(context.paths.exports_dir.rglob("*.csv"))
    assert len(files) == 1
    assert csv_rows(files[0])[1] == ["导出时间（北京时间）", "2026-10-18 09:31:00.000"]


def test_texts_module_is_what_the_service_uses() -> None:
    assert texts.COUNT_TEXT.format(count=2, files=4) == "预计 2 条记录，将导出为 4 个文件"


@pytest.mark.usefixtures("east")
def test_count_lists_the_formats_in_the_v1_order_whatever_the_query_order(client: TestClient) -> None:
    """EXP-014: CSV, then Excel, as V1.0.3's two check boxes; the order of the query never changes the text."""
    body = count(client, range="1h", formats=["xlsx", "csv"])
    assert body["formats"] == ["csv", "xlsx"]
    assert "将导出为 6 个文件（CSV、Excel）。" in body["confirm"]["text"]


def test_metrics_json_that_is_not_an_object_is_export_failed_naming_the_record(
    client: TestClient, context: ServiceContext, tmp_path: Path
) -> None:
    """D-210 question 6: valid JSON that is not an object stops the export at that record like any other write
    failure (V1.0.3 raises AttributeError there); the files of earlier records stay, the error names the record and
    the files written. The file content of other records is still D-168 A."""
    rows = [record("2026-10-18T08:30:00.000"), record("2026-10-18T09:00:00.000")]
    path = v1_database(tmp_path / "v1" / "odd.sqlite3", rows)
    con = sqlite3.connect(path)
    con.execute("UPDATE acquisitions SET software_metrics_json='[1, 2]' WHERE id=2")
    con.commit()
    con.close()
    register_device(client, path, name=EAST, position=1)
    response = export(client, start="2026-10-18T08:30:00", end="2026-10-18T09:30:00", formats=["csv"])
    assert response.status_code == 500, response.text
    error = error_of(response)
    assert (error["code"], error["message"]) == ("export_failed", "导出失败")
    assert error["detail"].startswith("记录 ID 2 导出失败：")
    assert "导出结束：成功 1 个文件，失败 1 个文件。" in error["detail"]
    assert len(list(context.paths.exports_dir.rglob("*.csv"))) == 1
