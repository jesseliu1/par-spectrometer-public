"""Display rules of the history page (历史回放) for the ui-v2 local service (stage two, route C).

These are copies, not moves: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2), so
the V1.0.x window keeps its own code and this module repeats the same rules for the API.
tests/api/test_history_parity.py runs both on the same records and compares every text, so the two copies cannot
drift apart unnoticed.

Origin in par_app/ui.py (V1.0.3):
  MainWindow._is_single_capture            -> is_single_capture
  MainWindow.refresh_history (row values)  -> exposure_text, result_text, exposure_style
  MainWindow._show_history_details         -> review_text, elapsed_text, DETAIL_GROUPS (the 7 groups / 54 values)
  MainWindow.show_history_spectrum         -> status_text, status_level, spectrum_values
Deliberate differences from V1.0.3, each decided or forced by the API (also listed in the PR):
  * exposure_style: new single-capture records are "normal" whatever their exposure (D-154, UI-052); V1.0.3 still
    colours every non-"正常" exposure orange.
  * review_text: a quality_json that is not a JSON object is read as "no review information" (D-126 wording); the
    V1.0.3 detail panel raised instead and left the panel half-filled.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np

from ..math_ops import WAVELENGTHS
from .metrics import format_metric

JsonObject = Mapping[str, Any]
DetailField = tuple[str, str, str]
DetailGroup = tuple[str, tuple[DetailField, ...]]

EXPOSURE_TEXTS = {0: "正常", 1: "过曝光", 2: "欠曝光"}
EXPOSURE_NORMAL = "正常"
EXPOSURE_UNKNOWN = "未知"
SPECTRUM_START_NM = int(WAVELENGTHS[0])
SPECTRUM_STEP_NM = int(WAVELENGTHS[1] - WAVELENGTHS[0])
PHOTON = "µmol·m⁻²·s⁻¹"
UNITLESS = "无量纲"
SPECIAL_RENDERING_INDICES = range(1, 16)

DETAIL_GROUPS: tuple[DetailGroup, ...] = (
    (
        "常用光量",
        (
            ("lux", "照度", "lx"),
            ("irradiance", "350–1050 nm 总辐照度", "W/m²"),
            ("par", "PAR 波段辐照度", "W/m²"),
            ("ppfd", "PPFD", PHOTON),
            ("pfd", "PFD", PHOTON),
            ("ypfd", "McCree-YPFD", PHOTON),
            ("chlorophyll_a_ypfd", "叶绿素 A 加权光子通量", PHOTON),
            ("chlorophyll_b_ypfd", "叶绿素 B 加权光子通量", PHOTON),
        ),
    ),
    (
        "波段光子通量",
        (
            ("pfd_uv", "紫外 PFD", PHOTON),
            ("pfd_b", "蓝光 PFD", PHOTON),
            ("pfd_g", "绿光 PFD", PHOTON),
            ("pfd_r", "红光 PFD", PHOTON),
            ("pfd_far_red", "远红光 PFD", PHOTON),
            ("pfd_nir", "近红外 PFD", PHOTON),
        ),
    ),
    (
        "光谱比例",
        (
            ("blue_red", "蓝红光子比 B:R", UNITLESS),
            ("red_far_red", "红远红光子比 R:FR", UNITLESS),
            ("blue_green", "蓝绿光子比 B:G", UNITLESS),
            ("blue_percent", "蓝光占 PPFD 比例", "%"),
            ("red_percent", "红光占 PPFD 比例", "%"),
            ("far_red_percent", "远红光占扩展 PPFD 比例", "%"),
        ),
    ),
    (
        "光色与峰值",
        (
            ("cct", "相关色温 CCT", "K"),
            ("ra", "一般显色指数 Ra", UNITLESS),
            ("duv", "色偏差 Duv", UNITLESS),
            ("peak_wavelength_nm", "PAR 峰值波长", "nm"),
            ("peak_value", "PAR 峰值功率", "mW·nm⁻¹"),
            ("extended_peak_wavelength_nm", "全谱峰值波长", "nm"),
            ("extended_peak_value", "全谱峰值功率", "mW·nm⁻¹"),
        ),
    ),
    (
        "扩展波段光量",
        (
            ("extended_par", "400–750 nm 扩展辐照度", "W/m²"),
            ("extended_ppfd", "400–750 nm 扩展 PPFD", PHOTON),
            ("extended_pfd", "350–1050 nm 全谱 PFD", PHOTON),
            ("pfd_fr", "700–780 nm PFD", PHOTON),
            ("extended_pfd_fr", "700–1050 nm PFD", PHOTON),
        ),
    ),
    ("特殊显色指数", tuple((f"r{index}", f"特殊显色指数 R{index}", UNITLESS) for index in SPECIAL_RENDERING_INDICES)),
    (
        "色度与三刺激值",
        (
            ("X", "三刺激值 X", ""),
            ("Y", "三刺激值 Y", ""),
            ("Z", "三刺激值 Z", ""),
            ("u", "CIE u", UNITLESS),
            ("v", "CIE v", UNITLESS),
            ("x", "CIE x", UNITLESS),
            ("y", "CIE y", UNITLESS),
        ),
    ),
)


def _quality(record: JsonObject) -> object:
    try:
        return json.loads(record.get("quality_json") or "{}")
    except (TypeError, ValueError, RecursionError):
        return None


def is_single_capture(record: JsonObject) -> bool:
    """True for records written by the single-capture strategy (quality_json strategy == "single_capture")."""
    quality = _quality(record)
    return isinstance(quality, dict) and quality.get("strategy") == "single_capture"


def exposure_text(record: JsonObject) -> str:
    """History "曝光" column: 正常 / 过曝光 / 欠曝光, anything else 未知."""
    return EXPOSURE_TEXTS.get(record.get("exposure_status"), EXPOSURE_UNKNOWN)  # type: ignore[arg-type]


def result_text(record: JsonObject) -> str:
    return "成功" if record.get("success") else "失败"


def exposure_style(record: JsonObject) -> Literal["normal", "warn"]:
    """Warning colour of the exposure column: non-"正常" values warn, except on new single-capture records (D-154)."""
    if exposure_text(record) == EXPOSURE_NORMAL or is_single_capture(record):
        return "normal"
    return "warn"


def review_text(record: JsonObject) -> str:
    """ "采集校验" text of the history detail header (UI-030, UI-036; D-126 for legacy records)."""
    if not record.get("success"):
        return "未完成采集"
    if is_single_capture(record):
        return "单次读取完成"
    quality = _quality(record)
    confirmed = quality.get("confirmed", None) if isinstance(quality, dict) else None
    if record.get("dli_eligible") == 0 or confirmed is False:
        return "复核未完成"
    if confirmed is True:
        return "已完成"
    return "未记录"


def elapsed_text(record: JsonObject) -> str:
    """ "采集耗时" value (unit ms shown next to it), one decimal; missing shows "—"."""
    return format_metric(record.get("elapsed_ms"), 1)


def status_text(record: JsonObject) -> str:
    """Status word of the history spectrum card: 采集成功/失败 plus single-capture / review suffix."""
    success = bool(record.get("success"))
    text = "采集成功" if success else "采集失败"
    if success and is_single_capture(record):
        text += " · 单次读取完成"
    elif success and record.get("dli_eligible") == 0:
        text += " · 复核未完成（不计入 DLI）"
    return text


def status_level(record: JsonObject) -> Literal["ok", "warn", "error"]:
    """Colour class of the status card: failure red, unreviewed or non-normal exposure amber (not single capture)."""
    if not record.get("success"):
        return "error"
    if not is_single_capture(record) and (exposure_text(record) != EXPOSURE_NORMAL or record.get("dli_eligible") == 0):
        return "warn"
    return "ok"


def spectrum_values(points: Sequence[float], coefficient: int | None) -> list[float]:
    """Plotted spectral irradiance: raw MCU counts / 10^coefficient (W·m⁻²·nm⁻¹), as the history chart draws it."""
    values = np.asarray(points, dtype=float) / (10 ** (coefficient or 0))
    return [float(value) for value in values]
