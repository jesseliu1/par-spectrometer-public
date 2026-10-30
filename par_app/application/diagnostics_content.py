"""What goes into the diagnostics bundle (导出诊断包, D-226), file by file, and how it is written into the zip.

Everything is read, nothing is written but the zip: the alpha's own text files with plain reads, the device databases
through read-only connections (device_audit). Every text passes the Redactor (redaction.py: credentials, the alpha
data directory, the program folder, home folders and any other absolute path); structured data is scrubbed by key
before it is serialised, and every CSV cell before it is written.

Memory and read transactions stay bounded (PR #63 review majors 2-4): a log goes in with at most its last
LOG_TAIL_BYTES bytes read from the source (read(limit), so a log that grows meanwhile cannot exceed it; the note
added on a cut log and the redaction marks may make the zip entry slightly longer than that); a table is read in
chunks of FETCH_ROWS rows, each its own SELECT (keyset by rowid) fetched to the end and closed before its rows are
redacted and written, so a whole table is never held in memory and a read snapshot lasts one chunk, never a whole
table (PR #63 re-review item 3). The files of one device therefore come from many short snapshots: a row the
coordinator adds meanwhile may be in one file and not in another or in counts.json.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Any

from ..alpha_info import CONFIG_FILE_NAME, TIER1_CONFIG_FILE_NAME
from .bundle_schema import COUNTS, RUNTIME_STATUS, ListOf, allow, setting_row
from .device_audit import tables
from .maintenance_log import SCAN_ROWS
from .redaction import Redactor

LOG_TAIL_BYTES = 5_000_000
"""Each log file goes in with at most its last 5 MB read from the source file (a long-running service.log stays
small enough to e-mail); the cut note and redaction marks may add a few bytes to the zip entry."""
DIAGNOSTICS_ROWS = 2000
"""The newest rows of the general device log (communication errors come once per poll while a device is offline, so
2000 rows may cover only a day or two); the maintenance rows of the same table go in whole (MAINTENANCE_CATEGORIES)."""
TIME_SYNC_ROWS = 500
INTERRUPTION_ROWS = 500
RECENT_ACQUISITIONS = 50
"""Rows per device table: the newest ones; the audit tables (calibration_audit, connection_audit) go in whole."""
BUNDLE_LOG_ROWS = 5000
"""maintenance_log.csv: at most the newest 5000 writes (time syncs excluded); the raw rows of every write are in the
device folders in full (calibration_audit.csv, connection_audit.csv, maintenance_diagnostics.csv)."""
FETCH_ROWS = 500
"""Rows per chunk SELECT while a table is written into the zip (one short read snapshot each)."""
LOG_LINES_PER_CHUNK = 2000
"""Log lines redacted and written at a time."""
MAINTENANCE_CATEGORIES = ("communication_maintenance", "calibration_write", "comm_write")
"""diagnostics categories of device writes: CommunicationMaintenance's rows, a failed calibration write, and the
coordinator's error row of a failed communication write task."""
TRUNCATED_NOTE = "（日志较长，只保留最后 {limit} 字节；完整日志在 alpha 数据目录 logs 中）\n"
TEXT_ENCODING = "utf-8"
CSV_ENCODING = "utf-8-sig"
"""With a byte-order mark, as V1.0.3's CSV exports: Excel then opens the Chinese text correctly."""
ACQUISITION_COLUMNS = (
    "id",
    "acquired_at",
    "success",
    "initialized",
    "need_power_cycle",
    "raw_data_valid",
    "calculate_data_valid",
    "stop_status",
    "spectral_coefficient",
    "exposure_status",
    "exposure_time_us",
    "error_stage",
    "error_detail",
    "elapsed_ms",
    "quality_json",
    "dli_eligible",
)
"""The summary of recent records: state, exposure and errors only; no spectrum and no metrics (D-226)."""


def log_tail_bytes(handle: IO[bytes], limit: int = LOG_TAIL_BYTES) -> tuple[bytes, bool]:
    """At most the last `limit` bytes of an open log (from the first whole line), and whether it was cut. Reads at
    most `limit` bytes even when the log grows after its size was taken."""
    size = handle.seek(0, io.SEEK_END)
    handle.seek(max(0, size - limit))
    data = handle.read(limit)
    cut = size > limit
    if cut and b"\n" in data:
        data = data[data.index(b"\n") + 1 :]
    return data, cut


def log_tail(path: Path, limit: int = LOG_TAIL_BYTES) -> tuple[str, bool]:
    with path.open("rb") as handle:
        data, cut = log_tail_bytes(handle, limit)
    return data.decode("utf-8", errors="replace"), cut


def json_text(value: Any) -> str:  # noqa: ANN401 (any JSON value)
    return json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"


