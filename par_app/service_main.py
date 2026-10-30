"""The alpha service process with tier-1 acquisition: python -m par_app.service_main [same options as par_app.api].

16_ 1.3: the main thread runs a QCoreApplication event loop (no window): AcquisitionHost, DeviceHub and the
coordinator object live there, exactly as in V1.0.3, so DeviceHub's queued slots and the event bridge receive the
coordinator's signals the way V1.0.3's window does. uvicorn serves HTTP on a worker thread (uvicorn installs no
signal handlers off the main thread). Tier 0 takes the same path: the Qt loop runs, but no DeviceHub is built, no
port is opened and no lock is taken.

par_app.api (and its `python -m par_app.api` entry) may not import Qt (import contract), so the two are assembled
here. Port, token, service.json, logging and stopping on the end of stdin are par_app.api.__main__'s, unchanged.

Shutdown (16_ 1.5): the shell's POST /api/v0/shutdown (API-19; the windowed exe has no stdin on Windows), the end of
stdin, the shell process going away (--parent-pid, par_app/parent_watch.py, D-223: a crashed shell), SIGTERM /
SIGINT (/ CTRL_BREAK) and the uvicorn thread ending on its own all lead to
`ServiceRunner.request_shutdown()` queued on the main thread's Qt loop (never run inside another main-thread
call; a start interrupted by it does not start the coordinator): refuse new start / tier requests (busy), stop the
takeover (coordinator.stop(), queued signals delivered, lock released), end every event stream, stop uvicorn, wait
for its thread, remove service.json, quit the Qt loop; exit code 0. The non-daemon threads still alive after that
are logged (SERVICE_STOPPED line), which the packaged self-test reads (par_shell/self_test.py). A 200 ms timer keeps
the interpreter returning to Python so signal handlers run while the main thread waits in the Qt loop.
"""

from __future__ import annotations

import logging
import os
import secrets
import signal
import socket
import sys
import threading
from collections.abc import Callable
from types import FrameType, TracebackType

import uvicorn

from .acquisition_host.faults import TakeoverFaults
from .acquisition_host.gateway import MainThreadGateway
from .acquisition_host.host import AcquisitionHost, HostBackend, MaintenanceBackend

# Names, not "from .api import __main__ as entry": imported that way, PyInstaller left par_app.api.__main__ out of the
# package (it excludes modules called __main__) and the frozen service stopped with ImportError at start.
from .api.__main__ import (
    LOOPBACK,
    STOP_ON_STDIN_EOF,
    TOKEN_BYTES,
    launch_id,
    parse_args,
    remove_service_file,
    watch_stdin,
    write_service_file,
)
from .api.__main__ import _configure_logging as configure_logging
from .api.app import create_app
from .api.context import ServiceContext
from .api.static import default_web_dir
from .application import ALPHA_VERSION
from .application.paths import AlphaPaths, default_data_dir, v103_program_marker
from .domain.clock import SystemClock
from .parent_watch import open_parent, watch_parent
from .qt_binding import PYSIDE6, BindingError, require
from .qt_compat import QCoreApplication, QTimer

LOG = logging.getLogger("par_app.service")
SIGNAL_POLL_MILLISECONDS = 200
"""Interval of the idle timer that lets Python run signal handlers while Qt's loop waits."""
STDIN_CHUNK_BYTES = 4096
EXIT_REFUSED_DATA_DIR = 2
"""Exit code when the data directory is a V1.0.x program folder (D-215); argparse errors use the same code."""
EXIT_WRONG_QT_BINDING = 3
"""Exit code when this process does not run on PySide6 (internal notes: the alpha service never runs on PyQt5)."""
REFUSED_DATA_DIR = "数据目录 {folder} 是 V1.0.3 的程序目录（含 {marker}），alpha 不能使用：请换一个目录（D-215）。"
SERVICE_STOPPED = "service stopped;"
"""Start of the last log line (service.log): the non-daemon threads still alive, "none" when nothing is left."""
UNCAUGHT = "uncaught exception (the service goes on, D-225 item 1)"
"""Start of the service.log entry for an exception that escaped during setup, before TakeoverFaults is installed."""
UVICORN_JOIN_SECONDS = 10.0
"""How long shutdown waits for the uvicorn thread after asking it to exit (then logs and goes on)."""


