# 配置、设备登记与数据库（CONF）

由 内部文档 誊抄（规格 v1，2026-10-16）。全部条目状态为「待确认」，由负责人逐条或批量批准（R-2-2）。

### CONF-001 V1.0.2发布目录含ZIP、SHA256及验收记录
- 规则：V1.0.2 的发布产物放在 release/V1.0.2 目录，目录内须同时包含发布ZIP、该ZIP的SHA256校验文件以及验收记录。
- 来源：业务规则与变更日志_V1.0.2.md 第 11 行「V1.0.2 交付（2026-10-12）」“发布目录为 `release/V1.0.2`，包含ZIP、SHA256及验收记录”
- 状态：待确认
- 现状符合度：未验证（build_release.ps1 在 release\V1.0.2 生成 PAR_Spectrometer_V1.0.2_trial.zip 与 .sha256；验收记录不由脚本生成，属人工产物；release 目录未纳入本仓库与旧仓库，无法核对实际交付内容。V1.0.3 发布准备起 $Version 为 V1.0.3，产物在 release\V1.0.3。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $ReleaseRoot；package_release.py main

### CONF-002 保留旧V1.0.1试用包
- 规则：发布V1.0.2时，旧的 release/PAR_Spectrometer_V1.0.1_trial.zip 必须保留，不得被删除或覆盖。
- 来源：业务规则与变更日志_V1.0.2.md 第 11 行「V1.0.2 交付（2026-10-12）」“旧 `release/PAR_Spectrometer_V1.0.1_trial.zip` 保留”
- 状态：待确认
- 现状符合度：未验证（build_release.ps1 仅在 release\V1.0.2 已存在时将其整体移入 stage_backups，不触碰 V1.0.1 ZIP（按脚本推断不会删除）；发布产物不在仓库内，无法确认文件实际仍在。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $ReleaseRoot

### CONF-003 USB串口驱动由系统或厂家提供
- 规则：USB串口驱动仍需由操作系统或设备厂家提供。
- 来源：业务规则与变更日志_V1.0.2.md 第 11 行「V1.0.2 交付（2026-10-12）」“运行EXE，无需安装Python。USB串口驱动仍需系统或厂家提供。”
- 状态：待确认
- 现状符合度：符合（build_release.ps1 的 PyInstaller --add-data 只加入 logo 与 resources/fonts，不打包任何驱动程序。现状补充（非原文要求）：tools/release_metadata.py main 另复制“驱动安装说明.txt”，发布说明_V1.0.2.txt 写明不含驱动安装程序；V1.0.3 起复制的是发布说明_V1.0.3.txt，同样写明（V1.0.2 的移至 内部文档）。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $DistRoot；tools/release_metadata.py main

### CONF-004 整包须解压到可写目录运行
- 规则：发布包须整包解压到可写目录后运行EXE。
- 来源：业务规则与变更日志_V1.0.2.md 第 11 行「V1.0.2 交付（2026-10-12）」“整包解压到可写目录，运行EXE，无需安装Python。”
- 状态：待确认
- 现状符合度：未验证（本条是对使用者的运行条件，非软件行为。现状：main.create_startup_hub 仅在 config/data/logs 三个子目录下 mkdir 并创建临时文件探测可写性，不探测程序根目录本身；任一探测失败抛 OSError，main.main 提示“请将完整发布文件夹解压到当前用户可写的本地目录”并退出。程序根目录只读但三个子目录已存在且可写时仍可启动。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：main.py create_startup_hub；main.py main；par_app/runtime_paths.py application_root

### CONF-005 运行EXE无需安装Python
- 规则：发布包为便携式独立文件夹，目标电脑无需另行安装Python即可运行EXE。
- 来源：业务规则与变更日志_V1.0.2.md 第 11 行「V1.0.2 交付（2026-10-12）」“整包解压到可写目录，运行EXE，无需安装Python。”
- 状态：待确认
- 现状符合度：未验证（build_release.ps1 以 PyInstaller --onedir 打包并携带 _internal 运行时；审计 critic.md 指出冻结包未在干净 Windows 上实测。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $DistRoot；par_app/runtime_paths.py resource_path

### CONF-006 不自动替换历史库
- 规则：已有配置引用缺失或损坏数据库、进入重新配置时，不自动替换历史库。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“取消或确认重新配置。重新保存前备份原配置，不自动替换历史库。”
- 状态：待确认
- 现状符合度：不符合（缺失分支：DEF-07 已修复（PR #21）；损坏分支：DEF-26 未修）。DEF-07 修复：AppConfigStore.load_for_startup 只校验不创建，verify_configuration.verify_release_startup 断言缺失库 unavailable/old.sqlite3 未被创建。确认重新配置后 main.create_startup_hub 以空配置构造 DeviceHub，DeviceHub.__init__ 不再打开旧版默认库；界面需要库时 DeviceHub._unregistered_database 才处理：data/par_spectrometer.sqlite3 存在才打开，缺失时暂用系统临时目录中的空库，不在程序目录新建同名库。D-163 已按推荐裁决，PR #21 实现：(1) 迁移期保留临时空库占位，新界面不建库、显示空状态留待 UI 重构；(2) 占位时设置页数据库摘要显示“未登记设备”（ui_unconfigured.database_summary_text）；(3) 未登记设备（无论回退到临时空库还是已有的旧版默认库）时 DLI 经纬度输入框与“保存经纬度并重置周期”按钮置灰，保存入口 ui_unconfigured.save_dli_location 也拒绝写入；刷新 DLI 页改用只读的 ParDatabase.peek_dli_enabled_at，不再向回退库写入 dli_enabled_at。逐项排查的其余写库入口：维护、校准、对时、采集写入都经 coordinator 按登记设备写各自的库，未登记时没有设备状态，不写回退库；导出只读；“保存并应用配置”写配置文件并创建登记库，是退出未配置状态的正常入口。系统临时目录不可写、或找不到任何可用临时目录（gettempdir 本身抛错）时抛 PlaceholderDatabaseError，临时目录只探测一次，启动对话框（main.startup_failure_message）指向临时目录，不再指向程序目录（R-1-5）。未覆盖：未配置状态长时间运行、临时目录被系统清理后定时刷新可能抛 sqlite3.OperationalError（推断，未复现）。已登记库恰为该路径且缺失的分支由新测试覆盖（含构造主窗口）。DEF-26（不符合）：已登记库恰为该路径、文件头完好但数据页损坏时，确认重新配置后界面首次取库，_unregistered_database 见 is_file() 为真，对该库执行 ParDatabase.initialize（切换 WAL、CREATE TABLE IF NOT EXISTS），历史文件被改写，随后启动失败；文件头全零时抛 sqlite3.DatabaseError，文件未被改写。基线 spec/v1-extraction 上同一路径在 DeviceHub.__init__ 即已出错，不是 PR #21 引入。由 strict xfail 测试锁定。另：AppConfigStore._repair_stale_database_paths 会自动把失效路径重链到同名库，仅在 AppConfigStore.load 中调用，正常启动传 initial_config 不走该路径，不能作为本条符合的依据。已知相关缺陷 DEF-27：旧版默认库存在且有记录、未登记设备时构造主窗口崩溃（AttributeError），本条第二个测试只覆盖 DeviceHub 层“打开不替换”，不构造主窗口。）
- 冲突：缺陷：确认重新配置后无条件创建旧版默认库，缺失的已登记库恰为该路径时会自动生成同名空库，待建 issue（DEF-07，已修复（PR #21））；缺陷：已登记的旧版默认库损坏时，确认重新配置后界面仍对其执行初始化并改写文件，待建 issue（DEF-26）；D-163 已裁决：迁移期用临时空库占位，摘要显示“未登记设备”，未登记设备期间禁止写入界面设置并将相关控件置灰。
- 验证：tests/qt/test_reconfigure_no_legacy_database.py::test_confirmed_reconfiguration_does_not_create_missing_legacy_database；tests/qt/test_reconfigure_no_legacy_database.py::test_existing_legacy_database_is_still_opened_when_no_device_is_registered；tests/qt/test_reconfigure_no_legacy_database.py::test_confirmed_reconfiguration_does_not_rewrite_corrupted_legacy_database；tests/qt/test_unconfigured_settings.py::test_placeholder_database_summary_reads_unregistered_device；tests/qt/test_unconfigured_settings.py::test_dli_location_is_not_written_while_unconfigured；tests/qt/test_unconfigured_settings.py::test_unconfigured_refresh_does_not_stamp_dli_enabled_at_into_legacy_database；tests/qt/test_unconfigured_settings.py::test_unwritable_temp_directory_is_reported_as_the_cause；tests/qt/test_unconfigured_settings.py::test_missing_temp_directory_is_reported_without_probing_again
- 代码锚点：main.py create_startup_hub；par_app/app_config.py AppConfigStore.load_for_startup；par_app/device_hub.py DeviceHub.__init__；par_app/device_hub.py DeviceHub._unregistered_database；par_app/device_hub.py DeviceHub._open_placeholder_database；par_app/ui_unconfigured.py database_summary_text；par_app/ui_unconfigured.py save_dli_location；par_app/ui_unconfigured.py dli_enabled_at；main.py startup_failure_message；par_app/database.py ParDatabase.__init__

