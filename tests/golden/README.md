# 金样数据（R-3-2）

指标计算与 DLI 积分的回归金样。原则：**期望值不来自待测实现**。正确值由独立参考实现 `reference.py`（纯 Python、`math.fsum`、不 import `par_app` 的任何模块，包括权重表）或手算闭式解给出；已知缺陷与待裁决口径只以“现状值”单独断言，与正确值分开存放。

## 文件

| 文件 | 作用 |
|---|---|
| `reference.py` | 独立参考实现：光子通量、能量、McCree YPFD、峰值、DLI 记录资格（D-126）、DLI 梯形积分、USNO 日出算法、光谱计算（逐点加减比值、2% 显示阈值与筛选） |
| `mccree1972_upstream.txt` | McCree 1972 相对量子效率表的独立副本（来源见下文），`reference.py` 只读这一份 |
| `spectra.py` | 合成光谱生成器与加载器（生成脚本） |
| `spectra.json` | 合成光谱数据：MCU 原始整数（701 点，350–1050 nm）+ 光谱系数 |
| `status_quo.py` / `status_quo.json` | 待裁决口径的**现状快照**（由待测代码生成，不是金样）：叶绿素（D-102）。旧记录 NULL 资格（D-126）的快照已在裁决后删除，改为正确值金样 |
| `tests/unit/test_golden_metrics.py` | 指标金样测试（marker `unit`） |
| `tests/qt/test_golden_dli.py` | DLI 金样测试（marker `qt`） |
| `tests/api/test_golden_operations_api.py` | 光谱计算金样测试：金样光谱经接口 API-14 计算，与参考实现逐点比较（marker `unit`） |

重新生成：`python -m tests.golden.spectra`（输入光谱）、`python -m tests.golden.status_quo`（现状快照）。`test_stored_spectra_equal_the_generator_output` 保证数据与生成器一致。

## 计算依据与单位

- 光谱辐照度 E(λ) = raw / 10^max(0, 系数)，单位 W·m⁻²·nm⁻¹（与 `software_metrics(raw_points, coefficient)` 输入一致）。
- 光子通量 = Σ E(λ)·λ·Δλ / (h·c·N_A) ×10⁶，单位 µmol·m⁻²·s⁻¹。常数取 SI 2019 精确值（CODATA 2018）：h = 6.62607015e-34 J·s，c = 299792458 m/s，N_A = 6.02214076e23 mol⁻¹，换算系数 8.3593472e-3。
- 积分规则：1 nm 闭区间矩形求和（V1.0.2 与 MCU 共同口径，内部文档）。平坦谱下比 ∫400–700 连续积分高 1/300 = 0.333%（1383.89 vs 1379.29），由 `test_rectangle_rule_is_one_third_percent_above_the_continuous_integral` 记录。
- 波段（闭区间，nm）：PPFD 400–700、PFD 350–780、B 400–499、G 500–599、R 600–699、FR 700–780、扩展 PPFD 400–750、扩展 PFD 350–1050、扩展 FR 700–1050（来源 MCU 固件）；远红 700–750、近红外 751–1050（来源 内部文档 导出字段名）。
- 能量：总辐照度 Σ 350–1050，PAR Σ 400–700，扩展 PAR Σ 400–750，单位 W·m⁻²。
- McCree YPFD：McCree 1972 field 均值 16 个节点（350–725 nm，步长 25 nm）线性插值，725 nm 以外为 0。MCU 外推到 740 nm，不作为参考。
  - **节点表来源（独立于产品）**：`tests/golden/mccree1972_upstream.txt`，内容取自 photobiologyWavebands（P. J. Aphalo）仓库 `data-raw/McCree1972a/tables_IV_III_photon_action_spectra.txt`（https://raw.githubusercontent.com/aphalo/photobiologyWavebands/main/data-raw/McCree1972a/tables_IV_III_photon_action_spectra.txt ，2026-10-17 读取），即 McCree, K. J. (1972) Agricultural Meteorology 9:191–216 的 Table IV（field 均值）和 Table III（chamber 均值）。这是 2026-10 审计核对产品表时用的同一上游文件（内部文档 第 3 条）。
  - `reference.py` 只读这份副本，不读 `par_app/mccree1972_weights.py`；插值在 `reference.py` 重写。产品表某个节点被改错时，产品 YPFD 变而参考值不变，`test_irradiance_and_mccree_match_reference` 变红；`test_product_mccree_table_equals_the_independent_upstream_table` 另外逐节点（field、chamber、波长）精确比较两份表，并在 340–1060 nm 每 1 nm 比较插值权重。
  - 两份表应永远一致。若需要修改，先说明上游或原文依据，并经负责人批准（指标口径）。
