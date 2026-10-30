"""Read-only SQLite access (internal notes 5.2–5.3).

Every connection opened here uses the URI form `file:<path>?mode=ro`: SQLite then refuses any write, cannot create
the database file and does not create tables or columns. ParDatabase is not used, because its constructor writes
(CREATE TABLE, ALTER TABLE ADD COLUMN, journal_mode=WAL).

The history queries repeat the SQL of ParDatabase.recent_acquisitions / get_spectrum (V1.0.3) with the paging the
API adds (OFFSET, one extra row to detect a further page); tests/api/test_readonly_history.py runs both against
the same database and compares the rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from ..database import BEIJING_TZ, DLI_ELIGIBLE_SQL, legacy_review_incomplete
from .errors import DatabaseUnavailable

BUSY_TIMEOUT_SECONDS = 10.0
"""Same lock wait as ParDatabase.connect (sqlite3.connect timeout=10)."""
SQLITE_MAX_INTEGER = 2**63 - 1
"""Largest SQLite INTEGER (64-bit signed). Larger ids or offsets cannot be bound as parameters (OverflowError), so
the API refuses them as invalid arguments (review N-2)."""
HISTORY_TABLES = frozenset({"acquisitions", "spectra"})
MISSING_FILE = "设备库文件不存在（保存配置并开始采集后建立）"
"""A device database the configuration names but the acquisition has not created (yet)."""

Row = dict[str, Any]


WINDOWS_EXTENDED_UNC = "\\\\?\\UNC\\"
WINDOWS_EXTENDED = "\\\\?\\"
URI_WITH_AUTHORITY = "file://"


def file_uri(path: PurePath) -> str:
    """file: URI of an absolute path with an empty authority, as SQLite requires.

    Path.as_uri percent-encodes spaces and non-ASCII names. A Windows UNC path (a network share, or a mapped drive
    after resolve()) becomes file://server/share/..., which SQLite refuses ("invalid uri authority"); it is
    written as file:////server/share/... instead, which SQLite opens as //server/share/... (review Q-3). Extended
    \\\\?\\ prefixes are dropped first, since as_uri cannot express them.
    """
    if isinstance(path, PureWindowsPath):
        text = str(path)
        if text.startswith(WINDOWS_EXTENDED_UNC):
            path = PureWindowsPath("\\\\" + text[len(WINDOWS_EXTENDED_UNC) :])
        elif text.startswith(WINDOWS_EXTENDED):
            path = PureWindowsPath(text[len(WINDOWS_EXTENDED) :])
    uri = path.as_uri()
    if uri.startswith(URI_WITH_AUTHORITY) and not uri.startswith(URI_WITH_AUTHORITY + "/"):
        uri = URI_WITH_AUTHORITY + "//" + uri[len(URI_WITH_AUTHORITY) :]
    return uri


def read_only_uri(path: Path, immutable: bool = False) -> str:
    """file: URI with mode=ro (and immutable=1 when asked), see file_uri.

    immutable=1 makes SQLite skip locking and the -wal/-shm files altogether. Only safe while no other program
    writes the file; the snapshot import uses it for a database at rest and checks the file did not change.
    """
    return f"{file_uri(path.resolve())}?mode=ro{'&immutable=1' if immutable else ''}"


@contextmanager
def connect_read_only(path: Path, immutable: bool = False) -> Iterator[sqlite3.Connection]:
    """Read-only connection; any sqlite3 error while opening or reading becomes DatabaseUnavailable(path)."""
    try:
        con = sqlite3.connect(read_only_uri(path, immutable), uri=True, timeout=BUSY_TIMEOUT_SECONDS)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    con.row_factory = sqlite3.Row
    try:
        yield con
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
    finally:
        con.close()


def missing_history_tables(con: sqlite3.Connection) -> set[str]:
    names = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return set(HISTORY_TABLES - names)


class SnapshotHistory:
    """History queries on one snapshot copy."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _checked(self) -> Path:
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        return self.path

    def acquisitions(self, start: str, end: str, limit: int, offset: int) -> list[Row]:
        """Rows with start <= acquired_at <= end, newest id first; offset 0 is ParDatabase.recent_acquisitions."""
        sql = "SELECT * FROM acquisitions WHERE acquired_at >= ? AND acquired_at <= ? ORDER BY id DESC LIMIT ? OFFSET ?"
        with connect_read_only(self._checked()) as con:
            return [dict(row) for row in con.execute(sql, (start, end, limit, offset))]

    def acquisition(self, acquisition_id: int) -> Row | None:
        with connect_read_only(self._checked()) as con:
            row = con.execute("SELECT * FROM acquisitions WHERE id=?", (acquisition_id,)).fetchone()
        return dict(row) if row else None

    def spectrum(self, acquisition_id: int) -> object | None:
        """Decoded raw_points_json of the record, or None when it has no spectrum row (ParDatabase.get_spectrum)."""
        with connect_read_only(self._checked()) as con:
            row = con.execute(
                "SELECT raw_points_json FROM spectra WHERE acquisition_id=?", (acquisition_id,)
            ).fetchone()
        if row is None:
            return None
        decoded: object = json.loads(row["raw_points_json"])
        return decoded


