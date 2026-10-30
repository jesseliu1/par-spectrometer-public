"""requirements.txt must not admit a pymodbus that the Modbus-TCP path cannot run on (old #4).

par_app/protocol.py passes `device_id=` to read_*/write_register(s) and overrides `ModbusTcpClient.send(request, addr)`.
pymodbus renamed `slave=` to `device_id=` in 3.10.0 (API_changes.rst, "API changes 3.10.0"); on 3.7-3.9 the keyword
raises TypeError and on 3.6.x the `send` override fails, so every TCP read/write fails on those versions.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version
from pymodbus.client import ModbusTcpClient

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
FIRST_DEVICE_ID_RELEASE = Version("3.10.0")


def _requirement(path: Path, name: str) -> Requirement:
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.split("#", 1)[0].strip()
        if text and not text.startswith("-") and Requirement(text).name.lower() == name:
            return Requirement(text)
    raise AssertionError(f"{name} not declared in {path.name}")


@pytest.mark.spec("CONF-052")
def test_pymodbus_floor_matches_tcp_api_in_use() -> None:
    declared = _requirement(ROOT / "requirements.txt", "pymodbus").specifier
    for too_old in ("3.6.0", "3.6.9", "3.7.4", "3.8.6", "3.9.2"):
        assert not declared.contains(too_old), f"requirements.txt admits pymodbus {too_old} (no device_id=)"
    lower_bounds = [Version(spec.version) for spec in declared if spec.operator in (">=", ">", "==", "~=", "===")]
    assert lower_bounds, "requirements.txt declares no lower bound for pymodbus"
    assert all(bound >= FIRST_DEVICE_ID_RELEASE for bound in lower_bounds), f"pymodbus floor < 3.10.0: {declared}"
    assert declared.contains(str(FIRST_DEVICE_ID_RELEASE))
    locked = _requirement(ROOT / "requirements.lock", "pymodbus").specifier
    assert all(declared.contains(spec.version) for spec in locked), "requirements.lock falls outside requirements.txt"
    # The keyword and override shapes the TCP path relies on, checked against the installed (locked) pymodbus.
    for method in ("read_holding_registers", "read_input_registers", "write_register", "write_registers"):
        assert "device_id" in inspect.signature(getattr(ModbusTcpClient, method)).parameters, method
    assert list(inspect.signature(ModbusTcpClient.send).parameters)[:3] == ["self", "request", "addr"]
