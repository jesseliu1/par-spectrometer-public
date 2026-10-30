"""The maintenance page's file and database I/O, off the service's Qt main thread (D-219, review M2 of PR #55).

`Worker` runs a job on one worker thread and hands its future back to the main thread through a queued signal; the
completion is dropped when the takeover or configuration changed meanwhile (the controller's `epoch`). `Events`
keeps the software events of each device database as last read there (13_ appendix A: queries do not run on the
thread that carries stop requests and maintenance results). No device is touched here.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

from ..qt_compat import QObject, Qt, pyqtSignal, pyqtSlot
from .maintenance_view import EVENT_LIMIT

if TYPE_CHECKING:
    from .maintenance_host import MaintenanceController

LOG = logging.getLogger(__name__)
Job = Callable[[], object]
Done = Callable[[Future[object]], None]


class Worker(QObject):
    """Main-thread object owning one worker thread."""

    _finished = pyqtSignal(object)
    """(epoch when submitted, the completion to run on the main thread, the future)."""

    def __init__(self, epoch: Callable[[], int]) -> None:
        super().__init__()
        self._epoch = epoch
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="maintenance-io")
        # the PyQt5 stubs omit connect()'s connection-type argument
        self._finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)

    def execute(self, job: Job, done: Done) -> None:
        """Run `job` on the worker thread; `done(future)` runs on the main thread afterwards, unless the epoch
        changed meanwhile."""
        epoch = self._epoch()
        future = self._pool.submit(job)
        future.add_done_callback(lambda finished: self._finished.emit((epoch, done, finished)))

    @pyqtSlot(object)
    def _on_finished(self, item: object) -> None:
        epoch, done, future = cast(tuple[int, Done, "Future[object]"], item)
        if epoch == self._epoch():
            done(future)

    def close(self) -> None:
        """The service is closing: no new job; one still running finishes on its own."""
        self._pool.shutdown(wait=False, cancel_futures=True)


class Events:
    """The software events of the maintenance target's database, read on the worker thread while the page is open;
    one read at a time, a change during a read asks for one more. A failed read keeps the last rows (R-1-5)."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {}
        self._running = False
        self._again = False
        self._job = 0

    def clear(self) -> None:
        self.rows.clear()
        self._running = self._again = False
        self._job += 1

    def loaded(self, path: str | None) -> bool:
        return path is not None and path in self.rows

    def load(self, c: MaintenanceController) -> None:
        if c.hub is None or c.session is None or not c.window.target:
            return
        if self._running:
            self._again = True
            return
        database = c.hub.database_for(c.window.target)
        if database is None:
            return
        path = str(database.path.resolve())
        self._running, self._again = True, False
        self._job += 1
        job = self._job

        def done(future: Future[object]) -> None:
            if job != self._job:
                return
            self._running = False
            try:
                rows = cast(list[dict[str, Any]], future.result())
            except (OSError, sqlite3.Error) as error:  # the last events stay shown; the next change retries
                LOG.warning("maintenance page could not read the software events of %s: %s", path, error)
            else:
                if rows != self.rows.get(path):
                    self.rows[path] = rows
                    c.published()
            if self._again:
                self.load(c)

        c.worker.execute(lambda: database.recent_diagnostics(EVENT_LIMIT), done)
