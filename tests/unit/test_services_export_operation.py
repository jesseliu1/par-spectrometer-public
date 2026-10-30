"""par_app.services.export, spectrum-operation part: result table, CSV/Excel files and the result directory.

Moved out of par_app/ui.py (R-8-1 stage one). Expected values are written by hand from the EXP/MATH rules and the
V1.0.2 status quo, not produced by the code under test. tests/qt/multidevice (operation export layout and results)
keeps covering the same logic through the MainWindow wrappers and dialogs; these tests pin the boundaries directly:
B = 0 and A = 0 ratios, NaN / inf values, Excel number-format edges, directory collisions and write failures.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
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


def fake_time(value: object) -> str:
    """Stand-in formatter: shows exactly which value the service asked to format."""
    return f"T<{value}>"


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream))


# ---------------------------------------- operation_table (was MainWindow._write_operation_file, content part)


def records(**extra: Any) -> tuple[dict[str, Any], dict[str, Any]]:  # noqa: ANN401 - record fields of any type
    a = {"id": 3, "acquired_at": "2026-08-07T10:00:00", "source_device": "East", "source_database": "east.sqlite3"}
    b = {"id": 9, "acquired_at": "2026-08-07T10:00:30", **extra}
    return a, b


def time_difference_spy(calls: list[tuple[Any, Any]]) -> svc.TimeDifference:
    def difference(a: Any, b: Any) -> Any:  # noqa: ANN401 - same signature as MainWindow._operation_time_difference
        calls.append((a, b))
        return 30.0

    return difference


def operation_result(op: str) -> svc.OperationResult:
    a = np.full(701, 2.0)
    b = np.full(701, 1.0)
    a[0], b[0] = 0.0, 4.0  # 0 / 4 = valid 0
    a[1], b[1] = 3.0, 0.0  # B = 0 -> NaN
    a[2], b[2] = NAN, 1.0
    a[3], b[3] = 50.0, 1.0  # sets the peak: threshold 2% x 50 = 1.0
    a[4], b[4] = 0.5, 1.0  # below the threshold
    out = {"add": a + b, "subtract": a - b}.get(op)
    if out is None:
        with np.errstate(divide="ignore", invalid="ignore"):
            out = np.where((b != 0) & np.isfinite(a) & np.isfinite(b), a / b, NAN)
    a_record, b_record = records()
    return a, b, out, op, a_record, b_record


@pytest.mark.spec("EXP-005 EXP-010 EXP-015 EXP-037 EXP-061")
def test_operation_table_for_subtraction_has_four_columns_and_source_metadata() -> None:
    calls: list[tuple[Any, Any]] = []
    result = operation_result("subtract")
    table = svc.operation_table(
        result, exported_at=EXPORTED_AT, format_time=format_beijing_time, time_difference=time_difference_spy(calls)
    )
    assert table.columns == ["波长（nm）", "光谱 A（mW/nm）", "光谱 B（mW/nm）", "计算结果（mW/nm）"]
    assert len(table.rows) == 701 and table.rows[0] == (350.0, 0.0, 4.0, -4.0) and table.rows[-1][0] == 1050.0
    assert table.metadata[0] == [
        "光谱 A：ID 3，采集时间 2026-08-07 10:00:00.000；光谱 B：ID 9，采集时间 2026-08-07 10:00:30.000；"
        "运算法则：减法（A − B）"
    ]
    assert table.metadata[1:] == [
        ["文件来源", "PAR 光谱仪专用软件 - 光谱运算"],
        ["导出时间（北京时间）", EXPORTED_TEXT],
        ["光谱 A 来源设备", "East"],
        ["光谱 A 来源数据库", "east.sqlite3"],
        ["光谱 B 来源设备", ""],
        ["光谱 B 来源数据库", ""],
        ["光谱 A 记录 ID", 3],
        ["光谱 A 采集时间（北京时间）", "2026-08-07 10:00:00.000"],
        ["光谱 B 记录 ID", 9],
        ["光谱 B 采集时间（北京时间）", "2026-08-07 10:00:30.000"],
        ["采集时间差 B - A（秒）", 30.0],
        ["运算法则", "减法（A − B）"],
        ["零值处理规则", "不适用。"],
    ]
    assert calls == [(result[4], result[5])]


@pytest.mark.spec("EXP-017 EXP-018 EXP-019 EXP-060")
def test_operation_table_for_division_adds_threshold_flags_and_rules() -> None:
    table = svc.operation_table(
        operation_result("divide"), exported_at=EXPORTED_AT, format_time=fake_time, time_difference=lambda a, b: None
    )
    assert table.columns[3:] == [
        "计算结果（比值 A/B）",
        "低信号标记（1=未通过显示筛选）",
        "结果有效标记（1=有效，0=无效）",
    ]
    assert table.metadata[0][0].endswith("运算法则：除法 / 比值（A / B）")
    assert table.metadata[11] == ["采集时间差 B - A（秒）", None]
    assert table.metadata[13][1].startswith("除法规则：A、B 有限且 B 非零时计算 A / B")
    assert [row[0] for row in table.metadata[14:]] == [
        "比值显示共同阈值（mW/nm）",
        "比值显示筛选规则",
        "低信号标记说明",
        "无效值说明",
    ]
    assert table.metadata[14][1] == pytest.approx(1.0)  # 2% of the common peak 50
    rows = table.rows
    assert rows[0][3] == 0.0 and (rows[0][4], rows[0][5]) == (1, 1)  # valid 0, hidden (A = 0 is not > 0)
    assert math.isnan(rows[1][3]) and (rows[1][4], rows[1][5]) == (1, 0)  # B = 0: NaN, invalid
    assert math.isnan(rows[2][3]) and (rows[2][4], rows[2][5]) == (1, 0)
    assert rows[3][3] == 50.0 and (rows[3][4], rows[3][5]) == (0, 1)
    assert rows[4][3] == 0.5 and (rows[4][4], rows[4][5]) == (1, 1)  # A below 2% threshold: hidden, still valid
    assert rows[5][3] == 2.0 and (rows[5][4], rows[5][5]) == (0, 1)


def test_operation_table_rejects_unknown_operations_and_short_results() -> None:
    a, b, out, _, a_record, b_record = operation_result("add")
    with pytest.raises(KeyError):
        svc.operation_table(
            (a, b, out, "mul", a_record, b_record),
            exported_at=EXPORTED_AT,
            format_time=fake_time,
            time_difference=lambda x, y: None,
        )
    with pytest.raises(ValueError):
        svc.operation_table(
            (a, b, out, "add", a_record),
            exported_at=EXPORTED_AT,
            format_time=fake_time,  # type: ignore[arg-type]
            time_difference=lambda x, y: None,
        )


# ---------------------------------------- write_operation_file (was MainWindow._write_operation_file)


def write_operation(tmp_path: Path, op: str, kind: str, result: svc.OperationResult | None = None) -> Path:
    path = tmp_path / f"op.{kind}"
    svc.write_operation_file(
        path,
        kind,
        result or operation_result(op),
        exported_at=EXPORTED_AT,
        format_time=format_beijing_time,
        time_difference=lambda a, b: 30.0,
        logo_path=LOGO,
    )
    return path


@pytest.mark.spec("EXP-016 EXP-039 EXP-040 EXP-065")
def test_operation_csv_is_metadata_blank_header_and_701_rows_with_nan_text(tmp_path: Path) -> None:
    lines = read_csv(write_operation(tmp_path, "divide", "csv"))
    header = lines.index(
        [
            "波长（nm）",
            "光谱 A（mW/nm）",
            "光谱 B（mW/nm）",
            "计算结果（比值 A/B）",
            "低信号标记（1=未通过显示筛选）",
            "结果有效标记（1=有效，0=无效）",
        ]
    )
    assert header == 19 and lines[header - 1] == []
    assert lines[0][0].startswith("光谱 A：ID 3") and len(lines[0]) == 1
    assert lines[2] == ["导出时间（北京时间）", EXPORTED_TEXT]
    data = lines[header + 1 :]
    assert len(data) == 701
    assert data[0] == ["350.0", "0.0", "4.0", "0.0", "1.0", "1.0"]  # flags are written through float() (EXP-018)
    assert data[1] == ["351.0", "3.0", "0.0", "NaN", "1.0", "0.0"]
    assert data[2] == ["352.0", "NaN", "1.0", "NaN", "1.0", "0.0"]


def test_operation_csv_writes_infinite_values_as_nan_text(tmp_path: Path) -> None:
    a, b, out, op, a_record, b_record = operation_result("add")
    out = out.copy()
    out[5], out[6] = INF, -INF
    lines = read_csv(write_operation(tmp_path, "add", "csv", (a, b, out, op, a_record, b_record)))
    header = lines.index(["波长（nm）", "光谱 A（mW/nm）", "光谱 B（mW/nm）", "计算结果（mW/nm）"])
    assert header == 15
    assert lines[header + 6][3] == "NaN" and lines[header + 7][3] == "NaN"
    assert len(lines) - header - 1 == 701


@pytest.mark.spec("EXP-028 EXP-029 EXP-030 EXP-031 EXP-032 EXP-033 EXP-034 EXP-035 EXP-062")
def test_operation_excel_data_sheet_layout_and_number_formats(tmp_path: Path) -> None:
    a, b, out, op, a_record, b_record = operation_result("divide")
    a = a.copy()
    a[10:16] = [1e-7, 1e-6, 999999.99, 1e6, -2.5e6, 0.123456789]
    path = write_operation(tmp_path, op, "xlsx", (a, b, out, op, a_record, b_record))
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["计算数据", "计算说明"] and workbook.active.title == "计算数据"
    data = workbook["计算数据"]
    assert data.max_row == 702 and data.max_column == 6
    assert data.freeze_panes == "B2" and data.auto_filter.ref == "A1:F702" and data.sheet_view.zoomScale == 90
    assert data.row_dimensions[1].height == 48 and data.row_dimensions[2].height == 22
    assert [data.column_dimensions[c].width for c in "ABCDEF"] == [12, 19, 19, 22, 20, 20]
    assert data["A1"].fill.fgColor.rgb == "00E8EEF5" and data["A1"].font.b and not data["A2"].font.b
    assert data["A2"].alignment.horizontal == "center" and data["A1"].alignment.wrap_text
    assert data["D3"].value == "NaN" and data["D3"].data_type == "s"  # EXP-028
    formats = {row: data.cell(row, 2).number_format for row in range(12, 18)}
    assert formats == {
        12: "0.######E+00",  # 1e-7 < 1e-6
        13: "0.########",  # 1e-6 is not below the edge
        14: "0.########",  # 999999.99
        15: "0.######E+00",  # 1e6 is on the edge (>=)
        16: "0.######E+00",  # |-2.5e6|
        17: "0.########",
    }
    assert data.cell(17, 2).value == 0.123456789  # raw value kept (EXP-030)
    assert data["A2"].number_format == "0" and data["B2"].number_format == "0"  # wavelength column / zero
    assert data["E2"].value == 1 and data["E2"].number_format == "0" and data["F3"].value == 0  # EXP-032


@pytest.mark.spec("EXP-029 EXP-036 EXP-037 EXP-063 EXP-064")
def test_operation_excel_details_sheet(tmp_path: Path) -> None:
    details = load_workbook(write_operation(tmp_path, "divide", "xlsx"))["计算说明"]
    rows = list(details.values)
    assert rows[0][0] == "结果摘要" and rows[0][1].startswith("光谱 A：ID 3，采集时间 2026-08-07 10:00:00.000")
    assert [row[0] for row in rows[1:4]] == ["文件来源", "导出时间（北京时间）", "光谱 A 来源设备"]
    assert rows[2][1] == EXPORTED_TEXT and details["B3"].number_format == "@" and details["B3"].data_type == "s"
    assert rows[-1][0] == "无效值说明" and len(rows) == 18
    assert (details.column_dimensions["A"].width, details.column_dimensions["B"].width) == (34, 100)
    assert details.freeze_panes == "B2"
    assert details["A1"].font.b and not details["B1"].font.b and details["A1"].fill.fgColor.rgb == "00F0F3F7"
    assert details["B1"].alignment.horizontal == "left" and details["B1"].alignment.vertical == "top"
    assert details.row_dimensions[3].height == 34  # short text: minimum height
    summary_width = sum(2 if ord(character) > 127 else 1 for character in rows[0][1])
    assert details.row_dimensions[1].height == max(34, 20 * (summary_width // 85 + 1) + 12)
    assert len(details._images) == 1 and details._images[0].anchor._from.col == 3  # D1


# ---------------------------------------- export_operation_files (was inline in export_operation_results)


@pytest.mark.spec("EXP-024 EXP-025")
def test_export_operation_files_writes_each_kind_into_a_fresh_directory(tmp_path: Path) -> None:
    written: list[tuple[Path, str]] = []

    def write(path: Path, kind: str) -> None:
        written.append((path, kind))
        path.write_text(kind)

    outcome = svc.export_operation_files(
        str(tmp_path), operation_result("divide"), ["csv", "xlsx"], started_at=EXPORTED_AT, write=write
    )
    directory = tmp_path / "A3_ratio_B9_20261017_090807_654321"
    assert outcome == svc.OperationExport(directory, ("A3_ratio_B9.csv", "A3_ratio_B9.xlsx"))
    assert written == [(directory / "A3_ratio_B9.csv", "csv"), (directory / "A3_ratio_B9.xlsx", "xlsx")]
    assert sorted(p.name for p in directory.iterdir()) == ["A3_ratio_B9.csv", "A3_ratio_B9.xlsx"]


@pytest.mark.spec("EXP-027")
def test_export_operation_files_appends_a_suffix_instead_of_reusing_a_directory(tmp_path: Path) -> None:
    name = "A3_add_B9_20261017_090807_654321"
    (tmp_path / name).mkdir()
    (tmp_path / f"{name}_1").mkdir()
    outcome = svc.export_operation_files(
        tmp_path, operation_result("add"), ["csv"], started_at=EXPORTED_AT, write=lambda path, kind: path.touch()
    )
    assert outcome.directory == tmp_path / f"{name}_2" and outcome.error is None
    assert list((tmp_path / name).iterdir()) == []


@pytest.mark.spec("EXP-020")
@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("disk full"), ValueError("bad value")])
def test_export_operation_files_returns_the_error_and_the_files_already_written(
    tmp_path: Path, error: Exception
) -> None:
    def write(path: Path, kind: str) -> None:
        if kind == "xlsx":
            raise error
        path.touch()

    outcome = svc.export_operation_files(
        tmp_path, operation_result("subtract"), ["csv", "xlsx"], started_at=EXPORTED_AT, write=write
    )
    assert outcome.error is error
    assert outcome.completed == ("A3_sub_B9.csv",)
    assert outcome.directory.is_dir()


def test_export_operation_files_reports_a_missing_parent_and_raises_other_errors(tmp_path: Path) -> None:
    outcome = svc.export_operation_files(
        tmp_path / "missing", operation_result("add"), ["csv"], started_at=EXPORTED_AT, write=lambda p, k: None
    )
    assert isinstance(outcome.error, FileNotFoundError) and outcome.completed == ()

    def write(path: Path, kind: str) -> None:
        raise KeyError("not an I/O error")

    with pytest.raises(KeyError):
        svc.export_operation_files(tmp_path, operation_result("add"), ["csv"], started_at=EXPORTED_AT, write=write)
    a, b, out, _, a_record, b_record = operation_result("add")
    with pytest.raises(KeyError):
        svc.export_operation_files(
            tmp_path / "new", (a, b, out, "mul", a_record, b_record), ["csv"], started_at=EXPORTED_AT, write=write
        )
    assert not (tmp_path / "new").exists()


def test_single_operation_file_name_parts() -> None:
    assert svc.OPERATION_TOKENS == {"add": "add", "subtract": "sub", "divide": "ratio"}
    assert svc.operation_file_stem("ratio", {"id": 1}, {"id": "2"}) == "A1_ratio_B2"
    assert [svc.file_extension(kind) for kind in ("csv", "xlsx", "other")] == ["csv", "xlsx", "xlsx"]
