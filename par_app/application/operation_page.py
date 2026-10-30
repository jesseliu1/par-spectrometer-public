"""Fixed content of the spectrum calculation page (API-11): operations, texts, axis, guide and export dialog.

The values are the copies in par_app.services.operation_display and operation_guide; this module only gathers
them so that the API layer maps a finished value into its response model and never reads services itself (route C
section 4, import contract "API layer reaches services only through the application layer").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..services import operation_display as display
from ..services import operation_guide as guide
from ..services.operation_guide import GuideLink, GuideParagraph, GuideSection
from .operations import EMPTY_SOURCES, EXPORT_CONFIRM, EXPORT_NOTE, PAGE_TITLE

__all__ = [
    "GuideLink",
    "GuideParagraph",
    "GuideSection",
    "PageAxis",
    "PageContent",
    "PageExport",
    "PageGuide",
    "PageTexts",
    "page_content",
]


@dataclass(frozen=True)
class PageTexts:
    """Field for field the API's OperationTexts."""

    source_labels: list[str]
    operation_label: str
    run_label: str
    export_label: str
    swap_tooltip: str
    auto_match_label: str
    auto_match_tooltip: str
    time_tooltip: str
    no_spectrum: str
    input_empty_heading: str
    input_empty_detail: str
    waiting_heading: str
    missing_heading: str
    missing_detail: str
    result_title: str
    x_label: str
    power_y_label: str
    empty_sources: str


@dataclass(frozen=True)
class PageAxis:
    start_nm: int
    end_nm: int
    ticks_wide: list[int]
    ticks_narrow: list[int]
    narrow_below_px: int


@dataclass(frozen=True)
class PageGuide:
    title: str
    details_button: str
    close_button: str
    summary: tuple[GuideParagraph, ...]
    navigation: tuple[tuple[str, str], ...]
    intro: str
    sections: tuple[GuideSection, ...]
    width_px: int
    height_px: int
    screen_fraction: float


@dataclass(frozen=True)
class PageExport:
    title: str
    formats_label: str
    formats: tuple[tuple[str, str, bool], ...]
    """(key, label, checked by default)"""
    cancel_label: str
    confirm_label: str
    note: str
    done_title: str
    failed_title: str
    directory: str


@dataclass(frozen=True)
class PageContent:
    title: str
    operations: tuple[tuple[str, str], ...]
    """(key, label), in V1.0.3's combo order"""
    default_operation: str
    texts: PageTexts
    axis: PageAxis
    guide: PageGuide
    export: PageExport


def page_content(exports_dir: Path) -> PageContent:
    """Everything API-11 returns except `as_of`; `exports_dir` is the alpha's output folder (D-207)."""
    return PageContent(
        title=PAGE_TITLE,
        operations=display.OPERATIONS,
        default_operation=display.OPERATIONS[0][0],
        texts=PageTexts(
            source_labels=list(display.SOURCE_LABELS),
            operation_label=display.OPERATION_LABEL,
            run_label=display.RUN_LABEL,
            export_label=display.EXPORT_LABEL,
            swap_tooltip=display.SWAP_TOOLTIP,
            auto_match_label=display.AUTO_MATCH_LABEL,
            auto_match_tooltip=display.AUTO_MATCH_TOOLTIP,
            time_tooltip=display.TIME_TOOLTIP,
            no_spectrum=display.NO_SPECTRUM,
            input_empty_heading=display.INPUT_EMPTY_HEADING,
            input_empty_detail=display.INPUT_EMPTY_DETAIL,
            waiting_heading=display.WAITING_HEADING,
            missing_heading=display.MISSING_HEADING,
            missing_detail=display.MISSING_DETAIL,
            result_title=display.RESULT_TITLE,
            x_label=display.X_LABEL,
            power_y_label=display.POWER_Y_LABEL,
            empty_sources=EMPTY_SOURCES,
        ),
        axis=PageAxis(
            start_nm=display.AXIS_START_NM,
            end_nm=display.AXIS_END_NM,
            ticks_wide=list(display.TICKS_WIDE),
            ticks_narrow=list(display.TICKS_NARROW),
            narrow_below_px=display.NARROW_CHART_PX,
        ),
        guide=PageGuide(
            title=guide.TITLE,
            details_button=guide.DETAILS_BUTTON,
            close_button=guide.CLOSE_BUTTON,
            summary=guide.SUMMARY,
            navigation=guide.NAVIGATION,
            intro=guide.INTRO,
            sections=guide.SECTIONS,
            width_px=guide.DIALOG_WIDTH_PX,
            height_px=guide.DIALOG_HEIGHT_PX,
            screen_fraction=guide.DIALOG_SCREEN_FRACTION,
        ),
        export=PageExport(
            title=display.EXPORT_TITLE,
            formats_label=display.EXPORT_FORMATS_LABEL,
            formats=display.EXPORT_FORMATS,
            cancel_label=display.EXPORT_CANCEL,
            confirm_label=EXPORT_CONFIRM,
            note=EXPORT_NOTE,
            done_title=display.EXPORT_DONE_TITLE,
            failed_title=display.EXPORT_FAILED_TITLE,
            directory=str(exports_dir),
        ),
    )
