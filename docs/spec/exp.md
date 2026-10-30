# 导出（EXP）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### EXP-001 单采后普通导出结构不变
- 规则：改为单次采集策略后，普通导出结构不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 23 行「单次采集策略（2026-10-11）」“失败停止开关及轮询周期保持原规则。普通导出结构、指标算法和页面布局不变。”
- 状态：待确认
- 现状符合度：未验证（“普通导出结构”包括文件头、元数据区、光谱区的整体组织；无单采改动前后的导出对照样本可比。现状结构由 _write_export_file 组织：4 行文件头 + _export_metadata_rows 69 项 + 空行 + _export_spectrum_rows 光谱区，无光谱时光谱区写提示行。审计 data-correctness.md B1 指出导出“PAR波段辐照度”比界面小10倍，属数值口径问题而非结构变化（已修复（PR #15），见 MATH-007）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_acquisition_file；par_app/services/export.py metadata_rows；par_app/services/export.py spectrum_rows

### EXP-002 CSV/Excel保留原有69项字段结构
- 规则：普通 CSV/Excel 导出保留原有 69 项字段结构。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“普通CSV/Excel保留原有69项字段结构及原始硬件CCT，只补全总辐照度标签的350–1050 nm范围”
- 状态：待确认
- 现状符合度：未验证（ui.py EXPORT_ALL_FIELDS = EXPORT_DIRECT_FIELDS + EXPORT_METRICS_FIELDS + EXPORT_MCU_FIELDS = 15+27+27 = 69 项，_export_metadata_rows 逐项输出。以上只证明项数为 69；“保留原有字段结构”需要与改动前的字段名和顺序逐项比较，目前没有改动前字段表或导出样本作基线，替换或重排字段后项数仍可为 69，因此不能判定符合。导出 PAR/扩展PAR 小 10 倍是已知缺陷（data-correctness.md B1，已修复（PR #15），见 MATH-007），不属本条约束。CCT 取值来源见 EXP-057，标签变更范围见 EXP-058。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py EXPORT_ALL_FIELDS；par_app/services/export.py metadata_rows

### EXP-003 导出格式固定 4+69+701
- 规则：固定的 4+69+701 导出格式保持不变。（裁决 D-127：无光谱或光谱不完整的记录照常导出 4 行文件头和 69 项元数据，光谱区写一行提示，不输出 701 点。）
- 来源：业务规则与变更日志_V1.0.2.md 第 93 行「单次采集与分段 DLI（2026-10-11）」“固定4+69+701导出格式保持不变，采集审计保存在SQLite的”
- 状态：待确认
- 现状符合度：符合（按 D-127 裁决，无光谱或光谱不完整的记录照常导出、光谱区写一行提示，是规格写明的例外。有光谱分支：_write_export_file 写 4 行 header、_export_metadata_rows 输出 69 项、_export_spectrum_rows 输出 701 行；无光谱分支：database.acquisitions_for_export 用 LEFT JOIN spectra 取出无光谱记录，_export_spectrum_rows 在 raw_points_json 为空、无法解析或点数不等于 701 时返回 None，_write_export_file 的 CSV 与 Excel 分支只写一行“光谱数据区 / 本记录无原始光谱数据…”提示，verify_export.py 断言这一例外。另：数值有已知缺陷 PAR/扩展PAR 导出小 10 倍（data-correctness B1，已修复（PR #15），见 MATH-007），不属本条格式约束。）
- 冲突：D-127 已裁决：无光谱或光谱不完整的记录照常导出（4 行文件头、69 项元数据，光谱区一行提示），在规格中写明这一例外（与 EXP-006 同一问题）
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_acquisition_file；par_app/services/export.py metadata_rows；par_app/services/export.py spectrum_rows；par_app/services/export.py EXPORT_ALL_FIELDS；par_app/database.py ParDatabase.acquisitions_for_export

### EXP-004 切换设备重读导出统计
- 规则：切换当前查看设备时，重新读取该设备数据库的导出记录统计。
- 来源：业务规则与变更日志_V1.0.2.md 第 236 行「多设备重构：第 5 阶段（2026-09-17）」“切换当前设备时重新读取该库的DLI经纬度、历史选择和导出统计”
- 状态：已废止 2026-10-17，由 EXP-042 替代（D-116 裁决：第236行“切换当前设备时重新读取该库的导出统计”标为历史废止）
- 现状符合度：不符合（_bind_active_device 调 update_export_range→refresh_export_count，但统计对象是 _export_source()（export_device_combo 独立选择），顶部切换设备不改变 export_device_combo（仅首次进入设置页时同步为当前设备一次），按第327行 P6 行为实现。）
- 冲突：D-116 已裁决：以第327行为准，导出区独立选择导出设备，顶部切换查看设备不改变导出统计；第236行“导出统计”和第245行“导出记录范围”标为历史；本条已废止，约束由 EXP-042 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._bind_active_device；par_app/ui.py MainWindow.refresh_export_count；par_app/ui.py MainWindow._export_source

### EXP-005 运算导出记录来源信息
- 规则：运算结果导出时记录A、B各自的来源设备、数据库、记录ID和采集时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 238 行「多设备重构：第 5 阶段（2026-09-17）」“运算导出记录来源设备、数据库、记录ID和时间。”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 元数据含“光谱 A/B 来源设备/来源数据库/记录 ID/采集时间”；verify_multidevice 覆盖导出来源。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table；par_app/ui.py MainWindow._operation_item

