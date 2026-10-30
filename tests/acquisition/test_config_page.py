"""What the settings page needs to edit the alpha's tier-1 configuration (16_ 3.2, 3.3; D-214).

* GET /acquisition-config carries V1.0.3's settings-page form (labels, choices, ranges, hints, tooltips, the button
  and its messages) and the four registration rows V1.0.3 shows (ensure_device_count), so the page renders the form
  and writes no rule of its own;
* saving takes the four rows as V1.0.3's form gives them: blank rows that were never registered are dropped
  (MainWindow.devices_from_form), blank names become 光谱仪N and the poll cycle is clamped (AppConfig.normalised),
  then DeviceHub.apply checks with V1.0.3's messages;
* POST /acquisition-config/import-preview reads a V1.0.3 configuration (directory or file) without writing anything,
  clears every database path, and refuses a device whose V1.0.3 database holds an unfinished communication
  maintenance session (D-131: a new database would bypass the verification).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from par_app.acquisition_host import config_io
from par_app.app_config import AppConfigStore
from par_app.application.errors import InvalidArgument
from par_app.database import ParDatabase
from par_app.models import AppConfig, BusConfig, DeviceConfig
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt


def _tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_config_view_carries_the_v103_form_and_four_rows(alpha: Alpha) -> None:
    write_config(alpha.data_dir, two_devices())
    assert alpha.get("/api/v0/acquisition-config").status_code == 403  # tier 0
    alpha.enable_tier_1()
    config = alpha.get("/api/v0/acquisition-config").json()
    rows = config["rows"]
    assert [row["name"] for row in rows] == ["North", "South", "", ""]
    assert [row["slave_id"] for row in rows] == [1, 2, 3, 4]  # ensure_device_count: free addresses
    assert [row["registered"] for row in rows] == [True, True, False, False]
    assert rows[2]["enabled"] is False and rows[2]["database_path"] == "" and rows[2]["database_name"] is None
    assert rows[0]["database_name"] == "North.sqlite3" and rows[0]["database_path"].endswith("North.sqlite3")
    form = config["form"]
    assert form["transports"] == [
        {"value": "rtu", "label": "Modbus RTU（串口）"},
        {"value": "tcp", "label": "Modbus TCP 客户端（网口）"},
    ]
    assert form["baudrates"] == [4800, 9600, 14400, 19200, 38400, 57600, 115200, 256000]
    assert form["parities"] == [
        {"value": "N", "label": "无校验"},
        {"value": "O", "label": "奇校验"},
        {"value": "E", "label": "偶校验"},
    ]
    assert (form["poll_min"], form["poll_max"], form["poll_decimals"]) == (40.0, 3600.0, 1)
    assert form["poll_hint"] == "下限 40 s；上限 3600 s（60 分钟），不随设备数量变化。"
    assert (form["slave_min"], form["slave_max"], form["tcp_port_min"], form["tcp_port_max"]) == (1, 247, 1, 65535)
    assert form["device_columns"] == ["设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"]
    assert form["name_placeholders"] == ["光谱仪1", "光谱仪2", "光谱仪3", "光谱仪4"]
    assert "连续 10 次通信失败后自动退出本次采集" in form["fail_stop_tooltip"]
    # in the alpha "重启软件" is "停止采集后再开始采集" (a new coordinator, D-215 question 5; spec review M-2)
    assert "重启软件" not in form["fail_stop_tooltip"]
    assert "需在“实时概览”停止采集后再开始采集" in form["fail_stop_tooltip"]
    assert form["save_label"] == "保存并应用全部配置"
    assert form["save_tooltip"] == "仅保存软件连接参数和设备登记，不写入设备硬件"
    assert form["saved_text"] == "配置已保存，等待当前事务结束后应用。"
    assert form["error_title"] == "配置未应用"
    labels = {item["key"]: item["label"] for item in form["labels"]}
    assert labels == {
        "transport": "连接方式",
        "serial_port": "计算机串口",
        "baudrate": "波特率",
        "parity": "奇偶校验",
        "host": "TCP 主机",
        "tcp_port": "TCP 端口",
        "poll_cycle_seconds": "全总线轮询周期",
    }


def test_saving_rows_follows_the_v103_form(tmp_path: Path) -> None:
    store = AppConfigStore(tmp_path)
    current = AppConfig(bus=BusConfig(serial_port="COM7"), devices=[DeviceConfig(name="North", slave_id=1)])
    rows = [
        {"name": "North", "slave_id": 1, "enabled": True},
        {"name": "", "slave_id": 2, "enabled": True},  # enabled without a name: kept, named 光谱仪2
        {"name": "  ", "slave_id": 3, "enabled": False},  # blank and never registered: dropped
        {"name": "", "slave_id": 4, "enabled": False},
    ]
    built = config_io.build(
        store, current, {"bus": {**BusConfig(serial_port="COM7").to_dict(), "poll_cycle_seconds": 5}, "devices": rows}
    )
    assert [device.name for device in built.devices] == ["North", "光谱仪2"]
    assert built.bus.poll_cycle_seconds == 40.0  # clamped as V1.0.3's normalised()
    registered = AppConfig(
        bus=BusConfig(serial_port="COM7"), devices=[DeviceConfig(name="A"), DeviceConfig(name="B", slave_id=2)]
    )
    kept = config_io.build(
        store,
        registered,
        {
            "bus": BusConfig(serial_port="COM7").to_dict(),
            "devices": [
                {"name": "A", "slave_id": 1, "enabled": True},
                {"name": "", "slave_id": 2, "enabled": False},  # a registered row stays even when blanked (V1.0.3)
            ],
        },
    )
    assert [device.name for device in kept.devices] == ["A", "光谱仪2"]


def _v103(root: Path, maintenance_on: str | None = None) -> AppConfig:
    stored = write_config(root, two_devices())
    for index, device in enumerate(stored.devices):
        if device.name == maintenance_on:
            with ParDatabase(device.database_path).connect() as connection:
                connection.execute(
                    "INSERT INTO app_settings(key,value_json,updated_at) VALUES('communication_maintenance',?,?)",
                    (json.dumps({"pending": {"slave_id": 9}, "verified": None}), "2026-10-18 10:00:00"),
                )
        if index == 0:
            Path(device.database_path + "-wal").write_bytes(b"")  # V1.0.3 may be running
    return stored


def test_import_preview_reads_v103_without_writing(alpha: Alpha, tmp_path: Path) -> None:
    v1_root = tmp_path / "V1.0.3"
    _v103(v1_root)
    before = _tree(v1_root)
    request = {"source_path": str(v1_root)}
    assert alpha.post("/api/v0/acquisition-config/import-preview", request).status_code == 403  # tier 0
    alpha.enable_tier_1()
    preview = alpha.post("/api/v0/acquisition-config/import-preview", request)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["source_path"] == str((v1_root / "config" / "app_config.json").resolve())
    assert body["bus"]["serial_port"] == "COM7" and body["bus"]["poll_cycle_seconds"] == 40.0
    assert [(d["name"], d["importable"], d["problem"]) for d in body["devices"]] == [
        ("North", True, None),
        ("South", True, None),
    ]
    assert body["devices"][0]["source_database_path"].endswith("North.sqlite3")
    assert [row["name"] for row in body["rows"]] == ["North", "South", "", ""]
    assert all(row["database_path"] == "" for row in body["rows"])
    assert "不改动" in body["note"]
    assert _tree(v1_root) == before
    assert not (alpha.data_dir / "config" / "app_config.json").exists()
    by_file = alpha.post(
        "/api/v0/acquisition-config/import-preview", {"source_path": str(v1_root / "config" / "app_config.json")}
    )
    assert by_file.status_code == 200 and by_file.json()["rows"] == body["rows"]
    assert list((alpha.data_dir / "data" / "staging").glob("*")) == []


def test_import_preview_refuses_a_device_with_unfinished_maintenance(alpha: Alpha, tmp_path: Path) -> None:
    v1_root = tmp_path / "V1.0.3"
    _v103(v1_root, maintenance_on="South")
    before = _tree(v1_root)
    alpha.enable_tier_1()
    body = alpha.post("/api/v0/acquisition-config/import-preview", {"source_path": str(v1_root)}).json()
    south = body["devices"][1]
    assert south["importable"] is False
    assert south["problem"] == "该设备在 V1.0.3 中有通信参数写入待核对，请先在 V1.0.3 完成核对，再导入"
    assert [row["name"] for row in body["rows"]] == ["North", "", "", ""]
    assert _tree(v1_root) == before


def test_import_preview_errors(alpha: Alpha, tmp_path: Path) -> None:
    alpha.enable_tier_1()
    missing = alpha.post("/api/v0/acquisition-config/import-preview", {"source_path": str(tmp_path / "nowhere")})
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "invalid_argument"
    assert missing.json()["error"]["message"].startswith("找不到 V1.0.3 的配置文件")
    broken = tmp_path / "broken" / "config" / "app_config.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")
    refused = alpha.post("/api/v0/acquisition-config/import-preview", {"source_path": str(broken.parents[1])})
    assert refused.status_code == 400 and refused.json()["error"]["message"] == "V1.0.3 的配置文件无法读取"
    empty = alpha.post("/api/v0/acquisition-config/import-preview", {"source_path": "  "})
    assert empty.status_code == 400


def test_a_client_database_path_must_be_one_the_alpha_configuration_holds(tmp_path: Path) -> None:
    """config_io.build refuses any path the alpha configuration does not already hold, even one inside the alpha's
    devices folder (review nit): new devices get DeviceHub.apply's default, or reuse_existing (D-215)."""
    store = AppConfigStore(tmp_path)
    current = AppConfig(bus=BusConfig(serial_port="COM7"), devices=[DeviceConfig(name="North", slave_id=1)])
    inside = config_io.devices_dir(store) / "Other.sqlite3"
    for given in (str(inside), str(tmp_path / "elsewhere.sqlite3")):
        with pytest.raises(InvalidArgument) as refused:
            config_io.build(
                store,
                current,
                {
                    "bus": BusConfig(serial_port="COM7").to_dict(),
                    "devices": [{"name": "North", "slave_id": 1, "enabled": True, "database_path": given}],
                },
            )
        assert refused.value.message.startswith("设备库路径只能沿用配置中已有的库")


