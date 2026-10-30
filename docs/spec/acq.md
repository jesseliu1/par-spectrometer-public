# 采集与冻结读取（ACQ）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### ACQ-001 不比较两次PPFD
- 规则：不比较两次 PPFD。
- 来源：业务规则与变更日志_V1.0.2.md 第 19 行「单次采集策略（2026-10-11）」“不再双采或第三采，不比较两次PPFD”
- 状态：待确认
- 现状符合度：符合（_capture_once 每轮只调用一次 read_spectrum_transaction，只得到一组指标，代码中无两次 PPFD 的比较；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 覆盖低PPFD、负值、NaN/inf，read 仅调用一次、记录成功。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd

### ACQ-002 每设备每轮只执行一次完整采集事务
- 规则：每台设备每个轮询周期只执行一次完整采集事务，不再进行双采或第三采。
- 来源：业务规则与变更日志_V1.0.2.md 第 19 行「单次采集策略（2026-10-11）」“每台设备每轮只执行一次完整采集事务，不再双采或第三采”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._capture_once 只调用一次 read_spectrum_transaction；verify_polling.py::PollingTests::test_single_capture_failure_and_halt_precedence 断言 len(calls)==1。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/coordinator.py PollingCoordinator._poll_one

### ACQ-003 软件不修改探头曝光时间
- 规则：曝光由探头自行自动控制（当前最大曝光时间1秒由探头固定），本软件不得写入或修改曝光时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 19 行「单次采集策略（2026-10-11）」“探头自行自动曝光，当前最大曝光时间固定1秒，本软件不修改曝光时间”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient

### ACQ-004 曝光状态保存
- 规则：曝光状态只保存和展示；本条约束其中的保存：完整成功读取的新记录保存曝光状态。（展示部分归 UI 领域；欠曝光不作为失败、不作为警告分列 ACQ-056、ACQ-057。）
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“完整成功读取的新记录设置 `dli_eligible=1`，曝光状态只保存和展示”
- 状态：待确认
- 现状符合度：符合（_capture_once 成功分支把 status.exposure_status、exposure_time_us 写入 save_acquisition；失败记录不含状态字段。verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 断言 record['exposure_status']==exposure。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/database.py ParDatabase.save_acquisition

### ACQ-005 新记录记录单组起止时间
- 规则：新记录须记录单组起止时间。（完成数、时钟读取异常分列 ACQ-058、ACQ-059。）
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“记录单组起止时间、完成数和时钟读取异常，不伪造双采的 `confirmed` 标记”
- 状态：待确认
- 现状符合度：符合（按 D-159 裁决，只要求成功记录写本组起止时间：成功记录的 quality_json.groups[0] 含 started_at/finished_at，另有 selected_started_at/selected_finished_at；普通失败记录 groups 为空，只有 round_started_at、acquired_at 列和 elapsed_ms 列，不在本条要求范围内。另：代码还写入原文未要求的 attempted_groups，属现状。）
- 冲突：D-159 已裁决：只要求成功记录写本组起止时间，失败记录不必写
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-006 不伪造双采confirmed标记
- 规则：单采新记录的 quality_json 不得写入双采时代的 confirmed 标记。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“不伪造双采的 `confirmed` 标记”
- 状态：待确认
- 现状符合度：符合（quality 不含 confirmed 键；verify_polling.py::PollingTests::test_single_capture_is_independent_of_exposure_and_ppfd assertNotIn("confirmed")。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-007 新记录strategy为single_capture
- 规则：新采集记录的 quality_json.strategy 必须为 single_capture。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“新记录的 `quality_json.strategy` 为 `single_capture`”
- 状态：待确认
- 现状符合度：符合（_capture_once 初始化 quality strategy="single_capture"，成功与失败记录均写入；测试断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-008 时钟读取失败不丢弃已完成光谱
- 规则：光谱已完整读取后MCU时钟读取失败时，仍保存该成功记录，mcu_time_ms 为空，并在 quality_json 记录失败原因。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“MCU时钟读取失败不丢弃已完成的光谱，时钟字段为空并记录原因。”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-155 已裁决：读取时钟期间软件停止属于“时钟读取失败”，已完整读到的光谱仍保存（时钟为空，原因记“软件停止”），DEF-22 已修复（PR #30）（同 ACQ-059）
- 验证：tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_before_the_clock_request_keeps_the_spectrum_with_empty_clock；tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_while_the_clock_packet_is_in_flight_keeps_the_spectrum_with_empty_clock；tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_after_spectrum_and_clock_were_both_read_keeps_both；tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_before_the_spectrum_is_complete_still_writes_nothing；tests/qt/test_clock_cancel_keeps_spectrum.py::test_clock_protocol_error_while_running_records_the_exception_text；tests/qt/test_clock_cancel_keeps_spectrum.py::test_clock_budget_exhausted_while_running_records_the_timeout_text
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.read_standard_time

### ACQ-009 采集状态仅completed或incomplete
- 规则：新记录 quality_json.acquisition_status 只取 completed（成功）或 incomplete（失败/未完成）。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“`acquisition_status` 为 `completed` 或 `incomplete`”
- 状态：待确认
- 现状符合度：符合（_capture_once 默认 incomplete，成功后置 completed；verify_polling.py::PollingTests::test_acquisition_round_budget_limits_single_capture 断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-010 单采后701点完整性检查不变
- 规则：单次采集仍须校验光谱为完整701点，不完整视为采集失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“冻结/恢复确认、701点完整性、硬件异常停止、失败停止开关及轮询周期保持原规则”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient._read_registers

