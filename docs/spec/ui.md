# 界面行为（UI）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### UI-001 冻结版使用随包字体
- 规则：冻结（发布）版必须使用随包的 Noto Sans SC 字体，不依赖系统固定字体路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 13 行「V1.0.2 交付（2026-10-12）」“`resources/fonts` 保存Noto Sans SC原始字体与OFL许可，冻结版使用随包字体。”
- 状态：待确认
- 现状符合度：符合（runtime_paths.chinese_font_path 在 frozen 时返回随包字体（仅开发环境才优先 simhei）；release_self_test 在 frozen 时断言 CHINESE_FONT_PATH 等于随包字体。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/runtime_paths.py chinese_font_path；par_app/release_self_test.py run_release_self_test

### UI-002 单采记录不因欠曝光变为警告色
- 规则：新单采记录不得仅因欠曝光而使实时/设置状态显示为警告。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“实时和设置状态仍显示曝光信息，但不再仅因新单采记录欠曝光变为警告”
- 状态：待确认
- 现状符合度：符合（_update_overview_status 仅对非单采旧记录在曝光非正常时用琥珀色；refresh_settings_console 颜色仅取决于 level（单采成功为 ok）。历史列表“曝光”列对非正常仍着橙色，属历史表而非实时/设置状态。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.refresh_settings_console

### UI-003 历史详情字段名为“采集校验”
- 规则：历史详情中原复核字段的名称改为“采集校验”。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“历史详情字段改为「采集校验」，新成功记录显示「单次读取完成」”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history 创建 ("review","采集校验") 字段。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-004 实时与设置状态仍显示曝光信息
- 规则：实时概览状态和设置页连接状态仍显示曝光信息。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“实时和设置状态仍显示曝光信息，但不再仅因新单采记录欠曝光变为警告”
- 状态：待确认
- 现状符合度：不符合（按 D-144 裁决需修改，待修复。按裁决，设置页连接状态在非成功状态下也须显示最近一次记录的曝光信息；现状 MainWindow.refresh_settings_console 只在 level=="ok" 时显示。原核对（未验证）：实时概览：MainWindow._update_overview_status 状态卡始终含“曝光：…”。设置页：MainWindow.refresh_settings_console 仅在 level=="ok" 时追加“曝光：…”；状态为 warning/error/power 等非 ok 时（例如已有曝光快照但后续通信失败）设置状态不显示曝光。原文未把曝光展示限定为成功状态，非 ok 时是否仍须显示待确认。）
- 冲突：D-144 已裁决：设置页连接状态在非成功状态下也显示最近一次记录的曝光信息，待修复（DEF-19）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.refresh_settings_console

### UI-005 新单采成功记录显示“单次读取完成”
- 规则：strategy 为 single_capture 的成功记录，采集校验显示“单次读取完成”。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“历史详情字段改为「采集校验」，新成功记录显示「单次读取完成」”
- 状态：待确认
- 现状符合度：符合（MainWindow._show_history_details 中 _is_single_capture 且成功时 review="单次读取完成"；实时状态卡与历史图状态卡同样追加。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details；par_app/ui.py MainWindow._is_single_capture

### UI-006 旧记录展示原复核结果，缺标记为“未记录”
- 规则：非单采的旧记录仍展示原复核结果；缺少审计标记时显示“未记录”。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“旧记录仍展示原复核结果，缺少审计标记仍为「未记录」”
- 状态：待确认
- 现状符合度：符合（按 D-145 裁决，缺审计标记但 dli_eligible=0 的旧记录显示“复核未完成”：MainWindow._show_history_details 判定顺序为失败→“未完成采集”；单采成功→“单次读取完成”；dli_eligible==0 或 confirmed is False→“复核未完成”；confirmed is True→“已完成”；否则“未记录”。非单采旧记录展示原复核结果，缺审计标记且 dli_eligible 不为 0 时显示“未记录”。）
- 冲突：D-145 已裁决：缺复核审计标记但 dli_eligible=0 的旧记录显示“复核未完成”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details

### UI-007 锁停时提示“恢复未确认”
- 规则：恢复未确认锁停时，界面须明确提示“恢复未确认”，并说明硬件实际状态不确定。
- 来源：业务规则与变更日志_V1.0.2.md 第 31 行「统一冻结读取（2026-10-11）」“提示「恢复未确认」，硬件实际状态不确定，不伪造未初始化或要求上电的状态位”
- 状态：待确认
- 现状符合度：符合（MainWindow._show_hardware_stop 对 resume_unconfirmed 显示“恢复命令或运行状态未确认…硬件实际状态尚不确定”；总线摘要“已停止（恢复未确认）”；verify_configuration.verify_resume_stop_ui。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_hardware_stop；par_app/ui.py MainWindow._refresh_communication_events

### UI-008 界面测试覆盖恢复未确认提示与持续红色停止
- 规则：界面测试须覆盖恢复未确认的明确提示以及持续的红色停止状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“界面测试覆盖明确提示和持续红色停止。未占用在线串口”
- 状态：待确认
- 现状符合度：符合（tests/qt/test_resume_stop_ui.py 在 _halt_acquisition 后 refresh_all，断言总线摘要含“恢复未确认”、弹窗含“硬件实际状态尚不确定”且只弹一次、acquisition_state_label 为“采集停止中”且 #dc2626；随后经 MainWindow.save_local_settings 保存配置、由协调器应用排队的配置（重建运行时状态）并再次 refresh_all，再次断言上述红色停止状态与总线摘要仍保持、弹窗未重复。ParModbusClient 被替换，未占用在线串口。原测试缺口 DEF-08 已补测试（PR #22）。）
- 冲突：缺陷：测试缺口，保存配置后未再次断言红色停止状态（DEF-08，已补测试（PR #22））
- 验证：tests/qt/test_resume_stop_ui.py::test_resume_unconfirmed_red_stop_persists_after_saving_config
- 代码锚点：verify_configuration.py verify_resume_stop_ui

### UI-009 全部指标对应当前显示记录
- 规则：点击“全部指标”打开当前所显示记录的分组详情（与历史详情同一组指标）；最新一轮采集失败时，详情仍对应保留显示的最近有效光谱记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“「全部指标」打开当前所显示记录的分组详情；失败后仍与保留的最近有效光谱对应”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._show_overview_metric_details 使用 self._overview_record（= ParDatabase.latest_successful_spectrum 的记录）与 history_detail_groups 构造对话框；verify_first_pages 中 inspect_metric_dialog 断言窗口标题含 _overview_record id）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_overview_metric_details；par_app/ui.py MainWindow.refresh_overview；par_app/database.py ParDatabase.latest_successful_spectrum

### UI-010 实时图内保留精简指标
- 规则：实时光谱图内继续保留原有的精简指标卡（具体组成见第56行条目）。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“图内保留原有精简指标，「全部指标」打开当前所显示记录的分组详情”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow.refresh_overview 调用 overview_chart.set_secondary_metrics_card(...) 在图内绘制指标卡；SpectrumCanvas._draw_core_metrics_card 绘制）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/ui.py SpectrumCanvas._draw_core_metrics_card

### UI-011 实时摘要1500像素阈值六列/三列
- 规则：可用内容宽度达到 1500 逻辑像素时实时摘要单行六列，否则两行三列。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“可用内容宽度达到1500逻辑像素时单行六列，否则两行三列”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._align_overview_metrics：kpi_width = 面板宽度减左右边距，columns = 6 if kpi_width >= 1500 else 3）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_overview_metrics

### UI-012 实时摘要六项指标及顺序
- 规则：实时摘要固定显示六项：照度、350–1050 nm 总辐照度、PPFD、McCree-YPFD、叶绿素 A 加权光子通量、叶绿素 B 加权光子通量。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“实时摘要为照度、350–1050 nm 总辐照度、PPFD、McCree-YPFD、叶绿素 A/B 加权光子通量六项”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._build_overview 按此顺序创建 6 张 KPI 卡（lux/irradiance/ppfd/ypfd/chlorophyll_a_ypfd/chlorophyll_b_ypfd）；verify_configuration.py verify_first_pages 断言 len(overview_kpi_cards)==6，审计 test-configuration.md 记该函数 PASS）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_overview；par_app/ui.py MainWindow.refresh_overview；par_app/services/metrics.py OVERVIEW_KPI_SOURCES

### UI-013 无有效光谱时禁用全部指标
- 规则：当前设备没有有效光谱记录时，“全部指标”按钮禁用。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“失败后仍与保留的最近有效光谱对应，无有效光谱时禁用”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._build_overview 初始 setEnabled(False)；refresh_overview 每次重绘先 setEnabled(False)，仅在 latest_successful_spectrum 有结果时 setEnabled(True)）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_overview；par_app/ui.py MainWindow.refresh_overview

### UI-014 CCT与峰值波长整数显示
- 规则：CCT、PAR 峰值波长、全谱峰值波长在界面上显示为整数。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“CCT、PAR峰值波长、全谱峰值波长显示整数”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._record_metric_values 对 cct/peak_wavelength_nm/extended_peak_wavelength_nm 用 _format_metric(...,0)；refresh_overview 图内指标同样 0 位小数；verify_first_pages 断言旧记录 cct=='6992'、峰值 '479'/'900'）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/metrics.py record_metric_values；par_app/services/metrics.py overview_metric_entries；par_app/services/metrics.py format_metric

### UI-015 不重复列出软件PPFD及扩展分波段
- 规则：详情不重复列出软件 PPFD，以及与常规波段重复的扩展紫外/蓝/绿/红波段。
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“软件PPFD及重复的扩展紫外/蓝/绿/红波段不重复列出”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history 的 groups 中无 software_ppfd、extended_pfd_uv/_b/_g/_r）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-016 硬件ee与400段计算值不新增界面展示
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history 的详情分组与实时指标均无 ee 及 400 段计算值；ee 仅在原有 69 项导出字段 EXPORT_MCU_FIELDS 中。“不新增通信读取”属采集协议约束，已另拆至 ACQ 领域。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow.refresh_overview

### UI-017 色度坐标4位小数
- 规则：色度坐标 u、v、x、y 显示 4 位小数。
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“扩展辐照度沿用现有PAR缩放口径；色度坐标显示4位小数”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._record_metric_values：key in ('u','v','x','y') 时 4 位小数，其余 3 位）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/metrics.py record_metric_values

### UI-018 详情与全部指标共54项
- 规则：历史详情与实时“全部指标”展示同一套 54 项非重复指标：常用光量含叶绿素 A/B，峰值组含全谱峰值功率，另列扩展波段光量、R1–R15 特殊显色指数、XYZ 及 u/v/x/y。
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“历史详情与实时「全部指标」共54项非重复指标：常用光量增加叶绿素A/B，峰值组增加全谱峰值功率”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._build_history 的 groups：8+6+6+7+5+15+7=54；_show_overview_metric_details 复用 history_detail_groups；verify_first_pages 断言 len(history_detail_values)==56（54 指标+耗时+校验））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._show_overview_metric_details；par_app/services/metrics.py record_metric_values

### UI-019 详情宽度不足单列回退
- 规则：历史详情宽度不足以容纳加宽后的双列时，沿用单列回退；不得通过挤压单位列或增加横向滚动来容纳。
- 来源：业务规则与变更日志_V1.0.2.md 第 40 行「实时概览与历史回放（2026-10-11）」“宽度不足沿用单列回退，不挤压单位或增加横向滚动”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._layout_history_details：minimum_column 计入 name_value_shift（3 个“字”宽），dual = available >= minimum_column*2+24，否则单列；单位列固定宽度 unit_width）
- 冲突：D-105 已裁决：以第40、42行（名称到数值加宽三字、三类字段等宽对齐）为准，第44行“紧凑相邻”已被取代
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details

### UI-020 历史表头单行采集时间
- 规则：历史记录表的时间列表头为单行“采集时间（北京时间）”。
- 来源：业务规则与变更日志_V1.0.2.md 第 42 行「实时概览与历史回放（2026-10-11）」“余宽均分在两列末端。历史表头为单行「采集时间（北京时间）」”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history 表头标签为 "采集时间（北京时间）"（无换行）；_size_history_header 按实际文字高度+16、最小 46 计算）
- 冲突：D-104 已裁决：以第42行单行表头为准，第49行“两行高度加16像素”标为历史废止
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._size_history_header

### UI-021 详情头部固定在滚动区外
- 规则：详情顶部的设备、记录 ID、完整时间、耗时及采集校验固定在滚动区上方，只有下方七组指标纵向滚动。
- 来源：业务规则与变更日志_V1.0.2.md 第 42 行「实时概览与历史回放（2026-10-11）」“详情顶部的设备、记录ID、完整时间、耗时及采集校验固定在滚动区上方，仅下方七组指标纵向滚动”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history：history_detail_header_widget 加在 history_details_panel 的 QVBoxLayout 中、位于 history_details_scroll 之上；七组指标在 history_details_content 内）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._layout_history_details

### UI-022 详情数值列宽在窗口内只增不减
- 规则：数值区按可容纳 99999.999 的宽度预留，更长读数才统一扩宽；扩宽后当前窗口后续保留该宽度，避免切换记录时单位来回移动。
- 来源：业务规则与变更日志_V1.0.2.md 第 42 行「实时概览与历史回放（2026-10-11）」“数值区按可容纳99999.999的紧凑宽度预留，更长读数才统一扩宽，当前窗口后续保留该宽度”
- 状态：待确认
- 现状符合度：符合（ui.py _layout_history_details：value_width = max(当前读数宽, “99999.999”宽, self._history_detail_value_width)，并回写 _history_detail_value_width）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details

### UI-023 按实际字体宽度自动退回单列
- 规则：按实际字体与可用宽度判断，空间不足时历史详情自动退回单列。
- 来源：业务规则与变更日志_V1.0.2.md 第 44 行「实时概览与历史回放（2026-10-11）」“按实际字体与可用宽度判断，空间不足自动退回单列”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._layout_history_details 用 fontMetrics 计算 minimum_column 决定是否双列）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details

### UI-024 详情共用一个纵向滚动区
- 规则：整个详情（双列或单列）共用一个纵向滚动区，不为每列单独滚动。
- 来源：业务规则与变更日志_V1.0.2.md 第 44 行「实时概览与历史回放（2026-10-11）」“名称可换行，数值和单位保留原字号，整个详情共用一个纵向滚动区”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history：七组指标都在同一个 history_details_scroll（QScrollArea）内的 detail_grid）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-025 详情双列分组归属
- 规则：历史详情双列时，左列为常用光量、波段光子通量、扩展波段光量、色度与三刺激值；右列为光谱比例、光色与峰值、特殊显色指数。
- 来源：业务规则与变更日志_V1.0.2.md 第 44 行「实时概览与历史回放（2026-10-11）」“左列为常用光量、波段光子通量、扩展波段光量、色度与三刺激值，右列为光谱比例、光色与峰值、特殊显色指数”
- 状态：待确认
- 现状符合度：符合（ui.py _layout_history_details：side = 1 if dual and group_index in (2,3,5)，即光谱比例、光色与峰值、特殊显色指数在右；其余（0,1,4,6）在左）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details；par_app/ui.py MainWindow._build_history

### UI-026 顶栏状态变短后重算宽度
- 规则：顶栏总线与采集状态的宽度随文字重新计算；状态变短后不保留长状态的占位宽度。
- 来源：业务规则与变更日志_V1.0.2.md 第 44 行「实时概览与历史回放（2026-10-11）」“状态变短后重新计算宽度，不保留长状态占位”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._update_device_bar_layout 每次按 sizeHint 重设 label 与 device_status_box 的 setFixedWidth；_on_bus_state 中调用该函数）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_device_bar_layout；par_app/ui.py MainWindow._on_bus_state

### UI-027 删除重复质量分组
- 规则：删除历史详情底部重复的采集质量分组。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“删除底部重复的采集质量分组，正文七组覆盖54项指标”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._build_history 的 groups 只有七个指标分组，无采集质量分组）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-028 历史列表五列内容
- 规则：历史记录列表为五列：序号、ID、采集时间、采集结果、曝光状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“历史记录区为左侧约40%的五列列表（序号、ID、采集时间、采集结果、曝光状态）”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._build_history：QTableWidget(0,5) 表头为序号/ID/采集时间（北京时间）/采集结果/曝光状态）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow.refresh_history

### UI-029 历史详情只用所选记录数值
- 规则：历史详情的全部数值只来自所选历史记录，不用实时值补齐。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“全部数值仅来自所选历史记录，不用实时值补齐”
- 状态：待确认
- 现状符合度：符合（ui.py _show_history_details 只调用 _record_metric_values(record)，record 来自 self._history_records（查询结果））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details；par_app/services/metrics.py record_metric_values

### UI-030 失败记录清空指标保留耗时校验
- 规则：选中失败记录时清空全部指标，但保留采集耗时和采集校验的显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“失败记录清空指标但保留耗时和采集校验；空查询及切换无数据设备时清空详情”
- 状态：待确认
- 现状符合度：符合（ui.py _show_history_details：先全部置“—”，写 elapsed 与 review（失败为“未完成采集”），success 为假时直接返回；verify_first_pages 断言 elapsed=='5464.7'、review=='未完成采集'）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details

### UI-031 旧记录缺复核审计显示未记录
- 规则：旧记录缺少复核审计时，采集校验显示“未记录”，不凭可计入 DLI 推断复核已完成。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“旧记录缺少复核审计时显示「未记录」，不凭可计入DLI推断复核已完成”
- 状态：待确认
- 现状符合度：符合（按 D-145 裁决：MainWindow._show_history_details 不以 dli_eligible==1 推断“已完成”；缺审计标记时显示“未记录”，dli_eligible==0 的旧记录按裁决显示“复核未完成”。verify_first_pages 断言 review=='未记录' 的样例为 dli_eligible=1，dli_eligible=0 的样例未覆盖。）
- 冲突：D-145 已裁决：缺复核审计标记但 dli_eligible=0 的旧记录显示“复核未完成”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details

### UI-032 空查询或无数据设备清空详情
- 规则：查询结果为空或切换到无数据设备时，清空详情。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“空查询及切换无数据设备时清空详情。缺失值及零分母比例显示「—」”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_history：selected_row<0 时 _show_history_details(None)，标题回到“记录详情 · 未选择记录”；_bind_active_device 清缓存后 refresh_all→refresh_history）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/ui.py MainWindow._show_history_details；par_app/ui.py MainWindow._bind_active_device

### UI-033 缺失值与零分母显示短横
- 规则：缺失值及分母为零的比例在详情中显示“—”，不伪造数值。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“缺失值及零分母比例显示「—」，旧记录缺少复核审计时显示「未记录」”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._ratio 分母为 None/0 返回 None；_format_metric 对 None/非有限值返回“—”。（实时图内指标卡与概览表另有 NaN/Inf 显示为 nan/inf 的已知问题，见 D-179（robustness-ui.md Bug 6；已裁决 2026-10-18：显示为“—”，阶段二随新界面实现），不在本条范围））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/metrics.py ratio；par_app/services/metrics.py format_metric；par_app/services/metrics.py record_metric_values

### UI-034 详情不缩字号隐藏内容
- 规则：详情空间不足时保留纵向滚动，不通过缩小字号隐藏内容。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“详情减少重复占位，空间不足仍保留纵向滚动，不通过缩字号隐藏内容”
- 状态：待确认
- 现状符合度：符合（详情字号统一取 history_table.font()，无随宽度缩放逻辑；指标区在 QScrollArea 内）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._layout_history_details

### UI-035 详情标题按字段换行不截断
- 规则：详情标题区空间不足时按字段换行，不截断文字。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“辅助信息保留正文字体；空间不足时按字段换行，不截断文字”
- 状态：待确认
- 现状符合度：符合（ui.py _layout_history_details 按 natural_width 累加，超出 available 时另起一行；QLabel 设 wordWrap(True) 且宽度不超过 available）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details

### UI-036 详情标题行字段
- 规则：详情标题为“记录详情 · 设备名称 · #ID”，其后依次显示完整北京时间（含毫秒）、采集耗时和采集校验。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“「记录详情 · 设备名称 · #ID」保持原字号字重，其后依次显示完整北京时间（含毫秒）、采集耗时和采集校验”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._show_history_details 设置 “记录详情 · {设备名} · #{id}” 与 format_beijing_time（%f 截到毫秒）+“（北京时间）”；elapsed/review 在 history_detail_quality）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_history_details；par_app/database.py format_beijing_time

### UI-037 选中记录时详情与光谱同步
- 规则：选中历史记录时，详情与历史光谱同步切换到该记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“不用实时值补齐。选中记录时详情与光谱同步”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow.show_history_spectrum（itemSelectionChanged 槽）先 _show_history_details(record) 再按同一 id 取光谱绘制）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_history_spectrum

### UI-038 历史状态行无悬停提示
- 规则：历史采集状态行不显示悬停提示，文字被省略时也不弹浮框；完整信息在右侧详情查看。
- 来源：业务规则与变更日志_V1.0.2.md 第 47 行「实时概览与历史回放（2026-10-11）」“历史采集状态行取消悬停提示，包括文字省略时也不弹浮框；完整信息可在右侧详情查看”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history 设 history_chart.status_label.tooltip_enabled=False；SingleLineStatusLabel.setText 据此置空 tooltip；verify_first_pages 断言 not history_chart.status_label.toolTip()）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py SingleLineStatusLabel.setText

### UI-039 实时状态保留悬停提示
- 规则：实时页的状态行保留悬停提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 47 行「实时概览与历史回放（2026-10-11）」“完整信息可在右侧详情查看。实时状态提示保留”
- 状态：待确认
- 现状符合度：符合（overview_chart.status_label 为 SingleLineStatusLabel，tooltip_enabled 默认 True；verify_first_pages 断言 overview_chart.status_label.toolTip() 非空）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SingleLineStatusLabel.setText；par_app/ui.py MainWindow._spectrum_view_controls

### UI-040 切换菜单不改变当前设备
- 规则：切换菜单页面不改变当前显示设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“临时窗口鼠标测试覆盖分隔带点击不改变设备/页面、菜单切换不改变当前设备”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._on_tab_changed 不调用 hub.set_active；verify_first_pages 逐页切换后断言 hub.active_key == active_key）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._on_tab_changed

### UI-041 切换设备不弹确认框
- 规则：设备选择使用单选按钮，点击即切换，不增加确认弹窗。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“设备选择使用Qt标准单选圆点，不增加确认弹窗”
- 状态：待确认
- 现状符合度：符合（ui.py _rebuild_device_bar 创建 QRadioButton，clicked→_select_device→hub.set_active，无对话框）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_device_bar；par_app/ui.py MainWindow._select_device

### UI-042 设备组与状态组放不下时上下排列
- 规则：设备选择组与状态组在一行放不下时改为上下排列。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“两组放不下时上下排列。菜单用选中背景与蓝色下划线区分”
- 状态：待确认
- 现状符合度：符合（ui.py _update_device_bar_layout：stacked = show_selector and width < max(1180, required_width)，stacked 时状态组移到第 1 行）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_device_bar_layout

### UI-043 长状态限宽换行
- 规则：顶栏的长总线/采集状态限制宽度并换行显示，不截断。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“长设备名省略并保留悬停全文，长状态限宽换行，两组放不下时上下排列”
- 状态：待确认
- 现状符合度：符合（ui.py _update_device_bar_layout：总线 300、采集状态 320 上限，超出时 setWordWrap(True)）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_device_bar_layout

### UI-044 长设备名省略保留悬停全文
- 规则：顶栏设备选项中过长的设备名省略显示，悬停时可查看全文。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“长设备名省略并保留悬停全文，长状态限宽换行”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow._style_device_buttons：宽度上限 180，elidedText(ElideRight) 显示，setToolTip 含完整名称（另附从站地址与状态））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons

### UI-045 顶栏与菜单间分隔带不可交互
- 规则：设备栏与菜单栏之间保留非交互分隔带；点击分隔带不改变当前设备或当前页面。
- 来源：业务规则与变更日志_V1.0.2.md 第 48 行「实时概览与历史回放（2026-10-11）」“两栏之间保留8逻辑像素的非交互分隔带及细线”
- 状态：待确认
- 现状符合度：符合（ui.py MainWindow.__init__ 创建 navigation_separator（QFrame，高 8，NoFocus，无点击处理）；verify_first_pages 鼠标测试断言点击后 hub.active_key 与 tabs.currentIndex 不变）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.__init__

