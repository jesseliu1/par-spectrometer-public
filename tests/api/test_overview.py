"""Contract tests of the read-only overview (api-contract-v0 API-09; D-211; ui-v2-pages.md 2.6).

The overview of a snapshot shows the newest successful record with a spectrum (UI-053): six KPI cards (UI-012),
the status line with record time and age (UI-055, UI-170, UI-171), the spectrum with the in-chart card (UI-060)
and, for "全部指标", the record id (UI-009, UI-013). Every text comes from par_app.services; tier 0 has no
acquisition, bus or start / stop state. The service clock is a FakeClock at conftest.NOW (2026-10-18 09:30).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.services import metrics as metric_service

from .conftest import NOW, RAW_FLAT, error_of, failed_record, legacy_database, record, register_device, v1_database

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec(
        "UI-009 UI-010 UI-012 UI-013 UI-014 UI-053 UI-054 UI-055 UI-057 UI-059 UI-060 UI-170 UI-171 UI-175"
    ),
]
URL = "/api/v0/devices/p1/latest"
DASH = "—"
FRESH = "2026-10-18T09:29:00.000"
"""60 s before the service clock."""
KPI_KEYS = ["lux", "irradiance", "ppfd", "ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd"]


def _quality(**fields: object) -> str:
    return json.dumps({"strategy": "single_capture", "acquisition_status": "completed", **fields})


def _overview(client: TestClient, tmp_path: Path, records: list[dict[str, Any]], **body: object) -> dict[str, Any]:
    register_device(client, v1_database(tmp_path / "v1" / "east.sqlite3", records), **body)
    response = client.get(URL)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_fresh_single_capture(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record(FRESH)], name="东区")
    assert body["source"] == "live_ro" and body["device"] == {"key": "p1", "name": "东区"}
    assert body["as_of"] == "2026-10-18T09:30:00.000"
    assert body["snapshot_text"] == "数据来自本机 2.0 采集的设备库；“距今”按本机当前时间计算"
    shown = body["display_record"]
    assert (shown["id"], shown["age_seconds"], shown["age_text"]) == (1, 60.0, "距今 60 秒")
    assert shown["exposure_text"] == "正常" and shown["review_text"] == "单次读取完成"
    assert shown["details_title"] == "全部指标 · #1 · 2026-10-18 09:29:00.000"
    assert body["status"] == {
        "text": "● 采集成功 · 单次读取完成　显示 #1　2026-10-18 09:29:00.000　距今 60 秒　曝光：正常　耗时：5464.7 ms",
        "level": "ok",
    }
    assert body["stale"] is False and body["details_enabled"] is True and body["metrics_error"] is None
    assert body["latest_attempt"] == {
        "id": 1,
        "success": True,
        "acquired_at": FRESH,
        "acquired_at_text": "2026-10-18 09:29:00.000",
    }
    assert body["record"]["id"] == 1 and body["record"]["acquired_at"] == FRESH


def test_kpis_core_overlay_and_table_are_the_services_texts(client: TestClient, tmp_path: Path) -> None:
    stored = record(FRESH)
    body = _overview(client, tmp_path, [stored])
    parameters = json.loads(stored["mcu_params_json"])
    metrics = json.loads(stored["software_metrics_json"])
    metrics["cct_kelvin"] = 5321  # ParDatabase.save_acquisition adds the rounded CCT
    expected = dict(metric_service.iter_overview_kpi_texts(metrics, parameters))
    assert [kpi["key"] for kpi in body["kpis"]] == KPI_KEYS
    assert {kpi["key"]: kpi["text"] for kpi in body["kpis"]} == expected
    assert body["kpis"][0] == {"key": "lux", "title": "照度", "text": "1234.5 lx"}
    assert [(row["label"], row["text"]) for row in body["core_metrics"]] == metric_service.overview_core_metrics(
        metrics, parameters
    )
    entries = metric_service.overview_metric_entries(metrics, parameters)
    overlay = body["chart"]["overlay"]
    assert [len(column) for column in overlay] == [8, 12]  # UI-060
    flat = [(row["label"], row["text"]) for column in overlay for row in column]
    assert flat == metric_service.overview_secondary_metrics(entries)  # all finite: same as V1.0.3
    assert all("无量纲" not in label for label, _ in flat)  # UI-059
    assert ("相关色温 CCT（K）", "5321") in flat  # UI-014: integer
    table = body["table"]
    assert [group["title"] for group in table] == ["常用光量", "波段光子通量", "植物光谱配比", "光色与光谱特征"]
    assert [(row["label"], row["text"]) for group in table for row in group["rows"]] == [
        (label, metric_service.format_entry_value(value)) for label, value in entries
    ]


def test_chart_spectrum_axis_and_ticks(client: TestClient, tmp_path: Path) -> None:
    chart = _overview(client, tmp_path, [record(FRESH)])["chart"]
    assert chart["title"] == "最新光谱" and chart["spectrum_state"] == "ok"
    assert chart["spectrum"]["values"] == [1.0] * 701  # raw 1000 / 10^3
    assert chart["spectrum"]["points"] == RAW_FLAT
    assert chart["y_max"] == pytest.approx(1.0 / 0.618)  # UI-175: peak at about 0.618 of the height
    assert chart["x_ticks"] == [350, 400, 500, 600, 700, 800, 900, 1000, 1050]  # UI-057: fixed 350–1050 nm


def test_texts_of_the_page(client: TestClient, tmp_path: Path) -> None:
    texts = _overview(client, tmp_path, [record(FRESH)])["texts"]
    assert texts["page_title"] == "实时概览"
    assert (texts["summary_title"], texts["details_button"], texts["metrics_toggle"]) == (
        "实时摘要",
        "全部指标",
        "显示指标",
    )
    assert texts["details_columns"] == ["指标", "数值", "单位"]
    # D-211 question 5: the unusable-spectrum text comes from the service like every other text (contract 1.2)
    assert texts["invalid_spectrum"] == "光谱数据无法解析"


def test_failed_round_keeps_the_last_valid_record(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record("2026-10-01T12:00:00.000"), failed_record("2026-10-01T12:01:00.000")])
    assert body["display_record"]["id"] == 1
    assert body["latest_attempt"]["id"] == 2 and body["latest_attempt"]["success"] is False
    assert body["status"]["text"].startswith(
        "● 本轮失败 · 保留最近有效数据 · 暂无新记录 · 单次读取完成　显示 #1　2026-10-01 12:00:00.000　距今 "
    )
    assert body["status"]["level"] == "error"
    assert body["stale"] is True
    assert body["kpis"][0]["text"] == "1234.5 lx"  # UI-055: the values of the kept record stay


def test_no_records(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [])
    assert body["display_record"] is None and body["latest_attempt"] is None and body["record"] is None
    assert body["status"] == {"text": "", "level": "none"}
    assert {kpi["text"] for kpi in body["kpis"]} == {DASH}
    assert body["chart"]["title"] == "当前设备暂无可显示光谱" and body["chart"]["spectrum"] is None
    assert body["chart"]["overlay"] == [] and body["table"] == [] and body["core_metrics"] == []
    assert body["details_enabled"] is False  # UI-013


def test_failures_only(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [failed_record("2026-10-18T09:00:00.000")])
    assert body["display_record"] is None and body["latest_attempt"]["id"] == 1
    assert body["status"] == {"text": "最近采集失败　2026-10-18 09:00:00.000", "level": "error"}  # UI-054
    assert body["chart"]["title"] == "最近采集失败，无新光谱"
    assert body["details_enabled"] is False


def test_success_without_spectrum_row_is_not_shown(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record("2026-10-18T09:00:00.000"), record(FRESH, raw_points=None)])
    assert body["display_record"]["id"] == 1  # UI-053: successful AND with a spectrum
    assert body["latest_attempt"]["id"] == 2
    assert body["status"]["text"].startswith("● 采集成功 · 暂无新记录 · 单次读取完成　显示 #1")


def test_stale_uses_the_poll_cycle_recorded_in_the_snapshot(client: TestClient, tmp_path: Path) -> None:
    """D-211 (D-206 rule): two recorded poll cycles, at least 120 s."""
    body = _overview(
        client, tmp_path, [record("2026-10-18T09:21:40.000", quality_json=_quality(poll_cycle_seconds=300))]
    )
    assert body["display_record"]["age_seconds"] == 500.0
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"], body["stale_after_seconds"]) == (
        300.0,
        "record",
        600.0,
    )
    assert body["stale"] is False and "暂无新记录" not in body["status"]["text"]
    assert "300 秒" in body["poll_cycle_text"]


def test_stale_prefers_the_poll_cycle_of_the_shown_record(client: TestClient, tmp_path: Path) -> None:
    """D-211 question 2 (supplement): the shown record's own quality_json.poll_cycle_seconds comes first, even when
    a later record by acquisition time (the D-206 pick) recorded another cycle."""
    body = _overview(
        client,
        tmp_path,
        [
            record("2026-10-18T09:25:00.000", raw_points=None, quality_json=_quality(poll_cycle_seconds=40)),
            record("2026-10-18T09:21:40.000", quality_json=_quality(poll_cycle_seconds=300)),
        ],
    )
    assert body["display_record"]["id"] == 2 and body["display_record"]["age_seconds"] == 500.0
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"], body["stale_after_seconds"]) == (
        300.0,
        "record",
        600.0,
    )
    assert body["stale"] is False and "暂无新记录" not in body["status"]["text"]
    assert "显示记录 #2" in body["poll_cycle_text"]


def test_stale_falls_back_to_the_d206_cycle_when_the_shown_record_has_none(client: TestClient, tmp_path: Path) -> None:
    """D-211 question 2 (supplement): no usable value in the shown record -> D-206 (latest successful record by
    acquisition time), then the 60 s default."""
    body = _overview(
        client,
        tmp_path,
        [
            record("2026-10-18T09:25:00.000", raw_points=None, quality_json=_quality(poll_cycle_seconds=300)),
            record("2026-10-18T09:21:40.000", quality_json=_quality(poll_cycle_seconds=10**400)),
        ],
    )
    assert body["display_record"]["id"] == 2
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"], body["stale_after_seconds"]) == (
        300.0,
        "record",
        600.0,
    )
    assert body["stale"] is False
    assert "2026-10-18 09:25:00.000" in body["poll_cycle_text"]


def test_stale_with_the_default_poll_cycle(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record("2026-10-18T09:27:59.000")])
    assert (body["poll_cycle_seconds"], body["poll_cycle_source"], body["stale_after_seconds"]) == (
        60.0,
        "default",
        120.0,
    )
    assert body["stale"] is True and " · 暂无新记录" in body["status"]["text"]
    assert body["status"]["level"] == "warn"
    assert "默认" in body["poll_cycle_text"]


def test_record_ahead_of_the_clock(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record("2026-10-18T09:30:10.000")])
    assert body["display_record"]["age_text"] == "记录时间晚于本机"
    assert body["stale"] is True


def test_unformattable_kpi_keeps_the_cards_before_it(client: TestClient, tmp_path: Path) -> None:
    """#38: the cards are written one at a time; V1.0.3 stops at the bad value with the earlier cards shown."""
    metrics = {"integrated_irradiance": 1.5, "ppfd": "broken", "mccree_ypfd": 2.0}
    body = _overview(
        client,
        tmp_path,
        [record(FRESH, software_metrics_json=json.dumps(metrics), mcu_params_json=json.dumps({"lux": 931.54}))],
    )
    assert [kpi["text"] for kpi in body["kpis"]] == ["931.5 lx", "1.500 W/m²", DASH, DASH, DASH, DASH]
    assert body["metrics_error"]["message"] == "记录 #1 的指标数据无法解析，指标只显示到出错之前"
    assert body["metrics_error"]["detail"].startswith("TypeError")
    assert body["chart"]["spectrum"] is None and body["chart"]["title"] == "当前设备暂无可显示光谱"
    assert body["chart"]["overlay"] == [] and body["table"] == []
    assert body["details_enabled"] is True  # V1.0.3 enables 全部指标 before the cards
    assert body["status"]["text"].startswith("● 采集成功")


