# 指标计算口径（MATH）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### MATH-001 单采后指标算法不变
- 规则：改为单次采集后，指标算法保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“失败停止开关及轮询周期保持原规则。普通导出结构、指标算法和页面布局不变。”
- 状态：待确认
- 现状符合度：未验证（本仓库无版本历史，无法与改动前算法逐行比对。指标计算不只在 software_metrics：PollingCoordinator._capture_once 以 software_metrics(points, spectral_coefficient) 计算并保存；界面另由 MainWindow._ratio 计算光子比与占比、MainWindow._cct_value 对 CCT 取整显示。以上位置均未与单采改动前版本比对。分支 fix/uv-band-350-399 按 D-103 裁决把 pfd_uv/extended_pfd_uv 改为 350–399 nm，这是经批准的口径变更（MATH-022），不是单采改造带来的算法变化。）
- 冲突：D-103 已裁决：紫外 PFD 改为 350–399 nm（与 MCU 一致），只对新记录生效，迁移期间先冻结现状、随 L3 变更一起改；DEF-11 已修复（PR #31），新口径见 MATH-022（相关；本条只约束单采改造不改算法，紫外区间修改另走 L3 变更）
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py software_metrics；par_app/coordinator.py PollingCoordinator._capture_once；par_app/services/metrics.py ratio；par_app/services/metrics.py cct_value

### MATH-002 冻结读取不改光谱算法
- 规则：冻结读取改造不改变光谱计算算法。
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“不回写或自动修复旧数据，不改光谱算法；原PPFD复核策略现已按上节取消。”
- 状态：待确认
- 现状符合度：未验证（无版本历史可比对；冻结读取只改变 protocol 读取时序，_capture_once 仍调用 software_metrics。分支 fix/uv-band-350-399 按 D-103 裁决改紫外区间（MATH-022），不属于冻结读取改造。）
- 冲突：D-103 已裁决：紫外 PFD 改为 350–399 nm（与 MCU 一致），只对新记录生效，迁移期间先冻结现状、随 L3 变更一起改；DEF-11 已修复（PR #31），新口径见 MATH-022（相关；本条只约束冻结读取不改算法，紫外区间修改另走 L3 变更）
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py software_metrics

### MATH-003 叶绿素摘要值来自已保存的软件加权计算
- 规则：实时摘要的叶绿素 A/B 值来自该记录已保存的软件加权计算结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“叶绿素值来自已保存的软件加权计算，不是叶绿素浓度”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_overview 从所显示记录的 software_metrics_json 读取 chlorophyll_a_ypfd/chlorophyll_b_ypfd，界面不重新计算；该值在采集时由 PollingCoordinator._capture_once 调用 math_ops.software_metrics 计算，经 ParDatabase.save_acquisition 写入 software_metrics_json。指标含义另见 MATH-019。）
- 冲突：D-102 已裁决：迁移期间冻结现状 9 锚点曲线，权重来源由农学或光学负责人确认后另开 L3 变更，只对新记录生效并在界面注明口径（相关；本条只约束取已保存值，不涉及权重）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_overview；par_app/services/metrics.py OVERVIEW_KPI_SOURCES；par_app/coordinator.py PollingCoordinator._capture_once；par_app/database.py ParDatabase.save_acquisition；par_app/math_ops.py software_metrics

### MATH-004 成功记录另存cct_kelvin
- 规则：成功记录另存 software_metrics_json.cct_kelvin：原始 CCT 为非负有限值时四舍五入取整；缺失、负数或非有限值时为空（null）。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“成功记录另存`software_metrics_json.cct_kelvin`，非负有限原始CCT按四舍五入取整，缺失、负数或非有限值为空”
- 状态：待确认
- 现状符合度：符合（database.py ParDatabase.save_acquisition：success 且有 mcu_params_json 时，cct 为 int/float、math.isfinite 且 >=0 则 int(cct+.5)，否则 None）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.save_acquisition

### MATH-005 新采集峰值波长存为JSON整数
- 规则：新采集记录的软件峰值波长（PAR 峰值、全谱峰值）取 1 nm 采样点对应波长，以 JSON 整数保存。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“新采集软件峰值为1 nm采样点对应的JSON整数”
- 状态：待确认
- 现状符合度：符合（math_ops.software_metrics 返回 int(base_wavelengths[idx]) 与 int(wavelengths[idx])，经 json.dumps 写入 software_metrics_json）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py software_metrics

