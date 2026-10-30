"""维护记录: a read-only list of every device write the device databases recorded (D-226; api-contract-v0 API-28).

Nothing is stored for it: each entry is rebuilt from what V1.0.3's code already writes into the device database, read
through a read-only connection (device_audit). The tables and rows, as the red-line code writes them:

  * 校准写入 - calibration_audit rows with action 'write' (PollingCoordinator: old, new and readback values, the
    MCU's status and error code; only a successful write is recorded there). A failed write leaves a diagnostics row
    of category 'calibration_write' (level ERROR, the error text) and nothing else: before, after and readback are
    "未记录". That ERROR row is also written when the coordinator refused the task before anything was sent (bus not
    connected, device disabled) and when the write was sent but the readback failed (the device may have changed),
    so "失败" means "not confirmed". A write cancelled midway (service stopped) or stopped by a hardware fault leaves
    no row at all (PollingCoordinator, red-line code): such a write is not in the list although the device may have
    taken it (PR #63 review M-3; NOTE says so).
  * 通信参数写入 / 通信参数核对 - diagnostics rows of category 'communication_maintenance' (CommunicationMaintenance):
    "开始维护操作" (action, connection used), "准备写入，结果必须使用新参数核对" (old, new, identity: written before
    the write command is sent), "维护操作完成" (action, result), and an ERROR row with the action on failure. A write
    is "待核对" from the moment it was prepared (V1.0.3 keeps it pending even when the command reported an error, the
    device may have taken it), "成功" once a later verification of that database passed, "失败" when it failed before
    anything was sent. The device's own readback of a write is the verification (its parameters and identity). The
    newest write stays "待核对" while app_settings.communication_maintenance still holds a pending write (V1.0.3 logs
    "维护操作完成" before it saves the verified state; if that save failed, V1.0.3 still asks for a verification,
    PR #63 review m-1).
  * 通信参数写入 (旧版记录) - connection_audit rows, if an older version left any (the current code writes none).
  * 设备对时 - time_sync_events (the coordinator's hourly time write); only on request (`time_sync`), since one row per
    device and hour would push the rare writes out of the list.

Refusals that never reach a database (the service's gates, the coordinator's "设备不可维护") are not in any table and
so not in the list.

Bounded reads (PR #63 reviews: major 2; re-review items 2 and 4; third review items 4 and 5): every query
walks the rowid (no MIN+MAX scan, no full-table sort), so the SQLite work does not grow with the history. The audit
tables give the newest limit + 1 + ROLLBACK_MARGIN_ROWS rows by id, sorted by time in Python with the final order
(a clock rollback is handled within that margin); calibration writes are looked for only among the newest
SCAN_ROWS calibration_audit rows (reads outnumber them; older rows: scan_limited). The device log is looked at only
within its newest SCAN_ROWS rows (older rows: scan_limited), only the rows of writes and verifications (parameter
reads are filtered out in SQL), in chunks of FETCH_ROWS rows, each a fresh fully fetched SELECT; a write whose start
lies before the window reads 待核对 (记录不完整), never 失败. The rows are interpreted newest first
(_CommunicationLog); only the newest entries are kept (_Newest), so memory follows the limit, not the history.
"""

from __future__ import annotations

import heapq
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Any, Literal

from ..database import BEIJING_TZ, format_beijing_time
from ..services.calibration import CALIBRATION_FIELDS
from .device_audit import DeviceDatabase, State, device_database, device_databases, read, rows, tables
from .errors import DatabaseUnavailable, InvalidArgument
from .paths import AlphaPaths
from .readonly import Row

DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
MS_PER_SECOND = 1000
NOT_RECORDED = "未记录"
TITLE = "维护记录"
NOTE = (
    "只读：来自设备库中校准审计、通信维护日志与对时记录（不新建任何存储）；最新在前。"
    "部分前置拒绝（如服务的模式与状态检查、协调器的“设备不可维护”）不留记录，不在此列。校准写入中途被取消（如停止服务）或因硬件异常停止时，"
    "软件不写任何记录，此列表也看不到，但设备可能已改，请读取校准核对；校准写入“失败”表示未确认写入成功，"
    "设备可能未改，也可能已改。"
)
EMPTY_TEXT = "没有设备写入记录"
NO_DEVICES_TEXT = "采集配置中还没有设备（开启采集模式并保存配置后，设备库在本软件的数据目录中建立）"
TIME_SYNC_LABEL = "包含设备对时（每台设备每小时一次）"
COLUMNS = ("时间", "设备", "类型", "写入前", "写入值", "回读", "结果", "说明")
LIMIT_TEXT = "只显示最新 {limit} 条"

Kind = Literal["calibration_write", "comm_write", "comm_verify", "time_sync"]
Result = Literal["success", "failure", "pending"]
KIND_TEXTS: dict[Kind, str] = {
    "calibration_write": "校准写入",
    "comm_write": "通信参数写入",
    "comm_verify": "通信参数核对",
    "time_sync": "设备对时",
}
LEGACY_COMM_TEXT = "通信参数写入（旧版记录）"
RESULT_TEXTS: dict[Result, str] = {"success": "成功", "failure": "失败", "pending": "待核对"}
PARITY_TEXTS = {"N": "无校验", "O": "奇校验", "E": "偶校验"}

MAINTENANCE = "communication_maintenance"
STARTED = "开始维护操作"
PREPARED = "准备写入，结果必须使用新参数核对"
FINISHED = "维护操作完成"
WRITE = "maintenance_write"
VERIFY = "maintenance_verify"
WRITE_ROWS = (
    "((category = 'calibration_write' AND level = 'ERROR') OR (category = 'communication_maintenance' AND "
    "(message = ? OR instr(details_json, '\"maintenance_write\"') > 0 "
    "OR instr(details_json, '\"maintenance_verify\"') > 0)))"
)
"""Only the rows of a write or a verification: a failed calibration write, a prepared write (no action field) and any
row whose action is maintenance_write / maintenance_verify; parameter reads (maintenance_read) are never fetched."""
DIAGNOSTICS_SQL = (
    "SELECT id, occurred_at, level, category, message, details_json FROM diagnostics "
    f"WHERE id < ? AND id > ? AND {WRITE_ROWS} ORDER BY id DESC LIMIT ?"
)
"""One chunk, newest first (keyset by id): each chunk is a fresh, fully fetched SELECT, so no read snapshot stays
open between chunks."""
NEWEST_ID_SQL = "SELECT MAX(id) FROM diagnostics"
OLDER_ROW_SQL = "SELECT id FROM diagnostics WHERE id <= ? ORDER BY id DESC LIMIT 1"
"""Separate rowid lookups (MAX alone and a rowid range seek are O(log n); MIN and MAX in one statement scan the whole
table, rv-63c item 4)."""
CALIBRATION_SQL = (
    "SELECT * FROM (SELECT * FROM calibration_audit ORDER BY id DESC LIMIT ?) "
    "WHERE action = 'write' ORDER BY id DESC LIMIT ?"
)
"""Calibration writes among the newest SCAN_ROWS audit rows by id: calibration reads outnumber writes, so the write
filter alone would walk the whole table (rv-63d item 1)."""
CALIBRATION_OLDER_SQL = "SELECT id FROM calibration_audit ORDER BY id DESC LIMIT 1 OFFSET ?"
"""Whether rows lie before that window (scan_limited)."""
CONNECTION_SQL = "SELECT * FROM connection_audit ORDER BY id DESC LIMIT ?"
TIME_SYNC_SQL = "SELECT * FROM time_sync_events ORDER BY id DESC LIMIT ?"
"""Candidates by rowid (no full-table sort, rv-63c item 4): the newest `limit` + 1 + ROLLBACK_MARGIN_ROWS rows by
id, then sorted by time in Python with the final order (_sort_key). A clock rollback is handled as long as the rows
written after it are fewer than ROLLBACK_MARGIN_ROWS; a newer-by-time row further back by id would be missed (the
trade-off for bounded work; rv-63b item 4)."""
ROLLBACK_MARGIN_ROWS = 500
"""Extra candidate rows per audit table beyond the limit, for a clock that went back."""
SESSION_SQL = "SELECT value_json FROM app_settings WHERE key = 'communication_maintenance'"
FETCH_ROWS = 200
"""Write-related device-log rows fetched per chunk."""
SCAN_ROWS = 100_000
"""How many of the newest device-log rows and of the newest calibration-audit rows (by id) are looked at per device;
older ones are not scanned and the response says so (scan_limited). A device offline for months writes about one
row per poll cycle."""
SCAN_LIMITED_TEXT = (
    "只扫描了每台设备最新 {rows} 条设备日志和 {rows} 条校准审计，更早记录未扫描，其中的写入未列出"
    "（诊断包 maintenance_diagnostics.csv 与 calibration_audit.csv 中有全部）"
)

