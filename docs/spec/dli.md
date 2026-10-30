# 日累计光积分（DLI）（DLI）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### DLI-001 各积分指标独立检查有限非负
- 规则：各 DLI 积分指标继续各自独立检查数值是否有限、非负；采集成功的记录不代表其每个指标都有效。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“各积分指标继续独立检查有限、非负数值；成功记录不代表每个指标都有效。”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_diagnostics 对每个指标分别做 float 转换，缺失或无法转换记为 NaN；DliCanvas.plot_dli 对每个序列单独判断 not isfinite 或 <0。回归测试：verify_multidevice.py verify_dli_calculation（NaN、inf、-1 分别判为无效）。无效值如何影响积分见 DLI-012。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/services/dli.py build_series

### DLI-002 失败记录dli_eligible=0
- 规则：采集失败记录的 dli_eligible 必须为0。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“不影响DLI候选资格。失败记录仍为0。各积分指标继续独立检查”
- 状态：待确认
- 现状符合度：符合（_capture_once 异常分支 save_acquisition 写 "dli_eligible": 0；verify_polling.py PollingTests.test_single_capture_failure_and_halt_precedence 断言为0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### DLI-003 完整成功的新记录dli_eligible=1
- 规则：完整成功读取的新采集记录必须设置 dli_eligible=1。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“完整成功读取的新记录设置 `dli_eligible=1`”
- 状态：待确认
- 现状符合度：符合（_capture_once 成功分支 save_acquisition 写 "dli_eligible": 1；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 断言为1。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### DLI-004 欠曝光不影响DLI候选资格
- 规则：欠曝光的成功记录仍具有 DLI 候选资格（dli_eligible 不因曝光状态改变）。
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“欠曝光不作为采集失败或警告，不影响DLI候选资格”
- 状态：待确认
- 现状符合度：符合（成功记录 dli_eligible 恒为1，与 exposure_status 无关；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### DLI-005 采集停止时记录DLI中断
- 规则：统一冻结读取语境下采集停止（恢复命令或运行状态未确认等）时，除将停止原因写入 diagnostics 外，还须记录 DLI 中断。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“原有硬件严重异常仍优先保留。停止原因写入diagnostics并记录DLI中断。”
- 状态：待确认
- 现状符合度：未验证（PollingCoordinator._halt_acquisition 对每台启用设备调用 database.save_dli_interruption(message)。例外路径：写入抛异常时被捕获，只追加到 log_errors，该设备不留下中断记录；_halt_reason 已存在时直接返回，因而每次运行至多写一轮中断记录。这一返回已作为 ACQ-030（原有硬件严重异常优先保留、不被覆盖）符合度的依据，锁停运行期不解除见 POLL-010；原文第31行没有“一次”的要求，该行为由这两条承接，不另立条目（shadow-rules.md 只登记数值字面量，不收这类控制流）。未找到断言锁停后 dli_interruptions 有记录的回归测试，verify_polling.py PollingTests.test_dli_preserves_invalid_sample_barriers 只直接调用 save_dli_interruption。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令（本条只约束停止时记录 DLI 中断）
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._halt_acquisition；par_app/database.py ParDatabase.save_dli_interruption

### DLI-006 单采曝光不决定DLI资格
- 规则：新单采记录的曝光状态不决定其 DLI 资格。
- 来源：业务规则与变更日志_V1.0.2.md 第 52 行「实时概览与历史回放（2026-10-11）」“新单采记录的曝光不决定采集成败、警告色或DLI资格”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._capture_once 成功分支固定写 dli_eligible=1，exposure_status 只保存；回归测试 verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd（曝光 0/1/2 均为 1）、verify_configuration.py verify_first_pages。资格不等于必然参与积分：指标值仍须有限非负，见 DLI-001、DLI-018。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/database.py ParDatabase.dli_samples

