# 本地接口合同草案 v0（阶段二路线 C）

- 日期：2026-10-17
- 状态：**草案**，不是规格条目，不参与 `tools/quality/spec_check.py` 的条目统计（本文的编号用 `API-` 前缀，不属于规格领域编号）。每个接口在落地 PR 中先写合同测试，再实现；接口行为以所引用的规格条目为准，本文与规格冲突时以规格为准（R-0-2）。
- 方案总述：内部文档；页面清单：`docs/design/ui-v2-pages.md`。
- 引用的 services 函数位于 `par_app/services/`（阶段一分支 `refactor/services-*`，尚未合并），名称以合并后的代码为准。

---

## 1. 通用约定

### 1.1 地址与鉴权

- 基础路径 `http://127.0.0.1:<随机端口>/api/v0`，服务只监听 `127.0.0.1`。
- 外壳启动服务时拿到一次性启动码，调用 `POST /api/v0/session` 换成仅本机、`HttpOnly`、`SameSite=Strict` 的会话 Cookie。其他接口没有有效会话一律返回 401。
- 服务校验 `Host` 必须是 `127.0.0.1:<端口>`，有 `Origin` 时必须同源，否则返回 403（防 DNS 重绑定和其他网页跨站调用）。

### 1.2 数据格式

- 编码 UTF-8，JSON。
- **时间**：库里原样存的时间字段（如 `acquired_at`）原样返回，字段名不变；另给 `*_text` 字段，是 `format_beijing_time` 处理后的显示文本。查询参数里的时间用与库内相同的北京时间 ISO 格式（`YYYY-MM-DDTHH:MM:SS.mmm`），服务端不做时区换算。
- **数值与显示文本**：凡是界面要显示的指标，接口同时给原始数值（`value`，缺失为 `null`）和显示文本（`text`，由 services 层生成，含单位、小数位、「—」）。**前端只显示 `text`，不自行换算或取整**（方案第 4 节「前端不算数」）。
- **设备标识** `key`：四个位置 `p1`–`p4`（UI-255），与 `AppConfig` 中的登记顺序一致。
- 每个读取接口的响应都带 `as_of`（服务端取数的北京时间，经 Clock 接口取得）和 `source`（`snapshot` 快照 / `live_ro` 实时只读 / `live` 采集中），便于前端判断数据新旧。

### 1.3 错误语义（R-1-5）

错误响应统一为：

```json
{"error": {"code": "database_unavailable", "message": "当前设备或计算页来源的数据库不可访问：<路径>", "retryable": true, "detail": "..."}}
```

| HTTP | code | 含义 | retryable | 前端要求 |
|---|---|---|---|---|
| 400 | `invalid_argument` | 参数缺失、格式错、起始时间晚于结束时间 | false | 指出哪个参数；不清空已显示的数据 |
| 401 | `unauthenticated` | 没有会话或会话过期 | false | 提示重启程序 |
| 403 | `forbidden_origin` | Host/Origin 校验失败 | false | — |
| 403 | `feature_disabled` | alpha 当前档位未开放该功能（方案 2.5） | false | 显示「alpha 中未开放」，不要伪装成成功 |
| 404 | `device_not_found` / `record_not_found` | 位置未登记，或记录不存在 | false | 记录不存在时按规格清空详情（UI-032） |
| 409 | `busy` | 同类操作正在进行（如快照导入未完成） | true | 保留现状，稍后重试 |
| 409 | `snapshot_changed` | 请求所带的设备库标识已不是该位置当前的库（配置换了库；光谱计算与导出，D-208，2.0 节） | false | 重读来源与记录列表，清除计算结果 |
| 503 | `database_unavailable` | 库文件不可访问、被锁、损坏 | true | **保留最近一次有效数据**，状态处显示原因并允许重试（UI-316，见修复 PR #13；路径写法见裁决 45、47） |
| 500 | `internal` | 未预期异常；服务记日志（含回溯），进程不退出。按出错位置分两层（D-225 问题 1，R-1-5）：HTTP 线程上的请求（查询、快照、导出）为 `retryable: true`，记入 `GET /tier` 的 `fault`（`kind: "request"`）并发 `service_error` 事件，不停止任何东西；服务 Qt 主线程上的接管或维护代码（请求经网关带到主线程的调用）为 `retryable: false`，`message` 为“已停止采集”的全文（#119 起档位不变，原为切回档位 0），服务随即停止接管（见 API-17 `service_error`） | true / false | 同 503；主线程那一层显示 `message` 全文，档位与接管状态按 `GET /tier` 重读 |
| 500 | `export_failed` | 写导出文件失败；`detail` 写明结果目录、已完成的文件与错误（EXP-020） | true | 显示 `detail` 全文，保留计算结果 |

硬性规则：

1. **区分「空」和「错」。** 查询成功但没有记录，返回 200 和空数组；库出错返回 503。服务端不得在出错时返回空数组冒充「没有数据」。
2. **不伪造成功。** 写入类接口失败时返回错误，不返回 200（R-1-5）。
3. **路径提示。** 503 的 `message` 中的库路径取异常里实际出错的库；取不到就不写路径，不冒用当前设备的路径（裁决 47）。
4. 任何错误都不清除设备锁存状态，不改历史记录。

---

## 2. 第一批：只读接口（档位 0 可用）

### 2.0 数据来源：只读 alpha 自己采集的设备库（issue #82，负责人 2026-10-26）

本节取代下文各接口中「档位 0 读已导入快照」的说法（方案 S-3，D-203、D-204、D-207～D-211 与 D-213～D-215 中与快照有关的部分）：

- 设备是 alpha 自己档位 1 配置（`<数据目录>/config/app_config.json`，格式同 V1.0.3）中登记的设备，位置 p1～p4 即配置中的顺序；每台的库在 `<数据目录>/data/devices/` 下（16_ 3.2），不在其中的库拒绝读取（409 `config_unavailable`）。
- API-03、API-05～07、API-09～15、API-22、API-23、API-26 都读这些设备库，只读（例外只有两处，都与 V1.0.3 相同：API-10 第一次读取某台设备而库中没有 DLI 启用时间时，写入 `app_settings.dli_enabled_at` 这一行，见 D-228 A；`PUT /devices/{key}/dli/location` 写入 `app_settings.dli_location` 这一行，见 #116；`mode=ro`，不带 `immutable=1`：采集同时在写，同 API-09 实时概览）。SQLite 读 WAL 库时会在库旁建立空的 `-wal` 与 `-shm`，只在 alpha 自己的设备目录中。
- 档位 0 不读配置：四个位置都为未配置，按位置读数据的接口 404 `device_not_found`（`message` 说明档位 0 不读取设备数据）；页面为空，不报错。登记了设备但还没有记录时，各接口照常返回空列表或零条。
- 响应的 `source` 为 `live_ro`。字段名 `snapshot_id` 暂沿用（#83 改名），含义改为设备库标识：同一位置换了另一个库（配置已改）时变化，带旧标识的光谱计算与导出请求 409 `snapshot_changed`（D-208、EXP-052 的保护不变）。`imported_at`、`snapshot_path` 恒为 null，API-11 的 `source_path` 同 `database_path`。
- API-03 `display_state`：停用的设备为 `disabled`（灰色“停用”，UI-259）；库不在 alpha 设备目录中的设备为 `fault`，光谱计算来源与导出设备都不列它，按位置读数据 409 `config_unavailable`。
- 事件流断开期间应用的配置（`config_applied` 不重放）：页面在事件流重新连上时重读设备清单；所看位置换了设备库时 DLI 页重读（保留所选日期）。API-03、API-26 的 `tier` 为当前档位（同 `/health`）。
- 「采集已暂停」（API-09 `paused`、API-10 `paused`）：alpha 未接管、维护中或锁停时为 true，同 API-09 实时概览（D-213）。
- API-20、API-21（导入、列出快照）标为废弃：仍可调用，但导入的快照不在任何页面显示；已导入的快照文件不删除，清理与删除代码见 #83。

### API-01 健康检查与运行信息

- `GET /api/v0/health`（无需会话）
- 响应：`version`（如 `2.0.0-alpha.1`）、`build_commit`、`tier`（0/1/2，方案 2.5）、`started_at`。
- 用途：外壳确认服务已就绪。

### API-02 关于

- `GET /api/v0/about`
- 响应：`product_name`、`version`、`release_date`、`contact`（文案与 V1.0.x 关于区一致）、`logo_url`。
- 规格：UI-093、UI-095。

### API-03 设备列表（顶部「查看设备」）

- `GET /api/v0/devices`
- 响应：固定 4 项数组，每项：
  - `key`、`position`（1–4）
  - `configured`（bool）、`enabled`（bool）、`name`、`address_text`（用于悬停全文）
  - `display_state`：`normal` / `disabled` / `fault` / `unconfigured`，前端据此取颜色令牌
  - `database_name`（文件名）、`database_path`（完整路径，只用于悬停）
- 设备信息来自 alpha 自己档位 1 配置中登记的设备（2.0 节）；档位 0 四个位置都为未配置。`fault` 只在档位 1 以上出现。
- 规格：UI-255、UI-259（停用优先，DEF-20 的裁决后行为）、UI-260、UI-261、UI-262、UI-263、UI-044。
- 说明：切换查看设备只是前端状态，不调用接口改变后台采集范围（UI-040、UI-257）。

### API-04 公共状态栏

- `GET /api/v0/status`
- 响应：`bus`（`level`、`message`）、`acquisition`（`level`、`message`，含「采集停止中」「恢复未确认」等）、`maintenance`（bool）、`halt`（全局停止原因，可空）、`alerts`（每台启用设备的异常：`key`、`name`、`time_text`、`failures`、`threshold`、`text`）。
- 档位 0：`bus.message` 固定为「未连接（alpha 只读）」，`alerts` 为空。
- 档位 1 以上数据来源：协调器公共方法 `bus_message()`、`halt_reason()`、`states()`、`status_text()`。
- 规格：UI-007、UI-137、UI-140、UI-142、UI-143、UI-144、UI-145、UI-147、UI-150、UI-253。

### API-05 历史记录列表

