"""History snapshots: import a V1.0.x database as a copy, list the copies, map them to device positions.

Import (API-20, internal notes 2.4 A, S-3): the source is never opened for writing and nothing is created beside
it (15_ 5.1). The copy goes into data/imported/<name>-<time>.sqlite of the alpha data directory. What is beside the
source decides how it is read:
  * At rest (no -wal / -journal, the usual case when V1.0.3 is closed): opened with `mode=ro&immutable=1`, so
    SQLite creates no -wal/-shm files next to it, and copied with the online backup API.
  * Anything else (a -wal or -journal beside it, with or without a -shm: V1.0.3 has it open, or crashed, was
    forced to stop or lost power; reviews M-2 and B-1): the database and its journal files are first copied byte
    for byte into the alpha's data/staging/ folder and the copy is read there, recovering the uncheckpointed
    records (a hot -journal is rolled back on the copy only). The source itself is never opened through SQLite:
    the mode is decided once, and if V1.0.3's last connection exited right after (deleting -wal and -shm), even a
    `mode=ro` connection would recreate them beside the source (review B-1). Byte-copying needs no write access,
    so this works in a read-only folder too.
In every case the size, modification time and SHA-256 of each file read are taken before and after; if any differ,
another program (V1.0.3) wrote meanwhile, the copy is discarded and the import answers busy (retry). Importing
while V1.0.3 is actively writing therefore needs a retry when a write lands mid-copy.
The copy is switched to journal_mode=DELETE so later read-only connections need no -wal/-shm files beside it.

Positions (tier 0, API-03): every snapshot is imported for one device position p1..p4; the newest snapshot of a
position is that device's history. V1.0.x configuration is not read (15_ 5.1), so the device name is the name
given at import (default: the source file name).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar

from ..domain.clock import Clock
from ..models import MAX_DEVICES, MAX_SAFE_FILENAME_LENGTH, safe_database_filename
from .errors import Busy, DatabaseUnavailable, DeviceNotFound, InvalidArgument
from .paths import AlphaPaths
from .readonly import connect_read_only, missing_history_tables
from .timefmt import beijing_iso

LOG = logging.getLogger(__name__)
T = TypeVar("T")
CHANGED_DURING_IMPORT = "源库在导入期间被其他程序（V1.0.3）修改，请稍后重新导入"
SNAPSHOT_SUFFIX = ".sqlite"
SIDECAR_SUFFIX = ".json"
PARTIAL_SUFFIX = ".partial"
FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
HASH_CHUNK_BYTES = 1 << 20
JOURNAL_SUFFIXES = ("-wal", "-journal")
SHARED_MEMORY_SUFFIX = "-shm"
STAGED_NAME = "source.sqlite3"
"""File name of the byte copy in data/staging/<temporary folder>/ (its -wal / -journal keep the same stem)."""
NAME_MAX_LENGTH = MAX_SAFE_FILENAME_LENGTH
"""Longest snapshot name accepted at import (the name also becomes the copy's file name)."""
DEVICE_KEYS = tuple(f"p{position}" for position in range(1, MAX_DEVICES + 1))


@dataclass(frozen=True)
class SourceFingerprint:
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class Snapshot:
    id: str
    name: str
    position: int
    file_name: str
    path: str
    source_path: str
    imported_at: str
    record_count: int
    source_before: SourceFingerprint
    source_after: SourceFingerprint

    @property
    def key(self) -> str:
        return f"p{self.position}"

    @property
    def source_changed_during_import(self) -> bool:
        return self.source_before != self.source_after


@dataclass(frozen=True)
class DeviceSlot:
    key: str
    position: int
    snapshot: Snapshot | None


def fingerprint(path: Path) -> SourceFingerprint:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    stat = path.stat()
    return SourceFingerprint(size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=digest.hexdigest())


def device_position(key: str) -> int:
    """p1..p4 -> 1..4; any other key is an invalid argument."""
    if key not in DEVICE_KEYS:
        raise InvalidArgument(f"设备位置无效：{key}（应为 {'、'.join(DEVICE_KEYS)}）")
    return DEVICE_KEYS.index(key) + 1


class ReadMode(Enum):
    AT_REST = "at_rest"
    LEFTOVER = "leftover"
    IN_USE = "in_use"


def _beside(source: Path, suffix: str) -> Path:
    return source.with_name(source.name + suffix)


def _journals(source: Path) -> list[Path]:
    return [path for suffix in JOURNAL_SUFFIXES if (path := _beside(source, suffix)).exists()]


def read_mode(source: Path) -> ReadMode:
    """How the import reads `source`, from the files beside it (see the module docstring)."""
    if not _journals(source):
        return ReadMode.AT_REST
    if _beside(source, SHARED_MEMORY_SUFFIX).exists():
        return ReadMode.IN_USE
    return ReadMode.LEFTOVER


def at_rest(source: Path) -> bool:
    """No -wal and no -journal beside the database: no other program has it open for writing right now."""
    return read_mode(source) is ReadMode.AT_REST


def _fingerprints(files: list[Path]) -> tuple[SourceFingerprint, ...]:
    return tuple(fingerprint(path) for path in files)


def _stage(files: list[Path], folder: Path) -> Path:
    """Byte copies of the database and its journals in `folder`; returns the staged database."""
    staged = folder / STAGED_NAME
    database = files[0]
    for path in files:
        shutil.copyfile(path, folder / (STAGED_NAME + path.name[len(database.name) :]))
    return staged


@contextmanager
def _staging_folder(paths: AlphaPaths) -> Iterator[Path]:
    paths.staging_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=paths.staging_dir) as folder:
        yield Path(folder)