### DLI-007 旧记录复核未完成不计入DLI
- 规则：旧记录的“复核未完成”提示及不计入 DLI 的规则保留。按 D-126 裁决：dli_eligible 为空的旧记录，quality_json 标明复核未完成（confirmed 为 false，非单采记录，即历史详情显示“复核未完成”的记录）的不计入 DLI；没有任何复核信息的旧记录照旧计入（见 DLI-021）。
- 来源：业务规则与变更日志_V1.0.2.md 第 52 行「实时概览与历史回放（2026-10-11）」“旧记录的复核未完成提示及不计入DLI规则保留”；按 D-126 裁决（docs/spec/pending-decisions.md M7，负责人 2026-10-17 按推荐）“记录里标明复核未完成的，不计入 DLI”“两种信息都没有的，计入 DLI”
- 状态：待确认
- 现状符合度：不符合（V1.0.2：dli_eligible 为空的旧记录一律计入，复核未完成的也计入）；DEF-14 已修复（PR #34）：ParDatabase.dli_samples 与 ParDatabase.dli_minute_metrics 共用 database.DLI_ELIGIBLE_SQL 判定资格：success=1 且 COALESCE(dli_eligible,1)=1，并且 dli_eligible 为空的旧记录还要通过 database.legacy_review_incomplete 检查——quality_json 是 JSON 对象、confirmed 为 JSON false 且 strategy 不是 single_capture 时不计入；quality_json 为空、无法解析、不是对象、缺 confirmed 或取值不是 false（如 0、"false"、null）时视为没有复核信息，照旧计入。判断条件与 MainWindow._show_history_details 显示“复核未完成”一致（test_review_incomplete_display_matches_dli_exclusion 逐例核对）。dli_eligible 为 0 或 1 的记录只看 dli_eligible。只在读取样本时筛选，数据库中的 quality_json、dli_eligible 不改写，库结构不变（test_filter_does_not_rewrite_history_or_schema）。金样 test_legacy_records_marked_review_incomplete_are_excluded：08:10 的未复核旧记录不再计入，累计由 3.30 变为 3.18 mol·m⁻²，期望值由独立参考 tests/golden/reference.py dli_record_eligible 与闭式解给出。状态行（MainWindow._update_overview_status、MainWindow.show_history_spectrum）只按 dli_eligible==0 显示“复核未完成”，对 dli_eligible 为空、confirmed=false 的旧记录不显示（＝V1.0.2）；这是显示文字问题，不属 D-126（只定 DLI 资格）也不属 D-145（dli_eligible=0 的历史详情），已登记为 D-171（待裁决），裁决前保持现状；因此本条“符合”只指 DLI 资格与历史详情，状态行提示是否补齐见 D-171。confirmed 取 0、"false"、null，单采记录带 confirmed=false，quality_json 无法解析或不是对象这三类边界的处理，是按阶段一预授权的实现选择，待负责人在 PR #34 批准时确认（docs/spec/pending-decisions.md D-126 节“实现边界”）。
- 冲突：D-126 已裁决：旧记录里标明“复核未完成”的不计入 DLI，没有任何复核信息的旧记录照旧计入；“原资格”即采集成功即计入、复核未完成的不计入（按 L3 处理并用金样确认）；DEF-14 已修复（PR #34）。升级后部分历史日期的 DLI 可能变小（与 DLI-021 相关）。D-171 已裁决 2026-10-18（按推荐）：这类旧记录由阶段二新界面在状态行提示“复核未完成（不计入 DLI）”，阶段一不改
- 验证：tests/unit/test_dli_legacy_review.py::test_dli_samples_eligibility_of_legacy_and_new_records；tests/unit/test_dli_legacy_review.py::test_dli_minute_metrics_uses_the_same_eligibility；tests/unit/test_dli_legacy_review.py::test_unconfirmed_legacy_record_cuts_the_segment_in_order；tests/unit/test_dli_legacy_review.py::test_filter_does_not_rewrite_history_or_schema；tests/qt/test_dli_legacy_review_display.py::test_review_incomplete_display_matches_dli_exclusion；tests/qt/test_golden_dli.py::test_legacy_records_marked_review_incomplete_are_excluded
- 代码锚点：par_app/database.py ParDatabase.dli_samples；par_app/database.py ParDatabase.dli_minute_metrics；par_app/database.py legacy_review_incomplete；par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.show_history_spectrum；par_app/ui.py MainWindow._show_history_details

### DLI-008 DLI 按实际采样时间梯形积分
- 规则：DLI 按记录的实际采样时间，对有效的连续区段做梯形积分（(a+b)·Δt/2，换算为 mol·m⁻²）。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“DLI按实际采样时间对有效连续区段做梯形积分”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 对相邻有效点做 (prev+value)*seconds/2e6；审计 data-correctness 一-9 恒定/正弦/缺测/跨午夜复算一致；verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/services/dli.py build_series

### DLI-009 DLI 支持最长 3600 秒轮询周期
- 规则：DLI 允许间隔规则须支持轮询周期最长 3600 秒的情形（此时允许间隔为 3660 秒）。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“允许间隔为`max(120秒, 当前轮询周期+60秒)`，支持最长3600秒轮询”
- 状态：待确认
- 现状符合度：符合（MAX_POLL_CYCLE_SECONDS=3600，effective_poll_cycle_seconds 上限截断后用于 max_gap 计算。未见 3600 秒周期的专门 DLI 测试。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/models.py MAX_POLL_CYCLE_SECONDS；par_app/models.py AppConfig.effective_poll_cycle_seconds；par_app/services/dli.py max_gap_seconds；par_app/ui.py MainWindow.refresh_diagnostics

### DLI-010 允许间隔 max(120, 周期+60)
- 规则：DLI 相邻有效点允许的最大间隔为 max(120 秒, 当前轮询周期 + 60 秒)，超过即视为超长空档。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“允许间隔为`max(120秒, 当前轮询周期+60秒)`”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics: max_gap_seconds = max(120.0, effective_poll_cycle_seconds() + 60.0) 传给 plot_dli。注：公式散写在 UI，未按 R-1-4 抽为命名函数。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py max_gap_seconds；par_app/services/dli.py integrate

