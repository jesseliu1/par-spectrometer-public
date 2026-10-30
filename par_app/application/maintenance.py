"""Tier 2 "设备维护写入" use cases (内部文档; D-216).

This layer holds what needs no Qt: the tier and takeover gate every maintenance request passes first (17_ 4, public
preconditions), the error codes of 17_ section 9, and the one-time write confirmations of 17_ 6.2 (bound to the
action, the maintenance target, a digest of the request body and, for the calibration, the draft version; 60 s,
single use). Everything else - V1.0.3's own window conditions (G1-G10), the verification state machine, the texts and
the call into the coordinator - runs on the service's Qt main thread in par_app.acquisition_host.maintenance_host and
is reached only through the `MaintenancePort` protocol below. Nothing here can clear a hardware latch.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Protocol

from ..domain.clock import Clock
from .errors import ApplicationError, Busy, ConfigUnavailable, ConfirmationRequired, FeatureDisabled, NotRunning
from .tier import CONFIRMATION_ID_BYTES, CONFIRMATION_SECONDS, MAINTENANCE_TIER
from .timefmt import beijing_iso

if TYPE_CHECKING:
    from .acquisition import AcquisitionService

TIER_TOO_LOW = "设备维护需要维护模式（在设置页先开启采集模式，再开启维护模式）"
NOT_TAKEN_OVER = "设备维护需要先开始采集：诊断、校准与通信维护都由运行中的采集协调器执行"
BUSY_TAKEOVER = "正在开始或停止采集，请稍候"
NO_BACKEND = "本服务入口不含采集功能（开发用的只读入口），请用 alpha 程序启动服务"
CONFIRMATION_INVALID = "写入需要先在确认框中确认（确认无效、已使用或已过期），请重新操作"
CONFIRMATION_MISMATCH = "确认的内容与本次请求不一致（操作、设备、参数或校准草稿已变化），请重新确认"
WRITE_ACTIONS = ("enter", "comm_write", "calibration_write", "leave", "calibration_reread", "close_discard")
"""Actions that need a confirmation id (17_ 6.2; D-216 question 10)."""


class NoSession(ApplicationError):
    """No maintenance page session is open (17_ 3.4)."""

    code = "no_session"
    retryable = False


class PreconditionFailed(ApplicationError):
    """One of V1.0.3's window conditions (17_ 1.3, G1-G10) does not hold; `message` is V1.0.3's own text."""

    code = "precondition_failed"
    retryable = True


class Halted(ApplicationError):
    """The coordinator's hardware latch is set; `message` is its own text. Only stopping the takeover ends it."""

    code = "halted"
    retryable = False


@dataclass(frozen=True)
class WriteConfirmation:
    id: str
    action: str
    expires_at: str
    title: str
    text: str


def body_digest(body: Mapping[str, Any]) -> str:
    """SHA-256 of the request body in canonical JSON (sorted keys): the confirmation and the write must match."""
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Issued:
    action: str
    key: str
    digest: str
    version: int
    expires: float