SENT_PENDING = "写入命令已发出，须用新参数核对"
SENT_WITH_ERROR = "写入命令报错：{error}；设备可能已改参数，须用新参数核对"
VERIFIED = "已用新参数核对通过（{time}）"
STILL_PENDING = "设备库中的维护状态（app_settings.communication_maintenance）仍有待核对的写入，须用新参数核对"
NOT_SENT = "未发出写入：{error}"
INCOMPLETE = "记录不完整（超出扫描范围）：写入命令报错：{error}；之前的记录未扫描，设备可能已改参数，须用新参数核对"
CALIBRATION_DONE = "{detail}（状态码 {status}，错误码 {error}）"


@dataclass
class LogEntry:
    device_key: str
    device_name: str
    occurred_at: str
    kind: Kind
    kind_text: str
    before_text: str
    after_text: str
    readback_text: str
    result: Result
    detail: str
    source: str
    order: int = field(default=0, repr=False)

    @property
    def occurred_at_text(self) -> str:
        return format_beijing_time(self.occurred_at)

    @property
    def result_text(self) -> str:
        return RESULT_TEXTS[self.result]


@dataclass(frozen=True)
class DeviceLogState:
    key: str
    position: int
    name: str
    database_name: str
    state: State
    problem: str | None


@dataclass(frozen=True)
class MaintenanceLog:
    devices: list[DeviceLogState]
    items: list[LogEntry]
    limit: int
    limit_reached: bool
    time_sync: bool
    scan_limited: bool = False
    """Device-log rows older than SCAN_ROWS were not scanned on at least one device."""


def _parse(value: object) -> Any:  # noqa: ANN401 (stored JSON of any shape)
    if value is None:
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, RecursionError):
        return value


def _number(value: object) -> str:
    return format(value, "g") if isinstance(value, float) else str(value)


def connection_text(value: object) -> str:
    """'地址 7 · COM3 · 9600 bps · 无校验' for a ConnectionConfig dict; other values as stored."""
    if not isinstance(value, Mapping) or "slave_id" not in value:
        return NOT_RECORDED if value is None else json.dumps(value, ensure_ascii=False)
    parity = str(value.get("parity", ""))
    port = value.get("serial_port") or value.get("host") or "—"
    return f"地址 {value.get('slave_id')} · {port} · {value.get('baudrate')} bps · {PARITY_TEXTS.get(parity, parity)}"


def calibration_text(value: object) -> str:
    """'x_min=350, x_max=1050, …' in the editor's field order, then any other stored field."""
    if not isinstance(value, Mapping):
        return NOT_RECORDED if value is None else json.dumps(value, ensure_ascii=False)
    names = [name for name in CALIBRATION_FIELDS if name in value]
    names += [name for name in value if name not in CALIBRATION_FIELDS]
    return ", ".join(f"{name}={_number(value[name])}" for name in names)


def identity_text(identity: object) -> str:
    if not isinstance(identity, Mapping):
        return ""
    return f"设备 {identity.get('device_name', '—')} 序列号 {identity.get('serial_number', '—')}"


