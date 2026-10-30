"""The page's requests and what took effect, as run events (issue #136 step 3).

A request is recorded as requested, then accepted or refused with the reason the page shows; what took effect comes
from the state cache: the takeover's states, 采集配置已生效 with each device's 启用, and maintenance. A refused request
is never recorded as accepted (R-1-5).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from par_app.application.acquisition import AcquisitionService
from par_app.application.errors import InstanceLocked
from par_app.application.events import EventHub
from par_app.application.paths import AlphaPaths
from par_app.domain.clock import BEIJING_TZ, FakeClock

pytestmark = [pytest.mark.unit]
WAIT = 5.0


class Backend:
    """Stands in for the Qt host: start is refused or accepted, a save is accepted."""

    def __init__(self, service: AcquisitionService, refuse: bool) -> None:
        self.service, self.refuse = service, refuse

    def start(self, allowed: Callable[[], None]) -> None:
        allowed()
        if self.refuse:
            self.service.cache.set_takeover("released", False, "串口正被其他程序占用（例如旧版光谱仪软件）")
            raise InstanceLocked("串口正被其他程序占用（例如旧版光谱仪软件）")
        self.service.cache.set_takeover("running", True)

    def request_stop(self, then: Callable[[], None] | None = None) -> None:
        self.service.cache.begin("running", "stopping")

    def apply_config(self, payload: Mapping[str, Any]) -> None:
        return None


def _service(tmp_path: Path, refuse: bool = False) -> AcquisitionService:
    service = AcquisitionService(
        AlphaPaths(tmp_path / "alpha"), FakeClock(datetime(2026, 10, 28, 16, 0, tzinfo=BEIJING_TZ)), EventHub()
    )
    service.tiers.write(1)
    service.attach(Backend(service, refuse))  # type: ignore[arg-type]
    return service


def _rows(service: AcquisitionService) -> list[dict[str, Any]]:
    assert service.run_events.flush(WAIT)
    path = service.run_events.path
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_refused_start_is_requested_then_refused_with_the_page_reason_never_accepted(tmp_path: Path) -> None:
    service = _service(tmp_path, refuse=True)
    with pytest.raises(InstanceLocked):
        service.start()
    actions = [(row["details"]["phase"], row["message"]) for row in _rows(service) if row["kind"] == "action"]
    assert actions[0] == ("requested", "开始采集：已请求")
    assert actions[-1] == ("refused", "开始采集：未执行，串口正被其他程序占用（例如旧版光谱仪软件）")
    assert "accepted" not in [phase for phase, _ in actions if _.startswith("开始采集")]
    service.run_events.close()


def test_start_stop_and_save_show_the_request_and_what_took_effect(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.start()
    service.save_config(
        {
            "bus": {},
            "devices": [
                {"name": "North", "slave_id": 1, "enabled": True},
                {"name": "South", "slave_id": 3, "enabled": False},
            ],
        }
    )
    service.cache.set_devices(
        [{"key": "North", "name": "North", "slave_id": 1, "enabled": True, "message": ""}], 40.0, True
    )
    service.cache.set_maintenance(True)
    service.stop()
    rows = _rows(service)
    lines = [row["message"] for row in rows]
    assert lines.index("开始采集：已请求") < lines.index("正在开始采集") < lines.index("采集已开始")
    assert lines.index("采集已开始") < lines.index("开始采集：已受理")
    save = next(row for row in rows if row["message"] == "保存并应用配置：已请求")
    assert [(item["name"], item["enabled"]) for item in save["details"]["devices"]] == [
        ("North", True),
        ("South", False),
    ]
    applied = next(row for row in rows if row["message"] == "采集配置已生效")
    assert applied["details"]["devices"] == [{"name": "North", "slave_id": 1, "enabled": True}]
    assert "设备维护未完成，采集暂停" in lines
    assert lines[-2:] == ["正在停止采集", "停止采集：已受理"]
    sequences = [row["sequence"] for row in rows]
    assert sequences == sorted(sequences) == list(range(1, len(rows) + 1))
    service.run_events.close()


def test_the_status_reports_how_the_event_log_is_doing(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.start()
    assert service.run_events.flush(WAIT)
    health = service.status()["event_log"]
    assert health["session"] == service.run_events.session and health["dropped"] == health["failed"] == 0
    assert health["written"] >= 3
    service.run_events.close()


def test_the_configuration_a_start_runs_with_is_recorded_as_in_effect(tmp_path: Path) -> None:
    """review of PR #144: a start (also the automatic one) applies the saved configuration without
    config_applied; the reset of the cache records it."""
    service = _service(tmp_path)
    devices = [
        {"key": "North", "name": "North", "slave_id": 1, "enabled": True, "message": ""},
        {"key": "South", "name": "South", "slave_id": 3, "enabled": False, "message": ""},
    ]
    service.cache.reset(("warning", "正在连接 COM6 …"), devices, False, 40.0, True)
    applied = next(row for row in _rows(service) if row["message"] == "采集配置已生效")
    assert [(item["name"], item["enabled"]) for item in applied["details"]["devices"]] == [
        ("North", True),
        ("South", False),
    ]
    assert applied["details"]["poll_cycle_seconds"] == 40.0
    service.run_events.close()