### UI-046 不做总数统计分页或模式切换
- 规则：历史列表不增加总数统计、分页或模式切换。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“并提示超出时缩小范围，不增加总数统计、分页或模式切换”
- 状态：待确认
- 现状符合度：符合（历史页无计数查询、分页控件或模式切换控件（_build_history 仅有起止时间、查询按钮与说明文字））
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-047 刷新与切换设备沿用已应用范围
- 规则：定时刷新、新记录到达和设备切换都使用最近一次已应用的时间范围，不采用尚未提交的编辑值。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“定时刷新、新记录到达及设备切换均使用最近一次已应用范围，不采用尚未提交的时间”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_history 只读 self._history_applied_range；refresh_all（定时器与 acquisition_saved）和 _bind_active_device 都不改该范围；verify_first_pages 断言 _history_applied_range == applied_range）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/ui.py MainWindow.refresh_all；par_app/ui.py MainWindow._bind_active_device

### UI-048 历史最多显示500条并提示
- 规则：历史列表最多显示所选范围内最近 500 条记录，并提示超出时缩小时间范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“最多显示范围内最近500条，并提示超出时缩小范围”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_history 调用 database.recent_acquisitions(500, start, end)（ORDER BY id DESC LIMIT 500）；history_limit_label 文案含 500。另：开始晚于结束时改显示“开始时间不能晚于结束时间”，原文未提及）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/database.py ParDatabase.recent_acquisitions

### UI-049 历史页首次打开用默认时间范围
- 规则：历史页在应用首次打开时使用默认时间范围并据此查询。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“历史页首次打开应用默认时间范围，此后编辑起止时间不立即查询”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history：开始=最近 500 条中最早记录当日 00:00（无记录时为当前时刻当日 00:00），结束=构建时北京时间；随即写入 _history_applied_range。原文未规定默认范围的具体取值）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-050 结束时间不自动推进
- 规则：历史查询的结束时间不自动推进，也不因库中存在未来时间的记录而扩大范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“结束时间不自动推进，也不按未来时间记录扩大范围”
- 状态：待确认
- 现状符合度：符合（代码中无对 history_end 的自动 setDateTime；verify_first_pages 断言 history_end 不变、future_id 不在列表中）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/ui.py MainWindow._build_history

### UI-051 编辑起止时间须点查询才生效
- 规则：编辑起止时间不立即查询；只有点击“查询记录”才应用新范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 50 行「实时概览与历史回放（2026-10-11）」“此后编辑起止时间不立即查询，点击「查询记录」才应用新范围”
- 状态：待确认
- 现状符合度：符合（history_start/history_end 未连接 dateTimeChanged；仅 history_query_button.clicked→_query_history 更新 _history_applied_range）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._query_history；par_app/ui.py MainWindow._build_history

### UI-052 单采曝光不决定警告色
- 规则：新单采记录的曝光状态不决定状态显示的警告色。
- 来源：业务规则与变更日志_V1.0.2.md 第 52 行「实时概览与历史回放（2026-10-11）」“新单采记录的曝光不决定采集成败、警告色或DLI资格”
- 状态：待确认
- 现状符合度：不符合（按 D-154 裁决需修改，待修复。按裁决，历史列表“曝光”列中新单采记录的欠曝光、过曝光须与“正常”同色，旧记录保留橙色；现状 refresh_history 对新单采记录的非正常值也着橙色 #d97706。原核对（未验证）：实时与历史状态行符合：_update_overview_status 与 show_history_spectrum 在 single_capture 时不因曝光改色，verify_first_pages 断言 _status_color=='#16a34a'。但 refresh_history 对列表“曝光状态”列非正常值仍着 #d97706 橙色，是否属于本条所说“警告色”需确认）
- 冲突：D-154 已裁决：第20、52行适用于历史列表“曝光”列：新单采记录的欠曝光、过曝光与“正常”同色，旧记录保留橙色，待修复（DEF-21）（同 ACQ-057）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.show_history_spectrum；par_app/ui.py MainWindow.refresh_history

### UI-053 实时保留最近成功且有光谱记录
- 规则：实时摘要与光谱显示当前设备最近一条成功且有光谱的记录；后续失败不清空该显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 53 行「实时概览与历史回放（2026-10-11）」“实时摘要与光谱保留当前设备最近一条成功且有光谱的记录”
- 状态：待确认
- 现状符合度：符合（database.py latest_successful_spectrum：JOIN spectra 且 success=1 取最新；refresh_overview 用该结果绘制摘要与光谱）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.latest_successful_spectrum；par_app/ui.py MainWindow.refresh_overview

### UI-054 无成功光谱时空图并更新失败时间
- 规则：当前设备没有成功光谱时，实时光谱保持空图，状态更新为最近失败时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 53 行「实时概览与历史回放（2026-10-11）」“同时保留所显示记录的时间、距今时间与曝光状态。没有成功光谱时保持空图并更新失败时间”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_overview：无 item 但有 rows 时每次刷新设置“最近采集失败　{时间}”，并绘制空图）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview

### UI-055 本轮失败提示并保留记录信息
- 规则：新一轮采集失败时，状态显示“本轮失败 · 保留最近有效数据”，同时保留所显示记录的时间、距今时间和曝光状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 53 行「实时概览与历史回放（2026-10-11）」“新一轮失败时显示「本轮失败 · 保留最近有效数据」，同时保留所显示记录的时间、距今时间与曝光状态”
- 状态：待确认
- 现状符合度：符合（ui.py _update_overview_status：最新记录 success 为假时 status=“本轮失败 · 保留最近有效数据”，状态卡含显示记录 #id、时间、距今、曝光、耗时；verify_first_pages 断言“本轮失败”且 KPI 不变）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.refresh_overview

### UI-056 实时状态单行省略悬停全文
- 规则：实时光谱标题右侧状态保持单行；宽度不足时尾部省略，悬停可查看全文。
- 来源：业务规则与变更日志_V1.0.2.md 第 54 行「实时概览与历史回放（2026-10-11）」“状态位于标题右侧，间隔十个中文字符宽度并保持单行；宽度不足时尾部省略，悬停可查看全文”
- 状态：待确认
- 现状符合度：符合（SingleLineStatusLabel.setText 用 elidedText(ElideRight) 并设完整 tooltip；_spectrum_view_controls inline_header 时 wordWrap(False)；verify_first_pages 断言 not status_label.wordWrap()）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SingleLineStatusLabel.setText；par_app/ui.py MainWindow._spectrum_view_controls

### UI-057 实时页固定350–1050且无波段选择
- 规则：实时页光谱固定显示 350–1050 nm，不显示波段选择控件。
- 来源：业务规则与变更日志_V1.0.2.md 第 54 行「实时概览与历史回放（2026-10-11）」“实时页固定350–1050 nm，不显示波段选择”
- 状态：待确认
- 现状符合度：符合（ui.py _build_overview：_spectrum_view_controls(inline_header=True) 隐藏 range_combo，默认项为 (350,1050)，overview_view_controls.hide()；verify_first_pages 断言 range_combo.isHidden()）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_overview；par_app/ui.py MainWindow._spectrum_view_controls

### UI-058 不增加图内指标
- 规则：实时图内不增加指标。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“不增加图内指标，不调整坐标框设置或四条参考曲线”
- 状态：待确认
- 现状符合度：未验证（现状图内指标由 SpectrumCanvas._draw_core_metrics_card 绘制。本条是相对前一版本“不增加”的约束，缺少前一版本基线无法比对）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/ui.py SpectrumCanvas._draw_core_metrics_card

### UI-059 图内指标省去无量纲保留单位
- 规则：图内指标省去比例及指数后的重复“无量纲”字样，保留百分比、光子通量、波长及功率单位。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“省去比例及指数后的重复「无量纲」，保留百分比、光子通量、波长及功率单位”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_overview：label.replace("（无量纲）", "")，其余单位后缀保留）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/services/metrics.py overview_secondary_metrics

### UI-060 实时图内20项指标分列
- 规则：实时图内详细指标共 20 项，按类别纵向阅读：左列 8 项波段光量，右列 12 项比例、光色和峰值；两列各自左对齐。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“实时图内20项详细指标按类别纵向阅读：左列8项波段光量，右列12项比例、光色和峰值”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_overview：entries 24 项去掉 4 项摘要（fixed_labels）后 20 项，set_secondary_metrics_card(column_break=8)；verify_first_pages 断言 20 项、column_break==8。另：NaN/Inf 在此卡显示为 nan/inf，见 D-179（robustness-ui.md Bug 6；已裁决 2026-10-18：显示为“—”，阶段二随新界面实现），不属本条）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/services/metrics.py overview_secondary_metrics；par_app/services/metrics.py OVERVIEW_FIXED_LABELS；par_app/ui.py SpectrumCanvas.set_secondary_metrics_card；par_app/ui.py SpectrumCanvas._draw_core_metrics_card

### UI-061 显示指标默认勾选不持久化
- 规则：“显示指标”默认勾选；关闭只影响当前运行，重新启动后恢复显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“「显示指标」默认勾选，关闭仅影响当前运行，重新启动恢复显示”
- 状态：待确认
- 现状符合度：符合（ui.py _build_overview：overview_metrics_toggle.setChecked(True)，toggled→_toggle_spectrum_metrics 只改 overview_chart.metrics_visible，无持久化；verify_first_pages 断言重启后 isChecked()）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_overview；par_app/ui.py MainWindow._toggle_spectrum_metrics

### UI-062 历史图内不显示四项读数
- 规则：历史光谱图内不显示重复的四项读数卡。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“不显示图内重复的四项读数，不添加比较操作”
- 状态：待确认
- 现状符合度：符合（ui.py show_history_spectrum 调用 set_core_metrics_card([])，历史图从不设置 secondary 指标；verify_first_pages 断言 not history_chart._core_metrics）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_history_spectrum

### UI-063 历史状态行内容与省略
- 规则：“历史光谱”标题在图外左侧，其后显示所选记录的采集状态、设备、ID、时间、曝光和耗时；单行放不下时省略尾部，不弹悬停提示，完整信息看详情区。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“间隔十个中文字符后显示所选历史记录的采集状态、设备、ID、时间、曝光和耗时；单行宽度不足时省略尾部”
- 状态：待确认
- 现状符合度：符合（ui.py show_history_spectrum set_status_card 文本含状态、设备名·#id、时间、曝光、耗时；status_label 为 SingleLineStatusLabel 且 tooltip_enabled=False；external_title=True）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_history_spectrum；par_app/ui.py MainWindow._build_history；par_app/ui.py SingleLineStatusLabel.setText

### UI-064 历史页不添加比较操作
- 规则：历史页不添加记录比较操作。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“不显示图内重复的四项读数，不添加比较操作”
- 状态：待确认
- 现状符合度：符合（_build_history 无比较相关控件；单选模式 SingleSelection）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-065 历史页固定350–1050无波段选择
- 规则：历史页删除波段选择，光谱固定显示 350–1050 nm。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“历史页使用五列列表及详情，删除波段选择，固定显示350–1050 nm”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history：_spectrum_view_controls(inline_header=True) 隐藏 range_combo，history_view_controls.hide()；verify_first_pages 断言 history_chart.range_combo.isHidden()）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._spectrum_view_controls

### UI-066 重启或切换设备默认不锁定
- 规则：重启软件或切换设备后，“锁定纵轴”默认不勾选。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“重启或切换设备后默认不锁定，不增加超量程提示”
- 状态：待确认
- 现状符合度：符合（ui.py _build_history 创建时未勾选；_bind_active_device 执行 history_axis_lock.setChecked(False)）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow._build_history

### UI-067 锁定纵轴不加超量程提示
- 规则：锁定纵轴后即使光谱超出范围也不增加超量程提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“重启或切换设备后默认不锁定，不增加超量程提示”
- 状态：待确认
- 现状符合度：符合（_plot_selected_spectrum 锁定时仅 set_ylim，无超量程判断或提示）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum

### UI-068 锁定纵轴行为
- 规则：勾选“锁定纵轴”时固定当前纵轴范围，选择其他记录时范围不变；取消勾选恢复自动缩放。
- 来源：业务规则与变更日志_V1.0.2.md 第 57 行「实时概览与历史回放（2026-10-11）」“「锁定纵轴」放在同一行最右侧，勾选时固定当前范围，选其他记录不变；取消恢复自动缩放”
- 状态：待确认
- 现状符合度：符合（ui.py _toggle_history_axis_lock 记录/清除 locked_ylim；_plot_selected_spectrum 非实时且 locked_ylim 存在时 set_ylim；verify_first_pages 断言锁定后 ylim 不变、解锁后上限变化）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._toggle_history_axis_lock；par_app/ui.py MainWindow._plot_selected_spectrum

### UI-069 按需更新触发条件
- 规则：查询、切换设备、选择记录与显示开关触发按需更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 59 行「实时概览与历史回放（2026-10-11）」“查询、切换设备、选择记录与显示开关按需更新”
- 状态：待确认
- 现状符合度：符合（_query_history→refresh_history；_bind_active_device 清缓存键后 refresh_all；itemSelectionChanged→show_history_spectrum；overview_metrics_toggle→_toggle_spectrum_metrics；history_axis_lock→_toggle_history_axis_lock）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._query_history；par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow.show_history_spectrum；par_app/ui.py MainWindow._toggle_spectrum_metrics

### UI-070 新记录到达保留当前选中
- 规则：新记录到达时尽量保留当前选中记录；若其已不在查询结果内，则改选现有记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 59 行「实时概览与历史回放（2026-10-11）」“新记录到达时尽量保留当前选中记录，若其已不在查询结果内则选择现有记录”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_history 以 _history_displayed_id 找回原行；找不到时选第一条成功记录，否则第 0 行；verify_first_pages 断言 _history_displayed_id 保持）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history

### UI-071 无新记录不重建表格与重画光谱
- 规则：没有新记录时，不重建历史表格、不重新读取和重画 701 点光谱；状态及距今时间仍做轻量更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 59 行「实时概览与历史回放（2026-10-11）」“无新记录时不重建历史表格、不读取和重画701点光谱；状态及距今时间仍轻量更新”
- 状态：待确认
- 现状符合度：符合（ui.py refresh_all 仅在最新记录 id 变化时 refresh_history；refresh_overview 以 _overview_plot_key 判定是否重画，但每次调用 _update_overview_status；verify_first_pages 用 mock 断言无新数据时 plot 未调用）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_all；par_app/ui.py MainWindow.refresh_overview；par_app/ui.py MainWindow.refresh_history

### UI-072 前两页回归覆盖范围
- 规则：verify_configuration.py 以临时库对前两页做回归，覆盖时间边界、500 条限制、曝光异常、失败保留、恢复采集、无数据、无新数据不重画、指标开关、纵轴锁定、切换设备及重启默认值；该验证不连接真实硬件、不写正式数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 60 行「实时概览与历史回放（2026-10-11）」“新增临时库前两页回归，覆盖时间边界、500条限制、曝光异常、失败保留、恢复采集、无数据、无新数据不重画、指标开关、纵轴锁定、切换设备及重启默认值”
- 状态：待确认
- 现状符合度：符合（仓库根 verify_configuration.py verify_first_pages 存在上述断言；审计 test-configuration.md：verify_first_pages 在 soft_runner 下全部 PASS（失败只在其他函数的像素断言）。1230×740/1680×900 截图检查未单独核对）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：测试流程条目，对应仓库根 verify_configuration.py 的 verify_first_pages，非 par_app 产品代码

### UI-073 唯一保存按钮统一保存通信与登记
- 规则：设置页只有一个“保存并应用全部配置”按钮，位于设备登记表下方；点击时同时保存通信参数和设备登记，不拆分为两个保存功能。
- 来源：业务规则与变更日志_V1.0.2.md 第 69 行「设置与导出布局（2026-09-20）」“唯一的「保存并应用全部配置」按钮位于设备登记表下方，仍统一保存通信参数和设备登记，不拆分功能”
- 状态：待确认
- 现状符合度：符合（bus_apply_button 加入 device_layout；device_apply_button 与 bus_apply_button 为同一对象；save_local_settings 用 app_config_from_form（bus+devices）一次调用 hub.apply。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow.save_local_settings；par_app/ui.py MainWindow.app_config_from_form；par_app/device_hub.py DeviceHub.apply

### UI-074 设备维护不设标题区仅留入口按钮
- 规则：“设备维护”不再单独设标题区，只保留一个文字为“设备维护”的白底普通入口按钮；布局调整不改变其原有点击行为（打开维护弹窗）。
- 来源：业务规则与变更日志_V1.0.2.md 第 69 行「设置与导出布局（2026-09-20）」“「设备维护」不再单设标题区；入口按钮文字为「设备维护」，保留白底普通按钮”
- 状态：待确认
- 现状符合度：符合（_build_settings 中 maintenance_button=QPushButton("设备维护") 放入 settings_maintenance_row，无对应 QGroupBox；clicked 连接 open_device_maintenance(0)。底边对齐等像素要求未核对（纯视觉）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._layout_settings_content；par_app/ui.py MainWindow.open_device_maintenance

### UI-075 设置页五区标题与左右分布
- 规则：设置与导出页以同级标题和细分隔线分为五区：左栏依次为“通信设置”“设备登记”“关于与技术支持”，右栏为“采集记录导出”“设备状态与最近日志”；“设备登记”独立于通信设置成区。
- 来源：业务规则与变更日志_V1.0.2.md 第 69 行「设置与导出布局（2026-09-20）」“左侧依次为「通信设置」「设备登记」「关于与技术支持」，右侧为「采集记录导出」「设备状态与最近日志」”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_settings 依次创建 QGroupBox 通信设置/设备登记/关于与技术支持（左栏）与 采集记录导出/设备状态与最近日志（右栏）；verify_configuration.verify_settings_layout 覆盖几何。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-076 仅隐藏自动读通信参数成功消息
- 规则：日志表仅隐藏自动读取通信参数的重复成功消息；底层日志不删除；通信恢复后失败记录和恢复记录都仍保留在列表中。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“仅隐藏自动读取通信参数的重复成功消息，不删除底层日志，通信恢复后仍保留失败和恢复记录”
- 状态：待确认
- 现状符合度：符合（过滤条件仅为 level==INFO 且 category==connection 且 message==“已读取设备当前通信参数”，仅作用于展示；_mark_ok 写 communication_recovery、_mark_failed 写 communication；verify_settings_logs 断言 events 未被修改且“通信恢复”“通信异常”行在列。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console；par_app/coordinator.py PollingCoordinator._mark_ok；par_app/coordinator.py PollingCoordinator._mark_failed

### UI-077 数据库行格式与 MB 换算
- 规则：数据库行文案为“数据库：文件名 · 文件大小：xx.xx MB”，大小按 1 MB = 1,000,000 字节换算，保留两位小数。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“数据库行使用「数据库：文件名 · 文件大小：xx.xx MB」，按1 MB = 1,000,000字节换算并保留两位小数”
- 状态：待确认
- 现状符合度：符合（refresh_database_summary: f"{st_size / 1_000_000:.2f} MB"；文件不存在时显示“尚未创建”（原文未规定该情形）；verify_settings_logs 断言完整文案。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_database_summary

### UI-078 日志列表取最近300条中最多50条
- 规则：日志表按最新在前排序，从最近 300 条日志中筛选后最多展示 50 条。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“按最新在前，从最近300条中筛选最多50条展示”
- 状态：待确认
- 现状符合度：符合（refresh_settings_console 调用 database.recent_diagnostics(300)（ORDER BY id DESC）后过滤并切片 [:50]。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console；par_app/database.py ParDatabase.recent_diagnostics

### UI-079 日志类别中文显示
- 规则：设置页日志表的类别以中文显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“日志类别中文显示，异常行标红，完整消息及详情放在悬停提示中”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_settings_console 用 category_names 映射中文，未知类别显示“其他”；verify_configuration.py verify_settings_logs 断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console

### UI-080 状态区三行内容
- 规则：设备状态区以三行展示：当前设备状态；最近采集时间与记录总数；数据库文件名与文件大小。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“状态区以三行展示当前设备状态、最近采集与记录总数、数据库文件与大小”
- 状态：待确认
- 现状符合度：符合（connection_status_label / serial_verified_label（最近采集：… · 共 N 条）/ database_summary_label；refresh_settings_console 与 refresh_database_summary 填充；verify_configuration.verify_settings_logs 断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console；par_app/ui.py MainWindow.refresh_database_summary

### UI-081 状态行悬停显示序列号
- 规则：悬停设置页设备状态行可查看设备序列号。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“悬停状态可查看序列号，数据库行不显示悬停提示”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_settings_console 设置 connection_status_label.setToolTip 含“设备序列号”；verify_configuration.py verify_settings_logs 断言 0x20260501 在提示中。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console

### UI-082 当前值正常普通色，不一致或异常标红
- 规则：回读当前值与配置值一致时用普通文字颜色；与配置值不一致或读取异常时标红。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“迟到回包按设备及连接配置核对。正常值用普通文字，不一致或异常标红”
- 状态：待确认
- 现状符合度：符合（_render_comm_values 对 mismatch 的值标签和 error 状态的标题使用 #b91c1c，否则 #334155；verify_automatic_comm 断言颜色。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._render_comm_values

### UI-083 未连接时不排队读取通信参数
- 规则：总线未连接时，设置页不向后台队列投递通信参数读取任务。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“未连接时不排队读取，连接恢复且设置页可见时补读一次”
- 状态：待确认
- 现状符合度：符合（_request_settings_comm 在 coordinator._client is None 时只渲染“总线未连接”，不调用 queue_task；verify_automatic_comm 断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._request_settings_comm

### UI-084 设置页不设手动读取通信参数按钮
- 规则：设置页外层取消手动读取通信参数的按钮，回读只由自动流程触发。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“正常值用普通文字，不一致或异常标红；取消外层手动读取按钮”
- 状态：待确认
- 现状符合度：符合（_build_settings 通信设置区只有“刷新串口”按钮（枚举端口，不读设备），无通信参数读取按钮。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-085 读取失败清除旧回读值
- 规则：通信参数读取失败时清除旧值。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“失败清除旧值，迟到回包按设备及连接配置核对”
- 状态：待确认
- 现状符合度：符合（MainWindow._accept_settings_comm 先置 _comm_readback=None，失败时显示“读取失败”。另：MainWindow._on_bus_state 在总线由连接变为断开时也清空回读值并显示“总线未连接”，原文未规定，仅为代码现状。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._accept_settings_comm

### UI-086 读取状态集中在当前值标题，无值显示—
- 规则：通信参数回读的读取状态只显示在“当前值”标题中；无有效回读值时各项显示“—”。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“读取状态集中在当前值标题，无有效值时各项显示「—」”
- 状态：待确认
- 现状符合度：符合（_render_comm_values 将状态写入 comm_source_label（“当前值 · 设备 · 状态”），_comm_readback 为 None 时各值显示“—”；verify_configuration.verify_automatic_comm 断言。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._render_comm_values

### UI-087 连接恢复且设置页可见时补读一次
- 规则：连接恢复且设置页可见时补读一次通信参数。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“未连接时不排队读取，连接恢复且设置页可见时补读一次；失败清除旧值”
- 状态：待确认
- 现状符合度：符合（MainWindow._on_bus_state 在连接由假变真且当前页为设置页时调用 _request_settings_comm。另有原文未规定的代码现状：MainWindow._on_device_state_changed 在当前设备转为在线且尚无回读值时也补读；_request_settings_comm 以 _comm_pending 防止同一设备重复投递。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._on_bus_state；par_app/ui.py MainWindow._request_settings_comm

### UI-088 迟到回包按设备及连接配置核对
- 规则：通信参数迟到回包须按设备及连接配置核对。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“失败清除旧值，迟到回包按设备及连接配置核对”
- 状态：待确认
- 现状符合度：符合（MainWindow._device_task_finished 的 comm_read 分支比较 _comm_pending 记录的签名与 MainWindow._comm_source_signature()（设备键、库路径、从站地址、传输方式、串口、主机、端口、波特率、校验），一致才采纳。另：不一致时丢弃并在设置页可见时重新读取，原文未规定，仅为代码现状。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_task_finished；par_app/ui.py MainWindow._comm_source_signature

