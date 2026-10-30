"""V1.0.3's maintenance texts, word for word (17_ 6.3; D-216 question 10).

The import contract keeps par_app.acquisition_host away from V1.0.3's widgets (par_app.ui, maintenance_dialog,
device_maintenance_dialog), so the texts are copied here. `SOURCES` names, for every text, the V1.0.3 file and
function it comes from; tests/acquisition/test_maintenance_texts.py parses those functions and checks every literal
part of every text (the parts between `{…}` placeholders of a template) against the string constants found there, so
a wording change on the V1.0.3 line turns that test red when it is merged forward.
"""

from __future__ import annotations

DIALOG = "par_app/device_maintenance_dialog.py"
COMM_DIALOG = "par_app/maintenance_dialog.py"
MAIN_WINDOW = "par_app/ui.py"

# --------------------------------------------------------------------------------------- confirmations (17_ 6.3)
ENTER_TITLE = "停止全部采集并进入维护"
ENTER_TEXT = (
    "将等待当前通信结束，停止全部设备采集、对时和自动重连。\n进入后只连接目标设备；关闭窗口不会恢复采集。是否继续？"
)
COMM_WRITE_TITLE = "确认硬件写入"
COMM_WRITE_TEXT = (
    "目标：{target}\n{identity}\n\n新参数：{new}\n\n"
    "本操作修改探头内部参数，动态生效，无需重新上电。写入成功后自动使用新参数核对；软件连接配置不会自动改变。"
)
CALIBRATION_WRITE_TITLE = "确认校准写入"
CALIBRATION_WRITE_TEXT = "设备：{name}（地址 {slave_id}）\n{changes}\n\n确认写入并回读？"
RESUME_TITLE = "确认恢复采集"
RESUME_TEXT = (
    "请确认维护核对已完成、原总线设备已接回，且所有启用设备与软件连接参数一致。\n恢复不会改变任何探头参数，是否继续？"
)
DISCARD_TITLE = "放弃待写入修改"
REREAD_TEXT = "重新读取将覆盖尚未写入的修改，是否继续？"
CLOSE_TEXT = "关闭将放弃尚未写入的校准修改，是否继续？"
ISOLATION_TITLE = "维护条件"
ISOLATION_TEXT = "请先只连接目标设备，并勾选确认。"
NOT_READ_TITLE = "校准未读取"
NOT_READ_TEXT = "请先读取当前设备校准参数，再执行写入。"
INVALID_TITLE = "校准参数无效"
INVALID_TEXT = "节点波长须递增，限幅下限不能大于上限。"
RESUME_FAILED_TITLE = "无法恢复采集"

# ------------------------------------------------------------------------------- device maintenance window
TARGET_TEXT = "维护目标：{name}（登记地址 {slave_id}）"
LEVEL_TEXTS = {
    "ok": "在线",
    "idle": "未读取",
    "error": "异常",
    "offline": "离线",
    "power": "需要重新上电",
    "warning": "等待",
}
LEVEL_HALTED = "硬件异常停止"
LEVEL_MAINTENANCE = "维护暂停"
LEVEL_ENTERING = "正在停止"
ADDRESS_TEXT = "地址：{slave_id}"
NO_ADDRESS = "地址：—"
COMMUNICATION_TEXT = "通信：{level}"
UNREGISTERED = "设备未登记"
STATE_DIAGNOSTICS = "正在读取设备诊断…"
STATE_ENTERING = "正在停止采集：等待当前通信结束"
STATE_CALIBRATION_WRITE = "正在写入校准并回读…"
STATE_CALIBRATION_READ = "正在读取硬件校准…"
STATE_TASK = "设备任务进行中…"
READ_IN_MAINTENANCE = "通信维护中，诊断读取已暂停。"
READ_ENTERING = "正在等待当前通信结束。"
READ_BUSY = "设备任务进行中。"
READ_UNREGISTERED = "设备未登记或已停用。"
READ_UNCONFIGURED = "连接配置尚未确认。"
READ_EXCLUDED = "设备连续通信失败，已退出本次采集。"
NOT_ENTERED = "未进入通信维护，{reason}"
READ_FAILED = "读取失败：{reason}"
CLOSE_IN_MAINTENANCE = "关闭（保持停止）"
CLOSE = "关闭"
NOT_IN_MAINTENANCE = "未进入通信维护；{state}"
EXPORT_SNAPSHOT = "导出诊断快照"
EXPORT_EVENTS = "导出事件记录"
EXPORTED_SNAPSHOT = "诊断快照已导出"
EXPORTED_EVENTS = "事件记录已导出"
EXPORT_FAILED_TITLE = "导出失败"
EXPORT_FILE_NAME = "device_diagnostics.json"

