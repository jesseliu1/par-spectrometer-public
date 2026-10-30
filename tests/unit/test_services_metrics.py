"""par_app.services.metrics: display conversion moved out of par_app/ui.py MainWindow (R-8-1 stage one).

Expected values are written by hand from the rules (MATH-007, UI-014, UI-017, UI-033, UI-304), not produced by
the code under test. The Qt tests in tests/qt/configuration_steps keep covering the same logic through the
MainWindow wrappers; these tests pin the boundaries (None / NaN / inf / zero denominator / old records) directly.
"""

from __future__ import annotations

import json
import math

import pytest

from par_app.services import metrics as svc

pytestmark = pytest.mark.unit
NAN = float("nan")
INF = float("inf")


# ---------------------------------------- ratio (was MainWindow._ratio)


@pytest.mark.spec("UI-033")
@pytest.mark.parametrize(
    ("numerator", "denominator", "multiplier", "expected"),
    [
        (3, 4, 1.0, 0.75),
        (1.694, 5.28, 100, 1.694 / 5.28 * 100),
        (0, 2, 1.0, 0.0),  # zero numerator is a valid 0
        (-1, 4, 1.0, -0.25),
        (1, 0, 1.0, None),  # zero denominator: no invented value
        (1, 0.0, 100, None),
        (1, -0.0, 1.0, None),
        (None, 1, 1.0, None),
        (1, None, 1.0, None),
        (None, None, 1.0, None),
    ],
)
def test_ratio(numerator: float | None, denominator: float | None, multiplier: float, expected: float | None) -> None:
    result = svc.ratio(numerator, denominator, multiplier)
    if expected is None:
        assert result is None
    else:
        assert type(result) is float
        assert result == pytest.approx(expected, rel=1e-15)


def test_ratio_passes_non_finite_through_for_the_formatter() -> None:
    """NaN / inf inputs are not filtered here; format_metric turns the result into "—" (status quo)."""
    assert math.isnan(svc.ratio(NAN, 1) or 0.0)
    assert svc.ratio(1, INF) == 0.0
    assert svc.ratio(INF, 2) == INF
    assert math.isnan(svc.ratio(1, NAN) or 0.0)


# ---------------------------------------- cct_value (was MainWindow._cct_value)


@pytest.mark.spec("UI-304")
@pytest.mark.parametrize(
    ("metrics", "parameters", "expected"),
    [
        ({"cct_kelvin": 6800}, {"cct": 6991.5}, 6800),  # saved value wins
        ({"cct_kelvin": None}, {"cct": 6991.5}, None),  # saved null is not replaced by the hardware value
        ({}, {"cct": 6991.5}, 6992),  # old record: hardware CCT, half rounds up
        ({}, {"cct": 6991.49}, 6991),
        ({}, {"cct": 0}, 0),
        ({}, {"cct": 0.4}, 0),
        ({}, {"cct": -1}, None),
        ({}, {"cct": -0.4}, None),
        ({}, {"cct": NAN}, None),
        ({}, {"cct": INF}, None),
        ({}, {"cct": None}, None),
        ({}, {"cct": "6991"}, None),  # text is not a number here
        ({}, {}, None),
    ],
)
def test_cct_value(metrics: dict, parameters: dict, expected: int | None) -> None:
    result = svc.cct_value(metrics, parameters)
    assert result == expected
    if expected is not None:
        assert type(result) is int


# ---------------------------------------- format_metric (was MainWindow._format_metric)


@pytest.mark.spec("UI-033")
@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (None, 3, "—"),
        (NAN, 3, "—"),
        (INF, 0, "—"),
        (-INF, 1, "—"),
        (0, 3, "0.000"),
        (1.17949, 3, "1.179"),
        (931.54, 1, "931.5"),
        (479.0, 0, "479"),
        (900, 0, "900"),
        (0.19874, 4, "0.1987"),
        (-2.5, 0, "-2"),  # f-string rounding (half to even), unlike cct_value's +0.5
    ],
)
def test_format_metric(value: float | None, decimals: int, expected: str) -> None:
    assert svc.format_metric(value, decimals) == expected


def test_format_metric_defaults_to_three_decimals() -> None:
    assert svc.format_metric(5.28) == "5.280"


