"""par_app.services.dli: DLI computation moved out of par_app/ui.py (R-8-1 stage one, behaviour-preserving).

Expected values are written by hand from the rules in docs/spec/dli.md (trapezoid (a+b)/2·Δt in µmol, reported in
mol·m⁻²; max gap max(120, poll cycle + 60); finite non-negative values only; [period start, cutoff] and never the
period end), or come from the independent reference in tests/golden/reference.py. None is produced by the code under
test; the sunrise status-quo pins were produced once by V1.0.2 (base 98d1e82) and copied as literals. The Qt tests
(tests/qt/test_golden_dli.py, tests/qt/multidevice/test_dli.py) keep covering the same logic through
DliCanvas.plot_dli and MainWindow._dli_period/_sunrise; these tests pin the boundaries directly: None / NaN / inf /
negative / zero, zero denominators, equal and reversed timestamps, gap edges, cutoff edges, polar day and night, and
old or malformed sample rows. No mocks, no clock: every function takes "now" or the cutoff as an argument.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

import pytest

from par_app.services import dli as svc
from tests.golden import reference

pytestmark = pytest.mark.unit
NAN = float("nan")
INF = float("inf")
START = datetime(2026, 10, 14, 6, 0, 0)
END = START + timedelta(days=1)
BEIJING = (39.9042, 116.4074)


def _at(*seconds: float) -> list[datetime]:
    return [START + timedelta(seconds=s) for s in seconds]


def _run(
    seconds: list[float],
    values: list[float],
    until: float,
    max_gap: float = 120.0,
    *,
    paused: bool = False,
) -> svc.DliIntegration:
    return svc.integrate(_at(*seconds), values, START, END, START + timedelta(seconds=until), max_gap, paused=paused)


def _same(actual: list[float], expected: list[float]) -> bool:
    """Element-wise equality where NaN equals NaN (NaN marks a break in the plotted curve)."""
    return len(actual) == len(expected) and all(
        (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b, rel=1e-12, abs=0.0)
        for a, b in zip(actual, expected, strict=True)
    )


# ---------------------------------------- sunrise / dli_period (was MainWindow._sunrise / _dli_period)


@pytest.mark.spec("DLI-015")
@pytest.mark.parametrize(
    ("day", "latitude", "longitude"),
    [
        (date(2026, 10, 14), *BEIJING),
        (date(2026, 3, 20), *BEIJING),
        (date(2026, 1, 1), 31.2304, 121.4737),  # Shanghai
        (date(2026, 7, 1), 22.5431, 114.0579),  # Shenzhen
        (date(2026, 10, 14), -33.8688, 151.2093),  # southern hemisphere, east of UTC+8
        (date(2026, 10, 14), 43.8256, 87.6168),  # Urumqi, far west of UTC+8
    ],
)
def test_sunrise_matches_independent_algorithm(day: date, latitude: float, longitude: float) -> None:
    """NOAA series (product) vs the USNO algorithm (reference); both ~1 min accurate -> 120 s tolerance."""
    product = svc.sunrise(day, latitude, longitude)
    assert abs((product - reference.sunrise_usno(day, latitude, longitude)).total_seconds()) <= 120


@pytest.mark.spec("DLI-015")
def test_sunrise_polar_night_and_polar_day_are_clipped_not_errors() -> None:
    """At 80°N there is no sunrise in December and no sunset in June; cos(hour angle) is clipped to [-1, 1].
    Polar night -> hour angle 0 -> local solar noon (~12:00 at 120°E); polar day -> hour angle 180° -> local solar
    midnight (~00:00 at 120°E). The equation of time stays within ±17 min, hence the 20 min window."""
    night = svc.sunrise(date(2026, 12, 21), 80.0, 120.0)
    day = svc.sunrise(date(2026, 6, 21), 80.0, 120.0)
    assert abs((night - datetime(2026, 12, 21, 12, 0)).total_seconds()) <= 20 * 60
    assert abs((day - datetime(2026, 6, 21, 0, 0)).total_seconds()) <= 20 * 60


# V1.0.2 STATUS-QUO pins (R-3-2: status quo, not golden reference values). Each expected time was produced by
# V1.0.2's own MainWindow._sunrise at base commit 98d1e82 (before this extraction), run once by hand and copied
# here as literals; nothing is computed by the code under test at test time. The USNO comparison above only
# bounds sunrise to ±120 s, so a uniform drift of up to 2 min (e.g. "+ 480" -> "+ 481" in the time-zone term)
# would move every DLI period boundary (DLI-015) unnoticed; these pins catch any drift above 1 ms. The 1 ms
# tolerance absorbs last-ulp differences in numpy trigonometry between platforms (Windows golden machine vs
# macOS), not behaviour changes. The ±180° pins record the status quo of the time-zone arithmetic: at -180° the
# sunrise of the location's civil day falls on the next Beijing calendar day. Update only together with a change
# owner approved for DLI-015 / DLI-026.
@pytest.mark.spec("DLI-015 DLI-026")
@pytest.mark.parametrize(
    ("day", "latitude", "longitude", "expected"),
    [
        pytest.param(
            date(2026, 3, 20), *BEIJING, datetime(2026, 3, 20, 6, 19, 43, 986313), id="beijing_spring_equinox"
        ),
        pytest.param(
            date(2026, 6, 21), *BEIJING, datetime(2026, 6, 21, 4, 45, 30, 657810), id="beijing_summer_solstice"
        ),
        pytest.param(date(2026, 9, 23), *BEIJING, datetime(2026, 9, 23, 6, 1, 33, 142552), id="beijing_autumn_equinox"),
        pytest.param(
            date(2026, 12, 21), *BEIJING, datetime(2026, 12, 21, 7, 32, 5, 424499), id="beijing_winter_solstice"
        ),
        pytest.param(
            date(2026, 1, 1), 31.2304, 121.4737, datetime(2026, 1, 1, 6, 52, 28, 139612), id="shanghai_new_year"
        ),
        pytest.param(date(2026, 10, 14), 43.8256, 87.6168, datetime(2026, 10, 14, 8, 21, 2, 813367), id="urumqi"),
        pytest.param(date(2026, 6, 21), 80.0, 120.0, datetime(2026, 6, 21, 0, 1, 19, 694208), id="polar_day_80n"),
        pytest.param(date(2026, 12, 21), 80.0, 120.0, datetime(2026, 12, 21, 11, 57, 49, 768443), id="polar_night_80n"),
        pytest.param(
            date(2026, 10, 14), 30.0, 180.0, datetime(2026, 10, 14, 2, 0, 10, 294079), id="longitude_plus_180"
        ),
        pytest.param(
            date(2026, 10, 14), 30.0, -180.0, datetime(2026, 10, 15, 2, 0, 10, 294079), id="longitude_minus_180"
        ),
        pytest.param(date(2028, 12, 31), *BEIJING, datetime(2028, 12, 31, 7, 35, 39, 459685), id="leap_year_day_366"),
    ],
)
def test_sunrise_equals_v102_status_quo(day: date, latitude: float, longitude: float, expected: datetime) -> None:
    assert abs((svc.sunrise(day, latitude, longitude) - expected).total_seconds()) <= 1e-3


@pytest.mark.spec("DLI-015 DLI-022")
def test_period_at_beijing_noon_equals_v102_status_quo() -> None:
    """Absolute period pin, far from any sunrise boundary: noon on the autumn equinox starts at that morning's
    V1.0.2 sunrise (same literal as the beijing_autumn_equinox pin above) and lasts exactly 24 h."""
    start, end = svc.dli_period(datetime(2026, 9, 23, 12, 0), BEIJING)
    expected = datetime(2026, 9, 23, 6, 1, 33, 142552)
    assert abs((start - expected).total_seconds()) <= 1e-3
    assert end - start == timedelta(days=1)


@pytest.mark.spec("DLI-026")
def test_sunrise_longitude_sign_east_positive() -> None:
    """East is positive: 1° further east rises 4 minutes earlier on the same day at the same latitude."""
    west = svc.sunrise(date(2026, 10, 14), 30.0, 110.0)
    east = svc.sunrise(date(2026, 10, 14), 30.0, 111.0)
    assert (west - east).total_seconds() == pytest.approx(240.0, abs=2e-6)


@pytest.mark.spec("DLI-015 DLI-022")
@pytest.mark.parametrize(
    ("now_offset", "starts_today"),
    [(-3600.0, False), (0.0, True), (3600.0, True), (17 * 3600.0, True)],
    ids=["hour_before", "at_sunrise", "hour_after", "late_evening"],
)
def test_period_starts_at_the_last_sunrise_and_lasts_24h(now_offset: float, starts_today: bool) -> None:
    day = date(2026, 10, 14)
    now = svc.sunrise(day, *BEIJING) + timedelta(seconds=now_offset)
    start, end = svc.dli_period(now, BEIJING)
    expected_day = day if starts_today else day - timedelta(days=1)
    assert start == svc.sunrise(expected_day, *BEIJING)
    assert abs((start - reference.sunrise_usno(expected_day, *BEIJING)).total_seconds()) <= 120
    assert end - start == timedelta(days=1)
    assert start <= now < end


@pytest.mark.spec("DLI-015")
def test_d165_gap_before_a_later_sunrise_shows_the_period_that_just_ended() -> None:
    """D-165 decided A (keep status quo): in October Beijing sunrise moves ~1 min later each day, so 1 ms before
    today's sunrise lies after yesterday's sunrise + 24 h; the period returned is still yesterday's."""
    day = date(2026, 10, 14)
    now = svc.sunrise(day, *BEIJING) - timedelta(milliseconds=1)
    start, end = svc.dli_period(now, BEIJING)
    assert start == svc.sunrise(day - timedelta(days=1), *BEIJING)
    assert end <= now