### CONF-007 发布包不含现场配置/数据库/日志/维护状态
- 规则：发布包内不得包含现场配置、采集数据库、日志或维护（待核对）状态文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“发布包不含现场配置、数据库、日志或维护状态。”
- 状态：待确认
- 现状符合度：符合（package_release.validate_release 拒绝 config/data/logs 目录下文件及 app_config.json、*.sqlite3/.db/-wal/-shm/.jsonl；维护待核对状态保存在设备数据库中，随数据库一并被拒。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：package_release.py validate_release

### CONF-008 数据库失效时可取消或确认重新配置
- 规则：已有配置引用缺失或损坏数据库并提示原因后，用户可选择取消或确认重新配置。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“已有配置引用缺失或损坏数据库时，明确提示原因，取消或确认重新配置”
- 状态：待确认
- 现状符合度：不符合（主路径符合：main.create_startup_hub：选“否”返回 None，main.main 返回 1 退出；选“是”继续启动并置 preserve_before_save。现状补充（非原文要求）：确认后以空 AppConfig 进入，不保留原登记信息供修改；verify_configuration.verify_release_startup 两分支均覆盖。例外 DEF-27：确认后若程序目录存在有记录的旧版默认库，主窗口构造崩溃，“继续启动”实际失败；DEF-26：失效的已登记库恰为旧版默认库且损坏时，确认后该文件被改写。）
- 冲突：D-141 已裁决：配置文件不可读时采用与数据库失效相同的流程，确认重新配置后以空配置进入（保存前备份原文件）；缺陷：确认重新配置后，程序目录有记录的旧版默认库会使主窗口构造崩溃，待建 issue（DEF-27）；缺陷：失效的已登记库恰为旧版默认库且损坏时，确认后该文件被改写，待建 issue（DEF-26）；alpha 档位 1（D-220）：配置或库不可用时“开始采集”答 409 config_unavailable 并指出出路；未接管时可“以空配置重新配置”（确认一次，V1.0.3 启动提问按 alpha 改写），不取锁、不开串口
- 验证：冻结待确认
- 代码锚点：main.py create_startup_hub；main.py main

### CONF-009 配置引用缺失/损坏数据库时明确提示原因
- 规则：启动时已有配置引用的数据库缺失或损坏时，须明确提示原因。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“已有配置引用缺失或损坏数据库时，明确提示原因，取消或确认重新配置”
- 状态：待确认
- 现状符合度：符合（AppConfigStore.load_for_startup 逐库检查 is_file 并以 mode=rw + PRAGMA quick_check 校验，失败抛 StartupConfigurationError，消息含设备、数据库路径、原因与配置文件路径；main.create_startup_hub 弹窗显示；verify_configuration.verify_release_startup 覆盖缺失库。现状补充（原文未涉及）：配置文件本身不可读或 JSON 非法时同样抛 StartupConfigurationError，但只含配置文件路径和原因，无设备与数据库信息。）
- 冲突：D-141 已裁决：配置文件不可读时采用与数据库失效相同的流程，确认重新配置后以空配置进入（保存前备份原文件）
- 验证：冻结待确认
- 代码锚点：par_app/app_config.py AppConfigStore.load_for_startup；main.py create_startup_hub

### CONF-010 重新配置保存前备份原配置
- 规则：从失效状态重新配置后首次保存配置前，须先备份原配置文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“取消或确认重新配置。重新保存前备份原配置，不自动替换历史库。”
- 状态：待确认
- 现状符合度：符合（AppConfigStore.save 在 preserve_before_save 为真且原文件存在时复制为 app_config.before_recovery_<时间戳>.json 后再替换；verify_release_startup 断言备份内容等于原文件。）
- 冲突：无（V1.0.3）；alpha 档位 1（D-220）：以空配置重新配置后首次保存前同样备份原配置（V1.0.3 AppConfigStore.preserve_before_save，备份名 app_config.before_recovery_<时间>.json）
- 验证：冻结待确认
- 代码锚点：par_app/app_config.py AppConfigStore.save

### CONF-011 首次启动进入设置页
- 规则：无有效配置（首次启动）时，主窗口打开后直接切换到“设置与导出”页。
- 来源：业务规则与变更日志_V1.0.2.md 第 12 行「V1.0.2 交付（2026-10-12）」“首次启动进入设置页，未保存配置前不采集；已有配置引用缺失或损坏数据库时”
- 状态：待确认
- 现状符合度：不符合（主路径符合：main.main 在 hub.config.configured 为假时 setCurrentIndex(settings_tab_index)；release_self_test 断言首页为设置页。例外 DEF-27：程序目录已有旧版默认库 data/par_spectrometer.sqlite3 且至少 1 条采集记录、没有登记设备时，MainWindow 构造即抛 AttributeError，进不了设置页；tests/qt/test_reconfigure_no_legacy_database.py::test_main_window_opens_on_existing_legacy_database_without_registered_device 以 strict xfail 锁定。）
- 冲突：缺陷：旧版默认库有记录且未登记设备时主窗口构造崩溃，进不了设置页，待建 issue（DEF-27）
- 验证：冻结待确认
- 代码锚点：main.py main；par_app/release_self_test.py run_release_self_test

