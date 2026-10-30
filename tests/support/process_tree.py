"""Keep every process a test starts - and everything those start - in one container the test owns (#66, review
of PR #78), so the test can end what is left without guessing by pid.

`ContainedPopen()` is passed as `popen=` to par_shell.service.ServiceProcess (or called like subprocess.Popen):

* POSIX: the child starts a new session (`start_new_session=True`), so it and all its descendants share one process
  group whose id is the child's pid. POSIX does not reuse a process group id while the group exists, so
  `killpg(pgid)` after `killpg(pgid, 0)` found the group reaches only this test's processes - also when the child
  itself has already been reaped by ServiceProcess.stop() and only orphaned descendants are left. A group that no
  longer exists is left alone (nothing is ever killed by a stale pid).
* Windows: the child is put into a Job Object right after it starts (before a launcher's own startup gets as far as
  starting its child), and processes it starts are in the job too. `TerminateJobObject` ends exactly the processes
  in the job; closing the job handle (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) does the same if the test process dies.
  NOT VERIFIED ON WINDOWS YET.

`end_all()` ends whatever is still running and returns a description of each container that still had processes;
a test asserts it is empty after a clean stop.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

KILL_WAIT_SECONDS = 30.0
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_EXIT_CODE = 1


class ContainedPopen:
    def __init__(self) -> None:
        self.started: list[subprocess.Popen[Any]] = []
        self.left: list[str] = []
        """What the last end_all() had to end."""
        self._jobs: list[int] = []

    def __call__(self, args: Sequence[str], **kwargs: Any) -> subprocess.Popen[Any]:  # noqa: ANN401
        if sys.platform == "win32":
            process: subprocess.Popen[Any] = subprocess.Popen(args, **kwargs)
            self._jobs.append(_windows_job(process))
        else:
            process = subprocess.Popen(args, start_new_session=True, **kwargs)
        self.started.append(process)
        return process

    def end_all(self) -> list[str]:
        """End every process still in a container; returns one line per container that still had some."""
        left: list[str] = []
        if sys.platform == "win32":
            for job in self._jobs:
                if _windows_job_has_processes(job):
                    left.append(f"job {job}")
                _windows_end_job(job)
            self._jobs.clear()
        else:
            for process in self.started:
                try:
                    os.killpg(process.pid, 0)  # the group still exists: its id cannot belong to anyone else
                except ProcessLookupError:
                    continue
                except PermissionError:
                    continue
                left.append(f"process group {process.pid}")
                os.killpg(process.pid, signal.SIGKILL)
        for process in self.started:
            if process.poll() is None:
                process.wait(KILL_WAIT_SECONDS)
        self.left = left
        return left


def _kernel32() -> Any:  # noqa: ANN401 (ctypes library)
    import ctypes  # noqa: PLC0415 (Windows only)

    return ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]


def _windows_job(process: subprocess.Popen[Any]) -> int:
    import ctypes  # noqa: PLC0415 (Windows only)
    from ctypes import wintypes  # noqa: PLC0415

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("r", "w", "o", "rb", "wb", "ob")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = _kernel32()
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(
        wintypes.HANDLE(job), JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
    )
    handle = int(process._handle)  # type: ignore[attr-defined]  # Popen's process handle on Windows
    if not kernel32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(handle)):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    return int(job)


def _windows_job_has_processes(job: int) -> bool:
    import ctypes  # noqa: PLC0415 (Windows only)
    from ctypes import wintypes  # noqa: PLC0415

    class Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    info = Accounting()
    job_object_basic_accounting_information = 1
    ok = _kernel32().QueryInformationJobObject(
        wintypes.HANDLE(job), job_object_basic_accounting_information, ctypes.byref(info), ctypes.sizeof(info), None
    )
    return bool(ok) and info.ActiveProcesses > 0


def _windows_end_job(job: int) -> None:
    from ctypes import wintypes  # noqa: PLC0415 (Windows only)

    kernel32 = _kernel32()
    kernel32.TerminateJobObject(wintypes.HANDLE(job), JOB_EXIT_CODE)
    kernel32.CloseHandle(wintypes.HANDLE(job))
