"""End-to-end smoke of the built front end on the real service (task: service + build output, httpx only).

Starts the service (`python -m par_app.service_main --web-dir web/dist`) as a subprocess on 127.0.0.1 with a
synthetic V1.0.x-format database registered as the one device of its own configuration (issue #82: the pages read
only the alpha's own device databases), raises the tier to 1 through the API (so it does not start acquiring by
itself, #92) and walks what the history and DLI pages load: index.html and its assets (same origin only), then the API
calls the pages make, with the token the shell puts in the URL fragment. Needs `npm run build` in web/ first (build
output is not committed); skipped without it, except when $PAR_REQUIRE_WEB_BUILD=1 (CI's web job), where a missing
build fails the test. A real browser run is not part of the test suite (see
tools/ui_v2_dev.md for the headless-browser screenshot).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from tools.ui_v2_e2e_devices import register

from .conftest import failed_record, record, v1_database

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
START_TIMEOUT_SECONDS = 30.0
REQUIRE_BUILD_ENV = "PAR_REQUIRE_WEB_BUILD"
ASSET = re.compile(r'(?:src|href)="([^"]+)"')


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """The device's database, written before the service starts."""
    path = v1_database(
        tmp_path / "alpha" / "data" / "devices" / "p1.sqlite3",
        [record("2026-10-17T08:00:00.000"), failed_record("2026-10-18T08:01:00.000")],
    )
    register(tmp_path / "alpha", [("东区", path)])
    return path


