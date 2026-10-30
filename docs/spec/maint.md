# 设备维护、校准与通信参数（MAINT）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### MAINT-001 维护/诊断事务预算10秒
- 规则：维护、诊断事务的通信预算保持10秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“维护/诊断预算10秒、单帧超时1.5秒、恢复清理独立预算2秒及用户设置的轮询周期不变”
- 状态：待确认
- 现状符合度：符合（诊断读取、校准读写、普通通信参数读取在 PollingCoordinator._process_tasks 中以 _transaction_budget()=DEVICE_TRANSACTION_BUDGET_SECONDS(10.0) 执行；独立通信维护的读取/写入/核对在 CommunicationMaintenance.execute 中以字面量 client.communication_budget(10.0, …) 执行，未引用同一常量，数值一致。代码另把该预算用于 read_identity 等事务，原文未列出身份读取。verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture 断言 _transaction_budget()==DEVICE_TRANSACTION_BUDGET_SECONDS。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py DEVICE_TRANSACTION_BUDGET_SECONDS；par_app/coordinator.py PollingCoordinator._transaction_budget；par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-002 配置不一致时仍不能恢复采集
- 规则：软件配置与通信维护核对结果不一致时，仍不能恢复采集。（裁决 D-131：该设备已停用或已移出登记时放行，不要求其参数一致；它重新启用或重新登记时，仍须先完成核对才能参与采集。）
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“配置不一致时仍不能恢复采集，软件配置不会自动改变”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-131 已裁决：停用或移出登记的设备在恢复检查中放行；该设备重新启用或重新登记时，仍须先完成核对才能参与采集，DEF-16 已修复（PR #32）；D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_verified_device_is_let_through_but_must_verify_when_re_enabled；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_enabled_matching_device_still_waits_for_explicit_resume；tests/qt/test_maintenance_rejoin_requires_verification.py::test_removed_device_registered_again_after_restart_must_verify_first；tests/qt/test_maintenance_rejoin_requires_verification.py::test_verified_device_removed_at_runtime_must_verify_when_registered_again；tests/qt/test_maintenance_rejoin_requires_verification.py::test_restart_after_resume_does_not_stop_but_still_holds_back_the_deferred_device；tests/qt/test_maintenance_rejoin_requires_verification.py::test_rejoin_hint_and_diagnostic_are_written_once；tests/qt/test_maintenance_rejoin_requires_verification.py::test_rejoined_device_rejects_manual_writes_until_verified；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_registered_device_with_pending_write_rejects_calibration_write；tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_device_with_pending_write_still_blocks_resume_and_restart；tests/qt/test_maintenance_rejoin_requires_verification.py::test_device_removed_at_runtime_with_pending_write_still_blocks_resume
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/maintenance.py CommunicationMaintenance.finish_after_resume；par_app/coordinator.py PollingCoordinator._awaiting_verification；par_app/maintenance.py check_manual_task

### MAINT-003 维护写入不自动改软件配置
- 规则：设备通信参数写入及核对不会自动修改软件的总线配置或设备登记，须用户手动更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“配置不一致时仍不能恢复采集，软件配置不会自动改变”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance 只写设备库 app_settings('communication_maintenance') 与 diagnostics，不调用 AppConfigStore.save 或 DeviceHub.apply；verify_maintenance.test_complete_flow_preserves_config。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-004 通信写入失败仍需核对
- 规则：通信参数写入失败时，仍需使用新参数核对。
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“失败仍需核对，配置不一致时仍不能恢复采集，软件配置不会自动改变”
- 状态：待确认
- 现状符合度：符合（按 D-133 裁决选 A，以建立 pending 为界：CommunicationMaintenance.execute 先在内存中设置 self.pending 并 _save(pending)，再写“准备写入”诊断，最后调用 change_mcu_comm；建立 pending 之后的失败（含尚未发出写命令的失败，以及超时、响应丢失）都不清除 pending，check_resume 遇 pending 拒绝恢复，须用新参数核对（verify_maintenance.py MaintenanceTests.test_lost_write_response_requires_verification）；建立 pending 之前的拒绝或失败不产生待核对状态，按裁决不需要核对。）
- 冲突：D-133 已裁决：选 A：已在设备库记下“准备写入”（建立 pending）后的任何失败都须核对，建立 pending 之前的失败不需要核对
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance.py CommunicationMaintenance.check_resume

### MAINT-005 通信写入成功后自动用新参数核对
- 规则：通信参数写入成功后，自动通过既有后台维护队列使用新参数执行核对，并在核对完成后刷新设置页的当前值。
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“通信写入成功后自动通过既有维护队列使用新参数核对，并刷新当前值”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.task_finished 在 maintenance_write 成功且 session.pending 时 queue_task("maintenance_verify")；MainWindow._device_task_finished 对 maintenance_verify 调用 _accept_settings_comm 刷新；verify_maintenance.test_write_automatically_verifies_and_refreshes_settings。）
- 冲突：D-135 已裁决：第300行“不自动重连”只指采集总线，写入成功后自动核对所建的维护连接不算重连；D-136 已裁决：写入成功时按第72、147行自动核对；第300行“直接点击核对”只适用于写入失败或结果未知，不废止
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.task_finished；par_app/ui.py MainWindow._device_task_finished；par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-006 关闭维护弹窗不自动恢复采集
- 规则：关闭维护弹窗不会自动恢复采集，采集保持停止，须显式执行恢复操作。
- 来源：业务规则与变更日志_V1.0.2.md 第 75 行「设置与导出布局（2026-09-20）」“待核对参数、配置不匹配、任务进行中和严重停止仍阻止恢复，关闭弹窗不自动恢复”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.reject/closeEvent 不调用 leave_maintenance；维护中关闭按钮文案“关闭（保持停止）”；verify_maintenance.test_dialog_close_keeps_stopped。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.closeEvent

### MAINT-007 待核对/不匹配/任务中/严重停止阻止恢复
- 规则：存在待核对的参数写入、配置与核对结果不匹配、维护任务进行中或严重硬件停止时，不允许恢复采集。（裁决 D-110：设置页和维护弹窗两处恢复入口统一采用维护弹窗按钮的这一套条件，另含“校准有未处理修改”和校准读取或写入进行中，见 MAINT-067、MAINT-068。）
- 来源：业务规则与变更日志_V1.0.2.md 第 75 行「设置与导出布局（2026-09-20）」“待核对参数、配置不匹配、任务进行中和严重停止仍阻止恢复”
- 状态：待确认
- 现状符合度：符合（按 D-110 裁决，分支 fix/resume-conditions-unified 修复 DEF-12 后，两处入口的可用条件都由 par_app/services/maintenance.py resume_gate 判定：MainWindow._refresh_communication_events（设置页 maintenance_resume_action）与 DeviceMaintenanceDialog.update_controls（弹窗 resume_button）传入同样的事实。只在维护中可恢复，依次检查：严重硬件停止（显示停止原因）；任务进行中（弹窗诊断读取、正在进入维护、通信维护面板读写、校准读取或写入），提示“任务尚未结束，暂不能恢复采集。”；校准有未处理修改，提示“校准修改尚未处理，暂不能恢复采集。”；各维护会话的 CommunicationMaintenance.check_resume（待核对写入、核对后参数不一致），提示其原因。顺序与文字＝V1.0.2 弹窗按钮；设置页按钮的提示和右栏状态文字显示同一原因。执行时 MainWindow.resume_after_maintenance 先刷新条件、按钮不可用即返回；coordinator maintenance_leave 再次校验 halt 与 check_resume（设备侧流程不变）。V1.0.2 原核对：_refresh_communication_events 的 allowed 需 _maintenance 且 halt is None 且各 session.check_resume 通过且弹窗 other_busy() 为假，不检查校准读取或写入进行中（_calibration_busy）和校准未处理修改（_calibration_dirty），与 DeviceMaintenanceDialog.update_controls 的条件和顺序不一致（DEF-12）。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”），DEF-12 已修复（PR #42）
- 验证：tests/unit/test_services_maintenance.py::test_allowed_only_in_maintenance_with_nothing_blocking；tests/unit/test_services_maintenance.py::test_a_running_task_refuses_with_the_window_wording；tests/unit/test_services_maintenance.py::test_severe_stop_refuses_with_its_own_message；tests/unit/test_services_maintenance.py::test_first_condition_in_window_order_wins；tests/unit/test_services_maintenance.py::test_first_failing_session_gives_the_reason_and_later_sessions_are_not_checked；tests/unit/test_services_maintenance.py::test_protocol_error_subclasses_refuse_and_other_errors_propagate；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_a_calibration_task_runs；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_both_entries_agree_on_every_condition
- 代码锚点：par_app/services/maintenance.py resume_gate；par_app/ui.py MainWindow._refresh_communication_events；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls；par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-008 维护模式暂停不受失败停止开关影响
- 规则：进入维护模式后的采集暂停及其恢复条件，不随任何设备“失败停止”开关是否勾选而变化。
- 来源：业务规则与变更日志_V1.0.2.md 第 117 行「失败停止开关（2026-09-30）」“维护模式暂停、硬件异常锁存均不随本开关变化”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks 的 maintenance_enter/maintenance_leave 分支与 run 循环不读取 auto_stop_on_failure。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator.run

### MAINT-009 软件事件在数据库中按ID倒序读取
- 规则：软件事件从设备库 diagnostics 按 ID 倒序读取。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“刷新后回到最新入库事件，数据库仍按ID倒序且不改写日志”
- 状态：待确认
- 现状符合度：符合（par_app/database.py ParDatabase.recent_diagnostics 使用 SELECT … ORDER BY id DESC LIMIT ? 读取。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.recent_diagnostics

### MAINT-010 中文显示不改原始日志与计数增量规则
- 规则：事件类别中文化只作用于显示，数据库原始日志内容、类别字段以及错误计数增量规则保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 129 行「统一设备维护（2026-09-18，当前布局）」“原始日志内容、类别及计数增量规则保留，窄窗口继续滚动查看”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics 只生成显示文本；par_app/database.py ParDatabase.recent_diagnostics 只读。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/database.py ParDatabase.recent_diagnostics

### MAINT-011 校准管理迁入设备维护弹窗
- 规则：原独立的P4校准管理页取消，光谱校准功能迁入设备维护弹窗。
- 来源：业务规则与变更日志_V1.0.2.md 第 131 行「统一设备维护（2026-09-18，当前布局）」“原P4校准管理迁入设备维护弹窗，入口位于设置与导出页左下方”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__ 将 owner.calibration_page 作为“光谱校准”页签；主导航无校准页。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__；par_app/ui.py MainWindow._build_calibration

### MAINT-012 维护目标独立选择不影响主界面与采集范围
- 规则：在维护窗口中切换维护设备后，不改变主界面当前查看对象，也不改变采集范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 132 行「统一设备维护（2026-09-18，当前布局）」“随后独立选择，不改变主界面查看对象或采集范围”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device 只改 self.key，不调用 hub.set_active 或 apply。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device

### MAINT-013 维护设备默认当前查看设备
- 规则：打开维护窗口时，维护目标默认取主界面当前查看的设备（存在待核对写入时除外，见第133行）。
- 来源：业务规则与变更日志_V1.0.2.md 第 132 行「统一设备维护（2026-09-18，当前布局）」“可切换光谱校准和通信参数页。维护设备默认当前查看设备”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare 在未锁定时 self.key = hub.active_key。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare

### MAINT-014 设备维护打开统一窗口并默认状态诊断页
- 规则：点击“设备维护”按钮进入统一维护窗口，默认显示“状态与诊断”页，可切换到“光谱校准”和“通信参数”页。
- 来源：业务规则与变更日志_V1.0.2.md 第 132 行「统一设备维护（2026-09-18，当前布局）」“「设备维护」按钮进入统一维护窗口，默认显示状态与诊断页，可切换光谱校准和通信参数页”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow.open_device_maintenance(page=0)；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__ 建三个页签。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.open_device_maintenance；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare

### MAINT-015 任务进行、校准未提交或写入待核对时锁定维护设备
- 规则：读取/写入过程中、校准存在未提交修改，或通信写入处于待核对状态时，维护窗口锁定维护设备选择，不能切换。
- 来源：业务规则与变更日志_V1.0.2.md 第 133 行「统一设备维护（2026-09-18，当前布局）」“读取/写入过程中、校准存在未提交修改或通信写入待核对时锁定设备”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.locked 覆盖 busy/entering/通信忙/校准忙/校准脏/任一会话 pending；change_device 在锁定时回退选择。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.locked；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device

### MAINT-016 关闭不清除通信写入待核对状态
- 规则：关闭维护窗口不会清除通信写入的待核对状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 133 行「统一设备维护（2026-09-18，当前布局）」“通信写入待核对状态不会因关闭而清除，重新打开优先定位待核对设备”
- 状态：待确认
- 现状符合度：符合（待核对状态由 par_app/maintenance.py CommunicationMaintenance._save 持久化在设备库 app_settings，关闭窗口不调用 finish。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance._save；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject

### MAINT-017 关闭前须确认放弃校准修改
- 规则：存在未写入的校准修改时关闭维护窗口，须先弹窗确认放弃；用户拒绝则不关闭。
- 来源：业务规则与变更日志_V1.0.2.md 第 133 行「统一设备维护（2026-09-18，当前布局）」“关闭前须确认放弃校准修改；通信写入待核对状态不会因关闭而清除”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject 在 _calibration_dirty 时询问，确认后 discard_calibration。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；par_app/ui.py MainWindow.discard_calibration

