"""Alpha self-test: the 2.0 counterpart of V1.0.x's --release-self-test (PAR_Spectrometer_2.exe --alpha-self-test R).

It runs the packaged program the way the shell does, without a window and without any device:

  1. writes a SYNTHETIC V1.0.x-format database into its own temporary folder (the writer is passed in by main_v2.py;
     the shell itself imports nothing from par_app, 13_ section 4);
  2. starts the service as a child process (frozen: the same exe with --service) on a temporary data directory, so
     the user's %LOCALAPPDATA%\\PAR_Spectrometer_2 is never touched;
  3. health check (version, tier 0), a request without the token must be refused, the bundled page, every script,
     stylesheet and font it loads (web_assets.py: present and non-empty) and the fonts' licences must be served
     (required in a frozen build);
  4. at tier 0 the service must list no device and refuse a device's records (issue #82: the pages show only the
     data the alpha acquires itself, and tier 0 reads none);
  5. stops the service through POST /api/v0/shutdown (the windowed exe's real stop path: it has no stdin on Windows)
     and expects exit code 0 and service.json removed BY THE SERVICE (not by the shell's clean-up); the synthetic
     source must be byte-identical with nothing created beside it;
  6. tier 1 (16_ 8.2; only when main_v2.py passes a Level1 kit, i.e. always from the exe): before the service starts,
     the kit writes a one-device configuration on Modbus TCP to a SYNTHETIC gateway on 127.0.0.1 that the kit runs in
     this process (par_app/alpha_self_test_bus.py; no serial port is named, no device is touched), with a byte copy
     of the synthetic database as that device's database. With the service at tier 0, acquisition is refused (403);
     tier 0 -> 1 through the two-step confirmation; the device's records are listed, one record must come back with
     exactly 54 metrics and a 701-point spectrum. V1.0.3's lock must be free (if V1.0.3 runs, the takeover steps are
     skipped, the tier goes back to 0 and the report says so: level1 = "skipped"); start the
     takeover (the service takes V1.0.3's lock, the coordinator polls the gateway until a record is saved; the lock
     is then held, as V1.0.3 would find it); stop the takeover (the lock is free again, every gateway connection
     closed) and return to tier 0 (acquisition refused again). Tier 2 is never entered: no maintenance and no device
     write. After the service stopped, its log must say that no non-daemon Python thread was left
     (service_main.py). The coordinator is a QThread, not listed there: "released" means coordinator.stop() has
     waited for it, and a QThread still running at exit would abort the process (exit code step);
  7. the Qt binding of this process must be PySide6 (internal notes: the alpha contains no PyQt5) and its version
     and the loaded QtCore's must be the ones build_manifest.json recorded from the build environment, which
     tools/alpha_release.py checked against requirements.lock (frozen build only);
  8. frozen Windows build only: the service must have logged that it watches the shell process (--parent-pid; it
     stops gracefully by itself if the shell crashes, par_app/parent_watch.py, D-223), pywebview's
     WinForms/WebView2 back end must load (.NET via pythonnet and the WebView2 SDK DLLs; no window is opened) and the
     WebView2 offline installer in redist\\ beside the exe must be the very file the build checked (size and SHA-256
     recorded in build_manifest.json, at least WEBVIEW2_MIN_BYTES, a Windows program).

Every step is written to report.json (created with mode "x": an existing report is never overwritten) with the
WebView2 runtime version found, if any. Exit code 0 only if every step passed.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .instance import SINGLE_INSTANCE_NAME
from .service import STOPPED_BY_REQUEST, ServiceInfo, ServiceProcess
from .web_assets import WebAssetError, check_page
from .webview2 import WEBVIEW2_MIN_BYTES, offline_installer, runtime_version, windows_registry

SOURCE_NAME = "synthetic_v1.sqlite3"
SNAPSHOT_NAME = "self-test"
SIDE_FILES = ("-wal", "-shm", "-journal")
WEB_FILES = ("fonts/NotoSansSC.ttf", "fonts/OFL.txt", "fonts/JetBrainsMono.ttf", "fonts/JetBrainsMono-OFL.txt")
"""Bundled fonts and their SIL OFL 1.1 licences (UI-001, D-205)."""
APP_ROOT_MARKER = '<div id="app">'
EXPECTED_METRICS = 54
"""Rows of the record detail (API-06, UI-011: the 54 metrics V1.0.x shows for a record)."""
EXPECTED_SPECTRUM_POINTS = 701
"""Points of a stored spectrum: 380-1080 nm in 1 nm steps (par_app.math_ops.WAVELENGTHS)."""
MANIFEST = "build_manifest.json"
"""Written by tools/alpha_release.py metadata next to the exe; holds the checked installer's size and SHA-256."""
WINDOWS_PROGRAM_MAGIC = b"MZ"
REQUEST_TIMEOUT_SECONDS = 30.0
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
ALPHA_QT_BINDING = "PySide6"
"""The only Qt binding the alpha service may run on (internal notes; par_shell imports nothing from par_app)."""
SERVICE_LOG = ("logs", "service.log")
SERVICE_STOPPED = "service stopped;"
"""Start of the service's last log line (par_app.service_main.SERVICE_STOPPED; a test keeps them equal)."""
NO_THREADS_LEFT = "non-daemon threads left: none"
WATCHING_SHELL = "watching the shell process"
"""What the service logs once it watches the shell's pid (par_app.parent_watch.WATCHING; a test keeps them equal)."""
RECORD_TIMEOUT_SECONDS = 60.0
"""Wait for the first record of the takeover (the first poll starts at once; one transaction budget is 40 s)."""
TAKEOVER_STOP_TIMEOUT_SECONDS = 60.0
"""coordinator.stop() may wait for one acquisition transaction (40 s) before the lock is released (16_ 1.5)."""
LEVEL1_POLL_SECONDS = 0.2
LEVEL1_PASSED = "passed"
LEVEL1_SKIPPED = "skipped: V1.0.3's lock is held on this computer (V1.0.3 is running); close it and run again"
WINDOWS_BACK_END = ("webview.platforms.winforms", "webview.platforms.edgechromium")


