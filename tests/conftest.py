"""Shared test setup (R-3-1).

* Qt runs offscreen; temp dir is the resolved real path (macOS /var -> /private/var made path asserts fail).
* Business time zone is fixed to Beijing on POSIX runners (Windows ignores TZ; the app formats Beijing time
  explicitly, so tests must not depend on the host zone). `utc_host` switches one test to a UTC host, to prove
  a Beijing time does not come from the host zone by accident.
* `qt_app` gives new Qt tests one QApplication with the bundled Noto Sans SC font and the app theme.
  Legacy verify_*.py subprocesses create their own QApplication and are NOT covered by this fixture; their
  font-dependent assertions are handled by named exemptions in tests/legacy/test_verify_scripts.py.
* `hardware` tests are skipped unless PAR_ALLOW_HARDWARE=1 (explicit, written authorization). Only a real
  `@pytest.mark.hardware` counts; a parametrize id that happens to read "hardware" does not.
* `@pytest.mark.exemption(reason=..., ref=..., owner=..., expires="YYYY-MM-DD", raises=..., platforms=...)` is
  the named, time-limited exemption of R-3-5, implemented in tests/exemptions.py (loaded below): inside its
  window it is an xfail that accepts only `raises`, in the call phase only; expired or incomplete, the test fails.
* Watchdog (#66): a test still running after WATCHDOG_SECONDS (PAR_TEST_WATCHDOG_SECONDS) ends the whole pytest
  process with every thread's traceback (faulthandler), so a hang - a modal dialog, a pipe nobody closes, a process
  that never exits - fails the run loudly instead of stalling it without output. Far above the slowest test.
* Qt binding (internal notes section 5): one process loads one binding, so a test session runs on PyQt5 (V1.0.3
  and everything else) or on PySide6 (the alpha service: tests/acquisition, tests/api and ALPHA_FILES). The binding
  is PAR_TEST_QT_BINDING, or PySide6 when every path given on the command line is an alpha test, else PyQt5.
  A test's binding is its `qt_binding("PyQt5" | "PySide6")` marker, else that of its file; the session deselects
  the others and says how many in the summary. tools/quality/check_all.py and CI run both sessions. In a PySide6
  session the other test folders are not even imported (they import PyQt5); importing PyQt5 there is an error.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app import qt_binding  # noqa: E402  (imports no Qt; fixes this session's binding below)

QT_BINDING_ENV = "PAR_TEST_QT_BINDING"
ALPHA_DIRS = ("tests/acquisition/", "tests/api/")
ALPHA_FILES = ("tests/unit/test_parent_watch_entry.py",)
"""Tests outside ALPHA_DIRS that run the alpha service's Qt code in-process (par_app.service_main)."""


