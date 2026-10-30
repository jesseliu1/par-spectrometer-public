"""Access guard of the local service: Host/Origin check and the one-time startup token (13_ 3.2, contract 1.1).

* Host must be one of `allowed_hosts` (the service passes exactly "127.0.0.1:<port>"), and an Origin header, when
  present, must be the same origin; otherwise 403 forbidden_origin (DNS rebinding, other web pages).
* Every path under the API prefix except the open ones (health) needs the token generated at startup, sent as
  `Authorization: Bearer <token>` or `X-PAR-Token: <token>`; otherwise 401 unauthenticated. Outside the prefix only
  GET and HEAD of the static front end (static.py, no data) go without the token; any other method there needs it
  too, so a route added later outside the prefix is not silently open (review N-2). Host/Origin always apply.
The cookie session of contract 1.1 (`POST /session`) is left to the shell PR; until then the token is the session.
* Only HTTP requests are checked and served. A websocket is closed (1008 policy violation) before the app sees it:
  there is no websocket route yet, and the PR that adds one (the event stream, API-17) extends the guard first
  (review N-6). Lifespan events pass through.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from http import HTTPStatus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

TOKEN_HEADER = "x-par-token"
POLICY_VIOLATION = 1008
"""WebSocket close code for a connection the server refuses by policy (RFC 6455 7.4.1)."""
BEARER_PREFIX = "bearer "
READ_METHODS = frozenset({"GET", "HEAD"})


def error_response(
    status: HTTPStatus, code: str, message: str, retryable: bool, detail: str | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "retryable": retryable, "detail": detail}}
    return JSONResponse(body, status_code=status)


class AccessGuard:
    def __init__(
        self,
        app: ASGIApp,
        token: str,
        allowed_hosts: Iterable[str],
        open_paths: Iterable[str],
        protected_prefix: str = "/",
    ) -> None:
        if not token:
            raise ValueError("the access token must not be empty")
        self.app = app
        self.token = token.encode()
        self.allowed_hosts = frozenset(allowed_hosts)
        self.allowed_origins = frozenset(f"http://{host}" for host in self.allowed_hosts)
        self.open_paths = frozenset(open_paths)
        self.protected_prefix = protected_prefix.rstrip("/")  # "/" (default) protects every path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": POLICY_VIOLATION})
            return
        headers = {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in scope["headers"]}
        response = self._reject(headers, str(scope["path"]), str(scope["method"]))
        if response is None:
            await self.app(scope, receive, send)
        else:
            await response(scope, receive, send)

    def _reject(self, headers: dict[str, str], path: str, method: str) -> JSONResponse | None:
        if headers.get("host") not in self.allowed_hosts:
            return error_response(
                HTTPStatus.FORBIDDEN, "forbidden_origin", "请求的 Host 不是本服务地址", False, headers.get("host")
            )
        origin = headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            return error_response(HTTPStatus.FORBIDDEN, "forbidden_origin", "跨站请求被拒绝", False, origin)
        if path in self.open_paths or not self._protected(path, method) or self._token_ok(headers):
            return None
        return error_response(HTTPStatus.UNAUTHORIZED, "unauthenticated", "缺少或错误的访问令牌，请重新启动程序", False)

    def _protected(self, path: str, method: str) -> bool:
        under_prefix = path == self.protected_prefix or path.startswith(self.protected_prefix + "/")
        return under_prefix or method not in READ_METHODS

    def _token_ok(self, headers: dict[str, str]) -> bool:
        authorization = headers.get("authorization", "")
        given = authorization[len(BEARER_PREFIX) :] if authorization.lower().startswith(BEARER_PREFIX) else None
        given = given if given is not None else headers.get(TOKEN_HEADER)
        return given is not None and hmac.compare_digest(given.strip().encode(), self.token)
