"""Single entry point for local and CI checks (R-1-3).

Usage:
  python tools/quality/check_all.py           # static checks + tests (excluding hardware)
  python tools/quality/check_all.py --static  # static checks only (fast, used by pre-commit)
  python tools/quality/check_all.py --binding PySide6
      # static checks + web checks + every Qt-independent test (`unit` marker) + the whole PySide6 session; leaves
      # out only the PyQt5 round of V1.0.3's Qt tests (the alpha regression on Windows, packaging guide section 三)

Tests run in two sessions, one per Qt binding (internal notes section 5; tests/conftest.py): PyQt5 for V1.0.3 and
everything else, PySide6 for the alpha service. A process loads one binding, so one pytest run cannot hold both.

Web front end (web/, review M-3): the R-1-5 colour token check runs whenever `node` is on PATH (it needs no npm
packages); the vitest suite runs in full mode once `npm ci` has installed web/node_modules. Either is reported as
SKIPPED otherwise. CI's `web` job always runs both plus the build (`npm run check`) and the built-page smoke test.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPED_PACKAGES = (
    "par_app/domain",
    "par_app/storage",
    "par_app/services",
    "par_app/application",
    "par_app/api",
    "par_app/acquisition_host",
    "par_app/service_main.py",
    "par_shell",
    "par_app/alpha_info.py",
    "par_app/alpha_self_test_db.py",
    "par_app/alpha_self_test_bus.py",
    "main_v2.py",
    "par_app/qt_binding.py",
    "par_app/qt_compat.py",
)


QT_BINDINGS = ("PySide6",)
"""Test sessions, one per Qt binding: PAR_TEST_QT_BINDING of tests/conftest.py."""


def run(title: str, args: list[str], env: dict[str, str] | None = None) -> bool:
    shown = " ".join(f"{key}={value}" for key, value in (env or {}).items())
    print(f"\n== {title}: {shown + ' ' if shown else ''}{' '.join(args)}", flush=True)
    return subprocess.run(args, cwd=ROOT, env={**os.environ, **env} if env else None).returncode == 0


def web_steps(full: bool) -> list[tuple[str, list[str]]]:
    """The web/ checks this machine can run; the others are announced as skipped."""
    steps: list[tuple[str, list[str]]] = []
    node = shutil.which("node")
    if node is None:
        print("== web colour tokens: SKIPPED (node not on PATH; CI's web job runs it)", flush=True)
    else:
        steps.append(("web colour tokens", [node, "web/scripts/check-tokens.mjs"]))
    if full:
        npm = shutil.which("npm")
        if npm is None or not (ROOT / "web" / "node_modules").is_dir():
            print("== web tests: SKIPPED (run `npm ci` in web/ first; CI's web job runs them)", flush=True)
        else:
            steps.append(("web tests", [npm, "--prefix", "web", "run", "test"]))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--static", action="store_true", help="skip the test suite")
    parser.add_argument(
        "--binding",
        choices=("PySide6",),
        help="PySide6: Qt-independent tests and the PySide6 session only, not the PyQt5 round (alpha on Windows)",
    )
    args = parser.parse_args()
    if args.static and args.binding:
        parser.error("--binding selects tests; --static runs none")
    py = sys.executable
    steps: list[tuple[str, list[str], dict[str, str] | None]] = [
        ("ratchet", [py, "tools/quality/ratchet.py"], None),
        (
            "import contracts",
            [py, "-c", "import sys; from importlinter.cli import lint_imports_command as c; sys.exit(c())"],
            None,
        ),
        ("spec traceability", [py, "tools/quality/spec_check.py"], None),
        ("shadow rules list", [py, "tools/quality/shadow_rules.py", "--check", "docs/spec/shadow-rules.md"], None),
    ]
    typed = [p for p in TYPED_PACKAGES if (ROOT / p).exists()]
    if typed:
        steps.append(("mypy strict", [py, "-m", "mypy", *typed], None))
        # The alpha ships on Windows: type-check the Windows branches too, whatever this machine is (issue #66).
        other = "linux" if sys.platform == "win32" else "win32"
        steps.append((f"mypy strict ({other})", [py, "-m", "mypy", "--platform", other, *typed], None))
    steps += [(title, cmd, None) for title, cmd in web_steps(full=not args.static)]
    if args.binding:  # the PyQt5 session restricted to Qt-independent tests, then the whole PySide6 session
        unit = {"PAR_TEST_QT_BINDING": "PyQt5"}
        steps.append(("tests (Qt-independent)", [py, "-m", "pytest", "-m", "unit and not hardware"], unit))
        env = {"PAR_TEST_QT_BINDING": args.binding}
        steps.append((f"tests ({args.binding})", [py, "-m", "pytest", "-m", "not hardware"], env))
    elif not args.static:
        for binding in QT_BINDINGS:
            env = {"PAR_TEST_QT_BINDING": binding}
            steps.append((f"tests ({binding})", [py, "-m", "pytest", "-m", "not hardware"], env))
    failed = [title for title, cmd, env in steps if not run(title, cmd, env)]
    print("\nall checks passed" if not failed else f"\nFAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
