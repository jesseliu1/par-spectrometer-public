"""Run events: every message the pages show comes from one numbered event, written to logs/events.jsonl (issue #136).

A notice on the page (the bus line, a device's message and failure line, the halt banner) carries the `event_id` and
the time of the event it was made from, so the same record can be found in the diagnostics bundle. The guarantee
owner set (2026-10-28, #136): a bundle exported successfully holds every notice the pages showed at export time; when
the log loses or cuts records, the page and the bundle say so; what survives a crash is not promised.

Numbers: `<session>-<sequence>`. The session is random per service start (never the date or a serial number), the
sequence counts from 1 within it, so a restart on the same day never repeats a number and a wall clock set back
does not reorder them: order is the sequence, the time is only shown.

Writing never holds up the caller: `record` builds the event, gives it its number and puts it into a bounded queue
under one lock (so the file order is the number order), and a daemon thread writes the queue to the file. A full
queue drops the event from the file and counts it; a failed write is counted with its first and latest error. The
event still goes back to the caller, whose notice keeps it in memory, so the export can add what the file lacks
(diagnostics bundle, #136 step 4). Nothing here reads or writes a device database or touches the bus.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..domain.clock import Clock
from .timefmt import beijing_iso

LOG = logging.getLogger(__name__)
SCHEMA_VERSION = 1
EVENTS_FILE = "events.jsonl"
QUEUE_LIMIT = 1000
"""Events waiting for the writer before new ones are dropped from the file (counted). The busiest source is one
device message per device per poll (at least 40 s), so 1000 covers minutes of a stalled disk with four devices."""
FILE_LIMIT_BYTES = 5_000_000
"""events.jsonl is moved to events.1.jsonl once it passes this size (the same 5 MB the bundle keeps of a log)."""
FILE_BACKUPS = 2
"""Older files kept: events.1.jsonl and events.2.jsonl."""
SESSION_HEX_DIGITS = 16
"""64 random bits per service start: two starts sharing a session (and so a number) is not to be expected."""
SEQUENCE_DIGITS = 6
DETAIL_TEXT_LIMIT = 2000
"""Characters kept of one text in `details` (an exception text, a reason); longer ones are cut and marked."""
CUT_MARK = "…（已截断）"
CLOSE_WAIT_SECONDS = 2.0
"""How long `close` waits for the writer to empty the queue at shutdown."""


def new_session() -> str:
    return secrets.token_hex(SESSION_HEX_DIGITS // 2)


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    session: str
    sequence: int
    occurred_at: str
    kind: str
    """bus, device, halt (step 1); actions follow in #136 step 3."""
    level: str
    message: str
    device_key: str | None = None
    device_name: str | None = None
    slave_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    def notice(self) -> dict[str, Any]:
        """What a page notice carries to find this event again."""
        return {"event_id": self.event_id, "occurred_at": self.occurred_at}

    def line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str) + "\n"


@dataclass
class LogHealth:
    written: int = 0
    """Events written to the file."""
    last_written_sequence: int | None = None
    dropped: int = 0
    """Events left out of the file because the queue was full."""
    failed: int = 0
    """Events whose write failed."""
    first_error: str | None = None
    last_error: str | None = None


def _bounded(value: object) -> object:
    if isinstance(value, str) and len(value) > DETAIL_TEXT_LIMIT:
        return value[:DETAIL_TEXT_LIMIT] + CUT_MARK
    if isinstance(value, Mapping):
        return {str(key): _bounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in value]
    return value


