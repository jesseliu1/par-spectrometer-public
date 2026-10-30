"""D-225 item 1, read-only layer (R-1-5; PR #61 review major 1).

An unexpected exception in a read-only route (here: the history list, a snapshot query on an HTTP thread) is
answered 500 `internal` and retryable, as before; it is now also written to the log with its traceback, kept as the
service's last fault (GET /tier `fault`, kind "request") and published as a `service_error` event, so the page
shows a notice. Nothing is cleared: the snapshot stays, the same request succeeds when retried, and the tier and
takeover are left as they are (no stop: a query changes no state).

`par_app.api` imports no Qt, so the test runs in both test sessions (one per binding, 18_ 5.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from par_app.api.app import create_app
from par_app.api.context import ServiceContext
from par_app.application.faults import REQUEST_FAULT
from tests.api.conftest import AUTH, DAY, HOST, TOKEN, error_of, record, register_device, v1_database

pytestmark = pytest.mark.unit
LIST = "/api/v0/devices/p1/acquisitions"
BINDINGS = [pytest.param(name, marks=pytest.mark.qt_binding(name), id=name) for name in ("PyQt5", "PySide6")]


@pytest.mark.parametrize("binding", BINDINGS)
def test_an_unexpected_error_in_a_read_route_is_reported_keeps_the_data_and_can_be_retried(
    binding: str,
    context: ServiceContext,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    published: list[tuple[str, dict[str, Any]]] = []
    publish = context.events.publish
    monkeypatch.setattr(
        context.events, "publish", lambda name, data: published.append((name, data)) or publish(name, data)
    )
    app = create_app(context, token=TOKEN, allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}", headers=AUTH, raise_server_exceptions=False) as client:
        register_device(client, v1_database(tmp_path / "v1" / "par.sqlite3", [record()]))
        shown = client.get(LIST, params=DAY)
        assert shown.status_code == 200 and shown.json()["items"]
        assert client.get("/api/v0/tier").json()["fault"] is None

        page = context.history.page
        failures = [RuntimeError("injected read fault")]

        def flaky(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401 (the query's own answer)
            if failures:
                raise failures.pop()
            return page(*args, **kwargs)

        monkeypatch.setattr(context.history, "page", flaky)
        broken = client.get(LIST, params=DAY)
        assert broken.status_code == 500
        assert error_of(broken) == {
            "code": "internal",
            "message": "服务内部错误，请重试",
            "retryable": True,
            "detail": "RuntimeError",
        }

        tier = client.get("/api/v0/tier").json()
        fault = tier["fault"]
        assert (fault["kind"], fault["where"], fault["error"]) == ("request", f"GET {LIST}", "RuntimeError")
        assert fault["message"] == REQUEST_FAULT and not fault["stopping"]
        assert (tier["tier"], tier["takeover"]) == (1, "running")  # nothing stopped or lowered for a query
        assert ("service_error", fault) in published

        retried = client.get(LIST, params=DAY)  # the data is still there: the retry shows it again
        assert retried.status_code == 200 and retried.json() == shown.json()
        assert [item["configured"] for item in client.get("/api/v0/devices").json()["items"]][0] is True
    assert "RuntimeError: injected read fault" in caplog.text  # the traceback is in the log (service.log)
