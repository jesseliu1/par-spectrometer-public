"""Routes of the spectrum calculation page (api-contract-v0 API-11..14, API-24, API-25), tier 0, read only except
for the export files written into the alpha's own output folder (D-207).

POST is used for inputs and compute only because they take two record references; they write nothing. Handlers are
plain `def` (thread pool), like the other routes.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from ..application.operation_page import GuideParagraph, page_content
from ..application.operations import Candidate, Computation, Inputs, InputSide, SourceRef
from ..application.readonly import SQLITE_MAX_INTEGER
from . import operation_models as models
from .context import ServiceContext
from .models import ErrorResponse
from .routes import API_PREFIX, ERRORS, Key, _context

router = APIRouter(prefix=API_PREFIX, responses=ERRORS)
CONFLICT: dict[int | str, dict[str, Any]] = {
    int(HTTPStatus.CONFLICT): {"model": ErrorResponse, "description": "snapshot_changed：该位置换了设备库（配置已改）"}
}
EXPORT_ERRORS: dict[int | str, dict[str, Any]] = {
    **CONFLICT,
    int(HTTPStatus.INTERNAL_SERVER_ERROR): {
        "model": ErrorResponse,
        "description": "export_failed：写文件失败；detail 写明结果目录与已完成的文件（EXP-020）",
    },
}


def _numbers(values: Iterable[float]) -> list[float | None]:
    """JSON has no NaN or infinity: an invalid point becomes null (a gap on the chart, never zero)."""
    return [float(value) if math.isfinite(value) else None for value in values]


def _paragraphs(items: Iterable[GuideParagraph]) -> list[models.GuideParagraphModel]:
    return [models.GuideParagraphModel(head=item.head, text=item.text) for item in items]


@router.get("/operations/page", response_model=models.OperationPage, summary="光谱计算页：运算法则、固定文本、应用说明")
def page(request: Request) -> models.OperationPage:
    context = _context(request)
    content = page_content(context.paths.exports_dir)
    guide = content.guide
    return models.OperationPage(
        as_of=context.now(),
        title=content.title,
        operations=[models.OperationKind(key=key, label=label) for key, label in content.operations],  # type: ignore[arg-type]
        default_operation=content.default_operation,
        texts=models.OperationTexts(**vars(content.texts)),
        axis=models.OperationAxis(**vars(content.axis)),
        guide=models.OperationGuide(
            title=guide.title,
            details_button=guide.details_button,
            close_button=guide.close_button,
            summary=_paragraphs(guide.summary),
            navigation=[models.GuideNavigation(text=text, anchor=anchor) for text, anchor in guide.navigation],
            intro=guide.intro,
            sections=[
                models.GuideSectionModel(
                    anchor=section.anchor,
                    title=section.title,
                    paragraphs=_paragraphs(section.paragraphs),
                    links=[models.GuideLinkModel(text=link.text, url=link.url) for link in section.links],
                )
                for section in guide.sections
            ],
            dialog=models.GuideDialog(
                width_px=guide.width_px, height_px=guide.height_px, screen_fraction=guide.screen_fraction
            ),
        ),
        export=models.OperationExportTexts(
            **{
                **vars(content.export),
                "formats": [
                    models.ExportFormat(key=key, label=label, checked=checked)  # type: ignore[arg-type]
                    for key, label, checked in content.export.formats
                ],
            }
        ),
    )


@router.get("/operation-sources", response_model=models.OperationSources, summary="光谱计算的 A/B 来源（已导入的快照）")
def sources(request: Request) -> models.OperationSources:
    context = _context(request)
    found = context.operations.sources()
    return models.OperationSources(
        as_of=context.now(),
        items=[
            models.OperationSourceItem(
                key=item.device.key,
                position=item.device.position,
                device_name=item.device.name,
                snapshot_id=item.device.id,
                database_path=item.device.path,
                source_path=item.device.path,
                imported_at=None,
                tooltip=item.tooltip,
            )
            for item in found.items
        ],
        initial_a=found.initial_a,
        initial_b=found.initial_b,
    )


def _candidate(item: Candidate) -> models.OperationCandidate:
    return models.OperationCandidate(**vars(item))


@router.get(
    "/operation-sources/{key}/spectra",
    response_model=models.OperationCandidates,
    summary="候选记录：最近 500 条成功且完整的光谱（keep 所指的旧记录附在最后）",
)
def spectra(
    request: Request,
    key: Key,
    keep: Annotated[
        int | None, Query(ge=0, le=SQLITE_MAX_INTEGER, description="仍选中的记录 ID：不在 500 条内但仍可用时附在最后")
    ] = None,
) -> models.OperationCandidates:
    context = _context(request)
    found = context.operations.spectra(key, keep)
    return models.OperationCandidates(
        as_of=context.now(),
        key=found.device.key,
        snapshot_id=found.device.id,
        limit=found.limit,
        items=[_candidate(item) for item in found.items],
        empty_text=found.empty_text,
    )


@router.get(
    "/operation-sources/{key}/nearest",
    response_model=models.OperationNearest,
    summary="最近时间匹配：全库中与给定时间最近的成功完整光谱（不设容差，不是同步采集）",
)
def nearest(
    request: Request,
    key: Key,
    acquired_at: Annotated[str, Query(description="A 记录的采集时间（库中原样）")],
) -> models.OperationNearest:
    context = _context(request)
    found = context.operations.nearest(key, acquired_at)
    match = (
        models.NearestCandidate(**vars(found.match), time_difference_seconds=found.time_difference_seconds)
        if found.match
        else None
    )
    return models.OperationNearest(as_of=context.now(), key=key, snapshot_id=found.device.id, match=match)


def _ref(body: models.SourceRefModel | None) -> SourceRef | None:
    return SourceRef(body.source, body.id, body.snapshot_id) if body is not None else None


def _input(side: InputSide) -> models.OperationInput:
    return models.OperationInput(
        label=side.label,
        source=side.ref.source if side.ref else None,
        snapshot_id=side.snapshot_id,
        id=side.ref.id if side.ref else None,
        valid=side.valid,
        title=side.title,
        legend=side.legend,
        device_name=side.device_name,
        acquired_at=side.acquired_at,
        acquired_at_text=side.acquired_at_text,
        y_range=side.y_range,
        values=[float(value) for value in side.values] if side.values is not None else None,
    )


def _inputs_fields(context: ServiceContext, inputs: Inputs) -> dict[str, Any]:
    return {
        "as_of": context.now(),
        "a": _input(inputs.a),
        "b": _input(inputs.b),
        "valid": inputs.valid,
        "time_difference": models.TimeDifference(
            seconds=inputs.time_difference_seconds, text=inputs.time_difference_text, tooltip=inputs.time_tooltip
        ),
        "placeholder": models.Placeholder(heading=inputs.placeholder_heading, detail=inputs.placeholder_detail),
    }


@router.post(
    "/operations/inputs",
    response_model=models.OperationInputs,
    responses=CONFLICT,
    summary="A/B 两图：所选记录的光谱、共同纵轴、采集时间差（不写任何数据）",
)
def inputs(request: Request, body: models.OperationInputsRequest) -> models.OperationInputs:
    context = _context(request)
    found = context.operations.inputs(_ref(body.a), _ref(body.b))
    return models.OperationInputs(**_inputs_fields(context, found))


def _result(computation: Computation) -> models.OperationResult:
    result = computation.result
    operation = result.operation
    return models.OperationResult(
        operation=operation,
        operation_label=result.operation_label,
        title=result.title,
        legend=result.legend,
        y_label=result.y_label,
        ratio=result.ratio,
        values=_numbers(result.values),
        plotted=_numbers(result.plotted),
        y_range=result.y_range,
        reference_line=result.reference_line,
        ratio_note=result.ratio_note,
        empty_text=result.empty_text,
        threshold=result.threshold,
    )


@router.post(
    "/operations/compute",
    response_model=models.OperationComputation,
    responses=CONFLICT,
    summary="执行计算：逐波长 A+B、A−B 或 A/B（V1.0.3 math_ops.combine；不写任何数据）",
)
def compute(request: Request, body: models.OperationRequest) -> models.OperationComputation:
    context = _context(request)
    a, b = _ref(body.a), _ref(body.b)
    assert a is not None and b is not None
    found = context.operations.compute(a, b, body.operation)
    return models.OperationComputation(**_inputs_fields(context, found.inputs), result=_result(found))


@router.post(
    "/operations/export",
    response_model=models.OperationExported,
    status_code=HTTPStatus.CREATED,
    responses=EXPORT_ERRORS,
    summary="导出计算结果：在 alpha 输出目录中新建结果目录，每种格式一个文件（V1.0.3 导出格式）",
)
def export(request: Request, body: models.OperationExportRequest) -> models.OperationExported:
    context = _context(request)
    a, b = _ref(body.a), _ref(body.b)
    assert a is not None and b is not None
    outcome = context.operations.export(a, b, body.operation, body.formats)
    return models.OperationExported(
        as_of=context.now(), directory=outcome.directory, files=outcome.files, text=outcome.text
    )