def _pause(seconds: float) -> None:
    """Sleep without the clock functions product code may not call (R-1-6)."""
    threading.Event().wait(seconds)


class StepFailed(AssertionError):
    """One self-test check did not hold."""


class Level1(Protocol):
    """The tier-1 kit (par_app.alpha_self_test_bus.Level1Kit, passed in by main_v2.py)."""

    def prepare(self, data_dir: Path, seed: Path) -> str: ...

    def lock_free(self) -> bool: ...

    def counts(self) -> tuple[int, int, int]: ...

    def qt_versions(self) -> dict[str, str]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class Expectations:
    version: str
    """The version the service must report (par_app.alpha_info.ALPHA_VERSION, passed in by main_v2.py)."""
    require_web: bool
    """A frozen build must serve the bundled page; a source checkout may run without `npm run build`."""
    require_installer: bool
    """A frozen Windows build must ship redist\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe (S-5)."""
    first_day: tuple[str, str]
    """(start, end) of the day the synthetic records were written on, in the API's time format."""
    require_windows_stack: bool = False
    """Frozen Windows build: the service must watch the shell process and the WinForms/WebView2 back end must load."""


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:  # noqa: ANN401 (JSON)
        return json.loads(self.body.decode("utf-8"))


def request(
    info: ServiceInfo, path: str, token: str | None, body: object = None, method: str | None = None
) -> Response:
    """One HTTP request to the local service, never through a proxy; HTTP errors are returned, not raised. Without
    `method`: POST when there is a body, else GET."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    verb = method or ("POST" if data else "GET")
    call = urllib.request.Request(info.base_url + path, data=data, headers=headers, method=verb)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(call, timeout=REQUEST_TIMEOUT_SECONDS) as answer:
            return Response(answer.status, dict(answer.headers.items()), answer.read())
    except urllib.error.HTTPError as error:
        return Response(error.code, dict(error.headers.items()), error.read())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


SETTINGS_FILE = ("config", "app_config_v2.json")
"""par_app.application.tier.SETTINGS_FILE_NAME under the data directory's config folder (the shell imports nothing
from par_app; tests/unit/test_shell.py keeps the two equal)."""
TIER_KEY = "device_write_tier"
"""par_app.application.tier.TIER_KEY (kept equal by the same test)."""


def _start_in_tier_0(data_dir: Path) -> str:
    """Since issue #119 the product service acquires at once without a settings file; the self-test starts from tier
    0 (nothing opened) and raises the tier itself, so it writes tier 0 before the service starts."""
    settings = data_dir.joinpath(*SETTINGS_FILE)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({TIER_KEY: 0}), encoding="utf-8")
    return "settings file with tier 0"


def watches_shell(data_dir: Path) -> bool:
    """True if the service logged that it watches the shell process (D-223)."""
    try:
        return WATCHING_SHELL in data_dir.joinpath(*SERVICE_LOG).read_text(encoding="utf-8")
    except OSError:
        return False


def check(condition: bool, message: str) -> None:
    if not condition:
        raise StepFailed(message)


@dataclass
class SelfTest:
    expect: Expectations
    make_database: Callable[[Path], int]
    program_dir: Path
    frozen: bool
    service_factory: Callable[[Path], ServiceProcess] = ServiceProcess
    level1: Level1 | None = None
    level1_result: str = "not run"
    """LEVEL1_PASSED, LEVEL1_SKIPPED or "not run" (no kit, or an earlier step failed)."""
    sleep: Callable[[float], None] = field(default=lambda seconds: _pause(seconds))
    steps: list[dict[str, Any]] = field(default_factory=list)
    service: dict[str, Any] = field(default_factory=dict)
    """How the service child ended: stopped_by, exit_code and whether it had to remove service.json itself."""

    def step(self, name: str, action: Callable[[], str]) -> None:
        """Run one check; record it as passed or failed and raise again so the run stops at the first failure."""
        try:
            detail = action()
        except Exception as error:
            self.steps.append({"name": name, "passed": False, "detail": f"{type(error).__name__}: {error}"})
            raise
        self.steps.append({"name": name, "passed": True, "detail": detail})

    def run(self, work: Path) -> None:
        source = work / "source" / SOURCE_NAME
        written: list[int] = []
        self.step("synthetic database", lambda: self._write(source, written))
        count = written[0]
        before = sha256(source)
        data_dir = work / "data"
        self.step("start in tier 0", lambda: _start_in_tier_0(data_dir))
        if self.level1 is not None:
            kit = self.level1
            self.step("tier-1 configuration", lambda: kit.prepare(data_dir, source))
        service = self.service_factory(data_dir)
        try:
            started: list[ServiceInfo] = []
            self.step("service start", lambda: self._start(service, started))
            info = started[0]
            self.step("health", lambda: self._health(info))
            self.step("token required", lambda: self._token_required(info))
            self.step("web front end", lambda: self._web(info))
            self.step("tier 0 shows no device data", lambda: self._no_device_data(info))
            if self.level1 is not None:
                self._tier1(info, self.level1, count)
        finally:
            service.stop()  # first: a takeover still running ends its transaction against the gateway
            if self.level1 is not None:
                self.level1.close()
            self.service = {
                "stopped_by": service.stopped_by,
                "exit_code": service.exit_code,
                "service_file_left_behind": service.service_file_left_behind,
            }
        self.step("service stop", lambda: self._stopped(service))
        self.step("source untouched", lambda: self._untouched(source, before))
        if self.level1 is not None:
            self.step("no thread left in the service", lambda: self._threads_left(data_dir))
            kit = self.level1
            self.step("Qt version", lambda: self._qt_version(kit))
        self.step("window toolkit", self._window_toolkit)
        self.step("webview2 offline installer", self._installer)

    def _write(self, source: Path, written: list[int]) -> str:
        written.append(self.make_database(source))
        return f"{written[0]} records in {source.name}"

    @staticmethod
    def _start(service: ServiceProcess, started: list[ServiceInfo]) -> str:
        info = service.start()
        started.append(info)
        return f"{info.base_url}, pid {info.pid}"

    def _health(self, info: ServiceInfo) -> str:
        answer = request(info, "/api/v0/health", None)
        check(answer.status == HTTP_OK, f"health answered {answer.status}")
        body = answer.json()
        check(body.get("version") == self.expect.version, f"version {body.get('version')} != {self.expect.version}")
        check(body.get("tier") == 0, f"device-write tier {body.get('tier')}, expected 0 (S-4)")
        return f"version {body['version']}, tier 0, build {body.get('build_commit')}"

    def _token_required(self, info: ServiceInfo) -> str:
        status = request(info, "/api/v0/devices", None).status
        check(status == HTTP_UNAUTHORIZED, f"a request without the token answered {status}")
        return "401 without the token"

    def _web(self, info: ServiceInfo) -> str:
        page = request(info, "/", None)
        if page.status == HTTP_NOT_FOUND and not self.expect.require_web:
            return "no built front end in this source checkout (allowed outside a frozen build)"
        check(page.status == HTTP_OK and APP_ROOT_MARKER in page.body.decode("utf-8"), f"/ answered {page.status}")
        check("default-src 'self'" in page.headers.get("content-security-policy", ""), "no Content-Security-Policy")

        def fetch(path: str) -> bytes:
            answer = request(info, path, None)
            check(answer.status == HTTP_OK, f"{path} answered {answer.status}")
            return answer.body

        try:
            loaded = check_page(page.body.decode("utf-8"), fetch)
        except WebAssetError as error:
            raise StepFailed(str(error)) from error
        for name in WEB_FILES:
            check(bool(fetch("/" + name)), f"/{name} is empty")
        return "index.html with CSP; " + ", ".join([*loaded, *WEB_FILES])

    def _no_device_data(self, info: ServiceInfo) -> str:
        answer = request(info, "/api/v0/devices", info.token)
        check(answer.status == HTTP_OK, f"device list answered {answer.status}: {answer.body[:300]!r}")
        configured = [item["key"] for item in answer.json()["items"] if item["configured"]]
        check(not configured, f"tier 0 lists devices {configured}, expected none")
        start, end = self.expect.first_day
        query = urllib.parse.urlencode({"start": start, "end": end})
        status = request(info, f"/api/v0/devices/p1/acquisitions?{query}", info.token).status
        check(status == HTTP_NOT_FOUND, f"records of p1 at tier 0 answered {status}, expected 404")
        return "no device listed, records of p1 refused (404) at tier 0"

    def _first_record(self, info: ServiceInfo, count: int, ids: list[int]) -> str:
        start, end = self.expect.first_day
        query = urllib.parse.urlencode({"start": start, "end": end})
        answer = request(info, f"/api/v0/devices/p1/acquisitions?{query}", info.token)
        check(answer.status == HTTP_OK, f"record list answered {answer.status}: {answer.body[:300]!r}")
        items = answer.json()["items"]
        check(len(items) == count, f"{len(items)} records listed, expected {count}")
        ids.append(int(items[0]["id"]))
        return f"{count} records, first id {ids[0]}"

    def _detail(self, info: ServiceInfo, record_id: int) -> str:
        answer = request(info, f"/api/v0/devices/p1/acquisitions/{record_id}", info.token)
        check(answer.status == HTTP_OK, f"record {record_id} answered {answer.status}")
        detail = answer.json()
        metrics = sum(len(group["items"]) for group in detail["groups"])
        points = detail["spectrum"]["points"] if detail.get("spectrum") else []
        check(detail["success"] and detail["spectrum_state"] == "ok", "the record or its spectrum did not come back")
        check(detail["record"]["id"] == record_id, f"asked for record {record_id}, got {detail['record']['id']}")
        check(metrics == EXPECTED_METRICS, f"{metrics} metrics, expected {EXPECTED_METRICS}")
        check(
            len(points) == EXPECTED_SPECTRUM_POINTS,
            f"{len(points)} spectrum points, expected {EXPECTED_SPECTRUM_POINTS}",
        )
        check(all(isinstance(value, int | float) for value in points), "the spectrum holds non-numeric points")
        return f"record {record_id}: {metrics} metrics, spectrum {len(points)} points"

    def _stopped(self, service: ServiceProcess) -> str:
        check(
            service.stopped_by == STOPPED_BY_REQUEST, f"stopped by {service.stopped_by}, expected the shutdown request"
        )
        check(service.exit_code == 0, f"service exit code {service.exit_code}")
        check(not service.service_file_left_behind, "the service did not remove its service.json (the shell had to)")
        if self.expect.require_windows_stack:
            check(watches_shell(service.data_dir), f"the service log has no '{WATCHING_SHELL}' line")
            watch = "it watched the shell process"
        else:
            watch = "shell watch checked in the frozen Windows build"
        return f"stopped by {service.stopped_by}, exit code 0, service.json removed by the service; {watch}"

    @staticmethod
    def _untouched(source: Path, before: str) -> str:
        check(sha256(source) == before, "the source database changed")
        left = [suffix for suffix in SIDE_FILES if source.with_name(source.name + suffix).exists()]
        check(not left, f"files created beside the source: {left}")
        return "SHA-256 unchanged, nothing created beside it"

    # ---------------------------------------------------------------- tier 1 (16_ 8.2)

    def _tier1(self, info: ServiceInfo, kit: Level1, count: int) -> None:
        self.step("tier 0 refuses acquisition", lambda: self._refused(info))
        self.step("tier 0 -> 1", lambda: self._tier_up(info))
        ids: list[int] = []
        self.step("record list", lambda: self._first_record(info, count, ids))
        self.step("record detail", lambda: self._detail(info, ids[0]))
        if not kit.lock_free():
            self.steps.append({"name": "V1.0.3 lock free", "passed": True, "detail": LEVEL1_SKIPPED})
            self.step("tier 1 -> 0", lambda: self._tier_down(info))
            self.level1_result = LEVEL1_SKIPPED
            return
        self.step("takeover start", lambda: self._takeover_start(info))
        self.step("takeover record", lambda: self._takeover_record(info, kit))
        self.step("takeover stop", lambda: self._takeover_stop(info, kit))
        self.step("tier 1 -> 0", lambda: self._tier_down(info))
        self.level1_result = LEVEL1_PASSED

    @staticmethod
    def _refused(info: ServiceInfo) -> str:
        status = request(info, "/api/v0/acquisition/start", info.token, {}).status
        check(status == HTTP_FORBIDDEN, f"POST /acquisition/start at tier 0 answered {status}, expected 403")
        return "POST /acquisition/start: 403 at tier 0"

    @staticmethod
    def _tier_up(info: ServiceInfo) -> str:
        issued = request(info, "/api/v0/tier/confirmations", info.token, {"tier": 1})
        check(issued.status == HTTP_CREATED, f"tier confirmation answered {issued.status}: {issued.body[:300]!r}")
        body = {"tier": 1, "confirmation_id": issued.json()["confirmation_id"]}
        answer = request(info, "/api/v0/tier", info.token, body, method="PUT")
        check(answer.status == HTTP_OK, f"PUT /tier 1 answered {answer.status}: {answer.body[:300]!r}")
        state = answer.json()
        check(state["tier"] == 1 and not state["lock_held"], f"after PUT /tier 1: {state}")
        return "tier 1 after the two-step confirmation; lock not taken yet"

    @staticmethod
    def _takeover_start(info: ServiceInfo) -> str:
        answer = request(info, "/api/v0/acquisition/start", info.token, {})
        check(
            answer.status == HTTP_ACCEPTED, f"POST /acquisition/start answered {answer.status}: {answer.body[:300]!r}"
        )
        status = answer.json()
        check(status["lock_held"], f"takeover started without V1.0.3's lock: {status}")
        return f"takeover {status['takeover']}, V1.0.3's lock held by the service"

    def _status(self, info: ServiceInfo) -> dict[str, Any]:
        answer = request(info, "/api/v0/acquisition/status", info.token)
        check(answer.status == HTTP_OK, f"GET /acquisition/status answered {answer.status}")
        return dict(answer.json())

    def _wait(
        self, info: ServiceInfo, done: Callable[[dict[str, Any]], bool], seconds: float, what: str
    ) -> dict[str, Any]:
        waited = 0.0  # counts the pauses only: with slow answers the real wait is longer (it fails late, never passes)
        while True:
            status = self._status(info)
            if done(status):
                return status
            check(waited < seconds, f"{what} not reached within {seconds:.0f} s: {status}")
            self.sleep(LEVEL1_POLL_SECONDS)
            waited += LEVEL1_POLL_SECONDS

    def _takeover_record(self, info: ServiceInfo, kit: Level1) -> str:
        def recorded(status: dict[str, Any]) -> bool:
            check(status["halt"] is None and not status["error"], f"the takeover failed: {status}")
            devices = status["devices"]
            return bool(devices and devices[0].get("latest_record_id"))

        status = self._wait(info, recorded, RECORD_TIMEOUT_SECONDS, "a saved record")
        requests, opened, _closed = kit.counts()
        check(requests > 0 and opened > 0, f"the synthetic gateway saw {requests} requests on {opened} connections")
        check(not kit.lock_free(), "V1.0.3's lock is free while the service has taken over (V1.0.3 could start)")
        record = status["devices"][0]["latest_record_id"]
        return f"record {record} saved; {requests} Modbus TCP requests to 127.0.0.1; V1.0.3's lock held"

    def _takeover_stop(self, info: ServiceInfo, kit: Level1) -> str:
        answer = request(info, "/api/v0/acquisition/stop", info.token, {})
        check(answer.status == HTTP_ACCEPTED, f"POST /acquisition/stop answered {answer.status}: {answer.body[:300]!r}")
        status = self._wait(
            info,
            lambda status: status["takeover"] == "released" and not status["lock_held"],
            TAKEOVER_STOP_TIMEOUT_SECONDS,
            "the takeover released",
        )
        check(kit.lock_free(), "V1.0.3's lock is still held after the takeover stopped")
        waited = 0.0
        while True:  # pymodbus closes its socket when the transaction ends; the gateway sees it a moment later
            requests, opened, closed = kit.counts()
            if opened == closed:
                break
            check(waited < TAKEOVER_STOP_TIMEOUT_SECONDS, f"{opened - closed} gateway connection(s) still open")
            self.sleep(LEVEL1_POLL_SECONDS)
            waited += LEVEL1_POLL_SECONDS
        return f"takeover {status['takeover']}; lock free again (V1.0.3 could start); {opened} connection(s) closed"

    def _tier_down(self, info: ServiceInfo) -> str:
        answer = request(info, "/api/v0/tier", info.token, {"tier": 0}, method="PUT")
        check(answer.status == HTTP_OK, f"PUT /tier 0 answered {answer.status}: {answer.body[:300]!r}")
        check(answer.json()["tier"] == 0, f"after PUT /tier 0: {answer.json()}")
        self._refused(info)
        return "tier 0; acquisition refused again (403)"

    @staticmethod
    def _threads_left(data_dir: Path) -> str:
        log = data_dir.joinpath(*SERVICE_LOG)
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if SERVICE_STOPPED in line]
        check(bool(lines), f"{log.name} has no '{SERVICE_STOPPED}' line: the service did not finish its shutdown")
        check(lines[-1].endswith(NO_THREADS_LEFT), f"threads left in the service: {lines[-1]}")
        return NO_THREADS_LEFT

    def _qt_version(self, kit: Level1) -> str:
        versions = kit.qt_versions()
        text = f"{versions.get('binding')} {versions.get('version')}, Qt {versions.get('qt')}"
        check(versions.get("binding") == ALPHA_QT_BINDING, f"the service code runs on {text}, not on PySide6")
        if not self.frozen:
            return text + " (source checkout: requirements.lock is checked by the build)"
        try:
            recorded = json.loads((self.program_dir / MANIFEST).read_text(encoding="utf-8"))["qt"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise StepFailed(f"{MANIFEST} records no Qt versions: {error!r}") from error
        check(recorded.get("runtime") == versions, f"{text} in the package, {MANIFEST} records {recorded}")
        return f"{text}, as recorded in {MANIFEST} (requirements.lock: {recorded.get('locked')})"

    def _window_toolkit(self) -> str:
        """Load pywebview's Windows back end without opening a window: .NET through pythonnet, the WebView2 SDK."""
        if not self.expect.require_windows_stack:
            return "not checked outside a frozen Windows build"
        for module in WINDOWS_BACK_END:
            importlib.import_module(module)
        return ", ".join(WINDOWS_BACK_END) + " loaded"

    def _installer(self) -> str:
        installer = offline_installer(self.program_dir)
        if installer is None:
            check(not self.expect.require_installer, f"no offline installer in {self.program_dir / 'redist'}")
            return "not required outside a frozen Windows build"
        size = installer.stat().st_size
        try:
            recorded = json.loads((self.program_dir / MANIFEST).read_text(encoding="utf-8"))["webview2_installer"]
            expected_hash, expected_size = str(recorded["sha256"]), int(recorded["size"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise StepFailed(f"{MANIFEST} records no checked WebView2 installer: {error!r}") from error
        check(size >= WEBVIEW2_MIN_BYTES, f"{installer.name} has {size} bytes: not the standalone installer")
        with installer.open("rb") as stream:
            check(stream.read(2) == WINDOWS_PROGRAM_MAGIC, f"{installer.name} is not a Windows program")
        check(size == expected_size, f"{installer.name} has {size} bytes, {MANIFEST} records {expected_size}")
        check(sha256(installer) == expected_hash, f"{installer.name} differs from the checked file (SHA-256)")
        return f"{installer.name}, {size} bytes, matches {MANIFEST} (SHA-256 {expected_hash[:12]}...)"


def run_self_test(report_path: Path, test: SelfTest) -> int:
    if report_path.exists():  # fail before starting anything; the "x" open below guards against a race
        raise FileExistsError(f"self-test report already exists: {report_path}")
    report: dict[str, Any] = {
        "version": test.expect.version,
        "frozen": test.frozen,
        "platform": sys.platform,
        "single_instance_lock": SINGLE_INSTANCE_NAME,
        "webview2_runtime": runtime_version(windows_registry) if sys.platform == "win32" else None,
    }
    work = Path(tempfile.mkdtemp(prefix="par_alpha_self_test_"))
    try:
        test.run(work)
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["error"] = traceback.format_exc()
    finally:
        report["steps"] = test.steps
        report["service"] = test.service
        report["level1"] = test.level1_result
        shutil.rmtree(work, onerror=lambda _f, path, info: report.setdefault("cleanup_errors", []).append(str(path)))
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return 0 if report["passed"] else 1
