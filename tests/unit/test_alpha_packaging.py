"""2.0.0-alpha packaging: entry point, single-instance lock, shell watch, release tool, scripts and CI workflow.

Windows-only code (named mutex, the shell-process handle, WebView2 download and signature check, the frozen exe)
runs against fakes or is checked as text here; it is NOT VERIFIED ON WINDOWS until build_alpha.ps1 has been run there
(internal notes). Every file is written under tmp_path (R-4-7).
"""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.utils import canonicalize_name

import main_v2
import par_shell.__main__ as shell_entry
from par_app import alpha_info, parent_watch
from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_shell import instance, service
from tools import alpha_qt, alpha_release

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_WEBVIEW2_URL = "https://go.microsoft.com/fwlink/?linkid=2124701"


# ------------------------------------------------------------------ entry point


def test_entry_dispatches_service_self_test_and_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, Any]] = []
    import par_app.service_main as service_entry

    monkeypatch.setattr(service_entry, "main", lambda argv: calls.append(("service", argv)) or 0)
    monkeypatch.setattr(shell_entry, "main", lambda argv: calls.append(("shell", argv)) or 0)
    monkeypatch.setattr(main_v2, "self_test", lambda report: calls.append(("self-test", report)) or 0)
    assert main_v2.main(["--service", "--port", "0"]) == 0
    assert main_v2.main([]) == 0
    assert main_v2.main(["--browser"]) == 0
    assert main_v2.main(["--alpha-self-test", str(tmp_path / "r.json")]) == 0
    assert main_v2.main(["--alpha-self-test"]) == 2
    assert calls == [
        ("service", ["--port", "0"]),
        ("shell", []),
        ("shell", ["--browser"]),
        ("self-test", tmp_path / "r.json"),
    ]


def test_entry_never_imports_qt_or_v1_modules_at_top_level() -> None:
    tree = ast.parse((ROOT / "main_v2.py").read_text(encoding="utf-8"))
    top = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    names = {alias.name for node in top if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module or "" for node in top if isinstance(node, ast.ImportFrom)}
    assert names <= {"__future__", "json", "os", "sys", "traceback", "collections.abc", "pathlib"}


