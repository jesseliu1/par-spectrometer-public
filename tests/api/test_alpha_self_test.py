"""The alpha self-test (main_v2.py --alpha-self-test): passes on the real service, fails loudly on each fault.

The passing run starts the real service from the source tree (python -m par_app.api, loopback only) on a synthetic
database in the self-test's own temporary folder. The frozen run (PAR_Spectrometer_2.exe) was checked by hand on
macOS (PR description); on Windows it runs in build_alpha.ps1 and package-alpha.yml. NOT VERIFIED ON WINDOWS YET.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import main_v2
from par_app import parent_watch
from par_app.alpha_info import ALPHA_VERSION
from par_app.alpha_self_test_db import DAY_END, DAY_START, RECORD_TIMES, write_synthetic_database
from par_shell import self_test
from par_shell.service import STOPPED_BY_KILL, ServiceInfo, ServiceProcess

pytestmark = pytest.mark.unit
EXPECT = self_test.Expectations(
    ALPHA_VERSION, require_web=False, require_installer=False, first_day=(DAY_START, DAY_END)
)


def _report(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def test_self_test_passes_on_the_real_service(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    test = self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, frozen=False)
    assert self_test.run_self_test(report, test) == 0, report.read_text(encoding="utf-8")
    result = _report(report)
    assert result["passed"] is True and result["version"] == ALPHA_VERSION and result["frozen"] is False
    assert [step["name"] for step in result["steps"]] == [
        "synthetic database",
        "start in tier 0",  # issue #119: the product's first-run tier is 1; the self-test starts from 0
        "service start",
        "health",
        "token required",
        "web front end",
        "tier 0 shows no device data",
        "service stop",
        "source untouched",
        "window toolkit",
        "webview2 offline installer",
    ]
    assert all(step["passed"] for step in result["steps"])
    assert result["service"] == {
        "stopped_by": "request",
        "exit_code": 0,
        "service_file_left_behind": False,
    }
    assert "no device listed" in result["steps"][6]["detail"]
    assert "cleanup_errors" not in result


def test_entry_point_runs_the_self_test_from_source(tmp_path: Path) -> None:
    report = tmp_path / "entry.json"
    assert main_v2.main([main_v2.SELF_TEST_FLAG, str(report)]) == 0
    assert _report(report)["passed"] is True


def test_an_existing_report_is_never_overwritten(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text("earlier run", encoding="utf-8")
    with pytest.raises(FileExistsError):
        self_test.run_self_test(report, self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False))
    assert report.read_text(encoding="utf-8") == "earlier run"


def test_synthetic_database_is_v1_format_and_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.sqlite3"
    assert write_synthetic_database(path) == len(RECORD_TIMES)
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT acquired_at, success FROM acquisitions ORDER BY id").fetchall()
        spectra = connection.execute("SELECT COUNT(*) FROM spectra").fetchone()[0]
    assert rows == [(moment, 1) for moment in RECORD_TIMES] and spectra == len(RECORD_TIMES)
    with pytest.raises(FileExistsError):
        write_synthetic_database(path)


class ScriptedService(ServiceProcess):
    """A service that never starts a process: start() returns `info`, stop() reports `stopped_by`/`exit_code`."""

    info_to_return = ServiceInfo("http://127.0.0.1:9", 9, "t", 1, ALPHA_VERSION)
    stopped = ("request", 0)

    def start(self, command: Any = None, timeout: float = 0) -> ServiceInfo:  # noqa: ANN401
        return self.info_to_return

    def stop(self, timeout: float = 0) -> None:
        self.stopped_by, self.exit_code = self.stopped


def _run(tmp_path: Path, test: self_test.SelfTest) -> dict[str, Any]:
    report = tmp_path / "report.json"
    assert self_test.run_self_test(report, test) == 1
    result = _report(report)
    assert result["passed"] is False and "error" in result
    return result


def test_a_wrong_version_fails_the_health_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = {"/api/v0/health": self_test.Response(200, {}, json.dumps({"version": "9.9", "tier": 0}).encode())}
    monkeypatch.setattr(self_test, "request", lambda info, path, token, body=None: answers[path])
    test = self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False, ScriptedService)
    result = _run(tmp_path, test)
    assert result["steps"][-1] == {
        "name": "health",
        "passed": False,
        "detail": "StepFailed: version 9.9 != 2.0.0-alpha.9",
    }
    assert result["service"]["stopped_by"] == "request"  # the service is stopped whatever failed


def test_a_tier_above_zero_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"version": ALPHA_VERSION, "tier": 1}).encode()
    monkeypatch.setattr(self_test, "request", lambda *a, **k: self_test.Response(200, {}, body))
    result = _run(tmp_path, self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False, ScriptedService))
    assert "tier 1" in result["steps"][-1]["detail"]


def test_a_frozen_build_must_serve_the_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def answer(info: ServiceInfo, path: str, token: str | None, body: object = None) -> self_test.Response:
        if path == "/api/v0/health":
            return self_test.Response(200, {}, json.dumps({"version": ALPHA_VERSION, "tier": 0}).encode())
        return self_test.Response(401 if path == "/api/v0/devices" else 404, {}, b"")

    monkeypatch.setattr(self_test, "request", answer)
    frozen = self_test.Expectations(ALPHA_VERSION, True, False, (DAY_START, DAY_END))
    result = _run(tmp_path, self_test.SelfTest(frozen, write_synthetic_database, tmp_path, True, ScriptedService))
    assert result["steps"][-1]["name"] == "web front end" and "answered 404" in result["steps"][-1]["detail"]


def test_a_killed_service_or_a_missing_installer_fails(tmp_path: Path) -> None:
    class Killed(ScriptedService):
        stopped = (STOPPED_BY_KILL, -9)

    killed = Killed(tmp_path)
    killed.stop()
    with pytest.raises(self_test.StepFailed, match="stopped by kill"):
        self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False)._stopped(killed)
    frozen = self_test.Expectations(ALPHA_VERSION, True, True, (DAY_START, DAY_END))
    with pytest.raises(self_test.StepFailed, match="no offline installer"):
        self_test.SelfTest(frozen, write_synthetic_database, tmp_path, True)._installer()
    (tmp_path / "redist").mkdir()
    (tmp_path / "redist" / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe").write_bytes(b"MZ")
    with pytest.raises(self_test.StepFailed, match="build_manifest.json"):  # review major 3: "MZ" is not enough
        self_test.SelfTest(frozen, write_synthetic_database, tmp_path, True)._installer()


def test_a_changed_source_fails(tmp_path: Path) -> None:
    source = tmp_path / "s.sqlite3"
    write_synthetic_database(source)
    before = self_test.sha256(source)
    (tmp_path / "s.sqlite3-wal").write_bytes(b"")
    with pytest.raises(self_test.StepFailed, match="beside the source"):
        self_test.SelfTest._untouched(source, before)
    with pytest.raises(self_test.StepFailed, match="changed"):
        self_test.SelfTest._untouched(source, "0" * 64)


def test_a_service_that_leaves_its_service_file_fails(tmp_path: Path) -> None:
    """Review M-1: the shell's clean-up must not hide a service that did not remove its own service.json."""
    service = ScriptedService(tmp_path)
    service.stop()
    service.service_file_left_behind = True
    with pytest.raises(self_test.StepFailed, match="did not remove its service.json"):
        self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False)._stopped(service)


