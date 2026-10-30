"""Spectral calibration logic: field table, availability, readback validation, PCHIP preview and node dragging.

Moved unchanged out of par_app/ui.py (R-8-1 stage one "logic extraction"; MainWindow and CalibrationCanvas keep
thin wrappers with unchanged signatures):
  MainWindow._build_calibration (field names, scales, range) -> CALIBRATION_FIELDS, field_scale, FIELD_LIMIT
  MainWindow._calibration_available             -> calibration_available (the UI reads the device, config,
                                                   snapshot and coordinator and passes the facts in)
  MainWindow._apply_hardware_calibration (checks) -> parse_readback (+ wavelengths_increasing, limits_ordered)
  MainWindow._calibration_changed (dirty flag)  -> is_dirty
  MainWindow._refresh_calibration_plots (check) -> wavelengths_out_of_order
  MainWindow.write_calibration (checks, text)   -> is_writable, change_lines
  MainWindow._calibration_nodes_changed (values) -> node_values
  MainWindow._format_mcu_timestamp              -> format_mcu_timestamp (time zone passed in)
  MainWindow._task_finished (MCU status texts)  -> status_texts (CalibrationStatusTexts)
  CalibrationCanvas._pchip                      -> pchip
  CalibrationCanvas.draw_calibration (numbers)  -> correction_curve (CorrectionCurve)
  CalibrationCanvas._on_press / _on_motion      -> nearest_node, dragged_node
Specs: MAINT-034/038/041/042/101/108/133/134/141/142/143, UI-127/129 (only the 代码锚点 changed).

Nothing here talks to the device. Reading and writing the calibration stay in the UI and the coordinator exactly
as before (R-4-2 red line 2): the UI still queues "calibration_read" / "calibration_write" itself, with the same
dict, in the same order. No clock is read; the time zone for the MCU timestamp is passed in by the UI.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, tzinfo

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

# Hardware calibration object 3, in the order the editor builds its fields. This order is also the key order of
# the value dict: it is what write_calibration lists in the confirmation and passes to "calibration_write".
CALIBRATION_FIELDS = (
    "x_min",
    "x_max",
    "x1",
    "x2",
    "x3",
    "y0",
    "y1",
    "y2",
    "y3",
    "y4",
    "k_global",
    "limit_min",
    "limit_max",
)
NODE_X_FIELDS = ("x_min", "x1", "x2", "x3", "x_max")
NODE_Y_FIELDS = ("y0", "y1", "y2", "y3", "y4")
NODE_FIELDS = tuple(zip(NODE_X_FIELDS, NODE_Y_FIELDS, strict=True))  # P0..P4 as (x name, y name)
PERCENT_SCALE = 100
"""y0..y4, limit_min and limit_max are protocol ratios shown as percent (UI-127, MAINT-040)."""
FIELD_LIMIT = 1_000_000
"""Every field accepts -1e6..1e6 in protocol units (the editor's spin box range); a readback outside is invalid."""

CURVE_POINTS = 701
"""Preview resolution: 701 points from P0 to P4 (one per nm when the nodes span 350..1050 nm)."""
PREVIEW_MIN_NM = 350.0
PREVIEW_MAX_NM = 1050.0
NODE_MIN_SPACING_NM = 1.0
"""A dragged node stays at least 1 nm away from its neighbours."""
PICK_X_SPAN_NM = 700
"""A press picks the nearest node in axes-normalised distance: x over 700 nm, y over the visible y span."""
PICK_RADIUS = 0.04

MCU_TIMESTAMP_MAX = 0xFFFFFFFF
VERSION_NODES_MAX = 255
NODE_COUNT_MASK = 0x0F
VERSION_SHIFT = 4


def field_scale(name: str) -> int:
    """Display scale of a field: percent fields ×100, wavelengths and k_global as stored."""
    return PERCENT_SCALE if name.startswith('y') or name.startswith('limit_') else 1


def calibration_available(
    *, device_enabled: bool, configured: bool, online: object, faulty: bool, maintenance: bool, halted: bool
) -> bool:
    """Reading/editing the calibration needs an enabled, configured, online, healthy device, no maintenance and
    no acquisition halt (MAINT-133/134). device_enabled is False when the target device does not exist."""
    return bool(device_enabled and configured and online and not faulty and not maintenance and not halted)


def wavelengths_increasing(values: Mapping[str, float]) -> bool:
    return values["x_min"] < values["x1"] < values["x2"] < values["x3"] < values["x_max"]


def limits_ordered(values: Mapping[str, float]) -> bool:
    return not values["limit_min"] > values["limit_max"]


def is_writable(values: Mapping[str, float]) -> bool:
    """write_calibration refuses node wavelengths that do not increase or a lower limit above the upper one."""
    return wavelengths_increasing(values) and limits_ordered(values)


def wavelengths_out_of_order(values: Mapping[str, float]) -> bool:
    """The preview's own check (any x not below the next one). Kept as written in V1.0.2: unlike
    `not wavelengths_increasing(values)` it is False when a wavelength is NaN, which the editor never holds."""
    return (
        values["x_min"] >= values["x1"]
        or values["x1"] >= values["x2"]
        or values["x2"] >= values["x3"]
        or values["x3"] >= values["x_max"]
    )


def parse_readback(payload: Mapping[str, object]) -> dict[str, float] | None:
    """All 13 fields as floats in CALIBRATION_FIELDS order, or None when any field is missing, not a number,
    not finite or outside ±FIELD_LIMIT, the node wavelengths do not increase, or limit_min > limit_max
    (MAINT-101: nothing is applied unless the whole readback is valid)."""
    calibration: dict[str, float] = {}
    for name in CALIBRATION_FIELDS:
        try:
            value = float(payload[name])  # type: ignore[arg-type]  # any stored value; float() decides
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if not np.isfinite(value) or not -FIELD_LIMIT <= value <= FIELD_LIMIT:
            return None
        calibration[name] = value
    if not wavelengths_increasing(calibration):
        return None
    if not limits_ordered(calibration):
        return None
    return calibration


def is_dirty(baseline: Mapping[str, float] | None, values: Mapping[str, float]) -> bool:
    """Pending (unwritten) edits exist once a readback is held and the values differ from it."""
    return baseline is not None and values != baseline


def change_lines(baseline: Mapping[str, float] | None, values: Mapping[str, float]) -> str:
    """'name: old → new' per field for the write confirmation (MAINT-034); no readback held shows '—'."""
    return "\n".join(
        f"{name}: {baseline.get(name, '—') if baseline else '—'} → {value}" for name, value in values.items()
    )


def pchip(x_nodes: FloatArray, y_nodes: FloatArray, x_values: FloatArray) -> FloatArray:
    """与 MCU 同类的单调三次 Hermite 插值预览。"""
    h = np.diff(x_nodes)
    slopes = np.diff(y_nodes) / h
    derivatives = np.zeros(5, dtype=float)
    for index in range(1, 4):
        if slopes[index - 1] == 0 or slopes[index] == 0 or np.sign(slopes[index - 1]) != np.sign(slopes[index]):
            derivatives[index] = 0
        else:
            w1, w2 = 2 * h[index] + h[index - 1], h[index] + 2 * h[index - 1]
            derivatives[index] = (w1 + w2) / (w1 / slopes[index - 1] + w2 / slopes[index])
    derivatives[0] = ((2 * h[0] + h[1]) * slopes[0] - h[0] * slopes[1]) / (h[0] + h[1])
    derivatives[-1] = ((2 * h[-1] + h[-2]) * slopes[-1] - h[-1] * slopes[-2]) / (h[-1] + h[-2])
    result = np.empty_like(x_values, dtype=float)
    for index, x in enumerate(x_values):
        segment = min(max(np.searchsorted(x_nodes, x) - 1, 0), 3)
        x0, _x1, span = x_nodes[segment], x_nodes[segment + 1], h[segment]
        t = (x - x0) / span
        result[index] = (
            (2 * t**3 - 3 * t**2 + 1) * y_nodes[segment]
            + (t**3 - 2 * t**2 + t) * derivatives[segment] * span
            + (-2 * t**3 + 3 * t**2) * y_nodes[segment + 1]
            + (t**3 - t**2) * derivatives[segment + 1] * span
        )
    return result


@dataclass(frozen=True)
class CorrectionCurve:
    """What the calibration preview draws, in percent: the combined correction the MCU applies per wavelength
    (PCHIP node correction + (k_global − 1), clipped to [limit_min, limit_max])."""

    node_x: FloatArray
    nodes: FloatArray
    """(5, 2): node wavelength and its clipped combined correction (the draggable points)."""
    curve_x: FloatArray
    curve_y: FloatArray
    global_percent: float
    limit_min_percent: float
    limit_max_percent: float


def correction_curve(calibration: Mapping[str, float]) -> CorrectionCurve:
    x = np.array([calibration[key] for key in NODE_X_FIELDS], dtype=float)
    # MCU 对每个波长点先叠加 PCHIP 修正和 k_global，再将结果限制到上下限。
    # 图表显示最终生效的综合修正百分比：k_global=0.87 且各 y=0 时即为 -13%。
    node_correction = np.array([calibration[key] for key in NODE_Y_FIELDS], dtype=float) * 100.0
    global_percent = (float(calibration["k_global"]) - 1.0) * 100.0
    limit_min_percent = float(calibration["limit_min"]) * 100.0
    limit_max_percent = float(calibration["limit_max"]) * 100.0
    nodes = np.column_stack((x, np.clip(node_correction + global_percent, limit_min_percent, limit_max_percent)))
    curve_x = np.linspace(x[0], x[-1], CURVE_POINTS)
    curve_y = np.clip(pchip(x, node_correction, curve_x) + global_percent, limit_min_percent, limit_max_percent)
    return CorrectionCurve(x, nodes, curve_x, curve_y, global_percent, limit_min_percent, limit_max_percent)


def node_values(
    values: Mapping[str, float],
    nodes: FloatArray,
    global_percent: float,
    limit_min_percent: float,
    limit_max_percent: float,
) -> dict[str, float]:
    """New x/y values after the five preview nodes moved (MAINT-038): every x takes the node wavelength; a y is
    recomputed from the node's combined percent only when that node's height differs from the clipped value it
    was drawn at, so untouched nodes keep their raw (even out-of-limit) correction."""
    updated: dict[str, float] = {}
    for index, (x_name, y_name) in enumerate(NODE_FIELDS):
        previous_percent = float(np.clip(values[y_name] * 100 + global_percent, limit_min_percent, limit_max_percent))
        updated[x_name] = float(nodes[index, 0])
        updated[y_name] = values[y_name]
        if float(nodes[index, 1]) != previous_percent:
            updated[y_name] = (float(nodes[index, 1]) - global_percent) / 100.0
    return updated


def nearest_node(nodes: FloatArray, x: float, y: float, ylim: tuple[float, float]) -> int | None:
    """Index of the node a press at (x, y) grabs, or None when the nearest one is too far away."""
    distances = np.hypot((nodes[:, 0] - x) / PICK_X_SPAN_NM, (nodes[:, 1] - y) / max(ylim[1] - ylim[0], 1))
    index = int(np.argmin(distances))
    return index if distances[index] < PICK_RADIUS else None


def dragged_node(
    nodes: FloatArray, index: int, x: float, y: float, limit_min_percent: float, limit_max_percent: float
) -> tuple[float, float]:
    """Where node `index` goes when dragged to (x, y): between its neighbours (1 nm apart; P0 and P4 stop at
    350/1050 nm) and inside the correction limits."""
    left = PREVIEW_MIN_NM if index == 0 else nodes[index - 1, 0] + NODE_MIN_SPACING_NM
    right = PREVIEW_MAX_NM if index == len(NODE_FIELDS) - 1 else nodes[index + 1, 0] - NODE_MIN_SPACING_NM
    return min(max(x, left), right), min(max(y, limit_min_percent), limit_max_percent)


def format_mcu_timestamp(value: object, tz: tzinfo) -> str:
    """将 MCU 的 32 位 Unix 秒级时间戳显示为北京时间，不改变其 UTC epoch 语义。"""
    try:
        timestamp = int(value)  # type: ignore[call-overload]  # any decoded value; int() decides
        if not 1 <= timestamp <= MCU_TIMESTAMP_MAX:
            raise ValueError
        return f"{datetime.fromtimestamp(timestamp, tz):%Y-%m-%d %H:%M:%S}（北京时间）"
    except (TypeError, ValueError, OverflowError, OSError):
        return "未设置 / 无效时间戳"


@dataclass(frozen=True)
class CalibrationStatusTexts:
    status: str
    error: str
    status_tooltip: str
    error_tooltip: str
    version: str
    time: str


def _status_text(code: object) -> str:
    if code == 1:
        return '校准状态：已校准'
    return '校准状态：未读取' if code is None else f'校准状态码：{code}'


def _error_text(code: object) -> str:
    if code == 0:
        return '错误状态：无错误'
    return '错误状态：未读取' if code is None else f'错误码：{code}'


def _version_text(version_nodes: object) -> str:
    if isinstance(version_nodes, int) and 0 <= version_nodes <= VERSION_NODES_MAX:
        return f'版本 / 节点数：v{version_nodes >> VERSION_SHIFT} / {version_nodes & NODE_COUNT_MASK}'
    return '版本 / 节点数：—'


def status_texts(status: object, tz: tzinfo) -> CalibrationStatusTexts:
    """Calibration information texts from the readback's _mcu_status (MAINT-041/042/141/142/143, UI-129).
    Anything that is not a dict counts as an empty status: missing values show "未读取" / "—", never old ones."""
    if not isinstance(status, dict):
        status = {}
    status_code = status.get('status')
    error_code = status.get('error')
    return CalibrationStatusTexts(
        status=_status_text(status_code),
        error=_error_text(error_code),
        status_tooltip=f'原始校准状态码：{status_code}' if status_code is not None else '',
        error_tooltip=f'原始错误码：{error_code}' if error_code is not None else '',
        version=_version_text(status.get('version_nodes')),
        time=format_mcu_timestamp(status.get('timestamp'), tz).removesuffix('（北京时间）'),
    )