### DLI-011 切段恢复后继续累计
- 规则：DLI 切段后数据恢复时，在此前累计值基础上继续累计，不清零。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“失败、旧复核不合格记录、无效指标、显式中断及超长空档均切段，不补零、不跨段积分，恢复后继续累计并标记“部分累计””
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 的 current 跨段保留，只在新段相邻有效点间继续累加；回归测试 verify_multidevice.py verify_dli_calculation：三段各 0.006，合计 0.018）。
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-012 失败、不合格、无效、中断、超长空档切段
- 规则：失败记录、旧复核不合格记录、无效指标、显式中断及超长空档均使 DLI 积分切段。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“失败、旧复核不合格记录、无效指标、显式中断及超长空档均切段，不补零、不跨段积分，恢复后继续累计并标记“部分累计””
- 状态：待确认
- 现状符合度：不符合（V1.0.2：复核未完成的旧记录仍计入 DLI）；DEF-14 已修复（PR #34）：ParDatabase.dli_samples 将 success=0 或 dli_eligible=0 的记录、dli_eligible 为空且 quality_json 标明复核未完成的旧记录（D-126，见 DLI-007）与 dli_interruptions 行标为 eligible=0，MainWindow.refresh_diagnostics 对其置 NaN；DliCanvas.plot_dli 遇 NaN/负值或间隔超过 max_gap 时重新起段。说明：refresh_diagnostics 对时间戳无法解析的行直接跳过，不作断点，正常写入路径不产生此类行。回归测试 verify_polling.py PollingTests.test_dli_preserves_invalid_sample_barriers、verify_multidevice.py verify_dli_calculation。不补零、不跨段积分见 DLI-047、DLI-048。
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.dli_samples；par_app/database.py ParDatabase.save_dli_interruption；par_app/services/dli.py integrate；par_app/services/dli.py build_series

### DLI-013 空档判定随当前轮询周期变化
- 规则：空档判定使用当前轮询周期而非记录当时的周期；更改轮询周期会改变历史中无显式中断空档的判定结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“更改轮询周期会改变无显式中断的历史空档判定”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 每次用 hub.config 的当前周期计算 max_gap 并对整段历史重算；审计 data-correctness 三-6 确认。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics；par_app/services/dli.py max_gap_seconds

### DLI-014 DLI 仅用正式启用时间之后的记录
- 规则：DLI 只使用正式启用时间之后的记录，该规则不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“正式启用时间、日出起算的24小时周期及未来记录排除规则不变”
- 状态：待确认
- 现状符合度：符合（ParDatabase.load_dli_enabled_at 首次写入 dli_enabled_at；dli_samples 以 acquired_at >= enabled_at 过滤并排除带时区的旧记录。2.0：API-10 第一次读取设备而库中没有启用时间时同样写入，`par_app/application/dli_enable.py`，D-228 A。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.load_dli_enabled_at；par_app/database.py ParDatabase.dli_samples

### DLI-015 DLI 周期为日出起算固定 24 小时
- 规则：DLI 积分周期从（按保存的经纬度计算的）日出时刻起算，固定 24 小时，该规则不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“正式启用时间、日出起算的24小时周期及未来记录排除规则不变”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；旧审计 #23（robustness-ui Bug 8）已修复（PR #26）：services/dli.py dli_period（MainWindow._dli_period 为薄包装，取北京时间后调用）在 sunrise（NOAA 近似，UTC+8）算出的 d-2～d+1 四天日出中取不晚于当前时刻的最晚一个作为 start，end=start+1 天，国内经度结果与 V1.0.2 相同；库中经度越界导致候选全晚于当前时刻时退回 V1.0.2 选法（昨日日出），不抛异常。空档期：某天日出比前一天日出加 24 小时更晚时，两者之间的空档内返回刚结束的周期（国内每次至多约 2 分钟，与 V1.0.2 相同），按 D-165 裁决保持现状。（V1.0.2 现状：MainWindow._dli_period 只在今日与昨日日出之间选择，国内经度符合；经度远离东八区时周期可能不含当前时刻。）
- 冲突：D-165 已裁决：空档期保持现状
- 验证：tests/qt/test_dli_period.py::test_far_longitude_period_contains_now；tests/qt/test_dli_period.py::test_beijing_gap_keeps_just_ended_period；tests/qt/test_dli_period.py::test_gap_between_periods_keeps_just_ended_period；tests/qt/test_dli_period.py::test_period_starts_at_latest_sunrise_not_after_now；tests/qt/test_dli_period.py::test_domestic_period_unchanged_from_v102；tests/qt/test_dli_period.py::test_sunrise_instant_starts_new_period；tests/qt/test_dli_period.py::test_out_of_range_longitude_does_not_raise；tests/unit/test_services_dli.py::test_period_starts_at_the_last_sunrise_and_lasts_24h；tests/unit/test_services_dli.py::test_d165_gap_before_a_later_sunrise_shows_the_period_that_just_ended
- 代码锚点：par_app/services/dli.py dli_period；par_app/services/dli.py sunrise