@pytest.mark.spec("DLI-025")
def test_period_follows_the_location_passed_in() -> None:
    now = datetime(2026, 10, 14, 12, 0)
    beijing, _ = svc.dli_period(now, BEIJING)
    urumqi, _ = svc.dli_period(now, (43.8256, 87.6168))
    assert urumqi - beijing > timedelta(hours=1)  # ~29° further west -> ~2 h later sunrise


# ---------------------------------------- max gap (was inline in MainWindow.refresh_diagnostics)


@pytest.mark.spec("DLI-009 DLI-010 DLI-013")
@pytest.mark.parametrize(
    ("cycle", "expected"),
    [(0.0, 120.0), (10.0, 120.0), (60.0, 120.0), (60.5, 120.5), (61.0, 121.0), (600.0, 660.0), (3600.0, 3660.0)],
)
def test_max_gap_is_120_s_or_poll_cycle_plus_60_s(cycle: float, expected: float) -> None:
    assert svc.max_gap_seconds(cycle) == expected


# ---------------------------------------- build_series (was inline in MainWindow.refresh_diagnostics)


def _row(stamp: object, metrics: object, eligible: object = 1) -> dict[str, object]:
    return {"timestamp": stamp, "software_metrics_json": metrics, "eligible": eligible}


ALL = json.dumps({"ppfd": 100.0, "mccree_ypfd": 90.0, "chlorophyll_a_ypfd": 30.0, "chlorophyll_b_ypfd": 20.0})