### UI-089 通信参数读取异常原因悬停查看
- 规则：通信参数读取失败时，异常原因可在悬停提示中查看。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“无有效值时各项显示「—」；异常原因可悬停查看”
- 状态：待确认
- 现状符合度：符合（_accept_settings_comm 失败分支把异常文本设为 comm_source_label 与各值标签的 toolTip；未连接时 toolTip 为总线消息；verify_automatic_comm 断言 toolTip=='timeout'。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._accept_settings_comm；par_app/ui.py MainWindow._request_settings_comm

### UI-090 配置值/当前值同行展示地址波特率校验位
- 规则：串口通信参数按“配置值 / 当前值”同行对照展示地址、波特率、校验位三项，并标明当前值来源设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 71 行「设置与导出布局（2026-09-20）」“串口通信参数按「配置值 / 当前值」同行展示地址、波特率、校验位，并标明当前值来源设备”
- 状态：待确认
- 现状符合度：符合（按 D-106 裁决，第71行中的“地址”历史废止，回读不显示从站地址：_build_settings 的对照网格只有“波特率”“奇偶校验”两行，comm_current_values 只有 2 个标签（verify_multidevice 断言 len==2），_render_comm_values 不显示回读地址；来源设备在 comm_source_label 中标明。）
- 冲突：D-106 已裁决：设置页不显示回读的从站地址，第71行中的“地址”标为历史废止
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._render_comm_values

### UI-091 维护目标设备在弹窗内选择
- 规则：维护目标设备由弹窗内的设备选择框选择；设置页外层不重复显示维护目标。
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“光谱校准、通信参数三个功能页，由弹窗选择设备；外层不重复显示维护目标”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog 顶栏有“维护设备”下拉框（change_device）；_build_settings 外层无维护目标显示控件。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device

### UI-092 设备维护按钮打开含三功能页的弹窗
- 规则：设置页“设备维护”按钮统一打开维护弹窗；弹窗内包含状态与诊断、光谱校准、通信参数三个功能页。
- 来源：业务规则与变更日志_V1.0.2.md 第 72 行「设置与导出布局（2026-09-20）」“「设备维护」按钮统一打开维护弹窗，弹窗内保留状态与诊断、光谱校准、通信参数三个功能页”
- 状态：待确认
- 现状符合度：符合（open_device_maintenance 创建/复用 DeviceMaintenanceDialog；其 tabs 依次为“设备状态与诊断”“光谱校准”“通信参数维护”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.open_device_maintenance；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog._build_diagnostics

### UI-093 关于区显示 LOGO、版本、发布日期、联系信息
- 规则：“关于与技术支持”位于左栏下方，显示 LOGO、版本 V1.0.2、下一行发布日期 2026年9月20日，以及公司和联系信息。
- 来源：业务规则与变更日志_V1.0.2.md 第 73 行「设置与导出布局（2026-09-20）」“「关于与技术支持」位于左下，恢复LOGO，显示V1.0.2及下一行发布日期2026年9月20日，并保留公司和联系信息”
- 状态：待确认
- 现状符合度：符合（V1.0.3 测试版的发布日期与本条字面不同，见冲突字段 D-181；_build_settings 关于区 settings_logo 加载 BRAND_LOGO_PATH；表单行顺序 软件名称、软件版本、发布日期、公司主体、技术支持、电子邮箱、官方网站、办公地址。V1.0.2 显示 SOFTWARE_VERSION="V1.0.2"、SOFTWARE_RELEASE_DATE="2026年9月20日"（均在 ui.py）；V1.0.3 测试版起两者移到 par_app/app_info.py，关于区显示 SOFTWARE_VERSION_LABEL="V1.0.3（测试版）"、SOFTWARE_RELEASE_DATE="2026年10月18日"（测试版 2 构建日期，D-181；发布准备，见 内部文档）。）
- 冲突：D-181 按阶段一预授权采用推荐 2026-10-18（待负责人确认，发出 test.2 前须确认）：测试版关于区显示该测试版的构建日期（V1.0.3 测试版 2 为 2026年10月18日），V1.0.2 正式发布日期保留在手册历史中；已在 par_app/app_info.py 实现。负责人确认前本条「规则」保留原文，确认后再改写规则
- 验证：tests/qt/test_configuration_settings_layout.py::test_about_section_shows_the_test_build_date_under_the_version
- 2.0 实现：网页“设置与导出”页底部“关于与技术支持”（`web/src/components/AboutPanel.vue`）显示 LOGO（仓库 `logo.png`）、软件名称、软件版本（“V2.0 试用版 · 构建 N”，页面不显示内部版本号 2.0.0-alpha.N，#118、#119）、技术支持、电子邮箱与版权行（公开版不含公司主体、官方网站、办公地址，LOGO 为通用图）（`web/src/lib/brand.ts`，`tests/unit/test_web_brand.py` 对照 `par_app/ui.py`）；不显示发布日期（2.0 未定发布日期）。顶栏左侧另显示 LOGO 与“PAR 光谱仪专用软件 / ASMART-GROW-SPECTRA I”。
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/app_info.py SOFTWARE_VERSION_LABEL；par_app/app_info.py SOFTWARE_RELEASE_DATE；par_app/ui.py BRAND_LOGO_PATH

### UI-094 右侧记录区始终展开
- 规则：设置页右侧记录区始终展开，显示采集状态、来源设备、数据库摘要及最近记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 73 行「设置与导出布局（2026-09-20）」“右侧记录区始终展开，显示采集状态、来源设备、数据库摘要及最近记录”
- 状态：待确认
- 现状符合度：符合（按 D-146 裁决，“最近记录”指最近日志：activity_group（设备状态与最近日志）无折叠控件，包含 connection_status_label、serial_verified_label、database_summary_label 与日志表 settings_activity。）
- 冲突：D-146 已裁决：设置页“最近记录”指最近日志
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-095 版本号仅在设置与导出页显示
- 规则：软件版本号只在“设置与导出”页显示，其他页面、窗口标题和弹窗不显示版本号。
- 来源：业务规则与变更日志_V1.0.2.md 第 73 行「设置与导出布局（2026-09-20）」“并保留公司和联系信息。版本号仅在设置与导出页显示”
- 状态：待确认
- 现状符合度：符合（界面上版本号只在 _build_settings 关于区显示（V1.0.3 起为 par_app/app_info.py 的 SOFTWARE_VERSION_LABEL）；SOFTWARE_VERSION 另被 release_self_test（自检输出，非界面）引用；主窗口标题与 show_about_support 弹窗不含版本。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/app_info.py SOFTWARE_VERSION_LABEL；par_app/ui.py MainWindow._build_settings；par_app/release_self_test.py run_release_self_test

### UI-096 设置页超高时整页滚动
- 规则：设置页内容超出可用高度时整页滚动，不保证所有分区在首屏完整显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 73 行「设置与导出布局（2026-09-20）」“内容超出可用高度时整页滚动，不保证所有分区在首屏完整显示”
- 状态：待确认
- 现状符合度：符合（_build_settings 用 QScrollArea(widgetResizable) 包裹整页内容。）
- 冲突：D-180 已裁决 2026-10-18（按推荐）：选 A，维持本条（V1.0.2 整页滚动，不保证首屏），第 82 行“1230x700首屏操作可见性已检查”只算当时的检查记录；阶段二新界面再定首屏布局。2026-10-18 起两个首屏用例按 A 改为滚动可达检查、豁免删除（内部文档 第 83 条，待负责人确认）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-097 维护/停止/严重状态在右上方提示
- 规则：维护暂停、正在停止通信或严重硬件停止时，设置页右上方显示明确提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 75 行「设置与导出布局（2026-09-20）」“维护暂停、正在停止或严重硬件状态会在右上方明确提示”
- 状态：待确认
- 现状符合度：符合（maintenance_attention 置于右栏顶部；_refresh_communication_events 在 halt/maintenance/entering 时显示 maintenance_status_label。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._refresh_communication_events

### UI-098 维护期间显示退出维护并恢复采集
- 规则：维护期间显示“退出维护并恢复采集”。
- 来源：业务规则与变更日志_V1.0.2.md 第 75 行「设置与导出布局（2026-09-20）」“会在右上方明确提示；维护期间显示「退出维护并恢复采集」”
- 状态：待确认
- 现状符合度：符合（maintenance_resume_action 文案“退出维护并恢复采集”；MainWindow._refresh_communication_events 中 maintenance_resume_button.setVisible(coordinator._maintenance)。非维护时隐藏属代码现状，原文未规定。）
- 冲突：D-110 已裁决：设置页和维护弹窗两处恢复采集入口都保留，禁止条件统一采用弹窗按钮那一套（含“校准有未处理修改”）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._refresh_communication_events

### UI-099 设备登记表列顺序
- 规则：设备登记表列顺序固定为：设备名称、从站地址、启用采集、失败停止、数据库文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 76 行「设置与导出布局（2026-09-20）」“设备登记表列顺序为「设备名称、从站地址、启用采集、失败停止、数据库文件」”
- 状态：待确认
- 现状符合度：符合（_build_settings: device_table.setHorizontalHeaderLabels(("设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"))。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-100 双击日志打开只读详情弹窗
- 规则：双击设置页日志表任意一列，打开只读弹窗，显示来源设备、数据库路径、时间、级别、类别、原始完整消息和详情。
- 来源：业务规则与变更日志_V1.0.2.md 第 80 行「设置与导出布局（2026-09-20）」“双击日志任意一列打开只读弹窗，显示来源设备、数据库路径、时间、级别、类别、原始完整消息和详情”
- 状态：待确认
- 现状符合度：符合（settings_activity.cellDoubleClicked → _show_settings_log_details（任意列都读第0列 UserRole 快照）；QTextBrowser 只读；快照含设备、数据库、时间、级别、类别、消息、详情；verify_configuration.verify_settings_logs。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_settings_log_details；par_app/ui.py MainWindow.refresh_settings_console

### UI-101 日志详情不新增通信查询
- 规则：日志详情功能不新增任何设备通信查询，旧悬停提示、列表筛选和底层日志均保留。
- 来源：业务规则与变更日志_V1.0.2.md 第 80 行「设置与导出布局（2026-09-20）」“旧悬停提示、列表筛选和底层日志均保留，不新增通信查询”
- 状态：待确认
- 现状符合度：符合（_show_settings_log_details 只读取表格项数据，不调用 queue_task；refresh_settings_console 仍设置悬停提示与筛选。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_settings_log_details

### UI-102 日志详情使用所点行的内容快照
- 规则：日志详情弹窗使用所点行在点击时的内容快照，不随后台刷新或切换查看对象而替换。
- 来源：业务规则与变更日志_V1.0.2.md 第 80 行「设置与导出布局（2026-09-20）」“弹窗使用所点行的内容快照，不随着后台刷新或查看对象切换而替换”
- 状态：待确认
- 现状符合度：符合（refresh_settings_console 把快照文本存入第0列 Qt.UserRole；弹窗打开时取出字符串传给 setPlainText；verify_settings_logs 在弹窗打开期间刷新为空列表后断言正文不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_settings_log_details；par_app/ui.py MainWindow.refresh_settings_console

### UI-103 日志详情可选中文字和复制全部
- 规则：日志详情弹窗中的文字可选中，并提供“复制全部”按钮复制完整内容。
- 来源：业务规则与变更日志_V1.0.2.md 第 80 行「设置与导出布局（2026-09-20）」“原始完整消息和详情；可选中文字或点击「复制全部」”
- 状态：待确认
- 现状符合度：符合（_show_settings_log_details 添加“复制全部”按钮，写入 QApplication.clipboard()；QTextBrowser 可选中文本；verify_settings_logs 断言剪贴板内容等于快照。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_settings_log_details

### UI-104 日志详情纯文本显示原始内容
- 规则：日志详情正文按纯文本显示，原样保留原始 JSON 或非 JSON 内容（不解析、不渲染 HTML）。
- 来源：业务规则与变更日志_V1.0.2.md 第 80 行「设置与导出布局（2026-09-20）」“正文按纯文本显示，保留原始JSON或非JSON内容”
- 状态：待确认
- 现状符合度：符合（_show_settings_log_details 用 setPlainText，关闭链接打开；快照使用 details_json 原始字符串；verify_settings_logs 用 '<html>raw error & invalid JSON</html>' 断言原样保留。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_settings_log_details

### UI-105 登记表每台设备独立“失败停止”开关列
- 规则：设备登记表在“启用采集”与“数据库文件”两列之间设“失败停止”列，每台已登记设备各有一个独立勾选开关，互不影响。
- 来源：业务规则与变更日志_V1.0.2.md 第 113 行「失败停止开关（2026-09-30）」“设备登记表在「启用采集」与「数据库文件」之间新增「失败停止」列，每台设备独立开关”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_settings 表头为("设备名称","从站地址","启用采集","失败停止","数据库文件")，每行独立 stop_box；_device_row_config 逐行读入 auto_stop_on_failure。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._device_row_config

### UI-106 “仅显示非零项”默认勾选
- 规则：诊断页硬件错误计数表的“仅显示非零项”筛选默认处于勾选状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“「仅显示非零项」默认勾选；已读且全零显示「未发现非零错误计数」”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog._build_diagnostics 中 self.nonzero.setChecked(True)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog._build_diagnostics

### UI-107 刷新后软件事件回到最新入库事件
- 规则：软件事件列表每次刷新后滚动回到最新入库的事件（列表顶部）。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“刷新后回到最新入库事件，数据库仍按ID倒序且不改写日志”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics 末尾 events.scrollToTop()，数据按 ID 倒序。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### UI-108 历史快照空态标注历史
- 规则：当显示的是历史快照（读取失败后保留或维护期间）且非零筛选为空时，空态文字明确标注为历史快照。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“未读取不当作零，历史快照空态明确标注历史”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.filter_errors historical 时显示“历史快照中未发现非零错误计数”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.filter_errors

### UI-109 已读且全零时显示“未发现非零错误计数”
- 规则：已读取且错误计数全零时显示“未发现非零错误计数”。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“已读且全零显示「未发现非零错误计数」，未读取不当作零”
- 状态：待确认
- 现状符合度：符合（按 D-147 裁决，只在“仅显示非零项”开启时提示：DeviceMaintenanceDialog.filter_errors 仅在全部行被隐藏时显示 errors_empty，筛选开启（默认）时已读全零显示该提示；取消勾选后全零行可见、不提示。）
- 冲突：D-147 已裁决：“未发现非零错误计数”只在“仅显示非零项”开启时提示
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.filter_errors

### UI-110 普通刷新不重算分隔位置
- 规则：诊断的普通刷新不重新计算硬件区/事件区分隔位置，保留用户手动拖动的高度；超出区域的条目滚动查看。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“普通刷新不重算分隔位置，保留手动高度，超出区域的条目滚动查看”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 仅在该库首次成功快照（previous is None）时启动 error_height_timer。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished

### UI-111 未读取的错误计数不当作零
- 规则：尚未读取的错误计数不当作零。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“已读且全零显示「未发现非零错误计数」，未读取不当作零”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.display_diagnostics 无快照时计数显示“—”并提示“尚未读取，不代表零错误”；DeviceMaintenanceDialog.filter_errors 只隐藏文本为“0”的行，未读取行不被隐藏，也不出现全零空态。“—”文案为代码现状，原文未规定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.filter_errors

### UI-112 硬件错误区高度按可见条数自动分配的触发时机
- 规则：硬件错误区在首次显示、首次成功读取、切换设备或切换非零筛选时按可见条数分配高度：全零、未读取及1至3条按约3行预留，更多条目逐步增高，最多约占表格区域40%，窄窗口不低于控件最小可读高度，其余空间给软件事件。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“全零、未读取及1至3条按约3行预留，更多条目逐步增高，最多约占表格区域40%（窄窗口不低于控件最小可读高度），其余空间给软件事件”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.fit_error_height 按 max(3, 可见行) 计算表高，hardware_height = max(section.minimumSizeHint().height(), min(preferred, int(available*0.4)))，即 40% 封顶但不低于硬件区最小尺寸；由 showEvent、task_finished（previous is None）、change_device、error_filter_changed 触发。）
- 冲突：无（“窄窗口不低于控件最小可读高度”另见 UI-313，内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.fit_error_height；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.error_filter_changed；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.showEvent

### UI-113 软件事件悬停与详情保留完整原文
- 规则：软件事件表单行省略显示，但悬停提示和“事件详情”中保留事件完整原文。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“悬停及事件详情保留完整原文，刷新后回到最新入库事件”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics 每格 setToolTip(原文)，show_event_details 输出完整事件 JSON。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.show_event_details

### UI-114 首次读取的增量显示“—”
- 规则：“较上次读取新增”列在首次读取时显示“—”，不显示 0。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“累计次数和「较上次读取新增」列适宽且数值居中，首次增量仍为「—」”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 无上次快照时 delta 为 None，display_diagnostics 显示“—”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### UI-115 维护顶栏采集状态完整显示不截断
- 规则：维护窗口顶栏的采集状态右侧分配剩余宽度（至少约100像素），完整文案可换行，不截断正常、部分异常、等待、维护暂停或带原因的停止状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 125 行「统一设备维护（2026-09-18，当前布局）」“完整文案可换行，不截断正常、部分异常、等待、维护暂停或带原因的停止状态”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__ 中 self.state.setWordWrap(True)、setMinimumWidth(100)、stretch=1。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__

### UI-116 硬件停止原因优先于任务进度显示
- 规则：维护顶栏同时存在硬件停止与任务进度时，优先显示硬件停止原因。
- 来源：业务规则与变更日志_V1.0.2.md 第 126 行「统一设备维护（2026-09-18，当前布局）」“维护暂停或硬件停止不冒充正常。硬件停止原因优先于任务进度”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 中 halt_reason 判断位于 busy/entering/calibration 之前。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### UI-117 诊断刷新期间顶栏红色显示读取进度
- 规则：诊断读取进行期间，维护顶栏以红色“正在读取设备诊断…”临时替代采集状态，不另占一行显示“设备任务进行中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 126 行「统一设备维护（2026-09-18，当前布局）」“诊断刷新期间顶栏以红色「正在读取设备诊断…」临时替代采集状态，不再另占一行显示「设备任务进行中」”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls busy 时 state_text="正在读取设备诊断…" 红色；read_reason 仅在 idle 时可见。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### UI-118 诊断成功后恢复实际采集状态且不冒充正常
- 规则：诊断读取成功后，顶栏恢复显示实际采集状态：正常采集为黑色；维护暂停或硬件停止时如实显示，不冒充正常。
- 来源：业务规则与变更日志_V1.0.2.md 第 126 行「统一设备维护（2026-09-18，当前布局）」“成功后恢复实际采集状态，正常采集为黑色，维护暂停或硬件停止不冒充正常”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 默认取主界面 acquisition_state_label 文案、黑色；halt 或 maintenance 时红色。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### UI-119 诊断读取失败保留红色原因与历史标识
- 规则：诊断读取失败后，在窗口底部保留红色失败原因，同时诊断快照保留“历史值”标识。
- 来源：业务规则与变更日志_V1.0.2.md 第 126 行「统一设备维护（2026-09-18，当前布局）」“读取失败后在底部保留红色失败原因，并保留历史快照标识”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 失败时 set_result(error=True) 并记录 failures；display_diagnostics 据此加“历史值 · ”前缀。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.set_result

### UI-120 失败原因与导出结果继续显示
- 规则：诊断失败原因与导出结果继续显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 127 行「统一设备维护（2026-09-18，当前布局）」“失败原因与导出结果继续显示，导出成功恢复普通文字颜色”
- 状态：待确认
- 现状符合度：不符合（按 D-158 裁决需修改，待修复。按裁决，失败原因和导出结果保持到下一次操作开始，现状的清空路径符合；需修改：导出写文件失败（OSError）也须在底部结果区显示（同时保留弹窗），现状只弹 QMessageBox.warning。原核对（未验证）：写入路径：读取失败时 DeviceMaintenanceDialog.task_finished 调 set_result("读取失败：…", error=True) 在底部显示；导出成功时 DeviceMaintenanceDialog.export_diagnostics 调 set_result 显示“诊断快照已导出/事件记录已导出”。清空路径：以下操作都调用 set_result('')，底部结果文字清空并隐藏，已显示的“读取失败：…”或“诊断快照已导出”随即消失——再次刷新（DeviceMaintenanceDialog.refresh_diagnostics，含切到诊断页、打开弹窗时 DeviceMaintenanceDialog.prepare 经 page_changed 触发的自动刷新）、切换页签（DeviceMaintenanceDialog.page_changed）、切换设备（DeviceMaintenanceDialog.change_device）、下一次读取成功（task_finished 的成功分支）。读取失败原因另记入 self.failures，该设备没有成功快照时，诊断时间行（display_diagnostics 的 stamp）显示“本次尚未读取硬件诊断；最近读取失败：…”；已有成功快照时该行只标“历史值”，不显示失败原因。导出结果没有其他保留位置。例外：导出写文件失败（OSError）只弹 QMessageBox.warning，不在底部结果区显示。原文“继续显示”持续到何时、“导出结果”是否包含导出失败，都未规定，见 D-158。）
- 冲突：D-158 已裁决：失败原因和导出结果保持到下一次操作开始；“导出结果”包括导出失败，导出失败也在底部结果区显示（同时保留弹窗），待修复（DEF-24）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.export_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.set_result；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.refresh_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.page_changed；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.change_device；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### UI-121 诊断成功不显示底部完成提示
- 规则：诊断读取成功后只更新快照与顶部实际状态，不再显示底部“诊断读取完成”；结果标签为空时隐藏。
- 来源：业务规则与变更日志_V1.0.2.md 第 127 行「统一设备维护（2026-09-18，当前布局）」“诊断成功后仅更新快照与顶部实际状态，不再显示底部「诊断读取完成」；空结果标签隐藏”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished 成功时 set_result("")，set_result 在文本为空时隐藏标签。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.task_finished；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.set_result

### UI-122 曝光时间仅界面按毫秒显示
- 规则：诊断页曝光时间在界面上按毫秒显示一位小数。
- 来源：业务规则与变更日志_V1.0.2.md 第 129 行「统一设备维护（2026-09-18，当前布局）」“曝光时间仅界面按毫秒显示一位小数，原始微秒值及诊断导出不变”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.display_diagnostics 以 exposure_time_us/1000 格式化为 .1f ms。原始微秒值与诊断导出不变两项已另拆至 MAINT 领域。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### UI-123 软件事件已知类别显示中文
- 规则：软件事件的连接、通信、诊断、校准等已知类别在界面显示中文名称；“读取通信参数”事件不再显示为 connection。
- 来源：业务规则与变更日志_V1.0.2.md 第 129 行「统一设备维护（2026-09-18，当前布局）」“软件事件的连接、通信、诊断、校准等已知类别显示中文，读取通信参数事件不再显示为connection”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics 的类别映射，并对 category=connection 且 message=已读取设备当前通信参数 显示“读取通信参数”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.display_diagnostics

### UI-124 主导航为五页
- 规则：主导航共五页，依次为：实时概览、历史回放、光谱运算、日累计光积分、设置与导出。
- 来源：业务规则与变更日志_V1.0.2.md 第 131 行「统一设备维护（2026-09-18，当前布局）」“主导航为五页：实时概览、历史回放、光谱运算、日累计光积分、设置与导出”
- 状态：待确认
- 现状符合度：符合（按 D-108 裁决，主导航为五页，页名以第254、262行“光谱计算”“光积累计算”为准，本条所列“光谱运算”“日累计光积分”为历史写法：par_app/ui.py MainWindow.__init__ 建 5 个页签，依次为实时概览、历史回放、光谱计算、光积累计算、设置与导出。）
- 冲突：D-108 已裁决：页名以“光谱计算”“光积累计算”为准，主导航为五页；第131行旧页名和第320行“六页”标为历史写法
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.__init__；par_app/ui.py PageTabBar

### UI-125 设备维护入口位于设置与导出页左下方
- 规则：设备维护弹窗的入口位于“设置与导出”页左下方。
- 来源：业务规则与变更日志_V1.0.2.md 第 131 行「统一设备维护（2026-09-18，当前布局）」“原P4校准管理迁入设备维护弹窗，入口位于设置与导出页左下方”
- 状态：已废止 2026-10-17，由 UI-074 替代（D-109 裁决：第131行入口位于“左下方”标为历史废止）
- 现状符合度：不符合（par_app/ui.py MainWindow._build_settings 将“设备维护”按钮加入右栏 settings_maintenance_row 并右对齐，不在左下方。）
- 冲突：D-109 已裁决：维护入口以第69行（右栏、右对齐、与办公地址底边对齐）为准，第131行“左下方”和第296行“左下方‘通信参数’按钮”标为历史废止；本条已废止，约束由 UI-074 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings

### UI-126 校准参数按节点配对与全局参数分组
- 规则：校准页按P0至P4逐行配对节点波长与节点修正值，中文列标题保留原变量名；整体倍率、修正上限、修正下限作为独立的全局参数显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 138 行「统一设备维护（2026-09-18，当前布局）」“P0至P4逐行配对波长和节点修正值，中文列标题保留原变量名；整体倍率、修正上下限独立为全局参数”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_calibration 的 form（P0–P4 × x/y）与 global_box（k_global/limit_min/limit_max）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_calibration

### UI-127 校准参数显示精度与单位
- 规则：波长显示1位小数；节点修正和修正上下限按百分比显示2位小数；整体倍率显示4位小数。
- 来源：业务规则与变更日志_V1.0.2.md 第 138 行「统一设备维护（2026-09-18，当前布局）」“波长显示1位小数，节点修正和上下限按百分比显示2位，倍率显示4位”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_calibration：x* decimals=1，y*/limit_* scale=100 decimals=2，k_global decimals=4。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_calibration；par_app/services/calibration.py field_scale

### UI-128 窄窗口校准参数区独立横向滚动
- 规则：窄窗口时校准参数区保留独立横向滚动，以保持字段单行和对齐，不撑宽图表。
- 来源：业务规则与变更日志_V1.0.2.md 第 140 行「统一设备维护（2026-09-18，当前布局）」“窄窗口参数区保留独立横向滚动以保持字段单行和对齐，不撑宽图表”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py CalibrationParameterScroll 为参数区独立 QScrollArea；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 在宽度<1080 时断言 parameter_scroll 横向滚动条 maximum>0 且滚到最右可见 limit_max，整页 scroll 横向 maximum 为 0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py CalibrationParameterScroll.resizeEvent；par_app/ui.py CalibrationDetailsPanel.arrange

### UI-129 校准信息五行内容
- 规则：校准信息按五行显示：校准状态、错误状态、版本/节点数、“上次校准时间（北京时间）”标题、完整秒级时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 141 行「统一设备维护（2026-09-18，当前布局）」“校准信息按五行显示：校准状态、错误状态、版本/节点数、「上次校准时间（北京时间）」、完整秒级时间”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_calibration 的 status_form 五个标签；时间由 _format_mcu_timestamp 格式化到秒。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_calibration；par_app/services/calibration.py status_texts；par_app/services/calibration.py format_mcu_timestamp

### UI-130 校准值状态标识规则
- 规则：正常回读后隐藏“当前硬件值”；有修改时显示红色“待写入修改”，放弃或写入回读成功后隐藏；回读失败或无效参数时保留红色异常标识。
- 来源：业务规则与变更日志_V1.0.2.md 第 142 行「统一设备维护（2026-09-18，当前布局）」“正常回读后隐藏「当前硬件值」，修改后显示红色「待写入修改」，放弃或写入回读成功后隐藏；回读失败或无效参数保留红色异常标识”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._refresh_calibration_plots（dirty 时红色显示）、_apply_hardware_calibration（隐藏）、_device_task_finished/_task_finished（“回读未确认”“回读参数无效”红色）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_calibration_plots；par_app/ui.py MainWindow._device_task_finished；par_app/services/calibration.py is_dirty

### UI-131 校准底部长说明的显示与隐藏
- 规则：正常读取、写入回读成功及放弃修改后隐藏底部长说明，不留空提示行；普通拖拽不增加操作说明；未读取提示及失败、无效参数提示仍保留。
- 来源：业务规则与变更日志_V1.0.2.md 第 142 行「统一设备维护（2026-09-18，当前布局）」“正常读取、写入回读成功及放弃修改后隐藏底部长说明，不留空提示行”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._apply_hardware_calibration 调 _set_calibration_note("")（隐藏）；失败/无效分支以 error=True 显示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._set_calibration_note；par_app/ui.py MainWindow._apply_hardware_calibration

### UI-132 校准读写期间维护顶栏显示红色进度
- 规则：校准读取、写入并回读期间，维护窗口顶栏显示对应的红色进度文字。
- 来源：业务规则与变更日志_V1.0.2.md 第 142 行「统一设备维护（2026-09-18，当前布局）」“读取、写入并回读期间，维护顶栏显示对应红色进度”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls 在 _calibration_busy 时显示“正在写入校准并回读…”/“正在读取硬件校准…”红色。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.update_controls

### UI-133 校准图横轴固定350–1050并保留端点刻度
- 规则：校准图横轴范围始终为350至1050 nm，显式保留两端刻度；常规刻度为350/400/500/600/700/800/900/1000/1050，画布宽度小于680像素时省略400和1000，放宽后恢复。
- 来源：业务规则与变更日志_V1.0.2.md 第 143 行「统一设备维护（2026-09-18，当前布局）」“横轴范围始终350至1050，显式保留两端刻度”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py CalibrationCanvas._set_wavelength_ticks 与 resizeEvent。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py CalibrationCanvas._set_wavelength_ticks；par_app/ui.py CalibrationCanvas.resizeEvent

### UI-134 读取连接参数锁定时清晰可读且解锁后可编辑
- 规则：“读取连接参数”各输入在锁定状态下保持清晰可读（不呈现难以辨认的灰色），维护解锁后仍允许编辑。
- 来源：业务规则与变更日志_V1.0.2.md 第 145 行「统一设备维护（2026-09-18，当前布局）」“读取连接参数锁定时保持清晰可读，维护解锁后仍允许编辑”
- 状态：待确认
- 现状符合度：符合（par_app/maintenance_dialog.py MaintenanceDialog.__init__ 为 old_fields 设置 disabled 样式；update_controls 在 ready 且无 pending 时启用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/maintenance_dialog.py MaintenanceDialog.__init__；par_app/maintenance_dialog.py MaintenanceDialog.update_controls

### UI-135 设置页可配置总线与设备登记字段
- 规则：设置页提供串口、波特率、奇偶校验的选择，以及设备名称、ID填写和“启用采集”勾选。
- 来源：业务规则与变更日志_V1.0.2.md 第 178 行「多设备重构：第 1 阶段（2026-09-17）」“启动后在设置页选择串口、波特率和奇偶校验，填写设备名称和 ID，勾选启用采集”
- 状态：待确认
- 现状符合度：符合（MainWindow.bus_config_from_form 读取 serial_port/baudrate/parity；_device_row_config 读取 device_name_items、device_id_spins、device_enabled_boxes。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.bus_config_from_form；par_app/ui.py MainWindow._device_row_config

### UI-136 不提供重新加入按钮
- 规则：界面不提供让已退出设备重新加入本次采集的按钮。
- 来源：业务规则与变更日志_V1.0.2.md 第 204 行「多设备重构：第 3 阶段（2026-09-17）」“退出后仅重启软件重新尝试，不提供重新加入按钮。”
- 状态：待确认
- 现状符合度：符合（ui.py / device_maintenance_dialog.py 中无“重新加入”控件（grep 无结果）；_process_tasks 对 excluded 设备的任务一律返回“已退出本次采集，重启软件后重新尝试”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：要求的是不存在某个按钮，代码中无对应实现可锚定

### UI-137 公共异常区显示全部启用设备异常
- 规则：公共异常文字区列出所有启用设备的当前异常，内容与当前选中的查看设备无关。
- 来源：业务规则与变更日志_V1.0.2.md 第 206 行「多设备重构：第 3 阶段（2026-09-17）」“公共异常文字区显示所有启用设备的当前异常，不依赖当前选择”
- 状态：待确认
- 现状符合度：符合（_refresh_communication_events 遍历 hub.keys() 中所有 enabled 设备快照，failures>0 即加一行，不按 active_key 过滤。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-138 恢复后隐藏异常但保留历史日志
- 规则：设备恢复正常后，公共异常区隐藏该设备的异常；历史日志不删除。
- 来源：业务规则与变更日志_V1.0.2.md 第 206 行「多设备重构：第 3 阶段（2026-09-17）」“正常恢复后隐藏该设备异常，历史日志不删除。”
- 状态：待确认
- 现状符合度：符合（_mark_ok 将 failures 置 0，_refresh_communication_events 只显示 failures>0 的设备并在无行时 hide；diagnostics 无删除路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._mark_ok

### UI-139 普通通信异常不弹窗
- 规则：普通通信异常只在公共异常文字区显示，不弹出对话框。
- 来源：业务规则与变更日志_V1.0.2.md 第 206 行「多设备重构：第 3 阶段（2026-09-17）」“正常恢复后隐藏该设备异常，历史日志不删除。普通通信异常不弹窗。”
- 状态：待确认
- 现状符合度：符合（coordinator.device_alert 从未 emit；ActiveDeviceService.communication_alert 在 UI 中无连接；弹窗只连接 acquisition_halted（_show_hardware_stop）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/device_hub.py ActiveDeviceService._on_alert

### UI-140 勾选失败停止的启用设备全部退出后显示红色采集停止中
- 规则：所有已启用的勾选“失败停止”设备退出后显示红色“采集停止中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 207 行「多设备重构：第 3 阶段（2026-09-17）」“所有已启用的勾选「失败停止」设备退出后显示红色「采集停止中」”
- 状态：待确认
- 现状符合度：符合（按 D-148 裁决，混合勾选配置下不显示红色：MainWindow._refresh_communication_events 仅在全部启用设备快照 excluded 时显示“采集停止中：无可采集设备，重启软件后重新尝试”（#dc2626）；所有启用设备均勾选且均退出时显示，混合配置下未勾选设备不会 excluded、不显示红色。）
- 冲突：D-148 已裁决：混合勾选配置下不显示红色“采集停止中”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-141 退出后仍可切换查看设备历史
- 规则：设备退出后，用户仍可在顶部切换并查看各设备的历史数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 207 行「多设备重构：第 3 阶段（2026-09-17）」“停止重连尝试；仍可切换查看设备历史。退出设备的维护任务也不会继续访问硬件。”
- 状态：待确认
- 现状符合度：符合（_style_device_buttons 对已登记设备 setEnabled(device is not None)，故障仅改红色不禁用；页面数据读库不依赖在线状态。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons；par_app/ui.py MainWindow._bind_active_device

### UI-142 正常采集时公共异常区隐藏
- 规则：所有启用设备正常采集（无连续失败）时，公共异常文字区隐藏。
- 来源：业务规则与变更日志_V1.0.2.md 第 211 行「多设备重构：第 3 阶段（2026-09-17）」“1. 正常采集时，公共异常文字区应隐藏。”
- 状态：待确认
- 现状符合度：符合（_refresh_communication_events：无 failures>0 的设备时 communication_events_label.setVisible(False)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-143 异常文字含设备名、时间和N/10次数
- 规则：通信中断后，公共异常文字包含设备名称、失败时间和“1/10、2/10”形式的连续失败次数。
- 来源：业务规则与变更日志_V1.0.2.md 第 212 行「多设备重构：第 3 阶段（2026-09-17）」“断开探头通信后，检查异常文字包含设备名称、时间和1/10、2/10等连续次数”
- 状态：待确认
- 现状符合度：符合（按 D-115 裁决，“1/10、2/10”只适用于勾选失败停止的设备：_refresh_communication_events 输出“时间  名称（地址）  message”；_mark_failed 勾选时生成“连续第 N/10 次”，默认不勾选时为“连续第 N 次…（未启用失败停止…）”，不带“/10”。）
- 冲突：D-115 已裁决：“1/10、2/10”只适用于勾选失败停止的设备，默认不勾选时显示“连续第 N 次”（不带上限）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._mark_failed

### UI-144 第10次前恢复后异常消失
- 规则：在第10次失败之前恢复通信，下一轮采集成功后公共异常文字消失。
- 来源：业务规则与变更日志_V1.0.2.md 第 212 行「多设备重构：第 3 阶段（2026-09-17）」“第10次之前恢复通信，下一轮成功后异常应消失。”
- 状态：待确认
- 现状符合度：符合（_mark_ok 清零 failures，_refresh_communication_events 随 device_state_changed 刷新并隐藏该行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_ok；par_app/ui.py MainWindow._refresh_communication_events

### UI-145 单台设备退出时显示红色采集停止中
- 规则：只登记一台启用设备且其因失败停止退出时，显示红色“采集停止中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 213 行「多设备重构：第 3 阶段（2026-09-17）」“恢复硬件连接也不自动重新加入。只有一台设备时显示红色「采集停止中」。”
- 状态：待确认
- 现状符合度：符合（_refresh_communication_events：唯一启用设备 excluded 即满足 all(excluded)，显示红色“采集停止中：无可采集设备…”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-146 默认不勾选时不出现红色采集停止中
- 规则：默认不勾选时，持续通信失败不出现红色“采集停止中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“异常区显示「未启用失败停止」，且不出现红色「采集停止中」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备不再触发全局锁停，界面不出现红色“采集停止中”。（V1.0.2 现状：原核对：普通失败路径下未勾选设备不 excluded，_refresh_communication_events 显示琥珀色“采集运行中：等待设备响应”；但 BUG-1 下静默设备触发 _halt_acquisition，显示红色“采集停止中”。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._halt_acquisition

### UI-147 默认不勾选时异常区提示未启用失败停止
- 规则：默认不勾选时，异常区显示“未启用失败停止”。
- 来源：业务规则与变更日志_V1.0.2.md 第 215 行「多设备重构：第 3 阶段（2026-09-17）」“确认设备仍在重试、异常区显示「未启用失败停止」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备走 _mark_failed，异常区显示“未启用失败停止”。（V1.0.2 现状：原核对：普通失败路径符合：PollingCoordinator._mark_failed 未勾选时消息含“（未启用失败停止，将继续按周期重试）”，由 MainWindow._refresh_communication_events 展示有失败计数的设备行。例外：通信静默导致恢复未确认时 PollingCoordinator._poll_one 捕获 AcquisitionResumeError 走 _halt_acquisition 而非 _mark_failed，不生成该文字，界面显示全局锁停（同 UI-146 的 D-101 路径）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/coordinator.py PollingCoordinator._mark_failed；par_app/coordinator.py PollingCoordinator._poll_one；par_app/ui.py MainWindow._refresh_communication_events

### UI-148 停止对话框内容
- 规则：硬件停止对话框标明设备名称、地址、时间、异常原因和“所有设备已停止采集”。
- 来源：业务规则与变更日志_V1.0.2.md 第 225 行「多设备重构：第 4 阶段（2026-09-17）」“对话框标明设备名称、地址、时间、异常原因和「所有设备已停止采集」”
- 状态：待确认
- 现状符合度：符合（_show_hardware_stop 文本含 occurred_at、name、slave_id、reason，硬件异常分支含“所有设备已停止采集”，标题“所有设备采集已停止”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_hardware_stop

### UI-149 对话框说明重新上电并重启
- 规则：硬件停止对话框说明应为设备重新上电并重启软件。
- 来源：业务规则与变更日志_V1.0.2.md 第 225 行「多设备重构：第 4 阶段（2026-09-17）」“异常原因和「所有设备已停止采集」，说明应重新上电并重启软件。”
- 状态：待确认
- 现状符合度：符合（_show_hardware_stop 硬件分支文本“请为该设备重新上电，然后退出并重新启动软件”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_hardware_stop

### UI-150 全局停止期间状态持续红色
- 规则：全局停止期间，实时运行状态持续显示红色“采集停止中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 226 行「多设备重构：第 4 阶段（2026-09-17）」“均不能解除全局停止。实时运行状态持续为红色「采集停止中」。”
- 状态：待确认
- 现状符合度：符合（_refresh_communication_events 在 halt_reason 存在时以 halt message（“采集停止中：…”）和 #dc2626 显示并调用 _status("error")；该函数随 3 秒定时 refresh_all 重复执行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/ui.py MainWindow._status

### UI-151 确认按钮只关闭提示
- 规则：硬件停止对话框的“确认”只关闭提示，不解除停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 226 行「多设备重构：第 4 阶段（2026-09-17）」“「确认」只关闭提示；页面刷新、切换设备、保存配置或移除异常设备”
- 状态：待确认
- 现状符合度：符合（_show_hardware_stop 仅 exec_ 对话框后刷新状态，不触碰 _halt_reason；_hardware_stop_shown 保证一次性。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._show_hardware_stop

### UI-152 切换设备重置历史选择
- 规则：切换当前查看设备时，历史选择按新设备数据库重新读取，不沿用上一台的选中记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 236 行「多设备重构：第 5 阶段（2026-09-17）」“切换当前设备时重新读取该库的DLI经纬度、历史选择和导出统计”
- 状态：待确认
- 现状符合度：符合（_bind_active_device 清空 _history_displayed_id/_history_refresh_key 和表格选择，refresh_all→refresh_history 按新库重查。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow.refresh_history

### UI-153 切换设备重读DLI经纬度
- 规则：切换当前查看设备时，重新读取该设备数据库中的DLI经纬度。
- 来源：业务规则与变更日志_V1.0.2.md 第 236 行「多设备重构：第 5 阶段（2026-09-17）」“切换当前设备时重新读取该库的DLI经纬度、历史选择和导出统计”
- 状态：待确认
- 现状符合度：符合（_bind_active_device 调用 self.database.load_dli_location() 并写回经纬度控件；verify_multidevice 覆盖 DLI 位置。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/database.py ParDatabase.load_dli_location

### UI-154 空库清空图表和指标
- 规则：切换到空库或无光谱记录的设备时，清空图表和指标，不保留上一台设备的数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 236 行「多设备重构：第 5 阶段（2026-09-17）」“空库或无光谱记录清空图表和指标，不保留上一台数据。”
- 状态：待确认
- 现状符合度：符合（refresh_overview 在 plot_key 变化时清空状态卡、指标卡与 KPI 并画“当前设备暂无可显示光谱”；refresh_history 无记录时画“当前设备无匹配光谱”；verify_multidevice 覆盖空库清屏。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/ui.py MainWindow.refresh_history

### UI-155 A、B分别选择数据库与记录
- 规则：光谱运算的A、B各自独立选择设备数据库和采集记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 237 行「多设备重构：第 5 阶段（2026-09-17）」“光谱运算由A、B分别选择设备数据库与采集记录”
- 状态：待确认
- 现状符合度：符合（_build_operations 建 a/b_database_combo 与 a/b_combo，_refresh_operation_records 按各自数据库填充记录。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations；par_app/ui.py MainWindow._refresh_operation_records

### UI-156 初始A为首台、B为第二台
- 规则：光谱运算初始时A选首台设备，B选第二台设备；只有一台设备时A、B同库。
- 来源：业务规则与变更日志_V1.0.2.md 第 237 行「多设备重构：第 5 阶段（2026-09-17）」“初始A为首台设备，B为第二台（仅一台时同库）。”
- 状态：待确认
- 现状符合度：符合（_rebuild_operation_databases 无旧选择时 index=min(position, count-1)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_operation_databases

### UI-157 记录以库路径+记录ID定位
- 规则：运算记录用数据库路径与记录ID共同定位，不同库中相同ID的记录可同时参与运算。
- 来源：业务规则与变更日志_V1.0.2.md 第 237 行「多设备重构：第 5 阶段（2026-09-17）」“记录使用数据库路径和记录ID共同定位，允许不同库各自的同号记录参与运算。”
- 状态：待确认
- 现状符合度：符合（记录下拉 itemData 为 (path, id)，_operation_item 按 path 找库再 get_spectrum(id)；verify_multidevice 覆盖两个库同号记录运算。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_item；par_app/ui.py MainWindow._refresh_operation_records

### UI-158 输入或运算法则改变清除旧结果
- 规则：运算输入（A/B库或记录）或运算法则改变后，清除旧运算结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 238 行「多设备重构：第 5 阶段（2026-09-17）」“顶部设备切换不改变A/B选定的运算来源；输入或运算法则改变后清除旧结果。”
- 状态：待确认
- 现状符合度：符合（op_combo.currentIndexChanged→_invalidate_operation_result；a/b_combo、库下拉变化→show_operation_inputs→_invalidate_operation_result（current_result=None、禁用导出）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._invalidate_operation_result；par_app/ui.py MainWindow.show_operation_inputs

### UI-159 顶部切换设备不改变A/B来源
- 规则：顶部切换查看设备不改变光谱运算中A、B已选定的来源。
- 来源：业务规则与变更日志_V1.0.2.md 第 238 行「多设备重构：第 5 阶段（2026-09-17）」“顶部设备切换不改变A/B选定的运算来源；输入或运算法则改变后清除旧结果。”
- 状态：待确认
- 现状符合度：符合（_bind_active_device 不修改运算下拉；refresh_operation_choices→_refresh_operation_records 保留仍有效的原选中 (path,id)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow.refresh_operation_choices

### UI-160 切换设备后实时/历史/DLI位置随之切换
- 规则：顶部切换设备后，实时页、历史页和DLI位置显示对应新设备的数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 245 行「多设备重构：第 5 阶段（2026-09-17）」“重启软件，在顶部切换设备，核对实时、历史、DLI位置和导出记录范围。”
- 状态：待确认
- 现状符合度：符合（_bind_active_device 重绑数据库并 refresh_all、重读 DLI 经纬度。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device

### UI-161 关闭最近时间跟随后两侧独立
- 规则：关闭“B 匹配 A 的最近时间”后，A、B两侧独立选择。
- 来源：业务规则与变更日志_V1.0.2.md 第 246 行「多设备重构：第 5 阶段（2026-09-17）」“默认会重选B的最近时间记录。关闭「B 匹配 A 的最近时间」后两侧独立选择。”
- 状态：待确认
- 现状符合度：符合（_operation_a_changed 仅在 operation_auto_match.isChecked() 时改 B。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed

### UI-162 切换A不改变B的设备库
- 规则：修改A的数据库或记录不改变B所选的设备数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 246 行「多设备重构：第 5 阶段（2026-09-17）」“切换A不改变B的设备库，默认会重选B的最近时间记录。”
- 状态：待确认
- 现状符合度：符合（_operation_a_changed 只在 b_database_combo 当前库内选记录，不改 b_database_combo。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed

### UI-163 默认切换A后重选B最近时间记录
- 规则：默认开启跟随时，切换A后在B当前库重选与A时间最近的记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 246 行「多设备重构：第 5 阶段（2026-09-17）」“切换A不改变B的设备库，默认会重选B的最近时间记录。”
- 状态：待确认
- 现状符合度：符合（operation_auto_match 默认 setChecked(True)，_operation_a_changed 调 nearest_operation_spectrum(A.acquired_at)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed；par_app/database.py ParDatabase.nearest_operation_spectrum

### UI-164 修改A/B或法则清除旧结果（手测）
- 规则：修改A/B或运算法则后，旧运算结果被清除。
- 来源：业务规则与变更日志_V1.0.2.md 第 247 行「多设备重构：第 5 阶段（2026-09-17）」“修改A/B或运算法则，应清除旧结果；切换顶部设备则保留明确选定的跨库来源。”
- 状态：待确认
- 现状符合度：符合（同第238行：op_combo/a_combo/b_combo 变化均触发 _invalidate_operation_result。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._invalidate_operation_result

### UI-165 切换顶部设备保留跨库来源（手测）
- 规则：切换顶部查看设备时，保留用户明确选定的跨库A/B来源。
- 来源：业务规则与变更日志_V1.0.2.md 第 247 行「多设备重构：第 5 阶段（2026-09-17）」“修改A/B或运算法则，应清除旧结果；切换顶部设备则保留明确选定的跨库来源。”
- 状态：待确认
- 现状符合度：符合（_bind_active_device 不改运算下拉，refresh_operation_choices 保留仍有效的选中项。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_operation_choices；par_app/ui.py MainWindow._refresh_operation_records

