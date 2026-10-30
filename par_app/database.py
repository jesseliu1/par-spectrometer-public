from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .models import ConnectionConfig


BEIJING_TZ = timezone(timedelta(hours=8), name="CST")


def beijing_now() -> str:
    """应用记录统一使用北京时间，不在界面或数据库中显示 UTC +00:00。"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def format_beijing_time(value: str | datetime | None) -> str:
    """兼容旧 UTC 记录，并将全部界面时间格式化为北京时间。"""
    if not value:
        return "—"
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(BEIJING_TZ).replace(tzinfo=None)
        return parsed.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except (TypeError, ValueError):
        return str(value)


def legacy_review_incomplete(quality_json: object) -> int:
    """D-126：旧记录（dli_eligible 为空）的 quality_json 是否标明“复核未完成”，是则返回 1。

    判断与历史详情显示“复核未完成”一致：quality_json 是 JSON 对象、confirmed 为 JSON false，且不是单采记录。
    空值、无法解析、不是对象、没有 confirmed 或取值不是 false，均视为没有复核信息，返回 0（照旧计入 DLI）。
    只在读取 DLI 样本时筛选，不改写数据库中的记录。
    """
    if not quality_json:
        return 0
    try:
        quality = json.loads(quality_json)  # type: ignore[arg-type]
    except (TypeError, ValueError, RecursionError):
        return 0
    if not isinstance(quality, dict) or quality.get("strategy") == "single_capture":
        return 0
    return int(quality.get("confirmed") is False)


# 计入 DLI 的记录：采集成功，且 dli_eligible 为 1；dli_eligible 为空的旧记录按 D-126 除去标明复核未完成的。
DLI_ELIGIBLE_SQL = (
    "success = 1 AND COALESCE(dli_eligible, 1) = 1 "
    "AND (CASE WHEN dli_eligible IS NULL THEN legacy_review_incomplete(quality_json) ELSE 0 END) = 0"
)


def _register_dli_functions(con: sqlite3.Connection) -> None:
    con.create_function("legacy_review_incomplete", 1, legacy_review_incomplete, deterministic=True)


class ParDatabase:
    """SQLite 是唯一持久化数据源；所有 UI 查询都经由此对象完成。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def initialize(self) -> None:
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_status (
                    id INTEGER PRIMARY KEY CHECK(id=1), level TEXT NOT NULL,
                    message TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS acquisitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    acquired_at TEXT NOT NULL, mcu_time_ms INTEGER,
                    success INTEGER NOT NULL, initialized INTEGER, need_power_cycle INTEGER,
                    raw_data_valid INTEGER, calculate_data_valid INTEGER, stop_status INTEGER,
                    spectral_coefficient INTEGER, exposure_status INTEGER, exposure_time_us INTEGER,
                    software_metrics_json TEXT, mcu_params_json TEXT, error_stage TEXT, error_detail TEXT,
                    elapsed_ms REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_acquisitions_time ON acquisitions(acquired_at DESC);
                CREATE TABLE IF NOT EXISTS spectra (
                    acquisition_id INTEGER PRIMARY KEY REFERENCES acquisitions(id) ON DELETE CASCADE,
                    raw_points_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diagnostics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
                    level TEXT NOT NULL, category TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_diagnostics_time ON diagnostics(occurred_at DESC);
                CREATE TABLE IF NOT EXISTS time_sync_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, success INTEGER NOT NULL,
                    mcu_time_ms INTEGER, detail TEXT
                );
                CREATE TABLE IF NOT EXISTS calibration_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, action TEXT NOT NULL,
                    success INTEGER NOT NULL, old_json TEXT, new_json TEXT, readback_json TEXT,
                    status_code INTEGER, error_code INTEGER, detail TEXT
                );
                CREATE TABLE IF NOT EXISTS connection_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, success INTEGER NOT NULL,
                    old_config_json TEXT, new_config_json TEXT, detail TEXT
                );
                CREATE TABLE IF NOT EXISTS dli_interruptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, reason TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_dli_interruptions_time ON dli_interruptions(occurred_at);
            """)
            columns = {row['name'] for row in con.execute('PRAGMA table_info(acquisitions)')}
            for name, definition in (('quality_json', 'TEXT'), ('dli_eligible', 'INTEGER')):
                if name not in columns:
                    con.execute(f'ALTER TABLE acquisitions ADD COLUMN {name} {definition}')

    def save_config(self, config: ConnectionConfig) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('connection',?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                        (json.dumps(config.to_dict(), ensure_ascii=False), beijing_now()))

    def load_config(self) -> ConnectionConfig:
        with self.connect() as con:
            row = con.execute("SELECT value_json FROM app_settings WHERE key='connection'").fetchone()
        return ConnectionConfig.from_dict(json.loads(row[0])) if row else ConnectionConfig()

    def save_par_device_identity(self, serial_number: int, device_type: int, device_name: str) -> None:
        value = json.dumps({"serial_number": serial_number, "device_type": device_type, "device_name": device_name}, ensure_ascii=False)
        with self.connect() as con:
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('par_device_identity',?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (value, beijing_now()))

    def load_par_device_identity(self) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT value_json FROM app_settings WHERE key='par_device_identity'").fetchone()
        try:
            return json.loads(row[0]) if row else None
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def save_dli_location(self, latitude: float, longitude: float) -> None:
        value = json.dumps({"latitude": latitude, "longitude": longitude})
        with self.connect() as con:
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_location',?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                        (value, beijing_now()))

    def load_dli_location(self) -> tuple[float, float]:
        """默认北京坐标；用户可在日累计光积分页修改为温室实际位置。"""
        with self.connect() as con:
            row = con.execute("SELECT value_json FROM app_settings WHERE key='dli_location'").fetchone()
        if not row:
            return 39.9042, 116.4074
        try:
            value = json.loads(row[0])
            return float(value["latitude"]), float(value["longitude"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return 39.9042, 116.4074

    def load_dli_enabled_at(self) -> str:
        """DLI 只使用正式启用后的无时区北京时间记录，旧数据仅保留审计用途。"""
        with self.connect() as con:
            row = con.execute("SELECT value_json FROM app_settings WHERE key='dli_enabled_at'").fetchone()
            if row:
                return str(json.loads(row[0]))
            enabled_at = beijing_now()
            con.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',?,?)",
                        (json.dumps(enabled_at), enabled_at))
            return enabled_at

    def peek_dli_enabled_at(self) -> str | None:
        """只读取 DLI 启用时间，缺失时不写入（未登记设备期间使用，D-163）。"""
        with self.connect() as con:
            row = con.execute("SELECT value_json FROM app_settings WHERE key='dli_enabled_at'").fetchone()
        return str(json.loads(row[0])) if row else None

    def save_dli_interruption(self, reason: str) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO dli_interruptions(occurred_at,reason) VALUES(?,?)", (beijing_now(), reason))

    def dli_minute_metrics(self, start: str, end: str, enabled_at: str) -> list[dict]:
        """按北京时间分钟平均正式 DLI 所需指标，不受原始采样频率和记录数量限制。"""
        sql = f"""
            SELECT substr(acquired_at, 1, 16) AS minute,
                   AVG(CAST(json_extract(software_metrics_json, '$.ppfd') AS REAL)) AS ppfd,
                   AVG(CAST(json_extract(software_metrics_json, '$.mccree_ypfd') AS REAL)) AS mccree_ypfd,
                   AVG(CAST(json_extract(software_metrics_json, '$.chlorophyll_a_ypfd') AS REAL)) AS chlorophyll_a_ypfd,
                   AVG(CAST(json_extract(software_metrics_json, '$.chlorophyll_b_ypfd') AS REAL)) AS chlorophyll_b_ypfd,
                   COUNT(*) AS samples
              FROM acquisitions
             WHERE acquired_at >= ? AND acquired_at < ? AND acquired_at >= ?
               AND software_metrics_json IS NOT NULL AND {DLI_ELIGIBLE_SQL}
               AND acquired_at NOT LIKE '%+%' AND acquired_at NOT LIKE '%Z'
             GROUP BY substr(acquired_at, 1, 16)
             ORDER BY minute
        """
        with self.connect() as con:
            _register_dli_functions(con)
            return [dict(row) for row in con.execute(sql, (start, end, enabled_at))]

    def dli_first_interruption(self, start: str, end: str, enabled_at: str) -> dict | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT occurred_at,reason FROM dli_interruptions WHERE occurred_at >= ? AND occurred_at < ? "
                "AND occurred_at >= ? ORDER BY occurred_at LIMIT 1", (start, end, enabled_at),
            ).fetchone()
        return dict(row) if row else None

    def dli_samples(self, start: str, end: str, enabled_at: str) -> list[dict]:
        with self.connect() as con:
            _register_dli_functions(con)
            rows = con.execute(
                "SELECT acquired_at AS timestamp, software_metrics_json, "
                f"CASE WHEN {DLI_ELIGIBLE_SQL} THEN 1 ELSE 0 END AS eligible "
                "FROM acquisitions WHERE acquired_at >= ? AND acquired_at < ? AND acquired_at >= ? "
                "AND acquired_at NOT LIKE '%+%' AND acquired_at NOT LIKE '%Z' "
                "UNION ALL SELECT occurred_at, NULL, 0 FROM dli_interruptions "
                "WHERE occurred_at >= ? AND occurred_at < ? AND occurred_at >= ? "
                "ORDER BY timestamp, eligible",
                (start, end, enabled_at, start, end, enabled_at),
            ).fetchall()
        return [dict(row) for row in rows]

    def diagnostic(self, level: str, category: str, message: str, **details: object) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO diagnostics(occurred_at,level,category,message,details_json) VALUES(?,?,?,?,?)",
                        (beijing_now(), level, category, message, json.dumps(details, ensure_ascii=False, default=str)))

    def set_runtime_status(self, level: str, message: str) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO runtime_status(id,level,message,updated_at) VALUES(1,?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET level=excluded.level,message=excluded.message,updated_at=excluded.updated_at",
                        (level, message, beijing_now()))

    def get_runtime_status(self) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT level,message,updated_at FROM runtime_status WHERE id=1").fetchone()
        return dict(row) if row else None

    def save_acquisition(self, record: dict) -> int:
        record = dict(record)
        if record.get("success") and record.get("mcu_params_json"):
            parameters = json.loads(record["mcu_params_json"])
            metrics = json.loads(record.get("software_metrics_json") or "{}")
            cct = parameters.get("cct")
            if isinstance(cct, (int, float)) and math.isfinite(cct) and cct >= 0:
                metrics["cct_kelvin"] = int(cct + .5)
            else:
                metrics["cct_kelvin"] = None
            record["software_metrics_json"] = json.dumps(metrics)
        fields = ("acquired_at", "mcu_time_ms", "success", "initialized", "need_power_cycle", "raw_data_valid",
                  "calculate_data_valid", "stop_status", "spectral_coefficient", "exposure_status", "exposure_time_us",
                  "software_metrics_json", "mcu_params_json", "error_stage", "error_detail", "elapsed_ms",
                  "quality_json", "dli_eligible")
        values = [record.get(field) for field in fields]
        with self.connect() as con:
            cur = con.execute(f"INSERT INTO acquisitions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", values)
            acquisition_id = int(cur.lastrowid)
            if record.get("raw_points") is not None:
                con.execute("INSERT INTO spectra(acquisition_id,raw_points_json) VALUES(?,?)",
                            (acquisition_id, json.dumps(record["raw_points"])))
        return acquisition_id

    def recent_acquisitions(self, limit: int = 200, start: str | None = None, end: str | None = None) -> list[dict]:
        where, params = [], []
        if start:
            where.append("acquired_at >= ?"); params.append(start)
        if end:
            where.append("acquired_at <= ?"); params.append(end)
        sql = "SELECT * FROM acquisitions" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as con:
            return [dict(row) for row in con.execute(sql, params)]

    def latest_successful_spectrum(self) -> tuple[dict, list[int]] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT a.*, s.raw_points_json FROM acquisitions a "
                "JOIN spectra s ON s.acquisition_id=a.id WHERE a.success=1 "
                "ORDER BY a.id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            record = dict(row)
            return record, json.loads(record.pop("raw_points_json"))

    def operation_spectra(self, limit: int = 500) -> list[dict]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT a.id,a.acquired_at FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id "
                "WHERE a.success=1 AND json_valid(s.raw_points_json) "
                "AND json_array_length(s.raw_points_json)=701 ORDER BY a.id DESC LIMIT ?", (limit,))
            return [dict(row) for row in rows]

    def nearest_operation_spectrum(self, acquired_at: str) -> dict | None:
        def timestamp(value):
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=BEIJING_TZ)
                return parsed.timestamp()
            except (TypeError, ValueError, OverflowError, OSError):
                return None

        with self.connect() as con:
            con.create_function("operation_timestamp", 1, timestamp, deterministic=True)
            row = con.execute(
                "SELECT a.id,a.acquired_at FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id "
                "WHERE a.success=1 AND json_valid(s.raw_points_json) "
                "AND json_array_length(s.raw_points_json)=701 "
                "AND operation_timestamp(a.acquired_at) IS NOT NULL AND operation_timestamp(?) IS NOT NULL "
                "ORDER BY ABS(operation_timestamp(a.acquired_at)-operation_timestamp(?)), "
                "operation_timestamp(a.acquired_at), a.id LIMIT 1",
                (acquired_at, acquired_at),
            ).fetchone()
        return dict(row) if row else None

    def acquisitions_for_export(self, start: str, end: str) -> list[dict]:
        """导出指定时间段的完整采集记录（含原始光谱），不使用界面展示用的条数限制。

        LEFT JOIN spectra 保证采集失败/无光谱的记录也能导出；每条记录的
        raw_points_json 为 701 点原始光谱数组（无光谱时为 None）。
        """
        with self.connect() as con:
            rows = con.execute(
                "SELECT a.*, s.raw_points_json FROM acquisitions a "
                "LEFT JOIN spectra s ON s.acquisition_id = a.id "
                "WHERE a.acquired_at >= ? AND a.acquired_at <= ? ORDER BY a.acquired_at, a.id",
                (start, end),
            )
            return [dict(row) for row in rows]


    def acquisition_export_count(self, start: str, end: str) -> int:
        with self.connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS count FROM acquisitions WHERE acquired_at >= ? AND acquired_at <= ?",
                (start, end),
            ).fetchone()
        return int(row["count"])

    def acquisition_summary(self) -> dict:
        with self.connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS total, MAX(acquired_at) AS latest FROM acquisitions"
            ).fetchone()
        return {"total": int(row["total"]), "latest": row["latest"]}

    def get_spectrum(self, acquisition_id: int) -> tuple[dict, list[int]] | None:
        with self.connect() as con:
            row = con.execute("SELECT a.*,s.raw_points_json FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id WHERE a.id=?", (acquisition_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        return data, json.loads(data.pop("raw_points_json"))

    def recent_diagnostics(self, limit: int = 300) -> list[dict]:
        with self.connect() as con:
            return [dict(row) for row in con.execute("SELECT * FROM diagnostics ORDER BY id DESC LIMIT ?", (limit,))]

    def save_time_sync(self, success: bool, mcu_time_ms: int | None, detail: str) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO time_sync_events(occurred_at,success,mcu_time_ms,detail) VALUES(?,?,?,?)", (beijing_now(), success, mcu_time_ms, detail))

    def save_calibration(self, **data: object) -> None:
        with self.connect() as con:
            con.execute("""INSERT INTO calibration_audit(occurred_at,action,success,old_json,new_json,readback_json,status_code,error_code,detail)
              VALUES(?,?,?,?,?,?,?,?,?)""", (beijing_now(), data.get("action"), data.get("success"),
                json.dumps(data.get("old"), ensure_ascii=False), json.dumps(data.get("new"), ensure_ascii=False),
                json.dumps(data.get("readback"), ensure_ascii=False), data.get("status"), data.get("error"), data.get("detail")))
