"""FastAPI application factory and error mapping of the local service (api-contract-v0 section 1.3, R-1-5).

Errors keep one shape, {"error": {code, message, retryable, detail}}. "No records" is 200 with an empty list; a
database that cannot be read is 503 database_unavailable and never an empty list. Unexpected exceptions are logged,
reported to the page (GET /tier `fault`, `service_error` event; D-225 item 1) and answered with 500 internal; the
process keeps running.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from ..application import ALPHA_VERSION
from ..application.errors import (
    ApplicationError,
    Busy,
    ConfigUnavailable,
    ConfirmationRequired,
    DatabaseUnavailable,
    DeviceNotFound,
    FeatureDisabled,
    InstanceLocked,
    InvalidArgument,
    NotRunning,
    RecordNotFound,
    SnapshotChanged,
)
from ..application.maintenance import Halted, NoSession, PreconditionFailed
from . import (
    acquisition_routes,
    maintenance_routes,
    operation_routes,
    overview_routes,
    settings_routes,
    support_routes,
)
from .context import ServiceContext
from .routes import API_PREFIX, HEALTH_PATH, router
from .security import AccessGuard, error_response
from .static import WebAssets

LOG = logging.getLogger(__name__)
STATUS_BY_ERROR: dict[type[ApplicationError], HTTPStatus] = {
    InvalidArgument: HTTPStatus.BAD_REQUEST,
    DeviceNotFound: HTTPStatus.NOT_FOUND,
    RecordNotFound: HTTPStatus.NOT_FOUND,
    Busy: HTTPStatus.CONFLICT,
    SnapshotChanged: HTTPStatus.CONFLICT,
    FeatureDisabled: HTTPStatus.FORBIDDEN,
    InstanceLocked: HTTPStatus.CONFLICT,
    ConfirmationRequired: HTTPStatus.CONFLICT,
    ConfigUnavailable: HTTPStatus.CONFLICT,
    NotRunning: HTTPStatus.CONFLICT,
    NoSession: HTTPStatus.CONFLICT,
    PreconditionFailed: HTTPStatus.CONFLICT,
    Halted: HTTPStatus.CONFLICT,
    DatabaseUnavailable: HTTPStatus.SERVICE_UNAVAILABLE,
}
DESCRIPTION = (
    "PAR 光谱仪 2.0.0-alpha 本机服务，只监听 127.0.0.1。除 /api/v0/health 外，每个请求都要带启动时生成的令牌："
    "`Authorization: Bearer <token>` 或 `X-PAR-Token: <token>`（令牌与端口写在数据目录的 service.json）。"
    "档位 0（出厂）：只读历史库快照，不连接、不写设备；档位 1（二次确认后）：可接管采集，"
    "复用 V1.0.3 的协调器与单实例锁，只写 alpha 自己的配置与设备库（16_）；档位 2（在档位 1 之上再次确认）："
    "设备维护页可读取诊断、读写校准与通信参数，只经协调器的任务队列，写入前须有服务发出的确认号（17_）。"
    "合同：docs/spec/api-contract-v0.md。"
)


def _status(error: ApplicationError) -> HTTPStatus:
    for kind in type(error).__mro__:
        if kind in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[kind]
    return HTTPStatus.INTERNAL_SERVER_ERROR


async def _application_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApplicationError)
    status = _status(error)
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        LOG.warning("%s: %s (%s)", error.code, error.message, error.detail)
    return error_response(status, error.code, error.message, error.retryable, error.detail)


def _location(entry: dict[str, Any]) -> str:
    return ".".join(str(part) for part in entry.get("loc", ()) if part not in ("query", "path", "body"))


async def _validation_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    entries = list(error.errors())
    names = "、".join(dict.fromkeys(_location(entry) or "请求" for entry in entries))
    detail = "; ".join(f"{_location(entry)}: {entry.get('msg')}" for entry in entries)
    return error_response(HTTPStatus.BAD_REQUEST, "invalid_argument", f"参数错误：{names}", False, detail)


async def _http_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    status = HTTPStatus(error.status_code)
    code = "not_found" if status == HTTPStatus.NOT_FOUND else status.phrase.lower().replace(" ", "_")
    return error_response(status, code, str(error.detail), False)


async def _unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """The request layer of D-225 item 1: logged with its traceback, kept as the service's last fault and published
    (`service_error`), answered 500 retryable; nothing is stopped or cleared (a handler on an HTTP thread never
    touches the takeover, 16_ 1.4). Main-thread errors arrive here as TakeoverFault instead (gateway)."""
    LOG.exception("unexpected error while serving a request", exc_info=error)
    context: ServiceContext = request.app.state.context
    try:
        context.acquisition.faults.report("request", f"{request.method} {request.url.path}", error)
    except Exception:
        LOG.exception("the unexpected error could not be reported to the page")
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, "internal", "服务内部错误，请重试", True, type(error).__name__
    )


def _schema_without_422(app: FastAPI) -> Callable[[], dict[str, Any]]:
    """FastAPI documents request validation as 422; this service answers 400 invalid_argument (contract 1.3)."""

    def schema() -> dict[str, Any]:
        if app.openapi_schema is None:
            document = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
            for operation in (op for path in document["paths"].values() for op in path.values()):
                operation.get("responses", {}).pop(str(int(HTTPStatus.UNPROCESSABLE_ENTITY)), None)
            for name in ("HTTPValidationError", "ValidationError"):
                document.get("components", {}).get("schemas", {}).pop(name, None)
            app.openapi_schema = document
        return app.openapi_schema

    return schema


def create_app(
    context: ServiceContext,
    token: str,
    allowed_hosts: Iterable[str],
    web_dir: Path | None = None,
    request_stop: Callable[[], None] | None = None,
) -> FastAPI:
    """The ASGI app of one service instance. `allowed_hosts` is exactly {"127.0.0.1:<port>"} in the real service;
    `web_dir` (the built front end, static.py) is served at "/" when given; `request_stop` is what
    POST /api/v0/shutdown calls (the real service: uvicorn's graceful shutdown; without it the route answers 404)."""
    app = FastAPI(
        title="PAR Spectrometer local service",
        version=ALPHA_VERSION,
        description=DESCRIPTION,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,  # Swagger UI / ReDoc load scripts from a CDN; the alpha must work offline
        redoc_url=None,
    )
    app.state.context = context
    app.state.request_stop = request_stop
    app.include_router(router)
    app.include_router(operation_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(overview_routes.router)
    app.include_router(acquisition_routes.router)
    app.include_router(maintenance_routes.router)
    app.include_router(support_routes.router)
    app.add_exception_handler(ApplicationError, _application_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
    if web_dir is not None:
        app.mount("/", WebAssets(web_dir), name="web")  # after the router: /api/v0 routes match first
    app.add_middleware(
        AccessGuard, token=token, allowed_hosts=allowed_hosts, open_paths=(HEALTH_PATH,), protected_prefix=API_PREFIX
    )
    app.openapi = _schema_without_422(app)  # type: ignore[method-assign]
    return app


def openapi_document() -> dict[str, Any]:
    """The OpenAPI schema stored in docs/spec/openapi-v0.json (independent of data dir, token and port)."""
    from ..application.paths import AlphaPaths
    from ..domain.clock import SystemClock

    context = ServiceContext(AlphaPaths(Path("unused")), SystemClock())
    return create_app(context, token="schema-only", allowed_hosts=()).openapi()
