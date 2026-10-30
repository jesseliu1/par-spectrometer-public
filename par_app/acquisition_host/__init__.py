"""Tier-1 acquisition takeover inside the alpha service (internal notes).

Runs on the service's Qt main thread: V1.0.3's single-instance lock (instance_lock), V1.0.3's own DeviceHub and
PollingCoordinator built exactly as main.py builds them (host), the event bridge from the coordinator's public
signals to the service's event stream and state cache (bridge), and the gateway that carries HTTP requests onto
the main thread (gateway). Red-line code (protocol, coordinator, maintenance, database) is reused unchanged; this
package only wraps it. import-linter keeps QtWidgets, QtGui, the old UI, the API layer and web frameworks out.

The package runs on PySide6 (internal notes; owner 2026-10-19, S-6): importing it fixes the process's
Qt binding to PySide6 before any of its modules imports a Qt name, unless a binding is already fixed (a test session
that compares alpha code with V1.0.3's PyQt5 windows); par_app.service_main refuses to run on anything but PySide6.
"""

from .. import qt_binding

qt_binding.prefer(qt_binding.PYSIDE6)
