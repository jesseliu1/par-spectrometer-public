"""Spec traceability check (R-2-1, R-2-4, R-6-5).

Parses business-rule entries in docs/spec/<domain>.md (`### ACQ-012 标题` + `- 字段：值` lines) and checks
that every entry is wired three ways:
  * fields: 规则/来源/状态/验证/代码锚点 present; 状态 well-formed; 来源 quotes the original text or links
    an approval;
  * 验证: each item is a collectable pytest node that carries @pytest.mark.spec(<id>), an acceptance record
    (`acceptance:docs/acceptance/<file>.md` with a table row `| <id> | … | <结论> |`), or `冻结待确认`
    (only while the entry is 待确认);
  * 代码锚点: each `path Symbol.attr` resolves in the source tree (or `无：<理由>`);
  * every spec marker in tests/ names a known id and sits on a collectable test.
Test nodes are located with the AST but only count when `pytest --collect-only` actually collects them.
Release mode additionally requires a non-empty spec, a JUnit report in which every referenced node passed,
and acceptance records that conclude 通过 for the release candidate commit.

Usage:
  python tools/quality/spec_check.py
  python tools/quality/spec_check.py --release --junit report.xml --candidate <commit>
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ("ACQ", "POLL", "DLI", "EXP", "MAINT", "CONF", "UI", "MATH")
ID_RE = r"(?:" + "|".join(DOMAINS) + r")-\d{3}"
HEADING = re.compile(rf"^###\s+({ID_RE})\s+(.+?)\s*$")
FIELD = re.compile(r"^-\s*(规则|来源|状态|现状符合度|冲突|验证|代码锚点)\s*[:：]\s*(.*)$")
STATUS = re.compile(
    rf"^(待确认|已批准 \d{{4}}-\d{{2}}-\d{{2}} \S+|已废止 \d{{4}}-\d{{2}}-\d{{2}}.*由 ({ID_RE}) 替代.*)$"
)
QUOTE = re.compile(r"[\"“][^\"”]{6,}[\"”]|https?://")  # a quoted excerpt, not just a 「section」 name
NODE = re.compile(r"^tests/[\w/.-]+\.py::\w+(?:::\w+)?$")
ACCEPT_ROW = re.compile(rf"^\|\s*({ID_RE})\s*\|.*\|\s*([^|]+?)\s*\|$")
REQUIRED = ("规则", "来源", "状态", "验证", "代码锚点")
NON_SPEC_FILES = {
    "README.md",
    "coverage-matrix.md",
    "pending-decisions.md",
    "shadow-rules.md",
    "ui-migration-tracker.md",
}
FROZEN = "冻结待确认"


@dataclass
class Entry:
    spec_id: str
    title: str
    location: str
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return self.fields.get("状态", "")


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT

    @property
    def spec(self) -> Path:
        return self.root / "docs" / "spec"

    @property
    def tests(self) -> Path:
        return self.root / "tests"

    @property
    def acceptance(self) -> Path:
        return self.root / "docs" / "acceptance"


def split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[；;]", value) if item.strip()]


def parse_specs(spec_dir: Path) -> tuple[dict[str, Entry], list[str]]:
    entries: dict[str, Entry] = {}
    errors: list[str] = []
    for path in sorted(spec_dir.glob("*.md")):
        if path.name in NON_SPEC_FILES:
            continue
        current: Entry | None = None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            heading = HEADING.match(line)
            if heading:
                spec_id, title = heading.groups()
                location = f"{path.name}:{number}"
                if spec_id in entries:
                    errors.append(f"{location}: duplicate id {spec_id} (first at {entries[spec_id].location})")
                    current = None
                    continue
                current = entries[spec_id] = Entry(spec_id, title, location)
                continue
            match = FIELD.match(line.strip())
            if current and match:
                current.fields[match.group(1)] = match.group(2).strip()
    return entries, errors


def spec_markers(test_dir: Path, root: Path) -> tuple[dict[str, set[str]], list[str]]:
    """Map collectable test node ids to the spec ids they declare; report markers pytest would never collect."""
    nodes: dict[str, set[str]] = {}
    errors: list[str] = []
    for path in sorted(test_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        file_id = path.relative_to(root).as_posix()
        collectable_file = path.name.startswith("test_")
        module_ids = _pytestmark_ids(tree.body)
        collected: set[int] = set()
        for item in tree.body:
            if _is_test_function(item):
                collected.add(id(item))
                nodes[f"{file_id}::{item.name}"] = module_ids | _decorator_ids(item)
            elif isinstance(item, ast.ClassDef) and item.name.startswith("Test"):
                class_ids = module_ids | _decorator_ids(item) | _pytestmark_ids(item.body)
                for method in item.body:
                    if _is_test_function(method):
                        collected.add(id(method))
                        nodes[f"{file_id}::{item.name}::{method.name}"] = class_ids | _decorator_ids(method)
        if not collectable_file:
            if module_ids or any(_decorator_ids(n) for n in ast.walk(tree) if _is_def(n)):
                errors.append(f"{file_id}: spec markers in a file pytest does not collect (name it test_*.py)")
            nodes = {k: v for k, v in nodes.items() if not k.startswith(f"{file_id}::")}
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in collected:
                if _decorator_ids(node):
                    errors.append(f"{file_id}:{node.lineno}: spec marker on non-collectable `{node.name}`")
    return nodes, errors


def _is_def(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))


def _is_test_function(node: ast.stmt) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")


def _spec_call_ids(expr: ast.AST) -> set[str]:
    ids: set[str] = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "spec":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids.update(re.findall(ID_RE, arg.value))
    return ids


def _decorator_ids(node: ast.AST) -> set[str]:
    ids: set[str] = set()
    for deco in getattr(node, "decorator_list", []):
        ids |= _spec_call_ids(deco)
    return ids


def _pytestmark_ids(body: list[ast.stmt]) -> set[str]:
    ids: set[str] = set()
    for stmt in body:
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets):
            ids |= _spec_call_ids(stmt.value)
    return ids


def pytest_collected(root: Path) -> set[str]:
    """Node ids pytest really collects under root/tests (parametrization stripped)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 5):  # 5 = no tests collected
        raise RuntimeError(f"pytest collection failed:\n{proc.stdout[-2000:]}{proc.stderr[-2000:]}")
    return {re.sub(r"\[.*\]$", "", line.strip()) for line in proc.stdout.splitlines() if "::" in line}


