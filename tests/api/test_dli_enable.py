"""dli_enable.store_enabled_at (D-228 option A): V1.0.3's one-row write, nothing more."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from par_app.application.dli_enable import store_enabled_at
from par_app.application.errors import DatabaseUnavailable
from par_app.database import ParDatabase

pytestmark = pytest.mark.unit
NOW = "2026-10-27T09:30:00.000"


def _rows(path: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(path) as con:
        return [tuple(row) for row in con.execute("SELECT key, value_json, updated_at FROM app_settings ORDER BY key")]


def test_writes_what_v103_writes(tmp_path: Path) -> None:
    ours, theirs = tmp_path / "ours.sqlite3", tmp_path / "v103.sqlite3"
    ParDatabase(ours)
    ParDatabase(theirs)
    assert store_enabled_at(ours, NOW) is True
    v103 = ParDatabase(theirs).load_dli_enabled_at()  # V1.0.3's own first write, at its own "now"
    assert _rows(ours) == [("dli_enabled_at", json.dumps(NOW), NOW)]
    assert _rows(theirs) == [("dli_enabled_at", json.dumps(v103), v103)]
    assert ParDatabase(ours).peek_dli_enabled_at() == NOW


def test_an_existing_value_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "par.sqlite3"
    ParDatabase(path)
    assert store_enabled_at(path, NOW) is True
    assert store_enabled_at(path, "2026-10-28T00:00:00.000") is False
    assert _rows(path) == [("dli_enabled_at", json.dumps(NOW), NOW)]


def test_no_app_settings_table_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE acquisitions (id INTEGER PRIMARY KEY)")
    schema = path.read_bytes()
    assert store_enabled_at(path, NOW) is False
    assert path.read_bytes() == schema


def test_a_missing_file_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "devices" / "missing.sqlite3"
    path.parent.mkdir()
    with pytest.raises(DatabaseUnavailable):
        store_enabled_at(path, NOW)
    assert list(path.parent.iterdir()) == []