- `GET /api/v0/devices/{key}/acquisitions?start=&end=`
- 参数：`start`、`end` 必填（前端首次打开时用默认范围，UI-049；结束时间不自动推进，UI-050）。
- 响应：
  - `range`：服务端实际使用的 `start`/`end` 原样回显（前端定时刷新和切换设备时沿用，UI-047）
  - `limit`：500；`limit_reached`：是否达到上限（UI-048，判定方式在接口 PR 中与 V1.0.2 实现核对）
  - `items[]`：`seq`、`id`、`acquired_at`、`acquired_at_text`、`result_text`、`exposure_text`、`exposure_style`（`normal`/`warn`，按 DEF-21/D-154：新单采记录的欠曝光、过曝光与正常同色，旧记录保留警告色）
- 数据来源：`ParDatabase.recent_acquisitions(500, start, end)`（对设备库只读，2.0 节）。
- 规格：UI-020、UI-028、UI-046、UI-047、UI-048、UI-050、UI-052、UI-070、UI-071、UI-305 起的列宽类条目由前端实现。
- 空结果：200 + 空 `items`，前端清空详情（UI-032）。

### API-06 历史记录详情（54 项指标）

- `GET /api/v0/devices/{key}/acquisitions/{id}`
- 响应：
  - `header`：采集状态、设备名、ID、时间、曝光、耗时（UI-036、UI-063）
  - `success`（bool）、`elapsed_text`、`review_text`（「采集校验」，新记录「单次读取完成」，旧记录缺标记为「未记录」）
  - `groups[]`：7 组，每组 `title` + `items[]`（`key`、`label`、`text`）；共 54 项，顺序和分组与 V1.0.x 一致
  - 失败记录：`groups` 中全部指标的 `text` 为「—」，保留 `elapsed_text`、`review_text`（UI-030）
- services：`metrics.decode_record_metrics`、`metrics.record_metric_values`、`metrics.format_metric`、`metrics.cct_value`、`metrics.scaled_par`。
- 规格：UI-003、UI-005、UI-006、UI-014、UI-017、UI-018、UI-025、UI-029、UI-030、UI-031、UI-033、UI-273、UI-304；口径 MATH-007（PAR ÷10）。

### API-07 单条光谱

- `GET /api/v0/devices/{key}/acquisitions/{id}/spectrum`
- 响应：`wavelength_start`（350）、`wavelength_step`（1）、`points`（701 个原始值）；记录无光谱时 404 `record_not_found`，`detail` 写「无光谱」。
- 来源：`ParDatabase.get_spectrum(id)`。
- 规格：UI-037、UI-057、UI-065、UI-173。

### API-08 参考曲线

- `GET /api/v0/reference-curves`
- 响应：四条曲线（叶绿素 A、叶绿素 B、McCree、人眼明视觉）各自的 `name`、`x[]`、`y[]`（已归一化，与 V1.0.x 叠加时同一数据）。内容固定，可长期缓存。
- 来源：`math_ops.chlorophyll_weight_curves`、`mccree1972_weights`、`photopic_weights`。不得在前端另存一份曲线数据（红线第 4 条：权重曲线只有一个来源）。
- 规格：UI-168、UI-278。

### API-09 实时概览：最新记录

- `GET /api/v0/devices/{key}/latest`
- 响应：
  - `display_record`：最近一条成功且有光谱的记录的 `id`、`acquired_at_text`、`age_seconds`（距今秒数，服务端用 Clock 计算）、`exposure_text`（UI-053、UI-170）
  - `kpis[]`：6 项 `label`、`text`，顺序固定（UI-012）
  - `core_metrics[]`：图内核心读数 4 行（`metrics.overview_core_metrics`）
  - `entries[]`：图内 24 项（`metrics.overview_metric_entries` + `format_entry_value`）
  - `latest_attempt`：最新一次采集（含失败）的 `success`、`acquired_at_text`；失败时前端显示「本轮失败 · 保留最近有效数据」（UI-055）
  - `stale`：是否已超过两个轮询周期（至少 120 秒）未有新记录（UI-171）
  - 无成功光谱：`display_record` 为 `null`，前端空图并显示最近失败时间（UI-054），「全部指标」按钮禁用（UI-013）
- 光谱另调 API-07。
- 来源：`ParDatabase.latest_successful_spectrum()`、`recent_acquisitions(1)`。
- 规格：UI-009、UI-010、UI-012、UI-013、UI-053、UI-054、UI-055、UI-059、UI-060、UI-170、UI-171。
- 数据来自设备库（2.0 节）；页面在档位 1 用 `GET /acquisition/devices/{key}/latest`（`live`），档位 0 没有设备、页面为空。
- 「全部指标」（UI-009、UI-018）：档位 1 的实时记录同样可用（#106，同 V1.0.3），内容为 API-06 `GET /devices/{key}/acquisitions/{display_record.id}` 的 `groups`，只在其 `snapshot_id` 与概览的相同时显示；弹窗打开后保持打开时那条记录的标题与数值（V1.0.3 的弹窗为模态、内容固定），同一位置换了库则关闭。

### API-10 DLI

- `GET /api/v0/devices/{key}/dli[?date=YYYY-MM-DD]`
- 参数：`date` 可选（北京日期）。不给为当前周期（＝V1.0.3）；给出时取该日 23:59:59.999 时正在进行的周期（同一个 `dli.dli_period`，国内经度即该日日出起算的周期）；给的是今天时取当前时刻正在进行的周期（＝不给 `date`，今天日出前也不会给出尚未开始的周期），不得晚于今天，格式错误或日期不存在为 400。档位 0 的这一口径见 D-204 问题 2。
- 响应（全部由服务端按 V1.0.3 口径算好，前端不做任何积分、取整或换算）：
  - `period`：`start`、`end`（北京时间毫秒）、`date`（起点所在日期）、`current`（当前时刻是否在本周期内）、`text`（周期行全文，`dli.dli_period`，DLI-015、DLI-022、UI-178；D-165 空档期显示刚结束的周期）
  - `location`：`latitude`、`longitude`、`stored`（库中是否保存了可读位置；否则为默认北京坐标）、`coordinates_text`（“纬度 x.xxxx °N，经度 y.yyyy °E”）、`text`（周期行悬停说明：位置与启用时间）。来源：设备库 `app_settings` 的 `dli_location`，解析同 `ParDatabase.load_dli_location`，**只读不写**（UI-153、DLI-024、DLI-050）
  - `enabled`：`at`、`stored`、`text`。来源：`dli_enabled_at`，同 `ParDatabase.peek_dli_enabled_at`；缺失时按 V1.0.3 `load_dli_enabled_at` 写入当前时刻（D-228 A），之后只计入此后的记录（DLI-014）；库中没有 `app_settings` 表或写入失败时按当前时刻、不写回，`stored` 为 false
  - `observed_until`：本次统计截至的观测时刻（服务时钟），四项共用（DLI-031）
  - `poll_cycle_seconds`、`poll_cycle_source`、`poll_cycle_record_at`、`max_gap_seconds`（`dli.max_gap_seconds`，DLI-010、DLI-013）、`gap_text`。轮询周期取记录自带的值（D-204 问题 1 裁决 D，边界见 D-206）：本周期内截至时刻（含）之前最近一条成功记录（`success = 1`，带时区后缀的时间除外，同 `dli_samples`）`quality_json` 中的 `poll_cycle_seconds`；本周期内没有成功记录时取周期之前最近一条。该值缺失或不可用（`quality_json` 为空或无法解析、不是对象、不是数字（字符串、布尔值也不算）、非有限、超出浮点范围的整数（如 10⁴⁰⁰）、不在 40～3600 秒内）时用默认配置的 60 秒（＝原 A），不往更早的记录找。`poll_cycle_source` 为 `record`（取自记录）或 `default`；`poll_cycle_record_at` 为所查看那条记录的采集时间（库中原样），没有成功记录时为 null。一个周期只用一个允许间隔（同 V1.0.3）。`gap_text` 写明来源：“允许间隔 360 秒（按轮询周期 300 秒计，取自 2026-10-18 08:00:00.000 的采集记录）”“允许间隔 120 秒（按默认轮询周期 60 秒计：… 的采集记录中没有可用的轮询周期）”“允许间隔 120 秒（按默认轮询周期 60 秒计：本周期及之前没有成功的采集记录）”。**与 V1.0.3 的差异**：V1.0.3 用显示时的运行配置；这里用记录采集时的配置，最后一条记录之后改过轮询周期、或记录里没有该字段（V1.0.0 时代）时两者可能不同
  - `snapshot_text`（数据来源说明：“数据来自本机 2.0 采集的设备库：<路径>”）、`paused`（未接管、维护或锁停时为 true，2.0 节）
  - 启用时间（D-228 A，负责人 2026-10-27）：与 V1.0.3 相同，DLI 第一次读取已登记设备而库中没有 `dli_enabled_at` 时写入当前时刻（只写这一行 `app_settings`，不建库、不改表结构，已有值不覆盖），这是本接口唯一的写入；写入之前的记录不计入
  - `metrics[]`：4 项，顺序固定（`dli.DLI_METRICS`：PPFD、McCree YPFD、叶绿素 A、叶绿素 B），每项：
    - `key`、`title`（V1.0.3 图标题）
    - `summary`：`DliSummary` 的全部字段（时间为北京时间毫秒或 null；`state` 为“积分中 / 部分累计 / 有效数据不足”）
    - `header`：`total_text`（“已累计：x.xxx mol·m⁻²”，无有效区间为“—”，DLI-034～036）、`state_text`（含“采集已暂停”“数据未更新（时长）”后缀，DLI-043、DLI-044）、`state_level`（`ok` / `warn` / `muted`，前端据此取颜色令牌）、`times_text`（首个有效 / 累计截至 / 最新有效，DLI-037、DLI-039）、`coverage_text`、`coverage_tooltip`（截至时间与起始、内部、尾部未覆盖，DLI-053）。文本复制自 `DliCanvas._update_header`（`services/dli_display.py`）
    - `y_max`：纵轴上限（下限固定为 0，UI-184）
    - `series`：`times`、`offsets_seconds`（距周期起点的秒数）、`cumulative`（累计 mol·m⁻²；断档处为 `null`，前端据此断线，不补零，DLI-012、DLI-029、DLI-047～049）
  - `interruptions[]`：本周期内、启用时间之后的 `dli_interruptions` 行（`occurred_at`、`occurred_at_text`、`reason`），按时间（DLI-005、DLI-012）
  - `ticks[]`：横轴刻度（`offset_seconds`、`at`、`text`、`narrow`）；两端与跨日零点为“月-日 换行 时:分”，图宽 ≥ 700 px 每 3 小时、否则只显示 `narrow` 的 6 小时刻度（UI-183，复制自 `DliCanvas._layout_plot`）
