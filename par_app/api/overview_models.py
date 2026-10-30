"""Response model of the overview endpoint (api-contract-v0 API-09, read-only snapshot subset; D-211).

Every text the page shows comes from the service (contract 1.2): KPI cards, status line, in-chart card, table and
chart titles are the V1.0.3 texts; the page computes no age, axis range or format. Tier 0 has no acquisition: there
is no acquisition or bus state and no start / stop control (those need tier 1, later in stage two).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import AcquisitionRow, DeviceRef, Source, Spectrum


class OverviewTexts(BaseModel):
    """Fixed texts of the page, copied from MainWindow._build_overview / _show_overview_metric_details."""

    page_title: str
    summary_title: str
    summary_context: str
    details_button: str
    metrics_toggle: str
    spectrum_title: str = Field(description="光谱区标题“最新光谱”（V1.0.3 overview_title_label）")
    x_label: str
    y_label: str
    empty_heading: str
    empty_detail: str
    invalid_spectrum: str = Field(description="光谱无法解析时空图中的说明“光谱数据无法解析”（D-211 问题 5）")
    details_columns: list[str]
    details_close: str


class OverviewKpi(BaseModel):
    key: str
    title: str
    text: str = Field(description="数值与单位，如“1234.5 lx”；没有显示记录时为“—”（UI-012，#38 逐卡写入）")


class OverviewRecord(BaseModel):
    id: int
    acquired_at: str | int | float | None = Field(description="按库中原样")
    acquired_at_text: str
    age_seconds: float | None = Field(description="距今秒数（服务时钟此刻 − 采集时间）；时间不可读时为 null")
    age_text: str = Field(description="“距今 N 秒”“记录时间晚于本机”或“记录时间不可用”（UI-170）")
    exposure_text: str
    elapsed_text: str
    review_text: str = Field(description="采集校验（与历史详情相同的规则）")
    details_title: str = Field(description="“全部指标”弹窗标题（UI-009）")


class OverviewAttempt(BaseModel):
    id: int
    success: bool
    acquired_at: str | int | float | None
    acquired_at_text: str


class OverviewStatus(BaseModel):
    text: str = Field(description="状态行全文，与 V1.0.3 实时页相同（UI-055、UI-170、UI-171）；无记录时为空")
    level: Literal["ok", "warn", "error", "none"] = Field(
        description="V1.0.3 的颜色：error 红（本轮失败、仅有失败）、warn 琥珀、ok 绿；none 不显示"
    )


class MetricRow(BaseModel):
    label: str
    text: str


class OverviewTableGroup(BaseModel):
    title: str
    rows: list[MetricRow]


class OverviewChart(BaseModel):
    title: str = Field(description="“最新光谱”，或空图标题“当前设备暂无可显示光谱”“最近采集失败，无新光谱”（UI-054）")
    spectrum_state: Literal["ok", "none", "invalid"] = Field(
        description="invalid：光谱不是 701 个数值（V1.0.3 遇到会中断刷新）"
    )
    spectrum: Spectrum | None
    y_max: float | None = Field(description="纵轴上限（下限 0）：最高点约在 0.618 高度（UI-175，首次绘制）")
    x_ticks: list[int]
    overlay: list[list[MetricRow]] = Field(
        description="图内指标卡的两列：有 20 项时左 8 右 12（UI-060），否则为核心读数 4 行；空表示不画"
    )


class OverviewError(BaseModel):
    message: str
    detail: str


class Overview(BaseModel):
    as_of: str
    source: Source = "live_ro"
    snapshot_id: str
    device: DeviceRef
    snapshot_text: str = Field(description="“快照数据，非实时”说明，含导入时间")
    texts: OverviewTexts
    display_record: OverviewRecord | None = Field(
        description="最近一条成功且有光谱的记录（UI-053）；没有时为 null，“全部指标”禁用（UI-013）"
    )
    latest_attempt: OverviewAttempt | None = Field(description="最新一条记录（含失败），按 ID")
    record: AcquisitionRow | None = Field(description="显示记录的库中原样字段")
    status: OverviewStatus
    stale: bool | None = Field(description="超过两个轮询周期（至少 120 秒）没有新记录（UI-171）")
    stale_after_seconds: float
    poll_cycle_seconds: float = Field(
        description="判断“暂无新记录”所用的轮询周期：先取显示记录自己的 quality_json.poll_cycle_seconds；"
        "缺失或不可用时按 D-206 取快照中按采集时间最近一条成功记录的值，再不可用时默认 60 秒（D-211 问题 2）"
    )
    poll_cycle_source: Literal["record", "default"]
    poll_cycle_text: str
    kpis: list[OverviewKpi] = Field(description="六张摘要卡，顺序固定（UI-012）")
    core_metrics: list[MetricRow] = Field(description="核心读数 4 行（metrics.overview_core_metrics）")
    table: list[OverviewTableGroup] = Field(
        description="概览指标表 4 组 × 6 项（24 项）；V1.0.3 中该表隐藏，同样 24 项见图内卡与摘要卡（D-211）"
    )
    chart: OverviewChart
    details_enabled: bool = Field(description="“全部指标”可用（UI-013）；记录 ID 见 display_record，内容用 API-06")
    metrics_error: OverviewError | None = Field(
        description="指标无法解析时：摘要卡只显示到出错之前（#38），其后为空；不伪装成功"
    )
