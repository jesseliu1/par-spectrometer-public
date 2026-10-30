"""Tier 2 device maintenance endpoints (17_ section 9; api-contract-v0 section 4 as amended by D-216).

Every handler is plain `def` (FastAPI's thread pool): the controller runs on the service's Qt main thread and is
reached through the application layer's MaintenanceService, which checks the tier (403 feature_disabled below 2) and
the running takeover first. A write is two requests: `…/confirmations` (the service checks the preconditions and
answers V1.0.3's dialog text with a one-time confirmation id), then the write itself with that id and the same body.
There is no endpoint that clears a hardware latch, and none for read_identity or a plain comm_write (D-216 q. 3).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..application.maintenance import MaintenanceService, WriteConfirmation
from .models import ErrorResponse
from .routes import API_PREFIX, ERRORS, Key, _context

MAINTENANCE_ERRORS: dict[int | str, dict[str, Any]] = {
    int(HTTPStatus.FORBIDDEN): {"model": ErrorResponse, "description": "feature_disabled：档位低于 2"},
    int(HTTPStatus.CONFLICT): {
        "model": ErrorResponse,
        "description": "not_running / busy / no_session / precondition_failed（V1.0.3 原文）/ halted / "
        "confirmation_required",
    },
}
router = APIRouter(prefix=API_PREFIX, responses={**ERRORS, **MAINTENANCE_ERRORS})


class MaintenanceState(BaseModel):
    """The maintenance page's view model; every text and every enabled state is the service's (17_ 9)."""

    model_config = ConfigDict(extra="allow")

    available: bool = Field(description="正在接管采集（协调器在运行）；否则只有 reason")
    reason: str
    version: int = Field(description="视图版本号；SSE maintenance_state 推送同一个号")


class Page(BaseModel):
    tab: int = Field(default=0, ge=0, le=2, description="0 设备状态与诊断；1 光谱校准；2 通信参数维护")


class Target(BaseModel):
    key: str = Field(description="协调器的设备标识（设备名，重名时带 #地址），见 state.devices")


class Confirmed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_id: str | None = None


class CommFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slave_id: int
    baudrate: int
    parity: str


class CommForm(BaseModel):
    """MaintenanceDialog's fields: 电脑串口, 读取连接参数, 准备写入的新参数, 已确认通信链路只连接目标设备."""

    model_config = ConfigDict(extra="forbid")

    serial_port: str
    old: CommFields
    new: CommFields
    isolated: bool
    confirmation_id: str | None = Field(default=None, description="只有写入需要；确认请求不带")


