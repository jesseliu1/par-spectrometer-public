"""Request and response models of the tier and takeover endpoints (16_ section 5; api-contract-v0 section 4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import AcquisitionRow, Source
from .overview_models import (
    MetricRow,
    OverviewAttempt,
    OverviewChart,
    OverviewError,
    OverviewKpi,
    OverviewRecord,
    OverviewStatus,
    OverviewTableGroup,
    OverviewTexts,
)

Takeover = Literal["released", "starting", "running", "stopping"]


class Fault(BaseModel):
    id: int = Field(description="本次服务运行中的序号（自 1 起）")
    kind: Literal["request", "takeover"] = Field(
        description="request：某个请求出现未预期异常，页面保留数据可重试；takeover：接管或维护的主线程代码出现未预期"
        "异常，服务已停止接管、档位不变（D-225 问题 1，#119）"
    )
    occurred_at: str = Field(description="北京时间")
    where: str = Field(description="出错位置：请求为“方法 路径”，主线程为槽函数或主线程调用")
    error: str = Field(description="异常类型名；回溯只在 service.log")
    message: str = Field(description="页面显示的全文")
    stopping: bool = Field(description="是否因此停止接管（档位不变，#119）")


class TierState(BaseModel):
    tier: int = Field(description="0 只读（出厂）；1 可接管采集；2 另可设备维护写入（17_）")
    takeover: Takeover = Field(description="接管状态，只在服务进程内存中，不持久化；alpha 每次启动都是 released")
    lock_held: bool = Field(description="是否持有 V1.0.3 的单实例锁（只在接管期间持有）")
    text: str = Field(description="状态栏固定一块的文字（16_ 4.4）")
    level: Literal["muted", "info", "warn", "error", "maintenance"] = Field(description="颜色令牌")
    settings_path: str = Field(description="alpha 自己的设置文件 app_config_v2.json 的完整路径")
    settings_problem: str | None = Field(description="设置文件无法读取时的原因（此时按默认档位：产品为 1，#119）")
    stop_text: str = Field(description="“停止采集”确认框全文；有锁停时另附锁停全文与“先重新上电”的提示")
    down_text: str = Field(description="“切回只读模式”确认框全文（#119 起页面不再提供该操作）")
    down_to_1_text: str = Field(description="“切回档位 1”（从档位 2）确认框全文（17_ 6.1）")
    maintenance: bool = Field(description="接管中且协调器处于通信维护态（状态栏用）")
    fault: Fault | None = Field(description="本次服务运行中最近一次未预期异常（D-225 问题 1）；没有为 null")


class ConfirmationRequest(BaseModel):
    tier: int = Field(description="要开启的档位：1（自 0）或 2（自 1）需要确认")


class Confirmation(BaseModel):
    confirmation_id: str
    tier: int
    expires_at: str = Field(description="北京时间；有效期 60 秒，只能使用一次")
    notice: str = Field(description="第一层说明全文")
    confirmation: str = Field(description="第二层确认（勾选）的文字")


class TierRequest(BaseModel):
    tier: int
    confirmation_id: str | None = Field(default=None, description="0→1、1→2 必须带本服务发出的有效确认号")


class Bus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["rtu", "tcp"]
    serial_port: str
    host: str
    tcp_port: int = Field(ge=1, le=65535)
    baudrate: int = Field(gt=0)
    parity: Literal["N", "E", "O"]
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    poll_cycle_seconds: float = Field(gt=0, allow_inf_nan=False, description="40～3600 秒之外按 V1.0.3 钳位")


class DeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slave_id: int
    enabled: bool
    auto_stop_on_failure: bool = False
    database_path: str = Field(
        default="", description="留空＝新设备，由程序在 alpha 数据目录建库；非空时只能是 alpha 配置中已有设备的库"
    )
    reuse_existing: bool = Field(
        default=False,
        description="沿用 alpha 数据目录 data/devices 中按设备名称的同名库（D-215）；库不存在时 400",
    )


class ConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bus: Bus
    devices: list[DeviceRequest] = Field(max_length=4)
    reconfigure: bool = Field(
        default=False,
        description="配置不可用（`problem` 非空）且未接管时：以空配置重新配置并保存，先备份原配置（D-220）；"
        "其余情况保存需正在接管",
    )


class ConfigDevice(BaseModel):
    name: str
    slave_id: int
    enabled: bool
    auto_stop_on_failure: bool
    database_path: str
    database_name: str
    database_exists: bool
    inside_alpha: bool = Field(description="库在 alpha 数据目录 data/devices 之下；否则开始采集会被拒绝")


class ConfigRow(BaseModel):
    name: str
    slave_id: int
    enabled: bool
    auto_stop_on_failure: bool
    database_path: str = Field(
        description="已登记设备的库（完整路径）；空白行与导入行为空，保存时由程序在 alpha 数据目录新建"
    )
    database_name: str | None
    registered: bool = Field(description="该行已登记（保存时即使名称清空也保留，同 V1.0.3 devices_from_form）")
    reuse_existing: bool = Field(default=False, description="读取时恒为 false；页面勾选后随保存发送（D-215）")


class Choice(BaseModel):
    value: str
    label: str


class FieldLabel(BaseModel):
    key: str
    label: str


class ConfigForm(BaseModel):
    """V1.0.3 设置页表单的文字、选项、范围与提示（原样），页面只渲染，不自写规则（D-214）。"""

    labels: list[FieldLabel]
    transports: list[Choice]
    baudrates: list[int]
    parities: list[Choice]
    parity_tooltip: str
    poll_min: float
    poll_max: float
    poll_decimals: int
    poll_hint: str
    poll_tooltip: str
    slave_min: int
    slave_max: int
    tcp_port_min: int
    tcp_port_max: int
    device_columns: list[str]
    name_placeholders: list[str]
    enabled_tooltip: str
    fail_stop_tooltip: str
    save_label: str
    save_tooltip: str
    saved_text: str
    error_title: str
    serial_port_hint: str
    new_database_text: str
    save_requires_running: str
    reuse_label: str = Field(description="设备行“沿用 alpha 目录中的同名库”勾选框的文字（D-215）")
    reuse_tooltip: str
    reconfigure_title: str = Field(description="配置或库不可用时的标题（V1.0.3 启动检查的弹窗标题，D-220）")
    reconfigure_text: str = Field(description="“以空配置重新配置”确认框正文（V1.0.3 原文按 alpha 改写，D-220）")
    reconfigure_label: str
    reconfigure_hint: str = Field(description="重新配置期间表单上方的说明（保存时先备份原配置，不需要先开始采集）")
    apply_failed_text: str = Field(description="后台应用配置失败后的“未生效”说明（D-221）")


class Problem(BaseModel):
    message: str
    detail: str | None


class AcquisitionConfig(BaseModel):
    as_of: str
    path: str = Field(description="alpha 的档位 1 配置文件完整路径（格式与 V1.0.3 相同，不是 V1.0.3 的文件）")
    exists: bool
    configured: bool
    bus: dict[str, Any]
    poll_cycle_seconds: float = Field(description="生效的轮询周期（40～3600 秒钳位后）")
    devices: list[ConfigDevice]
    devices_dir: str
    rows: list[ConfigRow] = Field(description="设置页的 4 行设备登记（V1.0.3 ensure_device_count）")
    blank_bus: dict[str, Any] = Field(description="以空配置重新配置时的总线参数（交付默认 57600 / N / 40 秒）")
    blank_rows: list[ConfigRow] = Field(description="以空配置重新配置时的 4 行空白登记")
    problem: Problem | None = Field(
        description="配置不可用的原因：文件无法读取、库不在 alpha 目录，或上次开始采集时库未通过 V1.0.3 启动检查"
        "（此时可在未接管状态下以空配置重新配置，D-220）；可用时为 null"
    )
    form: ConfigForm


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(description="V1.0.3 的程序目录，或其中的 config/app_config.json")


class ImportDevice(BaseModel):
    name: str
    slave_id: int
    enabled: bool
    auto_stop_on_failure: bool
    source_database_path: str = Field(description="该设备在 V1.0.3 中的库（只读检查维护会话，不导入）")
    importable: bool
    problem: str | None = Field(description="不能导入的原因（V1.0.3 中有待核对的通信参数写入等）")


class ImportPreview(BaseModel):
    as_of: str
    source_path: str
    bus: dict[str, Any]
    devices: list[ImportDevice]
    rows: list[ConfigRow] = Field(description="放入表单的 4 行：可导入的设备（库路径清空）与空白行")
    note: str


class SerialPort(BaseModel):
    value: str = Field(description="串口名称（如 COM3），选中后填入“计算机串口”并按原样保存")
    label: str = Field(description="下拉列表中的文字（V1.0.3：“COM3 — USB-SERIAL CH340”，无描述时为“未知设备”）")


class SerialPorts(BaseModel):
    as_of: str
    ports: list[SerialPort] = Field(
        description="本机串口，顺序同操作系统给出的顺序（V1.0.3 设置页不排序）；只枚举，不打开任何串口"
    )
    hint: str = Field(description="V1.0.3 “刷新串口”后的提示（串口框悬停文字）：检测到几个串口，或未检测到串口")


class Notice(BaseModel):
    """Where a shown message is recorded (#136): the run event in logs/events.jsonl and the diagnostics bundle."""

    event_id: str = Field(description="记录号“<运行会话>-<序号>”，每次启动服务的会话随机、序号从 1 起，重启不重号")
    occurred_at: str = Field(description="这条消息出现的北京时间；只说明出现时间，不表示仍然有效")


class Halt(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    slave_id: int | None = None
    occurred_at: str | None = None
    reason: str | None = None
    initialized: bool | None = None
    need_power_cycle: bool | None = None
    resume_unconfirmed: bool | None = None
    message: str | None = None
    log_errors: list[str] = []
    text: str = Field(description="锁停提示全文（V1.0.3 原文，只改“退出并重新启动软件”一句，D-212 问题 8）")
    notice: Notice | None = Field(default=None, description="锁停消息的记录号（#136）")


class RuntimeDevice(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="协调器的设备标识（设备名，重名时加 #地址）")
    position: str | None = Field(description="配置中的位置 p1–p4")
    name: str
    slave_id: int
    enabled: bool
    online: bool
    level: str
    message: str
    failures: int
    excluded: bool
    last_failure_at: str | None
    last_success_at: str | None
    last_error: str | None
    latest_record_id: int | None
    database_path: str
    status_text: str = Field(description="V1.0.3 状态栏的一行摘要（coordinator.status_text）")
    notice: Notice | None = Field(default=None, description="当前 message 的记录号（#136）；没有消息时为空")


class BusState(BaseModel):
    level: str
    message: str
    notice: Notice | None = Field(default=None, description="当前总线消息的记录号（#136）")


RunLevel = Literal["ok", "warn", "error", "muted"]


class RunBus(BaseModel):
    text: str = Field(description="“总线：<摘要>”，V1.0.3 MainWindow._on_bus_state 原文")
    level: RunLevel = Field(description="V1.0.3 的颜色：绿 ok、琥珀 warn、红 error、灰 muted")
    detail: str = Field(description="总线原文（V1.0.3 的悬停提示）；锁停时为锁停消息")
    notice: Notice | None = Field(default=None, description="detail 的记录号（#136）：总线消息的，锁停时为锁停的")
    devices_silent: bool = Field(
        default=False,
        description="所有启用的设备都已失败（含因失败停止退出本次采集的）、没有一台响应时为 true，"
        "此时为“总线：异常”（#131，非 V1.0.3）",
    )


class RunState(BaseModel):
    text: str = Field(description="采集状态，V1.0.3 MainWindow._refresh_communication_events 原文")
    level: RunLevel
    notice: Notice | None = Field(
        default=None, description="锁停时为锁停消息的记录号；其余状态是设备状态的汇总，没有自己的记录号（#136）"
    )


class RunStatus(BaseModel):
    bus: RunBus
    acquisition: RunState
    failures: list[str] = Field(
        description="启用设备中有连续失败的，每台一行“<时间>  <设备名>（地址 <n>）  <失败消息>”（V1.0.3 红字行）；"
        "没有时为空"
    )
    failure_notices: list[Notice | None] = Field(
        default=[], description="与 failures 逐行对应：该行失败消息的记录号（#136）"
    )


class EventLogHealth(BaseModel):
    """logs/events.jsonl (#136): written on its own thread; lost or failed writes are counted here."""

    session: str = Field(description="本次运行会话（记录号的前半）")
    written: int = Field(description="已写入的条数")
    last_written_sequence: int | None
    dropped: int = Field(description="写盘队列排满而未写入文件的条数；当前提示的记录号仍在，导出诊断包时补上")
    failed: int = Field(description="写盘失败的条数")
    first_error: str | None
    last_error: str | None


class AcquisitionStatus(BaseModel):
    as_of: str
    takeover: Takeover
    lock_held: bool
    error: str | None = Field(description="最近一次开始失败的原因")
    error_notice: Notice | None = Field(default=None, description="error 的记录号（#136）")
    bus: BusState
    halt: Halt | None = Field(description="锁停（硬件状态异常或恢复未确认）；没有清除按钮，停止再开始采集")
    maintenance: bool = Field(description="维护未完成，采集暂停（档位 1 不能离开维护）")
    poll_cycle_seconds: float | None
    config_apply_error: str | None = Field(
        description="上次保存的配置在后台应用失败（“应用配置失败：<原因>”），正在运行的仍是原配置；"
        "到下一次应用成功或下一次开始采集为止（D-221）"
    )
    devices: list[RuntimeDevice]
    run_status: RunStatus = Field(description="顶部常驻状态区：总线、采集状态与失败行，与 V1.0.3 一致（issue #73）")
    event_log: EventLogHealth | None = Field(default=None, description="运行事件日志的写入情况（#136）")


class LiveDevice(BaseModel):
    key: str
    name: str
    database_path: str


class LiveOverview(BaseModel):
    as_of: str
    source: Source = "live"
    snapshot_id: str = Field(
        description="这台设备这个库的标识（同 API-06 的 snapshot_id）；“全部指标”只显示同一库的记录详情（#106）"
    )
    device: LiveDevice
    texts: OverviewTexts
    display_record: OverviewRecord | None
    latest_attempt: OverviewAttempt | None
    record: AcquisitionRow | None = Field(description="显示记录的库中原样字段")
    status: OverviewStatus
    paused: bool = Field(description="维护中、锁停或未接管时为 true，状态行为“采集已暂停”")
    stale: bool | None
    stale_after_seconds: float
    poll_cycle_seconds: float = Field(description="alpha 配置中生效的轮询周期（同 V1.0.3 用运行配置）")
    kpis: list[OverviewKpi]
    core_metrics: list[MetricRow]
    table: list[OverviewTableGroup]
    chart: OverviewChart
    details_enabled: bool
    metrics_error: OverviewError | None
