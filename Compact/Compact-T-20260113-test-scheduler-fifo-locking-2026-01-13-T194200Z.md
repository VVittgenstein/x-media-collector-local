# Compact — T-20260113-test-scheduler-fifo-locking

- generated_at_utc: 2026-01-13T19:42:00Z
- subtask_type: test
- record_status: done

## 1) Scope（对齐范围）

- 目标：为调度器模块（`src/backend/scheduler/scheduler.py`）补齐自动化测试用例，覆盖 FIFO 队列行为、锁定状态和 Queued 取消逻辑。
- 非目标：不涉及实际任务执行（使用可控的 mock runner），不测试前端 UI 交互。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-test-scheduler-fifo-locking` 已更新为 `status: done`，`updated_at: 2026-01-13T19:42:00Z`，`owner: codex`。
- [FACT] 测试文件：`tests/scheduler/__init__.py`、`tests/scheduler/test_fifo_locking.py`。
- [TEST] 测试套件包含 12 个测试用例，全部通过：`python3 -m unittest tests.scheduler.test_fifo_locking -v`。

## 3) 已落实的"契约/决策"（测试覆盖）

### 验收条件1：覆盖 5 个账号 Start + MaxConcurrent=3 -> 3 Running + 2 Queued

- [CONTRACT] `test_five_accounts_three_running_two_queued`：
  - 创建 MaxConcurrent=3 的调度器
  - 依次入队 5 个账号（user1-user5）
  - 断言 `running_count == 3`，`queued_count == 2`
  - 断言 user1、user2、user3 为 Running
  - 断言 user4、user5 为 Queued（FIFO 顺序）
  - 验证 queue position：user4 -> 1，user5 -> 2

### 验收条件2：覆盖 Running 完成后队首转 Running

- [CONTRACT] `test_fifo_order_preserved_on_completion`：
  - 创建 MaxConcurrent=2 的调度器
  - 入队 4 个账号（first、second、third、fourth）
  - 初始状态：first + second Running，third + fourth Queued
  - 完成 first 任务，断言 third 自动提升为 Running
  - 队列变为：second + third Running，fourth Queued
  - 完成 second，断言 fourth 自动提升
  - 最终：third + fourth Running，队列为空

### 验收条件3：覆盖 Queued Cancel 直接移除且解锁，不触发 "Keep/Delete" 弹窗路径

- [CONTRACT] `test_queued_cancel_removes_from_queue_immediately`：
  - Queued 任务调用 `cancel()` 立即返回 `TaskStatus.IDLE`
  - 断言从队列中移除
  - 断言 handle 状态变为 IDLE

- [CONTRACT] `test_queued_cancel_unlocks_handle`：
  - 取消后 handle 解锁（`is_locked() == False`）
  - 可重新入队同一 handle（证明解锁成功）

- [CONTRACT] `test_queued_cancel_no_filesystem_side_effects`：
  - Queued 取消无文件系统副作用
  - 返回 IDLE，不触发 Keep/Delete 选择路径

### 验收条件4：覆盖 Locked 时配置不可更改/不可 Paste（可用状态断言表达）

- [CONTRACT] `test_queued_status_is_locked`：
  - `TaskStatus.QUEUED.is_locked()` 返回 True

- [CONTRACT] `test_running_status_is_locked`：
  - `TaskStatus.RUNNING.is_locked()` 返回 True

- [CONTRACT] `test_idle_status_is_not_locked`：
  - IDLE、DONE、FAILED、CANCELLED 状态 `is_locked()` 返回 False

- [CONTRACT] `test_locked_states_defined_correctly`：
  - 仅 QUEUED 和 RUNNING 为锁定状态

- [CONTRACT] `test_cannot_enqueue_same_handle_when_locked`：
  - Running 状态下重复入队抛出 `SchedulerConflictError`
  - 错误信息包含"已有活跃任务"

- [CONTRACT] `test_cannot_enqueue_queued_handle`：
  - Queued 状态下重复入队同样抛出 `SchedulerConflictError`

### 额外覆盖：配置变更时重调度

- [CONTRACT] `test_increase_max_concurrent_promotes_queued`：
  - MaxConcurrent 从 1 调至 3
  - 调用 `reschedule()` 后队列中任务自动提升
  - 验证所有 3 个任务变为 Running

## 4) 接口/行为变更对其他模块的影响

- [IMPACT] 无新增接口变更。测试用例锁定现有调度器行为。
- [IMPACT] 后续修改 `scheduler.py`、`models.py`、`config.py`、`task_status.py` 必须保持测试通过。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 使用 unittest 运行测试（环境未安装 pytest）。
- [LIMIT] 测试使用 asyncio.Event 控制的 mock runner，未涉及真实任务执行。
- [LIMIT] 未测试 Running 任务取消的 Keep/Delete 逻辑（该逻辑在 lifecycle 模块，非本任务范围）。
- [TODO] 如需 CI 集成，建议添加 pytest 依赖。