### DLI-016 DLI 排除未来记录
- 规则：时间晚于当前观测时刻的记录不参与 DLI 积分，该规则不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“正式启用时间、日出起算的24小时周期及未来记录排除规则不变”
- 状态：待确认
- 现状符合度：符合（plot_dli 以 cutoff=min(max(observed_until, start), end) 跳过 timestamp > cutoff 的点；verify_multidevice.py verify_dli_calculation 断言 end 处 999 未计入。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py MainWindow.refresh_diagnostics

### DLI-017 四项 DLI 指标独立检查
- 规则：PPFD、McCree YPFD、叶绿素A、叶绿素B 四项 DLI 指标各自独立判定有效性，某一项缺失不影响其他指标继续积分。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“四项指标独立检查，不因单项缺失使其他指标停止”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 对每个 metric 单独 float 转换，缺失只在该序列置 NaN，四个 DliCanvas 各自积分。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py build_series；par_app/ui.py MainWindow.refresh_diagnostics

### DLI-018 有限非负才有效，零值有效
- 规则：只有有限且非负的指标值才形成 DLI 有效点；零值是有效数据，不视为缺失。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“有限非负指标才形成有效点，零值是有效数据”
- 状态：待确认
- 现状符合度：符合（plot_dli: `not np.isfinite(value) or value < 0` 视为无效，0 参与积分；verify_multidevice.py verify_dli_calculation 覆盖 [0,0] 覆盖 60 秒、NaN/inf/-1 无效。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-019 欠曝光单采记录参与积分
- 规则：新单次采集记录即使欠曝光，仍可参与 DLI 积分（曝光状态不决定 DLI 资格）。
- 来源：业务规则与变更日志_V1.0.2.md 第 95 行「单次采集与分段 DLI（2026-10-11）」“新单采记录欠曝光仍可参与积分；有限非负指标才形成有效点”
- 状态：待确认
- 现状符合度：符合（_capture_once 成功记录固定 dli_eligible=1，曝光状态仅记录；verify_polling.py PollingTests.test_single_capture_is_independent_of_exposure_and_ppfd 覆盖 exposure=2。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once

### DLI-020 历史异常峰值不自动删改
- 规则：历史记录中的异常峰值不自动删除或修正。
- 来源：业务规则与变更日志_V1.0.2.md 第 96 行「单次采集与分段 DLI（2026-10-11）」“历史异常峰值不自动删除或修正。本次只使用临时库与模拟通信验证”
- 状态：待确认
- 现状符合度：符合（par_app 中无对 acquisitions/spectra 的 UPDATE 或 DELETE 语句（ParDatabase 只有 INSERT 与 SELECT）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.save_acquisition

### DLI-021 旧记录无质量标记沿用原资格
- 规则：旧记录无质量标记时，沿用原 DLI 资格。按 D-126 裁决，“原资格”即采集成功即计入、复核未完成的不计入：dli_eligible 为空且没有任何复核信息的旧记录，采集成功即计入 DLI；标明复核未完成的见 DLI-007。
- 来源：业务规则与变更日志_V1.0.2.md 第 96 行「单次采集与分段 DLI（2026-10-11）」“旧记录无质量标记时沿用原资格，历史异常峰值不自动删除或修正”；按 D-126 裁决（docs/spec/pending-decisions.md M7，负责人 2026-10-17 按推荐）“两种信息都没有的，计入 DLI，显示「未记录」（现状）”
- 状态：待确认
- 现状符合度：符合（分支 fix/dli-legacy-unconfirmed 修复 DEF-14 后：ParDatabase.dli_samples 与 ParDatabase.dli_minute_metrics 共用 database.DLI_ELIGIBLE_SQL 判定资格：success=1 且 COALESCE(dli_eligible,1)=1，并且 dli_eligible 为空的旧记录还要通过 database.legacy_review_incomplete 检查——quality_json 是 JSON 对象、confirmed 为 JSON false 且 strategy 不是 single_capture 时不计入；quality_json 为空、无法解析、不是对象、缺 confirmed 或取值不是 false（如 0、"false"、null）时视为没有复核信息，照旧计入。判断条件与 MainWindow._show_history_details 显示“复核未完成”一致（test_review_incomplete_display_matches_dli_exclusion 逐例核对）。dli_eligible 为 0 或 1 的记录只看 dli_eligible。只在读取样本时筛选，数据库中的 quality_json、dli_eligible 不改写，库结构不变（test_filter_does_not_rewrite_history_or_schema）。金样 test_legacy_records_marked_review_incomplete_are_excluded：08:10 的未复核旧记录不再计入，累计由 3.30 变为 3.18 mol·m⁻²，期望值由独立参考 tests/golden/reference.py dli_record_eligible 与闭式解给出。）
- 冲突：D-126 已裁决：旧记录里标明“复核未完成”的不计入 DLI，没有任何复核信息的旧记录照旧计入；“原资格”即采集成功即计入、复核未完成的不计入（按 L3 处理并用金样确认）；DEF-14 已修复（PR #34）（与 DLI-007 相关）
- 验证：tests/unit/test_dli_legacy_review.py::test_dli_samples_eligibility_of_legacy_and_new_records；tests/unit/test_dli_legacy_review.py::test_dli_minute_metrics_uses_the_same_eligibility；tests/qt/test_golden_dli.py::test_legacy_records_marked_review_incomplete_are_excluded；tests/unit/test_polling_protocol.py::test_quality_schema_upgrade_preserves_old_records
- 代码锚点：par_app/database.py ParDatabase.dli_samples；par_app/database.py ParDatabase.dli_minute_metrics；par_app/database.py legacy_review_incomplete

