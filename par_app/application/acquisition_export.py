"""Acquisition-record export of the settings page (采集记录导出; API-22, API-23) on the alpha's own
device databases (own_devices.py, issue #82).

The V1.0.3 rules, step by step (MainWindow.update_export_range, _current_export_range, refresh_export_count,
export_acquisitions):
  * range: a preset (最近 1/2/4/8/24 小时) ends at the service clock's Beijing time and is recomputed at every
    count and when the export is confirmed (EXP-051, #12); a custom range is used as given (EXP-050). Both are
    compared as [start second .000, end second .999] with the stored text (#11);
  * count: ParDatabase.acquisition_export_count; files = records × chosen formats (EXP-011);
  * export: the rows of ParDatabase.acquisitions_for_export (failed records and records without a spectrum
    included, D-127), each written by par_app.services.export once per chosen format into
    <folder>/<device>/<CSV|Excel>/<YYYY-MM-DD>/PAR_<time>_#<id>.<ext> (EXP-008, EXP-012, EXP-013), stopping at the
    first record that fails (V1.0.3 shows that record's error and how many files were written).
Every field of every file is V1.0.3's (services/export, with PAR ×10 of D-166 and the UV 350–399 labels of D-103).

What the alpha decides on its own (D-210, recommended and adopted under owner's standing approval, listed in the
PR; its snapshot part superseded by issue #82): the parent folder is the alpha's own output folder
<data dir>/exports/ (no folder dialog yet, like D-207); the device folder is named after the registered device
name (as V1.0.3); the export runs within one request (no progress bar and no cancel); the page confirms with the
range the count returned, and the export uses exactly that range and the database it was counted on
(snapshot_changed when the configuration put another database at that position), so what was confirmed is what is
written (EXP-052). The device database is only read.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..database import format_beijing_time
from ..domain.clock import Clock
from ..runtime_paths import resource_path
from ..services import export as export_service
from ..services import settings_display as texts
from .errors import Busy, DeviceNotFound, ExportFailed, InvalidArgument, RecordNotFound, SnapshotChanged
from .own_devices import DeviceDatabase, OwnDevices
from .paths import AlphaPaths
from .readonly import SnapshotExport

RANGE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
"""A start or end as the editors hold it: whole seconds, YYYY-MM-DDTHH:MM:SS (Beijing time)."""
LOGO_FILE = "logo.png"
"""The brand image of the Excel export, the same file V1.0.3 uses (ui.BRAND_LOGO_PATH)."""
BUSY_TEXT = "正在导出采集记录，请等待本次导出完成"
RECORDS_CHANGED = "确认之后所选范围内的记录有变化（采集仍在进行），请重新确认导出范围"


@dataclass(frozen=True)
class ExportRange:
    mode: str
    start: datetime
    end: datetime

    @property
    def editable(self) -> bool:
        """EXP-071: preset times are shown disabled."""
        return self.mode == texts.CUSTOM_RANGE

    @property
    def query(self) -> tuple[str, str]:
        return texts.query_bounds(self.start, self.end)

    @property
    def start_value(self) -> str:
        """The start second as the custom-range query takes it back (YYYY-MM-DDTHH:MM:SS)."""
        return f"{self.start:{texts.QUERY_START_FORMAT}}"

    @property
    def end_value(self) -> str:
        return f"{self.end:{texts.QUERY_START_FORMAT}}"

    @property
    def start_text(self) -> str:
        """How the start editor shows the time (yyyy-MM-dd HH:mm:ss)."""
        return f"{self.start:{texts.RANGE_TEXT_FORMAT}}"

    @property
    def end_text(self) -> str:
        return f"{self.end:{texts.RANGE_TEXT_FORMAT}}"


@dataclass(frozen=True)
class Confirmation:
    title: str
    text: str
    records: int
    files: int


@dataclass(frozen=True)
class ExportPreview:
    device: DeviceDatabase
    range: ExportRange
    kinds: list[str]
    count: int
    text: str
    confirm: Confirmation | None
    notice: str | None
    """What V1.0.3 says instead of the confirmation when 导出采集记录 is clicked now: the end is before the start, or
    the range holds no record; None when a confirmation follows (or no format is chosen: V1.0.3 then does nothing)."""

    @property
    def files(self) -> int:
        return self.count * len(self.kinds)

    @property
    def can_export(self) -> bool:
        """EXP-049: no records or no format disables 导出采集记录."""
        return self.count > 0 and bool(self.kinds)


@dataclass(frozen=True)
class ExportDone:
    directory: str
    device_folder: str
    records: int
    files: int
    text: str


def export_kinds(formats: list[str], *, allow_none: bool) -> list[str]:
    """The chosen formats in the V1.0.3 order (CSV, then Excel). The count accepts none (V1.0.3 shows "0 个文件"
    and disables the button); the export needs at least one."""
    known = [kind for kind, _, _ in texts.EXPORT_FORMATS]
    unknown = [kind for kind in formats if kind not in known]
    if unknown or (not formats and not allow_none):
        raise InvalidArgument(
            f"导出格式无效：{'、'.join(unknown) or '未选择'}（应为 {'、'.join(known)} 中的一种或两种）"
        )
    return [kind for kind in known if kind in formats]


def parse_time(name: str, value: str | None) -> datetime:
    if value is None or not RANGE_TIME.match(value):
        raise InvalidArgument(f"参数 {name} 无效：{(value or '')[:32]}（应为 YYYY-MM-DDTHH:MM:SS，北京时间）")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidArgument(f"参数 {name} 无效：{value}（日期不存在）") from error


class AcquisitionExports:
    def __init__(self, devices: OwnDevices, clock: Clock, paths: AlphaPaths) -> None:
        self.devices = devices
        self.clock = clock
        self.paths = paths
        self.lock = threading.Lock()
        """V1.0.3's _exporting: one export at a time; a second one is refused as busy, never run twice."""

    def resolve(self, mode: str, start: str | None = None, end: str | None = None) -> ExportRange:
        """_current_export_range: a preset from the clock now, a custom range as given."""
        hours = texts.preset_hours(mode)
        if hours is not None:
            now = self.clock.now().replace(tzinfo=None)
            first, last = texts.preset_range(hours, now)
            return ExportRange(mode, first, last)
        if mode != texts.CUSTOM_RANGE:
            keys = "、".join(key for key, _ in texts.range_options())
            raise InvalidArgument(f"导出范围无效：{mode[:16]}（应为 {keys}）")
        return ExportRange(mode, parse_time("start", start), parse_time("end", end))

    def preview(self, key: str, export_range: ExportRange, formats: list[str]) -> ExportPreview:
        """refresh_export_count, plus the confirmation export_acquisitions would show for this range now."""
        kinds = export_kinds(formats, allow_none=True)
        device = self.devices.database_for(key)
        database = SnapshotExport(Path(device.path))
        start, end = export_range.query
        count = database.count(start, end)
        confirm = None
        notice = None
        if kinds and export_range.end < export_range.start:
            notice = texts.END_BEFORE_START_TEXT
        elif kinds:
            records = database.row_count(start, end)
            notice = texts.NO_RECORDS_TEXT if records == 0 else None
        if kinds and notice is None:
            confirm = Confirmation(
                texts.CONFIRM_TITLE,
                texts.confirm_text(
                    device.name,
                    export_range.start,
                    export_range.end,
                    records,
                    kinds,
                    export_service.device_folder(device.name),
                    str(self.paths.exports_dir),
                ),
                records,
                records * len(kinds),
            )
        return ExportPreview(device, export_range, kinds, count, texts.count_text(count, len(kinds)), confirm, notice)

    def export(
        self,
        key: str,
        start: str,
        end: str,
        formats: list[str],
        snapshot_id: str | None = None,
        records: int | None = None,
    ) -> ExportDone:
        """export_acquisitions after 是: every record of [start, end] in each chosen format."""
        kinds = export_kinds(formats, allow_none=False)
        export_range = ExportRange(texts.CUSTOM_RANGE, parse_time("start", start), parse_time("end", end))
        if export_range.end < export_range.start:
            raise InvalidArgument(texts.END_BEFORE_START_TEXT)
        if not self.lock.acquire(blocking=False):
            raise Busy(BUSY_TEXT)
        try:
            return self._export(key, export_range, kinds, snapshot_id, records)
        finally:
            self.lock.release()

    def _device(self, key: str, snapshot_id: str | None) -> DeviceDatabase:
        try:
            device = self.devices.database_for(key)
        except DeviceNotFound as error:
            raise DeviceNotFound(texts.NO_SOURCE_TEXT, error.message) from error
        if snapshot_id is not None and snapshot_id != device.id:
            raise SnapshotChanged(
                f"位置 {key} 的设备库已更换，请重新确认导出范围",
                f"确认时的设备库 {snapshot_id}，当前设备库 {device.id}",
            )
        return device

    def _export(
        self, key: str, export_range: ExportRange, kinds: list[str], snapshot_id: str | None, records: int | None
    ) -> ExportDone:
        device = self._device(key, snapshot_id)
        rows = SnapshotExport(Path(device.path)).rows(*export_range.query)
        if not rows:
            raise RecordNotFound(texts.NO_RECORDS_TEXT)
        if records is not None and len(rows) != records:
            # EXP-052: what was confirmed is what is written. The device database grows while acquiring, so a record
            # saved into the range after the confirmation is refused rather than written unconfirmed (PR #95 review).
            raise SnapshotChanged(RECORDS_CHANGED, f"确认时 {records} 条，现在 {len(rows)} 条")
        folder = self.paths.exports_dir
        device_folder = export_service.device_folder(device.name)
        logo = resource_path(LOGO_FILE)
        success = 0
        for row in rows:
            try:
                acquired = export_service.folder_time(row, export_range.start)
                for kind in kinds:
                    day_folder = export_service.acquisition_day_folder(folder, device_folder, kind, acquired)
                    day_folder.mkdir(parents=True, exist_ok=True)
                    path = day_folder / export_service.acquisition_file_name(row, kind, acquired)
                    export_service.write_acquisition_file(
                        path,
                        row,
                        kind,
                        exported_at=self.clock.now(),
                        format_time=format_beijing_time,
                        logo_path=logo,
                    )
                    success += 1
            except (OSError, ValueError, AttributeError) as error:
                # AttributeError: metrics or parameter JSON that is valid but not an object (D-168 A keeps V1.0.3's
                # file content; D-210 question 6: the alpha reports that record like any failed write instead of
                # V1.0.3's uncaught exception)
                detail = "\n\n".join(
                    (
                        texts.RECORD_FAILED_TEXT.format(id=row.get("id"), error=error),
                        texts.PARTIAL_TEXT.format(success=success, failed=1),
                        f"保存目录：{folder}",
                    )
                )
                raise ExportFailed(texts.FAILED_TITLE, detail) from error
        return ExportDone(
            str(folder), device_folder, len(rows), success, texts.DONE_TEXT.format(count=success, folder=folder)
        )