# ---------------------------------------- scaled_par (MATH-007)


@pytest.mark.spec("MATH-007")
def test_par_display_is_stored_value_times_ten() -> None:
    assert svc.PAR_DISPLAY_FACTOR == 10
    assert svc.scaled_par(0.1179) == pytest.approx(1.179)
    assert svc.scaled_par(0) == 0
    assert svc.scaled_par(None) is None
    assert math.isnan(svc.scaled_par(NAN) or 0.0)


# ---------------------------------------- record_metric_values (was MainWindow._record_metric_values)

DETAIL_KEYS = {
    "lux", "irradiance", "par", "ppfd", "pfd", "ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd",
    "pfd_uv", "pfd_b", "pfd_g", "pfd_r", "pfd_far_red", "pfd_nir",
    "blue_red", "red_far_red", "blue_green", "blue_percent", "red_percent", "far_red_percent",
    "cct", "ra", "duv", "peak_wavelength_nm", "peak_value", "extended_peak_wavelength_nm", "extended_peak_value",
    "extended_par", "extended_ppfd", "extended_pfd", "pfd_fr", "extended_pfd_fr",
    *(f"r{index}" for index in range(1, 16)), "X", "Y", "Z", "u", "v", "x", "y",
}  # fmt: skip


def _record(metrics: dict | None, parameters: dict | None) -> dict:
    return {
        "mcu_params_json": None if parameters is None else json.dumps(parameters),
        "software_metrics_json": None if metrics is None else json.dumps(metrics),
    }


@pytest.mark.spec("UI-018")
def test_record_metric_values_has_the_54_detail_keys() -> None:
    assert len(DETAIL_KEYS) == 54
    assert set(svc.record_metric_values(_record({}, {}))) == DETAIL_KEYS


@pytest.mark.spec("UI-033")
@pytest.mark.parametrize("columns", [(None, None), ({}, {}), ("", "")])
def test_empty_record_shows_dash_everywhere(columns: tuple) -> None:
    record = {"mcu_params_json": columns[1], "software_metrics_json": columns[0]}
    values = svc.record_metric_values(record)
    assert values == dict.fromkeys(DETAIL_KEYS, "—")


@pytest.mark.spec("MATH-007 UI-014 UI-017")
def test_record_metric_values_formats() -> None:
    metrics = {
        "integrated_irradiance": 1.5049,
        "par": 0.11789,
        "extended_par": 0.14012,
        "ppfd": 5.28,
        "pfd": 6.281,
        "mccree_ypfd": 4.262,
        "pfd_b": 1.694,
        "pfd_g": 2.022,
        "pfd_r": 1.552,
        "pfd_far_red": 0.575,
        "extended_ppfd": 5.855,
        "cct_kelvin": 6992,
        "peak_wavelength_nm": 479,
        "extended_peak_wavelength_nm": 731,
    }
    parameters = {"lux": 931.54, "cct": 6991.5, "ra": 93.8051, "u": 0.19874, "x": 0.33119, "X": 10.125, "r15": 83.75}
    values = svc.record_metric_values(_record(metrics, parameters))
    assert values["lux"] == "931.5"
    assert values["irradiance"] == "1.505"
    assert values["par"] == "1.179"  # stored 0.11789 ×10
    assert values["extended_par"] == "1.401"  # stored 0.14012 ×10
    assert values["ppfd"] == "5.280"
    assert values["blue_red"] == f"{1.694 / 1.552:.3f}"
    assert values["red_far_red"] == f"{1.552 / 0.575:.3f}"
    assert values["blue_green"] == f"{1.694 / 2.022:.3f}"
    assert values["blue_percent"] == f"{1.694 / 5.28 * 100:.3f}"
    assert values["red_percent"] == f"{1.552 / 5.28 * 100:.3f}"
    assert values["far_red_percent"] == f"{0.575 / 5.855 * 100:.3f}"
    assert values["cct"] == "6992"
    assert values["ra"] == "93.805"
    assert values["peak_wavelength_nm"] == "479"
    assert values["extended_peak_wavelength_nm"] == "731"
    assert values["u"] == "0.1987"
    assert values["x"] == "0.3312"
    assert values["X"] == "10.125"
    assert values["r15"] == "83.750"
    assert values["v"] == "—"


