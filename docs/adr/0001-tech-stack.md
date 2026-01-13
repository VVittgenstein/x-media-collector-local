# ADR-0001：技术栈选择（本地 WebUI + 后台任务）

- Status: **Accepted**
- Date: 2026-01-13

## 背景 / Context

本项目是一个“本地部署 WebUI 小工具”，需要：

- 与 X 网页内部接口交互（GraphQL/非官方路径），且上游变化快，最好能集成成熟开源抓取库以降低维护成本。
- 支持长时间运行的后台任务：账号级并发（默认 3）+ FIFO 队列 + 任务锁定/状态展示。
- 尽量做到**一键启动**（不引入多进程/外部服务依赖），同时保持可维护性与可观测性。

## 决策 / Decision

### 后端

- 语言：**Python 3.11+**
- Web 框架：**FastAPI（ASGI） + Uvicorn**
- 并发/任务：**asyncio**（同进程内运行 Scheduler/Runner）
- 抓取层：优先集成 **twscrape**（可替换；业务层不绑定具体实现）
- 配置/状态持久化：本地文件（MVP 以 `data/*.json` 为主；必要时可引入 SQLite 作为内部索引实现细节，但不做“建库型产品”）

选择理由：

- `twscrape` 生态在 Python 侧更成熟；与抓取相关的调试/替换路径成本更低。
- FastAPI 便于提供 REST + SSE，并与 asyncio 的后台调度模型自然契合。
- 单进程内可实现“HTTP API + 后台队列”，利于一键启动与问题定位。

### 前端

- 形态：浏览器访问的本地 WebUI
- MVP 实现：**无构建链的静态页面（HTML/CSS/JS）**，由后端直接托管（降低本地启动复杂度）

说明：

- UI 复杂度主要集中在表单与状态展示（非重型交互/可视化）；MVP 不必强依赖 React/Vue 构建链。
- 若后续 UI 复杂度显著上升，可再引入 SPA（React/Vite 等），但不作为当前 MVP 的默认前提。

### 状态推送机制

- 采用 **SSE（Server-Sent Events）** 作为 UI 的实时状态更新通道；页面加载时先拉 `GET /api/state` 快照，再订阅 `GET /api/events` 增量事件。

选择理由：

- SSE 足够覆盖“任务状态/进度”单向推送需求，实现与部署复杂度低于 WebSocket。
- 断线重连与“快照兜底”组合可保证最终一致性与可恢复性。

## 备选方案 / Alternatives Considered

- Node.js（TypeScript）后端 + React/Vue 前端：生态成熟但会引入“抓取库选择/多语言集成”的额外复杂度；且一键启动需要处理双工具链（Node + Python 或纯 JS 抓取替代）。
- Go/Rust + 桌面壳（Wails/Tauri/Electron）：可打包体验好，但前期工程化与抓取生态集成成本更高，不利于快速迭代验证抓取与规则正确性。
- WebSocket：双向能力更强，但本项目主要是“后端推状态”，SSE 已足够。

## 影响 / Consequences

- ✅ 单运行时（Python）即可启动后端与任务调度；部署和排障更简单。
- ✅ Scrape Layer 可围绕 Python 生态快速迭代（升级/替换 `twscrape`）。
- ✅ SSE 提供足够的实时性且实现简单，UI 容错路径清晰（断线 → 重连/快照）。
- ⚠️ 若未来需要更复杂的前端交互（大量组件复用、复杂状态管理），可能需要引入构建链并调整目录结构与发布流程。

