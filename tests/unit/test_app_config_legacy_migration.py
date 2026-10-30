"""Legacy single-device migration must not crash startup on a non-object `connection` value.

Old repo issue #20 / old repository issue 19: a legacy database whose
app_settings['connection'] holds valid JSON that is not an object (list, string, number, bool) made
AppConfigStore.load_for_startup() and load() raise AttributeError, which main.py does not catch.
No mocks: each case builds a real temporary SQLite file and uses the real AppConfigStore.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from par_app.app_config import LEGACY_DATABASE_RELATIVE, AppConfigStore
from par_app.models import AppConfig

pytestmark = pytest.mark.unit


def _legacy_root(tmp_path: Path, value_json: str) -> Path:
    database = tmp_path / LEGACY_DATABASE_RELATIVE
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE app_settings(key TEXT PRIMARY KEY, value_json TEXT)")
        connection.execute("INSERT INTO app_settings VALUES('connection', ?)", (value_json,))
        connection.commit()
    finally:
        connection.close()
    return tmp_path


@pytest.mark.spec("CONF-038")
@pytest.mark.parametrize("value_json", ["[1, 2]", '"x"', "5", "true", "[]", '""', "0", "false"])
def test_non_object_legacy_connection_is_not_migrated(tmp_path: Path, value_json: str) -> None:
    root = _legacy_root(tmp_path, value_json)
    legacy = root / LEGACY_DATABASE_RELATIVE
    before = legacy.read_bytes()
    store = AppConfigStore(root)

    startup = store.load_for_startup()
    assert startup.configured is False
    assert startup.devices == []
    assert startup.bus.serial_port == ""
    assert store.load() == AppConfig()
    assert store.legacy_migration_note is not None
    assert "connection" in store.legacy_migration_note
    # 只证明 AppConfigStore 不写旧库；启动链中 DeviceHub 仍会打开旧库（建表/补列/WAL，范围见 D-138）。
    assert legacy.read_bytes() == before
    assert not store.path.exists()


@pytest.mark.spec("CONF-038")
def test_null_legacy_connection_is_nothing_to_migrate(tmp_path: Path) -> None:
    store = AppConfigStore(_legacy_root(tmp_path, "null"))

    startup = store.load_for_startup()
    assert startup.configured is False
    assert startup.devices == []
    assert startup.bus.serial_port == ""
    assert store.load() == AppConfig()
    assert store.legacy_migration_note is None


@pytest.mark.spec("CONF-038")
def test_migration_note_is_cleared_after_legacy_connection_is_repaired(tmp_path: Path) -> None:
    root = _legacy_root(tmp_path, "[1, 2]")
    store = AppConfigStore(root)
    store.load_for_startup()
    assert store.legacy_migration_note is not None

    connection = sqlite3.connect(root / LEGACY_DATABASE_RELATIVE)
    try:
        connection.execute("UPDATE app_settings SET value_json=? WHERE key='connection'", ('{"slave_id": 4}',))
        connection.commit()
    finally:
        connection.close()

    config = store.load_for_startup()
    assert [d.slave_id for d in config.devices] == [4]
    assert store.legacy_migration_note is None


@pytest.mark.spec("CONF-038")
def test_object_legacy_connection_still_migrates(tmp_path: Path) -> None:
    root = _legacy_root(tmp_path, '{"serial_port": "COM7", "slave_id": 3, "baudrate": 9600}')
    store = AppConfigStore(root)

    config = store.load_for_startup()
    assert config.configured is False
    assert config.bus.serial_port == "COM7"
    assert config.bus.baudrate == 9600
    assert [(d.slave_id, d.database_path) for d in config.devices] == [(3, str(root / LEGACY_DATABASE_RELATIVE))]
    assert store.legacy_migration_note is None


@pytest.mark.spec("CONF-038")
@pytest.mark.parametrize(
    ("value_json", "field"),
    [
        ('{"serial_port": "COM7", "slave_id": 3, "timeout_seconds": "abc"}', "timeout_seconds"),
        ('{"serial_port": "COM7", "slave_id": "abc"}', "slave_id"),
        ('{"serial_port": "COM7", "slave_id": true}', "slave_id"),
        ('{"serial_port": "COM7", "timeout_seconds": NaN}', "timeout_seconds"),
        ('{"serial_port": 7, "slave_id": 3}', "serial_port"),
        # 非整数浮点不得截断成另一个设备地址（3.9 → 3）。
        ('{"serial_port": "COM7", "slave_id": 3.9}', "slave_id"),
        ('{"serial_port": "COM7", "baudrate": 9600.5}', "baudrate"),
        # 超大整数：有限值检查本身不得抛 OverflowError 让启动退出。
        pytest.param('{"serial_port": "COM7", "slave_id": 1' + "0" * 400 + "}", "slave_id", id="huge-int-slave_id"),
        pytest.param(
            '{"serial_port": "COM7", "timeout_seconds": 1' + "0" * 400 + "}", "timeout_seconds", id="huge-int-timeout"
        ),
    ],
)
def test_wrongly_typed_legacy_connection_field_skips_migration(tmp_path: Path, value_json: str, field: str) -> None:
    # D-164 已裁决（负责人，2026-10-17，按推荐）：对象但字段类型错误时跳过迁移、进入未配置状态并记录原因。
    root = _legacy_root(tmp_path, value_json)
    legacy = root / LEGACY_DATABASE_RELATIVE
    before = legacy.read_bytes()
    store = AppConfigStore(root)

    startup = store.load_for_startup()
    assert startup.configured is False
    assert startup.devices == []
    assert startup.bus.serial_port == ""
    assert store.legacy_migration_note is not None
    assert field in store.legacy_migration_note
    assert "abc" in store.legacy_migration_note or "abc" not in value_json
    assert store.load() == AppConfig()
    assert legacy.read_bytes() == before
    assert not store.path.exists()


@pytest.mark.spec("CONF-038")
@pytest.mark.parametrize("database_path_json", ["null", "5", "[]", "{}"])
def test_unused_legacy_database_path_type_does_not_block_migration(tmp_path: Path, database_path_json: str) -> None:
    # 迁移不用旧 connection 的 database_path（设备直接指向旧库）；V1.0.2 能回填的输入不得因它被跳过。
    root = _legacy_root(tmp_path, '{"serial_port": "COM7", "slave_id": 3, "database_path": ' + database_path_json + "}")
    store = AppConfigStore(root)

    config = store.load_for_startup()
    assert config.configured is False
    assert config.bus.serial_port == "COM7"
    assert [(d.slave_id, d.database_path) for d in config.devices] == [(3, str(root / LEGACY_DATABASE_RELATIVE))]
    assert store.legacy_migration_note is None


@pytest.mark.spec("CONF-038")
def test_numeric_text_legacy_fields_are_converted_and_migrated(tmp_path: Path) -> None:
    root = _legacy_root(
        tmp_path, '{"serial_port": "COM7", "slave_id": "4", "timeout_seconds": "12.5", "baudrate": "9600"}'
    )
    store = AppConfigStore(root)

    config = store.load_for_startup()
    assert config.configured is False
    assert [d.slave_id for d in config.devices] == [4]
    assert config.bus.timeout_seconds == 12.5
    assert config.bus.baudrate == 9600
    assert store.legacy_migration_note is None


@pytest.mark.spec("CONF-038")
def test_integral_float_legacy_integer_fields_are_migrated_without_loss(tmp_path: Path) -> None:
    root = _legacy_root(tmp_path, '{"serial_port": "COM7", "slave_id": 3.0, "baudrate": 9600.0, "tcp_port": 502.0}')
    store = AppConfigStore(root)

    config = store.load_for_startup()
    assert [(d.slave_id, type(d.slave_id)) for d in config.devices] == [(3, int)]
    assert (config.bus.baudrate, type(config.bus.baudrate)) == (9600, int)
    assert (config.bus.tcp_port, type(config.bus.tcp_port)) == (502, int)
    assert store.legacy_migration_note is None
