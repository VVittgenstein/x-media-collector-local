# Compact — T-20260113-design-min-short-side-filter-approach

- generated_at_utc: 2026-01-13T20:50:18Z
- subtask_type: design
- record_status: done

## 1) Scope（对齐范围）

- 目标：基于 Spike 真实 JSON 样本确认图片/视频是否稳定提供 `width/height`（或可推导），并拍板 MIN_SHORT_SIDE 的自适应策略（有元数据则前置过滤，否则下载后复核删除）；补充用户可理解的提示文案；产出 ADR 文档供后续实现任务对齐。
- 非目标：本 Subtask 不交付 Downloader 侧“下载后复核删除”的实现代码与统计/展示实现（后续 build 任务落地）。

## 2) 已确认事实（Repo 落地 + 分析结论）

- [FACT] `record.json` 中 `T-20260113-design-min-short-side-filter-approach` 已更新为 `status: done`，并写入 `updated_at: 2026-01-13T20:46:53Z`、`owner: codex`。
- [FACT] 已新增 ADR 文档：`docs/adr/0005-min-short-side-metadata.md`（记录证据、策略与 UI 文案）。
- [FACT] 基于 `artifacts/samples/x_timeline_user_media_sample.json`：图片（photo）与视频（video）在样本中均提供 `original_info.width/height`，可用于前置过滤；但仍需保留“无尺寸信息”的兜底路径以应对解析失败/字段缺失/未来变更。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → 预期 OK。

## 3) 已落实的“契约/决策”（文档定义；待后续实现落地）

- [CONTRACT] 自适应策略（ADR-0005）：当 `width/height` 为可解析正整数时，按 `min(width,height) < MIN_SHORT_SIDE` 在下载前过滤（不生成下载意图，计入 `filtered_counts["min_short_side"]`）。
- [CONTRACT] 无元数据兜底（ADR-0005）：当缺失 `width/height` 时，不做前置过滤，但标记 `needs_post_min_short_side_check=true`；下载落盘后获取实际分辨率并复核，低于阈值则删除使其不进入最终结果，并计入过滤统计。
- [CONTRACT] UI/文档提示文案（ADR-0005 推荐）：提示用户“无分辨率元数据时可能需要先下载后判断并丢弃，因此会额外消耗带宽”。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] Scrape Layer 需尽量提供 `width/height`（样本中来自 `original_info`）；缺失时透传为 `null`，以触发兜底路径。
- [IMPACT] Filter Engine 需在无尺寸信息时输出 `needs_post_min_short_side_check`（已在引擎契约中定义，后续实现需保持一致）。
- [IMPACT] Downloader/Runner 落地时需实现：下载后获取分辨率（图片/视频分别处理）、删除低于阈值文件、并将该类删除计入过滤统计（避免“落盘后又留在目录里”违背 FR-09）。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前仅完成 ADR 文档输出与记录更新；下载后复核删除属于后续实现项。
- [RISK] 无元数据时会产生带宽浪费（下载后丢弃），需要 UI/文档明确告知用户以建立预期。
- [TODO] 后续实现中需补齐统计口径：被复核删除的媒体如何计入（建议统一落到 `*_skipped_filter` / `filtered_counts["min_short_side"]`），并在 UI 展示。
