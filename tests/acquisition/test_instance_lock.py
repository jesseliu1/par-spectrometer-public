"""V1.0.3's single-instance lock, both ways (16_ 2.2, 7.3; owner 2026-10-18: tier 1 must first take V1.0.3's lock).

1. The alpha's lock steps are main.py's: same key literal and the same QSharedMemory call sequence (parsed, so a
   later change of V1.0.3's lock turns this red).
2. V1.0.3 running (its real main.main() holding the lock) -> POST /acquisition/start is 409 instance_locked; no port
   opened, no file created in the alpha data directory.
3. The alpha acquiring -> V1.0.3's real main.main() shows its own "已在运行" text and returns 1 before
   create_startup_hub; after the alpha stopped, the same main.main() gets the lock.
The tests use the real key, so they are skipped while a real V1.0.3 on this machine holds it.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import threading
import time
import weakref
from pathlib import Path

import pytest

from par_app.acquisition_host import instance_lock
from par_app.acquisition_host.instance_lock import INSTANCE_LOCK_KEY, InstanceLock
from tests.acquisition.conftest import Alpha, bind_clock, pump, two_devices, write_config
from tests.support.fake_bus import FakeDevice, FakeSerial, wired
from tests.virtual_clock import yielding_clock

pytestmark = pytest.mark.qt
ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests" / "support" / "v1_main_probe.py"
V103_ALREADY_RUNNING = "软件已在运行。为避免多个程序同时占用串口，本次启动已取消。"
PROBE_SECONDS = 60.0


def _lock_calls(tree: ast.AST, variable: str) -> list[str]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            target = node.func.value
            if isinstance(target, ast.Name) and target.id == variable:
                args = [
                    ast.literal_eval(arg) if isinstance(arg, ast.Constant) else ast.unparse(arg) for arg in node.args
                ]
                calls.append((node.lineno, node.col_offset, f"{node.func.attr}({', '.join(map(str, args))})"))
    return [text for _line, _col, text in sorted(calls)]


def _key(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "QSharedMemory":
            argument = node.args[0]
            return str(ast.literal_eval(argument)) if isinstance(argument, ast.Constant) else ast.unparse(argument)
    raise AssertionError("no QSharedMemory(...) call")


def test_lock_key_and_steps_are_main_py_s() -> None:
    v103 = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    alpha = ast.parse(Path(instance_lock.__file__).read_text(encoding="utf-8"))
    assert _key(v103) == INSTANCE_LOCK_KEY == "VSCO_PAR_PAR_Spectrometer_SingleInstance"
    assert _key(alpha) == "self.key"
    v103_steps = _lock_calls(v103, "instance_lock")
    alpha_steps = [step.replace("LOCK_SIZE", "1") for step in _lock_calls(alpha, "instance_lock")]
    assert v103_steps == alpha_steps == ["create(1)", "attach()", "detach()", "create(1)"]


@pytest.fixture
def free_key(qt_app: object, alpha: Alpha) -> None:
    """V1.0.3's real key, free on this machine, and the alpha's host using it (the fixture gives it a test key)."""
    alpha.host.lock = InstanceLock()
    probe = InstanceLock()
    if not probe.acquire():
        pytest.skip("V1.0.3's lock is held on this machine (a V1.0.3 is running); lock tests need it free")
    probe.release()


def _probe(mode: str) -> subprocess.Popen[str]:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    return subprocess.Popen(
        [sys.executable, str(PROBE), mode],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _finish(process: subprocess.Popen[str], line: str | None = None) -> tuple[int, str]:
    output, errors = process.communicate(line, timeout=PROBE_SECONDS)
    assert "Traceback" not in errors, errors
    return process.returncode, output


def test_v103_running_refuses_the_takeover(free_key: None, alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(alpha.data_dir, two_devices())
    holder = _probe("hold")
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "STARTED"
        before = sorted(p.relative_to(alpha.data_dir) for p in alpha.data_dir.rglob("*"))
        clock = yielding_clock()
        bind_clock(monkeypatch, clock)
        port = FakeSerial(clock, {1: FakeDevice()})
        alpha.enable_tier_1()
        with wired(port):
            refused = alpha.post("/api/v0/acquisition/start")
        assert refused.status_code == 409 and refused.json()["error"]["code"] == "instance_locked"
        assert refused.json()["error"]["message"].startswith("串口正被其他程序占用（例如旧版光谱仪软件）")
        assert port.opened == 0 and alpha.host.hub is None and alpha.takeover() == "released"
        after = sorted(p.relative_to(alpha.data_dir) for p in alpha.data_dir.rglob("*"))
        new_files = [p for p in after if p not in before]
        # the run events (#136): the request, its refusal with the reason the page shows under 开始采集, and the
        # takeover back at released; nothing recorded as accepted
        assert new_files == [Path("config/app_config_v2.json"), Path("logs/events.jsonl")]
        assert alpha.context.acquisition.run_events.flush(5.0)
        lines = (alpha.data_dir / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines]
        starts = [event["details"]["phase"] for event in events if event["details"].get("action") == "start"]
        assert starts == ["requested", "refused"]
        refusal = next(event for event in events if event["kind"] == "takeover" and event["level"] == "error")
        assert refusal["message"] == refused.json()["error"]["message"]
    finally:
        code, output = _finish(holder, "release\n")  # the line ends V1.0.3's (patched) create_startup_hub
    assert code == 1 and output == "EXIT 1\n"


def test_alpha_acquiring_keeps_v103_out_until_it_stops(
    free_key: None, alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 50
    alpha.enable_tier_1()
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        code, output = _finish(_probe("probe"))
        assert code == 1 and output.splitlines() == [f"WARNING {V103_ALREADY_RUNNING}", "EXIT 1"]
        pump(port.held.is_set)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]
        port.release = lambda: not coordinator._running
        alpha.post("/api/v0/acquisition/stop")
        pump(lambda: alpha.takeover() == "released")
    code, output = _finish(_probe("probe"))
    assert output.splitlines() == ["STARTED", "EXIT 1"]  # got the lock, reached create_startup_hub


def test_v103_stays_out_while_the_stop_is_under_way(
    free_key: None, alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lock is released only after coordinator.stop() returned (review T1): during the up to 40 s a transaction
    may take to end, V1.0.3 must still be refused, or it could open the port the alpha has not let go of."""
    write_config(alpha.data_dir, two_devices())
    clock = yielding_clock()
    bind_clock(monkeypatch, clock)
    port = FakeSerial(clock, {1: FakeDevice(), 2: FakeDevice()})
    port.hold_at = 50
    alpha.enable_tier_1()
    probed: dict[str, object] = {}
    with wired(port):
        assert alpha.post("/api/v0/acquisition/start").status_code == 202
        pump(port.held.is_set)
        coordinator = alpha.host.hub.coordinator  # type: ignore[union-attr]

        def probe_during_the_stop() -> None:
            deadline = time.monotonic() + PROBE_SECONDS
            while coordinator._running and time.monotonic() < deadline:  # the main thread is inside stop()
                time.sleep(0.005)
            probed["result"] = _finish(_probe("probe"))
            probed["lock_held"] = alpha.host.lock.held

        prober = threading.Thread(target=probe_during_the_stop)
        port.release = lambda: "result" in probed  # the transaction ends only after V1.0.3 was tried
        prober.start()
        assert alpha.post("/api/v0/acquisition/stop").status_code == 202
        pump(lambda: alpha.takeover() == "released")
        prober.join(PROBE_SECONDS)
    code, output = probed["result"]  # type: ignore[misc]
    assert code == 1 and output.splitlines() == [f"WARNING {V103_ALREADY_RUNNING}", "EXIT 1"]
    assert probed["lock_held"] is True and not alpha.host.lock.held