@pytest.mark.spec("DLI-001 DLI-012 DLI-017 DLI-032")
def test_build_series_maps_rows_to_per_metric_values() -> None:
    rows = [
        _row("2026-10-14T08:00:00", ALL),
        _row("2026-10-14T08:01:00", ALL, eligible=0),  # ineligible: keeps its time, NaN everywhere
        _row("2026-10-14T08:02:00", json.dumps({"ppfd": 0.0, "mccree_ypfd": None, "chlorophyll_a_ypfd": "7.5"})),
        _row("2026-10-14T08:03:00", None),  # interruption row from dli_interruptions: NULL json, eligible 0
        _row("2026-10-14T08:04:00", None, eligible=1),  # NULL json but eligible -> "{}" -> NaN
        _row("2026-10-14T08:05:00", "{not json"),  # invalid JSON -> NaN
        _row("2026-10-14T08:06:00", "[1, 2]"),  # JSON that is not an object -> NaN
        _row("2026-10-14T08:07:00", json.dumps({"ppfd": [1], "mccree_ypfd": {}, "chlorophyll_a_ypfd": "x"})),
        _row("2026-10-14T08:08:00", json.dumps({"ppfd": True, "mccree_ypfd": -5, "chlorophyll_b_ypfd": "inf"})),
    ]
    times, series = svc.build_series(rows)
    assert list(times) == list(series) == list(svc.DLI_METRICS)
    stamps = [datetime(2026, 10, 14, 8, minute) for minute in range(9)]
    assert all(times[metric] == stamps for metric in svc.DLI_METRICS)
    expected = {
        "ppfd": [100.0, NAN, 0.0, NAN, NAN, NAN, NAN, NAN, 1.0],
        "mccree_ypfd": [90.0, NAN, NAN, NAN, NAN, NAN, NAN, NAN, -5.0],
        "chlorophyll_a_ypfd": [30.0, NAN, 7.5, NAN, NAN, NAN, NAN, NAN, NAN],
        "chlorophyll_b_ypfd": [20.0, NAN, NAN, NAN, NAN, NAN, NAN, NAN, INF],
    }
    for metric, values in expected.items():
        assert _same(series[metric], values), metric