### EXP-006 保持4行头+69项元数据+701点格式
- 规则：普通采集导出文件保持4行文件头、69项元数据及701点光谱格式。（裁决 D-127：无光谱或光谱不完整的记录照常导出 4 行文件头和 69 项元数据，光谱区写一行提示，不输出 701 点。）
- 来源：业务规则与变更日志_V1.0.2.md 第 239 行「多设备重构：第 5 阶段（2026-09-17）」“保持4行文件头、69项元数据及701点光谱格式”
- 状态：待确认
- 现状符合度：符合（按 D-127 裁决，无光谱或光谱不完整的记录只写一行提示，是规格写明的例外。有光谱分支：_write_export_file 写 4 行 header，EXPORT_ALL_FIELDS = 15+27+27 = 69 项，_export_spectrum_rows 输出 701 点；无光谱分支：acquisitions_for_export 以 LEFT JOIN 取出无光谱记录，_export_spectrum_rows 返回 None，_write_export_file 在 CSV 与 Excel 中写一行“本记录无原始光谱数据”提示。数值层面另有审计 data-correctness B1（PAR 导出小 10 倍，已修复（PR #15），见 MATH-007），不属本条格式约束。）
- 冲突：D-127 已裁决：无光谱或光谱不完整的记录照常导出（4 行文件头、69 项元数据，光谱区一行提示），在规格中写明这一例外（与 EXP-003 同一问题）
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_acquisition_file；par_app/services/export.py EXPORT_ALL_FIELDS；par_app/services/export.py spectrum_rows；par_app/database.py ParDatabase.acquisitions_for_export

### EXP-007 导出对话框期间切换设备不影响本次数据
- 规则：导出对话框期间切换设备，不改变本次已取得的导出数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 239 行「多设备重构：第 5 阶段（2026-09-17）」“导出对话框期间切换设备不会改变本次已取得的数据。”
- 状态：待确认
- 现状符合度：符合（export_acquisitions 在弹出目录选择和确认框之前取得 device_name 与 rows，之后只用这份快照；verify_multidevice 覆盖导出期间设备切换。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions

### EXP-008 采集导出按设备/格式/日期组织
- 规则：普通采集记录导出按“设备/CSV或Excel/日期”的目录结构组织。
- 来源：业务规则与变更日志_V1.0.2.md 第 239 行「多设备重构：第 5 阶段（2026-09-17）」“普通采集导出仍按设备/CSV或Excel/日期组织”
- 状态：待确认
- 现状符合度：符合（export_acquisitions 生成 <父目录>/<设备名>/<CSV|Excel>/<YYYY-MM-DD>/PAR_…_#ID.ext；审计 requirements.md M10 已实现。<设备名> 目录由 safe_database_filename 生成，Windows 保留名、控制字符和超长名的转换已修复（PR #23），被新规则改动的目录名末尾带 V1.0.2 结果的 8 位摘要，不会让 V1.0.2 下不同的两台设备共用目录而互相覆盖（tests/qt/test_export_device_folder.py），见 CONF-030。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions；par_app/services/export.py device_folder；par_app/services/export.py acquisition_day_folder

### EXP-009 切换设备后导出记录范围随之切换
- 规则：顶部切换设备后，导出记录范围对应新设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 245 行「多设备重构：第 5 阶段（2026-09-17）」“重启软件，在顶部切换设备，核对实时、历史、DLI位置和导出记录范围。”
- 状态：已废止 2026-10-17，由 EXP-042 替代（D-116 裁决：第245行“导出记录范围随顶部切换设备”标为历史废止）
- 现状符合度：不符合（导出统计/范围使用独立的 export_device_combo，顶部切换设备不改变它（仅首次进入设置页时同步为当前设备一次），按第327行 P6 实现。）
- 冲突：D-116 已裁决：以第327行为准，导出区独立选择导出设备，顶部切换查看设备不改变导出统计；第236行“导出统计”和第245行“导出记录范围”标为历史；本条已废止，约束由 EXP-042 承接
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._export_source；par_app/ui.py MainWindow.update_export_range

### EXP-010 运算导出含来源设备名称
- 规则：光谱运算分别选择A/B数据库及记录计算并导出后，导出文件含来源设备名称。
- 来源：业务规则与变更日志_V1.0.2.md 第 246 行「多设备重构：第 5 阶段（2026-09-17）」“在光谱运算分别选择A/B数据库及采集记录，计算并导出，检查来源设备名称”
- 状态：待确认
- 现状符合度：符合（_operation_item 注入 source_device，_write_operation_file 写“光谱 A/B 来源设备”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table；par_app/ui.py MainWindow._operation_item

### EXP-011 导出文件数按格式数预览
- 规则：导出前预览的文件数量 = 记录条数 × 所选格式数。
- 来源：业务规则与变更日志_V1.0.2.md 第 260 行「页面布局与显示（2026-09-19）」“采集记录导出支持CSV/Excel多选、一次确认，文件数量按格式数预览”
- 状态：待确认
- 现状符合度：符合（refresh_export_count 显示“预计 N 条记录，将导出为 N×格式数 个文件”；确认框同样按 len(rows)*len(kinds)。审计 robustness-ui Bug 1（“最近N小时”范围不刷新）曾使预览范围本身失准，但不影响本条乘法关系，已由 DEF-15 修复（PR #12，见 EXP-051）；Bug 2（结束时间截到整秒）已于 2026-10-17 修复，预计条数与导出条数按同一闭区间统计（旧仓库 旧仓库 issue 16，fix/export-end-second）。）
- 冲突：无
- 验证：tests/qt/test_export_end_second.py::test_custom_range_counts_and_exports_records_inside_end_second
- 代码锚点：par_app/ui.py MainWindow.refresh_export_count；par_app/ui.py MainWindow.export_acquisitions

### EXP-012 采集导出保持设备/格式/日期目录
- 规则：采集记录导出文件按 设备/格式/采集日期 三级目录存放。
- 来源：业务规则与变更日志_V1.0.2.md 第 260 行「页面布局与显示（2026-09-19）」“仍是每条记录每种格式一个文件，保持设备/格式/日期目录，不合并记录”
- 状态：待确认
- 现状符合度：符合（export_acquisitions：Path(folder)/device_folder/(CSV|Excel)/<采集日期>。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions；par_app/services/export.py device_folder；par_app/services/export.py acquisition_day_folder

### EXP-013 采集导出每记录每格式一文件
- 规则：采集记录导出仍为每条记录、每种格式各生成一个文件，不把多条记录合并到一个文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 260 行「页面布局与显示（2026-09-19）」“仍是每条记录每种格式一个文件，保持设备/格式/日期目录，不合并记录”
- 状态：待确认
- 现状符合度：符合（export_acquisitions 对每条 row、每个 selected_kind 调用一次 _write_export_file，文件名含记录 ID。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions；par_app/services/export.py acquisition_file_name；par_app/services/export.py write_acquisition_file

