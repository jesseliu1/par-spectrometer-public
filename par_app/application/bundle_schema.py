"""Allowlist of the structured data in the diagnostics bundle (D-226 问题 3; PR #63 third review, design change A).

Structured data (alpha configuration files, app_settings rows, status.json, counts.json, runtime_status.json,
manifest.json) is not scrubbed by pattern any more: only the keys listed here, with the types listed here, are
exported. Anything else is replaced, keeping the key name only:

  * a key that is not listed           -> "<omitted: unknown key>" (its value is dropped);
  * a listed key with an unexpected type -> "<omitted: unexpected type>";
  * a settings row whose name is not listed -> its value "<omitted: unknown setting>";
  * a configuration file that is not one of the known files, or not JSON -> "<omitted: unknown file>".

No listed key is a credential (tests/api/test_bundle_schema.py checks every name against redaction.SECRET_KEY).
Strings that are kept still pass the Redactor (paths, a token value). The shapes are those V1.0.3's red-line code
and the alpha write (models.AppConfig / BusConfig / DeviceConfig / ConnectionConfig, ParDatabase's app_settings,
CommunicationMaintenance, PollingCoordinator's device snapshot and halt reason, StatusCache, TierState, Fault,
tools/alpha_release.py's build manifest); a key added there later appears as "<omitted: unknown key>" until it is
listed here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

OMITTED_KEY = "<omitted: unknown key>"
OMITTED_TYPE = "<omitted: unexpected type>"
OMITTED_SETTING = "<omitted: unknown setting>"
OMITTED_FILE = "<omitted: unknown file>"

Redact = Callable[[Any], Any]


@dataclass(frozen=True)
class Scalar:
    """A string (redacted), a number (int or float, never bool) or a boolean."""

    kind: str  # "str" | "int" | "num" | "bool"


@dataclass(frozen=True)
class Object:
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class ListOf:
    item: Any


@dataclass(frozen=True)
class MapOf:
    """Any key (e.g. table names), each value of one schema."""

    value: Any


@dataclass(frozen=True)
class Opaque:
    """Our own build output with no site data (tools/alpha_release.py): kept as JSON, strings redacted, credential
    keys still dropped by the Redactor's key rule."""


STR, INT, NUM, BOOL = Scalar("str"), Scalar("int"), Scalar("num"), Scalar("bool")


def allow(value: Any, schema: Any, redact: Redact) -> Any:  # noqa: ANN401 (any JSON value)
    """`value` reduced to `schema`; None is always kept (a missing value is not data)."""
    if value is None:
        return None
    if isinstance(schema, Opaque):
        return redact(value)
    if isinstance(schema, Scalar):
        return _scalar(value, schema, redact)
    if isinstance(schema, ListOf):
        return [allow(item, schema.item, redact) for item in value] if isinstance(value, list) else OMITTED_TYPE
    if isinstance(schema, MapOf):
        if not isinstance(value, Mapping):
            return OMITTED_TYPE
        return {redact(str(key)): allow(item, schema.value, redact) for key, item in value.items()}
    if isinstance(schema, Object):
        if not isinstance(value, Mapping):
            return OMITTED_TYPE
        return {
            (str(key) if key in schema.fields else redact(str(key))): (
                allow(item, schema.fields[key], redact) if key in schema.fields else OMITTED_KEY
            )
            for key, item in value.items()
        }
    raise TypeError(f"unknown schema {schema!r}")


def _scalar(value: Any, schema: Scalar, redact: Redact) -> Any:  # noqa: ANN401
    if schema.kind == "bool":
        return value if isinstance(value, bool) else OMITTED_TYPE
    if schema.kind in ("int", "num"):
        number = isinstance(value, int | float) and not isinstance(value, bool)
        if schema.kind == "int":
            number = number and isinstance(value, int)
        return value if number else OMITTED_TYPE
    return redact(value) if isinstance(value, str) else OMITTED_TYPE


