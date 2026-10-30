"""Two-process wire parity: V1.0.3 on PyQt5 in one process, the alpha on PySide6 in another (internal notes 5.2).

A process loads one Qt binding (par_app/qt_binding.py), so a parity test can no longer run V1.0.3's windows and the
alpha service side by side. Each side is a test in a `sides_*.py` module (not collected by default: the name does
not match test_*.py); `run_sides` runs that module twice with pytest, once per binding. tests/conftest.py deselects
the items of the other binding, so the PyQt5 run records V1.0.3's side and the PySide6 run the alpha's. Every side
test hands what it saw to `record`, which writes it as JSON into PAR_PARITY_OUT; the parity test then compares the
two records. The encoding keeps bytes, tuples-as-lists and NaN exact, so equal records mean equal frames, rows and
texts, byte for byte and, where recorded, time for time.

Speed independence (#66): the two sides run at different real speeds (V1.0.3's window is much slower than the
alpha's API, and slower still on Windows), so nothing compared may depend on how fast a test thread is. To rerun a
parity test with one side's test thread slowed down, set PAR_PARITY_SLOW (opt-in; run_sides passes it on), e.g.

    PAR_PARITY_SLOW=V1.0.3=2 python -m pytest tests/acquisition/test_maintenance_parity.py \
        tests/acquisition/test_takeover_parity.py

("<side>=<seconds>[,<side>=<seconds>]", side V1.0.3 or alpha). `slow_down(side)` then sleeps that long (real time)
where a side's test thread is slowest on Windows: before a maintenance scenario's first step and between a held
frame and the stop request. With the harness of alpha.4 this reproduced every one of the twelve Windows failures of
#66 byte for byte on macOS; the records must not change with it.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from par_app import qt_binding

ROOT = Path(__file__).resolve().parents[2]
OUT_ENV = "PAR_PARITY_OUT"
SIDE_START_SECONDS = 300.0
"""Real time a side's pytest run may take besides its tests (start, collection, Qt, session fixtures and teardown)."""


def encode(value: Any) -> Any:  # noqa: ANN401 (JSON)
    if isinstance(value, bytes | bytearray):
        return {"bytes": bytes(value).hex()}
    if isinstance(value, float) and math.isnan(value):
        return {"float": "nan"}
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [encode(item) for item in value]
    return value


def decode(value: Any) -> Any:  # noqa: ANN401 (JSON)
    if isinstance(value, dict):
        if set(value) == {"bytes"}:
            return bytes.fromhex(value["bytes"])
        if value == {"float": "nan"}:
            return "NaN"  # compared as a marker: NaN != NaN would make equal records differ
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


SLOW_ENV = "PAR_PARITY_SLOW"


def slow_down(side: str) -> None:
    """Sleep (real time) as long as PAR_PARITY_SLOW asks for `side`; nothing when it is not set (see above)."""
    for item in filter(None, os.environ.get(SLOW_ENV, "").split(",")):
        name, _, seconds = item.partition("=")
        if name.strip() == side:
            time.sleep(float(seconds))


def record(name: str, data: dict[str, Any]) -> None:
    """Called by a side test: write `data` for the parity test (PAR_PARITY_OUT/<name>.json)."""
    out = os.environ.get(OUT_ENV)
    if not out:
        raise RuntimeError(f"{OUT_ENV} is not set: run the side modules through tests/support/parity_sides.run_sides")
    path = Path(out) / f"{name}.json"
    path.write_text(json.dumps(encode({"binding": qt_binding.chosen(), **data})), encoding="utf-8")


def _text(output: str | bytes | None) -> str:
    """TimeoutExpired keeps the output read so far as bytes on POSIX, as text on Windows."""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


FIRST_FAILURE_CHARS = 8000
STDERR_HEAD_CHARS = 3000
SUMMARY_CHARS = 3000
FAILURE_HEADER = re.compile(r"^_{3,} .+ _{3,}$", re.MULTILINE)