### CONF-012 第三方依赖与CPython许可随包
- 规则：发布包须附带第三方依赖许可文本与 CPython 许可。
- 来源：业务规则与变更日志_V1.0.2.md 第 13 行「V1.0.2 交付（2026-10-12）」“冻结版使用随包字体。第三方依赖与CPython许可随包提供；”
- 状态：待确认
- 现状符合度：符合（tools/release_metadata.py main 递归收集依赖分发包的 license/notice 文件到 third_party_licenses，复制 sys.base_prefix/LICENSE.txt，生成 THIRD_PARTY_NOTICES.txt；validate_release 要求 THIRD_PARTY_NOTICES.txt 存在。engineering.md 提示依赖 base_prefix 的 LICENSE.txt，换 Python 发行版可能失败。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：tools/release_metadata.py main；package_release.py validate_release

### CONF-013 闭源分发前须确认PyQt5授权
- 规则：对外闭源分发前，须确认已取得 PyQt5 商业授权或履行相应开源许可义务。
- 来源：业务规则与变更日志_V1.0.2.md 第 13 行「V1.0.2 交付（2026-10-12）」“闭源对外分发前须确认PyQt5商业授权或相应开源许可义务”
- 状态：待确认
- 现状符合度：未验证（法务前置条件，无代码可判；审计 extensibility.md 列为高风险待法务确认。THIRD_PARTY_NOTICES.txt 已写入相关提示。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：无：法务/发布流程前置条件，代码中仅 tools/release_metadata.py 写入提示文本

### CONF-014 随包保存Noto Sans SC字体与OFL许可
- 规则：resources/fonts 须保存 Noto Sans SC 原始字体文件及其 OFL 许可文本。
- 来源：业务规则与变更日志_V1.0.2.md 第 13 行「V1.0.2 交付（2026-10-12）」“`resources/fonts` 保存Noto Sans SC原始字体与OFL许可，冻结版使用随包字体。”
- 状态：待确认
- 现状符合度：不符合（本仓库基线 dd1b5a8 与当前分支的 resources/fonts 均只有 NotoSansSC.ttf，缺 OFL.txt；而 build_release.ps1 $Fonts 检查、package_release.validate_release 与 release_self_test.run_release_self_test 均要求 OFL.txt 存在，当前仓库直接构建或自检会失败。old/ 下旧目录含 OFL.txt 只作参考，不作为本仓库符合的证据（R-0-1）。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $Fonts；package_release.py validate_release；par_app/release_self_test.py run_release_self_test

### CONF-015 打包前检查必需资源
- 规则：打包前须检查必需资源。
- 来源：业务规则与变更日志_V1.0.2.md 第 14 行「V1.0.2 交付（2026-10-12）」“构建、输出均使用版本子目录。打包前检查必需资源”
- 状态：待确认
- 现状符合度：符合（按 D-139 裁决，“必需资源”即两份脚本现有的检查清单，缺失即拒绝：build_release.ps1 检查 logo.png、NotoSansSC.ttf、OFL.txt 与恰好一份 DOCX/PDF 手册，缺失即抛错；package_release.validate_release 检查 PAR_Spectrometer.exe、_internal/logo.png、字体、OFL、build_manifest.json、THIRD_PARTY_NOTICES.txt，缺失即抛 ValueError。）
- 冲突：D-139 已裁决：采用两份打包脚本现有的检查清单作为“必需资源”，缺失即拒绝构建或打包；D-142（发布、许可与验收流程条目的领域归属，已转规则提案）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $Fonts；package_release.py validate_release

### CONF-016 拒绝配置、数据库与现场日志入包
- 规则：打包时若发现配置、数据库或现场日志文件，必须拒绝生成发布包。
- 来源：业务规则与变更日志_V1.0.2.md 第 14 行「V1.0.2 交付（2026-10-12）」“打包前检查必需资源，拒绝配置、数据库和现场日志入包。”
- 状态：待确认
- 现状符合度：符合（package_release.validate_release 对 config/data/logs 下文件、app_config.json、sqlite/db/wal/shm/jsonl 抛 ValueError；engineering.md 评价为设计良好。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：package_release.py validate_release

### CONF-017 构建与输出使用版本子目录
- 规则：构建中间产物、PyInstaller 输出和发布目录均须位于以版本号命名的子目录（build/V1.0.2、dist/V1.0.2、release/V1.0.2）。
- 来源：业务规则与变更日志_V1.0.2.md 第 14 行「V1.0.2 交付（2026-10-12）」“构建、输出均使用版本子目录。打包前检查必需资源”
- 状态：待确认
- 现状符合度：符合（build_release.ps1 的 $BuildRoot/$DistRoot/$ReleaseRoot 均拼接 $Version。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $BuildRoot；build_release.ps1 $DistRoot；build_release.ps1 $ReleaseRoot

### CONF-018 重建须先生成手册再打包
- 规则：重新构建发布包时，须先运行 tools/generate_software_manual.py，再运行 build_release.ps1。
- 来源：业务规则与变更日志_V1.0.2.md 第 14 行「V1.0.2 交付（2026-10-12）」“先运行 `tools/generate_software_manual.py`，再运行 `build_release.ps1`”
- 状态：待确认
- 现状符合度：未验证（build_release.ps1 只检查项目根恰有一份 *_V1.0.2.docx 与 *.pdf，否则拒绝构建；不执行生成脚本，也不检查手册是否为本次重新生成，复用旧手册同样通过。需构建执行记录才能确认顺序已履行。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：build_release.ps1 $Manual；tools/generate_software_manual.py main

### CONF-019 自检不替代真机与干净Windows验收
- 规则：发布自检通过不能替代真实设备验收和干净 Windows 环境验收，两者仍须单独完成。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“此自检不替代真实设备或干净Windows验收”
- 状态：待确认
- 现状符合度：未验证（流程约束，无代码可判；审计 critic.md 指出冻结包与 build_release.ps1 均未在 Windows 实测，实机测试当前暂缓。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：无：验收流程要求，不对应代码

### CONF-020 自检仅使用临时数据库
- 规则：发布自检内部只能使用临时目录与临时数据库，不读写现场配置和数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“输出五页截图和JSON，内部仅使用临时数据库并禁止硬件访问。”
- 状态：待确认
- 现状符合度：符合（run_release_self_test 在 tempfile.TemporaryDirectory 下调用 create_hub，并断言配置为空、store 文件不存在。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：par_app/release_self_test.py run_release_self_test

### CONF-021 自检参数入口且报告路径须不存在
- 规则：EXE 支持参数 --release-self-test <报告路径>，报告路径须为不存在的路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“EXE支持 `--release-self-test <不存在的报告路径>`”
- 状态：待确认
- 现状符合度：不符合（main.main 识别 argv==3 且 argv[1]==--release-self-test；run_release_self_test 最后以 report.open('x') 写报告，已存在则失败。例外：自检先在 report.parent 下保存 page_<n>.png 截图，再创建报告。报告路径为尚不存在的 page_0.png～page_4.png 之一时，截图先占用该路径，随后报告创建失败（FileExistsError 未捕获）；且同目录已有的 page_<n>.png 会被截图覆盖。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：main.py main；par_app/release_self_test.py run_release_self_test

### CONF-022 自检报告父目录必须存在
- 规则：发布自检的报告父目录必须事先存在，自检不自动创建目录。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“报告父目录必须存在，输出五页截图和JSON”
- 状态：待确认
- 现状符合度：符合（run_release_self_test 不创建父目录，截图保存到 report.parent，报告用 open("x") 写入；父目录不存在时自检失败（以未捕获异常退出，无友好提示）。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：par_app/release_self_test.py run_release_self_test

