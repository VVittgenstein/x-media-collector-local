# ADR-0006：视频下载策略 - ffmpeg 作为必选依赖

- Status: **Accepted**
- Date: 2026-01-13

## 背景 / Context

项目需要下载 X 平台上的视频媒体。通过 Spike 实验（T-20260113-act-002-spike-cookie-scrape）获取的 JSON 样本分析，视频字段存在多种形态，需要确定下载策略与依赖选择。

### 视频字段形态分析

基于 `artifacts/samples/x_timeline_user_media_sample.json` 样本，视频媒体结构如下：

```json
{
  "type": "video",
  "media_url_https": "https://pbs.twimg.com/.../pu/img/xxx.jpg",  // 缩略图
  "original_info": {
    "width": 1920,
    "height": 1080
  },
  "video_info": {
    "duration_millis": 65199,
    "variants": [
      {
        "content_type": "application/x-mpegURL",
        "url": "https://video.twimg.com/.../pl/xxx.m3u8?tag=12&container=cmaf"
      },
      {
        "content_type": "video/mp4",
        "url": "https://video.twimg.com/.../vid/avc1/480x270/xxx.mp4?tag=12",
        "bitrate": 256000
      },
      {
        "content_type": "video/mp4",
        "url": "https://video.twimg.com/.../vid/avc1/640x360/xxx.mp4?tag=12",
        "bitrate": 832000
      },
      {
        "content_type": "video/mp4",
        "url": "https://video.twimg.com/.../vid/avc1/1280x720/xxx.mp4?tag=12",
        "bitrate": 2176000
      }
    ]
  }
}
```

**观察到的视频形态**：

| 形态 | content_type | 说明 | 下载方式 |
|------|-------------|------|---------|
| m3u8 流媒体 | `application/x-mpegURL` | HLS 分片流，通常为最高质量 | 需要 ffmpeg |
| 直链 MP4 (低) | `video/mp4` | 480x270, ~256kbps | 直接 HTTP |
| 直链 MP4 (中) | `video/mp4` | 640x360, ~832kbps | 直接 HTTP |
| 直链 MP4 (高) | `video/mp4` | 1280x720, ~2176kbps | 直接 HTTP |

**占比观察**：
- 所有视频均同时提供 m3u8 和多码率 MP4 两种形态
- MP4 直链的最高码率通常为 720p（部分可能有 1080p）
- m3u8 格式可能提供更高质量版本（取决于原始上传）

## 决策 / Decision

**一开始就引入 ffmpeg 作为必选依赖**，用于处理流媒体视频下载。

### 下载策略

1. **优先使用最高码率的 MP4 直链**
   - 遍历 `video_info.variants`，筛选 `content_type: "video/mp4"`
   - 按 `bitrate` 降序排序，选择最高码率
   - 使用标准 HTTP 下载

2. **若无可用 MP4，使用 ffmpeg 下载 m3u8**
   - 筛选 `content_type: "application/x-mpegURL"`
   - 调用 ffmpeg 进行流媒体下载并转码为 mp4

3. **ffmpeg 作为必选依赖**
   - 启动时检测 ffmpeg 可用性
   - 若未安装，在 UI 显示明确错误提示与安装指引
   - 不做"无 ffmpeg 时跳过视频"的降级逻辑

### 选择理由

- **功能完整性**：部分高质量视频可能仅提供 m3u8，没有 ffmpeg 会丢失这部分内容
- **本地工具定位**：用户本机安装 ffmpeg 是可接受的前置要求
- **简化逻辑**：不需要维护"有/无 ffmpeg"两套代码路径
- **未来扩展**：ffmpeg 还可用于视频完整性校验、格式转换等

## 视频下载失败的产品行为

当视频无法下载时，需要明确的计数与呈现策略：

### 错误计数

| 字段 | 说明 |
|------|------|
| `videos_downloaded` | 成功下载并落盘的视频数 |
| `videos_failed` | 下载失败的视频数（含网络错误、ffmpeg 错误等） |
| `videos_skipped_filter` | 被 MIN_SHORT_SIDE 等规则过滤的视频数 |

### 错误类型与呈现

| 错误类型 | 原因 | UI 呈现 |
|---------|------|---------|
| `NETWORK_ERROR` | HTTP 请求失败、超时 | "视频下载失败：网络错误" |
| `FFMPEG_ERROR` | ffmpeg 执行失败、转码错误 | "视频下载失败：ffmpeg 处理错误" |
| `NO_VARIANT` | 无可用的视频变体 | "视频下载失败：无可用格式" |
| `INCOMPLETE` | 下载不完整、校验失败 | "视频下载失败：文件不完整" |

### 失败处理流程

1. 单个视频失败不中断整体任务
2. 失败视频记录到任务日志，包含：tweet_id、错误类型、错误详情
3. 任务完成后，UI 显示 `videos_failed` 计数
4. 用户可点击查看失败详情（展示失败视频列表与原因）

### 重试策略

- 网络错误：自动重试 3 次，指数退避
- ffmpeg 错误：不自动重试（通常是格式问题，重试无意义）
- 用户可通过 Continue 重新尝试之前失败的视频

## 备选方案 / Alternatives Considered

1. **ffmpeg 作为可选依赖，无 ffmpeg 时仅下载 MP4**
   - 优点：降低安装门槛
   - 缺点：部分视频可能无法获取最高质量；需维护两套逻辑
   - **否决理由**：本地工具定位，ffmpeg 安装不是障碍；功能完整性优先

2. **仅下载 MP4，完全不使用 ffmpeg**
   - 优点：零外部依赖
   - 缺点：若某些视频仅提供 m3u8，将无法下载
   - **否决理由**：牺牲功能完整性

3. **内嵌 ffmpeg 二进制**
   - 优点：用户无需手动安装
   - 缺点：增加分发包体积（~100MB+）；跨平台复杂度高
   - **否决理由**：MVP 阶段不值得投入

## 影响 / Consequences

- **安装前置**：用户需先安装 ffmpeg（README 需提供各平台安装指引）
- **启动检查**：程序启动时检测 ffmpeg，未安装则阻止启动并提示
- **下载流程**：优先 MP4 直链，降级到 ffmpeg + m3u8
- **错误可见性**：视频下载失败有独立计数和详情展示

## ffmpeg 安装指引（README 需包含）

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg

# Windows (Scoop)
scoop install ffmpeg

# 验证安装
ffmpeg -version
```

## 相关决策

- [D-20260113-ffmpeg-required] 项目一开始就引入 ffmpeg 作为必选依赖