### EXP-014 采集记录导出支持CSV/Excel多选
- 规则：采集记录导出支持同时选择 CSV 和 Excel 两种格式。
- 来源：业务规则与变更日志_V1.0.2.md 第 260 行「页面布局与显示（2026-09-19）」“采集记录导出支持CSV/Excel多选、一次确认，文件数量按格式数预览”
- 状态：待确认
- 现状符合度：符合（_build_settings 建立 export_csv_choice、export_xlsx_choice 两个复选框，“导出采集记录”按钮把勾选的格式组成元组传给 export_acquisitions；refresh_export_count 在未勾选任何格式时禁用该按钮。单格式按钮 export_csv_button/export_xlsx_button 仍存在但已隐藏。确认次数见 EXP-059。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow.export_acquisitions；par_app/ui.py MainWindow.refresh_export_count

### EXP-015 计算导出完整701点
- 规则：计算结果导出完整的 701 点。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“导出完整701点和未经显示筛选改写的计算值，即使绘图隐藏尖峰也保留有限原值”
- 状态：待确认
- 现状符合度：符合（_write_operation_file（现为 services/export.py operation_table）以 zip(WAVELENGTHS, a, b, out, …) 逐点写出，CSV 与 Excel 均为 701 行数据；_redraw_operation_charts 只在 A、B 均为成功且完整的光谱时允许计算。未经显示筛选改写见 EXP-060。V1.0.2 的 zip 未加 strict，若传入不足 701 点的数组会静默截断成更短的表；refs #2 起改为写文件前校验等长，不等长时抛 ValueError 由导出入口提示“导出失败”，不写出数据文件（批量导出时本次新建的目录可能留空），正常 701 点输入的结果不变。）
- 冲突：无
- 验证：tests/qt/test_operation_export_length.py::test_complete_spectra_export_all_701_rows；tests/qt/test_operation_export_length.py::test_short_spectrum_is_rejected_not_truncated
- 代码锚点：par_app/services/export.py operation_table；par_app/services/export.py write_operation_file

### EXP-016 无效结果导出为文本NaN
- 规则：计算导出中所有无效（非有限）值统一写为文本“NaN”，不得写成0或空。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“及新增第六列结果有效标记（1=有效，0=无效）；无效结果统一写为文本NaN”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 的 CSV 与 Excel 均以 "NaN" 字符串替换非有限值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-017 比值导出含阈值与规则元数据
- 规则：比值运算的CSV/Excel导出包含共同阈值数值及筛选规则说明元数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“比值CSV/Excel包含共同阈值、规则元数据、第五列低信号标记（1=未通过显示筛选，0=通过）”
- 状态：待确认
- 现状符合度：符合（_write_operation_file(divide) 追加“比值显示共同阈值”“比值显示筛选规则”“低信号标记说明”“无效值说明”元数据行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table

### EXP-018 比值导出第五列低信号标记
- 规则：比值导出第五列为低信号标记：1=未通过显示筛选，0=通过。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“比值CSV/Excel包含共同阈值、规则元数据、第五列低信号标记（1=未通过显示筛选，0=通过）”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 第五列为 (~mask).astype(int)。注意 CSV 经 float() 写出为 1.0/0.0 文本。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table

### EXP-019 比值导出第六列结果有效标记
- 规则：比值导出新增第六列结果有效标记：1=有效，0=无效。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“及新增第六列结果有效标记（1=有效，0=无效）；无效结果统一写为文本NaN”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 第六列为 np.isfinite(out).astype(int)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table

### EXP-020 写入失败提示目录与已完成文件
- 规则：写入失败时提示保存目录和已完成的文件列表。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“取消不创建文件，写入失败提示目录及已完成文件”
- 状态：待确认
- 现状符合度：符合（except (OSError, ValueError) → QMessageBox.critical 显示保存目录与“已完成：…”。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/services/export.py export_operation_files

### EXP-021 取消导出不创建文件
- 规则：导出计算结果时取消，不创建文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“取消不创建文件，写入失败提示目录及已完成文件”
- 状态：待确认
- 现状符合度：符合（export_operation_results 在格式对话框或目录对话框取消时直接 return，均在 mkdir 与 _write_operation_file 之前，因此既不创建文件也不创建结果目录。“不创建目录”只是现状说明，原文只要求不创建文件。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results

### EXP-022 导出使用点击时结果快照
- 规则：导出使用点击导出时的计算结果快照；导出过程中改变选择不影响本次输出。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“导出使用点击时的结果快照，过程中改选不改变本次输出”
- 状态：待确认
- 现状符合度：符合（export_operation_results 开头 result = self.current_result 并全程使用该元组；格式与目录对话框为模态。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results

### EXP-023 导出按钮仅结果有效时启用
- 规则：“导出计算结果”仅在结果有效时启用。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“「导出计算结果」仅在结果有效时启用，支持CSV/Excel多选”
- 状态：待确认
- 现状符合度：符合（按 D-128 裁决，“结果有效”指已执行计算且输入未变化：_invalidate_operation_result 在输入变化时清空 current_result 并禁用按钮，_redraw_operation_charts 在 current_result 不为 None 时启用按钮，export_operation_results 只检查 current_result 是否为 None；全为 NaN 的比值结果可导出，与裁决一致。）
- 冲突：D-128 已裁决：“结果有效”指已执行计算且输入未变化，全部为 NaN 的结果也允许导出
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._invalidate_operation_result；par_app/ui.py MainWindow._redraw_operation_charts

### EXP-024 每次导出建独立结果目录
- 规则：用户选择父目录后，每次导出在其中新建一个名称含算法和时间的独立目录。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“用户选择父目录，每次创建带算法和时间的独立目录，重名追加序号不覆盖”
- 状态：待确认
- 现状符合度：符合（export_operation_results：目录名 A{id}_{add|sub|ratio}_B{id}_{北京时间到微秒}。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/services/export.py export_operation_files

