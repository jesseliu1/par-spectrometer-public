"""The top bar's run status (issue #73): V1.0.3's "总线：… ｜ 采集…" block and its red failure lines.

V1.0.3 builds them in MainWindow._on_bus_state (the bus summary and its colour, the bus message as tooltip) and
MainWindow._refresh_communication_events (the acquisition state and its colour; one line per enabled device with
failures). `run_status` derives the same from the state cache, which holds what those slots read: the bus line,
the halt, maintenance, whether the configuration was confirmed and every device's snapshot. It only reads; it
changes nothing in acquisition, retry or failure stop.

Each part also carries the `notice` ({event_id, occurred_at}) of the run event its message came from (#136): the bus
line the bus's or, during a halt, the halt's; the acquisition state the halt's (the other states are summaries of
the devices, whose failure lines carry their own, in `failure_notices`, one per line); None when there is none.

Not V1.0.3 (issue #131, owner 2026-10-28): when every enabled device has failed and none answers (also when all
of them left this run after failure stop), the bus line reads 总线：异常 in red with BUS_DEVICES_SILENT as its
detail. V1.0.3 keeps 已连接 because the port is open (between rounds the coordinator also reconnects, so it reads
连接中…), which looked normal on site. Only some devices
silent keeps the bus line; the acquisition state then says 部分设备异常. That line is a summary of the devices, so it
carries no notice of its own; the failure lines carry theirs. ALPHA_TEXTS lists texts that are not V1.0.3's.

Not carried over: V1.0.3's "正在停止通信…" / "正在停止采集：等待当前通信结束" while its device maintenance window
waits to enter maintenance (the alpha's maintenance page shows that state itself; D-227 item 4).

The texts are V1.0.3's word for word; `SOURCES` names the V1.0.3 function of each, and
tests/acquisition/test_run_status.py checks every literal part against that function's string constants. Colours
become the levels the web UI maps to its tokens: V1.0.3 green ok, amber warn, red error, slate muted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..database import format_beijing_time

MAIN_WINDOW = "par_app/ui.py"

BUS = "总线：{summary}"
BUS_HALTED_RESUME = "已停止（恢复未确认）"
BUS_HALTED_HARDWARE = "已停止（硬件异常）"
BUS_MAINTENANCE = "已暂停（维护模式）"
BUS_CONNECTING_PREFIX = "正在连接"
BUS_CONNECTING = "连接中…"
BUS_WAITING = "等待连接"
BUS_LEVELS = {"ok": "已连接", "warning": "等待 / 暂停", "error": "异常"}
BUS_OTHER = "未连接"
ACQUISITION_MAINTENANCE = "采集停止中：设备维护模式"
ACQUISITION_UNCONFIGURED = "等待配置，尚未采集"
ACQUISITION_NO_DEVICE = "采集停止中：无可采集设备，重启软件后重新尝试"
ACQUISITION_PARTLY = "采集运行中：部分设备异常"
ACQUISITION_NORMAL = "正常采集"
ACQUISITION_WAITING = "采集运行中：等待设备响应"
FAILURE_LINE = "{stamp}  {name}（地址 {slave_id}）  {message}"
BUS_DEVICES_SILENT = "所有启用的设备都不响应，将继续按周期重试"
ALPHA_TEXTS = {"BUS_DEVICES_SILENT": "issue #131"}

SOURCES: dict[str, tuple[str, str]] = {
    "BUS": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_HALTED_RESUME": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_HALTED_HARDWARE": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_MAINTENANCE": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_CONNECTING_PREFIX": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_CONNECTING": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_WAITING": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_LEVELS": (MAIN_WINDOW, "_on_bus_state"),
    "BUS_OTHER": (MAIN_WINDOW, "_on_bus_state"),
    "ACQUISITION_MAINTENANCE": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_UNCONFIGURED": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_NO_DEVICE": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_PARTLY": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_NORMAL": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_WAITING": (MAIN_WINDOW, "_refresh_communication_events"),
    "FAILURE_LINE": (MAIN_WINDOW, "_refresh_communication_events"),
}

_BUS_COLOURS = {"ok": "ok", "warning": "warn", "error": "error"}
"""V1.0.3: ok #15803d, warning #b45309, error #dc2626, anything else #475569."""