### MAINT-018 重新打开优先定位待核对设备
- 规则：重新打开维护窗口时，若存在写入待核对的设备，维护目标优先定位到该设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 133 行「统一设备维护（2026-09-18，当前布局）」“通信写入待核对状态不会因关闭而清除，重新打开优先定位待核对设备”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare 先按 pending 会话路径设定 key，锁定时不再覆盖为 active_key。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare

### MAINT-019 （设备协议细节，公开版略）
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 134 行「统一设备维护（2026-09-18，当前布局）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py PAR_ERRORS

### MAINT-020 状态与诊断页显示内容
- 规则：状态与诊断页显示：硬件身份、MCU温度、曝光模式/时间、初始化状态、数据有效状态，以及8项通信错误计数和14项PAR错误计数。
- 来源：业务规则与变更日志_V1.0.2.md 第 134 行「统一设备维护（2026-09-18，当前布局）」“状态与诊断显示硬件身份、MCU温度、曝光模式/时间、初始化和数据有效状态，以及8项通信错误计数和14项PAR错误计数”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/device_maintenance_dialog.py COMMUNICATION_ERRORS 8 项、PAR_ERRORS 14 项。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/device_maintenance_dialog.py COMMUNICATION_ERRORS；par_app/device_maintenance_dialog.py PAR_ERRORS

### MAINT-021 （设备协议细节，公开版略）
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 134 行「统一设备维护（2026-09-18，当前布局）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_diagnostics；par_app/protocol.py ParModbusClient._read_input

### MAINT-022 诊断快照与失败记录写入所选设备库
- 规则：诊断读取成功的快照和失败记录都保存到所选维护设备的数据库 diagnostics 表。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“诊断成功快照和失败记录保存在所选设备库的diagnostics”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks diagnostics_read 成功写 INFO（含数据），异常分支写 ERROR，均为 state.database。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/database.py ParDatabase.diagnostic

### MAINT-023 诊断读取不写云标记
- 规则：诊断读取不写入任何云端标记。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“不另开串口、不写云标记、不自动高频轮询。”
- 状态：待确认
- 现状符合度：符合（par_app 中检索 cloud/云 无云端写入相关代码。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：代码中不存在云标记写入逻辑，属否定性约束

### MAINT-024 诊断读取经原后台单线程队列执行
- 规则：诊断读取通过原后台单线程任务队列执行。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“通过原后台单线程队列和10秒预算执行，不另开串口”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.refresh_diagnostics 调用 coordinator.queue_task("diagnostics_read")；PollingCoordinator._process_tasks 在采集线程中逐个处理队列任务；verify_maintenance.py MaintenanceTests.test_diagnostics_uses_queue_and_respects_maintenance。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.refresh_diagnostics；par_app/coordinator.py PollingCoordinator.queue_task；par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-025 进入诊断页读取一次
- 规则：进入诊断页时读取一次诊断。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“进入诊断页读取一次，后续可手动刷新；通过原后台单线程队列和10秒预算执行”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.page_changed(0) 调用 refresh_diagnostics；prepare 打开窗口时经 QTimer 调 page_changed。另：停留在诊断页时切换维护设备，change_device 也调用 page_changed 再读一次，原文未提及该情形；刷新按钮不可用（停用、已退出、维护中、严重停止）时 refresh_diagnostics 只显示已有内容，不读硬件。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.page_changed；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.refresh_diagnostics

### MAINT-026 可查看最近100条软件事件
- 规则：诊断页可查看该设备库最近100条软件事件。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“可筛选非零项、查看最近100条软件事件和导出包含设备来源的JSON诊断”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics 调用 recent_diagnostics(100)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/database.py ParDatabase.recent_diagnostics

### MAINT-027 导出包含设备来源的JSON诊断
- 规则：可导出包含设备来源的JSON诊断。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“可筛选非零项、查看最近100条软件事件和导出包含设备来源的JSON诊断”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.export_diagnostics 以 device_name、slave_id、database（库路径）表示设备来源，另含 report_kind、snapshot、last_read_error、runtime、software_events；这三个来源字段是实现选择，原文只要求包含设备来源。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.export_diagnostics

### MAINT-028 本次新增基于同库同会话上次成功读取
- 规则：“较上次读取新增”以同一设备库在当前窗口会话内上次成功读取的计数为基准计算。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“本次新增基于同库在当前窗口会话的上次成功读取”
- 状态：待确认
- 现状符合度：不符合（按 D-134 裁决需修改，待修复。按裁决，每次打开维护窗口须清空“本次新增”的比较基准；现状 snapshots 只在 DeviceMaintenanceDialog.__init__ 中创建，MainWindow.open_device_maintenance 复用同一窗口对象，关窗重开不清空。原核对（未验证）：DeviceMaintenanceDialog.task_finished 以 self.snapshots[库路径] 为基准计算增量；snapshots 只在 DeviceMaintenanceDialog.__init__ 中创建，MainWindow.open_device_maintenance 复用同一个窗口对象，关闭后重新打开不清空快照，基准实际是软件运行期间的上次成功读取。“当前窗口会话”指一次打开期间还是窗口对象的整个生命周期，未确认。）
- 冲突：D-134 已裁决：选 A：每次打开维护窗口重新计算“本次新增”，关窗重开清空比较基准，待修复（DEF-17）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__；par_app/ui.py MainWindow.open_device_maintenance

### MAINT-029 硬件累计次数与当前故障分开显示
- 规则：诊断页把硬件错误累计次数（计数表）与当前故障状态（初始化、需重新上电等）分开显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“硬件累计次数与当前故障分开显示，本次新增基于同库在当前窗口会话的上次成功读取”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics：状态行显示初始化/上电，计数表单独显示累计次数。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### MAINT-030 诊断失败保留上次成功值并标记历史
- 规则：诊断读取失败时保留上次成功读取的值，并标记为历史值。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“首次读取、计数下降或饱和显示「—」；失败保留上次成功值并标记历史值”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 失败不覆盖 snapshots；display_diagnostics 加“历史值 · ”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### MAINT-031 首次、计数下降或饱和时增量显示“—”
- 规则：首次读取、计数比上次下降，或计数达到饱和值时，新增列显示“—”，不计算增量。
- 来源：业务规则与变更日志_V1.0.2.md 第 136 行「统一设备维护（2026-09-18，当前布局）」“首次读取、计数下降或饱和显示「—」；失败保留上次成功值并标记历史值”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 中 old is None、value < old 或 value == 65535 时 delta=None。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished

### MAINT-032 其他设备回包不覆盖当前校准目标
- 规则：校准读写的回包若来自非当前维护目标的设备，不覆盖当前维护目标的校准显示与状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“支持放弃待写入修改，其他设备回包不覆盖当前维护目标”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._device_task_finished 中 calibration 类回包 key != _calibration_key() 时直接返回。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_task_finished；par_app/ui.py MainWindow._calibration_key

### MAINT-033 支持放弃待写入的校准修改
- 规则：用户可放弃尚未写入的校准修改，界面恢复为上次硬件回读值。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“支持放弃待写入修改，其他设备回包不覆盖当前维护目标”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow.discard_calibration 以 _calibration_baseline 恢复。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.discard_calibration

### MAINT-034 校准写入前确认设备名称、地址及参数
- 规则：写入校准前须确认设备名称、地址及参数。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“写入前确认设备名称、地址及参数，写入后回读”
- 状态：待确认
- 现状符合度：符合（MainWindow.write_calibration 弹出“确认校准写入”，显示设备名、地址及逐项参数，用户不选“是”则不写入；参数以“旧值 → 新值”形式列出，是实现采用的展示方式，原文未规定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.write_calibration；par_app/services/calibration.py is_writable；par_app/services/calibration.py change_lines

### MAINT-035 校准写入后回读
- 规则：校准写入后回读。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“写入前确认设备名称、地址及参数，写入后回读”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 的 calibration_write 分支在同一事务内写入后调用 read_calibration 回读，回读值写入审计并返回界面，MainWindow._task_finished 经 _apply_hardware_calibration 显示回读值；回读时机与界面更新方式为实现细节。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-036 校准审计写入目标设备库
- 规则：校准读取与写入的审计记录写入维护目标设备自己的数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“写入后回读，审计仍写目标设备库。支持放弃待写入修改”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks 以 state.database.save_calibration 记录 read/write。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/database.py ParDatabase.save_calibration

### MAINT-037 校准有效读取后才允许编辑
- 规则：光谱校准参数仅在对当前维护设备有效读取后才允许编辑和写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 137 行「统一设备维护（2026-09-18，当前布局）」“有效读取后允许编辑；写入前确认设备名称、地址及参数”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._update_calibration_controls editable 要求 _calibration_device_key == 当前目标；_task_finished 仅在回读有效时设置该 key。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_calibration_controls；par_app/ui.py MainWindow._task_finished

### MAINT-038 拖拽保留未改变节点的原始修正值
- 规则：在图上拖拽节点时，未被改变的节点保留原始修正值（包括限幅前的值），不以图上限幅后的值覆盖。
- 来源：业务规则与变更日志_V1.0.2.md 第 138 行「统一设备维护（2026-09-18，当前布局）」“拖拽保留未改变节点的原始修正值（包括限幅前值）”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._calibration_nodes_changed 仅当节点纵坐标与原限幅显示值不同时才改写 y。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py node_values；par_app/ui.py MainWindow._calibration_nodes_changed

### MAINT-039 校准原值独立保存不随显示舍入
- 规则：硬件回读值与待写入值保存在独立的原值字典中；用户未编辑的字段写入时使用原值，不受界面显示舍入影响。
- 来源：业务规则与变更日志_V1.0.2.md 第 138 行「统一设备维护（2026-09-18，当前布局）」“使用独立原值字典保存硬件回读及待写入值，未编辑字段不随显示舍入”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._apply_hardware_calibration 写 _calibration_values；_calibration_dict 返回原值；仅 _calibration_field_changed 改动被编辑字段。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._apply_hardware_calibration；par_app/services/calibration.py parse_readback；par_app/ui.py MainWindow._calibration_dict；par_app/ui.py MainWindow._calibration_field_changed

### MAINT-040 百分比仅在编辑时换算回协议比例
- 规则：节点修正与上下限以百分比显示，只有用户编辑该字段时才把百分比换算回原协议比例值。
- 来源：业务规则与变更日志_V1.0.2.md 第 138 行「统一设备维护（2026-09-18，当前布局）」“未编辑字段不随显示舍入，百分比仅编辑时转换回原协议比例”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._calibration_field_changed：_calibration_values[name] = value / scale。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._calibration_field_changed

### MAINT-041 校准状态仅状态1显示已校准
- 规则：校准状态仅在状态码为1时显示“已校准”；未知状态保留数值显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“仅状态1显示「已校准」、错误0显示「无错误」；未知状态和非零错误保留数值，悬停可查看原始码”
- 状态：待确认
- 现状符合度：符合（MainWindow._task_finished：status_code == 1 显示“校准状态：已校准”，缺失显示“校准状态：未读取”，其他值显示“校准状态码：N”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py status_texts；par_app/ui.py MainWindow._task_finished

### MAINT-042 缺失校准信息不沿用上次状态
- 规则：校准信息缺失时不沿用上次状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“悬停可查看原始码。缺失信息不沿用上次状态或伪造版本”
- 状态：待确认
- 现状符合度：不符合（按 D-157 裁决需修改，待修复。按裁决，整次校准读取失败时须保留上次值并标明“历史值（本次读取失败）”；现状保留上次值但不加标识。原核对（未验证）：成功回包缺字段时，MainWindow._task_finished 把状态/错误显示为“未读取”，版本/节点数显示“—”，时间经 _format_mcu_timestamp 显示“未设置 / 无效时间戳”，都不沿用上次值。校准读取失败（ok=False）时，MainWindow._device_task_finished 只显示“回读未确认”和失败提示，_task_finished 不更新状态、错误、版本、时间标签，界面仍显示上次成功读取的内容；这是否属于“沿用上次状态”未确认。）
- 冲突：D-157 已裁决：整次校准读取失败也属“缺失信息”，界面保留上次值并标明“历史值（本次读取失败）”，待修复（DEF-23）
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py status_texts；par_app/services/calibration.py format_mcu_timestamp；par_app/ui.py MainWindow._task_finished；par_app/ui.py MainWindow._device_task_finished；par_app/ui.py MainWindow._reset_calibration

### MAINT-043 仅打开维护窗口不暂停采集
- 规则：只打开维护窗口（未进入通信维护）时，后台采集继续，不暂停。
- 来源：业务规则与变更日志_V1.0.2.md 第 144 行「统一设备维护（2026-09-18，当前布局）」“仅打开维护窗口不暂停采集；诊断和校准遵循既有串行事务调度”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow.open_device_maintenance 与 par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare 不调用 enter_maintenance/pause_polling。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.open_device_maintenance；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.prepare

### MAINT-044 诊断和校准遵循串行事务调度
- 规则：诊断与校准读写作为任务进入既有后台串行事务队列，与采集串行执行，不并发访问总线。
- 来源：业务规则与变更日志_V1.0.2.md 第 144 行「统一设备维护（2026-09-18，当前布局）」“仅打开维护窗口不暂停采集；诊断和校准遵循既有串行事务调度”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks 在采集线程内串行处理 diagnostics_read/calibration_read/calibration_write。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator.queue_task

### MAINT-045 进入通信维护须明确确认停止全部采集
- 规则：通信参数页须用户点击“停止全部采集并进入通信维护”并在确认框中确认后，才停止全部采集并进入通信维护；拒绝则不进入。
- 来源：业务规则与变更日志_V1.0.2.md 第 144 行「统一设备维护（2026-09-18，当前布局）」“通信页须明确确认「停止全部采集并进入通信维护」”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.enter_communication 弹 QMessageBox 确认后调用 coordinator.enter_maintenance。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.enter_communication；par_app/coordinator.py PollingCoordinator.enter_maintenance