def test_self_test_entry_writes_a_report_instead_of_raising(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Review N-3: an exception in the windowed exe would open a traceback dialog and hang an unattended build."""

    def broken(report: Path) -> int:
        raise ImportError("No module named 'uvicorn.loops.auto'")

    monkeypatch.setattr(main_v2, "_run_self_test", broken)
    report = tmp_path / "missing folder" / "report.json"
    assert main_v2.self_test(report) == 1
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["passed"] is False and "uvicorn.loops.auto" in result["error"]
    assert main_v2.self_test(report) == 1  # the existing report is kept, still no exception
    assert json.loads(report.read_text(encoding="utf-8")) == result


def test_build_commit_comes_from_the_bundle_unless_already_set(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    assert main_v2.export_build_commit(None, environ) is None
    assert main_v2.export_build_commit(tmp_path, environ) is None  # no build_info.json: health says null
    (tmp_path / main_v2.BUILD_INFO).write_text(json.dumps({"commit": "abc123"}), encoding="utf-8")
    assert main_v2.export_build_commit(tmp_path, environ) == "abc123"
    assert environ == {main_v2.BUILD_COMMIT_ENV: "abc123"}
    assert main_v2.export_build_commit(tmp_path, {main_v2.BUILD_COMMIT_ENV: "set"}) == "set"
    (tmp_path / main_v2.BUILD_INFO).write_text("{", encoding="utf-8")
    assert main_v2.export_build_commit(tmp_path, {}) is None


# ------------------------------------------------------------------ single-instance lock


class FakeMutex:
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.closed: list[int] = []
        self.next_handle = 100

    def create(self, name: str) -> tuple[int, int]:
        self.next_handle += 1
        exists = name in self.names
        self.names.add(name)
        return self.next_handle, instance.ERROR_ALREADY_EXISTS if exists else 0

    def close(self, handle: int) -> None:
        self.closed.append(handle)


def test_windows_mutex_admits_one_alpha_shell(tmp_path: Path) -> None:
    mutex = FakeMutex()
    first = instance.InstanceLock(tmp_path, platform="win32", mutex=mutex)
    second = instance.InstanceLock(tmp_path, platform="win32", mutex=mutex)
    assert first.acquire()
    assert mutex.names == {"Local\\PAR_Spectrometer_2.SingleInstance"}
    assert not second.acquire()
    assert mutex.closed == [102]  # the second handle is closed at once
    first.release()
    assert mutex.closed == [102, 101]


def test_windows_mutex_failure_is_an_error_not_a_free_pass(tmp_path: Path) -> None:
    class Broken(FakeMutex):
        def create(self, name: str) -> tuple[int, int]:
            return 0, 87  # ERROR_INVALID_PARAMETER

    with pytest.raises(OSError, match="CreateMutexW"):
        instance.InstanceLock(tmp_path, platform="win32", mutex=Broken()).acquire()


def test_a_mutex_held_by_an_elevated_alpha_counts_as_running(tmp_path: Path) -> None:
    """Review N-6: CreateMutexW on a mutex an elevated process created fails with ERROR_ACCESS_DENIED."""

    class Elevated(FakeMutex):
        def create(self, name: str) -> tuple[int, int]:
            return 0, instance.ERROR_ACCESS_DENIED

    assert not instance.InstanceLock(tmp_path, platform="win32", mutex=Elevated()).acquire()


POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="file lock; Windows uses the named mutex (faked above)")


@POSIX_ONLY
def test_file_lock_admits_one_alpha_shell_per_data_folder(tmp_path: Path) -> None:
    with instance.InstanceLock(tmp_path) as first:
        assert first.acquire()
        assert not instance.InstanceLock(tmp_path).acquire()
    with instance.InstanceLock(tmp_path) as again:
        assert again.acquire()


@POSIX_ONLY
def test_a_second_shell_does_not_start_a_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    told: list[str] = []
    monkeypatch.setattr(shell_entry, "webview2_available", lambda: True)
    monkeypatch.setattr(shell_entry, "ask", lambda text, yes_no: told.append(text) or False)
    monkeypatch.setattr(shell_entry, "ServiceProcess", lambda *a, **k: pytest.fail("service must not start"))
    with instance.InstanceLock(tmp_path) as held:
        assert held.acquire()
        assert shell_entry.main(["--data-dir", str(tmp_path)]) == 1
    assert told == [shell_entry.ALREADY_RUNNING]


# ------------------------------------------------------------------ the service watches the shell (D-223)


class FakeKernel32:
    """OpenProcess / WaitForSingleObject / CloseHandle as par_app.parent_watch.windows_waiter calls them."""

    def __init__(self, handle: int = 77) -> None:
        self.handle = handle
        self.calls: list[tuple[str, Any]] = []

    def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:  # noqa: N802 (Win32 name)
        self.calls.append(("open", (access, inherit, pid)))
        return self.handle

    def WaitForSingleObject(self, handle: int, milliseconds: int) -> int:  # noqa: N802
        self.calls.append(("wait", (handle, milliseconds)))
        return 0

    def CloseHandle(self, handle: int) -> int:  # noqa: N802
        self.calls.append(("close", handle))
        return 1


def test_windows_service_holds_a_synchronize_handle_to_the_shell() -> None:
    """Opened at start (a later process with the same pid is never taken for the shell), waited on, then closed."""
    kernel32 = FakeKernel32()
    wait = parent_watch.windows_waiter(4242, kernel32, lambda: 0)
    assert kernel32.calls == [("open", (parent_watch.SYNCHRONIZE, False, 4242))]
    wait()
    assert kernel32.calls[1:] == [("wait", (77, parent_watch.INFINITE)), ("close", 77)]


def test_windows_shell_already_gone_or_not_watchable() -> None:
    gone = parent_watch.windows_waiter(4242, FakeKernel32(handle=0), lambda: parent_watch.ERROR_INVALID_PARAMETER)
    assert gone() is None  # returns at once: the shutdown follows
    with pytest.raises(OSError) as raised:
        parent_watch.windows_waiter(4242, FakeKernel32(handle=0), lambda: 5)
    assert raised.value.errno == 5


def test_posix_waiter_returns_when_the_service_is_re_parented() -> None:
    parents = iter([4242, 4242, 4242, 1])
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    wait = parent_watch.posix_waiter(4242, clock, getppid=lambda: next(parents))
    wait()
    assert clock.monotonic() == 2 * parent_watch.POLL_SECONDS


def test_posix_waiter_polls_a_pid_that_is_not_the_direct_parent() -> None:
    alive = iter([True, True, False])
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    parent_watch.posix_waiter(4242, clock, getppid=lambda: 1, exists=lambda pid: next(alive))()
    assert clock.monotonic() == 2 * parent_watch.POLL_SECONDS


def test_shell_gone_stops_gracefully_then_the_backstop_ends_the_process() -> None:
    """The stop is asked first; os._exit only BACKSTOP_SECONDS later if the process is still running."""
    events: list[tuple[str, float]] = []
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    thread = parent_watch.watch_parent(
        4242,
        lambda: events.append(("stop", clock.monotonic())),
        clock,
        waiter=lambda: None,
        exit_process=lambda code: events.append((f"exit {code}", clock.monotonic())),
    )
    assert thread is not None
    thread.join(10)
    assert events == [("stop", 0.0), (f"exit {parent_watch.EXIT_BACKSTOP}", parent_watch.BACKSTOP_SECONDS)]
    assert parent_watch.BACKSTOP_SECONDS == service.STOP_TIMEOUT_SECONDS  # the shell's own wait (16_ 1.5)
    assert parent_watch.EXIT_BACKSTOP == 3  # D-223, shadow-rules: not 0 (a clean exit) nor 2 (refused / argparse)


class _FailingHandler(logging.Handler):
    """A log whose storage is full: every flush raises (review round 2 of PR #56, major 1)."""

    def emit(self, record: logging.LogRecord) -> None:
        return None

    def flush(self) -> None:
        raise OSError(28, "simulated full log device")


@pytest.mark.parametrize("failing", ["flush", "stop"])
def test_the_backstop_ends_the_process_even_if_logging_or_the_stop_request_fails(failing: str) -> None:
    """A failing log flush (or a stop request that raises) must not end the watch thread before os._exit."""
    events: list[tuple[str, float]] = []
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    handler = _FailingHandler()
    root = logging.getLogger()

    def stop() -> None:
        events.append(("stop", clock.monotonic()))
        if failing == "stop":
            raise RuntimeError("the event loop is gone")

    root.addHandler(handler)
    try:
        thread = parent_watch.watch_parent(
            4242,
            stop,
            clock,
            waiter=lambda: None,
            exit_process=lambda code: events.append((f"exit {code}", clock.monotonic())),
        )
        assert thread is not None
        thread.join(10)
    finally:
        root.removeHandler(handler)
    assert events == [("stop", 0.0), (f"exit {parent_watch.EXIT_BACKSTOP}", parent_watch.BACKSTOP_SECONDS)]


def test_a_shell_that_cannot_be_watched_does_not_stop_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(pid: int, clock: object) -> parent_watch.Waiter:
        raise OSError(5, "OpenProcess failed")

    monkeypatch.setattr(parent_watch, "_waiter", refused)
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    assert parent_watch.watch_parent(4242, lambda: pytest.fail("stopped"), clock) is None


def test_shell_passes_its_pid_and_uses_no_kill_on_close_job() -> None:
    """review of PR #56, blocker 2: Windows' kill-on-close Job Object ended the service at once when the shell
    crashed, possibly between freeze and resume; the service now watches the shell and stops gracefully."""
    assert service.PARENT_PID == parent_watch.PARENT_PID
    command = service.service_command(Path("data"))
    assert command[command.index(service.PARENT_PID) + 1] == str(os.getpid())
    source = (ROOT / "par_shell" / "service.py").read_text(encoding="utf-8")
    assert "AssignProcessToJobObject" not in source and "KILL_ON_JOB_CLOSE" not in source
    assert not (ROOT / "par_shell" / "winjob.py").exists()


# ------------------------------------------------------------------ release tool


FAKE_PAGE = (
    '<!doctype html><html><head><script type="module" crossorigin src="/assets/index-A.js"></script>'
    '<link rel="stylesheet" crossorigin href="/assets/index-B.css"></head><body><div id="app"></div></body></html>'
)
FAKE_ASSETS = {
    "_internal/web/assets/index-A.js": b"console.log(1)",
    "_internal/web/assets/index-B.css": b"@font-face{src:url(/assets/Mono-C.ttf)}",
    "_internal/web/assets/Mono-C.ttf": b"font",
}
FAKE_MANIFEST = {
    "packages": {},
    "npm_packages": {},
    "licence_exceptions": {},
    "qt_bundled": True,
    "qt": {"runtime": {"binding": "PySide6", "version": "6.11.2", "qt": "6.11.2"}},
}


def _fake_app(root: Path, exe: str = alpha_info.EXE_NAME, installer: bool = True) -> Path:
    app = root / alpha_info.APP_NAME
    sdk = [f"_internal/webview/lib/{name}" for name in alpha_release.WEBVIEW2_SDK_FILES]
    for name in [*alpha_release.required_files(exe, webview2=installer), *sdk]:
        (app / name).parent.mkdir(parents=True, exist_ok=True)
        (app / name).write_bytes(b"x")
    (app / "_internal/web/index.html").write_text(FAKE_PAGE, encoding="utf-8")
    for name, body in FAKE_ASSETS.items():
        (app / name).parent.mkdir(parents=True, exist_ok=True)
        (app / name).write_bytes(body)
    (app / "_internal/PySide6").mkdir()
    (app / "_internal/PySide6/QtCore.pyd").write_bytes(b"x")
    (app / alpha_release.MANIFEST).write_text(json.dumps(FAKE_MANIFEST), encoding="utf-8")
    return app


@pytest.mark.parametrize("name", alpha_release.WEBVIEW2_SDK_FILES)
def test_a_windows_package_needs_the_webview2_sdk_binaries(tmp_path: Path, name: str) -> None:
    """Review N-2: without them the window cannot open on Windows."""
    app = _fake_app(tmp_path)
    (app / "_internal" / "webview" / "lib" / name).unlink()
    with pytest.raises(ValueError, match=name):
        alpha_release.validate(app)
    (app / "PAR_Spectrometer_2").write_bytes(b"x")
    alpha_release.validate(app, exe_name="PAR_Spectrometer_2")  # a macOS/Linux build has no .exe and no SDK


def _fake_web(root: Path) -> Path:
    web = root / "web"
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "par-spectrometer-web"},
            "node_modules/vue": {"version": "3.5.44", "license": "MIT"},
            "node_modules/@vue/shared": {"version": "3.5.44", "license": "MIT"},
            "node_modules/echarts": {"version": "6.1.0", "license": "Apache-2.0"},
            "node_modules/vitest": {"version": "5.0.5", "license": "MIT", "dev": True},
            "node_modules/typescript": {"version": "5.9.3", "license": "Apache-2.0", "devOptional": True},
            "node_modules/vite": {"version": "8.3.4", "license": "MIT", "dev": True},
            "node_modules/@vitejs/plugin-vue": {"version": "6.0.10", "license": "MIT", "dev": True},
        },
    }
    for key in lock["packages"]:
        if key:
            (web / key).mkdir(parents=True)
            (web / key / "LICENSE").write_text(f"licence of {key}", encoding="utf-8")
    (web / "node_modules/echarts/licenses").mkdir()
    (web / "node_modules/echarts/licenses/LICENSE-d3").write_text("d3", encoding="utf-8")
    (web / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    return web


INSTALLER = {
    "file": alpha_release.REDIST_INSTALLER,
    "source": OFFICIAL_WEBVIEW2_URL,
    "original_name": "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    "sha256": "ab" * 32,
    "size": 180_000_000,
    "signer": "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US",
    "version": "141.0.3537.71",
    "product": "Microsoft Edge WebView2 Runtime",
    "description": "Microsoft Edge WebView2 Runtime Installer",
}
MAC_ONLY_GAPS = {
    name: "test only: macOS-only distribution without a licence file"
    for name in ("pyobjc-framework-Security", "pyobjc-framework-UniformTypeIdentifiers")
}
"""Only for running write_metadata on a developer Mac; never part of alpha_release.LICENCE_EXCEPTIONS."""


def _metadata(app: Path, web: Path, build_info: dict[str, Any], installer: dict[str, Any] | None) -> dict[str, Any]:
    exceptions = alpha_release.LICENCE_EXCEPTIONS | MAC_ONLY_GAPS
    return alpha_release.write_metadata(app, None, web, build_info, installer, exceptions=exceptions)


def test_metadata_lists_runtime_licences_fonts_and_s6(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    build_info = {"commit": "abc123", "dirty": False, "built_at": "2026-10-18T00:00:00+00:00"}
    manifest = _metadata(app, _fake_web(tmp_path), build_info, INSTALLER)
    assert manifest["version"] == alpha_info.ALPHA_VERSION and manifest["channel"] == "alpha"
    assert manifest["not_for_release"] is True and manifest["commit"] == "abc123"
    assert manifest["qt_bundled"] is True
    assert {"fastapi", "uvicorn", "pywebview", "starlette", "pydantic"} <= set(manifest["packages"])
    packaged = {canonicalize_name(name) for name in manifest["packages"]}
    assert {"pyside6-essentials", "shiboken6", "pymodbus", "pyserial"} <= packaged
    assert not {"pyqt5", "pyqt5-qt5", "pyqt5-sip"} & packaged
    assert set(manifest["npm_packages"]) == {
        "@vitejs/plugin-vue@6.0.10",
        "@vue/shared@3.5.44",
        "echarts@6.1.0",
        "vite@8.3.4",
        "vue@3.5.44",
    }
    assert manifest["npm_packages"]["vite@8.3.4"]["role"].startswith("build-tool helpers")
    licences = app / alpha_release.LICENSES_DIR
    assert (licences / "CPython" / "LICENSE.txt").is_file()
    assert (licences / "npm" / "echarts@6.1.0" / "licenses" / "LICENSE-d3").is_file()
    assert (licences / "npm" / "@vue__shared@3.5.44" / "LICENSE").is_file()
    assert any((licences / "pypi" / "fastapi").rglob("LICENSE*"))
    assert (app / alpha_release.README).read_text(encoding="utf-8").startswith("PAR 光谱仪专用软件 V2.0 试用版")
    notices = (app / alpha_release.NOTICES).read_text(encoding="utf-8")
    for text in (
        "NOT FOR RELEASE",
        alpha_info.window_title(),
        "This build CONTAINS PySide6/Qt 6",
        alpha_qt.S6_ALPHA,
        "LGPL v3",
        "S-6",
        "GPL v3",
        "Noto Sans SC",
        "JetBrains Mono 2.304",
        "SIL Open Font License 1.1",
        "echarts@6.1.0 - Apache-2.0",
        "bootloader exception",
        "ab" * 32,
        "O=Microsoft Corporation",
    ):
        assert text in notices, text
    flowing = " ".join(notices.split())  # lines are wrapped at 112 characters
    assert "the alpha runs on PySide6 under the LGPL v3 and contains no PyQt5" in flowing
    assert "PyQt5 - GPL" not in flowing


def test_metadata_says_so_when_qt_is_missing_and_package_refuses_it(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    (app / "_internal/PySide6/QtCore.pyd").unlink()
    (app / "_internal/PySide6").rmdir()
    manifest = _metadata(app, _fake_web(tmp_path), {}, None)
    notices = (app / alpha_release.NOTICES).read_text(encoding="utf-8")
    assert manifest["qt_bundled"] is False and manifest["qt"] is None
    assert "does NOT contain PySide6 or Qt files" in notices and "No WebView2 Runtime installer is shipped" in notices
    with pytest.raises(ValueError, match="PySide6"):
        alpha_qt.check_qt(app)  # validate() runs it (after the licence check, which fails on a Mac first)


def test_metadata_needs_installed_npm_packages(tmp_path: Path) -> None:
    web = _fake_web(tmp_path)
    (web / "node_modules" / "vue" / "LICENSE").unlink()
    (web / "node_modules" / "vue").rmdir()
    with pytest.raises(FileNotFoundError, match="npm ci"):
        _metadata(_fake_app(tmp_path), web, {}, None)


def test_every_shipped_npm_package_declares_a_licence() -> None:
    """Completeness of the npm part of the notices, from the committed lock file (no node_modules needed)."""
    lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    shipped = {
        key: entry
        for key, entry in lock["packages"].items()
        if key
        and (
            not (entry.get("dev") or entry.get("devOptional"))
            or key.rsplit("node_modules/", 1)[-1] in alpha_release.BUNDLER_HELPERS
        )
    }
    names = {key.rsplit("node_modules/", 1)[-1] for key in shipped}
    assert {"vue", "echarts", "zrender", "tslib", "vite", "rolldown", "@vitejs/plugin-vue"} <= names
    assert all(entry.get("license") for entry in shipped.values()), [
        k for k, e in shipped.items() if not e.get("license")
    ]


def test_package_writes_the_named_archive_and_checksum(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    archive = alpha_release.package(app, tmp_path)
    assert archive.name == "PAR_Spectrometer_2.0.0-alpha.9.zip"
    with zipfile.ZipFile(archive) as stream:
        names = stream.namelist()
    assert "PAR_Spectrometer_2/PAR_Spectrometer_2.exe" in names
    assert "PAR_Spectrometer_2/redist/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" in names
    assert all(name.startswith("PAR_Spectrometer_2/") for name in names)
    line = (tmp_path / f"{archive.name}.sha256").read_text(encoding="ascii")
    assert line == f"{alpha_release.sha256(archive)}  {archive.name}\n"


@pytest.mark.parametrize(
    "intruder",
    [
        "PAR_Spectrometer.exe",
        "data/devices/p1.sqlite3",
        "config/app_config.json",
        "logs/service.log",
        "_internal/service.json",
        "_internal/x.sqlite3-wal",
        "_internal/app_config.json",
        "snapshot.sqlite.partial",
        "shell.lock",
    ],
)
def test_package_refuses_v1_program_runtime_state_and_user_data(tmp_path: Path, intruder: str) -> None:
    app = _fake_app(tmp_path)
    (app / intruder).parent.mkdir(parents=True, exist_ok=True)
    (app / intruder).write_bytes(b"x")
    with pytest.raises(ValueError):
        alpha_release.package(app, tmp_path)
    assert not (tmp_path / alpha_info.archive_name()).exists()


@pytest.mark.parametrize("missing", alpha_release.required_files())
def test_package_refuses_a_folder_without_a_required_file(tmp_path: Path, missing: str) -> None:
    app = _fake_app(tmp_path)
    (app / missing).unlink()
    with pytest.raises(ValueError, match="required file missing"):
        alpha_release.validate(app)


def test_names_command_feeds_the_build_script(capsys: pytest.CaptureFixture[str]) -> None:
    assert alpha_release.main(["names"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "version": "2.0.0-alpha.9",
        "app_name": "PAR_Spectrometer_2",
        "exe": "PAR_Spectrometer_2.exe",
        "archive": "PAR_Spectrometer_2.0.0-alpha.9.zip",
    }


# ------------------------------------------------------------------ build script, spec, workflow


def test_build_script_downloads_from_microsoft_and_checks_the_signature() -> None:
    script = (ROOT / "build_alpha.ps1").read_text(encoding="utf-8")
    assert script.isascii(), "Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page"
    assert f'$WebView2Url = "{OFFICIAL_WEBVIEW2_URL}"' in script
    assert "Get-AuthenticodeSignature" in script and '-ne "Valid"' in script
    assert "O=Microsoft Corporation" in script and "$WebView2Sha256" in script
    assert "npm ci" in script and "npm run build" in script
    assert "PAR_ALPHA_BUILD_INFO" in script and "--alpha-self-test" in script
    for step in ("$Tool metadata", "$Tool package", "--webview2 $WebView2Info"):
        assert step in script, step


def test_no_microsoft_installer_is_committed() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "*.exe", "*.msi", "redist/*"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert tracked == []
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "redist/" in ignore and "*.exe" in ignore


def test_spec_bundles_web_and_entry_and_qtcore_only() -> None:
    """Tiers 1/2 (16_ 8.2, 18_): PySide6's QtCore, pymodbus, pyserial and V1.0.3's acquisition modules are packaged;
    PyQt5, every other Qt module, the old UI and matplotlib are excluded."""
    text = (ROOT / "PAR_Spectrometer_2.spec").read_text(encoding="utf-8")
    tree = ast.parse(text)  # valid Python (PyInstaller names such as Analysis are provided when it runs)
    assert "main_v2.py" in text and "(str(WEB_DIST), 'web')" in text and "contents_directory='_internal'" in text
    assert "console=False" in text and "(str(ROOT / 'logo.png'), '.')" in text
    names: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "QT_UNUSED":
                names["qt"] = {elt.value for elt in node.value.generators[0].iter.elts}  # type: ignore[attr-defined]
            if node.targets[0].id == "excludes":
                names["excludes"] = {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)}
    assert {"QtGui", "QtWidgets", "QtNetwork", "QtQml", "QtDBus"} <= names["qt"] and "QtCore" not in names["qt"]
    assert "'PySide6.' + name" in text
    assert {"matplotlib", "par_app.ui", "par_app.theme", "PyQt5", "PyQt6", "PySide2"} <= names["excludes"]
    for needed in ("PySide6", "shiboken6", "pymodbus", "serial", "par_app.coordinator", "par_app.protocol"):
        assert needed not in names["excludes"], needed
    assert "'/translations/'" in text
    for font in ("NotoSansSC.ttf", "OFL.txt", "JetBrainsMono.ttf", "JetBrainsMono-OFL.txt"):
        assert f"fonts/{font}" in text


def test_alpha_workflow_runs_only_by_hand() -> None:
    """Since 4c5225a (owner, 2026-10-27; 05_ section 7) the alpha package is built only by hand, not on pushes."""
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "package-alpha.yml").read_text(encoding="utf-8"))
    triggers = workflow[True]  # YAML 1.1 reads the key "on" as True
    assert set(triggers) == {"workflow_dispatch"}
    job = workflow["jobs"]["windows-package-alpha"]
    assert job["runs-on"] == "windows-latest"
    steps = {step.get("name", step.get("uses")): step for step in job["steps"]}
    upload = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact"))
    assert "NOT-FOR-RELEASE" in upload["with"]["name"]
    assert any("build_alpha.ps1" in str(step.get("run", "")) for step in steps.values())
    build = next(str(step["run"]) for step in steps.values() if "build_alpha.ps1" in str(step.get("run", "")))
    assert "-SkipSelfTest" not in build and "self-test-report.json" in build  # self-test runs before the ZIP
