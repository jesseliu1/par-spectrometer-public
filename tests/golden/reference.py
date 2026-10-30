"""Independent reference implementation for the golden metric and DLI tests (R-3-2).

Nothing here imports par_app. The McCree 1972 weight table is read from tests/golden/mccree1972_upstream.txt,
a copy of the upstream transcription kept apart from the product table (photobiologyWavebands
`data-raw/McCree1972a/tables_IV_III_photon_action_spectra.txt`, McCree 1972 Agric. Meteorol. 9:191-216,
Table IV field mean / Table III chamber mean; the same file the audit compared against in
internal notes §3). The interpolation over that table is re-implemented here, so
a wrong node in par_app/mccree1972_weights.py changes the product YPFD but not the expected value.

Physics (pure Python, `math.fsum`, no numpy):
  * spectral irradiance E(λ) [W·m⁻²·nm⁻¹] = raw / 10**max(0, coefficient)  (MCU register encoding);
  * photon flux density [µmol·m⁻²·s⁻¹] = Σ E(λ)·λ·Δλ / (h·c·N_A), λ in m, Δλ = 1 nm, ×1e6 for µmol;
  * energy [W·m⁻²] = Σ E(λ)·Δλ.
Constants are the exact SI 2019 values (CODATA 2018): h = 6.62607015e-34 J·s, c = 299792458 m/s,
N_A = 6.02214076e23 mol⁻¹, so 1e-9·1e6/(h·c·N_A) = 8.3593472e-3 µmol·J⁻¹·nm⁻¹.

Integration rule: closed-interval rectangle sum over the 1 nm samples (400–700 nm is 301 points), which is the
V1.0.2 and MCU convention (internal notes `range_accumulate`). For a flat spectrum
this is 301/300 of the continuous integral, i.e. +0.333 % (see `continuous_photon_flux`); the golden tests
pin the V1.0.2 rule, not the continuous integral.

Band edges come from the MCU firmware (internal notes) where it defines the band,
otherwise from the export field names in internal notes (700–750, 751–1050).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

PLANCK = 6.62607015e-34  # J·s, exact (SI 2019)
LIGHT_SPEED = 299_792_458.0  # m/s, exact
AVOGADRO = 6.02214076e23  # 1/mol, exact
PHOTON_FACTOR = 1e-9 * 1e6 / (PLANCK * LIGHT_SPEED * AVOGADRO)  # µmol/J per nm of wavelength
FIRST_NM, LAST_NM = 350, 1050

# (low, high) inclusive, nm. Source: MCU firmware spectral_metrics_calc.c unless noted.
BANDS: dict[str, tuple[int, int]] = {
    "ppfd": (400, 700),
    "pfd": (350, 780),
    "pfd_b": (400, 499),
    "pfd_g": (500, 599),
    "pfd_r": (600, 699),
    "pfd_fr": (700, 780),
    "pfd_far_red": (700, 750),  # export field 远红光PFD(700–750)
    "pfd_nir": (751, 1050),  # export field 近红外PFD(751–1050)
    "extended_ppfd": (400, 750),
    "extended_pfd": (350, 1050),
    "extended_pfd_fr": (700, 1050),
}
# UV band: D-103 decided 350–399 nm (MATH-022, PR #31). The V1.0.2 band is kept only so that tests can show the
# two bands apart; it is not a correct value.
UV_CANDIDATES: dict[str, tuple[int, int]] = {
    "mcu_350_399": (350, 399),  # MCU firmware spectral_calc_PFD_uv; par_app since D-103
    "v102_350_400": (350, 400),  # V1.0.2: 400 nm was counted in both UV and blue
}


MCCREE_TABLE = Path(__file__).with_name("mccree1972_upstream.txt")


@dataclass(frozen=True)
class McCreeTable:
    """McCree 1972 relative quantum efficiency, nodes every 25 nm (dimensionless, max 1.00 at 625 nm)."""

    wavelengths_nm: tuple[int, ...]
    field_mean: tuple[float, ...]  # Table IV, field-grown plants
    chamber_mean: tuple[float, ...]  # Table III, growth-chamber plants


def load_mccree_table(path: Path = MCCREE_TABLE) -> McCreeTable:
    """Parse the upstream whitespace table: a '#' title line, a column header, then 'nm field chamber' rows."""
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    data = [row for row in rows if row and not row[0].startswith("#") and row[0] != "w.length"]
    return McCreeTable(
        wavelengths_nm=tuple(int(row[0]) for row in data),
        field_mean=tuple(float(row[1]) for row in data),
        chamber_mean=tuple(float(row[2]) for row in data),
    )


MCCREE = load_mccree_table()


def wavelengths() -> list[int]:
    return list(range(FIRST_NM, LAST_NM + 1))


def irradiance(raw_points: Sequence[int], coefficient: int) -> list[float]:
    """Spectral irradiance in W·m⁻²·nm⁻¹ from MCU integers (register value / 10**coefficient)."""
    if len(raw_points) != LAST_NM - FIRST_NM + 1:
        raise ValueError("a spectrum has 701 points (350–1050 nm, 1 nm step)")
    scale = 10.0 ** max(0, coefficient)
    return [value / scale for value in raw_points]


def photon_flux(spectrum: Sequence[float], low_nm: int, high_nm: int) -> float:
    """µmol·m⁻²·s⁻¹ over [low, high] nm, closed-interval 1 nm rectangle sum."""
    terms = [spectrum[nm - FIRST_NM] * nm * PHOTON_FACTOR for nm in range(low_nm, high_nm + 1)]
    return math.fsum(terms)


def energy(spectrum: Sequence[float], low_nm: int, high_nm: int) -> float:
    """W·m⁻² over [low, high] nm, closed-interval 1 nm rectangle sum."""
    return math.fsum(spectrum[nm - FIRST_NM] for nm in range(low_nm, high_nm + 1))


def continuous_photon_flux(spectrum: Sequence[float], low_nm: int, high_nm: int) -> float:
    """Trapezoid integral of the photon flux (end points weighted 1/2); used only to document the 0.33 % gap."""
    flux = [spectrum[nm - FIRST_NM] * nm * PHOTON_FACTOR for nm in range(low_nm, high_nm + 1)]
    return math.fsum(flux) - (flux[0] + flux[-1]) / 2


def mccree_weight(nm: float) -> float:
    """McCree 1972 field mean, piecewise linear between the 25 nm table nodes, 0 outside 350–725 nm."""
    nodes, weights = MCCREE.wavelengths_nm, MCCREE.field_mean
    if nm < nodes[0] or nm > nodes[-1]:
        return 0.0
    for left in range(len(nodes) - 1):
        x0, x1 = nodes[left], nodes[left + 1]
        if x0 <= nm <= x1:
            y0, y1 = weights[left], weights[left + 1]
            return y0 + (y1 - y0) * (nm - x0) / (x1 - x0)
    return weights[-1]


def mccree_ypfd(spectrum: Sequence[float]) -> float:
    """Yield photon flux density: Σ PFD(λ)·w(λ) over the whole 350–1050 grid (w = 0 beyond 725 nm)."""
    return math.fsum(spectrum[i] * nm * PHOTON_FACTOR * mccree_weight(nm) for i, nm in enumerate(wavelengths()))


def peak(spectrum: Sequence[float], low_nm: int, high_nm: int) -> tuple[int, float]:
    """First wavelength with the maximum value in [low, high] nm."""
    best_nm = low_nm
    for nm in range(low_nm, high_nm + 1):
        if spectrum[nm - FIRST_NM] > spectrum[best_nm - FIRST_NM]:
            best_nm = nm
    return best_nm, spectrum[best_nm - FIRST_NM]


@dataclass(frozen=True)
class Metrics:
    """Correct values per physical definition (units in the field names' docstring)."""

    photon: dict[str, float]  # µmol·m⁻²·s⁻¹ per BANDS key
    total_irradiance: float  # W·m⁻², 350–1050 nm
    par_w_m2: float  # W·m⁻², 400–700 nm (the value the UI shows; NOT the stored /10 value)
    extended_par_w_m2: float  # W·m⁻², 400–750 nm
    mccree_ypfd: float  # µmol·m⁻²·s⁻¹
    peak: tuple[int, float]  # (nm, W·m⁻²·nm⁻¹), 400–700 nm
    extended_peak: tuple[int, float]  # 350–1050 nm


def metrics(raw_points: Sequence[int], coefficient: int) -> Metrics:
    spectrum = irradiance(raw_points, coefficient)
    return Metrics(
        photon={name: photon_flux(spectrum, low, high) for name, (low, high) in BANDS.items()},
        total_irradiance=energy(spectrum, FIRST_NM, LAST_NM),
        par_w_m2=energy(spectrum, 400, 700),
        extended_par_w_m2=energy(spectrum, 400, 750),
        mccree_ypfd=mccree_ypfd(spectrum),
        peak=peak(spectrum, 400, 700),
        extended_peak=peak(spectrum, FIRST_NM, LAST_NM),
    )


# ---------------------------------------------------------------- DLI


@dataclass(frozen=True)
class DliResult:
    total_mol_m2: float
    covered_seconds: float


def dli_record_eligible(success: object, dli_eligible: object, quality_json: object) -> bool:
    """Whether one stored acquisition counts toward DLI, written from the spec text (DLI-007, DLI-012, DLI-021)
    and the D-126 ruling (owner 2026-10-17), not from the product SQL.

    * a failed acquisition never counts;
    * a record that carries dli_eligible (written by V1.0.x and later) counts only when it is 1;
    * a legacy record (dli_eligible missing) counts ("原资格": a successful acquisition counts) unless its
      quality record says the review is incomplete: `confirmed` is the JSON value false and the record is not a
      single-capture record. This is the same condition under which the history details show "复核未完成".
      No readable review information (no quality record, not JSON, not an object, no `confirmed`, or a value
      that is not exactly false) means "照旧计入".
    """
    if success != 1:
        return False
    if dli_eligible is not None:
        return dli_eligible == 1
    try:
        quality = json.loads(quality_json) if quality_json else {}
    except ValueError:
        return True
    if not isinstance(quality, dict):
        return True
    review_incomplete = quality.get("strategy") != "single_capture" and quality.get("confirmed") is False
    return not review_incomplete


def dli_trapezoid(
    samples: Sequence[tuple[datetime, float]],
    period_start: datetime,
    period_end: datetime,
    cutoff: datetime,
    max_gap_seconds: float,
) -> DliResult:
    """Trapezoid DLI per docs/spec/dli.md (DLI-008/010/016/018/029/047/048).

    Only samples in [period_start, min(cutoff, period_end)) count (the end itself is excluded). A value that is
    not finite or is negative breaks the segment (zero is valid). Neighbours further apart than max_gap_seconds
    are not joined (no zero filling, no bridging). Each joined pair adds (a+b)/2·Δt µmol, reported in mol.
    """
    limit = min(max(cutoff, period_start), period_end)
    total: list[float] = []
    covered = 0.0
    previous: tuple[datetime, float] | None = None
    for stamp, value in samples:
        if stamp < period_start or stamp > limit or stamp >= period_end:
            continue
        if not math.isfinite(value) or value < 0:
            previous = None
            continue
        if previous is not None:
            seconds = (stamp - previous[0]).total_seconds()
            if 0 <= seconds <= max_gap_seconds:
                total.append((previous[1] + value) / 2 * seconds / 1e6)
                covered += seconds
        previous = stamp, value
    return DliResult(math.fsum(total), covered)


def sunrise_usno(day: date, latitude: float, longitude: float, utc_offset_hours: float = 8.0) -> datetime:
    """Sunrise by the USNO "Almanac for Computers" (1990) algorithm, zenith 90°50'.

    A different method from the NOAA fractional-year series used by the product; both are ~1 minute accurate,
    so comparisons use a 2 minute tolerance.
    """
    n = day.timetuple().tm_yday
    t = n + (6 - longitude / 15) / 24
    mean_anomaly = 0.9856 * t - 3.289
    true_long = (
        mean_anomaly
        + 1.916 * math.sin(math.radians(mean_anomaly))
        + 0.020 * math.sin(math.radians(2 * mean_anomaly))
        + 282.634
    ) % 360
    right_asc = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_long)))) % 360
    right_asc += (true_long // 90) * 90 - (right_asc // 90) * 90
    right_asc /= 15
    sin_dec = 0.39782 * math.sin(math.radians(true_long))
    cos_dec = math.cos(math.asin(sin_dec))
    zenith = math.radians(90 + 50 / 60)
    lat = math.radians(latitude)
    cos_h = (math.cos(zenith) - sin_dec * math.sin(lat)) / (cos_dec * math.cos(lat))
    hour = (360 - math.degrees(math.acos(cos_h))) / 15
    local_mean = hour + right_asc - 0.06571 * t - 6.622
    local_hours = (local_mean - longitude / 15 + utc_offset_hours) % 24
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=local_hours)