### DLI-022 DLI固定24小时周期不变
- 规则：DLI 页布局调整后，固定 24 小时的积分周期不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 259 行「页面布局与显示（2026-09-19）」“DLI当前布局见下方“光积累计算显示”；积分算法、缺测断线和固定24小时周期不变”
- 状态：待确认
- 现状符合度：符合（MainWindow._dli_period 返回 (start, start+1天)；回归测试 verify_multidevice.py verify_dli_page（周期标签含“固定24小时”，横轴两端为 10-11 06:19 与 10-12 06:19）。日出起算另见 DLI-015。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py dli_period

### DLI-023 布局调整后DLI积分算法不变
- 规则：DLI 页布局调整后，积分算法不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 259 行「页面布局与显示（2026-09-19）」“DLI当前布局见下方“光积累计算显示”；积分算法、缺测断线和固定24小时周期不变”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 仍为相邻有效点梯形积分 (a+b)·Δt/2/1e6；审计 data-correctness 一.9 复算通过；回归测试 verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-024 保存位置不重置DLI启用时间
- 规则：点击保存 DLI 位置不重置 DLI 启用时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 264 行「光积累计算显示（2026-10-11 更新）」“点击保存才重算当前设备的显示周期；不重置DLI启用时间、不改写历史采集记录”
- 状态：待确认
- 现状符合度：符合（MainWindow._save_dli_location 只调用 ParDatabase.save_dli_location 写 app_settings 的 dli_location 键并刷新；ParDatabase.load_dli_enabled_at 只在键缺失时首次写入。回归测试 verify_multidevice.py verify_dli_page：保存后 load_dli_enabled_at() 与保存前相同。2.0：`PUT /devices/{key}/dli/location` 同样只写 dli_location，`tests/api/test_dli_location.py` 断言启用时间不变，#116。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._save_dli_location；par_app/database.py ParDatabase.save_dli_location；par_app/database.py ParDatabase.load_dli_enabled_at

### DLI-025 保存位置后才重算周期
- 规则：编辑经纬度输入框不立即生效；仅点击“保存经纬度并重置周期”后才按新位置重算当前设备的DLI显示周期。
- 来源：业务规则与变更日志_V1.0.2.md 第 264 行「光积累计算显示（2026-10-11 更新）」“编辑位置尚不生效，点击保存才重算当前设备的显示周期”
- 状态：待确认
- 现状符合度：符合（_dli_period 使用 self.dli_location，该值只在 _save_dli_location（写入当前设备库）和切换设备时更新，输入框编辑不触发。2.0：页面输入框只在点“保存经纬度并重置周期”后提交，`web/tests/dli.test.ts`，#116。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._save_dli_location；par_app/ui.py MainWindow._dli_period；par_app/database.py ParDatabase.save_dli_location

### DLI-026 经纬度正负号约定
- 规则：DLI位置输入中纬度正值为北纬、负值为南纬；经度正值为东经、负值为西经。
- 来源：业务规则与变更日志_V1.0.2.md 第 264 行「光积累计算显示（2026-10-11 更新）」“正纬度为北纬、负值为南纬；正经度为东经、负值为西经”
- 状态：待确认
- 现状符合度：符合（_build_diagnostics 标签“纬度（°N）/经度（°E）”及悬停提示“正值为北纬，负值为南纬/正值为东经，负值为西经”；_sunrise 按东经为正计算。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_diagnostics；par_app/services/dli.py sunrise