### CONF-023 自检禁止硬件访问
- 规则：发布自检过程中禁止任何硬件（串口/TCP）访问。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“输出五页截图和JSON，内部仅使用临时数据库并禁止硬件访问。”
- 状态：待确认
- 现状符合度：符合（run_release_self_test patch par_app.coordinator.ParModbusClient 为抛 AssertionError，并在结束时 client.assert_not_called()。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：par_app/release_self_test.py run_release_self_test

### CONF-024 自检输出五页截图和JSON
- 规则：发布自检须输出主窗口五个页签的截图及一份 JSON 结果报告。
- 来源：业务规则与变更日志_V1.0.2.md 第 15 行「V1.0.2 交付（2026-10-12）」“报告父目录必须存在，输出五页截图和JSON”
- 状态：待确认
- 现状符合度：符合（run_release_self_test 遍历 window.tabs（实时概览、历史回放、光谱计算、光积累计算、设置与导出共5页）保存 page_<n>.png，最后写 JSON（version/frozen/passed/error）。）
- 冲突：D-142（发布、许可与验收流程条目的领域归属）
- 验证：冻结待确认
- 代码锚点：par_app/release_self_test.py run_release_self_test

### CONF-025 不改写旧库、旧quality_json与旧DLI资格
- 规则：旧库、旧 quality_json 和旧 DLI 资格不改写。
- 来源：业务规则与变更日志_V1.0.2.md 第 22 行「单次采集策略（2026-10-11）」“旧库、旧 `quality_json` 和旧DLI资格不改写”
- 状态：待确认
- 现状符合度：符合（按 D-138 裁决选 A：par_app 中无 UPDATE acquisitions，旧记录的 quality_json、dli_eligible 不被改写，DLI 查询以 COALESCE(dli_eligible,1) 兼容（verify_polling.PollingTests.test_quality_schema_upgrade_preserves_old_records），按 D-126 另在读取时排除标明复核未完成的旧记录，只筛选不改写（tests/unit/test_dli_legacy_review.py::test_filter_does_not_rewrite_history_or_schema，见 DLI-007）；ParDatabase.initialize 缺列时 ALTER TABLE ADD COLUMN、缺表时 CREATE TABLE IF NOT EXISTS、请求 PRAGMA journal_mode=WAL，属裁决允许的结构变更。）
- 冲突：D-138 已裁决：选 A：已有记录内容不改，允许补空列、补空表并切换 WAL 日志模式
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.initialize；par_app/database.py ParDatabase.dli_samples

### CONF-026 不回写或自动修复#5186等旧数据
- 规则：冻结读取上线后，不回写或自动修复历史数据（如光谱仪2历史#5186的跨倍率分包异常记录）。
- 来源：业务规则与变更日志_V1.0.2.md 第 32 行「统一冻结读取（2026-10-11）」“冻结读取针对光谱仪2历史#5186的跨倍率分包异常，不回写或自动修复旧数据”
- 状态：待确认
- 现状符合度：符合（代码中无修复/回写历史 acquisitions 的路径；ParDatabase.initialize 仅补列。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.initialize

### CONF-027 CCT整数显示不批量改写旧库
- 规则：CCT 改为整数显示后，不批量改写旧库。
- 来源：业务规则与变更日志_V1.0.2.md 第 37 行「实时概览与历史回放（2026-10-11）」“旧记录读取时兼容整数显示，不批量改写旧库”
- 状态：待确认
- 现状符合度：符合（按 D-138 裁决选 A：par_app 中无 UPDATE acquisitions，不为旧记录回填 software_metrics_json.cct_kelvin，cct_kelvin 只在 ParDatabase.save_acquisition 写新记录时生成；ParDatabase.initialize 缺列补列、缺表建表并请求 WAL 模式，属裁决允许的结构变更。原条目中的“旧记录读取时兼容整数显示”已拆出，属 UI 领域。）
- 冲突：D-138 已裁决：选 A：已有记录内容不改，允许补空列、补空表并切换 WAL 日志模式
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.save_acquisition；par_app/database.py ParDatabase.initialize

### CONF-028 保存后库路径固定，改名改地址不换库
- 规则：配置保存后设备数据库路径即固定写入配置；之后修改设备名称或从站地址不改变所用数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“不会因此自动登记。保存后固定路径，改名称或从站地址不换库”
- 状态：待确认
- 现状符合度：符合（DeviceHub.apply 将解析后的绝对路径写回 device.database_path 并保存；verify_configuration 断言改名“Renamed”、改地址 8 后 database_path 不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub.apply；par_app/ui.py MainWindow._device_row_config

### CONF-029 既有库与旧版路径不迁移
- 规则：既有设备数据库和旧版单设备库路径保持原位，不做文件迁移。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“保存后固定路径，改名称或从站地址不换库；既有库和旧版路径不迁移”
- 状态：待确认
- 现状符合度：符合（AppConfigStore._migrate_legacy 让设备直接指向旧库路径（不复制/移动）；_repair_stale_database_paths 仅在原绝对路径失效时改指向同名文件，不移动文件。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/app_config.py AppConfigStore._migrate_legacy；par_app/app_config.py AppConfigStore._repair_stale_database_paths

### CONF-030 未指定库时按首次登记名生成默认路径
- 规则：新设备未指定数据库时，按首次登记名称生成 data/devices/<设备名>.sqlite3。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“新设备未指定数据库时，按首次登记名称生成 `data/devices/<设备名>.sqlite3`”
- 状态：待确认
- 现状符合度：未验证（V1.0.2）；D-140 中的缺陷修复部分（DEF-18）已完成（PR #23）：safe_database_filename 先按 V1.0.2 规则转换；结果不超过 MAX_SAFE_FILENAME_LENGTH=100 个字符、不含其他控制字符且不是 Windows 保留名（CON/PRN/AUX/NUL/COM1-9/LPT1-9/CONIN$/CONOUT$ 及上标 1-3，不区分大小写，按第一个点号前的主干判断）时与 V1.0.2 完全相同，已生成的默认路径不变（已保存 database_path 的设备不再走默认路径）。否则另把控制字符 \x00-\x1f、\x7f 替换为“_”，带扩展名的保留名在主干后加“_”，截断到 100-1-FILENAME_DIGEST_LENGTH 个字符（再去除尾部空格和点）后接“_”和 V1.0.2 结果的 SHA-256 前 8 位（COM1 → COM1_xxxxxxxx，COM1.backup → COM1_.backup_xxxxxxxx）；因此新规则不会把 V1.0.2 下不同的名称合成同一个文件名或导出目录（#23 复审 major），V1.0.2 下替换后相同的名称仍然相同，照现状由 DeviceHub.apply 按路径重复拒绝保存（D-140 裁决）。（V1.0.2 现状：普通名称下符合：DeviceConfig.resolved_database_path → default_device_database_path（DEFAULT_DEVICE_DATABASE_DIR=data/devices），DeviceHub.apply 相对 store.root 解析。例外（原文未定义）：safe_database_filename 把 \ / : * ? " < > | 及换行、制表符替换为“_”并去除首尾空格和点，替换后为空时回退为 device<N>，此时文件名不等于设备名；不同名称替换后相同（如 A/B 与 A_B）会因路径重复被 DeviceHub.apply 拒绝；审计 robustness-ui Bug 4：未处理 Windows 保留名、其他控制字符与超长名，路径可能不可用。）
- 冲突：D-140 已裁决：允许任意名称并按现状规则转换文件名，替换后重名照现状拒绝保存；另补上 Windows 保留名和超长名的转换（DEF-18 已修复（PR #23））
- 验证：tests/unit/test_safe_database_filename.py::test_windows_reserved_names_are_rewritten；tests/unit/test_safe_database_filename.py::test_names_that_only_look_reserved_are_unchanged；tests/unit/test_safe_database_filename.py::test_control_characters_are_replaced；tests/unit/test_safe_database_filename.py::test_over_long_name_is_truncated_and_the_default_library_can_be_created；tests/unit/test_safe_database_filename.py::test_truncation_never_leaves_trailing_space_dot_or_reserved_name；tests/unit/test_safe_database_filename.py::test_empty_results_use_the_fallback；tests/unit/test_safe_database_filename.py::test_ordinary_names_keep_the_v102_result；tests/unit/test_safe_database_filename.py::test_new_rules_never_merge_names_that_v102_kept_apart；tests/unit/test_safe_database_filename.py::test_names_that_v102_merged_stay_merged；tests/unit/test_safe_database_filename.py::test_new_rules_keep_exactly_the_v102_groups_of_equal_names；tests/qt/test_export_device_folder.py::test_long_names_that_differ_after_the_limit_export_to_different_files
- 代码锚点：par_app/models.py default_device_database_path；par_app/models.py DeviceConfig.resolved_database_path；par_app/models.py safe_database_filename；par_app/device_hub.py DeviceHub.apply