### MAINT-046 通信参数写入动态生效无需重新上电
- 规则：通信参数写入后动态生效，核对与恢复无需断电或重新上电确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 144 行「统一设备维护（2026-09-18，当前布局）」“通信参数动态生效，无需断电或重新上电确认”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.submit 写入确认文案“动态生效，无需重新上电”；写后直接排队 maintenance_verify。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.submit；par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-047 通信维护按隔离、读取、写入、核对流程
- 规则：进入通信维护后按顺序操作：确认已隔离目标设备、读取目标设备、写入新参数、使用新参数核对；缺少前一步时后续操作被拒绝。
- 来源：业务规则与变更日志_V1.0.2.md 第 144 行「统一设备维护（2026-09-18，当前布局）」“之后按隔离目标、读取、写入、使用新参数核对的流程操作”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.submit 要求勾选隔离；par_app/maintenance.py CommunicationMaintenance.execute 要求写入前有 baseline、核对前有 pending。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.submit；par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-048 左栏为读取所用连接值不冒充硬件回读
- 规则：通信页左栏“读取连接参数”明确是本次读取所用的连接值，不得显示为硬件回读值；右栏为“准备写入的新参数”。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“左栏明确是读取所用连接值，不冒充硬件回读”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.__init__ 两栏标题为“读取连接参数”“准备写入的新参数”，左栏值来自用户输入/登记值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.__init__；par_app/maintenance_dialog.py MaintenanceDialog._fields

### MAINT-049 删除通信详情按钮及JSON弹窗
- 规则：通信页删除“详情”按钮及JSON弹窗。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“删除通信「详情」按钮及JSON弹窗，保留可选中复制的身份摘要、完整失败提示及后台日志”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.__init__ 只建读取、写入、新参数核对等按钮，par_app/maintenance_dialog.py 中没有“详情”按钮或JSON弹窗。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.__init__

### MAINT-050 串口支持手输且枚举异常不自动切换
- 规则：电脑串口支持手动输入；端口消失、无可用端口或枚举失败时均保留当前输入，不自动切换到其他端口。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“支持手动输入；端口消失、无可用端口或枚举失败均保留当前输入，不自动切换”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py SerialPortComboBox.refresh_ports 先保存 port_name，重建后 setEditText(selected)；OSError 时直接返回不改输入。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.refresh_ports

### MAINT-051 串口枚举不打开串口
- 规则：枚举系统串口时不打开任何串口。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“枚举不打开串口；未进入维护、任务忙或写入待核对时继续锁定”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py SerialPortComboBox.refresh_ports 仅调用 serial.tools.list_ports.comports()。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.refresh_ports

### MAINT-052 未进入维护、任务忙或待核对时锁定串口
- 规则：未进入通信维护、维护任务进行中或存在写入待核对时，电脑串口选择保持锁定。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“未进入维护、任务忙或写入待核对时继续锁定”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.update_controls：port 仅在 ready(维护中、无停止、不忙) 且无 pending 时启用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-053 电脑串口使用可编辑下拉框
- 规则：通信页电脑串口使用可编辑下拉框。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“电脑串口使用可编辑下拉框，页面显示及展开列表时枚举系统串口，列表显示端口号和设备描述，通信只提交端口号”
- 状态：待确认
- 现状符合度：符合（SerialPortComboBox.__init__ 调用 setEditable(True)；MaintenanceDialog.__init__ 以 SerialPortComboBox 作为电脑串口控件。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.__init__；par_app/maintenance_dialog.py MaintenanceDialog.__init__

### MAINT-054 待核对会话从保存的old/new参数恢复
- 规则：待核对会话打开时，通信页两栏从该次写入保存的 old/new 连接参数恢复，不以登记默认值冒充。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“待核对会话两栏从该次保存的old/new连接参数恢复，不以登记默认值冒充”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.update_controls 在 pending 时用 pending["old"]/["new"] 回填两栏与串口。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-055 未进入通信维护时显示主界面实际采集状态
- 规则：通信页在未进入通信维护时显示主界面的实际采集状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“未进入通信维护时显示主界面实际采集状态；维护进度和操作结果集中在状态区”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 在非维护、非停止时 set_state("未进入通信维护；"+主界面采集状态)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls；par_app/maintenance_dialog.py MaintenanceDialog.set_state

### MAINT-056 维护失败红色显示且不被待核对提示覆盖
- 规则：维护进度和操作结果集中显示在通信页状态区；操作失败时以红色显示，且不被随后的待核对提示覆盖。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“维护进度和操作结果集中在状态区，失败为红色且不被待核对提示覆盖”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.task_finished 失败时 set_state(attention=True) 并置 _operation_result=True，update_controls 在 _operation_result 为真时不再写待核对提示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.task_finished；par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-057 通信写入与核对须身份一致
- 规则：写入前设备身份须与此前读取一致，核对时新参数下的设备身份须与写入时一致，否则拒绝写入或核对失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“写后自动核对、待核对锁定、身份校验、关闭保持停止与明确恢复的事务逻辑不变”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance.py CommunicationMaintenance.execute 比较 identity 与 baseline/pending；测试 verify_maintenance.py test_identity_change_and_invalid_address_never_write。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-058 通信写入后自动使用新参数核对
- 规则：通信参数写入成功后，自动排队使用新参数核对，期间采集保持停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“写后自动核对、待核对锁定、身份校验、关闭保持停止与明确恢复的事务逻辑不变”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.task_finished 在 maintenance_write 成功且有 pending 时 queue_task("maintenance_verify")；测试 verify_maintenance.py test_write_automatically_verifies_and_refreshes_settings。）
- 冲突：D-135 已裁决：第300行“不自动重连”只指采集总线，写入成功后自动核对所建的维护连接不算重连；D-136 已裁决：写入成功时按第72、147行自动核对；第300行“直接点击核对”只适用于写入失败或结果未知，不废止
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-059 通信页状态区硬件停止优先
- 规则：通信页状态区存在硬件停止时，优先显示硬件停止信息。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“失败为红色且不被待核对提示覆盖，硬件停止优先”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.update_controls 末尾 halt_reason 存在时覆盖为停止消息；halted 槽同样处理。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.update_controls；par_app/maintenance_dialog.py MaintenanceDialog.halted

### MAINT-060 核对成功后始终说明仍保持停止不自动恢复
- 规则：核对成功的提示始终说明当前仍保持停止，软件不自动恢复采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 148 行「统一设备维护（2026-09-18，当前布局）」“条件满足才提示可明确恢复采集，始终说明当前仍保持停止，不自动恢复”
- 状态：待确认
- 现状符合度：未验证（不自动恢复符合（par_app/maintenance_dialog.py MaintenanceDialog._show_verified_state 不调用 leave_maintenance）；但存在阻止原因时文案为“设备身份和新参数核对通过，但暂不能恢复采集：…”，未出现“仍保持停止”字样，是否满足“始终说明”需人工判断。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog._show_verified_state

### MAINT-061 核对成功提示复用恢复检查
- 规则：新参数核对成功后，复用现有恢复检查：配置未匹配或存在其他阻止条件时显示原因；条件全部满足才提示可明确恢复采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 148 行「统一设备维护（2026-09-18，当前布局）」“核对成功提示复用现有恢复检查：配置未匹配或存在其他阻止条件时显示原因，条件满足才提示可明确恢复采集”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog._show_verified_state 调 CommunicationMaintenance.check_resume 并合并维护窗口 resume_reason。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog._show_verified_state；par_app/maintenance.py CommunicationMaintenance.check_resume

### MAINT-062 进入维护后隐藏进入按钮退出后恢复
- 规则：进入通信维护后隐藏页顶部“停止全部采集并进入通信维护”按钮，不在页内重复显示“通信维护中”；维护状态由窗口顶栏显示；退出维护后恢复该按钮。
- 来源：业务规则与变更日志_V1.0.2.md 第 148 行「统一设备维护（2026-09-18，当前布局）」“进入维护后隐藏顶部停止按钮，不再增加页内「通信维护中」重复状态”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 中 enter_button.setVisible(not coordinator._maintenance)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-063 重新打开已核对会话按当前条件显示
- 规则：重新打开已核对通过但未恢复的会话时，提示按当前恢复条件重新判定显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 148 行「统一设备维护（2026-09-18，当前布局）」“不自动恢复。重新打开已核对会话也按当前条件显示”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.__init__ 以 session.verified 设定 _verification_passed，update_controls 调 _show_verified_state 实时检查。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.__init__；par_app/maintenance_dialog.py MaintenanceDialog._show_verified_state

### MAINT-064 身份摘要转义显示且复制与确认保留原文
- 规则：通信页身份摘要中的特殊字符在显示时转义；复制和写入确认框使用原始纯文本。
- 来源：业务规则与变更日志_V1.0.2.md 第 149 行「统一设备维护（2026-09-18，当前布局）」“特殊字符转义且复制、写入确认保留原始纯文本”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.display_identity 用 html.escape 生成富文本并另存 _identity_text 原文；submit 确认框使用 _identity_text。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.display_identity；par_app/maintenance_dialog.py MaintenanceDialog.submit

### MAINT-065 严重异常仍须重新上电并重启软件
- 规则：严重硬件异常停止不能通过退出维护解除，仍须为异常探头重新上电并重启软件。
- 来源：业务规则与变更日志_V1.0.2.md 第 151 行「统一设备维护（2026-09-18，当前布局）」“严重异常仍须按既有要求重新上电并重启软件”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks maintenance_leave 在 halt_reason 时报“硬件异常停止仍有效，请重新上电并重启软件”。）
- 冲突：无（V1.0.3）；alpha 档位 1（D-212 问题 8、D-215 问题 5）：“重新上电并重启软件”在 alpha 中对应重新上电后“停止采集→开始采集”（新协调器，等同重启 V1.0.3）
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-066 关闭维护窗口不恢复已暂停的采集
- 规则：关闭维护窗口不会恢复已因通信维护暂停的采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 151 行「统一设备维护（2026-09-18，当前布局）」“关闭窗口不会恢复已暂停的采集；须使用设置与导出页右上方的「退出维护并恢复采集」按钮”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject 不调用 leave_maintenance，关闭按钮显示“关闭（保持停止）”；测试 verify_maintenance.py test_dialog_close_keeps_stopped。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-067 待核对、参数不匹配、任务中或严重停止时禁止恢复
- 规则：存在待核对写入、核对后软件连接参数不匹配、维护操作进行中或严重硬件停止时，禁止恢复采集。（裁决 D-110：设置页和维护弹窗两处恢复入口统一采用维护弹窗按钮的这一套条件，另含“校准有未处理修改”和校准读取或写入进行中，见 MAINT-068。）
- 来源：业务规则与变更日志_V1.0.2.md 第 151 行「统一设备维护（2026-09-18，当前布局）」“待核对写入、核对后软件参数不匹配、操作进行中或严重硬件停止时禁止恢复”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks maintenance_leave 检查 halt_reason 与 check_resume；par_app/maintenance.py CommunicationMaintenance.check_resume 拒绝 pending 与参数不匹配。按 D-110 裁决，分支 fix/resume-conditions-unified 修复 DEF-12 后，两处入口的可用条件都由 par_app/services/maintenance.py resume_gate 判定：MainWindow._refresh_communication_events（设置页 maintenance_resume_action）与 DeviceMaintenanceDialog.update_controls（弹窗 resume_button）传入同样的事实。只在维护中可恢复，依次检查：严重硬件停止（显示停止原因）；任务进行中（弹窗诊断读取、正在进入维护、通信维护面板读写、校准读取或写入），提示“任务尚未结束，暂不能恢复采集。”；校准有未处理修改，提示“校准修改尚未处理，暂不能恢复采集。”；各维护会话的 CommunicationMaintenance.check_resume（待核对写入、核对后参数不一致），提示其原因。顺序与文字＝V1.0.2 弹窗按钮；设置页按钮的提示和右栏状态文字显示同一原因。V1.0.2 原核对：par_app/ui.py MainWindow._refresh_communication_events 只在维护弹窗 other_busy 时禁用设置页恢复，不检查校准任务和校准未处理修改。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”），DEF-12 已修复（PR #42）
- 验证：tests/unit/test_services_maintenance.py::test_allowed_only_in_maintenance_with_nothing_blocking；tests/unit/test_services_maintenance.py::test_a_running_task_refuses_with_the_window_wording；tests/unit/test_services_maintenance.py::test_severe_stop_refuses_with_its_own_message；tests/unit/test_services_maintenance.py::test_first_condition_in_window_order_wins；tests/unit/test_services_maintenance.py::test_first_failing_session_gives_the_reason_and_later_sessions_are_not_checked；tests/unit/test_services_maintenance.py::test_protocol_error_subclasses_refuse_and_other_errors_propagate；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_a_calibration_task_runs；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_both_entries_agree_on_every_condition
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/services/maintenance.py resume_gate；par_app/ui.py MainWindow._refresh_communication_events；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-068 经设置页右上方按钮明确恢复采集
- 规则：恢复采集须使用“设置与导出”页右上方的“退出维护并恢复采集”按钮，经确认后执行。（裁决 D-110：设置页右上方“退出维护并恢复采集”按钮和维护弹窗内“退出通信维护并恢复采集”按钮两处入口都保留；两处的禁止条件统一采用弹窗按钮那一套，含“校准有未处理修改”，见 MAINT-067。）
- 来源：业务规则与变更日志_V1.0.2.md 第 151 行「统一设备维护（2026-09-18，当前布局）」“须使用设置与导出页右上方的「退出维护并恢复采集」按钮”
- 状态：待确认
- 现状符合度：符合（按 D-110 裁决。分支 fix/resume-conditions-unified 修复 DEF-12 后，两处入口的可用条件都由 par_app/services/maintenance.py resume_gate 判定：MainWindow._refresh_communication_events（设置页 maintenance_resume_action）与 DeviceMaintenanceDialog.update_controls（弹窗 resume_button）传入同样的事实。只在维护中可恢复，依次检查：严重硬件停止（显示停止原因）；任务进行中（弹窗诊断读取、正在进入维护、通信维护面板读写、校准读取或写入），提示“任务尚未结束，暂不能恢复采集。”；校准有未处理修改，提示“校准修改尚未处理，暂不能恢复采集。”；各维护会话的 CommunicationMaintenance.check_resume（待核对写入、核对后参数不一致），提示其原因。顺序与文字＝V1.0.2 弹窗按钮；设置页按钮的提示和右栏状态文字显示同一原因。两处按钮都经 MainWindow.resume_after_maintenance：先刷新条件、按钮不可用即返回，确认后才调用 PollingCoordinator.leave_maintenance，软件不自动恢复；校准面板改动 _calibration_dirty 或 _calibration_busy 后只刷新弹窗按钮（_maintenance_window.update_controls），设置页按钮的可用状态在下一次 _refresh_communication_events（弹窗关闭后或 3 秒定时刷新）时才更新，执行时由 resume_after_maintenance 再次判定，不会按过期状态恢复；设备侧流程（maintenance_leave 的严重停止与 check_resume 检查、顺序）不变。V1.0.2 原核对：两处入口都在，都调用 resume_after_maintenance；设置页入口不检查校准未处理修改和校准读取或写入进行中，可绕过弹窗的检查恢复采集（现有界面中维护弹窗以模态打开、关闭时须放弃未写入修改，这一缺口在常规操作下不易触发；修复不依赖这一点）。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”），DEF-12 已修复（PR #42）
- 验证：tests/unit/test_services_maintenance.py::test_allowed_only_in_maintenance_with_nothing_blocking；tests/unit/test_services_maintenance.py::test_not_in_maintenance_is_refused_without_a_reason_and_checks_nothing；tests/unit/test_services_maintenance.py::test_unhandled_calibration_changes_refuse_with_the_window_wording；tests/unit/test_services_maintenance.py::test_a_running_task_refuses_with_the_window_wording；tests/unit/test_services_maintenance.py::test_first_condition_in_window_order_wins；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_calibration_changes_are_unhandled；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_a_calibration_task_runs；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_both_entries_agree_on_every_condition
- 代码锚点：par_app/ui.py MainWindow.resume_after_maintenance；par_app/ui.py MainWindow._build_settings；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.resume_acquisition；par_app/services/maintenance.py resume_gate；par_app/ui.py MainWindow._refresh_communication_events；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-069 严重异常锁存后不执行硬件任务
- 规则：严重硬件异常锁存后，维护窗口不再执行任何硬件读取或写入任务。
- 来源：业务规则与变更日志_V1.0.2.md 第 152 行「统一设备维护（2026-09-18，当前布局）」“但不执行诊断硬件读取；严重异常锁存后同样不执行硬件任务”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._process_tasks 在 _halt_reason 时拒绝普通任务和维护任务；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 禁用刷新。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-070 停用或已退出设备只看事件不读硬件
- 规则：停用或已退出本次采集的设备可在维护窗口查看已有软件事件，但不执行诊断硬件读取。
- 来源：业务规则与变更日志_V1.0.2.md 第 152 行「统一设备维护（2026-09-18，当前布局）」“停用/已退出设备可查看已有软件事件，但不执行诊断硬件读取”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 中 available 要求 enabled 且非 excluded，否则禁用刷新；par_app/coordinator.py PollingCoordinator._process_tasks 对 excluded/停用设备拒绝 diagnostics_read。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls；par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-071 未登记设备不列入维护设备
- 规则：维护窗口的设备列表只列已登记设备，未登记设备不列入。
- 来源：业务规则与变更日志_V1.0.2.md 第 152 行「统一设备维护（2026-09-18，当前布局）」“未登记设备不列入；停用/已退出设备可查看已有软件事件”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.rebuild_devices 仅遍历 hub.keys()。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.rebuild_devices

