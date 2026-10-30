"""Export content: acquisition-record files and spectrum-operation result files (field assembly and file writing).

Moved unchanged out of par_app/ui.py (R-8-1 stage one "logic extraction"; MainWindow keeps thin wrappers with
unchanged signatures, and every dialog, confirmation, progress bar and message box stays in the UI):
  EXPORT_DIRECT_FIELDS / EXPORT_METRICS_FIELDS / EXPORT_MCU_FIELDS / EXPORT_ALL_FIELDS -> same names
  MainWindow._export_metadata_rows     -> metadata_rows
  MainWindow._export_spectrum_rows     -> spectrum_rows
  MainWindow._write_export_file        -> acquisition_header_rows, write_acquisition_file
  MainWindow._brand_excel_image        -> brand_image
  MainWindow.export_acquisitions       -> format_label, device_folder, folder_time, acquisition_day_folder,
                                          acquisition_file_name (naming only; the loop stays in the UI)
  MainWindow._write_operation_file     -> operation_table (OperationTable), write_operation_file
  MainWindow.export_operation_results  -> OPERATION_TOKENS, operation_file_stem, export_operation_files
                                          (returns OperationExport instead of showing a message box)
  MainWindow.export_operation          -> OPERATION_TOKENS, operation_file_stem, file_extension
Specs: see the 代码锚点 of the EXP entries listed in docs/spec/ui-migration-tracker.md. Rules and states are V1.0.2
status quo; known quirks are reported for separate fix PRs, not changed here.
Fixes merged before the move are kept here (release/v1.0.3 integration): PAR / extended PAR exported in the UI scale
(D-166, PR #15), UV PFD labels 350–399 nm (D-103, PR #31), length-checked zip for spectra (EXP-015, PR #28, refs #2).

No clock is read here (R-1-6): the caller passes the export time. No database is read: the caller passes the rows.
Beijing-time text comes from the formatter the caller passes (par_app.database.format_beijing_time), because the
services contract in pyproject.toml keeps par_app.database (sqlite3) out of this package.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, PatternFill
from openpyxl.styles import Font as ExcelFont

from ..math_ops import WAVELENGTHS, display_metrics, ratio_display_mask
from ..models import safe_database_filename

# Rows come from ParDatabase.acquisitions_for_export / the operation page; values are passed on exactly as stored
# (numbers, None, NaN, legacy shapes). Any is deliberate (R-1-3): export writes stored values untouched.
Record = Mapping[str, Any]
TableRow = list[Any]
TimeFormatter = Callable[[Any], str]
"""Formats a stored or current time as Beijing-time text (the UI passes par_app.database.format_beijing_time)."""
TimeDifference = Callable[[Any, Any], Any]
"""Seconds from spectrum A to spectrum B, or None (the UI passes MainWindow._operation_time_difference)."""
OperationResult = tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], str, Record, Record]
"""MainWindow.current_result: (A, B, result, operation, A record, B record)."""
FieldSpec = tuple[str, str, str, str]

# ---------------------------------------------------------------------------
# 采集记录导出字段定义
# 每条采集记录导出为一个独立文件：键值对元数据区 + 光谱数据区。
# 每条目：(存储键, 中文名, 英文名, 来源)
#   来源 direct = acquisitions 直接字段
#         metrics = software_metrics_json
#         mcu     = mcu_params_json
# ---------------------------------------------------------------------------
EXPORT_DIRECT_FIELDS: tuple[FieldSpec, ...] = (
    ("id", "记录ID", "Record ID", "direct"),
    ("acquired_at", "采集时间（北京时间）", "Acquired At (Beijing Time)", "direct"),
    ("mcu_time_ms", "MCU时间戳(ms)", "MCU Time (ms)", "direct"),
    ("success", "采集成功", "Success", "direct"),
    ("initialized", "光谱仪已初始化", "Initialized", "direct"),
    ("need_power_cycle", "需重新上电", "Need Power Cycle", "direct"),
    ("raw_data_valid", "原始数据有效", "Raw Data Valid", "direct"),
    ("calculate_data_valid", "计算数据有效", "Calculate Data Valid", "direct"),
    ("stop_status", "停止状态", "Stop Status", "direct"),
    ("spectral_coefficient", "光谱系数", "Spectral Coefficient", "direct"),
    ("exposure_status", "曝光状态", "Exposure Status", "direct"),
    ("exposure_time_us", "曝光时间(µs)", "Exposure Time (µs)", "direct"),
    ("error_stage", "错误阶段", "Error Stage", "direct"),
    ("error_detail", "错误详情", "Error Detail", "direct"),
    ("elapsed_ms", "耗时(ms)", "Elapsed (ms)", "direct"),
)

EXPORT_METRICS_FIELDS: tuple[FieldSpec, ...] = (
    ("peak_wavelength_nm", "PAR峰值波长(nm)", "PAR Peak Wavelength (nm)", "metrics"),
    ("peak_value", "PAR峰值功率", "PAR Peak Power", "metrics"),
    ("integrated_irradiance", "350–1050 nm 总辐照度(W/m²)", "Integrated Irradiance 350–1050 nm (W/m²)", "metrics"),
    ("software_ppfd", "软件PPFD(µmol·m⁻²·s⁻¹)", "Software PPFD", "metrics"),
    ("par", "PAR波段辐照度(W/m²)", "PAR Irradiance (W/m²)", "metrics"),
    ("pfd", "PFD(350–780)", "PFD", "metrics"),
    ("ppfd", "PPFD(400–700)", "PPFD", "metrics"),
    ("pfd_uv", "紫外PFD(350–399)", "UV PFD", "metrics"),
    ("pfd_b", "蓝光PFD(400–499)", "Blue PFD", "metrics"),
    ("pfd_g", "绿光PFD(500–599)", "Green PFD", "metrics"),
    ("pfd_r", "红光PFD(600–699)", "Red PFD", "metrics"),
    ("pfd_fr", "远红PFD(700–780)", "Far-red PFD", "metrics"),
    ("pfd_far_red", "远红光PFD(700–750)", "Far-red PFD (700–750)", "metrics"),
    ("pfd_nir", "近红外PFD(751–1050)", "NIR PFD", "metrics"),
    ("mccree_ypfd", "McCree YPFD", "McCree YPFD", "metrics"),
    ("chlorophyll_a_ypfd", "叶绿素A加权YPFD", "Chlorophyll A YPFD", "metrics"),
    ("chlorophyll_b_ypfd", "叶绿素B加权YPFD", "Chlorophyll B YPFD", "metrics"),
    ("extended_peak_wavelength_nm", "全谱峰值波长(nm)", "Extended Peak Wavelength (nm)", "metrics"),
    ("extended_peak_value", "全谱峰值功率", "Extended Peak Power", "metrics"),
    ("extended_par", "扩展PAR辐照度(400–750)", "Extended PAR Irradiance", "metrics"),
    ("extended_pfd", "扩展PFD(350–1050)", "Extended PFD", "metrics"),
    ("extended_ppfd", "扩展PPFD(400–750)", "Extended PPFD", "metrics"),
    ("extended_pfd_uv", "扩展紫外PFD(350–399)", "Extended UV PFD", "metrics"),
    ("extended_pfd_b", "扩展蓝光PFD(400–499)", "Extended Blue PFD", "metrics"),
    ("extended_pfd_g", "扩展绿光PFD(500–599)", "Extended Green PFD", "metrics"),
    ("extended_pfd_r", "扩展红光PFD(600–699)", "Extended Red PFD", "metrics"),
    ("extended_pfd_fr", "扩展远红PFD(700–1050)", "Extended Far-red PFD", "metrics"),
)

EXPORT_MCU_FIELDS: tuple[FieldSpec, ...] = (
    ("cct", "相关色温(K)", "CCT (K)", "mcu"),
    ("lux", "照度(lx)", "Illuminance (lx)", "mcu"),
    ("ee", "辐射照度", "Irradiance (ee)", "mcu"),
    ("r1", "特殊显色指数R1", "Special CRI R1", "mcu"),
    ("r2", "特殊显色指数R2", "Special CRI R2", "mcu"),
    ("r3", "特殊显色指数R3", "Special CRI R3", "mcu"),
    ("r4", "特殊显色指数R4", "Special CRI R4", "mcu"),
    ("r5", "特殊显色指数R5", "Special CRI R5", "mcu"),
    ("r6", "特殊显色指数R6", "Special CRI R6", "mcu"),
    ("r7", "特殊显色指数R7", "Special CRI R7", "mcu"),
    ("r8", "特殊显色指数R8", "Special CRI R8", "mcu"),
    ("r9", "特殊显色指数R9", "Special CRI R9", "mcu"),
    ("r10", "特殊显色指数R10", "Special CRI R10", "mcu"),
    ("r11", "特殊显色指数R11", "Special CRI R11", "mcu"),
    ("r12", "特殊显色指数R12", "Special CRI R12", "mcu"),
    ("r13", "特殊显色指数R13", "Special CRI R13", "mcu"),
    ("r14", "特殊显色指数R14", "Special CRI R14", "mcu"),
    ("r15", "特殊显色指数R15", "Special CRI R15", "mcu"),
    ("ra", "一般显色指数Ra", "General CRI Ra", "mcu"),
    ("X", "三刺激值X", "Tristimulus X", "mcu"),
    ("Y", "三刺激值Y", "Tristimulus Y", "mcu"),
    ("Z", "三刺激值Z", "Tristimulus Z", "mcu"),
    ("duv", "色偏差Duv", "Duv", "mcu"),
    ("u", "CIE u", "CIE u", "mcu"),
    ("v", "CIE v", "CIE v", "mcu"),
    ("x", "CIE x", "CIE x", "mcu"),
    ("y", "CIE y", "CIE y", "mcu"),
)

EXPORT_ALL_FIELDS = EXPORT_DIRECT_FIELDS + EXPORT_METRICS_FIELDS + EXPORT_MCU_FIELDS

NO_SPECTRUM_ROW = ["光谱数据区", "本记录无原始光谱数据（采集失败或未保存光谱）。"]
SPECTRUM_HEADER = ["波长（nm）", "原始光谱值"]
OPERATION_TOKENS = {"add": "add", "subtract": "sub", "divide": "ratio"}
OPERATION_NAMES = {"add": "加法（A + B）", "subtract": "减法（A − B）", "divide": "除法 / 比值（A / B）"}


# --- acquisition records -------------------------------------------------------------------------------------------


def metadata_rows(row: Record) -> list[TableRow]:
    """单条采集记录的键值对元数据区：中文名 | 英文名 | 值（EXPORT_ALL_FIELDS 69 项）。"""
    try:
        metrics = json.loads(row.get("software_metrics_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metrics = {}
    if isinstance(metrics, dict):  # D-166（PR #15）：par、extended_par 按界面口径 ×10 导出；非对象 JSON 仍按 D-168 现状
        metrics = display_metrics(metrics)
    try:
        mcu = json.loads(row.get("mcu_params_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        mcu = {}
    rows: list[TableRow] = []
    for key, zh, en, source in EXPORT_ALL_FIELDS:
        if source == "direct":
            value = row.get(key)
        elif source == "metrics":
            value = metrics.get(key)
        else:
            value = mcu.get(key)
        rows.append([zh, en, "" if value is None else value])
    return rows


def spectrum_rows(row: Record) -> list[list[float]] | None:
    """单条采集记录的光谱数据区：波长(nm) | 原始光谱值（701 行）；无光谱时返回 None。"""
    raw = row.get("raw_points_json")
    if not raw:
        return None
    try:
        points = json.loads(raw)
        points = [float(value) for value in points]
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if len(points) != len(WAVELENGTHS):
        return None
    return [[float(wavelength), value] for wavelength, value in zip(WAVELENGTHS, points, strict=True)]


def acquisition_header_rows(row: Record, *, exported_at: datetime, format_time: TimeFormatter) -> list[TableRow]:
    """文件信息头 4 行：文件来源、导出时间、采集记录 ID、采集时间（北京时间）。"""
    return [
        ["文件来源", "PAR 光谱仪专用软件 - 采集记录导出"],
        ["导出时间（北京时间）", format_time(exported_at)],
        ["采集记录 ID", row.get("id")],
        ["采集时间（北京时间）", format_time(row.get("acquired_at"))],
    ]


def brand_image(logo_path: Path | None, anchor: str) -> Any:  # noqa: ANN401 - openpyxl ships no type information
    """The brand logo as an openpyxl image anchored at `anchor`, or None when the logo file is missing."""
    if logo_path is None or not logo_path.exists():
        return None
    image = ExcelImage(str(logo_path))
    image.width, image.height = 112, 54
    image.anchor = anchor
    return image


def write_acquisition_file(
    path: str | Path,
    row: Record,
    kind: str,
    *,
    exported_at: datetime,
    format_time: TimeFormatter,
    logo_path: Path | None = None,
) -> None:
    """写单条采集记录到独立文件：文件信息头 + 键值对元数据区 + 光谱数据区（kind 为 "csv"，其余按 Excel 写）。"""
    metadata = metadata_rows(row)
    spectrum = spectrum_rows(row)
    header = acquisition_header_rows(row, exported_at=exported_at, format_time=format_time)
    if kind == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerows(header)
            writer.writerows(metadata)
            writer.writerow([])
            if spectrum is None:
                writer.writerow(NO_SPECTRUM_ROW)
            else:
                writer.writerow(SPECTRUM_HEADER)
                writer.writerows(spectrum)
        return
    wb = Workbook()
    ws = wb.active
    ws.title = f"采集 #{row.get('id')}"
    logo = brand_image(logo_path, "H1")
    if logo:
        ws.add_image(logo)
    for line in header:
        ws.append(line)
    for line in metadata:
        ws.append(line)
    ws.append([])
    if spectrum is None:
        ws.append(NO_SPECTRUM_ROW)
    else:
        ws.append(SPECTRUM_HEADER)
        for wavelength, value in spectrum:
            ws.append([wavelength, value])
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 64
    for cells in ws.iter_rows():
        for cell in cells:
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    wb.save(path)


def format_label(kind: str) -> str:
    """Format name in the confirmation text and the format folder: "CSV" for csv, otherwise "Excel"."""
    return "CSV" if kind == "csv" else "Excel"


def device_folder(device_name: str) -> str:
    """Top-level export folder for one device: its name made safe for the file system."""
    return safe_database_filename(device_name, fallback="spectrometer")


def folder_time(row: Record, fallback: datetime) -> datetime:
    """Naive acquisition time used for the date folder and file name; unparsable times use `fallback`."""
    try:
        return datetime.fromisoformat(str(row.get("acquired_at"))).replace(tzinfo=None)
    except (TypeError, ValueError):
        return fallback


def acquisition_day_folder(folder: str | Path, device: str, kind: str, acquired: datetime) -> Path:
    """<导出文件夹>/<设备>/<CSV|Excel>/<YYYY-MM-DD>（EXP-008/EXP-012/EXP-072）。"""
    return Path(folder) / device / format_label(kind) / f"{acquired:%Y-%m-%d}"


def acquisition_file_name(row: Record, kind: str, acquired: datetime) -> str:
    """PAR_<YYYYmmdd_HHMMSS>_#<记录ID>.<kind>（每条记录每种格式一个文件，EXP-013）。"""
    return f"PAR_{acquired:%Y%m%d_%H%M%S}_#{row.get('id')}.{kind}"


