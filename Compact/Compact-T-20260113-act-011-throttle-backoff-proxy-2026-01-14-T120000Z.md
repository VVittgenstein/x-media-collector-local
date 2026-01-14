# Compact — T-20260113-act-011-throttle-backoff-proxy

- generated_at_utc: 2026-01-14T12:00:00Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：实现请求限流（Throttle）模块，支持可配置的最小请求间隔（min_interval_s，默认 1.5s）与随机抖动（jitter_max_s，默认 1.0s）。
- 目标：实现指数退避重试（Retry）模块，对 429/5xx 错误自动重试（max_retries 默认 3，base_delay 默认 2s，max_delay 默认 60s）。
- 目标：实现可选代理配置（Proxy），支持 http/https/socks4/socks5 协议；开启后抓取/下载请求统一走代理。
- 目标：在 GlobalSettings UI 中提供配置入口，允许用户调整上述参数并持久化。
- 非目标：不实现自动代理切换/轮换；不做代理健康检查；不做 IP 池管理。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-011-throttle-backoff-proxy` 已更新为 `status: done`，`updated_at: 2026-01-14T12:00:00Z`，`owner: codex`。
- [FACT] 后端新增 `src/backend/net/` 模块：
  - `throttle.py`：ThrottleConfig（min_interval_s/jitter_max_s/enabled）+ Throttle 类（wait/wait_async 同步/异步阻塞）。
  - `retry.py`：RetryConfig（max_retries/base_delay_s/max_delay_s/jitter_factor/retryable_status_codes/enabled）+ with_retry/with_retry_async 函数 + RetryableError 异常。
  - `proxy.py`：ProxyConfig（enabled/url）+ validate 方法 + get_urllib_proxy_handlers 辅助函数。
- [FACT] 后端 `src/backend/settings/models.py` 扩展 GlobalSettings：新增 throttle/retry/proxy 字段及 get_throttle/get_retry/get_proxy 方法。
- [FACT] 后端 `src/backend/settings/api.py` 新增 API 端点：
  - `POST /api/settings/throttle`：保存 Throttle 配置。
  - `POST /api/settings/retry`：保存 Retry 配置。
  - `POST /api/settings/proxy`：保存 Proxy 配置（含 URL 校验）。
  - `DELETE /api/settings/proxy`：清除 Proxy 配置。
- [FACT] 后端 `src/backend/pipeline/account_runner.py` 集成：
  - `_make_download_func`：创建带 throttle+retry+proxy 的下载函数。
  - `run_account_pipeline`：从 settings 读取配置并应用到 downloader（throttle+retry+proxy）和 scraper（proxy）。
- [FACT] 前端 `src/frontend/settings/GlobalSettings.js` 扩展：
  - 新增 Throttle/Retry/Proxy 三个设置块。
  - 提供 enabled 开关、参数输入、保存/清除按钮。
- [FACT] 前端 `src/frontend/settings/GlobalSettings.css` 新增样式：`.settings-section-title`、`.checkbox-label`。
- [TEST] 全量 unittest：`python3 -m unittest discover -s tests` → 134 tests OK。
- [TEST] 新增 `tests/net/` 目录：
  - `test_throttle.py`：11 个测试覆盖 ThrottleConfig 序列化、Throttle wait/async/disabled/reset。
  - `test_retry.py`：17 个测试覆盖 RetryConfig 序列化、exponential backoff、retry exhausted、disabled、callback。
  - `test_proxy.py`：21 个测试覆盖 ProxyConfig validation、urllib handlers。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → OK。

## 3) 已落实的关键行为（验收对齐）

- [CONTRACT] Throttle 默认值保守（1.5s min_interval + 1.0s jitter），首次请求仅 jitter，后续请求强制 min_interval+jitter。
- [CONTRACT] Retry 对 429/500/502/503/504 自动重试，延迟按指数增长（2^attempt * base_delay），上限 max_delay，含 25% jitter。
- [CONTRACT] Proxy URL 必须包含 scheme（http/https/socks4/socks5），否则验证失败返回 400。
- [CONTRACT] 所有配置持久化到 `data/config.json`，版本号升至 2。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] `GET /api/settings` 返回新增字段：throttle（min_interval_s/jitter_max_s/enabled）、retry（max_retries/base_delay_s/max_delay_s/enabled）、proxy（enabled/url_configured）。
- [IMPACT] account_runner 下载函数签名变更：不再直接使用 `_download_bytes_with_retries`，改用 `_make_download_func` 生成带配置的函数（保留旧函数供兼容）。
- [IMPACT] TwscrapeMediaScraper 已支持 proxy 参数，现由 pipeline 从 settings 注入。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] Proxy URL 在保存后不回显（仅显示 url_configured 布尔值），需用户重新输入才能修改。
- [LIMIT] 当前仅支持单一代理 URL；不支持代理列表/轮换。
- [RISK] SOCKS 代理需要系统支持（PySocks 或系统级）；urllib 原生不支持 SOCKS，twscrape 可能需要额外配置。
- [TODO] 具体限流/重试参数可根据实际运行中的 429 频率进一步调优。

## Code Review - T-20260113-act-011-throttle-backoff-proxy - 2026-01-14T12:30:00Z

---review-start---
[P2] Throttle skipped on retry attempts
Downloader wraps each URL fetch with throttle before the first attempt, but retry attempts inside `with_retry` skip throttling. If a user sets `min_interval_s` higher than the retry backoff (e.g., 5s vs base_delay 0.5s), retries will fire faster than the configured spacing, undermining the rate-limit guarantees. Throttle should apply to every attempt, not just the first.
---review-end---

## 6) Code Review Fixes

- **[P2] Throttle skipped on retry attempts** — Fixed at 2026-01-14T13:00:00Z
  - 问题：`_make_download_func` 中 `throttle.wait()` 在 `with_retry` 之前调用，导致重试时跳过限流。
  - 修复：将 `throttle.wait()` 移入 `attempt_download()` 内部，确保每次尝试（含重试）都执行限流等待。
  - 文件变更：`src/backend/pipeline/account_runner.py:105-110`
