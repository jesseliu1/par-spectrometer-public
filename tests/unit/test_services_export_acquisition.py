"""par_app.services.export, acquisition-record part: field tables, metadata/spectrum rows, files and folder names.

Moved out of par_app/ui.py (R-8-1 stage one). Expected values are written by hand from the EXP rules and the V1.0.2
status quo, not produced by the code under test. tests/qt/test_export.py and tests/qt/multidevice keep covering the
same logic through the MainWindow wrappers and dialogs; these tests pin the boundaries directly: None / NaN / inf,
missing or malformed JSON, short spectra and old UTC records. The operation-result part is in
tests/unit/test_services_export_operation.py.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from par_app.database import format_beijing_time
from par_app.services import export as svc

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "logo.png"
NAN = float("nan")
INF = float("inf")
BEIJING = timezone(timedelta(hours=8))
EXPORTED_AT = datetime(2026, 10, 17, 9, 8, 7, 654321, tzinfo=BEIJING)
EXPORTED_TEXT = "2026-10-17 09:08:07.654"


# The 69 export fields of V1.0.2 (EXP-002 "保留原有69项字段结构"): copied by hand from EXPORT_DIRECT_FIELDS,
# EXPORT_METRICS_FIELDS and EXPORT_MCU_FIELDS in par_app/ui.py at dd1b5a8 (identical at c91ec03, the last commit
# before the move). Deliberately a literal, not derived from the code under test: a rename, a reorder or a source
# change must fail here. A decided label change (e.g. fix/uv-band-350-399) edits this table in the same PR.
V1_0_2_EXPORT_FIELDS: tuple[tuple[str, str, str, str], ...] = (
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
    ("peak_wavelength_nm", "PAR峰值波长(nm)", "PAR Peak Wavelength (nm)", "metrics"),
    ("peak_value", "PAR峰值功率", "PAR Peak Power", "metrics"),
    ("integrated_irradiance", "350–1050 nm 总辐照度(W/m²)", "Integrated Irradiance 350–1050 nm (W/m²)", "metrics"),
    ("software_ppfd", "软件PPFD(µmol·m⁻²·s⁻¹)", "Software PPFD", "metrics"),
    ("par", "PAR波段辐照度(W/m²)", "PAR Irradiance (W/m²)", "metrics"),
    ("pfd", "PFD(350–780)", "PFD", "metrics"),
    ("ppfd", "PPFD(400–700)", "PPFD", "metrics"),
    ("pfd_uv", "紫外PFD(350–399)", "UV PFD", "metrics"),  # D-103 (PR #31); V1.0.2: 350–400
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
    ("extended_pfd_uv", "扩展紫外PFD(350–399)", "Extended UV PFD", "metrics"),  # D-103 (PR #31); V1.0.2: 350–400
    ("extended_pfd_b", "扩展蓝光PFD(400–499)", "Extended Blue PFD", "metrics"),
    ("extended_pfd_g", "扩展绿光PFD(500–599)", "Extended Green PFD", "metrics"),
    ("extended_pfd_r", "扩展红光PFD(600–699)", "Extended Red PFD", "metrics"),
    ("extended_pfd_fr", "扩展远红PFD(700–1050)", "Extended Far-red PFD", "metrics"),
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


def fake_time(value: object) -> str:
    """Stand-in formatter: shows exactly which value the service asked to format."""
    return f"T<{value}>"


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream))


# ---------------------------------------- field tables (were ui.py EXPORT_*_FIELDS)


@pytest.mark.spec("EXP-002 EXP-057 EXP-058")
def test_field_tables_equal_the_v1_0_2_fields_entry_by_entry() -> None:
    assert len(V1_0_2_EXPORT_FIELDS) == 69
    assert svc.EXPORT_ALL_FIELDS == V1_0_2_EXPORT_FIELDS


@pytest.mark.spec("EXP-002 EXP-003")
def test_field_tables_hold_15_direct_27_metrics_27_mcu_fields_by_source() -> None:
    assert (len(svc.EXPORT_DIRECT_FIELDS), len(svc.EXPORT_METRICS_FIELDS), len(svc.EXPORT_MCU_FIELDS)) == (15, 27, 27)
    assert svc.EXPORT_ALL_FIELDS == svc.EXPORT_DIRECT_FIELDS + svc.EXPORT_METRICS_FIELDS + svc.EXPORT_MCU_FIELDS
    assert {source for *_, source in svc.EXPORT_DIRECT_FIELDS} == {"direct"}
    assert {source for *_, source in svc.EXPORT_METRICS_FIELDS} == {"metrics"}
    assert {source for *_, source in svc.EXPORT_MCU_FIELDS} == {"mcu"}
    assert svc.EXPORT_ALL_FIELDS[0] == ("id", "记录ID", "Record ID", "direct")
    assert svc.EXPORT_ALL_FIELDS[14] == ("elapsed_ms", "耗时(ms)", "Elapsed (ms)", "direct")
    assert svc.EXPORT_ALL_FIELDS[-1] == ("y", "CIE y", "CIE y", "mcu")
    for table in (svc.EXPORT_DIRECT_FIELDS, svc.EXPORT_METRICS_FIELDS, svc.EXPORT_MCU_FIELDS):
        assert len({key for key, *_ in table}) == len(table)


@pytest.mark.spec("EXP-057 EXP-058")
def test_cct_comes_from_the_hardware_parameters_and_irradiance_label_names_its_band() -> None:
    assert ("cct", "相关色温(K)", "CCT (K)", "mcu") in svc.EXPORT_MCU_FIELDS
    assert "cct" not in {key for key, *_ in svc.EXPORT_METRICS_FIELDS}
    irradiance = next(field for field in svc.EXPORT_METRICS_FIELDS if field[0] == "integrated_irradiance")
    assert irradiance[1] == "350–1050 nm 总辐照度(W/m²)"


# ---------------------------------------- metadata_rows (was MainWindow._export_metadata_rows)


def _value_of(rows: list[list[Any]], english: str) -> Any:  # noqa: ANN401 - stored values of any type
    return next(row[2] for row in rows if row[1] == english)


@pytest.mark.spec("EXP-002 EXP-057")
def test_metadata_rows_route_each_field_to_its_source() -> None:
    row = {
        "id": 42,
        "acquired_at": "2026-08-07T10:30:00",
        "elapsed_ms": 22.5,
        "ppfd": "direct column must not be used for a metrics field",
        "software_metrics_json": json.dumps({"ppfd": 520.5, "par": 14.02, "cct": 1111, "id": 99}),
        "mcu_params_json": json.dumps({"cct": 5800.0, "lux": 42000, "y": 0.3333, "ppfd": 1}),
    }
    rows = svc.metadata_rows(row)
    assert len(rows) == 69
    assert rows[0] == ["记录ID", "Record ID", 42]
    assert _value_of(rows, "Elapsed (ms)") == 22.5
    assert _value_of(rows, "PPFD") == 520.5
    assert _value_of(rows, "PAR Irradiance (W/m²)") == pytest.approx(140.2)  # ×10, D-166
    assert _value_of(rows, "CCT (K)") == 5800.0  # hardware CCT, not the software one (EXP-057)
    assert _value_of(rows, "Illuminance (lx)") == 42000
    assert rows[-1] == ["CIE y", "CIE y", 0.3333]
    assert [row[:2] for row in rows] == [[zh, en] for _, zh, en, _ in V1_0_2_EXPORT_FIELDS]


@pytest.mark.spec("EXP-002")
def test_metadata_rows_blank_only_missing_and_none_values() -> None:
    row = {
        "id": None,
        "success": 0,
        "initialized": False,
        "error_stage": "",
        "elapsed_ms": NAN,
        "software_metrics_json": json.dumps({"ppfd": None, "pfd": 0.0, "par": INF}),
        "mcu_params_json": json.dumps({"lux": -0.0}),
    }
    rows = svc.metadata_rows(row)
    assert _value_of(rows, "Record ID") == ""
    assert _value_of(rows, "Success") == 0
    assert _value_of(rows, "Initialized") is False
    assert _value_of(rows, "Error Stage") == ""
    assert math.isnan(_value_of(rows, "Elapsed (ms)"))
    assert _value_of(rows, "MCU Time (ms)") == ""  # key absent from the row
    assert _value_of(rows, "PPFD") == ""
    assert _value_of(rows, "PFD") == 0.0
    assert _value_of(rows, "PAR Irradiance (W/m²)") == INF
    assert _value_of(rows, "Illuminance (lx)") == 0.0
    assert _value_of(rows, "CCT (K)") == ""


@pytest.mark.spec("EXP-002")
@pytest.mark.parametrize("blob", [None, "", "{", "not json", b"\xff"])
def test_metadata_rows_treat_missing_or_unreadable_json_as_empty(blob: object) -> None:
    rows = svc.metadata_rows({"id": 1, "software_metrics_json": blob, "mcu_params_json": blob})
    assert len(rows) == 69
    assert [row[2] for row in rows[15:]] == [""] * 54
    assert rows[0][2] == 1


@pytest.mark.known_defect("D-168 pending: non-object metrics/MCU JSON aborts the export with AttributeError")
@pytest.mark.parametrize("blob", ["null", "[1, 2]", "5", '"text"'])
def test_known_defect_non_object_json_raises_attribute_error(blob: str) -> None:
    """Status quo: valid JSON that is not an object is not treated as empty; export_acquisitions does not catch it."""
    with pytest.raises(AttributeError):
        svc.metadata_rows({"id": 1, "software_metrics_json": blob})


@pytest.mark.spec("MATH-007")
def test_par_exported_in_ui_scale() -> None:
    """D-166 (PR #15, old repo issue #8 / audit data-correctness B1): par / extended_par are exported as stored ×10,
    the same scale as the UI (MATH-007); the stored record is not rewritten."""
    stored = {"par": 14.02, "extended_par": 1.5}
    row = {"software_metrics_json": json.dumps(stored)}
    rows = svc.metadata_rows(row)
    assert _value_of(rows, "PAR Irradiance (W/m²)") == pytest.approx(140.2)
    assert _value_of(rows, "Extended PAR Irradiance") == pytest.approx(15.0)
    assert json.loads(row["software_metrics_json"]) == stored


# ---------------------------------------- spectrum_rows (was MainWindow._export_spectrum_rows)


@pytest.mark.spec("EXP-003 EXP-006")
def test_spectrum_rows_pair_701_wavelengths_with_float_values() -> None:
    points = [100 + i for i in range(701)]
    points[3] = "1.5"  # numeric text is accepted
    rows = svc.spectrum_rows({"raw_points_json": json.dumps(points)})
    assert rows is not None and len(rows) == 701
    assert rows[0] == [350.0, 100.0] and rows[-1] == [1050.0, 800.0]
    assert rows[3] == [353.0, 1.5]
    assert all(type(wavelength) is float and type(value) is float for wavelength, value in rows)


def test_spectrum_rows_keep_non_finite_points() -> None:
    rows = svc.spectrum_rows({"raw_points_json": json.dumps([NAN, INF] + [0] * 699)})
    assert rows is not None
    assert math.isnan(rows[0][1]) and rows[1][1] == INF and rows[2] == [352.0, 0.0]


@pytest.mark.spec("EXP-003")
@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "[]",
        "{",
        "5",
        json.dumps([1.0] * 700),
        json.dumps([1.0] * 702),
        json.dumps([None] + [1.0] * 700),
        json.dumps(["x"] + [1.0] * 700),
        json.dumps({"350": 1}),
    ],
    ids=["none", "empty", "empty-list", "bad-json", "number", "700", "702", "null-point", "text-point", "object"],
)
def test_spectrum_rows_return_none_without_a_complete_spectrum(raw: str | None) -> None:
    assert svc.spectrum_rows({"raw_points_json": raw}) is None
    assert svc.spectrum_rows({}) is None


# ---------------------------------------- write_acquisition_file (was MainWindow._write_export_file)


def acquisition_row(*, spectrum: bool = True) -> dict[str, Any]:
    return {
        "id": 7,
        "acquired_at": "2026-08-07T02:30:00+00:00",  # old UTC record: shown as Beijing time
        "success": 1,
        "software_metrics_json": json.dumps({"ppfd": 520.5}),
        "mcu_params_json": json.dumps({"cct": 5800.0}),
        "raw_points_json": json.dumps([100 + i for i in range(701)]) if spectrum else None,
    }


@pytest.mark.spec("EXP-001 EXP-003 EXP-006 EXP-054")
def test_acquisition_csv_is_header_metadata_blank_and_701_points(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    svc.write_acquisition_file(path, acquisition_row(), "csv", exported_at=EXPORTED_AT, format_time=format_beijing_time)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    lines = read_csv(path)
    assert len(lines) == 4 + 69 + 1 + 1 + 701
    assert lines[:4] == [
        ["文件来源", "PAR 光谱仪专用软件 - 采集记录导出"],
        ["导出时间（北京时间）", EXPORTED_TEXT],
        ["采集记录 ID", "7"],
        ["采集时间（北京时间）", "2026-08-07 10:30:00.000"],
    ]
    assert lines[4] == ["记录ID", "Record ID", "7"]
    assert lines[73] == []
    assert lines[74] == ["波长（nm）", "原始光谱值"]
    assert lines[75] == ["350.0", "100.0"] and lines[-1] == ["1050.0", "800.0"]


@pytest.mark.spec("EXP-003")
def test_acquisition_csv_without_spectrum_writes_one_hint_row(tmp_path: Path) -> None:
    path = tmp_path / "b.csv"
    svc.write_acquisition_file(
        path, acquisition_row(spectrum=False), "csv", exported_at=EXPORTED_AT, format_time=fake_time
    )
    lines = read_csv(path)
    assert len(lines) == 4 + 69 + 1 + 1
    assert lines[1] == ["导出时间（北京时间）", f"T<{EXPORTED_AT}>"]
    assert lines[3] == ["采集时间（北京时间）", "T<2026-08-07T02:30:00+00:00>"]
    assert lines[-1] == ["光谱数据区", "本记录无原始光谱数据（采集失败或未保存光谱）。"]


@pytest.mark.spec("EXP-003 EXP-054")
@pytest.mark.parametrize("kind", ["xlsx", "other"])
def test_acquisition_excel_has_same_rows_one_sheet_widths_and_logo(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "a.xlsx"
    svc.write_acquisition_file(
        path, acquisition_row(), kind, exported_at=EXPORTED_AT, format_time=format_beijing_time, logo_path=LOGO
    )
    workbook = load_workbook(path)
    sheet = workbook.active
    assert workbook.sheetnames == ["采集 #7"]
    assert sheet.max_row == 4 + 69 + 1 + 1 + 701
    assert [cell.value for cell in sheet[2]][:2] == ["导出时间（北京时间）", EXPORTED_TEXT]
    assert sheet.cell(75, 1).value == "波长（nm）" and sheet.cell(76, 2).value == 100.0
    assert sheet.cell(74, 1).value is None
    assert (sheet.column_dimensions["A"].width, sheet.column_dimensions["B"].width) == (36, 46)
    assert sheet.column_dimensions["C"].width == 64
    assert sheet.cell(1, 1).alignment.horizontal == "left" and sheet.cell(1, 1).alignment.wrap_text
    assert len(sheet._images) == 1
    assert sheet._images[0].anchor._from.col == 7  # H1
    extent = sheet._images[0].anchor.ext
    assert (extent.width, extent.height) == (112 * 9525, 54 * 9525)  # 112 x 54 px in EMU


def test_acquisition_excel_without_logo_file_has_no_image(tmp_path: Path) -> None:
    for logo in (None, tmp_path / "missing.png"):
        path = tmp_path / "x.xlsx"
        svc.write_acquisition_file(
            path,
            acquisition_row(spectrum=False),
            "xlsx",
            exported_at=EXPORTED_AT,
            format_time=fake_time,
            logo_path=logo,
        )
        sheet = load_workbook(path).active
        assert sheet._images == []
        assert sheet.cell(75, 1).value == "光谱数据区"


@pytest.mark.known_defect(
    "D-170 pending / audit robustness-ui Bug 7 (critic verify-22): non-finite metadata is 'nan'/'inf' in CSV but an "
    "empty cell in Excel"
)
def test_known_defect_non_finite_metadata_differs_between_csv_and_excel(tmp_path: Path) -> None:
    row = {"id": 3, "elapsed_ms": NAN, "software_metrics_json": json.dumps({"ppfd": INF})}
    svc.write_acquisition_file(tmp_path / "n.csv", row, "csv", exported_at=EXPORTED_AT, format_time=fake_time)
    svc.write_acquisition_file(tmp_path / "n.xlsx", row, "xlsx", exported_at=EXPORTED_AT, format_time=fake_time)
    lines = read_csv(tmp_path / "n.csv")
    assert lines[4 + 14] == ["耗时(ms)", "Elapsed (ms)", "nan"]
    assert lines[4 + 15 + 6] == ["PPFD(400–700)", "PPFD", "inf"]
    sheet = load_workbook(tmp_path / "n.xlsx").active
    assert sheet.cell(5 + 14, 3).value is None
    assert sheet.cell(5 + 15 + 6, 3).value is None


# ---------------------------------------- acquisition folders and names (were inline in export_acquisitions)


@pytest.mark.spec("EXP-008 EXP-012 EXP-072")
def test_acquisition_files_are_sorted_by_device_format_and_date() -> None:
    acquired = datetime(2026, 8, 7, 10, 30, 5)
    row = {"id": 12}
    assert svc.acquisition_day_folder("/out", "East", "csv", acquired) == Path("/out/East/CSV/2026-08-07")
    assert svc.acquisition_day_folder(Path("/out"), "East", "xlsx", acquired) == Path("/out/East/Excel/2026-08-07")
    assert svc.acquisition_file_name(row, "csv", acquired) == "PAR_20260807_103005_#12.csv"
    assert svc.acquisition_file_name({}, "xlsx", acquired) == "PAR_20260807_103005_#None.xlsx"
    assert [svc.format_label(kind) for kind in ("csv", "xlsx", "other")] == ["CSV", "Excel", "Excel"]


@pytest.mark.spec("EXP-008")
@pytest.mark.parametrize(
    ("name", "folder"),
    [("East", "East"), ("西/区:1", "西_区_1"), ("  a.  ", "a"), ("", "spectrometer"), (" . ", "spectrometer")],
)
def test_device_folder_is_the_safe_device_name(name: str, folder: str) -> None:
    assert svc.device_folder(name) == folder


def test_folder_time_parses_naive_and_falls_back_for_unreadable_times() -> None:
    fallback = datetime(2026, 1, 1)
    assert svc.folder_time({"acquired_at": "2026-08-07T10:30:00.123"}, fallback) == datetime(
        2026, 8, 7, 10, 30, 0, 123000
    )
    for value in (None, "", "garbage", "2026-02-30T00:00:00", 12345):
        assert svc.folder_time({"acquired_at": value}, fallback) is fallback
    assert svc.folder_time({}, fallback) is fallback


@pytest.mark.known_defect("D-169 pending: old UTC records are filed under their UTC date, not the Beijing date")
def test_known_defect_folder_time_drops_the_offset_instead_of_converting() -> None:
    """Status quo: the file content shows Beijing time (format_beijing_time), the folder/file name the raw clock."""
    value = "2026-08-07T20:00:00+00:00"
    assert svc.folder_time({"acquired_at": value}, datetime(2026, 1, 1)) == datetime(2026, 8, 7, 20, 0, 0)
    assert format_beijing_time(value) == "2026-08-08 04:00:00.000"
