"""The allowlist of structured data in the diagnostics bundle (D-226 问题 3; PR #63 third review, design A)."""

from __future__ import annotations

import json

import pytest

from par_app.application import bundle_schema as schema
from par_app.application.redaction import SECRET_KEY, Redactor

pytestmark = pytest.mark.unit


@pytest.fixture
def redact() -> Redactor:
    return Redactor(None, [(r"C:\Users\Alice", "<HOME>")])


def test_no_allowlisted_key_is_a_credential() -> None:
    names = set().union(*(schema.field_names(item) for item in schema.ALL_SCHEMAS))
    assert names and not [name for name in names if SECRET_KEY.match(name)]


def test_unknown_keys_keep_their_name_only(redact: Redactor) -> None:
    config = {
        "bus": {"serial_port": "COM7", "baudrate": 9600, "secret_note": "LEAK_ONE"},
        "devices": [
            {"name": "North", "slave_id": 1, "database_path": r"C:\Users\Alice\x.sqlite3", "extra": ["LEAK_TWO"]}
        ],
        "configured": True,
        "password": "LEAK_THREE",
    }
    out = schema.allow(config, schema.APP_CONFIG, redact.structure)
    text = json.dumps(out, ensure_ascii=False)
    for leak in ("LEAK_ONE", "LEAK_TWO", "LEAK_THREE"):
        assert leak not in text
    assert out["bus"] == {"serial_port": "COM7", "baudrate": 9600, "secret_note": schema.OMITTED_KEY}
    assert out["password"] == schema.OMITTED_KEY and out["devices"][0]["extra"] == schema.OMITTED_KEY
    # a whole path outside the alpha folders keeps only its file name, also under the home folder (#66)
    assert out["devices"][0]["database_path"] == "<PATH>/x.sqlite3" and out["configured"] is True


def test_unexpected_types_are_dropped(redact: Redactor) -> None:
    out = schema.allow({"bus": "LEAK", "devices": {"a": 1}, "configured": "yes"}, schema.APP_CONFIG, redact.structure)
    assert out == {"bus": schema.OMITTED_TYPE, "devices": schema.OMITTED_TYPE, "configured": schema.OMITTED_TYPE}


def test_setting_rows_keep_only_listed_settings_and_fields(redact: Redactor) -> None:
    """rv-63c item 2: a row named after a credential with a sibling credentials object leaks nothing."""
    rows = [
        schema.setting_row("password", {"value": "FIRST"}, "t", redact.structure),
        schema.setting_row(
            "communication_maintenance",
            {"pending": None, "verified": None, "credentials": {"username": "SECOND"}},
            "t",
            redact.structure,
        ),
        schema.setting_row("dli_location", {"latitude": 39.9, "longitude": 116.4}, "t", redact.structure),
    ]
    text = json.dumps(rows, ensure_ascii=False)
    assert "FIRST" not in text and "SECOND" not in text
    assert rows[0]["value"] == schema.OMITTED_SETTING
    assert rows[1]["value"]["credentials"] == schema.OMITTED_KEY
    assert rows[2]["value"] == {"latitude": 39.9, "longitude": 116.4}


def test_known_configuration_files() -> None:
    assert schema.config_schema("app_config.json") is schema.APP_CONFIG
    assert schema.config_schema("app_config.before_recovery_20261019_093000.json") is schema.APP_CONFIG
    assert schema.config_schema("app_config_v2.json") is schema.TIER_CONFIG
    assert schema.config_schema("extra.json") is None


def test_communication_maintenance_as_v103_saves_it(tmp_path, redact: Redactor) -> None:  # noqa: ANN001
    """rv-63d item 2: the row CommunicationMaintenance._save writes (with deferred) keeps every field."""
    from par_app.database import ParDatabase
    from par_app.maintenance import CommunicationMaintenance

    database = ParDatabase(tmp_path / "North.sqlite3")
    connection = {"transport": "rtu", "serial_port": "COM7", "slave_id": 7, "baudrate": 9600, "parity": "N"}
    identity = {"serial_number": 1, "device_type": 1, "device_name": "PAR"}
    verified = {
        "connection": connection,
        "identity": identity,
        "parameters": {"slave_id": 7, "baudrate_index": 1, "parity_index": 0},
    }
    CommunicationMaintenance(database, "North")._save(None, verified, deferred=True)
    with database.connect() as con:
        key, value, updated = con.execute("SELECT key, value_json, updated_at FROM app_settings").fetchone()
    row = schema.setting_row(key, json.loads(value), updated, redact.structure)
    assert row["value"] == {"pending": None, "verified": verified, "deferred": True}
