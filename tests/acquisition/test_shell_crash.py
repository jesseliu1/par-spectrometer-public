"""A crashed shell while the service is in the middle of a frozen acquisition transaction (review of PR #56,
blocker 2; D-223).

A stand-in shell process starts the real service (par_app.service_main on the byte-level fake bus,
tests/support/fake_bus_service.py) the way par_shell/service.py does: with --parent-pid set to its own pid, and
without --stop-on-stdin-eof (the windowed exe has no stdin on Windows, so only the shell watch can see the crash).
The takeover is started; the fake device holds the first frame after the freeze (holding 25 = 1). The shell is then
killed (SIGKILL: no shutdown request, no clean-up). The service must notice, finish the transaction - the resume
command (holding 25 = 0) is written after the freeze - release the single-instance lock, remove service.json and
exit on its own. Before this fix the Windows shell held the service in a kill-on-close Job Object, which ended it at
the freeze, and the service did not know the --parent-pid option at all.

The lock uses a key of its own (PAR_TEST_LOCK_KEY, as tests/acquisition/conftest.py isolated_lock_key), so test runs
at the same time do not refuse each other's takeover.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from par_app.acquisition_host.instance_lock import InstanceLock
from par_app.api.__main__ import LAUNCH_ID_ENV
from par_app.parent_watch import BACKSTOP_SECONDS, SHELL_GONE
from par_app.service_main import SERVICE_STOPPED
from tests.acquisition.conftest import isolated_lock_key, two_devices, write_config

pytestmark = pytest.mark.qt
ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "tests" / "support" / "fake_bus_service.py"
START_SECONDS = 30.0
FREEZE_SECONDS = 30.0
STOP_SECONDS = 60.0
"""At least one acquisition transaction budget (40 s) plus margin (16_ 1.5)."""
BACKSTOP_TEXT = "the service did not stop within"
SHELL = """
import os, subprocess, sys, time
service, data_dir, out, err, *launcher = sys.argv[1:]
child = subprocess.Popen(
    [*launcher, sys.executable, service, "--port", "0", "--data-dir", data_dir, "--parent-pid", str(os.getpid())],
    stdin=subprocess.DEVNULL, stdout=open(out, "wb"), stderr=open(err, "wb"),
)
print(child.pid, os.getpid(), flush=True)
while True:
    time.sleep(1)