### EXP-025 计算导出每种格式一个文件
- 规则：计算结果导出时，每种所选格式生成一个文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“每种格式一个文件，包含波长/A/B/结果四列及元数据”
- 状态：待确认
- 现状符合度：符合（export_operation_results 对每个所选 kind 调用一次 _write_operation_file，文件名 A{id}_{算法}_B{id}.{csv|xlsx}。文件内容见 EXP-061。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/services/export.py export_operation_files

### EXP-026 计算导出CSV/Excel多选
- 规则：计算结果导出可同时选择CSV与Excel两种格式。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“「导出计算结果」仅在结果有效时启用，支持CSV/Excel多选”
- 状态：待确认
- 现状符合度：符合（export_operation_results 格式弹窗提供两个复选框，均未选时确定按钮禁用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results

### EXP-027 重名目录追加序号不覆盖
- 规则：结果目录重名时追加序号另建，不覆盖已有目录。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“用户选择父目录，每次创建带算法和时间的独立目录，重名追加序号不覆盖”
- 状态：待确认
- 现状符合度：符合（export_operation_results 循环 mkdir，FileExistsError 时追加 _1、_2…。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/services/export.py export_operation_files

### EXP-028 Excel中NaN为文本
- 规则：Excel中无效值以文本“NaN”写入。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“原始数值不舍入，标记列为整数，NaN为文本”
- 状态：待确认
- 现状符合度：符合（非有限值写入字符串 "NaN"。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-029 Excel分计算数据/说明两表
- 规则：Excel计算导出包含名为“计算数据”和“计算说明”的两张工作表。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“Excel计算导出分为「计算数据」和「计算说明」两张表，默认打开数据表”
- 状态：待确认
- 现状符合度：符合（_write_operation_file：active 表命名“计算数据”，create_sheet("计算说明")。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-030 Excel原始数值不舍入
- 规则：Excel只设置显示格式，单元格中保存的原始数值不舍入。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“原始数值不舍入，标记列为整数，NaN为文本”
- 状态：待确认
- 现状符合度：符合（单元格写入 float(value) 原值，仅设置 number_format。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-031 Excel数值显示格式规则
- 规则：光谱及结果数值：零显示为0；绝对值<0.000001或≥1000000用科学计数法；其余用最多8位小数的显示格式。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“光谱及结果的零显示为0，绝对值小于0.000001或达到1000000时使用科学计数法，其余采用最多8位小数的显示格式”
- 状态：待确认
- 现状符合度：符合（_write_operation_file：magnitude==0 → "0"；<1e-6 或 ≥1e6 → "0.######E+00"；否则 "0.########"。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-032 Excel标记列为整数
- 规则：Excel中低信号标记与结果有效标记列以整数显示。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“原始数值不舍入，标记列为整数，NaN为文本”
- 状态：待确认
- 现状符合度：符合（column≥5 的单元格 number_format="0"（值为 0/1）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-033 Excel默认打开数据表
- 规则：Excel计算导出打开时默认显示“计算数据”表。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“Excel计算导出分为「计算数据」和「计算说明」两张表，默认打开数据表”
- 状态：待确认
- 现状符合度：符合（workbook.active 保持为首个“计算数据”表。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-034 数据表冻结表头与波长列
- 规则：Excel 计算导出的数据表冻结表头和波长列。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“冻结表头和波长列、启用筛选。两表统一微软雅黑11磅”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 对“计算数据”表设 freeze_panes="B2"，冻结第 1 行与 A 列（波长）。筛选见 EXP-062。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-035 数据表首行列名后接701点
- 规则：“计算数据”表第一行为列名，其后紧接701个波长点数据行。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“默认打开数据表。数据表首行为列名，随后为701点；列宽12/19/19/22/20/20”
- 状态：待确认
- 现状符合度：符合（_write_operation_file：sheet.append(columns) 后逐行 append 701 行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-036 说明表独立两列
- 规则：Excel 计算导出的说明表为独立的两列结构。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“说明表独立两列，左对齐、长内容换行；完整北京时间按文本保存，保留毫秒”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 用 create_sheet("计算说明") 建独立工作表，首行 ["结果摘要", …]，其余逐行 append metadata_rows 中的两列键值对；D1 处另插品牌图片，不占数据列。左对齐见 EXP-063，换行见 EXP-064。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-037 说明表北京时间文本含毫秒
- 规则：说明表中的完整北京时间以文本形式保存并保留毫秒。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“说明表独立两列，左对齐、长内容换行；完整北京时间按文本保存，保留毫秒”
- 状态：待确认
- 现状符合度：符合（时间由 format_beijing_time 生成“YYYY-mm-dd HH:MM:SS.mmm”字符串，单元格 data_type="s"、number_format="@"。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table；par_app/services/export.py write_operation_file；par_app/database.py format_beijing_time

### EXP-038 普通采集导出不受计算导出影响
- 规则：光谱计算导出的改动不影响普通采集记录导出。
- 来源：业务规则与变更日志_V1.0.2.md 第 286 行「光谱计算交互（2026-10-11 更新）」“极小值及有效零/NaN区分。普通采集记录导出不受本次修改影响”
- 状态：待确认
- 现状符合度：未验证（没有本次修改前后的普通导出实现或样本可对照。现状仅能说明调用分支分离：普通导出走 export_acquisitions/_write_export_file，计算导出走 export_operation_results/_write_operation_file，两者不共用写文件函数。普通导出既有的 PAR 小10倍（data-correctness B1，已修复（PR #15），见 MATH-007）不能判断是否与本次修改有关。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_acquisition_file；par_app/services/export.py write_operation_file

