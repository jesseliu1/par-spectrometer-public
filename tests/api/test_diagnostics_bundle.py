"""POST /api/v0/support/diagnostics-bundle (API-27, D-226): one zip in the alpha's output folder; read only for
everything else.

Checked: the files and README, no token and no local folder anywhere in the zip, no spectra, the device databases
and configuration unchanged byte for byte, an unreadable database listed as a problem (the bundle is still written),
a write failure as 500 export_failed, and a second export never overwriting the first.
"""

from __future__ import annotations

import codecs
import json
import sqlite3
import time
import tracemalloc
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from par_app.api.context import ServiceContext
from par_app.application import diagnostics_content
from par_app.application.redaction import DATA_DIR_MARK, SECRET_MARK
from tests.api import support_data as data
from tests.api.conftest import TOKEN, error_of, import_snapshot, record, v1_database

pytestmark = pytest.mark.unit
EXPORT = "/api/v0/support/diagnostics-bundle"
SERVICE_TOKEN = "secret-service-token-1234567890"


@pytest.fixture
def data_dir(context: ServiceContext) -> Path:
    path = context.paths.data_dir
    context.paths.ensure()
    return path


@pytest.fixture
def populated(data_dir: Path, client: TestClient, tmp_path: Path) -> Path:
    """Two registered devices with audit rows and 60 records, a service.json with a token, a log naming the data
    directory and the token, the tier settings, and one imported snapshot."""
    data.write_config(data_dir, ["North", "South"])
    north = data.device_database(data_dir, "North")
    data.calibration_write(north, "2026-10-19T09:01:00.000")
    data.comm_write(north, "2026-10-19T09:02:00.000")
    data.comm_verify(north, "2026-10-19T09:02:05.000")
    data.time_sync(north, "2026-10-19T09:05:00.000")
    north.save_par_device_identity(305419896, 1, "PAR-FAKE")
    data.acquisitions(north, 60)
    data.device_database(data_dir, "South")
    (data_dir / "config" / "app_config_v2.json").write_text('{"device_write_tier": 0}', encoding="utf-8")
    (data_dir / "service.json").write_text(json.dumps({"token": SERVICE_TOKEN, "port": 1}), encoding="utf-8")
    (data_dir / "logs" / "service.log").write_text(
        f"INFO listening (data {data_dir})\nGET /#token={SERVICE_TOKEN}\nAuthorization: Bearer {TOKEN}\n",
        encoding="utf-8",
    )
    (data_dir / "logs" / "service.log.1").write_text("older log\n", encoding="utf-8")
    import_snapshot(client, v1_database(tmp_path / "v1" / "p1.sqlite3", [record()]), name="温室外")
    for name in ("North", "South"):
        data.close_wal(data_dir / "data" / "devices" / f"{name}.sqlite3")
    return data_dir


def _zip(response_body: dict[str, object]) -> zipfile.ZipFile:
    return zipfile.ZipFile(Path(str(response_body["path"])))


def test_bundle_contents(client: TestClient, populated: Path) -> None:
    response = client.post(EXPORT)
    assert response.status_code == 201, response.text
    body = response.json()
    path = Path(body["path"])
    assert path.parent == populated / "exports" / "diagnostics" and path.name == "PAR_diagnostics_20261018_093000.zip"
    assert body["size"] == path.stat().st_size and body["text"].startswith(f"已保存诊断包：{path}")
    assert not list(path.parent.glob("*.partial"))
    with _zip(body) as archive:
        names = set(archive.namelist())
        assert names == set(body["files"])
        for expected in (
            "README.txt",
            "manifest.json",
            "status.json",
            "maintenance_log.csv",
            "logs/service.log",
            "logs/service.log.1",
            "config/app_config.json",
            "config/app_config_v2.json",
            "devices/p1_North/calibration_audit.csv",
            "devices/p1_North/connection_audit.csv",
            "devices/p1_North/diagnostics.csv",
            "devices/p1_North/time_sync_events.csv",
            "devices/p1_North/app_settings.json",
            "devices/p1_North/acquisitions_recent.csv",
            "devices/p1_North/counts.json",
            "devices/p2_South/counts.json",
        ):
            assert expected in names, expected
        readme = archive.read("README.txt").decode("utf-8")
        assert "诊断包" in readme and "maintenance_log.csv" in readme and "不包含" in readme
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.0.0-alpha.9" and manifest["tier"] == 0
        assert manifest["data_dir"] == "<DATA_DIR>" and "python" in manifest["platform"]
        status = json.loads(archive.read("status.json"))
        assert status["tier"]["tier"] == 0 and status["acquisition"]["takeover"] == "released"
        assert [item["name"] for item in status["snapshots"]] == ["温室外"]
        settings = json.loads(archive.read("devices/p1_North/app_settings.json"))
        assert {row["key"] for row in settings} >= {"par_device_identity"}
        recent = archive.read("devices/p1_North/acquisitions_recent.csv").decode("utf-8-sig").splitlines()
        assert len(recent) == 1 + diagnostics_content.RECENT_ACQUISITIONS
        assert "raw_points" not in recent[0] and "software_metrics_json" not in recent[0]
        log = archive.read("maintenance_log.csv").decode("utf-8-sig")
        assert "校准写入" in log and "通信参数写入" in log and "成功" in log
        assert "设备对时" not in log  # in each device's time_sync_events.csv (PR #63 review M-2)
        rows = archive.read("devices/p1_North/maintenance_diagnostics.csv").decode("utf-8-sig")
        assert "准备写入，结果必须使用新参数核对" in rows and "维护操作完成" in rows
        counts = json.loads(archive.read("devices/p1_North/counts.json"))
        assert counts["rows"]["acquisitions"] == 60 and counts["rows"]["spectra"] == 60


