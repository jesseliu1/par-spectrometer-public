"""Carries calls from HTTP threads onto the service's Qt main thread (16_ 1.4).

DeviceHub, the coordinator object and the lock belong to the main thread, as in V1.0.3. An HTTP handler never calls
them itself: it hands a callable to `call` (waits for the result) or `post` (does not wait). The gateway emits a
signal with a queued connection to its own slot on the main thread, which runs the callable and fills a
concurrent.futures.Future. Called on the main thread itself, the callable runs at once (no deadlock); `queue` always
waits for the next turn of the main loop (never runs inside the current main-thread call).

An exception other than an ApplicationError is unexpected (D-225 item 1): `unexpected`, when set
(acquisition_host.faults), reports it and stops the takeover, and the waiting thread gets what it returns instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future
from typing import TypeVar, cast

from ..application.errors import ApplicationError
from ..qt_compat import QObject, Qt, QThread, pyqtSignal, pyqtSlot

LOG = logging.getLogger(__name__)
T = TypeVar("T")
Unexpected = Callable[[str, Exception], BaseException]
"""(where, error) -> the exception handed to the waiting thread."""


class MainThreadGateway(QObject):
    _requested = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        # the PyQt5 stubs omit connect()'s connection-type argument
        self._requested.connect(self._on_requested, Qt.ConnectionType.QueuedConnection)
        self.unexpected: Unexpected | None = None

    def on_main_thread(self) -> bool:
        return QThread.currentThread() is self.thread()

    def post(self, function: Callable[[], T]) -> Future[T]:
        future: Future[T] = Future()
        if self.on_main_thread():
            self._run(function, future)
        else:
            self._requested.emit((function, future))
        return future

    def queue(self, function: Callable[[], T]) -> Future[T]:
        """Run `function` on the main thread at its next turn, also when called there (queued signal)."""
        future: Future[T] = Future()
        self._requested.emit((function, future))
        return future

    def call(self, function: Callable[[], T], timeout: float) -> T:
        """Run `function` on the main thread and return its result (or raise its exception); TimeoutError when the
        main thread did not get to it within `timeout` seconds."""
        return self.post(function).result(timeout)

    @pyqtSlot(object)
    def _on_requested(self, item: object) -> None:
        function, future = cast(tuple[Callable[[], object], Future[object]], item)
        self._run(function, future)

    def _run(self, function: Callable[[], T], future: Future[T]) -> None:
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(function())
        except ApplicationError as error:  # an answer of the use case (busy, not running, ...): handed on as it is
            future.set_exception(error)
        except Exception as error:  # noqa: BLE001 (unexpected: reported, then handed on; D-225 item 1)
            future.set_exception(self._unexpected(function, error))
        except BaseException as error:  # handed to the waiting thread; a slot must not raise (process abort)
            if not isinstance(error, Exception):
                LOG.error("main-thread call ended with %r", error)
            future.set_exception(error)

    def _unexpected(self, function: Callable[[], object], error: Exception) -> BaseException:
        handler = self.unexpected
        if handler is None:
            return error
        where = f"main-thread call {getattr(function, '__qualname__', type(function).__name__)}"
        try:
            return handler(where, error)
        except Exception:
            LOG.exception("reporting an unexpected main-thread error failed")
            return error
