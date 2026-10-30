"""Golden spectra through the history API (api-contract-v0 5.6; R-3-2).

Each golden spectrum (tests/golden/spectra.json) is stored the way V1.0.3 stores an acquisition: software_metrics
computed by par_app.math_ops at capture time, then saved with ParDatabase. The API detail must show exactly the
texts par_app.services.metrics gives for that stored row, and those texts must agree with the independent
reference implementation (tests/golden/reference.py) to the displayed precision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.math_ops import software_metrics
from par_app.services import metrics as metric_service
from tests.api.conftest import record, register_device, v1_database
from tests.golden import reference, spectra

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-018 MATH-007")]
SPECTRA = spectra.load()
PHOTON_RTOL = 1e-6  # see tests/unit/test_golden_metrics.py: product photon constant truncated by -8.65e-7
HALF_LAST_DIGIT = 0.0005  # 3-decimal text: rounding moves the shown value by at most half a unit of the last digit
# API metric keys whose reference value is reference.BANDS photon flux of the same name (µmol·m⁻²·s⁻¹)
PHOTON_BANDS = (
    "ppfd",
    "pfd",
    "pfd_b",
    "pfd_g",
    "pfd_r",
    "pfd_fr",
    "pfd_far_red",
    "pfd_nir",
    "extended_ppfd",
    "extended_pfd",
)


def _stored(spectrum: spectra.Spectrum, at: str) -> dict[str, Any]:
    metrics = software_metrics(spectrum.raw_points, spectrum.coefficient)
    return record(
        at,
        spectral_coefficient=spectrum.coefficient,
        raw_points=spectrum.raw_points,
        software_metrics_json=json.dumps(metrics),
    )


@pytest.fixture
def golden_client(client: TestClient, tmp_path: Path) -> TestClient:
    rows = [_stored(spectrum, f"2026-10-01T12:{index:02d}:00.000") for index, spectrum in enumerate(SPECTRA)]
    register_device(client, v1_database(tmp_path / "v1" / "golden.sqlite3", rows))
    return client


def _texts(client: TestClient, acquisition_id: int) -> dict[str, str]:
    body = client.get(f"/api/v0/devices/p1/acquisitions/{acquisition_id}").json()
    return {item["key"]: item["text"] for group in body["groups"] for item in group["items"]}


@pytest.mark.parametrize("index", range(len(SPECTRA)), ids=[spectrum.name for spectrum in SPECTRA])
def test_api_texts_equal_the_services_texts_of_the_stored_row(
    golden_client: TestClient, index: int, tmp_path: Path
) -> None:
    from par_app.database import ParDatabase

    stored = ParDatabase(tmp_path / "v1" / "golden.sqlite3").get_spectrum(index + 1)
    assert stored is not None
    assert _texts(golden_client, index + 1) == metric_service.record_metric_values(stored[0])


@pytest.mark.parametrize("index", range(len(SPECTRA)), ids=[spectrum.name for spectrum in SPECTRA])
def test_api_texts_agree_with_the_independent_reference(golden_client: TestClient, index: int) -> None:
    spectrum = SPECTRA[index]
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    texts = _texts(golden_client, index + 1)
    photon = {key: expected.photon[key] for key in PHOTON_BANDS} | {"ypfd": expected.mccree_ypfd}
    for key, value in photon.items():
        assert abs(float(texts[key]) - value) <= HALF_LAST_DIGIT + abs(value) * PHOTON_RTOL, (key, texts[key], value)
    energy = {
        "irradiance": expected.total_irradiance,
        "par": expected.par_w_m2,
        "extended_par": expected.extended_par_w_m2,
    }
    for key, value in energy.items():  # MATH-007 / red line 4: par is stored ÷10 and shown ×10
        assert abs(float(texts[key]) - value) <= HALF_LAST_DIGIT, (key, texts[key], value)
    assert texts["peak_wavelength_nm"] == str(expected.peak[0])
    assert texts["extended_peak_wavelength_nm"] == str(expected.extended_peak[0])


def test_flat_spectrum_closed_form(golden_client: TestClient) -> None:
    """flat: raw 1000, coefficient 3 -> 1 W·m⁻²·nm⁻¹; total 701 W·m⁻², PAR 301 W·m⁻² (hand calculation)."""
    index = next(i for i, spectrum in enumerate(SPECTRA) if spectrum.name == "flat")
    texts = _texts(golden_client, index + 1)
    assert (texts["irradiance"], texts["par"]) == ("701.000", "301.000")
    spectrum = golden_client.get(f"/api/v0/devices/p1/acquisitions/{index + 1}/spectrum").json()["spectrum"]
    assert spectrum["values"] == [1.0] * 701


@pytest.mark.parametrize("index", range(len(SPECTRA)), ids=[spectrum.name for spectrum in SPECTRA])
def test_api_uv_band_and_photon_ratio_agree_with_the_reference(golden_client: TestClient, index: int) -> None:
    """Review N-10, red line 4: the UV band is 350–399 nm (D-103) end to end; B:R is the photon ratio."""
    spectrum = SPECTRA[index]
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    irradiance = reference.irradiance(spectrum.raw_points, spectrum.coefficient)
    texts = _texts(golden_client, index + 1)
    uv = reference.photon_flux(irradiance, *reference.UV_CANDIDATES["mcu_350_399"])
    assert abs(float(texts["pfd_uv"]) - uv) <= HALF_LAST_DIGIT + abs(uv) * PHOTON_RTOL, (texts["pfd_uv"], uv)
    blue, red = expected.photon["pfd_b"], expected.photon["pfd_r"]
    if red:
        ratio = blue / red
        assert abs(float(texts["blue_red"]) - ratio) <= HALF_LAST_DIGIT + abs(ratio) * PHOTON_RTOL