class ServiceRunner:
    def __init__(
        self,
        app: QCoreApplication,
        context: ServiceContext,
        host: AcquisitionHost,
        gateway: MainThreadGateway,
        server: uvicorn.Server,
    ) -> None:
        self.app = app
        self.context = context
        self.host = host
        self.gateway = gateway
        self.server = server
        self.thread: threading.Thread | None = None
        self.shutting_down = False
        self.finished = threading.Event()
        """Set once the shutdown sequence has completed."""

    def serve(self, listener: socket.socket) -> None:
        def run() -> None:
            try:
                self.server.run(sockets=[listener])
            except Exception:
                LOG.exception("uvicorn stopped with an error")
            finally:
                self.gateway.post(self.request_shutdown)  # the HTTP side is gone: the takeover must not go on alone

        self.thread = threading.Thread(target=run, name="uvicorn")
        self.thread.start()

    def request_shutdown(self) -> None:
        """Main thread only; safe to call more than once."""
        if self.shutting_down:
            return
        self.shutting_down = True
        LOG.info("shutting down: stopping the takeover first")
        self.context.acquisition.closing = True
        try:
            self.host.shutdown()
        except Exception:
            LOG.exception("stopping the takeover failed during shutdown")
        self.context.events.close()
        self.context.acquisition.run_events.close()  # writes what is queued (bounded wait, #136)
        self.context.acquisition.bus_trace.uninstall()
        self.server.should_exit = True
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(UVICORN_JOIN_SECONDS)
            if self.thread.is_alive():
                LOG.warning("uvicorn did not stop within %.0f s", UVICORN_JOIN_SECONDS)
        self.finished.set()
        self.app.quit()


def _install_signals(runner: ServiceRunner) -> None:
    """The handler only queues the shutdown (review M3): Python runs it on the main thread between two bytecodes,
    possibly in the middle of "开始采集" (lock taken, coordinator not yet started); the shutdown then runs from the Qt
    loop once that call has finished."""

    def stop(signum: int, _frame: FrameType | None) -> None:
        LOG.info("stop requested by signal %d", signum)
        QTimer.singleShot(0, runner.request_shutdown)

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        number = getattr(signal, name, None)
        if number is not None:
            signal.signal(number, stop)


def _watch_stdin(runner: ServiceRunner) -> None:
    try:
        sys.stdin.fileno()  # AttributeError: None (windowed exe); OSError/ValueError: not a real file
    except (AttributeError, OSError, ValueError):
        LOG.warning("%s given but the service has no stdin; POST /api/v0/shutdown stops it", STOP_ON_STDIN_EOF)
        return

    def stop() -> None:
        LOG.info("stop requested: stdin closed by the shell")
        runner.gateway.post(runner.request_shutdown)

    threading.Thread(target=watch_stdin, args=(_RawStdin(), stop), name="stdin-watch", daemon=True).start()


class _RawStdin:
    """stdin read with os.read on its descriptor. The watcher is a daemon thread still blocked in this read when a
    signal stops the service; through sys.stdin.buffer it would hold the BufferedReader's lock at interpreter
    shutdown, which aborts the process (Fatal Python error: _enter_buffered_busy) instead of exiting 0."""

    def read(self) -> bytes:
        descriptor = sys.stdin.fileno()
        while os.read(descriptor, STDIN_CHUNK_BYTES):
            pass
        return b""


def _takeover(paths: AlphaPaths, context: ServiceContext, gateway: MainThreadGateway) -> AcquisitionHost:
    """The tier-1 takeover (16_) and the tier-2 maintenance controller (17_) on this main thread, with the takeover
    layer of D-225 item 1 as sys.excepthook (acquisition_host/faults.py)."""
    acquisition = context.acquisition
    host = AcquisitionHost(
        paths.data_dir, acquisition.cache, context.events.publish, acquisition.publish_state, clock=context.clock
    )
    acquisition.attach(HostBackend(host, gateway), MaintenanceBackend(host, gateway))
    acquisition.bus_trace.install()  # every serial port the takeover opens is traced in memory (#136)
    # D-225 item 1 from here on: an exception escaping a slot or callback stops the takeover and writes tier 0
    sys.excepthook = TakeoverFaults(host, acquisition, gateway).excepthook
    return host


def _idle_timer() -> QTimer:
    """Lets the interpreter return to Python every SIGNAL_POLL_MILLISECONDS, so signal handlers run (16_ 1.5)."""
    idle = QTimer()
    idle.timeout.connect(lambda: None)
    idle.start(SIGNAL_POLL_MILLISECONDS)
    return idle


def _install_excepthook() -> None:
    """D-225 item 1: PySide6 hands an exception that escapes a slot to sys.excepthook and the event loop goes on
    (PyQt5 aborted the process). The windowed exe has no stderr, so the traceback is written to service.log, as
    V1.0.3's desktop program logs it (slot_errors); KeyboardInterrupt keeps Python's own handling. This first hook
    covers the setup; once the takeover is assembled, acquisition_host.faults.TakeoverFaults replaces it (log, tell
    the page, stop the takeover and write tier 0)."""

    def hook(kind: type[BaseException], error: BaseException, trace: TracebackType | None) -> None:
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, error, trace)
            return
        LOG.critical(UNCAUGHT, exc_info=(kind, error, trace))

    sys.excepthook = hook