def test_non_object_metrics_fail_before_any_card(client: TestClient, tmp_path: Path) -> None:
    body = _overview(client, tmp_path, [record(FRESH, software_metrics_json="[]", mcu_params_json=None)])
    assert {kpi["text"] for kpi in body["kpis"]} == {DASH}
    assert body["metrics_error"]["detail"].startswith("AttributeError")


def test_unreadable_entry_after_the_spectrum_shows_the_core_card(client: TestClient, tmp_path: Path) -> None:
    stored = record(FRESH)
    metrics = json.loads(stored["software_metrics_json"])
    metrics["pfd_b"] = [1, 2]  # a ratio of it cannot be computed
    body = _overview(client, tmp_path, [record(FRESH, software_metrics_json=json.dumps(metrics))])
    assert body["kpis"][2]["text"].endswith("µmol·m⁻²·s⁻¹") and body["kpis"][2]["text"] != DASH
    assert body["chart"]["spectrum"] is not None  # V1.0.3 had drawn the spectrum before the entries
    overlay = body["chart"]["overlay"]
    assert [[row["label"] for row in column] for column in overlay] == [
        ["照度（lx）", "PPFD（umol/m2/s）"],
        ["350–1050 nm 总辐照度（W/m2）", "McCree-YPFD（umol/m2/s）"],
    ]
    assert body["table"] == [] and body["metrics_error"] is not None


