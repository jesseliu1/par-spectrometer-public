"""Display conversion of stored acquisition metrics: PAR scaling, ratios, CCT rounding and text formats.

Moved unchanged out of par_app/ui.py (R-8-1 stage one "logic extraction"; MainWindow keeps thin wrappers):
  MainWindow._ratio                -> ratio
  MainWindow._cct_value            -> cct_value
  MainWindow._format_metric        -> format_metric
  MainWindow._record_metric_values -> record_metric_values
  MainWindow.refresh_overview      -> decode_record_metrics, iter_overview_kpi_texts, overview_core_metrics,
                                      overview_metric_entries, overview_secondary_metrics, format_entry_value
Specs: MATH-007 (extended_par follows the PAR ×10 display scaling), UI-014/UI-304 (integer CCT and peaks),
UI-017 (4-decimal chromaticity), UI-018 (54 detail values), UI-033 (missing value / zero denominator shows "—").

Inputs are the JSON objects stored in software_metrics_json / mcu_params_json. Their values are passed on
exactly as stored (no coercion), so old records and odd values behave as they did inside the UI.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

import numpy as np

# Decoded record JSON: values are whatever the database row holds (numbers, None, NaN, legacy shapes). Any is
# deliberate (R-1-3): these helpers pass stored values through untouched instead of inventing coercions.
JsonObject = Mapping[str, Any]
OverviewEntry = tuple[str, "float | str | None"]

EM_DASH = "—"
PAR_DISPLAY_FACTOR = 10
"""software_metrics stores par / extended_par ÷10 and the UI displays the stored value ×10. The par scaling itself is
V1.0.2 status quo guarded by R-4-2 red line 4 ("PAR ÷10"; no spec entry of its own); MATH-007 only says that
extended_par follows the same scaling."""

PHOTON_UNIT = "µmol·m⁻²·s⁻¹"
# Overview KPI cards in display order: key -> (source JSON, field, decimals, unit).
OVERVIEW_KPI_SOURCES: dict[str, tuple[str, str, int, str]] = {
    "lux": ("parameters", "lux", 1, "lx"),
    "irradiance": ("metrics", "integrated_irradiance", 3, "W/m²"),
    "ppfd": ("metrics", "ppfd", 3, PHOTON_UNIT),
    "ypfd": ("metrics", "mccree_ypfd", 3, PHOTON_UNIT),
    "chlorophyll_a_ypfd": ("metrics", "chlorophyll_a_ypfd", 3, PHOTON_UNIT),
    "chlorophyll_b_ypfd": ("metrics", "chlorophyll_b_ypfd", 3, PHOTON_UNIT),
}
# Labels already shown on the core card; the secondary overlay leaves them out.
OVERVIEW_FIXED_LABELS = frozenset(
    {"照度（lx）", "350–1050 nm 总辐照度（W/m²）", "PPFD（µmol·m⁻²·s⁻¹）", "McCree-YPFD（µmol·m⁻²·s⁻¹）"}
)
CHROMATICITY_KEYS = ("u", "v", "x", "y")


def ratio(numerator: float | None, denominator: float | None, multiplier: float = 1.0) -> float | None:
    """返回独立显示的光谱比例；分母为空或为零时不伪造数值。"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator) * multiplier


def cct_value(metrics: JsonObject, parameters: JsonObject) -> int | None:
    """Saved cct_kelvin, or for old records the hardware CCT; non-negative finite values round half up."""
    value = metrics.get("cct_kelvin", parameters.get("cct"))
    if isinstance(value, (int, float)) and np.isfinite(value) and value >= 0:
        return int(value + 0.5)
    return None


def format_metric(value: float | None, decimals: int = 3) -> str:
    """Fixed-decimal text; None and non-finite values show an em dash."""
    return EM_DASH if value is None or not np.isfinite(value) else f"{float(value):.{decimals}f}"


def scaled_par(value: float | None) -> float | None:
    """Stored par / extended_par -> displayed W·m⁻² (MATH-007); a missing value stays missing."""
    return None if value is None else value * PAR_DISPLAY_FACTOR


