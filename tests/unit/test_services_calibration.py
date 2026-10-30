"""par_app.services.calibration: calibration logic moved out of par_app/ui.py (R-8-1 stage one, behaviour-preserving).

Expected values are written by hand from docs/spec/maint.md and docs/spec/ui.md (MAINT-034/038/041/042/101/134/
141/142/143, UI-127/129) and from the PCHIP formulas worked out on paper (node slopes, weighted harmonic mean
for inner nodes, three-point end formula, cubic Hermite basis). None is produced by the code under test. The Qt
tests (tests/qt/test_maintenance*.py, tests/qt/multidevice) keep covering the same logic through MainWindow and
CalibrationCanvas; these tests pin the boundaries directly: missing / non-numeric / NaN / inf / overflowing / out of
range readbacks, equal wavelengths, equal limits, pick-radius and drag edges, timestamp range edges, version_nodes
range edges and non-dict statuses. No Qt, no device, no clock: the time zone is passed in.

Status-quo quirks found while extracting are not expected values: each is a separate test_known_defect_* case marked
known_defect with its pending decision (D-172..D-176 in docs/spec/pending-decisions.md, R-3-2/R-4-3). They assert
what V1.0.2 does today, not what is correct; a fix PR rewrites them once owner decides.
"""

from __future__ import annotations

from datetime import UTC, timedelta, timezone

import numpy as np
import pytest

from par_app.services import calibration as svc

pytestmark = pytest.mark.unit
NAN = float("nan")
INF = float("inf")
BEIJING = timezone(timedelta(hours=8))
X = (350.0, 500.0, 650.0, 800.0, 1050.0)


def _valid(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "x_min": 350.0, "x_max": 1050.0, "x1": 500.0, "x2": 650.0, "x3": 800.0,
        "y0": 0.01, "y1": -0.02, "y2": 0.0, "y3": 0.03, "y4": -0.04,
        "k_global": 0.87, "limit_min": -0.2, "limit_max": 0.2,
    }  # fmt: skip
    payload.update(changes)
    return payload


def _nodes(*ys: float) -> np.ndarray:
    return np.column_stack((np.array(X), np.array(ys, dtype=float)))


# --- field table (UI-127, MAINT-040) ---------------------------------------------------------------------------


def test_field_order_is_the_editor_order_and_the_write_order() -> None:
    assert svc.CALIBRATION_FIELDS == (
        "x_min", "x_max", "x1", "x2", "x3", "y0", "y1", "y2", "y3", "y4", "k_global", "limit_min", "limit_max",
    )  # fmt: skip
    assert svc.NODE_FIELDS == (("x_min", "y0"), ("x1", "y1"), ("x2", "y2"), ("x3", "y3"), ("x_max", "y4"))


@pytest.mark.spec("UI-127 MAINT-040")
def test_only_node_corrections_and_limits_are_shown_as_percent() -> None:
    scales = {name: svc.field_scale(name) for name in svc.CALIBRATION_FIELDS}
    assert scales == {
        "x_min": 1, "x_max": 1, "x1": 1, "x2": 1, "x3": 1, "y0": 100, "y1": 100, "y2": 100, "y3": 100, "y4": 100,
        "k_global": 1, "limit_min": 100, "limit_max": 100,
    }  # fmt: skip
    assert svc.FIELD_LIMIT == 1_000_000


# --- availability (MAINT-108/133/134) --------------------------------------------------------------------------

READY = {"device_enabled": True, "configured": True, "online": True, "faulty": False, "maintenance": False,
         "halted": False}  # fmt: skip


@pytest.mark.spec("MAINT-134")
def test_available_only_when_every_precondition_holds() -> None:
    assert svc.calibration_available(**READY) is True  # type: ignore[arg-type]