class BundleWriter:
    """Writes entries into an open zip one at a time, redacting as it goes; remembers the names written."""

    def __init__(self, archive: zipfile.ZipFile, moment: datetime, redact: Redactor) -> None:
        self.archive = archive
        self.stamp = (moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second)
        self.redact = redact
        self.names: list[str] = []

    @contextmanager
    def entry(self, name: str, encoding: str = TEXT_ENCODING) -> Iterator[IO[str]]:
        """Every entry carries the service clock's time (zipfile would otherwise read the system clock)."""
        info = zipfile.ZipInfo(name, date_time=self.stamp)
        info.compress_type = zipfile.ZIP_DEFLATED
        with self.archive.open(info, "w") as raw, io.TextIOWrapper(raw, encoding=encoding, newline="") as text:
            yield text
        self.names.append(name)

    def text(self, name: str, text: str) -> None:
        with self.entry(name) as out:
            out.write(self.redact(text))

    def json(self, name: str, value: Any, schema: Any) -> None:  # noqa: ANN401 (any JSON value, a bundle_schema)
        """Structured data through the allowlist (bundle_schema): only listed keys with listed types are kept."""
        self.raw(name, json_text(allow(value, schema, self.redact.structure)))

    def raw(self, name: str, text: str) -> None:
        """Text already reduced (allowlisted JSON whose strings were redacted one by one): a second pass over the
        serialised JSON could break its structure."""
        with self.entry(name) as out:
            out.write(text)

    def log(self, name: str, text: str, prefix: str = "") -> None:
        lines = text.splitlines(keepends=True)
        with self.entry(name) as out:
            out.write(prefix)
            for start in range(0, len(lines), LOG_LINES_PER_CHUNK):
                out.write(self.redact("".join(lines[start : start + LOG_LINES_PER_CHUNK])))

    def csv(self, name: str, columns: Sequence[str], records: Iterable[Sequence[Any]]) -> int:
        """Header and rows (UTF-8 with BOM); returns the number of rows."""
        count = 0
        with self.entry(name, CSV_ENCODING) as out:
            writer = csv.writer(out, lineterminator="\r\n")
            writer.writerow(columns)
            for record in records:
                writer.writerow(["" if value is None else self.redact.cell(value) for value in record])
                count += 1
        return count


def fetch_chunk(con: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """One short read: the SELECT is fetched to the end and its cursor closed before anything is written, so its read
    snapshot ends here (PR #63 re-review item 3)."""
    cursor = con.execute(sql, parameters)
    try:
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def table_rows(
    con: sqlite3.Connection, table: str, where: str = "", parameters: tuple[Any, ...] = (), newest: int | None = None
) -> Iterator[tuple[Any, ...]]:
    """The rows of `table` newest first (by rowid), at most `newest`: keyset pagination, one fresh SELECT of at most
    FETCH_ROWS rows per chunk, so no SELECT stays open while rows are redacted, compressed and written."""
    before: int | None = None
    left = newest
    while left is None or left > 0:
        size = FETCH_ROWS if left is None else min(FETCH_ROWS, left)
        conditions = [f"({where})"] if where else []
        arguments: list[Any] = list(parameters)
        if before is not None:
            conditions.append("rowid < ?")
            arguments.append(before)
        filtered = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        chunk = fetch_chunk(
            con, f"SELECT rowid, * FROM {table}{filtered} ORDER BY rowid DESC LIMIT ?", (*arguments, size)
        )
        for row in chunk:
            yield row[1:]
        if len(chunk) < size:
            return
        before = int(chunk[-1][0])
        if left is not None:
            left -= len(chunk)


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")]


DEVICE_TABLES: tuple[tuple[str, int | None], ...] = (
    ("calibration_audit", None),
    ("connection_audit", None),
    ("diagnostics", DIAGNOSTICS_ROWS),
    ("time_sync_events", TIME_SYNC_ROWS),
    ("dli_interruptions", INTERRUPTION_ROWS),
)


def write_device(con: sqlite3.Connection, database: Path, out: BundleWriter, folder: str) -> None:
    """The files of one device database into `folder` of the bundle; newest rows first."""
    names = tables(con)
    for table, newest in DEVICE_TABLES:
        if table in names:
            out.csv(f"{folder}/{table}.csv", _columns(con, table), table_rows(con, table, newest=newest))
    if "diagnostics" in names:
        marks = ", ".join("?" for _ in MAINTENANCE_CATEGORIES)
        out.csv(
            f"{folder}/maintenance_diagnostics.csv",
            _columns(con, "diagnostics"),
            table_rows(con, "diagnostics", f"category IN ({marks})", MAINTENANCE_CATEGORIES),
        )
    if "app_settings" in names:
        settings = [
            setting_row(key, _json_or_text(value), updated_at, out.redact.structure)
            for key, value, updated_at in fetch_chunk(
                con, "SELECT key, value_json, updated_at FROM app_settings ORDER BY key"
            )
        ]
        out.raw(f"{folder}/app_settings.json", json_text(settings))
    if "runtime_status" in names:
        columns = _columns(con, "runtime_status")
        status = [dict(zip(columns, row, strict=True)) for row in fetch_chunk(con, "SELECT * FROM runtime_status")]
        out.json(f"{folder}/runtime_status.json", status, ListOf(RUNTIME_STATUS))
    if "acquisitions" in names:
        present = set(_columns(con, "acquisitions"))
        columns = [name for name in ACQUISITION_COLUMNS if name in present]
        sql = f"SELECT {', '.join(columns)} FROM acquisitions ORDER BY id DESC LIMIT ?"
        out.csv(f"{folder}/acquisitions_recent.csv", columns, fetch_chunk(con, sql, (RECENT_ACQUISITIONS,)))
    counts = {table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in sorted(names)}
    out.json(
        f"{folder}/counts.json",
        {"database_name": database.name, "database_bytes": database.stat().st_size, "rows": counts},
        COUNTS,
    )


def _json_or_text(value: object) -> Any:  # noqa: ANN401
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, RecursionError):
        return value