def test_shell_reports_a_service_file_it_had_to_remove(tmp_path: Path) -> None:
    process = ServiceProcess(tmp_path)
    left = {"base_url": "http://127.0.0.1:9", "port": 9, "token": "t", "pid": 4321, "version": "x", "launch_id": "l1"}
    (tmp_path / "service.json").write_text(json.dumps(left), encoding="utf-8")
    process._remove_stale_service_file("l1")
    assert process.service_file_left_behind and not (tmp_path / "service.json").exists()
    process._remove_stale_service_file("l1")
    assert not process.service_file_left_behind


WINDOWS = self_test.Expectations(ALPHA_VERSION, True, True, (DAY_START, DAY_END), require_windows_stack=True)


def test_a_frozen_windows_build_needs_the_shell_watch(tmp_path: Path) -> None:
    """D-223 (replaces the kill-on-close Job Object, review of PR #56 blocker 2): the frozen Windows self-test
    fails unless the service logged that it watches the shell process, so a crashed shell stops it gracefully."""
    service = ScriptedService(tmp_path)
    service.stop()
    test = self_test.SelfTest(WINDOWS, write_synthetic_database, tmp_path, True)
    with pytest.raises(self_test.StepFailed, match="watching the shell process"):
        test._stopped(service)
    log = tmp_path.joinpath(*self_test.SERVICE_LOG)
    log.parent.mkdir(parents=True)
    log.write_text(f"x INFO par_app.service: {parent_watch.WATCHING} (pid 1)\n", encoding="utf-8")
    assert "watched the shell process" in test._stopped(service)
    assert self_test.WATCHING_SHELL == parent_watch.WATCHING