COMMUNICATION_ERRORS = (
    "通信改参超时",
    "CRC 错误",
    "帧错误",
    "接收超时",
    "非法功能码",
    "接收溢出",
    "发送超时",
    "接收冗余",
)
PAR_ERRORS = (
    "初始化设置曝光模式失败",
    "DMA 传输错误",
    "发送未完成",
    "发送返回长度错误",
    "初始化设备信息失败",
    "光谱仪波特率不符",
    "初始化解析失败",
    "发送命令失败",
    "DMA 接收超时",
    "DMA 接收错误",
    "数据长度或 CRC 错误",
    "光谱解析失败",
    "光谱计算错误",
    "连续失败超限",
)
NOT_READ_STAMP = "本次尚未读取硬件诊断"
LAST_FAILURE = "；最近读取失败：{reason}"
NOT_READ_VALUE = "本次尚未读取"
HISTORICAL = "历史值 · "
STAMP = "诊断快照时间：{time}"
IDENTITY_LINE = "设备身份：{name}    序列号：{serial}    类型：{type}"
VALUES_LINE = "MCU 温度：{temperature}    初始化：{initialized}    需要重新上电：{power}"
EXPOSURE_LINE = "曝光：{exposure}    曝光模式：{mode}    曝光时间：{time} ms"
DATA_LINE = "原始数据：{raw}    计算数据：{calculated}"
NO_NONZERO = "未发现非零错误计数"
NO_NONZERO_HISTORICAL = "历史快照中未发现非零错误计数"
NOT_READ_TOOLTIP = "尚未读取，不代表零错误"
NO_DELTA_TOOLTIP = "首次读取、计数下降或饱和，无法可靠计算增量"
EXPOSURES = {0: "正常", 1: "过曝光", 2: "欠曝光"}
EXPOSURE_MODES = {0: "手动", 1: "自动"}
EVENT_LEVELS = {"INFO": "信息", "WARNING": "警告", "ERROR": "错误", "DEBUG": "调试"}
EVENT_ACTIONS = {
    "maintenance_read": "读取通信参数",
    "maintenance_write": "写入通信参数",
    "maintenance_verify": "核对新参数",
}
EVENT_CATEGORIES = {
    "communication_maintenance": "通信参数维护",
    "diagnostics_read": "读取设备诊断",
    "time_sync": "设备对时",
    "acquisition_halted": "硬件异常停止",
    "connection": "连接",
    "communication": "通信异常",
    "communication_recovery": "通信恢复",
    "acquisition": "采集异常",
    "device": "设备",
    "read_identity": "读取设备身份",
    "comm_read": "读取通信参数",
    "comm_write": "写入通信参数",
    "calibration_read": "读取光谱校准",
    "calibration_write": "写入光谱校准",
}
COMM_PARAMETERS_READ = "已读取设备当前通信参数"
WRITE_OPERATION = "写入通信参数"

# ---------------------------------------------------------------------------- communication maintenance tab
STATE_NOT_ENTERED = "尚未进入通信维护，采集状态未改变。"
STATE_PENDING = "采集已停止：写入已尝试，结果待使用新参数核对；不会自动重连或恢复采集。"
STATE_VERIFIED_BLOCKED = "设备身份和新参数核对通过，但暂不能恢复采集：{reason}"
STATE_VERIFIED = "设备身份和新参数核对通过，可以退出通信维护并恢复采集；当前仍保持停止。"
STATE_MAINTENANCE = "维护模式：采集、对时和自动重连已停止；连接已释放。"
STATE_LEFT = "已退出通信维护。"
SUBMIT_TEXTS = {
    "maintenance_read": "正在读取目标设备…",
    "maintenance_write": "正在写入通信参数…",
    "maintenance_verify": "正在使用新参数核对…",
}
SUBMIT_OTHER = "维护通信进行中…"
FINISHED_TEXTS = {
    "maintenance_read": "目标设备已读取，请核对身份与准备写入值。",
    "maintenance_write": "写入命令已完成；请使用新参数核对，无需重新上电。采集保持停止。",
    "maintenance_verify": "设备身份和新参数核对通过。",
}
AUTO_VERIFY = "写入完成，正在使用新参数自动核对；采集保持停止。"
OPERATION_FAILED = "操作失败：{reason}\n采集保持停止；若写入结果不确定，仍须使用新参数核对。"
IDENTITY_NOT_READ = "设备身份：未读取"
IDENTITY_DEVICE = "设备：{name}    类型：{type}"
IDENTITY_SERIAL = "序列号：{serial}"
IDENTITY_CONNECTION = "{label}：{serial_port} / ID {slave_id} / {baudrate} / {parity}"
IDENTITY_LABELS = (("connection", "读取连接"), ("old", "原连接"), ("new", "待核对连接"))
UNREAD = "未读取"
FIXED_PARAMETERS = "数据位 / 停止位：8 / 1（固定）"
PARITY_LABELS = ("无校验 N", "奇校验 O", "偶校验 E")

