from __future__ import annotations

import argparse
import json
import logging
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from par_device import PARDevice
from raw_spectral_process import (
    PHOTOMETRIC_PARAM_NAMES,
    apply_scientific_primary_metrics_to_spectral_data,
    build_processing_result,
    get_algorithm_coverage,
    photometric_params_to_dict,
)

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

try:
    from pymodbus.client.serial import ModbusSerialClient
except Exception as exc:
    raise RuntimeError(f"pymodbus 导入失败: {exc}") from exc

logging.getLogger("pymodbus").setLevel(logging.ERROR)

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None


TARGET_DEVICE_NAME = "Silicon Labs CP210x USB to UART Bridge"
PREFERRED_PORT = "COM4"
BAUDRATE = 115200
PARITY = "N"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT = 3
SLAVE_ID = 1

REPORT_DIR = Path(__file__).resolve().parent / "data_history" / "PAR" / "Validation"

HARDWARE_METRIC_FIELDS = [
    "cct",
    "lux",
    "ee",
    "WM2",
    "peak_cwl",
    "peak_spectrum",
    "par",
    "pfd",
    "ppfd",
    "pfd_r",
    "pfd_b",
    "pfd_g",
    "pfd_uv",
    "pfd_fr",
    "chl_a_value",
    "chl_b_value",
    "E_peak_cwl",
    "E_peak_spectrum",
    "E_par",
    "E_pfd",
    "E_ppfd",
    "E_pfd_r",
    "E_pfd_b",
    "E_pfd_g",
    "E_pfd_uv",
    "E_pfd_fr",
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
    "ra",
    "X",
    "Y",
    "Z",
    "duv",
    "u",
    "v",
    "x",
    "y",
    "Measurement_Certainty",
]

COMPUTED_ONLY_METRIC_FIELDS = ["mccree_ypfd"]

CHLOROPHYLL_METRIC_FIELDS = ["chl_a_value", "chl_b_value"]

STATUS_DISPLAY_LABELS = {
    "PROVISIONAL_OK": "暂时一致，但未冻结",
    "PROVISIONAL_DIFF": "存在偏差，且未冻结",
}


@dataclass(frozen=True)
class MetricComparison:
    name: str
    hardware: float | None
    computed: float | None
    abs_diff: float | None
    rel_diff_pct: float | None
    confidence: str
    status: str
    note: str


@dataclass(frozen=True)
class ValidationRunResult:
    port: str
    snapshots: list[dict[str, Any]]
    all_comparisons: list[list[MetricComparison]]
    report_path: Path | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="直接读取 PAR 硬件并验证 Python 光谱算法")
    parser.add_argument("--ui", action="store_true", help="启动简单界面")
    parser.add_argument("--cli", action="store_true", help="强制命令行模式")
    parser.add_argument("--port", default="", help="串口名，留空时自动匹配")
    parser.add_argument("--device-name", default=TARGET_DEVICE_NAME, help="自动匹配串口时使用的设备描述关键词")
    parser.add_argument("--preferred-port", default=PREFERRED_PORT, help="自动匹配时优先尝试的串口")
    parser.add_argument("--baudrate", type=int, default=BAUDRATE)
    parser.add_argument("--parity", default=PARITY)
    parser.add_argument("--stopbits", type=float, default=STOPBITS)
    parser.add_argument("--bytesize", type=int, default=BYTESIZE)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--slave-id", type=int, default=SLAVE_ID)
    parser.add_argument("--count", type=int, default=1, help="连续采样次数")
    parser.add_argument("--interval", type=float, default=1.0, help="多次采样的间隔秒数")
    parser.add_argument("--output-dir", default=str(REPORT_DIR), help="报告输出目录")
    parser.add_argument("--no-save", action="store_true", help="只打印结果，不写 JSON 报告")
    return parser.parse_args()


def _find_target_port(explicit_port: str, preferred_port: str, target_device_name: str) -> str:
    if explicit_port:
        return explicit_port
    if not list_ports:
        raise RuntimeError("serial.tools.list_ports 不可用，且未显式提供 --port")
    if preferred_port:
        for port in list_ports.comports():
            if port.device.upper() == preferred_port.upper():
                return port.device
    for port in list_ports.comports():
        description = port.description or ""
        if target_device_name in description:
            return port.device
    raise RuntimeError(f"未找到目标设备串口: {target_device_name}")


def _await_stop_status(device: PARDevice, expected: int, timeout_sec: float = 10.0) -> None:
    started = time.time()
    while time.time() - started < timeout_sec:
        status_obj = device.get_status_blocking(timeout=3)
        if int(status_obj.stop_status_to_user) == int(expected):
            return
        time.sleep(0.15)
    raise RuntimeError(f"等待 stop_status_to_user={expected} 超时")


