"""Request and response models of the spectrum calculation endpoints (api-contract-v0 API-11..14, API-24, API-25).

Every number the page draws (values, plotted points, axis ranges, threshold) and every text comes from the service;
the front end does no arithmetic (contract 1.2). Invalid values (NaN) are sent as null: JSON has no NaN, and a
null point is drawn as a gap, never as zero (UI-218).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..application.readonly import SQLITE_MAX_INTEGER
from .models import DATABASE_ID_TEXT, Source

Range = tuple[float, float]


class OperationKind(BaseModel):
    key: Literal["add", "subtract", "divide"]
    label: str


class OperationTexts(BaseModel):
    source_labels: list[str]
    operation_label: str
    run_label: str
    export_label: str
    swap_tooltip: str = Field(description="交换按钮的悬停提示（UI-314）")
    auto_match_label: str
    auto_match_tooltip: str
    time_tooltip: str = Field(description="采集时间差的悬停提示：最近不代表同时（UI-206）")
    no_spectrum: str = Field(description="记录框没有候选时的文字（UI-207、UI-269）")
    input_empty_heading: str
    input_empty_detail: str
    waiting_heading: str
    missing_heading: str
    missing_detail: str
    result_title: str
    x_label: str
    power_y_label: str = Field(description="A、B 两图（及加减法结果）的纵轴名")
    empty_sources: str


class OperationAxis(BaseModel):
    start_nm: int
    end_nm: int
    ticks_wide: list[int]
    ticks_narrow: list[int] = Field(description="图宽小于 narrow_below_px 时用：省略 400 与 1000（UI-192）")
    narrow_below_px: int


class GuideParagraphModel(BaseModel):
    head: str | None = Field(description="行内加粗的小标题；没有时为 null")
    text: str


class GuideLinkModel(BaseModel):
    text: str
    url: str


class GuideSectionModel(BaseModel):
    anchor: str | None
    title: str
    paragraphs: list[GuideParagraphModel]
    links: list[GuideLinkModel]


class GuideNavigation(BaseModel):
    text: str
    anchor: str


class GuideDialog(BaseModel):
    width_px: int
    height_px: int
    screen_fraction: float


class OperationGuide(BaseModel):
    title: str
    details_button: str
    close_button: str
    summary: list[GuideParagraphModel]
    navigation: list[GuideNavigation]
    intro: str
    sections: list[GuideSectionModel]
    dialog: GuideDialog


class ExportFormat(BaseModel):
    key: Literal["csv", "xlsx"]
    label: str
    checked: bool = Field(description="格式对话框打开时是否已勾选")


class OperationExportTexts(BaseModel):
    title: str
    formats_label: str
    formats: list[ExportFormat]
    cancel_label: str
    confirm_label: str
    note: str
    done_title: str
    failed_title: str
    directory: str = Field(description="alpha 的导出目录（数据目录下 exports/，D-207）")


class OperationPage(BaseModel):
    as_of: str
    source: Source = "live_ro"
    title: str
    operations: list[OperationKind]
    default_operation: str
    texts: OperationTexts
    axis: OperationAxis
    guide: OperationGuide
    export: OperationExportTexts


class OperationSourceItem(BaseModel):
    key: str
    position: int
    device_name: str
    snapshot_id: str = Field(description=DATABASE_ID_TEXT)
    database_path: str = Field(description="设备库路径（alpha 数据目录 data/devices 下）")
    source_path: str = Field(description="同 database_path（快照时代为源库路径，#83 移除）")
    imported_at: str | None = Field(default=None, description="恒为 null（快照时代的导入时间，#83 移除）")
    display_state: Literal["normal", "disabled", "fault", "unconfigured"] = "normal"
    tooltip: str = Field(description="悬停全文：设备库的完整路径（UI-265）")


class OperationSources(BaseModel):
    as_of: str
    source: Source = "live_ro"
    items: list[OperationSourceItem]
    initial_a: str | None = Field(description="A 的初始来源：第一个位置（UI-156）")
    initial_b: str | None = Field(description="B 的初始来源：第二个位置；只有一个时与 A 相同")


class OperationCandidate(BaseModel):
    id: int
    acquired_at: str
    acquired_at_text: str
    label: str = Field(description="#ID | 北京时间，记录框的一项")


class OperationCandidates(BaseModel):
    as_of: str
    source: Source = "live_ro"
    key: str
    snapshot_id: str
    limit: int
    items: list[OperationCandidate] = Field(
        description="成功且为完整 701 点的记录，新的在前；keep 所指的旧记录附在最后"
    )
    empty_text: str


class NearestCandidate(OperationCandidate):
    time_difference_seconds: float | None = Field(description="该记录比 acquired_at 晚多少秒（早为负）")


class OperationNearest(BaseModel):
    as_of: str
    source: Source = "live_ro"
    key: str
    snapshot_id: str
    match: NearestCandidate | None


class SourceRefModel(BaseModel):
    source: str = Field(description="设备位置 p1–p4")
    id: int = Field(ge=0, le=SQLITE_MAX_INTEGER, description="采集记录 ID")
    snapshot_id: str | None = Field(
        default=None, description="调用方看到这条记录时的设备库标识；该位置换了设备库时返回 409 snapshot_changed"
    )


class OperationInputsRequest(BaseModel):
    a: SourceRefModel | None = None
    b: SourceRefModel | None = None


class OperationRequest(BaseModel):
    a: SourceRefModel
    b: SourceRefModel
    operation: str = Field(description="add / subtract / divide")


class OperationExportRequest(OperationRequest):
    formats: list[str] = Field(description="csv、xlsx 中的一种或两种（EXP-026）")


class OperationInput(BaseModel):
    label: str
    source: str | None
    snapshot_id: str | None
    id: int | None
    valid: bool = Field(description="成功且为完整 701 点的光谱")
    title: str
    legend: str
    device_name: str | None
    acquired_at: str | None
    acquired_at_text: str | None
    y_range: Range | None = Field(description="纵轴范围；A、B 都有效时两图共用（UI-209）")
    values: list[float] | None = Field(description="光谱 mW/nm = 原始值 / 10^光谱系数，不归一化（UI-211）")


class TimeDifference(BaseModel):
    seconds: float | None
    text: str
    tooltip: str


class Placeholder(BaseModel):
    heading: str
    detail: str


class OperationInputs(BaseModel):
    as_of: str
    source: Source = "live_ro"
    a: OperationInput
    b: OperationInput
    valid: bool
    time_difference: TimeDifference
    placeholder: Placeholder = Field(description="结果图尚未计算时中央的文字（UI-210、UI-216）")


class OperationResult(BaseModel):
    operation: str
    operation_label: str
    title: str
    legend: str
    y_label: str
    ratio: bool = Field(description="比值：无填充折线（UI-223），有 2% 显示筛选")
    values: list[float | None] = Field(description="完整计算结果，701 点；无效为 null（MATH-010），不截断（MATH-009）")
    plotted: list[float | None] = Field(description="绘制的点：比值中未通过 2% 筛选的为 null，断线不补零（UI-218）")
    y_range: Range = Field(description="结果图独立的纵轴范围（UI-214、UI-221、UI-222）")
    reference_line: bool = Field(description="是否画 1 倍虚线：只在 1 落在纵轴范围内时（UI-220）")
    ratio_note: str | None
    empty_text: str | None = Field(description="比值没有可绘制的点时的提示（UI-219）")
    threshold: float | None = Field(description="比值显示共同阈值 T（MATH-015）；加减法为 null")


class OperationComputation(OperationInputs):
    result: OperationResult


class OperationExported(BaseModel):
    as_of: str
    directory: str
    files: list[str]
    text: str