@pytest.mark.spec("DLI-014")
def test_build_series_skips_rows_whose_timestamp_does_not_parse() -> None:
    rows = [_row(None, ALL), _row("", ALL), _row("yesterday", ALL), _row(20261014, ALL), _row("2026-10-14T08:00", ALL)]
    times, series = svc.build_series(rows)
    assert times["ppfd"] == [datetime(2026, 10, 14, 8, 0)]
    assert series["ppfd"] == [100.0]


def test_build_series_ineligible_row_is_not_decoded() -> None:
    """eligible is checked first, so malformed JSON on an ineligible row never matters."""
    times, series = svc.build_series([_row("2026-10-14T08:00:00", "{broken", eligible=0)], metrics=("ppfd",))
    assert list(series) == ["ppfd"]
    assert times["ppfd"] == [datetime(2026, 10, 14, 8, 0)]
    assert math.isnan(series["ppfd"][0])


def test_build_series_empty() -> None:
    times, series = svc.build_series([])
    assert times == {metric: [] for metric in svc.DLI_METRICS}
    assert series == {metric: [] for metric in svc.DLI_METRICS}


# ---------------------------------------- integrate (was the computation in DliCanvas.plot_dli)


@pytest.mark.spec("DLI-008 DLI-030 DLI-039")
def test_trapezoid_over_actual_intervals_and_the_curve_matches_the_total() -> None:
    # (0+100)/2·40 + (100+300)/2·80 = 2000 + 16000 µmol = 0.018 mol
    result = _run([0, 40, 120], [0.0, 100.0, 300.0], until=120)
    s = result.summary
    assert s.total == pytest.approx(0.018, rel=1e-12)
    assert (s.covered_seconds, s.missing_seconds, s.coverage) == (120.0, 0.0, 1.0)
    assert (s.first_valid, s.last_valid, s.integrated_until) == (*_at(0, 120), _at(120)[0])
    assert (s.head_seconds, s.internal_seconds, s.tail_seconds) == (0.0, 0.0, 0.0)
    assert (s.state, s.stale, s.paused, s.cutoff) == ("积分中", False, False, _at(120)[0])
    assert result.plot_times == _at(0, 40, 120)
    assert _same(result.cumulative, [0.0, 0.002, 0.018])
    assert result.cumulative[-1] == s.total


