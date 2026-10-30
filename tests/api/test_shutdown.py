"""POST /api/v0/shutdown: the shell's stop request to its service child (review of PR #50, major 1).

A windowed exe (PyInstaller console=False) has no usable stdin on Windows, so closing the pipe cannot be the only
stop request. The shell asks over HTTP with the startup token; a page (any request carrying an Origin header) may
not stop the service. The real child without stdin is exercised in tests/api/test_service_entry.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from par_app.api.app import create_app
from par_app.api.context import ServiceContext

from .conftest import AUTH, HOST, TOKEN

pytestmark = pytest.mark.unit
SHUTDOWN = "/api/v0/shutdown"


def test_shutdown_needs_the_token_refuses_pages_and_asks_the_server_to_stop(context: ServiceContext) -> None:
    stops: list[str] = []
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,), request_stop=lambda: stops.append("stop"))
    with TestClient(app, base_url=f"http://{HOST}") as client:
        assert client.post(SHUTDOWN).status_code == 401
        from_page = client.post(SHUTDOWN, headers=AUTH | {"Origin": f"http://{HOST}"})
        assert from_page.status_code == 403
        assert from_page.json()["error"]["code"] == "forbidden_origin"
        assert client.get(SHUTDOWN, headers=AUTH).status_code == 405
        assert stops == []
        answer = client.post(SHUTDOWN, headers=AUTH)
        assert answer.status_code == 202 and answer.json() == {"stopping": True}
        assert stops == ["stop"]


def test_shutdown_is_not_found_when_the_service_has_no_stop_hook(client: TestClient) -> None:
    answer = client.post(SHUTDOWN)
    assert answer.status_code == 404 and answer.json()["error"]["code"] == "not_found"