- 来源：设备库上与 `ParDatabase.dli_samples` 相同的只读 SQL（`readonly.SnapshotDli`，资格判定共用 `database.DLI_ELIGIBLE_SQL`，含 D-126）；`dli.dli_period`、`dli.max_gap_seconds`、`dli.build_series`、`dli.integrate`（与 V1.0.3 `MainWindow.refresh_diagnostics` 同一代码）。
- 规格：DLI-001～056 的积分口径（DLI-008～029 为主），UI-153、UI-178～185（显示）。
- 错误：设备库不可读 503；库中启用时间无法解码（含该行存成 SQL NULL——V1.0.x 自己的库该列 NOT NULL，但快照是任意文件，V1.0.3 读它同样报错；PR #47 评审 N-4）或位置无法计算日出为 500 `internal`、`retryable: false`（只这一台设备的 DLI 不可看，其他页照常）。V1.0.0 时代没有 `app_settings`、`dli_interruptions` 表和 `quality_json`、`dli_eligible` 列的库按缺失（NULL）读，与 V1.0.x 打开时补列的结果相同。

- `PUT /devices/{key}/dli/location`（#116，负责人 2026-10-27 书面批准，R-4-2 第 3 条）：页面的“保存经纬度并重置周期”。请求体 `latitude`（-89.9～89.9，北纬为正）、`longitude`（-180～180，东经为正），按 4 位小数保存（同 V1.0.3 的两个输入框）；可带与 GET 相同的 `date`。只写该设备库 `app_settings.dli_location` 一行，语句与 `ParDatabase.save_dli_location` 相同（`INSERT … ON CONFLICT(key) DO UPDATE`，`value_json` 为 `{"latitude": …, "longitude": …}`，`updated_at` 为服务时钟的北京时间）；不改启用时间、历史记录与表结构，库中没有 `app_settings` 表时 503 `database_unavailable`、不建表。只读模式 403 `feature_disabled`；库不在 alpha 数据目录 409 `config_unavailable`（2.0 节）；超出范围或不是数字 400 `invalid_argument`。成功后按新位置返回所示周期（同 GET 的 `DliDay`），输入框只编辑不保存时周期不变（DLI-025）

### API-11 光谱计算：来源列表

- `GET /api/v0/operation-sources`
- 响应：`items[]`，每个可选的库一项：`key`、`position`、`device_name`、`snapshot_id`（设备库标识，2.0 节）、`database_path`（设备库）、`source_path`（同 `database_path`）、`imported_at`（恒为 null）、`display_state`（故障或停用也可选，UI-268；现为 `normal`）、`tooltip`（悬停全文：设备库路径，UI-265）；`initial_a`、`initial_b`：A 取第一个、B 取第二个，只有一个时相同，没有时为 null（UI-156）。
- 每台登记的设备一项（停用的也列出，UI-268），库为该设备的库（2.0 节）；档位 0 没有任何一项。
- 规格：UI-155、UI-156、UI-254、UI-264、UI-265、UI-268。

### API-12 光谱计算：候选记录

- `GET /api/v0/operation-sources/{key}/spectra[?keep=<id>]`
- 响应：`snapshot_id`、`limit`（500）、`items[]`：最近 500 条成功且为完整 701 点的记录，新的在前：`id`、`acquired_at`、`acquired_at_text`、`label`（“#ID | 北京时间”，记录框的一项）；`keep` 所指的记录不在 500 条内但仍可用时附在最后（UI-204）；`empty_text`（“无可用光谱”）。为空时前端显示“无可用光谱”并禁止执行（UI-207、UI-269）。
- 来源：`ParDatabase.operation_spectra(500)` 的同一条 SQL（`readonly.SnapshotOperations`）。

### API-13 光谱计算：最近时间匹配

- `GET /api/v0/operation-sources/{key}/nearest?acquired_at=`
- 响应：`snapshot_id`；`match`：`id`、`acquired_at`、`acquired_at_text`、`label`、`time_difference_seconds`（该记录比 `acquired_at` 晚多少秒）；无候选或 `acquired_at` 无法解析时为 `null`（＝V1.0.3）。
- 来源：`ParDatabase.nearest_operation_spectrum` 的同一条 SQL 与时间换算（全库搜索，不受 500 条限制；旧 UTC 与北京时间统一换算；等距先取较早时间再按 ID；不设隐含容差；不改设备时钟）。
- 何时匹配（首次进入、改 A、改 B 的库、重新打开开关）由页面按 V1.0.3 的规则决定（UI-201～203）。
- 规格：UI-195 至 UI-203、UI-288。

### API-14 光谱计算：两图与执行

- `POST /api/v0/operations/inputs`（选中记录后的 A、B 两图；POST 只因参数多，不写任何数据）
  - 请求：`a`、`b`：`{source, id, snapshot_id?}` 或 null。`snapshot_id` 是页面拿到列表时的设备库标识，该位置换了设备库时 409 `snapshot_changed`（D-208）。
  - 响应：`a`、`b`：`title`（“光谱 A：设备 · #ID”或“光谱 A：未选择记录”）、`legend`、`valid`（成功且完整 701 点）、`device_name`、`acquired_at(_text)`、`values`（原始值 / 10^光谱系数，不归一化，UI-211）、`y_range`（两侧都有效时共用，UI-209）；`valid`；`time_difference`（`seconds`、`text`“采集时间差：B 比 A 晚 x.xxx 秒”、`tooltip`，UI-206、UI-208）；`placeholder`（结果图中央“等待执行计算”或“缺少有效的 A/B 光谱”，UI-210、UI-216）。
- `POST /api/v0/operations/compute`（POST 只因参数多，不写任何数据）
  - 请求：`a`、`b`（必填）、`operation`：`add` / `subtract` / `divide`
  - 响应：上面的全部字段，另加 `result`：`title`（“计算结果：比值 A/B”）、`legend`、`y_label`、`ratio`、`values`（完整结果 701 点，无效为 null，不截断）、`plotted`（绘制的点：比值中未通过 2% 显示筛选的为 null，前端断线不补零，UI-218）、`y_range`（结果独立的纵轴，UI-214、UI-221、UI-222）、`reference_line`（1 倍虚线是否在范围内，UI-220）、`ratio_note`、`empty_text`（无可绘制比值点时，UI-219）、`threshold`（比值显示共同阈值 T，MATH-015）。
- 来源：`math_ops.combine`、`math_ops.ratio_display_mask`；标题、纵轴范围等显示规则复制到 `services/operation_display.py`，由 Qt 对照测试锁定。
- 记录不可用为 404 `record_not_found`（“光谱 A 没有可用的光谱”），库不可读为 503；前端保留上一次两图并可重试，结果在任何输入变化后作废（UI-158、UI-187、UI-266）。
- 规格：UI-157、UI-158、UI-208 至 UI-223 中的数值与文本类条目；MATH-008～018、020、021；版面类由前端实现。

### API-25 光谱计算：页面文本与应用说明

- `GET /api/v0/operations/page`
- 响应：`title`（“光谱计算”，UI-167）；`operations`（三种运算与名称，MATH-011）、`default_operation`；`texts`（控件文字与悬停提示、空状态文字）；`axis`（350–1050 nm、宽/窄两套刻度与 680 px 分界，UI-192～194）；`guide`（摘要四段、完整说明的章节、跳转、参考链接、弹窗 960×760 与 90%，UI-226～232、UI-235～250；只给文字结构，不给 HTML）；`export`（格式对话框文字、默认勾选 CSV、alpha 导出目录，D-207）。
- 来源：`services/operation_display.py`、`services/operation_guide.py`（复制自 V1.0.3，Qt 对照测试逐字比较 HTML）。

### API-15 设备统计（设置页状态区）

- `GET /api/v0/devices/{key}/summary`
- 响应：`total`、`latest_text`（`ParDatabase.acquisition_summary`）、`database_name`、`database_size_text`（「xx.xx MB」，1 MB = 1,000,000 字节，UI-077）。
- 规格：UI-077、UI-080。
- 实现（档位 0，D-209）：另给 `latest`（库中原样）、`records_text`（“最近采集：… · 共 N 条”）、`database_text`（设备库文件名与当前大小，同 V1.0.3 `database_summary_text`）、`serial_text`（设备库 `app_settings.par_device_identity`，UI-081）、`status_text`、`poll_cycle_text`（最近一条成功记录 `quality_json.poll_cycle_seconds`，D-206 的取值规则）；没有 `latest_text`，以 `records_text` 代替。

### API-26 设置与导出页：只读配置视图与导出区文字

- `GET /api/v0/settings`
- 响应：`title`、`groups`（通信设置、设备登记、采集记录导出、设备状态与最近日志，UI-075）、`tier`、`read_only_text`；`bus[]`（7 行 `label`、`text`）、`config_text`、`config_note`；`device_columns`（UI-099）、`devices[]`（4 个位置：`configured`、`state_text`（未导入为“未配置”，UI-261）、`name`、`slave_id_text`、`enabled_text`、`fail_stop_text`、`database_name`（源库文件名）、`database_path`、`snapshot_path`、`snapshot_id`、`imported_at`、`tooltip`（EXP-066））；`export`（导出区全部文字、`ranges`（EXP-068）、`default_range`（EXP-048）、`formats`（EXP-014）、`directory`（D-210））。
- 档位 0：不读配置，总线参数一律为“档位 0 不读取配置”，`devices` 四个位置都为未配置。档位 1：`devices` 为登记的设备（导出设备下拉，EXP-044），从站地址、启用采集、失败停止为 null（配置由页面左侧的 `GET /acquisition-config` 编辑）。本组接口不保存、不应用配置。

### API-16 日志

