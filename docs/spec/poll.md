# 轮询、失败处理与对时（POLL）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### POLL-001 未保存配置前不采集
- 规则：用户提交并保存配置之前，后台调度不发起任何采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“首次启动进入设置页，未保存配置前不采集；已有配置引用缺失或损坏数据库时”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 在 not self._config.configured 时跳过轮询；verify_configuration.verify_release_startup 断言未配置时不构造 ParModbusClient。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run

### POLL-002 单采后失败停止开关规则不变
- 规则：单次采集策略不改变原“失败停止”开关规则（各分支规则分别见 POLL-016、POLL-017 等条目，本条不重复展开）。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“冻结/恢复确认、701点完整性、硬件异常停止、失败停止开关及轮询周期保持原规则”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备现在同样走 _mark_failed，原失败停止开关规则对它成立。（V1.0.2 现状：原核对：单次采集改造未改动 PollingCoordinator._mark_failed 的开关判断（verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying）；但所引开关规则在设备完全静默时不成立：冻结路径抛 AcquisitionResumeError 触发全局锁停，不走 _mark_failed（内部文档 BUG-1，旧仓库 #3），详见 POLL-017。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring；tests/qt/test_polling_silent_device.py::test_gateway_reporting_the_target_silent_is_an_ordinary_failure
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py MAX_CONSECUTIVE_FAILURES

### POLL-003 单采后轮询周期规则不变
- 规则：单次采集策略不改变原轮询周期规则（原规则见 POLL-036、POLL-037）。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“冻结/恢复确认、701点完整性、硬件异常停止、失败停止开关及轮询周期保持原规则”；原轮询周期规则见第 188 行「多设备重构：第 2 阶段（2026-09-17）」“总周期固定为40~3600秒，与设备数量无关”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-01 已修复（PR #18）：BusConfig.from_dict 拒绝非有限周期（NaN、±Infinity、1e309 等浮点溢出，以及 float() 转出这些值的字符串如 "inf"）并抛 ValueError（消息含字段名 poll_cycle_seconds），AppConfigStore.load_for_startup 转为 StartupConfigurationError，启动时弹出“配置或数据库不可用”对话框并不开始采集，用户可选择进入设置按默认值重新配置（与 D-141 配置文件不可读同一流程）；有限的越界数值仍按原 min/max 钳位到 40/3600 秒。（V1.0.2 中 ±Infinity 被钳到 3600/40 秒，修复后按坏配置拒绝：按阶段一预授权采用 复审与审计 B5 的推荐，即 内部文档 第 60 号裁决（涉及 PR #18）。）（V1.0.2 现状：有限数值路径符合：AppConfig.effective_poll_cycle_seconds 用 min/max 夹在 MIN_POLL_CYCLE_SECONDS=40 与 MAX_POLL_CYCLE_SECONDS=3600 之间（verify_polling.py PollingTests.test_fixed_cycle_limits）。例外：配置文件中 poll_cycle_seconds 为 NaN 时，BusConfig.from_dict 的 float() 接受 NaN，min/max 钳位仍返回 NaN（经 AppConfigStore.load 本地复现）；PollingCoordinator.run 首轮后 _next_cycle_at = max(now + NaN, monotonic()) 为 NaN，now >= NaN 恒为假，此后不再轮询。界面 interval 微调框范围为40–3600，不会产生 NaN，只有手改或损坏的配置文件会触发。）
- 冲突：缺陷：配置文件中轮询周期为 NaN 时钳位失效，首轮后永久停止轮询且无提示，待建 issue（DEF-01，已修复（PR #18））
- 验证：tests/unit/test_poll_cycle_config.py::test_startup_rejects_non_finite_poll_cycle_with_visible_reason；tests/unit/test_poll_cycle_config.py::test_finite_poll_cycle_keeps_existing_clamp
- 代码锚点：par_app/models.py AppConfig.effective_poll_cycle_seconds；par_app/models.py BusConfig.from_dict；par_app/coordinator.py PollingCoordinator.run

### POLL-004 多设备共用总线须按总耗时评估周期
- 规则：多台设备共用一条总线时，须按各设备实际总耗时评估并设置轮询周期。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“不并发、不积压补跑；多设备共用总线须按实际总耗时评估周期。”
- 状态：待确认
- 现状符合度：未验证（本条是对操作者设置周期的要求，软件中无对应实现：不估算设备总耗时，保存配置时也不校验或提示；AppConfig.min_poll_cycle_seconds 恒返回固定下限40秒，与设备数无关，不是本条的实现。是否满足须由现场人工验收确认。）
- 冲突：D-107 已裁决：第105行的不变量（预算 ≤ 周期 − 2 秒 − 余量、启用第二台前须核算）随40秒方案作废，改为“超时顺延、不积压”（本条为第27行对操作者设置周期的要求，不随第105行作废）
- 验证：冻结待确认
- 代码锚点：无：操作者现场评估要求，软件无对应实现

### POLL-005 本轮超时则下一轮顺延，不并发不补跑
- 规则：本轮耗时达到或超过轮询周期时，下一轮在本轮结束后立即顺延开始，不并发执行、不积压补跑。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“若本轮耗时达到或超过周期，下一轮顺延，不并发、不积压补跑”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 单线程串行，_next_cycle_at=max(now+cycle, _clock.monotonic())；verify_polling.py::PollingTests::test_cycle_starts_and_connection_lifetime（45秒耗时→0/45.05/90.1（时间取自注入的 Clock，测试注入 FakeClock））。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run

### POLL-006 用户设置的轮询周期不被采集预算改写
- 规则：采集预算调整不改变用户设置的轮询周期。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“维护/诊断预算10秒、单帧超时1.5秒、恢复清理独立预算2秒及用户设置的轮询周期不变”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._cycle_seconds 直接取 AppConfig.effective_poll_cycle_seconds，与预算常量无关。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._cycle_seconds；par_app/models.py AppConfig.effective_poll_cycle_seconds

### POLL-007 恢复未确认锁定全部设备采集/对时/重连
- 规则：恢复未确认时，锁定所有设备的后台采集、对时和自动重连。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“锁定所有设备的后台采集、对时和自动重连，其他设备此前已成功完成的记录保留”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。RTU 冻结/恢复命令不等待回显，之后才到达的写回显、混在下一帧读应答里的帧、包超时后清空串口时读到的字节，其中本从站 CRC 正确的应答帧同样计为有效帧（par_app/rtu_frames.py count_slave_frames，在 ParModbusClient._rtu_exchange、_rtu_send_without_waiting_response、_drain_late_response 调用；网关 0x0A/0x0B 与校验错误的字节仍不计；PR #29 复审 blocker 修复）。RTU 事务开始前已在串口缓冲区里的字节（例如更早一次对时迟到的写回显）属于更早的交换，ParModbusClient.read_spectrum_transaction 在发出第一条命令前读掉丢弃、不计数（裁决 37“整次事务中”；PR #29 评审 统一复审 major 修复）。锁停范围收窄为有应答但停止/恢复状态不一致（确认停止后在恢复阶段失联、未停止但有应答后在恢复阶段失联、恢复后仍停在1、TCP 只回写应答、RTU 只回写回显）；整次无应答的设备不再锁停。（V1.0.2 现状：有应答但停止/恢复状态不一致时符合：_poll_one 捕获 AcquisitionResumeError→_halt_acquisition 设 _halt_reason 并断开总线；run、_ensure_bus_connected、_sync_time_if_due、_process_tasks 均据 _halt_reason 拒绝；verify_configuration.verify_resume_stop_ui。需修改：整次事务完全无应答的设备，现状同样经 AcquisitionResumeError 进入全局锁停，按裁决应按普通通信失败处理、按周期重试，不锁定其他设备（内部文档 BUG-1，旧仓库 #3）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring；tests/qt/test_polling_silent_device.py::test_answering_device_with_unconfirmed_resume_still_halts_every_device；tests/qt/test_polling_silent_device.py::test_tcp_answering_device_stuck_stopped_is_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_tcp_device_answering_only_writes_is_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_gateway_reporting_the_target_silent_is_an_ordinary_failure；tests/qt/test_polling_silent_device.py::test_device_answering_with_its_own_exception_code_still_halts；tests/qt/test_polling_silent_device.py::test_tcp_device_own_exception_code_is_resume_unconfirmed；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_device_answering_only_writes_still_halts_every_device；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_echo_of_the_extra_resume_counts_as_an_answer；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_late_echo_with_a_bad_crc_does_not_count；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_late_echo_from_another_device_does_not_count；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_late_gateway_exceptions_are_not_frames_from_the_device；tests/qt/test_polling_silent_device_late_echo.py::test_rtu_reply_left_over_from_before_the_transaction_does_not_count；tests/unit/test_rtu_frames.py::test_echo_followed_by_part_of_a_read_reply_still_counts_the_echo；tests/unit/test_rtu_frames.py::test_bytes_that_are_no_frame_from_the_device_count_zero
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._sync_time_if_due；par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/rtu_frames.py count_slave_frames

### POLL-008 确认提示与保存配置不解除锁定
- 规则：关闭停止提示、保存或应用配置都不得解除采集锁定。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“确认提示、保存配置均不解除锁定；检查通信和设备状态”
- 状态：待确认
- 现状符合度：符合（_apply_config 不清除 _halt_reason；_show_hardware_stop 文案“点击确认只关闭提示…保存配置也不能解除停止”；tests/qt/test_resume_stop_ui.py 在锁停后关闭提示（弹窗 exec_ 返回）、经 MainWindow.save_local_settings 保存并由协调器应用排队的配置后，断言 halt_reason 仍为恢复未确认且 _ensure_bus_connected() 返回 False（不重连总线），该测试在各平台门禁中执行；旧脚本 verify_resume_stop_ui 的同类断言排在 verify_settings_layout 之后，后者在 macOS/Linux 与 windows-latest 门禁因字体度量提前失败（tests/legacy/test_verify_scripts.py 豁免），门禁中执行不到。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：tests/qt/test_resume_stop_ui.py::test_resume_unconfirmed_red_stop_persists_after_saving_config
- 代码锚点：par_app/coordinator.py PollingCoordinator._apply_config；par_app/ui.py MainWindow._show_hardware_stop

### POLL-009 锁停原因写入diagnostics
- 规则：采集锁停时，停止原因须写入（各启用设备的）diagnostics。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“停止原因写入diagnostics并记录DLI中断”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 对每台启用设备 diagnostic("ERROR","acquisition_halted",...)，写库失败收集到 log_errors 并提示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition

### POLL-010 锁停只能检查设备后重启软件解除
- 规则：解除恢复未确认锁停的唯一途径是检查通信与设备状态、必要时重新上电，然后重启软件。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“检查通信和设备状态、必要时重新上电后重启软件”
- 状态：待确认
- 现状符合度：符合（_halt_reason 仅在 PollingCoordinator.__init__ 初始化为 None，运行期无清除路径；maintenance_leave 亦拒绝。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；alpha 档位 1（D-212 问题 8、D-215 问题 5）：“退出并重新启动软件”在 alpha 中对应“停止采集→开始采集”：新协调器的 _halt_reason 为 None，等同重启 V1.0.3；alpha 没有其他解除锁停的途径，不清除硬件锁存
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.__init__；par_app/coordinator.py PollingCoordinator._process_tasks

### POLL-011 锁停时保留其他设备已完成记录
- 规则：恢复未确认锁停时，其他设备此前已成功完成的记录必须保留。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“锁定所有设备的后台采集、对时和自动重连，其他设备此前已成功完成的记录保留”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 仅写诊断、运行状态与DLI中断，不删除或改写记录。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition

### POLL-012 失败停止为每台设备的独立开关
- 规则：“失败停止”是每台设备的独立开关，行为见“失败停止开关（2026-09-30）”。（默认值见 POLL-073；旧配置缺键取默认见 CONF-035。）
- 来源：业务规则与变更日志_V1.0.2.md 第 76 行「设置与导出布局（2026-09-20）」“「失败停止」为每台设备的独立开关，默认不勾选，行为见「失败停止开关（2026-09-30）」”
- 状态：待确认
- 现状符合度：符合（DeviceConfig.auto_stop_on_failure 为逐台字段；设置页每行独立 stop_box，MainWindow._device_row_config 逐行读取；PollingCoordinator._mark_failed 按 state.config 逐台判断；verify_polling.py PollingTests.test_failure_exit_switch_config_round_trip 断言两台设备开关独立保存与读回。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/models.py DeviceConfig；par_app/ui.py MainWindow._device_row_config；par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-013 串口连接失败保留原始异常
- 规则：串口连接失败时，保留原始异常（不以笼统提示替代）。（释放已打开句柄见 POLL-074。）
- 来源：业务规则与变更日志_V1.0.2.md 第 88 行「设置与导出布局（2026-09-20）」“串口连接失败现保留原始异常并释放已打开句柄”
- 状态：待确认
- 现状符合度：符合（ParModbusClient.connect 捕获 serial.SerialException，写 last_connection_error=str(exc)；verify_polling.py PollingTests.test_serial_connection_error_preserved_and_handle_closed。注：只捕获 SerialException；其他异常类型（如参数非法时 pyserial 抛 ValueError）会逃出 connect，由 PollingCoordinator.run 的调度异常分支显示为“调度异常：<原始异常>”，原始文本仍保留。V1.0.2 中这类异常约1秒后重试；PR #33 修复 DEF-02 不改变这条路径（连接在本轮读取任何设备之前，不属于 POLL-036 的轮内异常），仍约1秒重试、提示不变，见 DEF-28 ②。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.connect

### POLL-014 串口错误传到总线提示和采集诊断
- 规则：串口连接失败的原始错误传递到总线状态提示和各设备采集诊断中，不再只显示“总线未连接”。
- 来源：业务规则与变更日志_V1.0.2.md 第 88 行「设置与导出布局（2026-09-20）」“错误传递到总线提示和采集诊断，不再只显示「总线未连接」”
- 状态：待确认
- 现状符合度：符合（_ensure_bus_connected 以 last_connection_error 组成“总线连接失败：…”；_poll_one 在无连接且总线为 error 时把该消息作为 _mark_failed 的 detail 写入 diagnostics；verify_polling 断言 bus_message 与 last_error 含 'error 31'。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-015 通信失败不自动解除维护或硬件停止
- 规则：通信/串口失败及其重试不会自动解除维护模式或硬件停止状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 88 行「设置与导出布局（2026-09-20）」“已退出设备须重启软件后重试；不自动解除维护或硬件停止”
- 状态：待确认
- 现状符合度：符合（_ensure_bus_connected/_poll_all_devices 在 _maintenance 或 _halt_reason 时直接返回；_mark_failed 不触碰 _maintenance/_halt_reason；_halt_reason 在运行期无清除路径。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._halt_acquisition

### POLL-016 勾选失败停止时连续10次失败退出本次采集
- 规则：前提：设备勾选“失败停止”。触发：连续10次失败。期望：该设备退出本次采集。（退出后的重试条件见 POLL-075。）
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“勾选——完全恢复原规则（连续 10 次失败退出本次采集，须重启软件后重试）”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备勾选失败停止时第10轮退出。（V1.0.2 现状：原核对：普通失败路径符合：par_app/coordinator.py PollingCoordinator._mark_failed 在 auto_stop_on_failure 且 failures>=MAX_CONSECUTIVE_FAILURES(10) 时置 excluded，_poll_all_devices 跳过 excluded 设备（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）；但设备完全静默时首轮即因“恢复未确认”全局锁停，到不了第10轮（内部文档 符合性表“勾选失败停止后连续10轮失败退出”行）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_with_failure_stop_exits_on_the_tenth_round_after_ticking
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py MAX_CONSECUTIVE_FAILURES；par_app/coordinator.py PollingCoordinator._poll_all_devices

### POLL-017 未勾选失败停止时连续失败不退出采集
- 规则：前提：设备未勾选“失败停止”（默认）。触发：连续失败。期望：只累加连续失败计数，不退出。（不进入红色“采集停止中”属界面行为，另在 UI 领域登记；持续重连重试见 POLL-076；恢复后自动继续采集见 POLL-077。）
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“不勾选（默认）——连续失败只累加计数，不退出、不进入红色「采集停止中」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备未勾选时连续失败只累加计数（12轮后为12），不退出、不锁停。（V1.0.2 现状：原核对：普通异常路径符合（par_app/coordinator.py PollingCoordinator._mark_failed 未勾选时 excluded 恒 False，verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying）；但设备完全静默时停止/恢复均无法确认，read_spectrum_transaction 抛 AcquisitionResumeError，_poll_one 转入 _halt_acquisition 全局锁停，既不累加计数也停止全部采集（内部文档 BUG-1，有复现脚本）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._halt_acquisition

### POLL-018 取消勾选并保存后立即解除退出状态
- 规则：前提：设备已勾选“失败停止”且已因连续失败退出本次采集。触发：用户取消勾选并保存配置。期望：立即解除退出状态，回到按周期重试，无需重启软件。
- 来源：业务规则与变更日志_V1.0.2.md 第 115 行「失败停止开关（2026-09-30）」“勾选时若已退出，取消勾选并保存配置会立即解除退出状态、回到按周期重试，无需重启软件”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._rebuild_states 对同库既有状态在 excluded 且未勾选时清除 excluded 并置 warning；由 par_app/device_hub.py DeviceHub.apply → apply_config → _apply_config 触发；测试 verify_polling.py test_failure_exit_latch_clears_when_switch_unchecked。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/device_hub.py DeviceHub.apply

### POLL-019 改名或禁用再启用不解除退出状态
- 规则：前提：设备已勾选“失败停止”且已退出。触发：仅修改设备名称，或先禁用再启用该设备并保存（开关仍勾选）。期望：退出状态保持，仍须重启软件。
- 来源：业务规则与变更日志_V1.0.2.md 第 115 行「失败停止开关（2026-09-30）」“失败计数与历史 diagnostics 保留。仅改名称或禁用再启用不会解除退出状态”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._rebuild_states 以数据库路径复用旧运行态，仅在未勾选时清 excluded；par_app/device_hub.py DeviceHub.apply 将 database_path 固化为绝对路径，改名不改库路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/device_hub.py DeviceHub.apply

### POLL-020 解除退出状态时保留失败计数与历史诊断
- 规则：取消勾选解除退出状态时，不清零该设备的连续失败计数，也不删除或改写已有 diagnostics 记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 115 行「失败停止开关（2026-09-30）」“失败计数与历史 diagnostics 保留”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._rebuild_states 仅改 excluded/level/message，不重置 failures，不触碰 diagnostics 表。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states

### POLL-021 仅勾选时失败才置退出标志
- 规则：_mark_failed 只有在设备勾选“失败停止”时才可能置 state.excluded；未勾选时任何次数的失败都不置 excluded。
- 来源：业务规则与变更日志_V1.0.2.md 第 116 行「失败停止开关（2026-09-30）」“`PollingCoordinator._mark_failed` 仅在勾选时置 `state.excluded`”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._mark_failed：state.excluded = stop_on_failure and failures >= MAX_CONSECUTIVE_FAILURES。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-022 未勾选时失败消息文案
- 规则：未勾选“失败停止”的设备每次失败时，状态消息为“连续第 N 次尝试失败：<原因>（未启用失败停止，将继续按周期重试）”，N 为当前连续失败次数。
- 来源：业务规则与变更日志_V1.0.2.md 第 116 行「失败停止开关（2026-09-30）」“未勾选时消息为「连续第 N 次尝试失败：…（未启用失败停止，将继续按周期重试）」”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._mark_failed 未勾选分支 message 与原文一致。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-023 未勾选时每条失败按原格式写一条诊断
- 规则：未勾选“失败停止”时，每条失败仍按原格式写一条 diagnostics。（该记录 excluded 取值见 POLL-078。）
- 来源：业务规则与变更日志_V1.0.2.md 第 116 行「失败停止开关（2026-09-30）」“每条失败仍按原格式写一条 diagnostics，其 `excluded` 恒为 `False`”
- 状态：待确认
- 现状符合度：符合（按 D-123 裁决，“一条”指 category=communication 的原格式记录：PollingCoordinator._mark_failed 每次失败写一条 communication 记录；总线已连接而采集失败时，PollingCoordinator._capture_once 另写的一条 category=acquisition“采集失败”记录按裁决保留，不计入本条。）
- 冲突：D-123 已裁决：“一条”指 category=communication 的原格式记录，acquisition 类“采集失败”记录保留，日量估计从约2160条/天改为约4320条/天
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/database.py ParDatabase.diagnostic

### POLL-024 硬件全局停止与异常锁存不受失败停止开关影响
- 规则：探头未初始化或要求重新上电引发的硬件全局停止，以及硬件异常锁存，其触发与解除都不随“失败停止”开关是否勾选而变化。
- 来源：业务规则与变更日志_V1.0.2.md 第 117 行「失败停止开关（2026-09-30）」“探头未初始化或要求重新上电的硬件全局停止、维护模式暂停、硬件异常锁存均不随本开关变化”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._halt_acquisition 与 _poll_one 的 HardwareStateError 分支不读取 auto_stop_on_failure。按 D-101 裁决，有应答但状态不一致的“恢复未确认”锁停同样不随开关变化；整次完全无应答改按普通通信失败处理（待修复，见 POLL-007）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/coordinator.py PollingCoordinator._poll_one

