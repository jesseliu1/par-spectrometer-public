"""Request and response models of /api/v0 (docs/spec/api-contract-v0.md; generated schema: docs/spec/openapi-v0.json).

Displayed values come as text produced by par_app.services; the front end shows `text` fields as they are and does
no arithmetic (contract 1.2). Raw stored values are passed through unchanged next to them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictFloat, StrictInt

from ..application import DEVICE_WRITE_TIER
from ..application.history import PAGE_LIMIT
from ..application.snapshots import DEVICE_KEYS, NAME_MAX_LENGTH

DATABASE_ID_TEXT = "设备库标识（字段名沿用 snapshot_id，#83 改名）：同一位置换了设备库（配置已改）时变化"

Source = Literal["snapshot", "live_ro", "live"]
DisplayState = Literal["normal", "disabled", "fault", "unconfigured"]


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ShutdownAccepted(BaseModel):
    stopping: Literal[True] = Field(
        default=True, description="服务已开始正常关闭：处理完进行中的请求后退出（退出码 0），并删除 service.json"
    )


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    build_commit: str | None
    tier: int = Field(
        default=DEVICE_WRITE_TIER,
        description="设备写入档位（方案 2.5）：0 只读，不采集、不写设备；1 可接管采集（16_）；"
        "产品没有设置文件时为 1（#119，打开即采集，无需确认），"
        "值取自 alpha 设置文件 app_config_v2.json",
    )
    started_at: str


class Fingerprint(BaseModel):
    size: int
    mtime_ns: int
    sha256: str


class SnapshotModel(BaseModel):
    id: str
    name: str = Field(description="导入时给的设备名称（默认取源库文件名）")
    key: str
    position: int
    file_name: str
    path: str = Field(description="副本完整路径（alpha 数据目录 data/imported/ 下）")
    source_path: str
    imported_at: str
    record_count: int
    source_before: Fingerprint = Field(description="导入前源库的大小、修改时间和 SHA-256")
    source_after: Fingerprint = Field(description="导入后再取一次；与导入前不同说明期间有其他程序（V1.0.3）写了源库")
    source_changed_during_import: bool


class SnapshotImportRequest(BaseModel):
    source_path: str = Field(min_length=1, description="V1.0.x 历史库文件路径；只以只读方式打开，绝不写入")
    name: str | None = Field(
        default=None, max_length=NAME_MAX_LENGTH, description="设备名称，也用作副本文件名；默认取源库文件名"
    )
    position: int = Field(default=1, ge=1, le=len(DEVICE_KEYS), description="归属的设备位置 1–4（p1–p4）")


class SnapshotImported(BaseModel):
    as_of: str
    source: Source = "snapshot"
    snapshot: SnapshotModel


class SnapshotList(BaseModel):
    as_of: str
    source: Source = "snapshot"
    items: list[SnapshotModel]


class Device(BaseModel):
    key: str
    position: int
    configured: bool
    enabled: bool
    name: str
    address_text: str | None = Field(default=None, description="恒为 null")
    display_state: DisplayState
    database_name: str | None
    database_path: str | None
    snapshot_id: str | None = Field(description=DATABASE_ID_TEXT)
    imported_at: str | None = Field(description="恒为 null（快照时代的导入时间，#83 移除）")


class DeviceList(BaseModel):
    as_of: str
    source: Source = "live_ro"
    tier: int = DEVICE_WRITE_TIER
    items: list[Device]


class TimeRange(BaseModel):
    start: str
    end: str


class HistoryItem(BaseModel):
    seq: int = Field(description="本次查询中的序号（含分页偏移），从 1 开始")
    id: int
    acquired_at: str
    acquired_at_text: str
    success: bool
    result_text: str = Field(description="成功 / 失败")
    exposure_status: int | None
    exposure_text: str = Field(description="正常 / 过曝光 / 欠曝光 / 未知")
    exposure_style: Literal["normal", "warn"] = Field(
        description="新单采记录恒为 normal（D-154）；旧记录非“正常”为 warn"
    )


class HistoryPage(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    range: TimeRange
    limit: int = Field(description=f"每页条数上限，最大 {PAGE_LIMIT}")
    offset: int = Field(description="本页跳过的条数（实验性）；按 D-201 裁决历史回放页只用 0（UI-046 不分页）")
    limit_reached: bool = Field(description="本页之后范围内还有记录（UI-048：提示缩小时间范围）")
    next_offset: int | None = Field(description="下一页的 offset；没有更多记录时为 null")
    items: list[HistoryItem]


StoredValue = int | float | str | None
"""A value as SQLite returns it. Columns are dynamically typed, so an INTEGER column may hold a REAL or TEXT value
(review N-1); it is passed through as stored rather than refused."""


class AcquisitionRow(BaseModel):
    """One row of the V1.0.x acquisitions table, values as stored (columns missing in old databases are null).

    Only `id` (INTEGER PRIMARY KEY) is guaranteed to be an integer; every other column keeps the stored type.
    """

    id: int
    acquired_at: StoredValue
    mcu_time_ms: StoredValue = None
    success: StoredValue = None
    initialized: StoredValue = None
    need_power_cycle: StoredValue = None
    raw_data_valid: StoredValue = None
    calculate_data_valid: StoredValue = None
    stop_status: StoredValue = None
    spectral_coefficient: StoredValue = None
    exposure_status: StoredValue = None
    exposure_time_us: StoredValue = None
    software_metrics_json: StoredValue = None
    mcu_params_json: StoredValue = None
    error_stage: StoredValue = None
    error_detail: StoredValue = None
    elapsed_ms: StoredValue = None
    quality_json: StoredValue = None
    dli_eligible: StoredValue = None


class MetricItem(BaseModel):
    key: str
    label: str
    unit: str
    text: str


class MetricGroup(BaseModel):
    title: str
    items: list[MetricItem]


class Spectrum(BaseModel):
    wavelength_start: int
    wavelength_step: int
    spectral_coefficient: int | None
    points: list[int | float] = Field(description="MCU 原始值，按存储原样（整数仍是整数）")
    values: list[float] = Field(description="光谱辐照度 W·m⁻²·nm⁻¹ = 原始值 / 10^光谱系数（与 V1.0.x 历史光谱图一致）")


class ReferenceCurveModel(BaseModel):
    key: Literal["chlorophyll_a", "chlorophyll_b", "mccree", "photopic"]
    label: str = Field(description="图例文字（与 V1.0.x 相同）")
    line: Literal["dashed", "dotted", "dashdot"]
    width: float = Field(description="线宽（V1.0.x 的 matplotlib 线宽）")
    x: list[float] = Field(description="波长 nm")
    y: list[float] = Field(description="已归一化，画在右侧响应坐标轴上")


class ReferenceCurvesResponse(BaseModel):
    curves: list[ReferenceCurveModel] = Field(description="固定四条，顺序与 V1.0.x 图例相同（UI-168）")
    axis_label: str = Field(description="右侧响应坐标轴标题")
    axis_max: float = Field(description="右轴上限：叶绿素 A/B、McCree 峰值最大者 × 1.5（不含 V(λ)），下限 0")
    fill_start: int = Field(description="fill_colors 第一项的波长 nm，之后每项 +1 nm")
    fill_colors: list[list[float]] = Field(
        description="按波长着色：每项 [R, G, B]（0–1）；第 i 段（x_i 到 x_i+1）的曲线和填充用第 i 项颜色（UI-317）"
    )
    fill_opacity: float = Field(description="填充不透明度（线条不透明）")


class DetailHeader(BaseModel):
    title: str = Field(description="记录详情 · 设备名称 · #ID（UI-036）")
    time_text: str
    status_text: str
    status_level: Literal["ok", "warn", "error"]
    exposure_text: str


class DeviceRef(BaseModel):
    key: str
    name: str


class AcquisitionDetail(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    header: DetailHeader
    success: bool
    elapsed_text: str = Field(description="采集耗时（ms），一位小数")
    review_text: str = Field(description="采集校验")
    groups: list[MetricGroup] = Field(description="7 组共 54 项，顺序与 V1.0.x 历史详情一致；失败记录全部为“—”")
    record: AcquisitionRow
    spectrum_state: Literal["ok", "none", "invalid"]
    spectrum: Spectrum | None


class SpectrumResponse(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    id: int
    spectrum: Spectrum


class DliPeriod(BaseModel):
    start: str = Field(description="周期起点（日出，北京时间，毫秒）")
    end: str = Field(description="周期终点 = 起点 + 24 小时（DLI-015、DLI-022）")
    date: str = Field(description="起点所在的北京日期 YYYY-MM-DD（日期选择框显示它）")
    current: bool = Field(description="当前时刻在本周期内")
    text: str = Field(description="周期行全文（UI-178）")


class DliLocation(BaseModel):
    latitude: float = Field(description="纬度，正值为北纬（DLI-026）")
    longitude: float = Field(description="经度，正值为东经（DLI-026）")
    stored: bool = Field(description="库中保存了可读的位置；false 时为默认北京坐标")
    coordinates_text: str = Field(description="纬度 x.xxxx °N，经度 y.yyyy °E")
    text: str = Field(description="周期行的悬停说明：已保存位置与 DLI 启用时间")


class DliLocationRequest(BaseModel):
    """保存经纬度并重置周期（issue #116）：V1.0.3 的两个输入框，范围与位数同 MainWindow（UI-178、DLI-024）。"""

    latitude: StrictFloat | StrictInt = Field(
        description="纬度，-89.9～89.9，正值为北纬；按 4 位小数保存（数字，不接受文本或布尔值）"
    )
    longitude: StrictFloat | StrictInt = Field(
        description="经度，-180～180，正值为东经；按 4 位小数保存（数字，不接受文本或布尔值）"
    )