### ACQ-011 单采后冻结/恢复确认规则不变
- 规则：改为单次采集后，冻结（停止=1）与恢复（停止=0）确认规则保持原规则不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“冻结/恢复确认、701点完整性、硬件异常停止、失败停止开关及轮询周期保持原规则”
- 状态：待确认
- 现状符合度：符合（ParModbusClient.read_spectrum_transaction 仍为 set_stop(True)→wait_stop(1)→读取→finally set_stop(False)→wait_stop(0)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-012 单采后硬件异常停止规则不变
- 规则：单次采集仍沿用原硬件异常（未初始化/要求重新上电）全局停止规则。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“冻结/恢复确认、701点完整性、硬件异常停止、失败停止开关及轮询周期保持原规则”
- 状态：待确认
- 现状符合度：符合（_poll_one 捕获 HardwareStateError 调 _halt_acquisition；verify_polling.py::PollingTests::test_hardware_stop_is_global_and_latched。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/coordinator.py PollingCoordinator._poll_one

### ACQ-013 40秒预算仅限发起新请求，非墙钟硬截止
- 规则：40秒预算只约束是否发起后续采集请求；已发出的帧须收尾、恢复清理须执行，因此总耗时可超过40秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“40秒是发起后续采集请求的预算，不是墙钟硬截止：已发帧收尾和恢复清理可能使总耗时超过40秒”
- 状态：待确认
- 现状符合度：符合（acquisition_budget 置 _finish_packet，_packet_budget 为已发帧另给 timeout_seconds 期限并在异常时 _drain_late_response；verify_polling.py::PollingTests::test_acquisition_finishes_current_packet_only、test_rtu_finishes_or_drains_before_next_device。）
- 冲突：D-120 已裁决：“在40秒预算内截止”指40秒后不再发起新的读取请求，已发请求收尾和恢复可使总耗时超过40秒（与 ACQ-019 相关）
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient._packet_budget；par_app/protocol.py ParModbusClient._drain_late_response

### ACQ-014 单帧超时1.5秒
- 规则：单个请求帧的超时保持1.5秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“维护/诊断预算10秒、单帧超时1.5秒、恢复清理独立预算2秒及用户设置的轮询周期不变”
- 状态：待确认
- 现状符合度：符合（_frame_timeout(10)=min(1.5, 10/4)=1.5，赋给连接 timeout_seconds；测试断言 _bus_connection().timeout_seconds==1.5。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py _frame_timeout；par_app/coordinator.py PollingCoordinator._bus_connection

### ACQ-015 恢复清理独立预算2秒
- 规则：冻结读取后的恢复清理使用独立的2秒预算，不受采集轮预算剩余量影响。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“维护/诊断预算10秒、单帧超时1.5秒、恢复清理独立预算2秒及用户设置的轮询周期不变”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction 的 finally 将 _deadline 置空后在 communication_budget(2.0, lambda: False) 中恢复。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-016 每设备一轮采集预算40秒（读取与时钟共享）
- 规则：每台设备每轮采集预算为40秒，由单次完整读取及其后的设备时钟读取共享。
- 来源：业务规则与变更日志_V1.0.2.md 第 27 行「统一冻结读取（2026-10-11）」“每台设备一轮采集预算保持40秒，由单次完整读取和随后设备时钟读取共享”
- 状态：待确认
- 现状符合度：符合（ACQUISITION_TRANSACTION_BUDGET_SECONDS=40.0，_capture_once 在 acquisition_budget(40) 内完成读取与 read_standard_time。代码隐含：read_spectrum_transaction 为恢复预留2秒，读取段实际上限为 预算−2 秒（38秒），原文未写明。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS；par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget

### ACQ-017 不以延长单帧等待满足预算
- 规则：预算行为不得通过延长单帧等待时间来实现，单帧超时仍为1.5秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 28 行「统一冻结读取（2026-10-11）」“无旧双采候选组回退，不通过延长单帧等待实现”
- 状态：待确认
- 现状符合度：符合（测试断言 _bus_connection().timeout_seconds==1.5；_frame_timeout 上限1.5。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py _frame_timeout

### ACQ-018 回归：35秒读取在40秒预算内完成
- 规则：虚拟时钟回归须证明单次读取耗时35秒时在40秒预算内完成并保存成功记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 28 行「统一冻结读取（2026-10-11）」“虚拟时钟回归覆盖单次读取35秒在40秒预算内完成”
- 状态：待确认
- 现状符合度：符合（verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture 向协调器和总线客户端注入虚拟时钟 FakeClock（par_app/domain/clock.py），用例 (40,35)→completed_groups=1、dli_eligible=1、clock.monotonic()=35。注：该测试 patch 了 read_spectrum_transaction，未覆盖其内部为恢复预留2秒的真实协议路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture；par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget

### ACQ-019 回归：44秒需求在40秒预算内截止并记失败
- 规则：虚拟时钟回归须覆盖：读取需求44秒时在40秒预算内截止并记失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 28 行「统一冻结读取（2026-10-11）」“以及44秒需求在40秒预算内截止并记失败；无旧双采候选组回退”
- 状态：待确认
- 现状符合度：未验证（按 D-120 裁决，“40秒预算内截止”指40秒后不再发起新的读取请求，时间边界已明确。现有 verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture 用例 (40,44)→completed_groups=0、success=0、timed_out=True、clock.monotonic()=40（注入 FakeClock），但 patch 了整个 read_spectrum_transaction，只证明协调层在预算耗尽时写失败记录；真实协议路径（读取段只用“预算−2秒”、已发帧收尾、2秒恢复清理）未被覆盖。按 D-120 的技术说明，迁移到 pytest 时须走真实协议路径断言截止时刻。）
- 冲突：D-120 已裁决：“在40秒预算内截止”指40秒后不再发起新的读取请求，已发请求收尾和恢复可使总耗时超过40秒（与 ACQ-013 相关）
- 验证：冻结待确认
- 代码锚点：verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture；par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget；par_app/protocol.py ParModbusClient._check_budget

