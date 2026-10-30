"""Golden spectra through the spectrum calculation API (api-contract-v0 5.6; R-3-2).

Each golden spectrum (tests/golden/spectra.json) is stored the way V1.0.3 stores an acquisition and imported as a
snapshot. The API's A/B values, every result point, the ratio threshold and the plotted ratio points must equal
the independent reference (tests/golden/reference.py: irradiance, spectrum_operation, ratio_display_threshold,
ratio_display_passes), which imports nothing from par_app.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import record, register_device, v1_database
from tests.golden import reference, spectra

pytestmark = [
    pytest.mark.unit,
    pytest.mark.spec("UI-211 UI-218 MATH-008 MATH-009 MATH-010 MATH-011 MATH-013 MATH-014 MATH-015 MATH-021"),
]
SPECTRA = {item.name: item for item in spectra.load()}
PAIRS = [("led_450_660_730", "blackbody_5778K"), ("mono_550", "flat"), ("blackbody_2856K", "mono_550")]


@pytest.fixture
def golden(client: TestClient, tmp_path: Path) -> dict[str, int]:
    """All golden spectra in one snapshot (p1); returns name -> record id."""
    rows = [
        record(f"2026-10-01T08:{index:02d}:00.000", raw_points=item.raw_points, spectral_coefficient=item.coefficient)
        for index, item in enumerate(SPECTRA.values())
    ]
    register_device(client, v1_database(tmp_path / "golden.sqlite3", rows), name="金样")
    return {name: index + 1 for index, name in enumerate(SPECTRA)}


def _irradiance(name: str) -> list[float]:
    item = SPECTRA[name]
    return reference.irradiance(item.raw_points, item.coefficient)


def _same(api: list[float | None], expected: list[float]) -> bool:
    return all(
        (value is None and math.isnan(want)) or (value is not None and value == pytest.approx(want, rel=1e-12))
        for value, want in zip(api, expected, strict=True)
    )


def _compute(client: TestClient, ids: dict[str, int], a: str, b: str, operation: str) -> dict[str, Any]:
    body = {"a": {"source": "p1", "id": ids[a]}, "b": {"source": "p1", "id": ids[b]}, "operation": operation}
    response = client.post("/api/v0/operations/compute", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


@pytest.mark.parametrize(("a", "b"), PAIRS)
@pytest.mark.parametrize("operation", ["add", "subtract", "divide"])
def test_results_equal_the_reference(
    client: TestClient, golden: dict[str, int], a: str, b: str, operation: str
) -> None:
    body = _compute(client, golden, a, b, operation)
    values_a, values_b = _irradiance(a), _irradiance(b)
    assert body["a"]["values"] == pytest.approx(values_a, rel=1e-12)  # UI-211: raw / 10^coefficient, no scaling
    assert body["b"]["values"] == pytest.approx(values_b, rel=1e-12)
    expected = reference.spectrum_operation(values_a, values_b, operation)
    result = body["result"]
    assert _same(result["values"], expected)
    if operation != "divide":
        assert result["plotted"] == result["values"] and result["threshold"] is None  # MATH-021
        return
    threshold = reference.ratio_display_threshold(values_a, values_b)
    assert result["threshold"] == pytest.approx(threshold, rel=1e-12)
    drawn = [
        value if reference.ratio_display_passes(left, right, threshold) else math.nan
        for value, left, right in zip(expected, values_a, values_b, strict=True)
    ]
    assert _same(result["plotted"], drawn)


def test_closed_form_values(client: TestClient, golden: dict[str, int]) -> None:
    """mono_550 is 100 W·m⁻²·nm⁻¹ at 550 nm and 0 elsewhere; flat is 1 everywhere (tests/golden/README.md)."""
    ratio = _compute(client, golden, "mono_550", "flat", "divide")["result"]
    assert ratio["values"][200] == 100.0 and ratio["values"][0] == 0.0  # MATH-008: 0 / 1 is a valid 0
    assert ratio["threshold"] == pytest.approx(2.0)  # 2 % × 100
    # B = 1 is below T = 2 everywhere, so not one point is drawn although 100 / 1 is a valid ratio (MATH-014)
    assert set(ratio["plotted"]) == {None} and ratio["empty_text"] == "无满足阈值的比值数据"
    inverse = _compute(client, golden, "flat", "mono_550", "divide")["result"]
    assert inverse["values"][200] == 0.01 and set(inverse["values"][:200]) == {None}  # MATH-010: 1 / 0 is NaN
    assert inverse["threshold"] == ratio["threshold"]  # MATH-013: swapping keeps the threshold
    summed = _compute(client, golden, "mono_550", "flat", "add")["result"]
    assert summed["values"][200] == 101.0 and summed["values"][0] == 1.0