def test_no_token_no_local_folder_no_spectra(client: TestClient, populated: Path) -> None:
    body = client.post(EXPORT).json()
    home = str(Path.home())
    with _zip(body) as archive:
        for name in archive.namelist():
            text = archive.read(name).decode("utf-8", errors="replace")
            assert SERVICE_TOKEN not in text, name
            assert TOKEN not in text, name
            assert str(populated) not in text and str(populated.resolve()) not in text, name
            assert home not in text, name
            assert "raw_points_json" not in text, name
        assert "service.json" not in archive.namelist()
        log = archive.read("logs/service.log").decode("utf-8")
        assert "<DATA_DIR>" in log and "token=<TOKEN>" in log and "[credential header line removed]" in log


def test_sources_unchanged(client: TestClient, populated: Path) -> None:
    devices = populated / "data" / "devices"
    imported = populated / "data" / "imported"
    before = (data.fingerprint(devices), data.fingerprint(imported))
    configs = {path.name: path.read_bytes() for path in (populated / "config").iterdir()}
    log = (populated / "logs" / "service.log").read_bytes()
    assert client.post(EXPORT).status_code == 201
    assert (data.fingerprint(devices), data.fingerprint(imported)) == before
    assert {path.name: path.read_bytes() for path in (populated / "config").iterdir()} == configs
    assert (populated / "logs" / "service.log").read_bytes() == log


def test_second_export_gets_a_new_name(client: TestClient, populated: Path) -> None:
    first = client.post(EXPORT).json()
    second = client.post(EXPORT).json()
    assert first["path"] != second["path"] and second["file_name"].endswith("_2.zip")
    assert Path(first["path"]).is_file() and Path(second["path"]).is_file()


def test_unreadable_database_is_a_problem_not_a_failure(client: TestClient, populated: Path) -> None:
    (populated / "data" / "devices" / "South.sqlite3").write_bytes(b"not a database" * 100)
    response = client.post(EXPORT)
    assert response.status_code == 201, response.text
    body = response.json()
    assert any("South" in item for item in body["problems"]) and "生成时遇到的问题" in body["text"]
    with _zip(body) as archive:
        assert "devices/p2_South/ERROR.txt" in archive.namelist()
        assert "devices/p1_North/calibration_audit.csv" in archive.namelist()
        listed = json.loads(archive.read("manifest.json"))["problems"]
        # the page shows the real path; the zip has the same problems with the data directory replaced
        assert listed == [item.replace(str(populated), "<DATA_DIR>") for item in body["problems"]]


def test_empty_data_directory(client: TestClient, data_dir: Path) -> None:
    response = client.post(EXPORT)
    assert response.status_code == 201, response.text
    with _zip(response.json()) as archive:
        assert {"README.txt", "manifest.json", "status.json", "maintenance_log.csv"} <= set(archive.namelist())


def test_write_failure_is_export_failed(client: TestClient, data_dir: Path) -> None:
    (data_dir / "exports").write_text("a file where the folder should be", encoding="utf-8")
    response = client.post(EXPORT)
    assert response.status_code == 500
    error = error_of(response)
    assert error["code"] == "export_failed" and error["retryable"] is True


def test_needs_the_token(anonymous: TestClient) -> None:
    assert anonymous.post(EXPORT).status_code == 401


def test_csv_files_carry_a_byte_order_mark(client: TestClient, populated: Path) -> None:
    """README promises UTF-8 with BOM so Excel opens the Chinese text (PR #63 review nit)."""
    with _zip(client.post(EXPORT).json()) as archive:
        csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
        assert "maintenance_log.csv" in csv_names and len(csv_names) > 5
        for name in csv_names:
            assert archive.read(name).startswith(codecs.BOM_UTF8), name