def test_reuse_existing_takes_the_same_name_database_in_the_alpha_folder_only(tmp_path: Path) -> None:
    """A device registered again (removed earlier, or imported under the name of an alpha database) would hit V1.0.3's
    "默认数据库文件已存在…请明确选择该文件" and the browser has no file dialog: the row may ask to reuse the database of
    the same default name in the alpha's own devices folder (review Q3, D-215). Nothing outside that folder."""
    store = AppConfigStore(tmp_path)
    current = AppConfig(bus=BusConfig(serial_port="COM7"), devices=[])
    existing = config_io.devices_dir(store) / "West.sqlite3"
    existing.parent.mkdir(parents=True)
    ParDatabase(existing)
    body = {
        "bus": BusConfig(serial_port="COM7").to_dict(),
        "devices": [{"name": "West", "slave_id": 3, "enabled": True, "reuse_existing": True}],
    }
    built = config_io.build(store, current, body)
    assert built.devices[0].database_path == str(existing.resolve())
    plain = config_io.build(store, current, {**body, "devices": [{"name": "West", "slave_id": 3, "enabled": True}]})
    assert plain.devices[0].database_path == ""  # without the choice DeviceHub.apply refuses with V1.0.3's text
    missing = {**body, "devices": [{"name": "East", "slave_id": 4, "enabled": True, "reuse_existing": True}]}
    with pytest.raises(InvalidArgument) as refused:
        config_io.build(store, current, missing)
    assert refused.value.message == config_io.NO_DATABASE_TO_REUSE.format(name="East.sqlite3")


