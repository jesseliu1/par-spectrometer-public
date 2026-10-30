"""Every resource the built page loads must exist and be non-empty (review of PR #50, major 2).

index.html with its fonts but without its script or stylesheet is a blank or unstyled window. Starting from the page,
this follows <script src>, <link href> (stylesheet, modulepreload, preload, icon), url(...) in stylesheets and the
relative chunk imports of scripts, and asks `fetch` for each one. The self-test fetches over HTTP from the running
service (self_test.py); the packaging check reads the files in _internal/web (tools/alpha_release.py). Only paths on
the same site are followed: absolute URLs, data: and fragments are not resources of the package.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable
from html.parser import HTMLParser

LINK_RELS = frozenset({"stylesheet", "modulepreload", "preload", "icon"})
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")\s]+)['"]?\s*\)""")
JS_IMPORT = re.compile(r"""["'`]((?:\.{1,2}/|/assets/)[^"'`\s]+\.(?:m?js|css))["'`]""")
"""Chunk imports Vite writes into a script ("./chunk-x.js", "/assets/chunk-x.js")."""
EXTERNAL = ("http:", "https:", "data:", "blob:", "//", "#", "mailto:")


class WebAssetError(ValueError):
    """A resource the page names is missing or empty, or the page names no script."""


class _PageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        elif tag == "link" and values.get("href") and LINK_RELS & set(values.get("rel", "").lower().split()):
            self.links.append(values["href"])


def site_path(base: str, reference: str) -> str | None:
    """`reference` seen in the file at site path `base`, as a site path ("/assets/x.js"), or None if external."""
    reference = reference.split("#", 1)[0].split("?", 1)[0]
    if not reference or reference.lower().startswith(EXTERNAL):
        return None
    if not reference.startswith("/"):
        reference = posixpath.join(posixpath.dirname(base), reference)
    return posixpath.normpath(reference)


def nested(path: str, body: bytes) -> list[str]:
    """References inside a stylesheet or script, as site paths."""
    text = body.decode("utf-8", errors="replace")
    if path.endswith(".css"):
        found = CSS_URL.findall(text)
    elif path.endswith((".js", ".mjs")):
        found = JS_IMPORT.findall(text)
    else:
        return []
    return [item for item in (site_path(path, ref) for ref in found) if item is not None]


def check_page(index_html: str, fetch: Callable[[str], bytes]) -> list[str]:
    """Fetch every resource `index_html` (served at "/") loads, transitively; returns their site paths in order.
    `fetch(path)` returns the body or raises WebAssetError naming the path (missing, wrong status)."""
    page = _PageLinks()
    page.feed(index_html)
    if not page.scripts:
        raise WebAssetError("index.html names no script: the page would not start")
    pending = [item for item in (site_path("/", ref) for ref in page.scripts + page.links) if item is not None]
    loaded: list[str] = []
    while pending:
        path = pending.pop(0)
        if path in loaded:
            continue
        body = fetch(path)
        if not body:
            raise WebAssetError(f"{path} is empty")
        loaded.append(path)
        pending += nested(path, body)
    return loaded