### EXP-039 计算CSV不加入显示公式
- 规则：计算结果CSV不写入任何显示公式或样式。
- 来源：业务规则与变更日志_V1.0.2.md 第 286 行「光谱计算交互（2026-10-11 更新）」“CSV保持原先说明区、空行、表头和701点的结构及数据类型，不加入显示公式”
- 状态：待确认
- 现状符合度：符合（CSV 分支仅写原值或 "NaN"。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-040 计算CSV保持说明区/空行/表头/701点结构
- 规则：计算结果 CSV 保持原先说明区、空行、表头和 701 点的结构。
- 来源：业务规则与变更日志_V1.0.2.md 第 286 行「光谱计算交互（2026-10-11 更新）」“CSV保持原先说明区、空行、表头和701点的结构及数据类型，不加入显示公式”
- 状态：待确认
- 现状符合度：符合（_write_operation_file(csv)：先写 metadata_rows 说明区，再写空行和表头 columns，随后写 701 行数据。仅按原文列出的结构核对，未与修改前文件逐行比较。数据类型见 EXP-065。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-041 导出设备独立选择，不影响查看设备和采集配置
- 规则：设置页导出区单独选择“导出设备”，选择导出设备不改变全局查看设备，也不改变采集配置。
- 来源：业务规则与变更日志_V1.0.2.md 第 327 行「P6 导出设备选择（2026-09-17）」“导出区独立选择「导出设备」，首次进入默认当前查看设备，之后保持所选来源；不改变全局查看设备或采集配置。”
- 状态：待确认
- 现状符合度：符合（export_device_combo 变化只触发 MainWindow.update_export_range；_export_source 按路径查库，不调用 hub.set_active 或 apply_config。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._export_source；par_app/ui.py MainWindow.update_export_range

### EXP-042 导出设备首次进入默认当前查看设备，之后保持
- 规则：首次进入设置与导出页时，导出设备默认设为当前查看设备；此后保持用户所选的导出设备，不随查看设备变化。
- 来源：业务规则与变更日志_V1.0.2.md 第 327 行「P6 导出设备选择（2026-09-17）」“导出区独立选择「导出设备」，首次进入默认当前查看设备，之后保持所选来源；”
- 状态：待确认
- 现状符合度：符合（MainWindow._on_tab_changed 只在 _export_page_visited 为假时把导出设备设为 self.database；_rebuild_export_devices 用 previous 路径恢复选择；顶部切换设备经 _bind_active_device 只调用 update_export_range，不改 export_device_combo。）
- 冲突：D-116 已裁决：以第327行为准，导出区独立选择导出设备，顶部切换查看设备不改变导出统计；第236行“导出统计”和第245行“导出记录范围”标为历史（第236、245行对应的 EXP-004、EXP-009 已废止，由本条替代）
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._on_tab_changed；par_app/ui.py MainWindow._rebuild_export_devices

### EXP-043 每次只导出一台设备
- 规则：每次导出只包含一台设备的记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 327 行「P6 导出设备选择（2026-09-17）」“不改变全局查看设备或采集配置。每次只导出一台设备。”
- 状态：待确认
- 现状符合度：符合（MainWindow.export_acquisitions 只从 _export_source() 返回的单个数据库取数。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions；par_app/ui.py MainWindow._export_source

### EXP-044 导出设备列表显示自定义名称
- 规则：导出设备列表显示已登记设备的自定义名称。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“列表显示已登记设备的自定义名称，悬停显示库路径；故障及停用设备仍可导出，未配置设备不列入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_export_devices 对每个已登记设备 addItem(self.hub.device_at(key).name, path)，显示文本为设备名称。悬停路径见 EXP-066。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_export_devices

### EXP-045 改名保持同一库选择
- 规则：设备改名后，导出设备保持同一数据库的选择。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“改名保持同一库选择，移除设备后更新列表。”
- 状态：待确认
- 现状符合度：符合（下拉项 data 为数据库路径而非名称；配置变化时 _on_devices_changed 调用 _rebuild_export_devices，后者先记下 previous=currentData()，重建后 findData(previous) 恢复同一路径的选择。移除设备见 EXP-067。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_export_devices

### EXP-046 故障及停用设备仍可导出
- 规则：故障或停用设备仍出现在导出设备列表中，可以导出其已有记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“列表显示已登记设备的自定义名称，悬停显示库路径；故障及停用设备仍可导出，未配置设备不列入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_export_devices 遍历全部 hub.keys()，不按启用或故障过滤。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_export_devices

### EXP-047 未配置设备不列入导出列表
- 规则：未登记（未配置）的设备位置不出现在导出设备列表中。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“列表显示已登记设备的自定义名称，悬停显示库路径；故障及停用设备仍可导出，未配置设备不列入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_export_devices 只遍历 hub.keys()（已登记设备）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_export_devices

### EXP-048 导出范围默认最近1小时
- 规则：导出范围默认最近 1 小时。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“导出范围默认最近1小时，可选最近2、4、8、24小时或自定义时间；”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_settings 中 export_range 首项为“最近 1 小时”（data "1h"），未另设当前项，默认即首项；_rebuild_export_devices 末尾调用 update_export_range，经 refresh_export_count → _current_export_range 按当时北京时间填充 1 小时起止（fix/export-preset-window 起，之后定时刷新和导出时也重算，见 EXP-051）。可选范围集合见 EXP-068。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow.update_export_range；par_app/ui.py MainWindow._current_export_range

### EXP-049 无设备或零条记录时禁用导出按钮
- 规则：没有可用导出设备或所选范围内记录为零时，禁用导出按钮。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“记录数按新库重新统计。无设备或零条记录禁用导出按钮。”
- 状态：待确认
- 现状符合度：符合（MainWindow.refresh_export_count 在 database 为 None 时 count=0，导出按钮按 count>0（及格式数>0）启用。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_export_count