- `GET /api/v0/devices/{key}/logs`
- 响应：最近 300 条中筛选后最多 50 条，最新在前：`id`、`time_text`、`level`、`category_text`（中文类别）、`message`、`details`（完整原文，供详情弹窗）。
- 来源：`ParDatabase.recent_diagnostics(300)`。
- 规格：UI-078、UI-079、UI-100 至 UI-104、UI-123、UI-279、UI-280。
- 实现（档位 1，issue #107）：设置页「设备状态与最近日志」，文字逐字同 V1.0.3 `MainWindow.refresh_settings_console`。`items[]` 另给 `occurred_at`（库中原样）、`category`（原名）、`category_tooltip`、`result_text`（结果列：“已读取设备维护诊断”“已读取设备当前通信参数”显示为“设备诊断读取成功”“通信参数读取成功”，其余原样）、`result_tooltip`（完整消息，详情非空且不是 `{}` 时另起一行附详情，UI-280）、`error`（ERROR、WARNING、CRITICAL 标红，UI-279）、`details_text`（日志详情弹窗全文：设备、数据库绝对路径、时间、级别、类别（中文与原名）、消息、详情，纯文本，UI-100、UI-104）；筛选只去掉 INFO 级 `connection` 类“已读取设备当前通信参数”（UI-076），库里没有 diagnostics 表时为空列表。另给 `status`：状态区第一行（V1.0.3 `connection_status_label`）`text`、`level`、`tone`（normal / warning / error / muted，颜色）、`tooltip`（设备名与“设备序列号：0x…”，未存身份为“设备序列号：尚未读取”，UI-081）；取自接管状态缓存中该位置、同一设备库的调度器设备状态（16_ 1.4：不读调度器本身），还没有状态时为“等待本次采集”（`DeviceHub.idle_status`），alpha 未接管时为“设备名 · 未接管：alpha 未连接设备”（V1.0.3 无此状态）。另给 `columns`（时间、类别、结果）、`details_title`、`copy_label`。只读设备库（`mode=ro`），不向设备发任何请求（UI-101），不新增存储。档位 0 没有设备，404 `device_not_found`。

### API-17 事件流

- `GET /api/v0/events`（Server-Sent Events）
- 事件：`heartbeat`（每 15 秒）、`snapshot_imported`、`tier_changed`、`takeover_state`；档位 1 以上增加 `bus_config`、`config_applied`、 `bus_state`、`device_state`、`device_alert`、`acquisition_saved`、`acquisition_halted`、`maintenance_changed`、`task_finished`（来自协调器公共信号，方案附录 A）。
- 前端收到 `acquisition_saved` 后按需刷新（UI-069、UI-071）；断线时自动重连，期间保留现有数据。
- `service_error`（各档位，D-225 问题 1，R-1-5）：服务出现未预期异常；数据同 `GET /tier` 的 `fault`（`id` 本次运行内的序号、`kind`、`occurred_at`、`where`、`error` 异常类型名、`message` 页面全文、`stopping`），回溯只写 `service.log`。`kind: "request"`：HTTP 线程上的某个请求失败（500 `internal`，可重试），页面保留最后的数据，接管与档位不变。`kind: "takeover"`：服务 Qt 主线程上的代码（接管或维护的槽函数、回调，或请求经网关带到主线程的调用）抛出未预期异常，状态可能只更新了一半；服务记日志、发本事件，再在主线程排队执行与 `POST /shutdown`、外壳崩溃察觉相同的停止接管（`coordinator.stop()`：进行中的事务做完并发出恢复命令，关闭串口，释放 V1.0.3 的锁），锁释放后、接管变为 released 之前写档位 0（随后 `tier_changed`、`takeover_state`），服务本身继续运行。不清除锁停；维护态与待核对写入按停止时的样子留在设备库。服务正在关闭时由关闭流程停止接管。停止本身再出错时 `message` 改为“请退出 alpha 后重新打开”，`stopping` 为 false。页面收到后重读 `GET /tier`，以横幅显示 `message`，点“知道了”只关闭横幅。

### API-19 停止本机服务（外壳专用）

- `POST /api/v0/shutdown`，带启动令牌、**不带 Origin 头**（浏览器发 POST 必带 Origin，所以网页不能停服务）；无请求体。
- 响应：202 `{"stopping": true}`；服务处理完进行中的请求后正常退出（退出码 0）并删除 `service.json`。带 Origin 为 403 `forbidden_origin`；无令牌 401；服务未启用停止接口（只用于生成 OpenAPI 的应用对象）为 404。
- 来由：PR #50 复审 major 1——打包成无控制台 exe 后 Windows 上 `sys.stdin` 为 None，外壳关闭子进程标准输入的停止方式传不到服务。外壳的停止顺序：本接口 → 关闭标准输入 → CTRL_BREAK/SIGTERM → 强制结束；外壳崩溃时服务按 `--parent-pid` 察觉，按同一关闭顺序自行优雅停止，60 秒兜底（D-223；不再使用 kill-on-close Job Object）。档位 1/2 接管中收到本请求时，服务在主线程按 16_ 1.5 的关闭顺序先停止接管（`coordinator.stop()`，含协调器自己的冻结/恢复收尾，最长约一个采集事务）、释放 V1.0.3 的锁，再退出（`par_app/service_main.py`；`tests/acquisition/test_service_process.py` 的 request 用例）。

---

## 3. 第二批：只写本地文件或 alpha 自身数据（档位 0 可用）

只列名称和要点，接口 PR 时再细化：

| 编号 | 接口 | 写什么 | 规格 / services |
|---|---|---|---|
| API-20 | `POST /api/v0/snapshots` 导入历史库快照（SQLite 在线备份）；**已废弃**（#82：导入的快照不在任何页面显示，#83 移除） | alpha 自己的 `data/imported/` | 方案 2.4 A；导入后校验源文件未被修改；名称（默认源库文件名）已被另一位置的当前快照使用，或与之导出到同一个设备目录（`safe_database_filename` 转换后不分大小写相同）时 400 `invalid_argument`，同 V1.0.3 设备名称不能重复（D-210 问题 5） |
| API-21 | `GET /api/v0/snapshots` 列出已导入快照；**已废弃**（同 API-20） | 无 | — |
| API-22 | `GET /api/v0/devices/{key}/export/count?range=&start=&end=&formats=` 导出条数预览 | 无（只读） | EXP-011、EXP-049～051、EXP-053、EXP-068～071；`ParDatabase.acquisition_export_count` 同一 SQL。`range` 为 `1h`/`2h`/`4h`/`8h`/`24h`（按服务时钟此刻重算，#12）或 `custom`（`start`、`end` 为整秒 `YYYY-MM-DDTHH:MM:SS`）；查询 [开始秒, 结束秒.999]（#11）。响应 `range`（`start`、`end`、`*_text`、`editable`）、`count`、`files`（记录 × 格式）、`text`、`can_export`、`confirm`（V1.0.3 确认框全文，记录数取 `acquisitions_for_export` 的行数）、`notice`（“结束时间不能早于开始时间。”“所选时间范围内没有采集记录。”） |
| API-23 | `POST /api/v0/devices/{key}/export` 导出采集记录 | alpha 数据目录 `exports/`（D-210；外壳有目录选择框后改为所选文件夹） | EXP-001～003、EXP-006～008、EXP-012、EXP-013、EXP-052、EXP-054、EXP-057、EXP-058、EXP-072；`ParDatabase.acquisitions_for_export` 同一 SQL，`export.write_acquisition_file`、`acquisition_day_folder`、`acquisition_file_name`、`device_folder`。请求 `start`、`end`（确认时的整秒范围）、`formats`、`snapshot_id`、`records`（确认框中的记录数，可选；采集仍在进行、范围内的记录数与之不同时 409 `snapshot_changed`，须重新确认，EXP-052，#82）；201 返回 `directory`、`device_folder`、`records`、`files`、`text`；无记录 404、结束早于开始 400、设备库已更换 409 `snapshot_changed`、另一次导出进行中 409 `busy`、写文件失败 500 `export_failed`（`detail` 为失败记录、已成功文件数与保存目录，在第一条失败处停止，同 V1.0.3） |
| API-24 | `POST /api/v0/operations/export` 导出计算结果 | alpha 数据目录 `exports/`（D-207；外壳有目录选择框后改为所选文件夹） | EXP-005、EXP-010、EXP-015 至 EXP-040、EXP-060～065；`export.write_operation_file`、`export_operation_files`。请求同 compute 加 `formats`（csv、xlsx 中的一种或两种）；201 返回 `directory`、`files`、`text`（“已保存 N 个文件：…”）；写文件失败 500 `export_failed`，`detail` 为“保存目录 / 已完成 / 错误”（EXP-020）；导出用页面上的计算结果（EXP-022） |

选择导出文件夹由外壳弹出系统对话框完成，接口只接收外壳传入的路径。

### 3.1 实机验收支持：导出诊断包与维护记录（D-226）

负责人 2026-10-19 批准，供 2.0.0-alpha.2 实机验收（L2，只读功能）。各档位可用；都不连接设备、不写设备库、不改配置，设备库一律以只读连接（`mode=ro`）打开，不在 alpha `data/devices` 下的库不打开。边界见 D-226，字段以 `docs/spec/openapi-v0.json` 为准。

