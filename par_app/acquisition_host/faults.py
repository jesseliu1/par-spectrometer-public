"""The takeover layer of D-225 item 1 (R-1-5): an unexpected error on the service's Qt main thread stops the takeover.

The main thread holds only the takeover (DeviceHub, the coordinator object, the lock) and the maintenance controller
(16_ 1.3, 17_ 3.2), so an exception that escapes code running there - a slot or callback (PySide6 hands it to
sys.excepthook and goes on), or a call the gateway carried there for an HTTP request - may leave their state half
updated. `TakeoverFaults` then:

1. logs the traceback at CRITICAL (service.log);
2. keeps the fault and publishes `service_error` (application/faults.py), so the page shows TAKEOVER_FAULT;
3. queues the takeover stop that POST /shutdown and the shell watch run (AcquisitionHost.stop: coordinator.stop()
   lets the transaction in progress finish and resume the device, the port closes, the lock is released), with
   the page told again as its `then`; the tier is kept (issue #119: "开始采集" or the next start acquires again),
   and the service does not end.

A halt is never cleared and maintenance state is left in the device database as a stop leaves it. While the service
is closing, its own shutdown stops the takeover instead. Errors on HTTP threads are the request layer
(par_app.api.app). owner may still choose "always exit" (D-225 item 1): the stop would then be `request_shutdown`.
"""

from __future__ import annotations

import logging
import sys
import threading
from types import TracebackType

from ..application.acquisition import AcquisitionService
from ..application.errors import TakeoverFault
from ..application.faults import STOP_FAILED, TAKEOVER_FAULT
from .gateway import MainThreadGateway
from .host import AcquisitionHost

LOG = logging.getLogger("par_app.service")
UNCAUGHT_TAKEOVER = "uncaught exception in %s (D-225 item 1): stopping the takeover"
"""service.log entry (CRITICAL, with the traceback) of an unexpected error on the main thread."""
QT_CALLBACK = "a Qt slot or callback"


class TakeoverFaults:
    def __init__(self, host: AcquisitionHost, acquisition: AcquisitionService, gateway: MainThreadGateway) -> None:
        self.host = host
        self.acquisition = acquisition
        self.gateway = gateway
        self._lock = threading.Lock()
        self._stop_queued = False
        gateway.unexpected = self.main_thread_call_failed

    def excepthook(self, kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
        """sys.excepthook of the service: what escaped a slot or callback (KeyboardInterrupt keeps Python's own)."""
        if issubclass(kind, KeyboardInterrupt) or not isinstance(error, Exception):
            sys.__excepthook__(kind, error, trace)
            return
        self.failed(QT_CALLBACK, error.with_traceback(trace))

    def main_thread_call_failed(self, where: str, error: Exception) -> BaseException:
        """MainThreadGateway.unexpected: the HTTP request that carried the call gets TAKEOVER_FAULT (500)."""
        self.failed(where, error)
        return TakeoverFault(TAKEOVER_FAULT, type(error).__name__)

    def failed(self, where: str, error: Exception) -> None:
        LOG.critical(UNCAUGHT_TAKEOVER, where, exc_info=(type(error), error, error.__traceback__))
        try:
            self.acquisition.faults.report("takeover", where, error)
        except Exception:
            LOG.exception("the unexpected error could not be reported to the page")
        with self._lock:
            if self._stop_queued:
                return  # one stop is enough; it has not run yet
            self._stop_queued = True
        self.gateway.queue(self._stop)

    def _stop(self) -> None:
        """Main thread, at the next turn of the loop (never inside the call that failed)."""
        with self._lock:
            self._stop_queued = False
        if self.acquisition.closing:
            return  # the service's own shutdown stops the takeover
        try:
            self.host.stop(then=self.acquisition.lower_after_fault)
        except Exception as error:
            LOG.critical("stopping the takeover after an unexpected error failed", exc_info=error)
            try:
                self.acquisition.faults.report("takeover", "stop after an unexpected error", error, STOP_FAILED)
            except Exception:
                LOG.exception("the failed stop could not be reported to the page")