### UI-166 完整说明弹窗无右上角问号
- 规则：光谱计算的完整说明弹窗不显示标题栏右上角的上下文帮助问号按钮。
- 来源：业务规则与变更日志_V1.0.2.md 第 254 行「页面布局与显示（2026-09-19）」“菜单「光谱运算」更名为「光谱计算」；完整说明弹窗移除右上角问号”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.show_details 调用 dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-167 菜单名称为“光谱计算”
- 规则：主菜单页签原“光谱运算”的名称显示为“光谱计算”。
- 来源：业务规则与变更日志_V1.0.2.md 第 254 行「页面布局与显示（2026-09-19）」“菜单「光谱运算」更名为「光谱计算」；完整说明弹窗移除右上角问号”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_operations 末尾 self.tabs.addTab(tab, "光谱计算")。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-168 实时/历史固定叠加四条参考曲线
- 规则：实时页与历史页的光谱图固定叠加叶绿素A、叶绿素B、McCree、人眼明视觉四条参考曲线，不提供逐条勾选开关。
- 来源：业务规则与变更日志_V1.0.2.md 第 255 行「页面布局与显示（2026-09-19）」“实时与历史页固定叠加叶绿素 A/B、McCree、人眼明视觉四条参考曲线，不设勾选开关”
- 状态：待确认
- 现状符合度：符合（overview_chart 与 history_chart 均设 fixed_response_overlays=True；_spectrum_view_controls 对固定叠加的图跳过复选框；_plot_selected_spectrum 固定选中四条曲线并由 SpectrumCanvas._draw_response_overlays 绘制。）
- 冲突：D-102 已裁决：迁移期间冻结现状 9 锚点曲线，权重来源由农学或光学负责人确认后另开 L3 变更，只对新记录生效并在界面注明口径（相关；影响曲线形状，不影响本条“固定叠加、无开关”）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SpectrumCanvas._draw_response_overlays；par_app/ui.py MainWindow._spectrum_view_controls；par_app/ui.py MainWindow._plot_selected_spectrum

### UI-169 光谱状态信息置于图外固定行
- 规则：实时页与历史页的采集状态信息显示在光谱绘图区之外的固定一行（标题行），不绘入坐标框内。
- 来源：业务规则与变更日志_V1.0.2.md 第 256 行「页面布局与显示（2026-09-19）」“状态信息保留在图外固定行。实时页显示记录时间及距今秒数”
- 状态：待确认
- 现状符合度：符合（_spectrum_view_controls(inline_header=True) 为两页创建 SingleLineStatusLabel 并放入标题行；SpectrumCanvas._draw_status_card 在存在 status_label 时直接返回，不在图内绘制。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._spectrum_view_controls；par_app/ui.py SpectrumCanvas.set_status_card；par_app/ui.py SpectrumCanvas._draw_status_card

### UI-170 实时页显示记录时间与距今秒数
- 规则：实时页状态行显示当前所显示记录的采集时间（北京时间）以及该时间距当前的秒数。
- 来源：业务规则与变更日志_V1.0.2.md 第 256 行「页面布局与显示（2026-09-19）」“实时页显示记录时间及距今秒数，超过两个轮询周期（至少120秒）提示暂无新记录”
- 状态：待确认
- 现状符合度：符合（_update_overview_status 输出 format_beijing_time(acquired_at) 与 f"距今 {age:.0f} 秒"；记录时间晚于本机时显示“记录时间晚于本机”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status

### UI-171 超两个轮询周期提示暂无新记录
- 规则：实时页记录超过两个轮询周期（至少120秒）时提示暂无新记录，不把旧数据当作新采集结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 256 行「页面布局与显示（2026-09-19）」“超过两个轮询周期（至少120秒）提示暂无新记录，不把旧数据当作新采集结果”
- 状态：待确认
- 现状符合度：符合（按 D-149 裁决，维护或锁停时只显示“采集已暂停”：MainWindow._update_overview_status 中 stale = age > max(120, 2×effective_poll_cycle_seconds()) 或 age < -1，未暂停时追加“ · 暂无新记录”并用琥珀色；维护或全局锁停（paused）时只追加“ · 采集已暂停”。）
- 冲突：D-149 已裁决：维护或锁停时只显示“采集已暂停”，不再显示“暂无新记录”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_overview_status

### UI-172 切换设备或波段重新定量程
- 规则：实时页切换当前设备或显示波段后，丢弃原量程状态，按新数据重新确定纵轴量程。
- 来源：业务规则与变更日志_V1.0.2.md 第 257 行「页面布局与显示（2026-09-19）」“切换设备或波段重新确定量程。历史光谱按所选记录独立缩放”
- 状态：待确认
- 现状符合度：符合（_overview_scale 的 key 为 (数据库路径, wavelength_range)，key 变化即重置。波段选择后被“实时概览与历史回放（2026-10-11）”取消，现仅切换设备生效。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum

### UI-173 历史光谱按所选记录独立缩放
- 规则：历史光谱按所选记录独立缩放。
- 来源：业务规则与变更日志_V1.0.2.md 第 257 行「页面布局与显示（2026-09-19）」“切换设备或波段重新确定量程。历史光谱按所选记录独立缩放”
- 状态：待确认
- 现状符合度：符合（按 D-150 裁决，独立缩放只在未勾选“锁定纵轴”时适用：MainWindow.show_history_spectrum → _plot_selected_spectrum 未锁定时按所选记录缩放；勾选“锁定纵轴”时 MainWindow._toggle_history_axis_lock 固定当前范围，选其他记录不变。）
- 冲突：D-150 已裁决：第257行“按所选记录独立缩放”只在未勾选“锁定纵轴”时适用
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_history_spectrum；par_app/ui.py MainWindow._plot_selected_spectrum

### UI-174 实时纵轴延迟收缩条件
- 规则：实时光谱数据低于当前量程65%时不立即收缩；需该状态持续至少30秒且出现新记录后才收缩纵轴。纵轴放大时把曲线最高点放在约 62% 高度；“低于当前量程65%”指按这一高度重新算出的纵轴顶部低于当前顶部的65%，即曲线最高点降到当前纵轴顶部约40%以下。（来源：裁决 D-117，负责人 2026-10-17）
- 来源：业务规则与变更日志_V1.0.2.md 第 257 行「页面布局与显示（2026-09-19）」“实时纵轴立即扩展；数据低于当前量程65%并持续30秒、且有新记录后才收缩”
- 状态：待确认
- 现状符合度：符合（按 D-117 裁决选 B：_plot_selected_spectrum 按“最高点放在约 0.618 高度”算出建议上限 proposed=峰值/0.618，以 proposed < 当前上限×0.65 作为“低于65%”，即峰值低于当前量程约40%，持续 ≥30 s 且 record_id 与上次定标记录不同才收缩。）
- 冲突：D-117 已裁决：选 B（＝现状）：曲线最高点降到当前纵轴顶部约40%以下并持续30秒才收缩；“纵轴放大时最高点放在约62%高度”写进规格
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum

### UI-175 实时纵轴立即扩展
- 规则：实时光谱新数据所需纵轴上限大于当前量程时，立即扩大纵轴量程。
- 来源：业务规则与变更日志_V1.0.2.md 第 257 行「页面布局与显示（2026-09-19）」“实时纵轴立即扩展；数据低于当前量程65%并持续30秒、且有新记录后才收缩”
- 状态：待确认
- 现状符合度：符合（_plot_selected_spectrum(realtime=True)：proposed > state[1] 时直接以新量程重置 _overview_scale。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum

### UI-176 历史表默认约八条记录空间
- 规则：历史页表格默认提供约八条记录空间。
- 来源：业务规则与变更日志_V1.0.2.md 第 258 行「页面布局与显示（2026-09-19）」“表格默认提供约八条记录空间，可拖动表图分隔条”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history 纵向 QSplitter setSizes([310, 360])、行高28、表头≥46，约容纳8–9行）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-177 窄窗口历史表滚动保留完整列
- 规则：窗口较窄时历史表出现横向滚动条，保证完整采集时间和列标题不被截断或压缩。
- 来源：业务规则与变更日志_V1.0.2.md 第 258 行「页面布局与显示（2026-09-19）」“可拖动表图分隔条；窄窗口使用滚动条保留完整时间和列标题”
- 状态：待确认
- 现状符合度：符合（_align_history_table 以表头文字宽度及“2026-09-19 23:59:59.999”宽度计算列最小宽度，总和超过视口时切换为 ScrollBarAsNeeded。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_history_table

### UI-178 周期行显示完整起止与说明
- 规则：DLI周期单独一行居中显示，内容含完整起止日期时间、北京时间标注及“日出起算，固定24小时”。
- 来源：业务规则与变更日志_V1.0.2.md 第 264 行「光积累计算显示（2026-10-11 更新）」“周期另占一行居中，显示完整起止日期、北京时间及「日出起算，固定24小时」”
- 状态：待确认
- 现状符合度：符合（refresh_diagnostics 设置 dli_period_label 文本“积分周期：YYYY-mm-dd HH:MM → …（北京时间，日出起算，固定24小时）”，标签居中。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_diagnostics；par_app/ui.py MainWindow._build_diagnostics