| 编号 | 接口 | 写什么 | 要点 |
|---|---|---|---|
| API-27 | `POST /api/v0/support/diagnostics-bundle` 导出诊断包 | alpha 数据目录 `exports/diagnostics/PAR_diagnostics_<北京时间>.zip`（每次新建，先写 `.partial` 再改名；接口不接受路径） | 201 返回 `path`、`directory`、`file_name`、`size`、`files`（包内文件）、`problems`（生成时遇到的问题，如某台设备库读不出；包照样生成）、`text`（页面显示全文）。包内容见 D-226 问题 3 与包内 README.txt；不含 service.json、光谱，服务令牌替换为 `<TOKEN>`。结构化数据（配置、库内设置、状态、计数、manifest）按允许清单导出，未知键只留键名（`<omitted: …>`），保留的值中整个是绝对路径的（Windows 或 POSIX 写法，不论服务运行在哪个系统、是否在用户主目录下），除 alpha 数据目录和程序目录内的以外只留文件名，以分隔符结尾的目录只写 `<PATH>/`（#66）；日志与表格文字只做尽力去除（凭据键之后整行其余内容、Cookie/Authorization 头整行（LF 或 CRLF 换行均可）、本机路径替换为 `<DATA_DIR>`、`<PROGRAM_DIR>`、`<HOME>`，其他 Windows 绝对路径只留文件名），不保证完全去除；包供我方开发人员内部排查，发到公司外部前请先查看。manifest.json 的 `maintenance_log` 写明维护记录汇总的条数上限与扫描截断（`scan_limited`）。规则见 D-226 问题 3。另一次导出进行中 409 `busy`；写文件失败 500 `export_failed`（`detail` 为保存目录与错误） |
| API-28 | `GET /api/v0/support/maintenance-log?device=&limit=&time_sync=` 维护记录 | 无（只读） | `device` 为 p1–p4（不给为 alpha 档位 1 配置中的全部设备；未登记 404 `device_not_found`）；`limit` 1–1000，默认 200（否则 400）；`time_sync` 默认 false。响应 `devices[]`（`key`、`position`、`name`、`database_name`、`state`：ok / missing 库未建立 / outside 不在 alpha 目录、未打开 / unavailable 读取失败，`problem`）、`items[]`（最新在前：`device_key`、`device_name`、`occurred_at`、`occurred_at_text`、`kind`：calibration_write / comm_write / comm_verify / time_sync、`kind_text`、`before_text`、`after_text`、`readback_text`（库中没有为“未记录”）、`result`：success / failure / pending、`result_text`：成功 / 失败 / 待核对、`detail`、`source`（表名与行号））、`limit`、`limit_reached`、`time_sync`、`scan_limited`（某台设备只扫描了最新 10 万行设备日志，更早记录未扫描）、`texts`（标题、说明、列名、空状态文字、`scan_limited_text`）。排序为 `occurred_at` 倒序，同时间按设备、行号倒序。查询只沿 rowid 走：各审计表按 id 倒序取 `limit + 1 + 500` 行候选（校准审计只在最新 10 万行内找写入），再按时间排序，时钟回拨后写入少于 500 行时仍按时间正确；设备日志只扫描最新 10 万行。校准审计或设备日志有更早的行未扫描时 `scan_limited` 为 true；写入的开头在扫描范围之外时记为“待核对（记录不完整）”。来源与判定规则见 D-226 问题 2。不给 `device` 时某台库读不出不让整个请求失败，而在 `devices[]` 中写明（不冒充“没有记录”）；给了 `device` 时，该库读不出、尚未建立（missing）或不在 alpha 目录（outside）都是 503 `database_unavailable`（`detail` 为原因）；配置文件读不出 409 `config_unavailable`；没有配置为 200 + 空 `devices` |

---

## 4. 后期接口：写库、写配置、设备通信（**阶段二后期，需负责人批准**）

以下接口在本版本只列名称，不定义字段。每一项在实现前都要有负责人的书面批准（R-4-2 格式：同意 + 范围 + 验证要求），按 L3 处理。档位不够时一律返回 403 `feature_disabled`。

| 名称 | 涉及 | 需要档位 | 红线 |
|---|---|---|---|
| `PUT /devices/{key}/dli-location` 保存经纬度 | 写库（`app_settings`），会重算 DLI 周期 | 1 | 第 3 条（配置格式）相关，按 L2/L3 定级时核对 |
| `PUT /acquisition-config` 保存并应用总线与设备登记（原名 `PUT /config`） | 写 alpha 自己的配置文件与设备库；V1.0.3 `DeviceHub.apply` → 协调器 `apply_config` | 1 | 第 1、3 条；**已实现**（第 4.1 节，负责人 2026-10-18 批准） |
| `POST /acquisition/start`、`POST /acquisition/stop` 接管 / 释放采集 | 启动协调器；含冻结、恢复、自动对时写入；需取得 V1.0.3 单实例锁 | 1 | 第 1 条；**已实现**（第 4.1 节，负责人 2026-10-18 批准） |
| `POST /maintenance/enter`、`POST /maintenance/leave` | 协调器 `maintenance_enter` / `maintenance_leave` | 2 | 第 1、2 条；**已实现**（第 4.2 节） |
| `POST /maintenance/diagnostics/read` 读诊断（原名 `/devices/{key}/diagnostics/read`） | 任务 `diagnostics_read` | 2 | 第 1 条；**已实现** |
| ~~`POST /devices/{key}/identity/read` 读身份~~ | 任务 `read_identity` | — | **不开放**（D-216 问题 3：V1.0.3 界面从不排队该任务；身份只在维护读取、写入、核对和诊断中读取） |
| `POST /maintenance/calibration/read`、`…/write` 读写校准 |（设备协议细节，公开版略）| 2 | 第 1、2 条；**已实现** |
| `POST /acquisition/devices/{key}/comm/read` 读通信参数（设置页当前值） | 任务 `comm_read` | 2 | 第 1 条；**已实现** |
| `POST /maintenance/comm/write` 写通信参数 | 只对应 `maintenance_write`（普通 `comm_write` 协调器一律拒绝，不开放，D-216 问题 3） | 2 | 第 2 条；**已实现** |
| `POST /maintenance/comm/verify` 维护核对 | 任务 `maintenance_verify`；裁决 44 的逐台核对**不在本档位落地**（要改协调器，超出批准范围，D-216 问题 2） | 2 | 第 2 条；**已实现** |

任务名均为协调器和维护弹窗现有的任务类型；接口只做转发，不新增写入路径，不改变读写顺序。

### 4.1 档位 1：档位开关与接管采集（已实现，设计见 内部文档）

批准：负责人 2026-10-18「4的部分批准」（alpha 1 级接管采集；范围：红线代码原样复用、默认档位 0、1 级显式开启并二次确认、先取得 V1.0.3 单实例锁；实机验收前只供内部试用）。边界按推荐：D-212（设计）、D-213（实现）。字段以 `docs/spec/openapi-v0.json` 为准。

