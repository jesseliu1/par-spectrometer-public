"""tools/quality/shadow_rules.py: reverse lookup of numeric rules in code (R-2-2 gate 4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "quality"))

import shadow_rules  # noqa: E402

pytestmark = pytest.mark.unit


def _app(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_scan_finds_constants_literals_negatives_and_annotated_constants(tmp_path: Path) -> None:
    path = tmp_path / "m.py"
    path.write_text(
        "BUDGET = 40.0\nCLEANUP: float = 2.0\nOFFSET = -5\n\n"
        "def f(x):\n    return x * 701 + 1 - 100 + 2.0\n\n"
        "class K:\n    def m(self):\n        return -3\n",
        encoding="utf-8",
    )
    rows = shadow_rules.scan(path)
    assert (1, "constant", "BUDGET", "40.0") in rows
    assert (2, "constant", "CLEANUP", "2.0") in rows
    assert (3, "constant", "OFFSET", "-5") in rows
    assert {(6, "literal", "f", v) for v in ("701", "100", "2.0")} <= set(rows)
    assert (10, "literal", "m", "-3") in rows
    assert not any(value in ("1", "5", "40.0") and kind == "literal" for _, kind, _, value in rows)
    assert not any(value == "3" for *_, value in rows)  # negated literal is reported once, as -3


def test_generate_recurses_and_summarises_reference_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _app(
        tmp_path,
        {
            "par_app/a.py": "def f():\n    return 42\n",
            "par_app/sub/b.py": "LIMIT = 4\n",
            "par_app/mccree1972_weights.py": "T = (0.5, 0.7, 0.9)\n",
        },
    )
    monkeypatch.setattr(shadow_rules, "REFERENCE_TABLES", {"par_app/mccree1972_weights.py": "整表"})
    lines = shadow_rules.generate(root)
    assert "| par_app/a.py:2 | literal | f | 42 |  |" in lines
    assert "| par_app/sub/b.py:1 | constant | LIMIT | 4 |  |" in lines
    assert any("table | 整表 | 3 values" in line for line in lines)


def test_check_is_line_number_independent_and_reports_new_values(tmp_path: Path) -> None:
    root = _app(tmp_path, {"par_app/a.py": "def f():\n    return 42\n"})
    doc = tmp_path / "list.md"
    doc.write_text(
        "| par_app/a.py:99 | literal | f | 42 | 非业务规则：示例 |\n| par_app/a.py:3 | literal | f | 7 |  |\n"
    )
    errors, notes = shadow_rules.check(doc, root)
    assert errors == []
    assert notes == ["par_app/a.py: literal f = 7 is listed but no longer in code"]
    (root / "par_app/a.py").write_text("def f():\n    return 42 + 43\n")
    errors, _ = shadow_rules.check(doc, root)
    assert errors == ["par_app/a.py: literal f = 43 is not in list.md"]


def test_main_prints_table_and_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    root = _app(tmp_path, {"par_app/a.py": "X = 9\n"})
    monkeypatch.setattr(shadow_rules, "ROOT", root)
    assert shadow_rules.main([]) == 0
    table = capsys.readouterr().out
    assert table.startswith("| 文件:行 |") and "| par_app/a.py:1 | constant | X | 9 |" in table
    doc = tmp_path / "doc.md"
    doc.write_text(table)
    assert shadow_rules.main(["--check", str(doc)]) == 0
    doc.write_text(shadow_rules.HEADER)
    assert shadow_rules.main(["--check", str(doc)]) == 1
    assert "SHADOW FAIL" in capsys.readouterr().out