@pytest.mark.spec("DLI-001 DLI-012 DLI-018 DLI-036 DLI-046 DLI-047 DLI-048 DLI-051")
@pytest.mark.parametrize("bad", [NAN, INF, -INF, -1.0, -1e-12])
def test_invalid_value_breaks_the_segment(bad: float) -> None:
    # 0-60 s: 100·60 = 6000 µmol; the bad sample at 120 s breaks; 180-240 s: 6000 µmol. Total 0.012 mol.
    result = _run([0, 60, 120, 180, 240], [100.0, 100.0, bad, 100.0, 100.0], until=240)
    s = result.summary
    assert s.total == pytest.approx(0.012, rel=1e-12)
    assert (s.covered_seconds, s.internal_seconds, s.missing_seconds) == (120.0, 120.0, 120.0)
    assert s.state == "部分累计"
    assert result.plot_times == _at(0, 60, 120, 180, 240)
    assert _same(result.cumulative, [0.0, 0.006, NAN, 0.006, 0.012])


@pytest.mark.spec("DLI-018 DLI-036")
def test_zero_is_valid_and_integrates_to_zero() -> None:
    s = _run([0, 60, 120], [0.0, 0.0, 0.0], until=120).summary
    assert (s.total, s.covered_seconds, s.state) == (0.0, 120.0, "积分中")


@pytest.mark.spec("DLI-010 DLI-029 DLI-047 DLI-048")
def test_gap_edge_inclusive_at_max_gap_and_broken_beyond() -> None:
    joined = _run([0, 120], [100.0, 100.0], until=120).summary
    assert (joined.total, joined.covered_seconds, joined.state) == (pytest.approx(0.012), 120.0, "积分中")
    split = _run([0, 120.5], [100.0, 100.0], until=120.5)
    assert (split.summary.total, split.summary.covered_seconds) == (0.0, 0.0)
    assert split.summary.state == "有效数据不足"
    assert split.plot_times == _at(0, 120.5, 120.5)  # NaN marker at the later sample, then the sample itself
    assert _same(split.cumulative, [0.0, NAN, 0.0])
    wide = _run([0, 3600], [100.0, 100.0], until=3600, max_gap=3660.0).summary
    assert wide.total == pytest.approx(0.36, rel=1e-12)  # same samples, longer poll cycle -> bridged


@pytest.mark.spec("DLI-008")
def test_equal_timestamps_add_nothing_and_reversed_ones_break() -> None:
    same = _run([0, 60, 60, 120], [100.0, 100.0, 300.0, 300.0], until=120)
    # (100+100)/2·60 + 0 + (300+300)/2·60 = 6000 + 18000 µmol
    assert same.summary.total == pytest.approx(0.024, rel=1e-12)
    assert same.summary.covered_seconds == 120.0
    assert same.summary.integrated_until == _at(120)[0]
    back = _run([60, 30, 90], [100.0, 100.0, 100.0], until=90)
    assert back.summary.state == "部分累计"  # negative interval is treated as a break, not a negative area
    assert back.summary.total == pytest.approx(0.006, rel=1e-12)
    assert _same(back.cumulative, [0.0, NAN, 0.0, 0.006])


@pytest.mark.spec("DLI-016 DLI-028 DLI-033 DLI-040")
def test_window_is_period_start_to_cutoff_and_never_the_period_end() -> None:
    before = START - timedelta(seconds=60)
    stamps = [before, *_at(0, 60, 120, 180)]
    s = svc.integrate(stamps, [999.0, 100.0, 100.0, 100.0, 999.0], START, END, START + timedelta(seconds=120)).summary
    assert s.total == pytest.approx(0.012, rel=1e-12)  # 0..120 s only: earlier and later samples are ignored
    assert s.cutoff == _at(120)[0]
    at_end = svc.integrate([END - timedelta(seconds=60), END], [100.0, 100.0], START, END, END + timedelta(hours=5))
    assert at_end.summary.cutoff == END  # cutoff after the period end is clamped to it
    assert at_end.summary.covered_seconds == 0.0  # the sample at END itself is excluded
    assert at_end.summary.tail_seconds == 60.0
    assert at_end.summary.missing_seconds == 86400.0
    assert at_end.summary.coverage == 0.0