| 接口 | 档位 | 要点 |
|---|---|---|
| `GET /tier` | 0 | `tier`、`takeover`（released/starting/running/stopping，只在内存）、`lock_held`、`text`/`level`（状态栏常显一块，16_ 4.4）、`settings_path`、`settings_problem`（设置文件不可读时按默认档位：产品为 1，#119；测试与 `python -m par_app.api` 为 0）、`stop_text`/`down_text`（“停止采集”“切回档位 0”确认框全文，页面不自写；有锁停时停止确认另附锁停全文与“先重新上电”，D-215）、`fault`（本次运行中最近一次未预期异常，没有为 null；字段同 API-17 `service_error`，D-225 问题 1） |
| `POST /tier/confirmations` | 0 | 请求 `{"tier": 1}`；201 返回 `confirmation_id`（60 秒内有效、一次性）、`expires_at`、两层确认全文 `notice`、`confirmation`；其他档位 400 |
| `PUT /tier` | 0 | 0→1 必须带有效 `confirmation_id`，否则 409 `confirmation_required`；写 alpha 的 `config/app_config_v2.json`（`device_write_tier`）。1→0 不需确认；正在接管时先停止（202），释放锁后、接管状态变为 released 之前写 0，`tier_changed` 事件通知；档位已读作 0（设置文件被改或不可读）而接管仍在运行时，`PUT /tier {0}` 同样先停止（202，D-215） |
| `GET /acquisition-config` | 1 | alpha 的 `config/app_config.json`（V1.0.3 格式）：`path`、`exists`、`configured`、`bus`（原值）、`poll_cycle_seconds`（钳位后）、`devices[]`（含解析后的 `database_path`、`database_exists`、`inside_alpha`）、`devices_dir`、`rows`（设置页 4 行登记草稿，V1.0.3 `ensure_device_count`）、`form`（V1.0.3 设置页的标签、选项、范围、提示与按钮文字，D-214；另有“以空配置重新配置”“未生效”的文字，D-220、D-221）、`blank_bus`/`blank_rows`（空配置的表单）、`problem`（`message`、`detail`：文件无法读取、库不在 alpha 目录，或最近一次开始采集时库未通过 V1.0.3 启动检查；可用时为 null，D-220）；文件无法读取时仍 200（空表单加 `problem`）；不打开任何库 |
| `PUT /acquisition-config` | 1 + 接管中 | 请求 `bus`、`devices[]`（`name`、`slave_id`、`enabled`、`auto_stop_on_failure`、`database_path`：留空＝新设备由程序在 alpha `data/devices/` 建库，非空只能是 alpha 配置中已有设备的库，否则 400；`reuse_existing`：新设备沿用 alpha `data/devices/` 中按 V1.0.3 默认规则同名的库，不存在时 400，D-215）；服务先按 V1.0.3 `devices_from_form` 取行（登记过、启用、有名称或有库的行；空名称补“光谱仪N”）并 `normalised()`（D-214），再在主线程调用 V1.0.3 `DeviceHub.apply`，其 `ValueError` 原文 → 400；未接管 409 `not_running`；正在开始或停止 409 `busy`（16_ 7.5）。例外（D-220）：未接管且 `problem` 非空时，请求带 `"reconfigure": true` 即以空配置重新配置：服务在主线程建一个不启动的 V1.0.3 `DeviceHub`（空配置、`preserve_before_save`），由 `DeviceHub.apply` 判定并保存，原配置先备份为 `app_config.before_recovery_<时间>.json`；不取锁、不开串口。行中的库可以是运行中配置或配置文件已持有的库（后台应用失败后重试，D-221） |
| `POST /acquisition-config/import-preview` | 1 | 从 V1.0.3 配置导入副本（16_ 3.3，D-214）：请求 `source_path`（V1.0.3 程序目录或其中的 `config/app_config.json`）；只读源文件（读前读后比对，变化 409 `busy`），库路径清空；V1.0.3 库中有未完成通信维护会话的设备 `importable=false`（D-131）；返回 `bus`、`devices[]`、`rows`（放入表单的 4 行）、`note`；不写任何文件；找不到或无法解析 400 `invalid_argument` |
| `GET /acquisition-config/serial-ports` | 1 | 设置页“计算机串口”下拉列表与“刷新串口”（#74，V1.0.3 `MainWindow.refresh_serial_ports`）：只调用 `serial.tools.list_ports.comports()` 列出本机串口，不打开任何串口（MAINT-051），不替用户选择或切换（POLL-032）；不取锁、不经 Qt 主线程，任何接管状态都可读。返回 `ports[]`（`value` 串口名称，选中后填入并原样保存；`label` V1.0.3 的条目文字“COM3 — USB-SERIAL CH340”，无描述时为“未知设备”），顺序为操作系统给出的顺序（V1.0.3 设置页不排序），`hint`（V1.0.3 刷新后的悬停提示：“检测到 N 个串口，请手动选择；不会自动搜索或切换端口。”或“未检测到串口；请确认 USB 线、驱动和设备电源。”）；档位与入口同 `GET /acquisition-config`（档位 0 → 403，不含采集的开发入口 → 409 `config_unavailable`）；枚举失败 → 500 `internal`（`retryable: true`，“串口枚举失败：<原因>”，同 V1.0.3 `SerialPortComboBox.refresh_ports`），页面保留上次的列表并可重试（R-1-5）。串口框仍可手动填写 |
| `POST /acquisition/start` | 1 | 202。库路径不在 alpha `data/devices/` 下 → 409 `config_unavailable`（不取锁、不开串口）；取不到 V1.0.3 锁 → 409 `instance_locked`；`load_for_startup` 失败 → 409 `config_unavailable`（V1.0.3 原文在 `detail`；`message` 末尾指出“恢复原文件后重试，或选择‘以空配置重新配置…’”，并记为 `GET /acquisition-config` 的 `problem`，下一次开始成功或重新配置成功后清除，D-220）；正在开始/停止/关闭 → 409 `busy`；档位检查与进入 starting 在同一把锁内，主线程取锁前再查一次档位与关闭状态（档位已为 0 → 403，不取锁、不开串口；D-215） |
| `POST /acquisition/stop` | 1 | 202；主线程 `coordinator.stop()`（最长约一个采集事务 40 秒）→ 排队信号送达 → 释放锁，`takeover_state` 事件通知；未接管 409 `not_running`；正在停止 409 `busy`。档位读作 0 而接管未释放时仍可停止（D-215） |
| `GET /acquisition/status` | 1 | 状态缓存（HTTP 不碰协调器）：`takeover`、`lock_held`、`error`、`bus`、`halt`（协调器锁停原字典加 `text`：V1.0.3 锁停提示全文，只改“退出并重新启动软件”一句，D-212 问题 8；无清除接口）、`maintenance`、`poll_cycle_seconds`（未知时为 null）、`config_apply_error`（后台应用配置失败“应用配置失败：<原因>”，到下一次应用成功或下一次开始为止，正在运行的仍是原配置，D-221）、`devices[]`（`DeviceRuntimeState.snapshot()` 加 `status_text`、`position`）、`run_status`（顶部常驻状态区，issue #73：`bus` 为 V1.0.3 `MainWindow._on_bus_state` 的“总线：<摘要>”、颜色级别 ok/warn/error/muted 与原文 `detail`，串口开着但所有启用的设备都已失败、没有一台响应时（含因失败停止退出本次采集的），`bus` 为“总线：异常”、级别 error、`detail` 为“所有启用的设备都不响应，将继续按周期重试”、`devices_silent: true`（#131，负责人 2026-10-28，与 V1.0.3 不同；锁停、维护、串口打不开时照旧），「实时概览 → 采集控制」的总线一行显示同样结果；`acquisition` 为 `_refresh_communication_events` 的采集状态与级别，`failures[]` 为启用设备的红字失败行“<时间>  <设备名>（地址 <n>）  <失败消息>”；只读，由 `par_app/application/run_status.py` 从状态缓存推出，不改采集、重试与失败停止）；记录号（#136，第 4.3 节）：`bus.notice`、`halt.notice`、`devices[].notice`、`error_notice`、`run_status.bus.notice`、`run_status.acquisition.notice`（仅锁停时）、`run_status.failure_notices[]`（与 `failures` 逐行对应），各为 `{event_id, occurred_at}` 或 null；档位读作 0 而接管未释放时仍可读取（D-215） |
| `GET /acquisition/devices/{key}/latest` | 1 | API-09 的实时版，`source` = `live`：alpha 自己的设备库，只读连接（`mode=ro`，不加 `immutable`）；按 alpha 配置中的位置 p1–p4；轮询周期取 alpha 配置；`paused`（维护、锁停或未接管）；没有 `snapshot_text`；`snapshot_id`：这一位置这个库的标识，与 API-06 的 `snapshot_id` 相同，页面“全部指标”按 `display_record.id` 调 API-06 读同一库的这条记录，标识不同即不显示（#106）。库路径（解析后）不在 alpha `data/devices/` 下 → 409 `config_unavailable`，不打开该库；任何读取都不在 alpha 数据目录外新建或改动文件（PR #54 复审 B1） |
| `GET /events` | 0 | API-17，见上；新增 `tier_changed`、`takeover_state`、`bus_config`、`config_applied`、`service_error`（D-225 问题 1） |

档位 0 时除 `/tier`、`/tier/confirmations`、`PUT /tier`、`/events` 外，上表接口一律 403 `feature_disabled`；唯一例外是接管未释放时的 `POST /acquisition/stop` 与 `GET /acquisition/status`（D-215）；此时页面照常显示接管状态、锁停提示和“停止采集”，不提供开始采集与保存配置，也不读实时记录（PR #54 复审 M2）。数据目录是 V1.0.3 程序目录（含 `_internal`、`PAR_Spectrometer.exe`，或 `main.py` 与 `par_app/`）时服务拒绝启动，退出码 2，不在该目录建任何文件（D-215）。档位 1 或 2 已开启时，`par_app.service_main` 启动后自动执行一次与 `POST /acquisition/start` 相同的开始（#92，D-212 问题 2 改选）；没有设置文件（新安装）或设置文件无法读取时，产品服务按档位 1，即 `--first-run-tier` 默认 1，`python -m par_app.api` 与测试按 0（#119）；接管中出现未预期异常时只停止接管，档位不变（#119，原为写档位 0）；被拒（如 `instance_locked`）时接管保持 `released`，原因见 `GET /acquisition/status` 的 `error`。服务入口为 `python -m par_app.service_main`（主线程 Qt 事件循环、uvicorn 在工作线程）；`python -m par_app.api` 仍可启动，但不含采集，档位 1 接口答 409 `config_unavailable`。

### 4.2 档位 2：设备维护写入（已实现，设计见 内部文档）

批准：负责人 2026-10-18「4的部分批准」（alpha 设备维护页（写设备）、2 级校准与通信参数写入；范围：红线代码原样复用、新代码只做服务层封装与网页、2 级在 1 级之上显式开启并二次确认、写入沿用 V1.0.3 的核对流程与拒绝条件；实机验收前只供内部试用）。边界按推荐：D-216（设计）、D-217（实现）、D-218（PR #55 复审；问题 1 已裁决 2026-10-19：alpha 与 V1.0.3 一致，缺陷见 #57，不阻塞 #55）。有待核对写入时 `communication.isolation_enabled` 为 false，`communication.isolated` 是本次维护页会话保留的勾选；`POST /maintenance/comm/verify` 按它判断、不看请求体的 `isolated`，重新打开维护页后 409 `precondition_failed`（D-218 问题 1）。字段以 `docs/spec/openapi-v0.json` 为准。

- 档位：`POST /tier/confirmations {"tier": 2}` 只能在档位 1 时取（否则 409 `confirmation_required`）；`PUT /tier {2}` 必须带有效确认号；2→1 有维护任务在途时 409 `busy`（在服务主线程判断），否则立即降档、丢弃未写入校准修改、作废档位 2 时发出的全部写入确认号、停止设置页当前值的自动重读、维护态不变；降档后主线程不再排队任何维护任务（HTTP 侧已通过档位检查、尚未执行的请求答 403 `feature_disabled`，D-218）；2→0 同 1→0。`GET /tier` 增加 `down_to_1_text`、`maintenance`；`level` 增加 `maintenance`。
- 公共前置（每个维护接口按序）：档位 2（否则 403 `feature_disabled`）→ 正在接管（409 `not_running` / `busy`）→ 维护页会话（409 `no_session`）→ 无维护任务在途（409 `busy`）→ 锁停（409 `halted`，原文为协调器锁停文字）→ V1.0.3 界面门槛 G1–G10（409 `precondition_failed`，原文为 V1.0.3 提示；V1.0.3 只置灰按钮没有文字的几处由 alpha 写一句，见 D-217 问题 4）。协调器和会话自己的拒绝经 `task_finished` 原文显示。
- 写入两步：`…/confirmations`（同一请求体）返回 `confirmation_id`、`expires_at`、`title`、`text`（V1.0.3 确认框全文），再带确认号写入；确认号绑定操作、维护目标及其设备身份（从站地址、启用状态、串口、波特率、校验位、设备库、接管/配置纪元）、维护页会话、请求体 SHA-256（校准另绑定草稿版本），60 秒、单次，不符一律 409 `confirmation_required`；接管开始或结束、保存配置、打开或关闭维护页、进入或退出维护时已发出的确认号全部作废，保存配置还作废校准草稿；校准写入排队前再核对目标身份与读取时一致，不一致 409 `precondition_failed`（D-219）。需要确认：`enter`、`comm/write`、`calibration/write`、`leave`、有未写入修改时的 `calibration/read` 与关闭页面（`page/close`）。
- 页面：`GET /maintenance/state`（视图模型，全部文字、可用状态与悬停原因由服务给出）、`POST /maintenance/page {tab}`（同一时间一个会话；诊断、校准页签按 V1.0.3 自动读取）、`DELETE /maintenance/page[?confirmation_id=]`、`POST /maintenance/tab`、`PUT /maintenance/target`、`POST /maintenance/diagnostics/export`（写 alpha `exports/`）、`PATCH /maintenance/calibration/draft`（`{field, value}` 或 `{node, x, y}`；服务按 V1.0.3 编辑框位数取整）、`POST /maintenance/calibration/discard`、`POST /maintenance/comm/read`、`POST /maintenance/notice/dismiss`。
- 设置页当前值：`POST /acquisition/devices/{位置}/comm/read`；离开设置页时 `DELETE /acquisition/devices/comm/read`（204，停止设备上线、总线连上时的自动重读；V1.0.3 只在设置页为当前页时重读；档位 0/1 且未接管时 403，D-218）。读取失败或回包无效时保留上次有效值，`stale` 为 true 并附 `stale_text`（R-1-5，D-219）。
- 维护任务在途时 `PUT /acquisition-config` 409 `busy`（V1.0.3 的维护窗口为模态，期间不能保存设置；D-218）。
- 事件：`maintenance_state`（视图版本号，页面重读状态；只在维护页或设置页当前值打开时发）。
- 没有任何接口清除锁存（R22）；没有 `read_identity`、普通 `comm_write`、`apply_config` 的排队路径（R21）。