### ACQ-020 预算截止不回退旧双采候选组
- 规则：预算截止导致读取失败时，不得回退采用旧双采的候选组数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 28 行「统一冻结读取（2026-10-11）」“无旧双采候选组回退，不通过延长单帧等待实现”
- 状态：待确认
- 现状符合度：符合（_capture_once 只有单组，失败直接写失败记录；测试断言 len(groups)==completed。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-021 低速RTU每包64点
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 29 行「统一冻结读取（2026-10-11）」“低速RTU仍每包64点，高速及TCP仍每包最多125点”
- 状态：待确认
- 现状符合度：符合（_read_input_chunked：transport=="rtu" 且 baudrate<=19200 时 chunk_limit=64；“低速”界限 ≤19200 仅存在于代码，原文未定义；verify_polling.py::PollingTests::test_stop_status_confirmation_and_chunk_sizes。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient._read_input_chunked

### ACQ-022 删除低速RTU只读旁路
- 规则：不再存在低速RTU不冻结直接读取的旁路，任何波特率都不放弃帧一致性。
- 来源：业务规则与变更日志_V1.0.2.md 第 29 行「统一冻结读取（2026-10-11）」“删除低速RTU只读旁路，不再因波特率放弃帧一致性”
- 状态：待确认
- 现状符合度：符合（protocol.py 中波特率仅影响 _read_input_chunked 分包大小，事务路径无波特率判断。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-023 所有波特率RTU与TCP统一冻结读取序列
- 规则：所有波特率的RTU以及TCP统一按序执行：发停止命令→确认停止状态=1→读系数、701点光谱及光色参数→发恢复命令→确认停止状态=0。
- 来源：业务规则与变更日志_V1.0.2.md 第 29 行「统一冻结读取（2026-10-11）」“所有波特率的RTU及TCP统一执行：发送停止采集命令、确认停止状态为1”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction 无传输/波特率分支；verify_polling.py::PollingTests::test_all_transports_freeze_before_read_and_confirm_resume 覆盖 RTU 1200/9600/19200/115200 与 TCP 的事件顺序。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-024 高速RTU及TCP每包最多125点
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 29 行「统一冻结读取（2026-10-11）」“低速RTU仍每包64点，高速及TCP仍每包最多125点”
- 状态：待确认
- 现状符合度：符合（_read_input_chunked 其余情况 chunk_limit=125；测试覆盖115200。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient._read_input_chunked

### ACQ-025 （设备协议细节，公开版略）
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 30 行「统一冻结读取（2026-10-11）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.set_stop；par_app/protocol.py ParModbusClient.wait_stop；par_app/protocol.py ParModbusClient._rtu_exchange；par_app/rtu_frames.py LateEchoes

### ACQ-026 一旦尝试停止必用2秒独立预算尝试恢复
- 规则：一旦开始尝试停止，无论读取成功、失败、超时或取消，都用最多2秒独立预算尝试恢复并确认（尝试不等于保证成功；恢复未确认时的处理见 ACQ-029）。
- 来源：业务规则与变更日志_V1.0.2.md 第 30 行「统一冻结读取（2026-10-11）」“一旦开始尝试停止，无论读取成功、失败、超时或取消，都用最多2秒独立预算尝试恢复并确认”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction 在 set_stop 之前置 stopped=True，finally 中以 communication_budget(2.0, lambda: False) 忽略取消执行 set_stop(False)+wait_stop(0)；恢复失败时保留失败分支：无硬件异常则抛 AcquisitionResumeError，已有硬件异常则保留原异常。verify_polling.py PollingTests.test_cancelled_acquisition_still_confirms_resume、PollingTests.test_acquisition_thaws_after_budget_exhaustion、PollingTests.test_freeze_failures_never_read_unconfirmed_data_and_always_resume。DEF-10 修复（PR #29，D-101）：恢复仍必定尝试；未确认停止且整次事务没有收到该从站任何有效帧时，恢复失败不抛 AcquisitionResumeError，保留原始通信异常；静默后的下一次事务在停止命令之前先补发一次恢复命令。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-027 停止未确认不读取光谱
- 规则：停止命令失败或停止状态未确认为1时，不读取本组光谱。
- 来源：业务规则与变更日志_V1.0.2.md 第 30 行「统一冻结读取（2026-10-11）」“停止命令失败或状态未确认，不读取本组光谱”
- 状态：待确认
- 现状符合度：符合（wait_stop(1) 失败即抛出，_read_input_chunked 不被调用；verify_polling.py::PollingTests::test_freeze_failures_never_read_unconfirmed_data_and_always_resume。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-028 恢复未确认不伪造未初始化/需上电状态位
- 规则：恢复未确认时不得伪造“未初始化”或“要求重新上电”的硬件状态位。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“提示「恢复未确认」，硬件实际状态不确定，不伪造未初始化或要求上电的状态位”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 对 AcquisitionResumeError 将 initialized/need_power_cycle 记为 None，不改写 latest_status（运行级别用 "power" 仅作界面色级）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition

### ACQ-029 恢复未确认时不返回或保存本事务数据
- 规则：恢复命令或运行状态未确认时，不返回或保存当前事务数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“恢复命令或运行状态未确认时，不返回或保存当前事务数据”
- 状态：待确认
- 现状符合度：符合（finally 中抛 AcquisitionResumeError 覆盖返回值；_capture_once 对其直接 re-raise 不调 save_acquisition；verify_polling.py PollingTests.test_resume_failure_is_fatal_after_current_spectrum_read。现状附带：此时也不写任何不含事务数据的失败记录，本轮该设备零条记录；按 D-121 裁决允许，见 ACQ-038。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；D-121 已裁决：每设备每轮至多一条记录；总线未连接、取消、硬件严重异常、恢复未确认时允许零记录，以 diagnostics 留痕
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-030 硬件严重异常优先于恢复未确认
- 规则：事务中已发生硬件严重异常（未初始化/需上电）时，保留该硬件异常作为停止原因，恢复失败不得覆盖它。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“重新上电后重启软件。原有硬件严重异常仍优先保留。”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction finally 中 hardware_error 非空时吞掉恢复异常；_halt_acquisition 已有 _halt_reason 时不再覆盖；verify_polling.py::PollingTests::test_cleanup_failure_does_not_mask_hardware_state。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/coordinator.py PollingCoordinator._halt_acquisition

### ACQ-031 实机待确认：停止=1时数据全部稳定
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：未验证（原文自述未占用在线串口、未实机确认；实机测试当前暂缓。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-032 实机待确认：恢复预算内完成确认
- 规则：须在实机确认当前链路能在2秒恢复预算内完成恢复命令与状态确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“光色参数全部稳定，以及当前链路能够在恢复预算内完成确认”
- 状态：待确认
- 现状符合度：未验证（原文自述未实机确认；实机测试当前暂缓。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-033 轮询隔离测试覆盖冻结读取关键场景
- 规则：轮询隔离测试须覆盖：多波特率下的冻结顺序、失败/取消后的恢复、恢复失败锁定、分包大小。
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“轮询隔离测试覆盖多波特率顺序、失败/取消恢复、恢复失败锁定及分包大小”
- 状态：待确认
- 现状符合度：符合（verify_polling.py::PollingTests::test_all_transports_freeze_before_read_and_confirm_resume、test_freeze_failures_never_read_unconfirmed_data_and_always_resume、test_cancelled_acquisition_still_confirms_resume、test_resume_failure_is_fatal_after_current_spectrum_read、test_stop_status_confirmation_and_chunk_sizes。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：verify_polling.py PollingTests.test_all_transports_freeze_before_read_and_confirm_resume；verify_polling.py PollingTests.test_freeze_failures_never_read_unconfirmed_data_and_always_resume；verify_polling.py PollingTests.test_cancelled_acquisition_still_confirms_resume；verify_polling.py PollingTests.test_resume_failure_is_fatal_after_current_spectrum_read；verify_polling.py PollingTests.test_stop_status_confirmation_and_chunk_sizes；par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/protocol.py ParModbusClient._read_input_chunked

### ACQ-034 单采曝光不决定采集成败
- 规则：新单采记录的曝光状态不决定采集成败：过曝光/欠曝光仍记为成功。
- 来源：业务规则与变更日志_V1.0.2.md 第 52 行「实时概览与历史回放（2026-10-11）」“新单采记录的曝光不决定采集成败、警告色或DLI资格”
- 状态：待确认
- 现状符合度：符合（coordinator._capture_once 只在 initialized/need_power_cycle/点数不足时报错，不检查 exposure_status，成功即 success=1（docstring：曝光状态仅记录，不触发复采或决定 DLI 资格））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-035 成功记录保留三种曝光状态
- 规则：成功采集的数据保留正常、过曝光、欠曝光三种曝光状态（记录并显示）。
- 来源：业务规则与变更日志_V1.0.2.md 第 52 行「实时概览与历史回放（2026-10-11）」“成功采集的数据保留正常、过曝光和欠曝光三种曝光状态”
- 状态：待确认
- 现状符合度：符合（coordinator._capture_once 保存 status.exposure_status；ui.py refresh_history/_update_overview_status/show_history_spectrum 映射 {0:正常,1:过曝光,2:欠曝光}）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/ui.py MainWindow.refresh_history

### ACQ-036 acquired_at 取事务实际读取开始时间
- 规则：记录的 acquired_at 为该次采集事务实际开始读取的时间（北京时间）。
- 来源：业务规则与变更日志_V1.0.2.md 第 92 行「单次采集与分段 DLI（2026-10-11）」“`acquired_at`为该事务实际读取开始时间”
- 状态：待确认
- 现状符合度：符合（_capture_once 在调用 read_spectrum_transaction 前重新赋值 acquired_at=beijing_now()，并写入 groups[0].started_at；verify_polling 断言 acquired_at == groups[0].started_at。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-037 取消双采、第三采与组间回退
- 规则：采集不再执行 2026-09-18 方案的双采、第三采、低光分界2、20% 差异判断及组间回退。
- 来源：业务规则与变更日志_V1.0.2.md 第 92 行「单次采集与分段 DLI（2026-10-11）」“已取消原2026-09-18的双采、第三采、低光分界2和20%差异判断及组间回退”
- 状态：待确认
- 现状符合度：符合（_capture_once 只调用一次 read_spectrum_transaction，quality strategy='single_capture'；verify_polling.test_single_capture_is_independent_of_exposure_and_ppfd 断言无 confirmed/third_reason。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-038 每设备每轮只写一条单次结果
- 规则：每设备每轮只写一条单次结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 92 行「单次采集与分段 DLI（2026-10-11）」“每设备每轮只写一条单次结果，状态、缩放系数、701点和MCU参数来自同一事务”
- 状态：待确认
- 现状符合度：符合（按 D-121 裁决，每设备每轮“至多一条”：_capture_once 的成功分支与普通失败分支互斥，各只调用一次 save_acquisition，verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 断言 len(rows)==1。零条记录路径——_poll_one 中 self._client 为 None（总线未连接）时只调 _mark_failed；_capture_once 对 CommunicationCancelled、HardwareStateError、AcquisitionResumeError 直接 re-raise——属裁决允许的情形，verify_polling.py PollingTests.test_single_capture_failure_and_halt_precedence、PollingTests.test_resume_failure_is_fatal_after_current_spectrum_read 断言这些路径零条记录。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；D-121 已裁决：每设备每轮至多一条记录；总线未连接、取消、硬件严重异常、恢复未确认时允许零记录，以 diagnostics 留痕
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/database.py ParDatabase.save_acquisition

