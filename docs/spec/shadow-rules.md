# 代码中的数值与常量对账（闸 4）

由 `python tools/quality/shadow_rules.py` 生成，生成时间：2026-10-16，基线提交：dd1b5a8。每一行都要在最后一列填上：对应的规格编号，或者「非业务规则：<理由>」。只跳过 0、1、-1。`check_all.py` 会用 `--check` 校验本表是否覆盖了代码中的所有数值（不比较行号），代码里新增的数值必须先加进本表。表格可以重新生成，但已填写的说明要手工合并回去，不能被覆盖。`ui.py` 中的像素和尺寸字面量大多属于「纯视觉」，留到 UI 重做时由设计 token 接管，可以批量标注。

| 文件:行 | 类型 | 名称/所在函数 | 值 | 对应规格 / 非业务规则说明 |
|---|---|---|---|---|
| par_app/app_config.py:138 | literal | save | 2 |  |
| par_app/app_info.py:14 | constant | SOFTWARE_BUILD | 2 | 非业务规则：测试版构建序号，只写入 build_manifest.json（V1.0.3 发布准备） |
| par_app/app_config.py:161 | literal | _migrate_legacy | 10.0 |  |
| par_app/app_config.py:162 | literal | _migrate_legacy | 60.0 |  |
| par_app/app_config.py:175 | literal | _read_legacy_connection_json | 5 |  |
| par_app/coordinator.py:39 | constant | DEVICE_TRANSACTION_BUDGET_SECONDS | 10.0 |  |
| par_app/coordinator.py:40 | constant | ACQUISITION_TRANSACTION_BUDGET_SECONDS | 40.0 |  |
| par_app/coordinator.py:41 | constant | MAX_CONSECUTIVE_FAILURES | 10 |  |
| par_app/coordinator.py:43 | constant | BUS_RETRY_INTERVAL_SECONDS | 5.0 |  |
| par_app/coordinator.py:44 | constant | TIME_SYNC_INTERVAL_SECONDS | 3600.0 | POLL-086 |
| par_app/coordinator.py:109 | literal | _frame_timeout | 0.8 |  |
| par_app/coordinator.py:109 | literal | _frame_timeout | 1.5 |  |
| par_app/coordinator.py:109 | literal | _frame_timeout | 4.0 |  |
| par_app/coordinator.py:174 | literal | run | 0.05 |  |
| par_app/coordinator.py:177 | literal | run | 0.1 |  |
| par_app/coordinator.py:184 | literal | run | 0.05 |  |
| par_app/coordinator.py:417 | literal | _mark_ok | 1000 |  |
| par_app/coordinator.py:478 | literal | _capture_once | 701 |  |
| par_app/coordinator.py:496 | literal | _capture_once | 1000 |  |
| par_app/coordinator.py:524 | literal | _capture_once | 1000 |  |
| par_app/coordinator.py:539 | literal | _sync_time_if_due | 2.0 |  |
| par_app/database.py:14 | literal | <module> | 8 |  |
| par_app/database.py:19 | literal | beijing_now | -3 |  |
| par_app/database.py:30 | literal | format_beijing_time | -3 |  |
| par_app/database.py:45 | literal | connect | 10 |  |
| par_app/database.py:144 | literal | load_dli_location | 116.4074 |  |
| par_app/database.py:144 | literal | load_dli_location | 39.9042 |  |
| par_app/database.py:149 | literal | load_dli_location | 116.4074 |  |
| par_app/database.py:149 | literal | load_dli_location | 39.9042 |  |
| par_app/database.py:231 | literal | save_acquisition | 0.5 |  |
| par_app/database.py:248 | literal | recent_acquisitions | 200 |  |
| par_app/database.py:271 | literal | operation_spectra | 500 |  |
| par_app/database.py:341 | literal | recent_diagnostics | 300 |  |
| par_app/device_hub.py:137 | literal | apply | 4 |  |
| par_app/device_hub.py:149 | literal | apply | 247 |  |
| par_app/device_maintenance_dialog.py:50 | literal | arrange | 6 |  |
| par_app/device_maintenance_dialog.py:54 | literal | arrange | 24 |  |
| par_app/device_maintenance_dialog.py:78 | literal | __init__ | 1080 |  |
| par_app/device_maintenance_dialog.py:78 | literal | __init__ | 820 |  |
| par_app/device_maintenance_dialog.py:79 | literal | __init__ | 580 |  |
| par_app/device_maintenance_dialog.py:79 | literal | __init__ | 740 |  |
| par_app/device_maintenance_dialog.py:82 | literal | __init__ | 24 |  |
| par_app/device_maintenance_dialog.py:84 | literal | __init__ | 8 |  |
| par_app/device_maintenance_dialog.py:87 | literal | __init__ | 180 |  |
| par_app/device_maintenance_dialog.py:88 | literal | __init__ | 240 |  |
| par_app/device_maintenance_dialog.py:100 | literal | __init__ | 100 |  |
| par_app/device_maintenance_dialog.py:128 | literal | __init__ | 180 |  |
| par_app/device_maintenance_dialog.py:129 | literal | __init__ | 56 |  |
| par_app/device_maintenance_dialog.py:160 | literal | _build_diagnostics | 16 |  |
| par_app/device_maintenance_dialog.py:197 | literal | _build_diagnostics | 2 |  |
| par_app/device_maintenance_dialog.py:197 | literal | _build_diagnostics | 3 |  |
| par_app/device_maintenance_dialog.py:200 | literal | _build_diagnostics | 32 |  |
| par_app/device_maintenance_dialog.py:201 | literal | _build_diagnostics | 100 |  |
| par_app/device_maintenance_dialog.py:209 | literal | _build_diagnostics | 20 |  |
| par_app/device_maintenance_dialog.py:210 | literal | _build_diagnostics | 32 |  |
| par_app/device_maintenance_dialog.py:211 | literal | _build_diagnostics | 20 |  |
| par_app/device_maintenance_dialog.py:216 | literal | _build_diagnostics | 10 |  |
| par_app/device_maintenance_dialog.py:216 | literal | _build_diagnostics | 30 |  |
| par_app/device_maintenance_dialog.py:243 | literal | _build_diagnostics | 200 |  |
| par_app/device_maintenance_dialog.py:243 | literal | _build_diagnostics | 300 |  |
| par_app/device_maintenance_dialog.py:459 | literal | task_finished | 65535 |  |
| par_app/device_maintenance_dialog.py:500 | literal | display_diagnostics | 2 |  |
| par_app/device_maintenance_dialog.py:506 | literal | display_diagnostics | 1000 |  |
| par_app/device_maintenance_dialog.py:514 | literal | display_diagnostics | 8 |  |
| par_app/device_maintenance_dialog.py:516 | literal | display_diagnostics | 2 |  |
| par_app/device_maintenance_dialog.py:516 | literal | display_diagnostics | 3 |  |
| par_app/device_maintenance_dialog.py:520 | literal | display_diagnostics | 3 |  |
| par_app/device_maintenance_dialog.py:524 | literal | display_diagnostics | 100 |  |
| par_app/device_maintenance_dialog.py:581 | literal | show_event_details | 460 |  |
| par_app/device_maintenance_dialog.py:581 | literal | show_event_details | 700 |  |
| par_app/device_maintenance_dialog.py:585 | literal | show_event_details | 2 |  |
| par_app/device_maintenance_dialog.py:595 | literal | filter_errors | 2 |  |
| par_app/device_maintenance_dialog.py:616 | literal | fit_error_height | 3 |  |
| par_app/device_maintenance_dialog.py:617 | literal | fit_error_height | 2 |  |
| par_app/device_maintenance_dialog.py:618 | literal | fit_error_height | 3 |  |
| par_app/device_maintenance_dialog.py:622 | literal | fit_error_height | 0.4 |  |
| par_app/device_maintenance_dialog.py:662 | literal | export_diagnostics | 100 |  |
| par_app/device_maintenance_dialog.py:667 | literal | export_diagnostics | 2 |  |
| par_app/domain/clock.py:23 | constant | BEIJING_UTC_OFFSET_HOURS | 8 | 业务时区北京时间 UTC+8（ACQ-036、EXP-037、UI-020 等以北京时间记录和显示）；与 par_app/database.py:14 同一语义，Clock 第 2 步只改了 coordinator/protocol，database 改为由本常量单一来源留待后续步骤 |
| par_app/domain/clock.py:69 | constant | NANOSECONDS_PER_SECOND | 1000000000 | 非业务规则：FakeClock（仅测试用）的单调时钟分辨率，单位换算常量 |
| par_app/domain/clock.py:70 | constant | NANOSECONDS_PER_MICROSECOND | 1000 | 非业务规则：FakeClock（仅测试用）墙钟按 datetime 的微秒分辨率显示，单位换算常量 |
| par_app/maintenance.py:13 | literal | <module> | 115200 |  |
| par_app/maintenance.py:13 | literal | <module> | 14400 |  |
| par_app/maintenance.py:13 | literal | <module> | 19200 |  |
| par_app/maintenance.py:13 | literal | <module> | 256000 |  |
| par_app/maintenance.py:13 | literal | <module> | 38400 |  |
| par_app/maintenance.py:13 | literal | <module> | 4800 |  |
| par_app/maintenance.py:13 | literal | <module> | 57600 |  |
| par_app/maintenance.py:13 | literal | <module> | 9600 |  |
| par_app/maintenance.py:47 | literal | connection | 247 |  |
| par_app/maintenance.py:78 | literal | execute | 10.0 |  |
| par_app/maintenance_dialog.py:32 | literal | __init__ | 660 |  |
| par_app/maintenance_dialog.py:35 | literal | __init__ | 10 |  |
| par_app/maintenance_dialog.py:45 | literal | __init__ | 180 |  |
| par_app/maintenance_dialog.py:47 | literal | __init__ | 12 |  |
| par_app/maintenance_dialog.py:49 | literal | __init__ | 90 |  |
| par_app/maintenance_dialog.py:51 | literal | __init__ | 10 |  |
| par_app/maintenance_dialog.py:55 | literal | __init__ | 24 |  |
| par_app/maintenance_dialog.py:66 | literal | __init__ | 8 |  |
| par_app/maintenance_dialog.py:90 | literal | __init__ | 8 |  |
| par_app/maintenance_dialog.py:99 | literal | __init__ | 24 |  |
| par_app/maintenance_dialog.py:108 | literal | __init__ | 10 |  |
| par_app/maintenance_dialog.py:131 | literal | _fields | 12 |  |
| par_app/maintenance_dialog.py:132 | literal | _fields | 8 |  |
| par_app/maintenance_dialog.py:133 | literal | _fields | 247 |  |
| par_app/maintenance_dialog.py:144 | literal | _fields | 180 |  |
| par_app/maintenance_dialog.py:145 | literal | _fields | 90 |  |
| par_app/maintenance_dialog.py:153 | literal | resizeEvent | 760 |  |
| par_app/maintenance_dialog.py:183 | literal | display_identity | 4 |  |
| par_app/math_ops.py:7 | literal | <module> | 1051 |  |
| par_app/math_ops.py:7 | literal | <module> | 350 |  |
| par_app/math_ops.py:8 | literal | <module> | 0.015 |  |
| par_app/math_ops.py:8 | literal | <module> | 0.04 |  |
| par_app/math_ops.py:8 | literal | <module> | 0.1 |  |
| par_app/math_ops.py:8 | literal | <module> | 0.62 |  |
| par_app/math_ops.py:8 | literal | <module> | 400 |  |
| par_app/math_ops.py:8 | literal | <module> | 430 |  |
| par_app/math_ops.py:8 | literal | <module> | 460 |  |
| par_app/math_ops.py:8 | literal | <module> | 500 |  |
| par_app/math_ops.py:8 | literal | <module> | 550 |  |
| par_app/math_ops.py:9 | literal | <module> | 0.006 |  |
| par_app/math_ops.py:9 | literal | <module> | 0.1 |  |
| par_app/math_ops.py:9 | literal | <module> | 0.17 |  |
| par_app/math_ops.py:9 | literal | <module> | 0.87 |  |
| par_app/math_ops.py:9 | literal | <module> | 600 |  |
| par_app/math_ops.py:9 | literal | <module> | 640 |  |
| par_app/math_ops.py:9 | literal | <module> | 665 |  |
| par_app/math_ops.py:9 | literal | <module> | 699 |  |
| par_app/math_ops.py:10 | literal | <module> | 0.04 |  |
| par_app/math_ops.py:10 | literal | <module> | 0.1 |  |
| par_app/math_ops.py:10 | literal | <module> | 0.4 |  |
| par_app/math_ops.py:10 | literal | <module> | 400 |  |
| par_app/math_ops.py:10 | literal | <module> | 430 |  |
| par_app/math_ops.py:10 | literal | <module> | 457 |  |
| par_app/math_ops.py:10 | literal | <module> | 500 |  |
| par_app/math_ops.py:10 | literal | <module> | 550 |  |
| par_app/math_ops.py:11 | literal | <module> | 0.06 |  |
| par_app/math_ops.py:11 | literal | <module> | 0.08 |  |
| par_app/math_ops.py:11 | literal | <module> | 0.35 |  |
| par_app/math_ops.py:11 | literal | <module> | 600 |  |
| par_app/math_ops.py:11 | literal | <module> | 640 |  |
| par_app/math_ops.py:11 | literal | <module> | 665 |  |
| par_app/math_ops.py:11 | literal | <module> | 699 |  |
| par_app/math_ops.py:13 | constant | PAR_STORAGE_SCALE | 10.0 | MATH-007：par、extended_par 存储值为 W/m² ÷ 10，导出经 display_metrics 乘回（旧仓库 #8 修复，2026-10-17） |
| par_app/math_ops.py:22 | literal | interpolate | 2 |  |
| par_app/math_ops.py:27 | literal | interpolate | 2 |  |
| par_app/math_ops.py:28 | literal | interpolate | 0.5 |  |
| par_app/math_ops.py:28 | literal | interpolate | 2 |  |
| par_app/math_ops.py:28 | literal | interpolate | 3 |  |
| par_app/math_ops.py:28 | literal | interpolate | 4 |  |
| par_app/math_ops.py:28 | literal | interpolate | 5 |  |
| par_app/math_ops.py:30 | literal | interpolate | 1e-09 |  |
| par_app/math_ops.py:39 | literal | software_metrics | 10.0 |  |
| par_app/math_ops.py:46 | literal | software_metrics | 0.00835934 |  |
| par_app/math_ops.py:51 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:51 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:56 | literal | software_metrics | 1050 |  |
| par_app/math_ops.py:56 | literal | software_metrics | 350 |  |
| par_app/math_ops.py:57 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:57 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:65 | literal | software_metrics | 10.0 |  |
| par_app/math_ops.py:65 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:65 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:66 | literal | software_metrics | 350 |  |
| par_app/math_ops.py:66 | literal | software_metrics | 780 |  |
| par_app/math_ops.py:68 | literal | software_metrics | 350 |  |
| par_app/math_ops.py:68 | literal | software_metrics | 399 | MATH-022（D-103：紫外上界 399 nm，与 MCU 一致） |
| par_app/math_ops.py:69 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:69 | literal | software_metrics | 499 |  |
| par_app/math_ops.py:70 | literal | software_metrics | 500 |  |
| par_app/math_ops.py:70 | literal | software_metrics | 599 |  |
| par_app/math_ops.py:71 | literal | software_metrics | 600 |  |
| par_app/math_ops.py:71 | literal | software_metrics | 699 |  |
| par_app/math_ops.py:72 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:72 | literal | software_metrics | 780 |  |
| par_app/math_ops.py:73 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:73 | literal | software_metrics | 750 |  |
| par_app/math_ops.py:74 | literal | software_metrics | 1050 |  |
| par_app/math_ops.py:74 | literal | software_metrics | 751 |  |
| par_app/math_ops.py:80 | literal | software_metrics | 10.0 |  |
| par_app/math_ops.py:80 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:80 | literal | software_metrics | 750 |  |
| par_app/math_ops.py:81 | literal | software_metrics | 1050 |  |
| par_app/math_ops.py:81 | literal | software_metrics | 350 |  |
| par_app/math_ops.py:82 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:82 | literal | software_metrics | 750 |  |
| par_app/math_ops.py:83 | literal | software_metrics | 350 |  |
| par_app/math_ops.py:83 | literal | software_metrics | 399 | MATH-022（D-103：紫外上界 399 nm，与 MCU 一致） |
| par_app/math_ops.py:84 | literal | software_metrics | 400 |  |
| par_app/math_ops.py:84 | literal | software_metrics | 499 |  |
| par_app/math_ops.py:85 | literal | software_metrics | 500 |  |
| par_app/math_ops.py:85 | literal | software_metrics | 599 |  |
| par_app/math_ops.py:86 | literal | software_metrics | 600 |  |
| par_app/math_ops.py:86 | literal | software_metrics | 699 |  |
| par_app/math_ops.py:87 | literal | software_metrics | 1050 |  |
| par_app/math_ops.py:87 | literal | software_metrics | 700 |  |
| par_app/math_ops.py:110 | literal | ratio_display_mask | 0.02 |  |
| par_app/mccree1972_weights.py:1 | table | 整表 | 46 values | McCree 1972 表，整表核对（内部文档） |
| par_app/models.py:11 | constant | MAX_DEVICES | 4 |  |
| par_app/models.py:12 | constant | DEVICE_TIMEOUT_SECONDS | 10.0 |  |
| par_app/models.py:13 | constant | MIN_POLL_CYCLE_SECONDS | 40.0 |  |
| par_app/models.py:14 | constant | MAX_POLL_CYCLE_SECONDS | 3600.0 |  |
| par_app/models.py:15 | constant | DEFAULT_BAUDRATE | 19200 |  |
| par_app/models.py:26 | literal | ConnectionConfig | 502 |  |
| par_app/models.py:30 | literal | ConnectionConfig | 0.8 |  |
| par_app/models.py:31 | literal | ConnectionConfig | 2.0 |  |
| par_app/models.py:54 | literal | BusConfig | 502 |  |
| par_app/models.py:58 | literal | BusConfig | 60.0 |  |
| par_app/models.py:91 | constant | MAX_SAFE_FILENAME_LENGTH | 100 | CONF-030：设备名转文件名的单段长度上限（字符）；D-140 缺陷修复部分，取值按审计建议（旧仓库 #11），原文未规定具体数值；取值见 内部文档 裁决 64（#23 复审 question） |
| par_app/models.py:101 | constant | FILENAME_DIGEST_LENGTH | 8 | CONF-030：被新增规则（保留名、控制字符、超长）改动的文件名末尾所接 V1.0.2 结果 SHA-256 摘要的十六进制位数，使新规则不把 V1.0.2 下不同的名称合并（#23 复审 major），原文未规定；摘要做法及 8 位取值、`COM1` 输出改为 `COM1_<摘要>`，见 内部文档 裁决 64（#23 复审 question） |
| par_app/photopic_weights.py:1 | table | 整表 | 189 values | CIE V(λ) 表，整表核对（内部文档） |
| par_app/protocol.py:65 | literal | float_from_low_high | 65535 |  |
| par_app/protocol.py:73 | literal | uint64_from_low_words | 16 |  |
| par_app/protocol.py:73 | literal | uint64_from_low_words | 4 |  |
| par_app/protocol.py:73 | literal | uint64_from_low_words | 65535 |  |
| par_app/protocol.py:77 | literal | uint64_to_low_words | 16 |  |
| par_app/protocol.py:77 | literal | uint64_to_low_words | 4 |  |
| par_app/protocol.py:77 | literal | uint64_to_low_words | 65535 |  |
| par_app/protocol.py:81 | literal | crc16_modbus | 65535 |  |
| par_app/protocol.py:84 | literal | crc16_modbus | 8 |  |
| par_app/protocol.py:86 | literal | crc16_modbus | 40961 |  |
| par_app/protocol.py:89 | literal | crc16_modbus | 65535 |  |
| par_app/protocol.py:95 | constant | _READ_RETRY_COUNT | 3 |  |
| par_app/protocol.py:96 | constant | _READ_RETRY_DELAY_SECONDS | 0.25 |  |
| par_app/protocol.py:98 | constant | _INTER_REQUEST_DELAY_SECONDS | 0.1 |  |
| par_app/protocol.py:145 | literal | _packet_budget | 0.001 |  |
| par_app/protocol.py:164 | literal | _drain_late_response | 0.001 |  |
| par_app/protocol.py:166 | literal | _drain_late_response | 0.0001 |  |
| par_app/protocol.py:166 | literal | _drain_late_response | 0.02 |  |
| par_app/protocol.py:177 | literal | _io_timeout | 0.001 |  |
| par_app/protocol.py:190 | literal | _delay | 0.02 |  |
| par_app/protocol.py:206 | literal | _build_client | 8 |  |
| par_app/protocol.py:217 | literal | connect | 8 |  |
| par_app/protocol.py:220 | literal | connect | 0.02 |  |
| par_app/protocol.py:255 | literal | _read_input_chunked | 125 |  |
| par_app/protocol.py:255 | literal | _read_input_chunked | 19200 |  |
| par_app/protocol.py:255 | literal | _read_input_chunked | 64 |  |
| par_app/protocol.py:272 | literal | _read_registers | 3 |  |
| par_app/protocol.py:272 | literal | _read_registers | 4 |  |
| par_app/protocol.py:280 | literal | _read_registers | 10 | POLL-007（D-101 静默判据：Modbus 异常码 0x0A/0x0B 由网关代答目标无应答，不计为该设备的有效帧） |
| par_app/protocol.py:280 | literal | _read_registers | 11 | POLL-007（D-101 静默判据：Modbus 异常码 0x0A/0x0B 由网关代答目标无应答，不计为该设备的有效帧） |
| par_app/protocol.py:306 | literal | _write_register | 10 | POLL-007（D-101 静默判据：Modbus 异常码 0x0A/0x0B 由网关代答目标无应答，不计为该设备的有效帧） |
| par_app/protocol.py:306 | literal | _write_register | 11 | POLL-007（D-101 静默判据：Modbus 异常码 0x0A/0x0B 由网关代答目标无应答，不计为该设备的有效帧） |
| par_app/protocol.py:316 | literal | _rtu_frame | 255 |  |
| par_app/protocol.py:318 | literal | _rtu_frame | 255 |  |
| par_app/protocol.py:318 | literal | _rtu_frame | 8 |  |
| par_app/protocol.py:346 | literal | _rtu_exchange | 0.0001 |  |
| par_app/protocol.py:346 | literal | _rtu_exchange | 0.02 |  |
| par_app/protocol.py:360 | literal | _rtu_exchange | 5 |  |
| par_app/protocol.py:362 | literal | _rtu_exchange | 128 |  |
| par_app/protocol.py:364 | literal | _rtu_exchange | -2 |  |
| par_app/protocol.py:365 | literal | _rtu_exchange | -2 |  |
| par_app/protocol.py:365 | literal | _rtu_exchange | 8 |  |
| par_app/protocol.py:369 | literal | _rtu_exchange | 255 |  |
| par_app/protocol.py:371 | literal | _rtu_exchange | 128 |  |
| par_app/protocol.py:372 | literal | _rtu_exchange | 2 |  |
| par_app/protocol.py:378 | literal | _rtu_read_registers | 65535 |  |
| par_app/protocol.py:379 | literal | _rtu_read_registers | 2 |  |
| par_app/protocol.py:381 | literal | _rtu_read_registers | 2 |  |
| par_app/protocol.py:382 | literal | _rtu_read_registers | 2 |  |
| par_app/protocol.py:383 | literal | _rtu_read_registers | 2 |  |
| par_app/protocol.py:383 | literal | _rtu_read_registers | 3 |  |
| par_app/protocol.py:383 | literal | _rtu_read_registers | 5 |  |
| par_app/protocol.py:386 | literal | _rtu_write_single | 65535 |  |
| par_app/protocol.py:387 | literal | _rtu_write_single | 6 |  |
| par_app/protocol.py:387 | literal | _rtu_write_single | 8 |  |
| par_app/protocol.py:388 | literal | _rtu_write_single | 2 |  |
| par_app/protocol.py:388 | literal | _rtu_write_single | 6 |  |
| par_app/protocol.py:392 | literal | _rtu_write_multiple | 65535 |  |
| par_app/protocol.py:393 | literal | _rtu_write_multiple | 65535 |  |
| par_app/protocol.py:394 | literal | _rtu_write_multiple | 16 |  |
| par_app/protocol.py:394 | literal | _rtu_write_multiple | 8 |  |
| par_app/protocol.py:395 | literal | _rtu_write_multiple | 65535 |  |
| par_app/protocol.py:396 | literal | _rtu_write_multiple | 2 |  |
| par_app/protocol.py:396 | literal | _rtu_write_multiple | 6 |  |
| par_app/protocol.py:401 | literal | read_status | 59 |  |
| par_app/protocol.py:402 | literal | read_status | 400 |  |
| par_app/protocol.py:402 | literal | read_status | 76 |  |
| par_app/protocol.py:403 | literal | read_status | 58 |  |
| par_app/protocol.py:404 | literal | read_status | 58 |  |
| par_app/protocol.py:404 | literal | read_status | 62 |  |
| par_app/protocol.py:406 | literal | read_status | 53 |  |
| par_app/protocol.py:406 | literal | read_status | 75 |  |
| par_app/protocol.py:407 | literal | read_status | 54 |  |
| par_app/protocol.py:407 | literal | read_status | 55 |  |
| par_app/protocol.py:408 | literal | read_status | 255 |  |
| par_app/protocol.py:408 | literal | read_status | 8 |  |
| par_app/protocol.py:409 | literal | read_status | 52 |  |
| par_app/protocol.py:410 | literal | read_status | 74 |  |
| par_app/protocol.py:415 | literal | verify_par_signature | 59 |  |
| par_app/protocol.py:416 | literal | verify_par_signature | 400 |  |
| par_app/protocol.py:416 | literal | verify_par_signature | 76 |  |
| par_app/protocol.py:417 | literal | verify_par_signature | 58 |  |
| par_app/protocol.py:418 | literal | verify_par_signature | 58 |  |
| par_app/protocol.py:418 | literal | verify_par_signature | 62 |  |
| par_app/protocol.py:420 | literal | verify_par_signature | 255 |  |
| par_app/protocol.py:421 | literal | verify_par_signature | 15 |  |
| par_app/protocol.py:421 | literal | verify_par_signature | 8 |  |
| par_app/protocol.py:422 | literal | verify_par_signature | 2 |  |
| par_app/protocol.py:422 | literal | verify_par_signature | 52 |  |
| par_app/protocol.py:423 | literal | verify_par_signature | 53 |  |
| par_app/protocol.py:424 | literal | verify_par_signature | 54 |  |
| par_app/protocol.py:425 | literal | verify_par_signature | 55 |  |
| par_app/protocol.py:426 | literal | verify_par_signature | 74 |  |
| par_app/protocol.py:427 | literal | verify_par_signature | 120000000 |  |
| par_app/protocol.py:432 | literal | read_device_identity | 11 |  |
| par_app/protocol.py:432 | literal | read_device_identity | 2047 |  |
| par_app/protocol.py:433 | literal | read_device_identity | 16 |  |
| par_app/protocol.py:433 | literal | read_device_identity | 65535 |  |
| par_app/protocol.py:435 | literal | read_device_identity | 3 |  |
| par_app/protocol.py:436 | literal | read_device_identity | 255 |  |
| par_app/protocol.py:436 | literal | read_device_identity | 8 |  |
| par_app/protocol.py:438 | literal | read_device_identity | 2 |  |
| par_app/protocol.py:438 | literal | read_device_identity | 65535 |  |
| par_app/protocol.py:444 | literal | read_diagnostics | 2006 |  |
| par_app/protocol.py:444 | literal | read_diagnostics | 52 |  |
| par_app/protocol.py:445 | literal | read_diagnostics | 44 |  |
| par_app/protocol.py:445 | literal | read_diagnostics | 52 |  |
| par_app/protocol.py:448 | literal | read_diagnostics | 37 |  |
| par_app/protocol.py:448 | literal | read_diagnostics | 39 |  |
| par_app/protocol.py:449 | literal | read_diagnostics | 8 |  |
| par_app/protocol.py:450 | literal | read_diagnostics | 13 |  |
| par_app/protocol.py:450 | literal | read_diagnostics | 27 |  |
| par_app/protocol.py:452 | literal | read_diagnostics | 16 |  |
| par_app/protocol.py:452 | literal | read_diagnostics | 41 |  |
| par_app/protocol.py:452 | literal | read_diagnostics | 42 |  |
| par_app/protocol.py:453 | literal | read_diagnostics | 43 |  |
| par_app/protocol.py:461 | literal | set_stop | 25 |  |
| par_app/protocol.py:462 | literal | set_stop | 6 |  |
| par_app/protocol.py:464 | literal | set_stop | 25 |  |
| par_app/protocol.py:466 | literal | wait_stop | 2.0 |  |
| par_app/protocol.py:475 | literal | wait_stop | 0.04 |  |
| par_app/protocol.py:483 | literal | read_spectrum_transaction | 10.0 |  |
| par_app/protocol.py:484 | literal | read_spectrum_transaction | 2.0 |  |
| par_app/protocol.py:490 | literal | read_spectrum_transaction | 1000 |  |
| par_app/protocol.py:490 | literal | read_spectrum_transaction | 701 |  |
| par_app/protocol.py:491 | literal | read_spectrum_transaction | 1701 |  |
| par_app/protocol.py:491 | literal | read_spectrum_transaction | 54 |  |
| par_app/protocol.py:492 | literal | read_spectrum_transaction | 2 |  |
| par_app/protocol.py:503 | literal | read_spectrum_transaction | 2.0 |  |
| par_app/protocol.py:515 | literal | sync_time | 2.0 |  |
| par_app/protocol.py:516 | literal | sync_time | 1000 |  |
| par_app/protocol.py:517 | literal | sync_time | 32 |  |
| par_app/protocol.py:518 | literal | sync_time | 36 |  |
| par_app/protocol.py:521 | literal | sync_time | 2 |  |
| par_app/protocol.py:521 | literal | sync_time | 36 |  |
| par_app/protocol.py:523 | literal | sync_time | 1000 |  |
| par_app/protocol.py:524 | literal | sync_time | 32 |  |
| par_app/protocol.py:525 | literal | sync_time | 3 |  |
| par_app/protocol.py:525 | literal | sync_time | 36 |  |
| par_app/protocol.py:527 | literal | sync_time | 0.03 |  |
| par_app/protocol.py:531 | literal | sync_time | 36 |  |
| par_app/protocol.py:533 | literal | sync_time | 0.03 |  |
| par_app/protocol.py:538 | literal | read_standard_time | 32 |  |
| par_app/protocol.py:538 | literal | read_standard_time | 4 |  |
| par_app/protocol.py:542 | literal | read_mcu_comm | 29 |  |
| par_app/protocol.py:542 | literal | read_mcu_comm | 3 |  |
| par_app/protocol.py:543 | literal | read_mcu_comm | 2 |  |
| par_app/protocol.py:543 | literal | read_mcu_comm | 247 |  |
| par_app/protocol.py:543 | literal | read_mcu_comm | 7 |  |
| par_app/protocol.py:548 | literal | read_calibration | 3 |  |
| par_app/protocol.py:548 | literal | read_calibration | 39 |  |
| par_app/protocol.py:549 | literal | read_calibration | 40 |  |
| par_app/protocol.py:549 | literal | read_calibration | 66 |  |
| par_app/protocol.py:550 | literal | read_calibration | 4 |  |
| par_app/protocol.py:553 | literal | read_calibration | 28 |  |
| par_app/protocol.py:553 | literal | read_calibration | 39 |  |
| par_app/protocol.py:557 | literal | read_calibration | 2 |  |
| par_app/protocol.py:563 | literal | write_calibration | 3 |  |
| par_app/protocol.py:566 | literal | write_calibration | 39 |  |
| par_app/protocol.py:567 | literal | write_calibration | 40 |  |
| par_app/protocol.py:567 | literal | write_calibration | 88 |  |
| par_app/protocol.py:568 | literal | write_calibration | 2.0 |  |
| par_app/protocol.py:568 | literal | write_calibration | 3 |  |
| par_app/protocol.py:568 | literal | write_calibration | 4 |  |
| par_app/protocol.py:569 | literal | write_calibration | 3 |  |
| par_app/protocol.py:573 | literal | _wait_calibration | 2.0 |  |
| par_app/protocol.py:576 | literal | _wait_calibration | 244 |  |
| par_app/protocol.py:576 | literal | _wait_calibration | 7 |  |
| par_app/protocol.py:577 | literal | _wait_calibration | 16 |  |
| par_app/protocol.py:577 | literal | _wait_calibration | 2 |  |
| par_app/protocol.py:577 | literal | _wait_calibration | 3 |  |
| par_app/protocol.py:578 | literal | _wait_calibration | 4 |  |
| par_app/protocol.py:578 | literal | _wait_calibration | 5 |  |
| par_app/protocol.py:578 | literal | _wait_calibration | 6 |  |
| par_app/protocol.py:581 | literal | _wait_calibration | 0.04 |  |
| par_app/protocol.py:585 | literal | change_mcu_comm | 29 |  |
| par_app/release_self_test.py:43 | literal | run_release_self_test | 1230 |  |
| par_app/release_self_test.py:43 | literal | run_release_self_test | 740 |  |
| par_app/release_self_test.py:49 | literal | run_release_self_test | 3 |  |
| par_app/release_self_test.py:56 | literal | run_release_self_test | 150 |  |
| par_app/release_self_test.py:71 | literal | run_release_self_test | 2 |  |
| par_app/rtu_frames.py:12 | literal | <module> | 10 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。网关代答“目标设备无响应”异常码 0x0A，不计为该设备的有效帧） |
| par_app/rtu_frames.py:12 | literal | <module> | 11 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。网关代答“目标设备无响应”异常码 0x0B，不计为该设备的有效帧） |
| par_app/rtu_frames.py:21 | literal | count_slave_frames | 128 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。0x80 为异常应答标志） |
| par_app/rtu_frames.py:21 | literal | count_slave_frames | 2 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。下标 2 为异常码字节） |
| par_app/rtu_frames.py:23 | literal | count_slave_frames | 5 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。最短 RTU 应答帧 5 字节） |
| par_app/rtu_frames.py:25 | literal | count_slave_frames | 128 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。0x80 为异常应答标志） |
| par_app/rtu_frames.py:26 | literal | count_slave_frames | 5 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。异常应答帧长 5 字节） |
| par_app/rtu_frames.py:27 | literal | count_slave_frames | 3 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:27 | literal | count_slave_frames | 4 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:28 | literal | count_slave_frames | 5 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。读应答帧长 = 5 + 字节数） |
| par_app/rtu_frames.py:28 | literal | count_slave_frames | 2 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。下标 2 为读应答字节数） |
| par_app/rtu_frames.py:30 | literal | count_slave_frames | 8 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:30 | literal | count_slave_frames | 6 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:30 | literal | count_slave_frames | 16 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:33 | literal | count_slave_frames | 128 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。0x80 为异常应答标志） |
| par_app/rtu_frames.py:33 | literal | count_slave_frames | 2 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。下标 2 为异常码字节） |
| par_app/rtu_frames.py:42 | literal | _is_slave_frame | 5 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。最短 RTU 应答帧 5 字节） |
| par_app/rtu_frames.py:43 | literal | _is_slave_frame | 255 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。从站地址取低 8 位，与 ParModbusClient._rtu_frame 一致） |
| par_app/rtu_frames.py:44 | literal | _is_slave_frame | -2 | POLL-007（D-101 静默判据，阶段一裁决 37；PR #29 复审修复：在丢弃或解析失败的字节里按 Modbus RTU 帧格式找本从站 CRC 正确的应答帧。末 2 字节为 CRC（低字节在前）） |
| par_app/rtu_frames.py:13 | constant | WRITE_ECHO_BYTES | 8 |（设备协议细节，公开版略）|
| par_app/rtu_frames.py:14 | constant | REMEMBERED_FRAMES | 2 | ACQ-025（#132，负责人 2026-10-29 书面批准：晚到的写回显从应答中分出）。记住最近两帧不等回显发出的帧：补发恢复后紧跟停止时为两帧（D-101） |
| par_app/rtu_frames.py:15 | constant | EXCEPTION_REPLY_BYTES | 5 | ACQ-025（#132，负责人 2026-10-29 书面批准：晚到的写回显从应答中分出）。异常应答 5 字节，原在 ParModbusClient._rtu_exchange 的收完判断里 |
| par_app/rtu_frames.py:73 | literal | complete | 128 | ACQ-025（#132，负责人 2026-10-29 书面批准：晚到的写回显从应答中分出）。0x80 为异常应答标志，原在 ParModbusClient._rtu_exchange 的收完判断里 |
| par_app/services/calibration.py:56 | constant | PERCENT_SCALE | 100 | UI-127/MAINT-040：y0–y4、limit_min、limit_max 以百分比显示（协议比例 ×100）；原为 ui.py MainWindow._build_calibration 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:58 | constant | FIELD_LIMIT | 1000000 | MAINT-101：每个字段的输入范围 ±1000000（协议单位），回读超出即整包无效；百分比字段上相当于 ±1 亿 %，实际无约束，见 D-175；原为 ui.py MainWindow._build_calibration 的 setRange 字面量（_apply_hardware_calibration 经 field.minimum()/maximum() 使用），本次只搬移并命名 |
| par_app/services/calibration.py:61 | constant | CURVE_POINTS | 701 | 非业务规则：校准预览曲线在 P0–P4 间的采样点数；原为 ui.py CalibrationCanvas.draw_calibration 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:63 | constant | PREVIEW_MIN_NM | 350.0 | UI-133 横轴范围；拖拽止点规格未单列（P0 拖拽止于 350 nm，见 D-177）；原为 ui.py CalibrationCanvas._on_motion 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:64 | constant | PREVIEW_MAX_NM | 1050.0 | UI-133 横轴范围；拖拽止点规格未单列（P4 拖拽止于 1050 nm，见 D-177）；原为 ui.py CalibrationCanvas._on_motion 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:65 | constant | NODE_MIN_SPACING_NM | 1.0 | 规格未单列（拖拽交互细节，见 D-177）：拖拽节点与相邻节点至少相隔 1 nm；相邻节点间距不足 2 nm 时节点顺序被破坏，见 D-173；原为 ui.py CalibrationCanvas._on_motion 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:67 | constant | PICK_X_SPAN_NM | 700 | 非业务规则：拖拽拾取距离的横向归一化跨度（700 nm）；原为 ui.py CalibrationCanvas._on_press 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:69 | constant | PICK_RADIUS | 0.04 | 非业务规则：拖拽拾取半径（归一化距离 < 0.04）；原为 ui.py CalibrationCanvas._on_press 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:71 | constant | MCU_TIMESTAMP_MAX | 4294967295 | UI-129/MAINT-042：MCU 校准时间为 32 位 Unix 秒，1–0xFFFFFFFF 之外显示“未设置 / 无效时间戳”；原为 ui.py MainWindow._format_mcu_timestamp 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:72 | constant | VERSION_NODES_MAX | 255 | MAINT-143：version_nodes 仅为 0–255 的整数时解码，否则显示“—”；原为 ui.py MainWindow._task_finished 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:73 | constant | NODE_COUNT_MASK | 15 | MAINT-143：version_nodes 低 4 位为节点数；原为 ui.py MainWindow._task_finished 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:74 | constant | VERSION_SHIFT | 4 | MAINT-143：version_nodes 高 4 位为版本；原为 ui.py MainWindow._task_finished 字面量，本次只搬移并命名 |
| par_app/services/calibration.py:150 | literal | pchip | 5 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:151 | literal | pchip | 4 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:155 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:157 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:158 | literal | pchip | -2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:158 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:161 | literal | pchip | 3 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:165 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:165 | literal | pchip | 3 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:166 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:166 | literal | pchip | 3 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:167 | literal | pchip | -2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:167 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:167 | literal | pchip | 3 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:168 | literal | pchip | 2 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:168 | literal | pchip | 3 | 非业务规则：PCHIP 预览插值的固定结构（5 个节点、内部节点下标 1–3、末段下标 3、端点三点公式与 Hermite 基函数系数）；端点导数未限幅、与 MCU 是否一致见 D-172；原在 ui.py CalibrationCanvas._pchip，本次只搬移 |
| par_app/services/calibration.py:192 | literal | correction_curve | 100.0 | UI-127：协议比例换算为百分比（×100）；原在 ui.py CalibrationCanvas.draw_calibration，本次只搬移 |
| par_app/services/calibration.py:193 | literal | correction_curve | 100.0 | UI-127：协议比例换算为百分比（×100）；原在 ui.py CalibrationCanvas.draw_calibration，本次只搬移 |
| par_app/services/calibration.py:194 | literal | correction_curve | 100.0 | UI-127：协议比例换算为百分比（×100）；原在 ui.py CalibrationCanvas.draw_calibration，本次只搬移 |
| par_app/services/calibration.py:195 | literal | correction_curve | 100.0 | UI-127：协议比例换算为百分比（×100）；原在 ui.py CalibrationCanvas.draw_calibration，本次只搬移 |
| par_app/services/calibration.py:214 | literal | node_values | 100 | MAINT-038/MAINT-040：节点修正在协议比例与百分比之间换算（×100 / ÷100）；原在 ui.py MainWindow._calibration_nodes_changed，本次只搬移 |
| par_app/services/calibration.py:218 | literal | node_values | 100.0 | MAINT-038/MAINT-040：节点修正在协议比例与百分比之间换算（×100 / ÷100）；原在 ui.py MainWindow._calibration_nodes_changed，本次只搬移 |
| par_app/services/dli.py:31 | constant | MIN_MAX_GAP_SECONDS | 120.0 | DLI-010：允许间隔 max(120 秒, 周期+60 秒) 的下限；原为 ui.py refresh_diagnostics 字面量，本次只搬移并命名 |
| par_app/services/dli.py:33 | constant | POLL_CYCLE_GAP_MARGIN_SECONDS | 60.0 | DLI-010/DLI-013：允许间隔 = 当前轮询周期 + 60 秒；原为 ui.py refresh_diagnostics 字面量，本次只搬移并命名 |
| par_app/services/dli.py:80 | literal | sunrise | 2 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的谐波阶数与 2π；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:80 | literal | sunrise | 365 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）的年长（分数年 γ）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:81 | literal | sunrise | 229.18 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）的时差系数（分钟/弧度）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:82 | literal | sunrise | 7.5e-05 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:83 | literal | sunrise | 0.001868 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:84 | literal | sunrise | 0.032077 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:85 | literal | sunrise | 0.014615 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:85 | literal | sunrise | 2 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的谐波阶数与 2π；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:86 | literal | sunrise | 0.040849 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:86 | literal | sunrise | 2 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的谐波阶数与 2π；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:89 | literal | sunrise | 0.006918 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:90 | literal | sunrise | 0.399912 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:91 | literal | sunrise | 0.070257 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:92 | literal | sunrise | 0.006758 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:92 | literal | sunrise | 2 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的谐波阶数与 2π；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:93 | literal | sunrise | 0.000907 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:93 | literal | sunrise | 2 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的谐波阶数与 2π；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:94 | literal | sunrise | 0.002697 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:94 | literal | sunrise | 3 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的三阶谐波；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:95 | literal | sunrise | 0.00148 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）系数（时差/赤纬级数）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:95 | literal | sunrise | 3 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中的三阶谐波；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:97 | literal | sunrise | 90.833 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）的日出天顶角（含大气折射与日面半径）；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:101 | literal | sunrise | 4 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中每度经度 4 分钟；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:101 | literal | sunrise | 480 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中 UTC+8 的 480 分钟偏移；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:101 | literal | sunrise | 720 | DLI-015/DLI-026：NOAA 近似日出公式（UTC+8）中正午 720 分钟；原在 ui.py MainWindow._sunrise，本次只搬移 |
| par_app/services/dli.py:113 | literal | dli_period | -2 | DLI-015：候选日出取 d-2..d+1。sunrise 固定按 UTC+8 换算，日出相对日历日 d 偏移约 -4 h～+32 h，d-2 是能覆盖全部合法经度的最早候选日（旧审计 #23，PR #26；原在 ui.py MainWindow._dli_period，集成时随 services 抽离落到此处） |
| par_app/services/dli.py:200 | literal | _accumulate | 2000000.0 | DLI-008/DLI-030：梯形 (a+b)·Δt/2 与 µmol→mol（÷1e6）合并为 ÷2e6；原在 ui.py DliCanvas.plot_dli，本次只搬移 |
| par_app/services/export.py:205 | literal | brand_image | 112 | 非业务规则：纯视觉（品牌图片在 Excel 中的显示宽度，像素）；原在 ui.py MainWindow._brand_excel_image，本次只搬移 |
| par_app/services/export.py:205 | literal | brand_image | 54 | 非业务规则：纯视觉（品牌图片在 Excel 中的显示高度，像素）；原在 ui.py MainWindow._brand_excel_image，本次只搬移 |
| par_app/services/export.py:252 | literal | write_acquisition_file | 36 | 非业务规则：纯视觉（采集记录 Excel A 列宽）；原在 ui.py MainWindow._write_export_file，本次只搬移 |
| par_app/services/export.py:253 | literal | write_acquisition_file | 46 | 非业务规则：纯视觉（采集记录 Excel B 列宽）；原在 ui.py MainWindow._write_export_file，本次只搬移 |
| par_app/services/export.py:254 | literal | write_acquisition_file | 64 | 非业务规则：纯视觉（采集记录 Excel C 列宽）；原在 ui.py MainWindow._write_export_file，本次只搬移 |
| par_app/services/export.py:400 | literal | _fill_operation_data_sheet | 90 | 非业务规则：纯视觉（计算数据表缩放 90%）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:401 | literal | _fill_operation_data_sheet | 48 | 非业务规则：纯视觉（计算数据表表头行高）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:402 | literal | _fill_operation_data_sheet | 12 | 非业务规则：纯视觉（计算数据表列宽）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:402 | literal | _fill_operation_data_sheet | 19 | 非业务规则：纯视觉（计算数据表列宽）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:402 | literal | _fill_operation_data_sheet | 20 | 非业务规则：纯视觉（计算数据表列宽）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:402 | literal | _fill_operation_data_sheet | 22 | 非业务规则：纯视觉（计算数据表列宽 / 数据行行高）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:404 | literal | _fill_operation_data_sheet | 64 | 非业务规则：chr(64 + 序号) 把 1 起的列序号换成列字母（ASCII 64 = '@'）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:407 | literal | _fill_operation_data_sheet | 22 | 非业务规则：纯视觉（计算数据表列宽 / 数据行行高）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:409 | literal | _fill_operation_data_sheet | 11 | 非业务规则：纯视觉（Excel 字号 11）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:415 | literal | _fill_operation_data_sheet | 5 | EXP-032：第 5 列起（低信号标记、结果有效标记）按整数格式显示；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:417 | literal | _fill_operation_data_sheet | 1000000.0 | EXP-031：绝对值 ≥ 1000000 用科学计数法；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:417 | literal | _fill_operation_data_sheet | 1e-06 | EXP-031：绝对值 < 0.000001 用科学计数法；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:428 | literal | _fill_operation_details_sheet | 34 | 非业务规则：纯视觉（计算说明表 A 列宽 / 最小行高，EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:429 | literal | _fill_operation_details_sheet | 100 | 非业务规则：纯视觉（计算说明表 B 列宽）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:433 | literal | _fill_operation_details_sheet | 11 | 非业务规则：纯视觉（Excel 字号 11）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:440 | literal | _fill_operation_details_sheet | 127 | 非业务规则：说明表行高估算中 ASCII 上限，码位 > 127 的字符按 2 个宽度计（EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:440 | literal | _fill_operation_details_sheet | 2 | 非业务规则：说明表行高估算中宽字符计 2 个宽度（EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:441 | literal | _fill_operation_details_sheet | 12 | 非业务规则：说明表行高估算 20 × 行数 + 12（EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:441 | literal | _fill_operation_details_sheet | 20 | 非业务规则：说明表行高估算每行 20（EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:441 | literal | _fill_operation_details_sheet | 34 | 非业务规则：纯视觉（计算说明表 A 列宽 / 最小行高，EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:441 | literal | _fill_operation_details_sheet | 85 | 非业务规则：说明表行高估算每 85 个宽度折一行（EXP-064 的视觉实现）；原在 ui.py MainWindow._write_operation_file，本次只搬移 |
| par_app/services/export.py:480 | literal | export_operation_files | 3 | 非业务规则：MainWindow.current_result 元组下标 3 = 运算；原在 ui.py MainWindow.export_operation_results，本次只搬移 |
| par_app/services/export.py:480 | literal | export_operation_files | 4 | 非业务规则：MainWindow.current_result 元组下标 4 = A 记录；原在 ui.py MainWindow.export_operation_results，本次只搬移 |
| par_app/services/export.py:480 | literal | export_operation_files | 5 | 非业务规则：MainWindow.current_result 元组下标 5 = B 记录；原在 ui.py MainWindow.export_operation_results，本次只搬移 |
| par_app/services/metrics.py:31 | constant | PAR_DISPLAY_FACTOR | 10 | par 显示 = 存储值 ×10：V1.0.2 现状，口径受 R-4-2 红线第 4 条（PAR ÷10）约束，规格未单列条目；extended_par 沿用同一口径见 MATH-007 |
| par_app/services/metrics.py:40 | literal | <module> | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:41 | literal | <module> | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:42 | literal | <module> | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:43 | literal | <module> | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:44 | literal | <module> | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:64 | literal | cct_value | 0.5 | UI-304（CCT 四舍五入取整）；MATH-004 |
| par_app/services/metrics.py:68 | literal | format_metric | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:91 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:92 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:93 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:94 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:95 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:96 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:97 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:98 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:99 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:100 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:101 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:102 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:103 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:104 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:105 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:106 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:107 | literal | record_metric_values | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:107 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:108 | literal | record_metric_values | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:108 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:109 | literal | record_metric_values | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:109 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:111 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:112 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:114 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:116 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:117 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:118 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:119 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:120 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:121 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:124 | literal | record_metric_values | 16 | UI-018（R1–R15，range 上界） |
| par_app/services/metrics.py:125 | literal | record_metric_values | 3 | 显示精度：V1.0.2 现状默认 3 位小数（见 UI-017 现状符合度），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:125 | literal | record_metric_values | 4 | UI-017（u/v/x/y 4 位小数） |
| par_app/services/metrics.py:171 | literal | overview_metric_entries | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:172 | literal | overview_metric_entries | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/services/metrics.py:173 | literal | overview_metric_entries | 100 | V1.0.2 现状：标签单位为“%”的三项比例（蓝光、红光占 PPFD，远红光占扩展 PPFD）乘 100 显示为百分数；规格未单列条目（这三项属于 UI-018 的 54 项与概览 24 项），原在 ui.py，本次只搬移 |
| par_app/slot_errors.py:39 | constant | LABEL_MAX_CHARS | 80 | 非业务规则：状态栏常驻错误标签首行的截断长度，完整内容在悬停提示，纯显示 |
| par_app/ui.py:68 | literal | paintEvent | 17 |  |
| par_app/ui.py:69 | literal | paintEvent | 2 |  |
| par_app/ui.py:71 | literal | paintEvent | 3 |  |
| par_app/ui.py:71 | literal | paintEvent | 4 |  |
| par_app/ui.py:71 | literal | paintEvent | 5 |  |
| par_app/ui.py:73 | literal | paintEvent | 3 |  |
| par_app/ui.py:73 | literal | paintEvent | 4 |  |
| par_app/ui.py:73 | literal | paintEvent | 5 |  |
| par_app/ui.py:122 | literal | showPopup | 640 |  |
| par_app/ui.py:123 | literal | showPopup | 48 |  |
| par_app/ui.py:144 | literal | paintEvent | 2 |  |
| par_app/ui.py:144 | literal | paintEvent | 4 |  |
| par_app/ui.py:145 | literal | paintEvent | 2 |  |
| par_app/ui.py:276 | literal | __init__ | 4 |  |
| par_app/ui.py:276 | literal | __init__ | 7 |  |
| par_app/ui.py:277 | literal | __init__ | 111 |  |
| par_app/ui.py:282 | literal | __init__ | 0.66 |  |
| par_app/ui.py:292 | literal | draw | 0.015 |  |
| par_app/ui.py:292 | literal | draw | 0.99 |  |
| par_app/ui.py:295 | literal | set_status_card | 0.66 |  |
| par_app/ui.py:323 | literal | _draw_status_card | 9 |  |
| par_app/ui.py:326 | literal | _draw_status_card | 0.718 |  |
| par_app/ui.py:326 | literal | _draw_status_card | 1.018 |  |
| par_app/ui.py:328 | literal | _draw_status_card | 10 |  |
| par_app/ui.py:331 | literal | _draw_status_card | 0.992 |  |
| par_app/ui.py:331 | literal | _draw_status_card | 1.018 |  |
| par_app/ui.py:333 | literal | _draw_status_card | 10 |  |
| par_app/ui.py:353 | literal | _draw_core_metrics_card | 2 |  |
| par_app/ui.py:361 | literal | _draw_core_metrics_card | 5 |  |
| par_app/ui.py:365 | literal | _draw_core_metrics_card | 0.5 |  |
| par_app/ui.py:365 | literal | _draw_core_metrics_card | 1.5 |  |
| par_app/ui.py:366 | literal | _draw_core_metrics_card | 14 |  |
| par_app/ui.py:367 | literal | _draw_core_metrics_card | 0.4 |  |
| par_app/ui.py:367 | literal | _draw_core_metrics_card | 0.5 |  |
| par_app/ui.py:368 | literal | _draw_core_metrics_card | 0.74 |  |
| par_app/ui.py:369 | literal | _draw_core_metrics_card | 10 |  |
| par_app/ui.py:377 | literal | _wavelength_to_rgb | 380 |  |
| par_app/ui.py:377 | literal | _wavelength_to_rgb | 780 |  |
| par_app/ui.py:378 | literal | _wavelength_to_rgb | 0.55 |  |
| par_app/ui.py:379 | literal | _wavelength_to_rgb | 440 |  |
| par_app/ui.py:380 | literal | _wavelength_to_rgb | 440 |  |
| par_app/ui.py:380 | literal | _wavelength_to_rgb | 60 |  |
| par_app/ui.py:381 | literal | _wavelength_to_rgb | 490 |  |
| par_app/ui.py:382 | literal | _wavelength_to_rgb | 440 |  |
| par_app/ui.py:382 | literal | _wavelength_to_rgb | 50 |  |
| par_app/ui.py:383 | literal | _wavelength_to_rgb | 510 |  |
| par_app/ui.py:384 | literal | _wavelength_to_rgb | 20 |  |
| par_app/ui.py:384 | literal | _wavelength_to_rgb | 510 |  |
| par_app/ui.py:385 | literal | _wavelength_to_rgb | 580 |  |
| par_app/ui.py:386 | literal | _wavelength_to_rgb | 510 |  |
| par_app/ui.py:386 | literal | _wavelength_to_rgb | 70 |  |
| par_app/ui.py:387 | literal | _wavelength_to_rgb | 645 |  |
| par_app/ui.py:388 | literal | _wavelength_to_rgb | 645 |  |
| par_app/ui.py:388 | literal | _wavelength_to_rgb | 65 |  |
| par_app/ui.py:391 | literal | _wavelength_to_rgb | 420 |  |
| par_app/ui.py:392 | literal | _wavelength_to_rgb | 0.3 |  |
| par_app/ui.py:392 | literal | _wavelength_to_rgb | 0.7 |  |
| par_app/ui.py:392 | literal | _wavelength_to_rgb | 380 |  |
| par_app/ui.py:392 | literal | _wavelength_to_rgb | 40 |  |
| par_app/ui.py:393 | literal | _wavelength_to_rgb | 700 |  |
| par_app/ui.py:394 | literal | _wavelength_to_rgb | 0.3 |  |
| par_app/ui.py:394 | literal | _wavelength_to_rgb | 0.7 |  |
| par_app/ui.py:394 | literal | _wavelength_to_rgb | 780 |  |
| par_app/ui.py:394 | literal | _wavelength_to_rgb | 80 |  |
| par_app/ui.py:409 | literal | _add_colored_spectrum | 1.15 |  |
| par_app/ui.py:419 | literal | _normalized_curve | 2 |  |
| par_app/ui.py:424 | literal | _normalized_curve | 2 |  |
| par_app/ui.py:425 | literal | _normalized_curve | 0.5 |  |
| par_app/ui.py:425 | literal | _normalized_curve | 2 |  |
| par_app/ui.py:425 | literal | _normalized_curve | 3 |  |
| par_app/ui.py:425 | literal | _normalized_curve | 4 |  |
| par_app/ui.py:425 | literal | _normalized_curve | 5 |  |
| par_app/ui.py:427 | literal | _normalized_curve | 1e-09 |  |
| par_app/ui.py:432 | literal | _draw_response_overlays | 400 |  |
| par_app/ui.py:432 | literal | _draw_response_overlays | 700 |  |
| par_app/ui.py:437 | literal | _draw_response_overlays | 1e-09 |  |
| par_app/ui.py:438 | literal | _draw_response_overlays | 0.95 |  |
| par_app/ui.py:438 | literal | _draw_response_overlays | 1.6 |  |
| par_app/ui.py:439 | literal | _draw_response_overlays | 0.95 |  |
| par_app/ui.py:439 | literal | _draw_response_overlays | 1.6 |  |
| par_app/ui.py:440 | literal | _draw_response_overlays | 0.95 |  |
| par_app/ui.py:440 | literal | _draw_response_overlays | 1.7 |  |
| par_app/ui.py:441 | literal | _draw_response_overlays | 360 |  |
| par_app/ui.py:441 | literal | _draw_response_overlays | 831 |  |
| par_app/ui.py:443 | literal | _draw_response_overlays | 0.95 |  |
| par_app/ui.py:443 | literal | _draw_response_overlays | 1.6 |  |
| par_app/ui.py:445 | literal | _draw_response_overlays | 1050 |  |
| par_app/ui.py:445 | literal | _draw_response_overlays | 350 |  |
| par_app/ui.py:447 | literal | _draw_response_overlays | 1.5 |  |
| par_app/ui.py:449 | literal | _draw_response_overlays | 12 |  |
| par_app/ui.py:449 | literal | _draw_response_overlays | 13 |  |
| par_app/ui.py:454 | literal | _draw_response_overlays | 5 |  |
| par_app/ui.py:454 | literal | _draw_response_overlays | 9 |  |
| par_app/ui.py:463 | literal | _draw_response_overlays | 0.5 |  |
| par_app/ui.py:463 | literal | _draw_response_overlays | 9 |  |
| par_app/ui.py:464 | literal | _draw_response_overlays | 0.5 |  |
| par_app/ui.py:464 | literal | _draw_response_overlays | 0.92 |  |
| par_app/ui.py:469 | literal | plot | 1050 |  |
| par_app/ui.py:469 | literal | plot | 350 |  |
| par_app/ui.py:471 | literal | plot | 0.94 |  |
| par_app/ui.py:478 | literal | plot | 0.5 |  |
| par_app/ui.py:478 | literal | plot | 0.52 |  |
| par_app/ui.py:480 | literal | plot | 14 |  |
| par_app/ui.py:481 | literal | plot | 0.43 |  |
| par_app/ui.py:481 | literal | plot | 0.5 |  |
| par_app/ui.py:483 | literal | plot | 10 |  |
| par_app/ui.py:485 | literal | plot | 12 |  |
| par_app/ui.py:485 | literal | plot | 14 |  |
| par_app/ui.py:492 | literal | plot | 1.2 |  |
| par_app/ui.py:494 | literal | plot | 0.2 |  |
| par_app/ui.py:494 | literal | plot | 0.55 |  |
| par_app/ui.py:501 | literal | plot | 15 |  |
| par_app/ui.py:501 | literal | plot | 18 |  |
| par_app/ui.py:502 | literal | plot | 10 |  |
| par_app/ui.py:502 | literal | plot | 12 |  |
| par_app/ui.py:503 | literal | plot | 12 |  |
| par_app/ui.py:503 | literal | plot | 13 |  |
| par_app/ui.py:516 | literal | plot | 0.08 |  |
| par_app/ui.py:516 | literal | plot | 1e-09 |  |
| par_app/ui.py:520 | literal | plot | 0.618 |  |
| par_app/ui.py:520 | literal | plot | 1e-09 |  |
| par_app/ui.py:521 | literal | plot | 0.25 |  |
| par_app/ui.py:523 | literal | plot | 10 |  |
| par_app/ui.py:546 | literal | __init__ | 14 |  |
| par_app/ui.py:552 | literal | __init__ | 4 |  |
| par_app/ui.py:552 | literal | __init__ | 8 |  |
| par_app/ui.py:553 | literal | __init__ | 6 |  |
| par_app/ui.py:555 | literal | __init__ | 11 |  |
| par_app/ui.py:571 | literal | __init__ | 11 |  |
| par_app/ui.py:572 | literal | __init__ | 32 |  |
| par_app/ui.py:584 | literal | align_to_charts | 12 |  |
| par_app/ui.py:585 | literal | align_to_charts | 16 |  |
| par_app/ui.py:587 | literal | align_to_charts | 8 |  |
| par_app/ui.py:594 | literal | show_details | 0.9 |  |
| par_app/ui.py:594 | literal | show_details | 760 |  |
| par_app/ui.py:594 | literal | show_details | 960 |  |
| par_app/ui.py:595 | literal | show_details | 11 |  |
| par_app/ui.py:598 | literal | show_details | 11 |  |
| par_app/ui.py:601 | literal | show_details | 11 |  |
| par_app/ui.py:603 | literal | show_details | 14 |  |
| par_app/ui.py:702 | literal | __init__ | 4 |  |
| par_app/ui.py:702 | literal | __init__ | 7 |  |
| par_app/ui.py:703 | literal | __init__ | 111 |  |
| par_app/ui.py:711 | literal | _duration | 60 |  |
| par_app/ui.py:712 | literal | _duration | 60 |  |
| par_app/ui.py:753 | literal | _plot_left_margin | 100.0 |  |
| par_app/ui.py:754 | literal | _plot_left_margin | 64 |  |
| par_app/ui.py:755 | literal | _plot_left_margin | 20 |  |
| par_app/ui.py:761 | literal | _layout_plot | 3 |  |
| par_app/ui.py:761 | literal | _layout_plot | 6 |  |
| par_app/ui.py:761 | literal | _layout_plot | 700 |  |
| par_app/ui.py:766 | literal | _layout_plot | 7200 |  |
| par_app/ui.py:775 | literal | _layout_plot | 9 |  |
| par_app/ui.py:787 | literal | _layout_plot | 100.0 |  |
| par_app/ui.py:789 | literal | _layout_plot | 0.3 |  |
| par_app/ui.py:790 | literal | _layout_plot | 18 |  |
| par_app/ui.py:791 | literal | _layout_plot | 0.45 |  |
| par_app/ui.py:791 | literal | _layout_plot | 59 |  |
| par_app/ui.py:792 | literal | _layout_plot | 0.15 |  |
| par_app/ui.py:792 | literal | _layout_plot | 12 |  |
| par_app/ui.py:803 | literal | _layout_plot | -0.26 |  |
| par_app/ui.py:804 | literal | _layout_plot | 0.55 |  |
| par_app/ui.py:804 | literal | _layout_plot | 85 |  |
| par_app/ui.py:806 | literal | _layout_plot | 210 |  |
| par_app/ui.py:806 | literal | _layout_plot | 236 |  |
| par_app/ui.py:815 | literal | plot_dli | 120.0 |  |
| par_app/ui.py:870 | literal | plot_dli | 2.2 |  |
| par_app/ui.py:871 | literal | plot_dli | 0.12 |  |
| par_app/ui.py:873 | literal | plot_dli | 0.5 |  |
| par_app/ui.py:877 | literal | plot_dli | 10 |  |
| par_app/ui.py:878 | literal | plot_dli | 10 |  |
| par_app/ui.py:879 | literal | plot_dli | 0.25 |  |
| par_app/ui.py:880 | literal | plot_dli | 9 |  |
| par_app/ui.py:881 | literal | plot_dli | 0.001 |  |
| par_app/ui.py:881 | literal | plot_dli | 1.15 |  |
| par_app/ui.py:918 | literal | arrange | 1038 |  |
| par_app/ui.py:919 | literal | arrange | 262 |  |
| par_app/ui.py:930 | literal | arrange | 16 |  |
| par_app/ui.py:930 | literal | arrange | 246 |  |
| par_app/ui.py:934 | literal | arrange | 16 |  |
| par_app/ui.py:935 | literal | arrange | 16 |  |
| par_app/ui.py:950 | literal | __init__ | 1.02 |  |
| par_app/ui.py:950 | literal | __init__ | 3 |  |
| par_app/ui.py:950 | literal | __init__ | 6 |  |
| par_app/ui.py:951 | literal | __init__ | 111 |  |
| par_app/ui.py:954 | literal | __init__ | 2 |  |
| par_app/ui.py:957 | literal | __init__ | -20.0 |  |
| par_app/ui.py:957 | literal | __init__ | 20.0 |  |
| par_app/ui.py:1008 | literal | draw_calibration | 2.0 |  |
| par_app/ui.py:1010 | literal | draw_calibration | 3 |  |
| par_app/ui.py:1010 | literal | draw_calibration | 8 |  |
| par_app/ui.py:1012 | literal | draw_calibration | -5 |  |
| par_app/ui.py:1012 | literal | draw_calibration | 4 |  |
| par_app/ui.py:1012 | literal | draw_calibration | 5 |  |
| par_app/ui.py:1012 | literal | draw_calibration | 7 |  |
| par_app/ui.py:1013 | literal | draw_calibration | 4 |  |
| par_app/ui.py:1013 | literal | draw_calibration | 9 |  |
| par_app/ui.py:1015 | literal | draw_calibration | 0.6 |  |
| par_app/ui.py:1018 | literal | draw_calibration | 0.8 |  |
| par_app/ui.py:1021 | literal | draw_calibration | 0.12 |  |
| par_app/ui.py:1021 | literal | draw_calibration | 2.0 |  |
| par_app/ui.py:1024 | literal | draw_calibration | 13 |  |
| par_app/ui.py:1024 | literal | draw_calibration | 24 |  |
| par_app/ui.py:1025 | literal | draw_calibration | 10 |  |
| par_app/ui.py:1026 | literal | draw_calibration | 10 |  |
| par_app/ui.py:1027 | literal | draw_calibration | 0.25 |  |
| par_app/ui.py:1029 | literal | draw_calibration | 9 |  |
| par_app/ui.py:1030 | literal | draw_calibration | 1.01 |  |
| par_app/ui.py:1031 | literal | draw_calibration | 1.2 |  |
| par_app/ui.py:1031 | literal | draw_calibration | 3 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 1000 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 1050 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 350 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 400 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 500 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 600 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 700 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 800 |  |
| par_app/ui.py:1035 | literal | _set_wavelength_ticks | 900 |  |
| par_app/ui.py:1036 | literal | _set_wavelength_ticks | 680 |  |
| par_app/ui.py:1037 | literal | _set_wavelength_ticks | 1000 |  |
| par_app/ui.py:1037 | literal | _set_wavelength_ticks | 400 |  |
| par_app/ui.py:1039 | literal | _set_wavelength_ticks | 1050 |  |
| par_app/ui.py:1039 | literal | _set_wavelength_ticks | 350 |  |
| par_app/ui.py:1042 | literal | resizeEvent | 5 |  |
| par_app/ui.py:1047 | literal | _on_press | 5 |  |
| par_app/ui.py:1087 | literal | paintEvent | 2 |  |
| par_app/ui.py:1087 | literal | paintEvent | 3 |  |
| par_app/ui.py:1103 | literal | __init__ | 1380 |  |
| par_app/ui.py:1103 | literal | __init__ | 860 |  |
| par_app/ui.py:1117 | literal | __init__ | 8 |  |
| par_app/ui.py:1141 | literal | __init__ | 3000 |  |
| par_app/ui.py:1171 | literal | _build_device_bar | 18 |  |
| par_app/ui.py:1171 | literal | _build_device_bar | 8 |  |
| par_app/ui.py:1172 | literal | _build_device_bar | 32 |  |
| par_app/ui.py:1175 | literal | _build_device_bar | 8 |  |
| par_app/ui.py:1178 | literal | _build_device_bar | 6 |  |
| par_app/ui.py:1183 | literal | _build_device_bar | 12 |  |
| par_app/ui.py:1191 | literal | _build_device_bar | 300 |  |
| par_app/ui.py:1192 | literal | _build_device_bar | 320 |  |
| par_app/ui.py:1230 | literal | _style_device_buttons | 42 |  |
| par_app/ui.py:1244 | literal | _style_device_buttons | 180 |  |
| par_app/ui.py:1244 | literal | _style_device_buttons | 42 |  |
| par_app/ui.py:1245 | literal | _style_device_buttons | 24 |  |
| par_app/ui.py:1245 | literal | _style_device_buttons | 42 |  |
| par_app/ui.py:1259 | literal | _update_device_bar_layout | 300 |  |
| par_app/ui.py:1259 | literal | _update_device_bar_layout | 320 |  |
| par_app/ui.py:1261 | literal | _update_device_bar_layout | 16777215 |  |
| par_app/ui.py:1268 | literal | _update_device_bar_layout | 2 |  |
| par_app/ui.py:1270 | literal | _update_device_bar_layout | 68 |  |
| par_app/ui.py:1271 | literal | _update_device_bar_layout | 1180 |  |
| par_app/ui.py:1277 | literal | _update_device_bar_layout | 2 |  |
| par_app/ui.py:1280 | literal | _update_device_bar_layout | 2 |  |
| par_app/ui.py:1402 | literal | _reset_calibration | 2 |  |
| par_app/ui.py:1444 | literal | _render_comm_values | 2 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 115200 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 14400 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 19200 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 256000 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 38400 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 4800 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 57600 |  |
| par_app/ui.py:1477 | literal | _accept_settings_comm | 9600 |  |
| par_app/ui.py:1480 | literal | _accept_settings_comm | 247 |  |
| par_app/ui.py:1480 | literal | _accept_settings_comm | 3 |  |
| par_app/ui.py:1633 | literal | _apply_responsive_layout | 1280 |  |
| par_app/ui.py:1633 | literal | _apply_responsive_layout | 800 |  |
| par_app/ui.py:1638 | literal | _apply_responsive_layout | 22 |  |
| par_app/ui.py:1638 | literal | _apply_responsive_layout | 26 |  |
| par_app/ui.py:1639 | literal | _apply_responsive_layout | 2 |  |
| par_app/ui.py:1639 | literal | _apply_responsive_layout | 6 |  |
| par_app/ui.py:1660 | literal | _spectrum_view_controls | 16 |  |
| par_app/ui.py:1661 | literal | _spectrum_view_controls | 12 |  |
| par_app/ui.py:1665 | literal | _spectrum_view_controls | 1050 |  |
| par_app/ui.py:1665 | literal | _spectrum_view_controls | 350 |  |
| par_app/ui.py:1666 | literal | _spectrum_view_controls | 400 |  |
| par_app/ui.py:1666 | literal | _spectrum_view_controls | 700 |  |
| par_app/ui.py:1684 | literal | _spectrum_view_controls | 10 |  |
| par_app/ui.py:1685 | literal | _spectrum_view_controls | 30 |  |
| par_app/ui.py:1688 | literal | _spectrum_view_controls | 10 |  |
| par_app/ui.py:1691 | literal | _spectrum_view_controls | 24 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 1000 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 1050 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 350 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 400 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 500 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 600 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 700 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 800 |  |
| par_app/ui.py:1703 | literal | _plot_selected_spectrum | 900 |  |
| par_app/ui.py:1713 | literal | _plot_selected_spectrum | 0.65 |  |
| par_app/ui.py:1714 | literal | _plot_selected_spectrum | 2 |  |
| par_app/ui.py:1715 | literal | _plot_selected_spectrum | 3 |  |
| par_app/ui.py:1715 | literal | _plot_selected_spectrum | 30 |  |
| par_app/ui.py:1718 | literal | _plot_selected_spectrum | 3 |  |
| par_app/ui.py:1728 | literal | _plot_selected_spectrum | 14 |  |
| par_app/ui.py:1728 | literal | _plot_selected_spectrum | 6 |  |
| par_app/ui.py:1729 | literal | _plot_selected_spectrum | 8 |  |
| par_app/ui.py:1730 | literal | _plot_selected_spectrum | 0.015 |  |
| par_app/ui.py:1730 | literal | _plot_selected_spectrum | 0.99 |  |
| par_app/ui.py:1735 | literal | _build_overview | 14 |  |
| par_app/ui.py:1735 | literal | _build_overview | 16 |  |
| par_app/ui.py:1735 | literal | _build_overview | 18 |  |
| par_app/ui.py:1735 | literal | _build_overview | 8 |  |
| par_app/ui.py:1736 | literal | _build_overview | 6 |  |
| par_app/ui.py:1736 | literal | _build_overview | 8 |  |
| par_app/ui.py:1744 | literal | _build_overview | 10 |  |
| par_app/ui.py:1747 | literal | _build_overview | 6 |  |
| par_app/ui.py:1748 | literal | _build_overview | 28 |  |
| par_app/ui.py:1756 | literal | _build_overview | 12 |  |
| par_app/ui.py:1756 | literal | _build_overview | 8 |  |
| par_app/ui.py:1759 | literal | _build_overview | 8 |  |
| par_app/ui.py:1760 | literal | _build_overview | 8 |  |
| par_app/ui.py:1763 | literal | _build_overview | 30 |  |
| par_app/ui.py:1782 | literal | _build_overview | 8 |  |
| par_app/ui.py:1794 | literal | _build_overview | 10 |  |
| par_app/ui.py:1794 | literal | _build_overview | 6 |  |
| par_app/ui.py:1794 | literal | _build_overview | 7 |  |
| par_app/ui.py:1807 | literal | _build_overview | 2 |  |
| par_app/ui.py:1821 | literal | _build_overview | 11 |  |
| par_app/ui.py:1838 | literal | _build_overview | 8 |  |
| par_app/ui.py:1847 | literal | _build_overview | 10 |  |
| par_app/ui.py:1852 | literal | _build_overview | 12 |  |
| par_app/ui.py:1878 | literal | _show_overview_metric_details | 0.9 |  |
| par_app/ui.py:1878 | literal | _show_overview_metric_details | 720 |  |
| par_app/ui.py:1878 | literal | _show_overview_metric_details | 760 |  |
| par_app/ui.py:1880 | literal | _show_overview_metric_details | 3 |  |
| par_app/ui.py:1887 | literal | _show_overview_metric_details | 2 |  |
| par_app/ui.py:1891 | literal | _show_overview_metric_details | 3 |  |
| par_app/ui.py:1924 | literal | _align_overview_metrics | 1500 |  |
| par_app/ui.py:1924 | literal | _align_overview_metrics | 3 |  |
| par_app/ui.py:1924 | literal | _align_overview_metrics | 6 |  |
| par_app/ui.py:1929 | literal | _align_overview_metrics | 6 |  |
| par_app/ui.py:1933 | literal | _align_overview_metrics | 8 |  |
| par_app/ui.py:1938 | literal | _align_overview_metrics | 4 |  |
| par_app/ui.py:1939 | literal | _align_overview_metrics | 4 |  |
| par_app/ui.py:1942 | literal | _align_overview_metrics | 0.76 |  |
| par_app/ui.py:1944 | literal | _align_overview_metrics | 2 |  |
| par_app/ui.py:1945 | literal | _align_overview_metrics | 2 |  |
| par_app/ui.py:1951 | literal | _align_overview_metrics | 16777215 |  |
| par_app/ui.py:1955 | literal | _build_history | 650 |  |
| par_app/ui.py:1957 | literal | _build_history | 7 |  |
| par_app/ui.py:1957 | literal | _build_history | 9 |  |
| par_app/ui.py:1958 | literal | _build_history | 6 |  |
| par_app/ui.py:1962 | literal | _build_history | 16 |  |
| par_app/ui.py:1963 | literal | _build_history | 4 |  |
| par_app/ui.py:1968 | literal | _build_history | 500 |  |
| par_app/ui.py:1978 | literal | _build_history | 28 |  |
| par_app/ui.py:1980 | literal | _build_history | 32 |  |
| par_app/ui.py:1982 | literal | _build_history | 32 |  |
| par_app/ui.py:1985 | literal | _build_history | 10 |  |
| par_app/ui.py:1986 | literal | _build_history | 32 |  |
| par_app/ui.py:1989 | literal | _build_history | 40 |  |
| par_app/ui.py:2008 | literal | _build_history | 5 |  |
| par_app/ui.py:2009 | literal | _build_history | 5 |  |
| par_app/ui.py:2014 | literal | _build_history | 10 |  |
| par_app/ui.py:2015 | literal | _build_history | 28 |  |
| par_app/ui.py:2023 | literal | _build_history | 210 |  |
| par_app/ui.py:2023 | literal | _build_history | 50 |  |
| par_app/ui.py:2023 | literal | _build_history | 60 |  |
| par_app/ui.py:2023 | literal | _build_history | 80 |  |
| par_app/ui.py:2029 | literal | _build_history | 16 |  |
| par_app/ui.py:2030 | literal | _build_history | 2 |  |
| par_app/ui.py:2048 | literal | _build_history | 12 |  |
| par_app/ui.py:2048 | literal | _build_history | 6 |  |
| par_app/ui.py:2049 | literal | _build_history | 4 |  |
| par_app/ui.py:2056 | literal | _build_history | 12 |  |
| par_app/ui.py:2056 | literal | _build_history | 6 |  |
| par_app/ui.py:2057 | literal | _build_history | 4 |  |
| par_app/ui.py:2067 | literal | _build_history | 8 |  |
| par_app/ui.py:2068 | literal | _build_history | 6 |  |
| par_app/ui.py:2073 | literal | _build_history | 6 |  |
| par_app/ui.py:2083 | literal | _build_history | 6 |  |
| par_app/ui.py:2134 | literal | _build_history | 16 |  |
| par_app/ui.py:2152 | literal | _build_history | 3 |  |
| par_app/ui.py:2172 | literal | _build_history | 3 |  |
| par_app/ui.py:2177 | literal | _build_history | 3 |  |
| par_app/ui.py:2190 | literal | _build_history | 8 |  |
| par_app/ui.py:2196 | literal | _build_history | 10 |  |
| par_app/ui.py:2200 | literal | _build_history | 12 |  |
| par_app/ui.py:2209 | literal | _build_history | 600 |  |
| par_app/ui.py:2210 | literal | _build_history | 230 |  |
| par_app/ui.py:2211 | literal | _build_history | 298 |  |
| par_app/ui.py:2212 | literal | _build_history | 310 |  |
| par_app/ui.py:2212 | literal | _build_history | 360 |  |
| par_app/ui.py:2237 | literal | _layout_history_details | 24 |  |
| par_app/ui.py:2250 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2253 | literal | _layout_history_details | 12 |  |
| par_app/ui.py:2258 | literal | _layout_history_details | 12 |  |
| par_app/ui.py:2262 | literal | _layout_history_details | 12 |  |
| par_app/ui.py:2266 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2268 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2274 | literal | _layout_history_details | 3 |  |
| par_app/ui.py:2275 | literal | _layout_history_details | 24 |  |
| par_app/ui.py:2276 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2276 | literal | _layout_history_details | 24 |  |
| par_app/ui.py:2277 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2277 | literal | _layout_history_details | 24 |  |
| par_app/ui.py:2280 | literal | _layout_history_details | 24 |  |
| par_app/ui.py:2288 | literal | _layout_history_details | 9 |  |
| par_app/ui.py:2291 | literal | _layout_history_details | 3 |  |
| par_app/ui.py:2292 | literal | _layout_history_details | 8 |  |
| par_app/ui.py:2293 | literal | _layout_history_details | 16 |  |
| par_app/ui.py:2293 | literal | _layout_history_details | 4 |  |
| par_app/ui.py:2296 | literal | _layout_history_details | 2 |  |
| par_app/ui.py:2296 | literal | _layout_history_details | 3 |  |
| par_app/ui.py:2296 | literal | _layout_history_details | 5 |  |
| par_app/ui.py:2297 | literal | _layout_history_details | 5 |  |
| par_app/ui.py:2300 | literal | _layout_history_details | 4 |  |
| par_app/ui.py:2320 | literal | _size_history_header | 10000 |  |
| par_app/ui.py:2322 | literal | _size_history_header | 16 |  |
| par_app/ui.py:2322 | literal | _size_history_header | 46 |  |
| par_app/ui.py:2332 | literal | _align_history_table | 8 |  |
| par_app/ui.py:2335 | literal | _align_history_table | 10 |  |
| par_app/ui.py:2345 | literal | _align_history_table | 2 |  |
| par_app/ui.py:2351 | literal | _align_history_table | 2 |  |
| par_app/ui.py:2355 | literal | _align_history_table | 190 |  |
| par_app/ui.py:2355 | literal | _align_history_table | 45 |  |
| par_app/ui.py:2355 | literal | _align_history_table | 55 |  |
| par_app/ui.py:2355 | literal | _align_history_table | 65 |  |
| par_app/ui.py:2360 | literal | _align_history_table | 12 |  |
| par_app/ui.py:2361 | literal | _align_history_table | 2 |  |
| par_app/ui.py:2362 | literal | _align_history_table | 16 |  |
| par_app/ui.py:2375 | literal | _build_operations | 10 |  |
| par_app/ui.py:2385 | literal | _build_operations | 30 |  |
| par_app/ui.py:2390 | literal | _build_operations | 12 |  |
| par_app/ui.py:2391 | literal | _build_operations | 8 |  |
| par_app/ui.py:2393 | literal | _build_operations | 4 |  |
| par_app/ui.py:2397 | literal | _build_operations | 16 |  |
| par_app/ui.py:2398 | literal | _build_operations | 32 |  |
| par_app/ui.py:2408 | literal | _build_operations | 16 |  |
| par_app/ui.py:2410 | literal | _build_operations | 13 |  |
| par_app/ui.py:2413 | literal | _build_operations | 3 |  |
| par_app/ui.py:2417 | literal | _build_operations | 124 |  |
| par_app/ui.py:2417 | literal | _build_operations | 64 |  |
| par_app/ui.py:2418 | literal | _build_operations | 36 |  |
| par_app/ui.py:2421 | literal | _build_operations | 10 |  |
| par_app/ui.py:2425 | literal | _build_operations | 17 |  |
| par_app/ui.py:2427 | literal | _build_operations | 38 |  |
| par_app/ui.py:2427 | literal | _build_operations | 44 |  |
| par_app/ui.py:2434 | literal | _build_operations | 24 |  |
| par_app/ui.py:2441 | literal | _build_operations | 1050 |  |
| par_app/ui.py:2441 | literal | _build_operations | 350 |  |
| par_app/ui.py:2446 | literal | _build_operations | 20 |  |
| par_app/ui.py:2451 | literal | _build_operations | 11 |  |
| par_app/ui.py:2452 | literal | _build_operations | 36 |  |
| par_app/ui.py:2454 | literal | _build_operations | 54 |  |
| par_app/ui.py:2459 | literal | _build_operations | 11 |  |
| par_app/ui.py:2461 | literal | _build_operations | 12 |  |
| par_app/ui.py:2462 | literal | _build_operations | 36 |  |
| par_app/ui.py:2477 | literal | _build_operations | 600 |  |
| par_app/ui.py:2496 | literal | _update_operation_toolbar_layout | 96 |  |
| par_app/ui.py:2497 | literal | _update_operation_toolbar_layout | 18 |  |
| par_app/ui.py:2497 | literal | _update_operation_toolbar_layout | 64 |  |
| par_app/ui.py:2627 | literal | _operation_item | 701 |  |
| par_app/ui.py:2636 | literal | _build_calibration | 10 |  |
| par_app/ui.py:2637 | literal | _build_calibration | 8 |  |
| par_app/ui.py:2641 | literal | _build_calibration | 16 |  |
| par_app/ui.py:2644 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2649 | literal | _build_calibration | 3 |  |
| par_app/ui.py:2649 | literal | _build_calibration | 5 |  |
| par_app/ui.py:2649 | literal | _build_calibration | 7 |  |
| par_app/ui.py:2649 | literal | _build_calibration | 8 |  |
| par_app/ui.py:2651 | literal | _build_calibration | 9 |  |
| par_app/ui.py:2653 | literal | _build_calibration | 2 |  |
| par_app/ui.py:2653 | literal | _build_calibration | 3 |  |
| par_app/ui.py:2654 | literal | _build_calibration | 3 |  |
| par_app/ui.py:2654 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2657 | literal | _build_calibration | 8 |  |
| par_app/ui.py:2658 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2664 | literal | _build_calibration | 100 |  |
| par_app/ui.py:2664 | literal | _build_calibration | 2 |  |
| par_app/ui.py:2664 | literal | _build_calibration | 4 |  |
| par_app/ui.py:2668 | literal | _build_calibration | 10 |  |
| par_app/ui.py:2669 | literal | _build_calibration | 112 |  |
| par_app/ui.py:2677 | literal | _build_calibration | 2 |  |
| par_app/ui.py:2678 | literal | _build_calibration | 4 |  |
| par_app/ui.py:2679 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2680 | literal | _build_calibration | 8 |  |
| par_app/ui.py:2681 | literal | _build_calibration | 2 |  |
| par_app/ui.py:2681 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2682 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2692 | literal | _build_calibration | 2 |  |
| par_app/ui.py:2695 | literal | _build_calibration | 310 |  |
| par_app/ui.py:2696 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2706 | literal | _build_calibration | 4 |  |
| par_app/ui.py:2706 | literal | _build_calibration | 5 |  |
| par_app/ui.py:2709 | literal | _build_calibration | 3 |  |
| par_app/ui.py:2710 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2711 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2723 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2740 | literal | _build_calibration | 6 |  |
| par_app/ui.py:2745 | literal | _build_calibration | 24 |  |
| par_app/ui.py:2766 | literal | _build_calibration | 320 |  |
| par_app/ui.py:2792 | literal | _refresh_calibration_plots | 13 |  |
| par_app/ui.py:2792 | literal | _refresh_calibration_plots | 24 |  |
| par_app/ui.py:2793 | literal | _refresh_calibration_plots | 0.5 |  |
| par_app/ui.py:2838 | literal | _calibration_nodes_changed | 100 |  |
| par_app/ui.py:2848 | literal | _build_diagnostics | 10 |  |
| par_app/ui.py:2848 | literal | _build_diagnostics | 18 |  |
| par_app/ui.py:2848 | literal | _build_diagnostics | 8 |  |
| par_app/ui.py:2849 | literal | _build_diagnostics | 8 |  |
| par_app/ui.py:2851 | literal | _build_diagnostics | 24 |  |
| par_app/ui.py:2852 | literal | _build_diagnostics | 8 |  |
| par_app/ui.py:2854 | literal | _build_diagnostics | -89.9 |  |
| par_app/ui.py:2854 | literal | _build_diagnostics | 4 |  |
| par_app/ui.py:2854 | literal | _build_diagnostics | 89.9 |  |
| par_app/ui.py:2855 | literal | _build_diagnostics | -180.0 |  |
| par_app/ui.py:2855 | literal | _build_diagnostics | 180.0 |  |
| par_app/ui.py:2855 | literal | _build_diagnostics | 4 |  |
| par_app/ui.py:2863 | literal | _build_diagnostics | 8 |  |
| par_app/ui.py:2865 | literal | _build_diagnostics | 130 |  |
| par_app/ui.py:2865 | literal | _build_diagnostics | 44 |  |
| par_app/ui.py:2866 | literal | _build_diagnostics | 32 |  |
| par_app/ui.py:2871 | literal | _build_diagnostics | 32 |  |
| par_app/ui.py:2879 | literal | _build_diagnostics | 10 |  |
| par_app/ui.py:2892 | literal | _build_diagnostics | 16 |  |
| par_app/ui.py:2893 | literal | _build_diagnostics | 10 |  |
| par_app/ui.py:2899 | literal | _build_diagnostics | 2 |  |
| par_app/ui.py:2903 | literal | _build_diagnostics | 12 |  |
| par_app/ui.py:2903 | literal | _build_diagnostics | 4 |  |
| par_app/ui.py:2904 | literal | _build_diagnostics | 16 |  |
| par_app/ui.py:2905 | literal | _build_diagnostics | 2 |  |
| par_app/ui.py:2919 | literal | _build_diagnostics | 3 |  |
| par_app/ui.py:2921 | literal | _build_diagnostics | 2 |  |
| par_app/ui.py:2923 | literal | _build_diagnostics | 210 |  |
| par_app/ui.py:2925 | literal | _build_diagnostics | 2 |  |
| par_app/ui.py:2928 | literal | _build_diagnostics | 2 |  |
| par_app/ui.py:2938 | literal | _layout_dli_page | 18 |  |
| par_app/ui.py:2939 | literal | _layout_dli_page | 10 |  |
| par_app/ui.py:2939 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2939 | literal | _layout_dli_page | 8 |  |
| par_app/ui.py:2940 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2942 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2942 | literal | _layout_dli_page | 24 |  |
| par_app/ui.py:2942 | literal | _layout_dli_page | 3 |  |
| par_app/ui.py:2942 | literal | _layout_dli_page | 48 |  |
| par_app/ui.py:2948 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2956 | literal | _layout_dli_page | 4 |  |
| par_app/ui.py:2959 | literal | _layout_dli_page | 16 |  |
| par_app/ui.py:2974 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2975 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2977 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:2978 | literal | _layout_dli_page | 2 |  |
| par_app/ui.py:3025 | literal | _build_settings | 20 |  |
| par_app/ui.py:3025 | literal | _build_settings | 28 |  |
| par_app/ui.py:3025 | literal | _build_settings | 8 |  |
| par_app/ui.py:3036 | literal | _build_settings | 6 |  |
| par_app/ui.py:3039 | literal | _build_settings | 4 |  |
| par_app/ui.py:3040 | literal | _build_settings | 6 |  |
| par_app/ui.py:3046 | literal | _build_settings | 4 |  |
| par_app/ui.py:3054 | literal | _build_settings | 115200 |  |
| par_app/ui.py:3054 | literal | _build_settings | 14400 |  |
| par_app/ui.py:3054 | literal | _build_settings | 19200 |  |
| par_app/ui.py:3054 | literal | _build_settings | 256000 |  |
| par_app/ui.py:3054 | literal | _build_settings | 38400 |  |
| par_app/ui.py:3054 | literal | _build_settings | 4800 |  |
| par_app/ui.py:3054 | literal | _build_settings | 57600 |  |
| par_app/ui.py:3054 | literal | _build_settings | 9600 |  |
| par_app/ui.py:3061 | literal | _build_settings | 2 |  |
| par_app/ui.py:3066 | literal | _build_settings | 2 |  |
| par_app/ui.py:3067 | literal | _build_settings | 8 |  |
| par_app/ui.py:3068 | literal | _build_settings | 6 |  |
| par_app/ui.py:3070 | literal | _build_settings | 105 |  |
| par_app/ui.py:3071 | literal | _build_settings | 2 |  |
| par_app/ui.py:3073 | literal | _build_settings | 2 |  |
| par_app/ui.py:3081 | literal | _build_settings | 2 |  |
| par_app/ui.py:3086 | literal | _build_settings | 4 |  |
| par_app/ui.py:3087 | literal | _build_settings | 65535 |  |
| par_app/ui.py:3099 | literal | _build_settings | 6 |  |
| par_app/ui.py:3100 | literal | _build_settings | 8 |  |
| par_app/ui.py:3108 | literal | _build_settings | 105 |  |
| par_app/ui.py:3123 | literal | _build_settings | 4 |  |
| par_app/ui.py:3124 | literal | _build_settings | 5 |  |
| par_app/ui.py:3129 | literal | _build_settings | 36 |  |
| par_app/ui.py:3133 | literal | _build_settings | 2 |  |
| par_app/ui.py:3134 | literal | _build_settings | 3 |  |
| par_app/ui.py:3135 | literal | _build_settings | 130 |  |
| par_app/ui.py:3136 | literal | _build_settings | 80 |  |
| par_app/ui.py:3137 | literal | _build_settings | 2 |  |
| par_app/ui.py:3137 | literal | _build_settings | 88 |  |
| par_app/ui.py:3138 | literal | _build_settings | 3 |  |
| par_app/ui.py:3138 | literal | _build_settings | 88 |  |
| par_app/ui.py:3139 | literal | _build_settings | 4 |  |
| par_app/ui.py:3147 | literal | _build_settings | 247 |  |
| par_app/ui.py:3168 | literal | _build_settings | 2 |  |
| par_app/ui.py:3169 | literal | _build_settings | 3 |  |
| par_app/ui.py:3170 | literal | _build_settings | 4 |  |
| par_app/ui.py:3186 | literal | _build_settings | 260 |  |
| par_app/ui.py:3187 | literal | _build_settings | 44 |  |
| par_app/ui.py:3191 | literal | _build_settings | 28 |  |
| par_app/ui.py:3205 | literal | _build_settings | 30 |  |
| par_app/ui.py:3211 | literal | _build_settings | 6 |  |
| par_app/ui.py:3213 | literal | _build_settings | 10 |  |
| par_app/ui.py:3213 | literal | _build_settings | 6 |  |
| par_app/ui.py:3221 | literal | _build_settings | 2 |  |
| par_app/ui.py:3221 | literal | _build_settings | 24 |  |
| par_app/ui.py:3221 | literal | _build_settings | 4 |  |
| par_app/ui.py:3221 | literal | _build_settings | 8 |  |
| par_app/ui.py:3232 | literal | _build_settings | 10 |  |
| par_app/ui.py:3258 | literal | _build_settings | 260 |  |
| par_app/ui.py:3270 | literal | _build_settings | 105 |  |
| par_app/ui.py:3273 | literal | _build_settings | 8 |  |
| par_app/ui.py:3275 | literal | _build_settings | 180 |  |
| par_app/ui.py:3275 | literal | _build_settings | 3 |  |
| par_app/ui.py:3276 | literal | _build_settings | 2 |  |
| par_app/ui.py:3277 | literal | _build_settings | 29 |  |
| par_app/ui.py:3277 | literal | _build_settings | 36 |  |
| par_app/ui.py:3277 | literal | _build_settings | 8 |  |
| par_app/ui.py:3283 | literal | _build_settings | 4 |  |
| par_app/ui.py:3284 | literal | _build_settings | 10 |  |
| par_app/ui.py:3290 | literal | _build_settings | 6 |  |
| par_app/ui.py:3294 | literal | _build_settings | 8 |  |
| par_app/ui.py:3295 | literal | _build_settings | 12 |  |
| par_app/ui.py:3297 | literal | _build_settings | 112 |  |
| par_app/ui.py:3301 | literal | _build_settings | 112 |  |
| par_app/ui.py:3305 | literal | _build_settings | 6 |  |
| par_app/ui.py:3318 | literal | _build_settings | 64 |  |
| par_app/ui.py:3326 | literal | _build_settings | 4 |  |
| par_app/ui.py:3341 | literal | _build_settings | 700 |  |
| par_app/ui.py:3347 | literal | _build_settings | 1.5 |  |
| par_app/ui.py:3367 | literal | _layout_settings_content | 20 |  |
| par_app/ui.py:3367 | literal | _layout_settings_content | 8 |  |
| par_app/ui.py:3368 | literal | _layout_settings_content | 28 |  |
| par_app/ui.py:3373 | literal | _layout_settings_content | 2 |  |
| par_app/ui.py:3373 | literal | _layout_settings_content | 3 |  |
| par_app/ui.py:3374 | literal | _layout_settings_content | 24 |  |
| par_app/ui.py:3375 | literal | _layout_settings_content | 88 |  |
| par_app/ui.py:3377 | literal | _layout_settings_content | 36 |  |
| par_app/ui.py:3400 | literal | _layout_settings_content | 4 |  |
| par_app/ui.py:3412 | literal | show_about_support | 520 |  |
| par_app/ui.py:3413 | literal | show_about_support | 12 |  |
| par_app/ui.py:3413 | literal | show_about_support | 16 |  |
| par_app/ui.py:3413 | literal | show_about_support | 20 |  |
| par_app/ui.py:3413 | literal | show_about_support | 24 |  |
| par_app/ui.py:3417 | literal | show_about_support | 165 |  |
| par_app/ui.py:3422 | literal | show_about_support | 8 |  |
| par_app/ui.py:3474 | literal | open_communication_maintenance | 2 |  |
| par_app/ui.py:3549 | literal | _current_export_range | 2 | EXP-068：导出预设“最近 2 小时”的小时数（由 update_export_range 移入，修复旧仓库 #7） |
| par_app/ui.py:3549 | literal | _current_export_range | 24 | EXP-068：导出预设“最近 24 小时”的小时数（由 update_export_range 移入，修复旧仓库 #7） |
| par_app/ui.py:3549 | literal | _current_export_range | 4 | EXP-068：导出预设“最近 4 小时”的小时数（由 update_export_range 移入，修复旧仓库 #7） |
| par_app/ui.py:3549 | literal | _current_export_range | 8 | EXP-068：导出预设“最近 8 小时”的小时数（由 update_export_range 移入，修复旧仓库 #7） |
| par_app/ui.py:3573 | literal | populate_settings | 2 |  |
| par_app/ui.py:3691 | literal | _show_settings_log_details | 0.9 |  |
| par_app/ui.py:3691 | literal | _show_settings_log_details | 520 |  |
| par_app/ui.py:3691 | literal | _show_settings_log_details | 820 |  |
| par_app/ui.py:3719 | literal | refresh_settings_console | 2 |  |
| par_app/ui.py:3726 | literal | refresh_settings_console | 300 |  |
| par_app/ui.py:3728 | literal | refresh_settings_console | 50 |  |
| par_app/ui.py:3741 | literal | refresh_settings_console | 29 |  |
| par_app/ui.py:3745 | literal | refresh_settings_console | 2 |  |
| par_app/ui.py:3754 | literal | refresh_settings_console | 2 |  |
| par_app/ui.py:3759 | literal | refresh_settings_console | 2 |  |
| par_app/ui.py:3852 | literal | refresh_overview | 10 |  |
| par_app/ui.py:3886 | literal | refresh_overview | 8 |  |
| par_app/ui.py:3892 | literal | refresh_overview | 2 |  |
| par_app/ui.py:3892 | literal | refresh_overview | 6 |  |
| par_app/ui.py:3901 | literal | refresh_overview | 6 |  |
| par_app/ui.py:3918 | literal | _update_overview_status | 2 |  |
| par_app/ui.py:3927 | literal | _update_overview_status | 120.0 |  |
| par_app/ui.py:3927 | literal | _update_overview_status | 2 |  |
| par_app/ui.py:3963 | literal | _format_metric | 3 |  |
| par_app/ui.py:3990 | literal | refresh_history | 500 |  |
| par_app/ui.py:3993 | literal | refresh_history | 2 |  |
| par_app/ui.py:4000 | literal | refresh_history | 3 |  |
| par_app/ui.py:4002 | literal | refresh_history | 4 |  |
| par_app/ui.py:4187 | literal | show_history_spectrum | 2 |  |
| par_app/ui.py:4199 | literal | show_history_spectrum | 0.535 |  |
| par_app/ui.py:4204 | literal | show_history_spectrum | 10 |  |
| par_app/ui.py:4211 | literal | _operation_values | 10 |  |
| par_app/ui.py:4275 | literal | _redraw_operation_charts | 0.1 |  |
| par_app/ui.py:4275 | literal | _redraw_operation_charts | 0.25 |  |
| par_app/ui.py:4275 | literal | _redraw_operation_charts | 1e-09 |  |
| par_app/ui.py:4282 | literal | _redraw_operation_charts | 2 |  |
| par_app/ui.py:4284 | literal | _redraw_operation_charts | 2 |  |
| par_app/ui.py:4286 | literal | _redraw_operation_charts | 0.25 |  |
| par_app/ui.py:4296 | literal | _redraw_operation_charts | 0.02 |  |
| par_app/ui.py:4296 | literal | _redraw_operation_charts | 0.97 |  |
| par_app/ui.py:4298 | literal | _redraw_operation_charts | 0.85 |  |
| par_app/ui.py:4298 | literal | _redraw_operation_charts | 9 |  |
| par_app/ui.py:4301 | literal | _redraw_operation_charts | 0.5 |  |
| par_app/ui.py:4302 | literal | _redraw_operation_charts | 12 |  |
| par_app/ui.py:4308 | literal | _align_operation_guide | 11 |  |
| par_app/ui.py:4308 | literal | _align_operation_guide | 1100 |  |
| par_app/ui.py:4308 | literal | _align_operation_guide | 14 |  |
| par_app/ui.py:4308 | literal | _align_operation_guide | 800 |  |
| par_app/ui.py:4315 | literal | _layout_operation_charts | 1100 |  |
| par_app/ui.py:4315 | literal | _layout_operation_charts | 800 |  |
| par_app/ui.py:4316 | literal | _layout_operation_charts | 11 |  |
| par_app/ui.py:4316 | literal | _layout_operation_charts | 14 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 1000 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 1050 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 350 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 400 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 500 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 600 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 680 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 700 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 800 |  |
| par_app/ui.py:4319 | literal | _layout_operation_charts | 900 |  |
| par_app/ui.py:4321 | literal | _layout_operation_charts | 1050 |  |
| par_app/ui.py:4321 | literal | _layout_operation_charts | 350 |  |
| par_app/ui.py:4322 | literal | _layout_operation_charts | 0.2 |  |
| par_app/ui.py:4322 | literal | _layout_operation_charts | 1.08 |  |
| par_app/ui.py:4324 | literal | _layout_operation_charts | 0.5 |  |
| par_app/ui.py:4324 | literal | _layout_operation_charts | 4 |  |
| par_app/ui.py:4324 | literal | _layout_operation_charts | 6 |  |
| par_app/ui.py:4325 | literal | _layout_operation_charts | 8 |  |
| par_app/ui.py:4326 | literal | _layout_operation_charts | 8 |  |
| par_app/ui.py:4329 | literal | _layout_operation_charts | 2 |  |
| par_app/ui.py:4330 | literal | _layout_operation_charts | 80.0 |  |
| par_app/ui.py:4331 | literal | _layout_operation_charts | 2 |  |
| par_app/ui.py:4336 | literal | _layout_operation_charts | 0.5 |  |
| par_app/ui.py:4340 | literal | _layout_operation_charts | 0.42 |  |
| par_app/ui.py:4340 | literal | _layout_operation_charts | 0.5 |  |
| par_app/ui.py:4361 | literal | export_operation_results | 11 |  |
| par_app/ui.py:4370 | literal | export_operation_results | 11 |  |
| par_app/ui.py:4371 | literal | export_operation_results | 32 |  |
| par_app/ui.py:4647 | literal | export_acquisitions | 300 |  |
| par_app/ui.py:4736 | literal | _device_task_finished | 15000 |  |
| par_app/ui_unconfigured.py:23 | constant | BYTES_PER_MB | 1000000 | 非业务规则：设置页数据库摘要的文件大小单位换算（十进制 MB），由 ui.py refresh_database_summary 挪入 |
| par_app/api/__main__.py:31 | constant | TOKEN_BYTES | 32 | 非业务规则：本机服务一次性令牌的随机字节数（secrets.token_urlsafe，256 位），阶段二方案 13_ 第 3.2 节“每次启动生成一次性令牌” |
| par_app/api/__main__.py:33 | constant | SERVICE_FILE_MODE | 384 | 非业务规则：service.json 权限 0o600（仅本人可读写），阶段二服务骨架任务要求 |
| par_app/api/__main__.py:35 | constant | HIGHEST_PORT | 65535 | 非业务规则：TCP 端口取值上限，校验 --port 参数 |
| par_app/api/__main__.py:68 | constant | CHUNK | 65536 | 非业务规则：读 stdin 文件描述符（只为等到管道结束）每次读取的字节数，内容丢弃（PR #50 复审 major 1） |
| par_app/api/__main__.py:46 | literal | write_service_file | 2 | 非业务规则：JSON 缩进 |
| par_app/api/static.py:58 | literal | default_web_dir | 2 | 非业务规则：`Path(__file__).parents[2]` 取仓库根目录（par_app/api/static.py 上两级），用于找 web/dist |
| par_app/api/security.py:23 | constant | POLICY_VIOLATION | 1008 | 非业务规则：WebSocket 关闭码 1008（RFC 6455 7.4.1，按策略拒绝）；alpha 暂不接受 WebSocket（PR #45 审查 N-6） |
| par_app/application/__init__.py:12 | constant | DEVICE_WRITE_TIER | 0 | 阶段二 S-4（负责人 2026-10-18 按推荐批准）：alpha 设备写入档位出厂为 0，只读、不采集、不写设备；方案 13_ 第 2.5 节 |
| par_app/application/dli.py:39 | literal | <module> | 116.4074 | UI-153：未保存或无法读取 DLI 位置时用北京坐标，复制自 ParDatabase.load_dli_location（该处 39.9042 / 116.4074 的同一默认值） |
| par_app/application/dli.py:39 | literal | <module> | 39.9042 | 同上一行（纬度） |
| par_app/application/dli.py:53 | literal | <module> | -89.9 | DLI-024/UI-178（#116）：保存位置时纬度下限，复制自 V1.0.3 MainWindow dli_latitude.setRange(-89.9, 89.9) |
| par_app/application/dli.py:53 | literal | <module> | 89.9 | 同上一行（纬度上限） |
| par_app/application/dli.py:54 | literal | <module> | -180.0 | DLI-024/UI-178（#116）：保存位置时经度下限，复制自 V1.0.3 MainWindow dli_longitude.setRange(-180.0, 180.0) |
| par_app/application/dli.py:54 | literal | <module> | 180.0 | 同上一行（经度上限） |
| par_app/application/dli.py:56 | constant | LOCATION_DECIMALS | 4 | DLI-024/UI-178（#116）：位置按 4 位小数保存，同 V1.0.3 两个输入框的 setDecimals(4) |
| par_app/application/dli.py:42 | literal | <module> | 23 | 非业务规则：END_OF_DAY = 23:59:59.999，“该日结束时正在进行的周期”的基准时刻（API-10 的 date 参数，D-204 问题 2） |
| par_app/application/dli.py:42 | literal | <module> | 59 | 非业务规则：同上一行（分、秒） |
| par_app/application/dli.py:42 | literal | <module> | 999000 | 非业务规则：同上一行（999 毫秒，以微秒计） |
| par_app/application/dli.py:43 | literal | <module> | 3 | 非业务规则：最早可查日期 date.min + 3 天；dli_period 要算 d−2 日的日出，更早的日期 Python 无法表示 |
| par_app/services/dli_display.py:38 | constant | Y_AXIS_HEADROOM | 1.15 | UI-184（纵轴从 0 起）：纵轴上限为累计值 ×1.15，复制自 ui.py DliCanvas.plot_dli set_ylim |
| par_app/services/dli_display.py:40 | constant | Y_AXIS_MINIMUM_TOP | 0.001 | UI-184：纵轴上限至少 0.001 mol·m⁻²，复制自 ui.py DliCanvas.plot_dli set_ylim |
| par_app/services/dli_display.py:42 | constant | TICK_HOURS_WIDE | 3 | UI-183（内部刻度间隔随图宽调整）：图宽 ≥ 700 px 时每 3 小时一个刻度，复制自 ui.py DliCanvas._layout_plot |
| par_app/services/dli_display.py:43 | constant | TICK_HOURS_NARROW | 6 | UI-183：图宽 < 700 px 时每 6 小时，复制自 ui.py DliCanvas._layout_plot |
| par_app/services/dli_display.py:45 | constant | TICK_MIN_DISTANCE_SECONDS | 7200 | UI-183：距两端不足 2 小时的内部刻度不显示，复制自 ui.py DliCanvas._layout_plot |
| par_app/services/dli_display.py:83 | literal | duration_text | 60 | 非业务规则：秒→分→时换算，复制自 ui.py DliCanvas._duration（DLI-044、DLI-053 的时长文本） |
| par_app/services/dli_display.py:84 | literal | duration_text | 60 | 非业务规则：同上一行 |
| par_app/application/history.py:23 | constant | PAGE_LIMIT | 500 | UI-048（历史最多显示范围内最近 500 条）；接口每页上限沿用同一数值（api-contract-v0 API-05） |
| par_app/application/readonly.py:23 | constant | BUSY_TIMEOUT_SECONDS | 10.0 | 非业务规则：只读连接等锁时间，与 ParDatabase.connect 的 sqlite3.connect(timeout=10) 相同 |
| par_app/application/readonly.py:25 | literal | <module> | 2 | 非业务规则：SQLITE_MAX_INTEGER = 2**63 − 1，SQLite INTEGER（64 位有符号）上限；记录 ID 与 offset 超出即 400（PR #45 审查 N-2） |
| par_app/application/readonly.py:25 | literal | <module> | 63 | 非业务规则：同上一行（2**63 − 1 的指数） |
| par_app/application/snapshots.py:54 | literal | <module> | 20 | 非业务规则：计算源库 SHA-256 时每次读 1 MiB（1 << 20） |
| par_app/application/snapshots.py:321 | literal | _write_sidecar | 2 | 非业务规则：JSON 缩进 |
| par_app/application/timefmt.py:8 | constant | MICROSECOND_DIGITS_DROPPED | 3 | 非业务规则：%f 微秒截去 3 位成毫秒，与 par_app.database.beijing_now 的时间文本格式相同（api-contract-v0 1.2） |
| par_app/services/history.py:35 | literal | <module> | 2 | 曝光状态码 2 = 欠曝光（0 正常、1 过曝光），复制自 ui.py refresh_history，UI-052、D-154 |
| par_app/services/history.py:42 | literal | <module> | 16 | 特殊显色指数 R1–R15（range(1, 16)），复制自 ui.py 历史详情分组，UI-018 |
| par_app/services/history.py:189 | literal | spectrum_values | 10 | 光谱辐照度 = 原始值 / 10^光谱系数，复制自 ui.py show_history_spectrum（与 math_ops.software_metrics 的输入换算一致） |
| par_app/application/operations.py:39 | constant | ACQUIRED_AT_MAX_LENGTH | 64 | 非业务规则：最近时间匹配参数 acquired_at 的长度上限（库内时间 23–32 个字符），防止超长参数（API-13） |
| par_app/services/operation_display.py:43 | constant | CANDIDATE_LIMIT | 500 | UI-198、UI-204：计算页记录框列最近 500 条成功完整光谱，复制自 ui.py 对 ParDatabase.operation_spectra 的调用（默认 500） |
| par_app/services/operation_display.py:82 | literal | <module> | 1000 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 1050 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 350 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 400 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 500 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 600 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 700 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 800 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:82 | literal | <module> | 900 | UI-192、UI-193：计算页宽图横轴刻度 350,400,…,1000,1050，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 1050 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 350 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 500 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 600 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 700 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 800 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:83 | literal | <module> | 900 | UI-192、UI-193：计算页窄图横轴刻度（省略 400、1000），复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:84 | constant | NARROW_CHART_PX | 680 | UI-192：图宽小于 680 px 时用窄刻度，复制自 ui.py MainWindow._layout_operation_charts |
| par_app/services/operation_display.py:86 | constant | PEAK_HEIGHT_FRACTION | 0.618 | 非业务规则（显示）：非负光谱峰值位于绘图区约 0.618 高度，复制自 ui.py SpectrumCanvas.plot（UI-209 A/B 共同纵轴的来源） |
| par_app/services/operation_display.py:88 | constant | NEGATIVE_PADDING_FRACTION | 0.08 | 非业务规则（显示）：含负值的光谱纵轴上下各留 8% 跨度，复制自 ui.py SpectrumCanvas.plot |
| par_app/services/operation_display.py:90 | constant | MINIMUM_SPAN | 1e-09 | 非业务规则（显示）：纵轴跨度下限 1e-9（全零数据仍有坐标轴），复制自 ui.py SpectrumCanvas.plot 与 _redraw_operation_charts |
| par_app/services/operation_display.py:92 | constant | RATIO_PADDING_SPAN | 0.25 | UI-222：比值纵轴留白取 max(25% 跨度, 10% 幅值)，复制自 ui.py MainWindow._redraw_operation_charts |
| par_app/services/operation_display.py:93 | constant | RATIO_PADDING_MAGNITUDE | 0.1 | UI-222：同上一行（10% 幅值） |
| par_app/services/operation_display.py:95 | constant | SIGNED_PADDING_SPAN | 0.25 | UI-221：加减法结果跨零时上下各留 25% 跨度，复制自 ui.py MainWindow._redraw_operation_charts |
| par_app/services/operation_display.py:97 | constant | ZERO_SIDE_FACTOR | 2.0 | UI-221：加减法结果全在零一侧时纵轴到峰值的 2 倍（峰值约在半高），复制自 ui.py MainWindow._redraw_operation_charts |
| par_app/services/operation_display.py:99 | constant | FLAT_LIMIT | 1.0 | UI-221：加减法结果全为零时纵轴 −1…1，复制自 ui.py MainWindow._redraw_operation_charts |
| par_app/services/operation_display.py:102 | constant | RATIO_REFERENCE | 1.0 | UI-220：比值图的 1 倍参考虚线，复制自 ui.py SpectrumCanvas.plot axhline(1) 与 _redraw_operation_charts |
| par_app/services/operation_display.py:136 | literal | spectrum_values | 10 | 光谱 mW/nm = 原始值 / 10^光谱系数，不归一化（UI-211），复制自 ui.py MainWindow._operation_values |
| par_app/services/spectrum_display.py:23 | constant | FILL_OPACITY | 0.55 | UI-317：单条光谱的着色填充不透明度，复制自 ui.py SpectrumCanvas.plot alpha=0.55 |
| par_app/services/spectrum_display.py:26 | constant | RESPONSE_HEADROOM | 1.5 | UI-168：右侧响应坐标轴上限 = 叶绿素/McCree 峰值 × 1.5，复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:56 | literal | wavelength_to_rgb | 380 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:56 | literal | wavelength_to_rgb | 780 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:57 | literal | wavelength_to_rgb | 0.55 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:58 | literal | wavelength_to_rgb | 440 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:59 | literal | wavelength_to_rgb | 440 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:59 | literal | wavelength_to_rgb | 60 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:60 | literal | wavelength_to_rgb | 490 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:61 | literal | wavelength_to_rgb | 440 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:61 | literal | wavelength_to_rgb | 50 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:62 | literal | wavelength_to_rgb | 510 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:63 | literal | wavelength_to_rgb | 20 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:63 | literal | wavelength_to_rgb | 510 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:64 | literal | wavelength_to_rgb | 580 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:65 | literal | wavelength_to_rgb | 510 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:65 | literal | wavelength_to_rgb | 70 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:66 | literal | wavelength_to_rgb | 645 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:67 | literal | wavelength_to_rgb | 645 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:67 | literal | wavelength_to_rgb | 65 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:70 | literal | wavelength_to_rgb | 420 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:71 | literal | wavelength_to_rgb | 0.3 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:71 | literal | wavelength_to_rgb | 0.7 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:71 | literal | wavelength_to_rgb | 380 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:71 | literal | wavelength_to_rgb | 40 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:72 | literal | wavelength_to_rgb | 700 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:73 | literal | wavelength_to_rgb | 0.3 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:73 | literal | wavelength_to_rgb | 0.7 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:73 | literal | wavelength_to_rgb | 780 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:73 | literal | wavelength_to_rgb | 80 | UI-317：波长→颜色的可见光近似映射（纯显示），逐值复制自 ui.py SpectrumCanvas._wavelength_to_rgb |
| par_app/services/spectrum_display.py:86 | literal | reference_curves | 400 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:86 | literal | reference_curves | 700 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:91 | literal | reference_curves | 1e-09 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:92 | literal | reference_curves | 360 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:92 | literal | reference_curves | 831 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:97 | literal | reference_curves | 1.6 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:98 | literal | reference_curves | 1.6 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:99 | literal | reference_curves | 1.7 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/spectrum_display.py:100 | literal | reference_curves | 1.6 | UI-168：四条参考曲线的取样范围、归一化下限与线宽（纯显示，曲线数值仍由 math_ops / mccree1972_weights / photopic_weights 计算），复制自 ui.py SpectrumCanvas._draw_response_overlays |
| par_app/services/operation_guide.py:52 | constant | DIALOG_WIDTH_PX | 960 | UI-232：完整说明弹窗默认宽 960 逻辑像素，复制自 ui.py OperationGuideCanvas.show_details |
| par_app/services/operation_guide.py:53 | constant | DIALOG_HEIGHT_PX | 760 | UI-232：完整说明弹窗默认高 760 逻辑像素，复制自 ui.py OperationGuideCanvas.show_details |
| par_app/services/operation_guide.py:54 | constant | DIALOG_SCREEN_FRACTION | 0.9 | UI-232：弹窗不超过屏幕可用宽、高的 90%，复制自 ui.py OperationGuideCanvas.show_details |
| par_app/application/acquisition_export.py:117 | literal | parse_time | 32 | 非业务规则：参数错误提示里最多回显 32 个字符，防止超长参数（API-22、API-23） |
| par_app/application/acquisition_export.py:141 | literal | resolve | 16 | 非业务规则：导出范围参数错误提示里最多回显 16 个字符（API-22） |
| par_app/services/overview_display.py:78 | constant | TABLE_GROUP_SIZE | 6 | 非业务规则：实时概览隐藏的 24 项表按 6 行一组分 4 组，复制自 ui.py MainWindow.refresh_overview（row = index % 6） |
| par_app/services/overview_display.py:82 | constant | OVERLAY_COLUMN_BREAK | 8 | UI-060：图内 20 项指标左列 8 项波段光量、右列 12 项，复制自 ui.py MainWindow.refresh_overview（column_break=8） |
| par_app/services/overview_display.py:99 | constant | STALE_MINIMUM_SECONDS | 120.0 | UI-171：超过两个轮询周期且至少 120 秒提示“暂无新记录”，复制自 ui.py MainWindow._update_overview_status |
| par_app/services/overview_display.py:100 | constant | STALE_POLL_CYCLES | 2 | UI-171：两个轮询周期，复制自 ui.py MainWindow._update_overview_status |
| par_app/services/overview_display.py:102 | constant | FUTURE_TOLERANCE_SECONDS | 1.0 | UI-171：记录时间超前本机 1 秒以上也算“暂无新记录”（age < -1），复制自 ui.py MainWindow._update_overview_status |
| par_app/services/overview_display.py:104 | constant | ELAPSED_DEFAULT | 0 | 非业务规则：行中没有 elapsed_ms 时耗时显示 0.0 ms（record.get('elapsed_ms', 0)），复制自 ui.py MainWindow._update_overview_status |
| par_app/services/overview_display.py:215 | literal | overlay_columns | 2 | 非业务规则：只有核心读数卡时 4 行隔行分到两列（metrics[::2]、metrics[1::2]），复制自 ui.py SpectrumCanvas._draw_core_metrics_card |
| par_app/services/settings_display.py:40 | literal | <module> | 2 | EXP-068：导出范围预设“最近 2 小时”，复制自 ui.py MainWindow._build_settings (1, 2, 4, 8, 24) |
| par_app/services/settings_display.py:40 | literal | <module> | 24 | EXP-068：导出范围预设“最近 24 小时”，复制自 ui.py MainWindow._build_settings |
| par_app/services/settings_display.py:40 | literal | <module> | 4 | EXP-068：导出范围预设“最近 4 小时”，复制自 ui.py MainWindow._build_settings |
| par_app/services/settings_display.py:40 | literal | <module> | 8 | EXP-068：导出范围预设“最近 8 小时”，复制自 ui.py MainWindow._build_settings |
| par_app/services/settings_display.py:78 | constant | BYTES_PER_MB | 1000000 | UI-077：数据库文件大小按 1 MB = 1,000,000 字节换算，复制自 ui_unconfigured.BYTES_PER_MB |
| par_app/services/settings_display.py:143 | constant | LOG_SCAN_ROWS | 300 | UI-078：日志表从最近 300 条日志中筛选，复制自 ui.py MainWindow.refresh_settings_console（recent_diagnostics(300)） |
| par_app/services/settings_display.py:145 | constant | LOG_SHOWN_ROWS | 50 | UI-078：筛选后最多展示 50 条，复制自 ui.py MainWindow.refresh_settings_console（[:50]） |
| par_app/services/settings_display.py:188 | literal | <module> | 2 | 非业务规则：曝光状态码 2 显示“欠曝光”（设备上报值的显示名），复制自 ui.py MainWindow.refresh_settings_console |
| par_app/acquisition_host/config_io.py:34 | literal | <module> | 247 | CONF（V1.0.3 设置页从站地址 id_spin.setRange(1, 247)，与 DeviceHub.apply 的范围相同）：只作为表单范围交给页面，校验仍由 DeviceHub.apply 做（D-214） |
| par_app/acquisition_host/config_io.py:36 | literal | <module> | 65535 | 非业务规则：V1.0.3 设置页 TCP 端口 tcp_port.setRange(1, 65535)（TCP 端口号的取值范围），只作为表单范围交给页面（D-214） |
| par_app/acquisition_host/config_io.py:38 | constant | POLL_DECIMALS | 1 | 非业务规则：V1.0.3 设置页轮询周期 interval.setDecimals(1)，只决定页面输入步长（D-214） |
| par_app/acquisition_host/config_io.py:198 | constant | DELIVERY_BAUDRATE | 57600 | CONF（16_ 3.3；负责人 2026-10-27）：新安装空配置表单的默认波特率，即交付探头的设置；V1.0.3 为 DEFAULT_BAUDRATE 19200 |
| par_app/acquisition_host/config_io.py:200 | constant | DELIVERY_POLL_CYCLE_SECONDS | 40.0 | CONF（16_ 3.3；负责人 2026-10-27）：新安装空配置表单的默认轮询周期，等于 MIN_POLL_CYCLE_SECONDS；V1.0.3 为 60 秒 |
| par_app/acquisition_host/host.py:35 | constant | START_TIMEOUT_SECONDS | 30.0 | 非业务规则：HTTP 请求等待服务主线程完成“开始采集”（取锁、建 DeviceHub）的时限，超时答 busy（16_ 第 5 节，D-213） |
| par_app/acquisition_host/host.py:37 | constant | APPLY_TIMEOUT_SECONDS | 30.0 | 非业务规则：HTTP 请求等待主线程执行 DeviceHub.apply 的时限，超时答 busy（D-213） |
| par_app/acquisition_host/instance_lock.py:22 | constant | LOCK_SIZE | 1 | POLL 红线 1（串口独占）：照抄 V1.0.3 main.py 的 QSharedMemory.create(1)，测试 test_instance_lock 解析 main.py 锁定（16_ 2.2） |
| par_app/api/acquisition_models.py:58 | literal | Bus | 65535 | 非业务规则：TCP 端口号上限（请求校验） |
| par_app/api/acquisition_models.py:81 | literal | ConfigRequest | 4 | CONF：最多 4 台设备（models.MAX_DEVICES，DeviceHub.apply 同样检查）；请求校验 |
| par_app/application/events.py:20 | constant | QUEUE_LIMIT | 256 | 非业务规则：每个事件流订阅者最多积压 256 条，超出即关闭该流，页面重连重读状态（16_ 第 5 节） |
| par_app/application/events.py:22 | constant | HEARTBEAT_SECONDS | 15.0 | 非业务规则：事件流 15 秒心跳（api-contract-v0 API-17） |
| par_app/application/tier.py:29 | constant | FACTORY_TIER | 0 | D-212 /负责人 2026-10-18：alpha 出厂档位 0（只读） |
| par_app/application/tier.py:30 | constant | TAKEOVER_TIER | 1 | D-212 /负责人 2026-10-18：档位 1＝接管采集 |
| par_app/application/tier.py:33 | constant | CONFIRMATION_SECONDS | 60.0 | D-212（16_ 4.2）：开启档位 1 的二次确认号 60 秒内有效 |
| par_app/application/tier.py:35 | constant | CONFIRMATION_ID_BYTES | 16 | 非业务规则：确认号随机字节数（secrets.token_urlsafe） |
| par_app/application/tier.py:106 | literal | write | 2 | 非业务规则：JSON 缩进 |
| par_app/application/run_events.py:35 | constant | SCHEMA_VERSION | 1 | 非业务规则：events.jsonl 每行的格式版本（#136），字段变化时加一 |
| par_app/application/run_events.py:37 | constant | QUEUE_LIMIT | 1000 | 非业务规则：运行事件等待写盘的队列上限（#136）；满了不阻塞调用方，该条不进文件并计数，界面提示仍带记录号，导出时补上 |
| par_app/application/run_events.py:40 | constant | FILE_LIMIT_BYTES | 5000000 | 非业务规则：events.jsonl 超过 5 MB 换到 events.1.jsonl（#136），与诊断包每个日志保留 5 MB 一致（LOG_TAIL_BYTES） |
| par_app/application/run_events.py:42 | constant | FILE_BACKUPS | 2 | 非业务规则：保留 events.1.jsonl、events.2.jsonl 两个旧文件（#136） |
| par_app/application/run_events.py:44 | constant | SESSION_HEX_DIGITS | 16 | 非业务规则：记录号中运行会话的十六进制位数（#136），每次启动随机，64 位随机数使两次启动撞号可以不计（PR #143 评审） |
| par_app/application/run_events.py:45 | constant | SEQUENCE_DIGITS | 6 | 非业务规则：记录号中序号的显示位数（#136），不足补零，超出照常增长 |
| par_app/application/run_events.py:46 | constant | DETAIL_TEXT_LIMIT | 2000 | 非业务规则：运行事件详情中单段文字最多 2000 字，超出截断并标“（已截断）”（#136） |
| par_app/application/run_events.py:49 | constant | CLOSE_WAIT_SECONDS | 2.0 | 非业务规则：关闭服务时等待运行事件写完的上限（#136），不在通信路径上 |
| par_app/application/run_events.py:54 | literal | new_session | 2 | 非业务规则：十六进制位数折成字节数（每字节两位） |
| par_app/application/diagnostics_events.py:28 | constant | FLUSH_SECONDS | 2.0 | 非业务规则：导出诊断包时等待运行事件写完的上限（#136），超时照常导出并在 integrity.json 写明 |
| par_app/application/diagnostics_content.py:36 | constant | LOG_TAIL_BYTES | 5000000 | D-226 问题 3（按推荐）：诊断包中每个日志文件最多保留最后 5 MB，便于邮件发送；按字节硬上限读取（read(limit)，日志增长时也不超出）；完整日志仍在 alpha 数据目录 |
| par_app/application/diagnostics_content.py:39 | constant | DIAGNOSTICS_ROWS | 2000 | D-226 问题 3（按推荐）：诊断包中每台设备 diagnostics 表取最新 2000 行；设备写入相关类别另在 maintenance_diagnostics.csv 中全部导出（PR #63 评审 M-2） |
| par_app/application/diagnostics_content.py:42 | constant | TIME_SYNC_ROWS | 500 | D-226 问题 3（按推荐）：诊断包中每台设备 time_sync_events 取最新 500 行（约 20 天的每小时对时）；对时只在此文件，不进 maintenance_log.csv |
| par_app/application/diagnostics_content.py:43 | constant | INTERRUPTION_ROWS | 500 | D-226 问题 3（按推荐）：诊断包中每台设备 dli_interruptions 取最新 500 行 |
| par_app/application/diagnostics_content.py:44 | constant | RECENT_ACQUISITIONS | 50 | D-226 问题 3（按推荐）：诊断包只带最近 50 条采集记录的状态摘要，不带光谱与指标 |
| par_app/application/diagnostics_content.py:46 | constant | BUNDLE_LOG_ROWS | 5000 | D-226 问题 3（PR #63 评审 M-2 修订）：诊断包 maintenance_log.csv 最多最新 5000 条写入（不含对时）；超出时写入 manifest 的问题清单，各写入的原始行仍全部在设备目录中 |
| par_app/application/diagnostics_content.py:49 | constant | FETCH_ROWS | 500 | 非业务规则：诊断包导出表时每次从游标取 500 行写入 zip（流式，内存有界；PR #63 评审 major 2） |
| par_app/application/diagnostics_content.py:51 | constant | LOG_LINES_PER_CHUNK | 2000 | 非业务规则：日志按每 2000 行一块脱敏并写入 zip |
| par_app/application/diagnostics_content.py:100 | literal | json_text | 2 | 非业务规则：JSON 缩进 |
| par_app/application/maintenance_log.py:59 | constant | DEFAULT_LIMIT | 200 | D-226 问题 4（按推荐）：维护记录接口默认返回最新 200 条（API-28） |
| par_app/application/maintenance_log.py:60 | constant | MAX_LIMIT | 1000 | D-226 问题 4（按推荐）：维护记录接口 limit 上限 1000（诊断包另用 BUNDLE_LOG_ROWS） |
| par_app/application/maintenance_log.py:61 | constant | MS_PER_SECOND | 1000 | 非业务规则：对时记录 mcu_time_ms（毫秒）换算为秒再显示为北京时间 |
| par_app/application/maintenance_log.py:128 | constant | FETCH_ROWS | 200 | 非业务规则：维护记录按 id 倒序分块读取设备日志中与写入有关的行，每块一条新的 SELECT、200 行（有界查询；PR #63 评审 major 2、复审第 2 项） |
| par_app/application/maintenance_log.py:130 | constant | SCAN_ROWS | 100000 | D-226 问题 4（PR #63 复审第 2 项修订）：维护记录每台设备只扫描最新 10 万行设备日志与 10 万行校准审计（按 id），更早的不扫描并在响应中标明 scan_limited（页面显示“更早记录未扫描”）；诊断包 maintenance_diagnostics.csv 仍全部导出 |
| par_app/application/maintenance_log.py:125 | constant | ROLLBACK_MARGIN_ROWS | 500 | D-226 问题 4（PR #63 第三次评审修订）：维护记录各审计表按 id 倒序多取 500 行候选再按时间排序，时钟回拨后写入少于 500 行时仍按时间正确；换取查询工作量不随历史增长 |
| par_app/application/own_devices.py:27 | constant | DATABASE_ID_DIGITS | 16 | 非业务规则：设备库标识中路径哈希取前 16 位十六进制，只用来区分同一位置先后登记的不同设备库（#82） |
| par_app/application/redaction.py:93 | constant | SHORT_PATH_CHARS | 1024 | 非业务规则：Windows GetShortPathNameW 的缓冲区长度（字符），用于诊断包脱敏 8.3 短名 |
| par_app/service_main.py:45 | constant | SIGNAL_POLL_MILLISECONDS | 200 | 非业务规则：服务主线程空转定时器 200 毫秒，让 Python 信号处理函数在 Qt 事件循环中得以执行（16_ 1.5） |
| par_app/service_main.py:47 | constant | STDIN_CHUNK_BYTES | 4096 | 非业务规则：读取 stdin 直到结束的分块大小 |
| par_app/service_main.py:48 | constant | EXIT_REFUSED_DATA_DIR | 2 | 非业务规则：数据目录是 V1.0.3 程序目录时服务拒绝启动的退出码，与 argparse 参数错误相同（D-215） |
| par_app/service_main.py:50 | constant | EXIT_WRONG_QT_BINDING | 3 | 非业务规则：服务进程不是 PySide6 绑定时拒绝启动的退出码（alpha 不在 PyQt5 上运行，内部文档，D-225） |
| par_app/service_main.py:51 | constant | UVICORN_JOIN_SECONDS | 10.0 | 非业务规则：关闭时等待 uvicorn 线程退出的时限，超时记日志后继续（16_ 1.5 第 7 步） |
| par_app/parent_watch.py:41 | constant | POLL_SECONDS | 0.5 | 非业务规则：POSIX 上服务检查外壳进程是否还在的间隔（D-223；PR #56 复审 blocker 2） |
| par_app/parent_watch.py:43 | constant | BACKSTOP_SECONDS | 60.0 | D-223：外壳消失后服务优雅停止的兜底时限，超时自行结束；与外壳等待服务退出的时限 par_shell/service.py STOP_TIMEOUT_SECONDS 相同（16_ 1.5：一次采集事务预算 40 秒加余量），不改任何预算 |
| par_app/parent_watch.py:45 | constant | EXIT_BACKSTOP | 3 | 非业务规则：上述兜底结束进程时的退出码（2 已用于拒绝的数据目录与参数错误；D-223） |
| par_app/parent_watch.py:47 | constant | SYNCHRONIZE | 1048576 | 非业务规则：Win32 进程访问权限 SYNCHRONIZE（0x00100000），只用于等待外壳进程结束 |
| par_app/parent_watch.py:48 | constant | INFINITE | 4294967295 | 非业务规则：Win32 WaitForSingleObject 的无限等待（0xFFFFFFFF） |
| par_app/parent_watch.py:49 | constant | ERROR_INVALID_PARAMETER | 87 | 非业务规则：Win32 错误码 87，OpenProcess 对不存在的 pid 返回（外壳已结束） |
| par_app/acquisition_host/host.py:43 | constant | MAINTENANCE_TIMEOUT_SECONDS | 30.0 | 非业务规则：HTTP 请求等待主线程上的维护控制器的时限，超时答 busy（17_ 3.2；控制器只排队，不等设备） |
| par_app/acquisition_host/maintenance_actions.py:32 | constant | MAX_SLAVE_ID | 247 | MAINT（V1.0.3 MaintenanceDialog._fields：address.setRange(1, 247)）：表单范围，越界答 400；会话层 CommunicationMaintenance.connection 仍按原样检查（17_ 3.3） |
| par_app/acquisition_host/maintenance_actions.py:158 | literal | _write_export | 2 | 非业务规则：导出诊断 JSON 的缩进，照 V1.0.3 export_diagnostics 的 json.dumps(indent=2)（D-216 问题 11） |
| par_app/acquisition_host/maintenance_actions.py:374 | literal | _tab | 2 | 非业务规则：维护页页签序号 0–2（设备状态与诊断、光谱校准、通信参数维护，V1.0.3 顺序，MAINT-014） |
| par_app/acquisition_host/maintenance_calibration.py:29 | constant | PERCENT_DECIMALS | 2 | MAINT（V1.0.3 MainWindow._build_calibration：百分比字段 setDecimals(2)）：服务按编辑框位数取整，写入值＝编辑框值÷倍率（17_ 3.3，D-216 问题 5、7） |
| par_app/acquisition_host/maintenance_calibration.py:30 | constant | WAVELENGTH_DECIMALS | 1 | MAINT（同上：波长字段 setDecimals(1)） |
| par_app/acquisition_host/maintenance_calibration.py:31 | constant | FACTOR_DECIMALS | 4 | MAINT（同上：k_global setDecimals(4)） |
| par_app/acquisition_host/maintenance_calibration.py:119 | literal | drag | 100 | MAINT-038（V1.0.3 MainWindow._calibration_nodes_changed：y 编辑框显示 y×100，与 node_values 的百分比口径相同） |
| par_app/acquisition_host/maintenance_host.py:40 | literal | <module> | 2 | 非业务规则：维护页页签序号 0–2（同上） |
| par_app/acquisition_host/maintenance_host.py:299 | literal | open_page | 8 | 非业务规则：维护页会话号随机字节数（secrets.token_urlsafe） |
| par_app/acquisition_host/maintenance_page.py:297 | literal | settings_view | 2 | 非业务规则：V1.0.3 _render_comm_values 的列序号（地址、波特率、校验位），只决定显示 |
| par_app/acquisition_host/maintenance_view.py:21 | constant | COUNTER_SATURATED | 65535 | MAINT（V1.0.3 DeviceMaintenanceDialog.task_finished：计数饱和 65535 不计算本次新增） |
| par_app/acquisition_host/maintenance_view.py:23 | constant | EVENT_LIMIT | 100 | MAINT（V1.0.3 display_diagnostics / export_diagnostics：最近 100 条软件事件） |
| par_app/acquisition_host/maintenance_view.py:25 | constant | COMMUNICATION_ROWS | 8 | MAINT（V1.0.3 COMMUNICATION_ERRORS 8 项、其后为 14 项 PAR 错误，诊断表“类别”列） |
| par_app/acquisition_host/maintenance_view.py:66 | literal | _summary | 1000 | 非业务规则：曝光时间 µs→ms 显示换算，照 V1.0.3 display_diagnostics |
| par_app/acquisition_host/maintenance_view.py:150 | literal | event_rows | 2 | 非业务规则：事件详情 JSON 缩进，照 V1.0.3 show_event_details 的 json.dumps(indent=2) |
| par_app/acquisition_host/maintenance_view.py:193 | literal | comm_values | 247 | CONF（V1.0.3 MainWindow._accept_settings_comm：回读地址 1–247 才显示） |
| par_app/acquisition_host/maintenance_view.py:193 | literal | comm_values | 3 | CONF（同上：校验位索引 0–2） |
| par_app/acquisition_host/v1_texts.py:122 | literal | <module> | 2 | 非业务规则：V1.0.3 曝光状态文字表的键（0 正常、1 过曝光、2 欠曝光），文案逐字核对见 test_maintenance_texts |
| par_app/api/maintenance_routes.py:44 | literal | Page | 2 | 非业务规则：维护页页签序号上限（同上） |
| par_app/application/tier.py:33 | constant | MAINTENANCE_TIER | 2 |负责人 2026-10-18 批准：档位 2＝设备维护写入，在档位 1 之上再次确认开启（17_ 第 8 节，D-216） |
| par_app/alpha_self_test_db.py:21 | constant | FLAT_RAW_LEVEL | 1000 | 非业务规则：alpha 自检合成库的平坦光谱原始值（编造数据，不是测量值；自检只核对记录能导入并读回） |
| par_app/alpha_self_test_db.py:23 | constant | SPECTRAL_COEFFICIENT | 3 | 非业务规则：alpha 自检合成库的光谱系数（编造数据，取 V1.0.x 合法范围内的值；与 tests/api/conftest.py 合成记录相同） |
| par_app/alpha_self_test_db.py:25 | constant | ELAPSED_MS | 5000.0 | 非业务规则：alpha 自检合成库的采集耗时（编造数据；elapsed_ms 列为 NOT NULL） |
| par_app/alpha_self_test_bus.py:40 | constant | SLAVE_ID | 1 | 非业务规则：自检合成网关的从站地址（编造配置） |
| par_app/alpha_self_test_bus.py:41 | constant | MBAP_BYTES | 7 | 非业务规则：Modbus TCP 报文头 MBAP 长度（协议格式，tests/support/fake_gateway.py 同值） |
| par_app/alpha_self_test_bus.py:43 | constant | ILLEGAL_FUNCTION | 1 | 非业务规则：Modbus 异常码 01（协议格式） |
| par_app/alpha_self_test_bus.py:42 | constant | EXCEPTION_FLAG | 128 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:44 | constant | READ_HOLDING | 3 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:45 | constant | READ_INPUT | 4 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:46 | constant | WRITE_SINGLE | 6 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:47 | constant | WRITE_MULTIPLE | 16 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:48 | constant | REGISTER_MASK | 65535 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:49 | constant | STOP_REGISTER | 25 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:51 | constant | CLOCK_START | 32 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:52 | constant | CLOCK_WORDS | 4 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:53 | constant | SYNC_REGISTER | 36 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:54 | literal | <module> | 2 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:54 | literal | <module> | 3 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:56 | constant | STATUS_REGISTER | 58 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:57 | constant | COEFFICIENT | 3 | 非业务规则：自检合成网关的光谱系数（编造数据，与 FakeDevice 相同） |
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 20000 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 452 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 453 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 454 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 455 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 458 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 474 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:59 | literal | <module> | 475 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:61 | constant | SPECTRUM_START | 1000 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:62 | constant | SPECTRUM_POINTS | 701 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:63 | constant | SPECTRUM_BASE | 1000 | 非业务规则：自检合成网关的编造光谱值（不是测量值） |
| par_app/alpha_self_test_bus.py:64 | constant | SPECTRUM_PERIOD | 97 | 非业务规则：自检合成网关的编造光谱形状 |
| par_app/alpha_self_test_bus.py:66 | constant | IDENTITY_START | 2047 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:67 | literal | <module> | 22136 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:67 | literal | <module> | 3 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:67 | literal | <module> | 4660 |（设备协议细节，公开版略）|
| par_app/alpha_self_test_bus.py:69 | constant | ACCEPT_BACKLOG | 4 | 非业务规则：自检合成网关 listen 队列长度 |
| par_app/alpha_self_test_bus.py:142 | literal | _answer | 5 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:146 | literal | _answer | 2 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:152 | literal | _answer | 5 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:154 | literal | _answer | 2 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:154 | literal | _answer | 6 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:154 | literal | _answer | 8 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:157 | literal | _answer | 5 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/alpha_self_test_bus.py:162 | literal | _input | 8 | 非业务规则：Modbus PDU 字段偏移（协议格式） |
| par_app/application/bus_trace.py:27 | constant | TRACE_ENTRIES | 4000 | 非业务规则：串口收发记录（#136 第二、三步，负责人 2026-10-29 R-4-2 范围一），只读已发生的收发，不影响通信。内存中环形缓存的条数，约 4 台设备 10 轮 |
| par_app/application/bus_trace.py:29 | constant | KEPT_ENTRIES | 800 | 非业务规则：串口收发记录（#136 第二、三步，负责人 2026-10-29 R-4-2 范围一），只读已发生的收发，不影响通信。设备失败或锁停时留存的最近条数，约 4 台设备两三轮 |
| par_app/application/bus_trace.py:31 | constant | KEPT_HALTS | 5 | 非业务规则：串口收发记录（#136 第二、三步，负责人 2026-10-29 R-4-2 范围一），只读已发生的收发，不影响通信。最多留存 5 次锁停的记录 |
| par_app/application/bus_trace.py:32 | constant | KEPT_FAILURES | 15 | 非业务规则：串口收发记录（#136 第二、三步，负责人 2026-10-29 R-4-2 范围一），只读已发生的收发，不影响通信。最多留存 15 次设备失败的记录 |
| par_app/application/bus_trace_summary.py:23 | constant | STOP_REGISTER | 25 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 11 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 1701 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 2047 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 4 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 400 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 54 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 59 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:25 | literal | <module> | 76 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:26 | literal | <module> | 1000 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:26 | literal | <module> | 1701 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:27 | literal | <module> | 32 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:27 | literal | <module> | 36 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:29 | constant | ECHO_BYTES | 8 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:33 | literal | <module> | 10 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。网关代答异常码 0x0A，不计为设备的帧（阶段一裁决 37，D-101 口径） |
| par_app/application/bus_trace_summary.py:33 | literal | <module> | 11 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:40 | literal | crc16_modbus | 65535 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。CRC-16/Modbus 初值 0xFFFF，与 par_app/protocol.py crc16_modbus 相同 |
| par_app/application/bus_trace_summary.py:43 | literal | crc16_modbus | 8 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。CRC 逐位处理每字节 8 位 |
| par_app/application/bus_trace_summary.py:44 | literal | crc16_modbus | 40961 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。CRC-16/Modbus 多项式 0xA001 |
| par_app/application/bus_trace_summary.py:50 | literal | _request | 8 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。请求帧最短 8 字节 / 写应答 8 字节 |
| par_app/application/bus_trace_summary.py:53 | literal | _request | 2 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:53 | literal | _request | 6 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:55 | literal | _request | 6 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:60 | literal | _request | 8 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。请求帧最短 8 字节 / 写应答 8 字节 |
| par_app/application/bus_trace_summary.py:62 | literal | _request | 3 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:62 | literal | _request | 4 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:65 | literal | _request | 4 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:66 | literal | _request | 2 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:66 | literal | _request | 5 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。最短 RTU 帧 5 字节 / 读应答长度 = 5 + 字节数 |
| par_app/application/bus_trace_summary.py:67 | literal | _request | 16 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:68 | literal | _request | 8 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。请求帧最短 8 字节 / 写应答 8 字节 |
| par_app/application/bus_trace_summary.py:82 | literal | _frames | 128 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。0x80 为异常应答标志 |
| par_app/application/bus_trace_summary.py:83 | literal | _frames | 2 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:93 | literal | _frame_at | 5 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。最短 RTU 帧 5 字节 / 读应答长度 = 5 + 字节数 |
| par_app/application/bus_trace_summary.py:96 | literal | _frame_at | 128 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。0x80 为异常应答标志 |
| par_app/application/bus_trace_summary.py:97 | literal | _frame_at | 5 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。最短 RTU 帧 5 字节 / 读应答长度 = 5 + 字节数 |
| par_app/application/bus_trace_summary.py:98 | literal | _frame_at | 3 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:98 | literal | _frame_at | 4 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:99 | literal | _frame_at | 2 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:99 | literal | _frame_at | 5 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。最短 RTU 帧 5 字节 / 读应答长度 = 5 + 字节数 |
| par_app/application/bus_trace_summary.py:100 | literal | _frame_at | 16 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:100 | literal | _frame_at | 6 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:101 | literal | _frame_at | 8 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。请求帧最短 8 字节 / 写应答 8 字节 |
| par_app/application/bus_trace_summary.py:109 | literal | _crc_right | -2 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。末 2 字节为 CRC |
| par_app/application/bus_trace_summary.py:125 | literal | _verdict | 128 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。0x80 为异常应答标志 |
| par_app/application/bus_trace_summary.py:125 | literal | _verdict | 5 | 非业务规则：串口收发记录按 Modbus RTU 帧格式解析已收到的字节（#136），只用于诊断包摘要。最短 RTU 帧 5 字节 / 读应答长度 = 5 + 字节数 |
| par_app/application/bus_trace_summary.py:134 | literal | _verdict | 2 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:134 | literal | _verdict | 3 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:134 | literal | _verdict | 4 |（设备协议细节，公开版略）|
| par_app/application/bus_trace_summary.py:183 | literal | _ms | 1000 | 非业务规则：串口收发记录（#136），秒换算为毫秒 |
