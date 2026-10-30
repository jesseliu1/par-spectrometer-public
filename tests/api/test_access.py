"""Access guard of the local service: token, Host and Origin (13_ 3.2, api-contract-v0 1.1 and 1.3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import HOST, TOKEN, error_of

pytestmark = pytest.mark.unit

PROTECTED = [
    ("GET", "/api/v0/snapshots"),
    ("POST", "/api/v0/snapshots"),
    ("GET", "/api/v0/devices"),
    ("GET", "/api/v0/devices/p1/acquisitions?start=2026-10-01T00:00:00.000&end=2026-10-02T00:00:00.000"),
    ("GET", "/api/v0/devices/p1/acquisitions/1"),
    ("GET", "/api/v0/devices/p1/acquisitions/1/spectrum"),
    ("GET", "/api/v0/reference-curves"),
    ("GET", "/api/v0/openapi.json"),
]


def test_health_needs_no_token(anonymous: TestClient) -> None:
    response = anonymous.get("/api/v0/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "2.0.0-alpha.9"
    assert body["tier"] == 0
    assert body["started_at"] == "2026-10-18T09:30:00.000"


@pytest.mark.parametrize(("method", "url"), PROTECTED)
def test_every_other_route_needs_the_token(anonymous: TestClient, method: str, url: str) -> None:
    response = anonymous.request(method, url, json={})
    assert response.status_code == 401
    assert error_of(response) == {
        "code": "unauthenticated",
        "message": "缺少或错误的访问令牌，请重新启动程序",
        "retryable": False,
        "detail": None,
    }


@pytest.mark.parametrize(
    "headers",
    [{"X-PAR-Token": "wrong"}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}, {"X-PAR-Token": ""}],
)
def test_a_wrong_token_is_refused(anonymous: TestClient, headers: dict[str, str]) -> None:
    assert anonymous.get("/api/v0/devices", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "headers", [{"X-PAR-Token": TOKEN}, {"Authorization": f"Bearer {TOKEN}"}, {"authorization": f"bearer {TOKEN}"}]
)
def test_bearer_and_header_tokens_are_accepted(anonymous: TestClient, headers: dict[str, str]) -> None:
    assert anonymous.get("/api/v0/devices", headers=headers).status_code == 200


@pytest.mark.parametrize("host", ["evil.example:80", "localhost", "127.0.0.1:1"])
def test_a_foreign_host_is_refused_even_with_the_token(client: TestClient, host: str) -> None:
    for url in ("/api/v0/health", "/api/v0/devices"):
        response = client.get(url, headers={"Host": host})
        assert response.status_code == 403
        assert error_of(response)["code"] == "forbidden_origin"


def test_a_cross_site_origin_is_refused_and_the_same_origin_allowed(client: TestClient) -> None:
    refused = client.get("/api/v0/devices", headers={"Origin": "http://evil.example"})
    assert refused.status_code == 403
    assert error_of(refused)["code"] == "forbidden_origin"
    assert client.get("/api/v0/devices", headers={"Origin": f"http://{HOST}"}).status_code == 200


def test_interactive_docs_are_not_served(client: TestClient) -> None:
    """Swagger UI and ReDoc load scripts from a CDN; the offline alpha does not serve them."""
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_websocket_connections_are_refused() -> None:
    """Review N-6: only HTTP passes the guard's checks; a websocket is closed before the app sees it, even with the
    token (there is no websocket route yet; one that is added must extend the guard first)."""
    from starlette.testclient import TestClient as StarletteClient
    from starlette.types import Receive, Scope, Send
    from starlette.websockets import WebSocket, WebSocketDisconnect

    from par_app.api.security import AccessGuard

    reached: list[str] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        reached.append(scope["type"])
        if scope["type"] == "websocket":
            websocket = WebSocket(scope, receive, send)
            await websocket.accept()
            await websocket.send_text("hello")
            await websocket.close()

    guarded = AccessGuard(app, token=TOKEN, allowed_hosts=(HOST,), open_paths=())
    client = StarletteClient(guarded, base_url=f"http://{HOST}")  # no `with`: the probe app has no lifespan
    for headers in ({}, {"X-PAR-Token": TOKEN}):
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/ws", headers=headers) as websocket:
                websocket.receive_text()
        assert closed.value.code == 1008
    assert "websocket" not in reached