@pytest.mark.spec("MAINT-108 MAINT-133 MAINT-134")
@pytest.mark.parametrize(
    "change",
    [{"device_enabled": False}, {"configured": False}, {"online": False}, {"online": None}, {"online": 0},
     {"faulty": True}, {"maintenance": True}, {"halted": True}],
)  # fmt: skip
def test_any_failed_precondition_makes_calibration_unavailable(change: dict[str, object]) -> None:
    assert svc.calibration_available(**{**READY, **change}) is False  # type: ignore[arg-type]


@pytest.mark.known_defect("D-174 pending: the online flag is read as a truth value, any non-empty text counts")
def test_known_defect_online_accepts_any_truthy_value() -> None:
    assert svc.calibration_available(**{**READY, "online": "yes"}) is True  # type: ignore[arg-type]


# --- readback validation (MAINT-101) ---------------------------------------------------------------------------


@pytest.mark.spec("MAINT-101")
def test_valid_readback_is_returned_as_floats_in_field_order() -> None:
    payload = _valid(x_min=350, _mcu_status={"status": 1})
    assert list(payload)[0] == "x_min"
    result = svc.parse_readback(payload)
    assert result is not None
    assert list(result) == list(svc.CALIBRATION_FIELDS)
    assert result["x_min"] == 350.0 and isinstance(result["x_min"], float)
    assert result["k_global"] == 0.87
    assert "_mcu_status" not in result


@pytest.mark.spec("MAINT-101")
@pytest.mark.parametrize(
    "change",
    [
        {"y2": None}, {"y2": "abc"}, {"y2": [1]}, {"y2": NAN}, {"y2": INF}, {"y2": -INF}, {"y2": "1e400"},
        {"y2": 10**400}, {"k_global": 1_000_000.0001}, {"k_global": -1_000_000.0001},
    ],
)  # fmt: skip
def test_one_bad_field_rejects_the_whole_readback(change: dict[str, object]) -> None:
    assert svc.parse_readback(_valid(**change)) is None


@pytest.mark.spec("MAINT-101")
def test_missing_field_rejects_the_whole_readback() -> None:
    payload = _valid()
    del payload["limit_max"]
    assert svc.parse_readback(payload) is None


@pytest.mark.spec("MAINT-101")
def test_field_range_edges_are_inclusive() -> None:
    result = svc.parse_readback(_valid(k_global=1_000_000, x_min=-1_000_000.0))
    assert result is not None
    assert result["k_global"] == 1_000_000.0 and result["x_min"] == -1_000_000.0


@pytest.mark.known_defect("D-174 pending: readback fields accept bool and numeric text through float()")
def test_known_defect_readback_accepts_bool_and_numeric_text() -> None:
    result = svc.parse_readback(_valid(k_global="0.87", limit_max=True))
    assert result is not None
    assert result["k_global"] == 0.87 and result["limit_max"] == 1.0


@pytest.mark.known_defect("D-175 pending: ±1e6 is a protocol range, ±1e8 % on the percent fields")
def test_known_defect_percent_fields_accept_a_million_ratio() -> None:
    result = svc.parse_readback(_valid(y0=-1_000_000.0, y4=1_000_000))
    assert result is not None
    assert result["y0"] * svc.field_scale("y0") == -100_000_000.0


@pytest.mark.spec("MAINT-101")
@pytest.mark.parametrize(
    "change",
    [{"x1": 350.0}, {"x2": 500.0}, {"x3": 650.0}, {"x_max": 800.0}, {"x1": 700.0}, {"x_min": 1100.0}],
)
def test_node_wavelengths_must_strictly_increase(change: dict[str, object]) -> None:
    assert svc.parse_readback(_valid(**change)) is None


@pytest.mark.spec("MAINT-101")
def test_limits_may_be_equal_but_not_crossed() -> None:
    assert svc.parse_readback(_valid(limit_min=0.1, limit_max=0.1)) is not None
    assert svc.parse_readback(_valid(limit_min=0.1000001, limit_max=0.1)) is None


# --- write checks and confirmation text (MAINT-034) -----------------------------------------------------------


