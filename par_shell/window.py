"""The pywebview window (13_ 3.1). pywebview is imported only here, so the rest of the shell and its tests run
without it.

The page gets the token through the URL fragment (#token=…): the fragment is never sent to the server, and the
page removes it from the address at once (web/src/api/client.ts). A pywebview window has no address bar.
"""

from __future__ import annotations

import threading
import webbrowser
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from . import ALPHA_NOTICE, SHELL_TITLE
from .service import ServiceInfo

WINDOW_SIZE = (1600, 960)
MIN_SIZE = (1280, 800)
SMOKE_READY_SCRIPT = "document.querySelectorAll('nav.devices button').length"
"""Number of device buttons in the top bar: 4 once the page has fetched /api/v0/devices with its token. Run with
run_js (no eval wrapper): the page's Content-Security-Policy forbids eval, which evaluate_js relies on."""
DEVICE_SLOTS = 4


def page_url(info: ServiceInfo) -> str:
    return f"{info.base_url}/#token={quote(info.token, safe='')}"


def window_title(version: str) -> str:
    """S-2, issue #119: the product name and "V2.0 试用版"; the build version is not shown to customers here."""
    del version  # kept for the callers; the title no longer depends on it
    return f"{SHELL_TITLE} {ALPHA_NOTICE}"


def open_window(info: ServiceInfo, smoke_seconds: float | None = None, webview: Any = None) -> bool:  # noqa: ANN401
    """Show the window and block until it is closed. With `smoke_seconds`, close it by itself once the page has
    rendered its top bar and status line (or the time is up) and return whether it rendered."""
    if webview is None:
        import webview  # noqa: PLC0415 (optional at import time)
    window = webview.create_window(
        window_title(info.version), page_url(info), width=WINDOW_SIZE[0], height=WINDOW_SIZE[1], min_size=MIN_SIZE
    )
    rendered = threading.Event()
    if smoke_seconds is None:
        webview.start()
        return True
    webview.start(_smoke, (window, smoke_seconds, rendered))
    return rendered.is_set()


def _smoke(window: Any, seconds: float, rendered: threading.Event, wait: Callable[[float], bool] | None = None) -> None:  # noqa: ANN401
    """Runs in pywebview's worker thread: poll until the page rendered, then close the window."""
    pause = wait or threading.Event().wait
    try:
        window.events.loaded.wait(seconds)
        for _ in range(int(seconds * 10)):
            if _count(window.run_js(SMOKE_READY_SCRIPT)) >= DEVICE_SLOTS:
                rendered.set()
                break
            pause(0.1)
    finally:
        window.destroy()


def _count(result: object) -> int:
    """run_js gives a number (WebKit: 4.0) or its JSON text (WebView2: "4"); anything else counts as 0."""
    try:
        return int(float(str(result)))
    except ValueError:
        return 0


def open_in_browser(info: ServiceInfo, opener: Callable[[str], bool] = webbrowser.open) -> bool:
    """WebView2 fallback (appendix C): the default browser on the same local page."""
    return opener(page_url(info))