def _siblings(source: Path) -> set[str]:
    return {path.name for path in source.parent.glob(f"{source.name}*")}


def _copy(source: Path, target: Path) -> int:
    """Online backup of a source at rest (read-only, immutable=1: SQLite creates nothing beside it) into target;
    returns the number of acquisitions in the copy.

    Errors while reading the source surface through connect_read_only as DatabaseUnavailable(source); errors on
    the copy name the copy (ruling 47: the path is the database that actually failed).
    """
    with connect_read_only(source, immutable=True) as src:
        return _backup(src, source, target)


def _copy_staged(staged: Path, source: Path, target: Path) -> int:
    """Online backup of the staged byte copy into target. The staged copy is the alpha's own file, so it is opened
    normally: SQLite recovers its -wal (or rolls back its -journal) there. Its errors name the source, of which it
    is an exact copy."""
    try:
        src = sqlite3.connect(staged)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(source), f"{type(error).__name__}: {error}") from error
    try:
        return _backup(src, source, target)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(source), f"{type(error).__name__}: {error}") from error
    finally:
        src.close()


def _backup(src: sqlite3.Connection, source: Path, target: Path) -> int:
    missing = missing_history_tables(src)
    if missing:
        raise InvalidArgument(f"所选文件不是 V1.0.x 历史库，缺少数据表：{'、'.join(sorted(missing))}", str(source))
    try:
        dst = sqlite3.connect(target)
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(target), f"{type(error).__name__}: {error}") from error
    try:
        try:
            src.backup(dst)
        except sqlite3.Error as error:
            # The backup reads the source and writes the copy interleaved; which file failed cannot be told from
            # the exception, so no path is named (ruling 47; review M-3).
            raise DatabaseUnavailable(None, f"{type(error).__name__}: {error}") from error
        return _finish_copy(dst, target)
    finally:
        dst.close()


def _finish_copy(dst: sqlite3.Connection, target: Path) -> int:
    try:
        dst.execute("PRAGMA journal_mode=DELETE")
        check = dst.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise DatabaseUnavailable(str(target), f"副本完整性检查未通过：{check}")
        return int(dst.execute("SELECT COUNT(*) FROM acquisitions").fetchone()[0])
    except sqlite3.Error as error:
        raise DatabaseUnavailable(str(target), f"{type(error).__name__}: {error}") from error


EXPORT_FOLDER_FALLBACK = "spectrometer"
"""The device folder of a name that is empty after cleaning (par_app.services.export.device_folder)."""


def export_folder(name: str) -> str:
    """The device folder an acquisition export writes into for this name (services.export.device_folder)."""
    return safe_database_filename(name, fallback=EXPORT_FOLDER_FALLBACK)