### POLL-025 全部设备无响应时每轮重连一次
- 规则：前提：全部设备长时间无响应。期望：每轮重连一次。（重连后释放连接见 POLL-079。）
- 来源：业务规则与变更日志_V1.0.2.md 第 118 行「失败停止开关（2026-09-30）」“全部设备长时间无响应时每轮重连一次后释放连接”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。整条链路静默时不再锁停，每轮末全部离线断开、下一轮重连（12轮重开串口12次）。（V1.0.2 现状：原核对：机制本身符合：PollingCoordinator.run 每周期调用一次 _ensure_bus_connected，连接失败另受 BUS_RETRY_INTERVAL_SECONDS=5 秒间隔限制，一周期内只尝试一次；但设备完全静默时首轮即因“恢复未确认”全局锁停，_ensure_bus_connected 在 _halt_reason 非空时直接返回，不再重连（内部文档 BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_whole_link_silent_records_each_device_and_reconnects_every_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._ensure_bus_connected

### POLL-026 失败后不做自动参数搜索
- 规则：设备通信失败或全部无响应时，软件不自动扫描或切换串口、波特率、地址等通信参数，只使用用户指定参数重试。
- 来源：业务规则与变更日志_V1.0.2.md 第 118 行「失败停止开关（2026-09-30）」“每轮重连一次后释放连接，不做自动参数搜索”
- 状态：待确认
- 现状符合度：符合（par_app/coordinator.py PollingCoordinator._ensure_bus_connected 只用 self._config.bus 构建连接，代码中无扫描逻辑。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._bus_connection

### POLL-027 持续失败时每轮写一条诊断（约2160条/天）
- 规则：未勾选时设备持续失败，每轮仍写一条 diagnostics；40 秒周期下约 2160 条/天，属已知代价。
- 来源：业务规则与变更日志_V1.0.2.md 第 118 行「失败停止开关（2026-09-30）」“且每轮失败仍写一条 diagnostics（40 秒周期约 2160 条/天）”
- 状态：待确认
- 现状符合度：符合（按 D-123 裁决，“一条”指 communication 类记录：持续失败时 PollingCoordinator._mark_failed 每轮写一条 communication 记录，40 秒周期下约 2160 条/天；总线已连接而设备采集失败时 PollingCoordinator._capture_once 另写一条 acquisition 记录，按裁决保留，两类合计约 4320 条/天，与裁决更新后的日量估计一致。）
- 冲突：D-123 已裁决：“一条”指 category=communication 的原格式记录，acquisition 类“采集失败”记录保留，日量估计从约2160条/天改为约4320条/天
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-028 未勾选时失败计数无上限
- 规则：未勾选“失败停止”时，失败计数无上限增长。
- 来源：业务规则与变更日志_V1.0.2.md 第 118 行「失败停止开关（2026-09-30）」“不勾选时失败计数无上限增长，且每轮失败仍写一条 diagnostics”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备的失败计数随轮次增长（12轮后为12）。（V1.0.2 现状：D-156 已裁决接受采集成功即清零（PollingCoordinator._mark_ok 不分是否勾选），该分支不再是不符合的依据。原核对：普通失败路径符合：par_app/coordinator.py PollingCoordinator._mark_failed 未勾选时 failures 只递增、无上限（verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying 累加到12）；但设备完全静默时 AcquisitionResumeError 走 _halt_acquisition 而非 _mark_failed，计数不增长且全局锁停（BUG-1）。另：采集成功时 PollingCoordinator._mark_ok 不区分是否勾选，一律置 failures = 0。原文只对勾选设备规定“第10次前恢复成功，连续失败计数清零”（第204行，见 POLL-058）；未勾选设备恢复后是否清零，第114、118行都没有写，这一分支只存在于代码中，见 D-156。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）；D-156 已裁决：恢复成功后失败计数清零，不论是否勾选；第118行“无上限增长”指持续失败期间不封顶
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/coordinator.py PollingCoordinator._poll_one

### POLL-029 验收：勾选并保存后10轮退出与09-20记录一致
- 规则：验收：勾选“失败停止”并保存后，10轮退出行为与2026-09-20记录一致。（重启后计数清零见 POLL-080。）
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“勾选并保存后，10 轮退出行为与 2026-09-20 记录一致，重启软件后计数清零重新尝试”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。以静默设备复现：勾选并保存后连续10轮失败，第10轮退出。（V1.0.2 现状：原核对：普通失败路径符合：PollingCoordinator._mark_failed 第10次失败置 excluded（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）；设备完全静默时首轮即全局锁停，到不了10轮（内部文档）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_with_failure_stop_exits_on_the_tenth_round_after_ticking
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py MAX_CONSECUTIVE_FAILURES

### POLL-030 验收：默认状态断通信12轮后接回设备下一轮自动恢复
- 规则：验收：默认状态（未勾选“失败停止”）下断开设备通信12轮后，接回设备，下一轮自动恢复。（同一手测场景中的界面文案、琥珀色状态与不出现红色全局停止属界面行为，另在 UI 领域登记。）
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“默认状态下断开设备通信 12 轮后……不出现红色全局停止；接回设备后下一轮自动恢复”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默12轮后接回设备，下一轮先补发恢复命令再采集，采集成功、计数清零。（V1.0.2 现状：原核对：仅串口本身打不开、走 _poll_one→_mark_failed 路径时：未 excluded 设备每周期 _poll_one，接回后成功即 _mark_ok，可满足；但物理断开 RS485 时设备静默，首轮即“恢复未确认”全局锁停，run() 在 _halt_reason 非空时跳过轮询，接回设备也不会恢复，只能重启软件（内部文档 BUG-1 复现）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_recovered_device_gets_one_resume_before_its_first_capture
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/coordinator.py PollingCoordinator.run；par_app/protocol.py ParModbusClient.set_slave_id

### POLL-031 勾选=10次退出路径须有显式勾选的回归守护
- 规则：原本依赖默认退出规则的回归测试（test_ten_failures_exit_and_restart、test_healthy_device_continues_after_other_exits 及 verify_configuration.py）须显式勾选“失败停止”，以继续验证“勾选=10 次退出”路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 120 行「失败停止开关（2026-09-30）」“已显式勾选该开关，继续守住「勾选=10 次退出」路径”
- 状态：待确认
- 现状符合度：符合（verify_polling.py test_ten_failures_exit_and_restart 与 test_healthy_device_continues_after_other_exits 构造 DeviceConfig 时 auto_stop_on_failure=True；verify_configuration.py 断言 auto_stop_on_failure is True。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：verify_polling.py PollingTests.test_ten_failures_exit_and_restart；verify_polling.py PollingTests.test_healthy_device_continues_after_other_exits；verify_configuration.py main

### POLL-032 不自动搜索串口
- 规则：软件不自动搜索串口；连接只使用用户配置的串口。
- 来源：业务规则与变更日志_V1.0.2.md 第 170 行「多设备重构：第 1 阶段（2026-09-17）」“已统一为 DeviceHub / PollingCoordinator 入口，移除旧单设备服务及自动串口搜索”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._ensure_bus_connected 只用 bus.serial_port 连接；MainWindow.refresh_serial_ports 仅枚举并提示“请手动选择；不会自动搜索或切换端口”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/ui.py MainWindow.refresh_serial_ports

### POLL-033 统一DeviceHub与调度器入口
- 规则：采集统一经DeviceHub/PollingCoordinator入口运行，旧的单设备采集服务已移除。
- 来源：业务规则与变更日志_V1.0.2.md 第 170 行「多设备重构：第 1 阶段（2026-09-17）」“已统一为 DeviceHub / PollingCoordinator 入口，移除旧单设备服务及自动串口搜索”
- 状态：待确认
- 现状符合度：符合（main.py 装配 AppConfigStore→DeviceHub→MainWindow；par_app 中无旧 AcquisitionService/acquisition.py，ActiveDeviceService 仅为信号适配门面。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub；par_app/coordinator.py PollingCoordinator；par_app/device_hub.py ActiveDeviceService

### POLL-034 保存配置后持续保存数据
- 规则：保存配置后，采集数据持续保存到数据库。（实时页面出现光谱属界面行为，另在 UI 领域登记。）
- 来源：业务规则与变更日志_V1.0.2.md 第 179 行「多设备重构：第 1 阶段（2026-09-17）」“保存配置，确认实时页面出现光谱并持续保存数据”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._apply_config 重建状态并将 _next_cycle_at 置 0，run 立即按周期采集；_capture_once 每次成功写 save_acquisition 并发 acquisition_saved。设备静默触发全局锁停（BUG-1）后不再保存，属 D-101 裁决的 DEF-10 修复范围（DEF-10 已修复（PR #29）），不在本条手测前提内。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._apply_config；par_app/coordinator.py PollingCoordinator._capture_once

### POLL-035 串口不可用时不自动换用其他端口
- 规则：串口不可用时，软件不能自动换用其他端口。
- 来源：业务规则与变更日志_V1.0.2.md 第 182 行「多设备重构：第 1 阶段（2026-09-17）」“退出再启动，确认恢复已保存配置；串口不可用时不能自动换用其他端口”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._ensure_bus_connected 只用 self._config.bus 中的配置串口建连，无换口逻辑；MainWindow.refresh_serial_ports 端口消失时保留原输入不切换。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/ui.py MainWindow.refresh_serial_ports