def test_non_finite_entries_show_a_dash(client: TestClient, tmp_path: Path) -> None:
    """D-179 (decided 2026-10-18: option 1, implemented with the new UI)."""
    parameters = {"lux": 12.25, "cct": 5321.4, "ra": float("nan"), "duv": float("inf")}
    body = _overview(client, tmp_path, [record(FRESH, mcu_params_json=json.dumps(parameters))])
    flat = {row["label"]: row["text"] for column in body["chart"]["overlay"] for row in column}
    assert (flat["一般显色指数 Ra"], flat["色偏差 Duv"]) == (DASH, DASH)
    table = {row["label"]: row["text"] for group in body["table"] for row in group["rows"]}
    assert (table["一般显色指数 Ra（无量纲）"], table["色偏差 Duv（无量纲）"]) == (DASH, DASH)
    assert body["metrics_error"] is None


@pytest.mark.parametrize("points", [[1000] * 700, [1000] * 700 + ["x"]], ids=["700 points", "not a number"])
def test_unusable_spectrum_is_invalid_and_the_metrics_stay(
    client: TestClient, tmp_path: Path, points: list[object]
) -> None:
    body = _overview(client, tmp_path, [record(FRESH, raw_points=points)])
    chart = body["chart"]
    assert (chart["spectrum_state"], chart["spectrum"], chart["y_max"]) == ("invalid", None, None)
    assert chart["title"] == "当前设备暂无可显示光谱"
    assert body["kpis"][0]["text"] == "1234.5 lx" and len(chart["overlay"]) == 2


