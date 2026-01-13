# Compact — T-20260113-build-filter-engine

- generated_at_utc: 2026-01-13T11:46:33Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：实现“过滤与分类规则”的纯逻辑层（Filter Engine），将日期/媒体类型/来源类型/Reply+Quote 开关/MIN_SHORT_SIDE 固化为可测试的纯函数，并用 JSON fixtures 做回归。
- 非目标：本 Subtask 不实现真实抓取/分页/下载落盘；仅交付可复用的稳定业务逻辑与回归用例。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-build-filter-engine` 已更新为 `status: done`，`updated_at: 2026-01-13T11:46:33Z`，`owner: codex`。
- [FACT] 已新增 Filter Engine 模块：`src/shared/filter_engine/__init__.py`、`src/shared/filter_engine/models.py`、`src/shared/filter_engine/classifier.py`、`src/shared/filter_engine/engine.py`。
- [FACT] 已新增 JSON fixtures（>=5）：`artifacts/fixtures/tweets/*.json`（覆盖 Reply/Quote 分类、日期闭区间、媒体类型、来源类型、Reply+Quote 开关、MIN_SHORT_SIDE）。
- [TEST] Fixture 回归通过：`python3 -m unittest discover -s tests -v` → `OK`（`tests/filter_engine/test_fixtures.py`）。

## 3) 已落实的"契约/行为"（实现交付）

- [CONTRACT] 推文分类（`classify_tweet_source_type`）：
  - Reply 优先归 Reply（即使同时 Quote）
  - Quote 仅指“非 Reply 且存在引用关系（quoted_tweet）”的推文
- [CONTRACT] 筛选规则（`apply_filters`）：
  - 日期：按 `created_at` 的日期做闭区间（start/end 任意可为空）
  - 媒体类型：`images/videos/both` 逐媒体过滤；同推文含图+视频时，`both` 会产出两类下载意图
  - 来源类型：`Original/Reply/Retweet/Quote` 多选，按分类结果过滤
  - Reply+Quote 开关：仅对 Reply+Quote 生效；ON 时额外纳入被引用推文的媒体（并标记 `origin: quoted`）
  - MIN_SHORT_SIDE：有 `width/height` 则前置过滤并计入 `filtered_counts["min_short_side"]`；无尺寸信息则保留并标记 `needs_post_min_short_side_check`
- [CONTRACT] 输出稳定性：DownloadIntent 结果按 `trigger_created_at` 等 key 进行确定性排序，保证同输入下可复现。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 抓取层在对接 `T-20260113-act-009-scrape-and-apply-filters` 时，需组装 `Tweet`（含 `is_reply/is_retweet/quoted_tweet/media`）并调用 `apply_filters()`，将输出的 DownloadIntent 交给 Downloader。
- [IMPACT] Downloader 若要完整落实 MIN_SHORT_SIDE 的“无元数据降级”，需在下载后对 `needs_post_min_short_side_check` 的媒体做尺寸判断与删除/统计（后续任务对齐）。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前只提供纯逻辑与回归 fixtures；未接入真实抓取库字段映射（需要在 Scrape Layer 实现时做适配）。
- [TODO] “无 width/height 时下载后删除”的完整策略/文档说明待 `T-20260113-design-min-short-side-filter-approach` / `T-20260113-act-009-scrape-and-apply-filters` 统一落地。

