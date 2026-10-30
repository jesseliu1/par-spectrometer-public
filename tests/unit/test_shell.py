"""par_shell: service child process, WebView2 check, window (13_ 3.1, appendix C).

pywebview itself is replaced by fakes here, so these tests need no window system; the real window was smoked
locally on macOS (`python -m par_shell --smoke 15`, recorded in the PR). The Windows paths (registry, CTRL_BREAK)
run against fakes only and are marked as not verified on Windows.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from par_app.application import paths as alpha_paths
from par_app.domain.clock import BEIJING_TZ, FakeClock
from par_shell import service, webview2, window
from par_shell.__main__ import main as shell_main
from par_shell.service import ServiceError, ServiceInfo, ServiceProcess

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "tests" / "support" / "venv_launcher.py"
INFO = ServiceInfo(base_url="http://127.0.0.1:50123", port=50123, token="t/k+n", pid=4321, version="2.0.0-alpha.9")


def test_the_shell_imports_nothing_from_par_app_but_the_domain() -> None:
    """13_ section 4: the shell talks to the service over HTTP only. `par_app.domain` (pure types such as the
    Clock, R-1-6) is the one allowed import; review M-4."""
    for path in (ROOT / "par_shell").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom) and node.level == 0
                else []
            )
            offending = [
                name for name in names if name.split(".")[0] == "par_app" and not name.startswith("par_app.domain")
            ]
            assert not offending, f"{path.name} imports {offending}"


@pytest.mark.parametrize(
    "environ",
    [{"PAR_ALPHA_DATA_DIR": "/x/alpha"}, {"LOCALAPPDATA": "C:/Users/u/AppData/Local"}, {}],
)
def test_default_data_dir_matches_the_service(monkeypatch: pytest.MonkeyPatch, environ: dict[str, str]) -> None:
    for name in ("PAR_ALPHA_DATA_DIR", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    assert service.default_data_dir(environ) == alpha_paths.default_data_dir()


def test_service_command_from_source_and_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert service.service_command(tmp_path) == [
        sys.executable,
        "-m",
        "par_app.service_main",
        "--port",
        "0",
        "--data-dir",
        str(tmp_path),
        service.STOP_ON_STDIN_EOF,
        service.PARENT_PID,
        str(os.getpid()),
    ]
    from par_app.api.__main__ import STOP_ON_STDIN_EOF

    assert service.STOP_ON_STDIN_EOF == STOP_ON_STDIN_EOF
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = service.service_command(tmp_path, tmp_path / "web")
    assert command[:2] == [sys.executable, service.SERVICE_FLAG]
    assert command[-2:] == ["--web-dir", str(tmp_path / "web")]


def test_read_service_file_accepts_only_a_complete_file(tmp_path: Path) -> None:
    path = tmp_path / "service.json"
    assert service.read_service_file(path) is None
    path.write_text("{", encoding="utf-8")
    assert service.read_service_file(path) is None
    path.write_text(json.dumps({"base_url": INFO.base_url, "port": 1}), encoding="utf-8")
    assert service.read_service_file(path) is None
    path.write_text(json.dumps(vars(INFO) | {"started_at": "x"}), encoding="utf-8")
    assert service.read_service_file(path) == INFO
    path.write_text(json.dumps(vars(INFO) | {"launch_id": None}), encoding="utf-8")  # started by hand
    assert service.read_service_file(path) == INFO
    path.write_text(json.dumps(vars(INFO) | {"launch_id": "9f"}), encoding="utf-8")
    assert service.read_service_file(path) == dataclasses.replace(INFO, launch_id="9f")


class FakeStdin:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process

    def close(self) -> None:
        self.process.calls.append("close stdin")
        if not self.process.ignores_stdin:
            self.process.returncode = 0


class FakeProcess:
    def __init__(
        self,
        pid: int = INFO.pid,
        exits: int | None = None,
        ignores_terminate: bool = False,
        ignores_stdin: bool | None = None,
    ) -> None:
        self.pid = pid
        self.returncode = exits
        self.ignores_terminate = ignores_terminate
        self.ignores_stdin = ignores_terminate if ignores_stdin is None else ignores_stdin
        self.calls: list[str] = []
        self.stdin = FakeStdin(self)

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.calls.append("terminate")
        if not self.ignores_terminate:
            self.returncode = 0

    def send_signal(self, sig: int) -> None:
        self.calls.append(f"signal {sig}")
        self.terminate()

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("service", timeout or 0)
        return self.returncode

    def kill(self) -> None:
        self.calls.append("kill")
        self.returncode = -9


def _fake_clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 18, 9, 0, tzinfo=BEIJING_TZ))


def _process(tmp_path: Path, fake: FakeProcess, clock: FakeClock) -> ServiceProcess:
    return ServiceProcess(tmp_path, popen=lambda *a, **k: fake, clock=clock)


SERVICE_PID = 8765
"""The service's own pid in service.json: not the pid the shell started when a launcher is in between (#66)."""


