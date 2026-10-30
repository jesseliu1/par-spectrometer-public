"""Display texts of the maintenance page, computed the way V1.0.3's window computes them (17_ section 2, 6.3).

Pure functions over plain values: the diagnostics snapshot (DeviceMaintenanceDialog.task_finished and
display_diagnostics), the software event list, the identity summary of the communication tab
(MaintenanceDialog.display_identity) and the settings page's current communication values
(MainWindow._render_comm_values / _accept_settings_comm). The page only shows what these return.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ..domain.clock import BEIJING_TZ
from ..maintenance import BAUDRATES
from . import v1_texts as texts

COUNTER_SATURATED = 65535
"""DeviceMaintenanceDialog.task_finished: a saturated 16-bit counter has no reliable increment."""
EVENT_LIMIT = 100
"""DeviceMaintenanceDialog.display_diagnostics: the newest 100 software events."""
COMMUNICATION_ROWS = 8
"""The first eight error rows are communication counters (category 通信), the rest PAR counters."""


def snapshot_entry(payload: Mapping[str, Any], previous: Mapping[str, Any] | None, read_at: datetime) -> dict[str, Any]:
    """One successful diagnostics read: counts, the increment over the previous read of this page session (D-134 A),
    and the read time (DeviceMaintenanceDialog.task_finished)."""
    counts = list(payload["communication_errors"]) + list(payload["par_errors"])
    old = previous["counts"] if previous else None
    delta = [
        None if old is None or value < old[index] or value == COUNTER_SATURATED else value - old[index]
        for index, value in enumerate(counts)
    ]
    return {
        "payload": dict(payload),
        "counts": counts,
        "delta": delta,
        "read_at": read_at.astimezone(BEIJING_TZ).isoformat(timespec="seconds"),
    }


def _summary(data: Mapping[str, Any], historical: bool) -> dict[str, str]:
    payload = data["payload"]
    identity, status = payload["identity"], payload["status"]
    stamp = datetime.fromisoformat(data["read_at"]).strftime("%Y-%m-%d %H:%M:%S")
    temperature = payload["mcu_temperature_c"]
    temperature_text = f"{temperature:.2f} ℃" if math.isfinite(temperature) else "无效值"
    serial = f"{identity['serial_number']} (0x{identity['serial_number']:08X})"
    return {
        "stamp": (texts.HISTORICAL if historical else "") + texts.STAMP.format(time=stamp),
        "identity": texts.IDENTITY_LINE.format(
            name=identity["device_name"], serial=serial, type=identity["device_type"]
        ),
        "values": texts.VALUES_LINE.format(
            temperature=temperature_text,
            initialized="完成" if status["initialized"] else "未完成",
            power="是" if status["need_power_cycle"] else "否",
        ),
        "exposure": texts.EXPOSURE_LINE.format(
            exposure=texts.EXPOSURES.get(status["exposure_status"], "未知"),
            mode=texts.EXPOSURE_MODES.get(status["exposure_mode"], "未知"),
            time=f"{status['exposure_time_us'] / 1000:.1f}",
        ),
        "data": texts.DATA_LINE.format(
            raw="有效" if status["raw_data_valid"] else "无效",
            calculated="有效" if status["calculate_data_valid"] else "无效",
        ),
    }


def diagnostics_view(data: Mapping[str, Any] | None, failure: str | None, maintenance: bool) -> dict[str, Any]:
    """DeviceMaintenanceDialog.display_diagnostics and filter_errors, for the device the page shows."""
    historical = failure is not None or maintenance
    lines = {key: texts.NOT_READ_VALUE for key in ("identity", "values", "exposure", "data")}
    lines["stamp"] = texts.NOT_READ_STAMP + (texts.LAST_FAILURE.format(reason=failure) if failure is not None else "")
    if data:
        lines.update(_summary(data, historical))
    rows = []
    for index, name in enumerate(texts.COMMUNICATION_ERRORS + texts.PAR_ERRORS):
        delta = data["delta"][index] if data else None
        count = data["counts"][index] if data else None
        tooltip = texts.NOT_READ_TOOLTIP if not data else (texts.NO_DELTA_TOOLTIP if delta is None else "")
        rows.append(
            {
                "category": "通信" if index < COMMUNICATION_ROWS else "PAR",
                "name": name,
                "count": "—" if count is None else str(count),
                "delta": "—" if delta is None else str(delta),
                "zero": count == 0,
                "tooltip": tooltip,
            }
        )
    return {
        **lines,
        "has_snapshot": bool(data),
        "historical": historical,
        "rows": rows,
        "empty_text": texts.NO_NONZERO_HISTORICAL if historical else texts.NO_NONZERO,
    }


def _event_stamp(value: object) -> str:
    stamp = str(value or "")
    try:
        return datetime.fromisoformat(stamp).astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stamp


def _operation(event: Mapping[str, Any], details: Mapping[str, Any]) -> str:
    category = str(event.get("category", ""))
    operation = texts.EVENT_ACTIONS.get(str(details.get("action", "")))
    if operation:
        return operation
    operation = texts.EVENT_CATEGORIES.get(category, category)
    if category == "connection" and event.get("message") == texts.COMM_PARAMETERS_READ:
        operation = texts.EVENT_ACTIONS["maintenance_read"]
    if category == "communication_maintenance" and "old" in details and "new" in details:
        operation = texts.WRITE_OPERATION
    return operation


def event_rows(events: Sequence[Mapping[str, Any]], device_name: str, database: str) -> list[dict[str, Any]]:
    """The software event table and each row's 事件详情 (DeviceMaintenanceDialog.display_diagnostics and
    show_event_details)."""
    rows = []
    for event in events:
        try:
            details = json.loads(event.get("details_json") or "{}")
        except (ValueError, TypeError):
            details = {}
        if not isinstance(details, dict):
            details = {}
        level = str(event.get("level", ""))
        detail_event = {key: value for key, value in event.items() if key != "details_json"}
        detail_event["details"] = details
        rows.append(
            {
                "time": _event_stamp(event.get("occurred_at", "")),
                "level": texts.EVENT_LEVELS.get(level, level),
                "operation": _operation(event, details),
                "message": str(event.get("message", "")),
                "details": json.dumps(
                    {"device_name": device_name, "database": database, "event": detail_event},
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            }
        )
    return rows


def identity_lines(payload: Mapping[str, Any]) -> list[str]:
    """MaintenanceDialog.display_identity."""
    identity = payload.get("identity") or {}
    serial_number = identity.get("serial_number")
    serial_text = f"{serial_number} (0x{serial_number:08X})" if isinstance(serial_number, int) else texts.UNREAD
    lines = [
        texts.IDENTITY_DEVICE.format(
            name=identity.get("device_name", texts.UNREAD), type=identity.get("device_type", texts.UNREAD)
        ),
        texts.IDENTITY_SERIAL.format(serial=serial_text),
    ]
    for key, label in texts.IDENTITY_LABELS:
        connection = payload.get(key)
        if connection:
            lines.append(
                texts.IDENTITY_CONNECTION.format(
                    label=label,
                    serial_port=connection["serial_port"],
                    slave_id=connection["slave_id"],
                    baudrate=connection["baudrate"],
                    parity=connection["parity"],
                )
            )
    return lines


def comm_values(payload: object) -> tuple[int, int, int]:
    """MainWindow._accept_settings_comm: (address, baud rate, parity index) or ValueError with its text."""
    if not isinstance(payload, Mapping):
        raise ValueError(str(payload))
    try:
        address = int(payload["slave_id"])
        baud_index, parity_index = int(payload["baudrate_index"]), int(payload["parity_index"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(str(error)) from error
    if not 1 <= address <= 247 or not 0 <= baud_index < len(BAUDRATES) or not 0 <= parity_index < 3:  # noqa: PLR2004
        raise ValueError(texts.COMM_INVALID)
    return address, BAUDRATES[baud_index], parity_index
