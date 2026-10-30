"""Golden spectra through the overview API (api-contract-v0 5.6; R-3-2).

Each golden spectrum (tests/golden/spectra.json) is stored the way V1.0.3 stores an acquisition and imported as the
only record of a snapshot. The overview must show exactly the texts par_app.services.metrics gives for that stored
row, the plotted values and the y range must follow from the raw points, and the KPI values must agree with the
independent reference implementation (tests/golden/reference.py) to the displayed precision.
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

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-012 UI-060 UI-175 MATH-007")]
SPECTRA = spectra.load()
PHOTON_RTOL = 1e-6  # see tests/unit/test_golden_metrics.py: product photon constant truncated by -8.65e-7
HALF_LAST_DIGIT = 0.0005  # 3-decimal text
PEAK_HEIGHT = 0.618


def _body(client: TestClient, tmp_path: Path, spectrum: spectra.Spectrum) -> tuple[dict[str, Any], dict[str, Any]]:
    stored = record(
        "2026-10-18T09:29:00.000",
        spectral_coefficient=spectrum.coefficient,
        raw_points=spectrum.raw_points,
        software_metrics_json=json.dumps(software_metrics(spectrum.raw_points, spectrum.coefficient)),
    )
    register_device(client, v1_database(tmp_path / "v1" / f"{spectrum.name}.sqlite3", [stored]))
    body: dict[str, Any] = client.get("/api/v0/devices/p1/latest").json()
    return body, body["record"]


def _number(text: str) -> float:
    return float(text.split(" ")[0])


@pytest.mark.parametrize("index", range(len(SPECTRA)), ids=[spectrum.name for spectrum in SPECTRA])
def test_texts_equal_the_services_texts_of_the_stored_row(client: TestClient, tmp_path: Path, index: int) -> None:
    body, row = _body(client, tmp_path, SPECTRA[index])
    parameters, metrics = metric_service.decode_record_metrics(row)
    assert {kpi["key"]: kpi["text"] for kpi in body["kpis"]} == dict(
        metric_service.iter_overview_kpi_texts(metrics, parameters)
    )
    entries = metric_service.overview_metric_entries(metrics, parameters)
    flat = [(item["label"], item["text"]) for column in body["chart"]["overlay"] for item in column]
    assert flat == metric_service.overview_secondary_metrics(entries)


@pytest.mark.parametrize("index", range(len(SPECTRA)), ids=[spectrum.name for spectrum in SPECTRA])
def test_values_agree_with_the_independent_reference(client: TestClient, tmp_path: Path, index: int) -> None:
    spectrum = SPECTRA[index]
    body, _row = _body(client, tmp_path, spectrum)
    expected = reference.metrics(spectrum.raw_points, spectrum.coefficient)
    kpis = {kpi["key"]: kpi["text"] for kpi in body["kpis"]}
    assert abs(_number(kpis["irradiance"]) - expected.total_irradiance) <= HALF_LAST_DIGIT
    for key, value in (("ppfd", expected.photon["ppfd"]), ("ypfd", expected.mccree_ypfd)):
        assert abs(_number(kpis[key]) - value) <= HALF_LAST_DIGIT + abs(value) * PHOTON_RTOL, (key, kpis[key], value)
    plotted = reference.irradiance(spectrum.raw_points, spectrum.coefficient)
    assert body["chart"]["spectrum"]["values"] == pytest.approx(plotted, rel=1e-12, abs=1e-15)
    peak = max(plotted)
    low = min(plotted)
    if low >= 0:  # UI-175: from 0 with the peak at about 0.618 of the height
        assert body["chart"]["y_max"] == pytest.approx(max(peak / PEAK_HEIGHT, 1e-9), rel=1e-12)
    else:
        assert body["chart"]["y_max"] == pytest.approx(peak + max((peak - low) * 0.08, 1e-9), rel=1e-12)