@pytest.mark.spec("DLI-034 DLI-038 DLI-040")
def test_no_samples_and_zero_elapsed_time_have_no_invented_values() -> None:
    empty = _run([], [], until=3600).summary
    assert (empty.total, empty.covered_seconds, empty.coverage, empty.state) == (0.0, 0.0, 0.0, "有效数据不足")
    assert (empty.first_valid, empty.last_valid, empty.integrated_until) == (None, None, None)
    assert (empty.head_seconds, empty.internal_seconds, empty.tail_seconds) == (3600.0, 0.0, 0.0)
    assert (empty.missing_seconds, empty.stale) == (3600.0, False)
    for until in (START, START - timedelta(hours=1)):  # elapsed 0: coverage denominator is zero -> 0.0
        zero = svc.integrate(_at(0), [100.0], START, END, until).summary
        assert (zero.cutoff, zero.coverage, zero.missing_seconds) == (START, 0.0, 0.0)
        assert (zero.first_valid, zero.covered_seconds, zero.state) == (START, 0.0, "有效数据不足")


@pytest.mark.spec("DLI-034 DLI-037")
def test_single_point_is_not_enough() -> None:
    s = _run([600], [100.0], until=600).summary
    assert (s.total, s.covered_seconds, s.state) == (0.0, 0.0, "有效数据不足")
    assert (s.first_valid, s.last_valid, s.integrated_until) == (_at(600)[0], _at(600)[0], None)
    assert s.head_seconds == 600.0


@pytest.mark.spec("DLI-038 DLI-042 DLI-044 DLI-046")
@pytest.mark.parametrize(
    ("first", "tail", "state", "stale"),
    [
        (120.0, 120.0, "积分中", False),  # head and tail exactly at the max gap: still complete
        (120.5, 0.0, "部分累计", False),  # head longer than the max gap
        (0.0, 120.5, "部分累计", True),  # data not updated for longer than the max gap
    ],
)
def test_head_and_tail_against_the_max_gap(first: float, tail: float, state: str, stale: bool) -> None:
    last = first + 60
    s = _run([first, last], [100.0, 100.0], until=last + tail).summary
    assert (s.head_seconds, s.tail_seconds, s.state, s.stale) == (first, tail, state, stale)
    assert s.missing_seconds == first + tail
    assert s.coverage == pytest.approx(60 / (first + 60 + tail), rel=1e-12)


@pytest.mark.spec("DLI-043")
def test_paused_is_passed_through_unchanged() -> None:
    assert _run([0, 60], [100.0, 100.0], until=60, paused=True).summary.paused is True
    assert _run([0, 60], [100.0, 100.0], until=60).summary.paused is False


def test_summary_dict_keeps_the_keys_and_order_dli_canvas_exposed() -> None:
    summary = _run([0, 60], [100.0, 100.0], until=60).summary
    assert list(summary.as_dict()) == [
        "total", "covered_seconds", "missing_seconds", "coverage", "first_valid", "last_valid",
        "integrated_until", "head_seconds", "internal_seconds", "tail_seconds", "cutoff", "state", "stale", "paused",
    ]  # fmt: skip
    assert summary.as_dict()["first_valid"] is summary.first_valid


@pytest.mark.spec("DLI-008 DLI-030")
def test_matches_independent_reference_on_a_mixed_series() -> None:
    seconds = [0, 30, 145, 205, 265, 300, 300, 420, 500, 560, 3000, 3060]
    values = [0.0, 250.0, 500.0, NAN, 800.0, 750.0, 760.0, 900.0, -3.0, 1200.0, 1500.0, 1400.0]
    until = START + timedelta(seconds=3030)
    result = svc.integrate(_at(*seconds), values, START, END, until, 120.0)
    expected = reference.dli_trapezoid(list(zip(_at(*seconds), values, strict=True)), START, END, until, 120.0)
    assert result.summary.total == pytest.approx(expected.total_mol_m2, rel=1e-12)
    assert result.summary.covered_seconds == expected.covered_seconds
    assert result.summary.state == "部分累计"


def test_value_none_raises_like_the_original_canvas() -> None:
    """Status quo: plot_dli never received None (build_series turns it into NaN); a direct None raises TypeError
    from numpy as it did inside DliCanvas.plot_dli."""
    with pytest.raises(TypeError):
        _run([0, 60], [100.0, None], until=60)  # type: ignore[list-item]