def test_every_write_survives_a_flood_of_time_syncs_and_errors(client: TestClient, data_dir: Path) -> None:
    """One early communication write, then 1,200 time syncs and 3,000 communication errors: the write is still in
    maintenance_log.csv (no time syncs there) and its raw rows in maintenance_diagnostics.csv, although diagnostics.csv
    keeps only the newest rows (PR #63 review M-2)."""
    data.write_config(data_dir, ["North"])
    north = data.device_database(data_dir, "North")
    data.comm_write(north, "2026-09-01T09:00:00.000")
    con = sqlite3.connect(north.path)
    try:
        con.executemany(
            "INSERT INTO time_sync_events(occurred_at, success, mcu_time_ms, detail) VALUES(?, 1, 1, '设备对时完成')",
            [(f"2026-09-{2 + index // 100:02d}T{index % 24:02d}:00:00.000",) for index in range(1200)],
        )
        con.executemany(
            "INSERT INTO diagnostics(occurred_at, level, category, message, details_json) "
            "VALUES(?, 'ERROR', 'communication', '通信异常', '{}')",
            [(f"2026-10-01T09:{index // 60 % 60:02d}:{index % 60:02d}.000",) for index in range(3000)],
        )
        con.commit()
    finally:
        con.close()
    with _zip(client.post(EXPORT).json()) as archive:
        log = archive.read("maintenance_log.csv").decode("utf-8-sig")
        assert "通信参数写入" in log and "地址 7" in log and "设备对时" not in log
        rows = archive.read("devices/p1_North/maintenance_diagnostics.csv").decode("utf-8-sig")
        assert "准备写入，结果必须使用新参数核对" in rows
        diagnostics = archive.read("devices/p1_North/diagnostics.csv").decode("utf-8-sig").splitlines()
        assert len(diagnostics) == 1 + diagnostics_content.DIAGNOSTICS_ROWS


@pytest.mark.parametrize("inside_home", [False, True], ids=["outside-home", "inside-home"])
def test_outside_database_and_credentials_are_not_in_the_zip(
    client: TestClient, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inside_home: bool
) -> None:
    """A database outside the alpha folder is named by file name only (ERROR.txt, status.json); passwords and other
    credentials in configuration and logs, and absolute paths outside the data directory, never reach the zip
    (PR #63 review blocker 1, review m-2). inside-home: the database lies under the user's home folder, as
    pytest's temporary folder does on Windows (under %LOCALAPPDATA%); the folders between home and the file must not
    reach the zip either (#66: app_config.json kept the folder names after <HOME>)."""
    if inside_home:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
    outside = tmp_path / "Customer Site" / "North.sqlite3"
    data.write_config(data_dir, ["North"], {"North": str(outside)})
    (data_dir / "config" / "extra.json").write_text(
        json.dumps({"bus": {"password": "pw-config-1"}, "X-PAR-Token": "tok-config-2"}), encoding="utf-8"
    )
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs" / "service.log").write_text(
        'login {"password": "pw-log-3"} api_key=key-log-4\n'
        r"open c:\users\ALICE~1\AppData\Local\Temp\x.txt and D:\Customer Site\North.sqlite3"
        "\n",
        encoding="utf-8",
    )
    with _zip(client.post(EXPORT).json()) as archive:
        error = archive.read("devices/p1_North/ERROR.txt").decode("utf-8")
        assert "North.sqlite3" in error
        status = json.loads(archive.read("status.json"))
        assert status["devices"][0]["database"] == "North.sqlite3"
        for name in archive.namelist():
            text = archive.read(name).decode("utf-8", errors="replace")
            for secret in ("pw-config-1", "tok-config-2", "pw-log-3", "key-log-4", "ALICE", "Customer Site"):
                assert secret not in text, (name, secret)
            assert str(tmp_path) not in text, name


def test_windows_line_endings_in_the_log_are_redacted_the_same(client: TestClient, data_dir: Path) -> None:
    """The service log on Windows has CRLF line endings (logging in text mode): a credential header line still goes
    entirely, as with LF (#66: "Authorization: <SECRET> [rest of line removed]" was left)."""
    data.write_config(data_dir, ["North"])
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs" / "service.log").write_text(
        f"INFO listening (data {data_dir})\nAuthorization: Bearer {TOKEN}\nCookie: a=b\nINFO done\n",
        encoding="utf-8",
        newline="\r\n",
    )
    with _zip(client.post(EXPORT).json()) as archive:
        log = archive.read("logs/service.log").decode("utf-8")
    header_line = f"{SECRET_MARK} [credential header line removed]"
    assert log == f"INFO listening (data {DATA_DIR_MARK})\r\n{header_line}\r\n{header_line}\r\nINFO done\r\n"


