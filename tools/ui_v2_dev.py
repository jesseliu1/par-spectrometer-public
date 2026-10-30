"""One command for 2.0.0-alpha front-end development: the local service plus the Vite dev server.

Usage:
  python tools/ui_v2_dev.py [--demo] [--data-dir DIR] [--no-vite]

* Starts `python -m par_app.api` on 127.0.0.1 (random port) with a DEVELOPMENT data directory
  (default ~/.local/share/PAR_Spectrometer_2-dev, never the real alpha one), serving web/dist when built.
* --demo writes two synthetic V1.0.x databases (tools/ui_v2_demo_db.py) under <data dir>/demo-sources and imports
  them as snapshots p1/p2 (only when they are not there yet). Never point it at a field database (R-4-7).
* Then runs `npm run dev` in web/ with PAR_ALPHA_DATA_DIR set, so the Vite proxy (web/dev-proxy.ts) finds
  service.json and adds the token: open http://127.0.0.1:5173/. Ctrl+C stops both.
See tools/ui_v2_dev.md.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app.domain.clock import SystemClock  # noqa: E402
from par_shell.service import DATA_DIR_ENV, ServiceInfo, ServiceProcess  # noqa: E402
from tools import ui_v2_demo_db  # noqa: E402

WEB = ROOT / "web"
DEV_DATA_DIR = Path.home() / ".local" / "share" / "PAR_Spectrometer_2-dev"
DEMO_SOURCES = (("温室1号", 1, 10, 0), ("育苗室", 2, 30, 1))
"""(name, position, minutes between records, days back): two made-up devices."""


def _post(info: ServiceInfo, path: str, body: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        info.base_url + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-PAR-Token": info.token},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        result: dict[str, object] = json.loads(response.read().decode("utf-8"))
    return result


def import_demo(info: ServiceInfo, data_dir: Path, today: date | None = None) -> None:
    today = today or SystemClock().now().date()
    for name, position, minutes, days_back in DEMO_SOURCES:
        source = data_dir / "demo-sources" / f"{name}.sqlite3"
        if source.exists():
            continue
        day = (today - timedelta(days=days_back)).isoformat()
        ui_v2_demo_db.main([str(source), "--day", day, "--every-minutes", str(minutes)])
        _post(info, "/api/v0/snapshots", {"source_path": str(source), "position": position})
        print(f"imported demo snapshot {name} as p{position}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEV_DATA_DIR, help=f"default {DEV_DATA_DIR}")
    parser.add_argument("--demo", action="store_true", help="create and import two synthetic databases")
    parser.add_argument("--no-vite", action="store_true", help="only the service (open its URL with the token)")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.resolve()
    web_dir = WEB / "dist" if (WEB / "dist" / "index.html").is_file() else None
    with ServiceProcess(data_dir, web_dir) as service:
        info = service.start()
        print(f"service {info.version} on {info.base_url} (data {data_dir})", flush=True)
        if args.demo:
            import_demo(info, data_dir)
        if web_dir is not None:
            print(f"built page: {info.base_url}/#token={info.token}", flush=True)
        if args.no_vite:
            input("press Enter to stop the service\n")
            return 0
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if npm is None:
            print("npm not found: install Node 22 (see tools/ui_v2_dev.md)", file=sys.stderr)
            return 1
        print("dev page: http://127.0.0.1:5173/  (Ctrl+C stops both)", flush=True)
        try:
            return subprocess.call([npm, "run", "dev"], cwd=WEB, env={**os.environ, DATA_DIR_ENV: str(data_dir)})
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