def _unpublished(root: Path) -> set[str]:
    """Paths left out of the public tree, checked in the private one."""
    listing = root / "tools/quality/unpublished.txt"
    return set(listing.read_text(encoding="utf-8").split()) if listing.is_file() else set()


def resolve_anchor(anchor: str, root: Path) -> str | None:
    """Error message if `path Symbol.attr` does not resolve, else None."""
    if anchor.startswith(("无：", "无:")) and len(anchor) > 2:
        return None
    parts = anchor.split()
    if len(parts) != 2:
        return f"anchor `{anchor}` must be `<path> <Symbol[.attr]>` or `无：<理由>`"
    path, symbol = root / parts[0], parts[1]
    if not path.is_file() and parts[0] in _unpublished(root):
        return None
    if not path.is_file():
        return f"anchor file {parts[0]} does not exist"
    if path.suffix != ".py":  # scripts/specs (e.g. build_release.ps1 $ReleaseRoot): the symbol must occur verbatim
        return None if symbol in path.read_text(encoding="utf-8") else f"anchor symbol {symbol} not found in {parts[0]}"
    scope: list[ast.stmt] = ast.parse(path.read_text(encoding="utf-8")).body
    for name in symbol.split("."):
        found = next((n for n in scope if _defines(n, name)), None)
        if found is None:
            return f"anchor symbol {symbol} not found in {parts[0]}"
        scope = found.body if isinstance(found, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else []
    return None


def _defines(node: ast.stmt, name: str) -> bool:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    return False


def acceptance_result(spec_id: str, record: Path) -> tuple[str | None, str]:
    """(conclusion recorded for spec_id or None, the record's 候选提交 line)."""
    conclusion = None
    candidate = ""
    for line in record.read_text(encoding="utf-8").splitlines():
        if "候选提交" in line:
            candidate = line
        row = ACCEPT_ROW.match(line.strip())
        if row and row.group(1) == spec_id:
            conclusion = row.group(2)
    return conclusion, candidate


def junit_results(report: Path) -> dict[str, str]:
    """Outcome per test node id ("passed" / "skipped" / "failed"); parametrized cases keep the worst outcome."""
    outcomes: dict[str, str] = {}
    rank = {"passed": 0, "skipped": 1, "failed": 2}
    for case in ET.parse(report).iter("testcase"):
        parts = case.get("classname", "").split(".")
        cls = parts.pop() if parts and parts[-1].startswith("Test") else None
        name = re.sub(r"\[.*\]$", "", case.get("name", ""))
        node = "/".join(parts) + ".py::" + (f"{cls}::" if cls else "") + name
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        if rank[outcome] >= rank[outcomes.get(node, "passed")]:
            outcomes[node] = outcome
    return outcomes


def check(
    paths: Paths,
    release: bool = False,
    junit: Path | None = None,
    candidate: str | None = None,
    collected: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). `collected` overrides the real pytest collection (for tests)."""
    entries, errors = parse_specs(paths.spec)
    warnings: list[str] = []
    nodes, marker_errors = spec_markers(paths.tests, paths.root)
    errors += marker_errors
    referenced = any(NODE.match(i) for e in entries.values() for i in split_items(e.fields.get("验证", "")))
    if referenced:
        actual = collected if collected is not None else pytest_collected(paths.root)
        nodes = {node: ids for node, ids in nodes.items() if node in actual}
    for node, ids in nodes.items():
        errors += [f"{node}: test references unknown spec id {i}" for i in sorted(ids) if i not in entries]
    if release and not entries:
        errors.append("release: docs/spec has no entries")
    if release and (junit is None or not candidate):
        errors.append("release: --junit and --candidate are required")
    outcomes = junit_results(junit) if junit else {}
    for entry in entries.values():
        errors += [f"{entry.location}: {entry.spec_id} {e}" for e in _entry_errors(entry, entries, nodes, paths)]
        if release:
            errors += [
                f"{entry.location}: {entry.spec_id} {e}" for e in _release_errors(entry, outcomes, candidate, paths)
            ]
        if entry.status == "待确认":
            warnings.append(f"{entry.spec_id} is still 待确认")
    return errors, warnings


def _entry_errors(entry: Entry, entries: dict[str, Entry], nodes: dict[str, set[str]], paths: Paths) -> list[str]:
    errs = [f"is missing field '{name}'" for name in REQUIRED if not entry.fields.get(name)]
    status = STATUS.match(entry.status)
    if entry.status and not status:
        errs.append(f"has malformed 状态 `{entry.status}`")
    if status and status.group(2) and status.group(2) not in entries:
        errs.append(f"is replaced by unknown id {status.group(2)}")
    if entry.fields.get("来源") and not QUOTE.search(entry.fields["来源"]):
        errs.append("来源 must quote the original text or link an approval")
    if entry.status.startswith("已废止"):
        return errs
    for name in ("验证", "代码锚点"):
        if entry.fields.get(name) and not split_items(entry.fields[name]):
            errs.append(f"field '{name}' has no items")
    for item in split_items(entry.fields.get("验证", "")):
        errs += _verification_errors(entry, item, nodes, paths)
    for anchor in split_items(entry.fields.get("代码锚点", "")):
        problem = resolve_anchor(anchor, paths.root)
        if problem:
            errs.append(problem)
    return errs


def _acceptance_record(item: str, paths: Paths) -> Path | None:
    record = paths.root / item.removeprefix("acceptance:").strip()
    ok = record.parent == paths.acceptance and record.name != "README.md" and record.is_file()
    return record if ok else None


def _verification_errors(entry: Entry, item: str, nodes: dict[str, set[str]], paths: Paths) -> list[str]:
    if item == FROZEN:
        return [] if entry.status == "待确认" else [f"{FROZEN} is only allowed while 待确认"]
    if item.startswith("acceptance:") and item.endswith(("内部文档", "internal notes")):
        return []  # unpublished acceptance record
    if item.split("::")[0] in _unpublished(paths.root):
        return []
    if item.startswith("acceptance:"):
        record = _acceptance_record(item, paths)
        if record is None:
            return [f"acceptance record {item} must be an existing file in docs/acceptance (not README.md)"]
        conclusion, _ = acceptance_result(entry.spec_id, record)
        return [] if conclusion else [f"acceptance record {record.name} has no table row for {entry.spec_id}"]
    if not NODE.match(item):
        return [f"verification `{item}` is not a test node, acceptance record or {FROZEN}"]
    if item not in nodes:
        return [f"test node {item} does not exist or is not collected by pytest"]
    if entry.spec_id not in nodes[item]:
        return [f'test node {item} lacks @pytest.mark.spec("{entry.spec_id}")']
    return []


def _release_errors(entry: Entry, outcomes: dict[str, str], candidate: str | None, paths: Paths) -> list[str]:
    if not entry.status.startswith("已批准"):
        return []
    items = split_items(entry.fields.get("验证", ""))
    errs = ["is approved but has no executable verification"] if not items or FROZEN in items else []
    for item in items:
        if NODE.match(item) and outcomes.get(item) != "passed":
            errs.append(f"test node {item} did not pass in the JUnit report ({outcomes.get(item, 'not run')})")
        record = _acceptance_record(item, paths) if item.startswith("acceptance:") else None
        if record:
            conclusion, line = acceptance_result(entry.spec_id, record)
            if conclusion != "通过":
                errs.append(f"acceptance {record.name} concludes `{conclusion}` (need 通过)")
            if candidate and candidate not in line:
                errs.append(f"acceptance {record.name} is not for release candidate {candidate}")
    return errs


def main(argv: list[str] | None = None, paths: Paths | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", action="store_true", help="enforce release gate R-6-5")
    parser.add_argument("--junit", type=Path, help="pytest JUnit XML of the release candidate run")
    parser.add_argument("--candidate", help="release candidate commit that acceptance records must name")
    args = parser.parse_args(argv)
    paths = paths or Paths()
    errors, warnings = check(paths, args.release, args.junit, args.candidate)
    entries, _ = parse_specs(paths.spec)
    for line in warnings:
        print(f"note: {line}")
    for line in errors:
        print(f"SPEC FAIL: {line}")
    stage = " (skeleton: no entries yet, R-8-1 not met)" if not entries else ""
    print(f"spec: {len(entries)} entries{stage}, {'FAIL' if errors else 'ok'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
