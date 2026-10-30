"""Display rules of the spectrum calculation page (光谱计算) for the ui-v2 local service (stage two, route C).

These are copies, not moves: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2), so
the V1.0.x window keeps its own code and this module repeats the same texts and axis rules for the API. The numbers
themselves are not computed here: the result is par_app.math_ops.combine and the ratio display filter is
par_app.math_ops.ratio_display_mask, the code V1.0.3 itself runs. tests/api/test_operations_parity.py runs the
V1.0.3 MainWindow and the API on the same databases and compares every text, axis range and plotted value, so the
two copies cannot drift apart unnoticed. The guide texts are in operation_guide.py.

Origin in par_app/ui.py (V1.0.3):
  MainWindow._build_operations (labels, tooltips, operations)    -> OPERATIONS, the *_LABEL / *_TOOLTIP texts
  MainWindow._select_operation_record / _refresh_operation_records -> record_label, NO_SPECTRUM
  MainWindow._rebuild_operation_databases (initial A / B)        -> initial_sources
  MainWindow._operation_values                                   -> spectrum_values
  MainWindow._operation_time_difference                          -> time_difference
  MainWindow._redraw_operation_charts (titles, time text, empty texts, result axis, 1× line, ratio texts)
                                                                 -> input_title, time_difference_text,
                                                                    result_title, plotted_result, result_y_limits,
                                                                    reference_line_visible, RATIO_NOTE, NO_RATIO_DATA
  SpectrumCanvas.plot (y range of a spectrum chart, empty texts) -> spectrum_y_limits, INPUT_EMPTY_*
  MainWindow._layout_operation_charts (x ticks)                  -> TICKS_WIDE, TICKS_NARROW, NARROW_CHART_PX
  MainWindow.export_operation_results (dialog and outcome texts) -> EXPORT_*, export_done_text, export_failed_text
Not copied: the chart colours and the wavelength-coloured fill (the web page takes colours from its design tokens,
R-1-5) and the Matplotlib layout (title font sizes, margins), which the page lays out itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np

from ..domain.clock import BEIJING_TZ
from ..math_ops import WAVELENGTHS, ratio_display_mask
from .export import Record, TimeFormatter

OPERATIONS: tuple[tuple[str, str], ...] = (("add", "加法 A+B"), ("subtract", "减法 A-B"), ("divide", "比值 A/B"))
"""(key, label) of the three operations in the V1.0.3 order (MATH-011); the first is the default."""
DIVIDE = "divide"
SPECTRUM_POINTS = len(WAVELENGTHS)
"""A usable record has exactly 701 points (350–1050 nm, 1 nm), as ParDatabase.operation_spectra requires."""
CANDIDATE_LIMIT = 500
"""The record lists show the newest 500 usable records (ParDatabase.operation_spectra(500), UI-198)."""

SOURCE_LABELS = ("A", "B")
OPERATION_LABEL = "算法"
RUN_LABEL = "执行计算"
EXPORT_LABEL = "导出计算结果"
SWAP_TOOLTIP = "交换光谱 A 与 B"
"""UI-314."""
AUTO_MATCH_LABEL = "B 匹配 A 的最近时间"
AUTO_MATCH_TOOLTIP = "选择 B 全库中距 A 时间最近的成功完整光谱；最近不代表同步，不设置时间容差，也不修改设备时钟"
"""UI-195, UI-199, UI-206, UI-288."""
TIME_TOOLTIP = "最近时间匹配不是同步采集。光源变化越快，时间差对比较结果的影响越大。"
"""UI-206."""
NO_SPECTRUM = "无可用光谱"
"""UI-207, UI-269."""
INPUT_EMPTY_HEADING = "暂无可显示的光谱"
INPUT_EMPTY_DETAIL = "选择有效采集记录后将在此显示曲线"
"""SpectrumCanvas.plot defaults, shown in an A or B chart without a usable record."""
WAITING_HEADING = "等待执行计算"
"""UI-210."""
MISSING_HEADING = "缺少有效的 A/B 光谱"
MISSING_DETAIL = "A、B 均需成功且完整的光谱记录"
"""UI-216."""
RESULT_TITLE = "计算结果"
"""UI-213, UI-217: the result chart's title before a calculation, and its series name."""
X_LABEL = "波长 (nm)"
POWER_Y_LABEL = "功率 (mW/nm)"
RATIO_Y_LABEL = "比值（A/B）"
RATIO_NOTE = "比值显示：A、B 均达到两条光谱最大峰值的 2%。"
NO_RATIO_DATA = "无满足阈值的比值数据"
"""UI-219."""
TIME_PREFIX = "采集时间差："
TIME_UNAVAILABLE = "不可用"
TIME_SAME = "A 与 B 相同"