@pytest.mark.spec("UI-033")
def test_zero_denominators_and_non_finite_values_show_dash() -> None:
    metrics = {"pfd_b": 1, "pfd_r": 0, "pfd_g": 0, "pfd_far_red": 0, "ppfd": 0, "extended_ppfd": 0, "par": NAN}
    values = svc.record_metric_values(_record(metrics, {"lux": INF}))
    for key in ("blue_red", "red_far_red", "blue_green", "blue_percent", "red_percent", "far_red_percent"):
        assert values[key] == "—", key
    assert values["red_far_red"] == "—"
    assert values["par"] == "—"
    assert values["lux"] == "—"
    assert values["pfd_r"] == "0.000"


@pytest.mark.spec("UI-304")
def test_old_record_without_cct_kelvin_and_float_peaks() -> None:
    record = _record({"peak_wavelength_nm": 479.0, "extended_peak_wavelength_nm": 900.0}, {"cct": 6991.5})
    values = svc.record_metric_values(record)
    assert (values["cct"], values["peak_wavelength_nm"], values["extended_peak_wavelength_nm"]) == (
        "6992",
        "479",
        "900",
    )


def test_record_metric_values_does_not_modify_the_record() -> None:
    record = _record({"par": 0.1}, {"cct": 6991.5})
    original = dict(record)
    svc.record_metric_values(record)
    assert record == original


def test_decode_record_metrics_order_and_defaults() -> None:
    assert svc.decode_record_metrics({}) == ({}, {})
    assert svc.decode_record_metrics(_record({"ppfd": 1}, {"lux": 2})) == ({"lux": 2}, {"ppfd": 1})


# ---------------------------------------- overview (was inline in MainWindow.refresh_overview)

OVERVIEW_LABELS = (
    "照度（lx）", "350–1050 nm 总辐照度（W/m²）", "PAR 波段辐照度（W/m²）", "PPFD（µmol·m⁻²·s⁻¹）",
    "PFD（µmol·m⁻²·s⁻¹）", "McCree-YPFD（µmol·m⁻²·s⁻¹）", "紫外 PFD（µmol·m⁻²·s⁻¹）", "蓝光 PFD（µmol·m⁻²·s⁻¹）",
    "绿光 PFD（µmol·m⁻²·s⁻¹）", "红光 PFD（µmol·m⁻²·s⁻¹）", "远红光 PFD（µmol·m⁻²·s⁻¹）", "近红外 PFD（µmol·m⁻²·s⁻¹）",
    "蓝红光子比 B:R（无量纲）", "红远红光子比 R:FR（无量纲）", "蓝绿光子比 B:G（无量纲）", "蓝光占 PPFD 比例（%）",
    "红光占 PPFD 比例（%）", "远红光占扩展 PPFD 比例（%）", "相关色温 CCT（K）", "一般显色指数 Ra（无量纲）",
    "色偏差 Duv（无量纲）", "PAR 峰值波长（nm）", "PAR 峰值功率（mW·nm⁻¹）", "全谱峰值波长（nm）",
)  # fmt: skip


def test_iter_overview_kpi_texts() -> None:
    metrics = {"integrated_irradiance": 1.5049, "ppfd": 5.28, "mccree_ypfd": NAN, "chlorophyll_a_ypfd": 2.1234}
    texts = dict(svc.iter_overview_kpi_texts(metrics, {"lux": 931.54}))
    assert texts == {
        "lux": "931.5 lx",
        "irradiance": "1.505 W/m²",
        "ppfd": "5.280 µmol·m⁻²·s⁻¹",
        "ypfd": "— µmol·m⁻²·s⁻¹",
        "chlorophyll_a_ypfd": "2.123 µmol·m⁻²·s⁻¹",
        "chlorophyll_b_ypfd": "— µmol·m⁻²·s⁻¹",
    }
    assert list(texts) == ["lux", "irradiance", "ppfd", "ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd"]