### CONF-031 空白行按“光谱仪N”预览不自动登记
- 规则：设备登记表空白行的数据库文件按“光谱仪N”预览，但仅预览不会使该行被自动登记。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“空白行按「光谱仪N」预览，不会因此自动登记”
- 状态：待确认
- 现状符合度：符合（_device_row_config 空名称回退为 f"光谱仪{row+1}" 供预览；ensure_device_count 补的草稿行 enabled=False；devices_from_form 只收已登记行或用户勾选/填写过的行。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_row_config；par_app/ui.py MainWindow._update_device_database_preview；par_app/ui.py MainWindow.devices_from_form；par_app/app_config.py ensure_device_count

### CONF-032 自动生成路径已存在时拒绝复用
- 规则：自动生成的默认数据库路径已存在文件时，保存被拒绝；用户须明确选择该已有文件或另选新文件。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“自动生成的路径已存在时拒绝直接复用，须明确选择已有文件或另选新文件”
- 状态：待确认
- 现状符合度：符合（DeviceHub.apply：未显式指定 database_path 且 path.exists() 时抛 ValueError("默认数据库文件已存在…")；verify_configuration 覆盖拒绝及显式选择后接受。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub.apply；par_app/ui.py MainWindow._choose_device_database

### CONF-033 设备间禁止共用数据库
- 规则：不同设备不得共用同一个数据库文件，保存时检测到共用即拒绝。
- 来源：业务规则与变更日志_V1.0.2.md 第 74 行「设置与导出布局（2026-09-20）」“须明确选择已有文件或另选新文件；设备间禁止共用数据库”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-09 已修复（PR #24）：DeviceHub.apply 用 _shares_database 判重，路径键为 os.path.normcase 后再 casefold（各平台都按不区分大小写比较，Linux 等大小写敏感文件系统上只差大小写的两个路径也会被拒绝；该范围按阶段一预授权采用推荐，见 内部文档 裁决 63，涉及 PR #24），路径已存在时再与已登记且存在的库做 os.path.samefile 比较（硬链接、短文件名等别名）；默认库命名 data/devices/<设备名>.sqlite3、已保存路径和库文件均不变，设备名称判重仍区分大小写。（V1.0.2 现状：DeviceHub.apply 以 Path.resolve() 集合去重，显式同路径能拦截（verify_configuration 覆盖）；但审计 robustness-ui Bug 3：设备名仅大小写不同（East/east）且用默认路径时，在 macOS 上（Path 为 POSIX 路径，大小写不同即不相等；APFS 默认不区分大小写）两条路径都通过集合判重，随后指向同一文件，未被拦截。Windows 上 Path 为 WindowsPath，比较本身忽略大小写，East/east 会被判为重复；8.3 短文件名等其他文件别名未验证。）
- 冲突：缺陷：macOS 上设备名仅大小写不同时默认库路径判重失效，两台设备指向同一文件，待建 issue（DEF-09；Windows 不复现；已修复（PR #24））
- 验证：tests/qt/test_device_database_dedup.py::test_default_paths_differing_only_in_case_are_rejected；tests/qt/test_device_database_dedup.py::test_chosen_paths_differing_only_in_case_are_rejected；tests/qt/test_device_database_dedup.py::test_chosen_paths_that_are_the_same_existing_file_are_rejected；tests/qt/test_device_database_dedup.py::test_distinct_names_keep_separate_default_databases；tests/qt/test_device_database_dedup.py::test_two_distinct_existing_databases_are_saved；tests/qt/test_device_database_dedup.py::test_new_default_database_next_to_existing_database_is_saved
- 代码锚点：par_app/device_hub.py DeviceHub.apply；par_app/device_hub.py _shares_database

### CONF-034 采集审计保存在 quality_json
- 规则：单次采集的采集审计保存在 SQLite 的 quality_json 中。
- 来源：业务规则与变更日志_V1.0.2.md 第 93 行「单次采集与分段 DLI（2026-10-11）」“采集审计保存在SQLite的 `quality_json` 中，无需增加数据库列”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._capture_once 把 quality dict 以 json.dumps 放入记录的 quality_json，成功与失败分支均写入；ParDatabase.save_acquisition 将 quality_json 字段 INSERT 到 acquisitions。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._capture_once；par_app/database.py ParDatabase.save_acquisition

### CONF-035 失败停止开关默认关闭且旧配置缺键取默认
- 规则：DeviceConfig.auto_stop_on_failure 默认 False；读取旧 config/app_config.json 时若缺少该键，同样取 False，不改变现场采集节奏。
- 来源：业务规则与变更日志_V1.0.2.md 第 116 行「失败停止开关（2026-09-30）」“默认 `False`，旧 `config/app_config.json` 缺少该键时同样取默认值”
- 状态：待确认
- 现状符合度：符合（par_app/models.py DeviceConfig 字段默认 False，from_dict 仅取已有键；测试 verify_polling.py test_failure_exit_switch_config_round_trip。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/models.py DeviceConfig；par_app/models.py DeviceConfig.from_dict

### CONF-036 失败停止不参与登记行判定
- 规则：判断设备登记表某一行是否构成登记设备时不考虑“失败停止”勾选；在空行上只勾选“失败停止”不会登记新设备。
- 来源：业务规则与变更日志_V1.0.2.md 第 117 行「失败停止开关（2026-09-30）」“「失败停止」不参与设备登记行的判定，空行上勾选也不会凭空登记设备”
- 状态：待确认
- 现状符合度：符合（par_app/ui.py MainWindow.devices_from_form 仅按已登记、启用勾选、名称、数据库路径判定行，不读 device_stop_boxes。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.devices_from_form

