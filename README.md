# PAR 光谱仪专用软件 2.0

PAR 光谱仪（ASMART-GROW-SPECTRA I）的 Windows 上位机，2.0 版本。通过 Modbus RTU/TCP 采集
350–1050 nm 共 701 点光谱，计算 PPFD、McCree YPFD、叶绿素加权等指标，提供概览、历史回放、光谱运算、DLI、
导出、设备维护和诊断包。

作者：jesse.sijia.liu（jesse.sijia.liu@gmail.com）。本仓库是私有开发仓库的公开导出，每个发布版本单向同步一次，不含开发历史。当前版本见 `VERSION`。

## 结构

| 路径 | 内容 |
|---|---|
| `main_v2.py`、`par_shell/` | 桌面外壳：启动本地服务，用系统 WebView 打开网页界面 |
| `par_app/service_main.py`、`par_app/api/` | 本地服务（FastAPI），只监听本机 |
| `par_app/application/` | 应用层：页面用到的数据与操作 |
| `par_app/acquisition_host/` | 采集与设备维护（Qt 事件循环，PySide6 QtCore） |
| `par_app/services/`、`par_app/domain/` | 不依赖界面的业务规则与计算 |
| `par_app/protocol.py`、`coordinator.py`、`database.py`、`math_ops.py` 等 | 协议、轮询调度、存储、指标计算 |
| `web/` | 网页界面（Vue + Vite），含单元测试与 Playwright 端到端测试 |
| `docs/spec/` | 业务规格：每条规则一个编号（如 `ACQ-012`），待裁决与已裁决事项见 `pending-decisions.md`（`D-xxx`） |
| `docs/algorithms/` | 权重表与指标的验证脚本 |
| `docs/design/` | 2.0 界面设计说明 |
| `tests/` | pytest：单元、接口、采集、金样 |
| `tools/` | 打包、质量检查、开发辅助脚本 |

代码注释里的 `#N`、`PR #N` 指私有仓库中的 issue 和合并请求，公开仓库里没有对应页面；规格编号和 `D-xxx`
可在 `docs/spec/` 中查到。

## 开发环境

需要 Python 3.11 和 Node.js 22.22.2 以上（见 `web/package.json`）。

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.lock -r requirements-dev.txt
cd web && npm ci && npm run build && cd ..
.venv/bin/python main_v2.py
```

先构建网页界面（`web/dist`），桌面外壳和打包都用它。Windows 测试包用 `build_alpha.ps1` 构建。

## 检查与测试

```bash
.venv/bin/python tools/quality/check_all.py
```

依次运行质量棘轮、分层契约、规格映射检查、mypy、网页检查和 pytest（不含需要真机的 `hardware` 测试）。
在 macOS 上，像素和字体相关的断言可能出现伪失败。

## 许可证

PolyForm Strict License 1.0.0，见 `LICENSE.md`；第三方组件见 `NOTICE`。本仓库不接受外部贡献，见
`CONTRIBUTING.md`。