class MaintenanceConfirmations:
    """Write confirmations issued by this service process (17_ 6.2); each can be used once, until it expires."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._issued: dict[str, _Issued] = {}

    def issue(
        self, action: str, key: str, body: Mapping[str, Any], version: int, title: str, text: str
    ) -> WriteConfirmation:
        identifier = secrets.token_urlsafe(CONFIRMATION_ID_BYTES)
        now = self._clock.monotonic()
        wall = self._clock.now() + timedelta(seconds=CONFIRMATION_SECONDS)
        with self._lock:
            self._issued = {name: item for name, item in self._issued.items() if item.expires > now}
            self._issued[identifier] = _Issued(action, key, body_digest(body), version, now + CONFIRMATION_SECONDS)
        return WriteConfirmation(identifier, action, beijing_iso(wall), title, text)

    def consume(self, identifier: str | None, action: str, key: str, body: Mapping[str, Any], version: int) -> None:
        """Raises ConfirmationRequired unless `identifier` was issued for exactly this request and is still valid; a
        presented id is used up even when it does not match (it cannot be replayed with other values)."""
        with self._lock:
            issued = self._issued.pop(identifier, None) if identifier else None
        if issued is None or self._clock.monotonic() >= issued.expires:
            raise ConfirmationRequired(CONFIRMATION_INVALID)
        if (issued.action, issued.key, issued.digest, issued.version) != (action, key, body_digest(body), version):
            raise ConfirmationRequired(CONFIRMATION_MISMATCH)

    def clear(self) -> None:
        with self._lock:
            self._issued.clear()


class MaintenancePort(Protocol):
    """The Qt side (par_app.acquisition_host.maintenance_host via HostBackend). Safe to call from HTTP threads."""

    def view(self) -> dict[str, Any]:
        """The maintenance page's view model (17_ 9 GET /maintenance/state); read-only."""

    def open_page(self, tab: str) -> dict[str, Any]:
        """Open the single page session (17_ 3.4); raises Busy when one is open."""

    def close_page(self, confirmation_id: str | None) -> dict[str, Any]:
        """Close it (V1.0.3 reject()): Busy while a task runs; unwritten calibration edits need a confirmation."""

    def confirm(self, action: str, body: Mapping[str, Any]) -> WriteConfirmation:
        """Check the preconditions of a write and issue its confirmation with V1.0.3's dialog text."""

    def act(self, action: str, body: Mapping[str, Any], confirmation_id: str | None) -> dict[str, Any]:
        """Run one page action (17_ section 4); returns the new view model."""

    def settings_comm(self, key: str) -> dict[str, Any]:
        """The settings page's "通信参数当前值" of the device at `key`, asked as V1.0.3 asks (G9)."""

    def busy(self) -> bool:
        """A maintenance task is in flight or maintenance is being entered (2 -> 1 is refused then)."""

    def writing(self) -> bool:
        """A calibration or communication write is in flight (the stop confirmation says so)."""

    def settings_left(self) -> None:
        """The settings page is no longer shown: its automatic re-read on a reconnect stops (review M1)."""

    def lowered(self) -> None:
        """Tier 2 -> 1: unwritten calibration edits are dropped; maintenance itself stays (17_ 6.1). Raises Busy while
        a maintenance task runs (decided on the main thread); afterwards nothing is queued until `raised`."""

    def raised(self) -> None:
        """Tier 1 -> 2: maintenance calls are possible again."""


class MaintenanceService:
    """The public preconditions of every maintenance request (17_ section 4): tier 2, then a running takeover."""

    def __init__(self, acquisition: AcquisitionService) -> None:
        self.acquisition = acquisition

    def _port(self) -> MaintenancePort:
        port = self.acquisition.maintenance
        if port is None:
            raise ConfigUnavailable(NO_BACKEND)
        return port

    def _gate(self) -> MaintenancePort:
        acquisition = self.acquisition
        if acquisition.closing:
            raise Busy("服务正在关闭")
        if acquisition.tier() < MAINTENANCE_TIER:
            raise FeatureDisabled(TIER_TOO_LOW)
        port = self._port()
        takeover = acquisition.cache.takeover
        if takeover == "released":
            raise NotRunning(NOT_TAKEN_OVER)
        if takeover != "running":
            raise Busy(BUSY_TAKEOVER)
        return port

    def view(self) -> dict[str, Any]:
        """Readable in tier 2, and below it while a takeover is not released (only reading; 17_ section 8)."""
        acquisition = self.acquisition
        if acquisition.tier() < MAINTENANCE_TIER and acquisition.cache.takeover == "released":
            raise FeatureDisabled(TIER_TOO_LOW)
        return self._port().view()

    def open_page(self, tab: str) -> dict[str, Any]:
        return self._gate().open_page(tab)

    def close_page(self, confirmation_id: str | None) -> dict[str, Any]:
        """Closing is allowed below tier 2 too while a takeover runs (it only ends the page session)."""
        if self.acquisition.tier() < MAINTENANCE_TIER and self.acquisition.cache.takeover == "released":
            raise FeatureDisabled(TIER_TOO_LOW)
        return self._port().close_page(confirmation_id)

    def confirm(self, action: str, body: Mapping[str, Any]) -> WriteConfirmation:
        return self._gate().confirm(action, body)

    def act(self, action: str, body: Mapping[str, Any], confirmation_id: str | None = None) -> dict[str, Any]:
        return self._gate().act(action, body, confirmation_id)

    def settings_comm(self, key: str) -> dict[str, Any]:
        return self._gate().settings_comm(key)

    def settings_left(self) -> None:
        """Allowed below tier 2 too while a takeover runs (it only stops the automatic re-read; review M1)."""
        if self.acquisition.tier() < MAINTENANCE_TIER and self.acquisition.cache.takeover == "released":
            raise FeatureDisabled(TIER_TOO_LOW)
        self._port().settings_left()
