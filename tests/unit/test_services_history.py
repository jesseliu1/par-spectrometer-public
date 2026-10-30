"""par_app.services.history: history-page display rules copied for the ui-v2 API (hand-written expectations).

Parity with the V1.0.3 window itself is checked in tests/api/test_history_parity.py; these tests pin the rules
from the specs and decisions directly, including the cases where the copy deliberately differs (D-154, D-202).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from par_app.services import history as svc

pytestmark = pytest.mark.unit
SINGLE = json.dumps({"strategy": "single_capture"})


def _row(**fields: object) -> dict[str, Any]:
    return {"success": 1, "exposure_status": 0, "quality_json": SINGLE, "dli_eligible": 1, "elapsed_ms": 1.0, **fields}


@pytest.mark.parametrize(
    ("quality", "expected"),
    [
        (SINGLE, True),
        (json.dumps({"strategy": "double"}), False),
        (None, False),
        ("", False),
        ("{", False),
        ("[]", False),
    ],
)
def test_is_single_capture(quality: str | None, expected: bool) -> None:
    assert svc.is_single_capture({"quality_json": quality}) is expected


@pytest.mark.parametrize(("status", "text"), [(0, "正常"), (1, "过曝光"), (2, "欠曝光"), (3, "未知"), (None, "未知")])
def test_exposure_text(status: int | None, text: str) -> None:
    assert svc.exposure_text({"exposure_status": status}) == text


@pytest.mark.spec("UI-052")
@pytest.mark.parametrize(
    ("status", "quality", "style"),
    [
        (0, SINGLE, "normal"),
        (1, SINGLE, "normal"),  # D-154: new single-capture records keep the normal colour
        (2, SINGLE, "normal"),
        (None, SINGLE, "normal"),
        (0, None, "normal"),
        (1, None, "warn"),  # old records keep the warning colour
        (2, json.dumps({"confirmed": True}), "warn"),
        (None, None, "warn"),
    ],
)
def test_exposure_style(status: int | None, quality: str | None, style: str) -> None:
    assert svc.exposure_style({"exposure_status": status, "quality_json": quality}) == style


@pytest.mark.spec("UI-030")
@pytest.mark.parametrize(
    ("fields", "review"),
    [
        ({"success": 0}, "未完成采集"),
        ({"success": 0, "quality_json": "{"}, "未完成采集"),
        ({}, "单次读取完成"),
        ({"dli_eligible": 0}, "单次读取完成"),
        ({"quality_json": json.dumps({"confirmed": True}), "dli_eligible": 0}, "复核未完成"),
        ({"quality_json": json.dumps({"confirmed": False}), "dli_eligible": None}, "复核未完成"),
        ({"quality_json": json.dumps({"confirmed": True}), "dli_eligible": None}, "已完成"),
        ({"quality_json": json.dumps({"confirmed": 0}), "dli_eligible": None}, "未记录"),
        ({"quality_json": None, "dli_eligible": None}, "未记录"),
        ({"quality_json": "{", "dli_eligible": None}, "未记录"),  # D-202 (V1.0.3 raised)
        ({"quality_json": "[false]", "dli_eligible": None}, "未记录"),  # D-202 (V1.0.3 raised)
    ],
)
def test_review_text(fields: dict[str, Any], review: str) -> None:
    assert svc.review_text(_row(**fields)) == review


@pytest.mark.parametrize(("elapsed", "text"), [(5464.66, "5464.7"), (0.04, "0.0"), (None, "—"), (float("nan"), "—")])
def test_elapsed_text(elapsed: float | None, text: str) -> None:
    assert svc.elapsed_text({"elapsed_ms": elapsed}) == text


@pytest.mark.parametrize(
    ("fields", "text", "level"),
    [
        ({}, "采集成功 · 单次读取完成", "ok"),
        ({"exposure_status": 2}, "采集成功 · 单次读取完成", "ok"),
        ({"success": 0}, "采集失败", "error"),
        ({"quality_json": None}, "采集成功", "ok"),
        ({"quality_json": None, "exposure_status": 1}, "采集成功", "warn"),
        ({"quality_json": None, "dli_eligible": 0}, "采集成功 · 复核未完成（不计入 DLI）", "warn"),
    ],
)
def test_status_text_and_level(fields: dict[str, Any], text: str, level: str) -> None:
    row = _row(**fields)
    assert (svc.status_text(row), svc.status_level(row)) == (text, level)


@pytest.mark.spec("UI-018")
def test_detail_groups_hold_54_unique_keys_in_seven_groups() -> None:
    keys = [key for _title, fields in svc.DETAIL_GROUPS for key, _label, _unit in fields]
    assert len(svc.DETAIL_GROUPS) == 7
    assert len(keys) == len(set(keys)) == 54
    assert [len(fields) for _title, fields in svc.DETAIL_GROUPS] == [8, 6, 6, 7, 5, 15, 7]


def test_spectrum_values_divide_by_ten_to_the_coefficient() -> None:
    assert svc.spectrum_values([1000, 25, 0], 3) == [1.0, 0.025, 0.0]
    assert svc.spectrum_values([7, 8], None) == [7.0, 8.0]
    assert svc.spectrum_values([7], 0) == [7.0]
    assert (svc.SPECTRUM_START_NM, svc.SPECTRUM_STEP_NM) == (350, 1)