### POLL-036 周期从每轮开始计时，提前完成则等待
- 规则：轮询周期从每轮开始时刻计时；本轮正常提前完成时，等待周期剩余时间后再开始下一轮。
- 来源：业务规则与变更日志_V1.0.2.md 第 188 行「多设备重构：第 2 阶段（2026-09-17）」“从每轮开始计时，正常提前完成时等待剩余周期”
- 状态：待确认
- 现状符合度：不符合（正常路径符合：PollingCoordinator.run 在轮前记 now，_next_cycle_at = max(now + cycle, _clock.monotonic())；verify_polling.py PollingTests.test_cycle_starts_and_connection_lifetime（耗时12秒时开始时刻0/40/80（时间取自注入的 Clock，测试注入 FakeClock））。例外：轮内异常逃逸到 run() 的 except 分支时 _next_cycle_at 未更新，约1秒后立即重采全部设备，该轮的周期没有从开始时刻计满（内部文档 B3，repro_core.py::test_B3：60秒周期下开始时刻 100000.0/100001.0）；周期为 NaN 时首轮后不再开始下一轮（同报告 B5，见 POLL-037；DEF-01 已修复（PR #18），NaN 周期在加载配置时即被拒绝）。fix/polling-task-skip 分支（DEF-03）新增的轮内 apply_config 失败路径先单独处理为下一轮从本轮开始计满一个周期。PR #33 修复 DEF-02 后统一为一套：本轮进入采集后无论正常结束还是异常逃逸到 run()（含轮内 apply_config 失败、对时结果写库失败），都按 max(本轮开始 + 本轮配置的周期, 当前时刻) 安排下一轮；建立总线连接时抛异常（客户端构造失败或 connect() 抛非 SerialException）发生在读取任何设备之前，不在本条范围，仍同 V1.0.2 约1秒后重试（见 DEF-28 ②）；只有 apply_config 成功中断本轮时保留“下一轮立即开始”（POLL-081）。异常路径仍显示“调度异常”（D-178 B 修复后，轮内 apply_config 失败改为“应用配置失败：<原因>”并恢复原配置，见 CONF-056，PR #43）、断开总线、调度线程不退出。合并前不改基线判定；NaN 部分不在本次范围；旧 #10 其余两项见 DEF-28。）
- 冲突：缺陷：轮内异常逃逸到 run() 后下一轮约1秒即开始，周期未从本轮开始计满，待建 issue（DEF-02 已修复（PR #33）；NaN 周期见 DEF-01）
- 验证：tests/qt/test_polling_exception_cycle.py::test_time_sync_write_failure_does_not_reread_devices_within_the_cycle；tests/qt/test_polling_exception_cycle.py::test_client_constructor_failure_keeps_the_v102_one_second_retry；tests/qt/test_polling_exception_cycle.py::test_connect_raising_non_serial_exception_keeps_the_v102_one_second_retry；tests/qt/test_polling_task_interleave.py::test_failed_apply_config_mid_round_keeps_the_cycle_timed_from_the_round_start
- 代码锚点：par_app/coordinator.py PollingCoordinator.run

### POLL-037 总周期固定40~3600秒与设备数无关
- 规则：轮询总周期固定为40~3600秒，与设备数量无关。
- 来源：业务规则与变更日志_V1.0.2.md 第 188 行「多设备重构：第 2 阶段（2026-09-17）」“总周期固定为40~3600秒，与设备数量无关”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-01 已修复（PR #18）：BusConfig.from_dict 拒绝非有限周期（NaN、±Infinity、1e309 等浮点溢出，以及 float() 转出这些值的字符串如 "inf"）并抛 ValueError（消息含字段名 poll_cycle_seconds），AppConfigStore.load_for_startup 转为 StartupConfigurationError，启动时弹出“配置或数据库不可用”对话框并不开始采集，用户可选择进入设置按默认值重新配置（与 D-141 配置文件不可读同一流程）；有限的越界数值仍按原 min/max 钳位到 40/3600 秒。（V1.0.2 中 ±Infinity 被钳到 3600/40 秒，修复后按坏配置拒绝：按阶段一预授权采用 复审与审计 B5 的推荐，即 内部文档 第 60 号裁决（涉及 PR #18）。）（V1.0.2 现状：有限数值路径符合：models.py MIN_POLL_CYCLE_SECONDS=40、MAX_POLL_CYCLE_SECONDS=3600，AppConfig.effective_poll_cycle_seconds 夹在其间，AppConfig.min_poll_cycle_seconds 恒返回40与设备数无关；verify_polling.py PollingTests.test_fixed_cycle_limits 对1~4台断言。例外：配置文件 poll_cycle_seconds 为 NaN 时 BusConfig.from_dict 接受 NaN，钳位返回 NaN，周期落在范围之外，首轮后永久停止采集且无提示（本地经 AppConfigStore.load 复现；内部文档 B5）。超出范围按边界截取是代码行为，原文未规定，不作为本条规则。）
- 冲突：缺陷：配置文件中轮询周期为 NaN 时周期落在 40~3600 秒范围之外，首轮后永久停止采集，待建 issue（DEF-01，已修复（PR #18））
- 验证：tests/unit/test_poll_cycle_config.py::test_startup_rejects_non_finite_poll_cycle_with_visible_reason；tests/unit/test_poll_cycle_config.py::test_finite_poll_cycle_keeps_existing_clamp；tests/unit/test_poll_cycle_config.py::test_model_never_yields_non_finite_cycle
- 代码锚点：par_app/models.py MIN_POLL_CYCLE_SECONDS；par_app/models.py MAX_POLL_CYCLE_SECONDS；par_app/models.py AppConfig.effective_poll_cycle_seconds；par_app/models.py BusConfig.from_dict

### POLL-038 本轮超周期时下一轮顺延不补跑
- 规则：本轮耗尽预算及收尾导致总耗时超过周期时，下一轮顺延开始，不积压、不补跑。
- 来源：业务规则与变更日志_V1.0.2.md 第 188 行「多设备重构：第 2 阶段（2026-09-17）」“耗尽预算及收尾可能超过40秒周期；下一轮顺延，不积压补跑”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 单线程串行，本轮结束后 _next_cycle_at = max(now + cycle, _clock.monotonic())，超周期时下一轮在本轮结束后立即开始，只保留一个下次时刻，不并发、不积压；verify_polling.py PollingTests.test_cycle_starts_and_connection_lifetime（45秒耗时时开始时刻 0/45.05/90.1（时间取自注入的 Clock，测试注入 FakeClock））。超周期轮内异常逃逸到 except 分支时 _next_cycle_at 保持旧值（已过期），约1秒后开始下一轮，仍是一次顺延、无补跑。审计 robustness-core B3 是60秒周期内约1秒即异常的提前重采，不满足本条“超过周期”的前提，归 POLL-036。fix/polling-task-skip 分支补了经真实任务队列和 run() 的用例：轮内任务超时使本轮超周期后，下一轮在本轮结束后立即开始，再下一轮从新的轮起点计满周期，中间无补采：tests/qt/test_polling_task_interleave.py::test_round_stretched_past_the_cycle_by_tasks_is_followed_at_once_without_catch_up。PR #33 修复 DEF-02 后，异常路径同样按 max(本轮开始 + 周期, 当前时刻) 更新，超周期时取当前时刻，except 分支等待约1秒后开始下一轮，结果不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run

### POLL-039 每台设备采集预算40秒
- 规则：每台设备的采集预算为40秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 188 行「多设备重构：第 2 阶段（2026-09-17）」“当前每台采集预算40秒，耗尽预算及收尾可能超过40秒周期”
- 状态：已废止 2026-10-17，由 ACQ-060 替代（与 ACQ-060 摘录自同一行原文，重复登记；第三道关口审查后保留 ACQ 条目）
- 现状符合度：符合（coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS = 40.0；预算实际施加于 PollingCoordinator._capture_once 的 client.acquisition_budget(self._acquisition_budget(), …) 上下文，由 ParModbusClient.acquisition_budget 设定 deadline。领域归属：本条性质属采集事务预算，已另提 ACQ 同源条目，誊抄阶段不合并。）
- 冲突：无；本条已废止，约束由 ACQ-060 承接
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS；par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget

### POLL-040 单台失败不因全部未在线判断断开总线
- 规则：单台失败不再通过“全部未在线”判断断开总线。
- 来源：业务规则与变更日志_V1.0.2.md 第 189 行「多设备重构：第 2 阶段（2026-09-17）」“单台失败不再通过「全部未在线」判断断开总线”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。单台静默设备不再锁停或断开总线，另一台在线时整个过程只打开一次串口。（V1.0.2 现状：按 D-112 裁决 (a)：还有设备在线就不断开总线、全部离线时断开，PollingCoordinator._poll_all_devices 末尾“所有启用设备均不在线即 _disconnect_bus”与之一致，两台中一台失败、另一台在线时不断开（verify_polling.py PollingTests.test_failed_first_device_does_not_disconnect_next）；只登记一台时单台失败即断开、下一轮重连，也与裁决一致。需修改：单台设备完全静默时现状触发“恢复未确认”全局锁停并断开总线，其他设备在线也会断开（BUG-1），按 D-101 裁决应按普通失败处理。）
- 冲突：D-112 已裁决：还有设备在线就不断开总线；全部离线时断开、下一轮重连，只登记一台时这台失败后每轮重开串口；D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-041 正常轮询之间保持同一总线连接
- 规则：正常轮询的各轮之间保持同一总线连接，不在每轮或每台设备后重新打开。
- 来源：业务规则与变更日志_V1.0.2.md 第 189 行「多设备重构：第 2 阶段（2026-09-17）」“每台读完立即读下一台，正常轮询之间保持同一连接”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._ensure_bus_connected 在 _client 存在时直接复用，_poll_one 仅 set_slave_id 切换地址；test_cycle_starts_and_connection_lifetime 断言多轮只断开一次。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/protocol.py ParModbusClient.set_slave_id

### POLL-042 每台读完立即读下一台
- 规则：一轮中每台设备读取完成后立即读取下一台设备，中间不插入等待。
- 来源：业务规则与变更日志_V1.0.2.md 第 189 行「多设备重构：第 2 阶段（2026-09-17）」“每台读完立即读下一台，正常轮询之间保持同一连接”
- 状态：待确认
- 现状符合度：不符合（按 R-2-1 指 V1.0.2 基线：审计 requirements BUG-2 / robustness-core B2，PollingCoordinator._poll_all_devices 每台前检查任务队列，非空即 return，本轮剩余设备整周期漏采、对时也被跳过（有复现脚本 repro_core.py::test_B2）。PR #16 修复 DEF-03 后：设备之间若有排队任务，就地执行后继续本轮剩余设备和对时；任务执行期间下一台的读取被推迟，例如 comm_read 用满 10 秒预算时推迟约 10 秒，排了多个任务时按任务累加。D-161 已裁决这种推迟不算“插入等待”，因此修复分支合并后符合；该分支未合并前，主线仍按基线判不符合。）
- 冲突：D-161 已裁决：设备之间就地处理用户发起的任务、下一台读取因此推迟，不算“插入等待”，维持修复分支做法（负责人，2026-10-17，按推荐）；缺陷：轮询中途有任务入队时本轮剩余设备被跳过，未“读完立即读下一台”，待建 issue（DEF-03 已修复（PR #16））
- 验证：tests/qt/test_polling_task_interleave.py::test_task_queued_during_second_device_is_handled_and_round_continues；tests/qt/test_polling_task_interleave.py::test_task_queued_during_time_sync_does_not_skip_remaining_syncs；tests/qt/test_polling_task_interleave.py::test_run_loop_collects_every_device_in_the_cycle_a_task_arrived；tests/qt/test_polling_task_interleave.py::test_stop_while_a_mid_round_task_runs_ends_the_round；tests/qt/test_polling_task_interleave.py::test_task_that_uses_up_its_budget_does_not_end_the_round；tests/qt/test_polling_task_interleave.py::test_hardware_latch_raised_by_a_mid_round_task_ends_the_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices

### POLL-043 状态光谱光度参数与时钟共用40秒预算
- 规则：自2026-10-11起，每台设备一轮中的状态读取、701点光谱、光度参数及设备时间读取共用同一个40秒采集轮预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 190 行「多设备重构：第 2 阶段（2026-09-17）」“状态、701点光谱、光度参数及设备时间读取共用40秒采集轮预算（2026-10-11起）”
- 状态：已废止 2026-10-17，由 ACQ-061 替代（与 ACQ-061 摘录自同一行原文，重复登记；第三道关口审查后保留 ACQ 条目）
- 现状符合度：符合（PollingCoordinator._capture_once 在同一 client.acquisition_budget(40) 内执行 read_spectrum_transaction 与 read_standard_time；verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture。领域归属：本条性质属采集事务预算，已另提 ACQ 同源条目，誊抄阶段不合并。）
- 冲突：无；本条已废止，约束由 ACQ-061 承接
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget

### POLL-044 写库耗时不计入通信超时不误判失败
- 规则：SQLite写库耗时不计入通信超时；不得出现记录已成功入库又因写库耗时被标为通信失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 191 行「多设备重构：第 2 阶段（2026-09-17）」“计算及SQLite写库不计入通信超时，仍计入整轮耗时；不再出现先成功入库又因写库耗时标为通信失败”
- 状态：待确认
- 现状符合度：符合（save_acquisition 位于 acquisition_budget 之外；verify_polling.py test_slow_database_is_not_communication_timeout（写库12秒仍 online、failures=0）。另：审计 robustness-core 其他#1 指出 _mark_ok 写库“失败”（非耗时）会把成功采集再记一次失败。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/coordinator.py PollingCoordinator._mark_ok

### POLL-045 指标计算不计入通信超时
- 规则：采集后的指标计算耗时不计入通信超时预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 191 行「多设备重构：第 2 阶段（2026-09-17）」“计算及SQLite写库不计入通信超时，仍计入整轮耗时”
- 状态：待确认
- 现状符合度：不符合（PollingCoordinator._capture_once 中 software_metrics 在 acquisition_budget 上下文内、read_standard_time 之前执行，计算耗时会消耗时钟读取可用的预算（结构性偏差，实际影响极小）。）
- 冲突：缺陷：指标计算在采集通信预算内执行，计算耗时占用时钟读取的通信预算，待建 issue（DEF-04）
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/math_ops.py software_metrics

### POLL-046 计算及写库仍计入整轮耗时
- 规则：计算及SQLite写库耗时仍计入整轮耗时（影响下一轮开始时刻）。
- 来源：业务规则与变更日志_V1.0.2.md 第 191 行「多设备重构：第 2 阶段（2026-09-17）」“计算及SQLite写库不计入通信超时，仍计入整轮耗时”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 以轮前 now 计时，_next_cycle_at = max(now + cycle, _clock.monotonic())，轮内全部耗时都计入。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run

### POLL-047 冻结路径为解冻预留时间
- 规则：所有波特率的采集冻结读取路径都须在采集预算中为解冻（恢复采集）预留时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“所有波特率的采集冻结路径预留解冻时间，超时后仍允许最多2秒独立清理”
- 状态：已废止 2026-10-17，由 ACQ-062 替代（与 ACQ-062 摘录自同一行原文，重复登记；第三道关口审查后保留 ACQ 条目）
- 现状符合度：符合（ParModbusClient.read_spectrum_transaction 冻结读取段使用 communication_budget(available - 2.0)，不区分波特率；verify_polling.py PollingTests.test_all_transports_freeze_before_read_and_confirm_resume、PollingTests.test_acquisition_thaws_after_budget_exhaustion。领域归属：本条属冻结事务约束，已另提 ACQ 同源条目，誊抄阶段不合并。）
- 冲突：无；本条已废止，约束由 ACQ-062 承接
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### POLL-048 对时放在一轮设备读取之后
- 规则：设备对时在一轮所有设备读取完成之后进行。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“对时放在一轮设备读取之后，每台独立2秒预算”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._poll_all_devices 先遍历 _poll_one，再遍历在线设备 _sync_time_if_due。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._sync_time_if_due

### POLL-049 每台对时独立2秒预算
- 规则：每台设备的对时使用独立的2秒通信预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“对时放在一轮设备读取之后，每台独立2秒预算”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._sync_time_if_due 以 communication_budget(2.0) 包裹 sync_time；ParModbusClient.sync_time 默认 timeout_seconds=2.0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._sync_time_if_due；par_app/protocol.py ParModbusClient.sync_time

### POLL-050 超时后仍有最多2秒独立清理
- 规则：采集预算超时后，仍允许使用最多2秒的独立预算进行清理（恢复采集并确认）。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“所有波特率的采集冻结路径预留解冻时间，超时后仍允许最多2秒独立清理”
- 状态：已废止 2026-10-17，由 ACQ-063 替代（与 ACQ-063 摘录自同一行原文，重复登记；第三道关口审查后保留 ACQ 条目）
- 现状符合度：符合（read_spectrum_transaction 的 finally 中清除外层 deadline，以 communication_budget(2.0, lambda: False) 执行 set_stop(False)+wait_stop(0)；清理失败抛 AcquisitionResumeError。verify_polling.py PollingTests.test_freeze_failure_attempts_resume_within_budget。领域归属：本条属冻结事务清理约束，已另提 ACQ 同源条目，誊抄阶段不合并。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；本条已废止，约束由 ACQ-063 承接
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### POLL-051 关闭软件可取消采集通信等待
- 规则：关闭软件时可取消正在进行的采集通信等待，不必等预算耗尽。
- 来源：业务规则与变更日志_V1.0.2.md 第 193 行「多设备重构：第 2 阶段（2026-09-17）」“关闭软件可取消采集通信等待，工作线程退出后释放连接”
- 状态：待确认
- 现状符合度：符合（MainWindow.closeEvent→ActiveDeviceService.stop→PollingCoordinator.stop 置 _running=False，各预算的 cancelled 回调据此抛 CommunicationCancelled；verify_polling.py test_shared_deadline_and_cancellation、test_cancelled_acquisition_still_confirms_resume。注：当前包收尾与2秒恢复清理不可取消，stop() 的 wait() 无超时（审计 robustness-core 其他#7）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.closeEvent；par_app/coordinator.py PollingCoordinator.stop；par_app/protocol.py ParModbusClient.acquisition_budget

### POLL-052 工作线程退出后释放连接
- 规则：关闭软件时，后台工作线程退出后再释放总线连接。
- 来源：业务规则与变更日志_V1.0.2.md 第 193 行「多设备重构：第 2 阶段（2026-09-17）」“关闭软件可取消采集通信等待，工作线程退出后释放连接”
- 状态：待确认
- 现状符合度：不符合（字面顺序不符，原文含义待裁决：PollingCoordinator.run 的 while 循环结束后、run() 返回前，在工作线程内部调用 _disconnect_bus 释放连接；PollingCoordinator.stop 置 _running=False 后才 wait() 等线程结束。即释放发生在线程退出之前，而非“工作线程退出后”。verify_polling.py PollingTests.test_cycle_starts_and_connection_lifetime 只断言 _disconnect_bus 调用一次，不证明先后顺序。若原文意指“工作循环结束后释放”，须经确认后再改规则。）
- 冲突：D-124：“工作线程退出后释放连接”的先后顺序含义
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py PollingCoordinator._disconnect_bus

### POLL-053 勾选失败停止时第10次连续失败退出
- 规则：设备勾选“失败停止”时，连续第10次普通通信失败后该设备退出本次采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“勾选该设备「失败停止」后，连续第10次失败退出本次采集”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备也在第10次连续失败后退出。（V1.0.2 现状：原核对：_mark_failed：excluded = auto_stop_on_failure and failures >= MAX_CONSECUTIVE_FAILURES(10)，verify_polling test_ten_failures_exit_and_restart 覆盖。但审计 requirements.md BUG-1：设备完全静默时恢复确认失败抛 AcquisitionResumeError，首轮即全局锁停，到不了第10次。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_with_failure_stop_exits_on_the_tenth_round_after_ticking
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py MAX_CONSECUTIVE_FAILURES；par_app/models.py DeviceConfig

### POLL-054 普通通信失败取消时间退避
- 规则：普通通信失败后不做时间退避。（每个采集周期尝试一次见 POLL-081。）
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“普通通信失败取消时间退避，每个采集周期尝试一次”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._mark_failed 只累加计数，不设置任何按失败次数延长的等待；下一轮开始时刻仍由 PollingCoordinator.run 按固定周期计算。总线连接失败后的 BUS_RETRY_INTERVAL_SECONDS=5 秒为固定间隔，不随失败次数增长，且短于最小周期40秒。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator.run

### POLL-055 退出设备被跳过，其他设备继续
- 规则：设备因失败停止退出本次采集后，轮询跳过该设备，其他启用设备继续按周期采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“失败退出本次采集（默认不勾选，按「失败停止开关（2026-09-30）」持续重试）；退出后跳过该设备，其他设备继续。”
- 状态：待确认
- 现状符合度：符合（_poll_all_devices / _poll_one 对 state.excluded 直接跳过，其余设备照常 _poll_one；verify_polling test_healthy_device_continues_after_other_exits。（静默设备触发全局锁停属 BUG-1，记在“默认持续重试”条。））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._poll_one

### POLL-056 失败停止默认不勾选（第3阶段）
- 规则：“失败停止”默认不勾选。（未勾选时持续重试见 POLL-082。）
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“默认不勾选，按「失败停止开关（2026-09-30）」持续重试”
- 状态：待确认
- 现状符合度：符合（par_app/models.py DeviceConfig.auto_stop_on_failure 默认 False；verify_polling.py PollingTests.test_failure_exit_switch_config_round_trip 断言 DeviceConfig().auto_stop_on_failure is False。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/models.py DeviceConfig

### POLL-057 改名或禁用再启用不清除退出状态
- 规则：对同一数据库对应的设备改名，或禁用后再启用，不清除该设备本次运行的退出状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 204 行「多设备重构：第 3 阶段（2026-09-17）」“改名或禁用再启用同一数据库对应的设备，不清除本次运行的退出状态。”
- 状态：待确认
- 现状符合度：符合（_rebuild_states 按数据库路径从 _retired_states 复用旧运行态（保留 excluded，仅在取消失败停止时解除）；test_ten_failures_exit_and_restart 覆盖改名、禁用再启用后仍 excluded。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states

### POLL-058 第10次前恢复成功则计数清零
- 规则：勾选失败停止的设备在第10次失败之前采集成功，连续失败计数清零。
- 来源：业务规则与变更日志_V1.0.2.md 第 204 行「多设备重构：第 3 阶段（2026-09-17）」“勾选设备的第10次前恢复成功，连续失败计数清零”
- 状态：待确认
- 现状符合度：符合（_mark_ok 置 state.failures = 0；verify_polling test_recovery_clears_consecutive_count_but_preserves_log。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_ok