# ---------------------------------------------------------------- V1.0.3 shapes (models.py, red-line, read only)
CONNECTION = Object(
    {
        "transport": STR,
        "serial_port": STR,
        "host": STR,
        "tcp_port": INT,
        "slave_id": INT,
        "baudrate": INT,
        "parity": STR,
        "timeout_seconds": NUM,
        "acquisition_interval_seconds": NUM,
        "database_path": STR,
    }
)
BUS = Object(
    {
        "transport": STR,
        "serial_port": STR,
        "host": STR,
        "tcp_port": INT,
        "baudrate": INT,
        "parity": STR,
        "timeout_seconds": NUM,
        "poll_cycle_seconds": NUM,
    }
)
DEVICE = Object({"name": STR, "slave_id": INT, "enabled": BOOL, "database_path": STR, "auto_stop_on_failure": BOOL})
APP_CONFIG = Object({"bus": BUS, "devices": ListOf(DEVICE), "configured": BOOL})
TIER_CONFIG = Object({"device_write_tier": INT})
IDENTITY = Object({"serial_number": INT, "device_type": INT, "device_name": STR})
PARAMETERS = Object({"slave_id": INT, "baudrate_index": INT, "parity_index": INT})
COMM_RESULT = Object({"connection": CONNECTION, "identity": IDENTITY, "parameters": PARAMETERS})
PENDING_WRITE = Object({"old": CONNECTION, "new": CONNECTION, "identity": IDENTITY})
SETTINGS: Mapping[str, Any] = {
    "connection": CONNECTION,
    "par_device_identity": IDENTITY,
    "dli_location": Object({"latitude": NUM, "longitude": NUM}),
    "dli_enabled_at": STR,
    "communication_maintenance": Object({"pending": PENDING_WRITE, "verified": COMM_RESULT, "deferred": BOOL}),
}
"""app_settings rows by name (ParDatabase and CommunicationMaintenance write exactly these)."""
RUNTIME_STATUS = Object({"id": INT, "level": STR, "message": STR, "updated_at": STR})
COUNTS = Object({"database_name": STR, "database_bytes": INT, "rows": MapOf(INT)})