### EXP-050 自定义起止时间可编辑
- 规则：自定义起止时间可编辑。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“自定义起止时间可编辑，切换设备时保留，记录数按新库重新统计。”
- 状态：待确认
- 现状符合度：符合（MainWindow.update_export_range 在 custom 模式下对 export_start、export_end 调 setEnabled(True)；MainWindow._current_export_range 在 custom 模式下直接取编辑值，不随时间重算，定时刷新、切回设置页都不改动用户输入的起止（fix/export-preset-window 起由测试覆盖）。切换设备时保留见 EXP-069，按新库计数见 EXP-070。查询范围：开始时间截到整秒，结束时间补“.999”，即 [开始秒.000, 结束秒.999]，与历史页一致；修复前结束时间截到整秒，结束秒内带毫秒的记录既不计数也不导出（robustness-ui.md Bug 2，旧仓库 旧仓库 issue 16，2026-10-17 在 fix/export-end-second 修复）。）
- 冲突：无
- 验证：tests/qt/test_export_end_second.py::test_custom_range_counts_and_exports_records_inside_end_second；tests/qt/test_export_end_second.py::test_custom_range_bounds_are_whole_start_and_end_seconds；tests/qt/test_export_preset_range.py::test_custom_range_is_not_moved_by_time
- 代码锚点：par_app/ui.py MainWindow.update_export_range；par_app/ui.py MainWindow._current_export_range；par_app/ui.py MainWindow.refresh_export_count；par_app/ui.py MainWindow.export_acquisitions

### EXP-051 预设范围以当前北京时间为结束时间
- 规则：选择预设范围时，以当前北京时间为结束时间，开始时间向前推对应小时数。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“选择预设范围时，以当前北京时间为结束时间，开始时间向前推对应小时数，两项时间同步显示为禁用状态。”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-15 已修复（PR #12）：按 D-129 裁决核对。预设模式下 MainWindow._current_export_range 每次调用都取 datetime.now(BEIJING_TZ) 为结束、结束减 N 小时为开始，屏蔽信号写回 export_start、export_end 后返回；refresh_export_count（3 秒定时刷新与切回设置页时经 refresh_settings_console 调用，选择范围、切换导出设备时经 update_export_range 调用）和 export_acquisitions（点击导出时，确认框中的起止与实际查询用同一组值）都经它取范围，灰色起止、预计条数和实际导出时间窗一致。导出内容按点击导出那一刻的快照：export_acquisitions 在弹出文件夹选择框和确认框之前就已取定起止并查出记录（EXP-052），确认框里显示的起止与条数就是实际导出的内容；两个对话框打开期间 3 秒定时刷新照常运行，背景设置页上的灰色起止和预计条数会继续滚动，与确认框不再一致，这一点按阶段一裁决记录第 46 条接受，不影响本次导出。自定义模式直接取编辑值，不随时间移动（EXP-050）。查询时开始时间截到整秒，结束时间补“.999”包含整个结束秒，与历史页上界一致（robustness-ui.md Bug 2，旧仓库 旧仓库 issue 16，PR #11 修复）。起止时间显示与禁用见 EXP-071。（V1.0.2 现状：按原文触发条件“选择预设范围时”核对符合：export_range.currentIndexChanged 触发 update_export_range，取 datetime.now(BEIJING_TZ) 计算一次起止；此后 3 秒定时刷新、再次进入设置页和 export_acquisitions 都不重算，导出的是选择时刻往前 N 小时（requirements.md BUG-4、robustness-ui.md Bug 1），按 D-129 裁决为不符合。）
- 冲突：D-129 已裁决：选择“最近 N 小时”后，定时刷新时同步更新显示的起止时间，点击导出时按当时的北京时间重算；DEF-15 已修复（PR #12）
- 验证：tests/qt/test_export_preset_range.py::test_preset_rolls_on_timed_refresh_while_staying_on_settings；tests/qt/test_export_preset_range.py::test_preset_rolls_when_returning_to_settings；tests/qt/test_export_preset_range.py::test_export_uses_the_preset_window_at_the_moment_of_clicking；tests/qt/test_export_end_second.py::test_preset_range_counts_records_earlier_in_the_end_second
- 代码锚点：par_app/ui.py MainWindow.update_export_range；par_app/ui.py MainWindow._current_export_range；par_app/ui.py MainWindow.refresh_export_count；par_app/ui.py MainWindow.export_acquisitions

### EXP-052 取数后固定设备、数据和文件夹快照
- 规则：导出在取数后固定本次的设备名称、数据和目标文件夹，对话框期间切换设备不影响本次导出。
- 来源：业务规则与变更日志_V1.0.2.md 第 330 行「P6 导出设备选择（2026-09-17）」“取数后固定本次设备名称、数据及文件夹，不受对话框期间设备切换影响。”
- 状态：待确认
- 现状符合度：符合（MainWindow.export_acquisitions 在弹出确认框前已取得 device_name、rows、device_folder 和 folder，后续写文件只用这些局部变量。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions

### EXP-053 导出确认框显示设备名、起止时间和记录数
- 规则：执行导出前的确认框显示导出设备名称、起止时间和记录数。
- 来源：业务规则与变更日志_V1.0.2.md 第 330 行「P6 导出设备选择（2026-09-17）」“确认框显示设备名称、起止时间和记录数；取数后固定本次设备名称、数据及文件夹”
- 状态：待确认
- 现状符合度：符合（MainWindow.export_acquisitions 的“确认导出”对话框包含导出设备、时间范围、记录数、文件数、目录结构和目标文件夹。注意受 BUG-4 影响，预设范围显示的时间可能已过时，但与实际查询一致。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions

### EXP-054 采集记录导出CSV/Excel格式不变
- 规则：采集记录导出的 CSV/Excel 格式不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 330 行「P6 导出设备选择（2026-09-17）」“CSV/Excel格式和按设备/格式/日期的目录结构不变。”
- 状态：待确认
- 现状符合度：未验证（没有 P6 修改前的导出实现或样本可作基线比较。现状文件内容由 _write_export_file 生成：4 行头 + 69 项元数据 + 空行 + 光谱区，无光谱记录写提示行（见 EXP-003）。另有已知数值缺陷：导出的“PAR波段辐照度”比界面小10倍（data-correctness.md B1，已修复（PR #15），见 MATH-007），属于字段数值问题。目录结构见 EXP-072。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_acquisition_file

