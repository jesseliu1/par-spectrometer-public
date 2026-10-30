"""Layering checks the import contracts cannot express (review N-5).

par_app.database must stay importable for format_beijing_time, so no contract stops the application or API layer
from using ParDatabase, whose constructor writes (CREATE TABLE, ALTER TABLE, journal_mode=WAL). The alpha must
never write a V1.0.x database (15_ 5.1), so the name may not appear in their code at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
LAYERS = ("par_app/application", "par_app/api")
FORBIDDEN_NAME = "ParDatabase"


def _uses(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == FORBIDDEN_NAME:
            lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_NAME:
            lines.append(node.lineno)
        elif isinstance(node, ast.alias) and FORBIDDEN_NAME in (node.name.split(".")[-1], node.asname):
            lines.append(node.lineno)
        elif isinstance(node, ast.Constant) and node.value == FORBIDDEN_NAME:
            lines.append(node.lineno)  # getattr(database, "ParDatabase")
    return lines


def test_application_and_api_never_use_par_database() -> None:
    files = [path for layer in LAYERS for path in sorted((ROOT / layer).rglob("*.py"))]
    assert files
    found = {str(path.relative_to(ROOT)): lines for path in files if (lines := _uses(path))}
    assert found == {}


@pytest.mark.parametrize(
    "source",
    [
        "from par_app.database import ParDatabase as Db\n",
        "from par_app import database\ndb = database.ParDatabase('x')\n",
        "import par_app.database as d\nkind = getattr(d, 'ParDatabase')\n",
    ],
)
def test_the_check_sees_every_spelling(tmp_path: Path, source: str) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(source, encoding="utf-8")
    assert _uses(probe)
