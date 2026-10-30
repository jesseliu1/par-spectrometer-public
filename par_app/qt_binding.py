"""Which Qt binding this process runs on (internal notes; owner 2026-10-19, S-6).

One process uses exactly one binding:
  * V1.0.3 (main.py, par_app/ui.py and the dialogs) runs on PyQt5 and selects nothing: its own modules import PyQt5
    directly, and par_app.qt_compat, through which the shared red-line modules (coordinator, device_hub) get their Qt
    names, falls back to PyQt5 when no binding was chosen. V1.0.3's behaviour does not depend on this module;
  * the alpha service (par_app.service_main and everything under par_app.acquisition_host) runs on PySide6:
    par_app/acquisition_host/__init__.py calls `prefer(PYSIDE6)` before any of its modules imports a Qt name, and
    service_main refuses to start on any other binding (`require`).
This module imports no Qt binding itself, so it can be imported first. Once the binding is fixed it cannot change;
choosing PySide6 also makes any later `import PyQt5` in the process fail (`_RefuseOtherBinding`), so a stray PyQt5
import in the alpha shows as an ImportError instead of a second Qt in the same process (test sessions guard their
PyQt5 the same way, tests/conftest.py).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib.machinery import ModuleSpec
from types import ModuleType

PYQT5 = "PyQt5"
PYSIDE6 = "PySide6"
BINDINGS = (PYQT5, PYSIDE6)
DEFAULT = PYQT5
"""V1.0.3's binding; used when nothing chose one."""
FOREIGN = {PYQT5: ("PySide6", "shiboken6"), PYSIDE6: ("PyQt5",)}
"""Top-level packages that must not be loaded next to each binding."""

_chosen: str | None = None


class BindingError(RuntimeError):
    """A second Qt binding was asked for in a process that already has one."""


def chosen() -> str | None:
    """The binding fixed for this process, or None while nothing has fixed it."""
    return _chosen


def _loaded(names: Sequence[str]) -> list[str]:
    return [name for name in names if name in sys.modules]


def select(name: str, guard: bool | None = None) -> str:
    """Fix the binding of this process to `name`. Raises BindingError if another binding is fixed or loaded.
    `guard` (default: only for PySide6) makes importing the other binding fail from now on; V1.0.3's PyQt5
    process gets no guard, so nothing in it changes (test sessions ask for one)."""
    global _chosen
    if name not in BINDINGS:
        raise ValueError(f"unknown Qt binding {name!r}; expected one of {BINDINGS}")
    if _chosen is not None and _chosen != name:
        raise BindingError(f"this process already runs on {_chosen}; {name} cannot be loaded next to it")
    foreign = _loaded(FOREIGN[name])
    if foreign:
        raise BindingError(f"{', '.join(foreign)} already loaded in this process; {name} cannot be used next to it")
    if _chosen is None:
        _chosen = name
        if guard if guard is not None else name == PYSIDE6:
            sys.meta_path.insert(0, _RefuseOtherBinding(FOREIGN[name]))
    return name


def prefer(name: str) -> str:
    """`select(name)` unless a binding is already fixed (a test session that runs alpha code on PyQt5 to compare it
    with V1.0.3 fixes PyQt5 first). The alpha service checks the result with `require`."""
    return _chosen if _chosen is not None else select(name)


def resolve() -> str:
    """The binding par_app.qt_compat loads: the fixed one, else V1.0.3's PyQt5 (and it is fixed from now on)."""
    return _chosen if _chosen is not None else select(DEFAULT)


def require(name: str) -> None:
    """Raise BindingError unless this process is fixed to `name` (the alpha service: PySide6)."""
    if _chosen != name:
        raise BindingError(f"this process runs on {_chosen or 'no Qt binding yet'}, not {name}")


class _RefuseOtherBinding:
    """A meta-path finder that refuses the packages of the other binding (installed by `select(PYSIDE6)`)."""

    def __init__(self, refused: Sequence[str]) -> None:
        self.refused = tuple(refused)

    def find_spec(
        self, fullname: str, _path: Sequence[str] | None = None, _target: ModuleType | None = None
    ) -> ModuleSpec | None:
        if fullname.split(".", 1)[0] in self.refused:
            raise ImportError(f"{fullname} is refused: this process runs on {_chosen} (par_app/qt_binding.py)")
        return None