### CONF-037 已保存配置重启后自动使用
- 规则：用户保存过的配置在软件重启后自动加载并使用，无需再次确认。
- 来源：业务规则与变更日志_V1.0.2.md 第 171 行「多设备重构：第 1 阶段（2026-09-17）」“旧版配置仅回填供确认；本阶段保存过的配置在重启后自动使用”
- 状态：待确认
- 现状符合度：符合（AppConfigStore.load_for_startup 读取 config/app_config.json（configured 为 True 时 run 直接采集）；verify_configuration.py main 覆盖保存后重载。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/app_config.py AppConfigStore.load_for_startup；par_app/app_config.py AppConfigStore.save

### CONF-038 旧版配置仅回填供确认
- 规则：检测到旧版配置时，只将其回填到配置界面供用户确认，不直接作为已提交配置开始采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 171 行「多设备重构：第 1 阶段（2026-09-17）」“旧版配置仅回填供确认；本阶段保存过的配置在重启后自动使用”
- 状态：待确认
- 现状符合度：符合（AppConfigStore._migrate_legacy 返回的 AppConfig 未设置 configured（默认 False），run 不采集直至用户保存。V1.0.2 中旧库 connection 为非对象 JSON 时启动崩溃，已修复为不迁移（PR #25，旧仓库 旧仓库 issue 19）。对象但字段类型错误（如 timeout_seconds、slave_id 为 "abc"）按 D-164 裁决处理：PR #25 中 AppConfigStore._typed_legacy_connection 逐字段校验迁移实际用到的字段（transport、serial_port、host、tcp_port、slave_id、baudrate、parity、timeout_seconds、acquisition_interval_seconds；旧 connection 的 database_path 迁移不用，不校验，其类型错误照常迁移，与 V1.0.2 一致）的类型（数字文本照常转换；整数字段只接受整数、整数值浮点如 3.0 和整数文本，3.9 这类非整数浮点不截断、按类型错误处理；非有限值或超出浮点范围的数值同样按类型错误处理），不符时跳过迁移、不抛出，返回未配置默认值并把原因记入 legacy_migration_note；设置页连接状态在用户保存配置前显示“旧版连接配置无法读取，已跳过回填：<原因>”（DeviceHub.idle_status）。）
- 冲突：D-164 已裁决：旧连接配置为对象但字段类型错误时跳过迁移进入未配置状态，并在设置页状态栏提示一句原因
- 验证：tests/unit/test_app_config_legacy_migration.py::test_non_object_legacy_connection_is_not_migrated；tests/unit/test_app_config_legacy_migration.py::test_object_legacy_connection_still_migrates；tests/unit/test_app_config_legacy_migration.py::test_null_legacy_connection_is_nothing_to_migrate；tests/unit/test_app_config_legacy_migration.py::test_migration_note_is_cleared_after_legacy_connection_is_repaired；tests/unit/test_app_config_legacy_migration.py::test_wrongly_typed_legacy_connection_field_skips_migration；tests/unit/test_app_config_legacy_migration.py::test_unused_legacy_database_path_type_does_not_block_migration；tests/unit/test_app_config_legacy_migration.py::test_numeric_text_legacy_fields_are_converted_and_migrated；tests/unit/test_app_config_legacy_migration.py::test_integral_float_legacy_integer_fields_are_migrated_without_loss；tests/qt/test_legacy_migration_notice.py::test_settings_status_explains_skipped_legacy_migration；tests/qt/test_legacy_migration_notice.py::test_settings_status_has_no_legacy_notice_when_migration_succeeds
- 代码锚点：par_app/app_config.py AppConfigStore._migrate_legacy；par_app/app_config.py AppConfigStore.load_for_startup；par_app/app_config.py AppConfigStore._typed_legacy_connection；par_app/device_hub.py DeviceHub.idle_status；par_app/ui.py MainWindow.refresh_settings_console

### CONF-039 首次配置提交前不采集
- 规则：首次配置提交（保存）前，软件不进行采集。
- 来源：业务规则与变更日志_V1.0.2.md 第 171 行「多设备重构：第 1 阶段（2026-09-17）」“首次配置提交前不采集。旧版配置仅回填供确认”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator.run 在 config.configured 为假时空转；DeviceHub.apply 才置 configured=True；verify_configuration.py verify_release_startup 断言新启动 configured 为假。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.run；par_app/device_hub.py DeviceHub.apply

### CONF-040 总线通信参数由用户选择
- 规则：总线通信参数（串口、波特率、校验位等）由用户在设置中选择，软件不自动决定。
- 来源：业务规则与变更日志_V1.0.2.md 第 172 行「多设备重构：第 1 阶段（2026-09-17）」“总线通信参数由用户选择；每台设备分别填写名称、从站 ID 和独立数据库路径”
- 状态：待确认
- 现状符合度：符合（MainWindow.bus_config_from_form 从表单读取 transport/串口/波特率/校验/周期。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.bus_config_from_form；par_app/models.py BusConfig

### CONF-041 每台设备分别登记名称、ID和独立库
- 规则：每台设备分别填写名称、从站ID和独立数据库路径。
- 来源：业务规则与变更日志_V1.0.2.md 第 172 行「多设备重构：第 1 阶段（2026-09-17）」“每台设备分别填写名称、从站 ID 和独立数据库路径”
- 状态：待确认
- 现状符合度：符合（MainWindow._device_row_config 按行生成 DeviceConfig(name, slave_id, enabled, database_path, auto_stop_on_failure)。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_row_config；par_app/models.py DeviceConfig

### CONF-042 保存后待当前事务完成再切换配置
- 规则：点击“保存并应用全部配置”后，后台在当前通信事务完成后才切换到新配置，不打断进行中的事务。
- 来源：业务规则与变更日志_V1.0.2.md 第 173 行「多设备重构：第 1 阶段（2026-09-17）」“点击「保存并应用全部配置」，后台完成当前事务后切换”
- 状态：待确认
- 现状符合度：符合（DeviceHub.apply→PollingCoordinator.apply_config 入任务队列，由后台线程在两台设备事务之间的 _process_tasks 执行 _apply_config。注意 _poll_all_devices 见到队列非空即放弃本轮剩余设备（审计 BUG-2，见第189行条目）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator.apply_config；par_app/coordinator.py PollingCoordinator._apply_config

### CONF-043 编辑配置不影响当前采集
- 规则：在设置页编辑配置但未保存应用时，当前采集不受影响。
- 来源：业务规则与变更日志_V1.0.2.md 第 173 行「多设备重构：第 1 阶段（2026-09-17）」“编辑配置不影响当前采集；点击「保存并应用全部配置」，后台完成当前事务后切换”
- 状态：待确认
- 现状符合度：符合（表单修改不写入 hub.config，只有 MainWindow.save_local_settings→DeviceHub.apply 才提交。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.save_local_settings；par_app/device_hub.py DeviceHub.apply

### CONF-044 一个按钮统一提交总线与设备登记
- 规则：“保存并应用全部配置”一次统一提交总线参数与设备登记，不分开提交。
- 来源：业务规则与变更日志_V1.0.2.md 第 174 行「多设备重构：第 1 阶段（2026-09-17）」“「保存并应用全部配置」统一提交总线参数与设备登记”
- 状态：待确认
- 现状符合度：符合（MainWindow 中 device_apply_button 即 bus_apply_button；save_local_settings 以 app_config_from_form（总线+设备）整体调用 DeviceHub.apply。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.save_local_settings；par_app/ui.py MainWindow.app_config_from_form

