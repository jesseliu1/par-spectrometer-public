"""Golden regression of the overview metrics against an independent reference (R-3-2).

Input: the synthetic MCU spectra in tests/golden/spectra.json. Expected values: tests/golden/reference.py
(pure-Python physics, exact SI constants) and closed-form hand calculations — never software_metrics itself.
Units: photon metrics µmol·m⁻²·s⁻¹, energy metrics W·m⁻², peaks nm and W·m⁻²·nm⁻¹.

Tolerances:
  * PHOTON_RTOL = 1e-6. software_metrics uses the photon constant 8.35934e-3, truncated from 8.3593472e-3
    (relative -8.65e-7, audit data-correctness.md §1). 1e-6 accepts that truncation and rejects any change of
    the constant's last kept digit downwards or of any earlier digit (>= 1.2e-6). float64 summation noise is
    ~1e-15, far below.
  * ENERGY_RTOL = 1e-12: energy sums use no constant; only summation-order noise (~1e-15) is allowed.
  * ABS_FLOOR = 1e-9: for bands that are exactly zero (e.g. no green in the LED spectrum).
Known defects / pending decisions are asserted as status quo in tests marked `known_defect`; they are kept
apart from the correct values (R-3-2) and must not be read as correctness claims.
"""

from __future__ import annotations

import math

import pytest

from par_app.math_ops import software_metrics
from tests.golden import reference, spectra, status_quo

pytestmark = pytest.mark.unit

PHOTON_RTOL = 1e-6
ENERGY_RTOL = 1e-12
ABS_FLOOR = 1e-9
SPECTRA = spectra.load()
IDS = [spectrum.name for spectrum in SPECTRA]
# software_metrics key -> reference band (closed interval, nm)
PHOTON_KEYS = {
    "ppfd": "ppfd",
    "software_ppfd": "ppfd",
    "pfd": "pfd",
    "pfd_b": "pfd_b",
    "pfd_g": "pfd_g",
    "pfd_r": "pfd_r",
    "pfd_fr": "pfd_fr",
    "pfd_far_red": "pfd_far_red",
    "pfd_nir": "pfd_nir",
    "extended_ppfd": "extended_ppfd",
    "extended_pfd": "extended_pfd",
    "extended_pfd_b": "pfd_b",
    "extended_pfd_g": "pfd_g",
    "extended_pfd_r": "pfd_r",
    "extended_pfd_fr": "extended_pfd_fr",
}


def _close(actual: float, expected: float, rtol: float) -> bool:
    return math.isclose(actual, expected, rel_tol=rtol, abs_tol=ABS_FLOOR)


def test_stored_spectra_equal_the_generator_output() -> None:
    assert [s.__dict__ for s in SPECTRA] == [s.__dict__ for s in spectra.generate()]
    for spectrum in SPECTRA:
        assert len(spectrum.raw_points) == 701
        assert all(isinstance(v, int) and 0 <= v <= spectra.UINT16_MAX for v in spectrum.raw_points)


@pytest.mark.spec("MATH-001 MATH-002")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_photon_flux_bands_match_reference(spectrum: spectra.Spectrum) -> None:
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient).photon
    wrong = {
        key: (actual[key], expected[band])
        for key, band in PHOTON_KEYS.items()
        if not _close(float(actual[key]), expected[band], PHOTON_RTOL)
    }
    assert not wrong


@pytest.mark.spec("MATH-001 MATH-002")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_irradiance_and_mccree_match_reference(spectrum: spectra.Spectrum) -> None:
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    assert _close(float(actual["integrated_irradiance"]), expected.total_irradiance, ENERGY_RTOL)
    assert _close(float(actual["mccree_ypfd"]), expected.mccree_ypfd, PHOTON_RTOL)