AXIS_START_NM = int(WAVELENGTHS[0])
AXIS_END_NM = int(WAVELENGTHS[-1])
"""UI-193, UI-194: every chart of the page shows 350–1050 nm, no band choice."""
TICKS_WIDE = (350, 400, 500, 600, 700, 800, 900, 1000, 1050)
TICKS_NARROW = (350, 500, 600, 700, 800, 900, 1050)
NARROW_CHART_PX = 680
"""UI-192: a chart narrower than 680 px leaves out 400 and 1000, which would collide with the end labels."""
PEAK_HEIGHT_FRACTION = 0.618
"""SpectrumCanvas.plot: a non-negative spectrum's peak sits at about 0.618 of the plot height."""
NEGATIVE_PADDING_FRACTION = 0.08
"""SpectrumCanvas.plot: a spectrum with negative values gets 8 % of its span above and below."""
MINIMUM_SPAN = 1e-9
"""SpectrumCanvas.plot and _redraw_operation_charts: lower bound of an axis span (all-zero data still has an axis)."""
RATIO_PADDING_SPAN = 0.25
RATIO_PADDING_MAGNITUDE = 0.1
"""UI-222: the ratio axis adds max(25 % of the span, 10 % of the largest magnitude) around the visible ratios."""
SIGNED_PADDING_SPAN = 0.25
"""UI-221: a sum or difference crossing zero gets 25 % of its span above and below."""
ZERO_SIDE_FACTOR = 2.0
"""UI-221: a sum or difference on one side of zero ends at twice its peak, so the peak sits at half height."""
FLAT_LIMIT = 1.0
"""UI-221: an all-zero sum or difference is drawn on −1…1; an empty ratio on 0…1 (EMPTY_LIMITS)."""
EMPTY_LIMITS = (0.0, 1.0)
RATIO_REFERENCE = 1.0
"""UI-220: the dashed 1× line of the ratio chart."""

EXPORT_TITLE = "导出计算结果"
EXPORT_FORMATS_LABEL = "导出格式"
EXPORT_FORMATS: tuple[tuple[str, str, bool], ...] = (("csv", "CSV", True), ("xlsx", "Excel (.xlsx)", False))
"""(kind, label, checked at first) of the format dialog (EXP-026; UI-233)."""
EXPORT_CANCEL = "取消"
EXPORT_DONE_TITLE = "导出完成"
EXPORT_FAILED_TITLE = "导出失败"


def operation_label(operation: str) -> str:
    """The label of `operation` ("加法 A+B", ...); ValueError for anything but the three operations (MATH-011)."""
    for key, label in OPERATIONS:
        if key == operation:
            return label
    raise ValueError(f"不支持的运算：{operation}")


def initial_sources(keys: Sequence[str]) -> tuple[str | None, str | None]:
    """UI-156: A takes the first source and B the second; with one source both take it; none gives (None, None)."""
    if not keys:
        return None, None
    return keys[0], keys[min(1, len(keys) - 1)]


def record_label(record: Record, format_time: TimeFormatter) -> str:
    """'#<id> | <Beijing time>', the text of one entry of a record list (format_time: database.format_beijing_time)."""
    return f"#{record['id']} | {format_time(record['acquired_at'])}"


def spectrum_values(points: Sequence[float], coefficient: int | None) -> np.ndarray:
    """MainWindow._operation_values: raw counts / 10^coefficient, not normalised (UI-211)."""
    values: np.ndarray = np.asarray(points, dtype=float) / (10 ** (coefficient or 0))
    return values


def input_title(label: str, device: str | None = None, record_id: int | None = None) -> str:
    """Title of the A or B chart; without a usable record '光谱 A：未选择记录'."""
    if device is None or record_id is None:
        return f"光谱 {label}：未选择记录"
    return f"光谱 {label}：{device} · #{record_id}"


def legend(label: str) -> str:
    return f"光谱 {label}"


