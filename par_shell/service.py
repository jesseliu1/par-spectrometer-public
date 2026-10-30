"""The service child process: start, wait until it answers, stop (13_ 3.1).

The service writes <data dir>/service.json once its socket listens (par_app/service_main.py, with the options of
par_app/api/__main__.py); the shell waits for a service.json that carries the launch id it gave this child (a fresh
random value in the PAR_SERVICE_LAUNCH_ID environment variable), then for GET /api/v0/health. Not by the pid (issue
#66): from a Windows venv, sys.executable is a launcher that runs the real interpreter as its own child, so the pid
in service.json (the service's os.getpid(), ServiceInfo.pid) differs from Popen.pid (the launcher's); the launcher
passes on stdin, the console's CTRL_BREAK and the exit code, so the stops below still work through it. The frozen
exe has no launcher. Stopping asks in this order, each with
the grace period to exit: POST /api/v0/shutdown with the token (review of PR #50, major 1: the windowed exe has
no stdin on Windows, so the HTTP request is the stop path that works there), then the end of the child's stdin
(--stop-on-stdin-eof, review Q-1), then SIGTERM (POSIX) or CTRL_BREAK (Windows), then kill. A service.json the child
could not remove is removed here, but only if it is still the child's (same launch id). Not yet verified on
Windows. If the shell
crashes, the child sees that the process given as --parent-pid is gone and stops gracefully by itself (it finishes
the transaction in progress, resume command included, and releases V1.0.3's lock), with its own backstop after
STOP_TIMEOUT_SECONDS (par_app/parent_watch.py; review of PR #56, blocker 2; D-223). The child is no longer put
in a kill-on-close Job Object: Windows would end it at once when the shell ends, possibly between the freeze and the
resume, and that kill cannot be delayed. How the last stop went
(request, stdin, signal or kill), the exit code and whether service.json had to be removed here are kept for the
alpha self-test (self_test.py).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import signal
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from par_app.domain.clock import Clock, SystemClock

SERVICE_FILE = "service.json"
DATA_DIR_ENV = "PAR_ALPHA_DATA_DIR"
PRODUCT_DIR_NAME = "PAR_Spectrometer_2"
START_TIMEOUT_SECONDS = 30.0
STOP_TIMEOUT_SECONDS = 60.0
"""Wait for the service to exit by itself: while it has taken over acquisition it first stops the coordinator, which
may take one acquisition transaction budget (40 s, coordinator.ACQUISITION_TRANSACTION_BUDGET_SECONDS) plus margin;
killing it earlier could leave a device frozen (16_ 1.5)."""
SERVICE_MODULE = "par_app.service_main"
"""The service with the Qt main loop and the tier-1 takeover (16_ 1.6); par_app.api alone has no acquisition."""
POLL_SECONDS = 0.1
HEALTH_TIMEOUT_SECONDS = 2.0
HEALTH_PATH = "/api/v0/health"
SHUTDOWN_PATH = "/api/v0/shutdown"
STOP_ON_STDIN_EOF = "--stop-on-stdin-eof"
"""The service's stop-on-end-of-stdin option (same string as par_app/api/__main__.py; a test keeps them equal)."""
LAUNCH_ID_ENV = "PAR_SERVICE_LAUNCH_ID"
"""Environment variable with this launch's id, written back into service.json by the service (same string as
par_app/api/__main__.py; a test keeps them equal)."""
LAUNCH_ID_BYTES = 16
"""secrets.token_hex(16): 128 random bits, enough to never mistake another launch's service.json for this one's."""
PARENT_PID = "--parent-pid"
"""The service stops by itself when this pid (the shell) is gone (same string as par_app/parent_watch.py)."""
SERVICE_FLAG = "--service"
"""A frozen PAR_Spectrometer_2.exe runs as the service when started with this flag (packaging PR)."""
ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("par_shell")
STOPPED_BY_REQUEST = "request"
STOPPED_BY_STDIN = "stdin"
STOPPED_BY_SIGNAL = "signal"
STOPPED_BY_KILL = "kill"
STOPPED_BEFORE = "exited before stop"


class ServiceError(RuntimeError):
    """The service did not start, or stopped answering."""


@dataclass(frozen=True)
class ServiceInfo:
    base_url: str
    port: int
    token: str
    pid: int
    """The service process's own pid (with a launcher in between, not the pid the shell started)."""
    version: str
    launch_id: str | None = None
    """The launch id the shell gave the service; None if it was started without one (by hand)."""


def default_data_dir(environ: Mapping[str, str] = os.environ) -> Path:
    """Same rule as par_app.application.paths.default_data_dir (a test keeps the two equal)."""
    override = environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    local = environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / PRODUCT_DIR_NAME
    return Path.home() / ".local" / "share" / PRODUCT_DIR_NAME


def service_command(data_dir: Path, web_dir: Path | None = None) -> list[str]:
    """The child's command line: the frozen exe in service mode, or `python -m par_app.service_main` from source."""
    if getattr(sys, "frozen", False):
        command = [sys.executable, SERVICE_FLAG]
    else:
        command = [sys.executable, "-m", SERVICE_MODULE]
    command += ["--port", "0", "--data-dir", str(data_dir), STOP_ON_STDIN_EOF, PARENT_PID, str(os.getpid())]
    if web_dir is not None:
        command += ["--web-dir", str(web_dir)]
    return command


