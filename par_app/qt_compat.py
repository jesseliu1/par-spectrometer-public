"""The QtCore names the shared acquisition code uses, from the binding of this process (par_app/qt_binding.py).

internal notes section 3. The red-line modules (coordinator, device_hub) changed only their
import line to `from par_app.qt_compat import ...`; under V1.0.3 (main.py) the names below are PyQt5's own objects,
so V1.0.3 runs exactly as before. Under the alpha service they are PySide6's, with PyQt5's spelling kept:
  * `pyqtSignal` / `pyqtSlot` are PySide6's Signal / Slot, except that the argument type `dict` becomes `object`.
    PyQt5 hands a dict through a queued connection as the same Python object; PySide6 converts a signal declared
    with dict to QVariantMap and back, which drops non-string keys and wraps integers beyond 64 bits (checked
    2026-10-19, PySide6 6.11.2 against PyQt5 5.15.11). With `object` PySide6 passes the dict itself, as PyQt5 does
    (tests/unit/test_qt_compat.py). `list` is left alone: PyQt5 copies a list too, and no shared signal uses it;
  * `Signal` / `Slot` are the same two callables under the PySide6 names, for new code.
Only QtCore is exported: the alpha service runs under QCoreApplication and must not load QtGui or QtWidgets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from par_app import qt_binding

BINDING = qt_binding.resolve()
"""PyQt5 or PySide6: fixed for the whole process when this module is first imported."""

if TYPE_CHECKING:  # the public tree is type-checked against PySide6's stubs (no PyQt5)
    from PySide6.QtCore import QCoreApplication, QObject, QSharedMemory, Qt, QThread, QTimer, qVersion
    from PySide6.QtCore import Signal as pyqtSignal
    from PySide6.QtCore import Slot as pyqtSlot

    Signal = pyqtSignal
    Slot = pyqtSlot
    BINDING_VERSION: str
elif BINDING == qt_binding.PYSIDE6:
    import PySide6
    from PySide6.QtCore import QCoreApplication, QObject, QSharedMemory, Qt, QThread, QTimer, qVersion
    from PySide6.QtCore import Signal as _Signal
    from PySide6.QtCore import Slot as _Slot

    BINDING_VERSION = PySide6.__version__

    def _portable(types: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(object if kind is dict else kind for kind in types)

    def pyqtSignal(*types: Any, **options: Any) -> Any:  # noqa: N802, ANN401 (PyQt5's name; PySide6's Signal)
        return _Signal(*_portable(types), **options)

    def pyqtSlot(*types: Any, **options: Any) -> Callable[[Any], Any]:  # noqa: N802, ANN401 (PyQt5's name)
        return _Slot(*_portable(types), **options)  # type: ignore[no-any-return]

    Signal = pyqtSignal
    Slot = pyqtSlot
else:
    from PyQt5.QtCore import (
        PYQT_VERSION_STR,
        QCoreApplication,
        QObject,
        QSharedMemory,
        Qt,
        QThread,
        QTimer,
        pyqtSignal,
        pyqtSlot,
        qVersion,
    )

    BINDING_VERSION = PYQT_VERSION_STR
    Signal = pyqtSignal
    Slot = pyqtSlot

__all__ = [
    "BINDING",
    "BINDING_VERSION",
    "QCoreApplication",
    "QObject",
    "QSharedMemory",
    "QThread",
    "QTimer",
    "Qt",
    "Signal",
    "Slot",
    "pyqtSignal",
    "pyqtSlot",
    "qVersion",
]