### POLL-059 退出后仅重启软件才重新尝试
- 规则：设备因失败停止退出后，本次运行内不再尝试，只有重启软件才重新尝试该设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 204 行「多设备重构：第 3 阶段（2026-09-17）」“退出后仅重启软件重新尝试，不提供重新加入按钮。”
- 状态：已废止 2026-10-17，由 POLL-018 替代（D-114 裁决：第204行“退出后仅重启软件重新尝试”标为历史废止）
- 现状符合度：不符合（_rebuild_states 中 existing.excluded 且 auto_stop_on_failure 被取消时立即解除退出状态（按第115行“实时生效”实现），故“仅重启”字面不成立；除此之外 excluded 只在内存，重启后清零（test_ten_failures_exit_and_restart）。）
- 冲突：D-114 已裁决：取消勾选并保存即解除退出、不重启即恢复重试；除此之外退出后仅重启软件才重新尝试；本条已废止，约束由 POLL-018 承接（不取消勾选时仍须重启，见 POLL-075）
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states

### POLL-060 恢复事件写入设备库
- 规则：设备从连续失败中恢复时，恢复事件记录在该设备数据库中。
- 来源：业务规则与变更日志_V1.0.2.md 第 205 行「多设备重构：第 3 阶段（2026-09-17）」“连续尝试次数、原因及退出标志；恢复事件也保留在库中。”
- 状态：待确认
- 现状符合度：符合（_mark_ok 在 failures>0 时写 diagnostic("INFO","communication_recovery",...)；test_recovery_clears_consecutive_count_but_preserves_log。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_ok

### POLL-061 每次失败写设备库 diagnostics
- 规则：每次普通通信失败向该设备数据库 diagnostics 写一条记录，包含时间、名称、地址、轮次、连续尝试次数、原因及退出标志。
- 来源：业务规则与变更日志_V1.0.2.md 第 205 行「多设备重构：第 3 阶段（2026-09-17）」“每次失败写入该设备库的diagnostics，包含时间、名称、地址、轮次、连续尝试次数、原因及退出标志”
- 状态：待确认
- 现状符合度：符合（_mark_failed 调用 database.diagnostic(..., name, slave_id, attempt, cycle, excluded, attempted_at, reason)；test_ten_failures_exit_and_restart 校验 attempt 序列与 attempted_at。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/database.py ParDatabase.diagnostic

### POLL-062 所有已启用的勾选失败停止设备退出后停止重连
- 规则：所有已启用的勾选“失败停止”设备退出后，停止重连尝试。
- 来源：业务规则与变更日志_V1.0.2.md 第 207 行「多设备重构：第 3 阶段（2026-09-17）」“所有已启用的勾选「失败停止」设备退出后显示红色「采集停止中」，停止重连尝试”
- 状态：待确认
- 现状符合度：符合（按 D-125 裁决选 (b)：PollingCoordinator._ensure_bus_connected 以“没有任何 enabled 且未 excluded 的设备”为判据，全部启用设备都勾选且都已退出时不再重连（verify_polling.py PollingTests.test_ten_failures_exit_and_restart 断言 ParModbusClient 未被调用）；混合配置下仍有未勾选设备启用，继续重连，与裁决一致。）
- 冲突：D-125 已裁决：选 (b)：全部启用设备都勾选且都已退出时才停止重连
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected

### POLL-063 全部无响应时释放连接
- 规则：一轮内所有启用设备都无响应时，释放总线连接。
- 来源：业务规则与变更日志_V1.0.2.md 第 208 行「多设备重构：第 3 阶段（2026-09-17）」“全部无响应则释放连接，下一周期仅重试用户指定参数”
- 状态：待确认
- 现状符合度：符合（_poll_all_devices 末尾：无任何启用设备 online 时调用 _disconnect_bus。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._disconnect_bus

### POLL-064 重连只用用户指定参数不自动搜索
- 规则：全部无响应释放连接后，下一周期重试时仅用用户指定参数，不自动搜索。（下一周期是否会重连见 POLL-083。）
- 来源：业务规则与变更日志_V1.0.2.md 第 208 行「多设备重构：第 3 阶段（2026-09-17）」“全部无响应则释放连接，下一周期仅重试用户指定参数，不自动搜索。”
- 状态：待确认
- 现状符合度：符合（凡发生重连时，_ensure_bus_connected 只用 _bus_connection()（取自 self._config.bus）建连，无扫描或换参逻辑；V1.0.2 已移除旧版自动扫描（审计 architecture.md 版本对比）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._bus_connection

### POLL-065 链路不可用时逐台记录失败
- 规则：整条通信链路不可用时，每一轮仍分别为各启用设备记录一次失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 208 行「多设备重构：第 3 阶段（2026-09-17）」“整条链路不可用时，按轮分别记录各设备失败；”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。整条链路静默时每轮为每台启用设备各记一次 communication 失败。（V1.0.2 现状：原核对：串口/TCP 本身打不开、_client 为 None 时符合：_poll_one 对每台启用设备各调用一次 _mark_failed(总线错误信息)。反例：串口可打开但下游整条链路无应答（如 RS485 断线）时，首台设备的冻结事务抛 AcquisitionResumeError，_poll_one 转入 _halt_acquisition 全局锁停，_poll_all_devices 随即因 _halt_reason 非空返回，其余设备本轮及以后都没有逐台 communication 失败记录（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_whole_link_silent_records_each_device_and_reconnects_every_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._poll_all_devices

### POLL-066 手测：勾选后持续异常到10/10退出
- 规则：手测：勾选“失败停止”后持续异常，到10/10时该设备退出。（“显示已退出”属界面行为，另在 UI 领域登记。）
- 来源：业务规则与变更日志_V1.0.2.md 第 213 行「多设备重构：第 3 阶段（2026-09-17）」“勾选「失败停止」后持续异常到10/10，显示已退出；”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。以静默设备复现：持续异常到10/10时退出，消息为“连续第 10/10 次尝试失败…已退出本次采集”。（V1.0.2 现状：原核对：普通失败路径符合：_mark_failed 勾选时第10次置 excluded，消息为“连续第 10/10 次尝试失败…；已退出本次采集，重启软件后重新尝试”，level=error（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）。但同组手测上一步（第212行）以“断开探头通信”制造异常，设备静默时首轮即因“恢复未确认”全局锁停，计数到不了10/10（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_with_failure_stop_exits_on_the_tenth_round_after_ticking
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._poll_one

### POLL-067 退出后恢复硬件也不自动重新加入
- 规则：设备已退出后，即使硬件连接恢复，也不会自动重新加入本次采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 213 行「多设备重构：第 3 阶段（2026-09-17）」“显示已退出；恢复硬件连接也不自动重新加入。”
- 状态：待确认
- 现状符合度：符合（excluded 设备在 _poll_all_devices/_poll_one 中被跳过，_mark_ok 对 excluded 直接 return，无自动解除路径（取消勾选的例外见第115行）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_ok

### POLL-068 重启后重新尝试已保存配置的设备
- 规则：重启软件后，按已保存配置重新尝试此前退出的设备，成功后正常显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 214 行「多设备重构：第 3 阶段（2026-09-17）」“重启软件，重新尝试已保存配置的设备，成功后正常显示。”
- 状态：待确认
- 现状符合度：符合（退出状态只存在于 DeviceRuntimeState 内存；新 PollingCoordinator 构造时 excluded=False（test_ten_failures_exit_and_restart 的 restarted 部分）。）
- 冲突：无（V1.0.3）；alpha 档位 1（D-215 问题 5）：“重启软件”在 alpha 中对应“停止采集→开始采集”，每次开始都新建 DeviceHub 与协调器，失败计数清零、“失败停止”的退出状态解除，按 alpha 配置重新尝试；alpha 的失败停止悬停文字相应改为“需在‘实时概览’停止采集后再开始采集”
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py DeviceRuntimeState；par_app/coordinator.py PollingCoordinator.__init__

### POLL-069 手测：再勾选保存后10轮退出
- 规则：手测：再勾选“失败停止”并保存，10轮后退出。（退出后需重启见 POLL-084。）
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“接回硬件后下一轮自动恢复。再勾选保存，确认10轮后退出且需重启。”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。以静默设备复现：先恢复一轮使计数清零，再勾选并保存，此后第10轮退出。（V1.0.2 现状：原核对：普通失败路径：apply_config→_rebuild_states 更新 config.auto_stop_on_failure，接回硬件成功一轮后 _mark_ok 已将计数清零，之后 _mark_failed 到第10次置 excluded，机制上可满足；但本手测以“断开通信”为场景，设备静默时首轮即“恢复未确认”全局锁停，到不了10轮（BUG-1）。现有 verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying 末段是先累计12次失败、再勾选后下一轮立即退出，不能证明“保存后连续10轮退出”；PollingTests.test_ten_failures_exit_and_restart 是一开始就勾选的场景。另：计数未清零时勾选，下一次失败即退出而非再等10轮。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_with_failure_stop_exits_on_the_tenth_round_after_ticking
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/coordinator.py PollingCoordinator._mark_failed

### POLL-070 默认不勾选时接回硬件下一轮自动恢复
- 规则：默认不勾选时，接回硬件后下一轮采集自动恢复。
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“且不出现红色「采集停止中」；接回硬件后下一轮自动恢复。”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备接回后下一轮自动恢复采集。（V1.0.2 现状：原核对：仅在普通失败路径（如串口打不开）下：未 excluded 设备每周期 _poll_one，成功即 _mark_ok，总线释放后下一周期 _ensure_bus_connected 重连，可满足；但本手测以“断开通信超过10轮”为场景，设备静默时首轮即“恢复未确认”全局锁停，PollingCoordinator.run 在 _halt_reason 非空时跳过采集，_ensure_bus_connected 也拒绝重连，接回硬件后下一轮不会自动恢复，只能重启软件（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_recovered_device_gets_one_resume_before_its_first_capture
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/coordinator.py PollingCoordinator.run；par_app/protocol.py ParModbusClient.set_slave_id

### POLL-071 默认不勾选时超过10轮仍重试
- 规则：默认不勾选“失败停止”时，通信断开超过10轮后设备仍按周期重试。
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“默认不勾选「失败停止」时断开通信超过10轮，确认设备仍在重试”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备超过10轮仍按周期重试（RTU 与 TCP）。（V1.0.2 现状：原核对：_mark_failed 未勾选时 excluded 恒 False（test_failure_exit_switch_disabled_keeps_retrying 用 mock 覆盖）；但审计 requirements.md BUG-1：真实“断开通信”的完全静默设备首轮即触发恢复未确认全局锁停。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring；tests/qt/test_polling_silent_device.py::test_tcp_silent_transaction_raises_the_original_error_not_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_gateway_reporting_the_target_silent_is_an_ordinary_failure；tests/qt/test_polling_silent_device.py::test_tcp_gateway_target_no_response_is_silent_not_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_tcp_status_read_counts_only_replies_from_the_device
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/protocol.py ParModbusClient.read_spectrum_transaction

