from __future__ import annotations

import numpy as np

from .mccree1972_weights import build_weight_curve

WAVELENGTHS = np.arange(350, 1051, dtype=float)
CHLOROPHYLL_A_ANCHORS = ((400, .62), (430, 1.00), (460, .10), (500, .015), (550, .04),
                         (600, .10), (640, .17), (665, .87), (699, .006))
CHLOROPHYLL_B_ANCHORS = ((400, .10), (430, .40), (457, 1.00), (500, .04), (550, .04),
                         (600, .08), (640, .06), (665, .35), (699, 0))
# software_metrics 存储的 par、extended_par 为 W/m² ÷ 此值（旧版口径，不改存储；MATH-007、R-4-2 第 4 项）。
PAR_STORAGE_SCALE = 10.0


def chlorophyll_weight_curves(wavelengths: np.ndarray = WAVELENGTHS) -> tuple[np.ndarray, np.ndarray]:
    """返回与界面叠加曲线一致、峰值归一化为 1 的叶绿素 A/B 相对吸收权重。"""
    def interpolate(anchors: tuple[tuple[float, float], ...]) -> np.ndarray:
        x_nodes, y_nodes = zip(*anchors, strict=True)
        x_nodes, y_nodes = np.asarray(x_nodes, dtype=float), np.asarray(y_nodes, dtype=float)
        values = np.zeros_like(wavelengths, dtype=float)
        mask = (wavelengths >= x_nodes[0]) & (wavelengths <= x_nodes[-1])
        for index, wavelength in zip(np.flatnonzero(mask), wavelengths[mask], strict=True):
            segment = min(max(np.searchsorted(x_nodes, wavelength) - 1, 0), len(x_nodes) - 2)
            left, right = x_nodes[segment], x_nodes[segment + 1]
            t = (wavelength - left) / (right - left)
            p0 = y_nodes[max(segment - 1, 0)]
            p1, p2 = y_nodes[segment], y_nodes[segment + 1]
            p3 = y_nodes[min(segment + 2, len(y_nodes) - 1)]
            values[index] = .5 * ((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t + (-p0+3*p1-3*p2+p3)*t*t*t)
        values = np.maximum(values, 0.0)
        return values / max(float(np.max(values)), 1e-9)

    chlorophyll_a = interpolate(CHLOROPHYLL_A_ANCHORS)
    chlorophyll_b = interpolate(CHLOROPHYLL_B_ANCHORS)
    return chlorophyll_a, chlorophyll_b


def software_metrics(raw_points: list[int], coefficient: int) -> dict[str, float | int]:
    """按旧版 PAR 计算口径，从 701 点 MCU 原始谱生成概览指标。"""
    values = np.asarray(raw_points, dtype=float) / (10.0 ** max(0, coefficient))
    wavelengths = WAVELENGTHS
    # 采样间隔固定为 1 nm；沿用旧版的逐 nm 能量/光子积分口径。
    def energy(low_nm: int, high_nm: int) -> float:
        mask = (wavelengths >= low_nm) & (wavelengths <= high_nm)
        return float(np.sum(values[mask]))

    photon_factor = wavelengths * 8.35934e-3
    def photon(low_nm: int, high_nm: int) -> float:
        mask = (wavelengths >= low_nm) & (wavelengths <= high_nm)
        return float(np.sum(values[mask] * photon_factor[mask]))

    base_mask = (wavelengths >= 400) & (wavelengths <= 700)
    base_values = values[base_mask]
    base_wavelengths = wavelengths[base_mask]
    base_peak_index = int(np.argmax(base_values))
    extended_peak_index = int(np.argmax(values))
    watts = energy(350, 1050)
    ppfd = photon(400, 700)
    mccree_weights = np.asarray(build_weight_curve(wavelengths, variant="field"), dtype=float)
    chlorophyll_a, chlorophyll_b = chlorophyll_weight_curves(wavelengths)
    return {
        "peak_wavelength_nm": int(base_wavelengths[base_peak_index]),
        "peak_value": float(base_values[base_peak_index]),
        "integrated_irradiance": watts,
        "software_ppfd": ppfd,
        "par": energy(400, 700) / 10.0,
        "pfd": photon(350, 780),
        "ppfd": ppfd,
        "pfd_uv": photon(350, 399),
        "pfd_b": photon(400, 499),
        "pfd_g": photon(500, 599),
        "pfd_r": photon(600, 699),
        "pfd_fr": photon(700, 780),
        "pfd_far_red": photon(700, 750),
        "pfd_nir": photon(751, 1050),
        "mccree_ypfd": float(np.sum(values * photon_factor * mccree_weights)),
        "chlorophyll_a_ypfd": float(np.sum(values * photon_factor * chlorophyll_a)),
        "chlorophyll_b_ypfd": float(np.sum(values * photon_factor * chlorophyll_b)),
        "extended_peak_wavelength_nm": int(wavelengths[extended_peak_index]),
        "extended_peak_value": float(values[extended_peak_index]),
        "extended_par": energy(400, 750) / 10.0,
        "extended_pfd": photon(350, 1050),
        "extended_ppfd": photon(400, 750),
        "extended_pfd_uv": photon(350, 399),
        "extended_pfd_b": photon(400, 499),
        "extended_pfd_g": photon(500, 599),
        "extended_pfd_r": photon(600, 699),
        "extended_pfd_fr": photon(700, 1050),
    }


def display_metrics(metrics: dict) -> dict:
    """返回副本：par、extended_par 由存储口径还原为 W/m²（与界面显示一致，供导出使用）；None 和非数值原样保留。"""
    shown = dict(metrics)
    for key in ("par", "extended_par"):
        value = shown.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            shown[key] = value * PAR_STORAGE_SCALE
    return shown


def combine(a: np.ndarray, b: np.ndarray, operation: str) -> np.ndarray:
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "divide":
        result = np.full_like(a, np.nan, dtype=float)
        valid = np.isfinite(a) & np.isfinite(b) & (b != 0)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            np.divide(a, b, out=result, where=valid)
        result[~np.isfinite(result)] = np.nan
        return result
    raise ValueError(f"不支持的运算：{operation}")


def ratio_display_mask(a: np.ndarray, b: np.ndarray) -> tuple[float, np.ndarray]:
    values = np.concatenate((a, b))
    finite = values[np.isfinite(values)]
    peak = max(float(np.max(finite)), 0.) if finite.size else 0.
    threshold = peak * .02
    mask = np.isfinite(a) & np.isfinite(b) & (a >= threshold) & (b >= threshold) & (a > 0) & (b > 0)
    return threshold, mask
