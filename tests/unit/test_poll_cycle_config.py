"""Polling cycle read from config/app_config.json stays within 40~3600 s (POLL-003, POLL-037; DEF-01).

`json.loads` accepts the literal `NaN`. NaN has no order, so the existing min/max clamp in
`AppConfig.effective_poll_cycle_seconds` returned NaN and `PollingCoordinator.run` stopped polling after the
first cycle without any message. Every non-finite value (NaN, +/-Infinity, a float overflow such as 1e309,
or a string that float() turns into one of these) is rejected as a corrupt config, the same flow as an
unreadable config file (D-141). Finite out-of-range values keep the existing clamp. These tests drive the
real loader; nothing is mocked.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from par_app.app_config import AppConfigStore, StartupConfigurationError
from par_app.models import MAX_POLL_CYCLE_SECONDS, MIN_POLL_CYCLE_SECONDS, AppConfig

pytestmark = pytest.mark.unit


def _write_config(root: Path, poll_literal: str) -> None:
    path = root / "config" / "app_config.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"bus": {"serial_port": "COM3", "poll_cycle_seconds": ' + poll_literal + '}, '
        '"devices": [], "configured": true}',
        encoding="utf-8",
    )


NON_FINITE_LITERALS = ["NaN", "Infinity", "-Infinity", "1e309", "-1e309", '"inf"', '"-inf"', '"nan"']


@pytest.mark.spec("POLL-003", "POLL-037")
@pytest.mark.parametrize("literal", NON_FINITE_LITERALS)
def test_startup_rejects_non_finite_poll_cycle_with_visible_reason(tmp_path: Path, literal: str) -> None:
    _write_config(tmp_path, literal)
    with pytest.raises(StartupConfigurationError) as caught:
        AppConfigStore(tmp_path).load_for_startup()
    # main.create_startup_hub shows this text in the "配置或数据库不可用" dialog.
    assert "poll_cycle_seconds" in str(caught.value)


@pytest.mark.spec("POLL-003", "POLL-037")
@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("1e9", MAX_POLL_CYCLE_SECONDS),
        ("-1e9", MIN_POLL_CYCLE_SECONDS),
        ("0", MIN_POLL_CYCLE_SECONDS),
        ("120", 120.0),
    ],
)
def test_finite_poll_cycle_keeps_existing_clamp(tmp_path: Path, literal: str, expected: float) -> None:
    _write_config(tmp_path, literal)
    config = AppConfigStore(tmp_path).load_for_startup()
    assert config.bus.poll_cycle_seconds == expected
    assert config.effective_poll_cycle_seconds() == expected


@pytest.mark.spec("POLL-037")
@pytest.mark.parametrize("literal", NON_FINITE_LITERALS)
def test_model_never_yields_non_finite_cycle(literal: str) -> None:
    payload = json.loads('{"bus": {"poll_cycle_seconds": ' + literal + '}, "configured": true}')
    with pytest.raises(ValueError, match="poll_cycle_seconds"):
        AppConfig.from_dict(payload)
    assert math.isfinite(AppConfig.from_dict({"bus": {}}).effective_poll_cycle_seconds())
