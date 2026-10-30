"""Reverse lookup of business rules hidden in code (R-2-2 gate 4).

Lists every numeric literal and UPPER_CASE numeric constant in par_app/ (recursively), so each value can be
mapped to a spec entry or marked "非业务规则：<理由>" in docs/spec/shadow-rules.md. Only 0, 1 and -1 are
skipped (R-1-4: trivially readable). Reference weight tables are listed as one row each, to be checked as a
whole.

Usage:
  python tools/quality/shadow_rules.py                                  # print the Markdown table
  python tools/quality/shadow_rules.py --check docs/spec/shadow-rules.md  # fail if code has values the
                                                                         # list does not cover yet
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_VALUES = {0, 1, -1}  # 0.0 == 0 and 1.0 == 1, so floats are covered too
REFERENCE_TABLES = {
    "par_app/mccree1972_weights.py": "McCree 1972 表，整表核对（内部文档）",
    "par_app/photopic_weights.py": "CIE V(λ) 表，整表核对（内部文档）",
}
HEADER = "| 文件:行 | 类型 | 名称/所在函数 | 值 | 对应规格 / 非业务规则说明 |\n|---|---|---|---|---|"
ROW = re.compile(r"^\|\s*([^|:]+):\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")

Row = tuple[int, str, str, str]


def _number(node: ast.AST) -> int | float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _number(node.operand)
        return -inner if inner is not None else None
    return None


def scan(path: Path) -> list[Row]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rows: list[Row] = []
    scopes: dict[int, str] = {}
    handled: set[int] = set()
    # ast.walk is breadth-first, so deeper scopes overwrite outer ones: each node keeps its innermost scope.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for child in ast.walk(node):
                scopes[id(child)] = node.name
    for node in ast.walk(tree):
        if id(node) in handled:
            continue
        target = value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and target.id.isupper() and value is not None and _number(value) is not None:
            rows.append((node.lineno, "constant", target.id, repr(_number(value))))
            handled.update(id(n) for n in ast.walk(value))
            continue
        number = _number(node)
        if number is not None and number not in SKIP_VALUES:
            rows.append((node.lineno, "literal", scopes.get(id(node), "<module>"), repr(number)))
            handled.update(id(n) for n in ast.walk(node))
    return sorted(set(rows))


def generate(root: Path | None = None) -> list[str]:
    root = root or ROOT
    lines = []
    for path in sorted((root / "par_app").rglob("*.py")):
        name = path.relative_to(root).as_posix()
        if name in REFERENCE_TABLES:
            count = len(scan(path))
            lines.append(f"| {name}:1 | table | 整表 | {count} values | {REFERENCE_TABLES[name]} |")
            continue
        lines.extend(f"| {name}:{line} | {kind} | {who} | {value} |  |" for line, kind, who, value in scan(path))
    return lines


def keys(lines: list[str]) -> Counter[tuple[str, str, str, str]]:
    """Line-number-independent identity of each row: (file, kind, name/scope, value)."""
    found: Counter[tuple[str, str, str, str]] = Counter()
    for line in lines:
        match = ROW.match(line.strip())
        if match and match.group(2) in ("constant", "literal", "table"):
            file, kind, name, value = (part.strip() for part in match.groups())
            found[(file, kind, name, value)] += 1
    return found


def check(document: Path, root: Path | None = None) -> tuple[list[str], list[str]]:
    """(errors: values in code missing from the list, notes: listed values no longer in code)."""
    documented = keys(document.read_text(encoding="utf-8").splitlines())
    current = keys(generate(root or ROOT))
    missing = current - documented
    stale = documented - current
    errors = [f"{f}: {kind} {who} = {value} is not in {document.name}" for f, kind, who, value in missing]
    notes = [f"{f}: {kind} {who} = {value} is listed but no longer in code" for f, kind, who, value in stale]
    return errors, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", type=Path, help="verify that this Markdown list covers the code")
    args = parser.parse_args(argv)
    if args.check is None:
        print(HEADER)
        print("\n".join(generate()))
        return 0
    errors, notes = check(args.check)
    for line in notes:
        print(f"note: {line}")
    for line in errors:
        print(f"SHADOW FAIL: {line}")
    print(f"shadow rules: {'FAIL' if errors else 'ok'} ({len(errors)} undocumented, {len(notes)} stale)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
