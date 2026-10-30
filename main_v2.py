"""Entry point of PAR_Spectrometer_2.exe, the 2.0.0-alpha (one exe, two processes; 13_ section 3.1).

  PAR_Spectrometer_2.exe                         desktop shell (par_shell): starts the service, opens the window
  PAR_Spectrometer_2.exe --service ...           local service (par_app.service_main), started by the shell
  PAR_Spectrometer_2.exe --alpha-self-test R     packaging self-test, writes report R (par_shell/self_test.py)

This is the composition root: the only module that imports both par_shell and par_app (the shell itself talks to the
service over HTTP only, 13_ section 4). It imports neither PyQt5 nor V1.0.x's main.py or ui.py itself; the service
(par_app.service_main) runs a QCoreApplication with V1.0.3's coordinator for tiers 1 and 2 (16_ 1.3, 8.1).

A frozen build carries build_info.json (written by build_alpha.ps1: commit and build time); its commit is exported
as PAR_BUILD_COMMIT so the service's health answer names the commit the exe was built from.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import MutableMapping
from pathlib import Path

SERVICE_FLAG = "--service"
SELF_TEST_FLAG = "--alpha-self-test"
BUILD_INFO = "build_info.json"
BUILD_COMMIT_ENV = "PAR_BUILD_COMMIT"


def bundle_dir() -> Path | None:
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else None


def export_build_commit(bundle: Path | None, environ: MutableMapping[str, str] = os.environ) -> str | None:
    """PAR_BUILD_COMMIT from the bundle's build_info.json unless already set; returns the commit in effect."""
    if bundle is not None and BUILD_COMMIT_ENV not in environ:
        try:
            commit = json.loads((bundle / BUILD_INFO).read_text(encoding="utf-8")).get("commit")
        except (OSError, ValueError) as error:
            print(f"{BUILD_INFO} not readable: {error}", file=sys.stderr)
            commit = None
        if isinstance(commit, str) and commit:
            environ[BUILD_COMMIT_ENV] = commit
    return environ.get(BUILD_COMMIT_ENV)


def self_test(report: Path) -> int:
    """Run the self-test; whatever fails, return 1 with a report rather than raise: an uncaught exception in the
    windowed exe would open PyInstaller's traceback dialog and hang an unattended build (review N-3)."""
    try:
        return _run_self_test(report)
    except Exception:
        failure = {"passed": False, "frozen": bool(getattr(sys, "frozen", False)), "error": traceback.format_exc()}
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
            with report.open("x", encoding="utf-8") as stream:
                json.dump(failure, stream, ensure_ascii=False, indent=2)
        except OSError as error:  # an existing report is kept; the reason goes to stderr (if there is one)
            print(f"self-test report {report} not written: {error}", file=sys.stderr)
        print(failure["error"], file=sys.stderr)
        return 1


def _run_self_test(report: Path) -> int:
    from par_app.alpha_info import ALPHA_VERSION  # noqa: PLC0415
    from par_app.alpha_self_test_bus import Level1Kit  # noqa: PLC0415
    from par_app.alpha_self_test_db import DAY_END, DAY_START, write_synthetic_database  # noqa: PLC0415
    from par_shell.self_test import Expectations, SelfTest, run_self_test  # noqa: PLC0415

    frozen = bool(getattr(sys, "frozen", False))
    frozen_windows = frozen and sys.platform == "win32"
    expect = Expectations(
        version=ALPHA_VERSION,
        require_web=frozen,
        require_installer=frozen_windows,
        first_day=(DAY_START, DAY_END),
        require_windows_stack=frozen_windows,
    )
    program_dir = Path(sys.executable).resolve().parent
    report.parent.mkdir(parents=True, exist_ok=True)
    test = SelfTest(expect, write_synthetic_database, program_dir, frozen, level1=Level1Kit())
    return run_self_test(report, test)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    export_build_commit(bundle_dir())
    if args[:1] == [SERVICE_FLAG]:
        from par_app.service_main import main as service_main  # noqa: PLC0415

        return service_main(args[1:])
    if args[:1] == [SELF_TEST_FLAG]:
        if len(args) != 2:
            print(f"usage: {Path(sys.executable).name} {SELF_TEST_FLAG} <report.json>", file=sys.stderr)
            return 2
        return self_test(Path(args[1]))
    from par_shell.__main__ import main as shell_main  # noqa: PLC0415

    return shell_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
