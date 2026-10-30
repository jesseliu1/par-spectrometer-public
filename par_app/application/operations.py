"""Spectrum calculation use cases (光谱计算; API-11..14, API-24, API-25) on the alpha's own device databases, read only.

Sources are the devices of the alpha's own configuration, one per position (own_devices.py, issue #82). A record is
located by (position, record id), as V1.0.3 locates it by (database path, record id) (UI-157). The reads repeat
ParDatabase.operation_spectra, nearest_operation_spectrum and get_spectrum read only (readonly.SnapshotOperations);
the arithmetic is V1.0.3's own par_app.math_ops.combine and ratio_display_mask; the texts and axis ranges are the
copies in par_app.services.operation_display. The front end only shows them.

What the alpha decides on its own (recommended and adopted under owner's standing approval, listed in the PR):
  * D-207: exports go to the alpha's own output folder <data dir>/exports/ (no folder dialog yet); everything else
    about the export (folder and file names, the two formats, every field) is V1.0.3's export_service;
  * D-208 (the snapshot part superseded by issue #82): the "数据库" of a source is the device's database; the
    export's 来源数据库 is that database (= what V1.0.3 writes); a request carrying the id of a database that has
    since been replaced at that position (the configuration changed) is refused (snapshot_changed) instead of
    silently using records of another database.
Nothing is ever written except the export files (MATH-020).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from ..database import format_beijing_time
from ..domain.clock import Clock
from ..math_ops import combine, ratio_display_mask
from ..runtime_paths import resource_path
from ..services import export as export_service
from ..services import operation_display as display
from .errors import ExportFailed, InvalidArgument, RecordNotFound, SnapshotChanged
from .own_devices import DeviceDatabase, OwnDevices
from .paths import AlphaPaths
from .readonly import Row, SnapshotOperations

ACQUIRED_AT_MAX_LENGTH = 64
"""Longest acquired_at accepted by the nearest search; stored times are 23–32 characters."""
LOGO_FILE = "logo.png"
"""The brand image of the Excel export, the same file V1.0.3 uses (ui.BRAND_LOGO_PATH = resource_path("logo.png"))."""
PAGE_TITLE = "光谱计算"
"""UI-167: the page's name in the main navigation."""
EMPTY_SOURCES = "还没有可选的设备：请先在“设置与导出”页开启采集模式、登记设备并开始采集。"
EXPORT_CONFIRM = "导出到输出目录"
EXPORT_NOTE = "本软件不弹出目录选择框：每次导出都在下面的输出目录中新建一个结果目录，设备库不会被改动。"
SOURCE_TOOLTIP = "设备库：{path}"
DATABASE_DETAIL_MISSING = "记录 #{id} 不存在，或不是成功且完整的 701 点光谱"


@dataclass(frozen=True)
class SourceRef:
    """One side's record: device position, record id and, optionally, the database id the caller saw it in."""

    source: str
    id: int
    snapshot_id: str | None = None


@dataclass(frozen=True)
class OperationSource:
    device: DeviceDatabase
    tooltip: str


@dataclass(frozen=True)
class SourceList:
    items: list[OperationSource]
    initial_a: str | None
    initial_b: str | None


@dataclass(frozen=True)
class Candidate:
    id: int
    acquired_at: str
    acquired_at_text: str
    label: str


@dataclass(frozen=True)
class CandidateList:
    device: DeviceDatabase
    items: list[Candidate]

    @property
    def limit(self) -> int:
        return display.CANDIDATE_LIMIT

    @property
    def empty_text(self) -> str:
        return display.NO_SPECTRUM


@dataclass(frozen=True)
class NearestMatch:
    device: DeviceDatabase
    match: Candidate | None
    time_difference_seconds: float | None


@dataclass(frozen=True)
class InputSide:
    label: str
    ref: SourceRef | None
    snapshot_id: str | None
    title: str
    device_name: str | None
    record: Row | None
    """The stored row with source_device and source_database added, as V1.0.3 hands it to the export."""
    values: np.ndarray | None
    y_range: tuple[float, float] | None

    @property
    def valid(self) -> bool:
        return self.values is not None

    @property
    def legend(self) -> str:
        return display.legend(self.label)

    @property
    def acquired_at(self) -> str | None:
        return str(self.record["acquired_at"]) if self.record is not None else None

    @property
    def acquired_at_text(self) -> str | None:
        return format_beijing_time(self.record["acquired_at"]) if self.record is not None else None


@dataclass(frozen=True)
class Inputs:
    a: InputSide
    b: InputSide
    time_difference_seconds: float | None
    time_difference_text: str
    placeholder_heading: str
    placeholder_detail: str

    @property
    def valid(self) -> bool:
        return self.a.valid and self.b.valid

    @property
    def time_tooltip(self) -> str:
        return display.TIME_TOOLTIP