def read_service_file(path: Path) -> ServiceInfo | None:
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return ServiceInfo(
            base_url=str(payload["base_url"]),
            port=int(payload["port"]),
            token=str(payload["token"]),
            pid=int(payload["pid"]),
            version=str(payload["version"]),
            launch_id=_optional_text(payload.get("launch_id")),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _no_proxy_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never send 127.0.0.1 through a proxy


def health(info: ServiceInfo, timeout: float = HEALTH_TIMEOUT_SECONDS) -> dict[str, Any]:
    with _no_proxy_opener().open(info.base_url + HEALTH_PATH, timeout=timeout) as response:
        body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return body


def request_shutdown(info: ServiceInfo, timeout: float = HEALTH_TIMEOUT_SECONDS) -> None:
    """POST /api/v0/shutdown with the token and no Origin header (the service refuses a page's request)."""
    call = urllib.request.Request(
        info.base_url + SHUTDOWN_PATH, data=b"", headers={"Authorization": f"Bearer {info.token}"}, method="POST"
    )
    with _no_proxy_opener().open(call, timeout=timeout):
        pass  # urllib raises HTTPError (an OSError) for any answer other than 2xx


class ServiceProcess:
    """One service child. Use as a context manager: the service is stopped on exit, whatever happened."""

    def __init__(
        self,
        data_dir: Path,
        web_dir: Path | None = None,
        popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        clock: Clock | None = None,
        request_shutdown: Callable[[ServiceInfo], None] = request_shutdown,
    ) -> None:
        self.data_dir = data_dir
        self._request_shutdown = request_shutdown
        self.web_dir = web_dir
        self.service_file = data_dir / SERVICE_FILE
        self._popen = popen
        self._clock: Clock = clock if clock is not None else SystemClock()  # R-1-6 (review M-4)
        self.process: subprocess.Popen[bytes] | None = None
        self.launch_id: str | None = None
        """The id given to the last child started; its service.json must carry it (issue #66)."""
        self.info: ServiceInfo | None = None
        self.service_file_left_behind = False
        """True if the last stop() had to remove service.json itself: the child did not clean up (review M-1)."""
        self.stopped_by: str | None = None
        self.exit_code: int | None = None

    def __enter__(self) -> ServiceProcess:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def start(self, command: Sequence[str] | None = None, timeout: float = START_TIMEOUT_SECONDS) -> ServiceInfo:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP  # lets stop() send CTRL_BREAK to the child only
        self.launch_id = secrets.token_hex(LAUNCH_ID_BYTES)
        self.process = self._popen(
            list(command or service_command(self.data_dir, self.web_dir)),
            cwd=ROOT,
            stdin=subprocess.PIPE,  # closed by stop(): the service's stop request
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            env={**os.environ, LAUNCH_ID_ENV: self.launch_id},
        )
        self.info = self._wait_ready(timeout)
        return self.info

    def _wait_ready(self, timeout: float) -> ServiceInfo:
        assert self.process is not None
        deadline = self._clock.monotonic() + timeout
        while self._clock.monotonic() < deadline:
            if self.process.poll() is not None:
                raise ServiceError(
                    f"本机服务启动失败（退出码 {self.process.returncode}），日志见 {self.data_dir / 'logs'}"
                )
            info = read_service_file(self.service_file)
            if info is not None and info.launch_id == self.launch_id:
                try:
                    health(info)
                    return info
                except OSError:
                    pass
            self._clock.sleep(POLL_SECONDS)
        self.stop()
        raise ServiceError(f"本机服务在 {timeout:.0f} 秒内没有就绪，日志见 {self.data_dir / 'logs'}")

    def stop(self, timeout: float = STOP_TIMEOUT_SECONDS) -> None:
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            self.stopped_by = self._stop_running(process, timeout)
        else:
            self.stopped_by = STOPPED_BEFORE
        if self.stopped_by in (STOPPED_BY_REQUEST, STOPPED_BEFORE) and process.stdin is not None:
            process.stdin.close()  # the other stops closed it already
        self.exit_code = process.returncode
        self._remove_stale_service_file(self.launch_id)
        self.process = None

    def _stop_running(self, process: subprocess.Popen[bytes], timeout: float) -> str:
        """The shutdown request first, then the end of stdin, then a signal, each with `timeout` to exit; kill only
        if all three are ignored. Returns which of them ended the child."""
        if self.info is not None:
            try:
                self._request_shutdown(self.info)
                process.wait(timeout)
                return STOPPED_BY_REQUEST
            except (OSError, subprocess.TimeoutExpired) as error:
                LOG.warning("shutdown request did not stop the service: %s", error)
        try:
            if process.stdin is not None:
                process.stdin.close()
                process.wait(timeout)
                return STOPPED_BY_STDIN
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)  # untested on Windows (appendix C)
            else:
                process.terminate()
            process.wait(timeout)
            return STOPPED_BY_SIGNAL
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()
            return STOPPED_BY_KILL

    def _remove_stale_service_file(self, launch_id: str | None) -> None:
        """Remove service.json if the child of `launch_id` left it behind (never another launch's file)."""
        info = read_service_file(self.service_file)
        self.service_file_left_behind = info is not None and launch_id is not None and info.launch_id == launch_id
        if self.service_file_left_behind:
            self.service_file.unlink(missing_ok=True)
