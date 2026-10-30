"""Contract of GET /api/v0/reference-curves (api-contract-v0 API-08): the four reference curves and the fill colours.

The values are the V1.0.3 rules copied in par_app/services/spectrum_display.py; test_reference_curves_parity.py
compares them with the real V1.0.3 SpectrumCanvas. Here: the shape, the order and the values that can be checked
by hand.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from par_app.math_ops import WAVELENGTHS

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-168 UI-278 UI-317")]
URL = "/api/v0/reference-curves"


def test_four_curves_in_the_v1_legend_order(client: TestClient) -> None:
    body = client.get(URL).json()
    assert [(c["key"], c["label"], c["line"]) for c in body["curves"]] == [
        ("chlorophyll_a", "叶绿素 A", "dashed"),
        ("chlorophyll_b", "叶绿素 B", "dotted"),
        ("mccree", "McCree 相对作用曲线（参考）", "dashdot"),
        ("photopic", "人眼明视觉响应 V(λ，虚线)", "dashed"),
    ]
    spans = {c["key"]: (c["x"][0], c["x"][-1], len(c["x"]) == len(c["y"])) for c in body["curves"]}
    assert spans == {
        "chlorophyll_a": (400.0, 699.0, True),
        "chlorophyll_b": (400.0, 699.0, True),
        "mccree": (350.0, 725.0, True),
        "photopic": (360.0, 830.0, True),
    }


def test_right_axis_tops_at_one_and_a_half_times_the_highest_plant_curve(client: TestClient) -> None:
    body = client.get(URL).json()
    plant = [max(c["y"]) for c in body["curves"] if c["key"] != "photopic"]
    assert body["axis_max"] == pytest.approx(max(plant) * 1.5)
    assert body["axis_label"] == "归一化响应（叶绿素 / McCree）"
    assert max(next(c["y"] for c in body["curves"] if c["key"] == "mccree")) == pytest.approx(1.0)


def test_one_fill_colour_per_wavelength(client: TestClient) -> None:
    body = client.get(URL).json()
    assert body["fill_start"] == 350
    assert len(body["fill_colors"]) == len(WAVELENGTHS) == 701
    colours = dict(zip(range(350, 1051), body["fill_colors"], strict=True))
    assert colours[350] == colours[1050] == [0.55, 0.55, 0.55]  # outside 380–780 nm: grey
    assert colours[440] == [0.0, 0.0, 1.0]
    assert colours[510] == [0.0, 1.0, 0.0]
    assert colours[645] == [1.0, 0.0, 0.0]
    assert colours[700] == [1.0, 0.0, 0.0]
    assert colours[740] == pytest.approx([0.65, 0.0, 0.0])
    assert body["fill_opacity"] == 0.55


def test_the_content_is_fixed(client: TestClient) -> None:
    assert client.get(URL).json() == client.get(URL).json()