### MAINT-072 2026-09-18实机测试的释放确认与授权范围
- 规则：（单次测试事实，归测试/验收流程）2026-09-18 设备维护实机测试前，用户确认释放COM12，并授权只读与暂停/恢复。
- 来源：业务规则与变更日志_V1.0.2.md 第 160 行「设备维护实机测试（2026-09-18）」“用户确认释放COM12并授权只读与暂停/恢复”
- 状态：待确认
- 现状符合度：未验证（历史测试事实，不是软件行为，代码无法核实该次确认与授权。每次使用实机脚本前的通用确认要求另见 MAINT-092、MAINT-095（第166行）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：单次实机测试的释放确认与授权记录，无代码对应

### MAINT-073 2026-09-18实机测试对待核对地址的处理
- 规则：（单次测试事实，归测试/验收流程）2026-09-18 实机测试时正式配置地址为1、2，光谱仪1存在此前1→3的待核对写入；测试只读确认地址3身份字段及参数匹配后，仅在临时配置使用地址3、2，未改变正式配置或待维护状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 160 行「设备维护实机测试（2026-09-18）」“正式配置地址1、2，但光谱仪1存在此前1→3的待核对写入；只读确认地址3身份字段及参数匹配后，仅在临时配置使用3、2，未改变正式配置或待维护状态”
- 状态：待确认
- 现状符合度：未验证（历史测试事实，无法从代码核实该次执行情况。当前脚本的对应机制：tools/verify_maintenance_hardware.py main 中 --use-confirmed-pending-addresses 先做只读核对，再修改 deepcopy 出的临时配置。脚本遇正式 pending 的通用规则是默认中止（MAINT-097），显式参数分支见 MAINT-093、MAINT-096（第166行）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-074 支持普通通信参数读取
- 规则：在不进入通信维护的情况下，可经后台串行队列读取设备当前通信参数（普通通信参数读取）。
- 来源：业务规则与变更日志_V1.0.2.md 第 161 行「设备维护实机测试（2026-09-18）」“校准读取和本地修改后放弃、普通通信参数读取”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 处理 comm_read，调用 ParModbusClient.read_mcu_comm 并写 diagnostics。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/protocol.py ParModbusClient.read_mcu_comm

### MAINT-075 校准读取后本地修改可放弃
- 规则：校准页读取硬件校准后允许本地修改，未写入的本地修改可以放弃而不写入硬件。
- 来源：业务规则与变更日志_V1.0.2.md 第 161 行「设备维护实机测试（2026-09-18）」“JSON诊断导出、校准读取和本地修改后放弃”
- 状态：待确认
- 现状符合度：符合（MainWindow.discard_calibration 放弃待写入修改；DeviceMaintenanceDialog.reject 关闭前确认放弃。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.discard_calibration；par_app/ui.py MainWindow.read_calibration

### MAINT-076 诊断显示22项错误计数并可筛选非零项
- 规则：设备诊断读取后显示22项硬件错误计数（8项通信错误+14项PAR错误），并提供“仅显示非零项”筛选。
- 来源：业务规则与变更日志_V1.0.2.md 第 161 行「设备维护实机测试（2026-09-18）」“两台均通过诊断读取、22项错误计数显示与非零筛选”
- 状态：待确认
- 现状符合度：符合（ParModbusClient.read_diagnostics 返回 communication_errors（8项）与 par_errors（14项）；DeviceMaintenanceDialog.filter_errors 按非零勾选隐藏零值行；verify_maintenance.py test_diagnostics_register_layout。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.filter_errors

### MAINT-077 诊断结果可导出为JSON
- 规则：设备维护诊断支持导出JSON诊断文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 161 行「设备维护实机测试（2026-09-18）」“22项错误计数显示与非零筛选、JSON诊断导出”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.export_diagnostics 以 json.dumps 写出含设备名、地址、数据库、快照与软件事件的 JSON。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.export_diagnostics

### MAINT-078 关闭维护窗口保持暂停须明确恢复
- 规则：关闭维护窗口不恢复采集，采集保持暂停；只有明确执行恢复操作后才重新采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 162 行「设备维护实机测试（2026-09-18）」“关闭窗口保持暂停，明确恢复后再次成功采集；两台/单台两轮场景均通过”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.reject 不调用 leave_maintenance；恢复仅经 MainWindow.resume_after_maintenance → PollingCoordinator.leave_maintenance；verify_maintenance.py test_dialog_close_keeps_stopped。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；par_app/ui.py MainWindow.resume_after_maintenance；par_app/coordinator.py PollingCoordinator.leave_maintenance

### MAINT-079 未确认物理隔离时拦截通信维护读取
- 规则：通信维护中，用户未确认通信链路只连接目标设备（物理隔离）时，通信维护读取须被拦截，不发起通信。
- 来源：业务规则与变更日志_V1.0.2.md 第 162 行「设备维护实机测试（2026-09-18）」“诊断/校准禁止读取；未确认物理隔离时通信维护读取被拦截”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.submit 对所有 maintenance_* 操作检查 isolated 勾选，未勾选弹警告并返回；注意后台 CommunicationMaintenance.execute 仅对 maintenance_write 校验 isolated，读取的拦截只在界面层。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.submit；par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-080 进入通信维护后释放采集连接
- 规则：进入通信维护后，后台采集使用的总线连接须释放（断开），采集停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 162 行「设备维护实机测试（2026-09-18）」“进入通信维护后采集连接释放，诊断/校准禁止读取”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-06 已修复（PR #20）：正常路径：maintenance_enter 经 _enter_maintenance 调 _disconnect_bus 关闭 _client，全部释放才置 _maintenance、发出 maintenance_changed(True)；verify_polling.py PollingTests.test_communication_maintenance_exclusive_and_explicit_resume 断言 close 被调用且 _client 为 None。关闭失败：_disconnect_bus 把失败的连接留在 _unreleased 并返回原因，_enter_maintenance 发出 task_finished(False) 后返回，不进入维护。按 D-162 1A，_maintenance 仍为假，run 循环照常经 _ensure_bus_connected 新建连接恢复采集（旧句柄仍占串口时连接失败并显示总线错误，按原重试间隔重连）；按 D-162 2A，再次 maintenance_enter 时 _disconnect_bus 先重试关闭 _unreleased 中的旧连接和当前连接，全部成功即进入维护，仍有失败则继续拒绝；这里的“成功”只表示 close() 没有抛异常，不等于句柄已确认释放（见 D-162“实现边界”，真实释放待 Windows 实机验收）。（V1.0.2 现状：_disconnect_bus 吞掉 client.close() 的异常仍把 _client 置 None，照常进入维护。）
- 冲突：缺陷：关闭采集连接失败时异常被吞掉，仍宣布进入维护，连接不一定已释放，待建 issue（DEF-06）；DEF-06 已修复（PR #20）（关闭失败不进入维护，失败的连接保留并在下次断开时重试关闭，重复点击进入也须先释放）；D-162 已裁决：关闭失败未进入维护时恢复采集并按原逻辑重连，再次进入时重试关闭、全部释放即进入维护（1A、2A，负责人 2026-10-17）
- 验证：tests/qt/test_maintenance_enter_close_failure.py::test_close_failure_does_not_enter_maintenance；tests/qt/test_maintenance_enter_close_failure.py::test_retry_does_not_enter_maintenance_while_handle_is_unreleased；tests/qt/test_maintenance_enter_close_failure.py::test_failed_entry_resumes_acquisition_and_reconnects；tests/qt/test_maintenance_enter_close_failure.py::test_retry_enters_maintenance_once_close_succeeds
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator._enter_maintenance；par_app/coordinator.py PollingCoordinator._disconnect_bus

### MAINT-081 通信维护期间禁止诊断与校准读取
- 规则：处于通信维护模式时，诊断读取和校准读取均被禁止。
- 来源：业务规则与变更日志_V1.0.2.md 第 162 行「设备维护实机测试（2026-09-18）」“进入通信维护后采集连接释放，诊断/校准禁止读取”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 维护模式下非 maintenance_* 任务返回“维护模式下禁止普通硬件任务”；DeviceMaintenanceDialog.update_controls 维护中禁用刷新；test_communication_maintenance_exclusive_and_explicit_resume 断言 calibration_read 失败。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-082 实机只读测试拦截其他硬件写入
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 163 行「设备维护实机测试（2026-09-18）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：（设备协议细节，公开版略）
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main；par_app/protocol.py ParModbusClient.set_stop

### MAINT-083 实机测试的采集日志导出写临时目录
- 规则：实机测试产生的采集数据、日志及导出文件均写入临时目录，不写正式数据目录。
- 来源：业务规则与变更日志_V1.0.2.md 第 163 行「设备维护实机测试（2026-09-18）」“采集、日志及导出均写临时目录。测试线程退出，连接已关闭”
- 状态：待确认
- 现状符合度：符合（tools/verify_maintenance_hardware.py main 用 tempfile.mkdtemp 建输出目录，设备 database_path 与 AppConfigStore 均指向该目录。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-084 实机测试结束须退出线程并关闭连接
- 规则：实机测试结束时，测试使用的后台线程须退出，串口连接须关闭。
- 来源：业务规则与变更日志_V1.0.2.md 第 163 行「设备维护实机测试（2026-09-18）」“采集、日志及导出均写临时目录。测试线程退出，连接已关闭”
- 状态：待确认
- 现状符合度：未验证（仅读到脚本结构，未实跑；脚本是否在所有退出路径停止 coordinator 并关闭串口未逐路径核对。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main；par_app/coordinator.py PollingCoordinator.stop

