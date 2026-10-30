"""python -m par_app.api: binds 127.0.0.1 on a free port and publishes port and token in service.json (mode 600).

The service runs as a real subprocess on the loopback interface only; no other host is contacted (R-4-7).
"""

from __future__ import annotations

import io
import json
import os
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from par_app.api import __main__ as entry
from par_app.api.__main__ import LAUNCH_ID_ENV, STOP_ON_STDIN_EOF
from par_shell.service import STOPPED_BY_REQUEST, ServiceProcess

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
START_TIMEOUT_SECONDS = 30.0
LAUNCH_ID = "launch-id-of-this-test"


def _start(
    tmp_path: Path, extra: tuple[str, ...] = (), stdin: int | None = None
) -> Iterator[tuple[subprocess.Popen[bytes], dict[str, Any], Path]]:
    data_dir = tmp_path / "alpha data"
    process = subprocess.Popen(
        [sys.executable, "-m", "par_app.api", "--port", "0", "--data-dir", str(data_dir), *extra],
        cwd=ROOT,
        env=dict(os.environ, **{LAUNCH_ID_ENV: LAUNCH_ID}),
        stdin=stdin,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    service_file = data_dir / "service.json"
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    info: dict[str, Any] | None = None
    while time.monotonic() < deadline and process.poll() is None:
        try:
            info = json.loads(service_file.read_text(encoding="utf-8"))
            httpx.get(f"{info['base_url']}/api/v0/health", timeout=1.0)
            break
        except (OSError, ValueError, httpx.HTTPError):
            time.sleep(0.05)
    if info is None or process.poll() is not None:
        process.kill()
        stderr = process.communicate()[1].decode(errors="replace")
        pytest.fail(f"service did not start: {stderr}")
    try:
        yield process, info, service_file
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.fixture
def service(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[bytes], dict[str, Any], Path]]:
    yield from _start(tmp_path)


@pytest.fixture
def piped_service(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[bytes], dict[str, Any], Path]]:
    yield from _start(tmp_path, (STOP_ON_STDIN_EOF,), subprocess.PIPE)


def test_service_publishes_port_and_token_and_guards_requests(
    service: tuple[subprocess.Popen[bytes], dict[str, Any], Path],
) -> None:
    process, info, service_file = service
    assert set(info) == {"base_url", "port", "token", "pid", "version", "started_at", "data_dir", "launch_id"}
    assert info["base_url"] == f"http://127.0.0.1:{info['port']}"
    assert info["port"] > 0 and len(info["token"]) >= 43
    # the launch id the shell set, and the service's own pid: Popen.pid only without a Windows venv launcher (#66)
    assert info["launch_id"] == LAUNCH_ID and isinstance(info["pid"], int) and info["pid"] > 0
    assert process.poll() is None
    base = info["base_url"]
    assert httpx.get(f"{base}/api/v0/health").json()["tier"] == 0
    assert httpx.get(f"{base}/api/v0/devices").status_code == 401
    assert httpx.get(f"{base}/api/v0/devices", headers={"Authorization": f"Bearer {info['token']}"}).status_code == 200
    assert httpx.get(f"{base}/api/v0/health", headers={"Host": f"localhost:{info['port']}"}).status_code == 403
    if sys.platform != "win32":
        assert stat.S_IMODE(service_file.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="graceful stop by SIGTERM is POSIX-only")
def test_service_file_is_removed_on_stop(service: tuple[subprocess.Popen[bytes], dict[str, Any], Path]) -> None:
    process, _info, service_file = service
    os.kill(process.pid, signal.SIGTERM)
    assert process.wait(timeout=START_TIMEOUT_SECONDS) == 0
    assert not service_file.exists()
    assert (service_file.parent / "data" / "imported").is_dir()
    assert (service_file.parent / "logs" / "service.log").is_file()


def test_bad_port_is_refused(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "par_app.api", "--port", "70000", "--data-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        timeout=START_TIMEOUT_SECONDS,
    )
    assert result.returncode == 2
    assert b"port must be 0" in result.stderr