# ------------------------------------------------------------------------- main window (calibration, settings)
CALIBRATION_NOT_READ = "未读取当前维护设备的校准参数。"
CALIBRATION_FAILED = "校准操作失败：{reason}"
CALIBRATION_UNCONFIRMED = "回读未确认"
CALIBRATION_INVALID_STATE = "回读参数无效"
CALIBRATION_INVALID_NOTE = "硬件回读校准参数无效，请检查数值、节点波长顺序及限幅范围。"
CALIBRATION_PENDING = "待写入修改"
CALIBRATION_CURRENT = "当前硬件值"
CALIBRATION_UNREAD = "尚未读取"
CALIBRATION_OUT_OF_ORDER = "节点波长须递增"
COMM_STATES = {
    "unconfigured": "尚未配置",
    "halted": "采集已停止",
    "maintenance": "维护中",
    "excluded": "设备未参与采集",
    "disconnected": "总线未连接",
    "reading": "读取中…",
    "read": "已读取",
    "failed": "读取失败",
    "verifying": "写后核对中…",
    "unverified": "写入待核对",
    "unread": "尚未读取",
}
COMM_INVALID = "设备返回的通信参数无效"
COMM_SOURCE = "当前值 · {source} · {status}"
COMM_UNREGISTERED = "未登记"
COMM_MISMATCH = "与配置值不一致"
PARITY_TEXTS = ("无校验", "奇校验", "偶校验")
ACQUISITION_MAINTENANCE = "采集停止中：设备维护模式"
ACQUISITION_ENTERING = "正在停止采集：等待当前通信结束"
ACQUISITION_UNCONFIGURED = "等待配置，尚未采集"
ACQUISITION_NONE = "采集停止中：无可采集设备，重启软件后重新尝试"
ACQUISITION_PARTIAL = "采集运行中：部分设备异常"
ACQUISITION_OK = "正常采集"
ACQUISITION_WAITING = "采集运行中：等待设备响应"

# ------------------------------------ settings page 计算机串口 / 刷新串口 (#74; MainWindow.refresh_serial_ports)
SERIAL_PORT_LABEL = "{device} — {description}"
SERIAL_PORT_UNKNOWN = "未知设备"
SERIAL_PORTS_FOUND = "检测到 {count} 个串口，请手动选择；不会自动搜索或切换端口。"
SERIAL_PORTS_NONE = "未检测到串口；请确认 USB 线、驱动和设备电源。"
SERIAL_PORTS_FAILED = "串口枚举失败：{error}"
"""V1.0.3's settings page lets the enumeration error escape; SerialPortComboBox.refresh_ports says this (R-1-5)."""

