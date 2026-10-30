"""Response models of the support endpoints (api-contract-v0 API-27 导出诊断包, API-28 维护记录; D-226).

Both are read only for devices, configuration and databases; the bundle writes one zip into the alpha's own output
folder. Every text the page shows comes from the service (contract 1.2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiagnosticsExported(BaseModel):
    as_of: str
    path: str = Field(description="诊断包完整路径（alpha 数据目录 exports/diagnostics 下，每次新建）")
    directory: str
    file_name: str
    size: int = Field(description="zip 文件字节数")
    files: list[str] = Field(description="包内文件（相对路径）")
    problems: list[str] = Field(description="生成时遇到的问题（如某台设备库无法读取）；包仍然生成")
    text: str = Field(description="页面显示的结果全文")


class MaintenanceLogDevice(BaseModel):
    key: str
    position: int
    name: str
    database_name: str
    state: Literal["ok", "missing", "outside", "unavailable"] = Field(
        description=(
            "ok 已读取；missing 库尚未建立；outside 库不在 alpha data/devices 下（未打开）；unavailable 读取失败"
        )
    )
    problem: str | None = Field(description="state 不是 ok 时的说明")


class MaintenanceLogItem(BaseModel):
    device_key: str
    device_name: str
    occurred_at: str = Field(description="库中原样")
    occurred_at_text: str
    kind: Literal["calibration_write", "comm_write", "comm_verify", "time_sync"]
    kind_text: str
    before_text: str = Field(description="写入前的值；库中没有时为“未记录”")
    after_text: str = Field(description="写入的值；库中没有时为“未记录”")
    readback_text: str = Field(description="写入后从设备读回的值；库中没有时为“未记录”")
    result: Literal["success", "failure", "pending"]
    result_text: str = Field(description="成功 / 失败 / 待核对")
    detail: str
    source: str = Field(description="来源表与行号，如“calibration_audit #3”")


class MaintenanceLogTexts(BaseModel):
    title: str
    note: str
    columns: list[str]
    empty_text: str
    no_devices_text: str
    time_sync_label: str
    limit_text: str = Field(description="达到上限时显示")
    scan_limited_text: str = Field(description="scan_limited 为 true 时显示：更早的设备日志未扫描")


class MaintenanceLogResponse(BaseModel):
    as_of: str
    devices: list[MaintenanceLogDevice]
    items: list[MaintenanceLogItem] = Field(description="最新在前")
    limit: int
    limit_reached: bool
    time_sync: bool
    scan_limited: bool = Field(description="某台设备只扫描了最新的设备日志行，更早记录未扫描（D-226 问题 4）")
    texts: MaintenanceLogTexts