### MAINT-085 （设备协议细节，公开版略）
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 163 行「设备维护实机测试（2026-09-18）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_calibration

### MAINT-086 自动对时仅在测试进程中禁用
- 规则：实机测试期间自动对时只在测试进程内禁用，不改变正式软件的对时行为或配置。
- 来源：业务规则与变更日志_V1.0.2.md 第 163 行「设备维护实机测试（2026-09-18）」“自动对时仅在测试进程中禁用。采集、日志及导出均写临时目录”
- 状态：待确认
- 现状符合度：符合（tools/verify_maintenance_hardware.py main 以 patch('par_app.coordinator.PollingCoordinator._sync_time_if_due') 仅在进程内禁用，产品代码不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main；par_app/coordinator.py PollingCoordinator._sync_time_if_due

### MAINT-087 硬件身份不唯一，改参须保持物理隔离
- 规则：设备硬件身份字段（序列号、类型、名称）可能在多台设备上相同，不能作为唯一实物身份；因此修改设备通信参数时必须保持目标设备物理隔离（总线上只连接目标设备）。
- 来源：业务规则与变更日志_V1.0.2.md 第 164 行「设备维护实机测试（2026-09-18）」“不能作为唯一实物身份，因此改参必须保留物理隔离”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 对 maintenance_write 要求 payload isolated 为真；MaintenanceDialog.submit 要求勾选“已确认通信链路只连接目标设备”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance_dialog.py MaintenanceDialog.submit

### MAINT-088 完成待核对流程无需再次写硬件
- 规则：已尝试写入的通信参数在新参数核对通过后即可收尾，不需要再次向硬件写入参数。
- 来源：业务规则与变更日志_V1.0.2.md 第 165 行「设备维护实机测试（2026-09-18）」“用户需在隔离状态下完成「使用新参数核对」，再将软件登记改为3，接回总线并明确恢复采集；无需再次写硬件”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 的 maintenance_verify 分支只读状态/身份/通信参数并比对身份，不调用 change_mcu_comm。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-089 待核对写入须先用新参数核对
- 规则：存在待核对的通信参数写入时，须在目标设备隔离状态下完成“使用新参数核对”，核对完成前不能恢复采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 165 行「设备维护实机测试（2026-09-18）」“用户需在隔离状态下完成「使用新参数核对」，再将软件登记改为3，接回总线并明确恢复采集”
- 状态：待确认
- 现状符合度：未验证（核对前不能恢复：CommunicationMaintenance.check_resume 在 pending 存在时抛出“写入结果尚未核对，不能恢复采集”，maintenance_read 在 pending 时被拒，符合；verify_maintenance.py MaintenanceTests.test_verify_requires_pending_write、MaintenanceTests.test_lost_write_response_requires_verification。隔离状态：软件无法检测物理隔离，只依赖操作者确认——手动核对经 MaintenanceDialog.submit 要求勾选隔离确认；写入成功后的自动核对由 MaintenanceDialog.task_finished 直接排队，沿用写入时的勾选；后台 CommunicationMaintenance.execute 只在 maintenance_write 分支检查 isolated，核对分支不检查。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance_dialog.py MaintenanceDialog.submit；par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-090 核对后须更新软件登记再明确恢复
- 规则：新参数核对通过后，须先把软件中该设备的登记（地址等）改为新参数并接回总线，再明确恢复采集；软件登记与核对结果不一致时不得恢复。（裁决 D-131：该设备已停用或已移出登记时放行，不要求其参数一致；它重新启用或重新登记时，仍须先完成核对才能参与采集。）
- 来源：业务规则与变更日志_V1.0.2.md 第 165 行「设备维护实机测试（2026-09-18）」“再将软件登记改为3，接回总线并明确恢复采集；无需再次写硬件”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-131 已裁决：停用或移出登记的设备在恢复检查中放行；该设备重新启用或重新登记时，仍须先完成核对才能参与采集，DEF-16 已修复（PR #32）；D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_verified_device_is_let_through_but_must_verify_when_re_enabled；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_enabled_matching_device_still_waits_for_explicit_resume；tests/qt/test_maintenance_rejoin_requires_verification.py::test_removed_device_registered_again_after_restart_must_verify_first；tests/qt/test_maintenance_rejoin_requires_verification.py::test_verified_device_removed_at_runtime_must_verify_when_registered_again；tests/qt/test_maintenance_rejoin_requires_verification.py::test_rejoined_device_rejects_manual_writes_until_verified；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_registered_device_with_pending_write_rejects_calibration_write
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/ui.py MainWindow.resume_after_maintenance；par_app/maintenance.py CommunicationMaintenance.finish_after_resume；par_app/coordinator.py PollingCoordinator._awaiting_verification；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/maintenance.py check_manual_task

### MAINT-091 --isolated-device仅在确认物理隔离时使用
- 规则：仅当用户确认已物理隔离目标设备时，才可使用--isolated-device参数（本次为3）。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“`--isolated-device 3`仅在用户确认已物理隔离时使用”
- 状态：待确认
- 现状符合度：未验证（人工流程约束；脚本只校验该地址对应唯一启用登记设备，无法核实物理隔离。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main；无：物理隔离由用户确认，代码无法检测

### MAINT-092 使用实机脚本前须再次获得用户释放确认
- 规则：每次使用实机维护脚本前，须再次获得用户对释放硬件的确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“必须显式传入`--hardware-released`，使用前再次获得用户释放硬件确认”
- 状态：待确认
- 现状符合度：未验证（人工流程约束，代码只检查命令行标志，无法核实用户确认。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：人工确认流程，代码无法强制

### MAINT-093 只读核对模式仅核对已保存新参数
- 规则：使用--check-pending-readonly时，脚本只以已保存的新参数只读核对设备身份与参数，不做其他操作。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“`--check-pending-readonly`仅核对已保存新参数”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-094 实机脚本以Qt控件和真实后台通信验证
- 规则：实机维护脚本以Qt控件驱动并经实际后台通信验证，确认弹窗自动应答。原文同时记录该次测试未测试任何写入按钮，这是该次测试的覆盖范围，不构成禁止测试写入的规则。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“脚本以Qt控件驱动及实际后台通信验证，确认弹窗自动应答，未测试任何写入按钮”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：（设备协议细节，公开版略）
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main；par_app/protocol.py ParModbusClient.read_spectrum_transaction

### MAINT-095 实机脚本必须显式传入--hardware-released
- 规则：运行实机维护脚本tools/verify_maintenance_hardware.py必须显式传入--hardware-released参数，否则不运行。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“必须显式传入`--hardware-released`，使用前再次获得用户释放硬件确认”
- 状态：待确认
- 现状符合度：符合（argparse add_argument('--hardware-released', action='store_true', required=True)，缺失时 parser 报错退出。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-096 确认后的pending地址只改临时测试地址
- 规则：使用--use-confirmed-pending-addresses时，须在身份/参数核对通过后，才把待核对新地址用于临时测试配置，不改正式配置。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“`--use-confirmed-pending-addresses`在身份/参数核对后仅更改临时测试地址”
- 状态：待确认
- 现状符合度：符合（该模式先执行与 --check-pending-readonly 相同的只读断言，再修改 deepcopy(source) 的 slave_id，配置保存到临时目录。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-097 遇正式pending时实机脚本默认中止
- 规则：正式配置的设备库中存在待核对写入（pending）时，实机脚本默认中止，不进行测试。
- 来源：业务规则与变更日志_V1.0.2.md 第 166 行「设备维护实机测试（2026-09-18）」“遇正式pending默认中止；`--check-pending-readonly`仅核对已保存新参数”
- 状态：待确认
- 现状符合度：符合（tools/verify_maintenance_hardware.py main：存在 pending/verified 时 unfinished 为真，未带 --use-confirmed-pending-addresses 或 roundtrip 时断言失败（'Finish existing maintenance before this test'）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：tools/verify_maintenance_hardware.py main

### MAINT-098 退出设备的维护任务不访问硬件
- 规则：已退出本次采集的设备，其维护任务不再访问硬件。
- 来源：业务规则与变更日志_V1.0.2.md 第 207 行「多设备重构：第 3 阶段（2026-09-17）」“仍可切换查看设备历史。退出设备的维护任务也不会继续访问硬件。”
- 状态：待确认
- 现状符合度：符合（_process_tasks：维护任务在 state.excluded 时抛“设备不可维护…”，普通任务在 excluded 时直接返回失败，均不触达 client。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-099 不改硬件参数制造测试故障
- 规则：验证硬件停止时不得通过修改硬件参数来人为制造故障。
- 来源：业务规则与变更日志_V1.0.2.md 第 228 行「多设备重构：第 4 阶段（2026-09-17）」“若设备仍异常则再次停止。不通过修改硬件参数制造测试故障。”
- 状态：待确认
- 现状符合度：未验证（测试流程约束，不是软件行为；verify_polling 采用 mock 隔离模拟，无法从代码判断现场做法。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：测试/验收流程要求，无代码对应

### MAINT-100 切换设备清空校准字段及节点
- 规则：切换校准目标设备时，清空校准字段和曲线节点。
- 来源：业务规则与变更日志_V1.0.2.md 第 240 行「多设备重构：第 5 阶段（2026-09-17）」“切换设备清空校准字段及节点，当前设备有效回读后才允许写入”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.change_device 与 MainWindow._bind_active_device（窗口不可见时）调用 _reset_calibration，字段置0、节点清空。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._reset_calibration；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device

### MAINT-101 回包完整验证后一次性更新字段
- 规则：校准回包全部字段验证通过后才一次性更新界面字段，验证失败则不更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 240 行「多设备重构：第 5 阶段（2026-09-17）」“不覆盖当前校准。回包完整验证后才一次性更新字段。”
- 状态：待确认
- 现状符合度：符合（_apply_hardware_calibration 先校验全部字段有限、范围、节点递增与限幅，全部通过才批量 setValue；verify_multidevice 覆盖无效回包。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py parse_readback；par_app/ui.py MainWindow._apply_hardware_calibration

### MAINT-102 当前设备有效回读后才允许写校准
- 规则：只有当前校准设备有效回读之后才允许写入校准。
- 来源：业务规则与变更日志_V1.0.2.md 第 240 行「多设备重构：第 5 阶段（2026-09-17）」“切换设备清空校准字段及节点，当前设备有效回读后才允许写入；”
- 状态：待确认
- 现状符合度：符合（_update_calibration_controls 仅在 _calibration_device_key == _calibration_key() 时启用写入；write_calibration 再次检查。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_calibration_controls；par_app/ui.py MainWindow.write_calibration

### MAINT-103 非当前设备回包只提示不覆盖
- 规则：非当前校准设备的任务完成时，只显示带设备名的反馈，不覆盖当前设备的校准显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 240 行「多设备重构：第 5 阶段（2026-09-17）」“非当前设备任务完成只显示带设备名反馈，不覆盖当前校准。”
- 状态：待确认
- 现状符合度：符合（_device_task_finished 先 statusBar 显示“设备名：kind 完成/失败”，key != _calibration_key() 时 return。审计 robustness-ui 附注：此时 _calibration_busy 不清除，正常模态路径不可达。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_task_finished

### MAINT-104 切换校准设备后旧参数清空（手测）
- 规则：切换校准设备后旧校准参数被清空，可用“从硬件读取”重新读取核对。
- 来源：业务规则与变更日志_V1.0.2.md 第 248 行「多设备重构：第 5 阶段（2026-09-17）」“切换校准设备后确认旧参数清空，可用「从硬件读取」核对”
- 状态：待确认
- 现状符合度：符合（change_device→_reset_calibration；“从硬件读取”按钮连接 read_calibration。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._reset_calibration；par_app/ui.py MainWindow.read_calibration；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device

### MAINT-105 校准验收不必写入硬件
- 规则：校准设备切换的验收不需要向硬件写入校准。
- 来源：业务规则与变更日志_V1.0.2.md 第 248 行「多设备重构：第 5 阶段（2026-09-17）」“可用「从硬件读取」核对；不必写入硬件做验收。”
- 状态：待确认
- 现状符合度：未验证（验收流程说明，不是软件行为。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：验收流程说明，无代码对应

### MAINT-106 常规设置页只做软件连接配置与只读查询
- 规则：常规设置页只保留软件连接配置和只读查询，不在常规设置页执行设备硬件通信参数的写入；硬件通信参数维护须进入独立维护窗口。
- 来源：业务规则与变更日志_V1.0.2.md 第 296 行「多设备重构：第 6 阶段（2026-09-17）」“常规设置页只保留软件连接配置和只读查询；左下方「通信参数」按钮打开独立维护窗口。”
- 状态：待确认
- 现状符合度：符合（设置页只排队 comm_read（MainWindow._request_settings_comm）；后台收到 comm_write 一律拒绝并提示“常规采集禁止写入通信参数，请使用独立的设备维护窗口”（PollingCoordinator._write_device_comm）。）
- 冲突：D-109 已裁决：维护入口以第69行（右栏、右对齐、与办公地址底边对齐）为准，第131行“左下方”和第296行“左下方‘通信参数’按钮”标为历史废止；同句入口描述所立 MAINT-157 已废止、由 UI-074 替代，本条只承载“常规设置页只做软件连接配置与只读查询”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._request_settings_comm；par_app/coordinator.py PollingCoordinator._write_device_comm；par_app/ui.py MainWindow.open_device_maintenance