def _on_pyside6() -> bool:
    """par_app.acquisition_host chose PySide6 on import, unless a binding was already fixed (internal notes)."""
    try:
        require(PYSIDE6)
    except BindingError as error:
        print(f"PAR alpha service: {error}", file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not _on_pyside6():
        return EXIT_WRONG_QT_BINDING
    # the shell is taken hold of first, before the seconds of setup below (review N3 of PR #56)
    parent = open_parent(args.parent_pid, SystemClock()) if args.parent_pid is not None else None
    paths = AlphaPaths((args.data_dir or default_data_dir()).resolve())
    marker = v103_program_marker(paths.data_dir)
    if marker is not None:  # before anything is created there (review Q2)
        print(REFUSED_DATA_DIR.format(folder=paths.data_dir, marker=marker), file=sys.stderr)
        return EXIT_REFUSED_DATA_DIR
    paths.ensure()
    configure_logging(paths)
    _install_excepthook()
    web_dir = args.web_dir.resolve() if args.web_dir else default_web_dir()
    os.chdir(paths.data_dir)  # 16_ 3.1: as V1.0.3's os.chdir(root); every path used is absolute anyway
    app = QCoreApplication.instance() or QCoreApplication([sys.argv[0]])
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((LOOPBACK, args.port))
    listener.listen()
    bound_host, port = listener.getsockname()
    host_name = f"{bound_host}:{port}"
    token = secrets.token_urlsafe(TOKEN_BYTES)
    context = _service_context(paths, args.first_run_tier)
    gateway = MainThreadGateway()
    host = _takeover(paths, context, gateway)
    runners: list[ServiceRunner] = []
    fastapi_app = create_app(
        context, token=token, allowed_hosts=(host_name,), web_dir=web_dir, request_stop=_stop_request(gateway, runners)
    )
    server = uvicorn.Server(uvicorn.Config(fastapi_app, log_config=None, lifespan="off", access_log=False))
    runner = ServiceRunner(app, context, host, gateway, server)
    runners.append(runner)
    payload = _service_payload(host_name, port, token, context, paths)
    _install_signals(runner)
    idle = _idle_timer()
    runner.serve(listener)
    write_service_file(paths.service_file, payload)
    LOG.info(
        "PAR local service %s (tier %d) on http://%s (data %s)",
        ALPHA_VERSION,
        context.acquisition.tier(),
        host_name,
        paths.data_dir,
    )
    QTimer.singleShot(0, lambda: _auto_start(context))  # on the main thread once the Qt loop runs (issue #92)
    if args.stop_on_stdin_eof:
        _watch_stdin(runner)
    if args.parent_pid is not None:  # a crashed shell: the same graceful shutdown, then a backstop (D-223)
        watch_parent(args.parent_pid, lambda: _post(gateway, runner.request_shutdown), context.clock, parent)
    try:
        app.exec()
    finally:
        if not runner.finished.is_set():
            runner.request_shutdown()
        idle.stop()
        remove_service_file(paths.service_file, token)
        listener.close()
    _log_threads_left()
    return 0


def _auto_start(context: ServiceContext) -> None:
    """Issue #92: with tier 1 on, start acquiring as V1.0.3 does when opened; a refusal stays on the status."""
    if context.acquisition.auto_start():
        LOG.info("acquisition started automatically (tier %d)", context.acquisition.tier())


def _service_context(paths: AlphaPaths, first_run_tier: int) -> ServiceContext:
    """The service's context; without a settings file the tier is `first_run_tier`: 1 for the product, so a new
    installation acquires at once (issue #119, owner 2026-10-27); tests and the self-test start from 0."""
    context = ServiceContext(paths, SystemClock())
    context.acquisition.tiers.default = first_run_tier
    return context


def _service_payload(
    host_name: str, port: int, token: str, context: ServiceContext, paths: AlphaPaths
) -> dict[str, object]:
    """service.json: address, token, this process's pid and the shell's launch id (the shell finds its service by
    the launch id, not by the pid: a Windows venv launcher sits in between, issue #66)."""
    payload: dict[str, object] = {"base_url": f"http://{host_name}", "port": port, "token": token, "pid": os.getpid()}
    payload |= {"version": ALPHA_VERSION, "started_at": context.started_at, "data_dir": str(paths.data_dir)}
    return payload | {"launch_id": launch_id()}


def _stop_request(gateway: MainThreadGateway, runners: list[ServiceRunner]) -> Callable[[], None]:
    """What POST /api/v0/shutdown calls (API-19): the shutdown, queued on the main thread (never run inside the HTTP
    thread or another main-thread call)."""

    def request_stop() -> None:
        LOG.info("stop requested: shutdown requested by the shell")
        gateway.post(runners[0].request_shutdown)

    return request_stop


def _post(gateway: MainThreadGateway, call: Callable[[], None]) -> None:
    """Queue `call` on the main thread without waiting for it (the result is not needed)."""
    gateway.post(call)


def _log_threads_left() -> None:
    left = sorted(thread.name for thread in threading.enumerate() if not thread.daemon and thread.name != "MainThread")
    LOG.info("%s non-daemon threads left: %s", SERVICE_STOPPED, ", ".join(left) or "none")


if __name__ == "__main__":
    raise SystemExit(main())