@pytest.mark.spec("MAINT-034")
def test_writable_needs_increasing_wavelengths_and_ordered_limits() -> None:
    values = {k: float(v) for k, v in _valid().items()}  # type: ignore[arg-type]
    assert svc.is_writable(values)
    assert svc.is_writable({**values, "limit_min": 0.2})
    assert not svc.is_writable({**values, "limit_min": 0.21})
    assert not svc.is_writable({**values, "x3": 1050.0})
    assert not svc.is_writable({**values, "x1": 349.9})


def test_preview_order_check_matches_the_write_check_for_finite_wavelengths() -> None:
    values = {k: float(v) for k, v in _valid().items()}  # type: ignore[arg-type]
    assert not svc.wavelengths_out_of_order(values) and svc.wavelengths_increasing(values)
    for name, value in (("x1", 350.0), ("x2", 500.0), ("x3", 650.0), ("x_max", 800.0), ("x_min", 501.0)):
        assert svc.wavelengths_out_of_order({**values, name: value}), name
        assert not svc.wavelengths_increasing({**values, name: value}), name


@pytest.mark.known_defect("D-176 pending: the preview and write order checks disagree on a NaN wavelength")
def test_known_defect_nan_wavelength_passes_the_preview_check_but_not_the_write_check() -> None:
    values = {k: float(v) for k, v in _valid().items()}  # type: ignore[arg-type]
    assert not svc.wavelengths_out_of_order({**values, "x2": NAN})
    assert not svc.wavelengths_increasing({**values, "x2": NAN})


def test_dirty_only_against_a_held_readback() -> None:
    values = {"x_min": 350.0, "y0": 0.01}
    assert svc.is_dirty(None, values) is False
    assert svc.is_dirty(dict(values), values) is False
    assert svc.is_dirty({"x_min": 350.0, "y0": 0.02}, values) is True
    assert svc.is_dirty({}, values) is True


@pytest.mark.spec("MAINT-034")
def test_change_lines_list_old_and_new_values_in_dict_order() -> None:
    values = {"x_min": 351.0, "x1": 500.0, "k_global": 1.0}
    assert (
        svc.change_lines({"x_min": 350.0, "x1": 500.0}, values)
        == "x_min: 350.0 → 351.0\nx1: 500.0 → 500.0\nk_global: — → 1.0"
    )
    assert svc.change_lines(None, values) == "x_min: — → 351.0\nx1: — → 500.0\nk_global: — → 1.0"
    assert svc.change_lines({}, {"x1": 2.5}) == "x1: — → 2.5"


@pytest.mark.known_defect("D-175 pending: the confirmation lists protocol ratios while the editor shows percent")
def test_known_defect_confirmation_lists_ratios_not_percent() -> None:
    assert svc.field_scale("y0") == 100  # the editor shows y0 = 0.02 as 2.00
    assert svc.change_lines({"y0": 0.01, "limit_max": 0.2}, {"y0": 0.02, "limit_max": 0.3}) == (
        "y0: 0.01 → 0.02\nlimit_max: 0.2 → 0.3"
    )


# --- PCHIP preview --------------------------------------------------------------------------------------------


def _pchip(xs: tuple[float, ...], ys: tuple[float, ...], at: list[float]) -> np.ndarray:
    return svc.pchip(np.array(xs, dtype=float), np.array(ys, dtype=float), np.array(at, dtype=float))


def test_pchip_reproduces_lines_and_constants() -> None:
    at = [350.0, 420.0, 500.0, 777.7, 1049.0, 1050.0]
    assert _pchip(X, tuple(2 * x - 5 for x in X), at) == pytest.approx([2 * x - 5 for x in at])
    assert _pchip(X, (3.0,) * 5, at) == pytest.approx([3.0] * len(at))


def test_pchip_passes_through_every_node() -> None:
    ys = (0.0, 10.0, -4.0, 2.5, 7.0)
    assert _pchip(X, ys, list(X)) == pytest.approx(list(ys))


