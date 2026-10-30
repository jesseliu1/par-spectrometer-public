"""Display rules of the spectrum calculation page copied from ui.py (par_app/services/operation_display.py).

Expected values are written out by hand from the rules (UI-192..UI-222); test_operations_parity.py separately
compares the copies with the running V1.0.3 window.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from par_app.services import operation_display as display

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("UI-156 UI-197 UI-208 UI-209 UI-214 UI-218 UI-220 UI-221 UI-222 MATH-011 MATH-021 EXP-020"),
]


def test_operations_and_labels() -> None:
    assert [key for key, _ in display.OPERATIONS] == ["add", "subtract", "divide"]  # MATH-011: only these three
    assert display.operation_label("divide") == "比值 A/B"
    assert display.result_title("subtract") == "计算结果：减法 A-B"
    assert (display.result_y_label("divide"), display.result_y_label("add")) == ("比值（A/B）", "功率 (mW/nm)")
    with pytest.raises(ValueError, match="不支持的运算"):
        display.operation_label("multiply")


def test_initial_sources_take_the_first_and_the_second() -> None:
    assert display.initial_sources(["p1", "p3", "p4"]) == ("p1", "p3")
    assert display.initial_sources(["p2"]) == ("p2", "p2")
    assert display.initial_sources([]) == (None, None)


def test_titles_and_record_labels() -> None:
    assert display.input_title("A") == "光谱 A：未选择记录"
    assert display.input_title("B", "西区", 12) == "光谱 B：西区 · #12"
    assert display.record_label({"id": 7, "acquired_at": "x"}, lambda value: f"<{value}>") == "#7 | <x>"


@pytest.mark.parametrize(
    ("a", "b", "seconds"),
    [
        ("2026-10-01T08:00:00.000", "2026-10-01T08:00:01.500", 1.5),
        ("2026-10-01T08:00:00.000", "2026-10-01T00:00:00+00:00", 0.0),  # legacy UTC = 08:00 Beijing (UI-197)
        ("2026-10-01T08:00:00+08:00", "2026-10-01T07:59:00.000", -60.0),
        ("2026-10-01T08:00:00.000", "garbage", None),
        ("2026-10-01T08:00:00.000", None, None),
    ],
)
def test_time_difference_is_b_minus_a(a: str, b: str | None, seconds: float | None) -> None:
    assert display.time_difference({"acquired_at": a}, {"acquired_at": b}) == seconds
    assert display.time_difference({}, {"acquired_at": a}) is None


def test_time_difference_text() -> None:
    assert display.time_difference_text(12.3456) == "采集时间差：B 比 A 晚 12.346 秒"
    assert display.time_difference_text(-0.5) == "采集时间差：B 比 A 早 0.500 秒"
    assert display.time_difference_text(0.0) == "采集时间差：A 与 B 相同"
    assert display.time_difference_text(None) == "采集时间差：不可用"


def test_spectrum_axis_puts_the_peak_at_0618_or_pads_negative_spans() -> None:
    assert display.spectrum_y_limits(np.array([0.0, 6.18, np.nan])) == pytest.approx((0.0, 10.0))
    assert display.spectrum_y_limits(np.zeros(3)) == (0.0, 1e-9)
    assert display.spectrum_y_limits(np.array([-1.0, 4.0])) == pytest.approx((-1.4, 4.4))
    assert display.spectrum_y_limits(np.array([np.nan])) == pytest.approx((0.0, 1 / 0.618))
    assert display.common_y_limits((0.0, 3.0), (-1.0, 2.0)) == (-1.0, 3.0)


@pytest.mark.parametrize(
    ("values", "operation", "limits"),
    [
        ([1.0, 3.0], "add", (0.0, 6.0)),  # all above zero: peak at half height (UI-221)
        ([-3.0, -1.0], "subtract", (-6.0, 0.0)),
        ([-1.0, 3.0], "subtract", (-2.0, 4.0)),  # crossing zero: 25 % of the span each side
        ([0.0, 0.0], "add", (-1.0, 1.0)),
        ([0.5, 2.5], "divide", (0.0, 3.0)),  # padding max(0.5, 0.25) = 0.5, floored at 0 (UI-222)
        ([10.0, 10.0], "divide", (9.0, 11.0)),  # no span: 10 % of the magnitude
        ([np.nan, np.nan], "divide", (0.0, 1.0)),
    ],
)
def test_result_axis(values: list[float], operation: str, limits: tuple[float, float]) -> None:
    assert display.result_y_limits(np.array(values), operation) == pytest.approx(limits)


def test_ratio_plot_hides_points_below_the_common_threshold_and_keeps_sums_whole() -> None:
    a = np.array([10.0, 0.1, 5.0, 0.0])
    b = np.array([5.0, 5.0, 0.15, 2.0])
    out = np.array([2.0, 0.02, 33.3, 0.0])
    plotted = display.plotted_result(a, b, out, "divide")  # T = 2 % × 10 = 0.2
    assert [None if math.isnan(value) else value for value in plotted] == [2.0, None, None, None]
    assert display.plotted_result(a, b, out, "add") is out  # MATH-021


def test_reference_line_only_for_ratios_with_one_inside_the_range() -> None:
    plotted = np.array([0.5, np.nan])
    assert display.reference_line_visible(plotted, (0.0, 1.0), "divide") is True  # 1 on the edge still shows
    assert display.reference_line_visible(plotted, (1.01, 2.0), "divide") is False
    assert display.reference_line_visible(np.array([np.nan]), (0.0, 1.0), "divide") is False
    assert display.reference_line_visible(plotted, (0.0, 2.0), "add") is False


def test_export_outcome_texts() -> None:
    assert display.export_done_text(2, "/out/A1_ratio_B2") == "已保存 2 个文件：\n/out/A1_ratio_B2"
    assert display.export_failed_text("/out/x", ("A1.csv",), OSError("disk full")) == (
        "保存目录：/out/x\n已完成：A1.csv\ndisk full"
    )
    assert display.export_failed_text("/out/x", (), "boom").endswith("已完成：无\nboom")
