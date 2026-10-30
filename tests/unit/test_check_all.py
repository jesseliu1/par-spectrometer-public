"""tools/quality/check_all.py runs every gate and propagates failures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "quality"))

import check_all  # noqa: E402

pytestmark = pytest.mark.unit


def _record(monkeypatch: pytest.MonkeyPatch, fail: str | None = None) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        calls.append(args + [f"{key}={value}" for key, value in (env or {}).items() if key.startswith("PAR_TEST_")])
        failed = fail is not None and any(fail in part for part in args)
        return subprocess.CompletedProcess(args, 1 if failed else 0)

    monkeypatch.setattr(check_all.subprocess, "run", fake_run)
    return calls


def test_static_mode_runs_all_static_gates_without_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--static"])
    assert check_all.main() == 0
    joined = [" ".join(c) for c in calls]
    assert any("ratchet.py" in c for c in joined)
    assert any("lint_imports_command" in c for c in joined)
    assert any("spec_check.py" in c for c in joined)
    assert any("shadow_rules.py --check" in c for c in joined)
    assert not any("pytest" in c for c in joined)


def test_full_mode_adds_tests_and_mypy_when_typed_packages_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "par_app" / "domain").mkdir(parents=True)
    monkeypatch.setattr(check_all, "ROOT", tmp_path)
    calls = _record(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["check_all.py"])
    assert check_all.main() == 0
    joined = [" ".join(c) for c in calls]
    assert any("mypy par_app/domain" in c for c in joined)
    tests = [c for c in joined if "pytest -m not hardware" in c]
    assert [c.rsplit(" ", 1)[-1] for c in tests] == ["PAR_TEST_QT_BINDING=PySide6"]


def test_any_failing_gate_fails_the_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    _record(monkeypatch, fail="spec_check.py")
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--static"])
    assert check_all.main() == 1
    assert "FAILED: spec traceability" in capsys.readouterr().out


def _tools(monkeypatch: pytest.MonkeyPatch, present: set[str]) -> None:
    monkeypatch.setattr(check_all.shutil, "which", lambda name: f"/bin/{name}" if name in present else None)


def test_the_web_colour_token_check_runs_whenever_node_is_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review M-3: the R-1-5 token check is part of check_all, not only of a manual `npm run check`."""
    calls = _record(monkeypatch)
    _tools(monkeypatch, {"node"})
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--static"])
    assert check_all.main() == 0
    assert ["/bin/node", "web/scripts/check-tokens.mjs"] in calls


def test_full_mode_runs_the_web_tests_once_web_dependencies_are_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "web" / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(check_all, "ROOT", tmp_path)
    calls = _record(monkeypatch)
    _tools(monkeypatch, {"node", "npm"})
    monkeypatch.setattr(sys, "argv", ["check_all.py"])
    assert check_all.main() == 0
    assert ["/bin/npm", "--prefix", "web", "run", "test"] in calls


def test_without_node_the_web_checks_are_reported_as_skipped(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    calls = _record(monkeypatch)
    _tools(monkeypatch, set())
    monkeypatch.setattr(sys, "argv", ["check_all.py"])
    assert check_all.main() == 0
    out = capsys.readouterr().out
    assert "web colour tokens: SKIPPED" in out
    assert "web tests: SKIPPED" in out
    assert not any("check-tokens.mjs" in " ".join(c) for c in calls)


def test_the_pyside6_only_regression_skips_the_pyqt5_ui_round_but_no_other_test(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--binding PySide6 (Windows packaging guide, section 三; review rv-68c major 1): static gates, the web
    checks, every Qt-independent test (the `unit` marker, wherever it is, e.g. tests/unit/test_alpha_runtime.py) and
    the whole PySide6 session; only the PyQt5 round of V1.0.3's Qt tests is left out."""
    (tmp_path / "par_app" / "domain").mkdir(parents=True)
    (tmp_path / "web" / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(check_all, "ROOT", tmp_path)
    _tools(monkeypatch, {"node", "npm"})
    calls = _record(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--binding", "PySide6"])
    assert check_all.main() == 0
    joined = [" ".join(c) for c in calls]
    assert any("ratchet.py" in c for c in joined) and any("mypy par_app/domain" in c for c in joined)
    assert ["/bin/node", "web/scripts/check-tokens.mjs"] in calls
    assert any("--prefix web run test" in c for c in joined)
    tests = [c for c in joined if " -m pytest " in c]
    assert tests == [
        f"{sys.executable} -m pytest -m unit and not hardware PAR_TEST_QT_BINDING=PyQt5",
        f"{sys.executable} -m pytest -m not hardware PAR_TEST_QT_BINDING=PySide6",
    ]


def test_binding_and_static_do_not_mix(monkeypatch: pytest.MonkeyPatch) -> None:
    _record(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["check_all.py", "--static", "--binding", "PySide6"])
    with pytest.raises(SystemExit):
        check_all.main()