### DLI-027 DLI布局调整不改积分逻辑
- 规则：DLI 页布局调整不改变积分逻辑。
- 来源：业务规则与变更日志_V1.0.2.md 第 265 行「光积累计算显示（2026-10-11 更新）」“高度不足时页面纵向滚动，不通过撑大窗口改变菜单尺寸。字号、积分逻辑不变”
- 状态：待确认
- 现状符合度：符合（积分仍由 DliCanvas.plot_dli 计算；回归测试 verify_multidevice.py verify_dli_calculation 断言既有梯形、覆盖、缺测与未来记录排除结果不变。同句“字号不变”按覆盖矩阵第 265 行归为纯视觉要求，不在本条约束。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-028 DLI不向当前时刻外推
- 规则：DLI 累计不向当前时刻外推。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“保持原有梯形积分与分段规则，不跨缺测积分、不补零、不向当前时刻外推”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 只在相邻有效点之间累加；最后有效点至截至时刻的尾段只计入 tail_seconds 未覆盖时长，不产生积分。回归测试 verify_multidevice.py verify_dli_calculation：尾部 140 秒未覆盖时累计仍为 0.018。累计截至时间的定义见 DLI-039。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-029 DLI不跨缺测积分
- 规则：DLI 不跨缺测积分。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“保持原有梯形积分与分段规则，不跨缺测积分、不补零、不向当前时刻外推”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli：非有限或负值使 previous=None；相邻有效点间隔超过 max_gap_seconds 时不累加。回归测试 verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-030 DLI保持原有梯形积分
- 规则：DLI 保持原有梯形积分。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“保持原有梯形积分与分段规则，不跨缺测积分、不补零、不向当前时刻外推”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli：相邻有效点间隔在 [0, max_gap] 内累加 (a+b)·Δt/2/1e6；审计 data-correctness 一.9 恒定/正弦/缺测/跨午夜复算一致；回归测试 verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-031 同次刷新共用截至时间
- 规则：一次DLI刷新中四个指标使用同一个统计截至时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“同一次刷新共用截至时间，忽略尚未到时的记录”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 只计算一次 observed_until 并传给四个 plot_dli。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics

### DLI-032 四项指标独立判断缺值与完整性
- 规则：PPFD、McCree YPFD、叶绿素A、叶绿素B四项DLI各自独立判断缺值、连续区段和完整性状态，不共用PPFD的状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“四项指标各自判断缺值、连续区段和完整性，不再共用PPFD的状态”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 为每个指标单独构建时间/数值序列，四个 DliCanvas.plot_dli 各自计算 state/覆盖。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py build_series；par_app/services/dli.py integrate

### DLI-033 忽略晚于截至时间的记录
- 规则：时间戳晚于本次截至时间（尚未到时）的记录不参与积分。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“同一次刷新共用截至时间，忽略尚未到时的记录”
- 状态：待确认
- 现状符合度：符合（plot_dli：timestamp > cutoff 或 ≥ period_end 的样本直接跳过。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-034 无记录或单点显示有效数据不足
- 规则：周期内无记录或仅有一个有效点时，累计值显示“—”，状态显示“有效数据不足”。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“只有形成有效连续时间区间才显示累计数值；无记录或仅一个有效点显示「— / 有效数据不足」”
- 状态：待确认
- 现状符合度：符合（plot_dli：covered_seconds==0 → state='有效数据不足' 且图中央显示同文案；_update_header 累计值为“—”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py DliCanvas.plot_dli；par_app/ui.py DliCanvas._update_header

### DLI-035 有效连续区间才显示累计值
- 规则：只有至少形成一个有效连续时间区间（覆盖时长>0）时才显示累计数值。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“只有形成有效连续时间区间才显示累计数值；无记录或仅一个有效点显示「— / 有效数据不足」”
- 状态：待确认
- 现状符合度：符合（_update_header：covered_seconds>0 才格式化 total，否则显示“—”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._update_header；par_app/ui.py DliCanvas.plot_dli；par_app/services/dli.py integrate

### DLI-036 有效零光照区间显示0.000
- 规则：有效连续区间内光照值均为0时，累计值显示“0.000”而非“—”。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“无记录或仅一个有效点显示「— / 有效数据不足」，有效零光照区间显示「0.000」”
- 状态：待确认
- 现状符合度：符合（plot_dli 只排除非有限或负值，0 为有效点；covered_seconds>0 时 _update_header 以 .3f 输出 0.000。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py DliCanvas._update_header

### DLI-037 孤立有效点另显示最新有效时间
- 规则：若最后积分区段之后只出现孤立有效点（未形成区段），额外显示“最新有效”时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 267 行「光积累计算显示（2026-10-11 更新）」“累计截至时间指最后一个完成积分的区段终点；若后来只有孤立有效点，另显示最新有效时间”
- 状态：待确认
- 现状符合度：符合（_update_header：last_valid != integrated_until 时追加“　最新有效：…”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._update_header

