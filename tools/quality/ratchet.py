"""Quality ratchet (R-1-2, R-1-3): legacy debt may shrink but never grow.

Checks, per Python file in scope:
  * file length: files over FILE_LIMIT lines must be baselined and may not grow;
  * function length: functions over FUNC_LIMIT lines (Qt slots in UI modules: SLOT_LIMIT) must be
    baselined and may not grow. Functions nested in any block (if/try/with/class) are included;
  * ruff lint: per-file, per-rule violation counts may not exceed the baseline (new files: zero);
  * ruff format: files not baselined as legacy-unformatted must be formatted.

Usage:
  python tools/quality/ratchet.py                      # check against tools/quality/baseline.json
  python tools/quality/ratchet.py --against origin/main  # CI: check code AND this PR's baseline file
                                                       #     against the baseline on the target branch
  python tools/quality/ratchet.py --update              # lock in reduced debt; refuses any growth
  python tools/quality/ratchet.py --init                # one-off: create the baseline if none exists
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("baseline.json")
BASELINE_GIT_PATH = "tools/quality/baseline.json"
SCOPE = ("par_app", "par_shell", "tools", "tests", "main.py", "main_v2.py", "package_release.py")
FILE_LIMIT = 600
FUNC_LIMIT = 60
SLOT_LIMIT = 40
UI_MODULE = re.compile(r"^par_app/(ui(/.*)?|ui_[^/]*|[^/]*dialog[^/]*)\.py$|^par_app/ui/")


def python_files() -> list[Path]:
    files: list[Path] = []
    for entry in SCOPE:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
    files.extend(sorted(ROOT.glob("verify_*.py")))
    return [f for f in files if "__pycache__" not in f.parts]


def rel(path: Path | str) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def file_lengths(files: list[Path]) -> dict[str, int]:
    lengths = {}
    for f in files:
        count = len(f.read_text(encoding="utf-8").splitlines())
        if count > FILE_LIMIT:
            lengths[rel(f)] = count
    return lengths


def long_functions(files: list[Path]) -> dict[str, int]:
    """Functions longer than their limit, keyed "file::Qualified.name" (value: length in lines)."""
    result: dict[str, int] = {}
    for f in files:
        name = rel(f)
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        is_ui = bool(UI_MODULE.search(name))
        slots = _slot_names(tree) if is_ui else set()
        for qualname, node in _definitions(tree, ""):
            is_slot = is_ui and (node.name in slots or _is_slot(node))
            limit = SLOT_LIMIT if is_slot else FUNC_LIMIT
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > limit:
                result[f"{name}::{qualname}"] = length
    return result


def _definitions(node: ast.AST, prefix: str) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """All function definitions below node, at any depth, with dotted qualified names."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append((f"{prefix}{child.name}", child))
            found.extend(_definitions(child, f"{prefix}{child.name}."))
        elif isinstance(child, ast.ClassDef):
            found.extend(_definitions(child, f"{prefix}{child.name}."))
        else:
            found.extend(_definitions(child, prefix))
    return found