### MATH-006 硬件CCT原值保留
- 规则：（设备协议细节，公开版略）
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“硬件浮点解码及`mcu_params_json.cct`原值保留”
- 状态：待确认
- 现状符合度：符合（save_acquisition 只改写 software_metrics_json，mcu_params_json 原样写入；coordinator._capture_once 以 json.dumps(params) 保存协议层解码值）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.save_acquisition；par_app/coordinator.py PollingCoordinator._capture_once

### MATH-007 扩展辐照度沿用PAR缩放口径
- 规则：扩展辐照度（400–750 nm）在界面显示时沿用现有 PAR 缩放口径（存储值 ×10 显示）。（裁决 D-166：采集记录导出的“PAR波段辐照度(W/m²)”和“扩展PAR辐照度(400–750)”两个字段，在 CSV 和 Excel 两种格式中都与界面显示口径一致，输出存储值 ×10；software_metrics 的存储口径（÷10）、数据库和已有历史记录不改写；旧库中的已有记录重新导出时同样按 ×10 输出；本变更之前已经导出的文件不处理、不提供换算工具，由发布说明告知旧导出值小 10 倍。导出的字段名、顺序和 69 项不变。D-166 已批准 2026-10-18（PR #15 评论），见本条「冲突」字段。）
- 来源：业务规则与变更日志_V1.0.2.md 第 38 行「实时概览与历史回放（2026-10-11）」“R1–R15特殊显色指数、XYZ及u/v/x/y。扩展辐照度沿用现有PAR缩放口径”
- 状态：待确认
- 现状符合度：不符合（关联缺陷 data-correctness.md B1，旧仓库 #8。V1.0.2 界面部分符合：math_ops.software_metrics 存 extended_par = energy(400,750)/10，ui.py _record_metric_values 显示 extended_par*10，与 par 相同；导出部分不符合：_export_metadata_rows 直接输出存储值，导出比界面小 10 倍。已修复（PR #15）：_export_metadata_rows 经 math_ops.display_metrics 按 PAR_STORAGE_SCALE 乘回，导出值与界面一致；存储值和已有记录不变，已导出的旧文件不处理。测试覆盖 CSV 与 Excel 两条导出路径和界面显示值对照）
- 冲突：D-166 已批准 2026-10-18（PR #15 评论）：导出口径属红线 R-4-2 第 4 项，负责人按推荐选 A，书面批准（同意 + 范围 + 验证要求）已代录为 PR #15 评论 #15 docs/spec/pending-decisions.md D-166
- 验证：tests/qt/test_export_par_scale.py::test_export_par_and_extended_par_match_the_ui_scale；tests/qt/test_export_par_scale.py::test_export_scales_stored_values_without_touching_the_record
- 代码锚点：par_app/math_ops.py software_metrics；par_app/math_ops.py display_metrics；par_app/services/metrics.py scaled_par；par_app/services/metrics.py record_metric_values；par_app/services/metrics.py overview_metric_entries；par_app/services/export.py metadata_rows

### MATH-008 A=0且B非零有限得有效0
- 规则：A=0 且 B 为非零有限值时，比值结果为有效的0。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“A=0且B为非零有限值时结果为有效0。不截断有限高比值，不改写原始数据”
- 状态：待确认
- 现状符合度：符合（combine(divide) 对该点正常相除得 0.0，保留为有限值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py combine

### MATH-009 不截断有限高比值
- 规则：比值运算不截断有限的高比值。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“A=0且B为非零有限值时结果为有效0。不截断有限高比值，不改写原始数据”
- 状态：待确认
- 现状符合度：符合（combine(divide) 无 clip，只把非有限结果置 NaN；MainWindow._write_operation_file 导出完整 out；MainWindow._redraw_operation_charts 仅按 2% 筛选隐藏点、不改数值。verify_multidevice.py verify_operation_data 断言 1e12/1 结果为 1e12。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py combine；par_app/ui.py MainWindow._redraw_operation_charts；par_app/services/export.py operation_table

### MATH-010 比值B=0/非有限/溢出为NaN
- 规则：A/B运算中，B=0（含0/0）、任一输入非有限值、或计算溢出时，该点结果为无效NaN。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“比值中B=0（包括0/0）、输入非有限值或计算溢出均为无效NaN”
- 状态：待确认
- 现状符合度：符合（combine(divide)：valid = isfinite(a)&isfinite(b)&(b!=0) 才相除，其余及结果非有限均置 NaN。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py combine

