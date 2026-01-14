# x-media-collector-local

一个基于 WebUI 的 X.com 媒体批量下载工具（本地部署），支持会话认证、高级筛选与去重。

A local WebUI tool to batch download images and videos from X.com based on user handles, featuring session-based authentication and advanced filtering.

---

## 风险提示 / Risk Warning

> **请务必阅读以下内容：**
>
> - 本工具通过**浏览器会话模拟**访问 X 平台的非公开接口，**这可能违反平台服务条款**。
> - 使用本工具可能导致您的账号被**限流、临时锁定或永久封禁**。
> - **强烈建议使用非主要账号**进行操作，避免重要账号受到影响。
> - 本工具仅供学习研究和个人数据备份使用，请自行承担使用风险。

---

## 快速开始 / Quick Start

### 1. 系统要求

- Python 3.10+
- ffmpeg（必选依赖，用于处理视频下载）

### 2. 安装 ffmpeg

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

### 3. 一键启动

```bash
# 1. 克隆仓库
git clone <repository-url>
cd x-media-collector-local

# 2. 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动服务
uvicorn src.backend.app:app --host 127.0.0.1 --port 8000

# 5. 打开浏览器访问
# http://127.0.0.1:8000
```

启动后，在浏览器中打开 `http://127.0.0.1:8000` 即可使用 WebUI。

---

## 凭证配置 / Credentials Setup

本工具需要您手动提供 X 平台的登录凭证（Cookies）。**工具不会自动获取您的凭证**。

### 如何获取凭证

1. 在浏览器中登录 [x.com](https://x.com)
2. 按 `F12` 打开开发者工具
3. 切换到 **Application**（应用程序）→ **Cookies** → **https://x.com**
4. 找到以下两个 Cookie 并复制其 **Value**：

| Cookie 名称 | 格式说明 |
|------------|---------|
| `auth_token` | 约 40 字符的十六进制字符串 |
| `ct0` | 约 32 字符的十六进制字符串 |

5. 在 WebUI 的「设置」页面粘贴这些值并保存

### 凭证安全说明

- 凭证保存在本地 `data/config.json` 文件中，**不会上传到任何服务器**。
- 保存后的凭证在 UI 中仅显示"已设置"，**不会回显明文**。
- 凭证不会出现在任何日志或错误报告中。
- 如需更换凭证，请在设置页面点击"清除并重新输入"。

### 凭证失效处理

凭证可能因以下原因失效：
- X 平台主动使会话过期（通常 30-90 天）
- 您在浏览器中退出登录
- 账号密码被修改

遇到 `401 Unauthorized` 错误时，请重新获取并更新凭证。

---

## 使用建议 / Best Practices

### 降低风控风险

| 建议 | 说明 |
|-----|------|
| **使用非主账号** | 避免重要账号受到封禁影响 |
| **控制采集频率** | 默认限流参数已较为保守，如遇 429 错误请进一步降频 |
| **避免大规模采集** | 单次任务采集量建议控制在合理范围内 |
| **使用代理（可选）** | 在设置中配置代理可分散请求来源 |

### 默认限流参数

- 请求间隔：1.5 秒 + 随机抖动（0-1 秒）
- 重试策略：遇到 429/5xx 自动指数退避重试（最多 3 次）
- 并发数：默认 3 个账号并行（可在设置中调整）

---

## 故障排查 / Troubleshooting

遇到抓取失败时，请按以下顺序排查：

### 1. 检查凭证

```
症状：401 Unauthorized 或 "认证失败"
原因：凭证无效、已过期或复制不完整
解决：重新从浏览器获取 auth_token 和 ct0 并更新
```

### 2. 降低频率

```
症状：429 Too Many Requests 或频繁超时
原因：请求过于频繁触发平台限流
解决：在设置中增加请求间隔（min_interval_s），等待 5-10 分钟后重试
```

### 3. 启用代理

```
症状：持续 403 或连接被重置
原因：IP 可能被临时封禁
解决：在设置中配置 HTTP/SOCKS 代理，分散请求来源
```

### 4. 升级抓取库

```
症状：解析错误、字段缺失或 "scraper error"
原因：X 平台接口可能已更新，当前抓取库版本不兼容
解决：升级 twscrape 到最新版本

pip install --upgrade twscrape
```

更多排障信息请参阅 [docs/ops/troubleshooting.md](docs/ops/troubleshooting.md)。

---

## 功能特性 / Features

- **多账号并发**：支持同时采集多个 X 账号的媒体（默认并发 3）
- **FIFO 队列**：任务按先进先出顺序执行，可随时取消排队中的任务
- **高级筛选**：按日期范围、媒体类型（图片/视频）、来源类型（原创/转发/回复/引用）过滤
- **分辨率过滤**：通过 MIN_SHORT_SIDE 参数过滤低分辨率图片
- **智能去重**：基于内容 hash 去重，避免重复下载相同文件
- **规范命名**：文件名包含 tweetId、日期、hash，便于追溯
- **断点续采**：支持 Continue 继续之前中断的任务
- **配置复制**：可在账号间快速复制筛选配置

---

## 目录结构 / Directory Structure

下载的媒体文件按以下结构组织：

```
<download_root>/
└── <handle>/
    ├── images/
    │   └── <tweetId>_<YYYY-MM-DD>_<hash6>.jpg
    └── videos/
        └── <tweetId>_<YYYY-MM-DD>_<hash6>.mp4
```

---

## 技术栈 / Tech Stack

- **后端**：Python + FastAPI + uvicorn
- **前端**：原生 HTML/CSS/JavaScript（无框架）
- **抓取**：twscrape（X GraphQL 接口封装）
- **视频处理**：ffmpeg（处理 m3u8 流媒体）

---

## 许可 / License

本项目仅供学习研究使用。使用本工具访问第三方平台时，请遵守相关平台的服务条款。

---

## 问题反馈 / Issues

如遇到问题，请先查阅 [故障排查指南](docs/ops/troubleshooting.md)。
