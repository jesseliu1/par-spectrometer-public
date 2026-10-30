"""tools/quality/ratchet.py enforces R-1-2/R-1-3: legacy debt may only shrink."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "quality"))

import ratchet  # noqa: E402

pytestmark = pytest.mark.unit

LONG_BODY = "".join(f"    x{i} = {i}\n" for i in range(70))


def _empty() -> dict:
    return {"long_files": {}, "long_functions": {}, "ruff": {}, "unformatted": []}


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ratchet, "ROOT", tmp_path)
    monkeypatch.setattr(ratchet, "BASELINE", tmp_path / "baseline.json")
    return tmp_path


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_compare_blocks_growth_new_debt_and_unformatted_files() -> None:
    base = {"long_files": {"a.py": 700}, "long_functions": {}, "ruff": {"a.py": {"E702": 3}}, "unformatted": ["a.py"]}
    now = {
        "long_files": {"a.py": 710, "b.py": 650},
        "long_functions": {"b.py::f": 80},
        "ruff": {"a.py": {"E702": 2, "F401": 1}},
        "unformatted": ["a.py", "b.py"],
    }
    errors, improved = ratchet.compare(base, now)
    joined = "\n".join(errors)
    assert "a.py: grew from 700 to 710" in joined
    assert "b.py: 650 lines exceeds" in joined
    assert "b.py::f: 80 lines exceeds" in joined
    assert "ruff F401 0 -> 1" in joined
    assert "b.py: not ruff-formatted" in joined
    assert any("E702 reduced" in line for line in improved)


def test_compare_accepts_shrinking_debt() -> None:
    base = {"long_files": {"a.py": 700}, "long_functions": {"a.py::f": 90}, "ruff": {}, "unformatted": []}
    now = {"long_files": {}, "long_functions": {"a.py::f": 70}, "ruff": {}, "unformatted": []}
    errors, improved = ratchet.compare(base, now)
    assert errors == []
    assert "a.py: now within limit" in improved
    assert "a.py::f: 90 -> 70 lines" in improved


def test_long_functions_include_definitions_nested_in_blocks(tree: Path) -> None:
    source = "if True:\n    def hidden():\n" + LONG_BODY.replace("    ", "        ") + "class K:\n    def big(self):\n"
    source += LONG_BODY.replace("    ", "        ") + "\ndef small():\n    return 1\n"
    path = _write(tree, "m.py", source)
    assert ratchet.long_functions([path]) == {"m.py::hidden": 71, "m.py::K.big": 71}


def test_ui_slots_use_the_40_line_limit(tree: Path) -> None:
    body45 = "".join(f"        y{i} = {i}\n" for i in range(45))
    source = (
        "class Page:\n"
        "    def __init__(self, button):\n        button.clicked.connect(self.save)\n"
        f"    def save(self):\n{body45}"
        f"    def _on_change(self):\n{body45}"
        f"    @Slot()\n    def apply(self):\n{body45}"
        f"    def helper(self):\n{body45}"
    )
    ui = _write(tree, "par_app/ui_page.py", source)
    other = _write(tree, "par_app/math_x.py", source)
    found = ratchet.long_functions([ui, other])
    assert set(found) == {
        "par_app/ui_page.py::Page.save",
        "par_app/ui_page.py::Page._on_change",
        "par_app/ui_page.py::Page.apply",
    }


def test_file_lengths_and_python_files(tree: Path) -> None:
    _write(tree, "par_app/big.py", "x = 2\n" * 601)
    _write(tree, "par_app/__pycache__/junk.py", "")
    _write(tree, "verify_demo.py", "y = 3\n")
    files = ratchet.python_files()
    assert {ratchet.rel(f) for f in files} == {"par_app/big.py", "verify_demo.py"}
    assert ratchet.file_lengths(files) == {"par_app/big.py": 601}


def test_ruff_counts_and_unformatted_run_real_ruff(tree: Path) -> None:
    bad = _write(tree, "bad.py", "import os\nx=1;y=2\n")
    good = _write(tree, "good.py", "x = 1\n")
    counts = ratchet.ruff_counts([bad, good])
    assert counts["bad.py"]["F401"] == 1
    assert "good.py" not in counts
    assert ratchet.unformatted([bad, good]) == ["bad.py"]


def test_unformatted_rejects_unparseable_ruff_output(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = subprocess.CompletedProcess(args=[], returncode=2, stdout="something odd", stderr="")
    monkeypatch.setattr(ratchet.subprocess, "run", lambda *a, **k: fake)
    with pytest.raises(RuntimeError, match="cannot parse"):
        ratchet.unformatted([])


def test_main_init_update_and_check(tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    state = {"now": {**_empty(), "long_files": {"a.py": 700}}}
    monkeypatch.setattr(ratchet, "measure", lambda: state["now"])
    assert ratchet.main(["--init"]) == 0
    assert ratchet.main(["--init"]) == 1  # never silently re-create
    assert ratchet.main([]) == 0
    state["now"] = {**_empty(), "long_files": {"a.py": 999}}
    assert ratchet.main([]) == 1
    assert ratchet.main(["--update"]) == 1  # growth cannot be approved by --update
    assert json.loads(ratchet.BASELINE.read_text())["long_files"] == {"a.py": 700}
    state["now"] = {**_empty(), "long_files": {"a.py": 650}}
    assert ratchet.main([]) == 0
    assert "--update" in capsys.readouterr().out
    assert ratchet.main(["--update"]) == 0
    assert json.loads(ratchet.BASELINE.read_text())["long_files"] == {"a.py": 650}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_against_ref_rejects_growth_and_loosened_baseline_file(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratchet, "BASELINE_GIT_PATH", "baseline.json")
    _git(tree, "init", "-q", "-b", "main")
    _git(tree, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "root")
    assert ratchet.baseline_at("main") is None
    monkeypatch.setattr(ratchet, "measure", lambda: {**_empty(), "long_files": {"a.py": 700}})
    ratchet.BASELINE.write_text(json.dumps({**_empty(), "long_files": {"a.py": 700}}))
    assert ratchet.main(["--against", "main"]) == 0  # target predates the ratchet: falls back to file
    _git(tree, "add", "baseline.json")
    _git(tree, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "baseline")
    assert ratchet.baseline_at("main") == {**_empty(), "long_files": {"a.py": 700}}
    assert ratchet.main(["--against", "main"]) == 0
    ratchet.BASELINE.write_text(json.dumps({**_empty(), "long_files": {"a.py": 999}}))
    monkeypatch.setattr(ratchet, "measure", lambda: {**_empty(), "long_files": {"a.py": 999}})
    assert ratchet.main([]) == 0  # the PR's own baseline would accept it ...
    assert ratchet.main(["--against", "main"]) == 1  # ... the target branch baseline does not


def test_measure_reports_all_sections(tree: Path) -> None:
    _write(tree, "par_app/a.py", "x = 1\n")
    result = ratchet.measure()
    assert set(result) >= {"long_files", "long_functions", "ruff", "unformatted", "slot_limit"}


def test_against_unknown_ref_or_git_failure_fails_closed(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratchet, "BASELINE_GIT_PATH", "baseline.json")
    _git(tree, "init", "-q", "-b", "main")
    _git(tree, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "root")
    monkeypatch.setattr(ratchet, "measure", _empty)
    ratchet.BASELINE.write_text(json.dumps(_empty()))
    with pytest.raises(RuntimeError, match="cannot resolve"):
        ratchet.baseline_at("refs/heads/review-nonexistent-ref")
    assert ratchet.main(["--against", "refs/heads/review-nonexistent-ref"]) == 1
    failing = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal: boom")
    real = ratchet._git
    monkeypatch.setattr(ratchet, "_git", lambda *a: real(*a) if a[0] == "rev-parse" else failing)
    with pytest.raises(RuntimeError, match="ls-tree failed"):
        ratchet.baseline_at("main")