---

## 5. 合同测试要求

每个接口的合同测试至少覆盖：

1. 正常返回：字段齐全、类型正确，`text` 与 services 层对同一记录的输出逐字相同；
2. 空数据：200 + 空数组 / `null`；
3. 库不可用：503 `database_unavailable`，`retryable: true`，且不返回空数组；
4. 参数错误：400；
5. 档位不足（适用时）：403 `feature_disabled`；
6. 金样记录：用 `test/golden-v1` 的金样驱动 API-06、API-09、API-10，结果与金样一致；
7. 使用合成测试库，不用现场库（R-4-7）。

接口的 OpenAPI 描述由服务生成后存入仓库，接口变更必须体现为该文件的 diff。

### 4.3 运行事件与提示记录号（#136 第一步）

背景：现场排查 #132 时，界面上的提示在诊断包里找不到对应记录。负责人 2026-10-28 确定保证范围：导出成功的诊断包里，一定能查到导出当时界面上每一条提示；日志出问题时，界面和诊断包会写明；软件崩溃后能否找回不在保证范围内。设计与 评审见 #136。L2，不碰红线：不改协议、超时、预算与读写顺序，不改数据库结构和历史格式，协调器与协议代码不变。

- 记录的地方：状态缓存（`par_app/application/acquisition.py` `StatusCache`）。页面显示的每条运行消息都经过它：总线消息、每台设备的消息（红字失败行由它生成）、锁停、开始失败的原因。消息变化时记一条运行事件，同一消息再次到达时沿用原记录号；空消息不记。
- 记录号：`<运行会话>-<序号>`。运行会话为每次启动服务随机的 16 位十六进制（64 位随机数），序号从 1 起；重启不重号，不用日期和设备序列号；先后顺序看序号，时间（注入的时钟，北京时间）只用于显示。
- 文件：alpha 数据目录 `logs/events.jsonl`，每行一条 JSON：`schema`（1）、`event_id`、`session`、`sequence`、`occurred_at`、`kind`（bus / device / halt / takeover）、`level`、`message`（页面显示的原文）、`device_key`、`device_name`、`slave_id`、`details`（设备事件：online、failures、excluded、last_error、last_failure_at、latest_record_id、enabled；锁停：reason、occurred_at、cycle、resume_unconfirmed、initialized、need_power_cycle；单段文字超过 2000 字截断并标“（已截断）”）。超过 5 MB 换到 `events.1.jsonl`，保留两个旧文件；换文件时，页面仍在显示的提示（总线、各设备、锁停、开始失败）所对应的记录复制到新文件开头（记录号不变，带 `carried_over: true`），所以页面上显示的记录号总能在现有文件里找到。
- 写盘：由后台线程写，记录时只放进有上限的队列（1000 条），不等写盘、不因写盘失败报错。队列满时该条不进文件并计数；写盘失败计数并记下第一次和最近一次的原因。消息仍带着记录号，留在状态缓存里。
- 页面：顶栏总线与采集状态的悬停提示、红字失败行的悬停提示、设备按钮的悬停提示加一行“记录号 <编号>，出现于 <时间>”；锁停横幅在全文下方显示这一行。只说明出现时间，不表示消息仍然有效，不自动标“已过时”（#133 的现有表现不变）。
- 关闭服务时等待写完，最多 2 秒。
- 操作与生效（#136 第三部分）：页面的请求记为 `kind: action`，`details.phase` 为 requested（已请求）、accepted（已受理）、refused（未执行，带页面显示的原因与错误码）或 failed（出错）。请求包括开始采集、服务启动后自动开始、停止采集、保存并应用配置、以空配置重新配置、切换模式；保存时记下每台设备的名称、地址、是否启用和是否勾选失败停止。是否生效以状态缓存为准：接管状态变化记为 `kind: takeover`（正在开始采集 / 采集已开始 / 正在停止采集 / 采集已停止，串口已释放），配置生效记为 `kind: config`（“采集配置已生效”，带每台设备的名称、地址和是否启用），维护暂停与恢复记为 `kind: maintenance`。被拒绝的请求不会记成已受理。
- 日志状态：`GET /acquisition/status` 的 `event_log` 给出 `session`、`written`、`last_written_sequence`、`dropped`、`failed`、`first_error`、`last_error`。`dropped` 或 `failed` 不为 0 时，采集控制区显示“运行日志有记录未写入文件：…。当前提示的记录号仍在，导出诊断包时会补上。”
- 诊断包（#136 第四部分，API-27）：导出时先取状态缓存快照，再记一条 `kind: export` 的截点事件（快照里的提示都在截点之前编号），然后等待写盘最多 2 秒。`logs/` 下不再原样收录 `events*.jsonl`，改为写入 `events/`：
  - `events.jsonl`：按旧到新读取 `events.2.jsonl`、`events.1.jsonl`、`events.jsonl`，每个文件最多取最后 5 MB；本次运行截点之后的记录不收录。每条记录只保留已知字段，详情按诊断包规则去除凭据和本机路径。
  - `events.csv`：同一批记录的表格，UTF-8 带 BOM；以 `=`、`+`、`-`、`@`、制表符或回车开头的单元格前加 `'`。
  - `integrity.json`：`complete`、`reasons`、`cut`、`flushed`、`health`、`files`（每个文件的大小与是否截断）、`records`、`unreadable_lines`、`shown`（导出时页面上每条提示的位置、记录号及是否在文件中）、`from_memory`。页面提示的记录不在文件中（写盘排满、写盘失败、被截断）时，从快照补写到 `events.jsonl`，`source` 为 `memory`。不完整时 `problems` 中写“运行事件记录不完整：…”，导出结果文字里也会显示。
- 串口收发记录（#136 第二、三步；负责人 2026-10-29 按 R-4-2 书面批准范围一，记录在 #132）：
  - 记录点：协议打开串口时经 `par_app/rtu_frames.py` 的 `PORT_TAP` 套一层（`par_app/application/bus_trace.py`），只把每次写出的帧和每次读到的字节连同客户端单调时钟的时刻复制进内存中的环形缓存（4000 条）。通信线程上只多一次加锁追加，不写盘、不解析，不改字节、顺序和时间；V1.0.3 桌面程序不装这一层；TCP 不记录。
  - 留存：状态缓存记下设备失败（级别不是 ok 的设备消息）或锁停事件时，把缓存最后 800 条以该事件的记录号留存（最多 15 次设备失败、5 次锁停，更早的被挤出并计数）。只在内存，重启或崩溃后不在（与第一步的保证范围一致）。
  - （设备协议细节，公开版略）

---

## 6. 实现状态（随接口 PR 更新）