SOURCES: dict[str, tuple[str, str]] = {
    "ENTER_TITLE": (DIALOG, "enter_communication"),
    "ENTER_TEXT": (DIALOG, "enter_communication"),
    "COMM_WRITE_TITLE": (COMM_DIALOG, "submit"),
    "COMM_WRITE_TEXT": (COMM_DIALOG, "submit"),
    "CALIBRATION_WRITE_TITLE": (MAIN_WINDOW, "write_calibration"),
    "CALIBRATION_WRITE_TEXT": (MAIN_WINDOW, "write_calibration"),
    "RESUME_TITLE": (MAIN_WINDOW, "resume_after_maintenance"),
    "RESUME_TEXT": (MAIN_WINDOW, "resume_after_maintenance"),
    "DISCARD_TITLE": (MAIN_WINDOW, "read_calibration"),
    "REREAD_TEXT": (MAIN_WINDOW, "read_calibration"),
    "CLOSE_TEXT": (DIALOG, "reject"),
    "ISOLATION_TITLE": (COMM_DIALOG, "submit"),
    "ISOLATION_TEXT": (COMM_DIALOG, "submit"),
    "NOT_READ_TITLE": (MAIN_WINDOW, "write_calibration"),
    "NOT_READ_TEXT": (MAIN_WINDOW, "write_calibration"),
    "INVALID_TITLE": (MAIN_WINDOW, "write_calibration"),
    "INVALID_TEXT": (MAIN_WINDOW, "write_calibration"),
    "RESUME_FAILED_TITLE": (MAIN_WINDOW, "_device_task_finished"),
    "TARGET_TEXT": (COMM_DIALOG, "__init__"),
    "LEVEL_TEXTS": (DIALOG, "update_controls"),
    "LEVEL_HALTED": (DIALOG, "update_controls"),
    "LEVEL_MAINTENANCE": (DIALOG, "update_controls"),
    "LEVEL_ENTERING": (DIALOG, "update_controls"),
    "ADDRESS_TEXT": (DIALOG, "update_controls"),
    "NO_ADDRESS": (DIALOG, "update_controls"),
    "COMMUNICATION_TEXT": (DIALOG, "update_controls"),
    "UNREGISTERED": (DIALOG, "update_controls"),
    "STATE_DIAGNOSTICS": (DIALOG, "update_controls"),
    "STATE_ENTERING": (DIALOG, "update_controls"),
    "STATE_CALIBRATION_WRITE": (DIALOG, "update_controls"),
    "STATE_CALIBRATION_READ": (DIALOG, "update_controls"),
    "STATE_TASK": (DIALOG, "update_controls"),
    "READ_IN_MAINTENANCE": (DIALOG, "update_controls"),
    "READ_ENTERING": (DIALOG, "update_controls"),
    "READ_BUSY": (DIALOG, "update_controls"),
    "READ_UNREGISTERED": (DIALOG, "update_controls"),
    "READ_UNCONFIGURED": (DIALOG, "update_controls"),
    "READ_EXCLUDED": (DIALOG, "update_controls"),
    "NOT_ENTERED": (DIALOG, "task_finished"),
    "READ_FAILED": (DIALOG, "task_finished"),
    "CLOSE_IN_MAINTENANCE": (DIALOG, "update_controls"),
    "CLOSE": (DIALOG, "update_controls"),
    "NOT_IN_MAINTENANCE": (DIALOG, "update_controls"),
    "EXPORT_SNAPSHOT": (DIALOG, "update_controls"),
    "EXPORT_EVENTS": (DIALOG, "update_controls"),
    "EXPORTED_SNAPSHOT": (DIALOG, "export_diagnostics"),
    "EXPORTED_EVENTS": (DIALOG, "export_diagnostics"),
    "EXPORT_FAILED_TITLE": (DIALOG, "export_diagnostics"),
    "EXPORT_FILE_NAME": (DIALOG, "export_diagnostics"),
    "COMMUNICATION_ERRORS": (DIALOG, "<module>"),
    "PAR_ERRORS": (DIALOG, "<module>"),
    "NOT_READ_STAMP": (DIALOG, "display_diagnostics"),
    "LAST_FAILURE": (DIALOG, "display_diagnostics"),
    "NOT_READ_VALUE": (DIALOG, "display_diagnostics"),
    "HISTORICAL": (DIALOG, "display_diagnostics"),
    "STAMP": (DIALOG, "display_diagnostics"),
    "IDENTITY_LINE": (DIALOG, "display_diagnostics"),
    "VALUES_LINE": (DIALOG, "display_diagnostics"),
    "EXPOSURE_LINE": (DIALOG, "display_diagnostics"),
    "DATA_LINE": (DIALOG, "display_diagnostics"),
    "NO_NONZERO": (DIALOG, "filter_errors"),
    "NO_NONZERO_HISTORICAL": (DIALOG, "filter_errors"),
    "NOT_READ_TOOLTIP": (DIALOG, "display_diagnostics"),
    "NO_DELTA_TOOLTIP": (DIALOG, "display_diagnostics"),
    "EXPOSURES": (DIALOG, "display_diagnostics"),
    "EXPOSURE_MODES": (DIALOG, "display_diagnostics"),
    "EVENT_LEVELS": (DIALOG, "display_diagnostics"),
    "EVENT_ACTIONS": (DIALOG, "display_diagnostics"),
    "EVENT_CATEGORIES": (DIALOG, "display_diagnostics"),
    "COMM_PARAMETERS_READ": (DIALOG, "display_diagnostics"),
    "WRITE_OPERATION": (DIALOG, "display_diagnostics"),
    "STATE_NOT_ENTERED": (COMM_DIALOG, "__init__"),
    "STATE_PENDING": (COMM_DIALOG, "update_controls"),
    "STATE_VERIFIED_BLOCKED": (COMM_DIALOG, "_show_verified_state"),
    "STATE_VERIFIED": (COMM_DIALOG, "_show_verified_state"),
    "STATE_MAINTENANCE": (COMM_DIALOG, "mode_changed"),
    "STATE_LEFT": (COMM_DIALOG, "mode_changed"),
    "SUBMIT_TEXTS": (COMM_DIALOG, "submit"),
    "SUBMIT_OTHER": (COMM_DIALOG, "submit"),
    "FINISHED_TEXTS": (COMM_DIALOG, "task_finished"),
    "AUTO_VERIFY": (COMM_DIALOG, "task_finished"),
    "OPERATION_FAILED": (COMM_DIALOG, "task_finished"),
    "IDENTITY_NOT_READ": (COMM_DIALOG, "__init__"),
    "IDENTITY_DEVICE": (COMM_DIALOG, "display_identity"),
    "IDENTITY_SERIAL": (COMM_DIALOG, "display_identity"),
    "IDENTITY_CONNECTION": (COMM_DIALOG, "display_identity"),
    "SERIAL_PORT_LABEL": (MAIN_WINDOW, "refresh_serial_ports"),
    "SERIAL_PORT_UNKNOWN": (MAIN_WINDOW, "refresh_serial_ports"),
    "SERIAL_PORTS_FOUND": (MAIN_WINDOW, "refresh_serial_ports"),
    "SERIAL_PORTS_NONE": (MAIN_WINDOW, "refresh_serial_ports"),
    "SERIAL_PORTS_FAILED": (MAIN_WINDOW, "refresh_ports"),
    "IDENTITY_LABELS": (COMM_DIALOG, "display_identity"),
    "UNREAD": (COMM_DIALOG, "display_identity"),
    "FIXED_PARAMETERS": (COMM_DIALOG, "__init__"),
    "PARITY_LABELS": (COMM_DIALOG, "_fields"),
    "CALIBRATION_NOT_READ": (MAIN_WINDOW, "_reset_calibration"),
    "CALIBRATION_FAILED": (MAIN_WINDOW, "_device_task_finished"),
    "CALIBRATION_UNCONFIRMED": (MAIN_WINDOW, "_device_task_finished"),
    "CALIBRATION_INVALID_STATE": (MAIN_WINDOW, "_task_finished"),
    "CALIBRATION_INVALID_NOTE": (MAIN_WINDOW, "_task_finished"),
    "CALIBRATION_PENDING": (MAIN_WINDOW, "_refresh_calibration_plots"),
    "CALIBRATION_CURRENT": (MAIN_WINDOW, "_refresh_calibration_plots"),
    "CALIBRATION_UNREAD": (MAIN_WINDOW, "_reset_calibration"),
    "CALIBRATION_OUT_OF_ORDER": (MAIN_WINDOW, "_refresh_calibration_plots"),
    "COMM_INVALID": (MAIN_WINDOW, "_accept_settings_comm"),
    "COMM_SOURCE": (MAIN_WINDOW, "_render_comm_values"),
    "COMM_UNREGISTERED": (MAIN_WINDOW, "_render_comm_values"),
    "COMM_MISMATCH": (MAIN_WINDOW, "_render_comm_values"),
    "PARITY_TEXTS": (MAIN_WINDOW, "_render_comm_values"),
    "ACQUISITION_MAINTENANCE": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_ENTERING": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_UNCONFIGURED": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_NONE": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_PARTIAL": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_OK": (MAIN_WINDOW, "_refresh_communication_events"),
    "ACQUISITION_WAITING": (MAIN_WINDOW, "_refresh_communication_events"),
}
"""V1.0.3 file and function of every text above (COMM_STATES: the functions listed in COMM_STATE_SOURCES)."""
COMM_STATE_SOURCES = (
    "_request_settings_comm",
    "_accept_settings_comm",
    "_device_task_finished",
    "_on_bus_state",
    "_populate_active_device",
)