### MAINT-107 确认进入维护后先结束当前事务再允许维护
- 规则：操作者确认进入通信维护后，由唯一后台线程完成当前事务并释放采集连接，此后才允许执行维护操作；未完成交接前维护读写按钮不可用。
- 来源：业务规则与变更日志_V1.0.2.md 第 297 行「多设备重构：第 6 阶段（2026-09-17）」“确认进入后，唯一后台线程完成当前事务、释放采集连接，再允许维护操作。”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-06 已修复（PR #20）：正常路径：DeviceMaintenanceDialog.enter_communication 先弹确认框，再调用 PollingCoordinator.enter_maintenance 排队 maintenance_enter；同一线程在 _process_tasks 中于事务之间处理，_enter_maintenance 在 _disconnect_bus 全部释放后才发出 maintenance_changed(True)，MaintenanceDialog.update_controls 仅在 coordinator._maintenance 为真时启用读写。关闭失败：不进入维护，DeviceMaintenanceDialog.task_finished 结束“正在停止”并在窗口底部显示“未进入通信维护，采集连接关闭失败：原因”，维护读写保持不可用；按 D-162 1A 后台按原逻辑恢复采集并重连，按 D-162 2A 操作者再次点击进入时重试关闭未释放的连接，成功即进入维护。（V1.0.2 现状：_disconnect_bus 吞掉 client.close() 的异常，照常宣布进入维护并启用维护操作。）
- 冲突：缺陷：关闭采集连接失败时仍宣布进入维护并启用维护操作，未满足“释放连接后再允许维护”，待建 issue（DEF-06）；DEF-06 已修复（PR #20）（关闭失败不进入维护，失败的连接保留并在下次断开时重试关闭，重复点击进入也须先释放）；D-162 已裁决：关闭失败未进入维护时恢复采集并按原逻辑重连，再次进入时重试关闭、全部释放即进入维护（1A、2A，负责人 2026-10-17）
- 验证：tests/qt/test_maintenance_enter_close_failure.py::test_close_failure_does_not_enter_maintenance；tests/qt/test_maintenance_enter_close_failure.py::test_retry_does_not_enter_maintenance_while_handle_is_unreleased；tests/qt/test_maintenance_enter_close_failure.py::test_dialog_reports_failed_entry_and_keeps_maintenance_disabled；tests/qt/test_maintenance_enter_close_failure.py::test_failed_entry_resumes_acquisition_and_reconnects；tests/qt/test_maintenance_enter_close_failure.py::test_retry_enters_maintenance_once_close_succeeds
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.enter_communication；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/coordinator.py PollingCoordinator.enter_maintenance；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator._enter_maintenance；par_app/coordinator.py PollingCoordinator._disconnect_bus；par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-108 维护期间禁止采集、对时、重连和普通硬件任务
- 规则：通信维护期间禁止后台采集、自动对时、自动重连以及普通校准等硬件任务；此类任务请求应被拒绝。
- 来源：业务规则与变更日志_V1.0.2.md 第 297 行「多设备重构：第 6 阶段（2026-09-17）」“维护期间禁止采集、对时、自动重连和普通校准等硬件任务。”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 在 _maintenance 时跳过轮询；_ensure_bus_connected、_poll_all_devices、_sync_time_if_due 在 _maintenance 时直接返回；_process_tasks 对非维护任务返回“维护模式下禁止普通硬件任务”；MainWindow._calibration_available 要求不在维护中。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._sync_time_if_due；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/ui.py MainWindow._calibration_available；par_app/services/calibration.py calibration_available

### MAINT-109 分别填写旧连接参数与新地址/波特率/校验
- 规则：维护窗口分别提供读取所用的旧连接参数，以及准备写入的新从站地址、新波特率和新校验位，两组参数独立填写。
- 来源：业务规则与变更日志_V1.0.2.md 第 298 行「多设备重构：第 6 阶段（2026-09-17）」“维护窗口锁定进入时选择的设备，分别填写旧连接参数、新地址、新波特率和新校验。”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog 用 _fields 分别建 old_fields（读取连接参数）和 new_fields（准备写入的新参数），各含从站 ID、波特率、奇偶校验；values() 分别组装 connection 与 new。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog._fields；par_app/maintenance_dialog.py MaintenanceDialog.values；par_app/maintenance_dialog.py MaintenanceDialog.submit

### MAINT-110 维护窗口锁定进入时选择的设备
- 规则：进入通信维护后，维护窗口锁定进入时选择的目标设备，不允许切换维护目标。
- 来源：业务规则与变更日志_V1.0.2.md 第 298 行「多设备重构：第 6 阶段（2026-09-17）」“维护窗口锁定进入时选择的设备，分别填写旧连接参数、新地址、新波特率和新校验。”
- 状态：已废止 2026-10-17，由 MAINT-015 替代（D-119 裁决：第298行“维护窗口锁定进入时选择的设备”标为历史废止）
- 现状符合度：不符合（DeviceMaintenanceDialog.locked 只在任务进行中、校准忙或有未提交修改、存在待核对写入时返回真；update_controls 用 devices.setEnabled(not self.locked())，所以已进入维护、空闲且无待核对写入时仍可切换维护目标（行为与第133行一致，与本条字面不一致）。）
- 冲突：D-119 已裁决：进入通信维护后允许切换维护目标，以第133行的三种锁定情形为准，第298行锁定一句标为历史废止；本条已废止，约束由 MAINT-015 承接
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.locked；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-111 维护链路只连接目标探头
- 规则：执行通信维护时，维护链路应只连接目标探头；软件要求操作者确认已隔离后才执行维护通信。
- 来源：业务规则与变更日志_V1.0.2.md 第 298 行「多设备重构：第 6 阶段（2026-09-17）」“维护链路应只连接目标探头；设备名称和数据库不写入硬件。”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.submit 在未勾选“已确认通信链路只连接目标设备”时拦截读取/写入/核对；CommunicationMaintenance.execute 写入时要求 payload['isolated'] 为真。软件无法检测物理隔离，只能依赖操作者确认。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.submit；par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-112 设备名称和数据库不写入硬件
- 规则：通信维护只向硬件写入通信参数（从站地址、波特率、校验），设备名称和数据库信息不写入硬件。
- 来源：业务规则与变更日志_V1.0.2.md 第 298 行「多设备重构：第 6 阶段（2026-09-17）」“维护链路应只连接目标探头；设备名称和数据库不写入硬件。”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.change_mcu_comm；par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance.py CommunicationMaintenance.parameters

### MAINT-113 写入前再次核对身份及旧参数
- 规则：写入事务中须再次读取设备身份和通信参数：旧连接参数须与此前读取时一致、回读参数须与旧连接参数一致、身份须与此前读取一致，任一不符即拒绝写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“先读取身份和当前参数；写入前再次核对身份及旧参数，并明确确认。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute：config.to_dict() 与 baseline['connection'] 不同则拒绝；parameters != self.parameters(config) 报“回读通信参数与指定连接参数不一致”；identity != baseline['identity'] 报“设备身份与此前读取不一致，禁止写入”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute

### MAINT-114 写入前须先读取身份和当前参数
- 规则：通信参数写入前，必须先对目标设备执行一次读取，取得设备身份和当前通信参数；未读取时拒绝写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“先读取身份和当前参数；写入前再次核对身份及旧参数，并明确确认。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 对 maintenance_write 在无 baseline 时报“请先读取并确认目标设备”；MaintenanceDialog.update_controls 无 baseline 时禁用写入按钮。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-115 每项维护事务共用10秒通信预算
- 规则：每项维护事务的连接、状态、身份、参数及写入共用10秒通信预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“每项维护事务含连接、状态、身份、参数及写入共用10秒通信预算，结束释放连接。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 用 client.communication_budget(10.0, cancelled) 包住 connect、read_status、read_device_identity、read_mcu_comm 及 change_mcu_comm；10.0 为字面量，未引用 DEVICE_TRANSACTION_BUDGET_SECONDS。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/protocol.py ParModbusClient.communication_budget

### MAINT-116 维护不自动修改共享总线或设备登记
- 规则：通信维护（含写入和核对成功后）不自动修改软件中的共享总线参数或设备登记。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“结束释放连接。不会自动修改共享总线或软件设备登记。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 与 check_resume 都不修改 AppConfig；check_resume 在参数不一致时要求操作者到常规设置手动更新登记或禁用该设备。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance.py CommunicationMaintenance.check_resume

### MAINT-117 通信参数写入须明确确认
- 规则：通信参数写入前须明确确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“先读取身份和当前参数；写入前再次核对身份及旧参数，并明确确认。”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.submit 对 maintenance_write 弹出“确认硬件写入”，非 Yes 直接返回不排队写入；确认框默认按钮为 No 是实现细节，原文未规定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.submit

### MAINT-118 写入后不自动重连
- 规则：通信参数写入后不自动重连。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“写入后不自动重连。通信参数动态生效，操作者直接点击「使用新参数核对」”
- 状态：待确认
- 现状符合度：符合（按 D-135 裁决，“不自动重连”只指采集总线：写入后 coordinator 仍处于 _maintenance，PollingCoordinator.run 与 _ensure_bus_connected 不连接采集总线，只有 maintenance_leave 才清除维护状态；写入成功后 MaintenanceDialog.task_finished 自动排队 maintenance_verify、CommunicationMaintenance.execute 以新参数新建维护连接，按裁决不算重连。）
- 冲突：D-135 已裁决：第300行“不自动重连”只指采集总线，写入成功后自动核对所建的维护连接不算重连
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-119 写入结果未知时禁止恢复采集
- 规则：写入结果未知（待核对）时，禁止恢复采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“写入超时或响应丢失仍视为结果未知，禁止自动重复写入或恢复采集。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.check_resume 在 pending 存在时抛出“写入结果尚未核对，不能恢复采集”；PollingCoordinator._process_tasks 的 maintenance_leave 先调用 check_resume。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-120 写入结果未知时禁止自动重复写入
- 规则：写入超时或响应丢失时视为写入结果未知，保留待核对状态，禁止软件自动重复写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“写入超时或响应丢失仍视为结果未知，禁止自动重复写入或恢复采集。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 在发出 change_mcu_comm 之前先 _save(pending)，异常时 pending 保留；pending 存在时 maintenance_write 被拒绝、写入按钮禁用（MaintenanceDialog.update_controls），代码无自动重试。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### MAINT-121 新参数核对由操作者手动触发
- 规则：写入后由操作者直接点击“使用新参数核对”发起核对。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“通信参数动态生效，操作者直接点击「使用新参数核对」，用保存的新参数回读核对身份及通信参数”
- 状态：待确认
- 现状符合度：符合（按 D-136 裁决，本条只适用于写入失败或结果未知：此时不自动核对，由操作者点击“使用新参数核对”经 MaintenanceDialog.submit 发起；写入成功且存在 pending 时 MaintenanceDialog.task_finished 自动排队 maintenance_verify，按第72、147行处理，见 MAINT-005。）
- 冲突：D-136 已裁决：写入成功时按第72、147行自动核对；第300行“直接点击核对”只适用于写入失败或结果未知，不废止
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.task_finished；par_app/maintenance_dialog.py MaintenanceDialog.submit

### MAINT-122 用保存的新参数回读核对身份及通信参数
- 规则：写入后的核对使用保存的新参数，回读核对设备身份及通信参数。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“用保存的新参数回读核对身份及通信参数，无需重新上电。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 的 maintenance_verify 以 self.pending['new'] 建连接，回读参数须等于 parameters(config)，identity 须等于 pending['identity']，通过后 _save(None, result)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance.py CommunicationMaintenance._save

### MAINT-123 严重硬件异常不能用退出维护解除
- 规则：严重硬件异常仍按全局锁存停止处理，执行“退出维护”不能解除该停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 301 行「多设备重构：第 6 阶段（2026-09-17）」“严重硬件异常仍遵循全局锁存停止，不能用退出维护解除。”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 的 maintenance_leave 在 _halt_reason 存在时报“硬件异常停止仍有效，请重新上电并重启软件”；维护任务中的 HardwareStateError 调用 _halt_acquisition 锁存。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator._halt_acquisition

### MAINT-124 待核对状态持久化到对应设备库
- 规则：通信写入的待核对状态写入该目标设备的数据库，而不是只保存在内存中。
- 来源：业务规则与变更日志_V1.0.2.md 第 301 行「多设备重构：第 6 阶段（2026-09-17）」“待核对状态写入对应设备库，重启时仍进入维护停止；核对通过但未明确恢复时也保持该状态。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance._save 把 {pending, verified} 写入目标设备库 app_settings 表的 communication_maintenance 键；DEF-16 修复后（分支 fix/rejoin-requires-verification），恢复采集时设备已停用或已移出登记的，另写 deferred: true（D-131），V1.0.2 读取时忽略该键。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance._save；par_app/maintenance.py CommunicationMaintenance.__init__

