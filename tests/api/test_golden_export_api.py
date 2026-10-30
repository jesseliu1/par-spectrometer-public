"""Golden spectra through the acquisition export API (api-contract-v0 5.6; R-3-2).

Each golden spectrum (tests/golden/spectra.json) is stored the way V1.0.3 stores an acquisition (metrics computed by
the product at acquisition time) and imported as a snapshot, then exported as CSV through API-23. The exported
fields must equal the independent reference (tests/golden/reference.py, which imports nothing from par_app): PAR
and extended PAR in W/m² as the UI shows them (D-166: stored ÷10, exported ×10), the photon bands with UV at
350–399 nm (D-103), McCree YPFD, total irradiance, the peaks, and the 701 raw points unchanged.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.math_ops import software_metrics
from tests.api.conftest import record, register_device, v1_database
from tests.golden import reference, spectra

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("EXP-002 EXP-003 EXP-006 MATH-007 MATH-022"),
]
SPECTRA = spectra.load()
REL_ENERGY = 1e-12
"""Energies and peaks: no physical constant, only summation order (tests/golden/README.md 容差)."""
REL_PHOTON = 1e-6
"""Photon metrics: the product's truncated constant 8.35934e-3 (tests/golden/README.md 容差)."""
FIELDS = {
    "ppfd": "PPFD(400–700)",
    "pfd": "PFD(350–780)",
    "pfd_b": "蓝光PFD(400–499)",
    "pfd_g": "绿光PFD(500–599)",
    "pfd_r": "红光PFD(600–699)",
    "pfd_fr": "远红PFD(700–780)",
    "pfd_far_red": "远红光PFD(700–750)",
    "pfd_nir": "近红外PFD(751–1050)",
    "extended_ppfd": "扩展PPFD(400–750)",
    "extended_pfd": "扩展PFD(350–1050)",
    "extended_pfd_fr": "扩展远红PFD(700–1050)",
}


@pytest.fixture
def exported(client: TestClient, context: ServiceContext, tmp_path: Path) -> dict[str, list[list[str]]]:
    rows = [
        record(
            f"2026-10-01T08:{index:02d}:00.000",
            raw_points=item.raw_points,
            spectral_coefficient=item.coefficient,
            software_metrics_json=json.dumps(software_metrics(item.raw_points, item.coefficient)),
        )
        for index, item in enumerate(SPECTRA)
    ]
    register_device(client, v1_database(tmp_path / "golden.sqlite3", rows), name="金样")
    response = client.post(
        "/api/v0/devices/p1/export",
        json={"start": "2026-10-01T08:00:00", "end": "2026-10-01T08:59:59", "formats": ["csv"]},
    )
    assert response.status_code == 201, response.text
    folder = context.paths.exports_dir / "金样" / "CSV" / "2026-10-01"
    return {
        item.name: list(
            csv.reader(
                io.StringIO((folder / f"PAR_20261001_08{index:02d}00_#{index + 1}.csv").read_text(encoding="utf-8-sig"))
            )
        )
        for index, item in enumerate(SPECTRA)
    }


@pytest.mark.parametrize("item", SPECTRA, ids=[item.name for item in SPECTRA])
def test_exported_fields_equal_the_reference(exported: dict[str, list[list[str]]], item: spectra.Spectrum) -> None:
    rows = exported[item.name]
    fields = {row[0]: row[2] for row in rows[4:73]}
    want = reference.metrics(item.raw_points, item.coefficient)
    assert float(fields["PAR波段辐照度(W/m²)"]) == pytest.approx(
        want.par_w_m2, rel=REL_ENERGY
    )  # D-166: as the UI shows
    assert float(fields["扩展PAR辐照度(400–750)"]) == pytest.approx(want.extended_par_w_m2, rel=REL_ENERGY)
    assert float(fields["350–1050 nm 总辐照度(W/m²)"]) == pytest.approx(want.total_irradiance, rel=REL_ENERGY)
    assert float(fields["McCree YPFD"]) == pytest.approx(want.mccree_ypfd, rel=REL_PHOTON)
    for key, label in FIELDS.items():
        assert float(fields[label]) == pytest.approx(want.photon[key], rel=REL_PHOTON), label
    spectrum = reference.irradiance(item.raw_points, item.coefficient)
    low, high = reference.UV_CANDIDATES["mcu_350_399"]
    assert float(fields["紫外PFD(350–399)"]) == pytest.approx(
        reference.photon_flux(spectrum, low, high), rel=REL_PHOTON
    )
    assert int(fields["PAR峰值波长(nm)"]) == want.peak[0]
    assert int(fields["全谱峰值波长(nm)"]) == want.extended_peak[0]
    assert rows[74] == ["波长（nm）", "原始光谱值"]
    points = rows[75:]
    assert [float(row[0]) for row in points] == [float(nm) for nm in reference.wavelengths()]
    assert [float(row[1]) for row in points] == [float(value) for value in item.raw_points]
