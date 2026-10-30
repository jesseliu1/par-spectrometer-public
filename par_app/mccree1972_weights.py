from __future__ import annotations

"""McCree 1972 Table III / IV 的可追溯 25 nm 平均作用权重。

来源：McCree, K. J. (1972), Agricultural Meteorology 9, 191–216。
公开转录表的最后一个可追溯节点为 725 nm；本模块不对 725 nm 之后做外推。
"""

from bisect import bisect_left
from typing import Iterable, Literal

MCCREE_SOURCE = "McCree 1972 Table III / IV"
MCCREE_START_NM = 350
MCCREE_END_NM = 725
MCCREE_WAVELENGTHS_NM: tuple[int, ...] = (
    350, 375, 400, 425, 450, 475, 500, 525,
    550, 575, 600, 625, 650, 675, 700, 725,
)
MCCREE_FIELD_MEAN: tuple[float, ...] = (
    0.02, 0.12, 0.42, 0.68, 0.70, 0.63, 0.65, 0.72,
    0.82, 0.91, 0.97, 1.00, 0.90, 0.90, 0.48, 0.23,
)
MCCREE_CHAMBER_MEAN: tuple[float, ...] = (
    0.16, 0.45, 0.66, 0.76, 0.75, 0.68, 0.71, 0.74,
    0.87, 0.95, 1.00, 1.00, 0.94, 0.92, 0.44, 0.20,
)
MCCREE_VARIANTS = {"field": MCCREE_FIELD_MEAN, "chamber": MCCREE_CHAMBER_MEAN}


def weight_at_wavelength(wavelength_nm: float, variant: Literal["field", "chamber"] = "field") -> float:
    """在原始表覆盖范围内作分段线性插值；范围外严格返回 0。"""
    wavelength = float(wavelength_nm)
    if wavelength < MCCREE_START_NM or wavelength > MCCREE_END_NM:
        return 0.0
    values = MCCREE_VARIANTS[variant]
    index = bisect_left(MCCREE_WAVELENGTHS_NM, wavelength)
    if index == 0:
        return values[0]
    if index == len(MCCREE_WAVELENGTHS_NM):
        return values[-1]
    if MCCREE_WAVELENGTHS_NM[index] == wavelength:
        return values[index]
    left = index - 1
    x0, x1 = MCCREE_WAVELENGTHS_NM[left], MCCREE_WAVELENGTHS_NM[index]
    y0, y1 = values[left], values[index]
    return y0 + (y1 - y0) * (wavelength - x0) / (x1 - x0)


def build_weight_curve(wavelengths_nm: Iterable[float], variant: Literal["field", "chamber"] = "field") -> tuple[float, ...]:
    return tuple(weight_at_wavelength(wavelength, variant) for wavelength in wavelengths_nm)