### MAINT-125 核对通过但未明确恢复时重启仍保持维护停止
- 规则：核对已通过但操作者尚未明确恢复采集时，该状态同样持久保存，重启后仍处于维护停止。（裁决 D-132：只对重启时仍在登记中的设备生效；移出登记的设备重新登记时的核对要求见 MAINT-002。）
- 来源：业务规则与变更日志_V1.0.2.md 第 301 行「多设备重构：第 6 阶段（2026-09-17）」“待核对状态写入对应设备库，重启时仍进入维护停止；核对通过但未明确恢复时也保持该状态。”
- 状态：待确认
- 现状符合度：符合（按 D-132 裁决，只对当前登记的设备生效：核对通过后 CommunicationMaintenance._save(None, result) 保存 verified；PollingCoordinator._rebuild_states 为当前登记设备加载 CommunicationMaintenance，PollingCoordinator.__init__ 在有 verified 时置 _maintenance=True；maintenance_leave 成功后 session.finish_after_resume 才清除。重启前已移出登记的设备不加载，属裁决写明的边界。核对通过后设备被停用、尚未恢复采集即重启的，仍按本条进入维护停止（＝V1.0.2）。DEF-16 修复后（分支 fix/rejoin-requires-verification）：恢复采集时设备已停用或已移出登记的，其 verified 按 D-131 保留，但 finish_after_resume 同时标为暂缓（deferred），操作者已明确恢复，不属本条“尚未明确恢复”；PollingCoordinator.__init__ 只按 CommunicationMaintenance.blocks_startup（会话未完成且未暂缓）置 _maintenance=True，重启不再因它进入维护停止（M8 第 (2) 点“重启后不再因它进入维护停止”，＝V1.0.2 恢复时清除 verified 后的结果），该设备重新启用或重新登记后仍由 PollingCoordinator._awaiting_verification 挡在采集外，直到完成核对（MAINT-002）。）
- 冲突：D-132 已裁决：只对当前登记的设备加载维护会话，这一边界写进规格；重新登记时按 D-131 仍须先核对；D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围；alpha 档位 1（D-213 问题 5、D-215 问题 5）：每次“开始采集”新建协调器并重新读取库中的维护会话，待核对写入仍进入维护停止（同重启 V1.0.3）；档位 1 不能离开维护
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_restart_after_resume_does_not_stop_but_still_holds_back_the_deferred_device
- 代码锚点：par_app/maintenance.py CommunicationMaintenance._save；par_app/maintenance.py CommunicationMaintenance.finish；par_app/maintenance.py CommunicationMaintenance.finish_after_resume；par_app/maintenance.py CommunicationMaintenance.blocks_startup；par_app/coordinator.py PollingCoordinator.__init__；par_app/coordinator.py PollingCoordinator._rebuild_states

### MAINT-126 重启后存在待核对写入仍进入维护停止
- 规则：软件重启时，若设备库中存在待核对写入，启动即进入维护停止状态，不恢复采集。（裁决 D-132：只对重启时仍在登记中的设备生效；移出登记的设备重新登记时的核对要求见 MAINT-002。）
- 来源：业务规则与变更日志_V1.0.2.md 第 301 行「多设备重构：第 6 阶段（2026-09-17）」“待核对状态写入对应设备库，重启时仍进入维护停止；核对通过但未明确恢复时也保持该状态。”
- 状态：待确认
- 现状符合度：符合（按 D-132 裁决，只对当前登记的设备生效：PollingCoordinator._rebuild_states 为当前登记设备加载 CommunicationMaintenance，PollingCoordinator.__init__ 在 pending 或 verified 存在时置 _maintenance=True（DEF-16 修复后经 CommunicationMaintenance.blocks_startup 判断，pending 一律进入维护停止，只有恢复采集时已暂缓的 verified 除外，见 MAINT-125）；待核对设备在重启前被移出登记时不加载其库（robustness-core.md 第84行），属裁决写明的边界。）
- 冲突：D-132 已裁决：只对当前登记的设备加载维护会话，这一边界写进规格；重新登记时按 D-131 仍须先核对；D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围；alpha 档位 1（D-213 问题 5、D-215 问题 5）：每次“开始采集”新建协调器并重新读取库中的维护会话，待核对写入仍进入维护停止（同重启 V1.0.3）；档位 1 不能离开维护
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_device_with_pending_write_still_blocks_resume_and_restart
- 代码锚点：par_app/coordinator.py PollingCoordinator.__init__；par_app/maintenance.py CommunicationMaintenance.__init__；par_app/coordinator.py PollingCoordinator._rebuild_states

### MAINT-127 关闭维护窗口不恢复采集
- 规则：关闭维护窗口只返回常规界面，采集保持停止，不因关闭而恢复。
- 来源：业务规则与变更日志_V1.0.2.md 第 302 行「多设备重构：第 6 阶段（2026-09-17）」“关闭维护窗口只返回常规界面，不恢复采集。”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.reject/closeEvent 只关闭窗口，不调用 leave_maintenance；关闭按钮在维护中显示“关闭（保持停止）”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.closeEvent；par_app/maintenance_dialog.py MaintenanceDialog.reject

### MAINT-128 存在未核对写入时拒绝恢复采集
- 规则：存在未核对的通信写入时，拒绝退出维护并恢复采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 302 行「多设备重构：第 6 阶段（2026-09-17）」“未核对写入或软件参数仍不匹配时拒绝恢复。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.check_resume 在 pending 存在时抛错，maintenance_leave 失败；MainWindow._refresh_communication_events 同时禁用恢复按钮。该设备已停用或在运行中移出登记时同样拒绝（＝V1.0.2，D-131 的放行只针对已核对会话，见 MAINT-002 适用边界；D-167 已裁决 2026-10-18（按推荐）：保留此保守做法）。）
- 冲突：D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_device_with_pending_write_still_blocks_resume_and_restart；tests/qt/test_maintenance_rejoin_requires_verification.py::test_device_removed_at_runtime_with_pending_write_still_blocks_resume
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/ui.py MainWindow._refresh_communication_events

### MAINT-129 经“设备维护 → 退出维护并恢复采集”明确恢复
- 规则：需要时先手动更新软件连接配置；接回设备并核对总线一致性后，选择“设备维护 → 退出维护并恢复采集”恢复采集。（裁决 D-110：设置页右上方“退出维护并恢复采集”按钮和维护弹窗内“退出通信维护并恢复采集”按钮两处入口都保留；两处的禁止条件统一采用弹窗按钮那一套，含“校准有未处理修改”，见 MAINT-067。）
- 来源：业务规则与变更日志_V1.0.2.md 第 302 行「多设备重构：第 6 阶段（2026-09-17）」“需要时先手动更新软件连接配置；接回设备并核对总线一致性后，选择「设备维护 → 退出维护并恢复采集」。”
- 状态：待确认
- 现状符合度：符合（按 D-110 裁决。分支 fix/resume-conditions-unified 修复 DEF-12 后，两处入口的可用条件都由 par_app/services/maintenance.py resume_gate 判定：MainWindow._refresh_communication_events（设置页 maintenance_resume_action）与 DeviceMaintenanceDialog.update_controls（弹窗 resume_button）传入同样的事实。只在维护中可恢复，依次检查：严重硬件停止（显示停止原因）；任务进行中（弹窗诊断读取、正在进入维护、通信维护面板读写、校准读取或写入），提示“任务尚未结束，暂不能恢复采集。”；校准有未处理修改，提示“校准修改尚未处理，暂不能恢复采集。”；各维护会话的 CommunicationMaintenance.check_resume（待核对写入、核对后参数不一致），提示其原因。顺序与文字＝V1.0.2 弹窗按钮；设置页按钮的提示和右栏状态文字显示同一原因。两处按钮都经 MainWindow.resume_after_maintenance：先刷新条件、按钮不可用即返回，确认后才调用 PollingCoordinator.leave_maintenance，软件不自动恢复；设备侧流程（maintenance_leave 的严重停止与 check_resume 检查、顺序）不变。V1.0.2 原核对：两处入口都在，都调用 resume_after_maintenance；设置页入口不检查校准未处理修改和校准读取或写入进行中，可绕过弹窗的检查恢复采集（现有界面中维护弹窗以模态打开、关闭时须放弃未写入修改，这一缺口在常规操作下不易触发；修复不依赖这一点）。弹窗内按钮文字与原文“退出维护并恢复采集”不同，本修复不改（＝现状）。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”），DEF-12 已修复（PR #42）
- 验证：tests/unit/test_services_maintenance.py::test_allowed_only_in_maintenance_with_nothing_blocking；tests/unit/test_services_maintenance.py::test_not_in_maintenance_is_refused_without_a_reason_and_checks_nothing；tests/unit/test_services_maintenance.py::test_unhandled_calibration_changes_refuse_with_the_window_wording；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_calibration_changes_are_unhandled；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_settings_entry_refuses_while_a_calibration_task_runs；tests/qt/test_resume_conditions_unified.py::TestResumeConditions::test_both_entries_agree_on_every_condition
- 代码锚点：par_app/ui.py MainWindow.resume_after_maintenance；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.resume_acquisition；par_app/coordinator.py PollingCoordinator.leave_maintenance；par_app/services/maintenance.py resume_gate；par_app/ui.py MainWindow._refresh_communication_events；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### MAINT-130 软件参数与核对结果不一致时拒绝恢复
- 规则：核对通过后，若软件的总线参数（传输方式、串口、波特率、校验）或该设备登记从站地址与核对通过的新参数不一致，拒绝恢复采集。（裁决 D-131：该设备已停用或已移出登记时放行，不要求其参数一致；它重新启用或重新登记时，仍须先完成核对才能参与采集。）
- 来源：业务规则与变更日志_V1.0.2.md 第 302 行「多设备重构：第 6 阶段（2026-09-17）」“未核对写入或软件参数仍不匹配时拒绝恢复。”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-131 已裁决：停用或移出登记的设备在恢复检查中放行；该设备重新启用或重新登记时，仍须先完成核对才能参与采集，DEF-16 已修复（PR #32）；D-167 已裁决 2026-10-18（按推荐）：pending 设备停用或移出、设备停用后未明确恢复即重启、pending 设备运行中重新登记这几格保留＝V1.0.2 的保守做法（1A、2A、3A），M8 第 (1)(2) 点的适用范围按 D-167 正文矩阵收窄；deferred 键列入 PR #32 的 L3 批准范围
- 验证：tests/qt/test_maintenance_rejoin_requires_verification.py::test_disabled_verified_device_is_let_through_but_must_verify_when_re_enabled；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_enabled_matching_device_still_waits_for_explicit_resume；tests/qt/test_maintenance_rejoin_requires_verification.py::test_removed_device_registered_again_after_restart_must_verify_first；tests/qt/test_maintenance_rejoin_requires_verification.py::test_verified_device_removed_at_runtime_must_verify_when_registered_again；tests/qt/test_maintenance_rejoin_requires_verification.py::test_restart_after_resume_does_not_stop_but_still_holds_back_the_deferred_device；tests/qt/test_maintenance_rejoin_requires_verification.py::test_rejoin_hint_and_diagnostic_are_written_once；tests/qt/test_maintenance_rejoin_requires_verification.py::test_rejoined_device_rejects_manual_writes_until_verified；tests/qt/test_maintenance_rejoin_requires_verification.py::test_re_registered_device_with_pending_write_rejects_calibration_write
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.check_resume；par_app/maintenance.py CommunicationMaintenance.finish_after_resume；par_app/coordinator.py PollingCoordinator._awaiting_verification；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/maintenance.py check_manual_task

### MAINT-131 维护不做运维身份认证
- 规则：当前阶段软件不对运维人员做身份认证；维护弹窗用于工作流隔离，不作为权限控制。
- 来源：业务规则与变更日志_V1.0.2.md 第 303 行「多设备重构：第 6 阶段（2026-09-17）」“当前阶段仍不对软件作运维身份认证；维护弹窗用于工作流隔离，不是权限控制。”
- 状态：待确认
- 现状符合度：符合（par_app 中没有登录、口令或权限校验代码；DeviceMaintenanceDialog 由“设备维护”按钮直接打开。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：产品边界声明（不做身份认证），无对应实现；par_app/ui.py MainWindow.open_device_maintenance

### MAINT-132 通信维护日志写入目标设备库 diagnostics
- 规则：通信维护日志写入目标设备库的 diagnostics，类别为 communication_maintenance，内容包含动作、旧/新参数、身份和结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 303 行「多设备重构：第 6 阶段（2026-09-17）」“日志在目标设备库的 diagnostics，类别为 communication_maintenance，包含动作、旧/新参数、身份和结果。”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 调用 self.database.diagnostic(…, 'communication_maintenance', …)：开始时记 action 与 connection；写入前记 old/new/identity；完成时记 action 与 result（含 identity、parameters）；失败时记 ERROR、异常消息和 action（失败记录不含参数和身份）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/database.py ParDatabase.diagnostic

### MAINT-133 故障时禁用校准读写，恢复后须重新读取
- 规则：校准目标设备发生故障时禁用校准读写；故障恢复后必须重新读取一次才能写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 314 行「公共设备状态栏（2026-09-17）」“有效回读后才允许写入。故障发生时禁用读写，恢复后需重新读取才能写入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._update_calibration_controls：不可用时禁用读取并把 _calibration_device_key 置 None，恢复后需重新 read_calibration 才能 editable。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_calibration_controls；par_app/ui.py MainWindow._calibration_available；par_app/services/calibration.py calibration_available

### MAINT-134 校准读取的前置条件
- 规则：仅当（原P4）当前设备已配置启用、在线且无故障，且不处于维护或全局停止时，才可读取硬件校准。
- 来源：业务规则与变更日志_V1.0.2.md 第 314 行「公共设备状态栏（2026-09-17）」“P4仅当前设备已配置启用、在线且无故障、无维护或全局停止时可读取硬件；”
- 状态：待确认
- 现状符合度：符合（按 D-137 裁决，“当前设备”即维护弹窗所选设备：MainWindow._calibration_key 在维护弹窗可见时取弹窗所选维护设备，否则取主界面当前查看设备；MainWindow._calibration_available 对这台设备要求 device.enabled、config.configured、snapshot['online']、非 _device_is_faulty、非 coordinator._maintenance、无 halt_reason。）
- 冲突：D-137 已裁决：“当前设备”即维护弹窗所选设备，读取前提原样适用；第312行“P4 参与公共单选”随 P4 迁入维护弹窗作废
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py calibration_available；par_app/ui.py MainWindow._calibration_available；par_app/ui.py MainWindow._calibration_key；par_app/ui.py MainWindow._update_calibration_controls

