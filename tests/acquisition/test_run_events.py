"""Run events (issue #136 step 1): every shown message becomes one numbered event in logs/events.jsonl.

The log numbers events `<session>-<sequence>`, writes them on its own thread and never holds up or fails the caller:
a full queue or a failed write is counted, and the event still reaches the caller's notice.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from par_app.application.run_events import CLOSE_WAIT_SECONDS, CUT_MARK, DETAIL_TEXT_LIMIT, EVENTS_FILE, RunEventLog
from par_app.domain.clock import BEIJING_TZ, FakeClock

pytestmark = [pytest.mark.unit]

WAIT = 5.0
"""Seconds a test waits for the writer thread (wall time; the log itself never waits on the bus path)."""


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 28, 15, 55, 41, tzinfo=BEIJING_TZ))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _device(name: str, slave_id: int, message: str, level: str = "ok", **changes: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "key": name,
        "name": name,
        "slave_id": slave_id,
        "enabled": True,
        "level": level,
        "message": message,
        "failures": 0,
        "online": True,
        "excluded": False,
        **changes,
    }


def test_events_are_numbered_by_session_and_sequence_and_written_in_order(tmp_path: Path) -> None:
    log = RunEventLog(tmp_path, _clock(), session="3f9a1c2b")
    first = log.record("bus", "ok", "总线已连接")
    second = log.record(
        "device", "warning", "连续第 1 次尝试失败", {"key": "North", "name": "North", "slave_id": 3}, failures=1
    )
    assert (first.event_id, second.event_id) == ("3f9a1c2b-000001", "3f9a1c2b-000002")
    assert second.notice() == {"event_id": "3f9a1c2b-000002", "occurred_at": "2026-10-28T15:55:41.000"}
    assert log.flush(WAIT)
    rows = _lines(tmp_path / EVENTS_FILE)
    assert [row["event_id"] for row in rows] == [first.event_id, second.event_id]
    assert rows[1] | {"details": None} == {
        "event_id": "3f9a1c2b-000002",
        "session": "3f9a1c2b",
        "sequence": 2,
        "occurred_at": "2026-10-28T15:55:41.000",
        "kind": "device",
        "level": "warning",
        "message": "连续第 1 次尝试失败",
        "device_key": "North",
        "device_name": "North",
        "slave_id": 3,
        "details": None,
        "schema": 1,
    }
    assert rows[1]["details"] == {"failures": 1}
    assert log.health()["written"] == 2 and log.health()["last_written_sequence"] == 2
    log.close()


def test_a_restart_on_the_same_day_and_a_clock_set_back_never_repeat_or_reorder_numbers(tmp_path: Path) -> None:
    clock = _clock()
    before = RunEventLog(tmp_path, clock)
    after = RunEventLog(tmp_path, clock)  # a new service start: a new random session, same date
    assert before.session != after.session
    one = after.record("bus", "ok", "a")
    clock.set_wall(datetime(2026, 10, 27, 8, 0, tzinfo=BEIJING_TZ))  # the wall clock goes back a day
    two = after.record("bus", "ok", "b")
    assert two.sequence == one.sequence + 1 and two.occurred_at < one.occurred_at  # order is the number, not time
    assert before.record("bus", "ok", "c").event_id != one.event_id


def test_a_stalled_disk_drops_events_from_the_file_counts_them_and_never_blocks_the_caller(tmp_path: Path) -> None:
    gate = threading.Event()

    class Stalled:
        def __init__(self, path: Path) -> None:
            self.path = path

        def __enter__(self) -> Stalled:
            gate.wait(WAIT)
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def write(self, text: str) -> None:
            return None

    log = RunEventLog(tmp_path, _clock(), queue_limit=2, opener=Stalled)
    events = [log.record("device", "warning", f"第 {n} 次") for n in range(10)]  # returns at once although stalled
    assert [event.sequence for event in events] == list(range(1, 11))  # every caller still gets its event
    assert log.health()["dropped"] >= 7  # one in the writer's hand, two queued, the rest dropped
    assert not log.flush(0.01)  # queued events are counted at once: a flush never reports them written early
    gate.set()
    assert log.flush(WAIT)
    health = log.health()
    assert health["written"] + health["dropped"] == 10 and health["failed"] == 0
    log.close()


def test_a_failed_write_is_counted_with_its_reason_and_the_caller_goes_on(tmp_path: Path) -> None:
    def broken(path: Path) -> Any:  # noqa: ANN401 (an opener)
        raise PermissionError("disk is read-only")

    log = RunEventLog(tmp_path, _clock(), opener=broken)
    event = log.record("halt", "error", "采集停止中")
    assert event.event_id.endswith("-000001")
    assert log.flush(WAIT)
    health = log.health()
    assert (health["written"], health["failed"]) == (0, 1)
    assert health["first_error"] == health["last_error"] == "PermissionError: disk is read-only"
    log.close()


def test_events_after_close_are_counted_as_dropped(tmp_path: Path) -> None:
    log = RunEventLog(tmp_path, _clock())
    log.record("bus", "ok", "总线已连接")
    log.close()
    log.record("bus", "idle", "未在采集")
    assert len(_lines(tmp_path / EVENTS_FILE)) == 1 and log.health()["dropped"] == 1


def test_a_full_file_moves_to_a_numbered_backup(tmp_path: Path) -> None:
    log = RunEventLog(tmp_path, _clock(), file_limit=200)
    for n in range(6):
        log.record("bus", "ok", f"第 {n} 条总线消息")
    assert log.flush(WAIT)
    log.close()
    files = sorted(path.name for path in tmp_path.iterdir())
    assert "events.jsonl" in files and "events.1.jsonl" in files and len(files) <= 3
    sequences = sorted(row["sequence"] for name in files for row in _lines(tmp_path / name))
    assert sequences == sorted(set(sequences)) and sequences[-1] == 6


def test_long_detail_texts_are_cut_and_marked(tmp_path: Path) -> None:
    log = RunEventLog(tmp_path, _clock())
    event = log.record("device", "warning", "失败", reason="x" * (DETAIL_TEXT_LIMIT + 10), nested={"a": ["y" * 3000]})
    assert event.details["reason"] == "x" * DETAIL_TEXT_LIMIT + CUT_MARK
    assert event.details["nested"]["a"][0].endswith(CUT_MARK)
    log.close()


def test_a_failed_write_is_cut_back_and_a_half_line_left_by_a_crash_is_closed(tmp_path: Path) -> None:
    """PR #143 review: a write that fails half way must not join the next record into one broken line."""
    calls = {"n": 0}

    class HalfWrite:
        def __init__(self, path: Path) -> None:
            self.handle = path.open("a", encoding="utf-8")

        def __enter__(self) -> HalfWrite:
            return self

        def __exit__(self, *exc: object) -> None:
            self.handle.close()

        def write(self, text: str) -> None:
            calls["n"] += 1
            if calls["n"] == 2:  # the second record: half of it reaches the disk, then the disk is full
                self.handle.write(text[: len(text) // 2])
                self.handle.flush()
                raise OSError(28, "No space left on device")
            self.handle.write(text)

    log = RunEventLog(tmp_path, _clock(), opener=HalfWrite)
    for message in ("一", "二", "三"):
        log.record("bus", "ok", message)
    assert log.flush(WAIT)
    assert [row["message"] for row in _lines(tmp_path / EVENTS_FILE)] == ["一", "三"]
    assert log.health()["failed"] == 1 and "No space left on device" in log.health()["last_error"]
    log.close()
    (tmp_path / EVENTS_FILE).write_text('{"event_id": "x", "seq', encoding="utf-8")  # a crash mid-line
    after = RunEventLog(tmp_path, _clock())
    after.record("bus", "ok", "重启后")
    assert after.flush(WAIT)
    lines = (tmp_path / EVENTS_FILE).read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"event_id": "x", "seq' and json.loads(lines[1])["message"] == "重启后"
    after.close()


def test_a_session_is_sixteen_hex_digits(tmp_path: Path) -> None:
    log = RunEventLog(tmp_path, _clock())
    assert len(log.session) == 16 and int(log.session, 16) >= 0
    assert log.record("bus", "ok", "a").event_id == f"{log.session}-000001"
    log.close()


def test_close_waits_at_most_once_for_a_stalled_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PR #143 review: shutdown waits CLOSE_WAIT_SECONDS in all, not once for the queue and again to join."""
    gate = threading.Event()
    waits: list[float] = []

    class Stalled:
        def __init__(self, path: Path) -> None:
            return None

        def __enter__(self) -> Stalled:
            gate.wait(WAIT)
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def write(self, text: str) -> None:
            return None

    log = RunEventLog(tmp_path, _clock(), opener=Stalled)
    log.record("bus", "ok", "总线已连接")
    real_flush = log.flush

    def flush(timeout: float) -> bool:
        waits.append(timeout)
        return real_flush(0.01)  # the stalled writer does not finish in time

    monkeypatch.setattr(log, "flush", flush)
    log.close()
    assert waits == [CLOSE_WAIT_SECONDS]  # one bounded wait, then no join of the busy writer
    gate.set()
