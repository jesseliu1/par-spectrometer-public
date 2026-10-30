"""Errors of the application layer; par_app.api maps each to the HTTP status and code of api-contract-v0 1.3.

Every error says what failed in user terms (`message`), whether retrying can help (`retryable`) and, where there
is one, the technical cause (`detail`). Raising one never clears or rewrites anything (R-1-5).
"""

from __future__ import annotations


class ApplicationError(Exception):
    code = "internal"
    retryable = True

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class InvalidArgument(ApplicationError):
    code = "invalid_argument"
    retryable = False


class DeviceNotFound(ApplicationError):
    code = "device_not_found"
    retryable = False


class RecordNotFound(ApplicationError):
    code = "record_not_found"
    retryable = False


class Busy(ApplicationError):
    code = "busy"
    retryable = True


class DatabaseUnavailable(ApplicationError):
    """A database file could not be read. `path` is the file that actually failed, or None (ruling 47)."""

    code = "database_unavailable"
    retryable = True

    def __init__(self, path: str | None, detail: str | None = None) -> None:
        where = f"：{path}" if path else ""
        super().__init__(f"数据库不可访问{where}", detail)
        self.path = path


class RecordUnreadable(ApplicationError):
    """A stored record could not be decoded (for example malformed metrics JSON); other records stay readable."""

    code = "internal"
    retryable = False


class SnapshotChanged(ApplicationError):
    """A request names the snapshot it was prepared on, and that position has been re-imported since: its record
    ids may now mean other records, so the request is refused instead of silently using the new copy (D-208)."""

    code = "snapshot_changed"
    retryable = False


class ExportFailed(ApplicationError):
    """Writing an export file failed; `detail` names the result folder and the files already written (EXP-020)."""

    code = "export_failed"
    retryable = True


class FeatureDisabled(ApplicationError):
    """The alpha's device-write tier does not allow this (403, contract 1.3; 16_ section 5)."""

    code = "feature_disabled"
    retryable = False


class InstanceLocked(ApplicationError):
    """V1.0.3's single-instance lock is held by another program (V1.0.3 or another alpha service; 16_ 2.2)."""

    code = "instance_locked"
    retryable = True


class ConfirmationRequired(ApplicationError):
    """0 -> 1 without a valid second confirmation issued by this service (16_ 4.2)."""

    code = "confirmation_required"
    retryable = False


class ConfigUnavailable(ApplicationError):
    """The alpha's tier-1 configuration or a database it names cannot be used (16_ 3.2, section 5)."""

    code = "config_unavailable"
    retryable = True


class NotRunning(ApplicationError):
    """The request needs the acquisition takeover to be running (16_ section 5)."""

    code = "not_running"
    retryable = False


class TakeoverFault(ApplicationError):
    """Code on the service's Qt main thread raised unexpectedly while handling this request; the service stops the
    takeover and writes tier 0 (D-225 item 1, application/faults.py). Answered 500 with the fault's message."""

    code = "internal"
    retryable = False
