# Compact — T-20260113-act-001-arch-task-model

- generated_at_utc: 2026-01-13T11:10:31Z
- subtask_type: design
- record_status: done

## 1) Scope（对齐范围）

- 目标：拍板本地 WebUI 工具的后端架构与异步任务执行模型，支撑“账号级并发（默认 3）+ FIFO + 参数锁定 + 状态展示”，并明确抓取层与业务层边界。
- 非目标：本 Subtask 不交付可运行的抓取/队列/前端实现代码（仅产出架构/ADR 文档与记录更新）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-001-arch-task-model` 已更新为 `status: done`，并写入 `updated_at: 2026-01-13T10:58:30Z`、`owner: codex`。
- [FACT] 已新增设计文档（当前工作区存在；`git diff` 未展示因文件为 untracked）：`docs/architecture.md`、`docs/adr/0001-tech-stack.md`、`docs/adr/0002-task-execution-model.md`。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → `OK`。

## 3) 已落实的“契约/决策”（文档定义；待后续实现落地）

- [CONTRACT] 技术栈（ADR-0001）：后端 `Python 3.11+` + `FastAPI(Uvicorn)` + `asyncio`；抓取层优先 `twscrape`；前端 MVP 为后端托管的静态 `HTML/CSS/JS`；状态推送选 `SSE`。
- [CONTRACT] 并发与队列（ADR-0002）：调度单元为 `Run(run_id)`；全局 FIFO 队列 + `MaxConcurrent`（默认 3）；同一 `handle` 仅允许一个活跃 Run（Queued/Running），冲突返回 `409`。
- [CONTRACT] 状态机与锁定（architecture + ADR-0002）：`Idle / Queued / Running / Done / Failed / Cancelled`；Start/Continue 请求被接受即进入 Queued/Running 并立即锁定参数；结束或取消后解锁；Queued 取消无副作用并解锁。
- [CONTRACT] UI 状态一致性（architecture + ADR-0002）：`GET /api/state` 获取快照；`GET /api/events` 以 SSE 推增量事件；事件携带 `seq` 与 `updated_at`，前端按 `seq` 去重/顺序应用，断线或 seq 跳跃时回拉快照；可选轮询作为兜底。
- [CONTRACT] 分层边界（architecture）：Scrape Layer 输出稳定领域对象（示例 `Tweet`/`MediaCandidate`），并提供 `iter_media_candidates(handle, credentials, cursor?)`；业务层（Filter Engine/Downloader）不绑定抓取实现，抓取层可替换/升级。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] Backend 需提供：状态快照接口（`/api/state`）、SSE 事件流（`/api/events`），以及任务控制能力（start/continue/cancel；具体路由在后续实现任务中落盘）。
- [IMPACT] 前端状态同步需遵循：快照 + SSE 增量、`seq` 顺序应用、断线重连后回拉快照的恢复策略。
- [IMPACT] 调度器需遵循：全局 FIFO + `MaxConcurrent` 动态调整语义（调小不抢占已 Running）+ per-handle 互斥（409 冲突）。
- [IMPACT] 本地持久化路径约定（architecture/ADR-0002）：`data/config.json`、`data/accounts.json`、`data/runs/<run_id>.json`、`data/dedup/<handle>.*` 将被后续实现任务引用。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前仅完成架构与 ADR 文档输出；未实现真实 API/队列/Runner/抓取/落盘逻辑。
- [TODO] Running 取消的“保留/删除已落盘文件”二选一策略尚未定义/实现（ADR-0002 明确延后）。
- [RISK] 若 UI 复杂度显著上升，可能需要引入 SPA 构建链并调整发布流程（ADR-0001 已提示）。
- [RISK] 凭证敏感信息的“本地存储/不日志输出/不 UI 明文回显”需要在后续实现中严格落实（本 Subtask 仅在架构层标注约束）。

## Code Review - T-20260113-act-001-arch-task-model - 2026-01-13T12:39:26Z

---review-start---
[P1] Render settings UI when initial fetch fails  
If the initial `/api/settings` request returns non-2xx (or throws), `load()` returns without calling `_render`, leaving all settings blocks empty and preventing users from entering credentials or other values. Because the UI never renders any form after the first failure, the user cannot recover (even if the backend comes back) without a full page reload. Consider rendering default fields and showing the error banner so the page remains usable after transient API errors.
---review-end---