class WritesServiceFileOnSleep(FakeClock):
    """A FakeClock whose waits also make the child's service.json appear, as the real child would: with the launch id
    the shell gave it (environment) and its own pid."""

    def __init__(self, wall: datetime, path: Path) -> None:
        super().__init__(wall)
        self.path = path
        self.launch_id: str | None = None

    def popen(self, fake: FakeProcess) -> Any:  # noqa: ANN401 (stands in for subprocess.Popen)
        def start(*_args: object, **kwargs: Any) -> FakeProcess:  # noqa: ANN401
            self.launch_id = kwargs["env"][service.LAUNCH_ID_ENV]
            return fake

        return start

    def sleep(self, seconds: float) -> None:
        super().sleep(seconds)
        payload = vars(INFO) | {"pid": SERVICE_PID, "launch_id": self.launch_id}
        self.path.write_text(json.dumps(payload), encoding="utf-8")


def test_the_default_clock_is_the_system_clock(tmp_path: Path) -> None:
    """R-1-6 (review M-4): without an injected clock the shell reads time through SystemClock, not time.*."""
    from par_app.domain.clock import SystemClock

    assert isinstance(ServiceProcess(tmp_path)._clock, SystemClock)


def test_start_waits_for_the_childs_own_service_file_and_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeProcess()
    clock = WritesServiceFileOnSleep(datetime(2026, 10, 18, 9, 0, tzinfo=BEIJING_TZ), tmp_path / "service.json")
    process = ServiceProcess(tmp_path, popen=clock.popen(fake), clock=clock)
    stale = vars(INFO) | {"launch_id": "an earlier launch"}  # even with the child's pid it is not the child's (#66)
    (tmp_path / "service.json").write_text(json.dumps(stale), encoding="utf-8")
    checks: list[ServiceInfo] = []

    def healthy(info: ServiceInfo) -> dict[str, Any]:
        checks.append(info)
        if len(checks) == 1:
            raise OSError("not listening yet")
        return {"status": "ok"}

    monkeypatch.setattr(service, "health", healthy)
    info = process.start(["service"])
    assert process.launch_id is not None and len(process.launch_id) == 2 * service.LAUNCH_ID_BYTES
    assert info == dataclasses.replace(INFO, pid=SERVICE_PID, launch_id=process.launch_id)
    assert len(checks) == 2
    assert all(check.launch_id == process.launch_id for check in checks)  # the stale file was never asked


def test_every_start_gets_a_new_launch_id_and_the_service_uses_the_same_variable(tmp_path: Path) -> None:
    from par_app.api.__main__ import LAUNCH_ID_ENV

    assert service.LAUNCH_ID_ENV == LAUNCH_ID_ENV
    ids = []
    for _ in range(2):
        clock = WritesServiceFileOnSleep(datetime(2026, 10, 18, 9, 0, tzinfo=BEIJING_TZ), tmp_path / "service.json")
        process = ServiceProcess(tmp_path, popen=clock.popen(FakeProcess()), clock=clock)
        with pytest.raises(ServiceError):
            process.start(["service"], timeout=0.0)
        ids.append(clock.launch_id)
    assert ids[0] and ids[1] and ids[0] != ids[1]


def test_start_reports_a_child_that_exits(tmp_path: Path) -> None:
    process = _process(tmp_path, FakeProcess(exits=2), _fake_clock())
    with pytest.raises(ServiceError, match="退出码 2"):
        process.start(["service"])


def test_start_gives_up_after_the_timeout_and_stops_the_child(tmp_path: Path) -> None:
    fake = FakeProcess()
    process = _process(tmp_path, fake, _fake_clock())
    with pytest.raises(ServiceError, match="没有就绪"):
        process.start(["service"], timeout=1.0)
    assert fake.calls  # asked to stop
    assert process.process is None


