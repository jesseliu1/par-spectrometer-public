"""The top bar's run status (issue #73): V1.0.3's "总线：… ｜ 采集…" block and its red failure lines, from the state
cache (MainWindow._on_bus_state, MainWindow._refresh_communication_events; UI-253, UI-252, UI-137..UI-147, UI-150).

The texts are V1.0.3's word for word: like v1_texts, `run_status.SOURCES` names the V1.0.3 function of every text
and the literal parts are looked up among that function's string constants.
"""

from __future__ import annotations

from typing import Any

import pytest

from par_app.application import run_status
from par_app.application.run_status import run_status as derive
from tests.acquisition.test_maintenance_texts import _constants, _parts

pytestmark = [pytest.mark.unit, pytest.mark.spec("UI-253 UI-252 UI-137 UI-142 UI-143 UI-146 UI-147 UI-150")]

PORT_FAILED = "总线连接失败：could not open port 'COM6': FileNotFoundError"


def _device(name: str, slave_id: int, **changes: Any) -> dict[str, Any]:  # noqa: ANN401 (a snapshot value)
    device = {
        "key": name,
        "name": name,
        "slave_id": slave_id,
        "enabled": True,
        "online": True,
        "level": "ok",
        "message": "采集成功",
        "failures": 0,
        "excluded": False,
        "last_failure_at": None,
    }
    device.update(changes)
    return device


def _failing(name: str, slave_id: int, failures: int, *, stop: bool = False) -> dict[str, Any]:
    if stop:
        message = f"连续第 {failures}/10 次尝试失败：{PORT_FAILED}"
        message += "；已退出本次采集，重启软件后重新尝试" if failures >= 10 else ""
    else:
        message = f"连续第 {failures} 次尝试失败：{PORT_FAILED}（未启用失败停止，将继续按周期重试）"
    return _device(
        name,
        slave_id,
        online=False,
        level="error" if stop and failures >= 10 else "warning",
        message=message,
        failures=failures,
        excluded=stop and failures >= 10,
        last_failure_at="2026-10-26T09:00:00.123",
    )


def _snapshot(*devices: dict[str, Any], bus: tuple[str, str] = ("ok", "总线已连接"), **changes: Any) -> dict[str, Any]:  # noqa: ANN401
    snapshot = {
        "takeover": "running",
        "bus": {"level": bus[0], "message": bus[1]},
        "halt": None,
        "maintenance": False,
        "configured": True,
        "devices": list(devices),
    }
    snapshot.update(changes)
    return snapshot


def test_running_normally_reads_connected_and_normal_with_no_failure_lines() -> None:
    status = derive(_snapshot(_device("North", 1), _device("South", 2)))
    assert status["bus"] == {"text": "总线：已连接", "level": "ok", "detail": "总线已连接"}
    assert status["acquisition"] == {"text": "正常采集", "level": "ok"}
    assert status["failures"] == []  # UI-142: hidden while every device acquires


def test_port_that_cannot_open_reads_bus_error_waiting_and_the_failure_line() -> None:
    """Issue #73 criteria 1 and 2: 采集运行中 with its state, 总线 异常, the reason, the count and 将继续按周期重试."""
    status = derive(_snapshot(_failing("North", 1, 17), bus=("error", PORT_FAILED)))
    assert status["bus"] == {"text": "总线：异常", "level": "error", "detail": PORT_FAILED}
    assert status["acquisition"] == {"text": "采集运行中：等待设备响应", "level": "warn"}
    assert status["failures"] == [
        f"2026-10-26 09:00:00.123  North（地址 1）  连续第 17 次尝试失败：{PORT_FAILED}"
        "（未启用失败停止，将继续按周期重试）"
    ]


def test_one_device_failing_while_another_acquires_reads_partly_abnormal() -> None:
    status = derive(_snapshot(_device("North", 1), _failing("South", 2, 3)))
    assert status["acquisition"] == {"text": "采集运行中：部分设备异常", "level": "ok"}
    assert [line.split("  ")[1] for line in status["failures"]] == ["South（地址 2）"]  # UI-137, UI-143


def test_every_enabled_device_stopped_after_failures_reads_red_stopped_and_says_so() -> None:
    status = derive(_snapshot(_failing("North", 1, 10, stop=True), _device("Off", 3, enabled=False, online=False)))
    assert status["acquisition"] == {"text": "采集停止中：无可采集设备，重启软件后重新尝试", "level": "error"}
    assert status["failures"][0].endswith(f"连续第 10/10 次尝试失败：{PORT_FAILED}；已退出本次采集，重启软件后重新尝试")


def test_disabled_devices_are_left_out() -> None:
    off = _failing("Off", 3, 4) | {"enabled": False}
    status = derive(_snapshot(_device("North", 1), off))
    assert status["failures"] == [] and status["acquisition"]["text"] == "正常采集"
    assert derive(_snapshot(off))["acquisition"]["text"] == "采集停止中：无可采集设备，重启软件后重新尝试"


@pytest.mark.parametrize(
    ("resume_unconfirmed", "bus_text"), [(False, "总线：已停止（硬件异常）"), (True, "总线：已停止（恢复未确认）")]
)
def test_a_halt_reads_stopped_in_red_with_the_coordinator_message(resume_unconfirmed: bool, bus_text: str) -> None:
    message = "采集停止中：North（地址 1）需要重新上电；所有设备的后台采集已停止"
    halt = {"message": message, "resume_unconfirmed": resume_unconfirmed, "text": "…"}
    status = derive(_snapshot(_device("North", 1, online=False), halt=halt, bus=("error", "x")))
    assert status["bus"] == {"text": bus_text, "level": "error", "detail": message}
    assert status["acquisition"] == {"text": message, "level": "error"}  # UI-150