def _relative(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(ROOT).as_posix() + ("/" if path.is_dir() else "")
    except ValueError:
        return None


def _alpha_path(relative: str) -> bool:
    return True  # public tree: every test runs in the one PySide6 session


def _session_binding() -> str:
    chosen = os.environ.get(QT_BINDING_ENV)
    if chosen:
        return chosen
    given = [Path(arg.split("::", 1)[0]) for arg in sys.argv[1:] if not arg.startswith("-")]
    paths = [_relative(path) for path in given if path.exists()]
    if paths and all(path is not None and _alpha_path(path) for path in paths):
        return qt_binding.PYSIDE6
    return qt_binding.PYSIDE6


QT_BINDING = qt_binding.select(_session_binding(), guard=True)
os.environ["PYTEST_QT_API"] = QT_BINDING.lower()  # pytest-qt would otherwise load the first binding it finds

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["TMPDIR"] = str(Path(tempfile.gettempdir()).resolve())
tempfile.tempdir = None
if hasattr(time, "tzset"):
    os.environ["TZ"] = "Asia/Shanghai"
    time.tzset()


pytest_plugins = ["tests.exemptions"]

WATCHDOG_SECONDS = float(os.environ.get("PAR_TEST_WATCHDOG_SECONDS", "900"))
"""Per-test bound of the watchdog (15 minutes; the slowest test, the shell-crash backstop, takes about two)."""


WATCHDOG_EXIT = 70
"""Exit code of a run the watchdog ended (any non-zero fails check_all)."""


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """The watchdog runs for a test's whole protocol - setup (session and module fixtures included, which are set up
    in the first test's setup), call and teardown (torn down in the last test's teardown); review rv-78 major 4.
    A timer thread, not faulthandler's own timer, so the output capture can be suspended first."""
    capture = item.config.pluginmanager.getplugin("capturemanager")
    timer = threading.Timer(watchdog_seconds(item), _expire, args=(item.nodeid, capture, watchdog_seconds(item)))
    timer.daemon = True
    timer.start()
    try:
        return (yield)
    finally:
        timer.cancel()


def watchdog_seconds(item: pytest.Item) -> float:
    """The test's watchdog bound: its `watchdog(seconds=N)` marker (a test whose fixtures run several bounded steps
    in a row, e.g. the parity runs' `recorded`, rv-70e), else WATCHDOG_SECONDS."""
    marker = item.get_closest_marker("watchdog")
    seconds = marker.kwargs.get("seconds") if marker is not None else None
    return float(seconds) if seconds else WATCHDOG_SECONDS


def _expire(nodeid: str, capture: object, seconds: float = WATCHDOG_SECONDS) -> None:
    """Diagnostics as far as they go, then the exit whatever happened (rv-78 major 3): the capture is suspended and
    the text goes straight to file descriptor 2, never through sys.stderr, which a test may have replaced."""
    try:
        try:
            suspend = getattr(capture, "suspend", None)
            if suspend is not None:
                suspend(in_=False)
        except BaseException:  # noqa: BLE001 - the exit below must happen whatever the capture does
            pass
        message = (
            f"\nWATCHDOG: {nodeid} still running after {seconds:.0f} s; ending the test run "
            "(tests/conftest.py, #66). Tracebacks of every thread:\n"
        )
        os.write(2, message.encode("utf-8", errors="replace"))
        faulthandler.dump_traceback(file=2, all_threads=True)
    finally:
        os._exit(WATCHDOG_EXIT)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """In a PySide6 session, folders and files with no alpha test are not imported (they import PyQt5)."""
    if QT_BINDING != qt_binding.PYSIDE6:
        return None
    relative = _relative(collection_path)
    if relative is None or not relative.startswith("tests/") or relative == "tests/":
        return None
    if collection_path.is_dir():
        inside = relative.startswith(ALPHA_DIRS)
        return not inside and not any(alpha.startswith(relative) for alpha in (*ALPHA_DIRS, *ALPHA_FILES))
    return collection_path.suffix == ".py" and not _alpha_path(relative)


def _binding_of(item: pytest.Item) -> str:
    marker = item.get_closest_marker("qt_binding")
    if marker is not None:
        return str(marker.args[0])
    return qt_binding.PYSIDE6  # public tree: one session, also for a probe outside tests/


_UNPUBLISHED = tuple(Path(__file__).with_name("unpublished_tests.txt").read_text("utf-8").split())
"""Public tree: tests that read V1.0.3 or unpublished documents; the private repository runs them."""


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    unpublished = [item for item in items if item.nodeid.startswith(_UNPUBLISHED)]
    if unpublished:
        config.hook.pytest_deselected(items=unpublished)
        items[:] = [item for item in items if item not in unpublished]
    skip = pytest.mark.skip(reason="hardware test: set PAR_ALLOW_HARDWARE=1 with written authorization (R-3-1)")
    for item in items:
        if item.get_closest_marker("hardware") and os.environ.get("PAR_ALLOW_HARDWARE") != "1":
            item.add_marker(skip)
    other = [item for item in items if _binding_of(item) != QT_BINDING]
    if other:
        config.hook.pytest_deselected(items=other)
        items[:] = [item for item in items if _binding_of(item) == QT_BINDING]
    config.stash[_OTHER_BINDING] = len(other)


_OTHER_BINDING = pytest.StashKey[int]()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    other = config.stash.get(_OTHER_BINDING, 0)
    line = f"Qt binding of this session: {QT_BINDING}"
    if other:
        line += f"; {other} tests deselected that run on the other binding ({QT_BINDING_ENV}; check_all.py runs both)"
    terminalreporter.write_line(line)


@pytest.fixture
def utc_host() -> Iterator[None]:
    """Switch the host zone to UTC so Beijing time cannot come from the local zone by accident."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is POSIX-only; Windows ignores TZ")
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = old
        time.tzset()


@pytest.fixture(scope="session")
def qt_app() -> Iterator[object]:
    """QApplication with the bundled font and app theme, for new `qt`/`layout` tests. In a PySide6 session: the
    QCoreApplication the alpha service runs under (no widgets, no theme)."""
    if QT_BINDING == qt_binding.PYSIDE6:
        from par_app.qt_compat import QCoreApplication

        yield QCoreApplication.instance() or QCoreApplication([])
        return
