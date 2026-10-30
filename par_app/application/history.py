"""History replay use cases (API-05 list, API-06/07 detail and spectrum) on the device databases the alpha acquires
itself (own_devices.py, issue #82).

Every text comes from par_app.services (metrics.record_metric_values for the 54 values, services.history for the
row, header and review texts) and par_app.database.format_beijing_time for times, so the API shows what the V1.0.3
history page shows for the same record (front end does no arithmetic, 13_ section 4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..database import format_beijing_time
from ..services import history as history_service
from ..services import metrics as metric_service
from .errors import InvalidArgument, RecordNotFound, RecordUnreadable
from .own_devices import DeviceDatabase, OwnDevices
from .readonly import Row, SnapshotHistory

PAGE_LIMIT = 500
"""Most rows per page: the V1.0.x history list shows at most the newest 500 records of the range (UI-048)."""
INVALID_SPECTRUM = object()
"""Stands for a raw_points_json that is not valid JSON; _spectrum reports it as "invalid"."""
QUERY_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")
"""Exactly the stored form YYYY-MM-DDTHH:MM:SS.mmm: times are compared as text, so "…:00" would sort before the
stored "…:00.000" and leave that record out of an end bound (review N-9)."""


@dataclass(frozen=True)
class HistoryItem:
    seq: int
    id: int
    acquired_at: str
    acquired_at_text: str
    success: bool
    result_text: str
    exposure_status: int | None
    exposure_text: str
    exposure_style: Literal["normal", "warn"]


@dataclass(frozen=True)
class HistoryPage:
    device: DeviceDatabase
    start: str
    end: str
    limit: int
    offset: int
    items: list[HistoryItem]
    limit_reached: bool
    """More records exist in the range after this page (UI-048: the list asks to narrow the range)."""


@dataclass(frozen=True)
class MetricItem:
    key: str
    label: str
    unit: str
    text: str


@dataclass(frozen=True)
class MetricGroup:
    title: str
    items: list[MetricItem]


@dataclass(frozen=True)
class Spectrum:
    wavelength_start: int
    wavelength_step: int
    spectral_coefficient: int | None
    points: list[int | float]
    values: list[float]


@dataclass(frozen=True)
class RecordDetail:
    device: DeviceDatabase
    row: Row
    title: str
    time_text: str
    status_text: str
    status_level: Literal["ok", "warn", "error"]
    exposure_text: str
    success: bool
    elapsed_text: str
    review_text: str
    groups: list[MetricGroup]
    spectrum_state: Literal["ok", "none", "invalid"]
    spectrum: Spectrum | None


def query_time(name: str, value: str) -> str:
    """Validate a query time (Beijing ISO, no zone, as stored); it is passed on unchanged, like V1.0.x does."""
    if not QUERY_TIME.match(value):
        raise InvalidArgument(f"参数 {name} 格式错误：{value}（应为 YYYY-MM-DDTHH:MM:SS.mmm，北京时间）")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidArgument(f"参数 {name} 不是有效时间：{value}", str(error)) from error
    return value


def _item(seq: int, row: Row) -> HistoryItem:
    return HistoryItem(
        seq=seq,
        id=int(row["id"]),
        acquired_at=str(row["acquired_at"]),
        acquired_at_text=format_beijing_time(row.get("acquired_at")),
        success=bool(row.get("success")),
        result_text=history_service.result_text(row),
        exposure_status=row.get("exposure_status"),
        exposure_text=history_service.exposure_text(row),
        exposure_style=history_service.exposure_style(row),
    )


def _groups(row: Row) -> list[MetricGroup]:
    """The 7 groups / 54 values; a failed record shows "—" everywhere (UI-030)."""
    texts: dict[str, str] = {}
    if row.get("success"):
        try:
            texts = metric_service.record_metric_values(row)
        except (TypeError, ValueError, AttributeError) as error:
            raise RecordUnreadable(
                f"记录 #{row['id']} 的指标数据无法解析", f"{type(error).__name__}: {error}"
            ) from error
    return [
        MetricGroup(
            title, [MetricItem(key, label, unit, texts.get(key, metric_service.EM_DASH)) for key, label, unit in fields]
        )
        for title, fields in history_service.DETAIL_GROUPS
    ]


def _spectrum(row: Row, decoded: object | None) -> tuple[Literal["ok", "none", "invalid"], Spectrum | None]:
    if decoded is None:
        return "none", None
    coefficient = row.get("spectral_coefficient")
    if not isinstance(decoded, list) or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in decoded
    ):
        return "invalid", None
    return "ok", Spectrum(
        wavelength_start=history_service.SPECTRUM_START_NM,
        wavelength_step=history_service.SPECTRUM_STEP_NM,
        spectral_coefficient=coefficient,
        points=list(decoded),
        values=history_service.spectrum_values(decoded, coefficient),
    )


class HistoryQueries:
    def __init__(self, devices: OwnDevices) -> None:
        self.devices = devices

    def page(self, key: str, start: str, end: str, limit: int = PAGE_LIMIT, offset: int = 0) -> HistoryPage:
        start, end = query_time("start", start), query_time("end", end)
        if start > end:
            raise InvalidArgument("开始时间不能晚于结束时间")
        if not 1 <= limit <= PAGE_LIMIT:
            raise InvalidArgument(f"参数 limit 应在 1–{PAGE_LIMIT} 之间：{limit}")
        if offset < 0:
            raise InvalidArgument(f"参数 offset 不能为负数：{offset}")
        device = self.devices.database_for(key)
        database = SnapshotHistory(Path(device.path))
        rows = database.acquisitions(start, end, limit + 1, offset)  # one extra row tells whether more exist
        items = [_item(offset + index + 1, row) for index, row in enumerate(rows[:limit])]
        return HistoryPage(device, start, end, limit, offset, items, limit_reached=len(rows) > limit)

    def _load(self, key: str, acquisition_id: int) -> tuple[DeviceDatabase, Row, object | None]:
        device = self.devices.database_for(key)
        database = SnapshotHistory(Path(device.path))
        row = database.acquisition(acquisition_id)
        if row is None:
            raise RecordNotFound(f"记录 #{acquisition_id} 不存在")
        try:
            decoded = database.spectrum(acquisition_id)
        except ValueError:
            decoded = INVALID_SPECTRUM
        return device, row, decoded

    def spectrum(self, key: str, acquisition_id: int) -> tuple[DeviceDatabase, Spectrum]:
        """API-07: the record's spectrum; a record without a usable spectrum is record_not_found."""
        device, row, decoded = self._load(key, acquisition_id)
        state, spectrum = _spectrum(row, decoded)
        if spectrum is None:
            raise RecordNotFound(
                f"记录 #{acquisition_id} 没有可用光谱", "无光谱" if state == "none" else "光谱数据无法解析"
            )
        return device, spectrum

    def detail(self, key: str, acquisition_id: int) -> RecordDetail:
        device, row, decoded = self._load(key, acquisition_id)
        state, spectrum = _spectrum(row, decoded)
        return RecordDetail(
            device=device,
            row=row,
            title=f"记录详情 · {device.name} · #{row['id']}",
            time_text=f"{format_beijing_time(row.get('acquired_at'))}（北京时间）",
            status_text=history_service.status_text(row),
            status_level=history_service.status_level(row),
            exposure_text=history_service.exposure_text(row),
            success=bool(row.get("success")),
            elapsed_text=history_service.elapsed_text(row),
            review_text=history_service.review_text(row),
            groups=_groups(row),
            spectrum_state=state,
            spectrum=spectrum,
        )
