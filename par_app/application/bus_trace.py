"""The bus trace (issue #136 steps 2 and 3; owner's R-4-2 approval of 2026-10-29, scope one, recorded in #132).

The serial port the protocol opens is wrapped here (through `rtu_frames.PORT_TAP`, which the alpha service installs):
every frame written and every non-empty read is copied, with the client's monotonic time, into a bounded ring in
memory. Nothing else happens on the communication thread: no disk, no parsing, no change to the bytes, their order
or their timing (a lock and a deque append per call). V1.0.3's desktop program never installs it.

When the state cache records a device failure or a halt (#136 run events), the last KEPT_ENTRIES of the ring are
kept under that event's number, so the export can show what was on the line when it happened. The diagnostics
bundle then reads the kept windows and the current ring on its own thread and turns them into one record per
exchange (bus_trace_summary): no payload bytes leave memory.

Not covered (owner 2026-10-28, #136): a crash or restart loses what is in memory; TCP is not traced.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..domain.clock import Clock
from ..rtu_frames import PORT_TAP

TRACE_ENTRIES = 4000
"""The ring: about ten rounds of four devices (a device's round is some 25 frames out and as many reads in)."""
KEPT_ENTRIES = 800
"""What a device failure or a halt keeps: the last two or three rounds of four devices."""
KEPT_HALTS = 5
KEPT_FAILURES = 15
SENT, RECEIVED = "sent", "received"


@dataclass(frozen=True)
class Entry:
    at: float
    """The client's monotonic time of the write (before it) or of the read (after it)."""
    direction: str
    data: bytes


@dataclass(frozen=True)
class Window:
    """A stretch of the ring with the clock's wall time at its end, so each entry gets its Beijing time."""

    event_id: str | None
    kind: str
    message: str
    ended_at: datetime
    ended_mono: float
    entries: tuple[Entry, ...]

    def wall(self, at: float) -> datetime:
        return self.ended_at - timedelta(seconds=self.ended_mono - at)


class TappedPort:
    """The serial port as the protocol uses it; writes and non-empty reads are copied into the trace."""

    def __init__(self, port: Any, clock: Clock, trace: BusTrace) -> None:  # noqa: ANN401 (a serial.Serial)
        self.__dict__.update(_port=port, _clock=clock, _trace=trace)

    def write(self, data: bytes) -> Any:  # noqa: ANN401 (whatever the port returns, unchanged)
        at = self._clock.monotonic()
        written = self._port.write(data)
        self._trace.add(Entry(at, SENT, bytes(data)))  # only a frame that went out; its time is when it was sent
        return written

    def read(self, size: int = 1) -> bytes:
        data = bytes(self._port.read(size))
        if data:
            self._trace.add(Entry(self._clock.monotonic(), RECEIVED, data))
        return data

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 (in_waiting, setDTR, close, ...)
        return getattr(self.__dict__["_port"], name)

    def __setattr__(self, name: str, value: object) -> None:  # timeout, write_timeout
        setattr(self.__dict__["_port"], name, value)


class BusTrace:
    """The ring and the windows kept at failures and halts; `add` is the only call on the communication thread."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: deque[Entry] = deque(maxlen=TRACE_ENTRIES)
        self._halts: deque[Window] = deque(maxlen=KEPT_HALTS)
        self._failures: deque[Window] = deque(maxlen=KEPT_FAILURES)
        self.windows_dropped = 0
        self.installed = False

    def install(self) -> None:
        """Wrap every serial port the protocol opens from now on (the alpha service, at start)."""
        PORT_TAP.recorder = self.wrap
        self.installed = True

    def uninstall(self) -> None:
        if PORT_TAP.recorder == self.wrap:
            PORT_TAP.recorder = None
        self.installed = False

    def wrap(self, port: Any, clock: Clock) -> TappedPort:  # noqa: ANN401
        return TappedPort(port, clock, self)

    def add(self, entry: Entry) -> None:
        with self._lock:
            self._entries.append(entry)

    def keep(self, event_id: str, kind: str, message: str) -> None:
        """Keep the last KEPT_ENTRIES under the run event `event_id` (a device failure or a halt)."""
        window = self._window(event_id, kind, message, KEPT_ENTRIES)
        if not window.entries:
            return
        kept = self._halts if kind == "halt" else self._failures
        with self._lock:
            self.windows_dropped += len(kept) == kept.maxlen
            kept.append(window)

    def kept(self) -> list[Window]:
        with self._lock:
            windows = [*self._halts, *self._failures]
        return sorted(windows, key=lambda window: (window.ended_mono, window.event_id or ""))  # numbers are in order

    def current(self) -> Window:
        """The whole ring now (the export's own view)."""
        return self._window(None, "export", "导出时串口收发记录中的全部内容", TRACE_ENTRIES)

    def _window(self, event_id: str | None, kind: str, message: str, size: int) -> Window:
        with self._lock:
            entries = tuple(self._entries)[-size:]
        ended_at, ended_mono = self._clock.now(), self._clock.monotonic()
        return Window(event_id, kind, message, ended_at, ended_mono, entries)