DLI_OPTIONAL_COLUMNS = ("quality_json", "dli_eligible")
"""Columns ParDatabase.initialize adds to old databases (ALTER TABLE ADD COLUMN); a snapshot of a V1.0.0-era file
that V1.0.x never reopened lacks them. They read as NULL, exactly what the ALTER TABLE would have given."""


def _table_names(con: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _setting(con: sqlite3.Connection, key: str) -> tuple[bool, str | None]:
    """(present, value_json) of `key`; (False, None) when the key or the whole table (old databases) is missing.

    A present row can still hold SQL NULL (not in V1.0.x's own schema, where the column is NOT NULL, but a
    snapshot is an arbitrary file): V1.0.3 fails decoding it, so the caller must keep "present but NULL" apart
    from "missing" (PR #47 review N-4).
    """
    if "app_settings" not in _table_names(con):
        return False, None
    row = con.execute("SELECT value_json FROM app_settings WHERE key=?", (key,)).fetchone()
    return (False, None) if row is None else (True, row[0])


class SnapshotDli:
    """The DLI reads of ParDatabase (load_dli_location, peek_dli_enabled_at, dli_samples) on one snapshot copy.

    Same SQL, same eligibility predicate (par_app.database.DLI_ELIGIBLE_SQL with legacy_review_incomplete, D-126)
    and the same parsing; tests/api/test_readonly_dli.py runs both against the same database and compares. Nothing
    is written here; the DLI use case stores a missing enable time itself through dli_enable.store_enabled_at, as
    load_dli_enabled_at does (D-228 A).
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _checked(self) -> Path:
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        return self.path

    def location_value(self) -> str | None:
        """Stored dli_location JSON text (ParDatabase.load_dli_location parses it), None when not stored.

        A row stored as SQL NULL also reads as None: load_dli_location falls back to the default for both.
        """
        with connect_read_only(self._checked()) as con:
            return _setting(con, "dli_location")[1]

    def enabled_at_value(self) -> tuple[bool, str | None]:
        """(present, stored dli_enabled_at JSON text), for application.dli.parse_enabled_at.

        ParDatabase.peek_dli_enabled_at decodes the text; on a present row holding SQL NULL it raises, which the
        present flag lets the parser reproduce instead of reading "missing" (PR #47 review N-4).
        """
        with connect_read_only(self._checked()) as con:
            return _setting(con, "dli_enabled_at")

    def samples(self, start: str, end: str, enabled_at: str) -> list[Row]:
        """ParDatabase.dli_samples: records and interruptions in [start, end) from enabled_at on, time order."""
        with connect_read_only(self._checked()) as con:
            con.create_function("legacy_review_incomplete", 1, legacy_review_incomplete, deterministic=True)
            present = {str(row[1]) for row in con.execute("PRAGMA table_info(acquisitions)")}
            columns = ", ".join(
                name if name in present else f"NULL AS {name}"
                for name in ("acquired_at", "success", "software_metrics_json", *DLI_OPTIONAL_COLUMNS)
            )
            records = (
                "SELECT acquired_at AS timestamp, software_metrics_json, "
                f"CASE WHEN {DLI_ELIGIBLE_SQL} THEN 1 ELSE 0 END AS eligible "
                f"FROM (SELECT {columns} FROM acquisitions) "
                "WHERE acquired_at >= ? AND acquired_at < ? AND acquired_at >= ? "
                "AND acquired_at NOT LIKE '%+%' AND acquired_at NOT LIKE '%Z'"
            )
            parameters: tuple[str, ...] = (start, end, enabled_at)
            if "dli_interruptions" in _table_names(con):
                records += (
                    " UNION ALL SELECT occurred_at, NULL, 0 FROM dli_interruptions "
                    "WHERE occurred_at >= ? AND occurred_at < ? AND occurred_at >= ?"
                )
                parameters += (start, end, enabled_at)
            rows = con.execute(f"{records} ORDER BY timestamp, eligible", parameters).fetchall()
        return [dict(row) for row in rows]

    def poll_cycle_record(self, end: str, cutoff: str) -> Row | None:
        """acquired_at and quality_json of the latest successful record before `end` and at or before `cutoff`
        (zone-suffixed times excluded as in dli_samples), None when there is none (D-204 question 1 = D, D-206).

        No lower bound: a period without records takes the latest one before it. A V1.0.0-era table without
        quality_json reads the column as NULL. V1.0.3 has no such query: it takes the cycle from its configuration.
        """
        with connect_read_only(self._checked()) as con:
            present = {str(row[1]) for row in con.execute("PRAGMA table_info(acquisitions)")}
            quality = "quality_json" if "quality_json" in present else "NULL AS quality_json"
            row = con.execute(
                f"SELECT acquired_at, {quality} FROM acquisitions "
                "WHERE success = 1 AND acquired_at < ? AND acquired_at <= ? "
                "AND acquired_at NOT LIKE '%+%' AND acquired_at NOT LIKE '%Z' "
                "ORDER BY acquired_at DESC, id DESC LIMIT 1",
                (end, cutoff),
            ).fetchone()
        return dict(row) if row is not None else None

    def interruptions(self, start: str, end: str, enabled_at: str) -> list[Row]:
        """dli_interruptions rows in [start, end) from enabled_at on (the bounds of dli_samples), oldest first."""
        with connect_read_only(self._checked()) as con:
            if "dli_interruptions" not in _table_names(con):
                return []
            rows = con.execute(
                "SELECT occurred_at, reason FROM dli_interruptions WHERE occurred_at >= ? AND occurred_at < ? "
                "AND occurred_at >= ? ORDER BY occurred_at, id",
                (start, end, enabled_at),
            ).fetchall()
        return [dict(row) for row in rows]


OPERATION_SPECTRA_SQL = (
    "SELECT a.id,a.acquired_at FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id "
    "WHERE a.success=1 AND json_valid(s.raw_points_json) "
    "AND json_array_length(s.raw_points_json)=701 ORDER BY a.id DESC LIMIT ?"
)
"""ParDatabase.operation_spectra (V1.0.3), character for character."""
NEAREST_OPERATION_SQL = (
    "SELECT a.id,a.acquired_at FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id "
    "WHERE a.success=1 AND json_valid(s.raw_points_json) "
    "AND json_array_length(s.raw_points_json)=701 "
    "AND operation_timestamp(a.acquired_at) IS NOT NULL AND operation_timestamp(?) IS NOT NULL "
    "ORDER BY ABS(operation_timestamp(a.acquired_at)-operation_timestamp(?)), "
    "operation_timestamp(a.acquired_at), a.id LIMIT 1"
)
"""ParDatabase.nearest_operation_spectrum (V1.0.3), character for character: the whole database is searched (not
only the newest 500, UI-198), equal distances take the earlier time and then the smaller id (UI-200, D-151), and no
tolerance is applied (UI-288)."""


def operation_timestamp(value: object) -> float | None:
    """The SQL function of ParDatabase.nearest_operation_spectrum: seconds since the epoch, a plain time read as
    Beijing time and a zone-suffixed legacy time in its own zone (UI-197); None when unreadable."""
    try:
        parsed = datetime.fromisoformat(value)  # type: ignore[arg-type]  # SQLite passes any stored type
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BEIJING_TZ)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class SnapshotOperations:
    """The spectrum calculation reads of ParDatabase (operation_spectra, nearest_operation_spectrum, get_spectrum)
    on one snapshot copy; tests/api/test_readonly_operations.py runs both against the same database and compares."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _checked(self) -> Path:
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        return self.path

    def spectra(self, limit: int) -> list[Row]:
        """id and acquired_at of the newest `limit` successful records with a valid 701-point spectrum."""
        with connect_read_only(self._checked()) as con:
            return [dict(row) for row in con.execute(OPERATION_SPECTRA_SQL, (limit,))]

    def nearest(self, acquired_at: str) -> Row | None:
        """id and acquired_at of the usable record closest in time to `acquired_at`, None when there is none."""
        with connect_read_only(self._checked()) as con:
            con.create_function("operation_timestamp", 1, operation_timestamp, deterministic=True)
            row = con.execute(NEAREST_OPERATION_SQL, (acquired_at, acquired_at)).fetchone()
        return dict(row) if row else None

    def record(self, acquisition_id: int) -> tuple[Row, str] | None:
        """The acquisitions row and the stored raw_points_json text (ParDatabase.get_spectrum before decoding), None
        when the record or its spectrum row does not exist."""
        with connect_read_only(self._checked()) as con:
            row = con.execute(
                "SELECT a.*,s.raw_points_json FROM acquisitions a JOIN spectra s ON s.acquisition_id=a.id WHERE a.id=?",
                (acquisition_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        return data, data.pop("raw_points_json")


EXPORT_COUNT_SQL = "SELECT COUNT(*) AS count FROM acquisitions WHERE acquired_at >= ? AND acquired_at <= ?"
"""ParDatabase.acquisition_export_count (V1.0.3), character for character: the settings page's preview."""
EXPORT_ROWS_SQL = (
    "SELECT a.*, s.raw_points_json FROM acquisitions a "
    "LEFT JOIN spectra s ON s.acquisition_id = a.id "
    "WHERE a.acquired_at >= ? AND a.acquired_at <= ? ORDER BY a.acquired_at, a.id"
)
"""ParDatabase.acquisitions_for_export (V1.0.3), character for character: failed records and records without a
spectrum are exported too (D-127), oldest first."""
EXPORT_ROW_COUNT_SQL = (
    "SELECT COUNT(*) AS count FROM acquisitions a LEFT JOIN spectra s ON s.acquisition_id = a.id "
    "WHERE a.acquired_at >= ? AND a.acquired_at <= ?"
)
"""len(acquisitions_for_export(...)) without reading the spectra: the record count of V1.0.3's confirmation."""
SUMMARY_SQL = "SELECT COUNT(*) AS total, MAX(acquired_at) AS latest FROM acquisitions"
"""ParDatabase.acquisition_summary (V1.0.3), character for character."""


class SnapshotExport:
    """The settings page reads of ParDatabase (acquisition_export_count, acquisitions_for_export,
    acquisition_summary, load_par_device_identity) on one snapshot copy; tests/api/test_readonly_export.py runs
    both against the same database and compares."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _checked(self) -> Path:
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        return self.path

    def count(self, start: str, end: str) -> int:
        with connect_read_only(self._checked()) as con:
            row = con.execute(EXPORT_COUNT_SQL, (start, end)).fetchone()
        return int(row["count"])

    def row_count(self, start: str, end: str) -> int:
        with connect_read_only(self._checked()) as con:
            row = con.execute(EXPORT_ROW_COUNT_SQL, (start, end)).fetchone()
        return int(row["count"])

    def rows(self, start: str, end: str) -> list[Row]:
        with connect_read_only(self._checked()) as con:
            return [dict(row) for row in con.execute(EXPORT_ROWS_SQL, (start, end))]

    def summary(self) -> Row:
        with connect_read_only(self._checked()) as con:
            row = con.execute(SUMMARY_SQL).fetchone()
        return {"total": int(row["total"]), "latest": row["latest"]}

    def identity(self) -> Any:  # noqa: ANN401 - whatever JSON V1.0.x stored, as load_par_device_identity returns it
        """The stored device identity (decoded JSON), None when missing or unreadable (load_par_device_identity).

        A database V1.0.x never reopened may lack app_settings; ParDatabase would create it, the copy reads None.
        """
        with connect_read_only(self._checked()) as con:
            value = _setting(con, "par_device_identity")[1]
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None


RECENT_DIAGNOSTICS_SQL = "SELECT * FROM diagnostics ORDER BY id DESC LIMIT ?"
"""ParDatabase.recent_diagnostics (V1.0.3), character for character: the newest device log rows by id."""


class SnapshotDiagnostics:
    """The settings page's device log (ParDatabase.recent_diagnostics) on one device database, read only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def recent(self, limit: int) -> list[Row]:
        """The newest `limit` rows of the diagnostics table; none when the table is missing (a database V1.0.x
        never reopened: ParDatabase would create the table empty)."""
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        with connect_read_only(self.path) as con:
            if "diagnostics" not in _table_names(con):
                return []
            return [dict(row) for row in con.execute(RECENT_DIAGNOSTICS_SQL, (limit,))]


LATEST_ACQUISITION_SQL = "SELECT * FROM acquisitions ORDER BY id DESC LIMIT ?"
"""ParDatabase.recent_acquisitions(1) without a time range (V1.0.3), character for character: the newest record by
id, failed or not; refresh_overview reads it for "本轮失败" (UI-055) and the failed-only status (UI-054)."""
LATEST_SUCCESSFUL_SPECTRUM_SQL = (
    "SELECT a.*, s.raw_points_json FROM acquisitions a "
    "JOIN spectra s ON s.acquisition_id=a.id WHERE a.success=1 "
    "ORDER BY a.id DESC LIMIT 1"
)
"""ParDatabase.latest_successful_spectrum (V1.0.3), character for character: the record the overview shows
(UI-053)."""


class SnapshotOverview:
    """The overview reads of ParDatabase (recent_acquisitions(1), latest_successful_spectrum) on one snapshot copy;
    tests/api/test_readonly_overview.py runs both against the same database and compares."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _checked(self) -> Path:
        if not self.path.is_file():
            raise DatabaseUnavailable(str(self.path), MISSING_FILE)
        return self.path

    def latest(self) -> Row | None:
        with connect_read_only(self._checked()) as con:
            row = con.execute(LATEST_ACQUISITION_SQL, (1,)).fetchone()
        return dict(row) if row else None

    def latest_successful(self) -> tuple[Row, str] | None:
        """The row and the stored raw_points_json text (latest_successful_spectrum before json.loads), None when no
        successful record has a spectrum row. Decoding is left to the caller, so a broken spectrum does not hide
        the record's metrics."""
        with connect_read_only(self._checked()) as con:
            row = con.execute(LATEST_SUCCESSFUL_SPECTRUM_SQL).fetchone()
        if row is None:
            return None
        data = dict(row)
        return data, data.pop("raw_points_json")