### EXP-055 P6 导出设备选择的验证记录
- 规则：（原文为验证记录，不是产品行为约束；是否提升为强制验证要求待负责人确认）P6 的验证记录为：verify_multidevice.py 覆盖默认选择、独立来源、DLI位置、零记录、停用库、切换期间确认信息及文件快照；verify_configuration.py 与 verify_export.py 回归；P6 宽窄截图检查。
- 来源：业务规则与变更日志_V1.0.2.md 第 331 行「P6 导出设备选择（2026-09-17）」“验证：verify_multidevice.py覆盖默认选择、独立来源、DLI位置、零记录、停用库、切换期间确认信息及文件快照”
- 状态：待确认
- 现状符合度：未验证（本次誊抄未运行测试。verify_multidevice.py main 中有导出设备默认选择、顶部切换后保持、预设范围起止、自定义时间保留、零记录禁用、对话框期间切换设备的确认信息与文件快照，以及 export_{width}.png 宽窄截图的断言；verify_export.py main 校验普通导出文件结构；verify_configuration.py main 为配置回归入口。审计 test-multidevice.md：原脚本在第718行因过时断言中止；该验证没有覆盖“预设范围随时间推进”，所以 BUG-4 未被发现。所列 DLI 位置检查属于 DLI 领域内容，随原文记录保留在此。）
- 冲突：D-130（第331行验证记录是否提升为强制验证要求）
- 验证：冻结待确认
- 代码锚点：verify_multidevice.py main；verify_configuration.py main；verify_export.py main

### EXP-056 光谱运算结果可导出 CSV 或 Excel
- 规则：光谱运算结果可以导出为 CSV 或 Excel 文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 339 行「产品边界」“光谱运算结果仅驻留当前会话，可导出 CSV 或 Excel，不作为永久采集记录入库。”
- 状态：待确认
- 现状符合度：符合（MainWindow.export_operation_results 支持 CSV/Excel（第284行已更新为多选）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_operation_results；par_app/ui.py MainWindow.export_operation；par_app/services/export.py write_operation_file

### EXP-057 普通导出CCT为原始硬件值
- 规则：普通 CSV/Excel 导出的 CCT 保留原始硬件 CCT。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“普通CSV/Excel保留原有69项字段结构及原始硬件CCT，只补全总辐照度标签的350–1050 nm范围”
- 状态：待确认
- 现状符合度：符合（EXPORT_MCU_FIELDS 中 ("cct", "相关色温(K)", "CCT (K)", "mcu")，_export_metadata_rows 对 source=="mcu" 的字段取 mcu_params_json 中的原值，不取 software_metrics_json.cct_kelvin 的取整值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py EXPORT_MCU_FIELDS；par_app/services/export.py metadata_rows

### EXP-058 普通导出只补全总辐照度标签范围
- 规则：普通 CSV/Excel 导出的字段标签只补全总辐照度标签的 350–1050 nm 范围。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“普通CSV/Excel保留原有69项字段结构及原始硬件CCT，只补全总辐照度标签的350–1050 nm范围”
- 状态：待确认
- 现状符合度：未验证（EXPORT_METRICS_FIELDS 中 integrated_irradiance 的标签为“350–1050 nm 总辐照度(W/m²)”/“Integrated Irradiance 350–1050 nm (W/m²)”，已含范围；“只”改这一处、其余标签不变，没有修改前的字段表可比。另：分支 fix/uv-band-350-399 按 D-103 把紫外、扩展紫外两个标签的区间改为 350–399，属于经批准的后续改动，tests/qt/test_uv_band_history.py 断言新标签。）
- 冲突：D-103 已裁决（紫外 PFD 改为 350–399 nm，只对新记录生效）：分支 fix/uv-band-350-399 随之把“紫外PFD(350–400)”“扩展紫外PFD(350–400)”两个标签改为 350–399（MATH-022，DEF-11）；本条只约束 2026-10-11 那次改动，字段项数和顺序不变
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py EXPORT_METRICS_FIELDS

### EXP-059 采集记录导出一次确认
- 规则：采集记录导出一次确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 260 行「页面布局与显示（2026-09-19）」“采集记录导出支持CSV/Excel多选、一次确认，文件数量按格式数预览”
- 状态：待确认
- 现状符合度：符合（export_acquisitions 对所选的全部格式只弹一次 QMessageBox.question“确认导出”，确认后在循环中对每条记录、每种格式写文件，循环内不再确认。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions

### EXP-060 计算导出保留未经显示筛选改写的计算值
- 规则：计算结果导出未经显示筛选改写的计算值；即使绘图隐藏尖峰，也保留有限原值。
- 来源：业务规则与变更日志_V1.0.2.md 第 283 行「光谱计算交互（2026-10-11 更新）」“导出完整701点和未经显示筛选改写的计算值，即使绘图隐藏尖峰也保留有限原值”
- 状态：待确认
- 现状符合度：符合（_redraw_operation_charts 只对绘图用的 plotted 做 np.where(mask, out, np.nan)；_write_operation_file 写入 current_result 中的 out 原值，非有限值写文本 NaN，有限值不受 ratio_display_mask 影响。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table；par_app/ui.py MainWindow._redraw_operation_charts

### EXP-061 计算导出文件含波长/A/B/结果四列及元数据
- 规则：计算结果导出文件包含波长、A、B、结果四列及元数据。
- 来源：业务规则与变更日志_V1.0.2.md 第 284 行「光谱计算交互（2026-10-11 更新）」“每种格式一个文件，包含波长/A/B/结果四列及元数据”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 的 columns 为“波长（nm）/光谱 A/光谱 B/计算结果”，比值另按第283行加第五、六列标记；元数据在 CSV 中写在说明区，在 Excel 中写入“计算说明”表。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py operation_table