### MAINT-135 校准须有效回读后才允许写入
- 规则：校准参数只有在对同一目标设备有效回读之后才允许编辑和写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 314 行「公共设备状态栏（2026-09-17）」“有效回读后才允许写入。故障发生时禁用读写，恢复后需重新读取才能写入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._update_calibration_controls：editable 要求 _calibration_device_key == _calibration_key()，该值只在成功回读后设置；写入按钮和字段按 editable 启用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_calibration_controls；par_app/ui.py MainWindow.read_calibration

### MAINT-136 软件事件显示处理不改写日志
- 规则：软件事件表的显示处理不改写设备库中的日志。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“刷新后回到最新入库事件，数据库仍按ID倒序且不改写日志”
- 状态：待确认
- 现状符合度：符合（ParDatabase.recent_diagnostics 只做 SELECT；DeviceMaintenanceDialog.display_diagnostics 的单行化、中文类别等转换只作用于表格单元格文本，不写回数据库。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/database.py ParDatabase.recent_diagnostics

### MAINT-137 诊断读取使用10秒预算
- 规则：诊断读取使用10秒事务预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“通过原后台单线程队列和10秒预算执行，不另开串口”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 的 diagnostics_read 分支以 communication_budget(_transaction_budget()) 执行，_transaction_budget 返回 DEVICE_TRANSACTION_BUDGET_SECONDS=10.0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator._transaction_budget；par_app/coordinator.py DEVICE_TRANSACTION_BUDGET_SECONDS

### MAINT-138 诊断读取不另开串口
- 规则：诊断读取不另开串口。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“通过原后台单线程队列和10秒预算执行，不另开串口”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._process_tasks 的 diagnostics_read 在共享的采集连接 self._client 上执行；_client 为 None 时报“总线未连接”失败，不新建连接。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._process_tasks

### MAINT-139 诊断后续可手动刷新
- 规则：进入诊断页读取后，可手动刷新诊断。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“进入诊断页读取一次，后续可手动刷新”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog._build_diagnostics 把刷新按钮连接到 refresh_diagnostics；按钮在设备可读时启用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog._build_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.refresh_diagnostics

### MAINT-140 诊断不自动高频轮询
- 规则：诊断读取不做自动高频轮询。
- 来源：业务规则与变更日志_V1.0.2.md 第 135 行「统一设备维护（2026-09-18，当前布局）」“不另开串口、不写云标记、不自动高频轮询”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 只由刷新按钮和 page_changed（进入诊断页、切换维护设备）调用，没有定时器周期触发诊断读取。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.page_changed；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.refresh_diagnostics

### MAINT-141 校准错误仅错误0显示无错误
- 规则：错误状态仅在错误码为0时显示“无错误”；非零错误保留数值显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“仅状态1显示「已校准」、错误0显示「无错误」；未知状态和非零错误保留数值”
- 状态：待确认
- 现状符合度：符合（MainWindow._task_finished：error_code == 0 显示“错误状态：无错误”，缺失显示“错误状态：未读取”，其他值显示“错误码：N”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py status_texts；par_app/ui.py MainWindow._task_finished

### MAINT-142 校准状态与错误悬停可查看原始码
- 规则：校准状态与错误状态悬停时可查看原始码。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“未知状态和非零错误保留数值，悬停可查看原始码”
- 状态：待确认
- 现状符合度：符合（MainWindow._task_finished 在状态码、错误码存在时分别 setToolTip(“原始校准状态码：N”/“原始错误码：N”)，缺失时清空提示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py status_texts；par_app/ui.py MainWindow._task_finished

### MAINT-143 缺失校准信息不伪造版本
- 规则：校准版本信息缺失时不伪造版本。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“悬停可查看原始码。缺失信息不沿用上次状态或伪造版本”
- 状态：待确认
- 现状符合度：符合（MainWindow._task_finished 仅在 version_nodes 为 0–255 整数时解码版本/节点数，否则显示“—”。读取失败时版本标签保留上次成功读取的值，见 MAINT-042。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/calibration.py status_texts；par_app/ui.py MainWindow._task_finished

### MAINT-144 保留可选中复制的身份摘要
- 规则：通信页保留可选中复制的身份摘要。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“删除通信「详情」按钮及JSON弹窗，保留可选中复制的身份摘要、完整失败提示及后台日志”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.__init__ 的 identity 标签设置 Qt.TextSelectableByMouse；MaintenanceDialog.display_identity 生成摘要文本。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.__init__；par_app/maintenance_dialog.py MaintenanceDialog.display_identity

### MAINT-145 保留完整失败提示
- 规则：通信维护操作失败时保留完整失败提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“删除通信「详情」按钮及JSON弹窗，保留可选中复制的身份摘要、完整失败提示及后台日志”
- 状态：待确认
- 现状符合度：符合（MaintenanceDialog.task_finished 失败时 set_state(“操作失败：{完整异常文本}…”, attention=True)，并置 _operation_result 防止被待核对提示覆盖。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-146 保留通信维护后台日志
- 规则：通信维护操作保留后台日志。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“删除通信「详情」按钮及JSON弹窗，保留可选中复制的身份摘要、完整失败提示及后台日志”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 在开始、写入前、完成和失败时调用 database.diagnostic 写入 communication_maintenance 类别日志。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/database.py ParDatabase.diagnostic

### MAINT-147 页面显示及展开列表时枚举系统串口
- 规则：电脑串口在页面显示及展开列表时枚举系统串口。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“电脑串口使用可编辑下拉框，页面显示及展开列表时枚举系统串口”
- 状态：待确认
- 现状符合度：符合（SerialPortComboBox.showEvent 与 showPopup 均调用 refresh_ports；构造时 __init__ 也枚举一次。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.showEvent；par_app/ui.py SerialPortComboBox.showPopup；par_app/ui.py SerialPortComboBox.refresh_ports

### MAINT-148 串口列表显示端口号和设备描述
- 规则：电脑串口列表显示端口号和设备描述。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“列表显示端口号和设备描述，通信只提交端口号”
- 状态：待确认
- 现状符合度：符合（SerialPortComboBox.refresh_ports 以“端口 - 描述”作为条目文本，端口号作为条目数据。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.refresh_ports

### MAINT-149 通信只提交端口号
- 规则：电脑串口用于通信时只提交端口号。
- 来源：业务规则与变更日志_V1.0.2.md 第 146 行「统一设备维护（2026-09-18，当前布局）」“列表显示端口号和设备描述，通信只提交端口号”
- 状态：待确认
- 现状符合度：符合（SerialPortComboBox._select_port 选中条目后把编辑文本设为端口号；port_name 在文本等于条目文本时返回条目数据（端口号），否则返回手输文本；MaintenanceDialog.values 用 port_name 组装连接参数；verify_maintenance.py MaintenanceTests.test_maintenance_port_enumeration_preserves_selection。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SerialPortComboBox.port_name；par_app/ui.py SerialPortComboBox._select_port；par_app/maintenance_dialog.py MaintenanceDialog.values

### MAINT-150 维护事务结束释放连接
- 规则：每项维护事务结束时释放维护连接。
- 来源：业务规则与变更日志_V1.0.2.md 第 299 行「多设备重构：第 6 阶段（2026-09-17）」“每项维护事务含连接、状态、身份、参数及写入共用10秒通信预算，结束释放连接”
- 状态：待确认
- 现状符合度：未验证（CommunicationMaintenance.execute 成功路径调用 client.close() 并置 closed；异常路径在 finally 中补关。例外：成功路径 close() 抛异常时事务转为失败上报，finally 再次关闭的异常被吞；异常路径中 close() 的异常被吞。这两种情况下底层串口是否已释放取决于 ParModbusClient.close，未核实。verify_maintenance.py MaintenanceTests.test_verification_close_failure_does_not_unlock 只覆盖核对时关闭失败不解锁。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/protocol.py ParModbusClient.close

### MAINT-151 新参数核对无需重新上电
- 规则：使用新参数核对无需重新上电。
- 来源：业务规则与变更日志_V1.0.2.md 第 300 行「多设备重构：第 6 阶段（2026-09-17）」“用保存的新参数回读核对身份及通信参数，无需重新上电”
- 状态：待确认
- 现状符合度：符合（CommunicationMaintenance.execute 的 maintenance_verify 分支直接以新参数连接并回读，不要求断电或重新上电；设备状态报告 need_power_cycle 时按硬件异常处理，属另一规则。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance.py CommunicationMaintenance.execute；par_app/maintenance_dialog.py MaintenanceDialog.task_finished

### MAINT-152 诊断曝光时间原始微秒值不变
- 规则：诊断曝光时间的原始微秒值不变，只在界面上换算为毫秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 129 行「统一设备维护（2026-09-18，当前布局）」“曝光时间仅界面按毫秒显示一位小数，原始微秒值及诊断导出不变”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.task_finished 把 payload 原样存入 snapshots；display_diagnostics 只在生成显示文字时计算 exposure_time_us/1000，不修改快照中的 status.exposure_time_us）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### MAINT-153 诊断导出不因界面毫秒显示而改变
- 规则：诊断导出内容不变，曝光时间仍按原始微秒值导出，不跟随界面的毫秒显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 129 行「统一设备维护（2026-09-18，当前布局）」“曝光时间仅界面按毫秒显示一位小数，原始微秒值及诊断导出不变”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.export_diagnostics 把 snapshot=self.snapshots.get(path)（含原始 payload.status.exposure_time_us，单位微秒）直接 json.dumps 写出，不做毫秒换算）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.export_diagnostics

### MAINT-154 通信写入待核对时的锁定逻辑不变
- 规则：通信写入处于待核对状态时，锁定的事务逻辑保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“写后自动核对、待核对锁定、身份校验、关闭保持停止与明确恢复的事务逻辑不变”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.locked 在任一会话 pending 时返回真，此时设备选择被锁定。par_app/maintenance.py CommunicationMaintenance.check_resume 在 pending 时拒绝恢复。verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 中，pending 时断言 dialog.devices 不可用、maintenance_resume_action 不可用、写入按钮不可用。）
- 冲突：无（与 MAINT-015（第133行）、MAINT-067（第151行）内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.locked；par_app/maintenance.py CommunicationMaintenance.check_resume；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks

### MAINT-155 关闭维护窗口后保持停止的逻辑不变
- 规则：关闭维护窗口后采集保持停止，这一事务逻辑不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“写后自动核对、待核对锁定、身份校验、关闭保持停止与明确恢复的事务逻辑不变”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject 只处理校准放弃确认后调用 super().reject()，不调用 leave_maintenance。verify_maintenance.py MaintenanceTests.test_dialog_close_keeps_stopped 断言 reject 后 coordinator._maintenance 仍为真。但该测试用的是 par_app/maintenance_dialog.py MaintenanceDialog，不是统一维护窗口 DeviceMaintenanceDialog。）
- 冲突：无（与 MAINT-066（第151行）内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.reject；verify_maintenance.py MaintenanceTests.test_dialog_close_keeps_stopped

### MAINT-156 须明确恢复才退出维护的逻辑不变
- 规则：退出通信维护、恢复采集必须经过明确的恢复操作，这一事务逻辑不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 147 行「统一设备维护（2026-09-18，当前布局）」“写后自动核对、待核对锁定、身份校验、关闭保持停止与明确恢复的事务逻辑不变”
- 状态：待确认
- 现状符合度：符合（恢复只能走 coordinator.leave_maintenance，入口是 par_app/ui.py MainWindow.resume_after_maintenance。该方法先检查 maintenance_resume_action 是否可用，再弹窗确认，确认后才调用。设置页按钮和 par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.resume_acquisition 都走这个方法。verify_maintenance.py MaintenanceTests.test_exclusive_mode_and_explicit_resume 断言维护期间不采集，显式 leave_maintenance 后才退出维护。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”）（本条不涉及入口位置和禁止条件，见 MAINT-068）；与 MAINT-068（第151行）内容重复，按 R-2-2 合并留待裁决环节
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.resume_after_maintenance；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.resume_acquisition；verify_maintenance.py MaintenanceTests.test_exclusive_mode_and_explicit_resume

### MAINT-157 常规设置页左下方“通信参数”按钮打开独立维护窗口
- 规则：常规设置页左下方的“通信参数”按钮打开独立维护窗口。
- 来源：业务规则与变更日志_V1.0.2.md 第 296 行「多设备重构：第 6 阶段（2026-09-17）」“常规设置页只保留软件连接配置和只读查询；左下方「通信参数」按钮打开独立维护窗口。”
- 状态：已废止 2026-10-17，由 UI-074 替代（D-109 裁决：第296行“左下方‘通信参数’按钮”标为历史废止）
- 现状符合度：不符合（par_app/ui.py MainWindow._build_settings 只建一个“设备维护”按钮，放在右栏 settings_maintenance_row 内右对齐，点击调用 MainWindow.open_device_maintenance 打开统一维护弹窗；设置页没有名为“通信参数”的按钮，入口也不在左下方。现状与第69行一致，与第131行“左下方”和本条都不一致。本条与 MAINT-106 同出第296行，MAINT-106 只承载“常规设置页只做软件连接配置与只读查询”。）
- 冲突：D-109 已裁决：维护入口以第69行（右栏、右对齐、与办公地址底边对齐）为准，第131行“左下方”和第296行“左下方‘通信参数’按钮”标为历史废止；本条已废止，约束由 UI-074 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow.open_device_maintenance
