"""The alpha shell's single-instance lock (15_ section 5; its name differs from V1.0.3's lock).

One alpha at a time per user: a second shell would start a second service on the same data directory and the two
would race on service.json and on snapshot imports. The lock is held for the life of the shell process and released
by the operating system when the process ends, even if it crashes.

* Windows: a named mutex in the session namespace, Local\\PAR_Spectrometer_2.SingleInstance (CreateMutexW; a second
  CreateMutexW on the same name returns ERROR_ALREADY_EXISTS). NOT VERIFIED ON WINDOWS YET.
* Elsewhere: an exclusive flock on <data dir>/shell.lock (development on macOS/Linux).

V1.0.3 holds a QSharedMemory segment with the key VSCO_PAR_PAR_Spectrometer_SingleInstance (main.py). The two locks
never share a name, so the alpha and V1.0.3 can run at the same time; tier 0 opens no serial port, so they do not
compete for the bus either. Tier 1 must take V1.0.3's lock as well (13_ section 2.5); that comes with its own approval.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO, Protocol

SINGLE_INSTANCE_NAME = "PAR_Spectrometer_2.SingleInstance"
"""Same string as par_app.alpha_info.SINGLE_INSTANCE_NAME (a test keeps them equal)."""
WINDOWS_NAMESPACE = "Local\\"
"""Per logon session, like V1.0.3's QSharedMemory (Qt 5 creates its file mapping without a Global\\ prefix)."""
LOCK_FILE = "shell.lock"
ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5
"""CreateMutexW on a mutex an elevated alpha created: it exists, so another alpha shell runs (review N-6)."""


def mutex_name() -> str:
    return WINDOWS_NAMESPACE + SINGLE_INSTANCE_NAME


class Win32Mutex(Protocol):
    def create(self, name: str) -> tuple[int, int]:
        """CreateMutexW(NULL, FALSE, name): (handle or 0, GetLastError() right after the call)."""

    def close(self, handle: int) -> None: ...


class _Kernel32Mutex:
    """The real CreateMutexW / CloseHandle (Windows only)."""

    def __init__(self) -> None:
        self._kernel32: Any = None
        self._last_error: Callable[[], int] = lambda: 0
        if sys.platform != "win32":
            raise OSError("a named mutex needs Windows")
        import ctypes  # noqa: PLC0415 (Windows only)
        from ctypes import wintypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32 = kernel32
        self._last_error = ctypes.get_last_error

    def create(self, name: str) -> tuple[int, int]:
        handle = self._kernel32.CreateMutexW(None, False, name)
        return int(handle or 0), int(self._last_error())

    def close(self, handle: int) -> None:
        self._kernel32.CloseHandle(handle)


class InstanceLock:
    """acquire() -> True if this process now holds the lock, False if another alpha shell holds it."""

    def __init__(self, data_dir: Path, platform: str = sys.platform, mutex: Win32Mutex | None = None) -> None:
        self.data_dir = data_dir
        self.platform = platform
        self._mutex = mutex
        self._handle: int | None = None
        self._file: BinaryIO | None = None

    def acquire(self) -> bool:
        if self.platform == "win32":
            return self._acquire_mutex()
        return self._acquire_file()

    def release(self) -> None:
        if self._handle is not None and self._mutex is not None:
            self._mutex.close(self._handle)
            self._handle = None
        if self._file is not None:
            self._file.close()  # closing the descriptor drops the flock
            self._file = None

    def __enter__(self) -> InstanceLock:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    def _acquire_mutex(self) -> bool:
        if self._mutex is None:
            self._mutex = _Kernel32Mutex()
        handle, error = self._mutex.create(mutex_name())
        if not handle and error == ERROR_ACCESS_DENIED:
            return False
        if not handle:
            raise OSError(error, f"CreateMutexW({mutex_name()}) failed")
        if error == ERROR_ALREADY_EXISTS:
            self._mutex.close(handle)
            return False
        self._handle = handle
        return True

    def _acquire_file(self) -> bool:
        if sys.platform == "win32":  # Windows uses the named mutex; this also keeps mypy on Windows off fcntl (#66)
            raise OSError("the lock file is the POSIX fallback; Windows uses the named mutex")
        import fcntl  # noqa: PLC0415 (POSIX only)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        handle = (self.data_dir / LOCK_FILE).open("ab")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._file = handle
        return True