### DLI-038 未覆盖时长含起始内部尾部缺测
- 规则：DLI 未覆盖时长包含起始、内部和尾部缺测。
- 来源：业务规则与变更日志_V1.0.2.md 第 267 行「光积累计算显示（2026-10-11 更新）」“未覆盖时长包含起始、内部和尾部缺测，可悬停查看分项与统计截至时间”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli：missing = elapsed − covered，其中 head = 首个有效点 − 周期开始，internal = (最后有效点 − 首个有效点) − covered，tail = 截至时刻 − 最后有效点，三者之和等于 missing；回归测试 verify_multidevice.py verify_dli_calculation（missing 720 = 内部 580 + 尾部 140）。悬停展示见 DLI-053。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-039 累计截至为最后积分区段终点
- 规则：“累计截至时间”取最后一个完成积分的有效区段的终点时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 267 行「光积累计算显示（2026-10-11 更新）」“累计截至时间指最后一个完成积分的区段终点；若后来只有孤立有效点，另显示最新有效时间”
- 状态：待确认
- 现状符合度：符合（plot_dli：仅在 0<间隔≤max_gap 完成累加时更新 integrated_until。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-040 覆盖率分母为周期已过去时长
- 规则：覆盖率 = 有效连续区段总时长 ÷（本周期开始至统计截至时刻的已过去时长），不以完整24小时或样本数为分母。
- 来源：业务规则与变更日志_V1.0.2.md 第 267 行「光积累计算显示（2026-10-11 更新）」“覆盖率为有效连续区段时长除以本周期开始至截至时刻的已过去时长，不以完整24小时或样本数量为分母”
- 状态：待确认
- 现状符合度：符合（plot_dli：coverage = covered_seconds / (cutoff − period_start)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-041 DLI状态随定时刷新更新
- 规则：DLI页打开时随界面定时刷新更新状态与截至时间，不依赖是否有新增采集记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 268 行「光积累计算显示（2026-10-11 更新）」“页面打开时随定时刷新更新状态，不依赖新增采集记录”
- 状态：待确认
- 现状符合度：符合（MainWindow 3秒定时器调用 refresh_all；当前页为 DLI 时每次都调用 refresh_diagnostics（以当前时间为截至），与 _refresh_data_key 无关。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_all；par_app/ui.py MainWindow.refresh_diagnostics

### DLI-042 数据未更新时保留此前累计
- 规则：出现“数据未更新”时保留并显示此前已累计的数值，不清零。
- 来源：业务规则与变更日志_V1.0.2.md 第 268 行「光积累计算显示（2026-10-11 更新）」“最后有效点超过允许间隔时显示「数据未更新」及持续时长，保留此前累计”
- 状态：待确认
- 现状符合度：符合（stale 只影响状态文本；total/cumulative 不变，_update_header 照常显示已累计值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._update_header

### DLI-043 暂停/停用/锁定时显示采集已暂停
- 规则：采集处于暂停（维护等）、当前设备停用或全局锁定时，DLI状态显示“采集已暂停”。
- 来源：业务规则与变更日志_V1.0.2.md 第 268 行「光积累计算显示（2026-10-11 更新）」“采集暂停、设备停用或全局锁定时显示「采集已暂停」”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 的 paused = 维护中/halt_reason/线程未运行/未配置/设备未启用/设备已退出(excluded)；_update_header 追加“ · 采集已暂停”。代码另把失败停止退出(excluded)也视为暂停，原文未列。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令（本条只约束锁定时的显示）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics；par_app/ui.py DliCanvas._update_header

### DLI-044 超允许间隔显示数据未更新
- 规则：统计截至时刻距最后有效点超过允许间隔时，状态显示“数据未更新”及已持续时长。
- 来源：业务规则与变更日志_V1.0.2.md 第 268 行「光积累计算显示（2026-10-11 更新）」“最后有效点超过允许间隔时显示「数据未更新」及持续时长，保留此前累计”
- 状态：待确认
- 现状符合度：符合（plot_dli：stale = tail_seconds > max_gap_seconds；_update_header 追加“ · 数据未更新（时分秒）”。允许间隔 max(120, 周期+60) 由 refresh_diagnostics 传入。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py DliCanvas._update_header；par_app/ui.py MainWindow.refresh_diagnostics

### DLI-045 DLI显示调整不改软件指标
- 规则：DLI 显示调整不改变软件指标。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“纵轴从零开始；不改变软件指标、采集通信、数据库结构或历史值”
- 状态：待确认
- 现状符合度：未验证（DLI 页只从 software_metrics_json 读取指标值，不调用 math_ops.software_metrics；但无调整前后指标计算的对照证据。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics；par_app/math_ops.py software_metrics

### DLI-046 切段恢复后标记部分累计
- 规则：DLI 切段后数据恢复继续累计时，状态标记为“部分累计”。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“失败、旧复核不合格记录、无效指标、显式中断及超长空档均切段，不补零、不跨段积分，恢复后继续累计并标记“部分累计””
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 遇无效值或超长空档置 partial=True，covered_seconds>0 时 state='部分累计'，DliCanvas._update_header 显示该状态；回归测试 verify_multidevice.py main（NaN 断点后 state=='部分累计'）。另：代码在起始空档超过允许间隔或数据未更新时也标“部分累计”，原文本句未列。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py DliCanvas._update_header