### EXP-062 计算数据表启用筛选
- 规则：Excel 计算导出的数据表启用筛选。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“冻结表头和波长列、启用筛选。两表统一微软雅黑11磅”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 对“计算数据”表设 sheet.auto_filter.ref = sheet.dimensions。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-063 计算说明表左对齐
- 规则：Excel 计算导出的说明表左对齐。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“说明表独立两列，左对齐、长内容换行；完整北京时间按文本保存，保留毫秒”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 对“计算说明”表全部单元格设 Alignment(horizontal="left", vertical="top", wrap_text=True)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-064 计算说明表长内容换行
- 规则：Excel 计算导出的说明表长内容换行。
- 来源：业务规则与变更日志_V1.0.2.md 第 285 行「光谱计算交互（2026-10-11 更新）」“说明表独立两列，左对齐、长内容换行；完整北京时间按文本保存，保留毫秒”
- 状态：待确认
- 现状符合度：符合（_write_operation_file 对“计算说明”表单元格设 wrap_text=True。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-065 计算CSV保持原先数据类型
- 规则：计算结果 CSV 保持原先的数据类型。
- 来源：业务规则与变更日志_V1.0.2.md 第 286 行「光谱计算交互（2026-10-11 更新）」“CSV保持原先说明区、空行、表头和701点的结构及数据类型，不加入显示公式”
- 状态：待确认
- 现状符合度：未验证（没有修改前的 CSV 实现或样本可比。现状：数据行每个值经 float() 写出，非有限值写文本“NaN”，比值的两列标记也以浮点文本 1.0/0.0 写出；说明区为原值。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/services/export.py write_operation_file

### EXP-066 导出设备悬停显示库路径
- 规则：导出设备列表悬停显示库路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“列表显示已登记设备的自定义名称，悬停显示库路径；故障及停用设备仍可导出，未配置设备不列入。”
- 状态：待确认
- 现状符合度：符合（MainWindow._rebuild_export_devices 为每个下拉项设 Qt.ToolTipRole=数据库路径；MainWindow.update_export_range 把下拉框 toolTip 设为当前所选路径。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._rebuild_export_devices；par_app/ui.py MainWindow.update_export_range

### EXP-067 移除设备后更新导出设备列表
- 规则：移除设备后，导出设备列表随之更新。
- 来源：业务规则与变更日志_V1.0.2.md 第 328 行「P6 导出设备选择（2026-09-17）」“改名保持同一库选择，移除设备后更新列表。”
- 状态：待确认
- 现状符合度：符合（hub.devices_changed 连接 MainWindow._on_devices_changed，后者调用 _rebuild_export_devices 清空并按当前 hub.keys() 重建列表；被移除设备不再出现，原选择找不到时保留重建后的首项。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._on_devices_changed；par_app/ui.py MainWindow._rebuild_export_devices

### EXP-068 导出范围可选最近2/4/8/24小时或自定义
- 规则：导出范围可选最近 2、4、8、24 小时或自定义时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“导出范围默认最近1小时，可选最近2、4、8、24小时或自定义时间；”
- 状态：待确认
- 现状符合度：符合（MainWindow._build_settings 按 (1, 2, 4, 8, 24) 加入“最近 N 小时”并追加“自定义时间”（data "custom"）；MainWindow._current_export_range 识别 1h/2h/4h/8h/24h（fix/export-preset-window 起由 update_export_range 移入），其余按自定义处理。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._build_settings；par_app/ui.py MainWindow._current_export_range

### EXP-069 切换设备时保留自定义起止时间
- 规则：切换设备时保留自定义起止时间。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“自定义起止时间可编辑，切换设备时保留，记录数按新库重新统计。”
- 状态：待确认
- 现状符合度：符合（切换导出设备（export_device_combo.currentIndexChanged）和顶部切换查看设备（_bind_active_device）都调用 update_export_range，custom 模式下只启用控件并重新计数，不改 export_start/export_end。原文“切换设备”指哪一种未写明，两种情况现状都保留。）
- 冲突：D-116 已裁决：以第327行为准，导出区独立选择导出设备，顶部切换查看设备不改变导出统计；第236行“导出统计”和第245行“导出记录范围”标为历史
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.update_export_range；par_app/ui.py MainWindow._bind_active_device

### EXP-070 切换设备后记录数按新库重新统计
- 规则：切换设备后，记录数按新库重新统计。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“自定义起止时间可编辑，切换设备时保留，记录数按新库重新统计。”
- 状态：待确认
- 现状符合度：符合（按 D-116 裁决，“新库”指新选的导出设备库：refresh_export_count 用 _export_source() 返回的导出设备数据库调用 acquisition_export_count；顶部切换查看设备不改变 export_device_combo，与裁决一致。）
- 冲突：D-116 已裁决：以第327行为准，导出区独立选择导出设备，顶部切换查看设备不改变导出统计；第236行“导出统计”和第245行“导出记录范围”标为历史
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.refresh_export_count；par_app/ui.py MainWindow._export_source

### EXP-071 预设范围起止时间同步显示为禁用
- 规则：选择预设范围时，开始和结束两项时间同步显示为禁用状态。
- 来源：业务规则与变更日志_V1.0.2.md 第 329 行「P6 导出设备选择（2026-09-17）」“以当前北京时间为结束时间，开始时间向前推对应小时数，两项时间同步显示为禁用状态。”
- 状态：待确认
- 现状符合度：符合（预设模式下 MainWindow.update_export_range 对 export_start、export_end 调 setEnabled(False)，MainWindow._current_export_range 写入按当时北京时间计算的起止；fix/export-preset-window 起，定时刷新和导出时也同步更新显示的起止，见 EXP-051。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.update_export_range；par_app/ui.py MainWindow._current_export_range

### EXP-072 采集记录导出目录结构不变
- 规则：采集记录导出按设备/格式/日期的目录结构不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 330 行「P6 导出设备选择（2026-09-17）」“CSV/Excel格式和按设备/格式/日期的目录结构不变。”
- 状态：待确认
- 现状符合度：符合（按原文列出的目录结构核对：MainWindow.export_acquisitions 写到 <父目录>/<设备名>/<CSV|Excel>/<YYYY-MM-DD>/PAR_…_#ID.<ext>（requirements.md M10 已实现）。<设备名> 目录由 safe_database_filename 生成，Windows 保留名、控制字符和超长名的转换已修复（PR #23），被新规则改动的目录名末尾带 V1.0.2 结果的 8 位摘要，不会让 V1.0.2 下不同的两台设备共用目录而互相覆盖（tests/qt/test_export_device_folder.py），见 CONF-030。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.export_acquisitions；par_app/services/export.py device_folder；par_app/services/export.py acquisition_day_folder
