"""The coordinator's private fields V1.0.3's window reads, read the same way and only here (17_ 1.4; D-213 q. 5).

V1.0.3's MainWindow, DeviceMaintenanceDialog and MaintenanceDialog read `PollingCoordinator._maintenance`, `_client`
(whether the bus is connected now) and `_maintenance_sessions` (each session's `pending`, `verified`, `baseline` and
`check_resume`) on the GUI thread; the coordinator has no public accessor for them and adding one would change a
red-line file. The alpha reads them on its Qt main thread, exactly as V1.0.3 does, through the functions below,
which never write: no session method other than `check_resume` (which only raises) is called. `sessions()` and
`session_for()` hand out the live session objects, as V1.0.3's windows hold them (callers only read their
attributes, on this thread); `session_state()` hands out copies of the values (review N1).
tests/unit/test_architecture.py checks that no other new module touches an underscore attribute of the coordinator
or of a session.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..coordinator import PollingCoordinator
from ..maintenance import CommunicationMaintenance


def maintenance(coordinator: PollingCoordinator) -> bool:
    """`coordinator._maintenance`, as V1.0.3's window reads it."""
    return bool(coordinator._maintenance)


def bus_connected(coordinator: PollingCoordinator) -> bool:
    """`coordinator._client is not None`: V1.0.3's MainWindow decides "connected" from the current client, read when
    it handles a signal, not from the level the signal carried (ui.py _on_bus_state, _request_settings_comm)."""
    return coordinator._client is not None


def sessions(coordinator: PollingCoordinator) -> list[CommunicationMaintenance]:
    """The sessions in the coordinator's order (resume_gate checks them in this order, as V1.0.3 does)."""
    return list(coordinator._maintenance_sessions.values())


def session_for(coordinator: PollingCoordinator, database_path: Path) -> CommunicationMaintenance | None:
    """The session of one device database (MaintenanceDialog.session)."""
    return coordinator._maintenance_sessions.get(Path(database_path).resolve())


def pending_paths(coordinator: PollingCoordinator) -> set[Path]:
    """Databases with a write waiting to be verified (DeviceMaintenanceDialog.prepare)."""
    return {path for path, session in coordinator._maintenance_sessions.items() if session.pending}


def any_pending(coordinator: PollingCoordinator) -> bool:
    """DeviceMaintenanceDialog.locked: any session with a write waiting to be verified."""
    return any(session.pending for session in coordinator._maintenance_sessions.values())


def session_state(session: CommunicationMaintenance | None) -> dict[str, Any]:
    """Copies of a session's pending, verified and baseline (None for each when there is no session)."""
    if session is None:
        return {"pending": None, "verified": None, "baseline": None}
    return {
        "pending": deepcopy(session.pending),
        "verified": deepcopy(session.verified),
        "baseline": deepcopy(session.baseline),
    }
