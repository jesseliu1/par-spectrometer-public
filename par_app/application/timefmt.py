"""Time text of the service: Beijing ISO with milliseconds, the same shape the database stores (contract 1.2)."""

from __future__ import annotations

from datetime import datetime

ISO_MICROSECONDS = "%Y-%m-%dT%H:%M:%S.%f"
MICROSECOND_DIGITS_DROPPED = 3
"""%f gives microseconds; the last 3 digits are dropped to keep milliseconds, as par_app.database.beijing_now does."""


def beijing_iso(moment: datetime) -> str:
    """`moment` (a Clock.now() value, already Beijing time) as YYYY-MM-DDTHH:MM:SS.mmm."""
    return moment.strftime(ISO_MICROSECONDS)[:-MICROSECOND_DIGITS_DROPPED]