### ACQ-039 状态、系数、光谱与参数同一事务
- 规则：一条采集记录中的状态、缩放系数、701 点光谱和 MCU 光度参数必须来自同一次冻结读取事务。
- 来源：业务规则与变更日志_V1.0.2.md 第 92 行「单次采集与分段 DLI（2026-10-11）」“状态、缩放系数、701点和MCU参数来自同一事务”
- 状态：待确认
- 现状符合度：符合（ParModbusClient.read_spectrum_transaction 在一次停止/恢复包裹内返回 status、raw_points、params；_capture_once 直接使用该三元组保存。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/coordinator.py PollingCoordinator._capture_once

### ACQ-040 启用第二台设备前须重新核算预算
- 规则：启用第二台及以上设备前，必须重新核算采集轮预算与轮询周期的关系，否则会撑爆周期。
- 来源：业务规则与变更日志_V1.0.2.md 第 105 行「采集轮预算调整（2026-09-30，历史记录）」“启用第二台设备前必须重新核算，否则会撑爆周期”
- 状态：已废止 2026-10-17，由 POLL-037 替代（D-107、D-122 裁决：第105行“启用第二台设备前必须重新核算”标为历史废止）
- 现状符合度：未验证（原文未写明核算由谁完成：人工前置核算还是软件强制校验。软件侧现状：MainWindow._refresh_interval_range 与 AppConfig.min_poll_cycle_seconds 的周期范围与设备数量无关，DeviceHub.apply 启用多台设备时不做预算核算或提示；人工核算的执行证据未见。核算责任待 D-107 裁决。）
- 冲突：D-107 已裁决：第105行的不变量（预算 ≤ 周期 − 2 秒 − 余量、启用第二台前须核算）随40秒方案作废，改为“超时顺延、不积压”；D-122 已裁决：随 D-107 作废，不再要求启用第二台设备前核算；本条已废止，约束由 POLL-037（周期40~3600秒、与设备数量无关）承接
- 验证：冻结待确认
- 代码锚点：无：V1.0.2 没有启用设备前的预算核算实现（差异证据为 MainWindow._refresh_interval_range、AppConfig.min_poll_cycle_seconds、DeviceHub.apply，见现状符合度）

### ACQ-041 采集轮预算不超过周期减对时减余量
- 规则：采集轮预算须满足：采集轮预算 ≤ 轮询周期 − 对时（2 秒）− 余量。
- 来源：业务规则与变更日志_V1.0.2.md 第 105 行「采集轮预算调整（2026-09-30，历史记录）」“须满足 `采集轮预算 ≤ 轮询周期 − 对时（2 秒） − 余量`”
- 状态：已废止 2026-10-17，由 POLL-005 替代（D-107 裁决：第105行“采集轮预算 ≤ 轮询周期 − 对时（2 秒）− 余量”标为历史废止）
- 现状符合度：不符合（数值反例：par_app/coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS=40.0，par_app/models.py MIN_POLL_CYCLE_SECONDS=40.0，最小周期下 40 > 40−2−余量；代码无启动或保存时的该不变量校验，DeviceHub.apply 不检查。以上常量和配置入口是差异证据或候选实现位置，不是本约束的实现。）
- 冲突：D-107 已裁决：第105行的不变量（预算 ≤ 周期 − 2 秒 − 余量、启用第二台前须核算）随40秒方案作废，改为“超时顺延、不积压”；本条已废止，约束由 POLL-005（超时顺延、不并发不补跑）承接
- 验证：冻结待确认
- 代码锚点：无：V1.0.2 没有预算与周期关系的校验实现（差异证据为 ACQUISITION_TRANSACTION_BUDGET_SECONDS、MIN_POLL_CYCLE_SECONDS、DeviceHub.apply，见现状符合度）

### ACQ-042 未初始化或需重新上电时立即终止读谱
- 规则：读取状态发现“未初始化”或“需要重新上电”时，立即终止本次光谱读取，不再读取701点光谱。
- 来源：业务规则与变更日志_V1.0.2.md 第 223 行「多设备重构：第 4 阶段（2026-09-17）」“读取状态发现「未初始化」或「需要重新上电」时立即终止光谱读取”
- 状态：待确认
- 现状符合度：符合（wait_stop 读状态时 not initialized 或 need_power_cycle 即抛 HardwareStateError，read_spectrum_transaction 不再读 _read_input_chunked；verify_polling test_hardware_state_stops_before_spectrum_read。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.wait_stop；par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/protocol.py HardwareStateError

### ACQ-043 硬件异常锁定本次运行全局停止
- 规则：发现未初始化或需重新上电时，锁定本次软件运行的全局停止状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 223 行「多设备重构：第 4 阶段（2026-09-17）」“需要重新上电」时立即终止光谱读取，锁定本次软件运行的全局停止状态”
- 状态：待确认
- 现状符合度：符合（_poll_one 捕获 HardwareStateError 调用 _halt_acquisition，设置 _halt_reason（仅内存，无清除路径）；test_hardware_stop_is_global_and_latched。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/coordinator.py PollingCoordinator._poll_one

