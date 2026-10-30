"""Wavelength-coloured fill and the four reference curves of the spectrum charts, for the ui-v2 local service.

A copy, not a move: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2). The fill
colour is SpectrumCanvas._wavelength_to_rgb and the fill opacity SpectrumCanvas.plot (one series 0.55); the curves,
labels, right axis label and its top are SpectrumCanvas._draw_response_overlays. The curve values come from the
same functions V1.0.3 calls (math_ops.chlorophyll_weight_curves, mccree1972_weights.build_weight_curve,
photopic_weights.build_photopic_curve), never from a stored copy (red line 4: one source for weight curves).
tests/api/test_reference_curves_parity.py compares every value with the V1.0.3 SpectrumCanvas.

Specs: UI-168 (four curves on the overview and history charts, no toggles), UI-278, UI-317 (coloured fill).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..math_ops import WAVELENGTHS, chlorophyll_weight_curves
from ..mccree1972_weights import MCCREE_END_NM, MCCREE_START_NM, build_weight_curve
from ..photopic_weights import build_photopic_curve

FILL_OPACITY = 0.55
"""SpectrumCanvas.plot: one series is filled at alpha 0.55 (every chart of the web pages shows one series)."""
RESPONSE_AXIS_LABEL = "归一化响应（叶绿素 / McCree）"
RESPONSE_HEADROOM = 1.5
"""_draw_response_overlays: the right axis tops at 1.5 × the highest chlorophyll / McCree peak (not V(λ))."""


@dataclass(frozen=True)
class ReferenceCurve:
    key: str
    label: str
    """Legend text, as in V1.0.3."""
    line: str
    """"dashed", "dotted" or "dashdot" (matplotlib "--", ":", "-.")."""
    width: float
    x: tuple[float, ...]
    y: tuple[float, ...]


@dataclass(frozen=True)
class ReferenceCurves:
    curves: tuple[ReferenceCurve, ...]
    axis_label: str
    axis_max: float
    fill_start: int
    fill_colors: tuple[tuple[float, float, float], ...]
    """RGB 0–1 of each wavelength from fill_start, 1 nm apart; segment i (x_i to x_i+1) takes colour i."""
    fill_opacity: float


def wavelength_to_rgb(wavelength: float) -> tuple[float, float, float]:
    """沿用旧界面的可见光近似映射；可见光外以灰色表示。"""
    w = float(wavelength)
    if w < 380 or w > 780:
        return (0.55, 0.55, 0.55)
    if w < 440:
        red, green, blue = -(w - 440) / 60, 0.0, 1.0
    elif w < 490:
        red, green, blue = 0.0, (w - 440) / 50, 1.0
    elif w < 510:
        red, green, blue = 0.0, 1.0, -(w - 510) / 20
    elif w < 580:
        red, green, blue = (w - 510) / 70, 1.0, 0.0
    elif w < 645:
        red, green, blue = 1.0, -(w - 645) / 65, 0.0
    else:
        red, green, blue = 1.0, 0.0, 0.0
    if w < 420:
        factor = 0.3 + 0.7 * (w - 380) / 40
    elif w > 700:
        factor = 0.3 + 0.7 * (780 - w) / 80
    else:
        factor = 1.0
    r, g, b = (max(0.0, min(value * factor, 1.0)) for value in (red, green, blue))
    return (r, g, b)


def _curve(key: str, label: str, line: str, width: float, x: np.ndarray, y: np.ndarray) -> ReferenceCurve:
    return ReferenceCurve(key, label, line, width, tuple(float(v) for v in x), tuple(float(v) for v in y))


def reference_curves() -> ReferenceCurves:
    """The curves exactly as _draw_response_overlays plots them, in its order."""
    chlorophyll_x = np.arange(400, 700, dtype=float)
    chl_a_y, chl_b_y = chlorophyll_weight_curves(chlorophyll_x)
    # McCree 仅使用可追溯的 350–725 nm 原始 25 nm 表；相邻节点之间为分段线性插值，绝不外推。
    mccree_x = np.arange(MCCREE_START_NM, MCCREE_END_NM + 1, dtype=float)
    mccree_y = np.asarray(build_weight_curve(mccree_x, variant="field"), dtype=float)
    mccree_y /= max(float(np.max(mccree_y)), 1e-9)
    photopic_x = np.arange(360, 831, dtype=float)
    photopic_y = np.asarray(build_photopic_curve(photopic_x), dtype=float)
    top = max(float(np.max(chl_a_y)), float(np.max(chl_b_y)), float(np.max(mccree_y))) * RESPONSE_HEADROOM
    return ReferenceCurves(
        curves=(
            _curve("chlorophyll_a", "叶绿素 A", "dashed", 1.6, chlorophyll_x, chl_a_y),
            _curve("chlorophyll_b", "叶绿素 B", "dotted", 1.6, chlorophyll_x, chl_b_y),
            _curve("mccree", "McCree 相对作用曲线（参考）", "dashdot", 1.7, mccree_x, mccree_y),
            _curve("photopic", "人眼明视觉响应 V(λ，虚线)", "dashed", 1.6, photopic_x, photopic_y),
        ),
        axis_label=RESPONSE_AXIS_LABEL,
        axis_max=top,
        fill_start=int(WAVELENGTHS[0]),
        fill_colors=tuple(wavelength_to_rgb(w) for w in WAVELENGTHS),
        fill_opacity=FILL_OPACITY,
    )