@pytest.mark.parametrize(
    ("metrics_column", "parameters_column"),
    [
        ("null", '{"lux": 931.54}'),  # metrics broken, lux fine: V1.0.2 raised before setting any card
        ("[]", '{"lux": "931.54"}'),  # metrics broken, lux not a number: still AttributeError, not TypeError
        ("{}", "null"),
        ('"text"', "[]"),
    ],
)
def test_iter_overview_kpi_texts_non_object_column_raises_before_any_text(
    metrics_column: str, parameters_column: str
) -> None:
    """A JSON column that is not an object fails as in V1.0.2 (AttributeError on .get) on the very first step, so
    refresh_overview leaves every KPI card at its reset "—"."""
    parameters, metrics = svc.decode_record_metrics(
        {"mcu_params_json": parameters_column, "software_metrics_json": metrics_column}
    )
    with pytest.raises(AttributeError):
        next(svc.iter_overview_kpi_texts(metrics, parameters))


def test_iter_overview_kpi_texts_yields_earlier_cards_before_a_bad_value() -> None:
    """V1.0.2 set each card before formatting the next: a value that cannot be formatted raises only when its own
    card is reached, after the earlier texts were produced (the refresh_overview side is in tests/qt)."""
    texts = svc.iter_overview_kpi_texts({"integrated_irradiance": 1.5, "ppfd": "broken"}, {"lux": 931.54})
    assert next(texts) == ("lux", "931.5 lx")
    assert next(texts) == ("irradiance", "1.500 W/m²")
    with pytest.raises(TypeError):
        next(texts)


# One record with every displayed field set to a different value, so that a label reading the wrong field, a swapped
# ratio or a lost scaling changes the text. Ratio inputs are chosen so every expected value is exact in binary.
FULL_METRICS = {
    "integrated_irradiance": 11.111,
    "par": 0.375,
    "ppfd": 40.0,
    "pfd": 62.5,
    "mccree_ypfd": 55.55,
    "chlorophyll_a_ypfd": 66.66,
    "chlorophyll_b_ypfd": 77.77,
    "pfd_uv": 1.25,
    "pfd_b": 2.5,
    "pfd_g": 10.0,
    "pfd_r": 5.0,
    "pfd_far_red": 8.0,
    "pfd_nir": 3.5,
    "cct_kelvin": 5600,
    "peak_wavelength_nm": 451,
    "peak_value": 0.875,
    "extended_peak_wavelength_nm": 732,
    "extended_peak_value": 0.725,
    "extended_par": 0.3125,
    "extended_ppfd": 32.0,
    "extended_pfd": 48.5,
    "pfd_fr": 6.5,
    "extended_pfd_fr": 7.25,
}
FULL_PARAMETERS = {
    "lux": 1234.56,
    "cct": 6000.0,  # differs from cct_kelvin: the saved software CCT must win
    "ra": 91.5,
    "duv": 0.0042,
    **{f"r{index}": 70 + index + 0.25 for index in range(1, 16)},
    "X": 10.5,
    "Y": 11.5,
    "Z": 12.5,
    "u": 0.2101,
    "v": 0.3102,
    "x": 0.3303,
    "y": 0.3404,
}


@pytest.mark.spec("MATH-007 UI-014 UI-017 UI-018 UI-304")
def test_record_metric_values_all_54_texts() -> None:
    values = svc.record_metric_values(_record(FULL_METRICS, FULL_PARAMETERS))
    assert values == {
        "lux": "1234.6",
        "irradiance": "11.111",
        "par": "3.750",  # 0.375 ×10
        "ppfd": "40.000",
        "pfd": "62.500",
        "ypfd": "55.550",
        "chlorophyll_a_ypfd": "66.660",
        "chlorophyll_b_ypfd": "77.770",
        "pfd_uv": "1.250",
        "pfd_b": "2.500",
        "pfd_g": "10.000",
        "pfd_r": "5.000",
        "pfd_far_red": "8.000",
        "pfd_nir": "3.500",
        "blue_red": "0.500",  # 2.5 / 5
        "red_far_red": "0.625",  # 5 / 8
        "blue_green": "0.250",  # 2.5 / 10
        "blue_percent": "6.250",  # 2.5 / 40 ×100
        "red_percent": "12.500",  # 5 / 40 ×100
        "far_red_percent": "25.000",  # 8 / 32 (extended PPFD) ×100
        "cct": "5600",
        "ra": "91.500",
        "duv": "0.004",
        "peak_wavelength_nm": "451",
        "peak_value": "0.875",
        "extended_peak_wavelength_nm": "732",
        "extended_peak_value": "0.725",
        "extended_par": "3.125",  # 0.3125 ×10
        "extended_ppfd": "32.000",
        "extended_pfd": "48.500",
        "pfd_fr": "6.500",
        "extended_pfd_fr": "7.250",
        "r1": "71.250", "r2": "72.250", "r3": "73.250", "r4": "74.250", "r5": "75.250",
        "r6": "76.250", "r7": "77.250", "r8": "78.250", "r9": "79.250", "r10": "80.250",
        "r11": "81.250", "r12": "82.250", "r13": "83.250", "r14": "84.250", "r15": "85.250",
        "X": "10.500",
        "Y": "11.500",
        "Z": "12.500",
        "u": "0.2101",
        "v": "0.3102",
        "x": "0.3303",
        "y": "0.3404",
    }  # fmt: skip