class RunEventLog:
    """Numbers events and writes them to `directory`/events.jsonl. `record` may be called from any thread."""

    def __init__(
        self,
        directory: Path,
        clock: Clock,
        session: str | None = None,
        queue_limit: int = QUEUE_LIMIT,
        file_limit: int = FILE_LIMIT_BYTES,
        opener: Callable[[Path], Any] | None = None,
    ) -> None:
        self.directory = directory
        self.path = directory / EVENTS_FILE
        self.clock = clock
        self.session = session or new_session()
        self._file_limit = file_limit
        self._open = opener or (lambda path: path.open("a", encoding="utf-8"))
        self._lock = threading.Lock()
        self._sequence = 0
        self._queue: queue.Queue[RunEvent | None] = queue.Queue(maxsize=queue_limit)
        self._health = LogHealth()
        self._health_lock = threading.Lock()
        self._pending = 0
        self._written = threading.Condition()
        self._writer: threading.Thread | None = None
        self._closed = False
        self._pinned: dict[str, RunEvent] = {}
        """The events notices still show, by where they are shown: carried into a new file on rotation."""

    def record(
        self,
        kind: str,
        level: str,
        message: str,
        device: Mapping[str, Any] | None = None,
        **details: object,
    ) -> RunEvent:
        """Number the event and queue it for the file; never blocks and never raises because of the file."""
        with self._lock:
            self._sequence += 1
            event = RunEvent(
                event_id=f"{self.session}-{self._sequence:0{SEQUENCE_DIGITS}d}",
                session=self.session,
                sequence=self._sequence,
                occurred_at=beijing_iso(self.clock.now()),
                kind=kind,
                level=level,
                message=message,
                device_key=None if device is None else _text(device.get("key")),
                device_name=None if device is None else _text(device.get("name")),
                slave_id=None if device is None else _integer(device.get("slave_id")),
                details=dict(_bounded(details)),  # type: ignore[call-overload]
            )
            if self._closed:
                self._count_dropped()
                return event
            self._ensure_writer()
            with self._written:  # counted before the writer can see it, so a flush never misses it
                self._pending += 1
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                with self._written:
                    self._pending -= 1
                    self._written.notify_all()
                self._count_dropped()
        return event

    def pin(self, slot: str, event: RunEvent | None) -> None:
        """`event` is what the notice at `slot` (the bus line, a device, the halt) shows now; None when nothing is
        shown there any more. A rotation copies the pinned events into the new file, so a notice the page still
        shows can always be found in the current files."""
        with self._lock:
            if event is None:
                self._pinned.pop(slot, None)
            else:
                self._pinned[slot] = event

    def unpin_except(self, prefix: str, kept: set[str]) -> None:
        """Unpin every slot starting with `prefix` but those in `kept` (devices no longer configured)."""
        with self._lock:
            for slot in [slot for slot in self._pinned if slot.startswith(prefix) and slot not in kept]:
                del self._pinned[slot]

    def health(self) -> dict[str, Any]:
        with self._health_lock:
            return {"session": self.session, **asdict(self._health)}

    def flush(self, timeout: float) -> bool:
        """Wait up to `timeout` seconds for every queued event to be written (or to fail); True when none is left.
        Only for the export and shutdown, never on the bus path."""
        with self._written:
            return self._written.wait_for(lambda: self._pending == 0, timeout)

    def close(self) -> None:
        """Stop taking events, let the writer finish what is queued and stop it: at most CLOSE_WAIT_SECONDS in all.

        A writer still busy after that wait (a stalled disk) is left to end with the process (a daemon thread); only
        an idle writer is asked to stop and joined, which returns at once since nothing is left to write."""
        with self._lock:
            self._closed = True
            writer = self._writer
        if writer is None or not self.flush(CLOSE_WAIT_SECONDS):
            return
        self._queue.put_nowait(None)  # the queue is empty: flushed, and closed to new events
        writer.join()

    # ------------------------------------------------------------------ writer
    def _ensure_writer(self) -> None:
        if self._writer is None:
            self._writer = threading.Thread(target=self._run, name="run-events-writer", daemon=True)
            self._writer.start()

    def _count_dropped(self) -> None:
        with self._health_lock:
            self._health.dropped += 1

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            if event is None:
                return
            self._write(event)
            with self._written:
                self._pending -= 1
                self._written.notify_all()

    def _write(self, event: RunEvent) -> None:
        size: int | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._rotate_if_full(event)
            size = self.path.stat().st_size if self.path.exists() else 0
            line = event.line() if size == 0 or _ends_with_newline(self.path) else "\n" + event.line()
            with self._open(self.path) as handle:
                handle.write(line)
        except Exception as exc:  # the file is a record, not a reason to stop: count and remember why (R-1-5)
            text = f"{type(exc).__name__}: {exc}"
            if size is not None:
                text += _cut_back(self.path, size)
            with self._health_lock:
                self._health.failed += 1
                self._health.first_error = self._health.first_error or text
                self._health.last_error = text
            return
        with self._health_lock:
            self._health.written += 1
            self._health.last_written_sequence = event.sequence

    def _rotate_if_full(self, writing: RunEvent) -> None:
        """Move the full file to events.1.jsonl and start the new one with the pinned events already written (marked
        `carried_over`; the same event_id), so the oldest file going never takes a notice still shown with it."""
        if not self.path.exists() or self.path.stat().st_size < self._file_limit:
            return
        for index in range(FILE_BACKUPS, 0, -1):
            older = self.directory / f"events.{index}.jsonl"
            newer = self.path if index == 1 else self.directory / f"events.{index - 1}.jsonl"
            if newer.exists():
                newer.replace(older)
        with self._lock:
            carried = sorted(self._pinned.values(), key=lambda item: item.sequence)
        lines = [
            json.dumps({**asdict(item), "carried_over": True}, ensure_ascii=False, default=str) + "\n"
            for item in carried
            if item.sequence < writing.sequence
        ]
        if lines:
            with self._open(self.path) as handle:
                handle.write("".join(lines))


def _ends_with_newline(path: Path) -> bool:
    """Whether the file ends a line; a line left half written (a crash) is closed before the next one."""
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) == b"\n"


def _cut_back(path: Path, size: int) -> str:
    """After a failed write, cut the file back to where the line began, so a half line never joins the next one;
    "" when that worked (or nothing was written), else why it did not."""
    try:
        if path.exists() and path.stat().st_size > size:
            os.truncate(path, size)
    except OSError as error:
        return f"（回退未完成：{type(error).__name__}: {error}）"
    return ""


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
