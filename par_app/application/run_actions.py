"""Texts and details of the run events the takeover records (issue #136; run_events.py writes them).

A request of the page is recorded as requested, then accepted or refused with the reason the page shows (`recorded`);
accepted is not yet in effect: the state cache records what took effect (the takeover's states, 采集配置已生效,
maintenance pausing or resuming) and every message it shows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from .errors import ApplicationError
from .run_events import RunEventLog

T = TypeVar("T")
HALT_DETAILS = ("reason", "occurred_at", "cycle", "resume_unconfirmed", "initialized", "need_power_cycle")
"""What a halt event keeps besides its message (the coordinator's halt_reason)."""
DEVICE_DETAILS = ("online", "failures", "excluded", "last_error", "last_failure_at", "latest_record_id", "enabled")
"""What a device event keeps besides its message (the coordinator's device snapshot)."""
TAKEOVER_TEXTS = {
    "released": "采集已停止，串口已释放",
    "starting": "正在开始采集",
    "running": "采集已开始",
    "stopping": "正在停止采集",
}
"""Run events of the takeover's states: what took effect, as against the request (#136 step 3)."""
CONFIG_APPLIED = "采集配置已生效"
MAINTENANCE_TEXTS = {True: "设备维护未完成，采集暂停", False: "维护结束，采集继续"}
ACTION_TEXTS = {
    "start": "开始采集",
    "auto_start": "启动服务后自动开始采集",
    "stop": "停止采集",
    "save_config": "保存并应用配置",
    "reconfigure": "以空配置重新配置",
    "set_tier": "切换模式",
}
"""Run events of the page's requests (#136 step 3): requested, then accepted or refused with the reason."""


def recorded(log: RunEventLog, name: str, run: Callable[[], T], **details: object) -> T:
    """Run one request of the page between its run events; a refused one is never recorded as accepted (R-1-5)."""
    text = ACTION_TEXTS[name]
    log.record("action", "info", f"{text}：已请求", None, action=name, phase="requested", **details)
    try:
        result = run()
    except ApplicationError as error:
        message = f"{text}：未执行，{error.message}"
        log.record(
            "action", "warning", message, None, action=name, phase="refused", code=error.code, detail=error.detail
        )
        raise
    except Exception as error:
        log.record(
            "action", "error", f"{text}：出错，{type(error).__name__}: {error}", None, action=name, phase="failed"
        )
        raise
    log.record("action", "info", f"{text}：已受理", None, action=name, phase="accepted")
    return result


def saved_devices(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """What a save asks for, device by device (the page's rows): name, address, 启用 and 失败停止."""
    rows = payload.get("devices")
    return [
        {name: row.get(name) for name in ("name", "slave_id", "enabled", "auto_stop_on_failure")}
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, Mapping)
    ]


def applied_config(devices: list[dict[str, Any]], poll: float | None, configured: bool | None) -> dict[str, Any]:
    """The details of 采集配置已生效: each device's name, address and 启用 as the coordinator runs them."""
    applied = [{name: device.get(name) for name in ("name", "slave_id", "enabled")} for device in devices]
    return {"devices": applied, "poll_cycle_seconds": poll, "configured": configured}
