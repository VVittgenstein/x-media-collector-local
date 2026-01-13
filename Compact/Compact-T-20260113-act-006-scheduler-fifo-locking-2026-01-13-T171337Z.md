# Compact — T-20260113-act-006-scheduler-fifo-locking

- generated_at_utc: 2026-01-13T17:13:37Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：落地可工作的 Scheduler（全局 FIFO + MaxConcurrent=3 默认值 + per-handle 互斥），并打通前端 Start/Continue/Queued Cancel 的锁定/解锁体验。
- 非目标：不交付真实抓取/过滤/下载 Runner（本任务用可取消的 sleep runner 占位，后续任务替换为 pipeline）。

## 2) 已确认事实（Repo 落地 + 实现覆盖）

- [FACT] `record.json` 中 `T-20260113-act-006-scheduler-fifo-locking` 已更新为 `status: done`，`updated_at: 2026-01-13T17:13:37Z`，`owner: codex`。
- [FACT] 已新增后端 Scheduler 模块与 API：
  - `src/backend/scheduler/scheduler.py`：FIFO 队列 + MaxConcurrent 闸门 + per-handle 活跃互斥（Queued/Running）。
  - `src/backend/scheduler/api.py`：`/api/scheduler/*`（start/continue/cancel/state/handles）。
  - `src/backend/scheduler/models.py`：Run 记录与 UTC 时间格式化。
- [FACT] 已新增稳定状态枚举：
  - `src/shared/task_status.py`：`Idle / Queued / Running / Done / Failed / Cancelled`（与 ADR-0002 对齐）。
- [FACT] 已打通前端交互：
  - `src/frontend/app.js`：Start/Continue 调用后端、Queued/Running 锁定配置与 URL、Queued Cancel 直接解锁（无弹窗）。
- [FACT] 已完成应用集成：
  - `src/backend/app.py`：挂载 scheduler router，并在 app.state 注入 `scheduler`。
  - `src/backend/settings/api.py`：更新 `MaxConcurrent` 后调用 `scheduler.reschedule()` 以便立即补齐队列。
- [TEST] 语法检查：`python3 -m py_compile ...` → OK
- [TEST] 现有 unittest（不含 pytest 用例）：`python3 -m unittest tests.validators.test_x_handle_url tests.filter_engine.test_fixtures` → OK

## 3) 已落实的关键行为（验收对齐）

- [CONTRACT] MaxConcurrent=3：连续对 5 个不同账号点 Start/Continue，调度器会让前 3 个进入 Running，其余进入 Queued（全局 FIFO）。
- [CONTRACT] FIFO：任一 Running 结束后，Scheduler 自动从队首取出下一个 Queued 转为 Running（不会让新任务插队）。
- [CONTRACT] 立即锁定：Start/Continue 被后端接受后，账号行状态进入 Queued/Running，UI 立即锁定 URL 与配置输入，并禁用 Paste。
- [CONTRACT] Queued Cancel：Queued 状态点击 Cancel 会直接从队列移除并回到 Idle，立即解锁、无弹窗、无副作用。
- [CONTRACT] per-handle 互斥：同一 handle 若已有活跃任务（Queued/Running），新的 start/continue 会被后端以 409 拒绝。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 后续生命周期任务（`T-20260113-act-007-lifecycle-start-continue-cancel`）可在此基础上扩展 Running Cancel 的 Keep/Delete 弹窗与文件系统效果，并替换占位 runner 为真实 pipeline。
- [IMPACT] 后续抓取与过滤集成（`T-20260113-act-009-scrape-and-apply-filters`）可复用 Scheduler 的 Run 参数快照（account_config）作为过滤/下载输入。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] Runner 当前为可取消的 sleep 占位实现，仅用于验证 FIFO/锁定/取消语义；未做真实抓取/落盘。
- [LIMIT] 前端当前用轮询 `/api/scheduler/state` 做状态刷新（800ms）；SSE/seq 一致性策略将在后续任务落地。