def decode_record_metrics(record: JsonObject) -> tuple[dict[str, Any], dict[str, Any]]:
    """(mcu parameters, software metrics) decoded from an acquisition row; empty columns decode to {}."""
    parameters = json.loads(record.get("mcu_params_json") or "{}")
    metrics = json.loads(record.get("software_metrics_json") or "{}")
    return parameters, metrics


def record_metric_values(record: JsonObject) -> dict[str, str]:
    """The 54 history-detail / all-metrics texts of one record, keyed like history_detail_values."""
    parameters, metrics = decode_record_metrics(record)
    values: dict[str, str] = {}
    for key, value, decimals in (
        ("lux", parameters.get("lux"), 1),
        ("irradiance", metrics.get("integrated_irradiance"), 3),
        ("par", scaled_par(metrics.get("par")), 3),
        ("ppfd", metrics.get("ppfd"), 3),
        ("pfd", metrics.get("pfd"), 3),
        ("ypfd", metrics.get("mccree_ypfd"), 3),
        ("chlorophyll_a_ypfd", metrics.get("chlorophyll_a_ypfd"), 3),
        ("chlorophyll_b_ypfd", metrics.get("chlorophyll_b_ypfd"), 3),
        ("pfd_uv", metrics.get("pfd_uv"), 3),
        ("pfd_b", metrics.get("pfd_b"), 3),
        ("pfd_g", metrics.get("pfd_g"), 3),
        ("pfd_r", metrics.get("pfd_r"), 3),
        ("pfd_far_red", metrics.get("pfd_far_red"), 3),
        ("pfd_nir", metrics.get("pfd_nir"), 3),
        ("blue_red", ratio(metrics.get("pfd_b"), metrics.get("pfd_r")), 3),
        ("red_far_red", ratio(metrics.get("pfd_r"), metrics.get("pfd_far_red")), 3),
        ("blue_green", ratio(metrics.get("pfd_b"), metrics.get("pfd_g")), 3),
        ("blue_percent", ratio(metrics.get("pfd_b"), metrics.get("ppfd"), 100), 3),
        ("red_percent", ratio(metrics.get("pfd_r"), metrics.get("ppfd"), 100), 3),
        ("far_red_percent", ratio(metrics.get("pfd_far_red"), metrics.get("extended_ppfd"), 100), 3),
        ("cct", cct_value(metrics, parameters), 0),
        ("ra", parameters.get("ra"), 3),
        ("duv", parameters.get("duv"), 3),
        ("peak_wavelength_nm", metrics.get("peak_wavelength_nm"), 0),
        ("peak_value", metrics.get("peak_value"), 3),
        ("extended_peak_wavelength_nm", metrics.get("extended_peak_wavelength_nm"), 0),
        ("extended_peak_value", metrics.get("extended_peak_value"), 3),
        ("extended_par", scaled_par(metrics.get("extended_par")), 3),
        ("extended_ppfd", metrics.get("extended_ppfd"), 3),
        ("extended_pfd", metrics.get("extended_pfd"), 3),
        ("pfd_fr", metrics.get("pfd_fr"), 3),
        ("extended_pfd_fr", metrics.get("extended_pfd_fr"), 3),
    ):
        values[key] = format_metric(value, decimals)
    for key in (*(f"r{index}" for index in range(1, 16)), "X", "Y", "Z", *CHROMATICITY_KEYS):
        values[key] = format_metric(parameters.get(key), 4 if key in CHROMATICITY_KEYS else 3)
    return values


def iter_overview_kpi_texts(metrics: JsonObject, parameters: JsonObject) -> Iterator[tuple[str, str]]:
    """(card key, value + unit) for the six overview KPI cards, one at a time in OVERVIEW_KPI_SOURCES order.

    Lazy on purpose: V1.0.2 formatted and set each card in turn, so the caller must set a card before asking for
    the next one. A value that cannot be formatted (for example a string) then raises after the earlier cards
    already show their text, exactly as before. All fields are read on the first step, before any text is
    produced, so a JSON column that is not an object raises AttributeError before a single card changes.
    """
    sources = OVERVIEW_KPI_SOURCES.items()
    values = {key: metrics.get(field) for key, (source, field, _d, _u) in sources if source == "metrics"}
    values |= {key: parameters.get(field) for key, (source, field, _d, _u) in sources if source == "parameters"}
    for key, (_s, _f, decimals, unit) in sources:
        yield key, f"{format_metric(values[key], decimals)} {unit}"