def test_pchip_flattens_at_local_extrema() -> None:
    # Inner slopes change sign at every node, so every inner derivative is 0; midpoint of a Hermite segment with
    # zero end derivatives is the mean of its ends.
    xs = (0.0, 1.0, 2.0, 3.0, 4.0)
    assert _pchip(xs, (0.0, 10.0, 0.0, 10.0, 0.0), [1.5, 2.5]) == pytest.approx([5.0, 5.0])
    # A zero slope on either side also gives a zero derivative.
    assert _pchip(xs, (0.0, 10.0, 10.0, 10.0, 10.0), [1.5, 2.5, 3.5]) == pytest.approx([10.0, 10.0, 10.0])


def test_pchip_end_derivatives_use_the_three_point_formula() -> None:
    # Slopes 10, 0: d0 = ((2·1 + 1)·10 − 1·0) / 2 = 15, d1 = 0 → p(0.5) = 0.125·15 + 0.5·10 = 6.875.
    xs = (0.0, 1.0, 2.0, 3.0, 4.0)
    assert _pchip(xs, (0.0, 10.0, 10.0, 10.0, 10.0), [0.5]) == pytest.approx([6.875])
    assert _pchip(xs, (10.0, 10.0, 10.0, 10.0, 0.0), [3.5]) == pytest.approx([6.875])


@pytest.mark.known_defect("D-172 pending (L3): end derivatives are not limited, the end segment overshoots")
def test_known_defect_pchip_end_segment_overshoots_the_nodes() -> None:
    # Slopes 1, −10: d0 = ((2 + 1)·1 − 1·(−10)) / 2 = 6.5, d1 = 0 (sign change). p(t) on [0, 1] = 3t² − 2t³ +
    # 6.5(t³ − 2t² + t) peaks at ≈ 1.3137 > max(y0, y1) = 1, although the docstring says "monotone".
    xs = (0.0, 1.0, 2.0, 3.0, 4.0)
    at = [i / 1000 for i in range(1001)]
    first = _pchip(xs, (0.0, 1.0, -9.0, -9.0, -9.0), at)
    assert first.max() == pytest.approx(1.3136708845, abs=1e-9)
    assert first.max() > 1.0
    on_x = _pchip(X, (0.0, 1.0, -9.0, -9.0, -9.0), list(np.linspace(350.0, 500.0, 1001)))
    assert on_x.max() == pytest.approx(1.3136708845, abs=1e-9)


def test_pchip_inner_derivatives_are_weighted_harmonic_means_on_uneven_spacing() -> None:
    # h = 1, 2, 1, 2; slopes 1, 2, 1, 2 → d1 = d2 = d3 = 9/7 (weights 5 and 4), d0 = 2/3, d4 = 8/3.
    xs, ys = (0.0, 1.0, 3.0, 4.0, 6.0), (0.0, 1.0, 5.0, 6.0, 10.0)
    # x = 1.5: t = 0.25, span 2: 0.84375·1 + 0.15625·5 + (0.140625 − 0.046875)·2·9/7
    # x = 0.5: t = 0.5, span 1: 0.125·2/3 + 0.5·1 − 0.125·9/7
    expected = [1.625 + 0.09375 * 18 / 7, 0.125 * 2 / 3 + 0.5 - 0.125 * 9 / 7]
    assert _pchip(xs, ys, [1.5, 0.5]) == pytest.approx(expected, abs=1e-12)


# --- correction curve (combined correction, clipped) ----------------------------------------------------------


def _calibration(ys: tuple[float, ...], k_global: float, limit_min: float, limit_max: float) -> dict[str, float]:
    values = dict(zip(("x_min", "x1", "x2", "x3", "x_max"), X, strict=True))
    values.update(zip(("y0", "y1", "y2", "y3", "y4"), ys, strict=True))
    values.update(k_global=k_global, limit_min=limit_min, limit_max=limit_max)
    return values