def spectrum_operation(a: Sequence[float], b: Sequence[float], operation: str) -> list[float]:
    """A+B, A−B or A/B point by point per docs/spec/math.md (MATH-008..MATH-011), written from the rules alone.

    A ratio is NaN where B is 0 (0/0 included), where either input is not finite and where the quotient overflows;
    A = 0 over a non-zero finite B is a valid 0; finite high ratios are kept as they are (no capping).
    """
    out: list[float] = []
    for left, right in zip(a, b, strict=True):
        if operation == "add":
            out.append(left + right)
        elif operation == "subtract":
            out.append(left - right)
        elif operation == "divide":
            if not (math.isfinite(left) and math.isfinite(right)) or right == 0:
                out.append(math.nan)
                continue
            try:
                quotient = left / right
            except OverflowError:
                quotient = math.nan
            out.append(quotient if math.isfinite(quotient) else math.nan)
        else:
            raise ValueError(operation)
    return out


def ratio_display_threshold(a: Sequence[float], b: Sequence[float]) -> float:
    """T = 2 % × max(peak of A, peak of B) over all 701 points, 350–1050 nm (MATH-015)."""
    return 0.02 * max(max(a), max(b))


def ratio_display_passes(a: float, b: float, threshold: float) -> bool:
    """A ratio point is drawn only when A ≥ T, B ≥ T and B ≠ 0 (MATH-014)."""
    return a >= threshold and b >= threshold and b != 0