def overview_core_metrics(metrics: JsonObject, parameters: JsonObject) -> list[tuple[str, str]]:
    """The four (label, text) rows of the core card drawn inside the overview spectrum."""
    return [
        ("照度（lx）", format_metric(parameters.get("lux"), 1)),
        ("350–1050 nm 总辐照度（W/m2）", format_metric(metrics.get("integrated_irradiance"))),
        ("PPFD（umol/m2/s）", format_metric(metrics.get("ppfd"))),
        ("McCree-YPFD（umol/m2/s）", format_metric(metrics.get("mccree_ypfd"))),
    ]


def overview_metric_entries(metrics: JsonObject, parameters: JsonObject) -> tuple[OverviewEntry, ...]:
    """The 24 overview table entries in order; values are raw numbers, None, or already formatted text."""
    ppfd = metrics.get("ppfd")
    return (
        ("照度（lx）", parameters.get("lux")),
        ("350–1050 nm 总辐照度（W/m²）", metrics.get("integrated_irradiance")),
        ("PAR 波段辐照度（W/m²）", scaled_par(metrics.get("par"))),
        ("PPFD（µmol·m⁻²·s⁻¹）", ppfd),
        ("PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd")),
        ("McCree-YPFD（µmol·m⁻²·s⁻¹）", metrics.get("mccree_ypfd")),
        ("紫外 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_uv")),
        ("蓝光 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_b")),
        ("绿光 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_g")),
        ("红光 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_r")),
        ("远红光 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_far_red")),
        ("近红外 PFD（µmol·m⁻²·s⁻¹）", metrics.get("pfd_nir")),
        ("蓝红光子比 B:R（无量纲）", ratio(metrics.get("pfd_b"), metrics.get("pfd_r"))),
        ("红远红光子比 R:FR（无量纲）", ratio(metrics.get("pfd_r"), metrics.get("pfd_far_red"))),
        ("蓝绿光子比 B:G（无量纲）", ratio(metrics.get("pfd_b"), metrics.get("pfd_g"))),
        ("蓝光占 PPFD 比例（%）", ratio(metrics.get("pfd_b"), ppfd, 100)),
        ("红光占 PPFD 比例（%）", ratio(metrics.get("pfd_r"), ppfd, 100)),
        ("远红光占扩展 PPFD 比例（%）", ratio(metrics.get("pfd_far_red"), metrics.get("extended_ppfd"), 100)),
        ("相关色温 CCT（K）", format_metric(cct_value(metrics, parameters), 0)),
        ("一般显色指数 Ra（无量纲）", parameters.get("ra")),
        ("色偏差 Duv（无量纲）", parameters.get("duv")),
        ("PAR 峰值波长（nm）", format_metric(metrics.get("peak_wavelength_nm"), 0)),
        ("PAR 峰值功率（mW·nm⁻¹）", metrics.get("peak_value")),
        ("全谱峰值波长（nm）", format_metric(metrics.get("extended_peak_wavelength_nm"), 0)),
    )


def format_entry_value(value: float | str | None) -> str:
    """Overview table / overlay text: preformatted text as is, None as "—", numbers with 3 decimals."""
    if isinstance(value, str):
        return value
    return EM_DASH if value is None else f"{float(value):.3f}"


def overview_secondary_metrics(entries: Iterable[OverviewEntry]) -> list[tuple[str, str]]:
    """Overlay rows: every entry except the core-card ones, with the "（无量纲）" suffix dropped."""
    return [
        (label.replace("（无量纲）", ""), format_entry_value(value))
        for label, value in entries
        if label not in OVERVIEW_FIXED_LABELS
    ]