@dataclass(frozen=True)
class Result:
    operation: str
    values: np.ndarray
    plotted: np.ndarray
    y_range: tuple[float, float]
    reference_line: bool
    threshold: float | None

    @property
    def ratio(self) -> bool:
        return self.operation == display.DIVIDE

    # What V1.0.3 draws around the result (MainWindow._draw_operation_result), so the API only maps values.
    @property
    def operation_label(self) -> str:
        return display.operation_label(self.operation)

    @property
    def title(self) -> str:
        return display.result_title(self.operation)

    @property
    def legend(self) -> str:
        return display.RESULT_TITLE

    @property
    def y_label(self) -> str:
        return display.result_y_label(self.operation)

    @property
    def ratio_note(self) -> str | None:
        return display.RATIO_NOTE if self.ratio else None

    @property
    def empty_text(self) -> str | None:
        """无满足阈值的比值数据 when no ratio point passes the threshold, else None."""
        return display.NO_RATIO_DATA if self.ratio and not display.has_plotted_values(self.plotted) else None


@dataclass(frozen=True)
class Computation:
    inputs: Inputs
    result: Result


@dataclass(frozen=True)
class ExportOutcome:
    directory: str
    files: list[str]
    text: str


def _candidate(row: Row) -> Candidate:
    return Candidate(
        id=int(row["id"]),
        acquired_at=str(row["acquired_at"]),
        acquired_at_text=format_beijing_time(row["acquired_at"]),
        label=display.record_label(row, format_beijing_time),
    )


def _usable_points(row: Row, stored: object) -> list[float] | None:
    """The decoded 701 points of a successful record (MainWindow._operation_item), None when not usable. A spectrum
    that is not a JSON list of numbers (V1.0.3 would fail on it) is not usable either."""
    if not row.get("success") or not isinstance(stored, str):
        return None
    try:
        points: Any = json.loads(stored)
    except ValueError:
        return None
    if not isinstance(points, list) or len(points) != display.SPECTRUM_POINTS:
        return None
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in points):
        return None
    return points


def operation_key(operation: str) -> str:
    try:
        display.operation_label(operation)
    except ValueError as error:
        keys = "、".join(key for key, _ in display.OPERATIONS)
        raise InvalidArgument(f"运算法则无效：{operation}（应为 {keys}）") from error
    return operation


def export_kinds(formats: list[str]) -> list[str]:
    """The chosen formats in the V1.0.3 order (CSV, then Excel); at least one, no others (EXP-026)."""
    known = [kind for kind, _, _ in display.EXPORT_FORMATS]
    unknown = [kind for kind in formats if kind not in known]
    if unknown or not formats:
        raise InvalidArgument(
            f"导出格式无效：{'、'.join(unknown) or '未选择'}（应为 {'、'.join(known)} 中的一种或两种）"
        )
    return [kind for kind in known if kind in formats]