def test_v103_stays_out_while_tier_2_is_in_maintenance(
    free_key: None, alpha: Alpha, monkeypatch: pytest.MonkeyPatch
) -> None:
    """17_ 10.5: communication maintenance releases the acquisition connection but never V1.0.3's lock."""
    from tests.acquisition.maintenance_support import enter, fake_port, open_page, start

    port = fake_port(monkeypatch)
    with wired(port):
        start(alpha)
        open_page(alpha, tab=2)
        enter(alpha)
        code, output = _finish(_probe("probe"))
        assert code == 1 and output.splitlines() == [f"WARNING {V103_ALREADY_RUNNING}", "EXIT 1"]
        assert alpha.post("/api/v0/acquisition/stop").status_code == 202
        pump(lambda: alpha.takeover() == "released")
    code, output = _finish(_probe("probe"))
    assert output.splitlines() == ["STARTED", "EXIT 1"]


class _WindowsSegment:
    """Stands in for QSharedMemory with Windows' rule: a failed create() still holds a handle to the existing file
    mapping until the object is destroyed (Qt's qsharedmemory_win.cpp returns false on ERROR_ALREADY_EXISTS but keeps
    the handle; detach() does nothing while not attached). The segment lives while any such object lives."""

    alive: list[weakref.ref[_WindowsSegment]] = []

    def __init__(self, _key: str) -> None:
        _WindowsSegment.alive.append(weakref.ref(self))

    def create(self, _size: int) -> bool:
        return False  # another program (V1.0.3) holds the lock

    def attach(self) -> bool:
        return True

    def detach(self) -> bool:
        return True


def test_a_refused_lock_keeps_no_handle_to_v103_s_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #66 (tests/qt/test_alpha_lock_coexistence.py on Windows): a QSharedMemory object that failed create()
    keeps V1.0.3's segment alive on Windows for as long as it exists, and V1.0.3 could not start again after it quit.
    The alpha's refused acquire() must therefore drop its object at once."""
    _WindowsSegment.alive.clear()
    monkeypatch.setattr(instance_lock, "QSharedMemory", _WindowsSegment)
    lock = InstanceLock("test-key-of-this-test")
    assert not lock.acquire()
    assert not lock.held
    assert _WindowsSegment.alive and all(ref() is None for ref in _WindowsSegment.alive)