def test_large_database_is_streamed_into_the_zip(client: TestClient, data_dir: Path) -> None:
    """50,000 calibration writes go in whole (D-226) without holding the table in memory: rows are fetched in chunks
    and written to the zip entry as they come (PR #63 review major 2)."""
    data.write_config(data_dir, ["North"])
    north = data.device_database(data_dir, "North")
    count = 50_000
    con = sqlite3.connect(north.path)
    try:
        con.executemany(
            "INSERT INTO calibration_audit(occurred_at, action, success, old_json, new_json, readback_json, "
            "status_code, error_code, detail) VALUES(?, 'write', 1, ?, ?, ?, 3, 0, '写入并回读光谱仪校准')",
            [
                (f"2026-10-01T09:00:{index % 60:02d}.000", '{"x_min": 350.0}', '{"x_min": 351.0}', '{"x_min": 351.0}')
                for index in range(count)
            ],
        )
        con.commit()
    finally:
        con.close()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        response = client.post(EXPORT)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    elapsed = time.perf_counter() - started
    assert response.status_code == 201, response.text
    with _zip(response.json()) as archive:
        lines = archive.read("devices/p1_North/calibration_audit.csv").decode("utf-8-sig").splitlines()
        assert len(lines) == 1 + count
        log = archive.read("maintenance_log.csv").decode("utf-8-sig").splitlines()
        assert len(log) == 1 + diagnostics_content.BUNDLE_LOG_ROWS
    assert peak < 20_000_000, peak
    assert elapsed < 60, elapsed


def test_structured_files_are_allowlisted(client: TestClient, data_dir: Path) -> None:
    """Configuration files and app_settings rows keep only listed keys and settings; unknown ones keep the name only
    (PR #63 third review, design A and item 2)."""
    data.write_config(data_dir, ["North"])
    config = json.loads((data_dir / "config" / "app_config.json").read_text(encoding="utf-8"))
    config["bus"]["password"] = "CONFIG_LEAK_1"
    config["notes"] = {"customer": "CONFIG_LEAK_2"}
    (data_dir / "config" / "app_config.json").write_text(json.dumps(config), encoding="utf-8")
    (data_dir / "config" / "extra.json").write_text('{"anything": "CONFIG_LEAK_3"}', encoding="utf-8")
    north = data.device_database(data_dir, "North")
    with north.connect() as con:
        con.executemany(
            "INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, 't')",
            [
                ("password", json.dumps({"value": "FIRST"})),
                ("site_notes", json.dumps("SETTING_LEAK")),
                ("connection", json.dumps({**data.OLD, "credentials": {"username": "SECOND"}})),
            ],
        )
    with _zip(client.post(EXPORT).json()) as archive:
        texts = {name: archive.read(name).decode("utf-8", errors="replace") for name in archive.namelist()}
        for name, text in texts.items():
            for leak in ("CONFIG_LEAK_1", "CONFIG_LEAK_2", "CONFIG_LEAK_3", "FIRST", "SECOND", "SETTING_LEAK"):
                assert leak not in text, (name, leak)
        saved = json.loads(texts["config/app_config.json"])
        assert saved["bus"]["password"] == "<omitted: unknown key>" and saved["bus"]["serial_port"] == "COM7"
        assert json.loads(texts["config/extra.json"]) == "<omitted: unknown file>"
        settings = {row["key"]: row["value"] for row in json.loads(texts["devices/p1_North/app_settings.json"])}
        assert settings["password"] == settings["site_notes"] == "<omitted: unknown setting>"
        assert settings["connection"]["credentials"] == "<omitted: unknown key>"
        assert settings["connection"]["slave_id"] == 1


def test_scan_window_is_disclosed_in_the_bundle(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writes beyond the maintenance log's scan window are named in the problems and manifest (rv-63c item 6)."""
    from par_app.application import maintenance_log

    monkeypatch.setattr(maintenance_log, "SCAN_ROWS", 10)
    data.write_config(data_dir, ["North"])
    north = data.device_database(data_dir, "North")
    data.comm_write(north, "2026-09-01T09:00:00.000")
    for index in range(20):
        data.diagnostic(north, f"2026-10-01T09:00:{index:02d}.000", "ERROR", "communication", "通信异常")
    body = client.post(EXPORT).json()
    assert any("未扫描" in problem for problem in body["problems"]), body["problems"]
    with _zip(body) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["maintenance_log"]["scan_limited"] is True
        assert any("未扫描" in problem for problem in manifest["problems"])
        assert "未扫描" in archive.read("README.txt").decode("utf-8")