class SnapshotStore:
    """Imported snapshots in one alpha data directory; at most one import runs at a time (409 busy otherwise)."""

    def __init__(self, paths: AlphaPaths, clock: Clock) -> None:
        self.paths = paths
        self.clock = clock
        self._import_lock = threading.Lock()

    def import_snapshot(self, source_path: str, name: str | None = None, position: int = 1) -> Snapshot:
        source = Path(source_path).expanduser()
        if not source_path.strip() or not source.is_file():
            raise InvalidArgument(f"源库文件不存在：{source_path}")
        if position not in range(1, MAX_DEVICES + 1):
            raise InvalidArgument(f"设备位置无效：{position}（应为 1–{MAX_DEVICES}）")
        if not self._import_lock.acquire(blocking=False):
            raise Busy("已有快照导入正在进行，请稍后重试")
        try:
            self._refuse_duplicate_name(name or source.stem, position)
            return self._import(source.resolve(), name or source.stem, position)
        finally:
            self._import_lock.release()

    def _refuse_duplicate_name(self, name: str, position: int) -> None:
        """V1.0.3 refuses two devices with one name (device_hub: 设备名称不能为空或重复。); two positions with one
        name would also export into one device folder and overwrite each other's files (D-210 question 5). The
        folder is the name after safe_database_filename (A/B and A?B both give A_B) and Windows compares folder names
        without case, so a name whose folder another position already uses is refused as well (review #52
        item 6). The position being re-imported may keep its own name."""
        wanted = name.strip()
        folder = export_folder(wanted)
        for other, snapshot in sorted(_latest_per_position(self.snapshots()).items()):
            if other == position:
                continue
            if snapshot.name.strip() == wanted:
                raise InvalidArgument(
                    f"设备名称“{wanted}”已用于位置 {other}，不同位置不能同名（同 V1.0.3：设备名称不能为空或重复。）"
                )
            used = export_folder(snapshot.name)
            if used.casefold() == folder.casefold():
                raise InvalidArgument(
                    f"设备名称“{wanted}”与位置 {other} 的“{snapshot.name.strip()}”导出到同一个设备目录“{used}”，"
                    "不同位置不能共用设备目录（同 V1.0.3：设备名称不能为空或重复。）"
                )

    def _import(self, source: Path, name: str, position: int) -> Snapshot:
        try:
            self.paths.ensure()
        except OSError as error:
            raise DatabaseUnavailable(str(self.paths.data_dir), f"{type(error).__name__}: {error}") from error
        imported_at = self.clock.now()
        stem = self._free_stem(f"{safe_database_filename(name, 'snapshot')}-{imported_at.strftime(FILE_TIME_FORMAT)}")
        target = self.paths.imported_dir / f"{stem}{SNAPSHOT_SUFFIX}"
        partial = target.with_name(target.name + PARTIAL_SUFFIX)
        siblings = _siblings(source)
        try:
            count, before, after = self._copy_source(source, partial)
            _move(partial, target)
        finally:
            partial.unlink(missing_ok=True)
        snapshot = Snapshot(
            id=stem,
            name=name,
            position=position,
            file_name=target.name,
            path=str(target),
            source_path=str(source),
            imported_at=beijing_iso(imported_at),
            record_count=count,
            source_before=before,
            source_after=after,
        )
        try:
            self._write_sidecar(snapshot)
        except DatabaseUnavailable:
            target.unlink(missing_ok=True)  # a copy without its description would never be listed
            raise
        created = _siblings(source) - siblings
        if created:
            LOG.warning("SQLite left files beside the source database while reading it: %s", sorted(created))
        return snapshot

    def _copy_source(self, source: Path, partial: Path) -> tuple[int, SourceFingerprint, SourceFingerprint]:
        """Copy `source` into `partial` the way read_mode() says; returns the record count and the fingerprints of
        the database file before and after.

        Only a source at rest is opened through SQLite (immutable=1 creates nothing beside it); any source with
        journal files is byte-copied into staging and read there, so nothing can appear beside the source even
        when V1.0.3 exits right after the mode was decided (review B-1)."""
        mode = read_mode(source)
        files = [source] if mode is ReadMode.AT_REST else [source, *_journals(source)]
        before = _read_source(lambda: _fingerprints(files), source)
        if mode is ReadMode.AT_REST:
            count = _copy(source, partial)
            after = _read_source(lambda: _fingerprints(files), source)
            if after != before:
                raise Busy(CHANGED_DURING_IMPORT, str(source))
        else:
            with self._staging() as folder:
                staged = _read_source(lambda: _stage(files, folder), source)
                after = _read_source(lambda: _fingerprints(files), source)
                if after != before:
                    raise Busy(CHANGED_DURING_IMPORT, str(source))
                count = _copy_staged(staged, source, partial)
        return count, before[0], after[0]

    @contextmanager
    def _staging(self) -> Iterator[Path]:
        try:
            with _staging_folder(self.paths) as folder:
                yield folder
        except OSError as error:
            raise DatabaseUnavailable(str(self.paths.staging_dir), f"{type(error).__name__}: {error}") from error

    def _free_stem(self, stem: str) -> str:
        candidate, number = stem, 1
        while any(
            (self.paths.imported_dir / f"{candidate}{suffix}").exists() for suffix in (SNAPSHOT_SUFFIX, SIDECAR_SUFFIX)
        ):
            number += 1
            candidate = f"{stem}-{number}"
        return candidate

    def _write_sidecar(self, snapshot: Snapshot) -> None:
        sidecar = Path(snapshot.path).with_suffix(SIDECAR_SUFFIX)
        temporary = sidecar.with_name(sidecar.name + PARTIAL_SUFFIX)
        try:
            temporary.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, sidecar)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise DatabaseUnavailable(str(sidecar), f"{type(error).__name__}: {error}") from error

    def snapshots(self) -> list[Snapshot]:
        """All snapshot descriptions, newest import first. A description that cannot be read or parsed raises
        DatabaseUnavailable naming that file: imports write descriptions atomically, so a broken one is a fault to
        report, never an empty or shorter list (R-1-5; review M-1)."""
        if not self.paths.imported_dir.is_dir():
            return []
        found = [_load(path) for path in sorted(self.paths.imported_dir.glob(f"*{SIDECAR_SUFFIX}"))]
        return sorted(found, key=lambda snapshot: (snapshot.imported_at, snapshot.id), reverse=True)

    def devices(self) -> list[DeviceSlot]:
        latest = _latest_per_position(self.snapshots())
        return [
            DeviceSlot(key=key, position=index + 1, snapshot=latest.get(index + 1))
            for index, key in enumerate(DEVICE_KEYS)
        ]

    def snapshot_for(self, key: str) -> Snapshot:
        position = device_position(key)
        snapshot = _latest_per_position(self.snapshots()).get(position)
        if snapshot is None:
            raise DeviceNotFound(f"设备位置 {key} 还没有导入历史库快照")
        return snapshot