### UI-179 DLI四图两列两行
- 规则：DLI页四个指标图按两列两行排列。
- 来源：业务规则与变更日志_V1.0.2.md 第 265 行「光积累计算显示（2026-10-11 更新）」“四图保持两列两行；图外左侧为指标名称、右侧为已累计值，窄时分行”
- 状态：待确认
- 现状符合度：符合（_build_diagnostics 将四个 DliCanvas 面板放入 dli_chart_grid 的 (index//2, index%2)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_diagnostics

### UI-180 DLI图外标题：左名称右累计值
- 规则：每个DLI图的图外标题区左侧显示指标名称、右侧显示已累计值；宽度不足时名称与累计值分两行。
- 来源：业务规则与变更日志_V1.0.2.md 第 265 行「光积累计算显示（2026-10-11 更新）」“四图保持两列两行；图外左侧为指标名称、右侧为已累计值，窄时分行”
- 状态：待确认
- 现状符合度：符合（_layout_dli_page 按 header_title+header_total 文字宽度判断 inline，否则分两行，累计值右对齐。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_dli_page；par_app/ui.py DliCanvas._update_header

### UI-181 DLI图头显示状态/时间/覆盖信息
- 规则：每个DLI图标题下方依次显示：状态；首个有效时间/累计截至时间；有效时长/未覆盖时长/覆盖率。
- 来源：业务规则与变更日志_V1.0.2.md 第 265 行「光积累计算显示（2026-10-11 更新）」“其下分别显示状态、首个有效时间/累计截至时间、有效时长/未覆盖时长/覆盖率”
- 状态：待确认
- 现状符合度：符合（DliCanvas._update_header 设置 header_state、header_times（首个有效/累计截至/可选最新有效）、header_coverage（有效/未覆盖/覆盖率）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._update_header

### UI-182 DLI页高度不足纵向滚动
- 规则：DLI页高度不足时页面整体纵向滚动，不得通过撑大主窗口来容纳内容（不改变菜单尺寸）。
- 来源：业务规则与变更日志_V1.0.2.md 第 265 行「光积累计算显示（2026-10-11 更新）」“高度不足时页面纵向滚动，不通过撑大窗口改变菜单尺寸”
- 状态：待确认
- 现状符合度：符合（_build_diagnostics 把整页放入 QScrollArea(widgetResizable=True)，图面板最小高度 210/236 由滚动区吸收。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_diagnostics

### UI-183 DLI横轴端点与零点完整标注
- 规则：DLI横轴两端显示完整月日/时分，周期内跨日零点也显示月日/时分；内部刻度间隔随图宽调整。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“横轴保留周期两端完整月日/时分与跨日零点，内部刻度随宽度疏密变化；零点紧邻端点时错行显示”
- 状态：待确认
- 现状符合度：符合（DliCanvas._layout_plot：端点和 midnight 用 '%m-%d\n%H:%M'，内部刻度宽≥700用3小时、否则6小时，且离端点<2小时的内部刻度省略。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._layout_plot

### UI-184 DLI纵轴从零开始
- 规则：DLI累计曲线纵轴下限固定为0。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“纵轴从零开始；不改变软件指标、采集通信、数据库结构或历史值”
- 状态：待确认
- 现状符合度：符合（plot_dli：axes.set_ylim(0, max(current*1.15, .001))。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas.plot_dli

### UI-185 零点紧邻端点时错行显示
- 规则：跨日零点标签与端点标签重叠时，零点标签错行（下移）显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 269 行「光积累计算显示（2026-10-11 更新）」“横轴保留周期两端完整月日/时分与跨日零点，内部刻度随宽度疏密变化；零点紧邻端点时错行显示”
- 状态：待确认
- 现状符合度：符合（_layout_plot 检测 midnight 标签与相邻标签 bbox 重叠时平移 −0.26 英寸并加大底边距。2.0 新界面（issue #108）：web/src/lib/dli.ts midnightStagger 按同样的外框（起点左对齐、终点右对齐、其余居中）先比左邻、再比右邻，重叠时零点标签下移 26 像素（STAGGER_PX），邻居是起点标签则左对齐、否则右对齐；DliChart.vue 用第二条无轴线 x 轴放这一行，底边距与图高同加 26 像素（V1.0.3 底边距 59→85、最小高度 210→236）；页面测试见 web/tests/dli.test.ts。国内经度下零点离端点至少约 4.5 小时，1100 像素以上窗口不触发；保存的经度远离东八区（如东经 174.76°、西经 135°）时触发。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py DliCanvas._layout_plot；web/src/lib/dli.ts midnightStagger；web/src/components/DliChart.vue midnightStagger

### UI-186 交换A/B不触发最近时间匹配
- 规则：点击交换A/B来源时，只互换两侧设备库与记录，不触发“B匹配A的最近时间”重新匹配。
- 来源：业务规则与变更日志_V1.0.2.md 第 275 行「光谱计算交互（2026-10-11 更新）」“保留四分区；交换不触发匹配，结果等待重新执行”
- 状态：待确认
- 现状符合度：符合（_swap_operation_sources 在 blockSignals 下设置库与记录，结束仅调用 show_operation_inputs，不调用 _operation_a_changed。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._swap_operation_sources

### UI-187 交换后结果作废待重新执行
- 规则：交换A/B后清除已有计算结果，需用户重新点击执行计算。
- 来源：业务规则与变更日志_V1.0.2.md 第 275 行「光谱计算交互（2026-10-11 更新）」“保留四分区；交换不触发匹配，结果等待重新执行”
- 状态：待确认
- 现状符合度：符合（_swap_operation_sources → show_operation_inputs → _invalidate_operation_result（current_result=None、导出按钮禁用）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_operation_inputs；par_app/ui.py MainWindow._invalidate_operation_result

### UI-188 计算页两行控件顺序
- 规则：光谱计算页第一行依次为：A设备库及记录、交换按钮、B设备库及记录；第二行依次为：最近时间匹配、算法、采集时间差、执行计算、导出计算结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 275 行「光谱计算交互（2026-10-11 更新）」“第一行选择A设备库及记录、交换、B设备库及记录；第二行依次为最近时间匹配、算法、采集时间差、执行计算、导出计算结果”
- 状态：待确认
- 现状符合度：符合（_update_operation_toolbar_layout 宽模式 rows=((A组, 交换, B组), (operation_options[匹配,算法,算法框], operation_actions[时间差, 执行, 导出]))。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_operation_toolbar_layout；par_app/ui.py MainWindow._build_operations

### UI-189 计算页保留四分区
- 规则：光谱计算页保留A图、B图、计算结果图、应用说明四个分区。
- 来源：业务规则与变更日志_V1.0.2.md 第 275 行「光谱计算交互（2026-10-11 更新）」“保留四分区；交换不触发匹配，结果等待重新执行”
- 状态：待确认
- 现状符合度：符合（_build_operations：上方 A/B 两图水平分割，下方结果图与 OperationGuideCanvas 水平分割。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-190 计算页控件宽度不足时拆行
- 规则：计算页控件按实际宽度居中排列；窗口宽度不足时拆成多行，而不是压缩控件。
- 来源：业务规则与变更日志_V1.0.2.md 第 275 行「光谱计算交互（2026-10-11 更新）」“导出计算结果。按控件实际宽度居中排列，宽度不足时拆行”
- 状态：待确认
- 现状符合度：符合（_update_operation_toolbar_layout 按 minimumSizeHint 求 needed_width，不足时切换为四行 compact 模式，各行两侧 stretch 居中。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_operation_toolbar_layout

### UI-191 其他页不随计算页刻度调整
- 规则：计算页的波段与刻度调整不影响实时、历史和光积累计算页。
- 来源：业务规则与变更日志_V1.0.2.md 第 277 行「光谱计算交互（2026-10-11 更新）」“避免标签重叠。实时、历史和光积累计算页不随此调整”
- 状态：待确认
- 现状符合度：符合（实时/历史刻度由 _plot_selected_spectrum 独立设置 (350,400,…,1000,1050)；DLI 横轴为时间轴，由 DliCanvas._layout_plot 设置。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum；par_app/ui.py DliCanvas._layout_plot

### UI-192 窄图省略400与1000刻度
- 规则：计算页图宽较窄时省略紧邻端点的400、1000刻度，避免与端点标签重叠。
- 来源：业务规则与变更日志_V1.0.2.md 第 277 行「光谱计算交互（2026-10-11 更新）」“A、B及结果曲线均标注350和1050端点；窄图省略紧邻端点的400、1000刻度，避免标签重叠”
- 状态：待确认
- 现状符合度：符合（_layout_operation_charts：chart.width() < 680 时刻度为 (350,500,…,900,1050)。阈值680像素仅存在于代码。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_operation_charts

### UI-193 计算页三图标注350/1050端点
- 规则：A、B及计算结果三图横轴均标注350与1050两个端点刻度。
- 来源：业务规则与变更日志_V1.0.2.md 第 277 行「光谱计算交互（2026-10-11 更新）」“A、B及结果曲线均标注350和1050端点；窄图省略紧邻端点的400、1000刻度，避免标签重叠”
- 状态：待确认
- 现状符合度：符合（_layout_operation_charts 两套刻度均含 350 与 1050。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_operation_charts

### UI-194 计算页固定350–1050nm无波段选择
- 规则：光谱计算页固定按350–1050 nm显示，不提供可见的波段选择控件。
- 来源：业务规则与变更日志_V1.0.2.md 第 277 行「光谱计算交互（2026-10-11 更新）」“计算页固定显示350–1050nm，移除可见波段选择”
- 状态：待确认
- 现状符合度：符合（_build_operations 中 operation_range 只有“350–1050 nm”一项且 hide()；_layout_operation_charts 固定 set_xlim(350, 1050)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations；par_app/ui.py MainWindow._layout_operation_charts

### UI-195 B匹配A最近时间默认开启
- 规则：“B 匹配 A 的最近时间”选项默认处于开启状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“「B 匹配 A 的最近时间」默认开启：首次进入、主动修改A或修改B设备时”
- 状态：待确认
- 现状符合度：符合（_build_operations：operation_auto_match.setChecked(True)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-196 匹配不修改设备时钟
- 规则：最近时间匹配不修改设备时钟。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“兼容旧UTC时间与北京时间，不修改设备时钟，不设置隐含容差”
- 状态：待确认
- 现状符合度：符合（MainWindow._operation_a_changed 只调用 ParDatabase.nearest_operation_spectrum，后者为只读 SQL，不调用协议层或对时任务。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.nearest_operation_spectrum；par_app/ui.py MainWindow._operation_a_changed

### UI-197 匹配兼容旧UTC与北京时间
- 规则：时间匹配同时兼容带时区的旧UTC记录与无时区的北京时间记录，统一换算后比较。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“等距时先选较早时间，再按记录ID；兼容旧UTC时间与北京时间”
- 状态：待确认
- 现状符合度：符合（nearest_operation_spectrum 内 timestamp()：带 tzinfo 的按自身时区，无时区按 BEIJING_TZ。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.nearest_operation_spectrum

### UI-198 匹配搜索B全库成功完整701点
- 规则：最近时间匹配在当前B设备库全部记录中搜索采集成功且为完整701点的光谱，不受下拉框只列最近500条的限制。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“在当前B库搜索与A时间最近的成功完整701点光谱，不限于下拉框最近500条”
- 状态：待确认
- 现状符合度：符合（ParDatabase.nearest_operation_spectrum：success=1、json_array_length=701，无 LIMIT 候选限制；下拉框 operation_spectra 才限 500；匹配结果不在下拉框时由 _select_operation_record 追加。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.nearest_operation_spectrum；par_app/ui.py MainWindow._select_operation_record

### UI-199 最近时间匹配非同步采集
- 规则：最近时间匹配仅从历史记录中挑选，不触发或等同于同步采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“不设置隐含容差。此功能是历史记录匹配，不是同步采集”
- 状态：待确认
- 现状符合度：符合（_operation_a_changed 只查询数据库；复选框悬停提示“最近不代表同步”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed

### UI-200 等距先选较早时间再按ID
- 规则：与A时间差相等时先选较早时间，再按记录ID。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“等距时先选较早时间，再按记录ID；兼容旧UTC时间与北京时间”
- 状态：待确认
- 现状符合度：符合（ParDatabase.nearest_operation_spectrum ORDER BY ABS(差), operation_timestamp(acquired_at), a.id。原文未规定 ID 排序方向，现状按 SQL 默认升序取较小 ID，属代码现状。）
- 冲突：D-151 已裁决：时间差和采集时间都相同时取记录 ID 较小者
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.nearest_operation_spectrum

### UI-201 首次进入/改A/改B设备时匹配
- 规则：跟随开启时，首次进入计算页、用户主动修改A（设备库或记录）、或修改B设备库时，自动为B选择与A时间最近的记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“「B 匹配 A 的最近时间」默认开启：首次进入、主动修改A或修改B设备时”
- 状态：待确认
- 现状符合度：符合（_rebuild_operation_databases 初次构建及 _on_tab_changed 首次进入调用 _operation_a_changed；a_combo 变化、A/B 库变化（_operation_database_changed）均调用 _operation_a_changed。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed；par_app/ui.py MainWindow._operation_database_changed；par_app/ui.py MainWindow._on_tab_changed

### UI-202 下次主动修改A重新匹配
- 规则：手动选B后，下一次用户主动修改A时（跟随开启）重新为B匹配最近时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“手动选择B不改变A，后台刷新保留手动B及已选旧记录；下一次主动修改A重新匹配”
- 状态：待确认
- 现状符合度：符合（a_combo 变化 → _operation_a_changed，跟随开启即调用 nearest_operation_spectrum 覆盖B。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed

### UI-203 关闭跟随独立选择、重开即匹配
- 规则：关闭“B匹配A”后A、B独立选择；重新开启时立即执行一次匹配。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“关闭跟随后独立选择，重新开启立即匹配。无候选显示「无可用光谱」”
- 状态：待确认
- 现状符合度：符合（operation_auto_match.toggled → _operation_a_changed，未勾选时不改B，勾选时立即匹配。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_a_changed

### UI-204 后台刷新保留手动B与旧记录
- 规则：后台定时刷新记录列表时保留用户手动选定的B，以及已选中但已不在最近500条中的旧记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“手动选择B不改变A，后台刷新保留手动B及已选旧记录；下一次主动修改A重新匹配”
- 状态：待确认
- 现状符合度：符合（refresh_operation_choices → _refresh_operation_records：previous 仍有效时经 _select_operation_record 保留（不在列表则追加）；信号被屏蔽，不触发匹配。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_operation_choices；par_app/ui.py MainWindow._refresh_operation_records

### UI-205 手动选择B不改变A
- 规则：用户手动选择B记录时不改变A的选择。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“手动选择B不改变A，后台刷新保留手动B及已选旧记录；下一次主动修改A重新匹配”
- 状态：待确认
- 现状符合度：符合（b_combo.currentIndexChanged 仅连接 show_operation_inputs。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations；par_app/ui.py MainWindow.show_operation_inputs

### UI-206 提示最近记录不代表同时采集
- 规则：界面需表明最近时间记录不代表同时采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“秒」，不重复下拉框已有时间；最近记录不代表同时采集”
- 状态：待确认
- 现状符合度：符合（operation_time_label 悬停提示“最近时间匹配不是同步采集…”；复选框提示及说明面板同样说明。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-207 无候选时显示无可用光谱
- 规则：匹配或列表中没有可用候选记录时，记录框显示“无可用光谱”。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“关闭跟随后独立选择，重新开启立即匹配。无候选显示「无可用光谱」”
- 状态：待确认
- 现状符合度：符合（_select_operation_record 无结果时清空并添加“无可用光谱”且禁用；_refresh_operation_records 无记录时同样处理。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._select_operation_record；par_app/ui.py MainWindow._refresh_operation_records

### UI-208 突出显示采集时间差
- 规则：选择区下方突出显示“采集时间差：B 比 A 早/晚 … 秒”，不重复下拉框中已有的时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 279 行「光谱计算交互（2026-10-11 更新）」“选择区下方突出「采集时间差：B 比 A 早/晚 ... 秒」，不重复下拉框已有时间”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 设置 operation_time_label 为“采集时间差：B 比 A 晚/早 x.xxx 秒”（相同时为“A 与 B 相同”，不可算为“不可用”），11pt 加粗。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts；par_app/ui.py MainWindow._operation_time_difference

### UI-209 A/B图共用完整波段纵轴
- 规则：A、B两图按350–1050 nm完整波段数据取共同的纵轴范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“A/B按完整波段使用相同纵轴范围，结果图独立缩放，不归一化原数据”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：输入均有效时取两图 ylim 的 min/max 统一设置。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-210 A/B有效时中央显示等待执行计算
- 规则：A、B均为有效光谱但尚未执行时，结果面板正中央显示“等待执行计算”。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“有效A/B已选时在面板正中央显示「等待执行计算」；输入缺失则显示「缺少有效的 A/B 光谱」”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 设 empty_heading=“等待执行计算”；_layout_operation_charts 将其定位到 figure (.5,.5)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts；par_app/ui.py MainWindow._layout_operation_charts

### UI-211 不归一化原始光谱
- 规则：A/B 光谱不归一化原数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“A/B按完整波段使用相同纵轴范围，结果图独立缩放，不归一化原数据”
- 状态：待确认
- 现状符合度：符合（MainWindow._operation_values 只做 points/10^spectral_coefficient 系数换算，无归一化；系数换算为代码现状，本条原文未规定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_values

### UI-212 待执行结果不显示纵轴刻度
- 规则：结果尚未执行时，结果图不显示无意义的纵轴刻度。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“待执行结果不显示无意义的纵轴刻度。低高度下收紧运算图标题与边距”
- 状态：待确认
- 现状符合度：符合（_invalidate_operation_result：set_yticks([])、清空纵轴标签；空图 axes.set_axis_off()。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._invalidate_operation_result；par_app/ui.py SpectrumCanvas.plot

### UI-213 未计算时结果标题为计算结果
- 规则：尚未执行计算时，结果图标题为“计算结果”。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“结果标题按左下整个面板水平居中；尚未计算时标题为「计算结果」”
- 状态：待确认
- 现状符合度：符合（_invalidate_operation_result 以标题“计算结果”绘制空图。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._invalidate_operation_result

### UI-214 结果图独立缩放
- 规则：计算结果图的纵轴独立于A/B图缩放。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“A/B按完整波段使用相同纵轴范围，结果图独立缩放，不归一化原数据”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 对 operation_result_chart 单独按结果有限值计算 limits。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-215 结果标题按面板水平居中
- 规则：计算结果图标题以左下整个面板（而非坐标框）水平居中。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“结果标题按左下整个面板水平居中；尚未计算时标题为「计算结果」”
- 状态：待确认
- 现状符合度：符合（_layout_operation_charts：title.set_x((.5-left)/(right-left))，即图面中心。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_operation_charts

### UI-216 输入缺失显示缺少有效A/B光谱
- 规则：A或B缺少有效光谱时，结果面板显示“缺少有效的 A/B 光谱”。
- 来源：业务规则与变更日志_V1.0.2.md 第 280 行「光谱计算交互（2026-10-11 更新）」“有效A/B已选时在面板正中央显示「等待执行计算」；输入缺失则显示「缺少有效的 A/B 光谱」”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：valid_inputs 为 False 时 empty_heading=“缺少有效的 A/B 光谱”，执行按钮禁用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-217 结果标题与图例用计算结果
- 规则：计算结果图的标题和图例名称采用“计算结果”。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“计算统一为A+B、A-B、A/B，标题和图例采用「计算结果」”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 以系列名“计算结果”、标题“计算结果：<算法>”绘制。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-218 低信号断开不补零不跨缺口
- 规则：未通过阈值的低信号点在比值曲线上断开，不补零，也不跨缺口连线。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“仅A>=T、B>=T且B非零的点绘制，低信号断开，不补零、不跨缺口连线”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：plotted = np.where(mask, out, nan)，NaN 处折线断开。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-219 无有效比值点时明确提示
- 规则：全零或当前显示波段内无满足阈值的比值点时，结果图明确提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“交换来源不改变筛选范围。全零或当前显示波段无有效点时明确提示”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：可见范围内无有限 plotted 值时在图中央写“无满足阈值的比值数据”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-220 1倍参考线不参与缩放
- 规则：比值图的1倍参考线只在1落入纵轴范围时显示，不参与纵轴范围计算。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“比值保留无填充折线，纵轴按可见有效值上下留白；1倍参考线只在纵轴范围内显示，不参与缩放”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 最终 limits 只由 plotted 有限值决定，随后 lines[1]（axhline 1）按 low≤1≤high 设可见。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-221 加减法零基线与半高峰值
- 规则：加减法结果纵轴包含零基线；结果全在零一侧时峰值约位于图高一半，跨零时上下留白。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“加减法保留零基线，单侧结果的峰值约在图高一半处，跨零结果上下留白”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：low==0 → (0, 2h)；high==0 → (2l, 0)；跨零 → 各加25%跨度留白。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-222 比值纵轴按可见有效值留白
- 规则：比值图纵轴范围按可见的有效比值上下加留白确定。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“比值保留无填充折线，纵轴按可见有效值上下留白；1倍参考线只在纵轴范围内显示，不参与缩放”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts：divide 时 padding=max(25%跨度, 10%幅值)，下限不低于0。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts

### UI-223 比值结果为无填充折线
- 规则：比值结果以无填充的折线绘制。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“比值保留无填充折线，纵轴按可见有效值上下留白；1倍参考线只在纵轴范围内显示，不参与缩放”
- 状态：待确认
- 现状符合度：符合（SpectrumCanvas.plot(ratio=True) 直接 axes.plot 折线，不走彩色填充。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SpectrumCanvas.plot

### UI-224 1680×900窗口完整显示摘要
- 规则：1680×900窗口下说明摘要完整显示、无需滚动。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“1680×900窗口完整显示摘要，空间不足时独立纵向滚动，不反向撑高窗口”
- 状态：待确认
- 现状符合度：未验证（需在 Windows 1680×900 实测；原文第61行记录光谱运算页窗口高度断言“期望900、实际979”失败，审计 test-multidevice 在 macOS 未复现。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py MainWindow._layout_operation_charts

### UI-225 切换结果状态时说明位置稳定
- 规则：结果在等待、加减、比值之间切换时，说明面板的标题、正文和按钮位置保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“等待、加减及比值之间切换时标题、正文和按钮位置稳定”
- 状态：待确认
- 现状符合度：符合（align_to_charts 几何不依赖结果图内容；未做 Windows 截图核对。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.align_to_charts

### UI-226 摘要四段行内加粗标题
- 规则：说明摘要以行内加粗标题组织为四段：补光组合、补光增量、温室综合透光评估、叶片光谱透射比较。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“以行内加粗标题组织补光组合、补光增量、温室综合透光评估、叶片光谱透射比较四段”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.__init__ 的 summary HTML 含四个 <p><b>…</b>：补光组合/补光增量/温室综合透光评估/叶片光谱透射比较。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__

### UI-227 摘要空间不足独立滚动不撑窗
- 规则：说明摘要空间不足时在面板内独立纵向滚动，不反向撑高主窗口。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“1680×900窗口完整显示摘要，空间不足时独立纵向滚动，不反向撑高窗口”
- 状态：待确认
- 现状符合度：符合（summary 为 QTextBrowser（自带纵向滚动，水平滚动关闭），OperationGuideCanvas 尺寸策略为 Ignored/Preferred，frame 几何由 align_to_charts 手动设定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py OperationGuideCanvas.align_to_charts

### UI-228 说明面板与B图左右对齐、高度自定
- 规则：说明面板左右边界与B绘图区对齐；上下范围由说明面板自身高度决定，不随结果图纵轴边距变化。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“左右仍与B绘图区对齐；上下改由说明面板自身高度决定，不再随结果图纵轴边距改变”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.align_to_charts 以 upper(=B图) axes 的 x0/x1 定左右，top=标题高+12、bottom=自身高−16，不读取 result 图。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.align_to_charts；par_app/ui.py MainWindow._align_operation_guide

### UI-229 页面与弹窗统一标题
- 规则：光谱计算页说明面板与完整说明弹窗的标题统一为“光谱计算应用说明”。
- 来源：业务规则与变更日志_V1.0.2.md 第 287 行「光谱计算交互（2026-10-11 更新）」“页面与弹窗统一标题「光谱计算应用说明」。右下正文控件及容器均无边框”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.__init__ 标题 QLabel 与 show_details 的 setWindowTitle 均为“光谱计算应用说明”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py OperationGuideCanvas.show_details

### UI-230 完整说明保留外部参考链接
- 规则：完整说明正文保留可点击打开的外部参考链接。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“支持补光/温室/叶片/显示与导出四个章节跳转；正文11磅并保留外部参考链接”
- 状态：待确认
- 现状符合度：符合（show_details：scroll.setOpenExternalLinks(True)，正文含四个 rp-photonics 链接。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-231 完整说明四章节跳转
- 规则：完整说明弹窗提供补光、温室、叶片、显示与导出四个章节的跳转链接。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“支持补光/温室/叶片/显示与导出四个章节跳转；正文11磅并保留外部参考链接”
- 状态：待确认
- 现状符合度：符合（show_details 顶部导航 QLabel 四个锚点 lighting/greenhouse/leaf/display，linkActivated → scrollToAnchor。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-232 完整说明弹窗960×760且≤屏幕90%
- 规则：完整说明弹窗默认960×760逻辑像素，且不超过当前屏幕可用宽、高的90%。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“完整说明弹窗默认960×760逻辑像素，上限为当前屏幕可用宽高的90%”
- 状态：待确认
- 现状符合度：符合（show_details：dialog.resize(min(960, avail.w*.9), min(760, avail.h*.9))。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-233 计算导出格式弹窗无问号
- 规则：计算结果导出格式弹窗不显示右上角上下文帮助问号。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“正文11磅并保留外部参考链接。计算导出格式弹窗移除无用途的右上角问号”
- 状态：待确认
- 现状符合度：符合（export_operation_results：dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results

### UI-234 说明/格式弹窗不改变计算选择
- 规则：完整说明弹窗和计算导出格式弹窗不改变计算选择。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“均不改变计算选择、结果快照或原有导出取消/失败处理”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.show_details 只展示文本；MainWindow.export_operation_results 不修改 A/B 下拉或算法选择。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details；par_app/ui.py MainWindow.export_operation_results

### UI-235 不把单点等同全温室平均
- 规则：说明中不得把单点比值等同于全温室平均透光。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“不把一天太阳轨迹称为材料球面/半球透过率，不把单点等同全温室平均”
- 状态：待确认
- 现状符合度：符合（show_details：“单点不代表全温室平均”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-236 不称太阳轨迹为球面/半球透过率
- 规则：说明中不得把一天太阳轨迹下的测量称为材料球面或半球透过率。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“不把一天太阳轨迹称为材料球面/半球透过率，不把单点等同全温室平均”
- 状态：待确认
- 现状符合度：符合（show_details：“不将它命名为材料的球面或半球透过率。一天只覆盖当天太阳轨迹…”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-237 全天累计比值须另行统计
- 规则：全天累计比值须另行统计。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“全天累计比值须另行统计，本页不自动生成方向分布图或空间平均”
- 状态：待确认
- 现状符合度：符合（光谱计算页只计算所选 A/B 两条记录，无全天累计比值功能；OperationGuideCanvas.show_details 说明文字中“累计光量之比”的定义为代码文案，原文未规定。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details；par_app/ui.py MainWindow._build_operations

### UI-238 完整说明按来源/用途/条件/边界组织
- 规则：完整说明各案例按来源、用途、测量条件和解释边界组织内容。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“完整说明按来源、用途、测量条件和解释边界组织”
- 状态：待确认
- 现状符合度：符合（show_details 各章节使用“来源与用途/条件与限制/测量布置/结果边界”等加粗小标题。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-239 本页不生成方向分布或空间平均
- 规则：光谱计算页不自动生成太阳方向分布图或空间平均结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“全天累计比值须另行统计，本页不自动生成方向分布图或空间平均”
- 状态：待确认
- 现状符合度：符合（_build_operations 无此类功能；show_details 明示“不由本页自动生成”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations；par_app/ui.py OperationGuideCanvas.show_details

### UI-240 温室案例强调角度天气等因素
- 规则：温室案例需强调太阳高度角/方位角、直射散射及天气、设备响应差异、时间错配、多点代表性。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“温室案例将覆盖物、骨架和遮阳设施作为综合影响，强调太阳高度角/方位角、直射散射及天气、响应差异、时间错配、多点代表性”
- 状态：待确认
- 现状符合度：符合（show_details 温室章节均有对应表述（太阳高度角、方位角、直射与散射、天气、逐波长响应差异、时间错配、多个代表性测点）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-241 温室案例按综合影响解释
- 规则：温室案例把覆盖物、骨架和遮阳设施的作用作为综合影响来说明。
- 来源：业务规则与变更日志_V1.0.2.md 第 289 行「光谱计算交互（2026-10-11 更新）」“温室案例将覆盖物、骨架和遮阳设施作为综合影响，强调太阳高度角/方位角、直射散射及天气、响应差异、时间错配、多点代表性”
- 状态：待确认
- 现状符合度：符合（show_details 温室章节：“覆盖材料、骨架、遮阳设施的共同作用”“温室综合透光评估”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-242 叶片案例A覆盖B同夹具空白
- 规则：叶片案例采用贴近接收口的固定夹具：A为叶片覆盖接收口时的光谱，B为同一夹具未放叶片的空白参考。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“叶片案例采用贴近接收口的固定夹具，A为叶片覆盖、B为同夹具空白”
- 状态：待确认
- 现状符合度：符合（show_details 叶片章节“A 为叶片贴近并覆盖接收口时的光谱，B 为同一光源、同一夹具未放叶片时的空白参考”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-243 叶片案例六项测量提醒
- 规则：叶片案例须提醒：防漏光、固定受光面与间距、避免夹伤、检查暗信号、复测参考、多点重复。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“提醒防漏光、固定受光面/间距、避免夹伤、暗信号检查、复测参考和多点重复”
- 状态：待确认
- 现状符合度：符合（show_details“夹具与重复测量”段落覆盖六项。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-244 接收几何透射比≠总半球透过率
- 规则：说明须指出固定接收几何下的透射比不等于总半球透过率。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“接收几何下的透射比不等于总半球透过率；缺少反射测量不能将1−A/B当作吸收率”
- 状态：待确认
- 现状符合度：符合（show_details“散射与接收范围”段：“不直接等同于总半球透过率”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-245 无反射测量不得以1−A/B为吸收率
- 规则：说明须指出缺少反射测量时不能把1−A/B当作吸收率。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“接收几何下的透射比不等于总半球透过率；缺少反射测量不能将1−A/B当作吸收率”
- 状态：待确认
- 现状符合度：符合（show_details“透射不等于吸收”段。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-246 摘要和弹窗提醒导出保留值≠测量可靠
- 规则：摘要和弹窗均提醒可能隐藏真实低透射区：导出保留数值不等于测量可靠。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“摘要和弹窗均提醒可能隐藏真实低透射区：曲线空缺不代表零透射或完全吸收，导出保留数值不等于测量可靠”
- 状态：待确认
- 现状符合度：符合（按 D-118 裁决，三点提醒只要求在弹窗写全：弹窗 OperationGuideCanvas.show_details 含“导出保留数值不意味着该数值具备测量可信度”；摘要 OperationGuideCanvas.__init__ 无此句，按裁决不要求。）
- 冲突：D-118 已裁决：三点提醒只要求在弹窗写全，摘要保留“可能隐藏低透射区、空缺不代表零透射”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py OperationGuideCanvas.show_details

### UI-247 摘要和弹窗提醒空缺≠零透射或完全吸收
- 规则：摘要和弹窗均提醒可能隐藏真实低透射区：曲线空缺不代表零透射或完全吸收。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“摘要和弹窗均提醒可能隐藏真实低透射区：曲线空缺不代表零透射或完全吸收，导出保留数值不等于测量可靠”
- 状态：待确认
- 现状符合度：符合（按 D-118 裁决，三点提醒只要求在弹窗写全，摘要保留“可能隐藏低透射区、空缺不代表零透射”：弹窗 OperationGuideCanvas.show_details 含“曲线空缺不代表零透射，也不代表完全吸收”；摘要 OperationGuideCanvas.__init__ 含“空缺不代表零透射”，不含“完全吸收”，按裁决不要求。）
- 冲突：D-118 已裁决：三点提醒只要求在弹窗写全，摘要保留“可能隐藏低透射区、空缺不代表零透射”
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py OperationGuideCanvas.show_details

### UI-248 摘要与弹窗提醒可能隐藏低透射区
- 规则：说明摘要和完整说明弹窗都需提醒2%筛选可能隐藏真实的低透射区。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“2%显示筛选保持不变，摘要和弹窗均提醒可能隐藏真实低透射区”
- 状态：待确认
- 现状符合度：符合（摘要：“2% 筛选可能隐藏低透射区”；弹窗：“2%筛选可能隐藏真实的低透射区”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.__init__；par_app/ui.py OperationGuideCanvas.show_details

### UI-249 案例为应用建议非标准方法
- 规则：说明须注明案例是应用建议，不作为标准方法认证。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“的光学定义与原理；案例是应用建议，不作为标准方法认证”
- 状态：待确认
- 现状符合度：符合（show_details：“温室与夹具案例为应用建议，不作为标准方法认证”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-250 附四个光学定义参考链接
- 规则：完整说明附透过率、积分球、吸收率、吸光度四个光学定义参考链接。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“参考[透过率](https://www.rp-photonics.com/transmittance.html)”
- 状态：待确认
- 现状符合度：符合（show_details“参考资料”含 transmittance/integrating_spheres/absorptance/absorbance 四个链接。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details

### UI-251 光谱计算回归仅用临时库
- 规则：verify_operations() 用临时数据库验证：超过500条的匹配、残缺/失败记录排除、同号跨库、混合时区、手动选择、交换、全波段端点、多尺寸布局、NaN及两种格式导出；不访问在线硬件或正式数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 292 行「光谱计算交互（2026-10-11 更新）」“verify_multidevice.py的verify_operations()使用临时数据库验证超过500条的匹配”
- 状态：待确认
- 现状符合度：未验证（函数存在（verify_multidevice.py:97），但 main() 不调用它，完整回归不覆盖 verify_operation_export_layout（审计 test-multidevice、critic）；单独运行时在 macOS offscreen 下于帮助弹窗几何断言失败（#7，环境原因）。未在 Windows 上运行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：verify_multidevice.py verify_operations；verify_multidevice.py main

### UI-252 异常详情独立显示且正常时隐藏
- 规则：设备异常的详细信息显示在公共栏下方的独立区域，没有异常时隐藏该区域。
- 来源：业务规则与变更日志_V1.0.2.md 第 311 行「公共设备状态栏（2026-09-17）」“异常详细信息仍在下方独立区域，正常时隐藏。”
- 状态：待确认
- 现状符合度：符合（MainWindow._refresh_communication_events 汇总启用设备的失败行写入 communication_events_label，无失败时 setVisible(False)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-253 顶部公共栏合并查看设备、总线和采集状态
- 规则：顶部公共栏合并显示查看设备选择、总线状态和采集状态；正常宽度时放在同一行，窄窗口时分两行。
- 来源：业务规则与变更日志_V1.0.2.md 第 311 行「公共设备状态栏（2026-09-17）」“顶部合并「查看设备」、总线状态和采集状态，正常宽度同一行，窄窗口分两行。”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_device_bar 把 device_selector 与 bus_status_label/acquisition_state_label 放入同一 device_bar；_update_device_bar_layout 在宽度小于 max(1180, 所需宽度) 时改为两行。标签文字现为“当前显示设备：”（第50行）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_device_bar；par_app/ui.py MainWindow._update_device_bar_layout

### UI-254 光谱计算 A/B 数据库选择独立于公共选择
- 规则：光谱计算页的 A/B 数据库选择独立于公共查看设备，切换查看设备不改变 A/B 来源。
- 来源：业务规则与变更日志_V1.0.2.md 第 312 行「公共设备状态栏（2026-09-17）」“P3运算、P6设置隐藏公共选择，但保留总线和采集状态；P3的A/B数据库选择独立。”
- 状态：待确认
- 现状符合度：符合（MainWindow._bind_active_device 不修改 a_database_combo/b_database_combo；A/B 只在 _rebuild_operation_databases、_operation_database_changed 中由用户选择或配置变化更新。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow._rebuild_operation_databases

### UI-255 公共设备选择为四位置单选
- 规则：实时、历史、DLI 等页面共用一个四位置的设备单选（对应最多4台登记设备）。原文所列 P4 校准已迁入维护弹窗（第131行）。
- 来源：业务规则与变更日志_V1.0.2.md 第 312 行「公共设备状态栏（2026-09-17）」“P1实时、P2历史、P4校准、P5 DLI共用四位置单选，跨页保持当前设备；”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_device_bar 按 MAX_DEVICES=4 生成 QRadioButton；_update_device_bar_layout 只在光谱计算和设置与导出页隐藏选择器。）
- 冲突：D-137 已裁决：“当前设备”即维护弹窗所选设备，读取前提原样适用；第312行“P4 参与公共单选”随 P4 迁入维护弹窗作废
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_device_bar；par_app/models.py MAX_DEVICES；par_app/ui.py MainWindow._update_device_bar_layout

### UI-256 当前查看设备跨页保持
- 规则：公共设备选择在各页之间共享，切换页面不改变当前查看设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 312 行「公共设备状态栏（2026-09-17）」“P1实时、P2历史、P4校准、P5 DLI共用四位置单选，跨页保持当前设备；”
- 状态：待确认
- 现状符合度：符合（当前设备保存在 DeviceHub.active_key，MainWindow._on_tab_changed 不修改它。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub.set_active；par_app/ui.py MainWindow._on_tab_changed

### UI-257 查看设备选择不改变后台采集范围
- 规则：选择查看设备只改变界面查看对象，不改变后台采集的设备范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 312 行「公共设备状态栏（2026-09-17）」“选择只改变查看对象，不改变后台采集范围。”
- 状态：待确认
- 现状符合度：符合（DeviceHub.set_active 只改 active_key 并发 active_changed；PollingCoordinator._poll_all_devices 按登记启用设备轮询，与 active_key 无关。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub.set_active；par_app/coordinator.py PollingCoordinator._poll_all_devices

### UI-258 计算页和设置页隐藏设备选择但保留状态
- 规则：光谱计算页和设置页隐藏公共设备选择，但仍显示总线状态和采集状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 312 行「公共设备状态栏（2026-09-17）」“P3运算、P6设置隐藏公共选择，但保留总线和采集状态；P3的A/B数据库选择独立。”
- 状态：待确认
- 现状符合度：符合（MainWindow._update_device_bar_layout：show_selector 在 operation_tab_index/settings_tab_index 时为假，device_status_box 始终显示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._update_device_bar_layout

### UI-259 停用设备灰色标注“停用”且可查看
- 规则：停用设备灰色并标注“停用”，允许查看已有数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 313 行「公共设备状态栏（2026-09-17）」“停用设备灰色并标注「停用」，允许查看已有数据”
- 状态：待确认
- 现状符合度：不符合（按 D-152 裁决需修改，待修复。按裁决，停用期间须显示灰色并标“停用”，不清除故障或退出状态；现状 MainWindow._style_device_buttons 故障判断优先，显示红色。原核对（未验证）：MainWindow._style_device_buttons：未启用时文字追加“（停用）”、按钮仍可用；颜色 text_color = 红 if faulty else (黑 if enabled else 灰)，故障判断优先。设备故障后再停用、MainWindow._device_is_faulty 仍因旧快照 failures/excluded 为真时显示红色而非灰色。同行“故障红色”与“停用灰色”的交叉优先级原文未规定。）
- 冲突：D-152 已裁决：停用期间显示灰色并标“停用”（停用优先），不清除故障或退出状态，重新启用后照常显示，待修复（DEF-20）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons；par_app/ui.py MainWindow._device_is_faulty

### UI-260 故障设备红色、仍可查看且不自动跳转
- 规则：故障设备在设备选择中显示为红色，仍可被选为查看对象；设备故障时界面不自动切换到其他设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 313 行「公共设备状态栏（2026-09-17）」“故障红色仍可查看，不自动跳到其他设备；停用设备灰色并标注「停用」，允许查看已有数据。”
- 状态：待确认
- 现状符合度：符合（MainWindow._style_device_buttons：_device_is_faulty 为真时颜色 #dc2626，button.setEnabled(device is not None)；_on_device_state_changed 只刷新样式，不调用 set_active。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons；par_app/ui.py MainWindow._device_is_faulty；par_app/ui.py MainWindow._on_device_state_changed

### UI-261 未配置位置灰色且不可选
- 规则：未登记设备的位置显示为灰色“未配置”，不可选择。
- 来源：业务规则与变更日志_V1.0.2.md 第 313 行「公共设备状态栏（2026-09-17）」“正常设备黑色；未配置灰色禁选；故障红色仍可查看，不自动跳到其他设备；”
- 状态：待确认
- 现状符合度：符合（MainWindow._style_device_buttons：index >= len(keys) 时文字“未配置”、setEnabled(False)、颜色 #9ca3af。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons

### UI-262 正常设备在设备选择中显示为黑色
- 规则：设备选择中，正常（启用且无故障）的设备以黑色显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 313 行「公共设备状态栏（2026-09-17）」“正常设备黑色；未配置灰色禁选；故障红色仍可查看，不自动跳到其他设备；”
- 状态：待确认
- 现状符合度：符合（MainWindow._style_device_buttons：非故障且启用时 text_color='#111111'。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons

### UI-263 长设备名省略显示，悬停显示全名和地址
- 规则：设备名称过长时省略显示，鼠标悬停时显示完整名称和从站地址。
- 来源：业务规则与变更日志_V1.0.2.md 第 313 行「公共设备状态栏（2026-09-17）」“停用设备灰色并标注「停用」，允许查看已有数据。长名称省略显示，悬停显示全名和地址。”
- 状态：待确认
- 现状符合度：符合（MainWindow._style_device_buttons：按钮宽度上限180，elidedText(ElideRight) 省略；toolTip 为“全名（从站地址 N）· 状态：level”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._style_device_buttons

### UI-264 光谱计算页不设“参与运算的数据库”勾选区
- 规则：P3 取消“参与运算的数据库”勾选区。
- 来源：业务规则与变更日志_V1.0.2.md 第 321 行「导航与光谱来源选择（2026-09-17）」“P3取消「参与运算的数据库」勾选区，A/B各自一行「数据库 → 采集记录」”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py 中无“参与运算”文案；MainWindow._build_operations 只建 A/B 数据库下拉与记录下拉。）
- 冲突：无（同句的 A/B 布局另见 UI-295）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-265 计算页数据库下拉显示设备名，悬停显示完整路径
- 规则：光谱计算页 A/B 数据库下拉以设备名称显示各数据库，悬停显示数据库完整路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 321 行「导航与光谱来源选择（2026-09-17）」“下方为运算法则与执行按钮。数据库显示设备名称，悬停显示完整路径。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_operation_databases 用 addItem(设备名, 路径) 并设 ToolTipRole=路径，下拉 toolTip 为当前路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_operation_databases；par_app/ui.py MainWindow._refresh_operation_records

### UI-266 切换计算输入清除旧结果
- 规则：A/B 输入（数据库或记录）发生切换时，清除旧的计算结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 322 行「导航与光谱来源选择（2026-09-17）」“定时刷新保留仍存在的选中记录和计算结果，切换输入则清除旧结果。”
- 状态：待确认
- 现状符合度：符合（MainWindow.show_operation_inputs 调用 _invalidate_operation_result（current_result=None、禁用导出）；_operation_database_changed 与记录下拉变化都经此路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.show_operation_inputs；par_app/ui.py MainWindow._invalidate_operation_result；par_app/ui.py MainWindow._operation_database_changed

### UI-267 定时刷新保留仍存在的选中记录和计算结果
- 规则：定时刷新时，若 A/B 选中的记录仍存在，保留选中记录和已计算的结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 322 行「导航与光谱来源选择（2026-09-17）」“定时刷新保留仍存在的选中记录和计算结果，切换输入则清除旧结果。”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_operation_choices 重建记录列表后，只有 A/B 当前选择发生变化才调用 show_operation_inputs（会清除结果）；_refresh_operation_records 对仍存在的 previous 重新选中。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_operation_choices；par_app/ui.py MainWindow._refresh_operation_records

### UI-268 故障或停用设备的数据库仍可用于运算
- 规则：故障或停用设备的数据库仍列入光谱计算的 A/B 来源，可参与运算。
- 来源：业务规则与变更日志_V1.0.2.md 第 322 行「导航与光谱来源选择（2026-09-17）」“故障或停用设备的数据库仍可供运算；空库显示「无可用光谱」，禁止执行。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_operation_databases 遍历全部 hub.keys()，不按启用或故障过滤。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_operation_databases

### UI-269 空库显示“无可用光谱”并禁止执行计算
- 规则：A 或 B 所选数据库没有可用光谱时，记录下拉显示“无可用光谱”，禁止执行计算。
- 来源：业务规则与变更日志_V1.0.2.md 第 322 行「导航与光谱来源选择（2026-09-17）」“故障或停用设备的数据库仍可供运算；空库显示「无可用光谱」，禁止执行。”
- 状态：待确认
- 现状符合度：符合（MainWindow._refresh_operation_records 无记录时加入“无可用光谱”并禁用下拉；_redraw_operation_charts 在输入无效时 operation_run_button.setEnabled(False)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._refresh_operation_records；par_app/ui.py MainWindow._redraw_operation_charts

### UI-270 光谱来源选择的自动验证范围
- 规则：verify_multidevice.py 须覆盖：同库/跨库同号记录、A/B 单侧切换互相独立、空库禁用、导出来源、定时刷新保持，并生成1380/1000宽度的导航及光谱计算页截图；该验证不改变采集与硬件通信。
- 来源：业务规则与变更日志_V1.0.2.md 第 323 行「导航与光谱来源选择（2026-09-17）」“verify_multidevice.py覆盖同库/跨库同号记录、单侧切换独立、空库禁用、导出来源和定时刷新保持”
- 状态：待确认
- 现状符合度：未验证（誊抄时未运行测试。审计 test-multidevice.md：原脚本在第718行中止，绕过过时断言后才能跑完；verify_operations()（含导出布局检查）未被 main() 调用，完整回归不覆盖它。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：验证范围约束，对应测试脚本 verify_multidevice.py，不在 par_app 源码中

### UI-271 实时摘要切换列数时字号不缩小
- 规则：实时摘要在六列与三列之间切换时字号不缩小。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“可用内容宽度达到1500逻辑像素时单行六列，否则两行三列，字号不缩小”
- 状态：待确认
- 现状符合度：符合（MainWindow._align_overview_metrics 只改变列数与位置；KPI 卡片字号在 MainWindow._build_overview 固定为 10pt/14pt，不随列数变化）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_overview_metrics；par_app/ui.py MainWindow._build_overview

### UI-272 详情退回单列不改变列表或上下区域比例
- 规则：历史详情退回单列时不改变左侧列表或上下区域比例。
- 来源：业务规则与变更日志_V1.0.2.md 第 44 行「实时概览与历史回放（2026-10-11）」“空间不足自动退回单列，不改变左侧列表或上下区域比例”
- 状态：待确认
- 现状符合度：符合（MainWindow._layout_history_details 只重排详情分组，不修改 records_layout 的 2:3 stretch，也不调用历史 QSplitter.setSizes）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._layout_history_details；par_app/ui.py MainWindow._build_history

### UI-273 历史详情正文七组覆盖54项指标
- 规则：历史详情正文为七组，覆盖54项指标。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“删除底部重复的采集质量分组，正文七组覆盖54项指标”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history 的 groups 为常用光量8、波段光子通量6、光谱比例6、光色与峰值7、扩展波段光量5、特殊显色指数15、色度与三刺激值7，共七组54项）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-274 采集/曝光状态由左侧列表与光谱状态行显示
- 规则：采集/曝光状态由左侧列表与光谱状态行显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“采集/曝光状态由左侧列表与光谱状态行显示”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_history 在列表第4、5列填写采集结果与曝光状态；MainWindow.show_history_spectrum 的光谱状态行含采集状态与曝光）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/ui.py MainWindow.show_history_spectrum

### UI-275 历史记录区左侧约40%列表、右侧约60%详情
- 规则：历史记录区为左侧约40%的列表与右侧约60%的完整记录详情。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“历史记录区为左侧约40%的五列列表（序号、ID、采集时间、采集结果、曝光状态）与右侧约60%的完整记录详情”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history：records_layout 中表格 stretch 2、详情 stretch 3）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-276 历史光谱仍全宽显示
- 规则：历史记录区下方的光谱仍全宽显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 46 行「实时概览与历史回放（2026-10-11）」“与右侧约60%的完整记录详情，下方光谱仍全宽显示”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history：纵向 QSplitter 上部为记录区，下部为 history_chart 全宽）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-277 不调整实时图坐标框设置
- 规则：不调整实时图坐标框设置。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“不增加图内指标，不调整坐标框设置或四条参考曲线”
- 状态：待确认
- 现状符合度：未验证（本条是相对前一版本“不调整”的约束，缺少前一版本基线无法比对；现状坐标框由 MainWindow._plot_selected_spectrum 设置）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum

### UI-278 不调整实时图四条参考曲线
- 规则：不调整实时图四条参考曲线。
- 来源：业务规则与变更日志_V1.0.2.md 第 56 行「实时概览与历史回放（2026-10-11）」“不增加图内指标，不调整坐标框设置或四条参考曲线”
- 状态：待确认
- 现状符合度：未验证（本条是相对前一版本“不调整”的约束，缺少前一版本基线无法比对；现状实时图 fixed_response_overlays=True，MainWindow._plot_selected_spectrum 固定选四条曲线，SpectrumCanvas._draw_response_overlays 绘制）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._plot_selected_spectrum；par_app/ui.py SpectrumCanvas._draw_response_overlays

### UI-279 日志异常行标红
- 规则：设置页日志表异常行标红。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“日志类别中文显示，异常行标红，完整消息及详情放在悬停提示中”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_settings_console：level 为 ERROR/WARNING/CRITICAL 时前景 #b91c1c）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console

### UI-280 日志完整消息及详情放在悬停提示
- 规则：设置页日志的完整消息及详情放在悬停提示中。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“日志类别中文显示，异常行标红，完整消息及详情放在悬停提示中”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_settings_console：结果列 toolTip = message + details（details 非空且非 {} 时）；verify_configuration.py verify_settings_logs 断言）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_settings_console

### UI-281 数据库行不显示悬停提示
- 规则：设置页数据库行不显示悬停提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 70 行「设置与导出布局（2026-09-20）」“悬停状态可查看序列号，数据库行不显示悬停提示”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_database_summary 设置 database_summary_label.setToolTip("")；verify_configuration.py verify_settings_logs 断言数据库行提示为空）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_database_summary

### UI-282 诊断导出成功恢复普通文字颜色
- 规则：诊断导出成功后结果文字恢复普通颜色。
- 来源：业务规则与变更日志_V1.0.2.md 第 127 行「统一设备维护（2026-09-18，当前布局）」“失败原因与导出结果继续显示，导出成功恢复普通文字颜色”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.export_diagnostics 成功时调用 set_result(…)（error=False），DeviceMaintenanceDialog.set_result 设为 color:#000000）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.export_diagnostics；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.set_result

### UI-283 空间不足时校准信息移到参数下方且不缩字号或输入框
- 规则：空间不足时校准信息移到节点及全局参数下方，不缩小字号或输入框。
- 来源：业务规则与变更日志_V1.0.2.md 第 140 行「统一设备维护（2026-09-18，当前布局）」“空间不足时校准信息移到节点及全局参数下方，不缩小字号或输入框”
- 状态：待确认
- 现状符合度：符合（CalibrationDetailsPanel.arrange 在宽度 <1038 时把 information 放到参数区下方；该函数只设置几何位置，不修改字体或输入框尺寸；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 在宽度<1080 时断言 information.y 位于参数区下方）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py CalibrationDetailsPanel.arrange

### UI-284 低高度时校准页整页纵向滚动保证内容可达
- 规则：低高度时由整页纵向滚动保证校准内容可达。
- 来源：业务规则与变更日志_V1.0.2.md 第 140 行「统一设备维护（2026-09-18，当前布局）」“低高度由整页纵向滚动保证内容可达”
- 状态：待确认
- 现状符合度：符合（DeviceMaintenanceDialog.__init__ 以 QScrollArea 包裹校准页；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 在 740×580 断言纵向滚动条 maximum>0，滚到底后校准信息完整位于视口内）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__

### UI-285 默认1080×820窗口回读后校准页无横纵滚动条
- 规则：默认 1080×820 窗口正常回读后，校准页无横向和纵向滚动条。
- 来源：业务规则与变更日志_V1.0.2.md 第 140 行「统一设备维护（2026-09-18，当前布局）」“默认1080x820窗口正常回读后无横纵滚动条，缩窄后放宽可恢复三列”
- 状态：待确认
- 现状符合度：符合（verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 先模拟 calibration_read 回读，再在 1080×820 断言校准页 scroll 横、纵滚动条 maximum 均为 0 且纵向滚动条不可见）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py CalibrationDetailsPanel.arrange；par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.__init__

### UI-286 校准页缩窄后放宽可恢复三列
- 规则：校准页缩窄后再放宽，可恢复三列布局。
- 来源：业务规则与变更日志_V1.0.2.md 第 140 行「统一设备维护（2026-09-18，当前布局）」“默认1080x820窗口正常回读后无横纵滚动条，缩窄后放宽可恢复三列”
- 状态：待确认
- 现状符合度：符合（CalibrationDetailsPanel.resizeEvent 每次调用 arrange 按当前宽度重排；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 依次 1080→780→740→1080→1280，放宽回 ≥1080 时断言 information 与参数区同一行并排、间距16）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py CalibrationDetailsPanel.arrange；par_app/ui.py CalibrationDetailsPanel.resizeEvent

### UI-287 历史页表图分隔条可拖动
- 规则：历史页表格与光谱图之间的分隔条可拖动。
- 来源：业务规则与变更日志_V1.0.2.md 第 258 行「页面布局与显示（2026-09-19）」“表格默认提供约八条记录空间，可拖动表图分隔条”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_history 使用纵向 QSplitter 分隔表格与 history_chart，setChildrenCollapsible(False)，分隔条可拖动）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history

### UI-288 最近时间匹配不设置隐含容差
- 规则：最近时间匹配不设置隐含容差。
- 来源：业务规则与变更日志_V1.0.2.md 第 278 行「光谱计算交互（2026-10-11 更新）」“兼容旧UTC时间与北京时间，不修改设备时钟，不设置隐含容差”
- 状态：待确认
- 现状符合度：符合（ParDatabase.nearest_operation_spectrum 的 SQL 只按时间差排序取第一条，无时间窗口条件）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.nearest_operation_spectrum

### UI-289 说明/格式弹窗不改变结果快照
- 规则：完整说明弹窗和计算导出格式弹窗不改变结果快照。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“均不改变计算选择、结果快照或原有导出取消/失败处理”
- 状态：待确认
- 现状符合度：符合（OperationGuideCanvas.show_details 只展示文本；MainWindow.export_operation_results 开头读取 current_result 作为本次导出快照，弹窗期间不修改 current_result）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details；par_app/ui.py MainWindow.export_operation_results

### UI-290 格式弹窗不改变原有导出取消处理
- 规则：计算导出格式弹窗不改变原有导出取消处理。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“均不改变计算选择、结果快照或原有导出取消/失败处理”
- 状态：待确认
- 现状符合度：未验证（本条是相对原有处理“不改变”的约束，缺少改动前基线无法比对；现状 MainWindow.export_operation_results 在格式弹窗取消、未选格式或未选目录时直接返回，不写文件）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results

### UI-291 格式弹窗不改变原有导出失败处理
- 规则：计算导出格式弹窗不改变原有导出失败处理。
- 来源：业务规则与变更日志_V1.0.2.md 第 288 行「光谱计算交互（2026-10-11 更新）」“均不改变计算选择、结果快照或原有导出取消/失败处理”
- 状态：待确认
- 现状符合度：未验证（本条是相对原有处理“不改变”的约束，缺少改动前基线无法比对；现状 MainWindow.export_operation_results 捕获 OSError/ValueError 后弹出“导出失败”，列出保存目录与已完成文件）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/services/export.py export_operation_files

### UI-292 补绘下拉/上下三角保留原生点击区域
- 规则：补绘实心下拉三角和上下三角时保留原生点击区域。
- 来源：业务规则与变更日志_V1.0.2.md 第 77 行「设置与导出布局（2026-09-20）」“复用经纬度的绘制方式，保留原生点击区域、范围和步进”
- 状态：待确认
- 现状符合度：符合（SolidArrowComboBox 与 _SolidSpinArrows 只覆写 paintEvent，先调用原生 paintEvent 再叠加绘制，三角位置取自 style().subControlRect；未覆写鼠标事件或子控件区域）
- 冲突：无（设置页三个输入框的点击区域另见 UI-311，内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py SolidArrowComboBox.paintEvent；par_app/ui.py _SolidSpinArrows.paintEvent

### UI-293 补绘上下三角保留原有取值范围
- 规则：补绘上下三角时保留原有取值范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 77 行「设置与导出布局（2026-09-20）」“复用经纬度的绘制方式，保留原生点击区域、范围和步进”
- 状态：待确认
- 现状符合度：未验证（_SolidSpinArrows 不修改 range；现状构造处范围：轮询周期 MIN_POLL_CYCLE_SECONDS–MAX_POLL_CYCLE_SECONDS、从站地址 1–247、TCP端口 1–65535（MainWindow._build_settings）。缺少改动前基线，无法确认构造参数未变）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py _SolidSpinArrows.paintEvent；par_app/ui.py MainWindow._build_settings

### UI-294 补绘上下三角保留原有步进
- 规则：补绘上下三角时保留原有步进。
- 来源：业务规则与变更日志_V1.0.2.md 第 77 行「设置与导出布局（2026-09-20）」“复用经纬度的绘制方式，保留原生点击区域、范围和步进”
- 状态：待确认
- 现状符合度：未验证（_SolidSpinArrows 不修改 singleStep；MainWindow._build_settings 中轮询周期、从站地址、TCP端口均未调用 setSingleStep，沿用 Qt 默认步进1。缺少改动前基线，无法确认步进未变）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py _SolidSpinArrows.paintEvent；par_app/ui.py MainWindow._build_settings

### UI-295 P3 A/B各自一行“数据库 → 采集记录”，下方为运算法则与执行按钮
- 规则：光谱计算页 A/B 各自一行“数据库 → 采集记录”，下方为运算法则与执行按钮。
- 来源：业务规则与变更日志_V1.0.2.md 第 321 行「导航与光谱来源选择（2026-09-17）」“A/B各自一行「数据库 → 采集记录」，下方为运算法则与执行按钮”
- 状态：已废止 2026-10-17，由 UI-188 替代（D-153 裁决：第321行“A/B 各自一行、下方为运算法则与执行按钮”标为历史废止）
- 现状符合度：不符合（现状 MainWindow._build_operations 按第275行布局：第一行 A 设备库及记录、交换、B 设备库及记录，第二行最近时间匹配、算法、时间差、执行、导出；不是 A/B 各占一行。两条原文的取舍未经裁决。）
- 冲突：D-153 已裁决：第321行“A/B 各一行”布局已被第275行两行布局取代，标为历史废止；本条已废止，约束由 UI-188 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-296 曝光状态展示
- 规则：曝光状态只保存和展示；本条约束其中的展示：界面展示记录的曝光状态。（保存部分见 ACQ-004）
- 来源：业务规则与变更日志_V1.0.2.md 第 20 行「单次采集策略（2026-10-11）」“完整成功读取的新记录设置 `dli_eligible=1`，曝光状态只保存和展示；欠曝光不作为采集失败或警告”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_history 历史表第4列按 {0:正常,1:过曝光,2:欠曝光} 显示；MainWindow._update_overview_status 状态卡含“曝光：…”；MainWindow.refresh_settings_console 在 level==ok 时追加“曝光：…”；MainWindow.show_history_spectrum 详情含“曝光：…”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/ui.py MainWindow._update_overview_status；par_app/ui.py MainWindow.refresh_settings_console；par_app/ui.py MainWindow.show_history_spectrum

### UI-297 UI 读取数据库
- 规则：UI 读取数据库。（同句“通信由后台采集服务独占”见 ACQ-054，“数据永久保存于本地 SQLite”见 CONF-053）
- 来源：业务规则与变更日志_V1.0.2.md 第 338 行「产品边界」“数据永久保存于本地 SQLite；UI 读取数据库，通信由后台采集服务独占。”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_history 通过 self.database.recent_acquisitions(500, start, end) 从 ParDatabase 读取历史记录。另：界面还通过 coordinator 信号接收运行状态，并直接读取 hub.coordinator._maintenance 私有字段（_update_overview_status）。原文没有写“只读数据库”，因此这些不算违反本条，只作为现状记录。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_history；par_app/database.py ParDatabase.recent_acquisitions

### UI-298 未勾选失败停止时连续失败不进入红色采集停止中
- 规则：未勾选“失败停止”（默认）时，连续失败不进入红色“采集停止中”。
- 来源：业务规则与变更日志_V1.0.2.md 第 114 行「失败停止开关（2026-09-30）」“不勾选（默认）——连续失败只累加计数，不退出、不进入红色「采集停止中」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备连续失败时采集状态为琥珀色，不进入红色“采集停止中”。（V1.0.2 现状：原核对：普通失败路径下未勾选设备不会 excluded，MainWindow._refresh_communication_events 走琥珀色“采集运行中：等待设备响应”分支。但设备完全静默时 read_spectrum_transaction 抛 AcquisitionResumeError，PollingCoordinator._halt_acquisition 设 _halt_reason，界面因 halt_reason() 非空显示红色（#dc2626）“采集停止中：…所有设备的后台采集已停止”（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）；与 POLL-017 同源（第114行），誊抄阶段不合并
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._halt_acquisition

### UI-299 验收：默认状态断通信12轮显示第12次失败未启用失败停止
- 规则：验收：默认状态下断开设备通信12轮后，界面显示“连续第 12 次尝试失败…未启用失败停止”。
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“默认状态下断开设备通信 12 轮后，界面显示「连续第 12 次尝试失败…未启用失败停止」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。断通信12轮后异常区显示“连续第 12 次尝试失败…未启用失败停止”。（V1.0.2 现状：原核对：PollingCoordinator._mark_failed 未勾选时生成“连续第 N 次尝试失败：…（未启用失败停止，将继续按周期重试）”，由 _refresh_communication_events 显示在异常文字区（verify_polling.py PollingTests.test_failure_exit_switch_disabled_keeps_retrying 断言消息内容）。但物理断开通信时设备静默，首轮就进入“恢复未确认”全局锁停，消息被改写为锁停原因，到不了第12次（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._mark_failed

### UI-300 验收：默认状态断通信12轮采集状态为琥珀色等待设备响应
- 规则：验收：默认状态下断开设备通信12轮后，采集状态为琥珀色“采集运行中：等待设备响应”。
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“采集状态为琥珀色「采集运行中：等待设备响应」”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。断通信12轮后采集状态为琥珀色“采集运行中：等待设备响应”。（V1.0.2 现状：原核对：MainWindow._refresh_communication_events 在无 halt、非维护、不是全部 excluded、且无设备 online 时，显示 #b45309“采集运行中：等待设备响应”。但设备静默时首轮全局锁停，改为红色停止文案（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events

### UI-301 验收：默认状态断通信12轮不出现红色全局停止
- 规则：验收：默认状态下断开设备通信12轮后，不出现红色全局停止。
- 来源：业务规则与变更日志_V1.0.2.md 第 119 行「失败停止开关（2026-09-30）」“采集状态为琥珀色「采集运行中：等待设备响应」，不出现红色全局停止”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。断通信12轮后不出现红色全局停止。（V1.0.2 现状：原核对：设备静默时 PollingCoordinator._halt_acquisition 全局锁停，MainWindow._refresh_communication_events 因 halt_reason() 非空显示红色停止（BUG-1，有复现）。只有串口本身打不开、走 _mark_failed 路径时才不出现红色。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._halt_acquisition

### UI-302 保存配置后实时页面出现光谱
- 规则：保存配置后，实时页面出现光谱。
- 来源：业务规则与变更日志_V1.0.2.md 第 179 行「多设备重构：第 1 阶段（2026-09-17）」“保存配置，确认实时页面出现光谱并持续保存数据。”
- 状态：待确认
- 现状符合度：未验证（实现链路：PollingCoordinator._capture_once 成功后发 acquisition_saved，MainWindow 连接到 refresh_all，再调用 refresh_overview 读 latest_successful_spectrum，用 overview_chart（SpectrumCanvas）.plot 绘制。现有 verify_*.py 中没有“保存配置后实时页出现光谱”的端到端断言，未运行界面核对。）
- 冲突：无；与 POLL-034 同源（第179行）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_all；par_app/ui.py MainWindow.refresh_overview；par_app/ui.py SpectrumCanvas.plot

### UI-303 勾选失败停止后持续异常到10/10显示已退出
- 规则：勾选“失败停止”后持续异常到10/10时，界面显示已退出。
- 来源：业务规则与变更日志_V1.0.2.md 第 213 行「多设备重构：第 3 阶段（2026-09-17）」“勾选「失败停止」后持续异常到10/10，显示已退出；”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-10 已按 D-101 裁决修复（PR #29）：ParModbusClient.read_spectrum_transaction 统计本从站有效应答帧（网关替该设备回的异常码 0x0A/0x0B 表示目标无应答，不计为该设备的帧），未确认停止且整次事务没有收到该从站任何有效帧即为静默设备（任何异常、整次事务零有效帧（网关 0x0A/0x0B 不计）即为静默：串口写失败、USB 拔出、TCP 断连、回包全是校验错误都算，阶段一裁决 37），恢复失败时不再抛 AcquisitionResumeError，原始通信异常照常抛出，PollingCoordinator._poll_one 走 _mark_failed 计数、按周期重试，不触发全局锁停；有应答但停止/恢复状态不一致时仍抛 AcquisitionResumeError 全局锁停；静默后的下一次采集经 ParModbusClient.set_slave_id(resume_first) 先补发一次恢复命令再冻结。静默设备勾选失败停止后到10/10显示已退出，全部退出时为“采集停止中：无可采集设备…”。（V1.0.2 现状：原核对：普通失败路径：_mark_failed 第10次生成“连续第 10/10 次尝试失败…；已退出本次采集，重启软件后重新尝试”，MainWindow._refresh_communication_events 显示在异常文字区；全部启用设备都退出时显示红色“采集停止中：无可采集设备…”。但同组手测上一步（第212行）用断开探头通信制造异常，静默设备首轮就进入全局锁停，到不了10/10（BUG-1）。）
- 冲突：D-101 已裁决：单台设备整次事务完全无应答按普通通信失败处理、按周期重试，不触发全局锁停（有应答但停止/恢复状态不一致时仍全局锁停），恢复应答后的第一轮先补发一次恢复命令；DEF-10 已修复（PR #29）；与 POLL-066 同源（第213行）
- 验证：tests/qt/test_polling_silent_device.py::test_window_shows_amber_waiting_state_for_a_silent_device
- 代码锚点：par_app/ui.py MainWindow._refresh_communication_events；par_app/coordinator.py PollingCoordinator._mark_failed

### UI-304 旧记录读取时CCT与峰值波长兼容整数显示
- 规则：读取旧记录时，CCT、PAR峰值波长、全谱峰值波长兼容按整数显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“硬件浮点解码及`mcu_params_json.cct`原值保留。旧记录读取时兼容整数显示，不批量改写旧库。”
- 状态：待确认
- 现状符合度：符合（MainWindow._cct_value 取 metrics.get('cct_kelvin', parameters.get('cct'))：旧记录缺少 cct_kelvin 时回退到 mcu_params 的 cct，非负有限值按 int(value+.5) 取整，否则为空。MainWindow._record_metric_values 对 peak_wavelength_nm、extended_peak_wavelength_nm 以 0 位小数格式化（f-string，舍入方式与 CCT 的 +.5 不同，原文对旧记录未规定舍入方法）。verify_configuration.py verify_first_pages 构造缺少 cct_kelvin 的旧记录，断言 cct 显示为 "6992"、峰值显示为 "479"/"900"。由原 CONF-027 拆出；不批量改写旧库的部分保留为 CONF-027。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/metrics.py cct_value；par_app/services/metrics.py record_metric_values；verify_configuration.py verify_first_pages

### UI-305 历史表列宽先保证文字可读再分配剩余空间
- 规则：历史表各列宽度先满足文字可读所需的宽度，再把剩余宽度分配给各列。
- 来源：业务规则与变更日志_V1.0.2.md 第 49 行「实时概览与历史回放（2026-10-11）」“列宽先保证文字可读再分配剩余空间；宽屏消除多余横向滚动，窄窗口保留必要滚动，不缩小字号”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._align_history_table 中，每列最小宽度 = 表头最长行文字宽度 + 12；采集时间列再取“2026-09-19 23:59:59.999”宽度 + 16 与前者的较大值。剩余宽度 remaining 按权重 (45,55,190,65,65) 追加到各列。verify_configuration.py verify_first_pages 断言每列 columnWidth ≥ 表头文字宽度 + 12。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_history_table；verify_configuration.py verify_first_pages

### UI-306 宽屏时历史表消除多余横向滚动
- 规则：宽屏时历史表不出现多余的横向滚动（原文没有给出“宽屏”的宽度阈值）。
- 来源：业务规则与变更日志_V1.0.2.md 第 49 行「实时概览与历史回放（2026-10-11）」“列宽先保证文字可读再分配剩余空间；宽屏消除多余横向滚动，窄窗口保留必要滚动，不缩小字号”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._align_history_table 在 sum(minimums) <= 视口可用宽度时设为 ScrollBarAlwaysOff，列宽总和正好填满视口。实现上的“宽屏”判定是“各列可读最小宽度之和不超过视口”，原文没有给阈值。verify_configuration.py verify_first_pages 在 1680 宽度下断言 history_table.horizontalScrollBar().maximum()==0 且不可见。）
- 冲突：无（历史表头高度见 D-104，已裁决：以第42行单行表头为准，第49行“两行高度加16像素”标为历史废止；本条不涉及表头高度）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_history_table；verify_configuration.py verify_first_pages

### UI-307 窄窗口历史表保留必要横向滚动
- 规则：窗口较窄时，历史表保留必要的横向滚动。
- 来源：业务规则与变更日志_V1.0.2.md 第 49 行「实时概览与历史回放（2026-10-11）」“列宽先保证文字可读再分配剩余空间；宽屏消除多余横向滚动，窄窗口保留必要滚动，不缩小字号”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._align_history_table 在 sum(minimums) > 视口可用宽度时切换为 ScrollBarAsNeeded，列宽不低于各自的可读最小宽度。现有 verify_first_pages 只在 1680 宽度下断言无横向滚动，窄宽度下出现滚动没有测试断言。）
- 冲突：无（与 UI-177（第258行来源）同义重复，按 R-2-2 不在誊抄阶段合并，留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_history_table

### UI-308 历史表适配宽度时不缩小字号
- 规则：历史表在宽屏和窄窗口下都不靠缩小字号来适配宽度。
- 来源：业务规则与变更日志_V1.0.2.md 第 49 行「实时概览与历史回放（2026-10-11）」“列宽先保证文字可读再分配剩余空间；宽屏消除多余横向滚动，窄窗口保留必要滚动，不缩小字号”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_history 固定 history_table.setFont(QFont("Microsoft YaHei", 10))。MainWindow._align_history_table 只调整列宽和横向滚动策略，不改字体。ui.py 中历史表没有其他 setFont、setPointSize 调用。没有测试断言不同宽度下字号保持一致。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._align_history_table

### UI-309 查询区宽度不足时500条说明换到下一行并与查询区左对齐
- 规则：宽度不足时，500条说明移到下一行，并与查询区左侧对齐。
- 来源：业务规则与变更日志_V1.0.2.md 第 51 行「实时概览与历史回放（2026-10-11）」“宽度不足时说明移到下一行并与查询区左侧对齐，时间控件不压缩”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._align_history_table 中，当可用宽度 < history_query_fields.sizeHint 宽度 + 十个汉字间距 + 说明文字宽度时，compact 为真，history_limit_label 移到网格第 1 行第 0 列并跨 2 列；不足条件消失后移回第 0 行第 1 列。verify_configuration.py verify_first_pages 在 compact 时断言说明左边缘与查询区左边缘相差 ≤1 像素，非 compact 时断言与查询按钮间隔十个汉字宽度。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._align_history_table；verify_configuration.py verify_first_pages

### UI-310 查询区宽度不足时起止时间控件不压缩
- 规则：宽度不足时，起止时间控件不被压缩。
- 来源：业务规则与变更日志_V1.0.2.md 第 51 行「实时概览与历史回放（2026-10-11）」“宽度不足时说明移到下一行并与查询区左侧对齐，时间控件不压缩”
- 状态：待确认
- 现状符合度：未验证（par_app/ui.py MainWindow._build_history 给 history_start、history_end 设置了 setMinimumWidth(“2026-09-19 23:59:59”文字宽度 + 40)，作为宽度下限。MainWindow._align_history_table 的 compact 判定以 history_query_fields.sizeHint 为准，宽度不足时先让说明换行。但布局仍可能把控件从 sizeHint 压到 minimumWidth，两者是否相等没有核实，也没有测试断言不同窗口宽度下时间控件宽度不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_history；par_app/ui.py MainWindow._align_history_table

### UI-311 设置页自绘上下三角保留原生点击区域
- 规则：轮询周期、从站地址、TCP端口输入框补绘上下三角后，保留原生的点击区域。（同句的取值范围见 UI-293，步进见 UI-294。）
- 来源：业务规则与变更日志_V1.0.2.md 第 77 行「设置与导出布局（2026-09-20）」“轮询周期、从站地址、TCP端口补上下三角，复用经纬度的绘制方式，保留原生点击区域、范围和步进”
- 状态：待确认
- 现状符合度：符合（仅就点击区域：par_app/ui.py _SolidSpinArrows.paintEvent 先调用 super().paintEvent，再只在 style().subControlRect 返回的原生 SC_SpinBoxUp/Down 区域内叠画三角，不重写鼠标事件或子控件区域；SolidArrowSpinBox、SolidArrowDoubleSpinBox 只是继承。verify_configuration.py verify_settings_layout 点击 interval、device_id_spins[0]、tcp_port 的原生上下子控件中心，断言数值随点击变化，说明点击区域有效。该测试按当前 singleStep 断言，不能证明范围和步进与改动前一致，这两项缺改动前基线，见 UI-293、UI-294，仍为“未验证”。）
- 冲突：无（点击区域与 UI-292 内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py _SolidSpinArrows.paintEvent；par_app/ui.py MainWindow._build_settings；verify_configuration.py verify_settings_layout

### UI-312 设备表4行完整显示且无内部纵向滚动
- 规则：设备表按实际表头、控件行高和边缘尺寸计算高度，4行完整显示，表格内部不出现纵向滚动。
- 来源：业务规则与变更日志_V1.0.2.md 第 77 行「设置与导出布局（2026-09-20）」“设备表按实际表头、控件行高和边缘尺寸计算高度，4行完整显示，不再内部纵向滚动”
- 状态：待确认
- 现状符合度：符合（fix/settings-table-negative-height 修复后）。par_app/ui.py MainWindow._layout_settings_content 中，行高取 max(36, 各单元格控件 minimumSizeHint 高度)，表高取 setFixedHeight(各行高之和 + 表头和边框占用)，且只在设备表可见时调用 setFixedHeight。修复前的缺陷（旧仓库 旧仓库 issue 9）：设置页不在当前页签时，Qt 推迟设备表的 resize 事件，viewport().height() 滞后于 setFixedHeight()；eventFilter 每次 Resize/Move/Show 排队重算都会把滞后差值再叠加一次，反复缩放窗口、进出设置页后表高漂移到负数（Qt “Negative sizes” 警告），切回设置页时表格与“保存并应用全部配置”按钮重叠。修复后隐藏时不再设置固定高度，切回设置页时由视口 Show 事件触发重算。新测试覆盖两个场景：隐藏时反复重算表高保持不变且为正；切回设置页后4行完整显示、verticalScrollBar().maximum()==0、按钮位于表格下方。verify_configuration.py verify_settings_layout 仍断言滚动条最大值为0且第4行底边在视口内。
- 冲突：无
- 验证：tests/qt/test_settings_device_table_height.py::test_hidden_settings_relayout_keeps_device_table_height；tests/qt/test_settings_device_table_height.py::test_device_table_fits_rows_when_returning_to_settings
- 代码锚点：par_app/ui.py MainWindow._layout_settings_content；par_app/ui.py MainWindow.eventFilter；verify_configuration.py verify_settings_layout

### UI-313 硬件错误区自动高度不低于控件最小可读高度
- 规则：硬件错误区自动分配高度时，约40%的上限在窄窗口下不能让高度低于控件最小可读高度；两者冲突时以最小可读高度为准。
- 来源：业务规则与变更日志_V1.0.2.md 第 124 行「统一设备维护（2026-09-18，当前布局）」“最多约占表格区域40%（窄窗口不低于控件最小可读高度），其余空间给软件事件”
- 状态：待确认
- 现状符合度：符合（par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.fit_error_height 中 hardware_height = max(section.minimumSizeHint().height(), min(preferred, int(available * .4)))，最小可读高度优先于40%上限。verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks 在 1080×820、740×580 下只断言上界 sizes[0] <= max(minimum, 40%) + 1，下界“不低于最小可读高度”没有断言。）
- 冲突：无（UI-112 的规则和符合度已补入同一例外，两条内容重复，按 R-2-2 合并留待裁决环节）
- 验证：冻结待确认
- 代码锚点：par_app/device_maintenance_dialog.py DeviceMaintenanceDialog.fit_error_height；verify_maintenance.py MaintenanceTests.test_unified_window_device_isolation_and_locks

### UI-314 光谱计算页交换按钮保留悬停提示
- 规则：光谱计算页的交换A/B按钮保留悬停提示。
- 来源：业务规则与变更日志_V1.0.2.md 第 276 行「光谱计算交互（2026-10-11 更新）」“交换符号使用局部36px字体，实际字形宽度至少24像素，按钮保持44×38像素及悬停提示”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow._build_operations 中 operation_swap_button.setToolTip("交换光谱 A 与 B")，并设置同名 accessibleName。verify_multidevice.py verify_operation_interactions 只断言字号、字形宽度和尺寸，没有断言悬停提示。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_operations

### UI-315 导航为六页
- 规则：主导航为六页，等宽铺满。
- 来源：业务规则与变更日志_V1.0.2.md 第 320 行「导航与光谱来源选择（2026-09-17）」“六页导航保持等宽铺满，使用浅色边框分段”
- 状态：已废止 2026-10-17，由 UI-124 替代（D-108 裁决：第320行“六页”标为历史废止）
- 现状符合度：不符合（等宽铺满符合：PageTabBar.tabSizeHint 按页数平分宽度。页数不符：MainWindow 只建五个页签（实时概览、历史回放、光谱计算、光积累计算、设置与导出），与第131行“主导航为五页”一致、与本条“六页”不一致。）
- 冲突：D-108 已裁决：页名以“光谱计算”“光积累计算”为准，主导航为五页；第131行旧页名和第320行“六页”标为历史写法；本条已废止，约束由 UI-124 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py PageTabBar.tabSizeHint；par_app/ui.py MainWindow.__init__

### UI-316 运行中数据库不可用时不闪退、提示并定时重试
- 规则：软件运行中当前设备的数据库暂时不可访问（U 盘或网络盘断开、目录被删、库文件缺失、库被锁）时，软件不闪退：状态栏提示“当前设备或计算页来源的数据库不可访问：<实际失败的库路径>（原因）”，回溯中取不到库路径时不写路径（裁决 45、47），界面保留最近显示的数据，其他设备继续采集；下一次定时刷新自动重试，数据库恢复后自动刷新并清除提示，不用重启。定时刷新、切换设备、切换标签页、选择历史记录读库失败都就地按此处理。界面其他未预期错误写入日志文件，同类错误只提示一次，软件继续运行。数据一致性被破坏（库损坏、不是数据库文件）或后台线程失效时，按 R-1-5 安全停止后台采集和自动刷新、记录原因并提示重启软件。修复范围按 (a) 最小：计算页故障来源的隔离与恢复后的界面状态管理不在本条，留到新界面 ViewModel（阶段二，见 内部文档 DEF-25）。
- 来源：负责人裁决 D-160，2026-10-17（docs/spec/pending-decisions.md D-160「裁决」行；#13）“场景 A 选 1：运行中数据库暂时不可用时，状态栏提示「数据库不可访问：路径（原因）」，界面保留最近数据，其他设备继续采集，数据库恢复后自动刷新”；提示文案与库路径取法：负责人预授权裁决 45、47，2026-10-17（内部文档）“只改提示文案（写成“当前设备或计算页来源的数据库不可访问：路径”）”；“取异常回溯里最内层 ParDatabase 帧的 path；取不到时不写路径，不冒用当前设备路径”
- 状态：已批准 2026-10-17 负责人
- 现状符合度：符合（提示中的库路径由 par_app/slot_errors.py failed_database_path 取异常回溯里最内层 ParDatabase 帧的 path，取不到时不写路径；目前各刷新路径的 sqlite3 访问都经 ParDatabase 方法，不写路径的情形生产中很难出现。par_app/slot_errors.py report_database_errors 包住 MainWindow.refresh_all，report_slot_database_errors 包住 MainWindow._on_device_switched、MainWindow._on_tab_changed、MainWindow.show_history_spectrum：可恢复的 sqlite3.Error 只在状态栏提示并让刷新缓存失效，下一次定时刷新全部重查，整次刷新成功后清除提示；refresh_overview、show_history_spectrum、_refresh_operation_records 先读库再清屏或改下拉框，读库失败时保留已显示的数据；DLI 坐标改在 refresh_all 按库路径载入，切换设备时读库失败恢复后补齐。main.py main 安装 install_default_excepthook：其他异常写 logs/unhandled_exceptions.log，同类只提示一次，提示写在状态栏常驻标签，不弹模态框；safe_stop_reason 判为库损坏、后台线程失效、MemoryError/SystemError 时 stop_background_work 停止后台采集和定时刷新。“其他设备继续采集”由进程不退出、后台采集线程不受界面刷新失败影响推出，测试未在故障期间运行采集线程；Windows 实机待复核。）
- 冲突：无（D-160 已裁决；范围 (a) 之外的计算页故障来源隔离、恢复后重新匹配等登记在 内部文档 DEF-25 阶段二事项）
- 验证：tests/qt/test_slot_exceptions.py::test_production_setup_survives_30_seconds_without_database_or_modal_dialog；tests/qt/test_slot_exceptions.py::test_refresh_reports_deleted_database_directory_keeps_data_and_recovers；tests/qt/test_slot_exceptions.py::test_refresh_reports_missing_database_file_and_recovers；tests/qt/test_slot_exceptions.py::test_overview_failing_midway_keeps_shown_data_and_catches_up；tests/qt/test_slot_exceptions.py::test_excepthook_keeps_process_alive_logs_and_notifies_once；tests/qt/test_slot_exceptions.py::test_production_hook_stops_background_work_safely；tests/qt/test_database_unavailable_in_place.py::test_switching_to_a_device_with_unavailable_database_binds_it_and_recovers；tests/qt/test_database_unavailable_in_place.py::test_tab_switch_with_unavailable_current_database_is_handled_in_place；tests/qt/test_database_unavailable_in_place.py::test_unavailable_operation_source_is_reported_and_retried_by_the_timer
- 代码锚点：par_app/slot_errors.py report_database_errors；par_app/slot_errors.py report_slot_database_errors；par_app/slot_errors.py install_excepthook；par_app/slot_errors.py safe_stop_reason；par_app/slot_errors.py stop_background_work；par_app/ui.py MainWindow.refresh_all；main.py main

### UI-317 光谱曲线按波长着色填充
- 规则：实时概览、历史回放和光谱计算（A、B 与加法、减法结果）的光谱图，曲线下方按波长着色填充（可见光近似映射，380 nm 以下、780 nm 以上为灰色），曲线本身逐段同色；每段 x_i 到 x_i+1 取 x_i 的颜色，从 0 填到曲线；单条光谱的填充不透明度 0.55。比值结果为单色线、不填充（UI-223）。颜色只用于显示，不改变光谱数值、坐标轴范围或任何指标。
- 来源：V1.0.3 行为（par_app/ui.py SpectrumCanvas._wavelength_to_rgb、SpectrumCanvas._add_colored_spectrum、SpectrumCanvas.plot）；业务需求 #72 “新界面的光谱图和 V1.0.3 一样：曲线下按波长彩色填充”
- 状态：待确认
- 现状符合度：符合（V1.0.3：SpectrumCanvas.plot 非比值时调用 _add_colored_spectrum，单条 alpha 0.55、多条 0.20；页面上每张图只画一条光谱。2.0 新界面：API-08 由 par_app/services/spectrum_display.py 复制同一映射与不透明度，web/src/lib/spectrum.ts fillSeries 按段绘制，tests/api/test_reference_curves_parity.py 与真实 SpectrumCanvas 逐段比较颜色和不透明度；接口合同见 tests/api/test_reference_curves.py，页面绘制见 web/tests/referenceCurves.test.ts。）
- 冲突：无
- 验证：tests/api/test_reference_curves_parity.py::test_fill_and_line_colours_equal_v1
- 代码锚点：par_app/ui.py SpectrumCanvas._wavelength_to_rgb；par_app/ui.py SpectrumCanvas._add_colored_spectrum；par_app/services/spectrum_display.py wavelength_to_rgb；web/src/lib/spectrum.ts fillSeries

### UI-318 纵轴刻度不显示浮点残差
- 规则：2.0 新界面的光谱图（实时概览、历史回放、光谱计算 A、B 与结果）、参考曲线右轴和 DLI 图，纵轴刻度文字最多保留 12 位有效数字后只写出数值本身的小数位，不显示二进制浮点残差（如 2.0380000000000003 显示为 2.038），不用科学计数法，千位分隔符同 ECharts 默认；只改文字，纵轴范围、显示哪些刻度（UI-209、UI-214、UI-184 等）和曲线数据不变。
- 来源：V1.0.3 行为（par_app/ui.py 各画布用 Matplotlib 默认刻度格式，纵轴不出现浮点残差）；#108 “纵轴刻度只显示正常位数，例如「2.038」，不出现「2.0380000000000003」这种浮点残差；纵轴范围和曲线数据不变”
- 状态：待确认
- 现状符合度：符合（V1.0.3 Matplotlib 刻度无残差。2.0 新界面：web/src/lib/axis.ts axisNumber 作为各图纵轴 axisLabel.formatter；修复前光谱计算页加法、减法结果的纵轴端点（服务给的范围如 [0, 2.0380000000000003]，isRound 判为整齐而显示）按原值全部位数显示；e2e 演示库 2150 组 A/B 组合里 1012 个结果的端点带残差。实时概览、历史回放光谱图与 DLI 图未复现（顶端标签本就不显示），同样接上以免日后出现。页面测试见 web/tests/chartAxis.test.ts、web/tests/dli.test.ts。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：web/src/lib/axis.ts axisNumber；web/src/components/OperationChart.vue axisNumber；web/src/components/SpectrumChart.vue axisNumber；web/src/components/OverviewChart.vue axisNumber；web/src/components/DliChart.vue axisNumber；web/src/lib/spectrum.ts responseAxis
