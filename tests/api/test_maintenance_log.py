"""GET /api/v0/support/maintenance-log (API-28, D-226): every device write recorded in the alpha's device databases,
read only.

The rows are written with ParDatabase's own methods and the messages of PollingCoordinator / CommunicationMaintenance
(support_data); tests/acquisition/test_maintenance_flow.py checks the same log on rows the real code wrote.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.application import maintenance_log
from tests.api import support_data as data
from tests.api.conftest import error_of

pytestmark = pytest.mark.unit
LOG = "/api/v0/support/maintenance-log"
MAINTENANCE_SOURCE = Path(__file__).resolve().parents[2] / "par_app" / "maintenance.py"


@pytest.fixture
def data_dir(context: ServiceContext) -> Path:
    return context.paths.data_dir


@pytest.fixture
def north(data_dir: Path) -> Path:
    """North (p1) with a calibration read and write, a write verified, a write still pending, a failed write and a
    failed verification; South (p2) with one failed calibration write."""
    data.write_config(data_dir, ["North", "South"])
    database = data.device_database(data_dir, "North")
    data.calibration_read(database, "2026-10-19T09:00:00.000")
    data.calibration_write(database, "2026-10-19T09:01:00.000")
    data.comm_write(database, "2026-10-19T09:02:00.000")
    data.comm_verify(database, "2026-10-19T09:02:05.000")
    data.comm_write(database, "2026-10-19T09:03:00.000", prepared=False, error="设备身份与此前读取不一致，禁止写入")
    data.comm_write(database, "2026-10-19T09:04:00.000", error="写入超时")
    data.comm_verify(database, "2026-10-19T09:04:05.000", error="新参数下设备身份不一致，核对失败")
    data.time_sync(database, "2026-10-19T09:05:00.000")
    data.diagnostic(database, "2026-10-19T09:06:00.000", "INFO", "connection", "已读取设备当前通信参数", slave_id=1)
    south = data.device_database(data_dir, "South")
    data.diagnostic(south, "2026-10-19T09:01:30.000", "ERROR", "calibration_write", "写入校准失败，状态=4 错误=2")
    return database.path


def test_lists_every_write_newest_first_with_before_after_readback_and_result(client: TestClient, north: Path) -> None:
    response = client.get(LOG)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [(item["kind"], item["result_text"]) for item in body["items"]] == [
        ("comm_verify", "失败"),
        ("comm_write", "待核对"),
        ("comm_write", "失败"),
        ("comm_verify", "成功"),
        ("comm_write", "成功"),
        ("calibration_write", "失败"),
        ("calibration_write", "成功"),
    ]
    verify_failed, pending, refused, verified, written, south, calibration = body["items"]
    assert calibration["device_name"] == "North" and calibration["kind_text"] == "校准写入"
    assert calibration["before_text"] == "x_min=350, y1=-0.0123, sensor_id=1"
    assert calibration["after_text"] == "x_min=350, y1=-0.015"
    assert calibration["readback_text"].startswith("x_min=350, y1=-0.015")
    assert calibration["detail"] == "写入并回读光谱仪校准（状态码 3，错误码 0）"
    assert calibration["occurred_at_text"] == "2026-10-19 09:01:00.000"
    assert south["device_name"] == "South" and south["detail"] == "写入校准失败，状态=4 错误=2"
    assert (south["before_text"], south["after_text"], south["readback_text"]) == ("未记录",) * 3
    assert written["before_text"] == "地址 1 · COM7 · 9600 bps · 无校验"
    assert written["after_text"] == "地址 7 · COM7 · 9600 bps · 无校验"
    assert written["readback_text"] == "未记录"
    assert written["detail"] == "已用新参数核对通过（2026-10-19 09:02:05.000）"
    assert verified["readback_text"] == "地址 7 · COM7 · 9600 bps · 无校验；设备 PAR-FAKE 序列号 305419896"
    assert refused["detail"] == "未发出写入：设备身份与此前读取不一致，禁止写入"
    assert refused["after_text"] == "未记录" and refused["before_text"].startswith("地址 1")
    assert pending["detail"] == "写入命令报错：写入超时；设备可能已改参数，须用新参数核对"
    assert verify_failed["detail"] == "新参数下设备身份不一致，核对失败"
    assert [device["state"] for device in body["devices"]] == ["ok", "ok"]
    assert body["texts"]["columns"] == ["时间", "设备", "类型", "写入前", "写入值", "回读", "结果", "说明"]
    assert body["limit"] == 200 and not body["limit_reached"] and body["time_sync"] is False


def test_time_sync_only_on_request_and_filter_by_device(client: TestClient, north: Path) -> None:
    body = client.get(LOG, params={"device": "p1", "time_sync": "true"}).json()
    assert {item["device_key"] for item in body["items"]} == {"p1"}
    sync = body["items"][0]
    assert sync["kind"] == "time_sync" and sync["result_text"] == "成功" and sync["kind_text"] == "设备对时"
    assert sync["after_text"].startswith("设备时间 2025-10-19 09:30:00")
    assert [device["key"] for device in body["devices"]] == ["p1"]


def test_limit(client: TestClient, north: Path) -> None:
    body = client.get(LOG, params={"limit": 2}).json()
    assert len(body["items"]) == 2 and body["limit_reached"] and body["texts"]["limit_text"] == "只显示最新 2 条"
    assert error_of(client.get(LOG, params={"limit": 0}))["code"] == "invalid_argument"
    assert error_of(client.get(LOG, params={"limit": 1001}))["code"] == "invalid_argument"


def test_reads_without_writing(client: TestClient, north: Path, data_dir: Path) -> None:
    data.close_wal(north)
    before = data.fingerprint(data_dir)
    config = (data_dir / "config" / "app_config.json").read_bytes()
    assert client.get(LOG, params={"time_sync": "true"}).status_code == 200
    assert data.fingerprint(data_dir) == before
    assert (data_dir / "config" / "app_config.json").read_bytes() == config


def test_no_configuration_is_an_empty_list(client: TestClient) -> None:
    body = client.get(LOG).json()
    assert body["devices"] == [] and body["items"] == []
    assert body["texts"]["no_devices_text"].startswith("采集配置中还没有设备")


def test_database_not_created_yet_and_unknown_device(client: TestClient, data_dir: Path) -> None:
    data.write_config(data_dir, ["North"])
    body = client.get(LOG).json()
    assert body["items"] == []
    assert body["devices"][0]["state"] == "missing" and body["devices"][0]["problem"] == "设备库尚未建立（未采集过）"
    assert not (data_dir / "data" / "devices" / "North.sqlite3").exists()  # reading never creates it
    assert error_of(client.get(LOG, params={"device": "p3"}))["code"] == "device_not_found"


def test_database_outside_the_alpha_folder_is_not_opened(client: TestClient, data_dir: Path, tmp_path: Path) -> None:
    outside = data.device_database(tmp_path / "elsewhere", "North").path
    data.write_config(data_dir, ["North"], {"North": str(outside)})
    before = sorted(path.name for path in outside.parent.iterdir())
    body = client.get(LOG).json()
    assert body["devices"][0]["state"] == "outside"
    assert sorted(path.name for path in outside.parent.iterdir()) == before  # no -wal/-shm created beside it


def test_unreadable_database_is_named_not_shown_as_empty(client: TestClient, data_dir: Path) -> None:
    data.write_config(data_dir, ["North", "South"])
    data.calibration_write(data.device_database(data_dir, "North"), "2026-10-19T09:01:00.000")
    broken = data_dir / "data" / "devices" / "South.sqlite3"
    broken.write_bytes(b"not a database" * 100)
    body = client.get(LOG).json()
    assert [item["device_key"] for item in body["items"]] == ["p1"]
    assert body["devices"][1]["state"] == "unavailable" and "数据库不可访问" in body["devices"][1]["problem"]
    response = client.get(LOG, params={"device": "p2"})
    assert response.status_code == 503 and error_of(response)["code"] == "database_unavailable"


def test_unreadable_configuration(client: TestClient, data_dir: Path) -> None:
    (data_dir / "config").mkdir(parents=True)
    (data_dir / "config" / "app_config.json").write_text("{", encoding="utf-8")
    response = client.get(LOG)
    assert response.status_code == 409 and error_of(response)["code"] == "config_unavailable"


def test_needs_the_token(anonymous: TestClient) -> None:
    assert anonymous.get(LOG).status_code == 401


def test_messages_match_communication_maintenance() -> None:
    """The log recognises CommunicationMaintenance's rows by their messages (red-line code, not imported here)."""
    source = MAINTENANCE_SOURCE.read_text(encoding="utf-8")
    for message in ("开始维护操作", "准备写入，结果必须使用新参数核对", "维护操作完成"):
        assert re.search(rf'"{message}"', source), message


