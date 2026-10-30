"""SYNTHETIC V1.0.x-format history database for the alpha self-test (main_v2.py --alpha-self-test).

The self-test's tier-1 kit puts a byte copy of this file in as the one device's database and reads one record back
(issue #82: the pages read only the alpha's own device databases). It is written by ParDatabase
itself, so it has exactly the tables a V1.0.3 installation creates; the records are made up (a flat spectrum, fixed
times on one day). It refuses to touch an existing file, so it can never write a real database (R-4-7), and it is
only ever created in the self-test's own temporary folder.
"""

from __future__ import annotations

import json
from pathlib import Path

from .database import ParDatabase
from .math_ops import WAVELENGTHS, software_metrics

RECORD_TIMES = ("2026-01-01T10:00:00.000", "2026-01-01T10:01:00.000", "2026-01-01T10:02:00.000")
"""Beijing time, V1.0.x's stored format. The self-test queries this day."""
DAY_START = "2026-01-01T00:00:00.000"
DAY_END = "2026-01-01T23:59:59.999"
FLAT_RAW_LEVEL = 1000
"""Raw count of every point of the made-up spectrum (not a measurement)."""
SPECTRAL_COEFFICIENT = 3
"""Made up: any coefficient V1.0.x accepts; the self-test checks that a record comes back, not its values."""
ELAPSED_MS = 5000.0
"""Made up acquisition duration (the column is NOT NULL)."""


def write_synthetic_database(path: Path) -> int:
    """Create `path` with len(RECORD_TIMES) successful records; returns that count."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}: the self-test only writes new synthetic files")
    path.parent.mkdir(parents=True, exist_ok=True)
    database = ParDatabase(path)
    raw = [FLAT_RAW_LEVEL] * len(WAVELENGTHS)
    metrics = json.dumps(software_metrics(raw, SPECTRAL_COEFFICIENT))
    for index, acquired_at in enumerate(RECORD_TIMES):
        database.save_acquisition(
            {
                "acquired_at": acquired_at,
                "mcu_time_ms": index,
                "success": 1,
                "initialized": 1,
                "need_power_cycle": 0,
                "raw_data_valid": 1,
                "calculate_data_valid": 1,
                "stop_status": 0,
                "spectral_coefficient": SPECTRAL_COEFFICIENT,
                "exposure_status": 0,
                "elapsed_ms": ELAPSED_MS,
                "software_metrics_json": metrics,
                "mcu_params_json": json.dumps({}),
                "raw_points": raw,
                "quality_json": json.dumps({"strategy": "single_capture", "acquisition_status": "completed"}),
                "dli_eligible": 1,
            }
        )
    return len(RECORD_TIMES)