def _set_stop(device: PARDevice, stop_value: int) -> None:
    future = device.set_stop(stop_value)
    if hasattr(future, "result"):
        future.result(timeout=2)


def capture_hardware_snapshot(device: PARDevice) -> dict[str, Any]:
    _set_stop(device, 1)
    _await_stop_status(device, 1)
    try:
        status_obj = device.get_status_blocking(timeout=5)
        spectral_obj = device.get_spectral_header_blocking(timeout=8)
        waves = device.get_wavelength_points_blocking(timeout=8)
        photometric = device.get_photometric_params_blocking(timeout=8)
        spectral_obj.wavelength_points_spectral_data = list(waves)
        spectral_obj.photometric_params = list(photometric)
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "par_sensor_status": asdict(status_obj),
            "spectral_data": asdict(spectral_obj),
        }
        return snapshot
    finally:
        try:
            _set_stop(device, 0)
            _await_stop_status(device, 0, timeout_sec=5.0)
        except Exception:
            pass


def _relative_diff_pct(hardware: float | None, computed: float | None) -> float | None:
    if hardware is None or computed is None:
        return None
    baseline = abs(hardware) if abs(hardware) > 1e-12 else 1.0
    return abs(computed - hardware) / baseline * 100.0


def _classify_metric(name: str, hardware: float | None, computed: float | None, confidence: str) -> str:
    if computed is None:
        if confidence == "unsupported":
            return "UNSUPPORTED"
        return "NO_CALC"
    if hardware is None:
        return "NO_HW"

    abs_diff = abs(computed - hardware)
    rel_diff_pct = _relative_diff_pct(hardware, computed) or 0.0

    if name in {"peak_cwl", "E_peak_cwl"}:
        return "OK" if abs_diff <= 0.5 else "DIFF"
    if name in {"peak_spectrum", "E_peak_spectrum"}:
        if abs_diff <= 0.002:
            return "OK"
        if abs_diff <= 0.02:
            return "WARN"
        return "DIFF"
    if name in {"par", "E_par"}:
        if abs_diff <= 0.05 or rel_diff_pct <= 5.0:
            return "OK"
        if abs_diff <= 0.2 or rel_diff_pct <= 15.0:
            return "WARN"
        return "DIFF"
    if name == "WM2":
        if abs_diff <= 0.05 or rel_diff_pct <= 0.5:
            return "OK"
        if abs_diff <= 0.2 or rel_diff_pct <= 2.0:
            return "WARN"
        return "DIFF"
    if name == "ee":
        if abs_diff <= 0.05 or rel_diff_pct <= 0.5:
            return "OK"
        if abs_diff <= 0.2 or rel_diff_pct <= 5.0:
            return "WARN"
        return "DIFF"
    if name in {"cct", "lux"}:
        if rel_diff_pct <= 2.0:
            return "OK"
        if rel_diff_pct <= 5.0:
            return "WARN"
        return "DIFF"
    if name in {"X", "Y", "Z"}:
        if abs_diff <= 15.0 or rel_diff_pct <= 1.0:
            return "OK"
        if abs_diff <= 30.0 or rel_diff_pct <= 3.0:
            return "WARN"
        return "DIFF"
    if name == "r15":
        if confidence == "provisional":
            if abs_diff <= 1.0 or rel_diff_pct <= 1.5:
                return "PROVISIONAL_OK"
            return "PROVISIONAL_DIFF"
        if abs_diff <= 0.5 or rel_diff_pct <= 1.0:
            return "OK"
        if abs_diff <= 1.0 or rel_diff_pct <= 3.0:
            return "WARN"
        return "DIFF"
    if name == "ra" or (name.startswith("r") and name[1:].isdigit() and name != "r15"):
        if abs_diff <= 0.2 or rel_diff_pct <= 0.5:
            return "OK"
        if abs_diff <= 0.5 or rel_diff_pct <= 2.0:
            return "WARN"
        return "DIFF"
    if name == "duv":
        if abs_diff <= 0.001:
            return "OK"
        if abs_diff <= 0.005:
            return "WARN"
        return "DIFF"
    if name in {"u", "v", "x", "y"}:
        if abs_diff <= 0.001:
            return "OK"
        if abs_diff <= 0.01:
            return "WARN"
        return "DIFF"
    if name in CHLOROPHYLL_METRIC_FIELDS:
        if confidence == "provisional":
            if abs_diff <= 0.2 or rel_diff_pct <= 10.0:
                return "PROVISIONAL_OK"
            return "PROVISIONAL_DIFF"
        if abs_diff <= 0.15 or rel_diff_pct <= 1.5:
            return "OK"
        if abs_diff <= 0.5 or rel_diff_pct <= 5.0:
            return "WARN"
        return "DIFF"
    if "pfd" in name or "ppfd" in name:
        if confidence == "provisional":
            if abs_diff <= 0.2 or rel_diff_pct <= 10.0:
                return "PROVISIONAL_OK"
            return "PROVISIONAL_DIFF"
        if abs_diff <= 0.15 or rel_diff_pct <= 1.5:
            return "OK"
        if abs_diff <= 0.5 or rel_diff_pct <= 5.0:
            return "WARN"
        return "DIFF"
    return "CHECK"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _display_status(status: str) -> str:
    return STATUS_DISPLAY_LABELS.get(status, status)


