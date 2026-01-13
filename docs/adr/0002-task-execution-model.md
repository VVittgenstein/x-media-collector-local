# ADR-0002：异步任务执行模型（账号级并发 + FIFO 队列）

- Status: **Accepted**
- Date: 2026-01-13

## 背景 / Context

产品行为要求：

- 并发只发生在账号之间；全局最大并发账号数 `MaxConcurrent` 默认 3，可随时调整。
- 同一账号不可并行跑多个任务（账号级串行）。
- 超出并发上限的任务进入 FIFO 队列。
- 点击 Start/Continue 后该行参数立即锁定（Queued/Running 都锁定），直到任务结束或取消。
- UI 需要稳定地获取状态与进度，且在刷新/重连后能恢复一致视图。

## 决策 / Decision

### 1) 调度单元：Run（一次执行实例）

- 每次点击 **Start New** 或 **Continue** 都创建一个 `run_id`（UUID/时间戳均可）。
- `Run` 记录：`handle`、启动类型（start/continue）、当次的参数快照（用于锁定与可复现）、进度/统计、错误信息、更新时间等。

### 2) 全局调度：FIFO 队列 + 并发闸门

- Scheduler 维护：
  - `queue`: 全局 FIFO 队列（元素为 `run_id`）
  - `running`: 当前 Running 的 `run_id` 集合
  - `max_concurrent`: 运行中账号数上限（默认 3）
- 入队策略：
  - 当用户请求 start/continue 且系统可接受该账号（见“账号级互斥”），创建 Run；
  - 若 `len(running) < max_concurrent` → 直接进入 Running 并启动；
  - 否则 → 进入 Queued（追加到 `queue` 尾部）。
- 出队策略：
  - 当任一 Running 结束（Done/Failed/Cancelled）或 `max_concurrent` 调大；
  - Scheduler 从 `queue` 头部取出队首 run，转为 Running 并启动，直到 `len(running) == max_concurrent` 或队列为空。

### 3) 账号级互斥：同 handle 仅允许一个活跃 Run

- 定义“活跃”：`Queued` 或 `Running`。
- 约束：同一 `handle` 若已有活跃 Run，则新的 start/continue：
  - **后端返回 409（Conflict）**；
  - 前端按钮置灰/提示“该账号任务已在队列/运行中”。
- 实现建议：
  - 维护 `active_run_by_handle: Dict[handle, run_id]`
  - 或者为每个 handle 使用 `asyncio.Lock` 并结合状态检查（防止竞态）

该设计保证“账号内串行”与 UI 锁定语义天然一致。

### 4) 状态机与锁定规则

对外（UI）状态固定为：

`Idle / Queued / Running / Done / Failed / Cancelled`

状态转换：

- `Idle → Running | Queued`：用户 start/continue 且请求被接受后立即进入（并立即锁定参数）。
- `Queued → Running`：按 FIFO 轮到且有并发 slot。
- `Queued → Idle`：Queued 取消（移出队列、解锁、无副作用）。
- `Running → Done/Failed/Cancelled`：运行结束/失败/取消（解锁）。

锁定规则：

- **锁定时机**：Run 创建成功即锁定（进入 Queued/Running）。
- **锁定范围**：URL、筛选参数、Copy/Paste、Start/Continue 不可变更；仅允许 Cancel。
- **解锁时机**：进入 Done/Failed/Cancelled，或 Queued 取消回 Idle。

### 5) MaxConcurrent 动态调整

- 调大：Scheduler 立即尝试从队首补齐新的 Running。
- 调小：不强行打断已 Running 的任务；仅在后续调度时限制新的启动，直到 Running 数回落到上限之下。

### 6) 取消语义（MVP）

- Queued 取消：从 `queue` 移除该 `run_id`，将状态置回 `Idle`，不触碰文件系统。
- Running 取消：对 Runner 发出取消信号（`asyncio` 取消/检查 token），Runner：
  - 尽快停止新的抓取/下载；
  - 清理由本次下载产生的“临时文件”（例如 `.part`）；
  - 已经落盘的最终文件是否删除，由“取消选项”决定（后续任务再细化为 Keep/Delete 二选一）。

### 7) 状态更新：事件流 + 快照兜底

- 每次状态或统计变更都写入内存状态，并 **append/覆盖** 到 `data/runs/<run_id>.json`（保证重启后可回放到最后状态）。
- 后端通过 SSE 推送事件：
  - `run_state_changed`（Queued/Running/Done/Failed/Cancelled）
  - `run_progress`（下载数、跳过数、过滤数、速率、当前页/游标等）
  - `run_log`（可选，面向用户的简短提示）
- 前端一致性：
  - 页面加载先拉快照 `GET /api/state`
  - 再订阅 SSE，并使用 `seq` 进行去重/顺序保证
  - 断线重连或检测到 `seq` 跳跃时重新拉快照

## 备选方案 / Alternatives Considered

- 外部任务队列（Celery/RQ/Redis）：会引入额外服务依赖，不利于一键启动与本地工具定位。
- 线程池：可行但状态同步与取消更复杂；在 Python 中优先选择 asyncio 以贴合 I/O 密集的抓取/下载流程。
- 每账号独立队列：更灵活但超出 MVP 需求；MVP 用全局 FIFO 即可满足验收用例。

## 影响 / Consequences

- ✅ 严格满足“账号级并发 + FIFO + 立即锁定”的产品行为。
- ✅ 通过“每 handle 仅一个活跃 Run”简化竞态与 UI 逻辑。
- ✅ SSE + 快照兜底可在刷新/重启/断线下收敛一致。
- ⚠️ Running 取消的“保留/删除”策略需要后续任务明确，以免影响续跑与去重语义。