def time_difference(a_record: Record, b_record: Record) -> float | None:
    """B − A in seconds; old zone-suffixed times are compared in their own zone, plain times as Beijing time
    (UI-197). None when either time is missing or unreadable. Also the export's 采集时间差 cell."""
    try:
        stamps = [datetime.fromisoformat(record['acquired_at']) for record in (a_record, b_record)]
        stamps = [stamp.replace(tzinfo=BEIJING_TZ) if stamp.tzinfo is None else stamp for stamp in stamps]
        return (stamps[1] - stamps[0]).total_seconds()
    except (ValueError, TypeError, KeyError):
        return None


def time_difference_text(difference: float | None) -> str:
    """UI-208: '采集时间差：B 比 A 晚 12.345 秒' (or 早, 'A 与 B 相同', '不可用')."""
    if difference is None:
        text = TIME_UNAVAILABLE
    elif difference == 0:
        text = TIME_SAME
    else:
        text = f"B 比 A {'晚' if difference > 0 else '早'} {abs(difference):.3f} 秒"
    return f"{TIME_PREFIX}{text}"


def spectrum_y_limits(values: np.ndarray) -> tuple[float, float]:
    """y range SpectrumCanvas.plot gives one spectrum on 350–1050 nm: from 0 with the peak at 0.618 of the height,
    or 8 % padding around a span reaching below zero."""
    finite = values[np.isfinite(values)]
    low, high = (float(np.min(finite)), float(np.max(finite))) if finite.size else EMPTY_LIMITS
    if low < 0:
        padding = max((high - low) * NEGATIVE_PADDING_FRACTION, MINIMUM_SPAN)
        return low - padding, high + padding
    return 0.0, max(high / PEAK_HEIGHT_FRACTION, MINIMUM_SPAN)


def common_y_limits(*limits: tuple[float, float]) -> tuple[float, float]:
    """UI-209: the A and B charts share one y range, the union of their own ranges."""
    return min(low for low, _ in limits), max(high for _, high in limits)


def result_title(operation: str) -> str:
    """UI-217: '计算结果：加法 A+B'."""
    return f"{RESULT_TITLE}：{operation_label(operation)}"


def result_y_label(operation: str) -> str:
    return RATIO_Y_LABEL if operation == DIVIDE else POWER_Y_LABEL


def plotted_result(a: np.ndarray, b: np.ndarray, out: np.ndarray, operation: str) -> np.ndarray:
    """The plotted result: a ratio keeps only the points passing the 2 % display filter (UI-218, MATH-014); a sum or
    difference is plotted whole (MATH-021). The full result `out` is not changed (MATH-020)."""
    if operation != DIVIDE:
        return out
    _, mask = ratio_display_mask(a, b)
    return np.where(mask, out, np.nan)


def result_y_limits(plotted: np.ndarray, operation: str) -> tuple[float, float]:
    """y range of the result chart, from the plotted finite values only (UI-214, UI-220..UI-222)."""
    finite = plotted[np.isfinite(plotted)]
    if not finite.size:
        return EMPTY_LIMITS
    low, high = float(np.min(finite)), float(np.max(finite))
    if operation == DIVIDE:
        padding = max(
            (high - low) * RATIO_PADDING_SPAN, max(abs(low), abs(high)) * RATIO_PADDING_MAGNITUDE, MINIMUM_SPAN
        )
        return max(0.0, low - padding), high + padding
    low, high = min(0.0, low), max(0.0, high)
    if low == high:
        return -FLAT_LIMIT, FLAT_LIMIT
    if low == 0:
        return 0.0, high * ZERO_SIDE_FACTOR
    if high == 0:
        return low * ZERO_SIDE_FACTOR, 0.0
    padding = (high - low) * SIGNED_PADDING_SPAN
    return low - padding, high + padding


def has_plotted_values(plotted: np.ndarray) -> bool:
    return bool(np.isfinite(plotted).any())


def reference_line_visible(plotted: np.ndarray, limits: tuple[float, float], operation: str) -> bool:
    """UI-220: the 1× line of a ratio shows only when there are plotted ratios and 1 lies inside the y range."""
    return operation == DIVIDE and has_plotted_values(plotted) and limits[0] <= RATIO_REFERENCE <= limits[1]


def export_done_text(count: int, directory: str) -> str:
    """Message after a successful export (V1.0.3 QMessageBox '导出完成')."""
    return f"已保存 {count} 个文件：\n{directory}"


def export_failed_text(directory: str, completed: Sequence[str], error: object) -> str:
    """EXP-020: the result directory, the files already written and the error (V1.0.3 QMessageBox '导出失败')."""
    return f"保存目录：{directory}\n已完成：{', '.join(completed) or '无'}\n{error}"
