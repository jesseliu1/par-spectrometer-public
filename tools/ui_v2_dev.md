# 2.0.0-alpha 网页界面：开发者启动说明

阶段二路线 C（内部文档）的网页界面在 `web/`（Vue 3 + TypeScript + Vite + ECharts），本机服务在 `par_app/api/`，桌面外壳在 `par_shell/`。alpha 档位 0：只读历史库快照，不连接、不写设备。

## 一次性准备

- Python：`python -m venv .venv`，再 `pip install -r requirements.lock`（含 fastapi、uvicorn、pywebview；Windows 上 pywebview 走 pythonnet + WebView2）。
- Node 22（≥ 22.22.2）：开发和打包时才需要，用户安装包里没有 Node。
- 前端依赖：`cd web && npm ci`（按 `package-lock.json` 安装，版本全部锁定）。

## 一条命令起服务 + 前端

```bash
python tools/ui_v2_dev.py --demo
```

- 起本机服务（127.0.0.1，随机端口），数据目录默认 `~/.local/share/PAR_Spectrometer_2-dev`（开发专用，不是 alpha 正式数据目录，可用 `--data-dir` 改）。
- `--demo`：用 `tools/ui_v2_demo_db.py` 生成两个**合成**的 V1.0.x 格式数据库并导入为位置 1、2 的快照（已存在就跳过）。不要把现场数据库当演示数据用（R-4-7）。演示库带当天 00:00 的 DLI 启用时间；要在“光积累计算”页看到曲线，用 `python tools/ui_v2_demo_db.py <新文件> --every-minutes 1` 另生成每分钟一条的库再导入（默认允许间隔 120 秒，10 分钟一条的记录连不成积分区段）。
- 页面地址加 `?view=dli` 直接打开“光积累计算”页（如 `http://127.0.0.1:5173/?view=dli`），`?view=calc` 打开“光谱计算”页，`?view=settings` 打开“设置与导出”页（配置只读；采集记录导出写到数据目录的 `exports/<设备>/<CSV|Excel>/<日期>/`，D-210；页面底部的“导出诊断包”写 `exports/diagnostics/`，“维护记录”列出 alpha 设备库中记录的设备写入，D-226）。
- 光谱计算页要看出比值，可另生成一个“温室内”库：`python tools/ui_v2_demo_db.py <新文件> --filter greenhouse --offset-seconds 20`（同一光源乘一条虚构的覆盖材料透过率，每条记录晚 20 秒），导入到另一个位置。导出的文件在数据目录的 `exports/` 下（D-207）。
- 然后在 `web/` 里运行 `npm run dev`：打开 <http://127.0.0.1:5173/>，改代码即热更新。浏览器里没有令牌，Vite 代理（`web/dev-proxy.ts`）每次请求读 `service.json` 代加令牌，并拒绝其他来源（Host/Origin）的请求。
- `Ctrl+C` 同时停掉两者。`--no-vite` 只起服务。

也可以分开起：

```bash
PAR_ALPHA_DATA_DIR=~/.local/share/PAR_Spectrometer_2-dev python -m par_app.api --port 0
cd web && PAR_ALPHA_DATA_DIR=~/.local/share/PAR_Spectrometer_2-dev npm run dev
```

## 构建与由服务托管

```bash
cd web && npm run build          # vue-tsc 类型检查 + vite build → web/dist（不入库）
python -m par_app.api --port 0   # 自动托管 web/dist；或 --web-dir <目录> / 环境变量 PAR_WEB_DIR
```

服务在 `/` 托管页面（静态文件不需要令牌，带只允许本源的 CSP），`/api/v0` 仍要令牌。直接在浏览器打开时，地址要带令牌片段：`http://127.0.0.1:<端口>/#token=<service.json 里的 token>`，页面读取后会立即从地址栏去掉。

## 桌面外壳

```bash
python -m par_shell                     # 起服务子进程 → 读 service.json → 打开窗口；关窗即停服务
python -m par_shell --smoke 15          # 本地冒烟：页面取到设备列表后自动关窗，成功退出码 0
python -m par_shell --browser           # 不开窗口，用默认浏览器打开（WebView2 缺失时的兜底）
```

Windows 上外壳先查 WebView2 运行时（注册表 EdgeUpdate 客户端键 `pv`，方案附录 C）；缺失时提示随包离线安装程序位置（`redist/`），可选用浏览器打开。**这部分尚未在 Windows 上验证。**

## 检查

```bash
cd web && npm run check:tokens   # 颜色值只能出现在 src/styles/tokens.css（R-1-5）
cd web && npm run test           # vitest：API 客户端、时间范围、错误时保留数据、页面状态、组件
cd web && npm run build
cd web && npm run test:e2e       # Playwright 端到端（真实服务 + 合成库 + Chromium）：导入、查询、选择、失败保留与重试、
                                 # 图表实际渲染、非 127.0.0.1 请求拦截。需先 npm run build 与 npx playwright install chromium；
                                 # 在 worktree 等没有 .venv 的目录用 PAR_E2E_PYTHON 指定 Python
python tools/quality/check_all.py   # 含 tests/api/test_web_smoke.py（需先 npm run build，否则跳过）
python tools/ui_v2_screenshot.py <输出目录> [--page dli] [--height 1300]   # 本机 Chrome/Edge 无界面截图（100% 与 150%）
cd web && PAR_SCREENSHOT_DIR=<输出目录绝对路径> npm run test:e2e -- -g 截图   # 光谱计算页执行比值后的截图 calc-100/150.png（1680×900）
```

## 设计令牌

`web/src/styles/tokens.css` 是唯一允许写颜色的文件，变量名对齐 Stitch designMd / Material 颜色角色（`--color-surface`、`--color-on-surface`、`--color-primary`、`--color-outline` 等）。现在是中性占位方向（S-9：负责人在 Stitch 三套方向中选定前），选定后只换这个文件的值。ECharts 的颜色通过 `web/src/lib/theme.ts` 从令牌读取。
