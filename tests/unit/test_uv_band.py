"""UV PFD band is 350–399 nm, the MCU definition (D-103, DEF-11; MATH-022).

`software_metrics` integrates closed ranges [low, high] on the 1 nm grid. Before the fix `pfd_uv` and
`extended_pfd_uv` summed 350–400 nm, so the 400 nm point was counted in both UV and blue and
UV + B + G + R exceeded the 350–699 nm total by that one point. The expected values below are computed
independently from the raw points, not from the code under test.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from par_app.math_ops import WAVELENGTHS, software_metrics

pytestmark = [pytest.mark.unit, pytest.mark.spec("MATH-022")]

PHOTON_FACTOR = 8.35934e-3  # µmol·m⁻²·s⁻¹ per (W·m⁻²·nm⁻¹ · nm), same constant as the product
REL_TOL = 1e-9
POINTS = 701
COEFFICIENT = 3


def _photon(raw: list[int], low: int, high: int, coefficient: int = COEFFICIENT) -> float:
    """Independent closed-range photon flux: Σ value·λ·k for low ≤ λ ≤ high."""
    scale = 10.0**coefficient
    return math.fsum(raw[nm - 350] / scale * nm * PHOTON_FACTOR for nm in range(low, high + 1))


def _single_point(nm: int, value: int = 1000) -> list[int]:
    raw = [0] * POINTS
    raw[nm - 350] = value
    return raw


def _random_spectrum() -> list[int]:
    rng = random.Random(20261017)
    return [rng.randint(0, 65535) for _ in range(POINTS)]


def _blackbody_2856k() -> list[int]:
    h, c, k_b = 6.626e-34, 2.998e8, 1.381e-23
    lam = WAVELENGTHS * 1e-9
    radiance = 1 / lam**5 / (np.exp(h * c / (lam * k_b * 2856)) - 1)
    return [int(x) for x in np.round(radiance / radiance.max() * 60000)]


SPECTRA = {
    "flat": [1000] * POINTS,
    "random": _random_spectrum(),
    "blackbody_2856k": _blackbody_2856k(),
}


@pytest.mark.parametrize("name", sorted(SPECTRA))
def test_uv_pfd_is_the_closed_350_399_nm_sum(name: str) -> None:
    raw = SPECTRA[name]
    metrics = software_metrics(raw, COEFFICIENT)
    expected = _photon(raw, 350, 399)
    assert math.isclose(metrics["pfd_uv"], expected, rel_tol=REL_TOL)
    assert math.isclose(metrics["extended_pfd_uv"], expected, rel_tol=REL_TOL)


def test_400_nm_counts_only_as_blue() -> None:
    metrics = software_metrics(_single_point(400), COEFFICIENT)
    assert metrics["pfd_uv"] == 0
    assert metrics["extended_pfd_uv"] == 0
    assert metrics["pfd_b"] > 0
    assert metrics["extended_pfd_b"] > 0


def test_399_nm_counts_only_as_uv() -> None:
    metrics = software_metrics(_single_point(399), COEFFICIENT)
    assert metrics["pfd_uv"] > 0
    assert metrics["extended_pfd_uv"] > 0
    assert metrics["pfd_b"] == 0
    assert metrics["extended_pfd_b"] == 0


@pytest.mark.parametrize("name", sorted(SPECTRA))
@pytest.mark.parametrize("prefix", ["", "extended_"])
def test_uv_blue_green_red_add_up_to_the_350_699_nm_total(name: str, prefix: str) -> None:
    raw = SPECTRA[name]
    metrics = software_metrics(raw, COEFFICIENT)
    bands = math.fsum(float(metrics[f"{prefix}pfd_{band}"]) for band in ("uv", "b", "g", "r"))
    assert math.isclose(bands, _photon(raw, 350, 699), rel_tol=REL_TOL)


@pytest.mark.parametrize("prefix", ["", "extended_"])
@pytest.mark.parametrize("nm", [350, 399, 400, 499, 500, 599, 600, 699, 700])
def test_each_edge_point_falls_in_exactly_one_sub_band(prefix: str, nm: int) -> None:
    """UV/B/G/R/FR edges abut without overlap: 399|400, 499|500, 599|600, 699|700."""
    metrics = software_metrics(_single_point(nm), COEFFICIENT)
    hits = [band for band in ("uv", "b", "g", "r", "fr") if metrics[f"{prefix}pfd_{band}"] > 0]
    assert len(hits) == 1, (nm, hits)