| 编号 | 状态 | 与本草案的差异 | PR |
|---|---|---|---|
| 1.1 鉴权 | 部分实现 | 会话 Cookie（`POST /session`）仍未实现（页面 PR 改用 URL 片段传令牌，见下一行）；当前每个请求带启动令牌：`Authorization: Bearer <token>` 或 `X-PAR-Token: <token>`，端口与令牌写在数据目录 `service.json`（权限 600）。Host 必须是 `127.0.0.1:<端口>`，有 Origin 时必须同源，否则 403 `forbidden_origin`。服务只绑定 127.0.0.1（S-7），`service.json` 的 `base_url` 取 socket 实际绑定的地址；写 `service.json` 时端口已在监听，外壳读到即可连接。`service.json` 另有 `pid`（服务自己的进程号）和 `launch_id`（外壳经环境变量 `PAR_SERVICE_LAUNCH_ID` 给的启动号，非外壳启动为 null）；外壳按 `launch_id` 认自己的服务，不按进程号（Windows 虚拟环境的 python.exe 是启动器，服务是它的子进程，#66）。WebSocket 一律以 1008 关闭（事件流 API-17 落地时再扩展鉴权） | 分支 `ui-v2/service-skeleton` |
| 1.1 网页 | 已实现（页面 PR） | 服务在 `/` 托管构建好的网页（`--web-dir`、`$PAR_WEB_DIR`、打包目录 `web/` 或仓库 `web/dist`；未构建时只有接口）。静态文件的 GET/HEAD 不需要令牌（`/api/v0` 以外的其他方法也要令牌，以后在前缀外加的路由不会默认放开），但同样校验 Host/Origin，并带只允许本源的 Content-Security-Policy（`connect-src 'self'`、不允许 eval）；`/api/v0` 下除 health 外仍要令牌。外壳打开 `http://127.0.0.1:<端口>/#token=<令牌>`：片段不发给服务器，页面读取后立即从地址中去掉，只存本窗口的 sessionStorage 供刷新使用。开发时 Vite 代理（`web/dev-proxy.ts`）读 service.json 代加令牌，拒绝跨站请求（Origin 不符或 `Sec-Fetch-Site` 不是 same-origin/none）。外壳停止服务先发 `POST /api/v0/shutdown`（API-19），再关闭服务的 stdin（`--stop-on-stdin-eof`，见方案附录 C） | 分支 `ui-v2/web-history` |
| 1.3 错误 | 已实现 | 另有 404 `not_found`（路由不存在）、405；参数错误一律 400，不用 FastAPI 默认的 422；记录内容无法解析（如指标 JSON 损坏、字段是 BLOB）为 500 `internal`、`retryable: false`，其他记录照常可看；记录 ID 和 `offset` 超出 SQLite 整数范围（> 2^63−1）为 400 `invalid_argument`；查询时间必须恰为 `YYYY-MM-DDTHH:MM:SS.mmm`（3 位毫秒，与库内按文本比较），否则 400 | 同上 |
| API-01 | 已实现 | `build_commit` 取环境变量 `PAR_BUILD_COMMIT`，未设置为 null；`tier` 取 alpha 设置文件 `config/app_config_v2.json`（缺失或不可读为 0；分支 `ui-v2/level1-acquisition`） | 同上 |
| API-03 | 已实现（档位 0） | 设备名称取导入时给的名称（默认源库文件名），不读 V1.0.x 配置；另给 `snapshot_id`、`imported_at`；`address_text` 恒为 null | 同上 |
| API-05 | 已实现 | 增加 `limit`（1–500，默认 500）、`offset`（默认 0）、`next_offset`；不返回总数（UI-046）；`offset` 为**实验性**：按 D-201 裁决（A，负责人 2026-10-18）历史回放页只用 `offset=0`（＝V1.0.x，UI-046 不分页）。`limit_reached` = 范围内本页之后还有记录。`exposure_style` 按 D-154 | 同上 |
| API-06 | 已实现 | `groups[].items[]` 只有 `text`（另给 `label`、`unit`），还没有原始数值 `value`；`header` 含 `title`、`time_text`、`status_text`、`status_level`、`exposure_text`；`record` 是 acquisitions 表该行原样字段（SQLite 动态类型，除 `id` 外各字段按存储类型原样给出：整数、小数或文本）；quality_json 不是 JSON 对象时“采集校验”显示“未记录”（D-202 裁决 A，负责人 2026-10-18）；详情直接带光谱（`spectrum_state`：ok / none / invalid） | 同上 |
| API-07 | 已实现 | 除原始值 `points`（按存储原样，整数仍是整数）外另给 `values`（原始值 / 10^光谱系数，与 V1.0.x 历史光谱图一致）；光谱 JSON 损坏时也是 404 `record_not_found`，`detail` 为“光谱数据无法解析” | 同上 |
| API-10 | 已实现（读设备库，2.0 节） | 增加可选参数 `date`（过去的周期，D-204 问题 2）；允许间隔的轮询周期取快照记录 `quality_json.poll_cycle_seconds`，缺失或不可用时 60 秒，另给 `poll_cycle_source`、`poll_cycle_record_at`（D-204 问题 1 = D，D-206，分支 `ui-v2/dli-poll-cycle`）；`paused` 按是否在采集（#82），另给 `snapshot_text`（数据来源）；另给 `header`（图头全部文本）、`y_max`、`ticks`、`interruptions`、`series.offsets_seconds`；`location`/`enabled` 带 `stored`。UI-185（零点标签与端点重叠时错行）未在接口中处理，由页面按渲染结果处理（alpha 未实现） | 分支 `ui-v2/web-dli` |
| API-19 | 已实现（档位 0–2） | 草案第 2 节原无此接口，PR #50 复审 major 1 新增；只供外壳，带 Origin 的请求 403；接管中先停止接管再退出（16_ 1.5，分支 `ui-v2/packaging-levels`） | 分支 `ui-v2/packaging`（PR #50） |
| API-20 | 已实现 | 请求 `source_path`、`name`（可选）、`position`（1–4，默认 1）。按源库旁的文件分两种读法，源库旁都不新建任何文件：① 库静止（无 -wal/-journal）以 `mode=ro&immutable=1` 打开；② 其余情况（有 -wal 或 -journal，不论有无 -shm：V1.0.3 正在使用，或崩溃、强制结束、断电后的残留）先把库和日志文件按字节复制到 alpha 数据目录 `data/staging/`，再从这份副本备份（未检查点的记录随之复制，热 -journal 在副本上回滚），只读目录也能导入；源库本身从不经 SQLite 打开——状态只判定一次，若 V1.0.3 恰在判定后退出（删掉 -wal/-shm），连 `mode=ro` 连接都会在源库旁重建这两个文件（复审 B-1）。两种读法导入前后都比对所读每个文件的大小、修改时间和 SHA-256，期间被改动则丢弃副本并返回 409 `busy`（V1.0.3 正在写库时导入可能需要重试）。Windows 网络共享（UNC）和映射盘路径以空 authority 的 `file:////server/share/…` URI 打开（未在 Windows 上实测）。副本改为 journal_mode=DELETE；副本或数据目录写入失败为 503，消息里是实际失败的那个文件（裁决 47）；在线备份中途失败无法区分是读源库还是写副本，503 不附路径（复审 M-3） | 同上 |
| API-21 | 已实现 | 新导入在前；描述文件不可读或损坏时返回 503 `database_unavailable` 并指明该文件，不伪装成空列表或更短的列表（R-1-5；复审 M-1），文件恢复可读后接口随之恢复；设备列表和历史查询读到坏描述文件时同样 503，不显示“未配置”、不返回 404 | 同上 |
| API-11～14、API-24、API-25 | 已实现（读设备库，2.0 节） | 来源为登记的设备（#82，原为已导入的快照）；另加 `POST /operations/inputs`（选中后的两图与时间差）与 `GET /operations/page`（API-25，页面文本与应用说明）；请求可带 `snapshot_id`，设备库已更换时 409 `snapshot_changed`；导出写 alpha 数据目录 `exports/`，接口不接受路径（D-207），写失败 500 `export_failed`；导出“来源数据库”写设备库路径，与 V1.0.3 对同一库的导出逐字段相同（D-208） | 分支 `ui-v2/web-calc` |
| API-15、API-22、API-23、API-26 | 已实现（读设备库，2.0 节） | 档位 0 不读配置、没有设备（#82，原为快照不含配置，D-209）；API-15 另给状态区文字与序列号、记录中的轮询周期；导出写 alpha 数据目录 `exports/`，按 V1.0.3 的 设备/格式/日期 结构，接口不接受路径，确认后按确认时的范围与设备库导出（D-210）；导出文件与 V1.0.3 对同一库逐字节（CSV）、逐单元格（Excel）相同 | 分支 `ui-v2/web-export` |
| API-09 | 已实现（读设备库，2.0 节；页面在档位 1 用实时概览接口） | 另给 `snapshot_text`（数据来源说明）、`texts`（页面固定文字）、`display_record`（另含 `age_text`、`elapsed_text`、`review_text`、`details_title`）、`record`（显示记录原样字段）、`status`（V1.0.3 状态行全文与颜色级别 ok/warn/error/none）、`stale_after_seconds`、`poll_cycle_seconds` / `poll_cycle_source` / `poll_cycle_text`（先取显示记录自己 `quality_json` 中的轮询周期，不可用时回退 D-206 的取值规则，再回退默认 60 秒，D-211 问题 2）、`core_metrics`、`table`（V1.0.3 中隐藏的 24 项表，4 组 × 6）、`chart`（`title`、`spectrum_state`、`spectrum` 含 `values`、`y_max`、`x_ticks`、`overlay` 两列）、`details_enabled`、`metrics_error`；`kpis[]` 另含 `key`、`title`；光谱直接在响应中，不另调 API-07；非有限值显示“—”（D-179）；坏值、坏光谱、默认页等差异见 D-211；没有采集、总线状态 | 分支 `ui-v2/web-overview` |
| API-08 | 已实现 | 每条曲线另给 `key`、`line`（dashed / dotted / dashdot）、`width`（V1.0.x 线宽），名称字段为 `label`（图例全文）；另给右轴 `axis_label`、`axis_max`（叶绿素 A/B、McCree 峰值最大者 × 1.5）与按波长着色 `fill_start`、`fill_colors`（每 nm 一个 [R, G, B]，0–1）、`fill_opacity`（UI-317）；数值由 `par_app/services/spectrum_display.py` 调用 V1.0.x 的同一组函数得出，与真实 `SpectrumCanvas` 逐值对照（tests/api/test_reference_curves_parity.py）；页面在启动时读一次，失败时换页再读，读到前光谱图照旧为单色 | 分支 `feat/spectrum-color-fill`（#72） |
| API-17 | 已实现 | `GET /api/v0/events`，`text/event-stream`；令牌放请求头（页面用 `fetch` 读流，不用 `EventSource`），同样校验 Host/Origin；每个事件带递增 `id`，不支持 `Last-Event-ID` 补发；每个订阅者最多积压 256 条，超出即关闭该流；15 秒无事件发 `heartbeat`；连接后先发注释行 `: connected`；服务关闭时主动结束所有流；`service_error` 与 `GET /tier` 的 `fault`（未预期异常分层处理，D-225 问题 1） | 分支 `ui-v2/level1-acquisition`；`service_error` 为 PR #61 |
| 4.1 档位与接管 | 已实现（后端与页面） | 见第 4.1 节；`PUT /config` 改名为 `PUT /acquisition-config`；从 V1.0.3 配置导入副本（16_ 3.3）随页面实现（D-214 问题 6）；档位 0 时设置页（API-26）不读配置、没有设备（#82），档位 1 时左侧改为 alpha 配置的编辑 | 分支 `ui-v2/level1-acquisition` |
| API-16 | 已实现（档位 1，读设备库，2.0 节） | 另给 `status`（状态区第一行，取自接管状态缓存；未接管时说明未接管）、`columns`、`details_title`、`copy_label`，`items[]` 另给 `occurred_at`、`category`、`category_tooltip`、`result_text`、`result_tooltip`、`error`、`details_text`（见 API-16 实现说明）；页面每 3 秒与 API-15 一起重读（同 V1.0.3 `refresh_settings_console`） | issue #107 |
| API-27、API-28 | 已实现（档位 0–2） | 草案原无，D-226 新增（第 3.1 节）：诊断包写 alpha `exports/diagnostics`；维护记录只读 alpha 设备库的现有审计与日志表，不新增存储 | 分支 `ui-v2/diagnostics` |
| 4.3 运行事件 | 第一步已实现 | 记录号与 `logs/events.jsonl`（分支 `feat/136-event-notices`）；操作与生效事件、日志状态、诊断包 `events/`（分支 `feat/136-event-bundle`）（#136） | 两个分支 |
| 其余 | 未实现 | — | — |