def test_global_factor_alone_shifts_the_whole_curve() -> None:
    # k_global = 0.87 with every y = 0 is −13 % everywhere (comment kept from V1.0.2).
    curve = svc.correction_curve(_calibration((0.0,) * 5, 0.87, -0.2, 0.2))
    assert curve.global_percent == pytest.approx(-13.0)
    assert (curve.limit_min_percent, curve.limit_max_percent) == pytest.approx((-20.0, 20.0))
    assert curve.nodes[:, 1] == pytest.approx([-13.0] * 5)
    assert curve.curve_y == pytest.approx([-13.0] * 701)


def test_curve_spans_the_nodes_with_701_points_and_is_clipped_to_the_limits() -> None:
    curve = svc.correction_curve(_calibration((0.5, 0.0, 0.0, 0.0, -0.5), 1.0, -0.3, 0.3))
    assert list(curve.node_x) == list(X)
    assert curve.nodes.tolist() == [[350.0, 30.0], [500.0, 0.0], [650.0, 0.0], [800.0, 0.0], [1050.0, -30.0]]
    assert len(curve.curve_x) == 701 and curve.curve_x[0] == 350.0 and curve.curve_x[-1] == 1050.0
    assert curve.curve_x[1] == pytest.approx(351.0)
    assert curve.curve_y[0] == 30.0 and curve.curve_y[-1] == -30.0
    assert curve.curve_y.max() == 30.0 and curve.curve_y.min() == -30.0
    assert curve.curve_y[300] == pytest.approx(0.0)  # 650 nm


def test_curve_x_follows_the_nodes_not_the_axis() -> None:
    values = _calibration((0.0,) * 5, 1.0, -0.1, 0.1)
    values.update(x_min=400.0, x_max=1000.0)
    curve = svc.correction_curve(values)
    assert curve.curve_x[0] == 400.0 and curve.curve_x[-1] == 1000.0 and len(curve.curve_x) == 701


# --- node dragging (MAINT-038; drag limits not in the spec, D-177) --------------------------------------------


@pytest.mark.spec("MAINT-038")
def test_untouched_nodes_keep_their_raw_values_even_outside_the_limits() -> None:
    values = _calibration((0.5, 0.0, 0.0, 0.0, -0.5), 1.0, -0.3, 0.3)
    drawn = svc.correction_curve(values).nodes
    updated = svc.node_values(values, drawn, 0.0, -30.0, 30.0)
    assert updated == {"x_min": 350.0, "y0": 0.5, "x1": 500.0, "y1": 0.0, "x2": 650.0, "y2": 0.0,
                       "x3": 800.0, "y3": 0.0, "x_max": 1050.0, "y4": -0.5}  # fmt: skip


@pytest.mark.spec("MAINT-038 MAINT-040")
def test_moved_node_converts_its_combined_percent_back_to_a_ratio() -> None:
    values = _calibration((0.5, 0.0, 0.0, 0.0, -0.5), 1.5, -1.0, 1.0)  # global +50 %
    nodes = svc.correction_curve(values).nodes.copy()
    nodes[1] = (510.0, 60.0)  # y1 moved: 60 % combined − 50 % global = 10 % → 0.1
    nodes[3, 0] = 790.0  # x3 moved only
    updated = svc.node_values(values, nodes, 50.0, -100.0, 100.0)
    assert updated["x1"] == 510.0 and updated["y1"] == pytest.approx(0.1)
    assert updated["x3"] == 790.0 and updated["y3"] == 0.0
    assert updated["y0"] == 0.5 and updated["y4"] == -0.5