def test_stop_kills_a_child_that_does_not_exit_and_removes_only_its_own_service_file(tmp_path: Path) -> None:
    fake = FakeProcess(ignores_terminate=True)
    process = _process(tmp_path, fake, _fake_clock())
    process.process = fake  # type: ignore[assignment]
    process.launch_id = "launch 1"
    (tmp_path / "service.json").write_text(json.dumps(vars(INFO) | {"launch_id": "launch 1"}), encoding="utf-8")
    process.stop(timeout=0.01)
    assert fake.calls[-1] == "kill"
    assert not (tmp_path / "service.json").exists()

    other = FakeProcess()  # the same pid: a pid says nothing behind a launcher (#66)
    process.process = other  # type: ignore[assignment]
    another = vars(INFO) | {"launch_id": "another instance"}
    (tmp_path / "service.json").write_text(json.dumps(another), encoding="utf-8")
    process.stop()
    assert (tmp_path / "service.json").exists()


def test_stop_closes_stdin_first_and_signals_only_when_that_is_ignored(tmp_path: Path) -> None:
    """Review Q-1: the end of stdin is the stop request (works without a console); the signal is the fallback."""
    polite = FakeProcess()
    process = _process(tmp_path, polite, _fake_clock())
    process.process = polite  # type: ignore[assignment]
    process.stop()
    assert polite.calls == ["close stdin"]

    deaf = FakeProcess(ignores_stdin=True)
    process.process = deaf  # type: ignore[assignment]
    process.stop(timeout=0.01)
    assert deaf.calls[0] == "close stdin"
    assert deaf.calls[1] in ("terminate", f"signal {getattr(service.signal, 'CTRL_BREAK_EVENT', 1)}")
    assert "kill" not in deaf.calls


class FakeRegistry:
    def __init__(self, values: dict[tuple[str, str], str]) -> None:
        self.values = values

    def __call__(self, hive: str, key: str, name: str) -> str | None:
        assert name == webview2.VERSION_VALUE
        return self.values.get((hive, key))


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, None),
        ({(webview2.HKLM, webview2.WOW_CLIENT_KEY): "0.0.0.0"}, None),
        ({(webview2.HKLM, webview2.WOW_CLIENT_KEY): ""}, None),
        ({(webview2.HKLM, webview2.WOW_CLIENT_KEY): "131.0.2903.70"}, "131.0.2903.70"),
        ({(webview2.HKLM, webview2.CLIENT_KEY): "130.0.1"}, "130.0.1"),
        ({(webview2.HKCU, webview2.CLIENT_KEY): "129.0.5 "}, "129.0.5"),
    ],
)
def test_webview2_runtime_version_from_the_registry(values: dict[tuple[str, str], str], expected: str | None) -> None:
    """Appendix C detection logic, against a fake registry (NOT verified on Windows)."""
    assert webview2.runtime_version(FakeRegistry(values)) == expected


def test_webview2_is_only_required_on_windows(tmp_path: Path) -> None:
    assert webview2.webview2_available("darwin", FakeRegistry({}))
    assert not webview2.webview2_available("win32", FakeRegistry({}))
    message = webview2.missing_runtime_message(tmp_path)
    assert "未找到随包安装程序" in message and "不会自动安装" in message
    (tmp_path / "redist").mkdir()
    (tmp_path / "redist" / webview2.OFFLINE_INSTALLER).write_bytes(b"")
    assert str(tmp_path / "redist" / webview2.OFFLINE_INSTALLER) in webview2.missing_runtime_message(tmp_path)


def test_page_url_carries_the_token_in_the_fragment_only() -> None:
    assert window.page_url(INFO) == "http://127.0.0.1:50123/#token=t%2Fk%2Bn"
    assert window.window_title("2.0.0-alpha.9") == (
        "PAR 光谱仪专用软件 ASMART-GROW-SPECTRA I V2.0 试用版"
    )  # S-2, 15_ section 4: V1.0.x's title + version + notice


class FakeWindow:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.events = type("Events", (), {"loaded": threading.Event()})()
        self.events.loaded.set()
        self.destroyed = False
        self.scripts: list[str] = []

    def run_js(self, script: str) -> object:
        self.scripts.append(script)
        return self.results.pop(0) if self.results else 0

    def destroy(self) -> None:
        self.destroyed = True


class FakeWebview:
    def __init__(self, page: FakeWindow) -> None:
        self.page = page
        self.created: dict[str, Any] = {}

    def create_window(self, title: str, url: str, **options: Any) -> FakeWindow:  # noqa: ANN401
        self.created = {"title": title, "url": url, **options}
        return self.page

    def start(self, func: Any = None, args: tuple[Any, ...] = ()) -> None:  # noqa: ANN401
        if func is not None:
            func(*args)