def test_a_frozen_windows_build_must_load_the_window_back_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review N-2: pythonnet or the WebView2 SDK missing from _internal is caught without opening a window."""
    test = self_test.SelfTest(WINDOWS, write_synthetic_database, tmp_path, True)
    monkeypatch.setattr(self_test, "WINDOWS_BACK_END", ("json", "par_shell_missing_back_end"))
    with pytest.raises(ModuleNotFoundError):
        test._window_toolkit()
    monkeypatch.setattr(self_test, "WINDOWS_BACK_END", ("json",))
    assert test._window_toolkit() == "json loaded"
    assert "not checked" in self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False)._window_toolkit()


# ------------------------------------------------------------------ review of PR #50


PAGE = (
    '<!doctype html><html><head><script type="module" crossorigin src="/assets/index-A.js"></script>'
    '<link rel="stylesheet" crossorigin href="/assets/index-B.css"></head><body><div id="app"></div></body></html>'
)
CSP = {"content-security-policy": "default-src 'self'"}
SITE = {
    "/": PAGE.encode(),
    "/assets/index-A.js": b"console.log(1)",
    "/assets/index-B.css": b"@font-face{src:url(/assets/Mono-C.ttf)}body{font-family:x}",
    "/assets/Mono-C.ttf": b"font",
    **{f"/{name}": b"font or licence" for name in self_test.WEB_FILES},
}
INFO = ServiceInfo("http://127.0.0.1:9", 9, "t", 1, ALPHA_VERSION)
FROZEN = self_test.Expectations(ALPHA_VERSION, True, False, (DAY_START, DAY_END))


def _site(monkeypatch: pytest.MonkeyPatch, site: dict[str, bytes]) -> None:
    def answer(info: ServiceInfo, path: str, token: str | None, body: object = None) -> self_test.Response:
        if path not in site:
            return self_test.Response(404, {}, b"")
        return self_test.Response(200, CSP if path == "/" else {}, site[path])

    monkeypatch.setattr(self_test, "request", answer)


def test_the_web_step_loads_every_script_stylesheet_and_font_the_page_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _site(monkeypatch, SITE)
    detail = self_test.SelfTest(FROZEN, write_synthetic_database, tmp_path, True)._web(INFO)
    for path in ("/assets/index-A.js", "/assets/index-B.css", "/assets/Mono-C.ttf"):
        assert path in detail


@pytest.mark.parametrize(
    ("path", "body", "message"),
    [
        ("/assets/index-A.js", None, "/assets/index-A.js answered 404"),
        ("/assets/index-B.css", None, "/assets/index-B.css answered 404"),
        ("/assets/Mono-C.ttf", None, "/assets/Mono-C.ttf answered 404"),
        ("/assets/index-A.js", b"", "/assets/index-A.js is empty"),
        ("/", b'<div id="app"></div>', "names no script"),
    ],
)
def test_a_missing_or_empty_page_resource_fails_the_web_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, body: bytes | None, message: str
) -> None:
    """review major 2: the page with its fonts but without its JS or CSS is a blank window, not a pass."""
    site = dict(SITE)
    if body is None:
        del site[path]
    else:
        site[path] = body
    _site(monkeypatch, site)
    with pytest.raises(self_test.StepFailed, match=message):
        self_test.SelfTest(FROZEN, write_synthetic_database, tmp_path, True)._web(INFO)


def _detail(metrics: int, points: int) -> dict[str, Any]:
    items = [{"label": f"m{i}", "text": "1"} for i in range(metrics)]
    return {
        "success": True,
        "spectrum_state": "ok",
        "record": {"id": 7},
        "groups": [{"title": "g", "items": items}],
        "spectrum": {"points": [1000] * points},
    }


@pytest.mark.parametrize(
    ("metrics", "points", "message"),
    [(53, 701, "53 metrics, expected 54"), (54, 700, "700 spectrum points, expected 701"), (54, 0, "0 spectrum")],
)
def test_the_detail_step_needs_54_metrics_and_701_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metrics: int, points: int, message: str
) -> None:
    """review nit: the documented 54 metrics and 701-point spectrum are asserted, not only reported."""
    body = json.dumps(_detail(metrics, points)).encode()
    monkeypatch.setattr(self_test, "request", lambda *a, **k: self_test.Response(200, {}, body))
    test = self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False)
    with pytest.raises(self_test.StepFailed, match=message):
        test._detail(INFO, 7)
    good = json.dumps(_detail(54, 701)).encode()
    monkeypatch.setattr(self_test, "request", lambda *a, **k: self_test.Response(200, {}, good))
    assert test._detail(INFO, 7) == "record 7: 54 metrics, spectrum 701 points"


def _installer_folder(tmp_path: Path, body: bytes, recorded: dict[str, Any] | None) -> Path:
    (tmp_path / "redist").mkdir(parents=True)
    (tmp_path / "redist" / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe").write_bytes(body)
    if recorded is not None:
        manifest = {"webview2_installer": recorded}
        (tmp_path / "build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("fault", ["corrupted", "not MZ", "too small", "unrecorded"])
def test_the_installer_step_needs_the_checked_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """review major 3: the shipped installer must be the very file the build checked (signature, product,
    architecture: tools/alpha_release.py check_webview2), byte for byte, not just any file named like it."""
    import hashlib

    monkeypatch.setattr(self_test, "WEBVIEW2_MIN_BYTES", 16)
    body = b"MZ" + b"\0" * 30
    recorded = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
    frozen = self_test.Expectations(ALPHA_VERSION, True, True, (DAY_START, DAY_END))
    good = _installer_folder(tmp_path / "good", body, recorded)
    assert (
        "matches build_manifest.json" in self_test.SelfTest(frozen, write_synthetic_database, good, True)._installer()
    )
    bad_body, bad_recorded = {
        "corrupted": (body[:-1] + b"x", recorded),
        "not MZ": (b"ZM" + body[2:], {"sha256": hashlib.sha256(b"ZM" + body[2:]).hexdigest(), "size": len(body)}),
        "too small": (b"MZ", {"sha256": hashlib.sha256(b"MZ").hexdigest(), "size": 2}),
        "unrecorded": (body, None),
    }[fault]
    bad = _installer_folder(tmp_path / "bad", bad_body, bad_recorded)
    with pytest.raises(self_test.StepFailed):
        self_test.SelfTest(frozen, write_synthetic_database, bad, True)._installer()


# ------------------------------------------------------------------ tier 1 (16_ 8.2)


class FakeKit:
    """The tier-1 kit without a gateway or a lock: lock_free() answers from `free` in turn."""

    def __init__(self, free: tuple[bool, ...] = (True, False, True), counts: tuple[int, int, int] = (20, 1, 1)) -> None:
        self.free = list(free)
        self.counted = counts
        self.closed = False

    def prepare(self, data_dir: Path, seed: Path) -> str:
        return "1 device, Modbus TCP 127.0.0.1:9 (synthetic gateway), no serial port"

    def lock_free(self) -> bool:
        return self.free.pop(0)

    def counts(self) -> tuple[int, int, int]:
        return self.counted

    def qt_versions(self) -> dict[str, str]:
        return dict(self.binding)

    binding = {"binding": "PySide6", "version": "6.11.2", "qt": "6.11.2"}

    def close(self) -> None:
        self.closed = True


def _tier1_service(monkeypatch: pytest.MonkeyPatch, start_status: int = 202) -> list[str]:
    """Scripted answers of a service whose takeover works; returns the requests made ("METHOD path")."""
    calls: list[str] = []
    state = {"tier": 0, "takeover": "released"}

    def answer(
        info: ServiceInfo, path: str, token: str | None, body: object = None, method: str | None = None
    ) -> self_test.Response:
        verb = method or ("POST" if body is not None else "GET")
        calls.append(f"{verb} {path}")
        status: dict[str, Any] = {
            "takeover": state["takeover"],
            "lock_held": state["takeover"] == "running",
            "halt": None,
            "error": None,
            "devices": [{"latest_record_id": 4 if state["takeover"] == "running" else None}],
        }
        if path == "/api/v0/acquisition/start":
            if state["tier"] == 0:
                return self_test.Response(403, {}, b"{}")
            state["takeover"] = "running" if start_status == 202 else "released"
            return self_test.Response(start_status, {}, json.dumps({**status, "lock_held": True}).encode())
        if path == "/api/v0/tier/confirmations":
            return self_test.Response(201, {}, json.dumps({"confirmation_id": "c1"}).encode())
        if path == "/api/v0/tier":
            state["tier"] = int(body["tier"])  # type: ignore[index]
            return self_test.Response(200, {}, json.dumps({"tier": state["tier"], "lock_held": False}).encode())
        if path == "/api/v0/acquisition/stop":
            state["takeover"] = "released"
            return self_test.Response(202, {}, json.dumps(status).encode())
        if path == "/api/v0/acquisition/status":
            return self_test.Response(200, {}, json.dumps(status).encode())
        if path.startswith("/api/v0/devices/p1/acquisitions?"):
            items = [{"id": index} for index in (3, 2, 1)]
            return self_test.Response(200 if state["tier"] else 404, {}, json.dumps({"items": items}).encode())
        if path == "/api/v0/devices/p1/acquisitions/3":
            return self_test.Response(200, {}, json.dumps(RECORD_DETAIL).encode())
        raise AssertionError(path)

    monkeypatch.setattr(self_test, "request", answer)
    return calls


RECORD_DETAIL = {
    "success": True,
    "spectrum_state": "ok",
    "record": {"id": 3},
    "groups": [{"items": [{}] * self_test.EXPECTED_METRICS}],
    "spectrum": {"points": [1000] * self_test.EXPECTED_SPECTRUM_POINTS},
}


def _tier1(tmp_path: Path, kit: FakeKit) -> self_test.SelfTest:
    test = self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False, level1=kit, sleep=lambda _s: None)
    test._tier1(INFO, kit, len(RECORD_TIMES))
    return test


def test_tier1_steps_take_over_record_release_and_return_to_tier_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _tier1_service(monkeypatch)
    test = _tier1(tmp_path, FakeKit())
    assert test.level1_result == self_test.LEVEL1_PASSED
    assert [step["name"] for step in test.steps] == [
        "tier 0 refuses acquisition",
        "tier 0 -> 1",
        "record list",
        "record detail",
        "takeover start",
        "takeover record",
        "takeover stop",
        "tier 1 -> 0",
    ]
    assert "PUT /api/v0/tier" in calls and calls[-1] == "POST /api/v0/acquisition/start"  # 403 again at tier 0
    assert not any("maintenance" in call or '"tier": 2' in call for call in calls)  # tier 2 is never entered


def test_tier1_is_skipped_not_failed_while_v103_holds_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _tier1_service(monkeypatch)
    test = _tier1(tmp_path, FakeKit(free=(False,)))
    assert test.level1_result == self_test.LEVEL1_SKIPPED
    assert test.steps[-2] == {"name": "V1.0.3 lock free", "passed": True, "detail": self_test.LEVEL1_SKIPPED}
    assert test.steps[-1]["name"] == "tier 1 -> 0"
    assert not any(call.startswith("POST /api/v0/acquisition/start") for call in calls[1:-1])  # no takeover
    assert calls[-1] == "POST /api/v0/acquisition/start"  # refused again at tier 0


@pytest.mark.parametrize(
    ("free", "counts", "start_status", "message"),
    [
        ((True, True), (20, 1, 1), 202, "lock is free while the service has taken over"),
        ((True, False, False), (20, 1, 1), 202, "still held after the takeover stopped"),
        ((True, False, True), (0, 0, 0), 202, "gateway saw 0 requests"),
        ((True,), (20, 1, 1), 409, "POST /acquisition/start answered 409"),
    ],
)
def test_tier1_fails_on_a_lock_that_is_not_taken_or_not_released(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    free: tuple[bool, ...],
    counts: tuple[int, int, int],
    start_status: int,
    message: str,
) -> None:
    _tier1_service(monkeypatch, start_status)
    with pytest.raises(self_test.StepFailed, match=message):
        _tier1(tmp_path, FakeKit(free=free, counts=counts))


def test_tier1_fails_on_a_gateway_connection_left_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tier1_service(monkeypatch)
    monkeypatch.setattr(self_test, "TAKEOVER_STOP_TIMEOUT_SECONDS", 1.0)
    with pytest.raises(self_test.StepFailed, match="connection\\(s\\) still open"):
        _tier1(tmp_path, FakeKit(counts=(20, 2, 1)))


def test_threads_left_in_the_service_fail(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "service.log"
    log.parent.mkdir()
    log.write_text("x INFO started\n", encoding="utf-8")
    with pytest.raises(self_test.StepFailed, match="did not finish its shutdown"):
        self_test.SelfTest._threads_left(tmp_path)
    log.write_text(f"x INFO {self_test.SERVICE_STOPPED} non-daemon threads left: QThread\n", encoding="utf-8")
    with pytest.raises(self_test.StepFailed, match="QThread"):
        self_test.SelfTest._threads_left(tmp_path)
    log.write_text(f"x INFO {self_test.SERVICE_STOPPED} non-daemon threads left: none\n", encoding="utf-8")
    assert self_test.SelfTest._threads_left(tmp_path) == self_test.NO_THREADS_LEFT


def test_the_stop_marker_is_the_services() -> None:
    from par_app import service_main

    assert self_test.SERVICE_STOPPED == service_main.SERVICE_STOPPED


def test_a_frozen_build_must_run_the_qt_it_recorded(tmp_path: Path) -> None:
    frozen = self_test.SelfTest(FROZEN, write_synthetic_database, tmp_path, True)
    with pytest.raises(self_test.StepFailed, match="records no Qt versions"):
        frozen._qt_version(FakeKit())
    runtime = {"binding": "PySide6", "version": "6.11.2", "qt": "6.11.1"}
    manifest = {"qt": {"runtime": runtime, "locked": {"pyside6-essentials": "6.11.2"}}}
    (tmp_path / "build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(self_test.StepFailed, match="6.11.1"):
        frozen._qt_version(FakeKit())
    manifest["qt"]["runtime"]["qt"] = "6.11.2"
    (tmp_path / "build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert "as recorded in build_manifest.json" in frozen._qt_version(FakeKit())


def test_the_service_code_must_run_on_pyside6(tmp_path: Path) -> None:
    """internal notes: the alpha contains no PyQt5; a kit on any other binding fails the step, frozen or not."""
    kit = FakeKit()
    kit.binding = {"binding": "PyQt5", "version": "5.15.11", "qt": "5.15.2"}
    for frozen in (True, False):
        test = self_test.SelfTest(FROZEN if frozen else EXPECT, write_synthetic_database, tmp_path, frozen)
        with pytest.raises(self_test.StepFailed, match="not on PySide6"):
            test._qt_version(kit)
    assert (
        self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, False)
        ._qt_version(FakeKit())
        .startswith("PySide6 6.11.2, Qt 6.11.2")
    )


def test_the_real_kit_reports_pyside6() -> None:
    from par_app.alpha_self_test_bus import Level1Kit

    versions = Level1Kit.qt_versions()
    assert versions["binding"] == "PySide6" and versions["version"].startswith("6.") and versions["qt"].startswith("6.")


@pytest.mark.qt
def test_self_test_with_tier_1_passes_on_the_real_service(tmp_path: Path) -> None:
    """The whole self-test as the exe runs it (main_v2.py's kit): the real par_app.service_main, the synthetic
    loopback gateway, V1.0.3's real lock. Skipped while another program holds that lock."""
    from par_app.alpha_self_test_bus import Level1Kit

    kit = Level1Kit()
    if not kit.lock_free():
        pytest.skip("V1.0.3's lock is held on this machine")
    report = tmp_path / "report.json"
    test = self_test.SelfTest(EXPECT, write_synthetic_database, tmp_path, frozen=False, level1=kit)
    assert self_test.run_self_test(report, test) == 0, report.read_text(encoding="utf-8")
    result = _report(report)
    if result["level1"] != self_test.LEVEL1_PASSED:
        pytest.skip(f"tier 1 not checked: {result['level1']}")  # the lock was taken by another test meanwhile
    names = [step["name"] for step in result["steps"]]
    assert (
        names[1:3] == ["start in tier 0", "tier-1 configuration"]
        and "takeover record" in names
        and "no thread left in the service" in names
    )
    assert result["service"]["stopped_by"] == "request" and result["service"]["exit_code"] == 0
    requests, opened, closed = kit.counts()
    assert requests > 0 and opened == closed > 0
