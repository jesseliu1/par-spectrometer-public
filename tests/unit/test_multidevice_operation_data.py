"""verify_multidevice.py:57-94 verify_operation_data(): spectrum arithmetic and operation record queries.

Migrated from the script-style regression (R-3-4); mapping in tests/migration/verify_multidevice.md.
No Qt, no hardware: math_ops and a temporary SQLite database only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from par_app.database import ParDatabase
from par_app.math_ops import combine, ratio_display_mask

pytestmark = pytest.mark.unit


def test_divide_and_common_ratio_display_threshold() -> None:
    """Division leaves undefined points as NaN; the ratio display mask uses one threshold for A and B."""
    numerator = np.array([6.0, 0.0, 2.0, 0.0, 1.0e12, -6.0])
    denominator = np.array([3.0, 0.0, 0.0, 3.0, 1.0, 3.0])
    np.testing.assert_allclose(
        combine(numerator, denominator, 'divide'), [2.0, np.nan, np.nan, 0.0, 1.0e12, -2.0], equal_nan=True
    )
    assert np.isnan(combine(np.array([np.inf, np.nan, 1.0e308]), np.array([1.0, 1.0, 1.0e-308]), 'divide')).all()
    numerator = np.array([100.0, 2.0, 1.99, 0.0, 50.0, 6.0])
    denominator = np.array([20.0, 2.0, 10.0, 0.0, 0.0, 1.99])
    threshold, mask = ratio_display_mask(numerator, denominator)
    assert threshold == 2.0
    np.testing.assert_array_equal(mask, [True, True, False, False, False, False])
    swapped_threshold, swapped_mask = ratio_display_mask(denominator, numerator)
    assert swapped_threshold == threshold
    np.testing.assert_array_equal(mask, swapped_mask)
    assert not ratio_display_mask(np.zeros(701), np.zeros(701))[1].any()
    assert not ratio_display_mask(np.full(701, np.nan), np.zeros(701))[1].any()


def test_operation_spectra_window_and_nearest_record(tmp_path: Path) -> None:
    """Only the newest 500 valid full spectra are offered; nearest lookup handles time zones and bad input."""
    database = ParDatabase(tmp_path / 'records.sqlite3')
    with database.connect() as connection:
        for index in range(505):
            stamp = (datetime(2026, 9, 18) + timedelta(seconds=index * 40)).isoformat()
            record_id = connection.execute(
                'INSERT INTO acquisitions(acquired_at,success,elapsed_ms) VALUES(?,1,1)', (stamp,)
            ).lastrowid
            connection.execute('INSERT INTO spectra VALUES(?,?)', (record_id, json.dumps([index] * 701)))
    for success, points in ((0, [1] * 701), (1, [1] * 700), (1, None)):
        database.save_acquisition(
            dict(acquired_at='2026-09-18T00:00:01', success=success, elapsed_ms=1, raw_points=points)
        )
    assert len(database.operation_spectra()) == 500
    assert all(row['id'] > 5 for row in database.operation_spectra())
    assert database.nearest_operation_spectrum('2026-09-18T00:00:01')['id'] == 1
    assert database.nearest_operation_spectrum('2026-09-18T00:00:39')['id'] == 2
    assert database.nearest_operation_spectrum('2026-09-18T00:00:20')['id'] == 1
    assert database.nearest_operation_spectrum('2026-09-17T16:00:01+00:00')['id'] == 1
    with database.connect() as connection:
        connection.execute("UPDATE acquisitions SET acquired_at='2026-09-17T16:00:00+00:00' WHERE id=1")
    assert database.nearest_operation_spectrum('2026-09-18T00:00:01')['id'] == 1
    assert database.nearest_operation_spectrum('invalid') is None
    assert database.acquisition_summary()['total'] == 508