class DraftEdit(BaseModel):
    """One box edited (`field`, `value` as typed in its unit) or one preview node dragged (`node`, `x` nm, `y` %)."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    value: float | None = None
    node: int | None = None
    x: float | None = None
    y: float | None = None


class WriteConfirmationModel(BaseModel):
    confirmation_id: str
    action: str
    expires_at: str = Field(description="北京时间；60 秒内有效，只能使用一次")
    title: str = Field(description="V1.0.3 确认框标题")
    text: str = Field(description="V1.0.3 确认框正文（服务按 V1.0.3 的格式生成）")


class SettingsComm(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    source: str = Field(description="“当前值 · 设备 · 状态”（V1.0.3 设置页原文）")


def _service(request: Request) -> MaintenanceService:
    return _context(request).maintenance


def _state(data: dict[str, Any]) -> MaintenanceState:
    return MaintenanceState(**data)


def _confirmation(issued: WriteConfirmation) -> WriteConfirmationModel:
    return WriteConfirmationModel(
        confirmation_id=issued.id,
        action=issued.action,
        expires_at=issued.expires_at,
        title=issued.title,
        text=issued.text,
    )


def _form(body: CommForm) -> dict[str, Any]:
    return body.model_dump(exclude={"confirmation_id"})


@router.get("/maintenance/state", response_model=MaintenanceState, summary="设备维护页视图模型（只读）")
def state(request: Request) -> MaintenanceState:
    return _state(_service(request).view())


@router.post(
    "/maintenance/page", response_model=MaintenanceState, summary="打开维护页会话（同一时间一个；自动读取同 V1.0.3）"
)
def open_page(request: Request, body: Page) -> MaintenanceState:
    return _state(_service(request).open_page(str(body.tab)))


@router.delete(
    "/maintenance/page", response_model=MaintenanceState, summary="关闭维护页会话（有未写入校准修改须带放弃确认号）"
)
def close_page(
    request: Request, confirmation_id: Annotated[str | None, Query(description="放弃修改的确认号")] = None
) -> MaintenanceState:
    return _state(_service(request).close_page(confirmation_id))


def _act(request: Request, action: str, body: dict[str, Any], confirmation_id: str | None = None) -> MaintenanceState:
    return _state(_service(request).act(action, body, confirmation_id))


def _confirm(request: Request, action: str, body: dict[str, Any]) -> WriteConfirmationModel:
    return _confirmation(_service(request).confirm(action, body))


@router.post(
    "/maintenance/tab", response_model=MaintenanceState, summary="切换页签（诊断、校准页签按 V1.0.3 自动读取）"
)
def tab(request: Request, body: Page) -> MaintenanceState:
    return _act(request, "tab", {"tab": body.tab})


@router.put("/maintenance/target", response_model=MaintenanceState, summary="选择维护设备（锁定时 409）")
def target(request: Request, body: Target) -> MaintenanceState:
    return _act(request, "target", {"key": body.key})


@router.post(
    "/maintenance/diagnostics/read", response_model=MaintenanceState, summary="读取设备诊断（diagnostics_read）"
)
def diagnostics_read(request: Request) -> MaintenanceState:
    return _act(request, "diagnostics_read", {})


@router.post(
    "/maintenance/diagnostics/export",
    response_model=MaintenanceState,
    summary="导出诊断（写 alpha 数据目录 exports/，内容同 V1.0.3）",
)
def diagnostics_export(request: Request) -> MaintenanceState:
    return _act(request, "diagnostics_export", {})


@router.post(
    "/maintenance/calibration/read/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="重新读取校准前放弃未写入修改的确认",
)
def calibration_reread_confirmation(request: Request) -> WriteConfirmationModel:
    return _confirm(request, "calibration_reread", {})


@router.post(
    "/maintenance/calibration/read", response_model=MaintenanceState, summary="从硬件读取校准（calibration_read）"
)
def calibration_read(request: Request, body: Confirmed) -> MaintenanceState:
    return _act(request, "calibration_read", {}, body.confirmation_id)


@router.patch(
    "/maintenance/calibration/draft", response_model=MaintenanceState, summary="编辑校准草稿（服务按编辑框位数取整）"
)
def calibration_edit(request: Request, body: DraftEdit) -> MaintenanceState:
    return _act(request, "calibration_edit", body.model_dump(exclude_none=True))


@router.post("/maintenance/calibration/discard", response_model=MaintenanceState, summary="放弃待写入修改")
def calibration_discard(request: Request) -> MaintenanceState:
    return _act(request, "calibration_discard", {})


@router.post(
    "/maintenance/calibration/write/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="校准写入的确认（V1.0.3 原文，列出改动）",
)
def calibration_write_confirmation(request: Request) -> WriteConfirmationModel:
    return _confirm(request, "calibration_write", {})


@router.post(
    "/maintenance/calibration/write", response_model=MaintenanceState, summary="写入硬件并回读（calibration_write）"
)
def calibration_write(request: Request, body: Confirmed) -> MaintenanceState:
    return _act(request, "calibration_write", {}, body.confirmation_id)


@router.post(
    "/maintenance/enter/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="停止全部采集并进入通信维护的确认",
)
def enter_confirmation(request: Request) -> WriteConfirmationModel:
    return _confirm(request, "enter", {})


@router.post("/maintenance/enter", response_model=MaintenanceState, summary="进入通信维护（enter_maintenance）")
def enter(request: Request, body: Confirmed) -> MaintenanceState:
    return _act(request, "enter", {}, body.confirmation_id)


@router.post("/maintenance/comm/read", response_model=MaintenanceState, summary="读取目标设备（maintenance_read）")
def comm_read(request: Request, body: CommForm) -> MaintenanceState:
    return _act(request, "comm_read", _form(body))


@router.post(
    "/maintenance/comm/write/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="写入通信参数的确认（V1.0.3 原文）",
)
def comm_write_confirmation(request: Request, body: CommForm) -> WriteConfirmationModel:
    return _confirm(request, "comm_write", _form(body))


@router.post(
    "/maintenance/comm/write",
    response_model=MaintenanceState,
    summary="确认并写入（maintenance_write；成功后自动 maintenance_verify）",
)
def comm_write(request: Request, body: CommForm) -> MaintenanceState:
    return _act(request, "comm_write", _form(body), body.confirmation_id)


@router.post(
    "/maintenance/comm/verify", response_model=MaintenanceState, summary="使用新参数核对（maintenance_verify）"
)
def comm_verify(request: Request, body: CommForm) -> MaintenanceState:
    return _act(request, "comm_verify", _form(body))


@router.post(
    "/maintenance/leave/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="退出维护并恢复采集的确认（resume_gate 不通过时 409）",
)
def leave_confirmation(request: Request) -> WriteConfirmationModel:
    return _confirm(request, "leave", {})


@router.post(
    "/maintenance/leave",
    response_model=MaintenanceState,
    summary="退出维护并恢复采集（leave_maintenance；维护页与设置页同一入口，D-110）",
)
def leave(request: Request, body: Confirmed) -> MaintenanceState:
    return _act(request, "leave", {}, body.confirmation_id)


@router.post(
    "/maintenance/page/close/confirmations",
    response_model=WriteConfirmationModel,
    status_code=HTTPStatus.CREATED,
    summary="关闭维护页时放弃未写入校准修改的确认",
)
def close_confirmation(request: Request) -> WriteConfirmationModel:
    return _confirm(request, "close_discard", {})


@router.post("/maintenance/notice/dismiss", response_model=MaintenanceState, summary="关闭提示框（“无法恢复采集”）")
def dismiss(request: Request) -> MaintenanceState:
    return _act(request, "dismiss_notice", {})


@router.post(
    "/acquisition/devices/{key}/comm/read",
    response_model=SettingsComm,
    summary="设置页“通信参数当前值”（comm_read；不满足 V1.0.3 条件时只返回状态文字）",
)
def settings_comm(request: Request, key: Key) -> SettingsComm:
    return SettingsComm(**_service(request).settings_comm(key))


@router.delete(
    "/acquisition/devices/comm/read",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    summary="离开设置页：停止“通信参数当前值”在设备上线、总线连上时的自动重读（V1.0.3 只在设置页显示时重读）",
)
def settings_left(request: Request) -> Response:
    _service(request).settings_left()
    return Response(status_code=HTTPStatus.NO_CONTENT)