def test_maintenance_reads_paused_bus_and_red_acquisition() -> None:
    status = derive(
        _snapshot(_device("North", 1), maintenance=True, bus=("warning", "维护模式：采集、对时和自动重连已停止"))
    )
    assert status["bus"] == {
        "text": "总线：已暂停（维护模式）",
        "level": "warn",
        "detail": "维护模式：采集、对时和自动重连已停止",
    }
    assert status["acquisition"] == {"text": "采集停止中：设备维护模式", "level": "error"}


@pytest.mark.parametrize(
    ("bus", "configured", "text", "level"),
    [
        (("warning", "正在连接 COM7 …"), True, "总线：连接中…", "warn"),
        (("idle", "维护已结束，等待连接"), True, "总线：等待连接", "muted"),
        (("idle", "未在采集"), False, "总线：未连接", "muted"),
        (("warning", "其他等待"), True, "总线：等待 / 暂停", "warn"),
    ],
)
def test_bus_summaries(bus: tuple[str, str], configured: bool, text: str, level: str) -> None:
    status = derive(_snapshot(_device("North", 1, online=False), bus=bus, configured=configured))
    assert status["bus"] == {"text": text, "level": level, "detail": bus[1]}


def test_unconfigured_reads_waiting_for_configuration() -> None:
    status = derive(_snapshot(bus=("idle", "未在采集"), configured=False))
    assert status["acquisition"] == {"text": "等待配置，尚未采集", "level": "muted"}


@pytest.mark.parametrize("name", sorted(run_status.SOURCES))
def test_text_is_v103_wording(name: str) -> None:
    file, function = run_status.SOURCES[name]
    constants = _constants(file, function)
    for part in _parts(getattr(run_status, name)):
        assert any(part in constant for constant in constants), f"{name}: {part!r} not in {file}:{function}"


def test_every_text_has_a_source() -> None:
    names = {name for name, value in vars(run_status).items() if name.isupper() and isinstance(value, (str, dict))}
    names = {name for name in names if not name.startswith("_")}
    names -= {"MAIN_WINDOW", "SOURCES", "ALPHA_TEXTS", *run_status.ALPHA_TEXTS}
    assert names <= set(run_status.SOURCES), names - set(run_status.SOURCES)


SILENT = "所有启用的设备都不响应，将继续按周期重试"


@pytest.mark.parametrize("bus", [("ok", "总线已连接"), ("warning", "正在连接 COM6 …"), ("idle", "等待连接")])
def test_every_enabled_device_not_responding_reads_bus_abnormal(bus: tuple[str, str]) -> None:
    """Issue #131 (owner 2026-10-28): the port is open but no enabled device answers; between rounds the bus is
    reconnected, so the bus line says 已连接 or 连接中, which looked normal on site. A disabled device does not
    count."""
    off = _device("Off", 3, enabled=False)
    status = derive(_snapshot(_failing("North", 1, 2), _failing("South", 2, 1), off, bus=bus))
    assert status["bus"] == {"text": "总线：异常", "level": "error", "detail": SILENT, "devices_silent": True}
    assert status["acquisition"] == {"text": "采集运行中：等待设备响应", "level": "warn"}
    assert len(status["failures"]) == 2  # the red lines name each device, its count and 将继续按周期重试


def test_some_devices_answering_or_none_tried_yet_keep_the_bus_line() -> None:
    """Issue #131: only some devices silent stays 已连接 with 部分设备异常; before the first round nothing has
    failed yet."""
    partly = derive(_snapshot(_device("North", 1), _failing("South", 2, 3)))
    assert partly["bus"]["text"] == "总线：已连接" and "devices_silent" not in partly["bus"]
    assert partly["acquisition"]["text"] == "采集运行中：部分设备异常"
    fresh = _device("North", 1, online=False, message="尚未采集")
    assert derive(_snapshot(fresh))["bus"]["text"] == "总线：已连接"


def test_devices_left_out_after_failure_stop_count_as_not_answering() -> None:
    """review of the PR: a device out of this run (failure stop reached) did not answer either; only a device
    that answers keeps 已连接 (负责人: 所有启用的设备都不响应 → 异常, no exception for failure stop)."""
    out = _failing("North", 1, 10, stop=True)
    assert derive(_snapshot(out, _device("South", 2)))["bus"]["text"] == "总线：已连接"
    assert derive(_snapshot(out, _failing("South", 2, 4)))["bus"]["text"] == "总线：异常"
    alone = derive(_snapshot(out))
    assert alone["bus"]["text"] == "总线：异常"
    assert alone["acquisition"]["text"] == "采集停止中：无可采集设备，重启软件后重新尝试"


def test_a_halt_maintenance_or_a_port_error_keep_their_own_bus_line() -> None:
    silent = _failing("North", 1, 3)
    halted = derive(_snapshot(silent, halt={"message": "锁停", "resume_unconfirmed": True}))
    assert halted["bus"]["text"] == "总线：已停止（恢复未确认）"
    assert derive(_snapshot(silent, maintenance=True))["bus"]["text"] == "总线：已暂停（维护模式）"
    port = derive(_snapshot(silent, bus=("error", PORT_FAILED)))
    assert port["bus"] == {"text": "总线：异常", "level": "error", "detail": PORT_FAILED}