README = """PAR 光谱仪 2.0.0-alpha 诊断包
================================

本诊断包由 alpha 的“设置与导出 → 导出诊断包”生成，供我方开发人员内部排查问题。生成时只读取文件和设备库
（设备库以只读方式打开），没有改动任何设备、配置或历史记录。

去除方式：
- 结构化数据（config/ 下的配置、各设备的 app_settings.json、status.json、counts.json、runtime_status.json、
  manifest.json）按允许清单导出：只保留已知的键和类型；未知的键只保留键名，值写作 <omitted: unknown key>，
  未知的设置写作 <omitted: unknown setting>，未知的配置文件写作 <omitted: unknown file>。
- 日志和表格中的文字只做尽力去除，不能保证完全去除：本机服务的令牌改为 <TOKEN>；名称以 password、secret、
  token、api_key、authorization、cookie 等结尾的键一旦后接“:”或“=”，该行其后的内容全部删除；Cookie、
  Authorization 头整行删除。发到公司外部前请先打开看一眼。

不包含的内容：
- 本机服务的令牌（service.json 不在包内；本机服务自己的日志从不写令牌）；
- 光谱数据和指标（只有最近 {recent} 条采集记录的状态摘要）；
- 历史库快照副本本身（只列出名称、导入时间、记录数和指纹）。
路径替换：alpha 数据目录写作 <DATA_DIR>，程序目录写作 <PROGRAM_DIR>，用户主目录（含其他用户目录、
8.3 短名写法）写作 <HOME>，其他 Windows 绝对路径（含 UNC、扩展长度 UNC 与 URL 编码写法）和 Python 报错行中的路径
只保留文件名，写作 <PATH>/文件名。其他写法的路径（如非 Windows 系统上日志正文中的绝对路径）可能仍在，
发送前请查看。
请注意，包内含有：各设备库 app_settings.json 中的现场经纬度（dli_location）与设备序列号，以及设备名称。

文件说明：
- README.txt：本说明。
- manifest.json：生成时间、alpha 版本、构建提交号、档位、操作系统与 Python/SQLite 版本、包内文件清单，
  以及生成时遇到的问题（如某台设备库无法读取）。
- build_manifest.json：安装包自带的构建清单（版本、提交号、依赖版本）；开发环境运行时没有此文件。
- status.json：生成时的状态快照：档位与接管状态、总线与各设备状态、维护状态、锁停原因、最近一次未预期异常，
  已导入的历史库快照清单，以及 alpha 配置中各设备库的状态。
- logs/：alpha 数据目录 logs 下的文件（本机服务日志 service.log；服务不轮转日志，文件会一直增长），运行事件
  events*.jsonl 除外（见 events/）；每个文件最多读取源文件最后 {log_limit} 字节（截断说明与替换标记可能使包内
  文件略长一些）。
- events/：运行事件（#136）。页面上的每条运行提示（总线、设备、锁停、开始失败）都带“记录号”，凭记录号在这里
  找到同一条：
  - events.jsonl：每行一条，只保留已知字段，详情经过同样的去除；记录号为“<运行会话>-<序号>”，先后看序号；
  - events.csv：同一批记录的表格（Excel 可直接打开）；以 = + - @ 开头的文字前加了 '，防止被当作公式；
  - integrity.json：完整性清单。cut 为导出时记下的截点，本次运行此后的记录不在包内；shown 列出导出时页面上
    每条提示的记录号以及它是否在文件中；文件里缺的（写盘排满、写盘失败、被截断）已从内存补上，标 source 为
    memory；complete 为 false 时 reasons 写明原因，manifest.json 的问题中也会写出。
- bus_trace/：串口收发记录（#136）。设备失败或锁停时，软件把内存中最近一段收发留存在该事件的记录号下：
  - <记录号>.jsonl：留存的一段；记录号与 events/ 和页面上的相同。第一行是这段的说明；transaction 行是每台设备
    从冻结到恢复确认的一次事务，first_problem 为第一处问题，resume_problem 为恢复命令之后的第一处问题；exchange
    行是每次发出的命令：步骤、从站、发出和收到多少字节、首字节和末字节在发出后多少毫秒、收到哪些帧（late_echo
    为晚到的回显）、该从站的有效帧数、结论（正常、无应答、应答不完整、异常应答、CRC 不符、从站或功能码不符、
    字节数不符、应答后有多余字节等）。只有长度与帧的种类，没有光谱、序列号等内容；
  - current.jsonl：导出时内存中的全部记录；index.json：各段清单。软件重启后内存中的记录不再有。
- config/：alpha 自己的配置文件：{tier1_config}（档位 1 的总线与设备登记，格式同 V1.0.3）、
  {settings_config}（档位设置），以及“以空配置重新配置”时留下的备份（如有）。
- maintenance_log.csv：维护记录（与页面“维护记录”相同，不含设备对时，最新 {log_rows} 条）：时间、设备、类型
  （校准写入、通信参数写入、通信参数核对）、写入前、写入值、回读、结果（成功/失败/待核对）、说明、
  来源（表名与行号）。库中没有保存的字段写作“未记录”。设备对时见各设备的 time_sync_events.csv。
  中途被取消或因硬件异常停止的校准写入，V1.0.3 不写任何记录，这里也看不到（设备可能已改）。
  每台设备只扫描最新 {scan_rows} 条设备日志和 {scan_rows} 条校准审计：更早记录未扫描时，manifest.json 的
  maintenance_log.scan_limited 为 true，problems 中写明“未扫描”，跨越扫描边界的写入记为“待核对（记录不完整）”；
  原始行见 maintenance_diagnostics.csv（通信参数）与 calibration_audit.csv（校准）。
- devices/<位置>_<设备名>/：alpha 配置中每台设备的设备库（只读）：
  - calibration_audit.csv：校准读取与写入的审计（全部行）：写入前、写入值、回读、MCU 状态码与错误码；
  - connection_audit.csv：旧版通信参数写入审计（全部行；当前版本不再写这张表，通常为空）；
  - diagnostics.csv：设备日志（最新 {diagnostics} 条），含通信维护（开始、准备写入、完成、失败）、读取诊断、
    对时失败、通信异常与恢复、硬件异常停止等；设备离线时每个采集周期都有一条，可能只覆盖一两天；
  - maintenance_diagnostics.csv：设备日志中与设备写入有关的全部行（类别 {categories}），
    不受上面条数限制，较早的写入也在这里；
  - time_sync_events.csv：设备对时记录（最新 {time_sync} 条）；
  - dli_interruptions.csv：DLI 中断记录（最新 {interruptions} 条）；
  - app_settings.json：库内设置，含 communication_maintenance（待核对写入与核对结果）、par_device_identity
    （设备身份与序列号）、connection、dli_location（现场经纬度）、dli_enabled_at；
  - runtime_status.json：库内运行状态；
  - acquisitions_recent.csv：最近 {recent} 条采集记录的状态摘要（成功与否、曝光、错误阶段与原因、耗时、
    quality_json），不含光谱与指标；
  - counts.json：库文件大小与各表行数；
  - ERROR.txt：该设备库无法读取时的原因（此时没有上面的文件）。
CSV 文件为 UTF-8（带 BOM），可直接用 Excel 打开；最新的行在前。各文件分别读取（每次一条查询），生成期间
设备仍在写入时，counts.json 的行数与各 CSV 可能相差几行。
"""


def readme() -> str:
    return README.format(
        recent=RECENT_ACQUISITIONS,
        log_limit=LOG_TAIL_BYTES,
        diagnostics=DIAGNOSTICS_ROWS,
        time_sync=TIME_SYNC_ROWS,
        interruptions=INTERRUPTION_ROWS,
        tier1_config=TIER1_CONFIG_FILE_NAME,
        settings_config=CONFIG_FILE_NAME,
        log_rows=BUNDLE_LOG_ROWS,
        scan_rows=SCAN_ROWS,
        categories="、".join(MAINTENANCE_CATEGORIES),
    )
