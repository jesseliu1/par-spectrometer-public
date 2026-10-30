"""Event stream of the local service (api-contract-v0 API-17; 16_ section 5, "SSE 事件").

Events are hints; the state is what GET /acquisition/status and GET /tier answer. `publish` may be called from any
thread (the Qt main thread of the service publishes the coordinator's signals); each subscriber is an asyncio queue
on the event loop that serves its stream, fed with `call_soon_threadsafe`, so publishing never blocks. A subscriber
whose queue is full is closed (its page reconnects and reads the state again) instead of slowing the publisher down.
Ids grow by one per published event; Last-Event-ID is not supported (no replay).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

LOG = logging.getLogger(__name__)
QUEUE_LIMIT = 256
"""Events one subscriber may have waiting before its stream is closed (16_ section 5)."""
HEARTBEAT_SECONDS = 15.0
"""A `heartbeat` event goes out after this long without another event (API-17)."""


@dataclass(frozen=True)
class Event:
    id: int | None
    name: str
    data: dict[str, Any]

    def encode(self) -> str:
        """One SSE message: `id:` (when there is one), `event:` and a single `data:` line of JSON."""
        lines = [] if self.id is None else [f"id: {self.id}"]
        lines += [f"event: {self.name}", "data: " + json.dumps(self.data, ensure_ascii=False, default=str)]
        return "\n".join(lines) + "\n\n"


CLOSED = Event(None, "", {})
"""Sentinel put into a subscriber's queue when its stream must end (service closing, or the queue overflowed)."""


class Subscription:
    def __init__(self, hub: EventHub, loop: asyncio.AbstractEventLoop) -> None:
        self._hub = hub
        self.loop = loop
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.closed = False

    def offer(self, event: Event) -> None:
        """Runs on the subscriber's event loop."""
        if self.closed:
            return
        if event is CLOSED or self.queue.qsize() >= QUEUE_LIMIT:
            if event is not CLOSED:
                LOG.warning("event subscriber fell %d events behind; closing its stream", QUEUE_LIMIT)
            self.closed = True
            self.queue.put_nowait(CLOSED)
            return
        self.queue.put_nowait(event)

    async def next(self, timeout: float = HEARTBEAT_SECONDS) -> Event | None:
        """The next event, CLOSED when the stream must end, or None after `timeout` seconds without one."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except TimeoutError:
            return None

    def cancel(self) -> None:
        self._hub.unsubscribe(self)


class EventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[Subscription] = []
        self._next_id = 1
        self._closed = False

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> Subscription:
        subscription = Subscription(self, loop)
        with self._lock:
            if self._closed:
                subscription.offer(CLOSED)
            else:
                self._subscribers.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            if subscription in self._subscribers:
                self._subscribers.remove(subscription)

    def publish(self, name: str, data: dict[str, Any]) -> Event:
        with self._lock:
            event = Event(self._next_id, name, data)
            self._next_id += 1
            subscribers = list(self._subscribers)
        for subscription in subscribers:
            self._deliver(subscription, event)
        return event

    def close(self) -> None:
        """End every stream (service shutdown): uvicorn's graceful stop would otherwise wait for them forever."""
        with self._lock:
            self._closed = True
            subscribers, self._subscribers = self._subscribers, []
        for subscription in subscribers:
            self._deliver(subscription, CLOSED)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def _deliver(self, subscription: Subscription, event: Event) -> None:
        try:
            subscription.loop.call_soon_threadsafe(subscription.offer, event)
        except RuntimeError:  # the subscriber's loop is closed: its stream is gone
            self.unsubscribe(subscription)
