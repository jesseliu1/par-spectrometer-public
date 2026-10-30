"""The real alpha service (par_app.service_main) on the byte-level fake bus, for subprocess tests (16_ 7.8).

python tests/support/fake_bus_service.py <par_app.service_main options>

serial.Serial is patched before the service starts; there is no "fake bus mode" in product code. Two slaves
answer (addresses 1 and 2) on the real clock. When the service has returned, the port counters and the threads
still alive are printed, so a test can check that the port was closed and no non-daemon thread was left behind.

Test-only environment (tests/acquisition/test_shell_crash.py):
- PAR_TEST_LOCK_KEY: the single-instance lock key the takeover uses instead of V1.0.3's (one key per test, so test
  runs at the same time do not refuse each other; the product key is not changed);
- PAR_TEST_HOLD_AFTER_FREEZE=<file>: the first frame written after a freeze (write holding 25 = 1) is held until
  <file> exists; <file>.held is created when the hold begins, so the test knows the device is frozen right then;
- PAR_TEST_SLOT_FAULT_AFTER_FREEZE=1 (tests/acquisition/test_uncaught_errors.py): once a freeze was written, the next
  maintenance-controller slot that reaches maintenance_page.follow_registration raises RuntimeError (once).
- PAR_TEST_DELIVERED_BUS=1 (web/e2e): the two slaves answer at 57600 bps, no parity, the bus the probes are delivered
  with and the blank settings form's default (owner 2026-10-27); otherwise at 19200 bps, N, as the tests' configs;
- PAR_TEST_PRODUCT_TIER=1: keep the product's first-run tier (1, issue #119); otherwise the service is started with
  --first-run-tier 0, the state these tests begin from (nothing opened until a test raises the tier).
After the service returned, every write to holding 25 is printed in order (`STOP25 <slave>:<value> ...`).
"""

from __future__ import annotations

import functools
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from par_app import service_main  # noqa: E402
from par_app.acquisition_host import host as host_module  # noqa: E402
from par_app.acquisition_host.instance_lock import InstanceLock  # noqa: E402
from par_app.domain.clock import SystemClock  # noqa: E402
from tests.support.fake_bus import BAUDRATES, FakeDevice, FakeSerial, wired  # noqa: E402

STOP_REGISTER_WRITE = (6, 0, 25)
"""Function 06, register 25 (stop/resume), as the frame's bytes 1..3."""

baud = BAUDRATES.index(57600 if os.environ.get("PAR_TEST_DELIVERED_BUS") else 19200)
port = FakeSerial(SystemClock(), {1: FakeDevice(comm=[1, baud, 0]), 2: FakeDevice(comm=[2, baud, 0])})
lock_key = os.environ.get("PAR_TEST_LOCK_KEY")
if lock_key:
    host_module.InstanceLock = functools.partial(InstanceLock, lock_key)  # type: ignore[misc]
release_file = os.environ.get("PAR_TEST_HOLD_AFTER_FREEZE")
if release_file:
    frozen: list[bool] = []

    def after_freeze(frame: bytes) -> bool:
        if frozen:
            Path(release_file + ".held").touch()
            return True
        if tuple(frame[1:4]) == STOP_REGISTER_WRITE and frame[4:6] == b"\x00\x01":
            frozen.append(True)
        return False

    port.hold_when = after_freeze
    port.release = lambda: Path(release_file).exists()
if os.environ.get("PAR_TEST_SLOT_FAULT_AFTER_FREEZE"):
    from par_app.acquisition_host import maintenance_page  # noqa: E402

    follow_registration = maintenance_page.follow_registration
    armed = [True]

    def broken(controller: object) -> None:
        frozen = any(tuple(f[1:4]) == STOP_REGISTER_WRITE and f[4:6] == b"\x00\x01" for _, f in port.written())
        if frozen and armed:
            armed.clear()
            raise RuntimeError("injected slot fault")
        follow_registration(controller)  # type: ignore[arg-type]

    maintenance_page.follow_registration = broken  # type: ignore[assignment]
arguments = sys.argv[1:]
if "--first-run-tier" not in arguments and os.environ.get("PAR_TEST_PRODUCT_TIER") != "1":
    arguments += ["--first-run-tier", "0"]
with wired(port):
    code = service_main.main(arguments)
stops = [f"{frame[0]}:{frame[5]}" for _, frame in port.written() if tuple(frame[1:4]) == STOP_REGISTER_WRITE]
print(f"STOP25 {' '.join(stops)}", flush=True)
alive = sorted(thread.name for thread in threading.enumerate() if not thread.daemon)
print(f"PORT opened={port.opened} closed={port.closed} frames={len(port.written())}", flush=True)
print(f"THREADS {','.join(alive)}", flush=True)
raise SystemExit(code)