- DLI：对 [周期起点, min(截至, 周期终点)) 内的样本做梯形积分 (a+b)/2·Δt，µmol→mol；非有限或负值切段，零值有效；相邻点间隔超过允许间隔不连接、不补零（DLI-008/010/016/018/029/047/048）。
- DLI 记录资格（`reference.dli_record_eligible`，按规格原文与 D-126 裁决独立重写，不读产品 SQL）：采集失败不计入；带 `dli_eligible` 的记录只在其为 1 时计入；`dli_eligible` 为空的旧记录，`quality_json` 是 JSON 对象、`confirmed` 为 JSON false 且不是单采记录（即历史详情显示“复核未完成”）时不计入，其余（无 `quality_json`、无法解析、不是对象、无 `confirmed`、取值不是 false）照旧计入（DLI-007、DLI-021）。
  - **独立性的范围**：参考实现不读产品 SQL，代码上独立；但它与产品出自同一作者对 D-126 的同一理解，**解释上不独立**。金样只覆盖 `confirmed=false`、`confirmed=true`、无 `quality_json`、无法解析四种形态；`confirmed` 为 `0`、`"false"`、`null`，以及单采记录带 `confirmed=false` 的处理，只由单元测试（`tests/unit/test_dli_legacy_review.py`）和阶段一预授权支撑，待负责人在 PR #34 批准时确认（见 `docs/spec/pending-decisions.md` D-126 节“实现边界”），在确认前不算金样真值。
- 日出：USNO《Almanac for Computers》1990 算法（天顶 90°50′，北京时间 UTC+8），与产品的 NOAA 级数是不同方法。

## 金样清单