def _hardware_metric_map(spectral_data: dict[str, Any]) -> dict[str, float | None]:
    hardware_map = {field_name: _to_float(spectral_data.get(field_name)) for field_name in HARDWARE_METRIC_FIELDS}
    photometric_params = spectral_data.get("photometric_params") or []
    if photometric_params:
        for field_name, value in photometric_params_to_dict(photometric_params).items():
            if field_name in HARDWARE_METRIC_FIELDS:
                hardware_map[field_name] = _to_float(value)
    return hardware_map


def compare_snapshot(snapshot: dict[str, Any]) -> list[MetricComparison]:
    spectral_data = snapshot["spectral_data"]
    hardware_metric_map = _hardware_metric_map(spectral_data)
    result = build_processing_result(
        spectral_data["wavelength_points_spectral_data"],
        int(spectral_data["spectral_coefficient"]),
    )

    comparisons: list[MetricComparison] = []
    for field_name in HARDWARE_METRIC_FIELDS:
        hardware_value = hardware_metric_map.get(field_name)
        computed_value = _to_float(result.metrics.get(field_name))
        confidence = result.confidence.get(field_name, "hardware_only")
        note = result.notes.get(field_name, "")
        abs_diff = None if hardware_value is None or computed_value is None else abs(computed_value - hardware_value)
        rel_diff_pct = _relative_diff_pct(hardware_value, computed_value)
        comparisons.append(
            MetricComparison(
                name=field_name,
                hardware=hardware_value,
                computed=computed_value,
                abs_diff=abs_diff,
                rel_diff_pct=rel_diff_pct,
                confidence=confidence,
                status=_classify_metric(field_name, hardware_value, computed_value, confidence),
                note=note,
            )
        )
    return comparisons


def _computed_only_metric_map(snapshot: dict[str, Any]) -> dict[str, float | None]:
    spectral_data = snapshot["spectral_data"]
    result = build_processing_result(
        spectral_data["wavelength_points_spectral_data"],
        int(spectral_data["spectral_coefficient"]),
    )
    return {field_name: _to_float(result.metrics.get(field_name)) for field_name in COMPUTED_ONLY_METRIC_FIELDS}


def _project_scientific_primary_spectral(snapshot: dict[str, Any]) -> dict[str, Any]:
    return apply_scientific_primary_metrics_to_spectral_data(snapshot["spectral_data"])