def test_reuse_existing_is_offered_by_the_form_and_saved_through_the_api(
    alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice(), 3: FakeDevice()})
    port.hold_at = 300
    alpha.enable_tier_1()
    config = alpha.get("/api/v0/acquisition-config").json()
    assert config["form"]["reuse_label"] == "沿用数据目录中的同名库"
    assert [row["reuse_existing"] for row in config["rows"]] == [False, False, False, False]
    west = alpha.data_dir / "data" / "devices" / "West.sqlite3"
    ParDatabase(west)
    keep = [
        {k: d[k] for k in ("name", "slave_id", "enabled", "auto_stop_on_failure", "database_path")}
        for d in config["devices"]
    ]
    with wired(port):
        alpha.post("/api/v0/acquisition/start")
        refused = alpha.put(
            "/api/v0/acquisition-config",
            {"bus": config["bus"], "devices": [*keep, {"name": "West", "slave_id": 3, "enabled": True}]},
        )
        assert refused.json()["error"]["message"].startswith("默认数据库文件已存在：West.sqlite3。")
        saved = alpha.put(
            "/api/v0/acquisition-config",
            {
                "bus": config["bus"],
                "devices": [*keep, {"name": "West", "slave_id": 3, "enabled": True, "reuse_existing": True}],
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["devices"][2]["database_path"] == str(west)
        pump(port.held.is_set)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        alpha.post("/api/v0/acquisition/stop")
        pump(lambda: alpha.takeover() == "released")