def test_named_device_without_a_readable_database_is_503(client: TestClient, data_dir: Path, tmp_path: Path) -> None:
    """API-28: with `device`, a database that cannot be read is 503 database_unavailable, also when it was never
    created or lies outside the alpha folder (PR #63 review major 5)."""
    outside = data.device_database(tmp_path / "elsewhere", "South").path
    data.write_config(data_dir, ["North", "South"], {"South": str(outside)})
    for key, problem in (("p1", "设备库尚未建立（未采集过）"), ("p2", "不在本软件数据目录")):
        response = client.get(LOG, params={"device": key})
        assert response.status_code == 503, response.text
        error = error_of(response)
        assert error["code"] == "database_unavailable" and error["retryable"] is True
        assert problem in error["detail"]
        assert str(tmp_path) not in error["message"]
    assert client.get(LOG).status_code == 200  # all devices: named in devices[], not an error


def test_write_still_pending_in_the_database_is_never_success(client: TestClient, data_dir: Path) -> None:
    """V1.0.3 logs "维护操作完成" before saving the verified state; when that save fails the pending write stays in
    app_settings.communication_maintenance and must be verified again (PR #63 review m-1)."""
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    data.comm_write(database, "2026-10-19T09:02:00.000")
    data.comm_verify(database, "2026-10-19T09:02:05.000")
    data.diagnostic(
        database,
        "2026-10-19T09:02:05.100",
        "ERROR",
        "communication_maintenance",
        "database is locked",
        device_name="North",
        action="maintenance_verify",
    )
    with database.connect() as con:
        con.execute(
            "INSERT INTO app_settings(key, value_json, updated_at) VALUES('communication_maintenance', ?, ?)",
            ('{"pending": {"old": {}, "new": {}, "identity": {}}, "verified": null}', "2026-10-19T09:02:05.000"),
        )
    items = client.get(LOG).json()["items"]
    write = next(item for item in items if item["kind"] == "comm_write")
    assert write["result"] == "pending" and "app_settings" in write["detail"]


