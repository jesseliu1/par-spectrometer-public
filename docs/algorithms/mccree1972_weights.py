from __future__ import annotations

import bisect
from typing import Iterable, Literal, Sequence


PLANCK_CONSTANT = 6.62607015e-34
LIGHT_SPEED = 299792458.0
AVOGADRO_CONSTANT = 6.02214076e23

MCCREE_SOURCE_URL = (
    "https://raw.githubusercontent.com/aphalo/photobiologyWavebands/main/"
    "data-raw/McCree1972a/tables_IV_III_photon_action_spectra.txt"
)

MCCREE_APPLY_START_NM = 350
MCCREE_APPLY_END_NM = 740

# Upstream raw table from photobiologyWavebands currently exposes 16 tabulated points
# from 350 nm to 725 nm. To honor the agreed 350-740 nm application window while
# keeping a segmented 25 nm scheme, we extend one last endpoint to 740 nm using
# the slope of the final 700-725 nm segment, then do piecewise-linear interpolation.
MCCREE_RAW_WAVELENGTHS_NM: tuple[int, ...] = (
    350,
    375,
    400,
    425,
    450,
    475,
    500,
    525,
    550,
    575,
    600,
    625,
    650,
    675,
    700,
    725,
)

MCCREE_FIELD_MEAN_RAW: tuple[float, ...] = (
    0.02,
    0.12,
    0.42,
    0.68,
    0.70,
    0.63,
    0.65,
    0.72,
    0.82,
    0.91,
    0.97,
    1.00,
    0.90,
    0.90,
    0.48,
    0.23,
)

MCCREE_CHAMBER_MEAN_RAW: tuple[float, ...] = (
    0.16,
    0.45,
    0.66,
    0.76,
    0.75,
    0.68,
    0.71,
    0.74,
    0.87,
    0.95,
    1.00,
    1.00,
    0.94,
    0.92,
    0.44,
    0.20,
)

MCCREE_VARIANTS = {
    "field": MCCREE_FIELD_MEAN_RAW,
    "chamber": MCCREE_CHAMBER_MEAN_RAW,
}


def _extend_last_point_to_740(raw_values: Sequence[float]) -> float:
    left_nm = MCCREE_RAW_WAVELENGTHS_NM[-2]
    right_nm = MCCREE_RAW_WAVELENGTHS_NM[-1]
    left_value = float(raw_values[-2])
    right_value = float(raw_values[-1])
    slope = (right_value - left_value) / float(right_nm - left_nm)
    tail_value = right_value + slope * float(MCCREE_APPLY_END_NM - right_nm)
    return max(0.0, tail_value)


def get_effective_knots(
    variant: Literal["field", "chamber"] = "field",
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    raw_values = MCCREE_VARIANTS[variant]
    tail_value = _extend_last_point_to_740(raw_values)
    wavelengths = MCCREE_RAW_WAVELENGTHS_NM + (MCCREE_APPLY_END_NM,)
    values = tuple(float(value) for value in raw_values) + (tail_value,)
    return wavelengths, values


def weight_at_wavelength(
    wavelength_nm: int,
    variant: Literal["field", "chamber"] = "field",
) -> float:
    if wavelength_nm < MCCREE_APPLY_START_NM or wavelength_nm > MCCREE_APPLY_END_NM:
        return 0.0

    wavelengths, values = get_effective_knots(variant=variant)
    if wavelength_nm <= wavelengths[0]:
        return values[0]
    if wavelength_nm >= wavelengths[-1]:
        return values[-1]

    right_index = bisect.bisect_left(wavelengths, wavelength_nm)
    if wavelengths[right_index] == wavelength_nm:
        return values[right_index]

    left_index = right_index - 1
    left_nm = wavelengths[left_index]
    right_nm = wavelengths[right_index]
    left_value = values[left_index]
    right_value = values[right_index]
    ratio = (wavelength_nm - left_nm) / float(right_nm - left_nm)
    return left_value + (right_value - left_value) * ratio


def build_weight_curve(
    wavelengths_nm: Iterable[int],
    variant: Literal["field", "chamber"] = "field",
) -> tuple[float, ...]:
    return tuple(weight_at_wavelength(int(wavelength_nm), variant=variant) for wavelength_nm in wavelengths_nm)


def weighted_photon_integral_umol(
    spectral_values_wm2_nm: Sequence[float],
    wavelengths_nm: Sequence[int],
    variant: Literal["field", "chamber"] = "field",
) -> float:
    if len(spectral_values_wm2_nm) != len(wavelengths_nm):
        raise ValueError("spectrum length does not match wavelength length")

    photon_flux = 0.0
    for wavelength_nm, value_wm2_nm in zip(wavelengths_nm, spectral_values_wm2_nm):
        weight = weight_at_wavelength(int(wavelength_nm), variant=variant)
        if weight <= 0.0:
            continue
        wavelength_m = float(wavelength_nm) * 1e-9
        photon_flux += (
            float(value_wm2_nm)
            * wavelength_m
            / (PLANCK_CONSTANT * LIGHT_SPEED * AVOGADRO_CONSTANT)
            * weight
        )
    return photon_flux * 1e6