class OperationQueries:
    def __init__(self, devices: OwnDevices, clock: Clock, paths: AlphaPaths) -> None:
        self.devices = devices
        self.clock = clock
        self.paths = paths

    # --- sources and records -----------------------------------------------------------------------------------

    def sources(self) -> SourceList:
        """Every registered device, disabled ones too (UI-268: V1.0.3 lists every registered device)."""
        items = [
            OperationSource(slot.database, SOURCE_TOOLTIP.format(path=slot.database.path))
            for slot in self.devices.devices()
            if slot.usable and slot.database is not None
        ]
        initial_a, initial_b = display.initial_sources([item.device.key for item in items])
        return SourceList(items, initial_a, initial_b)

    def spectra(self, key: str, keep: int | None = None) -> CandidateList:
        """The newest 500 usable records; `keep` (the record still selected) is added after them when it is older
        but still usable, as V1.0.3's periodic refresh keeps it (UI-204)."""
        device = self.devices.database_for(key)
        database = SnapshotOperations(Path(device.path))
        items = [_candidate(row) for row in database.spectra(display.CANDIDATE_LIMIT)]
        if keep is not None and keep not in {item.id for item in items}:
            found = database.record(keep)
            if found is not None and _usable_points(*found) is not None:
                items.append(_candidate(found[0]))
        return CandidateList(device, items)

    def nearest(self, key: str, acquired_at: str) -> NearestMatch:
        """The usable record of `key` closest in time to `acquired_at` (UI-195..UI-203, UI-288)."""
        if not acquired_at or len(acquired_at) > ACQUIRED_AT_MAX_LENGTH:
            raise InvalidArgument(f"参数 acquired_at 无效：{acquired_at[:ACQUIRED_AT_MAX_LENGTH]}")
        device = self.devices.database_for(key)
        row = SnapshotOperations(Path(device.path)).nearest(acquired_at)
        if row is None:
            return NearestMatch(device, None, None)
        return NearestMatch(device, _candidate(row), display.time_difference({"acquired_at": acquired_at}, row))

    # --- inputs, result --------------------------------------------------------------------------------------------

    def _device(self, ref: SourceRef) -> DeviceDatabase:
        device = self.devices.database_for(ref.source)
        if ref.snapshot_id is not None and ref.snapshot_id != device.id:
            raise SnapshotChanged(
                f"位置 {ref.source} 的设备库已更换，请重新选择记录",
                f"请求中的设备库 {ref.snapshot_id}，当前设备库 {device.id}",
            )
        return device

    def _side(self, label: str, ref: SourceRef | None) -> InputSide:
        if ref is None:
            return InputSide(label, None, None, display.input_title(label), None, None, None, None)
        device = self._device(ref)
        found = SnapshotOperations(Path(device.path)).record(ref.id)
        points = _usable_points(*found) if found is not None else None
        if found is None or points is None:
            return InputSide(label, ref, device.id, display.input_title(label), device.name, None, None, None)
        row = dict(found[0], source_device=device.name, source_database=device.path)
        values = display.spectrum_values(points, row.get("spectral_coefficient"))
        title = display.input_title(label, device.name, ref.id)
        return InputSide(label, ref, device.id, title, device.name, row, values, display.spectrum_y_limits(values))

    def inputs(self, a: SourceRef | None, b: SourceRef | None) -> Inputs:
        """What the A and B charts and the time line show for a selection (MainWindow._redraw_operation_charts)."""
        label_a, label_b = display.SOURCE_LABELS
        side_a, side_b = self._side(label_a, a), self._side(label_b, b)
        valid = side_a.valid and side_b.valid
        if valid:
            assert side_a.y_range is not None and side_b.y_range is not None
            common = display.common_y_limits(side_a.y_range, side_b.y_range)
            side_a, side_b = replace(side_a, y_range=common), replace(side_b, y_range=common)
        difference = display.time_difference(side_a.record or {}, side_b.record or {})
        return Inputs(
            side_a,
            side_b,
            difference,
            display.time_difference_text(difference),
            display.WAITING_HEADING if valid else display.MISSING_HEADING,
            "" if valid else display.MISSING_DETAIL,
        )

    def compute(self, a: SourceRef, b: SourceRef, operation: str) -> Computation:
        """MainWindow.run_operation and the result part of _redraw_operation_charts."""
        operation = operation_key(operation)
        inputs = self.inputs(a, b)
        for side in (inputs.a, inputs.b):
            if not side.valid:
                raise RecordNotFound(
                    f"光谱 {side.label} 没有可用的光谱",
                    DATABASE_DETAIL_MISSING.format(id=side.ref.id if side.ref else ""),
                )
        values_a, values_b = inputs.a.values, inputs.b.values
        assert values_a is not None and values_b is not None
        out = combine(values_a, values_b, operation)
        plotted = display.plotted_result(values_a, values_b, out, operation)
        limits = display.result_y_limits(plotted, operation)
        threshold = ratio_display_mask(values_a, values_b)[0] if operation == display.DIVIDE else None
        reference = display.reference_line_visible(plotted, limits, operation)
        return Computation(inputs, Result(operation, out, plotted, limits, reference, threshold))

    # --- export ----------------------------------------------------------------------------------------------------

    def export(self, a: SourceRef, b: SourceRef, operation: str, formats: list[str]) -> ExportOutcome:
        """Recompute the result of (a, b, operation) and write one file per format into a new folder of the alpha's
        output directory (D-207), with V1.0.3's export_service (EXP-005..EXP-040)."""
        kinds = export_kinds(formats)
        computation = self.compute(a, b, operation)
        inputs, result = computation.inputs, computation.result
        assert inputs.a.values is not None and inputs.b.values is not None
        assert inputs.a.record is not None and inputs.b.record is not None
        snapshot: export_service.OperationResult = (
            inputs.a.values,
            inputs.b.values,
            result.values,
            result.operation,
            inputs.a.record,
            inputs.b.record,
        )
        try:
            self.paths.exports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ExportFailed(
                display.EXPORT_FAILED_TITLE, display.export_failed_text(str(self.paths.exports_dir), (), error)
            ) from error
        logo = resource_path(LOGO_FILE)
        outcome = export_service.export_operation_files(
            self.paths.exports_dir,
            snapshot,
            kinds,
            started_at=self.clock.now(),
            write=lambda path, kind: export_service.write_operation_file(
                path,
                kind,
                snapshot,
                exported_at=self.clock.now(),
                format_time=format_beijing_time,
                time_difference=display.time_difference,
                logo_path=logo,
            ),
        )
        directory = str(outcome.directory)
        if outcome.error is not None:
            raise ExportFailed(
                display.EXPORT_FAILED_TITLE, display.export_failed_text(directory, outcome.completed, outcome.error)
            )
        return ExportOutcome(
            directory, list(outcome.completed), display.export_done_text(len(outcome.completed), directory)
        )
