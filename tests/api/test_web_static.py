"""The service serves the built front end next to /api/v0 (par_app/api/static.py).

Static files need no token but keep the Host/Origin check and carry a Content-Security-Policy that allows only
the service's own origin; every API path except health still needs the token. A stand-in build in tmp_path is
used here; tests/api/test_web_smoke.py runs the real web/dist build.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from par_app.api import static
from par_app.api.__main__ import parse_args
from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.api.routes import API_PREFIX

from .conftest import AUTH, HOST, TOKEN

pytestmark = pytest.mark.unit
INDEX = '<!doctype html><html><head><script type="module" src="/assets/app.js"></script></head></html>'


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text(INDEX, encoding="utf-8")
    (directory / "assets" / "app.js").write_text("console.log('page')", encoding="utf-8")
    return directory


@pytest.fixture
def browser(context: ServiceContext, web_dir: Path) -> Iterator[TestClient]:
    """A client without the token, like a browser loading the page."""
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,), web_dir=web_dir)
    with TestClient(app, base_url=f"http://{HOST}") as client:
        yield client


def test_the_page_and_its_assets_need_no_token(browser: TestClient) -> None:
    page = browser.get("/")
    assert page.status_code == 200
    assert page.text == INDEX
    assert page.headers["content-type"].startswith("text/html")
    asset = browser.get("/assets/app.js")
    assert asset.status_code == 200
    assert "javascript" in asset.headers["content-type"]


def test_static_responses_allow_only_the_own_origin(browser: TestClient) -> None:
    headers = browser.get("/").headers
    policy = headers["content-security-policy"]
    for directive in ("default-src 'self'", "script-src 'self'", "connect-src 'self'", "frame-ancestors 'none'"):
        assert directive in policy
    assert "unsafe-eval" not in policy
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"


def test_api_paths_still_need_the_token_and_health_does_not(browser: TestClient) -> None:
    assert browser.get("/api/v0/devices").status_code == 401
    assert browser.get("/api/v0/unknown").status_code == 401
    assert browser.get("/api/v0").status_code == 401
    assert browser.get("/api/v0/health").status_code == 200
    assert browser.get("/api/v0/devices", headers=AUTH).status_code == 200


def test_host_and_origin_checks_cover_static_files(browser: TestClient) -> None:
    assert browser.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert browser.get("/", headers={"Origin": "http://evil.example"}).status_code == 403


def test_unknown_files_and_traversal_are_not_found(browser: TestClient, web_dir: Path) -> None:
    (web_dir.parent / "secret.txt").write_text("outside", encoding="utf-8")
    assert browser.get("/missing.js").status_code == 404
    response = browser.get("/../secret.txt")
    assert response.status_code == 404
    assert "outside" not in response.text


def test_without_a_build_only_the_api_is_served(anonymous: TestClient) -> None:
    assert anonymous.get("/").status_code == 404
    assert anonymous.get("/api/v0/health").status_code == 200


def test_web_dir_is_found_from_env_bundle_or_repository(
    tmp_path: Path, web_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(static.WEB_DIR_ENV, str(web_dir))
    assert static.default_web_dir() == web_dir
    monkeypatch.setenv(static.WEB_DIR_ENV, str(tmp_path / "not-built"))
    assert static.default_web_dir() is None
    monkeypatch.delenv(static.WEB_DIR_ENV)
    bundle = tmp_path / "bundle"
    (bundle / "web").mkdir(parents=True)
    (bundle / "web" / "index.html").write_text(INDEX, encoding="utf-8")
    monkeypatch.setattr("sys._MEIPASS", str(bundle), raising=False)
    assert static.default_web_dir() == bundle / "web"


def test_an_explicit_web_dir_must_hold_a_build(tmp_path: Path, web_dir: Path) -> None:
    assert parse_args(["--web-dir", str(web_dir)]).web_dir == web_dir
    with pytest.raises(SystemExit):
        parse_args(["--web-dir", str(tmp_path / "empty")])


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_outside_the_api_prefix_only_reads_go_without_the_token(browser: TestClient, method: str) -> None:
    """Review N-2: a route added later outside /api/v0 (e.g. contract 1.1 POST /session) is not silently open."""
    assert browser.request(method, "/").status_code == 401
    assert browser.request(method, "/session").status_code == 401
    assert browser.request(method, "/", headers=AUTH).status_code == 405
    assert browser.head("/").status_code == 200


def _route_prefix(route: object) -> str:
    """The path (or, for an included router, its prefix; FastAPI 0.14x includes routers lazily) of an app route."""
    included = getattr(route, "original_router", None)
    return str(included.prefix) if included is not None else str(getattr(route, "path", ""))


def test_every_route_but_the_static_mount_is_under_the_api_prefix(context: ServiceContext, web_dir: Path) -> None:
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,), web_dir=web_dir)
    others = [route for route in app.routes if not (isinstance(route, Mount) and route.name == "web")]
    assert len(others) == len(app.routes) - 1
    outside = [_route_prefix(route) for route in others]
    assert [prefix for prefix in outside if prefix != API_PREFIX and not prefix.startswith(API_PREFIX + "/")] == []
    assert all(path.startswith(API_PREFIX + "/") for path in app.openapi()["paths"])
