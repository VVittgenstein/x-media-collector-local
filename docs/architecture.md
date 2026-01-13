# x-media-collector-local 架构（MVP）

## 1. 目标与约束

- **本地部署 WebUI**：用户在浏览器里配置账号与筛选条件，启动/取消/续跑任务。
- **并发模型**：并发只发生在“账号之间”；单账号内部串行处理；全局最大并发账号数 `MaxConcurrent` 默认 **3**，可调整；其余任务 **FIFO** 排队。
- **任务锁定**：点击 Start/Continue 后，该行账号参数立即锁定（无论 Queued 还是 Running）；任务结束或取消后解锁。
- **抓取方向**：不使用官方 API，走“已登录会话 + X 网页内部接口（GraphQL）”，优先集成 `twscrape`；同时要预留抓取层可替换/升级空间。
- **结果目标**：落盘目录结构、命名、去重与统计口径可复现；UI 不做预览墙，仅展示统计与打开文件夹入口。

## 2. 组件划分（高层）

- **Frontend（Browser UI）**
  - 账号列表（Account Rows）：URL + 每账号筛选配置 + 状态/统计 + 控制按钮。
  - 全局设置（Global Settings）：凭证、Download Root、MaxConcurrent。
  - 通过 `REST + SSE` 与后端交互。
- **Backend（FastAPI）**
  - API：设置读写、账号行管理、任务控制（start/continue/cancel）、状态快照、事件流（SSE）。
  - 内置 **Scheduler/Runner**：负责队列、并发、任务生命周期与状态持久化。
- **Scheduler（队列与并发控制）**
  - 全局 FIFO 队列 + `MaxConcurrent` 并发闸门。
  - 账号级互斥：同一 handle 同时最多 1 个活跃 run（Queued/Running）。
- **Runner（单账号执行器）**
  - 调用 Scrape Layer 迭代推文/媒体候选 → Filter Engine 过滤 → Downloader 落盘与去重 → 更新统计与进度。
- **Scrape Layer（可替换）**
  - 封装与 X 内部接口交互（默认：`twscrape`）。
  - 输出统一的领域对象（Tweet/MediaCandidate），屏蔽上游字段/分页细节。
- **Business Layer（稳定核心）**
  - Filter Engine：日期/媒体类型/来源类型/Reply+Quote 开关/MIN_SHORT_SIDE 等纯逻辑。
  - Downloader：命名、去重、文件写入、临时文件清理、统计口径。
- **Persistence（本地）**
  - `data/config.json`：全局设置（含敏感凭证，需避免日志输出与 UI 明文回显）。
  - `data/accounts.json`：账号列表与每账号配置（用于 UI 重启恢复）。
  - `data/runs/<run_id>.json`：运行时状态快照/游标（用于 Continue）。
  - `data/dedup/<handle>.*`：账号内去重索引（内容 hash → 已存在文件）。

## 3. 进程与并发模型

- **单进程模型**：一个 Python 进程同时承载 Web Server 与后台调度/运行（避免额外部署组件，利于一键启动）。
- **并发原则**：
  - **账号间并发**：最多 `MaxConcurrent` 个账号同时处于 Running。
  - **账号内串行**：Runner 内按“分页 → 推文 → 媒体”串行推进，配合限速/退避降低风控风险（MVP 先以正确性与稳定性为主）。
- **取消与收敛**：
  - Running 取消通过 cancellation token/`asyncio.Task` 取消触发，Runner 在关键边界点检查并尽快退出。
  - 取消/失败/完成均应落盘最终状态，确保 UI 重载后能收敛到一致视图。

## 4. 任务模型（状态机 + 锁定）

### 4.1 任务实体

- **Account Row**：UI 的一行；包含 `url/handle + account_config + task_status + stats`。
- **Run**：一次执行实例，对应一次 Start New 或 Continue（建议为每次点击生成唯一 `run_id`）。
- **Job（调度单元）**：Scheduler 管理的队列元素，实质上是 `run_id` 的引用及其运行参数快照。

### 4.2 状态机（MVP）

`Idle → (Queued | Running) → Done / Failed / Cancelled`

- Idle → Running：当 `running_count < MaxConcurrent` 且账号无活跃 run。
- Idle → Queued：当无可用 slot（或策略要求排队）。
- Queued → Running：有 slot 后按 FIFO 出队并启动。
- Queued → Idle：Queued 取消（移出队列、无副作用、立即解锁）。
- Running → Done：正常完成。
- Running → Failed：不可恢复错误（401/403/解析失败等）或重试耗尽。
- Running → Cancelled：用户取消（是否保留/清理临时文件由取消选项决定，见 ADR-0002）。

### 4.3 锁定规则

- **锁定时机**：用户点击 Start New / Continue 后，后端接受请求即立刻将该账号置为 Locked（Queued/Running 都视为 Locked）。
- **锁定范围**：URL、筛选参数、Copy/Paste Config、Start/Continue 均不可操作（允许 Cancel）。
- **解锁时机**：进入 Done/Failed/Cancelled 或 Queued 取消后回到 Idle。

## 5. UI 状态刷新（SSE）

- **初始快照**：页面加载 `GET /api/state` 获取全量状态（账号列表 + 全局设置 + 所有任务状态）。
- **增量更新**：页面建立 `GET /api/events`（SSE）订阅事件流，接收状态变更与进度事件。
- **一致性策略**：
  - 每条事件带 `seq`（单调递增）与 `updated_at`；前端按 `seq` 严格应用，忽略乱序/重复。
  - SSE 断线重连后：若检测到 `seq` 跳跃或超时，前端重新拉取 `GET /api/state` 以恢复一致性。
  - 兜底：可按 30–60s 周期轮询快照（只在 SSE 断开或前台切换恢复时启用）。

## 6. Scrape Layer 与业务层边界（可替换点）

### 6.1 领域对象（建议）

- `Tweet`: `tweet_id`, `created_at`, `source_type`(Original/Reply/Retweet/Quote), `quoted_tweet_id?`, `media[]`
- `MediaCandidate`: `media_id`, `kind`(image/video), `url`, `width`, `height`, `tweet_id`, `created_at`

### 6.2 接口形状（示意）

- `Scraper.iter_media_candidates(handle, credentials, cursor?) -> AsyncIterator[MediaCandidate]`
- Scrape Layer 只负责“**尽可能稳定地拿到候选媒体**”，不关心下载目录/命名/去重/队列/统计。
- Business Layer 只依赖上述稳定对象与游标语义；Scrape Layer 可替换为：
  - `twscrape`（默认）
  - 自研 GraphQL（应急）
  - 浏览器自动化（兜底/高成本）

## 7. 本地目录与持久化约定（建议）

- 输出目录：`<download_root>/<handle>/images/` 与 `<download_root>/<handle>/videos/`
- 文件命名：必须包含 `tweetId`，并包含 `created_at` 日期与内容 hash 前缀（详见后续命名 ADR/规范任务）。
- 去重：账号内基于“下载后内容 hash”判重，first wins；重复下载的临时文件删除并计入 `skipped_duplicate`。

