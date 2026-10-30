"""python -m par_shell [--data-dir DIR] [--web-dir DIR] [--browser] [--smoke SECONDS]

Start the local service, open the window, stop the service when the window closes (13_ 3.1). --browser opens the
page in the default browser instead of a window (the WebView2 fallback, appendix C); --smoke closes the window by
itself once the page has rendered and exits 0 only if it did (local check, not a test of the page itself).
"""

from __future__ import annotations

import argparse
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from . import ALPHA_NOTICE, SHELL_TITLE
from .instance import InstanceLock
from .service import ServiceError, ServiceProcess, default_data_dir
from .webview2 import missing_runtime_message, webview2_available
from .window import open_in_browser, open_window

MB_YESNO = 0x04
MB_ICONWARNING = 0x30
MB_OK = 0x00
IDYES = 6
SMOKE_NO_RUNTIME = 3
"""--smoke without the WebView2 runtime: exit at once, no dialog (build_alpha.ps1 runs the smoke unattended)."""
ALREADY_RUNNING = "PAR 光谱仪 2.0 已在运行，请切换到已打开的窗口。"


def ask(text: str, yes_no: bool) -> bool:
    """A Windows message box (no window toolkit is needed for it); elsewhere the text goes to stderr."""
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        style = (MB_YESNO if yes_no else MB_OK) | MB_ICONWARNING
        return int(ctypes.windll.user32.MessageBoxW(None, text, f"{SHELL_TITLE} {ALPHA_NOTICE}", style)) == IDYES
    print(text, file=sys.stderr)
    return False


def wait_for_browser_session(confirm: Callable[[str, bool], bool] = ask) -> None:
    """Keep the service up while the browser shows the page: a message box on Windows, Ctrl+C elsewhere."""
    if sys.platform == "win32":
        confirm("界面已在浏览器中打开。关闭此对话框即停止本机服务。", False)
        return
    print("界面已在浏览器中打开；按 Ctrl+C 停止本机服务。", file=sys.stderr)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m par_shell", description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=None, help="alpha data directory (default as the service)")
    parser.add_argument("--web-dir", type=Path, default=None, help="built front end (default: the service's)")
    parser.add_argument("--browser", action="store_true", help="open the default browser instead of a window")
    parser.add_argument("--smoke", type=float, default=None, metavar="SECONDS", help="close once rendered")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    program_dir = Path(sys.executable).resolve().parent
    use_browser = args.browser
    if not use_browser and not webview2_available():
        if args.smoke is not None:
            print("--smoke: the WebView2 runtime is not installed", file=sys.stderr)
            return SMOKE_NO_RUNTIME
        if not ask(missing_runtime_message(program_dir), True):
            return 1
        use_browser = True
    data_dir = (args.data_dir or default_data_dir()).resolve()
    with InstanceLock(data_dir) as lock:
        if not lock.acquire():
            ask(ALREADY_RUNNING, False)
            return 1
        return _run(data_dir, args.web_dir, use_browser, args.smoke)


def _run(data_dir: Path, web_dir: Path | None, use_browser: bool, smoke: float | None) -> int:
    with ServiceProcess(data_dir, web_dir) as service:
        try:
            info = service.start()
        except ServiceError as error:
            ask(str(error), False)
            return 1
        if use_browser:
            open_in_browser(info)
            wait_for_browser_session()
            return 0
        return 0 if open_window(info, smoke_seconds=smoke) else 1


if __name__ == "__main__":
    raise SystemExit(main())
