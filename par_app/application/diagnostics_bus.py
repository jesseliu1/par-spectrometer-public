"""The bus trace in the diagnostics bundle (issue #136 steps 2 and 3): bus_trace/.

Each window kept at a device failure or a halt goes in as bus_trace/<record number>.jsonl, the number being the run
event's in events/ and on the page; the whole ring at export time as bus_trace/current.jsonl; bus_trace/index.json
lists them. A window file holds one `window` line, one `transaction` line per 冻结 (the first problem and the first
problem after 恢复) and one `exchange` line per frame written (bus_trace_summary). Built on the export's thread
from memory; every string goes through the bundle's redaction.
"""

from __future__ import annotations

import json
from typing import Any

from . import diagnostics_content as content
from .acquisition import AcquisitionService
from .bus_trace import KEPT_ENTRIES, TRACE_ENTRIES, Window
from .bus_trace_summary import exchanges, transactions

FOLDER = "bus_trace"
CURRENT = "current"


def write_bus_trace(out: content.BundleWriter, acquisition: AcquisitionService) -> None:
    trace = acquisition.bus_trace
    listed = []
    for window in [*trace.kept(), trace.current()]:
        name = window.event_id or CURRENT
        records = list(exchanges(window))
        found = transactions(records)
        head = _head(window, len(records), len(found))
        lines = [{"type": "window", **head}]
        lines += [{"type": "transaction", **item} for item in found]
        lines += [{"type": "exchange", **record} for record in records]
        out.raw(f"{FOLDER}/{name}.jsonl", "".join(_line(out, line) for line in lines))
        listed.append({"file": f"{name}.jsonl", **head})
    index = {
        "installed": trace.installed,
        "ring_entries": TRACE_ENTRIES,
        "kept_entries": KEPT_ENTRIES,
        "windows_dropped": trace.windows_dropped,
        "windows": listed,
    }
    out.raw(f"{FOLDER}/index.json", _line(out, index))


def _head(window: Window, exchange_count: int, transaction_count: int) -> dict[str, Any]:
    return {
        "event_id": window.event_id,
        "kind": window.kind,
        "message": window.message,
        "entries": len(window.entries),
        "exchanges": exchange_count,
        "transactions": transaction_count,
    }


def _line(out: content.BundleWriter, value: dict[str, Any]) -> str:
    return json.dumps(out.redact.structure(value), ensure_ascii=False) + "\n"