def test_press_picks_the_nearest_node_inside_the_radius() -> None:
    nodes = _nodes(0.0, 0.0, 0.0, 0.0, 0.0)
    assert svc.nearest_node(nodes, 527.0, 0.0, (-10.0, 10.0)) == 1  # 27/700 < 0.04
    assert svc.nearest_node(nodes, 528.0, 0.0, (-10.0, 10.0)) is None  # 28/700 == 0.04 is outside
    assert svc.nearest_node(nodes, 650.0, 0.79, (-10.0, 10.0)) == 2  # 0.79/20 < 0.04
    assert svc.nearest_node(nodes, 650.0, 0.8, (-10.0, 10.0)) is None
    # A y span below 1 counts as 1.
    assert svc.nearest_node(nodes, 800.0, 0.039, (0.0, 0.5)) == 3
    assert svc.nearest_node(nodes, 800.0, 0.041, (0.0, 0.5)) is None


def test_drag_stays_between_neighbours_and_inside_the_axis_and_limits() -> None:
    nodes = _nodes(0.0, 0.0, 0.0, 0.0, 0.0)
    assert svc.dragged_node(nodes, 0, 300.0, 0.0, -20.0, 20.0) == (350.0, 0.0)
    assert svc.dragged_node(nodes, 0, 600.0, 0.0, -20.0, 20.0) == (499.0, 0.0)
    assert svc.dragged_node(nodes, 4, 1100.0, 0.0, -20.0, 20.0) == (1050.0, 0.0)
    assert svc.dragged_node(nodes, 4, 700.0, 0.0, -20.0, 20.0) == (801.0, 0.0)
    assert svc.dragged_node(nodes, 2, 499.5, 25.0, -20.0, 20.0) == (501.0, 20.0)
    assert svc.dragged_node(nodes, 2, 900.0, -25.0, -20.0, 20.0) == (799.0, -20.0)
    assert svc.dragged_node(nodes, 2, 640.0, 5.0, -20.0, 20.0) == (640.0, 5.0)


@pytest.mark.known_defect("D-173 pending: neighbours closer than 2 nm put the dragged node on or left of its left one")
def test_known_defect_drag_between_close_neighbours_breaks_the_order() -> None:
    nodes = np.column_stack((np.array([350.0, 500.0, 500.5, 501.0, 1050.0]), np.zeros(5)))
    for target in (400.0, 500.5, 900.0):
        x, _y = svc.dragged_node(nodes, 2, target, 0.0, -20.0, 20.0)
        assert x == 500.0 and x <= nodes[1, 0]


# --- MCU status texts (MAINT-041/042/141/142/143, UI-129) -----------------------------------------------------


@pytest.mark.spec("UI-129 MAINT-042")
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1970-01-01 08:00:01（北京时间）"),
        (1_700_000_000, "2023-11-15 06:13:20（北京时间）"),
        (0xFFFFFFFF, "2106-02-07 14:28:15（北京时间）"),
        (0, "未设置 / 无效时间戳"),
        (-5, "未设置 / 无效时间戳"),
        (0x100000000, "未设置 / 无效时间戳"),
        (None, "未设置 / 无效时间戳"),
        ("abc", "未设置 / 无效时间戳"),
        (NAN, "未设置 / 无效时间戳"),
        (INF, "未设置 / 无效时间戳"),
    ],
)
def test_mcu_timestamp(value: object, expected: str) -> None:
    assert svc.format_mcu_timestamp(value, BEIJING) == expected


def test_mcu_timestamp_uses_the_given_time_zone() -> None:
    assert svc.format_mcu_timestamp(1, UTC) == "1970-01-01 00:00:01（北京时间）"


@pytest.mark.known_defect("D-174 pending: int() accepts bool, numeric text and fractions as MCU timestamps")
@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "1970-01-01 08:00:01（北京时间）"), ("1700000000", "2023-11-15 06:13:20（北京时间）"),
     (1_700_000_000.9, "2023-11-15 06:13:20（北京时间）")],
)  # fmt: skip
def test_known_defect_timestamp_accepts_bool_numeric_text_and_fractions(value: object, expected: str) -> None:
    assert svc.format_mcu_timestamp(value, BEIJING) == expected