def test_legacy_database(client: TestClient, tmp_path: Path) -> None:
    register_device(client, legacy_database(tmp_path / "v1" / "legacy.sqlite3"))
    body = client.get(URL).json()
    assert body["display_record"]["id"] == 1 and body["display_record"]["exposure_text"] == "欠曝光"
    assert body["display_record"]["acquired_at_text"] == "2026-10-01 16:00:00.000"  # UTC text shown in Beijing time
    assert body["status"]["text"].startswith("● 本轮失败 · 保留最近有效数据 · 暂无新记录　显示 #1")
    assert body["poll_cycle_source"] == "default"


def test_device_not_imported(client: TestClient) -> None:
    response = client.get("/api/v0/devices/p3/latest")
    assert response.status_code == 404 and error_of(response)["code"] == "device_not_found"


def test_unknown_position_is_not_a_device(client: TestClient) -> None:
    response = client.get("/api/v0/devices/p9/latest")
    assert response.status_code in (400, 404)


def test_missing_snapshot_copy_is_503_and_retryable(client: TestClient, tmp_path: Path) -> None:
    snapshot = register_device(client, v1_database(tmp_path / "v1" / "east.sqlite3", [record(FRESH)]))
    Path(snapshot["path"]).unlink()
    response = client.get(URL)
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "database_unavailable" and error["retryable"] is True


def test_reads_nothing_but_the_copy(client: TestClient, tmp_path: Path) -> None:
    source = v1_database(tmp_path / "v1" / "east.sqlite3", [record(FRESH)])
    register_device(client, source)
    before = {path.name: path.stat().st_mtime_ns for path in source.parent.iterdir()}
    assert client.get(URL).status_code == 200
    assert {path.name: path.stat().st_mtime_ns for path in source.parent.iterdir()} == before


def test_clock_is_the_service_clock(client: TestClient, tmp_path: Path) -> None:
    assert NOW.isoformat().startswith("2026-10-18T09:30:00")
    body = _overview(client, tmp_path, [record("2026-10-18T09:00:00.000")])
    assert body["display_record"]["age_seconds"] == 1800.0


@pytest.mark.spec("UI-009")
def test_live_overview_names_the_database_whose_detail_it_offers(client: TestClient, tmp_path: Path) -> None:
    """Issue #106: the live overview's "全部指标" reads API-06 of the same database; its snapshot_id says which, and
    another database at the same position (the configuration was changed) has another one."""
    register_device(client, v1_database(tmp_path / "v1" / "east.sqlite3", [record(FRESH)]), name="东区")
    live = client.get("/api/v0/acquisition/devices/p1/latest").json()
    assert live["details_enabled"] is True and live["display_record"]["id"] == 1
    detail = client.get("/api/v0/devices/p1/acquisitions/1").json()
    assert detail["snapshot_id"] == live["snapshot_id"] == client.get(URL).json()["snapshot_id"]
    assert len(detail["groups"]) == 7 and sum(len(group["items"]) for group in detail["groups"]) == 54  # UI-018
    register_device(client, v1_database(tmp_path / "v2" / "east.sqlite3", [record(FRESH)]), name="东区")
    replaced = client.get("/api/v0/acquisition/devices/p1/latest").json()
    assert replaced["snapshot_id"] != live["snapshot_id"]
    assert client.get("/api/v0/devices/p1/acquisitions/1").json()["snapshot_id"] == replaced["snapshot_id"]