def _entry(device: DeviceDatabase, row: Row, kind: Kind, source: str, **fields: Any) -> LogEntry:  # noqa: ANN401
    values = {"before_text": NOT_RECORDED, "after_text": NOT_RECORDED, "readback_text": NOT_RECORDED, **fields}
    return LogEntry(
        device_key=device.key,
        device_name=device.name,
        occurred_at=str(row.get("occurred_at") or ""),
        kind=kind,
        kind_text=fields.pop("kind_text", KIND_TEXTS[kind]),
        before_text=values["before_text"],
        after_text=values["after_text"],
        readback_text=values["readback_text"],
        result=values["result"],
        detail=values["detail"],
        source=f"{source} #{row.get('id')}",
        order=int(row.get("id") or 0),
    )


def _calibration(device: DeviceDatabase, row: Row) -> LogEntry:
    detail = CALIBRATION_DONE.format(
        detail=row.get("detail") or "", status=row.get("status_code"), error=row.get("error_code")
    )
    return _entry(
        device,
        row,
        "calibration_write",
        "calibration_audit",
        before_text=calibration_text(_parse(row.get("old_json"))),
        after_text=calibration_text(_parse(row.get("new_json"))),
        readback_text=calibration_text(_parse(row.get("readback_json"))),
        result="success" if row.get("success") else "failure",
        detail=detail,
    )


class _CommunicationLog:
    """Turns the maintenance rows of one database, read newest first, into write and verify entries.

    Read backwards, each write takes its result from the nearest later verification that passed (V1.0.3 marks every
    write prepared since the last verification as verified by the next one that passes); a write error is held until
    its attempt's "准备写入" (the command was sent: still 待核对) or its "开始维护操作" (nothing was sent: 失败)."""

    def __init__(self, device: DeviceDatabase, session_pending: bool) -> None:
        self.device = device
        self.entries: list[LogEntry] = []
        self.next_verified: LogEntry | None = None
        """The nearest later verification that passed."""
        self.error: tuple[Row, str] | None = None
        """A write's error row whose attempt has not been reached yet."""
        self.session_pending = session_pending
        """app_settings still holds a pending write: the newest prepared write cannot be 成功."""
        self.newest_write_seen = False

    def add(self, row: Row) -> None:
        details = _parse(row.get("details_json"))
        details = details if isinstance(details, dict) else {}
        action, message = details.get("action"), str(row.get("message") or "")
        if row.get("category") == "calibration_write":
            if row.get("level") == "ERROR":
                self.entries.append(
                    _entry(self.device, row, "calibration_write", "diagnostics", result="failure", detail=message)
                )
            return
        if message == FINISHED and action == VERIFY:
            self._verified(row, details.get("result"))
        elif message == PREPARED and "old" in details and "new" in details:
            self._prepared(row, details)
        elif message == STARTED and action == WRITE:
            self._started(details)
        elif row.get("level") == "ERROR" and action == WRITE:
            if self.error is not None:
                self._not_sent(*self.error, NOT_RECORDED)
            self.error = (row, message)
        elif row.get("level") == "ERROR" and action == VERIFY:
            self.entries.append(
                _entry(self.device, row, "comm_verify", "diagnostics", result="failure", detail=message)
            )

    def finish(self, truncated: bool) -> None:
        """No older row was read. An error whose attempt start was not read: when the table has no older row it
        failed before anything was sent; when older rows were left unscanned its start is unknown, so it stays
        待核对 (记录不完整), never 失败 (rv-63c item 5)."""
        if self.error is None:
            return
        row, message = self.error
        self.error = None
        if not truncated:
            self._not_sent(row, message, NOT_RECORDED)
            return
        self.entries.append(
            _entry(
                self.device, row, "comm_write", "diagnostics", result="pending", detail=INCOMPLETE.format(error=message)
            )
        )

    def _prepared(self, row: Row, details: Mapping[str, Any]) -> None:
        detail = SENT_PENDING if self.error is None else SENT_WITH_ERROR.format(error=self.error[1])
        self.error = None
        result: Result = "pending"
        if not self.newest_write_seen and self.session_pending:
            detail = STILL_PENDING
        elif self.next_verified is not None:
            result, detail = "success", VERIFIED.format(time=self.next_verified.occurred_at_text)
        self.newest_write_seen = True
        self.entries.append(
            _entry(
                self.device,
                row,
                "comm_write",
                "diagnostics",
                before_text=connection_text(details.get("old")),
                after_text=connection_text(details.get("new")),
                result=result,
                detail=detail,
            )
        )

    def _started(self, details: Mapping[str, Any]) -> None:
        if self.error is not None:
            self._not_sent(*self.error, connection_text(details.get("connection")))
            self.error = None

    def _not_sent(self, row: Row, message: str, before: str) -> None:
        self.entries.append(
            _entry(
                self.device,
                row,
                "comm_write",
                "diagnostics",
                before_text=before,
                result="failure",
                detail=NOT_SENT.format(error=message),
            )
        )

    def _verified(self, row: Row, result: object) -> None:
        result = result if isinstance(result, Mapping) else {}
        readback = connection_text(result.get("connection"))
        identity = identity_text(result.get("identity"))
        entry = _entry(
            self.device,
            row,
            "comm_verify",
            "diagnostics",
            after_text=connection_text(result.get("connection")),
            readback_text=f"{readback}；{identity}" if identity else readback,
            result="success",
            detail=FINISHED,
        )
        self.entries.append(entry)
        self.next_verified = entry


