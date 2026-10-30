"""par_shell.service.ServiceProcess against the real service (python -m par_app.service_main) on 127.0.0.1, directly
and behind tests/support/venv_launcher.py (#66: a Windows venv's python.exe is a launcher). Every test is bounded
(`_bounded`): a stop that must kill also kills the service by its own pid, so a problem fails fast. Moved from
tests/unit/test_shell.py (size limit)."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from par_shell import service
from par_shell.service import ServiceError, ServiceProcess
from tests.support.process_tree import ContainedPopen
from tests.support.venv_launcher import LAUNCHER_PID_ENV

from .test_shell import LAUNCHER

pytestmark = pytest.mark.unit


TEST_STOP_SECONDS = 20.0
"""A test's own wait at each stop step (the product waits STOP_TIMEOUT_SECONDS; no takeover runs here)."""
NEVER_READY = """
import subprocess, sys, pathlib
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
pathlib.Path(sys.argv[1]).write_text(str(grandchild.pid), encoding="utf-8")
sys.stdin.read()  # the shell's stop closes stdin; the grandchild is left behind
"""


@contextlib.contextmanager
def _bounded(data_dir: Path) -> Iterator[tuple[ServiceProcess, ContainedPopen]]:
    """A ServiceProcess whose child (and everything it starts) runs in a container the test owns
    (tests/support/process_tree.py); the stop waits TEST_STOP_SECONDS per step, then whatever is still running in
    the container is ended - on every path, also after a failed start (review rv-78 majors 1 and 2: no kill by
    a remembered pid). `container.left` lists what had to be ended; a clean stop leaves it empty."""
    container = ContainedPopen()
    child = ServiceProcess(data_dir, popen=container)
    try:
        yield child, container
    finally:
        try:
            child.stop(timeout=TEST_STOP_SECONDS)
        finally:
            container.end_all()


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        done = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False)
        return str(pid) in done.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_failed_start_behind_a_launcher_leaves_no_process(tmp_path: Path) -> None:
    """rv-78 major 1: the start times out, the product's own stop clears child.process and child.info is never
    set; a descendant of the launcher that is still running is ended anyway, through the container."""
    grandchild_pid = tmp_path / "grandchild.pid"
    command = [sys.executable, str(LAUNCHER), sys.executable, "-c", NEVER_READY, str(grandchild_pid)]
    with _bounded(tmp_path / "alpha") as (child, container):
        with pytest.raises(ServiceError, match="没有就绪"):
            child.start(command, timeout=2.0)
        assert child.process is None and child.info is None
        pid = int(grandchild_pid.read_text(encoding="utf-8"))
        assert _alive(pid)  # left behind by the product's stop, as a launcher's child could be
    assert container.left
    for _ in range(50):  # reaping by init may take a moment after SIGKILL
        if not _alive(pid):
            break
        time.sleep(0.1)
    assert not _alive(pid)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups; Windows uses the job object")
def test_the_container_never_signals_a_group_that_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """rv-78 major 2: after the child and everything it started are gone, end_all() sends no kill at all - a pid
    that has been reaped is never signalled again."""
    container = ContainedPopen()
    process = container([sys.executable, "-c", "pass"])
    process.wait(TEST_STOP_SECONDS)
    sent: list[tuple[int, int]] = []
    real = os.killpg

    def spy(pgid: int, sig: int) -> None:
        sent.append((pgid, sig))
        real(pgid, sig)

    monkeypatch.setattr(os, "killpg", spy)
    assert container.end_all() == []
    assert sent == [(process.pid, 0)]  # only the existence check


def test_the_real_service_starts_answers_and_stops(tmp_path: Path) -> None:
    """Integration: python -m par_app.service_main as the child, on 127.0.0.1 only; it exits by itself (code 0,
    review N-3) on the shell's shutdown request (stdin still open: no abort at interpreter exit), and service.json is
    gone afterwards."""
    data_dir = tmp_path / "alpha"
    with _bounded(data_dir) as (child, container):
        info = child.start()
        popen = child.process
        assert popen is not None
        assert info.base_url.startswith("http://127.0.0.1:")
        assert service.health(info)["tier"] == 1  # the product starts in tier 1 (issue #119)
        assert (data_dir / "service.json").exists()
    assert popen.returncode == 0  # not -9 / 1: no kill, no TerminateProcess
    assert child.stopped_by == service.STOPPED_BY_REQUEST
    assert "shutdown requested" in (data_dir / "logs" / "service.log").read_text(encoding="utf-8")
    assert not (data_dir / "service.json").exists()
    assert child.process is None
    assert container.left == []  # nothing was left to end


@pytest.mark.parametrize("launchers", [1, 2], ids=["one-launcher", "two-launchers"])
def test_the_real_service_behind_a_launcher_starts_answers_and_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launchers: int
) -> None:
    """Issue #66: from a Windows venv, sys.executable is a launcher that runs the real interpreter as its child, so the
    service's pid (service.json) is not the pid the shell started. tests/support/venv_launcher.py does the same on
    every platform. The shell must still find its service (by the launch id, not the pid), report the service's own
    pid, stop it by the shutdown request (exit code 0, relayed by the launcher) and leave no service.json.
    two-launchers: what the stand-in amounts to inside a real Windows venv, where its own Popen(sys.executable) goes
    through the native launcher once more (review of PR #68)."""
    data_dir = tmp_path / "alpha"
    launcher_pid = tmp_path / "launcher.pid"
    monkeypatch.setenv(LAUNCHER_PID_ENV, str(launcher_pid))
    command = [*[sys.executable, str(LAUNCHER)] * launchers, *service.service_command(data_dir)]
    with _bounded(data_dir) as (child, container):
        info = child.start(command)
        popen = child.process
        assert popen is not None
        assert info.launch_id == child.launch_id
        # Never compared with a pid from Popen: from a Windows venv any of those may be a native launcher (review
        # review of PR #68). The service names its own pid twice: service.json and uvicorn's start line in its log.
        assert info.pid not in (popen.pid, int(launcher_pid.read_text(encoding="utf-8")))
        log = (data_dir / "logs" / "service.log").read_text(encoding="utf-8")
        assert f"Started server process [{info.pid}]" in log
        assert service.health(info)["tier"] == 1  # the product starts in tier 1 (issue #119)
    assert popen.returncode == 0
    assert child.stopped_by == service.STOPPED_BY_REQUEST
    assert not child.service_file_left_behind and not (data_dir / "service.json").exists()
    assert container.left == []