### ACQ-044 全局停止后全部设备停止通信
- 规则：全局停止后，所有设备停止后台采集、对时、自动重连及维护通信。
- 来源：业务规则与变更日志_V1.0.2.md 第 224 行「多设备重构：第 4 阶段（2026-09-17）」“全部设备停止后台采集、对时、重连及维护通信”
- 状态：待确认
- 现状符合度：符合（run/_poll_all_devices/_sync_time_if_due/_ensure_bus_connected 均检查 _halt_reason；_process_tasks 中维护及普通任务在 halt 时拒绝；test_hardware_stop_is_global_and_latched。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py PollingCoordinator._ensure_bus_connected；par_app/coordinator.py PollingCoordinator._sync_time_if_due；par_app/coordinator.py PollingCoordinator._process_tasks

### ACQ-045 冻结路径用2秒独立预算尽力恢复
- 规则：硬件异常终止时，冻结读取路径用最多2秒的独立清理预算尽力发送恢复命令、恢复设备更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 224 行「多设备重构：第 4 阶段（2026-09-17）」“冻结读取路径允许最多2秒独立清理预算尽力恢复设备更新”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction 的 finally 在 stopped 时以 communication_budget(2.0) 执行 set_stop(False)+wait_stop(0)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-046 清理失败不掩盖原硬件异常
- 规则：硬件异常后的恢复清理失败时，仍以原硬件异常为准上报，不被清理错误替换。
- 来源：业务规则与变更日志_V1.0.2.md 第 224 行「多设备重构：第 4 阶段（2026-09-17）」“尽力恢复设备更新，清理失败不能掩盖原硬件异常。”
- 状态：待确认
- 现状符合度：符合（finally 中 hardware_error 已存在时吞掉清理异常、不抛 AcquisitionResumeError；verify_polling test_cleanup_failure_does_not_mask_hardware_state。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-047 停止先于弹窗生效
- 规则：全局停止在界面弹窗出现之前已经生效。
- 来源：业务规则与变更日志_V1.0.2.md 第 225 行「多设备重构：第 4 阶段（2026-09-17）」“停止在UI弹窗之前生效。对话框标明设备名称、地址、时间”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 先设 _halt_reason、断开总线、写库，最后才 emit acquisition_halted 触发 _show_hardware_stop。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/ui.py MainWindow._show_hardware_stop

### ACQ-048 刷新/切换/保存/移除均不解除全局停止
- 规则：页面刷新、切换设备、保存配置或移除异常设备都不能解除全局停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 226 行「多设备重构：第 4 阶段（2026-09-17）」“页面刷新、切换设备、保存配置或移除异常设备均不能解除全局停止。”
- 状态：待确认
- 现状符合度：符合（_apply_config/_rebuild_states 不重置 _halt_reason，_halt_reason 无清除代码；test_hardware_stop_is_global_and_latched 覆盖移除异常设备后的 apply_config。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._apply_config；par_app/coordinator.py PollingCoordinator._halt_acquisition

### ACQ-049 停止原因写入各启用设备diagnostics
- 规则：全局停止时，停止原因、原始状态位及轮次写入每台启用设备数据库的 diagnostics。
- 来源：业务规则与变更日志_V1.0.2.md 第 227 行「多设备重构：第 4 阶段（2026-09-17）」“停止原因、原始状态及轮次写入各启用设备数据库的diagnostics”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 对每台 enabled 设备写 diagnostic("ERROR","acquisition_halted", reason 含 initialized/need_power_cycle/cycle)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition

### ACQ-050 全局停止记录运行状态和DLI中断
- 规则：全局停止时，同时为各启用设备记录运行状态和DLI中断。
- 来源：业务规则与变更日志_V1.0.2.md 第 227 行「多设备重构：第 4 阶段（2026-09-17）」“写入各启用设备数据库的diagnostics，同时记录运行状态和DLI中断。”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 对每台启用设备调用 set_runtime_status("power", …) 与 save_dli_interruption(message)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/database.py ParDatabase.save_dli_interruption

### ACQ-051 日志写入失败仍停止并在弹窗提示
- 规则：停止日志写入失败时仍执行全局停止，并在弹窗中显示写入失败信息。
- 来源：业务规则与变更日志_V1.0.2.md 第 227 行「多设备重构：第 4 阶段（2026-09-17）」“同时记录运行状态和DLI中断。日志写入失败仍停止，弹窗显示写入失败信息。”
- 状态：待确认
- 现状符合度：符合（_halt_acquisition 先设 _halt_reason，写库异常收集到 reason['log_errors']；_show_hardware_stop 追加“部分停止记录未能写入数据库”；test_logging_failure_cannot_prevent_hardware_stop。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/ui.py MainWindow._show_hardware_stop

### ACQ-052 只有重启才重新尝试，仍异常则再停
- 规则：全局停止后只有重启软件才会重新尝试采集；重启后设备仍异常则再次全局停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 228 行「多设备重构：第 4 阶段（2026-09-17）」“只有重启软件才会重新尝试；若设备仍异常则再次停止。”
- 状态：待确认
- 现状符合度：符合（_halt_reason 只在内存，新 PollingCoordinator 为 None（test_hardware_stop_is_global_and_latched 的 restarted）；重启后同一检查路径再次触发 _halt_acquisition；退出维护也被拒绝。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.__init__；par_app/coordinator.py PollingCoordinator._halt_acquisition