def _read_source(read: Callable[[], T], source: Path) -> T:
    """Run a file-level read of the source; a file gone meanwhile is busy (V1.0.3 started or stopped), any other
    OSError names the source (ruling 47)."""
    try:
        return read()
    except FileNotFoundError as error:
        raise Busy(CHANGED_DURING_IMPORT, str(source)) from error
    except OSError as error:
        raise DatabaseUnavailable(str(source), f"{type(error).__name__}: {error}") from error


def _move(partial: Path, target: Path) -> None:
    """Put the finished copy in place; an OSError names the copy, the file that actually failed (ruling 47)."""
    try:
        os.replace(partial, target)
    except OSError as error:
        raise DatabaseUnavailable(str(target), f"{type(error).__name__}: {error}") from error


def _latest_per_position(snapshots: Iterable[Snapshot]) -> dict[int, Snapshot]:
    latest: dict[int, Snapshot] = {}
    for snapshot in snapshots:  # newest first
        latest.setdefault(snapshot.position, snapshot)
    return latest


def _load(path: Path) -> Snapshot:
    """The snapshot a description file records; unreadable or corrupt is an explicit error (R-1-5, review M-1)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["source_before"] = SourceFingerprint(**data["source_before"])
        data["source_after"] = SourceFingerprint(**data["source_after"])
        return Snapshot(**data)
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise DatabaseUnavailable(str(path), f"{type(error).__name__}: {error}") from error