def _many_rows(path: Path, count: int) -> None:
    """`count` calibration writes, `count` communication-maintenance rows and `count` other diagnostics."""
    rows = [
        (f"2026-10-{1 + index // 10000:02d}T09:{index // 60 % 60:02d}:{index % 60:02d}.{index % 1000:03d}",)
        for index in range(count)
    ]
    con = sqlite3.connect(path)
    try:
        con.executemany(
            "INSERT INTO calibration_audit(occurred_at, action, success, old_json, new_json, readback_json, "
            "status_code, error_code, detail) VALUES(?, 'write', 1, '{}', '{}', '{}', 3, 0, 'x')",
            rows,
        )
        con.executemany(
            "INSERT INTO diagnostics(occurred_at, level, category, message, details_json) "
            "VALUES(?, 'INFO', 'communication_maintenance', '开始维护操作', '{\"action\": \"maintenance_read\"}')",
            rows,
        )
        con.executemany(
            "INSERT INTO diagnostics(occurred_at, level, category, message, details_json) "
            "VALUES(?, 'ERROR', 'communication', '通信异常', '{}')",
            rows,
        )
        con.commit()
    finally:
        con.close()


def test_large_database_reads_only_what_the_limit_needs(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bounded SQL (ORDER BY id DESC LIMIT): limit=5 on 50,000 rows per table builds the bounded candidate set
    (limit + 1 + ROLLBACK_MARGIN_ROWS), not all of them (PR #63 review major 2)."""
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    _many_rows(database.path, 50_000)
    built = []
    original = maintenance_log._calibration
    monkeypatch.setattr(
        maintenance_log,
        "_calibration",
        lambda *args: built.append(1) or original(*args),  # type: ignore[func-returns-value]
    )
    started = time.perf_counter()
    body = client.get(LOG, params={"limit": 5}).json()
    elapsed = time.perf_counter() - started
    assert len(body["items"]) == 5 and body["limit_reached"]
    assert len(built) <= 6 + maintenance_log.ROLLBACK_MARGIN_ROWS, len(built)  # bounded candidate set
    assert elapsed < 2.0, elapsed


def _insert(path: Path, sql: str, rows: list[tuple[object, ...]]) -> None:
    con = sqlite3.connect(path)
    try:
        con.executemany(sql, rows)
        con.commit()
    finally:
        con.close()


DIAG_SQL = "INSERT INTO diagnostics(occurred_at, level, category, message, details_json) VALUES(?, ?, ?, ?, ?)"


def _count_adds(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    added: list[int] = []
    original = maintenance_log._CommunicationLog.add

    def counting(self: maintenance_log._CommunicationLog, row: dict[str, object]) -> None:
        added.append(1)
        original(self, row)

    monkeypatch.setattr(maintenance_log._CommunicationLog, "add", counting)
    return added


def test_read_only_maintenance_rows_are_never_scanned(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10,000 reads of the communication parameters (开始维护操作 / 维护操作完成 with maintenance_read) are not
    writes: the SQL leaves them out, so limit=1 interprets none of them (rv-63b item 2)."""
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    data.comm_write(database, "2026-09-01T09:00:00.000")
    read = '{"action": "maintenance_read", "device_name": "North"}'
    _insert(
        database.path,
        DIAG_SQL,
        [
            (f"2026-10-01T09:00:{index % 60:02d}.000", "INFO", "communication_maintenance", message, read)
            for index in range(5000)
            for message in ("开始维护操作", "维护操作完成")
        ],
    )
    added = _count_adds(monkeypatch)
    body = client.get(LOG, params={"limit": 1}).json()
    assert [item["kind"] for item in body["items"]] == ["comm_write"]
    assert len(added) <= 3, len(added)  # the one write's own rows
    assert body["scan_limited"] is False


def test_scan_window_bounds_the_rows_interpreted(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the newest SCAN_ROWS rows of the device log are looked at; older ones are reported as not scanned
    ("更早记录未扫描") instead of being read (rv-63b item 2)."""
    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 100)
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    for index in range(150):
        data.comm_write(database, f"2026-10-01T09:{index // 60:02d}:{index % 60:02d}.000", prepared=False, error="超时")
    added = _count_adds(monkeypatch)
    body = client.get(LOG, params={"limit": 1000}).json()
    assert len(added) <= 100, len(added)
    assert body["scan_limited"] is True and "未扫描" in body["texts"]["scan_limited_text"]
    assert 0 < len(body["items"]) <= 50


def test_newest_by_time_even_when_the_clock_went_back(client: TestClient, data_dir: Path) -> None:
    """Rows written after a clock rollback have higher ids but earlier times: limit=1 still returns the newest time
    (rv-63b item 4)."""
    data.write_config(data_dir, ["North", "South"])
    north = data.device_database(data_dir, "North")
    for when in ("2026-10-19T12:00:00.000", "2026-10-19T11:00:00.000", "2026-10-19T10:00:00.000"):
        data.calibration_write(north, when)
    south = data.device_database(data_dir, "South")
    for when in ("2026-10-19T11:30:00.000", "2026-10-19T09:00:00.000"):
        data.comm_write(south, when, prepared=False, error="超时")
    body = client.get(LOG, params={"limit": 1}).json()
    assert [item["occurred_at"] for item in body["items"]] == ["2026-10-19T12:00:00.000"]
    body = client.get(LOG, params={"limit": 2, "device": "p2"}).json()
    assert [item["occurred_at"] for item in body["items"]] == ["2026-10-19T11:30:00.000", "2026-10-19T09:00:00.000"]
    body = client.get(LOG, params={"limit": 2}).json()
    assert [item["occurred_at"] for item in body["items"]] == ["2026-10-19T12:00:00.000", "2026-10-19T11:30:00.000"]


def test_write_cut_by_the_scan_window_is_never_failure(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rv-63c item 5: id 1 "准备写入", id 2 the write's ERROR, then ordinary rows past the window. The write's start is
    outside the window: it must read 待核对 / 记录不完整, never 失败 / 未发出."""
    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 50)
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    data.diagnostic(
        database,
        "2026-10-19T09:00:00.000",
        "WARNING",
        "communication_maintenance",
        "准备写入，结果必须使用新参数核对",
        device_name="North",
        old=data.OLD,
        new=data.NEW,
        identity=data.IDENTITY,
    )
    data.diagnostic(
        database,
        "2026-10-19T09:00:01.000",
        "ERROR",
        "communication_maintenance",
        "写入超时",
        device_name="North",
        action="maintenance_write",
    )
    _insert(
        database.path,
        DIAG_SQL,
        [
            (f"2026-10-19T10:{index // 60:02d}:{index % 60:02d}.000", "ERROR", "communication", "通信异常", "{}")
            for index in range(49)
        ],
    )
    body = client.get(LOG).json()
    assert body["scan_limited"] is True
    (write,) = [item for item in body["items"] if item["kind"] == "comm_write"]
    assert write["result"] == "pending" and "记录不完整" in write["detail"] and "未发出" not in write["detail"]


def _steps(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Counts SQLite virtual-machine steps on every read-only connection the log opens."""
    from contextlib import contextmanager

    from par_app.application import device_audit, readonly

    steps = [0]
    original = readonly.connect_read_only

    @contextmanager
    def counting(path: Path, immutable: bool = False):  # noqa: ANN202
        with original(path, immutable) as con:

            def tick() -> int:
                steps[0] += 1
                return 0

            con.set_progress_handler(tick, 1)
            yield con

    monkeypatch.setattr(device_audit, "connect_read_only", counting)
    return steps


def test_sql_work_does_not_grow_with_the_history(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """rv-63c item 4: SQLite steps for limit=5 with 10,000 vs 100,000 rows per table stay within a small factor
    (rowid-ordered queries with LIMIT, a fixed scan window; no MIN/MAX scan, no full-table sort)."""
    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 2000)
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    steps = _steps(monkeypatch)
    counted = []
    total = 0
    for size in (10_000, 100_000):
        _many_rows(database.path, size - total)
        total = size
        steps[0] = 0
        assert client.get(LOG, params={"limit": 5, "time_sync": "true"}).status_code == 200
        counted.append(steps[0])
    small, large = counted
    assert large < small * 2, counted


def _calibration_reads(path: Path, count: int, writes: int = 0) -> None:
    """`writes` calibration writes first, then `count` calibration reads (the usual mix: reads are frequent)."""
    rows = [("write" if index < writes else "read",) for index in range(count)]
    _insert(
        path,
        "INSERT INTO calibration_audit(occurred_at, action, success, old_json, new_json, readback_json, status_code, "
        "error_code, detail) VALUES('2026-10-01T09:00:00.000', ?, 1, '{}', '{}', '{}', 3, 0, 'x')",
        rows,
    )


def test_calibration_reads_do_not_grow_the_work(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rv-63d item 1: with almost only calibration reads, the write query is bounded by the newest SCAN_ROWS rows by
    id (same step count for 10,000 and 100,000 rows), and older rows are disclosed as scan_limited."""
    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 2000)
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    steps = _steps(monkeypatch)
    counted, limited = [], []
    total = 0
    for size in (10_000, 100_000):
        _calibration_reads(database.path, size - total, writes=3 if total == 0 else 0)
        total = size
        steps[0] = 0
        body = client.get(LOG, params={"limit": 5}).json()
        counted.append(steps[0])
        limited.append(body["scan_limited"])
        assert body["items"] == []  # the three writes lie before the window
    small, large = counted
    assert large < small * 2, counted
    assert limited == [True, True]


def test_calibration_writes_inside_the_window_are_listed(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 2000)
    data.write_config(data_dir, ["North"])
    database = data.device_database(data_dir, "North")
    _calibration_reads(database.path, 100)
    data.calibration_write(database, "2026-10-19T09:01:00.000")
    body = client.get(LOG).json()
    assert [item["kind"] for item in body["items"]] == ["calibration_write"] and body["scan_limited"] is False
