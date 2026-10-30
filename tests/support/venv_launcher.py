"""A stand-in for the Windows venv launcher, so its effect can be tested on every platform (#66).

python tests/support/venv_launcher.py <program> [arguments...]

On Windows a virtual environment's Scripts\\python.exe is a small launcher: it starts the real interpreter as a CHILD
process, hands it its standard handles, waits for it and exits with its exit code. A program started through it has
another pid than the process its parent started (Popen.pid is the launcher's), which is what broke the shell's wait
for service.json on the first Windows run of the alpha suite (issue #66). The frozen exe has no launcher.

This script does the same with subprocess: the child inherits stdin, stdout and stderr (closing the parent's pipe
reaches the child), SIGTERM / SIGINT are passed on to it (on Windows the console delivers CTRL_BREAK to the whole
process group instead), and the child's exit code is returned. Test-only environment:
- PAR_TEST_LAUNCHER_PID=<file>: this stand-in's own pid (os.getpid()) is written to <file>, so a test can tell the
  real program from the launcher. Not the child's Popen.pid: run from a real Windows venv, this stand-in's own
  Popen(sys.executable) goes through the native launcher again, so that pid would be another launcher (review
  of PR #68). The program's real pid comes from the program itself (the service's service.json and log).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from types import FrameType

LAUNCHER_PID_ENV = "PAR_TEST_LAUNCHER_PID"


def main(argv: list[str]) -> int:
    record = os.environ.get(LAUNCHER_PID_ENV)
    if record:
        Path(record).write_text(str(os.getpid()), encoding="utf-8")
    child = subprocess.Popen(argv)

    def relay(signum: int, _frame: FrameType | None) -> None:
        child.send_signal(signum)

    for name in ("SIGTERM", "SIGINT"):
        signal.signal(getattr(signal, name), relay)
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
