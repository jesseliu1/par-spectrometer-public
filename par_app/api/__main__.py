"""Service entry point: python -m par_app.api [--port 0] [--data-dir <dir>].

Binds 127.0.0.1 only (there is no option for another address; S-7: no LAN access in the alpha). Port 0 lets the
system pick a free port. Once the socket listens, the address it is actually bound to and a one-time token go to
<data-dir>/service.json (mode 600), which the shell reads and may connect to at once; the file is removed again when
the service stops. service.json also carries the launch id the shell put in PAR_SERVICE_LAUNCH_ID (null when started
without one): the shell recognises its own service by it, since through a Windows venv launcher the service's pid is
not the pid the shell started (issue #66).

Stopping: the shell's stop request is POST /api/v0/shutdown with the token (review of PR #50, major 1: the
windowed exe has sys.stdin None on Windows, so the end of a pipe cannot reach it); uvicorn then shuts down gracefully
and the process exits 0. The end of stdin (--stop-on-stdin-eof, review Q-1) stays a second channel where stdin exists
(the source tree; on POSIX also a crashed shell), and SIGTERM (POSIX) or CTRL_BREAK (Windows console) still work.
With --parent-pid the service also stops gracefully when the shell process is gone (a crashed shell;
par_app/parent_watch.py, D-223).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import signal
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import BinaryIO, Protocol

import uvicorn

from ..application import ALPHA_VERSION
from ..application.paths import AlphaPaths, default_data_dir
from ..domain.clock import SystemClock
from ..parent_watch import PARENT_PID, open_parent, watch_parent
from .app import create_app
from .context import ServiceContext
from .static import INDEX, default_web_dir

LOOPBACK = "127.0.0.1"
TOKEN_BYTES = 32
"""secrets.token_urlsafe(32): 256 random bits, 43 URL-safe characters."""
SERVICE_FILE_MODE = 0o600
"""Owner read/write only (POSIX). On Windows the file sits in the per-user %LOCALAPPDATA% instead."""
HIGHEST_PORT = 65535
STOP_ON_STDIN_EOF = "--stop-on-stdin-eof"
"""Set by the shell (par_shell/service.py keeps the same string): stop when stdin reaches its end."""
FIRST_RUN_TIER = "--first-run-tier"
"""The tier the product service reads without a settings file (issue #119); tests and the self-test pass 0."""
LAUNCH_ID_ENV = "PAR_SERVICE_LAUNCH_ID"
"""Set by the shell (par_shell/service.py keeps the same string): this launch's id, written into service.json."""
LOG = logging.getLogger("par_app.api")


def launch_id() -> str | None:
    """The launch id the shell gave this process, or None."""
    return os.environ.get(LAUNCH_ID_ENV) or None


class _Readable(Protocol):
    def read(self) -> bytes: ...


def watch_stdin(stream: _Readable | BinaryIO, stop: Callable[[], None]) -> None:
    """Block until `stream` ends (the shell closed the pipe, or the shell is gone), then ask for a stop."""
    try:
        stream.read()
    except (OSError, ValueError) as error:
        LOG.warning("stdin of the service failed (%s); stopping", error)
    stop()


class RawStdin:
    """Reads the file descriptor with os.read, not through sys.stdin.buffer: a daemon thread blocked in the buffered
    reader holds its lock, and Python aborts at exit when the service stops by request while stdin is still open
    ("could not acquire lock for <stdin> at interpreter shutdown", seen as exit code -6)."""

    CHUNK = 65536

    def __init__(self, descriptor: int) -> None:
        self.descriptor = descriptor

    def read(self) -> bytes:
        while os.read(self.descriptor, self.CHUNK):
            pass
        return b""


def write_service_file(path: Path, payload: dict[str, object]) -> None:
    """Write `payload` as JSON with mode 600 from the first byte on (created via os.open), then move it in place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, SERVICE_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.chmod(temporary, SERVICE_FILE_MODE)  # independent of the umask
    os.replace(temporary, path)


def remove_service_file(path: Path, token: str) -> None:
    """Remove service.json only if it is still ours (another instance may have replaced it)."""
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("token") == token:
            path.unlink()
    except (OSError, ValueError) as error:
        LOG.warning("service file %s not removed: %s", path, error)


def _stop_requested(signum: int, _frame: FrameType | None) -> None:
    """Uvicorn re-raises the stop signal after a graceful shutdown; exit normally so service.json is removed."""
    raise SystemExit(0)


def _port(text: str) -> int:
    value = int(text)
    if not 0 <= value <= HIGHEST_PORT:
        raise argparse.ArgumentTypeError(f"port must be 0–{HIGHEST_PORT}, got {value}")
    return value


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m par_app.api", description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=_port, default=0, help="TCP port on 127.0.0.1; 0 picks a free one (default)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="alpha data directory (default: %%LOCALAPPDATA%%\\PAR_Spectrometer_2)",
    )
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=None,
        help="built front end to serve at / (default: $PAR_WEB_DIR, the bundle, or web/dist when built)",
    )
    parser.add_argument(
        STOP_ON_STDIN_EOF,
        action="store_true",
        help="stop gracefully when stdin ends (set by the desktop shell, which closes the pipe to stop the service)",
    )
    parser.add_argument(
        PARENT_PID,
        type=int,
        default=None,
        help="pid of the desktop shell: stop gracefully when that process is gone (par_app/parent_watch.py, D-223)",
    )
    parser.add_argument(
        FIRST_RUN_TIER,
        type=int,
        choices=(0, 1),
        default=1,
        help="tier without a settings file (par_app.service_main only): 1 acquires at once, as V1.0.3 (issue #119); "
        "tests and the self-test pass 0",
    )
    args = parser.parse_args(argv)
    if args.web_dir is not None and not (args.web_dir / INDEX).is_file():
        parser.error(f"--web-dir {args.web_dir} holds no {INDEX} (run npm run build in web/)")
    return args


def _watch_stdin_in_background(server: uvicorn.Server) -> None:
    def stop() -> None:
        LOG.info("stop requested: stdin closed by the shell")
        server.should_exit = True  # uvicorn's own graceful shutdown, checked by its main loop

    try:
        descriptor = sys.stdin.fileno()  # AttributeError: None (windowed exe); OSError/ValueError: no real file
    except (AttributeError, OSError, ValueError):
        LOG.warning("%s given but the service has no stdin; POST /api/v0/shutdown stops it", STOP_ON_STDIN_EOF)
        return
    reader = RawStdin(descriptor)
    threading.Thread(target=watch_stdin, args=(reader, stop), name="stdin-watch", daemon=True).start()


def _configure_logging(paths: AlphaPaths) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    handlers.append(logging.FileHandler(paths.logs_dir / "service.log", encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # the shell is taken hold of first, before the seconds of setup below (review N3 of PR #56)
    parent = open_parent(args.parent_pid, SystemClock()) if args.parent_pid is not None else None
    paths = AlphaPaths((args.data_dir or default_data_dir()).resolve())
    paths.ensure()
    _configure_logging(paths)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((LOOPBACK, args.port))
    listener.listen()  # connections wait in the backlog until uvicorn accepts them (review N-7)
    bound_host, port = listener.getsockname()  # (host, port) for AF_INET
    host = f"{bound_host}:{port}"  # what the socket is really bound to, not the constant (review M-3)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    context = ServiceContext(paths, SystemClock())
    web_dir = args.web_dir.resolve() if args.web_dir else default_web_dir()
    servers: list[uvicorn.Server] = []

    def request_stop() -> None:
        LOG.info("stop requested: shutdown requested by the shell")
        servers[0].should_exit = True  # uvicorn's own graceful shutdown, checked by its main loop

    app = create_app(context, token=token, allowed_hosts=(host,), web_dir=web_dir, request_stop=request_stop)
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="off", access_log=False))
    servers.append(server)
    payload: dict[str, object] = {
        "base_url": f"http://{host}",
        "port": port,
        "token": token,
        "pid": os.getpid(),
        "version": ALPHA_VERSION,
        "started_at": context.started_at,
        "data_dir": str(paths.data_dir),
        "launch_id": launch_id(),
    }
    write_service_file(paths.service_file, payload)
    LOG.info("PAR local service %s listening on http://%s (data %s)", ALPHA_VERSION, host, paths.data_dir)
    LOG.info("web front end: %s", web_dir or "not built (API only)")
    if args.stop_on_stdin_eof:
        _watch_stdin_in_background(server)
    if args.parent_pid is not None:
        watch_parent(args.parent_pid, lambda: setattr(server, "should_exit", True), context.clock, parent)
    signal.signal(signal.SIGTERM, _stop_requested)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, _stop_requested)  # the shell's CTRL_BREAK (par_shell/service.py; untested)
    try:
        server.run(sockets=[listener])
    except KeyboardInterrupt:
        LOG.info("stopped by Ctrl+C")
    finally:
        remove_service_file(paths.service_file, token)
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
