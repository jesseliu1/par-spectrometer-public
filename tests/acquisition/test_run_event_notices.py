"""Shown messages carry their run event (issue #136 step 1): the state cache records an event when a message it holds
changes, keeps the same notice while the message stays the same, and the top bar's lines carry those notices.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from par_app.application.acquisition import StatusCache
from par_app.application.run_events import EVENTS_FILE, RunEventLog
from par_app.application.run_status import run_status
from tests.acquisition.test_run_events import WAIT, _clock, _device, _lines

pytestmark = [pytest.mark.unit]


def _cache(tmp_path: Path) -> tuple[StatusCache, RunEventLog]:
    clock = _clock()
    log = RunEventLog(tmp_path, clock, session="aaaa0001")
    return StatusCache(clock, log), log


def test_a_message_that_stays_the_same_keeps_its_notice_and_a_changed_one_gets_a_new_event(tmp_path: Path) -> None:
    cache, log = _cache(tmp_path)
    cache.reset(("warning", "正在连接 COM6 …"), [_device("North", 1, "")], False, 40.0, True)
    cache.set_bus("ok", "总线已连接")
    cache.set_bus("ok", "总线已连接")  # the same line again: no new event
    bus = cache.snapshot()["bus"]
    assert bus["notice"]["event_id"] == "aaaa0001-000003"
    cache.set_device(_device("North", 1, "采集成功 #1，正常，单次读取完成"))
    first = cache.snapshot()["devices"][0]["notice"]
    cache.set_device(_device("North", 1, "采集成功 #1，正常，单次读取完成"))  # acquisition_saved repeats it
    assert cache.snapshot()["devices"][0]["notice"] == first
    cache.set_device(_device("North", 1, "连续第 1 次尝试失败：设备通信超时", "warning", failures=1, online=False))
    changed = cache.snapshot()["devices"][0]["notice"]
    assert changed["event_id"] == "aaaa0001-000005" and changed != first
    assert log.flush(WAIT)
    rows = _lines(tmp_path / EVENTS_FILE)
    assert [row["kind"] for row in rows] == [
        "bus",
        "config",
        "bus",
        "device",
        "device",
    ]  # an empty message is no event; the start's config is
    assert rows[-1]["details"]["failures"] == 1 and rows[-1]["slave_id"] == 1
    log.close()


def test_every_line_the_top_bar_shows_names_its_event(tmp_path: Path) -> None:
    """The bus line, each red failure line and the halt carry the notice of the event their text came from."""
    cache, log = _cache(tmp_path)
    failing = "连续第 3 次尝试失败：设备通信超时（未启用失败停止，将继续按周期重试）"
    cache.reset(
        ("ok", "总线已连接"),
        [
            _device("North", 1, "采集成功"),
            _device(
                "South", 2, failing, "warning", failures=3, online=False, last_failure_at="2026-10-28T15:55:41.000"
            ),
        ],
        False,
        40.0,
        True,
    )
    snapshot = cache.snapshot()
    status = run_status(snapshot)
    assert status["bus"]["notice"] == snapshot["bus"]["notice"]
    assert status["failure_notices"] == [snapshot["devices"][1]["notice"]]
    assert status["failures"][0].endswith(failing)
    halt = {
        "name": "South",
        "slave_id": 2,
        "occurred_at": "2026-10-28T15:55:41.594",
        "reason": "恢复采集未确认：设备通信超时",
        "resume_unconfirmed": True,
        "cycle": 7,
        "message": "采集停止中：South（地址 2）恢复采集未确认：设备通信超时；所有设备的后台采集已停止",
        "text": "…",
    }
    cache.set_halt(halt)
    status = run_status(cache.snapshot())
    notice = cache.snapshot()["halt"]["notice"]
    assert status["bus"]["notice"] == status["acquisition"]["notice"] == notice
    assert log.flush(WAIT)
    row = next(row for row in _lines(tmp_path / EVENTS_FILE) if row["event_id"] == notice["event_id"])
    assert (row["kind"], row["message"], row["device_name"], row["slave_id"]) == ("halt", halt["message"], "South", 2)
    assert row["details"]["cycle"] == 7 and row["details"]["resume_unconfirmed"] is True
    log.close()


def test_a_refused_start_is_an_event_and_its_notice_goes_with_the_error(tmp_path: Path) -> None:
    cache, log = _cache(tmp_path)
    cache.set_takeover("released", False, "串口 COM6 被其他程序占用")
    notice = cache.snapshot()["error_notice"]
    cache.set_takeover("released", False, "串口 COM6 被其他程序占用")
    assert cache.snapshot()["error_notice"] == notice and notice["event_id"].endswith("-000001")
    cache.set_takeover("starting", False)
    assert cache.snapshot()["error_notice"] is None
    log.close()


def test_without_an_event_log_the_cache_works_as_before(tmp_path: Path) -> None:
    cache = StatusCache(_clock())
    cache.set_bus("ok", "总线已连接")
    cache.set_device(_device("North", 1, "采集成功"))
    snapshot = cache.snapshot()
    assert snapshot["bus"]["notice"] is None and snapshot["devices"][0]["notice"] is None
    assert not list(tmp_path.iterdir())


def test_a_notice_still_shown_stays_in_the_files_however_often_they_rotate(tmp_path: Path) -> None:
    """PR #143 review: "总线已连接" stays on the page for days while device events rotate the files; its record
    is carried into each new file, so the number shown can always be found."""
    clock = _clock()
    log = RunEventLog(tmp_path, clock, session="aaaa0002", file_limit=600)
    cache = StatusCache(clock, log)
    cache.set_bus("ok", "总线已连接")
    bus = cache.snapshot()["bus"]["notice"]
    for n in range(40):  # every message new: many rotations, the oldest file dropped again and again
        cache.set_device(_device("North", 1, f"采集成功 #{n}，正常，单次读取完成"))
        assert log.flush(WAIT)
    rows = [row for path in sorted(tmp_path.glob("events*.jsonl")) for row in _lines(path)]
    assert min(row["sequence"] for row in rows if not row.get("carried_over")) > 2  # the first files are gone
    carried = [row for row in rows if row["event_id"] == bus["event_id"]]
    assert carried and carried[0]["message"] == "总线已连接" and carried[0]["carried_over"] is True
    device = cache.snapshot()["devices"][0]["notice"]
    assert device["event_id"] in {row["event_id"] for row in rows}
    cache.set_bus("error", "总线连接失败：COM6")  # no longer shown: no longer carried
    for n in range(40, 80):
        cache.set_device(_device("North", 1, f"采集成功 #{n}，正常，单次读取完成"))
        assert log.flush(WAIT)
    rows = [row for path in sorted(tmp_path.glob("events*.jsonl")) for row in _lines(path)]
    assert bus["event_id"] not in {row["event_id"] for row in rows}
    log.close()