def side_report(binding: str, module: str, stdout: str, stderr: str, out: Path) -> str:
    """What a failed side shows (#66): its progress line, its FIRST failure (not the last), the test summary, the
    head of stderr (a watchdog or a fatal error says what happened first), and the file with the whole output."""
    log = out / f"side-{binding}-{Path(module).stem}.log"
    log.write_text(f"== stdout\n{stdout}\n== stderr\n{stderr}\n", encoding="utf-8")
    progress = stdout.lstrip().splitlines()[0] if stdout.strip() else "(no output)"
    headers = list(FAILURE_HEADER.finditer(stdout))
    first = ""
    if headers:
        end = headers[1].start() if len(headers) > 1 else len(stdout)
        first = stdout[headers[0].start() : end][:FIRST_FAILURE_CHARS]
    summary_at = stdout.rfind("short test summary info")
    summary = stdout[summary_at:][-SUMMARY_CHARS:] if summary_at >= 0 else stdout[-SUMMARY_CHARS:]
    return (
        f"progress: {progress}\n"
        f"-- first failure:\n{first or '(none reported: the process ended before pytest reported one)'}\n"
        f"-- summary:\n{summary or '(none: the process ended before its summary)'}\n"
        f"-- stderr (head):\n{stderr[:STDERR_HEAD_CHARS]}\n"
        f"-- whole output: {log}"
    )


def side_budget(
    tests_per_side: int, per_test_seconds: float | None = None, start_seconds: float = SIDE_START_SECONDS
) -> float:
    """Real-time budget of one side's run: each side test is bounded by the side's own per-test watchdog
    (PAR_TEST_WATCHDOG_SECONDS, tests/conftest.py), plus the time the run takes besides its tests."""
    from tests.conftest import WATCHDOG_SECONDS

    return tests_per_side * (per_test_seconds or WATCHDOG_SECONDS) + start_seconds


def recorded_watchdog(tests_per_side: int) -> float:
    """The parent test's watchdog bound for a `recorded` fixture that runs both sides one after the other (rv-70e):
    both side budgets and the comparison. Used as @pytest.mark.watchdog(seconds=...) by the parity test modules."""
    return len(qt_binding.BINDINGS) * side_budget(tests_per_side) + SIDE_START_SECONDS


def run_sides(
    module: str,
    out: Path,
    tests_per_side: int,
    per_test_seconds: float | None = None,
    start_seconds: float = SIDE_START_SECONDS,
) -> dict[str, dict[str, Any]]:
    """Run `module` (a tests/... path) once on PyQt5 and once on PySide6; the records by name. Each run must pass
    and record something, within side_budget(tests_per_side): a side still running then is killed and reported with
    its first output and log (a stuck side; a side's own watchdog ends a stuck test first)."""
    out.mkdir(parents=True, exist_ok=True)
    budget = side_budget(tests_per_side, per_test_seconds, start_seconds)
    for binding in qt_binding.BINDINGS:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("PYTEST_")}
        environment.update({"PAR_TEST_QT_BINDING": binding, OUT_ENV: str(out), "QT_QPA_PLATFORM": "offscreen"})
        before = set(out.glob("*.json"))
        command = [sys.executable, "-m", "pytest", module, "-q", "-p", "no:cacheprovider", "-m", "not hardware"]
        try:
            done = subprocess.run(
                command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=budget, check=False
            )
        except subprocess.TimeoutExpired as expired:  # the child was killed; its output so far is kept
            report = side_report(binding, module, _text(expired.stdout), _text(expired.stderr), out)
            raise AssertionError(
                f"{binding} side of {module} did not finish within {budget:.0f} s (killed):\n{report}"
            ) from None
        report = side_report(binding, module, done.stdout, done.stderr, out)
        assert done.returncode == 0, f"{binding} side of {module} failed (exit {done.returncode}):\n{report}"
        assert set(out.glob("*.json")) - before, f"{binding} side of {module} recorded nothing:\n{report}"
    records = {path.stem: decode(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(out.glob("*.json"))}
    return records