# ---------------------------------------------------------------- alpha status (StatusCache, TierState, Fault)
NOTICE = Object({"event_id": STR, "occurred_at": STR})
"""Where a shown message is recorded (#136): its run event in events/events.jsonl."""
FAULT = Object(
    {"id": INT, "kind": STR, "occurred_at": STR, "where": STR, "error": STR, "message": STR, "stopping": BOOL}
)
HALT = Object(
    {
        "name": STR,
        "slave_id": INT,
        "occurred_at": STR,
        "reason": STR,
        "initialized": BOOL,
        "need_power_cycle": BOOL,
        "resume_unconfirmed": BOOL,
        "cycle": INT,
        "message": STR,
        "log_errors": ListOf(STR),
        "text": STR,
        "notice": NOTICE,
    }
)
DEVICE_STATE = Object(
    {
        "key": STR,
        "name": STR,
        "slave_id": INT,
        "enabled": BOOL,
        "online": BOOL,
        "level": STR,
        "message": STR,
        "failures": INT,
        "excluded": BOOL,
        "last_failure_at": STR,
        "last_success_at": STR,
        "last_error": STR,
        "last_elapsed_ms": NUM,
        "latest_record_id": INT,
        "exposure_status": INT,
        "database_path": STR,
        "identity": IDENTITY,
        "status_text": STR,
        "position": STR,
        "notice": NOTICE,
    }
)
STATUS = Object(
    {
        "as_of": STR,
        "service": Object({"version": STR, "build_commit": STR, "started_at": STR}),
        "tier": Object(
            {
                "tier": INT,
                "takeover": STR,
                "lock_held": BOOL,
                "text": STR,
                "level": STR,
                "settings_path": STR,
                "settings_problem": STR,
                "stop_text": STR,
                "down_text": STR,
                "down_to_1_text": STR,
                "maintenance": BOOL,
                "fault": FAULT,
            }
        ),
        "acquisition": Object(
            {
                "takeover": STR,
                "lock_held": BOOL,
                "error": STR,
                "error_notice": NOTICE,
                "bus": Object({"level": STR, "message": STR, "notice": NOTICE}),
                "halt": HALT,
                "maintenance": BOOL,
                "poll_cycle_seconds": NUM,
                "config_apply_error": STR,
                "configured": BOOL,
                "devices": ListOf(DEVICE_STATE),
                "as_of": STR,
            }
        ),
        "snapshots": ListOf(
            Object(
                {
                    "key": STR,
                    "name": STR,
                    "file_name": STR,
                    "source_name": STR,
                    "imported_at": STR,
                    "record_count": INT,
                    "source_sha256": STR,
                }
            )
        ),
        "devices": ListOf(Object({"key": STR, "name": STR, "database": STR, "state": STR, "problem": STR})),
    }
)
MANIFEST = Object(
    {
        "generated_at": STR,
        "version": STR,
        "build_commit": STR,
        "tier": INT,
        "data_dir": STR,
        "platform": Object(
            {
                "system": STR,
                "release": STR,
                "version": STR,
                "machine": STR,
                "platform": STR,
                "python": STR,
                "sqlite": STR,
                "frozen": BOOL,
            }
        ),
        "files": ListOf(STR),
        "problems": ListOf(STR),
        "maintenance_log": Object({"rows": INT, "limit": INT, "limit_reached": BOOL, "scan_limited": BOOL}),
    }
)
BUILD_MANIFEST = Object(
    {
        "version": STR,
        "channel": STR,
        "not_for_release": BOOL,
        "app_name": STR,
        "exe": STR,
        "window_title": STR,
        "commit": STR,
        "dirty": BOOL,
        "built_at": STR,
        "python": STR,
        "architecture": STR,
        "platform": STR,
        "qt_bundled": BOOL,
        "qt": Opaque(),
        "webview2_installer": Opaque(),
        "packages": Opaque(),
        "npm_packages": Opaque(),
        "licence_exceptions": Opaque(),
    }
)
CONFIG_FILES: tuple[tuple[re.Pattern[str], Any], ...] = (
    (re.compile(r"app_config\.json"), APP_CONFIG),
    (re.compile(r"app_config\.before_recovery_[\w.-]+\.json"), APP_CONFIG),
    (re.compile(r"app_config_v2\.json"), TIER_CONFIG),
)
"""The alpha's own configuration files: the tier-1 configuration (V1.0.3's format), its backups taken before
"以空配置重新配置" (app_config.before_recovery_<time>.json) and the tier settings."""


def config_schema(name: str) -> Any:  # noqa: ANN401
    return next((schema for pattern, schema in CONFIG_FILES if pattern.fullmatch(name)), None)


def setting_row(key: object, value: object, updated_at: object, redact: Redact) -> dict[str, Any]:
    """One app_settings row: the value only when the setting's name is listed."""
    schema = SETTINGS.get(key) if isinstance(key, str) else None
    return {
        "key": redact(key) if isinstance(key, str) else OMITTED_TYPE,
        "value": OMITTED_SETTING if schema is None else allow(value, schema, redact),
        "updated_at": allow(updated_at, STR, redact),
    }


def field_names(schema: Any) -> set[str]:  # noqa: ANN401
    """Every key name the allowlist lets through (for the test that none is a credential)."""
    if isinstance(schema, Object):
        names = set(schema.fields)
        for item in schema.fields.values():
            names |= field_names(item)
        return names
    if isinstance(schema, ListOf):
        return field_names(schema.item)
    if isinstance(schema, MapOf):
        return field_names(schema.value)
    return set()


ALL_SCHEMAS = (APP_CONFIG, TIER_CONFIG, *SETTINGS.values(), RUNTIME_STATUS, COUNTS, STATUS, MANIFEST, BUILD_MANIFEST)
