"""The alpha's maintenance texts are V1.0.3's, word for word (17_ 6.3, 10.5).

par_app/acquisition_host/v1_texts.py copies them (the import contract keeps the old windows out of the service);
for every text, this parses the V1.0.3 function `SOURCES` names and checks each literal part of the text (the parts
between `{…}` placeholders of a template; every string of a dict or tuple) among the string constants of that
function, f-string parts included. A wording change on the V1.0.3 line fails here when it is merged forward.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import pytest

from par_app.acquisition_host import v1_texts

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = re.compile(r"\{[^{}]*\}")


@cache
def _constants(file: str, function: str) -> frozenset[str]:
    tree = ast.parse((ROOT / file).read_text(encoding="utf-8"))
    scopes: list[ast.AST] = [tree] if function == "<module>" else []
    if function != "<module>":
        scopes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function]
    assert scopes, f"{file} has no function {function}"
    found = set()
    for scope in scopes:
        for node in ast.walk(scope):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add(node.value)
    return frozenset(found)


def _parts(value: object) -> list[str]:
    if isinstance(value, str):
        return [part for part in PLACEHOLDER.split(value) if part]
    if isinstance(value, dict):
        return [part for item in value.values() for part in _parts(item)]
    if isinstance(value, (tuple, list)):
        return [part for item in value for part in _parts(item)]
    return []


@pytest.mark.parametrize("name", sorted(v1_texts.SOURCES))
def test_text_is_v103_wording(name: str) -> None:
    file, function = v1_texts.SOURCES[name]
    constants = _constants(file, function)
    for part in _parts(getattr(v1_texts, name)):
        assert any(part in constant for constant in constants), f"{name}: {part!r} not in {file}:{function}"


def test_settings_comm_states_are_v103_wording() -> None:
    constants = frozenset().union(*(_constants(v1_texts.MAIN_WINDOW, f) for f in v1_texts.COMM_STATE_SOURCES))
    for state, text in v1_texts.COMM_STATES.items():
        assert text in constants, state


def test_every_text_has_a_source() -> None:
    names = {name for name, value in vars(v1_texts).items() if name.isupper() and not name.startswith("SOURCE")}
    names -= {"DIALOG", "COMM_DIALOG", "MAIN_WINDOW", "COMM_STATES", "COMM_STATE_SOURCES"}
    assert names <= set(v1_texts.SOURCES), names - set(v1_texts.SOURCES)