"""
"""The stand-in shell prints the pid it started (on Windows from a venv: the launcher of the service, which exits
exactly when the service does) and its own pid (the process the service watches, which the test kills; issue #66).
Its PAR_SERVICE_LAUNCH_ID, inherited by the service, tells the test which service.json is this service's. With the
venv launcher stand-in (tests/support/venv_launcher.py) as optional last arguments, the service runs as the child of a
launcher, as from a Windows venv."""
LAUNCHER = ROOT / "tests" / "support" / "venv_launcher.py"
LAUNCH_ID = "shell-crash-test-launch"


@dataclass
class Crash:
    shell: subprocess.Popen[str]
    pid: int
    shell_pid: int
    data_dir: Path
    key: str
    out: Path
    err: Path
    release: Path

    def alive(self) -> bool:
        return _alive(self.pid)


STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001


def _alive(pid: int) -> bool:
    """Whether the service process still runs. Windows: os.kill(pid, 0) would send CTRL_C_EVENT, so the process is
    asked for its exit code instead (review round 2 of PR #56, major 2: this test runs on Windows too)."""
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _kill(pid: int) -> None:
    """Clean-up only: end a service the test left running."""
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            kernel32.TerminateProcess(handle, 1)
            kernel32.CloseHandle(handle)
        return
    os.kill(pid, signal.SIGKILL)


def _wait(check: Callable[[], bool], seconds: float, what: str) -> None:
    deadline = time.monotonic() + seconds
    while not check():
        assert time.monotonic() < deadline, f"{what}: not reached in {seconds:.0f} s"
        time.sleep(0.05)


def _service_info(path: Path, launch_id: str) -> dict[str, Any] | None:
    """service.json of the service started with `launch_id`, once it answers (not by pid: issue #66)."""
    try:
        info: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if info["launch_id"] != launch_id:
            return None
        httpx.get(f"{info['base_url']}/api/v0/health", timeout=1.0).raise_for_status()
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        return None
    return info


@pytest.fixture
def crash(qt_app: object, tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Crash]:
    """`request.param` True: the stand-in shell starts the service through the venv launcher stand-in (#66)."""
    launcher = [sys.executable, str(LAUNCHER)] if getattr(request, "param", False) else []
    data_dir = (tmp_path / "alpha data").resolve()
    write_config(data_dir, two_devices())
    key = isolated_lock_key()
    release = tmp_path / "release"
    out, err = tmp_path / "service.out", tmp_path / "service.err"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PAR_TEST_LOCK_KEY=key, PAR_TEST_HOLD_AFTER_FREEZE=str(release))
    env[LAUNCH_ID_ENV] = LAUNCH_ID
    shell = subprocess.Popen(
        [sys.executable, "-c", SHELL, str(SERVICE), str(data_dir), str(out), str(err), *launcher],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert shell.stdout is not None
    service_pid, shell_pid = (int(pid) for pid in shell.stdout.readline().split())
    running = Crash(shell, service_pid, shell_pid, data_dir, key, out, err, release)
    try:
        yield running
    finally:
        release.touch()
        if shell.poll() is None:
            shell.kill()
        shell.wait()
        if running.alive():
            _kill(running.pid)


def _frozen_then_shell_killed(crash: Crash) -> InstanceLock:
    """Start the takeover, wait until the device is frozen and the next frame held, then kill the shell (on Windows
    TerminateProcess, the same as ending the shell process alone in Task Manager); returns a probe of the lock."""
    service_file = crash.data_dir / "service.json"
    found: list[dict[str, Any]] = []

    def started() -> bool:
        assert crash.alive(), crash.err.read_text(encoding="utf-8", errors="replace")
        info = _service_info(service_file, LAUNCH_ID)
        found.extend([info] if info else [])
        return bool(found)

    _wait(started, START_SECONDS, "service start")
    info = found[0]
    with httpx.Client(base_url=info["base_url"], headers={"Authorization": f"Bearer {info['token']}"}) as client:
        issued = client.post("/api/v0/tier/confirmations", json={"tier": 1}).json()
        assert client.put("/api/v0/tier", json={"tier": 1, "confirmation_id": issued["confirmation_id"]}).is_success
        started_takeover = client.post("/api/v0/acquisition/start")
        assert started_takeover.status_code == 202 and started_takeover.json()["lock_held"], started_takeover.text
    held = Path(f"{crash.release}.held")
    _wait(held.exists, FREEZE_SECONDS, "device frozen, next frame held")
    probe = InstanceLock(crash.key)
    assert not probe.acquire()  # the service holds the lock in the middle of the transaction

    _kill(crash.shell_pid)  # the shell crashes: no shutdown request, stdin never was the stop path
    crash.shell.wait()
    log = crash.data_dir / "logs" / "service.log"
    _wait(lambda: SHELL_GONE in log.read_text(encoding="utf-8"), STOP_SECONDS, "service noticed the shell is gone")
    assert crash.alive()  # not killed: it waits for the transaction in progress
    return probe


@pytest.mark.parametrize("crash", [False, True], ids=["direct", "venv-launcher"], indirect=True)
def test_a_crashed_shell_lets_the_frozen_transaction_resume_then_the_service_exits(crash: Crash) -> None:
    service_file = crash.data_dir / "service.json"
    log = crash.data_dir / "logs" / "service.log"
    probe = _frozen_then_shell_killed(crash)
    crash.release.touch()  # the held frame goes out; the transaction finishes as on the wire
    _wait(lambda: not crash.alive(), STOP_SECONDS, "service exit")

    output = crash.out.read_text(encoding="utf-8").splitlines()
    stops = next(line for line in output if line.startswith("STOP25")).split()[1:]
    assert stops, output
    for slave in {entry.split(":")[0] for entry in stops}:
        writes = [entry.split(":")[1] for entry in stops if entry.split(":")[0] == slave]
        assert writes[-1] == "0", f"slave {slave} left frozen: {stops}"  # the resume command went out
    assert "1:1" in stops and stops.index("1:0", stops.index("1:1")) > stops.index("1:1")
    assert "opened=1 closed=1" in next(line for line in output if line.startswith("PORT "))
    assert output[-1] == "THREADS MainThread"
    assert probe.acquire()  # the lock is free again
    probe.release()
    assert not service_file.exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[-1].endswith(f"{SERVICE_STOPPED} non-daemon threads left: none")
    assert "Traceback" not in crash.err.read_text(encoding="utf-8", errors="replace")


def test_a_shutdown_that_hangs_after_the_shell_crash_ends_at_the_backstop(crash: Crash) -> None:
    """The held frame is never released, so the graceful shutdown cannot finish: BACKSTOP_SECONDS after the shell
    went away the service ends itself (os._exit(EXIT_BACKSTOP)); the lock is free again afterwards."""
    log = crash.data_dir / "logs" / "service.log"
    probe = _frozen_then_shell_killed(crash)
    gone = time.monotonic()
    _wait(lambda: not crash.alive(), BACKSTOP_SECONDS + STOP_SECONDS, "service exit at the backstop")
    assert time.monotonic() - gone >= BACKSTOP_SECONDS - 5.0  # not before the backstop
    assert BACKSTOP_TEXT in log.read_text(encoding="utf-8")
    assert probe.acquire()  # the operating system released the lock with the process
    probe.release()
