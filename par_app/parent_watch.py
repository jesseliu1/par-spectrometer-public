"""The service stops by itself when the shell that started it is gone (review of PR #56, blocker 2; D-223).

The shell passes its own pid (`--parent-pid`, par_shell/service.py). If that process ends without the normal stop
request - a crash, or the shell process alone ended in Task Manager - the service runs the same graceful shutdown
as POST /api/v0/shutdown: coordinator.stop() finishes the transaction in progress, including the resume command
after a freeze, the queued signals are delivered, V1.0.3's lock is released, then the process exits 0 (16_ 1.5).
Until this PR the Windows shell put the service in a kill-on-close Job Object, which ended it AT ONCE when the shell
went away, possibly between the freeze and the resume; Windows cannot delay that kill, so the Job Object is no
longer used.

Backstop: if the service is still running BACKSTOP_SECONDS after the shell went away (a shutdown that hangs), it
ends itself with os._exit(EXIT_BACKSTOP). That is the same limit as the shell's own wait for the service to exit
(par_shell/service.py STOP_TIMEOUT_SECONDS, 16_ 1.5: one acquisition transaction budget of 40 s plus margin), so a
kill can still leave a device frozen only where the shell's stop would have killed it too.

Not covered (D-223): logoff and shutdown end the service too, and so may "End task" on the app group in Task
Manager or "End process tree"; those are the same as V1.0.3 being killed (16_ 1.5).

How the shell's end is seen:
- Windows: a SYNCHRONIZE handle to the shell process, opened right after the arguments are parsed (`open_parent`,
  so a later process with the same pid is never mistaken for the shell) and waited on by a daemon thread. The
  windowed exe has no stdin, so the end of the pipe cannot be used there (PR #50 review, major 1).
- POSIX (macOS, the source tree): the shell is the direct parent; when it ends the service is re-parented, so
  os.getppid() changes. Polled every POLL_SECONDS. If the given pid is not the direct parent, its existence is
  polled with signal 0 instead.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from collections.abc import Callable
from typing import Any

from .domain.clock import Clock

PARENT_PID = "--parent-pid"
"""The option the shell sets (par_shell/service.py keeps the same string; a test keeps them equal)."""
WATCHING = "watching the shell process"
"""Logged once the watch runs (par_shell/self_test.py looks for it in service.log; a test keeps them equal)."""
SHELL_GONE = "stop requested: the shell process is gone"
POLL_SECONDS = 0.5
"""POSIX: how often the parent is checked."""
BACKSTOP_SECONDS = 60.0
"""The service ends itself this long after the shell went away if the graceful shutdown has not finished."""
EXIT_BACKSTOP = 3
"""Exit code of that backstop (2 is a refused data directory or an argparse error)."""
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
ERROR_INVALID_PARAMETER = 87
"""OpenProcess's error for a pid no process has (the shell already ended)."""
LOG = logging.getLogger("par_app.service")

Waiter = Callable[[], None]
"""Blocks until the shell process is gone."""


def windows_waiter(pid: int, kernel32: Any = None, last_error: Callable[[], int] | None = None) -> Waiter:  # noqa: ANN401
    """Open the shell's handle now; the returned waiter blocks on it. Raises OSError if the handle cannot be opened
    for another reason than the shell being gone already."""
    api = kernel32 if kernel32 is not None else _kernel32()
    error: Callable[[], int] = last_error if last_error is not None else getattr(ctypes, "get_last_error", _no_error)
    handle = api.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        code = error()
        if code == ERROR_INVALID_PARAMETER:
            return _gone_already
        raise OSError(code, "OpenProcess failed")

    def wait() -> None:
        try:
            api.WaitForSingleObject(handle, INFINITE)
        finally:
            api.CloseHandle(handle)

    return wait


def posix_waiter(
    pid: int,
    clock: Clock,
    getppid: Callable[[], int] = os.getppid,
    exists: Callable[[int], bool] | None = None,
) -> Waiter:
    """Poll until the shell is gone: the parent pid changed (direct parent) or the pid no longer exists."""
    direct = getppid() == pid
    alive = exists if exists is not None else _exists

    def wait() -> None:
        while (getppid() == pid) if direct else alive(pid):
            clock.sleep(POLL_SECONDS)

    return wait


def open_parent(pid: int, clock: Clock) -> Waiter | OSError:
    """Take hold of the shell process now, right after the arguments are parsed (review N3 of PR #56): the
    Windows handle is opened, and on POSIX the direct parent is noted, before the seconds the service needs to set up
    Qt, uvicorn and service.json, so a shell that dies in that time cannot have its pid reused by another process that
    the service would then watch instead. The error, if any, is handed to `watch_parent`, which logs it once logging
    is configured."""
    try:
        return _waiter(pid, clock)
    except OSError as error:
        return error


def watch_parent(
    pid: int,
    stop: Callable[[], None],
    clock: Clock,
    waiter: Waiter | OSError | None = None,
    exit_process: Callable[[int], None] = os._exit,
) -> threading.Thread | None:
    """Start the watch on a daemon thread: when the shell is gone call `stop` (which queues the graceful shutdown),
    then end the process after BACKSTOP_SECONDS if it is still running. `waiter` is what `open_parent` returned at
    start (None: open it now). Returns None (and logs) if the shell cannot be watched; the service then runs on, as
    it did before (the shutdown request still stops it)."""
    opened = waiter if waiter is not None else open_parent(pid, clock)
    if isinstance(opened, OSError):
        LOG.warning(
            "the shell process %d cannot be watched (%s): a crashed shell leaves the service running", pid, opened
        )
        return None
    wait = opened

    def run() -> None:
        wait()
        try:
            LOG.info(SHELL_GONE)
            stop()
        finally:  # nothing that fails here may keep the backstop from ending the process (review round 2, major 1)
            try:
                clock.sleep(BACKSTOP_SECONDS)
                LOG.error(
                    "the service did not stop within %.0f s after the shell went away: ending it", BACKSTOP_SECONDS
                )
                _flush_logs()
            finally:
                exit_process(EXIT_BACKSTOP)

    thread = threading.Thread(target=run, name="shell-watch", daemon=True)
    thread.start()
    LOG.info("%s (pid %d)", WATCHING, pid)
    return thread


def _waiter(pid: int, clock: Clock) -> Waiter:
    if sys.platform == "win32":
        return windows_waiter(pid)
    return posix_waiter(pid, clock)


def _exists(pid: int) -> bool:
    """POSIX only (on Windows os.kill with 0 would send CTRL_C_EVENT)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _gone_already() -> None:
    return None


def _no_error() -> int:
    return 0


def _flush_logs() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def _kernel32() -> Any:  # noqa: ANN401 (ctypes library object)
    from ctypes import wintypes  # noqa: PLC0415

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32