@pytest.mark.spec("MATH-001")
def test_product_mccree_table_equals_the_independent_upstream_table() -> None:
    """The product table (par_app/mccree1972_weights.py) must equal, node by node, the upstream transcription kept
    in tests/golden/mccree1972_upstream.txt (photobiologyWavebands, McCree 1972 Tables IV/III). Values are 2-digit
    table entries, compared exactly. The interpolated product weights must also match the reference on every
    1 nm grid point the metrics use (340–1060 nm, 0 outside 350–725 nm)."""
    from par_app import mccree1972_weights as product

    upstream = reference.MCCREE
    assert len(upstream.wavelengths_nm) == 16
    assert product.MCCREE_WAVELENGTHS_NM == upstream.wavelengths_nm
    assert product.MCCREE_FIELD_MEAN == upstream.field_mean
    assert product.MCCREE_CHAMBER_MEAN == upstream.chamber_mean
    grid = range(340, 1061)
    wrong = {
        nm: (w, reference.mccree_weight(nm))
        for nm, w in zip(grid, product.build_weight_curve(grid, variant="field"), strict=True)
        if not math.isclose(w, reference.mccree_weight(nm), rel_tol=1e-12, abs_tol=1e-15)
    }
    assert not wrong


@pytest.mark.spec("MATH-005")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_peaks_match_reference_as_integer_wavelengths(spectrum: spectra.Spectrum) -> None:
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    assert type(actual["peak_wavelength_nm"]) is int and type(actual["extended_peak_wavelength_nm"]) is int
    assert (actual["peak_wavelength_nm"], actual["extended_peak_wavelength_nm"]) == (
        expected.peak[0],
        expected.extended_peak[0],
    )
    assert _close(float(actual["peak_value"]), expected.peak[1], ENERGY_RTOL)
    assert _close(float(actual["extended_peak_value"]), expected.extended_peak[1], ENERGY_RTOL)


@pytest.mark.spec("MATH-007")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_displayed_par_equals_physical_par(spectrum: spectra.Spectrum) -> None:
    """The UI shows stored ×10 (MATH-007); that displayed value is the correct PAR in W·m⁻²."""
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    assert _close(float(actual["par"]) * 10, expected.par_w_m2, ENERGY_RTOL)
    assert _close(float(actual["extended_par"]) * 10, expected.extended_par_w_m2, ENERGY_RTOL)


@pytest.mark.known_defect("old repo issue #8 / audit data-correctness B1")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_known_defect_stored_par_is_tenfold_smaller(spectrum: spectra.Spectrum) -> None:
    """STATUS QUO, not a correct value: "par"/"extended_par" store Σ/10, and the export writes them unscaled,
    so exported PAR is 10x smaller than the UI and than physics. The correct value is asserted in
    test_displayed_par_equals_physical_par. Delete or rewrite this test when the export defect is fixed."""
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    assert _close(float(actual["par"]), expected.par_w_m2 / 10, ENERGY_RTOL)
    assert _close(float(actual["extended_par"]), expected.extended_par_w_m2 / 10, ENERGY_RTOL)


@pytest.mark.spec("MATH-022")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_pfd_uv_is_350_399_and_counts_400nm_once(spectrum: spectra.Spectrum) -> None:
    """D-103 decided (MATH-022, DEF-11, PR #31): pfd_uv / extended_pfd_uv are the closed 350–399 nm sum (the MCU
    band), so 400 nm is counted in blue only and UV + B + G + R equals the 350–699 nm total. Replaces the
    status-quo test test_known_defect_pfd_uv_counts_400nm_twice (V1.0.2: 350–400 nm, 400 nm counted twice)."""
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    irradiance = reference.irradiance(spectrum.raw_points, spectrum.coefficient)
    expected = reference.photon_flux(irradiance, *reference.UV_CANDIDATES["mcu_350_399"])
    assert _close(float(actual["pfd_uv"]), expected, PHOTON_RTOL)
    assert _close(float(actual["extended_pfd_uv"]), expected, PHOTON_RTOL)
    bands = sum(float(actual[key]) for key in ("pfd_uv", "pfd_b", "pfd_g", "pfd_r"))
    assert _close(bands, reference.photon_flux(irradiance, 350, 699), PHOTON_RTOL)