@pytest.fixture
def served(tmp_path: Path, source: Path) -> Iterator[tuple[str, str]]:
    if not (WEB_DIST / "index.html").is_file():
        if os.environ.get(REQUIRE_BUILD_ENV) == "1":
            pytest.fail(f"web/dist is not built but ${REQUIRE_BUILD_ENV}=1")
        pytest.skip("web/dist is not built: run `npm ci && npm run build` in web/")
    data_dir = tmp_path / "alpha"
    process = subprocess.Popen(
        [
            sys.executable,
            *("-m", "par_app.service_main", "--port", "0", "--data-dir", str(data_dir), "--web-dir", str(WEB_DIST)),
            *("--first-run-tier", "0"),  # the state this test begins from (issue #119 made 1 the product default)
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    info: dict[str, Any] | None = None
    while time.monotonic() < deadline and process.poll() is None:
        try:
            info = json.loads((data_dir / "service.json").read_text(encoding="utf-8"))
            httpx.get(f"{info['base_url']}/api/v0/health", timeout=1.0)
            break
        except (OSError, ValueError, httpx.HTTPError):
            info = None
            time.sleep(0.05)
    if info is None:
        process.kill()
        pytest.fail(f"service did not start: {process.communicate()[1].decode(errors='replace')}")
    api = {"X-PAR-Token": str(info["token"])}
    issued = httpx.post(f"{info['base_url']}/api/v0/tier/confirmations", json={"tier": 1}, headers=api)
    raised = httpx.put(
        f"{info['base_url']}/api/v0/tier",
        json={"tier": 1, "confirmation_id": issued.json()["confirmation_id"]},
        headers=api,
    )
    assert raised.status_code == 200, raised.text
    try:
        yield str(info["base_url"]), str(info["token"])
    finally:
        process.terminate()
        process.wait(10)


def test_page_assets_history_dli_and_calculation_api_on_the_running_service(
    served: tuple[str, str], source: Path
) -> None:
    base_url, token = served
    with httpx.Client(base_url=base_url, timeout=5.0) as browser:
        page = browser.get("/")
        assert page.status_code == 200
        assert "connect-src 'self'" in page.headers["content-security-policy"]
        assets = ASSET.findall(page.text)
        assert assets, page.text
        for asset in assets:
            assert asset.startswith("/") and not asset.startswith("//"), f"not same-origin: {asset}"
            response = browser.get(asset)
            assert response.status_code == 200, asset
        for name in ("NotoSansSC.ttf", "OFL.txt", "JetBrainsMono.ttf", "JetBrainsMono-OFL.txt"):
            assert browser.get(f"/fonts/{name}").status_code == 200, name  # UI-001: bundled fonts, no online font
        assert browser.get("/api/v0/devices").status_code == 401  # the page alone carries no data

        api = {"X-PAR-Token": token}
        before = _content(source)
        devices = browser.get("/api/v0/devices", headers=api).json()
        assert [d["key"] for d in devices["items"] if d["configured"]] == ["p1"]
        probe = browser.get(
            "/api/v0/devices/p1/acquisitions",
            params={"start": "0001-01-01T00:00:00.000", "end": "9999-12-31T23:59:59.999"},
            headers=api,
        ).json()
        assert [item["success"] for item in probe["items"]] == [False, True]
        detail = browser.get(f"/api/v0/devices/p1/acquisitions/{probe['items'][1]['id']}", headers=api).json()
        assert len(detail["spectrum"]["values"]) == 701
        assert sum(len(group["items"]) for group in detail["groups"]) == 54
        dli = browser.get("/api/v0/devices/p1/dli", headers=api)
        assert dli.status_code == 200, dli.text
        body = dli.json()
        assert [metric["key"] for metric in body["metrics"]] == [
            "ppfd",
            "mccree_ypfd",
            "chlorophyll_a_ypfd",
            "chlorophyll_b_ypfd",
        ]
        assert body["period"]["text"].startswith("积分周期：")
        past = browser.get("/api/v0/devices/p1/dli", params={"date": "2026-10-17"}, headers=api)
        assert past.status_code == 200 and past.json()["period"]["current"] is False
        assert browser.get("/api/v0/devices/p1/dli").status_code == 401
        after = _content(source)  # the DLI's only write: the enable time, as V1.0.3 (D-228 A)
        assert after["dli_enabled_at"] and not before["dli_enabled_at"]
        assert {**after, "dli_enabled_at": None} == {**before, "dli_enabled_at": None}
        settled = source.read_bytes()
        _check_calculation(browser, api)
        assert source.read_bytes() == settled  # exports go to the alpha's own output folder only (D-207)


def _content(path: Path) -> dict[str, Any]:
    """The device database's schema, records and settings, with the DLI enable time apart."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
        settings = con.execute("SELECT key, value_json, updated_at FROM app_settings ORDER BY key").fetchall()
        return {
            "schema": con.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall(),
            "acquisitions": con.execute("SELECT * FROM acquisitions ORDER BY id").fetchall(),
            "spectra": con.execute("SELECT * FROM spectra ORDER BY rowid").fetchall(),
            "settings": [row for row in settings if row[0] != "dli_enabled_at"],
            "dli_enabled_at": [row for row in settings if row[0] == "dli_enabled_at"],
        }


def _check_calculation(browser: httpx.Client, api: dict[str, str]) -> None:
    """光谱计算 on the running service: sources, candidates, a ratio and an export in both formats (API-11..14, 24)."""
    sources = browser.get("/api/v0/operation-sources", headers=api).json()
    assert (sources["initial_a"], sources["initial_b"]) == ("p1", "p1")
    candidates = browser.get("/api/v0/operation-sources/p1/spectra", headers=api).json()["items"]
    ref = {"source": "p1", "id": candidates[0]["id"]}
    computed = browser.post("/api/v0/operations/compute", json={"a": ref, "b": ref, "operation": "divide"}, headers=api)
    assert computed.status_code == 200, computed.text
    assert set(computed.json()["result"]["values"]) == {1.0}
    exported = browser.post(
        "/api/v0/operations/export",
        json={"a": ref, "b": ref, "operation": "divide", "formats": ["csv", "xlsx"]},
        headers=api,
    )
    assert exported.status_code == 201, exported.text
    assert len(exported.json()["files"]) == 2