### MATH-011 计算仅A+B、A-B、A/B三种
- 规则：光谱计算只提供逐波长 A+B、A−B、A/B 三种运算。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“计算统一为A+B、A-B、A/B，标题和图例采用「计算结果」”
- 状态：待确认
- 现状符合度：符合（op_combo 仅“加法 A+B/减法 A-B/比值 A/B”；math_ops.combine 只接受 add/subtract/divide。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py combine；par_app/ui.py MainWindow._build_operations

### MATH-012 2%是显示筛选约定而非检测下限或精度保证
- 规则：比值的 2% 阈值是显示筛选约定，不是仪器检测下限或精度保证。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“2%是显示筛选约定，不是仪器检测下限或精度保证，加减法不受影响”
- 状态：待确认
- 现状符合度：符合（筛选只作用于绘图：MainWindow._redraw_operation_charts 用 mask 把未通过点置 NaN 后绘制，MainWindow._write_operation_file 导出完整 out 并另列低信号标记；完整说明 OperationGuideCanvas.show_details 写明“该规则不是检测下限、信噪比判据或精度保证”；比值导出元数据“低信号标记说明”写明“仅影响绘图，完整计算值不变；不是仪器检测下限”。导出元数据未提及“精度保证”，原文未要求导出写明，不视为例外。加减法不筛选见 MATH-021。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py OperationGuideCanvas.show_details；par_app/services/export.py operation_table；par_app/ui.py MainWindow._redraw_operation_charts

### MATH-013 交换来源不改变筛选范围
- 规则：交换A、B来源后比值筛选所用阈值与通过点集合不变（对称规则）。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“不补零、不跨缺口连线；交换来源不改变筛选范围”
- 状态：待确认
- 现状符合度：符合（ratio_display_mask 的阈值与条件对 a、b 对称。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py ratio_display_mask

### MATH-014 仅A≥T、B≥T且B≠0的点绘制
- 规则：比值曲线只绘制 A≥T、B≥T 且 B≠0 的波长点，其余点不绘制。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“仅A>=T、B>=T且B非零的点绘制，低信号断开，不补零、不跨缺口连线”
- 状态：待确认
- 现状符合度：（设备协议细节，公开版略）
- 冲突：D-143 已裁决：规格只覆盖设备实际能产生的有限、非负输入，范围外的处理按技术记录保持现状
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py ratio_display_mask；par_app/ui.py MainWindow._redraw_operation_charts

### MATH-015 比值显示共同阈值T定义
- 规则：比值显示阈值 T = 2% × max(A全波段峰值, B全波段峰值)，峰值固定在350–1050 nm全部701点上取。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“比值显示共同阈值T=2%×max(A全波段峰值,B全波段峰值)，峰值固定取350–1050nm”
- 状态：待确认
- 现状符合度：符合（按 D-143 裁决，规格只覆盖设备能产生的有限、非负输入：此范围内 ratio_display_mask 对有限值取最大值、下限 0、乘 0.02，与原文 T=2%×max(A峰值,B峰值) 一致。剔除非有限值、峰值下限 0 只影响范围外输入（含 MainWindow._write_operation_file 导出的阈值数值），按技术记录保持现状。）
- 冲突：D-143 已裁决：规格只覆盖设备实际能产生的有限、非负输入，范围外的处理按技术记录保持现状
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py ratio_display_mask；par_app/services/export.py operation_table

### MATH-016 不自动做背景/暗信号/跨设备校正
- 规则：光谱计算不自动执行背景扣除、暗信号校正或跨设备响应校正。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“本页不计算吸收率/吸光度，不自动完成背景、暗信号或跨设备响应校正”
- 状态：待确认
- 现状符合度：符合（run_operation 直接对 _operation_values 结果调用 combine，无校正步骤。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.run_operation；par_app/math_ops.py combine

### MATH-017 本页不计算吸收率/吸光度
- 规则：光谱计算页不计算吸收率或吸光度。
- 来源：业务规则与变更日志_V1.0.2.md 第 290 行「光谱计算交互（2026-10-11 更新）」“本页不计算吸收率/吸光度，不自动完成背景、暗信号或跨设备响应校正”
- 状态：待确认
- 现状符合度：符合（math_ops.combine 只有 add/subtract/divide。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py combine

### MATH-018 2%显示筛选保持不变
- 规则：比值2%显示筛选规则保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 291 行「光谱计算交互（2026-10-11 更新）」“2%显示筛选保持不变，摘要和弹窗均提醒可能隐藏真实低透射区”
- 状态：待确认
- 现状符合度：符合（ratio_display_mask 仍为 0.02×峰值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py ratio_display_mask