# --- spectrum-operation results ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationTable:
    """Content of one operation export: summary + key/value metadata, data columns and the 701 data rows.

    `metadata[0]` is the one-cell summary line; the rest are two-column key/value rows (the Excel 计算说明 sheet).
    `rows` hold the raw values; writers turn non-finite values into the text "NaN".
    """

    metadata: list[TableRow]
    columns: list[str]
    rows: list[tuple[Any, ...]]


def operation_table(
    result: OperationResult, *, exported_at: datetime, format_time: TimeFormatter, time_difference: TimeDifference
) -> OperationTable:
    """Metadata, columns and rows of a spectrum-operation export (EXP-005/010/015..019/037/060/061)."""
    a, b, out, op, a_record, b_record = result
    rows: Iterable[tuple[Any, ...]] = list(zip(WAVELENGTHS, a, b, out, strict=True))  # EXP-015：长度不符在写文件前报错
    operation_name = OPERATION_NAMES[op]
    divide_rule = (
        "除法规则：A、B 有限且 B 非零时计算 A / B；B = 0（包括双零）、非有限输入或计算溢出为 NaN（无效）。"
        "A = 0 且 B 非零时结果为有效的 0；不截断有限高比值。"
        if op == "divide"
        else "不适用。"
    )
    metadata: list[TableRow] = [
        [
            f"光谱 A：ID {a_record['id']}，采集时间 {format_time(a_record.get('acquired_at'))}；"
            f"光谱 B：ID {b_record['id']}，采集时间 {format_time(b_record.get('acquired_at'))}；"
            f"运算法则：{operation_name}"
        ],
        ["文件来源", "PAR 光谱仪专用软件 - 光谱运算"],
        ["导出时间（北京时间）", format_time(exported_at)],
        ["光谱 A 来源设备", a_record.get("source_device", "")],
        ["光谱 A 来源数据库", a_record.get("source_database", "")],
        ["光谱 B 来源设备", b_record.get("source_device", "")],
        ["光谱 B 来源数据库", b_record.get("source_database", "")],
        ["光谱 A 记录 ID", a_record["id"]],
        ["光谱 A 采集时间（北京时间）", format_time(a_record.get("acquired_at"))],
        ["光谱 B 记录 ID", b_record["id"]],
        ["光谱 B 采集时间（北京时间）", format_time(b_record.get("acquired_at"))],
        ["采集时间差 B - A（秒）", time_difference(a_record, b_record)],
        ["运算法则", operation_name],
        ["零值处理规则", divide_rule],
    ]
    columns = [
        "波长（nm）",
        "光谱 A（mW/nm）",
        "光谱 B（mW/nm）",
        "计算结果（比值 A/B）" if op == "divide" else "计算结果（mW/nm）",
    ]
    if op == "divide":
        threshold, mask = ratio_display_mask(a, b)
        metadata.extend(
            [
                ["比值显示共同阈值（mW/nm）", threshold],
                ["比值显示筛选规则", "T=2%×max(A全波段峰值,B全波段峰值)；A>=T、B>=T且B非零；峰值波段350–1050 nm"],
                ["低信号标记说明", "1=未通过显示筛选，0=通过；仅影响绘图，完整计算值不变；不是仪器检测下限"],
            ]
        )
        columns.append("低信号标记（1=未通过显示筛选）")
        columns.append("结果有效标记（1=有效，0=无效）")
        rows = list(zip(WAVELENGTHS, a, b, out, (~mask).astype(int), np.isfinite(out).astype(int), strict=True))
        metadata.append(["无效值说明", "NaN=无效计算结果，不等于0；低信号标记仅控制绘图，有效的低信号计算值仍保留"])
    return OperationTable(metadata, columns, list(rows))