| 金样 | 输入 | 来源 / 独立依据 | 关键手算值 |
|---|---|---|---|
| `flat` | raw 1000 ×701，系数 3 → 1 W·m⁻²·nm⁻¹ | 闭式：PPFD = 301·550·k | PPFD 1383.890；总辐照度 701；PAR 301 W·m⁻² |
| `mono_550` | 550 nm raw 10000，系数 2 → 100 W·m⁻²·nm⁻¹ | 闭式：100·550·k；McCree w(550)=0.82 | PPFD 459.764；YPFD 377.007 |
| `blackbody_2856K` | Planck 2856 K（CIE A 光源），峰值缩放到 60000，系数 4 | reference.py | — |
| `blackbody_5778K` | Planck 5778 K（日光替代），峰值缩放到 60000，系数 4 | reference.py | — |
| `led_450_660_730` | 三个高斯峰 450/660/730 nm（40000/60000/20000，FWHM 20/20/25），系数 3 | reference.py | — |
| DLI 恒定 | 1000 µmol·m⁻²·s⁻¹，每 60 s，12 h | 闭式 | 43.2 mol·m⁻² |
| DLI 正弦 | 1500·sin(πt/12h)，每 60 s | 闭式 2·1500·43200/π·10⁻⁶ | 41.253 |
| DLI 缺测 1 h | 恒定 1000，删去 3–4 h 内的点 | 闭式 11 h×3.6 | 39.6，状态“部分累计” |
| DLI NaN / 负值 / 零值 | 第 100 点为 NaN、-5、0 | 闭式 | 43.08 / 43.08 / 43.14 |
| DLI 跨午夜 | 22:00→02:00，恒定 100 | 闭式 | 1.44 |
| DLI 截至与周期终点 | 恒定 1000 到起点+25 h，截至 2 h / 30 h | 闭式 | 7.2 / 86.34 |
| DLI 非等距、非线性 | 时间 [0,40,120] s、值 [0,1000,2000]；另一组 22 点、间隔 30–120 s（均值约 89 s）、值 2000·(t/T)² | 闭式 / reference.py；同时算出左矩形和“固定 60 s 步长”两种错误口径，断言产品与它们相差 > 5 % | 0.14（左矩形 0.08，固定 60 s 0.12）；1.2051（左矩形 −8.0 %，固定 60 s −30 %） |
| DLI 资格 | 临时数据库：失败、dli_eligible=0、中断、启用前、带时区记录；其余记录均显式 dli_eligible=1（不含 NULL） | 闭式 | 3.3 |
| DLI 资格（旧记录，D-126） | 同上，另把 08:10、08:30、08:45、08:55 存为旧记录（dli_eligible 为空）：08:10 为 V1.0.x 双采未复核的 quality_json 内容（confirmed=false）+ 人为构造的 dli_eligible 为空（已知 V1.0.x 版本写入时同时写 dli_eligible=0，不会产生这种组合），08:30 confirmed=true，08:45 无 quality_json，08:55 quality_json 无法解析 | 每条记录的资格由 `reference.dli_record_eligible` 给出并与手写结论核对；累计值由参考梯形积分与闭式解给出 | 3.18（只有 08:10 不计入；V1.0.2 计入时为 3.30） |
| 光谱计算 | 金样光谱两两组合（LED/5778 K、mono_550/flat、2856 K/mono_550）× 加、减、比值 | `reference.spectrum_operation`、`ratio_display_threshold`、`ratio_display_passes` 按 MATH-008～015 原文重写，不 import `par_app` | mono_550/flat：550 nm 处比值 100、其余 0（A=0 有效）；flat/mono_550：550 nm 处 0.01、其余 NaN（B=0）；阈值 2.0，B=1 < T，全部不绘制 |

光谱的 5778 K 黑体同时作为 R-3-2 要求的“日光”样本；没有使用实测太阳光谱。

## 容差

| 比较 | 容差 | 理由 |
|---|---|---|
| 光子类指标 vs 参考 | 相对 1e-6（零值绝对 1e-9） | 产品常数 8.35934e-3 由 8.3593472e-3 截断，相对 -8.65e-7（审计 data-correctness §1）；1e-6 接受截断，拒绝向下改末位或改任何更高位 |
| 能量、峰值 vs 参考 | 相对 1e-12 | 无物理常数，只有求和次序误差（~1e-15） |
| 叶绿素现状快照 | 相对 1e-9 | 快照保留 12 位有效数字 |
| DLI 产品 vs 参考 / 闭式 | 相对 1e-12 | 相同算术，只有求和次序差异 |
| DLI 正弦 vs 连续积分 | 相对 1e-5 | 60 s 梯形步长对凹曲线低估约 1.6e-6 |
| 日出 产品 vs USNO | 120 s | 两种近似各约 1 分钟精度；实测差 4–39 s |
| 日出 产品 vs V1.0.2 现状钉值 | 1 ms | `tests/unit/test_services_dli.py::test_sunrise_equals_v102_status_quo`：V1.0.2（98d1e82 的 `MainWindow._sunrise`）一次性算出、手抄为常量的现状值（不是正确值）；只吸收跨平台 numpy 末位差，任何 ≥1 ms 的整体漂移（如 +480→+481）都会变红 |

## 已知缺陷与待裁决（现状值，不是正确值）

标记 `@pytest.mark.known_defect`（`pytest -m known_defect` 可单独列出）。

| 指标 | 现状 | 正确值存放 | 处理 |
|---|---|---|---|
| `par`、`extended_par` | 存 Σ/10；V1.0.2 导出直接写存储值，比界面和物理值小 10 倍（旧仓库 issue #8，审计 B1） | `test_displayed_par_equals_physical_par` 断言存储值 ×10 = 物理 PAR（MATH-007 显示口径） | `test_known_defect_stored_par_is_tenfold_smaller` 单独断言存储现状；导出已按 D-166 修复（PR #15），存储口径不变 |
| `chlorophyll_a_ypfd`、`chlorophyll_b_ypfd` | 9 锚点 Catmull-Rom 曲线，权重来源待裁决（D-102） | 无独立依据 | `status_quo.json` 快照，`test_known_defect_chlorophyll_snapshot` 只检测变化 |