### POLL-072 硬件异常不计为普通通信失败
- 规则：未初始化或需重新上电的硬件异常不累计为普通通信失败次数。
- 来源：业务规则与变更日志_V1.0.2.md 第 223 行「多设备重构：第 4 阶段（2026-09-17）」“锁定本次软件运行的全局停止状态，不累计为普通通信失败。”
- 状态：待确认
- 现状符合度：符合（_poll_one 中 HardwareStateError 分支走 _halt_acquisition 而非 _mark_failed；test_hardware_stop_is_global_and_latched 断言 failures==0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one

### POLL-073 失败停止默认不勾选（设备登记表）
- 规则：设备登记表中的“失败停止”默认不勾选。
- 来源：业务规则与变更日志_V1.0.2.md 第 76 行「设置与导出布局（2026-09-20）」“「失败停止」为每台设备的独立开关，默认不勾选，行为见「失败停止开关（2026-09-30）」”
- 状态：待确认
- 现状符合度：符合（par_app/models.py DeviceConfig.auto_stop_on_failure 默认 False；MainWindow._build_settings 新建的 stop_box 为未勾选的 QCheckBox，MainWindow._refresh_device_table 按配置值回填；verify_polling.py PollingTests.test_failure_exit_switch_config_round_trip 断言 DeviceConfig().auto_stop_on_failure is False。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/models.py DeviceConfig；par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._refresh_device_table

### POLL-074 串口连接失败释放已打开句柄
- 规则：串口连接失败时，释放已打开的句柄。
- 来源：业务规则与变更日志_V1.0.2.md 第 88 行「设置与导出布局（2026-09-20）」“串口连接失败现保留原始异常并释放已打开句柄”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-05 已修复（PR #19）：serial.Serial 构造成功、句柄存入 _serial 之后，setDTR(False)、setRTS(False)、reset_input_buffer() 抛出非 SerialException 时，ParModbusClient.connect 先把 _serial 置 None 并关闭句柄，关闭本身抛 OSError 时不覆盖原始异常，然后原样抛出原始异常（仍由 run() 以“调度异常”显示，见 POLL-013），不改通信参数与控制线、清缓冲的顺序；tests/unit/test_serial_connect.py 用内存假串口覆盖三步各自失败及关闭失败的情况。（V1.0.2 现状：SerialException 路径符合：ParModbusClient.connect 在 serial.SerialException 分支中，若 _serial 已创建则 close 并置 None；connect 返回 False 后 PollingCoordinator._ensure_bus_connected 另调用 client.close()；verify_polling.py PollingTests.test_serial_connection_error_preserved_and_handle_closed。例外路径不符合：connect 在 serial.Serial 构造成功、句柄已存入 _serial 之后，还会调用 setDTR(False)、setRTS(False)、reset_input_buffer()，except 只捕获 serial.SerialException。本地 pyserial 的 POSIX 实现中，控制线经 fcntl.ioctl、清缓冲经 termios.tcflush 执行，失败时抛 OSError 或 termios.error，都不是 SerialException；异常直接穿出 connect，句柄不关闭且仍留在 _serial，_ensure_bus_connected 中的 client.close() 也不会执行，调度器只持有 self._client（此时仍为 None），无法代为清理。pyserial 的 Windows 实现中 EscapeCommFunction、PurgeComm 不检查返回值，不抛异常；未在 Windows 实机验证。）
- 冲突：缺陷：串口句柄创建后设置控制线或清缓冲抛出非 SerialException 时句柄不释放，待建 issue（DEF-05，已修复（PR #19））
- 验证：tests/unit/test_serial_connect.py::test_non_serial_exception_after_open_closes_handle_and_reraises；tests/unit/test_serial_connect.py::test_close_failure_does_not_mask_original_error；tests/unit/test_serial_connect.py::test_successful_connect_keeps_handle_open；冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.connect；par_app/coordinator.py PollingCoordinator._ensure_bus_connected

### POLL-075 勾选失败停止退出后须重启软件后重试
- 规则：前提：设备勾选“失败停止”且已因连续10次失败退出本次采集。期望：须重启软件后重试。
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“勾选——完全恢复原规则（连续 10 次失败退出本次采集，须重启软件后重试）”
- 状态：待确认
- 现状符合度：符合（按 D-114 裁决，除取消勾选并保存外，退出后仅重启才重新尝试：excluded 只存于内存 DeviceRuntimeState，新 PollingCoordinator 构造时为 False（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）；PollingCoordinator._rebuild_states 在取消勾选并保存后立即清除 excluded（PollingTests.test_failure_exit_latch_clears_when_switch_unchecked），属裁决允许的例外。）
- 冲突：D-114 已裁决：取消勾选并保存即解除退出、不重启即恢复重试；除此之外退出后仅重启软件才重新尝试；alpha 档位 1（D-215 问题 5）：“重启软件”在 alpha 中对应“停止采集→开始采集”，每次开始都新建 DeviceHub 与协调器，失败计数清零、“失败停止”的退出状态解除，按 alpha 配置重新尝试；alpha 的失败停止悬停文字相应改为“需在‘实时概览’停止采集后再开始采集”
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/coordinator.py PollingCoordinator.__init__

### POLL-076 未勾选失败停止时按轮询周期持续重连重试
- 规则：前提：设备未勾选“失败停止”（默认）。触发：连续失败。期望：按轮询周期持续重连重试。
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“不勾选（默认）——连续失败只累加计数，不退出、不进入红色「采集停止中」，按轮询周期持续重连重试”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备未勾选时按周期持续重试。（V1.0.2 现状：原核对：普通失败路径符合：未勾选设备不 excluded，PollingCoordinator.run 每周期调用 _ensure_bus_connected 与 _poll_all_devices，全部离线时本轮末断开、下一周期重连（verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying 断言仍会重连）；但设备完全静默时 read_spectrum_transaction 抛 AcquisitionResumeError，_poll_one 转入 _halt_acquisition 全局锁停，此后 run() 跳过轮询、_ensure_bus_connected 拒绝重连（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._halt_acquisition

### POLL-077 未勾选失败停止时设备恢复后自动继续采集
- 规则：前提：设备未勾选“失败停止”（默认）且连续失败。触发：设备恢复。期望：自动继续采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“按轮询周期持续重连重试，设备恢复后自动继续采集”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备恢复后自动继续采集，并记录“通信已恢复”。（V1.0.2 现状：原核对：普通失败路径符合：未 excluded 设备每周期 _poll_one，采集成功即 _mark_ok 清除失败状态；但设备完全静默时首轮即“恢复未确认”全局锁停，_halt_reason 运行期无清除路径，设备恢复后也不会自动继续，只能重启软件（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_recovered_device_gets_one_resume_before_its_first_capture
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_one；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/protocol.py ParModbusClient.set_slave_id

### POLL-078 未勾选时按原格式所写诊断的excluded恒为False
- 规则：未勾选“失败停止”时，每条失败按原格式所写的那一条 diagnostics（见 POLL-023），其 excluded 恒为 False。
- 来源：业务规则与变更日志_V1.0.2.md 第 116 行「失败停止开关（2026-09-30）」“每条失败仍按原格式写一条 diagnostics，其 `excluded` 恒为 `False`”
- 状态：待确认
- 现状符合度：符合（按 D-123 裁决，“原格式所写的那一条”指 category=communication 记录：PollingCoordinator._mark_failed 写入时 excluded=state.excluded，未勾选时恒为 False；verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying 断言12条记录 excluded 全为 False。acquisition 类“采集失败”记录不在本条范围。）
- 冲突：D-123 已裁决：“一条”指 category=communication 的原格式记录，acquisition 类“采集失败”记录保留，日量估计从约2160条/天改为约4320条/天
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._capture_once

### POLL-079 全部设备无响应时重连后释放连接
- 规则：前提：全部设备长时间无响应。期望：每轮重连后释放连接。
- 来源：业务规则与变更日志_V1.0.2.md 第 118 行「失败停止开关（2026-09-30）」“全部设备长时间无响应时每轮重连一次后释放连接”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._poll_all_devices 末尾在无任何启用设备 online 时调用 _disconnect_bus；静默设备触发全局锁停时 _halt_acquisition 也调用 _disconnect_bus，连接同样被释放。只登记一台设备时单台失败即触发本释放，按 D-112 裁决 (a) 属期望行为。）
- 冲突：D-112 已裁决：还有设备在线就不断开总线；全部离线时断开、下一轮重连，只登记一台时这台失败后每轮重开串口
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices；par_app/coordinator.py PollingCoordinator._disconnect_bus

### POLL-080 验收：重启软件后计数清零重新尝试
- 规则：验收：勾选“失败停止”的设备退出后，重启软件后计数清零重新尝试。
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“勾选并保存后，10 轮退出行为与 2026-09-20 记录一致，重启软件后计数清零重新尝试”
- 状态：待确认
- 现状符合度：符合（失败计数与 excluded 仅存于内存 DeviceRuntimeState，新 PollingCoordinator 构造时 failures=0、excluded=False；verify_polling.py PollingTests.test_ten_failures_exit_and_restart 的 restarted 部分断言未退出且首次失败计数为1。）
- 冲突：无（V1.0.3）；alpha 档位 1（D-215 问题 5）：“重启软件”在 alpha 中对应“停止采集→开始采集”，每次开始都新建 DeviceHub 与协调器，失败计数清零、“失败停止”的退出状态解除，按 alpha 配置重新尝试；alpha 的失败停止悬停文字相应改为“需在‘实时概览’停止采集后再开始采集”
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py DeviceRuntimeState；par_app/coordinator.py PollingCoordinator.__init__

