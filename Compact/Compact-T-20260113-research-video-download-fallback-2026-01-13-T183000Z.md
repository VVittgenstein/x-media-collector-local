# Compact — T-20260113-research-video-download-fallback

- generated_at_utc: 2026-01-13T18:30:00Z
- subtask_type: research
- record_status: done

## 1) Scope（对齐范围）

- 目标：基于 Spike 样本分析视频字段形态，确认 ffmpeg 作为必选依赖的决策，并定义视频下载失败时的产品层行为（计数与错误呈现）。
- 非目标：不在本 Subtask 内实现视频下载功能（后续 `T-20260113-act-009-scrape-and-apply-filters` 落地集成）。

## 2) 已确认事实（Repo 落地 + 分析结论）

- [FACT] `record.json` 中 `T-20260113-research-video-download-fallback` 已更新为 `status: done`，`updated_at: 2026-01-13T18:30:00Z`，`owner: codex`。
- [FACT] 已新增 ADR 文档：`docs/adr/0006-video-download-fallback.md`（视频下载策略决策记录）。
- [FACT] 已分析 `artifacts/samples/x_timeline_user_media_sample.json` 中的视频字段结构。

## 3) 视频字段形态分析（基于 Spike 样本）

### 视频结构

视频媒体位于 `extended_entities.media[]`，`type: "video"`，包含：

- `original_info.width/height`：原始分辨率（可用于 MIN_SHORT_SIDE 前置过滤）
- `video_info.duration_millis`：视频时长
- `video_info.variants[]`：可用的视频格式变体

### 格式变体（variants）

| content_type | 说明 | 下载方式 | 样本观察 |
|--------------|------|---------|---------|
| `application/x-mpegURL` | HLS 流媒体 (m3u8) | 需要 ffmpeg | 每个视频都有 |
| `video/mp4` | 直链 MP4 | 直接 HTTP | 多码率可选 |

### 样本中的 MP4 码率分布

- 256kbps (480x270)
- 832kbps (640x360)
- 2176kbps (1280x720)

### 占比观察

- 所有视频均同时提供 m3u8 和多码率 MP4 两种形态
- MP4 直链最高码率通常为 720p，部分可能有 1080p
- m3u8 可能提供更高质量版本

## 4) 下载策略（已拍板）

- [DECISION] **ffmpeg 作为必选依赖**，一开始就引入，不做降级跳过。
- [CONTRACT] 优先使用最高 bitrate 的 MP4 直链（标准 HTTP 下载）。
- [CONTRACT] 若无可用 MP4，降级使用 ffmpeg 下载 m3u8 并转码为 mp4。
- [CONTRACT] 启动时检测 ffmpeg 可用性，未安装则阻止启动并提示安装指引。

## 5) 视频下载失败的产品行为

### 错误计数字段

| 字段 | 说明 |
|------|------|
| `videos_downloaded` | 成功下载并落盘的视频数 |
| `videos_failed` | 下载失败的视频数 |
| `videos_skipped_filter` | 被 MIN_SHORT_SIDE 等规则过滤的视频数 |

### 错误类型与呈现

| 错误类型 | 原因 | UI 呈现 |
|---------|------|---------|
| `NETWORK_ERROR` | HTTP 请求失败、超时 | "视频下载失败：网络错误" |
| `FFMPEG_ERROR` | ffmpeg 执行/转码失败 | "视频下载失败：ffmpeg 处理错误" |
| `NO_VARIANT` | 无可用的视频变体 | "视频下载失败：无可用格式" |
| `INCOMPLETE` | 下载不完整、校验失败 | "视频下载失败：文件不完整" |

### 失败处理规则

- [CONTRACT] 单个视频失败不中断整体任务
- [CONTRACT] 失败视频记录到任务日志（tweet_id、错误类型、错误详情）
- [CONTRACT] 任务完成后 UI 显示 `videos_failed` 计数，可点击查看失败详情
- [CONTRACT] 网络错误自动重试 3 次（指数退避），ffmpeg 错误不自动重试

## 6) 显式限制 / 风险 / 未完成 TODO

- [TODO] 实现视频下载功能（归入 `T-20260113-act-009-scrape-and-apply-filters`）
- [TODO] 实现 ffmpeg 启动检测与安装指引 UI
- [TODO] 实现视频下载失败的详情展示 UI
- [RISK] 部分视频可能仅提供受 DRM 保护的流，ffmpeg 也无法处理（需观察实际占比）

## 7) 相关决策引用

- [D-20260113-ffmpeg-required] 项目一开始就引入 ffmpeg 作为必选依赖
- [DEP-006] ffmpeg 已加入 `external_dependencies`，status: approved