### ACQ-053 采集事务：暂停→确认停止→读701点与27参数→恢复
- 规则：每次采集先暂停 MCU 光谱更新，确认已停止后直接读取701点光谱和27个光色参数，读取后恢复更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 337 行「产品边界」“采集过程：暂停 MCU 光谱更新 → 确认停止 → 直接读 701 点谱和 27 个参数 → 恢复更新。”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令（恢复更新未确认时的处理）；第28-29行（统一冻结读取 2026-10-11）对本流程有更细规定：恢复后须确认停止状态为0，恢复用独立2秒预算。
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction；par_app/models.py PHOTOMETRIC_NAMES

### ACQ-054 通信由后台采集服务独占
- 规则：通信由后台采集服务独占。（同句“UI 读取数据库”归 UI 领域。）
- 来源：业务规则与变更日志_V1.0.2.md 第 338 行「产品边界」“数据永久保存于本地 SQLite；UI 读取数据库，通信由后台采集服务独占。”
- 状态：待确认
- 现状符合度：符合（par_app 中只有 protocol.py、coordinator.py、maintenance.py 构造 ParModbusClient；par_app/ui.py 不引用 ParModbusClient，硬件操作经 PollingCoordinator.queue_task 入队，由 PollingCoordinator._process_tasks 在后台线程执行，CommunicationMaintenance 也只由 coordinator 创建；界面只用 serial.tools.list_ports 枚举串口，不打开串口。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py PollingCoordinator._process_tasks；par_app/coordinator.py PollingCoordinator.queue_task

### ACQ-055 不以低光分界或曝光状态触发复采
- 规则：不以低光分界或曝光状态触发复采。
- 来源：业务规则与变更日志_V1.0.2.md 第 19 行「单次采集策略（2026-10-11）」“不比较两次PPFD，也不以低光分界或曝光状态触发复采”
- 状态：待确认
- 现状符合度：符合（_capture_once 每轮只调用一次 read_spectrum_transaction，成功后不检查 exposure_status 或 PPFD 阈值，无复采分支；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 覆盖曝光 0/1/2 与 PPFD 0、1.99、100、9000 等组合，read 仅调用一次。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd

### ACQ-056 欠曝光不作为采集失败
- 规则：欠曝光不作为采集失败。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“曝光状态只保存和展示；欠曝光不作为采集失败或警告”
- 状态：待确认
- 现状符合度：符合（_capture_once 只在 initialized=0、need_power_cycle=1、点数不足等情况报错，不检查 exposure_status，完整读取即写 success=1；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 对 exposure=2 断言 success==1、acquisition_status=='completed'。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd

### ACQ-057 欠曝光不作为警告
- 规则：欠曝光不作为警告。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“曝光状态只保存和展示；欠曝光不作为采集失败或警告”
- 状态：待确认
- 现状符合度：不符合（按 D-154 裁决需修改，待修复。按裁决，历史列表“曝光”列中新单采记录的欠曝光、过曝光须与“正常”同色，旧记录保留橙色；现状 MainWindow.refresh_history 对新单采记录的非正常值也着橙色 #d97706。原核对（未验证）：采集运行状态符合：_capture_once 成功时 state.level="ok"，消息只附曝光文字，_mark_ok 以该级别写 set_runtime_status，测试对 exposure=2 断言 level=='ok'；实时概览状态卡对单采记录不因曝光着琥珀色（呈现层另见 UI-002）。但 MainWindow.refresh_history 的历史表“曝光”列对非“正常”值（含欠曝光）着橙色 #d97706，这是否构成本条所说的“警告”，原文未定义，见 D-154。）
- 冲突：D-154 已裁决：第20、52行适用于历史列表“曝光”列：新单采记录的欠曝光、过曝光与“正常”同色，旧记录保留橙色，待修复（DEF-21）（同 UI-052）
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.refresh_history

### ACQ-058 新记录记录完成数
- 规则：新记录须记录完成数。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“记录单组起止时间、完成数和时钟读取异常，不伪造双采的 `confirmed` 标记”
- 状态：待确认
- 现状符合度：符合（_capture_once 初始化 quality_json.completed_groups=0，成功时置 1，成功与普通失败记录都写入；verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture 断言 completed_groups 与 len(groups) 一致。不写记录的路径见 ACQ-038。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture

### ACQ-059 新记录记录时钟读取异常
- 规则：新记录须记录时钟读取异常。
- 来源：业务规则与变更日志_V1.0.2.md 第 21 行「单次采集策略（2026-10-11）」“记录单组起止时间、完成数和时钟读取异常，不伪造双采的 `confirmed` 标记”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-22 已修复（PR #30）：光谱（含恢复确认）完整读到后，读 MCU 时钟期间软件停止（CommunicationCancelled，含时钟回包已收到、随后报告取消的情形），_capture_once 不再上抛，照常保存成功记录：mcu_time_ms 为空，quality_json.groups[0].clock_error 记“软件停止”，dli_eligible 为1，不计失败、不写诊断；光谱和时钟都已读到后才发现软件停止的（时钟回包已解析，离开采集预算时才检测到取消），两者都保存：mcu_time_ms 保留读到的值，不记 clock_error，照常为成功记录（阶段一裁决 39）。软件未停止时读时钟抛 ProtocolError/OSError（含预算耗尽的 CommunicationTimeout，timed_out 记 true）照旧记异常文本。光谱读完前停止仍不写任何记录（D-121＝现状）。（V1.0.2 现状：不符合（按 D-155 裁决需修改，待修复。按裁决，读取时钟期间软件停止属于时钟读取异常，须保存已完成光谱并记录时钟异常（原因“软件停止”）；现状对 CommunicationCancelled 直接 re-raise，不写任何记录。原核对（未验证）：光谱完整读取后 read_standard_time 抛 ProtocolError/OSError（含预算耗尽的 CommunicationTimeout）时，写 quality_json.groups[0].clock_error 并保存成功记录，verify_polling.py PollingTests.test_completed_spectrum_survives_clock_budget_exhaustion 断言 clock_error 存在。例外：_capture_once 对时钟读取期间的 CommunicationCancelled、HardwareStateError、AcquisitionResumeError 直接 re-raise，不写任何记录，已完成的光谱也不保存；按现有实现，此阶段实际能抛出的只有 CommunicationCancelled（软件停止时 _check_budget 触发），PollingCoordinator._poll_one 对它直接 return，也不写诊断。这是否属于本条“时钟读取异常”原文未定义，见 D-155。））
- 冲突：D-155 已裁决：读取时钟期间软件停止属于“时钟读取失败”，已完整读到的光谱仍保存（时钟为空，原因记“软件停止”），DEF-22 已修复（PR #30）（同 ACQ-008）
- 验证：tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_before_the_clock_request_keeps_the_spectrum_with_empty_clock；tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_while_the_clock_packet_is_in_flight_keeps_the_spectrum_with_empty_clock；tests/qt/test_clock_cancel_keeps_spectrum.py::test_stop_after_spectrum_and_clock_were_both_read_keeps_both；tests/qt/test_clock_cancel_keeps_spectrum.py::test_clock_protocol_error_while_running_records_the_exception_text；tests/qt/test_clock_cancel_keeps_spectrum.py::test_clock_budget_exhausted_while_running_records_the_timeout_text
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.read_standard_time；verify_polling.py PollingTests.test_completed_spectrum_survives_clock_budget_exhaustion

### ACQ-060 每台设备采集预算40秒（第2阶段）
- 规则：每台设备的采集预算为40秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 188 行「多设备重构：第 2 阶段（2026-09-17）」“当前每台采集预算40秒，耗尽预算及收尾可能超过40秒周期”
- 状态：待确认
- 现状符合度：符合（coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS=40.0。PollingCoordinator._capture_once 在 client.acquisition_budget(self._acquisition_budget(), …) 上下文内采集，由 ParModbusClient.acquisition_budget 设定 deadline。）
- 冲突：无；原与 POLL-039 同源（第188行），POLL-039 已于 2026-10-17 废止、由本条替代，与 ACQ-016（第27行）内容相近，誊抄阶段不合并
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py ACQUISITION_TRANSACTION_BUDGET_SECONDS；par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget

### ACQ-061 状态光谱光度参数与设备时间共用40秒采集轮预算
- 规则：自2026-10-11起，状态、701点光谱、光度参数及设备时间读取共用40秒采集轮预算。
- 来源：业务规则与变更日志_V1.0.2.md 第 190 行「多设备重构：第 2 阶段（2026-09-17）」“状态、701点光谱、光度参数及设备时间读取共用40秒采集轮预算（2026-10-11起）”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._capture_once 在同一个 client.acquisition_budget(40) 上下文内执行 read_spectrum_transaction（状态、光谱、光度参数）和 read_standard_time；见 verify_polling.py PollingTests.test_acquisition_round_budget_limits_single_capture。）
- 冲突：无；原与 POLL-043 同源（第190行），POLL-043 已于 2026-10-17 废止、由本条替代
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/protocol.py ParModbusClient.acquisition_budget；par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-062 所有波特率的采集冻结路径预留解冻时间
- 规则：所有波特率的采集冻结路径都须预留解冻时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“所有波特率的采集冻结路径预留解冻时间，超时后仍允许最多2秒独立清理”
- 状态：待确认
- 现状符合度：符合（ParModbusClient.read_spectrum_transaction 的冻结读取段使用 communication_budget(max(0, available - 2.0))，不区分波特率；见 verify_polling.py PollingTests.test_all_transports_freeze_before_read_and_confirm_resume 和 PollingTests.test_acquisition_thaws_after_budget_exhaustion。）
- 冲突：无；原与 POLL-047 同源（第192行），POLL-047 已于 2026-10-17 废止、由本条替代
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-063 采集预算超时后仍允许最多2秒独立清理
- 规则：采集冻结路径超时后，仍允许最多2秒独立清理。
- 来源：业务规则与变更日志_V1.0.2.md 第 192 行「多设备重构：第 2 阶段（2026-09-17）」“所有波特率的采集冻结路径预留解冻时间，超时后仍允许最多2秒独立清理”
- 状态：待确认
- 现状符合度：符合（read_spectrum_transaction 的 finally 中把 _deadline 置空、_finish_packet 置 False，在 communication_budget(2.0, lambda: False) 中执行 set_stop(False) 和 wait_stop(0)。清理失败时的上报分支：事务中此前没有硬件异常时，清理中抛出的 HardwareStateError 原样上抛、不包装，其他异常包装为 AcquisitionResumeError；事务中已有 HardwareStateError 时，清理异常一律被吞掉，原硬件异常继续上抛（见 ACQ-030、ACQ-046）。见 verify_polling.py PollingTests.test_freeze_failure_attempts_resume_within_budget。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；原与 POLL-050 同源（第192行），POLL-050 已于 2026-10-17 废止、由本条替代，与 ACQ-015（第27行）内容相近，誊抄阶段不合并
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_spectrum_transaction

### ACQ-064 硬件ee与旧400段计算值不新增通信读取
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/protocol.py ParModbusClient.read_status；par_app/protocol.py ParModbusClient.read_spectrum_transaction
