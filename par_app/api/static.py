"""Serves the built web front end (web/dist) next to /api/v0 (13_ section 3.1: one service, one origin).

* The build output is not committed; it is produced by `npm run build` in web/ and bundled when packaging. The
  service finds it at --web-dir, $PAR_WEB_DIR, the PyInstaller bundle (<_MEIPASS>/web) or <repo>/web/dist, in that
  order. Without a build, only the API is served and "/" answers 404.
* Static files need no token (they carry no data); every /api/v0 path except health still does (security.py).
  The page learns the token from the URL fragment the shell opens, which never reaches the server.
* Every static response carries a Content-Security-Policy that allows only this origin: the page can load no
  script, style, font or image from elsewhere and can connect nowhere else (offline alpha, no external requests).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

WEB_DIR_ENV = "PAR_WEB_DIR"
INDEX = "index.html"
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",  # ECharts and Vue set inline style attributes
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    )
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-cache",
}


def _built(directory: Path) -> Path | None:
    return directory if (directory / INDEX).is_file() else None


def default_web_dir() -> Path | None:
    """$PAR_WEB_DIR, else the PyInstaller bundle's web/, else <repo>/web/dist; None when none holds index.html."""
    override = os.environ.get(WEB_DIR_ENV)
    if override:
        return _built(Path(override))
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return _built(Path(bundle) / "web")
    return _built(Path(__file__).resolve().parents[2] / "web" / "dist")


class WebAssets(StaticFiles):
    """StaticFiles with index.html at "/" and the security headers above on every response."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, html=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers.update(SECURITY_HEADERS)
        return response
