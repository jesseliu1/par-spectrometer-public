"""导出诊断包 (D-226; api-contract-v0 API-27): one zip the business partner can send to support after a field test.

Written like the other alpha exports (D-207, D-210): into the alpha's own output folder, <data dir>/exports/diagnostics,
under a new name each time (PAR_diagnostics_<北京时间>.zip); the API takes no path. The zip is first written as
"<name>.partial" and renamed when complete, so a half-written file never carries the final name. Contents: see
diagnostics_content.README. Nothing is written anywhere else: device databases are opened read only, configuration
and logs are read as files, and no device is contacted (the status comes from the service's cache).

The zip is written entry by entry while it is read (diagnostics_content.BundleWriter): tables are streamed in chunks,
every text is redacted on its way in (redaction.py), and the whole bundle is never held in memory.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sqlite3
import sys
import threading
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any

from ..domain.clock import Clock
from ..models import safe_database_filename
from . import bundle_schema as schema
from . import diagnostics_bus, diagnostics_events
from . import diagnostics_content as content
from .acquisition import AcquisitionService
from .device_audit import DeviceDatabase, config_path, device_databases, read
from .errors import ApplicationError, Busy, ExportFailed
from .maintenance_log import COLUMNS, SCAN_ROWS, MaintenanceLogQueries
from .paths import AlphaPaths
from .redaction import DATA_DIR_MARK, Redactor, program_folder
from .snapshots import Snapshot, SnapshotStore
from .timefmt import beijing_iso

FOLDER = "diagnostics"
EVENT_FILES = re.compile(r"events(\.\d+)?\.jsonl")
NAME = "PAR_diagnostics_{stamp}{suffix}.zip"
STAMP_FORMAT = "%Y%m%d_%H%M%S"
BUILD_MANIFEST = "build_manifest.json"
BUSY_TEXT = "另一次诊断包导出正在进行，请稍候"
DONE_TEXT = (
    "已保存诊断包：{path}\n共 {count} 个文件。诊断包供我方开发人员内部排查：配置与库内设置只导出已知字段；"
    "日志只做了尽力去除令牌、密码与本机路径，不能保证完全去除。发到公司外部前请先打开看一眼"
    "（包内含现场经纬度与设备序列号，见包内 README.txt）。"
)
PROBLEMS_TEXT = "\n生成时遇到的问题（已写入包内 manifest.json）：\n{problems}"
FAILED_TITLE = "诊断包导出失败"
FAILED_TEXT = "保存目录：{directory}\n错误：{error}"
SOURCE_COLUMN = "来源"
NO_BUILD_MANIFEST = "未找到 build_manifest.json（开发环境运行，不是安装包）"
SCAN_LIMITED_PROBLEM = (
    "maintenance_log.csv 只扫描了每台设备最新 {rows} 条设备日志和 {rows} 条校准审计，"
    "更早记录未扫描，其中的写入未列入汇总；"
    "原始行全部在各设备的 maintenance_diagnostics.csv（通信参数）与 calibration_audit.csv（校准）中"
)
LOG_LIMIT_PROBLEM = (
    "maintenance_log.csv 只含最新 {limit} 条写入；更早的写入见各设备的 calibration_audit.csv 与 "
    "maintenance_diagnostics.csv"
)


@dataclass(frozen=True)
class DiagnosticsExported:
    path: str
    directory: str
    file_name: str
    size: int
    files: list[str]
    problems: list[str]
    text: str


@dataclass(frozen=True)
class ServiceInfo:
    version: str
    build_commit: str | None
    started_at: str


class DiagnosticsBundles:
    def __init__(
        self,
        paths: AlphaPaths,
        clock: Clock,
        acquisition: AcquisitionService,
        snapshots: SnapshotStore,
        log: MaintenanceLogQueries,
    ) -> None:
        self.paths = paths
        self.clock = clock
        self.acquisition = acquisition
        self.snapshots = snapshots
        self.log = log
        self._lock = threading.Lock()

    def export(self, service: ServiceInfo) -> DiagnosticsExported:
        if not self._lock.acquire(blocking=False):
            raise Busy(BUSY_TEXT)
        try:
            return self._export(service)
        finally:
            self._lock.release()

    def _export(self, service: ServiceInfo) -> DiagnosticsExported:
        redact = Redactor.for_paths(self.paths)
        problems: list[str] = []
        directory = self.paths.exports_dir / FOLDER
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = self._free_name(directory)
            names = self._write(target, redact, service, problems)
        except OSError as error:
            raise ExportFailed(FAILED_TITLE, FAILED_TEXT.format(directory=directory, error=error)) from error
        text = DONE_TEXT.format(path=target, count=len(names))
        if problems:
            text += PROBLEMS_TEXT.format(problems="\n".join(f"- {item}" for item in problems))
        return DiagnosticsExported(
            path=str(target),
            directory=str(directory),
            file_name=target.name,
            size=target.stat().st_size,
            files=sorted(names),
            problems=problems,
            text=text,
        )

    def _free_name(self, directory: Path) -> Path:
        stamp = self.clock.now().strftime(STAMP_FORMAT)
        index = 1
        while True:
            suffix = "" if index == 1 else f"_{index}"
            candidate = directory / NAME.format(stamp=stamp, suffix=suffix)
            if not candidate.exists() and not candidate.with_name(candidate.name + ".partial").exists():
                return candidate
            index += 1

    def _write(self, target: Path, redact: Redactor, service: ServiceInfo, problems: list[str]) -> list[str]:
        """Writes the zip as "<name>.partial" entry by entry, then renames it; returns the entry names."""
        partial = target.with_name(target.name + ".partial")
        try:
            with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                out = content.BundleWriter(archive, self.clock.now(), redact)
                summary = self._files(out, service, problems)
                manifest = self._manifest(service, [*out.names, "manifest.json"], problems)
                out.json("manifest.json", {**manifest, "maintenance_log": summary}, schema.MANIFEST)
            os.replace(partial, target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return out.names

    def _files(self, out: content.BundleWriter, service: ServiceInfo, problems: list[str]) -> dict[str, Any]:
        """Writes every entry but the manifest; returns the maintenance log's summary for it."""
        out.text("README.txt", content.readme())
        self._build_manifest(out, problems)
        self._logs(out, problems)
        self._guard(problems, "运行事件", lambda: diagnostics_events.write_events(out, self.acquisition, problems))
        self._guard(problems, "串口收发记录", lambda: diagnostics_bus.write_bus_trace(out, self.acquisition))
        self._configs(out, problems)
        devices = self._devices(problems)
        out.json("status.json", self._status(service, devices, problems), schema.STATUS)
        summary = self._maintenance_log(out, problems)
        for device in devices:
            self._device(out, device, problems)
        return summary

    @staticmethod
    def _guard(problems: list[str], what: str, action: Callable[[], None]) -> None:
        """Run one part of the bundle; a failure is listed in manifest.json and the rest still goes in. A failure
        of the zip itself (OSError while writing) is not caught here: the export fails as a whole."""
        try:
            action()
        except ApplicationError as error:
            problems.append(f"{what}：{error.message}" + (f"（{error.detail}）" if error.detail else ""))
        except (ValueError, sqlite3.Error) as error:
            problems.append(f"{what}：{type(error).__name__}: {error}")

    @staticmethod
    def _read_guard(problems: list[str], what: str, read_file: Callable[[], Any]) -> Any:  # noqa: ANN401
        """Read one source file; a failure is listed in manifest.json (None is returned) and the rest still goes in."""
        try:
            return read_file()
        except (OSError, ValueError) as error:
            problems.append(f"{what}：{type(error).__name__}: {error}")
            return None

    def _build_manifest(self, out: content.BundleWriter, problems: list[str]) -> None:
        folder = program_folder()
        path = None if folder is None else folder / BUILD_MANIFEST
        if path is None or not path.is_file():
            problems.append(NO_BUILD_MANIFEST)
            return
        text = self._read_guard(problems, BUILD_MANIFEST, lambda: path.read_text(encoding="utf-8"))
        if text is not None:
            try:
                out.json(BUILD_MANIFEST, json.loads(text), schema.BUILD_MANIFEST)
            except (ValueError, RecursionError):
                out.text(BUILD_MANIFEST, content.json_text(schema.OMITTED_FILE))

    def _logs(self, out: content.BundleWriter, problems: list[str]) -> None:
        folder = self.paths.logs_dir
        for path in sorted(folder.iterdir()) if folder.is_dir() else []:
            if not path.is_file() or EVENT_FILES.fullmatch(path.name):
                continue  # the run events go in reduced to their fields, under events/ (diagnostics_events)
            found: tuple[str, bool] | None = self._read_guard(
                problems, f"日志 {path.name}", partial(content.log_tail, path)
            )
            if found is not None:
                text, cut = found
                note = content.TRUNCATED_NOTE.format(limit=content.LOG_TAIL_BYTES) if cut else ""
                out.log(f"logs/{path.name}", text, note)

    def _configs(self, out: content.BundleWriter, problems: list[str]) -> None:
        """Each known configuration file through its allowlist (bundle_schema.CONFIG_FILES); any other file, or one
        that is not JSON, is written as "<omitted: unknown file>"."""
        folder = self.paths.config_dir
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            text: str | None = self._read_guard(
                problems, f"配置 {path.name}", partial(path.read_text, encoding=content.TEXT_ENCODING)
            )
            if text is None:
                continue
            known = schema.config_schema(path.name)
            try:
                value = json.loads(text) if known is not None else None
            except (ValueError, RecursionError):
                known = None
            if known is None:
                out.text(f"config/{path.name}", content.json_text(schema.OMITTED_FILE))
            else:
                out.json(f"config/{path.name}", value, known)

    def _devices(self, problems: list[str]) -> list[DeviceDatabase]:
        found: list[DeviceDatabase] = []

        def add() -> None:
            found.extend(device_databases(self.paths))

        self._guard(problems, f"设备登记 {config_path(self.paths).name}", add)
        return found

    def _status(self, service: ServiceInfo, devices: list[DeviceDatabase], problems: list[str]) -> dict[str, Any]:
        snapshots: list[dict[str, Any]] = []
        try:
            snapshots.extend(_snapshot(item) for item in self.snapshots.snapshots())
        except ApplicationError as error:
            problems.append(f"历史库快照清单：{error.message}" + (f"（{error.detail}）" if error.detail else ""))
        except (OSError, ValueError, sqlite3.Error) as error:
            problems.append(f"历史库快照清单：{type(error).__name__}: {error}")
        return {
            "as_of": beijing_iso(self.clock.now()),
            "service": asdict(service),
            "tier": asdict(self.acquisition.state()),
            "acquisition": self.acquisition.cache.snapshot(),
            "snapshots": snapshots,
            "devices": [
                {
                    "key": device.key,
                    "name": device.name,
                    "database": _shown_path(device),
                    "state": device.state()[0],
                    "problem": device.state()[1],
                }
                for device in devices
            ],
        }

    def _maintenance_log(self, out: content.BundleWriter, problems: list[str]) -> dict[str, Any]:
        """Every write but the time syncs (those are in each device's time_sync_events.csv), at most BUNDLE_LOG_ROWS;
        a limit reached or device-log rows left unscanned are named in the problems and the manifest (rv-63c 6)."""
        summary: dict[str, Any] = {}

        def add() -> None:
            log = self.log.collect(None, content.BUNDLE_LOG_ROWS, time_sync=False)
            summary.update(
                rows=len(log.items), limit=log.limit, limit_reached=log.limit_reached, scan_limited=log.scan_limited
            )
            if log.scan_limited:
                problems.append(SCAN_LIMITED_PROBLEM.format(rows=SCAN_ROWS))
            for state in log.devices:
                if state.problem is not None:
                    problems.append(f"维护记录 {state.key} {state.name}：{state.problem}")
            if log.limit_reached:
                problems.append(LOG_LIMIT_PROBLEM.format(limit=log.limit))
            out.csv(
                "maintenance_log.csv",
                [*COLUMNS, SOURCE_COLUMN],
                (
                    (
                        item.occurred_at_text,
                        item.device_name,
                        item.kind_text,
                        item.before_text,
                        item.after_text,
                        item.readback_text,
                        item.result_text,
                        item.detail,
                        item.source,
                    )
                    for item in log.items
                ),
            )

        self._guard(problems, "维护记录", add)
        return summary

    def _device(self, out: content.BundleWriter, device: DeviceDatabase, problems: list[str]) -> None:
        folder = f"devices/{device.key}_{safe_database_filename(device.name, 'device')}"
        state, problem = device.state()
        if state != "ok":
            out.text(f"{folder}/ERROR.txt", f"{problem}：{_shown_path(device)}\n")
            return
        try:
            read(device, lambda con: content.write_device(con, device.path, out, folder))
        except (ApplicationError, sqlite3.Error) as error:
            message = error.message if isinstance(error, ApplicationError) else f"{type(error).__name__}: {error}"
            detail = f"（{error.detail}）" if isinstance(error, ApplicationError) and error.detail else ""
            out.text(f"{folder}/ERROR.txt", f"{message}{detail}\n")
            problems.append(f"设备库 {device.key} {device.name}：{message}{detail}")

    def _manifest(self, service: ServiceInfo, names: list[str], problems: list[str]) -> dict[str, Any]:
        return {
            "generated_at": beijing_iso(self.clock.now()),
            "version": service.version,
            "build_commit": service.build_commit,
            "tier": self.acquisition.tier(),
            "data_dir": DATA_DIR_MARK,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "sqlite": sqlite3.sqlite_version,
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            "files": sorted(names),
            "problems": problems,
        }


def _shown_path(device: DeviceDatabase) -> str:
    """A database inside the alpha folder by its path (redacted to <DATA_DIR>/...), one outside by its file name only:
    an outside path often names the customer or site (PR #63 review m-2)."""
    return str(device.path) if device.inside else device.path.name


def _snapshot(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "key": snapshot.key,
        "name": snapshot.name,
        "file_name": snapshot.file_name,
        "source_name": Path(snapshot.source_path).name,
        "imported_at": snapshot.imported_at,
        "record_count": snapshot.record_count,
        "source_sha256": snapshot.source_after.sha256,
    }