class DliEnabled(BaseModel):
    at: str = Field(description="DLI 启用时间：只计入此后的记录（DLI-014）")
    stored: bool = Field(
        description="库中保存了启用时间；false 时按当前时刻（与 V1.0.3 未登记设备相同，D-163），只读不写"
    )
    text: str


class DliSummaryModel(BaseModel):
    """services.dli.DliSummary, every field (times in Beijing ISO with milliseconds, null when absent)."""

    total: float = Field(description="累计 mol·m⁻²")
    covered_seconds: float
    missing_seconds: float
    coverage: float = Field(description="覆盖率 0–1：有效时长 / 周期已过去时长（DLI-040）")
    first_valid: str | None
    last_valid: str | None
    integrated_until: str | None
    head_seconds: float
    internal_seconds: float
    tail_seconds: float
    cutoff: str
    state: Literal["积分中", "部分累计", "有效数据不足"]
    stale: bool
    paused: bool


class DliHeader(BaseModel):
    total_text: str = Field(description="已累计：x.xxx mol·m⁻²；没有有效区间为“—”（DLI-034..036）")
    state_text: str = Field(description="状态，含“采集已暂停”“数据未更新（时长）”后缀（DLI-043、DLI-044）")
    state_level: Literal["ok", "warn", "muted"]
    times_text: str = Field(description="首个有效 / 累计截至 / 最新有效（DLI-037、DLI-039）")
    coverage_text: str
    coverage_tooltip: str = Field(description="截至时间与起始、内部、尾部未覆盖（DLI-053）")