@pytest.mark.spec("MATH-022")
@pytest.mark.parametrize("spectrum", [s for s in SPECTRA if s.name == "flat"], ids=["flat"])
def test_d103_pfd_uv_equals_mcu_band(spectrum: spectra.Spectrum) -> None:
    """D-103 decided (PR #31): pfd_uv equals the MCU band 350–399 nm and no longer the V1.0.2 band 350–400 nm.
    Was the strict xfail test_pending_d103_pfd_uv_equals_mcu_band while D-103 was pending."""
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    irradiance = reference.irradiance(spectrum.raw_points, spectrum.coefficient)
    expected = reference.photon_flux(irradiance, *reference.UV_CANDIDATES["mcu_350_399"])
    v102 = reference.photon_flux(irradiance, *reference.UV_CANDIDATES["v102_350_400"])
    assert not _close(v102, expected, PHOTON_RTOL)  # the flat spectrum tells the two bands apart
    assert _close(float(actual["pfd_uv"]), expected, PHOTON_RTOL)


@pytest.mark.spec("MATH-019")
@pytest.mark.known_defect("D-102 pending: chlorophyll weight source")
@pytest.mark.parametrize("spectrum", SPECTRA, ids=IDS)
def test_known_defect_chlorophyll_snapshot(spectrum: spectra.Spectrum) -> None:
    """STATUS QUO snapshot (status_quo.json, generated by the code under test), pending D-102. Only detects
    change; it is not an independent golden value."""
    actual = software_metrics(spectrum.raw_points, spectrum.coefficient)
    snapshot = status_quo.load()[spectrum.name]
    for name in status_quo.PENDING_METRICS:
        assert math.isclose(float(actual[name]), snapshot[name], rel_tol=1e-9), name


@pytest.mark.spec("MATH-001")
def test_closed_form_anchors() -> None:
    """Hand calculations independent of reference.py (k = 1e-3/(h·c·N_A) in µmol per W·s·nm)."""
    k = 1e-3 / (6.62607015e-34 * 299792458.0 * 6.02214076e23)
    mono = next(s for s in SPECTRA if s.name == "mono_550")
    flat = next(s for s in SPECTRA if s.name == "flat")
    m = software_metrics(mono.raw_points, mono.coefficient)
    assert math.isclose(m["ppfd"], 100 * 550 * k, rel_tol=PHOTON_RTOL)  # 459.764 (audit)
    assert math.isclose(m["mccree_ypfd"], 0.82 * 100 * 550 * k, rel_tol=PHOTON_RTOL)  # 377.007, w(550)=0.82
    f = software_metrics(flat.raw_points, flat.coefficient)
    assert math.isclose(f["ppfd"], 301 * 550 * k, rel_tol=PHOTON_RTOL)  # Σλ over 400..700 = 301·550
    assert math.isclose(f["integrated_irradiance"], 701.0, rel_tol=ENERGY_RTOL)  # 701 samples × 1 W/m²/nm
    assert math.isclose(f["par"] * 10, 301.0, rel_tol=ENERGY_RTOL)
    assert (round(m["ppfd"], 3), round(f["ppfd"], 2)) == (459.764, 1383.89)


def test_rectangle_rule_is_one_third_percent_above_the_continuous_integral() -> None:
    """Documents the V1.0.2 convention: closed 1 nm rectangle sum vs ∫400–700 for a flat 1 W/m²/nm spectrum."""
    flat = reference.irradiance(next(s for s in SPECTRA if s.name == "flat").raw_points, 3)
    rectangle = reference.photon_flux(flat, 400, 700)
    continuous = reference.continuous_photon_flux(flat, 400, 700)
    assert math.isclose(continuous, (700**2 - 400**2) / 2 * reference.PHOTON_FACTOR, rel_tol=1e-12)  # 1379.29
    assert math.isclose(rectangle / continuous - 1, 1 / 300, rel_tol=1e-9)  # +0.333 %