def _legacy_connection(device: DeviceDatabase, row: Row) -> LogEntry:
    return _entry(
        device,
        row,
        "comm_write",
        "connection_audit",
        kind_text=LEGACY_COMM_TEXT,
        before_text=connection_text(_parse(row.get("old_config_json"))),
        after_text=connection_text(_parse(row.get("new_config_json"))),
        result="success" if row.get("success") else "failure",
        detail=str(row.get("detail") or ""),
    )


def _time_sync(device: DeviceDatabase, row: Row) -> LogEntry:
    stamp = row.get("mcu_time_ms")
    after = NOT_RECORDED
    if isinstance(stamp, int) and not isinstance(stamp, bool):
        try:
            moment = datetime.fromtimestamp(stamp / MS_PER_SECOND, BEIJING_TZ)
            after = f"设备时间 {format_beijing_time(moment)}"
        except (OverflowError, OSError, ValueError):
            after = f"mcu_time_ms={stamp}"
    return _entry(
        device,
        row,
        "time_sync",
        "time_sync_events",
        after_text=after,
        result="success" if row.get("success") else "failure",
        detail=str(row.get("detail") or ""),
    )


def _session_pending(con: sqlite3.Connection) -> bool:
    """Whether app_settings.communication_maintenance still holds a pending write (V1.0.3's own state)."""
    found = rows(con, SESSION_SQL)
    saved = _parse(found[0]["value_json"]) if found else None
    return isinstance(saved, Mapping) and bool(saved.get("pending"))