def _build_chlorophyll_projection(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    spectral_data = snapshot["spectral_data"]
    projected = _project_scientific_primary_spectral(snapshot)
    projection: dict[str, dict[str, Any]] = {}
    for field_name in CHLOROPHYLL_METRIC_FIELDS:
        projection[field_name] = {
            "hardware_register": _to_float(spectral_data.get(field_name)),
            "python_scientific_primary": _to_float(projected.get(field_name)),
            "projected_backup_field": _to_float(projected.get(f"hardware_{field_name}")),
            "projected_source": projected.get(f"{field_name}_source"),
            "projected_confidence": projected.get(f"{field_name}_confidence"),
            "projected_note": projected.get(f"{field_name}_note"),
        }
    return projection


def _format_chlorophyll_projection_brief(field_name: str, row: dict[str, Any]) -> str:
    return (
        f"{field_name}: scientific_primary={_format_number(row['python_scientific_primary'])} | "
        f"hardware_{field_name}={_format_number(row['projected_backup_field'])}"
    )


def _format_chlorophyll_projection_detail(field_name: str, row: dict[str, Any]) -> str:
    return (
        f"current_dual_track: {field_name}={_format_number(row['python_scientific_primary'])} | "
        f"hardware_{field_name}={_format_number(row['projected_backup_field'])} | "
        f"source={row['projected_source']} | confidence={row['projected_confidence']}"
    )


def _format_number(value: float | None, digits: int = 6) -> str:
    if value is None:
        return "-"
    if abs(value - round(value)) < 1e-12:
        return str(int(round(value)))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def print_snapshot_report(index: int, snapshot: dict[str, Any], comparisons: Iterable[MetricComparison]) -> None:
    spectral_data = snapshot["spectral_data"]
    status_data = snapshot["par_sensor_status"]
    chlorophyll_projection = _build_chlorophyll_projection(snapshot)
    computed_only_metrics = _computed_only_metric_map(snapshot)
    print()
    print(f"=== Capture #{index} ===")
    print(
        "timestamp="
        f"{snapshot['timestamp']} | exposure_status={status_data.get('exposure_status')} | "
        f"exposure_us={status_data.get('current_exposure_us')} | coef={spectral_data.get('spectral_coefficient')}"
    )
    print(
        f"initialized={status_data.get('initialized')} | communication_ok={status_data.get('communication_ok')} | "
        f"wave_count={len(spectral_data.get('wavelength_points_spectral_data', []))} | photometric_count={len(spectral_data.get('photometric_params', []))}"
    )
    print(
        f"{'metric':<24} {'hardware':>14} {'calc':>14} {'abs_diff':>12} {'rel%':>9} {'confidence':>12} {'status':>18}"
    )
    for item in comparisons:
        rel_text = "-" if item.rel_diff_pct is None else _format_number(item.rel_diff_pct, 3)
        print(
            f"{item.name:<24} {_format_number(item.hardware):>14} {_format_number(item.computed):>14} "
            f"{_format_number(item.abs_diff):>12} {rel_text:>9} {item.confidence:>12} {_display_status(item.status):>18}"
        )
        if item.note:
            print(f"  note: {item.note}")
    print("chlorophyll_dual_track:")
    for field_name in CHLOROPHYLL_METRIC_FIELDS:
        row = chlorophyll_projection[field_name]
        print("  " + _format_chlorophyll_projection_brief(field_name, row))
    if computed_only_metrics:
        print("computed_only_metrics:")
        for field_name in COMPUTED_ONLY_METRIC_FIELDS:
            print(f"  {field_name}: {_format_number(computed_only_metrics.get(field_name))}")


def print_aggregate_summary(all_comparisons: list[list[MetricComparison]]) -> None:
    if not all_comparisons:
        return
    metric_rows: dict[str, list[MetricComparison]] = {}
    for comparisons in all_comparisons:
        for item in comparisons:
            metric_rows.setdefault(item.name, []).append(item)

    print()
    print("=== Aggregate Summary ===")
    print(f"{'metric':<24} {'samples':>8} {'max_abs':>12} {'max_rel%':>10} {'worst_status':>18}")
    for metric_name in HARDWARE_METRIC_FIELDS:
        rows = metric_rows.get(metric_name, [])
        if not rows:
            continue
        abs_diffs = [row.abs_diff for row in rows if row.abs_diff is not None]
        rel_diffs = [row.rel_diff_pct for row in rows if row.rel_diff_pct is not None]
        status_order = {
            "DIFF": 7,
            "PROVISIONAL_DIFF": 6,
            "WARN": 5,
            "CHECK": 4,
            "PROVISIONAL_OK": 3,
            "OK": 2,
            "UNSUPPORTED": 1,
            "NO_CALC": 1,
            "NO_HW": 1,
        }
        worst_status = max(rows, key=lambda row: status_order.get(row.status, 0)).status
        print(
            f"{metric_name:<24} {len(rows):>8} {_format_number(max(abs_diffs) if abs_diffs else None):>12} "
            f"{_format_number(max(rel_diffs) if rel_diffs else None, 3):>10} {_display_status(worst_status):>18}"
        )


def print_computed_only_summary(snapshots: list[dict[str, Any]]) -> None:
    if not snapshots:
        return
    metric_rows: dict[str, list[float]] = {field_name: [] for field_name in COMPUTED_ONLY_METRIC_FIELDS}
    for snapshot in snapshots:
        metric_map = _computed_only_metric_map(snapshot)
        for field_name in COMPUTED_ONLY_METRIC_FIELDS:
            value = metric_map.get(field_name)
            if value is not None:
                metric_rows[field_name].append(value)

    print()
    print("=== Computed-only Summary ===")
    print(f"{'metric':<24} {'samples':>8} {'min':>12} {'max':>12} {'avg':>12}")
    for field_name in COMPUTED_ONLY_METRIC_FIELDS:
        values = metric_rows.get(field_name, [])
        if not values:
            continue
        print(
            f"{field_name:<24} {len(values):>8} {_format_number(min(values)):>12} {_format_number(max(values)):>12} {_format_number(sum(values) / len(values)):>12}"
        )


def save_report(output_dir: Path, port: str, snapshots: list[dict[str, Any]], all_comparisons: list[list[MetricComparison]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"light_algorithm_validation_{port}_{timestamp}.json"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "port": port,
        "capture_count": len(snapshots),
        "captures": [],
    }
    for snapshot, comparisons in zip(snapshots, all_comparisons):
        payload["captures"].append(
            {
                "snapshot": snapshot,
                "projected_scientific_primary_spectral": _project_scientific_primary_spectral(snapshot),
                "chlorophyll_projection": _build_chlorophyll_projection(snapshot),
                "computed_only_metrics": _computed_only_metric_map(snapshot),
                "comparisons": [asdict(item) for item in comparisons],
            }
        )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_status_summary(run_result: ValidationRunResult) -> str:
    coverage = get_algorithm_coverage()
    lines = [
        f"port={run_result.port}",
        f"captures={len(run_result.snapshots)}",
        f"confirmed={len(coverage['confirmed'])}",
        f"provisional={len(coverage['provisional'])}",
        f"unsupported={len(coverage['unsupported'])}",
    ]
    if run_result.report_path is not None:
        lines.append(f"report={run_result.report_path}")
    return " | ".join(lines)


def build_validation_conclusion(run_result: ValidationRunResult) -> str:
    total_metrics = 0
    status_counts: dict[str, int] = {}
    worst_items: list[tuple[int, MetricComparison]] = []

    for capture_index, comparisons in enumerate(run_result.all_comparisons, start=1):
        for item in comparisons:
            total_metrics += 1
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            if item.status in {"DIFF", "WARN", "PROVISIONAL_DIFF", "CHECK"}:
                worst_items.append((capture_index, item))

    worst_items.sort(
        key=lambda entry: (
            0 if entry[1].rel_diff_pct is None else -entry[1].rel_diff_pct,
            0 if entry[1].abs_diff is None else -entry[1].abs_diff,
        )
    )

    lines = [
        "本次验证结论",
        f"- 已完成采样 {len(run_result.snapshots)} 次，累计对比 {total_metrics} 个指标。",
        f"- OK: {status_counts.get('OK', 0)}，WARN: {status_counts.get('WARN', 0)}，DIFF: {status_counts.get('DIFF', 0)}，暂时一致但未冻结: {status_counts.get('PROVISIONAL_OK', 0)}，存在偏差且未冻结: {status_counts.get('PROVISIONAL_DIFF', 0)}，UNSUPPORTED: {status_counts.get('UNSUPPORTED', 0)}。",
    ]

    coverage = get_algorithm_coverage()
    lines.append(
        f"- 当前算法覆盖状态: confirmed {len(coverage['confirmed'])} 项，provisional {len(coverage['provisional'])} 项，unsupported {len(coverage['unsupported'])} 项。"
    )
    lines.append("- 新增计算专用指标 mccree_ypfd：它没有硬件寄存器对照项，当前只在算法侧输出，用于后续 McCree 加权链路验证与展示。")

    if status_counts.get("DIFF", 0) == 0 and status_counts.get("WARN", 0) == 0:
        lines.append("- 已确认口径字段整体与硬件输出一致，当前没有发现 confirmed 字段的明显异常项。")
    else:
        lines.append("- 已确认口径字段中存在需要关注的差异项，建议优先看下方列出的最大偏差指标。")

    if status_counts.get("PROVISIONAL_DIFF", 0) > 0 or status_counts.get("PROVISIONAL_OK", 0) > 0:
        lines.append("- provisional 字段仅表示当前可算但口径未冻结，结果可参考但不应直接作为最终替代依据。")

    chlorophyll_rows = [
        (capture_index, item)
        for capture_index, comparisons in enumerate(run_result.all_comparisons, start=1)
        for item in comparisons
        if item.name in CHLOROPHYLL_METRIC_FIELDS
    ]
    if chlorophyll_rows:
        chlorophyll_diff_count = sum(1 for _, item in chlorophyll_rows if item.status == "PROVISIONAL_DIFF")
        chlorophyll_ok_count = sum(1 for _, item in chlorophyll_rows if item.status == "PROVISIONAL_OK")
        lines.append(
            "- 叶绿素专项: 当前显示的算法值就是基于用户提供响应曲线算出的加权辐照度；"
            f"本次样本中 暂时一致但未冻结={chlorophyll_ok_count}，存在偏差且未冻结={chlorophyll_diff_count}。"
        )
        lines.append("- 报告中已同时写出 projected_scientific_primary_spectral 与 chlorophyll_projection，便于核对当前科学主值与硬件备份双轨语义。")
        lines.append("- 叶绿素 A/B 仍处于 provisional，原因是科学算法已可用，但硬件寄存器值与科学值的关系尚不稳定，当前不能把硬件值视为真值。")

    if coverage["unsupported"]:
        lines.append("- unsupported 字段目前没有仓库内可验证公式，因此脚本会明确标记为未完成，而不是给出伪结果。")

    if worst_items:
        lines.append("- 本次最值得看的差异项:")
        for capture_index, item in worst_items[:5]:
            lines.append(
                "  "
                f"capture {capture_index} | {item.name} | status={item.status} | "
                f"abs_diff={_format_number(item.abs_diff)} | rel_diff={_format_number(item.rel_diff_pct, 3)}%"
            )

    return "\n".join(lines)


def build_chlorophyll_diagnostics(run_result: ValidationRunResult) -> str:
    lines = [
        "叶绿素专项诊断",
        "- 当前算法值 = 400-699 nm 光谱按用户提供的 chl_a/chl_b 响应曲线做加权辐照度积分。",
        "- 当前结论 = 权重调用链已经接通，科学值可稳定计算；当前运行时应采用科学主值，硬件寄存器值只保留为备份。",
        "- 读表方式 = hardware 是设备寄存器值，computed 是当前 Python 科学值，abs_diff / rel_diff 用于观察硬件寄存器与科学值的偏离程度，而不是继续拟合硬件。",
    ]

    for capture_index, comparisons in enumerate(run_result.all_comparisons, start=1):
        projection = _build_chlorophyll_projection(run_result.snapshots[capture_index - 1])
        lines.append(f"- capture {capture_index}:")
        found_any = False
        for item in comparisons:
            if item.name not in CHLOROPHYLL_METRIC_FIELDS:
                continue
            found_any = True
            row = projection[item.name]
            lines.append(
                "  "
                f"{item.name}: hardware={_format_number(item.hardware)} | computed={_format_number(item.computed)} | "
                f"abs_diff={_format_number(item.abs_diff)} | rel_diff={_format_number(item.rel_diff_pct, 3)}% | "
                f"status={_display_status(item.status)}"
            )
            lines.append("  " + _format_chlorophyll_projection_detail(item.name, row))
            if row["projected_note"]:
                lines.append(f"  projected_note: {row['projected_note']}")
            if item.note:
                lines.append(f"  note: {item.note}")
        if not found_any:
            lines.append("  未发现叶绿素对比项")

    lines.append("- Measurement_Certainty 已按当前需求忽略，不参与叶绿素公式完成度判断。")
    return "\n".join(lines)


def _open_device(args: argparse.Namespace) -> tuple[str, Any, PARDevice]:
    port = _find_target_port(args.port, args.preferred_port, args.device_name)
    client = ModbusSerialClient(
        port=port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )
    if not client.connect():
        raise RuntimeError(f"串口打开失败: {port}")
    device = PARDevice(client, unit=args.slave_id, prefer_direct=True)
    return port, client, device


def run_validation_session(args: argparse.Namespace) -> ValidationRunResult:
    port, client, device = _open_device(args)
    snapshots: list[dict[str, Any]] = []
    all_comparisons: list[list[MetricComparison]] = []
    try:
        capture_count = max(1, int(args.count))
        for index in range(1, capture_count + 1):
            snapshot = capture_hardware_snapshot(device)
            comparisons = compare_snapshot(snapshot)
            snapshots.append(snapshot)
            all_comparisons.append(comparisons)
            if index < capture_count:
                time.sleep(max(0.0, float(args.interval)))
    finally:
        try:
            client.close()
        except Exception:
            pass

    report_path = None
    if not args.no_save:
        report_path = save_report(Path(args.output_dir), port.replace(':', '_'), snapshots, all_comparisons)
    return ValidationRunResult(
        port=port,
        snapshots=snapshots,
        all_comparisons=all_comparisons,
        report_path=report_path,
    )


def _all_rows(run_result: ValidationRunResult) -> list[tuple[int, MetricComparison]]:
    rows: list[tuple[int, MetricComparison]] = []
    for capture_index, comparisons in enumerate(run_result.all_comparisons, start=1):
        for item in comparisons:
            rows.append((capture_index, item))
    return rows


def _should_launch_ui(args: argparse.Namespace) -> bool:
    if args.cli:
        return False
    if args.ui:
        return True
    return False


class ValidationUi:
    def __init__(self, root: Any, args: argparse.Namespace):
        self.root = root
        self.args = args
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_result: ValidationRunResult | None = None

        self.root.title("光算法验证")
        self.root.geometry("1220x760")

        self.port_var = tk.StringVar(value=args.port or "")
        self.device_name_var = tk.StringVar(value=args.device_name)
        self.preferred_port_var = tk.StringVar(value=args.preferred_port)
        self.count_var = tk.StringVar(value=str(args.count))
        self.interval_var = tk.StringVar(value=str(args.interval))
        self.output_dir_var = tk.StringVar(value=args.output_dir)
        self.no_save_var = tk.BooleanVar(value=bool(args.no_save))
        self.status_var = tk.StringVar(value="未开始")

        self._build_layout()
        self.root.after(150, self._poll_queue)

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)

        ttk.Label(header, text="串口").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.port_var, width=12).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        ttk.Label(header, text="设备描述").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.device_name_var, width=34).grid(row=0, column=3, sticky=tk.W, padx=4, pady=4)
        ttk.Label(header, text="优先串口").grid(row=0, column=4, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.preferred_port_var, width=12).grid(row=0, column=5, sticky=tk.W, padx=4, pady=4)

        ttk.Label(header, text="采样次数").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.count_var, width=12).grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)
        ttk.Label(header, text="间隔秒").grid(row=1, column=2, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.interval_var, width=12).grid(row=1, column=3, sticky=tk.W, padx=4, pady=4)
        ttk.Label(header, text="输出目录").grid(row=1, column=4, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(header, textvariable=self.output_dir_var, width=28).grid(row=1, column=5, sticky=tk.W, padx=4, pady=4)

        ttk.Checkbutton(header, text="不写报告", variable=self.no_save_var).grid(row=2, column=0, sticky=tk.W, padx=4, pady=6)
        self.run_button = ttk.Button(header, text="开始采集并对比", command=self._start_run)
        self.run_button.grid(row=2, column=1, sticky=tk.W, padx=4, pady=6)
        ttk.Label(header, textvariable=self.status_var).grid(row=2, column=2, columnspan=4, sticky=tk.W, padx=8, pady=6)

        summary_frame = ttk.LabelFrame(self.root, text="完整性与摘要", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.coverage_text = tk.Text(summary_frame, height=6, wrap="word")
        self.coverage_text.pack(fill=tk.X)
        self.coverage_text.insert(tk.END, self._coverage_text())
        self.coverage_text.configure(state=tk.DISABLED)

        conclusion_frame = ttk.LabelFrame(self.root, text="验证结论", padding=10)
        conclusion_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        self.conclusion_text = tk.Text(conclusion_frame, height=10, wrap="word")
        self.conclusion_text.pack(fill=tk.BOTH, expand=True)
        self.conclusion_text.insert(
            tk.END,
            "结论区会在每次采集完成后自动生成。\n当前状态: 还没有执行新的硬件验证。",
        )

        chlorophyll_frame = ttk.LabelFrame(self.root, text="叶绿素专项诊断", padding=10)
        chlorophyll_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        self.chlorophyll_text = tk.Text(chlorophyll_frame, height=9, wrap="word")
        self.chlorophyll_text.pack(fill=tk.BOTH, expand=True)
        self.chlorophyll_text.insert(
            tk.END,
            "叶绿素专项区会在每次采集完成后自动刷新。\n"
            "这里会并排显示硬件 chl_a/chl_b 与当前权重积分值，便于判断是否还缺少后处理缩放。",
        )

        table_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("capture", "metric", "hardware", "calc", "abs_diff", "rel_diff", "confidence", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
        headings = {
            "capture": "采样",
            "metric": "指标",
            "hardware": "硬件值",
            "calc": "算法值",
            "abs_diff": "绝对差",
            "rel_diff": "相对差%",
            "confidence": "完成度",
            "status": "状态",
        }
        widths = {
            "capture": 60,
            "metric": 150,
            "hardware": 120,
            "calc": 120,
            "abs_diff": 110,
            "rel_diff": 100,
            "confidence": 90,
            "status": 120,
        }
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor=tk.CENTER)

        yscroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        detail_frame = ttk.LabelFrame(self.root, text="说明", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        self.detail_text = tk.Text(detail_frame, height=8, wrap="word")
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _coverage_text(self) -> str:
        coverage = get_algorithm_coverage()
        return (
            "当前完成状态\n"
            f"confirmed ({len(coverage['confirmed'])}): {', '.join(coverage['confirmed'])}\n"
            f"provisional ({len(coverage['provisional'])}): {', '.join(coverage['provisional'])}\n"
            f"unsupported ({len(coverage['unsupported'])}): {', '.join(coverage['unsupported'])}\n"
            "说明: raw_spectral_process.py 对 confirmed/provisional 字段已有可执行实现，但 unsupported 字段还没有仓库内可验证公式，因此还不算完整。"
        )

    def _start_run(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.status_var.set("已有任务运行中")
            return
        run_args = argparse.Namespace(**vars(self.args))
        run_args.port = self.port_var.get().strip()
        run_args.device_name = self.device_name_var.get().strip()
        run_args.preferred_port = self.preferred_port_var.get().strip()
        run_args.count = int(self.count_var.get().strip() or "1")
        run_args.interval = float(self.interval_var.get().strip() or "1")
        run_args.output_dir = self.output_dir_var.get().strip()
        run_args.no_save = bool(self.no_save_var.get())
        run_args.cli = False
        run_args.ui = True
        self.status_var.set("采集中...")
        self.run_button.configure(state=tk.DISABLED)

        def _worker() -> None:
            try:
                result = run_validation_session(run_args)
                self.queue.put(("result", result))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        self.worker = threading.Thread(target=_worker, daemon=True)
        self.worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "result":
                    self._apply_result(payload)
                elif kind == "error":
                    self.status_var.set(f"失败: {payload}")
                    self.run_button.configure(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _apply_result(self, run_result: ValidationRunResult) -> None:
        self.last_result = run_result
        self.status_var.set(build_status_summary(run_result))
        self.run_button.configure(state=tk.NORMAL)

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        for capture_index, item in _all_rows(run_result):
            self.tree.insert(
                "",
                tk.END,
                values=(
                    capture_index,
                    item.name,
                    _format_number(item.hardware),
                    _format_number(item.computed),
                    _format_number(item.abs_diff),
                    _format_number(item.rel_diff_pct, 3),
                    item.confidence,
                    _display_status(item.status),
                ),
            )

        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, self.status_var.get())

        self.conclusion_text.delete("1.0", tk.END)
        self.conclusion_text.insert(tk.END, build_validation_conclusion(run_result))

        self.chlorophyll_text.delete("1.0", tk.END)
        self.chlorophyll_text.insert(tk.END, build_chlorophyll_diagnostics(run_result))

    def _on_tree_select(self, _event: Any) -> None:
        selection = self.tree.selection()
        if not selection or self.last_result is None:
            return
        item_values = self.tree.item(selection[0], "values")
        capture_index = int(item_values[0])
        metric_name = item_values[1]
        metric = None
        for row in self.last_result.all_comparisons[capture_index - 1]:
            if row.name == metric_name:
                metric = row
                break
        if metric is None:
            return
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(
            tk.END,
            (
                f"capture={capture_index}\n"
                f"metric={metric.name}\n"
                f"hardware={_format_number(metric.hardware)}\n"
                f"computed={_format_number(metric.computed)}\n"
                f"abs_diff={_format_number(metric.abs_diff)}\n"
                f"rel_diff_pct={_format_number(metric.rel_diff_pct, 3)}\n"
                f"confidence={metric.confidence}\n"
                f"status={_display_status(metric.status)}\n\n"
                f"note={metric.note or '-'}"
            ),
        )
        if metric.name in CHLOROPHYLL_METRIC_FIELDS:
            projection = _build_chlorophyll_projection(self.last_result.snapshots[capture_index - 1])[metric.name]
            self.detail_text.insert(
                tk.END,
                (
                    "\n\n叶绿素专项说明\n"
                    "- 当前 computed 是运行时应采用的科学主值，不再以复刻硬件最终口径为目标。\n"
                    f"- {_format_chlorophyll_projection_detail(metric.name, projection)}\n"
                    "- 如果 hardware 与 computed 持续偏离，应优先视为硬件寄存器与科学值不一致，而不是继续假设存在待还原缩放。"
                ),
            )


def run_ui(args: argparse.Namespace) -> int:
    if tk is None or ttk is None:
        raise RuntimeError("当前 Python 环境不可用 tkinter，无法启动 UI")
    try:
        root = tk.Tk()
    except Exception as exc:
        raise RuntimeError(
            "当前 Python 环境的 Tk/Tcl 运行库不可用，无法启动 UI；"
            "可改用 --cli，或修复 Python 自带的 Tcl/Tk 安装。"
        ) from exc
    ValidationUi(root, args)
    root.mainloop()
    return 0


def main() -> int:
    args = _parse_args()
    if _should_launch_ui(args):
        try:
            return run_ui(args)
        except RuntimeError as exc:
            if args.ui:
                raise
            print(f"[WARN] UI 启动失败，已自动回退到 CLI: {exc}")

    try:
        run_result = run_validation_session(args)
    except Exception as exc:
        print(f"[ERROR] 验证失败: {exc}")
        return 1

    print(f"已连接 PAR 设备: port={run_result.port}, baudrate={args.baudrate}, slave_id={args.slave_id}")
    for index, (snapshot, comparisons) in enumerate(zip(run_result.snapshots, run_result.all_comparisons), start=1):
        print_snapshot_report(index, snapshot, comparisons)
    print_aggregate_summary(run_result.all_comparisons)
    print_computed_only_summary(run_result.snapshots)
    if run_result.report_path is not None:
        print()
        print(f"报告已写入: {run_result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())