## 已裁决、转为正常断言

| 指标 | 原现状（V1.0.2） | 裁决后 | 测试 |
|---|---|---|---|
| `pfd_uv`、`extended_pfd_uv` | 350–400 nm 闭区间，400 nm 同时计入 UV 与蓝光 | D-103 已裁决为 350–399 nm（MATH-022，DEF-11，PR #31），与 MCU 一致；`reference.UV_CANDIDATES["mcu_350_399"]` 为正确区间，`v102_350_400` 只用于区分两种区间 | `test_pfd_uv_is_350_399_and_counts_400nm_once`（原 `test_known_defect_pfd_uv_counts_400nm_twice`）；`test_d103_pfd_uv_equals_mcu_band`（原 strict xfail `test_pending_d103_pfd_uv_equals_mcu_band`） |

## 未覆盖的缺口

- MainWindow 刷新 DLI 时从数据库行组装各指标序列（含 `max(120, 轮询周期+60)` 允许间隔）的代码写在窗口方法内部，不构造整个 MainWindow 就无法单独调用。`test_eligibility_rows_cut_segments` 覆盖了 `ParDatabase.dli_samples` 和 `DliCanvas.plot_dli`，中间“不合格行→NaN”的映射按规格（DLI-012）在测试中重写，产品自身这段循环未覆盖。允许间隔公式（DLI-010）同样未覆盖。
- 四项 DLI 指标共用截至时间（DLI-031）、各自独立判断（DLI-017/032）需要 MainWindow，未覆盖。
- 照度（lux）、CCT、显色指数来自 MCU 寄存器，不在 `software_metrics` 内，不在本金样范围。

## Windows 基线（R-3-2）

- **数值金样**：期望值不是预先生成后存档的文件，而是在每次测试运行时由独立参考实现（`reference.py`，纯 Python、`math.fsum`、SI 精确常数）和手算闭式解当场计算；输入 `spectra.json` 与 `mccree1972_upstream.txt` 是平台无关的整数和两位小数文本，`test_stored_spectra_equal_the_generator_output` 保证输入与生成器一致。因此数值期望值不依赖平台。
- CI 的 tests 矩阵包含 `windows-latest`（内部文档，`pip install -r requirements.lock` 锁定依赖，`-m "not hardware"`），这些金样测试（marker `unit` 与 `qt`，均与字体无关）在 Windows runner 上运行并与参考值比较。数值金样在 Windows 上的验证以该 job 的结果为准；本分支在 macOS 本机运行通过，**未在本机取得 Windows 结果**，不在此声称。
- **截图 / 布局金样：具名延期。** Windows CI 的 offscreen 平台没有中文字体（issue #5），截图和布局基线在那里生成没有意义，本分支不生成。负责人：评审。完成条件：#5 解决后，在 Windows（100 % 与 150 % 缩放）用 `requirements.lock` 生成截图 / 布局基线，生成脚本与数据分开存放，记录 Windows 版本、Python 与依赖版本，并由测试比较。按 R-6-4，此项延期须负责人明确接受该具名风险后才算满足 R-3-2 的 Windows 要求。

## 更新金样的审批

- 修改 `spectra.json`、`mccree1972_upstream.txt`、`reference.py` 的口径（波段、常数、积分规则、权重）或 `status_quo.json`，PR 必须写明业务原因和前后差异。
- **凡涉及指标口径的金样变化（含 D-102、D-103、D-126 裁决后的更新、PAR 存储/导出口径），须经负责人批准（R-3-2）。** D-126 的更新（删除 `dli_d126` 快照、新增旧记录资格金样）随修复 PR 提交，待负责人批准。
- 不得把 known-defect 测试的现状值改写成“正确值”；缺陷修复后应删除或改写对应的现状测试，并把正确值断言放进普通测试。
