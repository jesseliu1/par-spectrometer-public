"""The per-test watchdog of tests/conftest.py (#66: a check_all run on Windows hung for ten minutes with no output
at a modal dialog). A test that runs longer than PAR_TEST_WATCHDOG_SECONDS ends the whole pytest process with every
thread's traceback, so a hang fails the run loudly instead of stalling it."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import conftest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
RUN_SECONDS = 60.0
"""Bound of this test itself: the watchdog fires after 2 s."""
HANGING_CALL = """
import threading


def test_hangs() -> None:
    threading.Event().wait()
"""
HANGING_SESSION_SETUP = """
import threading

import pytest


@pytest.fixture(scope="session")
def slow_resource() -> None:
    threading.Event().wait()


def test_hangs(slow_resource: None) -> None:
    pass
"""
HANGING_SESSION_TEARDOWN = """
import threading

import pytest


@pytest.fixture(scope="session")
def slow_resource():
    yield
    threading.Event().wait()


def test_hangs(slow_resource: None) -> None:
    pass
"""
HANGING_WITHOUT_A_USABLE_STDERR = """
import sys
import threading


class NoFile:
    def write(self, text: str) -> int:
        raise OSError("no stderr")

    def flush(self) -> None:
        raise OSError("no stderr")

    def fileno(self) -> int:
        raise OSError("no fileno")


def test_hangs() -> None:
    sys.stderr = NoFile()
    threading.Event().wait()
"""


def _run(tmp_path: Path, probe: str, *options: str) -> subprocess.CompletedProcess[str]:
    test = tmp_path / "test_hanging_probe.py"
    test.write_text(probe, encoding="utf-8")
    env = dict(os.environ, PAR_TEST_WATCHDOG_SECONDS="2", PAR_TEST_QT_BINDING="PySide6")
    return subprocess.run(  # the repository's conftest as a plugin: the probe lives outside tests/
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "tests.conftest", "-q", *options, str(test)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=RUN_SECONDS,
    )


@pytest.mark.parametrize(
    "probe",
    [HANGING_CALL, HANGING_SESSION_SETUP, HANGING_SESSION_TEARDOWN],
    ids=["test-body", "session-fixture-setup", "session-fixture-teardown"],
)
def test_a_hang_anywhere_in_a_test_s_run_ends_it_with_tracebacks(tmp_path: Path, probe: str) -> None:
    """review rv-78 major 4: the watchdog covers setup, call and teardown, session fixtures included."""
    done = _run(tmp_path, probe)
    output = done.stdout + done.stderr
    assert done.returncode == conftest.WATCHDOG_EXIT, output
    assert "WATCHDOG: " in output and "test_hanging_probe.py" in output, output


def test_the_run_ends_even_when_the_diagnostics_fail(tmp_path: Path) -> None:
    """rv-78 major 3: with -s and a stderr that cannot be written, the exit must still happen."""
    done = _run(tmp_path, HANGING_WITHOUT_A_USABLE_STDERR, "-s")
    assert done.returncode == conftest.WATCHDOG_EXIT, done.stdout + done.stderr


def test_the_watchdog_is_generous_by_default() -> None:
    assert conftest.WATCHDOG_SECONDS >= 600  # far above the slowest test (the 60 s shell-crash backstop and setup)