class DliSeries(BaseModel):
    times: list[str]
    offsets_seconds: list[float] = Field(description="距周期起点的秒数（横轴位置）")
    cumulative: list[float | None] = Field(description="累计 mol·m⁻²；null 处断线（DLI-012、DLI-049），不补零")


class DliMetric(BaseModel):
    key: str
    title: str
    summary: DliSummaryModel
    header: DliHeader
    y_max: float = Field(description="纵轴上限（下限固定为 0，UI-184）")
    series: DliSeries


class DliTick(BaseModel):
    offset_seconds: float
    at: str
    text: str = Field(description="两端与跨日零点为“月-日\\n时:分”，其余“时:分”（UI-183）")
    narrow: bool = Field(description="图宽不足 700 px 时也显示（6 小时间隔）；false 只在宽图显示（3 小时）")


class DliInterruption(BaseModel):
    occurred_at: str
    occurred_at_text: str
    reason: str


class DliDay(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    requested_date: str | None = Field(description="请求中的 date；未给时为 null（当前周期）")
    period: DliPeriod
    location: DliLocation
    enabled: DliEnabled
    observed_until: str = Field(description="本次统计截至的观测时刻（服务时钟），四项共用（DLI-031）")
    poll_cycle_seconds: float = Field(
        description="允许间隔所用轮询周期：取本周期截至时刻前最近一条成功记录（本周期没有时取之前最近一条）"
        "quality_json 中的 poll_cycle_seconds，缺失或不可用时为默认 60 秒（D-204 问题 1 = D，D-206）"
    )
    poll_cycle_source: Literal["record", "default"] = Field(
        description="record：取自采集记录；default：记录中没有可用的轮询周期，用默认值"
    )
    poll_cycle_record_at: str | None = Field(
        description="所查看的那条成功记录的采集时间（按库中原样）；没有成功记录时为 null"
    )
    max_gap_seconds: float = Field(description="相邻有效点允许间隔 max(120, 周期 + 60)（DLI-010）")
    gap_text: str = Field(description="允许间隔说明，写明轮询周期的取值来源")
    snapshot_text: str
    paused: bool
    metrics: list[DliMetric] = Field(description="PPFD、McCree YPFD、叶绿素 A、叶绿素 B，顺序固定")
    interruptions: list[DliInterruption] = Field(description="本周期内（启用时间之后）记录的 DLI 中断，按时间")
    ticks: list[DliTick]