### CONF-045 名称、ID或库路径重复时拒绝提交
- 规则：提交配置时，设备名称、从站ID或数据库路径重复会拒绝提交。
- 来源：业务规则与变更日志_V1.0.2.md 第 174 行「多设备重构：第 1 阶段（2026-09-17）」“统一提交总线参数与设备登记；重复名称、ID 或数据库路径会拒绝提交”
- 状态：待确认
- 现状符合度：不符合（V1.0.2）；DEF-09 已修复（PR #24）：DeviceHub.apply 用 _shares_database 判重，路径键为 os.path.normcase 后再 casefold（各平台都按不区分大小写比较，Linux 等大小写敏感文件系统上只差大小写的两个路径也会被拒绝；该范围按阶段一预授权采用推荐，见 内部文档 裁决 63，涉及 PR #24），路径已存在时再与已登记且存在的库做 os.path.samefile 比较（硬链接、短文件名等别名）；默认库命名 data/devices/<设备名>.sqlite3、已保存路径和库文件均不变，设备名称判重仍区分大小写。（V1.0.2 现状：DeviceHub.apply 对名称（strip 后区分大小写）、slave_id（1~247）去重，重复抛 ValueError，MainWindow.save_local_settings 弹“配置未应用”；显式同一路径也能拦截。例外：数据库路径以 Path.resolve() 后的集合比较判重，不按目标文件系统的文件身份判重；已确认的反例限于 macOS：Path 为 POSIX 路径，大小写不同即不相等，而 APFS 默认不区分大小写，两个尚不存在的默认路径如 East.sqlite3 与 east.sqlite3 会通过比较，随后指向同一文件（与 CONF-033 同一边界，审计 robustness-ui Bug 3）。Windows 上 Path 为 WindowsPath，比较忽略大小写（PureWindowsPath 下 East.sqlite3、east.sqlite3 相等，集合长度为1），该反例不成立；8.3 短文件名等其他文件别名未验证。）
- 冲突：缺陷：macOS 上大小写不同的数据库路径判重失效，重复路径未被拒绝，待建 issue（DEF-09；Windows 不复现；已修复（PR #24））
- 验证：tests/qt/test_device_database_dedup.py::test_default_paths_differing_only_in_case_are_rejected；tests/qt/test_device_database_dedup.py::test_chosen_paths_differing_only_in_case_are_rejected；tests/qt/test_device_database_dedup.py::test_distinct_names_keep_separate_default_databases；tests/qt/test_device_database_dedup.py::test_two_distinct_existing_databases_are_saved；tests/qt/test_device_database_dedup.py::test_new_default_database_next_to_existing_database_is_saved
- 代码锚点：par_app/device_hub.py DeviceHub.apply；par_app/device_hub.py _shares_database；par_app/ui.py MainWindow.save_local_settings

### CONF-046 修改设备名称不移动数据库
- 规则：修改设备名称后不自动移动或重命名其数据库，继续使用原数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 175 行「多设备重构：第 1 阶段（2026-09-17）」“默认库路径在首次提交时固定，修改设备名称不自动移动数据库”
- 状态：待确认
- 现状符合度：符合（database_path 已固定在配置中，改名后 MainWindow._device_row_config 仍带原路径；verify_configuration.py main 改名后断言 database_path 不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow._device_row_config；par_app/device_hub.py DeviceHub.apply

### CONF-047 默认库路径在首次提交时固定
- 规则：设备未指定数据库路径时，默认库路径在首次提交时确定并写入配置，之后保持不变。
- 来源：业务规则与变更日志_V1.0.2.md 第 175 行「多设备重构：第 1 阶段（2026-09-17）」“默认库路径在首次提交时固定，修改设备名称不自动移动数据库”
- 状态：待确认
- 现状符合度：符合（DeviceHub.apply 将 resolved_database_path 解析后写回 device.database_path 再保存；verify_configuration.py main 断言提交后库位于 data/devices。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub.apply；par_app/models.py DeviceConfig.resolved_database_path

### CONF-048 未保存的改名不影响当前名称和采集
- 规则：在设置页修改设备名称但不保存时，当前设备名称和采集均不受影响。
- 来源：业务规则与变更日志_V1.0.2.md 第 180 行「多设备重构：第 1 阶段（2026-09-17）」“打开设置页修改名称但不保存，确认当前设备名称和采集不受影响”
- 状态：待确认
- 现状符合度：符合（名称只在 DeviceHub.apply 提交后经 config_applied 更新 hub.config；未保存的表单修改不进入 PollingCoordinator。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/device_hub.py DeviceHub._on_config_applied；par_app/ui.py MainWindow.save_local_settings

### CONF-049 保存新名称后沿用同一数据库
- 规则：保存设备新名称并生效后，该设备仍使用同一数据库，历史记录不丢失。
- 来源：业务规则与变更日志_V1.0.2.md 第 181 行「多设备重构：第 1 阶段（2026-09-17）」“保存新名称，确认生效后仍使用同一数据库，历史记录不丢失”
- 状态：待确认
- 现状符合度：符合（PollingCoordinator._rebuild_states 按数据库路径复用 DeviceRuntimeState；database_path 在首次提交时已固定；verify_configuration.py main 改名后断言路径不变。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/device_hub.py DeviceHub.apply

### CONF-050 重启后恢复已保存配置
- 规则：退出并重新启动软件后，恢复上次已保存的配置。
- 来源：业务规则与变更日志_V1.0.2.md 第 182 行「多设备重构：第 1 阶段（2026-09-17）」“退出再启动，确认恢复已保存配置；串口不可用时不能自动换用其他端口”
- 状态：待确认
- 现状符合度：符合（main.py 调用 AppConfigStore.load_for_startup 读取 config/app_config.json。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/app_config.py AppConfigStore.load_for_startup

### CONF-051 仅支持光谱仪型号，不接入其他设备功能
- 规则：软件仅支持光谱仪型号，不接入温湿度、CO₂、风扇、加热或探头链功能。
- 来源：业务规则与变更日志_V1.0.2.md 第 335 行「产品边界」“仅支持光谱仪型号，不接入温湿度、CO₂、风扇、加热或探头链功能。”
- 状态：待确认
- 现状符合度：符合（在 par_app 中 grep 温湿度/CO2/CO₂/风扇/加热/探头链/humid/fan 均无结果。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：无：负向产品边界，par_app 中无对应实现（grep 无结果）

