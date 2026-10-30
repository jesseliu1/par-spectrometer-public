"""How the state cache turns the messages it holds into run events (issue #136); `StatusCache` uses it under its lock.

A new message is recorded once and its notice ({event_id, occurred_at}) is kept with it until it changes; the event a
notice shows is pinned at its place on the page (bus, device:<key>, halt, error), so a rotation of the event files
keeps it, and unpinned once nothing is shown there.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .bus_trace import BusTrace
from .run_actions import DEVICE_DETAILS, TAKEOVER_TEXTS
from .run_events import RunEventLog
from .tier import Takeover

KEPT_KINDS = ("device", "halt")
"""A device failure or a halt keeps the bus trace's last stretch under its record number."""


class CacheNotices:
    """The run-event half of `StatusCache`: its fields are the cache's own."""

    _events: RunEventLog | None
    _trace: BusTrace | None
    _takeover: Takeover
    _bus: dict[str, Any]
    _devices: dict[str, dict[str, Any]]
    _order: list[str]

    def _notice(
        self,
        kind: str,
        level: str,
        message: str,
        device: Mapping[str, Any] | None,
        slot: str | None = None,
        **details: object,
    ) -> dict[str, Any] | None:
        """Record one run event and return its notice; `slot` is where the page shows it (kept through rotations).
        None without an event log (tests of other things)."""
        if self._events is None:
            return None
        event = self._events.record(kind, level, message, device, **details)
        if slot is not None:
            self._events.pin(slot, event)
        if self._trace is not None and kind in KEPT_KINDS and level != "ok":  # what was on the line then (#136)
            self._trace.keep(event.event_id, kind, message)
        return event.notice()

    def _pin(self, slot: str) -> None:
        """Nothing is shown at `slot` any more."""
        if self._events is not None:
            self._events.pin(slot, None)

    def _moved(self, state: Takeover) -> None:
        if state != self._takeover:  # what actually happened after a request (#136 step 3)
            self._notice("takeover", "info", TAKEOVER_TEXTS.get(state, str(state)), None, state=state)

    def _set_bus(self, level: str, message: str) -> None:
        notice = self._bus.get("notice")
        if (level, message) != (self._bus.get("level"), self._bus.get("message")):
            notice = self._notice("bus", level, message, None, "bus")
        self._bus = {"level": level, "message": message, "notice": notice}

    def _with_notice(self, device: Mapping[str, Any], before: Mapping[str, Any] | None) -> dict[str, Any]:
        entry = copy.deepcopy(dict(device))
        message, level = entry.get("message"), entry.get("level")
        if before is not None and (before.get("message"), before.get("level")) == (message, level):
            entry["notice"] = before.get("notice")
        elif message:
            details = {name: entry.get(name) for name in DEVICE_DETAILS}
            entry["notice"] = self._notice(
                "device", str(level), str(message), entry, f"device:{entry.get('key')}", **details
            )
        else:
            entry["notice"] = None
            self._pin(f"device:{entry.get('key')}")
        return entry

    def _replace_devices(self, devices: list[dict[str, Any]]) -> None:
        before = self._devices
        self._order = [str(device["key"]) for device in devices]
        if self._events is not None:
            self._events.unpin_except("device:", {f"device:{device['key']}" for device in devices})
        self._devices = {
            str(device["key"]): self._with_notice(device, before.get(str(device["key"]))) for device in devices
        }