@pytest.mark.parametrize(("results", "rendered"), [([0.0, None, 4.0], True), (["4"], True), ([2, "x"], False)])
def test_smoke_closes_the_window_and_reports_whether_the_page_rendered(
    results: list[object], rendered: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(threading.Event, "wait", lambda self, timeout=None: True)
    fake = FakeWebview(FakeWindow(results))
    assert window.open_window(INFO, smoke_seconds=0.5, webview=fake) is rendered
    assert fake.page.destroyed
    assert fake.created["title"].endswith("V2.0 试用版") and "alpha" not in fake.created["title"]
    assert fake.created["url"] == window.page_url(INFO)
    assert all("eval" not in script for script in fake.page.scripts)


def test_browser_fallback_opens_the_same_page() -> None:
    opened: list[str] = []
    assert window.open_in_browser(INFO, lambda url: opened.append(url) is None)
    assert opened == [window.page_url(INFO)]


def test_missing_webview2_and_a_declined_browser_exits_without_starting_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import par_shell.__main__ as entry

    monkeypatch.setattr(entry, "webview2_available", lambda: False)
    monkeypatch.setattr(entry, "ask", lambda text, yes_no: False)
    monkeypatch.setattr(entry, "ServiceProcess", lambda *a, **k: pytest.fail("service must not start"))
    assert shell_main([]) == 1


class FreeLock:
    """The shell's single-instance lock as a test sees it: always free, never the real mutex or lock file."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def __enter__(self) -> FreeLock:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def acquire(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_dialog_and_no_real_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """#66: par_shell.__main__.ask is a modal Windows message box that blocks until someone closes it, and the real
    InstanceLock is a session-wide mutex on Windows that a running alpha holds. Every test here gets a free fake
    lock, and a dialog fails the test at once instead of waiting for a click that never comes."""
    import par_shell.__main__ as entry

    def no_dialog(text: str, yes_no: bool) -> bool:
        raise AssertionError(f"the shell would have shown a modal dialog in a test: {text!r}")

    monkeypatch.setattr(entry, "InstanceLock", FreeLock)
    monkeypatch.setattr(entry, "ask", no_dialog)


class FakeService:
    instances: list[FakeService] = []

    def __init__(self, data_dir: Path, web_dir: Path | None = None) -> None:
        self.data_dir = data_dir
        self.events: list[str] = []
        FakeService.instances.append(self)

    def __enter__(self) -> FakeService:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.events.append("stop")

    def start(self) -> ServiceInfo:
        self.events.append("start")
        return INFO


def test_main_s_tests_do_not_depend_on_another_alpha_running(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#66 (Windows, check_all --binding PySide6): the run hung after test 29 of this file, at the next main() test.
    main() takes the shell's single-instance lock - on Windows a named mutex for the whole logon session, whatever
    the data directory - and, refused because an alpha was running on that computer, showed a modal message box
    nobody could see or close. A test of main() must neither take the real lock nor open a dialog."""
    import par_shell.__main__ as entry
    from par_shell import instance

    FakeService.instances.clear()
    monkeypatch.setattr(entry, "webview2_available", lambda: True)
    monkeypatch.setattr(entry, "ServiceProcess", FakeService)
    monkeypatch.setattr(
        entry, "open_window", lambda info, smoke_seconds=None: FakeService.instances[0].events.append("window") is None
    )
    with instance.InstanceLock(tmp_path) as running:  # another alpha holds the real lock (on Windows: any data dir)
        if not running.acquire():
            pytest.skip("an alpha shell is running on this machine; its lock is not touched")
        assert shell_main(["--data-dir", str(tmp_path)]) == 0
    assert FakeService.instances[0].events == ["start", "window", "stop"]


@pytest.mark.parametrize("outcome", ["closed", "not rendered", "raises"])
def test_closing_the_window_stops_the_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: str) -> None:
    """Review N-3: main()'s own path, window closed → service stopped, whatever the window reported."""
    import par_shell.__main__ as entry

    FakeService.instances.clear()

    def fake_window(info: ServiceInfo, smoke_seconds: float | None = None) -> bool:
        FakeService.instances[0].events.append(f"window {info.base_url}")
        if outcome == "raises":
            raise RuntimeError("window toolkit failed")
        return outcome == "closed"

    monkeypatch.setattr(entry, "webview2_available", lambda: True)
    monkeypatch.setattr(entry, "ServiceProcess", FakeService)
    monkeypatch.setattr(entry, "open_window", fake_window)
    if outcome == "raises":
        with pytest.raises(RuntimeError):
            shell_main(["--data-dir", str(tmp_path)])
    else:
        assert shell_main(["--data-dir", str(tmp_path)]) == (0 if outcome == "closed" else 1)
    assert FakeService.instances[0].events == ["start", f"window {INFO.base_url}", "stop"]