def _cell(value: Any) -> float | str:  # noqa: ANN401 - numpy scalars of any dtype, as the export always wrote them
    return float(value) if np.isfinite(value) else "NaN"


def write_operation_file(
    path: Path,
    kind: str,
    result: OperationResult,
    *,
    exported_at: datetime,
    format_time: TimeFormatter,
    time_difference: TimeDifference,
    logo_path: Path | None = None,
) -> None:
    """Write one operation export file: CSV (说明区 + 空行 + 表头 + 701 行) or Excel (计算数据 + 计算说明 两表)."""
    table = operation_table(result, exported_at=exported_at, format_time=format_time, time_difference=time_difference)
    if kind == "csv":
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerows([*table.metadata, [], table.columns])
            writer.writerows([_cell(value) for value in row] for row in table.rows)
        return
    workbook = Workbook()
    _fill_operation_data_sheet(workbook.active, table)
    details = workbook.create_sheet("计算说明")
    _fill_operation_details_sheet(details, table)
    logo = brand_image(logo_path, "D1")
    if logo:
        details.add_image(logo)
    workbook.save(path)


def _fill_operation_data_sheet(sheet: Any, table: OperationTable) -> None:  # noqa: ANN401 - openpyxl worksheet
    """计算数据 sheet: column header, 701 rows, frozen header/wavelength column, filter and number formats."""
    sheet.title = "计算数据"
    sheet.append(table.columns)
    for row in table.rows:
        sheet.append([_cell(value) for value in row])
    sheet.freeze_panes = "B2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.zoomScale = 90
    sheet.row_dimensions[1].height = 48
    widths = (12, 19, 19, 22, 20, 20)
    for index, width in enumerate(widths[: len(table.columns)], 1):
        sheet.column_dimensions[chr(64 + index)].width = width
    for cells in sheet.iter_rows():
        if cells[0].row > 1:
            sheet.row_dimensions[cells[0].row].height = 22
        for cell in cells:
            cell.font = ExcelFont(name="Microsoft YaHei", size=11, bold=cell.row == 1)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if cell.row == 1:
                cell.fill = PatternFill("solid", fgColor="E8EEF5")
            elif isinstance(cell.value, (int, float)):
                magnitude = abs(cell.value)
                if cell.column == 1 or cell.column >= 5 or magnitude == 0:
                    cell.number_format = "0"
                elif magnitude < 1.0e-6 or magnitude >= 1.0e6:
                    cell.number_format = "0.######E+00"
                else:
                    cell.number_format = "0.########"