def _bus(snapshot: Mapping[str, Any], enabled: list[Mapping[str, Any]]) -> dict[str, Any]:
    """MainWindow._on_bus_state (its maintenance-window branch excepted), and 异常 when no device answers (#131)."""
    level, message = str(snapshot["bus"]["level"]), str(snapshot["bus"]["message"])
    halt = snapshot.get("halt")
    if halt is None and not snapshot.get("maintenance") and level != "error" and _all_silent(enabled):
        return {
            "text": BUS.format(summary=BUS_LEVELS["error"]),
            "level": "error",
            "detail": BUS_DEVICES_SILENT,
            "devices_silent": True,
        }
    if halt is not None:
        level, message = "error", str(halt.get("message"))
        summary = BUS_HALTED_RESUME if halt.get("resume_unconfirmed") else BUS_HALTED_HARDWARE
    elif snapshot.get("maintenance"):
        level, summary = "warning", BUS_MAINTENANCE
    elif level == "warning" and message.startswith(BUS_CONNECTING_PREFIX):
        summary = BUS_CONNECTING
    elif level == "idle" and snapshot.get("configured"):
        summary = BUS_WAITING
    else:
        summary = BUS_LEVELS.get(level, BUS_OTHER)
    notice = halt.get("notice") if halt is not None else snapshot["bus"].get("notice")
    return _noticed(
        {"text": BUS.format(summary=summary), "level": _BUS_COLOURS.get(level, "muted"), "detail": message}, notice
    )


def _all_silent(enabled: list[Mapping[str, Any]]) -> bool:
    """Every enabled device has failed and none answers, also when all of them left this run after failure stop."""
    return bool(enabled) and all(device.get("failures", 0) and not device.get("online", False) for device in enabled)


def _noticed(part: dict[str, Any], notice: object) -> dict[str, Any]:
    """`part` with its `notice` when there is one (the API answers null otherwise)."""
    return part if notice is None else {**part, "notice": notice}


def _acquisition(snapshot: Mapping[str, Any], enabled: list[Mapping[str, Any]], failing: bool) -> dict[str, str]:
    """MainWindow._refresh_communication_events: the acquisition state and its colour."""
    halt = snapshot.get("halt")
    if halt is not None:
        return _noticed({"text": str(halt.get("message")), "level": "error"}, halt.get("notice"))
    if snapshot.get("maintenance"):
        return {"text": ACQUISITION_MAINTENANCE, "level": "error"}
    if not snapshot.get("configured"):
        return {"text": ACQUISITION_UNCONFIGURED, "level": "muted"}
    if not enabled or all(device.get("excluded", False) for device in enabled):
        return {"text": ACQUISITION_NO_DEVICE, "level": "error"}
    if any(device.get("online", False) for device in enabled):
        return {"text": ACQUISITION_PARTLY if failing else ACQUISITION_NORMAL, "level": "ok"}
    return {"text": ACQUISITION_WAITING, "level": "warn"}


def run_status(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """The bus summary, the acquisition state and the failure lines for a StatusCache snapshot."""
    enabled = [device for device in snapshot["devices"] if device.get("enabled")]
    failing = [device for device in enabled if device.get("failures", 0)]
    failures = [
        FAILURE_LINE.format(
            stamp=format_beijing_time(device.get("last_failure_at")),
            name=device.get("name"),
            slave_id=device.get("slave_id"),
            message=device.get("message"),
        )
        for device in failing
    ]
    return {
        "bus": _bus(snapshot, enabled),
        "acquisition": _acquisition(snapshot, enabled, bool(failures)),
        "failures": failures,
        "failure_notices": [device.get("notice") for device in failing],
    }
