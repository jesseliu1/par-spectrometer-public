"""Structural guards for rules that tools cannot infer on their own (R-1-1, R-1-3, R-3-1)."""

from __future__ import annotations

import os
import tempfile
import time
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def _contracts() -> list[dict]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return config["tool"]["importlinter"]["contracts"]


def test_every_par_app_subpackage_is_bound_by_an_import_contract() -> None:
    covered = {m for c in _contracts() for m in c.get("source_modules", [])}
    packages = [p.parent for p in (ROOT / "par_app").rglob("__init__.py") if p.parent != ROOT / "par_app"]
    missing = [
        ".".join(p.relative_to(ROOT).parts)
        for p in packages
        if not any(".".join(p.relative_to(ROOT).parts).startswith(m) for m in covered)
    ]
    assert missing == [], f"add these packages to an import-linter contract in pyproject.toml: {missing}"


def test_domain_contract_forbids_every_qt_binding() -> None:
    domain = next(c for c in _contracts() if c["name"].startswith("Domain modules"))
    assert {"PyQt5", "PyQt6", "PySide2", "PySide6"} <= set(domain["forbidden_modules"])


def test_test_environment_is_pinned() -> None:
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert Path(tempfile.gettempdir()) == Path(tempfile.gettempdir()).resolve()
    if hasattr(time, "tzset"):
        assert os.environ["TZ"] == "Asia/Shanghai"


def test_acquisition_host_imports_no_widgets() -> None:
    """16_ 1.6: the takeover runs under QCoreApplication; QtWidgets/QtGui would need a GUI platform plugin. 18_: the
    alpha's Qt names come from par_app.qt_compat only, never from a binding directly."""
    import ast

    forbidden = ("PyQt5", "PySide6", "shiboken6")
    alpha = [ROOT / "par_app" / name for name in ("service_main.py", "alpha_self_test_bus.py", "qt_compat.py")]
    for path in [*(ROOT / "par_app" / "acquisition_host").glob("*.py"), *alpha[:2]]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            names += [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not [n for n in names if n.startswith(forbidden)], f"{path.name} imports {names}"
    compat = ast.parse(alpha[2].read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(compat) if isinstance(node, ast.ImportFrom)}
    assert {m for m in modules if m and m.startswith(("PyQt5", "PySide6"))} == {"PyQt5.QtCore", "PySide6.QtCore"}


def test_api_reaches_services_only_through_the_application_layer() -> None:
    """Route C section 4: the API calls the application layer only. The other API contracts allowed a direct
    `par_app.api -> par_app.services` import (review of PR #51, M-4); this one forbids it."""
    contract = next(
        c for c in _contracts() if c["name"] == "API layer reaches services only through the application layer"
    )
    assert contract["source_modules"] == ["par_app.api"]
    assert "par_app.services" in contract["forbidden_modules"]


def _private_reads(path: Path) -> list[str]:
    import ast

    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Attribute) or not node.attr.startswith("_") or node.attr.startswith("__"):
            continue
        if isinstance(node.value, ast.Name) and node.value.id in ("self", "cls"):
            continue
        found.append(f"{path.name}:{node.lineno} .{node.attr}")
    return found


def test_only_v1_reads_touches_private_fields() -> None:
    """17_ 1.4 / 3.1: V1.0.3's private coordinator and session fields are read in v1_reads.py only (read-only)."""
    found = [
        item
        for path in (ROOT / "par_app" / "acquisition_host").glob("*.py")
        if path.name != "v1_reads.py"
        for item in _private_reads(path)
    ]
    assert found == []


COORDINATOR_CALLS = {
    "queue_task",
    "enter_maintenance",
    "leave_maintenance",
    "halt_reason",
    "bus_message",
    "states",
    "state",
}
"""17_ 3.2: the maintenance modules change the coordinator only through these three calls; the others only read."""


def test_maintenance_calls_only_the_whitelisted_coordinator_methods() -> None:
    import ast

    for path in (ROOT / "par_app" / "acquisition_host").glob("maintenance_*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            owner = node.func.value
            name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
            if name == "coordinator":
                assert node.func.attr in COORDINATOR_CALLS, f"{path.name}:{node.lineno} coordinator.{node.func.attr}"


COORDINATOR_READS = {"bus_message", "halt_reason", "state", "states", "status_text", "database"}
"""Public PollingCoordinator methods that only read."""
COORDINATOR_CHANGES_ALLOWED = {
    "maintenance_host.py": {"queue_task", "enter_maintenance", "leave_maintenance"},
    "host.py": {"stop"},
    "faults.py": {"stop"},
}
"""Per file of par_app/acquisition_host: the coordinator methods that change something it may name (17_ 3.2).
faults.py names `stop` for AcquisitionHost.stop, the takeover stop POST /shutdown runs (D-225 item 1)."""


def test_coordinator_changes_are_named_only_where_allowed() -> None:
    """Review N3: any reference to a changing PollingCoordinator method (whatever the receiver is called, called or
    only taken as an alias) appears only in the file allowed to make it; host.py and v1_reads.py are covered too."""
    import ast

    source = ast.parse((ROOT / "par_app" / "coordinator.py").read_text(encoding="utf-8"))
    coordinator = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "PollingCoordinator")
    public = {n.name for n in coordinator.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    changes = public - COORDINATOR_READS
    assert {"queue_task", "enter_maintenance", "leave_maintenance", "apply_config", "pause_polling"} <= changes
    found = []
    for path in (ROOT / "par_app" / "acquisition_host").glob("*.py"):
        allowed = COORDINATOR_CHANGES_ALLOWED.get(path.name, set())
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                name = node.value  # getattr(coordinator, "queue_task")
            if name in changes and name not in allowed:
                found.append(f"{path.name}:{node.lineno} {name}")
    assert found == []
