"""Register SYNTHETIC device databases in a fresh alpha data directory, for the web e2e tests.

The pages read only the alpha's own device databases (issue #82), so the shared e2e service of web/e2e/setup.ts has
these devices in its configuration. The tier is left at 0: setup.ts raises it to 1 through the API once the service
runs, so the service does not start acquiring by itself (#92 starts a takeover only when it starts in tier 1) and no
port is ever opened. The configuration is
written by V1.0.3's AppConfigStore (same format as a saved configuration, 16_ 3.1); every database must already lie
under <data dir>/data/devices (tools/ui_v2_demo_db.py writes them). Test data only: it refuses a data directory that
already holds a configuration.

    python tools/ui_v2_e2e_devices.py <data dir> <name> <database> [<name> <database> ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app.app_config import AppConfigStore  # noqa: E402
from par_app.application.paths import AlphaPaths  # noqa: E402
from par_app.models import AppConfig, DeviceConfig  # noqa: E402


def register(data_dir: Path, devices: list[tuple[str, Path]]) -> None:
    paths = AlphaPaths(data_dir)
    store = AppConfigStore(data_dir)
    if store.path.exists():
        raise FileExistsError(f"refusing to overwrite {store.path}: only a fresh e2e data directory is set up")
    for _name, database in devices:
        if not paths.holds_device_database(database):
            raise ValueError(f"{database} is not under {paths.devices_dir}")
    config = AppConfig(
        devices=[
            DeviceConfig(name=name, slave_id=index + 1, database_path=str(database.resolve()))
            for index, (name, database) in enumerate(devices)
        ],
        configured=True,
    )
    store.save(config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("pairs", nargs="+", help="name database name database ...")
    args = parser.parse_args(argv)
    if len(args.pairs) % 2:
        parser.error("names and databases come in pairs")
    pairs = [(args.pairs[index], Path(args.pairs[index + 1])) for index in range(0, len(args.pairs), 2)]
    register(args.data_dir, pairs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
