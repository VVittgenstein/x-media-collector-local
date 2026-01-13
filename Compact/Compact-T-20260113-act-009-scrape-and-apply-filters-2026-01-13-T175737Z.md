# Compact — T-20260113-act-009-scrape-and-apply-filters

- generated_at_utc: 2026-01-13T17:57:37Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：把 Scrape Layer 的抓取结果转换为 Filter Engine 可消费的稳定领域对象，并将日期、媒体类型、来源类型、Reply+Quote 开关、MIN_SHORT_SIDE 应用到最终“下载意图”集合；同条件下结果稳定可复现。
- 非目标：不在本任务内交付限流/随机延迟/指数退避/代理配置（交由 `T-20260113-act-011-throttle-backoff-proxy`）；不在本任务内完整落地“无尺寸信息时下载后再做 MIN_SHORT_SIDE 判定”的策略（保持标记，后续统一）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-009-scrape-and-apply-filters` 已更新为 `status: done`，`updated_at: 2026-01-13T18:47:02Z`，`owner: codex`。
- [FACT] 已新增 UserMedia GraphQL 响应解析器：`src/backend/scraper/user_media_parser.py`（抽取 timeline 顶层 tweets、解析 created_at、提取 photo/video 媒体、video 选最高 bitrate 的 mp4、图片 URL 统一升级 `name=orig`、并可提取 bottom cursor）。
- [FACT] 已新增 `twscrape` Scrape Layer 封装：`src/backend/scraper/twscrape_scraper.py`（`user_by_login` + `user_media_raw` 分页迭代；每页输出 `ScrapePage(tweets, bottom_cursor)`；并提供 `collect_tweets()` 做跨页稳定排序）。
- [FACT] 已新增单账号 Runner 管线：`src/backend/pipeline/account_runner.py`（`scrape -> apply_filters -> MediaDownloader`），并在 `src/backend/app.py` 中替换 Scheduler 的 placeholder runner。
- [FACT]（Code Review P1）Runner 会检查每次下载返回的 `DownloadResult`，若存在 `FAILED` 则抛错以确保 Scheduler 将 run 标记为 `Failed`（见 `src/backend/pipeline/account_runner.py`；回归测试见 `tests/pipeline/test_account_runner.py`）。
- [TEST] 已新增样本回归：`tests/scraper/test_user_media_parser.py`（基于 `artifacts/samples/x_timeline_user_media_sample.json` 断言视频变体选择与 MIN_SHORT_SIDE 过滤计数）。

## 3) 已落实的"契约/行为"（实现交付）

- [CONTRACT] 分页（cursor 等价机制）：通过 `twscrape` 的 `user_media_raw` 逐页迭代；解析器可从每页响应抽取 `Bottom` cursor 值（用于未来 Continue/续跑游标落盘）。
- [CONTRACT] 过滤输入映射：`account_config` 支持前端 camelCase（`startDate/endDate/mediaType/sourceTypes/minShortSide/includeQuoteMediaInReply`）并转换为 `FilterConfig`（snake_case + 枚举值）后调用 `apply_filters()`。
- [CONTRACT] 结果稳定性：抓取页内与跨页 tweets 都做“按 created_at 降序 + tweet_id”确定性排序；Filter Engine 输出 DownloadIntent 已做确定性排序；Runner 保持该顺序进行下载（避免重排导致 first-wins 语义漂移）。
- [CONTRACT] MIN_SHORT_SIDE：对具备 width/height 的媒体做前置过滤，被过滤媒体不会进入下载意图，因此不会落盘（仅计入 `filtered_counts["min_short_side"]`）；无尺寸信息的媒体会被保留并标记 `needs_post_min_short_side_check`（后续任务统一完善）。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] Scheduler 已开始使用真实 Runner（`create_account_runner()`），运行前置条件为：本机安装 `twscrape` 依赖 + 设置有效 `auth_token/ct0`（由 Global Settings 落盘到 `data/config.json`）。
- [IMPACT] 后续 `T-20260113-act-010-*` 可在 `run_account_pipeline()` 内补齐“统计口径与落盘 run report”的增量更新（当前只做下载落盘与去重）。
- [IMPACT] 后续 `T-20260113-act-011-*` 可在 `TwscrapeMediaScraper` 与 `_download_bytes_with_retries` 处接入可配置节流/退避/代理策略。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 下载实现为同步 `urllib`，通过 `asyncio.to_thread` 规避阻塞事件循环；取消信号可能在“单个大文件下载进行中”时延迟生效。
- [TODO] 对 `needs_post_min_short_side_check` 的媒体补齐“下载后判定并删除/统计”的完整策略与实现（图片可用解析头或引入图像库；视频需另行方案/工具链）。

## 6) Code Review 修复

- [REVIEW-FIX] **P1: Propagate min_short_side post-check flags to downloader**
  - **问题**：Filter Engine 的下载意图包含 `width/height/needs_post_min_short_side_check`，但 Runner 重新构建 `MediaIntent` 时未透传，导致后续无法对“无尺寸信息媒体”进行下载后复核。
  - **修复**：Runner 的 `_to_media_intent()` 已完整透传 `width/height/needs_post_min_short_side_check` 到 `MediaIntent`（见 `src/backend/pipeline/account_runner.py`），为后续下载后 MIN_SHORT_SIDE 复核提供必要信息。
  - **测试**：已补充映射回归测试 `tests/pipeline/test_account_runner.py`（断言字段透传）。

- [REVIEW-FIX] **P1: Pipeline reports success despite download failures**
  - **问题**：`run_account_pipeline()` 未处理 `MediaDownloader.download()` 返回的 `DownloadResult`，即使全部失败也会被 Scheduler 视为成功完成（状态 Done）。
  - **修复**：Runner 收集所有 `DownloadResult` 并在存在任一 `FAILED` 时抛出异常，使 Scheduler 将 run 标记为 `Failed` 并记录错误信息（见 `src/backend/pipeline/account_runner.py`）。
  - **测试**：已补充失败传播回归测试 `tests/pipeline/test_account_runner.py`（断言存在失败时会抛错）。
