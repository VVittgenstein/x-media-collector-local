# ADR-0005：MIN_SHORT_SIDE 自适应过滤（有元数据则前置，否则下载后复核删除）

- Status: **Accepted**
- Date: 2026-01-13

## 背景 / Context

需求 FR-09 要求支持分辨率过滤：每账号可设置 `MIN_SHORT_SIDE`，当 `min(width, height) < MIN_SHORT_SIDE` 时视为低清媒体，**不进入最终下载结果**（不应落盘），仅计入过滤/跳过统计。

实现该规则的关键前提是：在“下载前”能否稳定拿到媒体的 `width/height`。如果上游 JSON 不稳定提供尺寸信息，则必须定义兜底策略，否则会出现：

- 过滤不生效（无法判断，导致低清内容被落盘）
- 或者只能“一律先下再删”（过滤可用但浪费带宽）

本 ADR 记录基于 Spike 样本对元数据可用性的确认，并拍板 MIN_SHORT_SIDE 的自适应策略。

## 事实 / Evidence（基于 Spike JSON 样本）

基于 `artifacts/samples/x_timeline_user_media_sample.json`：

### 图片（photo）

媒体位于 `legacy.extended_entities.media[]`，`type: "photo"`，样本中提供：

- `original_info.width/height`
- `media_url_https`（项目会升级为 `pbs.twimg.com` 的 `name=orig` 版本以尽量获取原图）

示例（节选）：

```json
{
  "type": "photo",
  "media_url_https": "https://pbs.twimg.com/media/XXX.jpg",
  "original_info": { "width": 4096, "height": 2304 }
}
```

### 视频（video）

媒体同样位于 `legacy.extended_entities.media[]`，`type: "video"`，样本中提供：

- `original_info.width/height`
- `video_info.variants[]`（包含 mp4 与 m3u8）

示例（节选）：

```json
{
  "type": "video",
  "original_info": { "width": 1920, "height": 1080 },
  "video_info": { "variants": [ { "content_type": "video/mp4", "url": "https://video.twimg.com/.../1280x720/...mp4" } ] }
}
```

结论：在该样本中，图片与视频均可通过 `original_info.width/height` 获取尺寸信息；但为应对上游字段缺失/异常（含 animated_gif、历史数据差异、解析失败、未来字段变更等），仍需保留“无尺寸信息”的降级路径。

## 决策 / Decision

采用 **自适应策略**：

1) **有可靠 `width/height`：下载前过滤**
- 判定“可靠”的标准：`width` 与 `height` 均为可解析的正整数。
- 在 Filter Engine 阶段执行：
  - 若 `min(width, height) < MIN_SHORT_SIDE` → 直接过滤掉，不生成下载意图，`filtered_counts["min_short_side"] += 1`。

2) **无 `width/height`：允许进入下载，但标记为需要下载后复核**
- 在 Filter Engine 阶段执行：
  - 不做前置过滤（避免误杀），但在下载意图上标记 `needs_post_min_short_side_check = true`。
- 在 Downloader 阶段执行（后续实现任务落地）：
  - 下载落盘后获取实际分辨率（图片/视频分别处理）
  - 若 `min(width, height) < MIN_SHORT_SIDE` → 删除该文件，使其不进入最终结果，并计入过滤统计

## 下载后复核（实现约束）

为保证“删除”安全且可解释，落地时必须遵守：

- 仅对 `needs_post_min_short_side_check=true` 的媒体做复核，避免重复开销
- **先确保文件写入成功**（原子落盘）后再进行复核与删除
- 若无法解析分辨率（格式异常/工具缺失）：
  - 默认策略：保留文件并记录 warning（避免误删）
  - 同时在统计/日志中可见该降级（便于用户理解为什么过滤可能不完全）

建议的尺寸获取方式（不限制具体实现）：

- 图片：读取文件头解析宽高（或引入轻量依赖如 Pillow/imagesize）
- 视频：使用 `ffprobe` 获取 `width/height`（项目已将 ffmpeg 作为必选依赖，见 ADR-0006）

## UI/文档文案（用户可理解）

当用户配置 `MIN_SHORT_SIDE` 时，UI/文档应提示（推荐文案）：

> 低于此值的媒体会被过滤；当无法提前获取分辨率信息时，可能需要先下载后判断并丢弃，因此会额外消耗带宽。

## 备选方案 / Alternatives Considered

1) **一律下载后判断**
- 优点：规则始终可用且最准确
- 缺点：带宽浪费显著，尤其在阈值较高时
- 结论：否决，作为无元数据时的兜底即可

2) **无元数据时直接放行（不复核）**
- 优点：实现最简单、无带宽浪费
- 缺点：过滤规则在部分媒体上失效，违背 FR-09 的“最终结果不落盘”语义
- 结论：否决

## 影响 / Consequences

- 过滤体验更一致：有无元数据都能尽量满足 FR-09 语义
- 性能/带宽更可控：大多数情况下（有元数据）前置过滤，不浪费下载
- 需要用户预期管理：无元数据时可能产生带宽浪费（通过 UI 文案解释）

## 相关决策

- [D-20260113-min-short-side-adaptive] MIN_SHORT_SIDE 过滤采用自适应策略：JSON 有 width/height 则下载前过滤，否则先下载再判断删除。