@pytest.mark.spec("MATH-007 UI-014 UI-304")
def test_overview_full_record_kpi_and_core_card() -> None:
    assert dict(svc.iter_overview_kpi_texts(FULL_METRICS, FULL_PARAMETERS)) == {
        "lux": "1234.6 lx",
        "irradiance": "11.111 W/m²",
        "ppfd": "40.000 µmol·m⁻²·s⁻¹",
        "ypfd": "55.550 µmol·m⁻²·s⁻¹",
        "chlorophyll_a_ypfd": "66.660 µmol·m⁻²·s⁻¹",
        "chlorophyll_b_ypfd": "77.770 µmol·m⁻²·s⁻¹",
    }
    assert svc.overview_core_metrics(FULL_METRICS, FULL_PARAMETERS) == [
        ("照度（lx）", "1234.6"),
        ("350–1050 nm 总辐照度（W/m2）", "11.111"),
        ("PPFD（umol/m2/s）", "40.000"),
        ("McCree-YPFD（umol/m2/s）", "55.550"),
    ]


@pytest.mark.spec("MATH-007 UI-014 UI-033 UI-304")
def test_overview_entries_all_24_values() -> None:
    assert svc.overview_metric_entries(FULL_METRICS, FULL_PARAMETERS) == (
        ("照度（lx）", 1234.56),
        ("350–1050 nm 总辐照度（W/m²）", 11.111),
        ("PAR 波段辐照度（W/m²）", 3.75),
        ("PPFD（µmol·m⁻²·s⁻¹）", 40.0),
        ("PFD（µmol·m⁻²·s⁻¹）", 62.5),
        ("McCree-YPFD（µmol·m⁻²·s⁻¹）", 55.55),
        ("紫外 PFD（µmol·m⁻²·s⁻¹）", 1.25),
        ("蓝光 PFD（µmol·m⁻²·s⁻¹）", 2.5),
        ("绿光 PFD（µmol·m⁻²·s⁻¹）", 10.0),
        ("红光 PFD（µmol·m⁻²·s⁻¹）", 5.0),
        ("远红光 PFD（µmol·m⁻²·s⁻¹）", 8.0),
        ("近红外 PFD（µmol·m⁻²·s⁻¹）", 3.5),
        ("蓝红光子比 B:R（无量纲）", 0.5),
        ("红远红光子比 R:FR（无量纲）", 0.625),
        ("蓝绿光子比 B:G（无量纲）", 0.25),
        ("蓝光占 PPFD 比例（%）", 6.25),
        ("红光占 PPFD 比例（%）", 12.5),
        ("远红光占扩展 PPFD 比例（%）", 25.0),
        ("相关色温 CCT（K）", "5600"),
        ("一般显色指数 Ra（无量纲）", 91.5),
        ("色偏差 Duv（无量纲）", 0.0042),
        ("PAR 峰值波长（nm）", "451"),
        ("PAR 峰值功率（mW·nm⁻¹）", 0.875),
        ("全谱峰值波长（nm）", "732"),
    )