### MATH-019 叶绿素值不是叶绿素浓度
- 规则：实时摘要的叶绿素 A/B 值不是叶绿素浓度。
- 来源：业务规则与变更日志_V1.0.2.md 第 36 行「实时概览与历史回放（2026-10-11）」“叶绿素值来自已保存的软件加权计算，不是叶绿素浓度”
- 状态：待确认
- 现状符合度：符合（math_ops.software_metrics 以叶绿素 A/B 权重曲线对光子通量加权得到 chlorophyll_a_ypfd/chlorophyll_b_ypfd；MainWindow._build_overview 摘要卡名称为“叶绿素 A/B 加权光子通量”，MainWindow.refresh_overview 显示单位 µmol·m⁻²·s⁻¹，未标为浓度。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/math_ops.py software_metrics；par_app/ui.py MainWindow._build_overview；par_app/ui.py MainWindow.refresh_overview；par_app/services/metrics.py OVERVIEW_KPI_SOURCES

### MATH-020 光谱计算不改写原始数据
- 规则：光谱计算不改写原始数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 281 行「光谱计算交互（2026-10-11 更新）」“A=0且B为非零有限值时结果为有效0。不截断有限高比值，不改写原始数据”
- 状态：待确认
- 现状符合度：符合（MainWindow._operation_values 由记录点数组除以 10^光谱系数生成新数组；combine 返回新数组，divide 写入独立的 result；MainWindow.run_operation 只把 av/bv/out 存入 current_result，不写数据库；绘图用 np.where 生成新数组。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._operation_values；par_app/ui.py MainWindow.run_operation；par_app/math_ops.py combine

### MATH-021 加减法不受2%筛选影响
- 规则：2% 显示筛选不作用于加法、减法结果。
- 来源：业务规则与变更日志_V1.0.2.md 第 282 行「光谱计算交互（2026-10-11 更新）」“2%是显示筛选约定，不是仪器检测下限或精度保证，加减法不受影响”
- 状态：待确认
- 现状符合度：符合（MainWindow._redraw_operation_charts 仅 op=="divide" 时调用 ratio_display_mask 并隐藏未通过点；MainWindow._write_operation_file 仅比值导出阈值元数据和低信号标记列。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._redraw_operation_charts；par_app/services/export.py operation_table

### MATH-022 紫外PFD取350–399 nm，只对新记录生效
- 规则：（设备协议细节，公开版略）
- 来源：D-103 裁决（docs/spec/pending-decisions.md，负责人 2026-10-17 按推荐）“设备协议细节，公开版略”
- 状态：待确认
- 现状符合度：符合（分支 fix/uv-band-350-399 修复 DEF-11 后：math_ops.software_metrics 中 pfd_uv、extended_pfd_uv 改为 photon(350, 399)；software_metrics 只在 PollingCoordinator._capture_once 采集时调用，历史详情和导出（MainWindow._export_metadata_rows）读 software_metrics_json 的存储值，ParDatabase 打开时不回写旧记录。旧记录导出时显示在新标签“紫外PFD(350–399)”“扩展紫外PFD(350–399)”下，其数值仍为旧口径 350–400 nm；记录本身没有口径标记，不另作区分，已在 docs/CHANGELOG.md 写明（阶段一裁决 40）。生效版本 V1.0.3 测试版（阶段一裁决 42）。）
- 冲突：D-103 已裁决（本条即裁决内容）；旧记录以新标签导出的口径差异按阶段一裁决 40 接受，在发布说明中写明，不改历史格式
- 验证：tests/unit/test_uv_band.py::test_uv_pfd_is_the_closed_350_399_nm_sum；tests/unit/test_uv_band.py::test_400_nm_counts_only_as_blue；tests/unit/test_uv_band.py::test_399_nm_counts_only_as_uv；tests/unit/test_uv_band.py::test_uv_blue_green_red_add_up_to_the_350_699_nm_total；tests/unit/test_uv_band.py::test_each_edge_point_falls_in_exactly_one_sub_band；tests/qt/test_uv_band_history.py::test_reopening_the_database_keeps_legacy_uv_values；tests/qt/test_uv_band_history.py::test_export_writes_the_stored_uv_value_under_the_new_band_label
- 代码锚点：par_app/math_ops.py software_metrics；par_app/services/export.py EXPORT_METRICS_FIELDS；par_app/services/export.py metadata_rows；par_app/coordinator.py PollingCoordinator._capture_once
