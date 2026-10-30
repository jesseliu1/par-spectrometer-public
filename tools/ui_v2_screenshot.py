"""Screenshot a built page (history or DLI) with a headless Chromium browser (development aid, not a test).

Usage:
  python tools/ui_v2_screenshot.py OUT_DIR [--page history|dli] [--browser PATH] [--scales 1 1.5]

Files are written as <page>-<scale %>.png. For the DLI page the demo database has one record per minute (the
default allowed gap is 120 s) and the page is opened with ?view=dli.

Starts the service with web/dist on a temporary data directory, imports a synthetic V1.0.x database
(tools/ui_v2_demo_db.py), and runs `<browser> --headless --screenshot` once per scale factor, 1600×960 CSS
pixels (--height for a taller page). The browser is $PAR_SCREENSHOT_BROWSER, --browser, or a local Chrome or
Edge. Background networking of the browser is switched off and a throw-away profile is used. On macOS the scale
factor only approximates Windows display scaling; the authoritative screenshots are taken on Windows at 100 % and
150 % (13_ section 5).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_shell.service import ServiceProcess  # noqa: E402
from par_shell.window import page_url  # noqa: E402
from tools import ui_v2_demo_db  # noqa: E402
from tools.ui_v2_dev import _post  # noqa: E402

BROWSER_ENV = "PAR_SCREENSHOT_BROWSER"
CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)
WIDTH, HEIGHT = 1600, 960
RENDER_BUDGET_MS = 8000
QUIET_FLAGS = (
    "--headless=new",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-features=Translate,OptimizationHints,MediaRouter",
)


def find_browser(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get(BROWSER_ENV), *CANDIDATES):
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--browser", default=None)
    parser.add_argument("--scales", type=float, nargs="+", default=[1.0, 1.5])
    parser.add_argument("--page", choices=("history", "dli"), default="history")
    parser.add_argument("--height", type=int, default=HEIGHT, help=f"CSS pixels (default {HEIGHT})")
    args = parser.parse_args(argv)
    browser = find_browser(args.browser)
    if browser is None:
        print("no Chrome/Edge found: set PAR_SCREENSHOT_BROWSER", file=sys.stderr)
        return 1
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("web/dist is not built: run npm run build in web/", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory() as scratch,
        ServiceProcess(Path(scratch) / "alpha", ROOT / "web" / "dist") as svc,
    ):
        info = svc.start()
        source = Path(scratch) / "source" / "温室1号.sqlite3"
        ui_v2_demo_db.main([str(source), *(["--every-minutes", "1"] if args.page == "dli" else [])])
        _post(info, "/api/v0/snapshots", {"source_path": str(source), "position": 1})
        for scale in args.scales:
            target = args.out_dir / f"{args.page}-{int(scale * 100)}.png"
            subprocess.run(
                [
                    browser,
                    *QUIET_FLAGS,
                    f"--user-data-dir={Path(scratch) / 'profile'}",
                    f"--window-size={WIDTH},{args.height}",
                    f"--force-device-scale-factor={scale}",
                    f"--virtual-time-budget={RENDER_BUDGET_MS}",
                    f"--screenshot={target}",
                    page_url(info).replace("/#", "/?view=dli#") if args.page == "dli" else page_url(info),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
            print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