### DLI-047 分段DLI不补零
- 规则：DLI 积分不补零。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“失败、旧复核不合格记录、无效指标、显式中断及超长空档均切段，不补零、不跨段积分，恢复后继续累计并标记“部分累计””
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 对缺测和无效点不插入 0 值，只在曲线中插入 NaN 断线，空档不产生积分；回归测试 verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-048 分段DLI不跨段积分
- 规则：DLI 不跨段积分。
- 来源：业务规则与变更日志_V1.0.2.md 第 94 行「单次采集与分段 DLI（2026-10-11）」“失败、旧复核不合格记录、无效指标、显式中断及超长空档均切段，不补零、不跨段积分，恢复后继续累计并标记“部分累计””
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 遇无效值将 previous 置空，间隔超过 max_gap 不累加，因此断点两侧的点不构成积分区间；回归测试 verify_multidevice.py verify_dli_calculation、verify_polling.py PollingTests.test_dli_preserves_invalid_sample_barriers。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/database.py ParDatabase.dli_samples

### DLI-049 布局调整后缺测断线不变
- 规则：DLI 页布局调整后，缺测断线规则不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 259 行「页面布局与显示（2026-09-19）」“DLI当前布局见下方“光积累计算显示”；积分算法、缺测断线和固定24小时周期不变”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 在无效点和超长空档处向累计曲线插入 NaN，使曲线断开；回归测试 verify_multidevice.py verify_dli_calculation 断言曲线含 2 个 NaN 断点。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/ui.py DliCanvas.plot_dli

### DLI-050 保存位置不改写历史采集记录
- 规则：点击保存 DLI 位置不改写历史采集记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 264 行「光积累计算显示（2026-10-11 更新）」“点击保存才重算当前设备的显示周期；不重置DLI启用时间、不改写历史采集记录”
- 状态：待确认
- 现状符合度：符合（ParDatabase.save_dli_location 只 upsert app_settings 的 dli_location 键；随后的 MainWindow.refresh_diagnostics 经 ParDatabase.dli_samples 只读 acquisitions。回归测试 verify_multidevice.py verify_dli_page 只断言保存后记录条数仍为 8，未逐值比对。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.save_dli_location；par_app/ui.py MainWindow._save_dli_location

### DLI-051 DLI不补零
- 规则：DLI 不对缺测补零。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“保持原有梯形积分与分段规则，不跨缺测积分、不补零、不向当前时刻外推”
- 状态：待确认
- 现状符合度：符合（DliCanvas.plot_dli 对缺测不插入 0 值，空档不产生积分；回归测试 verify_multidevice.py verify_dli_calculation。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate

### DLI-052 DLI保持原有分段规则
- 规则：DLI 保持原有分段规则。
- 来源：业务规则与变更日志_V1.0.2.md 第 266 行「光积累计算显示（2026-10-11 更新）」“保持原有梯形积分与分段规则，不跨缺测积分、不补零、不向当前时刻外推”
- 状态：待确认
- 现状符合度：符合（分段触发与第 94 行一致，见 DLI-012：失败、旧复核不合格、无效指标、显式中断、超长空档；实现于 ParDatabase.dli_samples 与 DliCanvas.plot_dli；回归测试 verify_multidevice.py verify_dli_calculation、verify_polling.py PollingTests.test_dli_preserves_invalid_sample_barriers。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/dli.py integrate；par_app/database.py ParDatabase.dli_samples

### DLI-053 悬停查看未覆盖分项与截至时间
- 规则：DLI 未覆盖时长可悬停查看起始、内部、尾部分项与统计截至时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 267 行「光积累计算显示（2026-10-11 更新）」“未覆盖时长包含起始、内部和尾部缺测，可悬停查看分项与统计截至时间”
- 状态：待确认
- 现状符合度：符合（DliCanvas._update_header 为 header_coverage 设置悬停提示，列出截至时间（北京时间）及起始/内部/尾部未覆盖；回归测试 verify_multidevice.py verify_dli_page（提示含“内部未覆盖”）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._update_header

### DLI-054 DLI显示调整不改采集通信
- 规则：DLI 显示调整不改变采集通信。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“纵轴从零开始；不改变软件指标、采集通信、数据库结构或历史值”
- 状态：待确认
- 现状符合度：未验证（DLI 页代码不调用 ParModbusClient；但无调整前后采集通信行为的对照证据。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics；par_app/protocol.py ParModbusClient

### DLI-055 DLI显示调整不改数据库结构
- 规则：DLI 显示调整不改变数据库结构。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“纵轴从零开始；不改变软件指标、采集通信、数据库结构或历史值”
- 状态：待确认
- 现状符合度：未验证（DLI 页只写 app_settings 的 dli_location、dli_enabled_at 键，只读 acquisitions、dli_interruptions，DLI 路径本身不执行 DDL；表结构定义在 ParDatabase.initialize，但无调整前后结构的对照证据。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.initialize；par_app/database.py ParDatabase.dli_samples

### DLI-056 DLI显示调整不改历史值
- 规则：DLI 显示调整不改变历史值。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“纵轴从零开始；不改变软件指标、采集通信、数据库结构或历史值”
- 状态：待确认
- 现状符合度：未验证（DLI 相关路径对 acquisitions 只读（ParDatabase.dli_samples），写入只有 app_settings 的位置与启用时间；无调整前后历史值的对照证据。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.dli_samples；par_app/database.py ParDatabase.save_dli_location
