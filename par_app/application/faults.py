"""Unexpected errors of the local service and what the page is told about them (D-225 item 1, R-1-5).

Two layers, decided by where the error happened (16_ 1.4: only the Qt main thread touches the takeover):

* "request": an HTTP handler raised something unexpected on its own thread (a query, a snapshot read, a file
  export). Nothing of the takeover was touched; the request is answered 500 `internal` (retryable), the page keeps
  its last valid data and can retry.
* "takeover": code on the Qt main thread raised (a slot or callback of the takeover or maintenance controller, or a
  call an HTTP request carried there). Its state may be half updated, so the service stops the takeover the way
  POST /shutdown and the shell watch do (the transaction in progress finishes and resumes the device, the port
  closes, the lock is released), keeps the tier (issue #119) and goes on serving so the page can say what happened.

The service keeps the last fault (GET /tier `fault`) and publishes each one as a `service_error` event; the traceback
goes to service.log. Nothing here clears a halt or rewrites a record.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..domain.clock import Clock
from .events import EventHub
from .timefmt import beijing_iso

FaultKind = Literal["request", "takeover"]
REQUEST_FAULT = "本机服务处理请求时出现内部错误（已记入 service.log）。页面保留上次读取的数据，可点“重试”。"
TAKEOVER_FAULT = (
    "软件运行出现异常，已停止采集以保护设备（当前一轮通信结束、设备已恢复后才停止）。"
    "可到“实时概览”点“开始采集”重试；如果反复出现，请在“设置与导出”导出诊断包发给我们。"
)
STOP_FAILED = (
    "停止采集时再次出现内部错误（已记入 service.log），采集可能未完全停止。请退出本软件后重新打开，"
    "必要时为设备重新上电。"
)
EVENT = "service_error"


@dataclass(frozen=True)
class Fault:
    id: int
    kind: FaultKind
    occurred_at: str
    where: str
    error: str
    """The exception's type name (its text and traceback are only in service.log)."""
    message: str
    stopping: bool
    """True when the service stops the takeover because of it (the tier is kept, issue #119)."""


class FaultLog:
    """The service's last unexpected error; safe to use from any thread."""

    def __init__(self, clock: Clock, events: EventHub) -> None:
        self._clock = clock
        self._events = events
        self._lock = threading.Lock()
        self._last: Fault | None = None
        self._count = 0

    def report(self, kind: FaultKind, where: str, error: BaseException, message: str | None = None) -> Fault:
        text = message if message is not None else (TAKEOVER_FAULT if kind == "takeover" else REQUEST_FAULT)
        with self._lock:
            self._count += 1
            fault = Fault(
                id=self._count,
                kind=kind,
                occurred_at=beijing_iso(self._clock.now()),
                where=where,
                error=type(error).__name__,
                message=text,
                stopping=kind == "takeover" and message is None,
            )
            self._last = fault
        self._events.publish(EVENT, asdict(fault))
        return fault

    def last(self) -> dict[str, Any] | None:
        with self._lock:
            return None if self._last is None else asdict(self._last)
