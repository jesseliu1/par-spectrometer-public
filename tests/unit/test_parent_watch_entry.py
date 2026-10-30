"""The entry points take hold of the shell process first and watch it (D-223; review of PR #56, N2 and N3).

The shell starts par_app.service_main; `python -m par_app.api` is the source tree's entry and has the same option.
"""

from __future__ import annotations

import signal
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn

import par_app.service_main as service_entry
from par_app import parent_watch
from par_app.api import __main__ as api_entry
from par_app.application import paths
from par_app.domain.clock import BEIJING_TZ, FakeClock


def test_an_error_opening_the_shell_at_start_is_logged_by_the_watch(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeClock(datetime(2026, 10, 19, tzinfo=BEIJING_TZ))
    refused = OSError(5, "OpenProcess failed")
    assert parent_watch.watch_parent(4242, lambda: pytest.fail("stopped"), clock, waiter=refused) is None
    assert "cannot be watched" in caplog.text


def _record_parent_watch(module: Any, monkeypatch: pytest.MonkeyPatch, events: list[tuple[Any, ...]]) -> Any:  # noqa: ANN401
    """Replace the entry point's open_parent / watch_parent with recorders; returns the waiter open_parent hands out."""

    def waiter() -> None:
        return None

    def open_parent(pid: int, _clock: object) -> parent_watch.Waiter:
        events.append(("open", pid))
        return waiter

    def watch_parent(pid: int, stop: Any, _clock: object, opened: object) -> None:  # noqa: ANN401
        events.append(("watch", pid, opened))
        events.append(("stop", stop))

    monkeypatch.setattr(module, "open_parent", open_parent)
    monkeypatch.setattr(module, "watch_parent", watch_parent)
    return waiter


def test_api_entry_watches_the_shell_it_took_hold_of_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """python -m par_app.api --parent-pid (review N2 of PR #56; the shell starts par_app.service_main, this
    entry is the source tree's): the shell is taken hold of before anything else is set up, the same handle is
    watched, and its stop asks uvicorn to shut down gracefully."""
    events: list[tuple[Any, ...]] = []
    waiter = _record_parent_watch(api_entry, monkeypatch, events)
    monkeypatch.setattr(api_entry, "_configure_logging", lambda _paths: events.append(("logging",)))
    monkeypatch.setattr(signal, "signal", lambda *_args: None)

    def run(server: uvicorn.Server, sockets: list[object]) -> None:
        events.append(("run",))
        for event in events:
            if event[0] == "stop":  # the shell is gone: the watch's stop
                event[1]()
                assert server.should_exit

    monkeypatch.setattr(uvicorn.Server, "run", run)
    assert api_entry.main(["--data-dir", str(tmp_path), "--parent-pid", "4242"]) == 0
    assert [event for event in events if event[0] != "stop"] == [
        ("open", 4242),
        ("logging",),
        ("watch", 4242, waiter),
        ("run",),
    ]
    events.clear()
    assert api_entry.main(["--data-dir", str(tmp_path / "plain")]) == 0
    assert events == [("logging",), ("run",)]  # no --parent-pid: nothing is watched


def test_service_entry_takes_hold_of_the_shell_before_anything_else(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """par_app.service_main opens the shell before the data directory is even checked (review N3 of PR #56):
    a refused V1.0.3 program folder returns at once, and the shell was already taken hold of by then."""
    folder = tmp_path / "V1.0.3"
    for name in paths.V103_PROGRAM_MARKERS[0]:
        target = folder / name.rstrip("/")
        if name.endswith("/"):
            target.mkdir(parents=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
    events: list[tuple[Any, ...]] = []
    _record_parent_watch(service_entry, monkeypatch, events)
    refused = service_entry.main(["--data-dir", str(folder), "--parent-pid", "4242"])
    assert refused == service_entry.EXIT_REFUSED_DATA_DIR
    assert events == [("open", 4242)]