### CONF-052 支持 Modbus RTU 与 TCP Client
- 规则：通信支持 Modbus RTU 与 Modbus TCP Client 两种方式。
- 来源：业务规则与变更日志_V1.0.2.md 第 336 行「产品边界」“支持 Modbus RTU 与 Modbus TCP Client。”
- 状态：待确认
- 现状符合度：符合（models.Transport = Literal['rtu','tcp']；ParModbusClient._build_client 分别建 ModbusSerialClient 与 _DeadlineTcpClient。边界：通信维护仅支持 RTU（CommunicationMaintenance.connection）。依赖声明：TCP 路径向 read_*/write_register(s) 传 device_id=，并覆写 ModbusTcpClient.send(request, addr)；device_id= 自 pymodbus 3.10.0 起才有（API_changes.rst「API changes 3.10.0」：slave= 改为 device_id=），requirements.txt 原写 pymodbus>=3.6，装 3.6–3.9 时 TCP 读写全部失败（旧仓库 #4）。requirements.txt 下限现为 pymodbus>=3.10（修复旧仓库 #4），requirements.lock 锁 3.16.1；该依赖下限由 tests/unit/test_dependency_floor.py::test_pymodbus_floor_matches_tcp_api_in_use 守护，它只覆盖依赖声明与 TCP 调用签名，不覆盖 RTU/TCP 实际收发。）
- 冲突：无
- 验证：冻结待确认；tests/unit/test_dependency_floor.py::test_pymodbus_floor_matches_tcp_api_in_use
- 代码锚点：par_app/models.py Transport；par_app/protocol.py ParModbusClient._build_client；par_app/maintenance.py CommunicationMaintenance.connection

### CONF-053 采集数据永久保存在本地 SQLite
- 规则：采集数据永久保存在本地 SQLite 数据库中。
- 来源：业务规则与变更日志_V1.0.2.md 第 338 行「产品边界」“数据永久保存于本地 SQLite；UI 读取数据库，通信由后台采集服务独占。”
- 状态：待确认
- 现状符合度：符合（ParDatabase 使用每台设备独立的 SQLite 文件；par_app 中没有删除采集记录或按期限清理的代码（仅有外键 ON DELETE CASCADE 定义）。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase；par_app/database.py ParDatabase.save_acquisition

### CONF-054 光谱运算结果只在当前会话，不入库
- 规则：光谱运算结果只保留在当前会话，不作为永久采集记录写入数据库。
- 来源：业务规则与变更日志_V1.0.2.md 第 339 行「产品边界」“光谱运算结果仅驻留当前会话，可导出 CSV 或 Excel，不作为永久采集记录入库。”
- 状态：待确认
- 现状符合度：符合（MainWindow.run_operation 把结果放在 self.current_result，不调用任何数据库写入方法。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/ui.py MainWindow.run_operation

### CONF-055 采集审计无需增加数据库列
- 规则：单次采集的采集审计无需增加数据库列。
- 来源：业务规则与变更日志_V1.0.2.md 第 93 行「单次采集与分段 DLI（2026-10-11）」“采集审计保存在SQLite的 `quality_json` 中，无需增加数据库列”
- 状态：待确认
- 现状符合度：未验证（原文语气为“无需”，不是禁止新增列的约束。现状：审计写入既有的 quality_json 列；ParDatabase.initialize 对旧库仅按需补 quality_json、dli_eligible 两列，单凭代码快照无法判断这两列是否早于 2026-10-11 本次变更已存在。）
- 冲突：无
- 验证：冻结待确认
- 代码锚点：par_app/database.py ParDatabase.initialize；par_app/coordinator.py PollingCoordinator._capture_once

### CONF-056 应用配置失败时恢复为原配置并提示
- 规则：后台切换到新保存的配置时，若为新配置重建设备运行时状态失败（如新数据库无法打开），恢复为切换前的配置：总线参数、轮询周期、设备登记和各设备的运行时状态（含“失败停止”退出标记）、已移出登记设备的保留状态都与切换前一致，原设备按原配置继续采集；总线状态提示“应用配置失败：<原因>”，不再显示“调度异常”；采集轮中失败时本轮在失败处结束，下一轮按 POLL-036 从本轮开始计满原配置的周期；两轮之间失败时不改变已安排的下一轮时刻。
- 来源：D-178 裁决 B（docs/spec/pending-decisions.md D-178「裁决」行；负责人 2026-10-18，按推荐，内部文档）“B：回滚到旧配置并保持旧设备继续采集，提示「应用配置失败：<原因>」，设置页保留未生效的新配置供修改后重试”
- 状态：已批准 2026-10-18 负责人
- 现状符合度：不符合（按 R-2-1 指 V1.0.2 基线：PollingCoordinator._apply_config 先把 _config 换成新配置再重建，重建失败时不回滚，失败设备之前的复用状态已被就地改写（键、设备配置、连接参数、解除“失败停止”退出并写库），异常显示为“调度异常：<原因>”，之后按新配置的总线和周期、旧的运行时状态运行（DEF-29）。PR #43（分支 fix/apply-config-rollback）修复后：PollingCoordinator._rebuild_states 先为全部设备建好新状态、打开新库和读取维护会话，这一步抛错时不改动任何现有状态对象、_retired_states 和维护会话，全部成功后才改写复用状态的字段并一次替换；PollingCoordinator._apply_config 在重建失败时把 _config 恢复为原对象并抛 ConfigApplyError，run() 的异常分支对它原样显示“应用配置失败：<原因>”，其余异常仍为“调度异常：<原因>”；下一轮安排、断开总线与约 1 秒等待沿用 run() 现有异常路径（#16/#33），config_applied 不发出，DeviceHub.config 保持原配置。重建前 _apply_config 已断开总线，各设备在线状态变为“总线已断开”，下一轮按原配置重新连接，这一点与成功应用时相同。未实现：D-178 B 中“设置页保留未生效的新配置供修改后重试”。失败后“保存并应用全部配置”按钮保持禁用（只有 config_applied → devices_changed 会重新启用它），设置页内部提示仍为“配置已保存，等待当前事务结束后应用。”（该标签隐藏，不直接显示），用户只能重启软件后重试，见 DEF-31（strict xfail tests/qt/test_apply_config_failure_restart.py::test_apply_button_is_enabled_again_after_a_failed_background_apply），另开 fix PR；“应用配置失败：<原因>”只在总线状态中显示到下一轮写入“正在连接…/总线已连接”为止，最长约一个周期。未覆盖：DeviceHub.apply 在入队前已把新配置写入配置文件，回滚不恢复文件，重启后按新配置启动，可能进不了设置页，见 D-183（重启验证 tests/qt/test_apply_config_failure_restart.py）；Windows 实机未验证。合并前不改基线判定。）
- 冲突：缺陷：应用配置失败时不回滚，配置与运行时状态不一致（DEF-29，修复见 PR #43）；D-178（已裁决 B）；D-183（已裁决 B，2026-10-27 顾问在 #71 确认：配置文件也写回原配置；未实现，见 #146）；缺陷：失败后“保存并应用全部配置”按钮保持禁用，不能修改后重试，待建 issue（DEF-31）；alpha 档位 1（D-221）：后台应用失败后设置页标“未生效”（状态 config_apply_error）并允许立即重新保存，有意偏离 DEF-31；配置文件是否写回原配置随 D-183
- 验证：tests/qt/test_apply_config_rollback.py::test_failed_rebuild_restores_config_states_and_retired_states；tests/qt/test_apply_config_rollback.py::test_failed_apply_config_mid_round_keeps_polling_the_old_configuration_and_reports_it；tests/qt/test_apply_config_rollback.py::test_failed_apply_config_between_rounds_keeps_the_scheduled_round
- 代码锚点：par_app/coordinator.py PollingCoordinator._apply_config；par_app/coordinator.py PollingCoordinator._rebuild_states；par_app/coordinator.py PollingCoordinator.run；par_app/coordinator.py ConfigApplyError
