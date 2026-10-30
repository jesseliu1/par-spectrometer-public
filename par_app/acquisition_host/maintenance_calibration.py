"""The calibration editor's state, kept by the service instead of V1.0.3's MainWindow widgets (17_ 3.3, 3.4;
D-216 question 5).

V1.0.3 keeps, per maintenance target: the readback it last applied (`_calibration_baseline`), the values the write
would send (`_calibration_values`, protocol units, CALIBRATION_FIELDS order), the device the readback belongs to
(`_calibration_device_key`) and what each QDoubleSpinBox shows. The values change in exactly three ways, reproduced
here with par_app.services.calibration's functions (D-216 question 7: no formula is changed):
  * a readback is applied whole (`_apply_hardware_calibration`): values = parse_readback(payload), every box shows
    value × scale rounded to its decimals;
  * a box is edited (`_calibration_field_changed`): the box rounds what was typed to its decimals (QDoubleSpinBox
    rounds half away from zero on the exact binary value, then bounds to its range) and, only when the box's value
    changed, values[name] = box value ÷ scale; untouched fields keep the raw readback (MAINT-039);
  * a preview node is dragged (`_calibration_nodes_changed`): dragged_node and node_values on the curve's nodes; the
    x and y boxes are set without changing the values.
`version` counts changes of the values, so a write confirmation names the exact draft it was issued for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from ..services import calibration as calibration_service

PERCENT_DECIMALS = 2
WAVELENGTH_DECIMALS = 1
FACTOR_DECIMALS = 4
"""Decimals of V1.0.3's boxes (MainWindow._build_calibration): x 1, percent fields 2, k_global 4."""
CAPTIONS = {"k_global": "整体倍率", "limit_min": "修正下限 (%)", "limit_max": "修正上限 (%)"}


def decimals(name: str) -> int:
    if name.startswith("x"):
        return WAVELENGTH_DECIMALS
    return (
        PERCENT_DECIMALS
        if calibration_service.field_scale(name) == calibration_service.PERCENT_SCALE
        else FACTOR_DECIMALS
    )


def box_value(name: str, value: float) -> float:
    """What V1.0.3's QDoubleSpinBox holds after setValue(value): rounded to its decimals, then bounded to its range."""
    step = Decimal(1).scaleb(-decimals(name))
    rounded = float(Decimal(value).quantize(step, rounding=ROUND_HALF_UP))
    limit = calibration_service.FIELD_LIMIT * calibration_service.field_scale(name)
    return min(max(rounded, -limit), limit)


def box_text(name: str, value: float) -> str:
    return f"{value:.{decimals(name)}f}"


@dataclass
class CalibrationDraft:
    device_key: str | None = None
    baseline: dict[str, float] | None = None
    values: dict[str, float] = field(default_factory=lambda: dict.fromkeys(calibration_service.CALIBRATION_FIELDS, 0.0))
    boxes: dict[str, float] = field(default_factory=lambda: dict.fromkeys(calibration_service.CALIBRATION_FIELDS, 0.0))
    shown: bool = False
    """A curve is shown (V1.0.3 clears the axes on reset; it draws after a readback or an edit)."""
    version: int = 0
    identity: tuple[object, ...] | None = None
    """The device identity the readback was taken from (MaintenanceController.identity; D-219, review B1): a write
    is refused unless the target still has exactly this identity."""

    @property
    def dirty(self) -> bool:
        return calibration_service.is_dirty(self.baseline, self.values)

    def reset(self) -> None:
        """MainWindow._reset_calibration."""
        self.device_key = None
        self.baseline = None
        self.values = dict.fromkeys(calibration_service.CALIBRATION_FIELDS, 0.0)
        self.boxes = dict.fromkeys(calibration_service.CALIBRATION_FIELDS, 0.0)
        self.shown = False
        self.identity = None
        self.version += 1

    def apply_readback(self, payload: Mapping[str, object]) -> bool:
        """MainWindow._apply_hardware_calibration: all or nothing (MAINT-101)."""
        parsed = calibration_service.parse_readback(payload)
        if parsed is None:
            return False
        self.values = parsed.copy()
        self.boxes = {
            name: box_value(name, value * calibration_service.field_scale(name)) for name, value in parsed.items()
        }
        self.shown = True
        self.version += 1
        return True

    def edit(self, name: str, typed: float) -> bool:
        """MainWindow._calibration_field_changed, reached only when the box's value changed (valueChanged)."""
        held = box_value(name, typed)
        if held == self.boxes[name]:
            return False
        self.boxes[name] = held
        self.values[name] = held / calibration_service.field_scale(name)
        self.shown = True
        self.version += 1
        return True

    def drag(self, index: int, x: float, y: float) -> None:
        """CalibrationCanvas._on_motion on the drawn nodes, then MainWindow._calibration_nodes_changed."""
        curve = calibration_service.correction_curve(self.values)
        nodes = curve.nodes.copy()
        nodes[index] = calibration_service.dragged_node(
            nodes, index, x, y, curve.limit_min_percent, curve.limit_max_percent
        )
        self.values.update(
            calibration_service.node_values(
                self.values, nodes, curve.global_percent, curve.limit_min_percent, curve.limit_max_percent
            )
        )
        for node, (x_name, y_name) in enumerate(calibration_service.NODE_FIELDS):
            self.boxes[x_name] = box_value(x_name, float(nodes[node, 0]))
            self.boxes[y_name] = box_value(y_name, self.values[y_name] * 100)
        self.version += 1

    def discard(self) -> None:
        """MainWindow.discard_calibration: back to the readback."""
        if self.baseline is not None:
            self.apply_readback(self.baseline)

    def accepted(self, key: str, identity: tuple[object, ...] | None) -> None:
        """A readback was applied for `key` (MainWindow._task_finished), taken from the device `identity`."""
        self.device_key = key
        self.identity = identity
        self.baseline = dict(self.values)
        self.version += 1


def curve_view(values: Mapping[str, float]) -> dict[str, Any] | None:
    """What the preview draws (CalibrationCanvas.draw_calibration), or None when the wavelengths are out of order
    (`_refresh_calibration_plots` then shows "节点波长须递增")."""
    if calibration_service.wavelengths_out_of_order(values):
        return None
    curve = calibration_service.correction_curve(values)
    return {
        "x": [float(value) for value in curve.curve_x],
        "y": [float(value) for value in curve.curve_y],
        "nodes": [[float(x), float(y)] for x, y in np.asarray(curve.nodes)],
        "global_percent": curve.global_percent,
        "limit_min_percent": curve.limit_min_percent,
        "limit_max_percent": curve.limit_max_percent,
    }


def field_rows(draft: CalibrationDraft, editable: bool) -> list[dict[str, Any]]:
    rows = []
    for name in calibration_service.CALIBRATION_FIELDS:
        scale = calibration_service.field_scale(name)
        limit = calibration_service.FIELD_LIMIT * scale
        rows.append(
            {
                "name": name,
                "caption": CAPTIONS.get(name, ""),
                "decimals": decimals(name),
                "text": box_text(name, draft.boxes[name]),
                "minimum": -limit,
                "maximum": limit,
                "enabled": editable,
            }
        )
    return rows
