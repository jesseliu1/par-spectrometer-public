"""tools/quality/spec_check.py: three-way spec/test/code mapping and the release gate (R-2-4, R-6-5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "quality"))

import spec_check  # noqa: E402
from spec_check import Paths  # noqa: E402

pytestmark = pytest.mark.unit

GOOD = """### ACQ-001 恢复未确认时锁定所有设备
- 规则：恢复未确认时锁定所有设备。
- 来源：变更日志「统一冻结读取」"恢复命令或运行状态未确认时……"
- 状态：已批准 2026-10-20 负责人
- 验证：tests/unit/test_x.py::test_lock；acceptance:docs/acceptance/2026-10-21_run.md
- 代码锚点：par_app/core.py Coordinator.halt
"""
TEST = """import pytest


@pytest.mark.spec(
    "ACQ-001",
)
def test_lock() -> None:
    pass
"""
ACCEPTANCE = (
    "# 验收\n- 候选提交 / 测试包：abc123\n\n"
    "| 规格编号 | 步骤 | 期望 | 实际 | 结论 |\n|---|---|---|---|---|\n| ACQ-001 | a | b | c | 通过 |\n"
)
CORE = "class Coordinator:\n    def halt(self) -> None:\n        pass\n"
JUNIT_PASS = '<testsuite><testcase classname="tests.unit.test_x" name="test_lock"/></testsuite>'
JUNIT_FAIL = '<testsuite><testcase classname="tests.unit.test_x" name="test_lock"><failure/></testcase></testsuite>'


def _repo(tmp_path: Path, spec: str = GOOD, test: str = TEST, extra: dict[str, str] | None = None) -> Paths:
    files = {
        "docs/spec/acq.md": spec,
        "docs/spec/README.md": "### ACQ-999 模板示例\n",
        "docs/acceptance/README.md": "| ACQ-001 | x | y | z | 通过 |\n",
        "docs/acceptance/2026-10-21_run.md": ACCEPTANCE,
        "tests/unit/test_x.py": test,
        "par_app/core.py": CORE,
        **(extra or {}),
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Paths(tmp_path)


def _errors(paths: Paths, release: bool = False, junit: Path | None = None, candidate: str | None = None) -> str:
    return "\n".join(spec_check.check(paths, release, junit, candidate)[0])


def test_well_formed_entry_passes_and_readme_examples_are_ignored(tmp_path: Path) -> None:
    paths = _repo(tmp_path)
    errors, warnings = spec_check.check(paths)
    assert errors == [] and warnings == []
    entries, _ = spec_check.parse_specs(paths.spec)
    assert set(entries) == {"ACQ-001"}


def test_missing_test_node_and_missing_anchor_fail(tmp_path: Path) -> None:
    spec = GOOD.replace("test_x.py::test_lock", "test_absent.py::test_missing").replace("core.py", "gone.py")
    out = _errors(_repo(tmp_path, spec=spec))
    assert "test node tests/unit/test_absent.py::test_missing does not exist" in out
    assert "anchor file par_app/gone.py does not exist" in out


def test_anchor_symbol_must_resolve(tmp_path: Path) -> None:
    out = _errors(_repo(tmp_path, spec=GOOD.replace("Coordinator.halt", "Coordinator.resume")))
    assert "anchor symbol Coordinator.resume not found" in out
    out = _errors(_repo(tmp_path / "b", spec=GOOD.replace("par_app/core.py Coordinator.halt", "随便写")))
    assert "must be `<path> <Symbol[.attr]>`" in out
    assert _errors(_repo(tmp_path / "c", spec=GOOD.replace("par_app/core.py Coordinator.halt", "无：纯视觉"))) == ""


def test_marker_on_non_collectable_function_does_not_count(tmp_path: Path) -> None:
    nested = (
        "import pytest\n\n\ndef helper() -> None:\n"
        "    @pytest.mark.spec('ACQ-001')\n    def test_lock() -> None:\n        pass\n"
    )
    out = _errors(_repo(tmp_path, test=nested))
    assert "spec marker on non-collectable `test_lock`" in out
    assert "test node tests/unit/test_x.py::test_lock does not exist" in out


def test_marker_in_non_test_file_and_unknown_ids_fail(tmp_path: Path) -> None:
    extra = {"tests/unit/helpers.py": TEST, "tests/unit/test_y.py": TEST.replace("ACQ-001", "DLI-404")}
    out = _errors(_repo(tmp_path, extra=extra))
    assert "tests/unit/helpers.py: spec markers in a file pytest does not collect" in out
    assert "test references unknown spec id DLI-404" in out


def test_test_without_matching_marker_fails(tmp_path: Path) -> None:
    out = _errors(_repo(tmp_path, test="def test_lock() -> None:\n    pass\n"))
    assert 'lacks @pytest.mark.spec("ACQ-001")' in out


def test_class_and_module_level_markers_are_recognised(tmp_path: Path) -> None:
    test = (
        "import pytest\n\npytestmark = pytest.mark.spec('ACQ-001')\n\n\n"
        "class TestLock:\n    def test_lock(self) -> None:\n        pass\n"
    )
    paths = _repo(tmp_path, spec=GOOD.replace("test_x.py::test_lock", "test_x.py::TestLock::test_lock"), test=test)
    assert _errors(paths) == ""


def test_field_format_rules(tmp_path: Path) -> None:
    spec = (
        GOOD.replace("已批准 2026-10-20 负责人", "批准了")
        .replace('"恢复命令或运行状态未确认时……"', "原文略")
        .replace("- 代码锚点：par_app/core.py Coordinator.halt\n", "")
    )
    spec += "\n### ACQ-001 重复\n- 状态：待确认\n"
    out = _errors(_repo(tmp_path, spec=spec))
    assert "malformed 状态" in out
    assert "来源 must quote" in out
    assert "missing field '代码锚点'" in out
    assert "duplicate id ACQ-001" in out


def test_frozen_only_while_pending_and_deprecation_needs_known_replacement(tmp_path: Path) -> None:
    frozen = GOOD.replace("tests/unit/test_x.py::test_lock；acceptance:docs/acceptance/2026-10-21_run.md", "冻结待确认")
    assert "only allowed while 待确认" in _errors(_repo(tmp_path, spec=frozen))
    pending = frozen.replace("已批准 2026-10-20 负责人", "待确认")
    paths = _repo(tmp_path / "b", spec=pending)
    errors, warnings = spec_check.check(paths)
    assert errors == [] and warnings == ["ACQ-001 is still 待确认"]
    gone = GOOD.replace("已批准 2026-10-20 负责人", "已废止 2026-10-22，由 ACQ-777 替代")
    assert "replaced by unknown id ACQ-777" in _errors(_repo(tmp_path / "c", spec=gone))


def test_acceptance_records_must_be_real_files_with_a_row(tmp_path: Path) -> None:
    readme = GOOD.replace("2026-10-21_run.md", "README.md")
    assert "must be an existing file in docs/acceptance" in _errors(_repo(tmp_path, spec=readme))
    norow = _repo(tmp_path / "b", extra={"docs/acceptance/2026-10-21_run.md": "# 空记录\n"})
    assert "has no table row for ACQ-001" in _errors(norow)
    weird = GOOD.replace("tests/unit/test_x.py::test_lock", "看过了")
    assert "is not a test node" in _errors(_repo(tmp_path / "c", spec=weird))


def test_release_requires_entries_junit_and_candidate(tmp_path: Path) -> None:
    empty = _repo(tmp_path, spec="# 空\n", test="def test_lock() -> None:\n    pass\n")
    out = _errors(empty, release=True)
    assert "docs/spec has no entries" in out and "--junit and --candidate are required" in out


def test_release_requires_passing_tests_and_matching_acceptance(tmp_path: Path) -> None:
    paths = _repo(tmp_path)
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_PASS)
    assert _errors(paths, release=True, junit=junit, candidate="abc123") == ""
    assert "is not for release candidate def456" in _errors(paths, release=True, junit=junit, candidate="def456")
    junit.write_text(JUNIT_FAIL)
    assert "did not pass in the JUnit report (failed)" in _errors(paths, release=True, junit=junit, candidate="abc123")
    junit.write_text("<testsuite/>")
    assert "(not run)" in _errors(paths, release=True, junit=junit, candidate="abc123")
    failed_acceptance = ACCEPTANCE.replace("| 通过 |", "| 失败 |")
    paths = _repo(tmp_path / "b", extra={"docs/acceptance/2026-10-21_run.md": failed_acceptance})
    junit.write_text(JUNIT_PASS)
    assert "concludes `失败`" in _errors(paths, release=True, junit=junit, candidate="abc123")


def test_release_rejects_approved_entry_without_executable_verification(tmp_path: Path) -> None:
    spec = GOOD.replace("tests/unit/test_x.py::test_lock；acceptance:docs/acceptance/2026-10-21_run.md", "冻结待确认")
    junit = tmp_path / "j.xml"
    junit.write_text("<testsuite/>")
    out = _errors(_repo(tmp_path, spec=spec), release=True, junit=junit, candidate="abc123")
    assert "approved but has no executable verification" in out


def test_junit_merges_parametrized_cases_and_classes(tmp_path: Path) -> None:
    report = tmp_path / "r.xml"
    report.write_text(
        "<testsuite>"
        '<testcase classname="tests.unit.test_x" name="test_p[a]"/>'
        '<testcase classname="tests.unit.test_x" name="test_p[b]"><skipped/></testcase>'
        '<testcase classname="tests.unit.test_x.TestK" name="test_m"><error/></testcase>'
        "</testsuite>"
    )
    assert spec_check.junit_results(report) == {
        "tests/unit/test_x.py::test_p": "skipped",
        "tests/unit/test_x.py::TestK::test_m": "failed",
    }


def test_main_reports_skeleton_state(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    paths = _repo(tmp_path, spec="# 空\n", test="def test_lock() -> None:\n    pass\n")
    assert spec_check.main([], paths) == 0
    assert "skeleton: no entries yet, R-8-1 not met" in capsys.readouterr().out
    assert spec_check.main(["--release"], paths) == 1
    assert "SPEC FAIL" in capsys.readouterr().out
    pending = _repo(tmp_path / "b", spec=GOOD.replace("已批准 2026-10-20 负责人", "待确认"))
    assert spec_check.main([], pending) == 0
    assert "note: ACQ-001 is still 待确认" in capsys.readouterr().out


def test_node_must_be_collected_by_real_pytest(tmp_path: Path) -> None:
    hidden = TEST + "\n\ntest_lock.__test__ = False\n"
    paths = _repo(tmp_path, test=hidden)
    out = _errors(paths)
    assert "not collected by pytest" in out
    assert spec_check.pytest_collected(_repo(tmp_path / "b").root) >= {"tests/unit/test_x.py::test_lock"}


def test_separator_only_fields_are_rejected(tmp_path: Path) -> None:
    spec = GOOD.replace("tests/unit/test_x.py::test_lock；acceptance:docs/acceptance/2026-10-21_run.md", "；")
    spec = spec.replace("par_app/core.py Coordinator.halt", "；")
    out = _errors(_repo(tmp_path, spec=spec))
    assert "field '验证' has no items" in out and "field '代码锚点' has no items" in out


def test_collection_failure_is_reported(tmp_path: Path) -> None:
    paths = _repo(tmp_path, test="import nonexistent_module_xyz\n\ndef test_lock() -> None:\n    pass\n")
    with pytest.raises(RuntimeError, match="pytest collection failed"):
        spec_check.check(paths)


def test_non_python_anchor_is_matched_textually(tmp_path: Path) -> None:
    extra = {"build_release.ps1": "$ReleaseRoot = 1\n"}
    ok = GOOD.replace("par_app/core.py Coordinator.halt", "build_release.ps1 $ReleaseRoot")
    assert _errors(_repo(tmp_path, spec=ok, extra=extra)) == ""
    bad = GOOD.replace("par_app/core.py Coordinator.halt", "build_release.ps1 $Missing")
    assert "anchor symbol $Missing not found" in _errors(_repo(tmp_path / "b", spec=bad, extra=extra))