### POLL-081 每个采集周期尝试一次
- 规则：普通通信失败后，每个采集周期尝试一次。
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“普通通信失败取消时间退避，每个采集周期尝试一次”
- 状态：待确认
- 现状符合度：不符合（按 R-2-1 指 V1.0.2 基线：_poll_all_devices 每周期遍历启用且未 excluded 的设备各调用一次 _poll_one；但本轮中途任务队列非空时 _poll_all_devices 直接 return，剩余设备本周期不被尝试（内部文档 BUG-2 / robustness-core.md B2，repro_core.py::test_B2）。PR #16 修复 DEF-03 后：中途入队的普通任务在设备之间就地处理，剩余设备本周期照常尝试；进入维护、硬件锁存、停止时按各自规则中断本轮；apply_config 中断本轮时 run() 不再把下一轮推迟一整个周期，未采设备在下一轮立即尝试。合并前不改基线判定。）
- 冲突：缺陷：轮询中途有任务入队时本轮剩余设备本周期不被尝试，待建 issue（DEF-03 已修复（PR #16））
- 验证：tests/qt/test_polling_task_interleave.py::test_task_queued_during_second_device_is_handled_and_round_continues；tests/qt/test_polling_task_interleave.py::test_maintenance_queued_mid_round_stops_the_rest_of_the_round；tests/qt/test_polling_task_interleave.py::test_apply_config_mid_round_ends_round_and_next_round_starts_at_once；tests/qt/test_polling_task_interleave.py::test_apply_config_queued_during_time_sync_starts_next_round_at_once；tests/qt/test_polling_task_interleave.py::test_run_loop_collects_every_device_in_the_cycle_a_task_arrived；tests/qt/test_polling_task_interleave.py::test_stop_while_a_mid_round_task_runs_ends_the_round；tests/qt/test_polling_task_interleave.py::test_task_that_uses_up_its_budget_does_not_end_the_round；tests/qt/test_polling_task_interleave.py::test_hardware_latch_raised_by_a_mid_round_task_ends_the_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._poll_all_devices

### POLL-082 默认不勾选时按失败停止开关规则持续重试
- 规则：未勾选“失败停止”（默认）时，按“失败停止开关（2026-09-30）”持续重试。
- 来源：业务规则与变更日志_V1.0.2.md 第 203 行「多设备重构：第 3 阶段（2026-09-17）」“默认不勾选，按「失败停止开关（2026-09-30）」持续重试”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。单台设备完全无响应按普通失败持续重试（RTU 与 TCP）。（V1.0.2 现状：原核对：普通失败路径符合：_mark_failed 未勾选时只累加计数（verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying）；但单台设备完全无响应会经 read_spectrum_transaction 恢复未确认触发 _halt_acquisition 全局锁停，不再持续重试（内部文档 BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_silent_device_is_an_ordinary_failure_and_others_keep_acquiring；tests/qt/test_polling_silent_device.py::test_tcp_silent_transaction_raises_the_original_error_not_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_gateway_reporting_the_target_silent_is_an_ordinary_failure；tests/qt/test_polling_silent_device.py::test_tcp_gateway_target_no_response_is_silent_not_resume_unconfirmed；tests/qt/test_polling_silent_device.py::test_tcp_status_read_counts_only_replies_from_the_device
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._poll_one；par_app/protocol.py ParModbusClient.read_spectrum_transaction

### POLL-083 全部无响应释放连接后下一周期重试
- 规则：全部无响应释放连接后，下一周期重试。（重试参数限制见 POLL-064。）
- 来源：业务规则与变更日志_V1.0.2.md 第 208 行「多设备重构：第 3 阶段（2026-09-17）」“全部无响应则释放连接，下一周期仅重试用户指定参数，不自动搜索。”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。所有设备静默时不再锁停，释放连接后下一周期重连重试。（V1.0.2 现状：原核对：串口/TCP 打不开时符合：_ensure_bus_connected 失败后按 BUS_RETRY_INTERVAL_SECONDS 间隔在下一周期再试；连接已打开但所有设备静默时，恢复确认失败在 ParModbusClient.read_spectrum_transaction 抛 AcquisitionResumeError，_poll_one 转入 _halt_acquisition 全局锁停，_ensure_bus_connected 此后拒绝重连，不会进入下一周期重试（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_whole_link_silent_records_each_device_and_reconnects_every_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._poll_one；par_app/protocol.py ParModbusClient.read_spectrum_transaction

### POLL-084 手测：再勾选后退出需重启
- 规则：手测：再勾选“失败停止”并保存，10轮后退出的设备需重启才重新尝试。
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“再勾选保存，确认10轮后退出且需重启。”
- 状态：待确认
- 现状符合度：符合（按 D-114 裁决，除取消勾选并保存外仅重启才重新尝试：不改配置时 excluded 设备被 _poll_all_devices/_poll_one 跳过，重启后清零（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）；取消勾选并保存后 PollingCoordinator._rebuild_states 立即解除退出（PollingTests.test_failure_exit_latch_clears_when_switch_unchecked），属裁决允许的例外。）
- 冲突：D-114 已裁决：取消勾选并保存即解除退出、不重启即恢复重试；除此之外退出后仅重启软件才重新尝试；alpha 档位 1（D-215 问题 5）：“重启软件”在 alpha 中对应“停止采集→开始采集”，每次开始都新建 DeviceHub 与协调器，失败计数清零、“失败停止”的退出状态解除，按 alpha 配置重新尝试；alpha 的失败停止悬停文字相应改为“需在‘实时概览’停止采集后再开始采集”
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/coordinator.py PollingCoordinator._poll_all_devices

### POLL-085 原10次失败退出规则不变，退出后须重启
- 规则：连续10次失败即退出本次采集的规则不变；已退出的设备须重启软件后才重新尝试。
- 来源：业务规则与变更日志_V1.0.2.md 第 88 行「设置与导出布局（2026-09-20）」“原10次失败退出本次采集的规则不变，已退出设备须重启软件后重试”
- 状态：已废止 2026-10-17，由 POLL-016 替代（D-111 裁决：第88行“原10次失败退出规则不变，已退出设备须重启软件后重试”标为历史废止）
- 现状符合度：不符合（勾选“失败停止”的设备符合：PollingCoordinator._mark_failed 在 auto_stop_on_failure 且 failures>=MAX_CONSECUTIVE_FAILURES 时置 excluded，重启后清零（verify_polling.py PollingTests.test_ten_failures_exit_and_restart）。不符合之处：默认不勾选时 excluded 恒为 False，不会退出（PollingTests.test_failure_exit_switch_disabled_keeps_retrying）；已退出设备取消勾选并保存后 PollingCoordinator._rebuild_states 立即解除退出，无需重启（PollingTests.test_failure_exit_latch_clears_when_switch_unchecked）。两处都与第114–115行一致。）
- 冲突：D-111 已裁决：第88行“原10次失败退出规则不变”仅在勾选失败停止时适用，标为历史表述；D-114 已裁决：取消勾选并保存即解除退出、不重启即恢复重试；除此之外退出后仅重启软件才重新尝试；本条已废止，约束由 POLL-016 承接（取消勾选即解除退出见 POLL-018）；alpha 档位 1（D-215 问题 5）：“重启软件”在 alpha 中对应“停止采集→开始采集”，每次开始都新建 DeviceHub 与协调器，失败计数清零、“失败停止”的退出状态解除，按 alpha 配置重新尝试；alpha 的失败停止悬停文字相应改为“需在‘实时概览’停止采集后再开始采集”
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py MAX_CONSECUTIVE_FAILURES；par_app/coordinator.py PollingCoordinator._rebuild_states

### POLL-086 启动后首轮即对时，之后每台每小时一次
- 规则：软件启动后，每台在线设备在第一轮读取完成后即对时，与主机已开机多久无关；此后同一设备两次对时至少间隔 3600 秒；对时失败同样记下时刻，3600 秒后才重试；停止采集导致对时被取消时不记时刻。
- 来源：开发总结_20260727.md 第 54 行“在后台线程中处理定时采集、失败重连、通信事件记录和每小时设备时间同步”；多设备支持改造方案_20260916.md 第 148 行“每个轮询周期（或每小时，沿用现有 3600 s 节流策略）对**每台分别**下发 `sync_time()`”；首轮对时：旧仓库 issue 旧仓库 issue 5，修复范围待负责人按 R-4-2 书面批准（分支 fix/first-time-sync 的 PR；方案见 内部文档 第二节第 2 步，目前只有 2026-10-17 会话中的口头意见，未入库）
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-30 已修复（PR #37）：PollingCoordinator._sync_time_if_due：DeviceRuntimeState.last_sync_at 为 None（本次运行尚未对时）时直接对时，否则距 last_sync_at 不足 TIME_SYNC_INTERVAL_SECONDS 就跳过；成功和失败都记下 last_sync_at；CommunicationCancelled 时不记；时间取自注入的 Clock，下发给 MCU 的是北京时间对应的 UTC 毫秒时间戳，与主机时区无关；ParModbusClient.sync_time 在 MCU 进入确认状态 2 时以当时的墙钟重新写入时间戳。tests/qt/test_polling_time_sync.py 覆盖开机 600 秒启动首轮即对时且下一轮不重复；其余在开机 2 小时后启动，覆盖首轮对时、3599 秒内不重复、满 3600 秒再对时、MCU 不确认时走完真实握手直到 2 秒预算用完后记失败且 3600 秒内不重试、握手中停止时取消且不记时刻、UTC 主机上时间戳不变；tests/unit/test_protocol_sync_time.py 覆盖握手等待后第二次时间戳取确认时刻、确认超时、完成超时、预算截断与取消。（V1.0.2 现状：last_sync_at=0.0 与从开机起算的 monotonic 比较，开机不满 1 小时启动时首轮及之后直到开机满 1 小时都不对时（旧仓库 #5）。）
- 冲突：无（原缺陷 DEF-30 已由 PR #37 修复，待验证）；alpha 档位 1（D-215 问题 5）：每次“开始采集”都新建协调器，各设备 last_sync_at 为空，首轮即对时，不沿用上一段接管的 3600 秒节流（同重启 V1.0.3）；停止后很快再开始会让对时比每小时一次更频繁
- 验证：tests/qt/test_polling_time_sync.py::test_first_round_syncs_time_when_started_600_seconds_after_boot；tests/qt/test_polling_time_sync.py::test_first_round_syncs_once_with_the_start_instant；tests/qt/test_polling_time_sync.py::test_after_the_first_sync_the_hourly_throttle_is_unchanged；tests/qt/test_polling_time_sync.py::test_failed_sync_is_retried_after_an_hour_not_every_round；tests/qt/test_polling_time_sync.py::test_stopping_during_the_handshake_cancels_without_remembering；tests/qt/test_polling_time_sync.py::test_sync_stamp_is_the_beijing_instant_on_a_utc_host；tests/unit/test_protocol_sync_time.py::test_second_stamp_is_the_wall_time_when_the_mcu_confirms；tests/unit/test_protocol_sync_time.py::test_mcu_that_never_confirms_fails_after_the_two_second_deadline；tests/unit/test_protocol_sync_time.py::test_mcu_that_confirms_but_never_finishes_fails_after_the_same_deadline
- 代码锚点：par_app/coordinator.py PollingCoordinator._sync_time_if_due；par_app/coordinator.py TIME_SYNC_INTERVAL_SECONDS；par_app/coordinator.py DeviceRuntimeState