def _fill_operation_details_sheet(details: Any, table: OperationTable) -> None:  # noqa: ANN401 - openpyxl worksheet
    """计算说明 sheet: summary line and key/value rows, left-aligned text with wrapped long values."""
    details.append(["结果摘要", table.metadata[0][0]])
    for row in table.metadata[1:]:
        details.append(row)
    details.column_dimensions["A"].width = 34
    details.column_dimensions["B"].width = 100
    details.freeze_panes = "B2"
    for cells in details.iter_rows():
        for cell in cells:
            cell.font = ExcelFont(name="Microsoft YaHei", size=11, bold=cell.column == 1)
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            if isinstance(cell.value, str):
                cell.data_type = "s"
                cell.number_format = "@"
            if cell.column == 1:
                cell.fill = PatternFill("solid", fgColor="F0F3F7")
        text_width = sum(2 if ord(character) > 127 else 1 for character in str(cells[1].value or ""))
        details.row_dimensions[cells[0].row].height = max(34, 20 * (text_width // 85 + 1) + 12)


def file_extension(kind: str) -> str:
    """Extension of a single operation export file: "csv" for csv, otherwise "xlsx"."""
    return "csv" if kind == "csv" else "xlsx"


def operation_file_stem(token: str, a_record: Record, b_record: Record) -> str:
    """A<A记录ID>_<token>_B<B记录ID>; token is OPERATION_TOKENS[operation] (EXP-024/EXP-025)."""
    return f"A{a_record['id']}_{token}_B{b_record['id']}"


@dataclass(frozen=True)
class OperationExport:
    """Outcome of export_operation_files: the result directory, the file names written, and the write error if any.

    On error the directory may already exist and `completed` lists the files written before the failure (EXP-020).
    """

    directory: Path
    completed: tuple[str, ...]
    error: OSError | ValueError | None = None


def export_operation_files(
    parent: str | Path,
    result: OperationResult,
    kinds: Sequence[str],
    *,
    started_at: datetime,
    write: Callable[[Path, str], None],
) -> OperationExport:
    """Create a fresh result directory under `parent` and write one file per kind with `write(path, kind)`.

    The directory is A<id>_<token>_B<id>_<started_at to the microsecond>; an existing name gets _1, _2, ...
    appended (EXP-024/EXP-027). OSError and ValueError end the export and are returned, not raised; nothing is
    shown to the user here.
    """
    stem = operation_file_stem(OPERATION_TOKENS[result[3]], result[4], result[5])
    name = f"{stem}_{started_at:%Y%m%d_%H%M%S_%f}"
    directory = Path(parent) / name
    completed: list[str] = []
    try:
        suffix = 0
        while True:
            try:
                directory.mkdir()
                break
            except FileExistsError:
                suffix += 1
                directory = Path(parent) / f"{name}_{suffix}"
        for kind in kinds:
            path = directory / f"{stem}.{kind}"
            write(path, kind)
            completed.append(path.name)
    except (OSError, ValueError) as exc:
        return OperationExport(directory, tuple(completed), exc)
    return OperationExport(directory, tuple(completed))