def _is_slot(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.name.startswith(("on_", "_on_")):
        return True
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name.endswith("Slot"):
            return True
    return False


def _slot_names(tree: ast.AST) -> set[str]:
    """Methods connected as signal handlers in this module: `<signal>.connect(self.<name>)`."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
            for arg in node.args:
                if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "self":
                    names.add(arg.attr)
    return names


def ruff_counts(files: list[Path]) -> dict[str, dict[str, int]]:
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format", "json", "--exit-zero", *map(str, files)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    counts: dict[str, Counter[str]] = {}
    for item in json.loads(proc.stdout or "[]"):
        counts.setdefault(rel(item["filename"]), Counter())[item["code"] or "syntax"] += 1
    return {name: dict(sorted(c.items())) for name, c in sorted(counts.items())}


def unformatted(files: list[Path]) -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", *map(str, files)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # Older ruff prints "Would reformat: <path>", newer prints a diagnostic with "--> <path>:<line>:<col>".
    found = set(re.findall(r"^Would reformat: (.+)$", proc.stdout + proc.stderr, re.M))
    found.update(re.findall(r"^\s*-->\s+(.+?):\d+:\d+", proc.stdout + proc.stderr, re.M))
    if proc.returncode != 0 and not found:
        raise RuntimeError(f"cannot parse `ruff format --check` output:\n{proc.stdout}{proc.stderr}")
    return sorted({rel(ROOT / name) for name in found})


def measure() -> dict:
    files = python_files()
    return {
        "file_limit": FILE_LIMIT,
        "function_limit": FUNC_LIMIT,
        "slot_limit": SLOT_LIMIT,
        "long_files": file_lengths(files),
        "long_functions": long_functions(files),
        "ruff": ruff_counts(files),
        "unformatted": unformatted(files),
    }


def compare(base: dict, now: dict) -> tuple[list[str], list[str]]:
    """Errors where `now` has more debt than `base`, and notes where it has less."""
    errors: list[str] = []
    improved: list[str] = []
    for kind in ("long_files", "long_functions"):
        for name, size in now[kind].items():
            old = base[kind].get(name)
            if old is None:
                errors.append(f"{name}: {size} lines exceeds its limit (new debt)")
            elif size > old:
                errors.append(f"{name}: grew from {old} to {size} lines (baselined debt may only shrink)")
            elif size < old:
                improved.append(f"{name}: {old} -> {size} lines")
        improved.extend(f"{name}: now within limit" for name in base[kind] if name not in now[kind])
    for name, codes in now["ruff"].items():
        old_codes = base["ruff"].get(name, {})
        for code, count in codes.items():
            if count > old_codes.get(code, 0):
                errors.append(f"{name}: ruff {code} {old_codes.get(code, 0)} -> {count}")
    for name, codes in base["ruff"].items():
        for code, count in codes.items():
            if now["ruff"].get(name, {}).get(code, 0) < count:
                improved.append(f"{name}: ruff {code} reduced")
    for name in now["unformatted"]:
        if name not in base["unformatted"]:
            errors.append(f"{name}: not ruff-formatted (run `ruff format {name}`)")
    return errors, improved


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def baseline_at(ref: str) -> dict | None:
    """Baseline committed at a git ref; None only when that valid commit has no baseline file yet.

    Raises RuntimeError when the ref does not resolve or git fails, so a typo or missing fetch can never
    silently downgrade the check to the PR's own baseline.
    """
    commit = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if commit.returncode != 0:
        raise RuntimeError(f"cannot resolve git ref {ref!r}: {commit.stderr.strip() or 'unknown ref'}")
    sha = commit.stdout.strip()
    listing = _git("ls-tree", "--name-only", sha, "--", BASELINE_GIT_PATH)
    if listing.returncode != 0:
        raise RuntimeError(f"git ls-tree failed for {ref}: {listing.stderr.strip()}")
    if not listing.stdout.strip():
        return None
    shown = _git("show", f"{sha}:{BASELINE_GIT_PATH}")
    if shown.returncode != 0:
        raise RuntimeError(f"git show failed for {ref}: {shown.stderr.strip()}")
    return json.loads(shown.stdout)


def report(errors: list[str], improved: list[str], hint: bool) -> int:
    for line in improved:
        print(f"improved: {line}")
    if improved and hint:
        print("debt went down; run `python tools/quality/ratchet.py --update` in this PR to lock it in")
    for line in errors:
        print(f"RATCHET FAIL: {line}")
    if not errors:
        print("ratchet: ok")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="lock in reduced debt (refuses any growth)")
    mode.add_argument("--init", action="store_true", help="create the baseline when none exists")
    mode.add_argument("--against", metavar="REF", help="compare with the baseline committed at a git ref")
    args = parser.parse_args(argv)
    now = measure()
    if args.init:
        if BASELINE.exists():
            print(f"RATCHET FAIL: {rel(BASELINE)} already exists; use --update to lock in improvements")
            return 1
        BASELINE.write_text(json.dumps(now, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"baseline created: {rel(BASELINE)}")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    if args.update:
        errors, improved = compare(base, now)
        if errors:
            print("refusing to update the baseline: it may only shrink")
            return report(errors, improved, hint=False)
        BASELINE.write_text(json.dumps(now, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"baseline updated: {rel(BASELINE)} ({len(improved)} improvements locked in)")
        return 0
    if args.against:
        try:
            target = baseline_at(args.against)
        except RuntimeError as exc:
            print(f"RATCHET FAIL: {exc}")
            return 1
        if target is None:
            print(f"{args.against} has no baseline yet (ratchet introduced by this change); checking the PR baseline")
            errors, improved = compare(base, now)
            return report(errors, improved, hint=True)
        errors, improved = compare(target, now)
        loosened, _ = compare(target, base)
        errors.extend(f"baseline file loosened vs {args.against}: {line}" for line in loosened)
        return report(errors, improved, hint=True)
    errors, improved = compare(base, now)
    return report(errors, improved, hint=True)


if __name__ == "__main__":
    raise SystemExit(main())