@pytest.mark.spec("UI-059 UI-060")
def test_overview_secondary_metrics_all_20_texts() -> None:
    entries = svc.overview_metric_entries(FULL_METRICS, FULL_PARAMETERS)
    assert svc.overview_secondary_metrics(entries) == [
        ("PAR 波段辐照度（W/m²）", "3.750"),
        ("PFD（µmol·m⁻²·s⁻¹）", "62.500"),
        ("紫外 PFD（µmol·m⁻²·s⁻¹）", "1.250"),
        ("蓝光 PFD（µmol·m⁻²·s⁻¹）", "2.500"),
        ("绿光 PFD（µmol·m⁻²·s⁻¹）", "10.000"),
        ("红光 PFD（µmol·m⁻²·s⁻¹）", "5.000"),
        ("远红光 PFD（µmol·m⁻²·s⁻¹）", "8.000"),
        ("近红外 PFD（µmol·m⁻²·s⁻¹）", "3.500"),
        ("蓝红光子比 B:R", "0.500"),
        ("红远红光子比 R:FR", "0.625"),
        ("蓝绿光子比 B:G", "0.250"),
        ("蓝光占 PPFD 比例（%）", "6.250"),
        ("红光占 PPFD 比例（%）", "12.500"),
        ("远红光占扩展 PPFD 比例（%）", "25.000"),
        ("相关色温 CCT（K）", "5600"),
        ("一般显色指数 Ra", "91.500"),
        ("色偏差 Duv", "0.004"),
        ("PAR 峰值波长（nm）", "451"),
        ("PAR 峰值功率（mW·nm⁻¹）", "0.875"),
        ("全谱峰值波长（nm）", "732"),
    ]


def test_overview_core_metrics() -> None:
    rows = svc.overview_core_metrics({"integrated_irradiance": 1.5049, "ppfd": 5.28}, {"lux": 931.54})
    assert rows == [
        ("照度（lx）", "931.5"),
        ("350–1050 nm 总辐照度（W/m2）", "1.505"),
        ("PPFD（umol/m2/s）", "5.280"),
        ("McCree-YPFD（umol/m2/s）", "—"),
    ]


@pytest.mark.spec("MATH-007 UI-014 UI-033")
def test_overview_entries_values() -> None:
    metrics = {
        "par": 0.11789,
        "ppfd": 5.28,
        "pfd_b": 1.694,
        "pfd_r": 0,
        "cct_kelvin": 6992,
        "peak_wavelength_nm": 479.4,
    }
    entries = svc.overview_metric_entries(metrics, {"lux": 931.54, "ra": 93.8})
    assert tuple(label for label, _value in entries) == OVERVIEW_LABELS
    values = dict(entries)
    assert values["照度（lx）"] == 931.54  # raw; the table formats it
    assert values["PAR 波段辐照度（W/m²）"] == pytest.approx(1.1789)
    assert values["蓝红光子比 B:R（无量纲）"] is None  # zero denominator
    assert values["蓝光占 PPFD 比例（%）"] == pytest.approx(1.694 / 5.28 * 100)
    assert values["相关色温 CCT（K）"] == "6992"
    assert values["PAR 峰值波长（nm）"] == "479"
    assert values["全谱峰值波长（nm）"] == "—"
    assert values["一般显色指数 Ra（无量纲）"] == 93.8


def test_overview_secondary_metrics_drop_core_rows_and_suffix() -> None:
    entries = svc.overview_metric_entries({"par": 0.1}, {"lux": 1})
    secondary = svc.overview_secondary_metrics(entries)
    assert len(secondary) == 20
    assert all(label not in svc.OVERVIEW_FIXED_LABELS for label, _text in secondary)
    assert all("（无量纲）" not in label for label, _text in secondary)
    assert secondary[0] == ("PAR 波段辐照度（W/m²）", "1.000")
    assert ("一般显色指数 Ra", "—") in secondary


@pytest.mark.known_defect("D-179: overview table and overlay show nan/inf (audit robustness-ui.md Bug 6)")
def test_known_defect_overview_entry_shows_nan_and_inf() -> None:
    """Status quo, not a correctness claim: raw non-finite numbers render as "nan"/"inf" in the overview table and
    overlay (format_entry_value does not route through format_metric). Kept unchanged by the extraction."""
    assert svc.format_entry_value(NAN) == "nan"
    assert svc.format_entry_value(INF) == "inf"


def test_format_entry_value() -> None:
    assert svc.format_entry_value("6992") == "6992"
    assert svc.format_entry_value(None) == "—"
    assert svc.format_entry_value(0) == "0.000"
    assert svc.format_entry_value(1.17949) == "1.179"