def test_service_binds_and_publishes_the_loopback_address_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review M-3 (mutant M06) and N-7: S-7 says no LAN access, so the bound address itself is checked, and the
    port already accepts connections when service.json appears (the shell may connect right away)."""
    import socket

    import uvicorn

    bound: list[tuple[str, int]] = []
    seen: dict[str, Any] = {}
    real_bind = socket.socket.bind

    def recording_bind(self: socket.socket, address: tuple[str, int]) -> None:
        bound.append(address)
        real_bind(self, address)

    def fake_run(_server: uvicorn.Server, sockets: list[socket.socket]) -> None:
        info = json.loads((tmp_path / "service.json").read_text(encoding="utf-8"))
        seen.update(info=info, address=sockets[0].getsockname())
        with socket.create_connection(("127.0.0.1", info["port"]), timeout=5.0):
            pass  # listening already: the backlog accepts the connection before uvicorn runs

    monkeypatch.setattr(entry, "_configure_logging", lambda _paths: None)  # no handlers left on the root logger
    monkeypatch.setattr(entry.signal, "signal", lambda *_args: None)  # keep the test process's SIGTERM handler
    monkeypatch.setattr(socket.socket, "bind", recording_bind)
    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    assert entry.main(["--port", "0", "--data-dir", str(tmp_path)]) == 0

    assert [host for host, _port in bound] == ["127.0.0.1"]
    host, port = seen["address"]
    assert host == "127.0.0.1"
    assert seen["info"]["base_url"] == f"http://127.0.0.1:{port}" and seen["info"]["port"] == port
    assert not (tmp_path / "service.json").exists()


def test_closing_stdin_stops_the_service_gracefully_on_every_platform(
    piped_service: tuple[subprocess.Popen[bytes], dict[str, Any], Path],
) -> None:
    """Review Q-1: the shell's stop signal is the end of the child's stdin (no console needed, unlike CTRL_BREAK)."""
    process, _info, service_file = piped_service
    assert process.stdin is not None
    process.stdin.close()
    assert process.wait(timeout=START_TIMEOUT_SECONDS) == 0
    assert not service_file.exists()
    log = (service_file.parent / "logs" / "service.log").read_text(encoding="utf-8")
    assert "stdin closed" in log


def test_the_stdin_watch_reports_the_end_of_input_and_a_broken_pipe() -> None:
    stops: list[str] = []
    entry.watch_stdin(io.BytesIO(b"ignored input"), lambda: stops.append("eof"))
    assert stops == ["eof"]

    class Broken:
        def read(self) -> bytes:
            raise OSError("pipe broken")

    entry.watch_stdin(Broken(), lambda: stops.append("broken"))
    assert stops == ["eof", "broken"]


NO_STDIN = "import sys; sys.stdin = None; from par_app.api.__main__ import main; raise SystemExit(main(sys.argv[1:]))"
"""The service as a PyInstaller windowed exe starts it on Windows: sys.stdin is None (no console)."""


def test_a_service_without_stdin_stops_gracefully_on_the_shutdown_request(tmp_path: Path) -> None:
    """review of PR #50, major 1: with console=False closing the pipe cannot reach the service; the shell's
    POST /api/v0/shutdown (token, no Origin) must still stop it with exit code 0 and service.json removed by it."""
    data_dir = tmp_path / "alpha"
    child = ServiceProcess(data_dir)
    command = [sys.executable, "-c", NO_STDIN, "--port", "0", "--data-dir", str(data_dir), STOP_ON_STDIN_EOF]
    child.start(command)
    child.stop()
    assert child.stopped_by == STOPPED_BY_REQUEST
    assert child.exit_code == 0
    assert not child.service_file_left_behind and not (data_dir / "service.json").exists()
    log = (data_dir / "logs" / "service.log").read_text(encoding="utf-8")
    assert "has no stdin" in log and "shutdown requested" in log