def test_stop_asks_by_request_first_then_stdin_then_a_signal(tmp_path: Path) -> None:
    """review of PR #50, major 1: the windowed exe has no stdin, so the first stop request is
    POST /api/v0/shutdown with the token; the end of stdin and the signal stay as fallbacks, kill last."""
    polite = FakeProcess()
    asked: list[ServiceInfo] = []

    def accepted(info: ServiceInfo) -> None:
        asked.append(info)
        polite.calls.append("shutdown request")
        polite.returncode = 0

    process = ServiceProcess(tmp_path, popen=lambda *a, **k: polite, clock=_fake_clock(), request_shutdown=accepted)
    process.process, process.info = polite, INFO  # type: ignore[assignment]
    process.stop()
    assert asked == [INFO] and polite.calls[0] == "shutdown request"
    assert process.stopped_by == service.STOPPED_BY_REQUEST and process.exit_code == 0

    def refused(info: ServiceInfo) -> None:
        raise OSError("connection refused")

    for fake, expected in ((FakeProcess(), service.STOPPED_BY_STDIN), (FakeProcess(ignores_stdin=True), "signal")):
        process = ServiceProcess(tmp_path, clock=_fake_clock(), request_shutdown=refused)
        process.process, process.info = fake, INFO  # type: ignore[assignment]
        process.stop(timeout=0.01)
        assert fake.calls[0] == "close stdin" and process.stopped_by == expected

    ignored = FakeProcess(ignores_stdin=True)
    process = ServiceProcess(
        tmp_path, popen=lambda *a, **k: ignored, clock=_fake_clock(), request_shutdown=lambda i: None
    )
    process.process, process.info = ignored, INFO  # type: ignore[assignment]
    process.stop(timeout=0.01)
    assert ignored.calls[0] == "close stdin" and process.stopped_by == service.STOPPED_BY_SIGNAL


def test_the_shutdown_request_carries_the_token_and_no_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Any] = []

    class Opener:
        def open(self, call: Any, timeout: float) -> Any:  # noqa: ANN401
            sent.append((call, timeout))

            class Answer:
                status = 202

                def __enter__(self) -> Any:  # noqa: ANN401
                    return self

                def __exit__(self, *_exc: object) -> None:
                    return None

            return Answer()

    monkeypatch.setattr(service, "_no_proxy_opener", Opener)
    service.request_shutdown(INFO)
    call, _timeout = sent[0]
    assert call.full_url == INFO.base_url + service.SHUTDOWN_PATH and call.get_method() == "POST"
    assert call.get_header("Authorization") == f"Bearer {INFO.token}"
    assert not call.has_header("Origin")


def test_a_window_smoke_without_webview2_fails_without_a_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_alpha.ps1 runs the frozen exe with --smoke (review of PR #50, major 2: the page must really
    initialise); unattended, a missing runtime must end the run with its own exit code, not wait on a message box."""
    import par_shell.__main__ as entry

    monkeypatch.setattr(entry, "webview2_available", lambda: False)
    monkeypatch.setattr(entry, "ask", lambda text, yes_no: pytest.fail("no dialog in a smoke run"))
    monkeypatch.setattr(entry, "ServiceProcess", lambda *a, **k: pytest.fail("service must not start"))
    assert shell_main(["--smoke", "5"]) == entry.SMOKE_NO_RUNTIME


def test_the_self_test_writes_the_tier_where_the_service_reads_it() -> None:
    """par_shell imports nothing from par_app; its copy of the settings file and key must stay V1.0.3-free and equal
    to par_app.application.tier (issue #119: the self-test starts the product service from tier 0)."""
    from par_app.application import tier
    from par_shell import self_test

    assert self_test.SETTINGS_FILE == ("config", tier.SETTINGS_FILE_NAME)
    assert self_test.TIER_KEY == tier.TIER_KEY