class _Newest:
    """The newest `size` entries by _sort_key, kept in a heap (memory bounded by the limit, not by the history)."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.heap: list[tuple[tuple[str, str, int], int, LogEntry]] = []
        self.counter = 0

    def add(self, entries: list[LogEntry]) -> None:
        for entry in entries:
            self.counter += 1
            item = (_sort_key(entry), self.counter, entry)
            if len(self.heap) < self.size:
                heapq.heappush(self.heap, item)
            elif item[0] > self.heap[0][0]:
                heapq.heapreplace(self.heap, item)
        entries.clear()

    def entries(self) -> list[LogEntry]:
        return [entry for _, _, entry in self.heap]


def _communication(
    device: DeviceDatabase, con: sqlite3.Connection, names: set[str], need: int
) -> tuple[list[LogEntry], bool]:
    """The newest `need` entries (by time) of the write rows among the newest SCAN_ROWS device-log rows, and whether
    older rows were left unscanned. Every write row in that window is interpreted (a rollback of the clock can make
    an older id newer in time); only `need` entries are kept."""
    communication = _CommunicationLog(device, "app_settings" in names and _session_pending(con))
    (high,) = con.execute(NEWEST_ID_SQL).fetchone()
    if high is None:
        return [], False
    floor = max(int(high) - SCAN_ROWS, 0)
    truncated = floor > 0 and con.execute(OLDER_ROW_SQL, (floor,)).fetchone() is not None
    newest, before = _Newest(need), int(high) + 1
    while True:
        cursor = con.execute(DIAGNOSTICS_SQL, (before, floor, PREPARED, FETCH_ROWS))
        try:
            chunk = cursor.fetchall()
        finally:
            cursor.close()
        for row in chunk:
            communication.add(dict(row))
        newest.add(communication.entries)
        if len(chunk) < FETCH_ROWS:
            break
        before = int(chunk[-1]["id"])
    communication.finish(truncated)
    newest.add(communication.entries)
    return newest.entries(), truncated


def device_entries(
    device: DeviceDatabase, con: sqlite3.Connection, time_sync: bool, limit: int
) -> tuple[list[LogEntry], bool]:
    """The newest `limit` + 1 write entries (by time) of each source of one database, and whether device-log rows
    were left unscanned (SCAN_ROWS)."""
    names = tables(con)
    need = limit + 1
    candidates = need + ROLLBACK_MARGIN_ROWS
    entries: list[LogEntry] = []
    limited = False
    if "calibration_audit" in names:
        entries += [_calibration(device, row) for row in rows(con, CALIBRATION_SQL, (SCAN_ROWS, candidates))]
        limited = con.execute(CALIBRATION_OLDER_SQL, (SCAN_ROWS,)).fetchone() is not None
    if "diagnostics" in names:
        found, scan_limited = _communication(device, con, names, need)
        limited = limited or scan_limited
        entries += found
    if "connection_audit" in names:
        entries += [_legacy_connection(device, row) for row in rows(con, CONNECTION_SQL, (candidates,))]
    if time_sync and "time_sync_events" in names:
        entries += [_time_sync(device, row) for row in rows(con, TIME_SYNC_SQL, (candidates,))]
    return entries, limited


def _device_reader(
    device: DeviceDatabase, time_sync: bool, limit: int, con: sqlite3.Connection
) -> tuple[list[LogEntry], bool]:
    return device_entries(device, con, time_sync, limit)


def _sort_key(entry: LogEntry) -> tuple[str, str, int]:
    """Newest first: time, then device, then row id (the SQL of every source orders the same way)."""
    return (entry.occurred_at, entry.device_key, entry.order)


def _newest_first(entries: list[LogEntry]) -> list[LogEntry]:
    return sorted(entries, key=_sort_key, reverse=True)


class MaintenanceLogQueries:
    def __init__(self, paths: AlphaPaths) -> None:
        self.paths = paths

    def log(self, key: str | None, limit: int = DEFAULT_LIMIT, time_sync: bool = False) -> MaintenanceLog:
        """Newest first, at most `limit`. With `key` a database that cannot be read (not created yet, outside the
        alpha folder, broken) is 503 database_unavailable; without, every registered device is read and one that
        cannot be read is named in `devices` (never shown as "no records")."""
        if not 1 <= limit <= MAX_LIMIT:
            raise InvalidArgument(f"limit 必须在 1–{MAX_LIMIT} 之间", str(limit))
        return self.collect(key, limit, time_sync)

    def collect(self, key: str | None, limit: int, time_sync: bool) -> MaintenanceLog:
        """`log` without the API's limit check (the diagnostics bundle asks for more rows than the page)."""
        devices = [device_database(self.paths, key)] if key is not None else device_databases(self.paths)
        states, entries, limited = [], [], False
        for device in devices:
            state, problem = device.state()
            if key is not None and not device.readable:
                raise DatabaseUnavailable(device.path.name, problem)
            if device.readable:
                try:
                    found, device_limited = read(device, partial(_device_reader, device, time_sync, limit))
                    entries += found
                    limited = limited or device_limited
                except DatabaseUnavailable as error:
                    if key is not None:
                        raise
                    state, problem = "unavailable", f"{error.message}（{error.detail}）"
            states.append(DeviceLogState(device.key, device.position, device.name, device.path.name, state, problem))
        ordered = _newest_first(entries)
        return MaintenanceLog(states, ordered[:limit], limit, len(ordered) > limit, time_sync, limited)