@pytest.mark.spec("MAINT-042 MAINT-143")
@pytest.mark.parametrize("status", [{}, None, [], "x", {"other": 1}])
def test_missing_status_shows_unread_and_no_version(status: object) -> None:
    texts = svc.status_texts(status, BEIJING)
    assert texts == svc.CalibrationStatusTexts(
        status="校准状态：未读取", error="错误状态：未读取", status_tooltip="", error_tooltip="",
        version="版本 / 节点数：—", time="未设置 / 无效时间戳",
    )  # fmt: skip


@pytest.mark.spec("MAINT-041 MAINT-141 MAINT-142 MAINT-143 UI-129")
def test_full_status() -> None:
    texts = svc.status_texts({"status": 1, "error": 0, "version_nodes": 0x15, "timestamp": 1_700_000_000}, BEIJING)
    assert texts == svc.CalibrationStatusTexts(
        status="校准状态：已校准", error="错误状态：无错误", status_tooltip="原始校准状态码：1",
        error_tooltip="原始错误码：0", version="版本 / 节点数：v1 / 5", time="2023-11-15 06:13:20",
    )  # fmt: skip


@pytest.mark.spec("MAINT-041 MAINT-141 MAINT-142")
def test_unknown_codes_keep_their_numbers() -> None:
    texts = svc.status_texts({"status": 2, "error": 7}, BEIJING)
    assert (texts.status, texts.error) == ("校准状态码：2", "错误码：7")
    assert (texts.status_tooltip, texts.error_tooltip) == ("原始校准状态码：2", "原始错误码：7")
    texts = svc.status_texts({"status": 0, "error": 1}, BEIJING)
    assert (texts.status, texts.error) == ("校准状态码：0", "错误码：1")


@pytest.mark.known_defect("D-174 pending: status True / error False compare equal to 1 / 0")
def test_known_defect_status_codes_accept_bool_and_float() -> None:
    texts = svc.status_texts({"status": True, "error": False, "version_nodes": True, "timestamp": True}, BEIJING)
    assert texts == svc.CalibrationStatusTexts(
        status="校准状态：已校准", error="错误状态：无错误", status_tooltip="原始校准状态码：True",
        error_tooltip="原始错误码：False", version="版本 / 节点数：v0 / 1", time="1970-01-01 08:00:01",
    )  # fmt: skip
    texts = svc.status_texts({"status": 1.0, "error": 0.0}, BEIJING)
    assert (texts.status, texts.error) == ("校准状态：已校准", "错误状态：无错误")
    assert (texts.status_tooltip, texts.error_tooltip) == ("原始校准状态码：1.0", "原始错误码：0.0")


@pytest.mark.known_defect("D-174 pending: version_nodes True is an int and decodes as 1")
def test_known_defect_version_nodes_accept_bool() -> None:
    assert svc.status_texts({"version_nodes": True}, BEIJING).version == "版本 / 节点数：v0 / 1"


@pytest.mark.spec("MAINT-143")
@pytest.mark.parametrize(
    ("version_nodes", "expected"),
    [(0, "版本 / 节点数：v0 / 0"), (0x15, "版本 / 节点数：v1 / 5"), (255, "版本 / 节点数：v15 / 15"),
     (256, "版本 / 节点数：—"), (-1, "版本 / 节点数：—"), ("21", "版本 / 节点数：—"), (21.0, "版本 / 节点数：—"),
     (None, "版本 / 节点数：—")],
)  # fmt: skip
def test_version_nodes_decoded_only_for_0_to_255_integers(version_nodes: object, expected: str) -> None:
    assert svc.status_texts({"version_nodes": version_nodes}, BEIJING).version == expected


def test_constants_are_the_v102_literals() -> None:
    assert (svc.CURVE_POINTS, svc.PREVIEW_MIN_NM, svc.PREVIEW_MAX_NM, svc.NODE_MIN_SPACING_NM) == (701, 350, 1050, 1)
    assert (svc.PICK_X_SPAN_NM, svc.PICK_RADIUS, svc.MCU_TIMESTAMP_MAX) == (700, 0.04, 2**32 - 1)
