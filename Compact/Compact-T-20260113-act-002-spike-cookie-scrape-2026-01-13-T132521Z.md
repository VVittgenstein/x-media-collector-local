# Compact — T-20260113-act-002-spike-cookie-scrape

- generated_at_utc: 2026-01-13T13:25:21Z
- subtask_type: research
- record_status: done

## 1) Scope（对齐范围）

- 目标：交付可运行的 Spike 脚本，用登录态 Cookie 访问 X 内部 GraphQL（UserMedia）抓取含媒体推文并下载落盘；同时沉淀可用于字段解析/测试的脱敏 JSON 响应样本与最小可复现日志。
- 非目标：不在本 Subtask 内把抓取能力接入 WebUI 的 Scheduler/Runner（后续 `T-20260113-act-009-scrape-and-apply-filters` 落地集成）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-002-spike-cookie-scrape` 已更新为 `status: done`，`updated_at: 2026-01-13T13:54:29Z`，`owner: codex`。
- [FACT] 已新增 Spike 脚本：`scripts/spike_scrape_sample.py`（twscrape + Cookie 登录态抓取 + 下载 + 脱敏日志/样本）。
- [FACT]（Code Review P2）已修复下载临时文件的 fd 泄露：`tempfile.mkstemp` 返回的 fd 在写入前已显式关闭（避免批量下载耗尽 fd）。
- [FACT]（Code Review P2）已修复持久化 `--accounts-db` 重跑的 username 冲突：同名 `--account-username` 存在时会更新 cookies/user-agent，避免唯一约束中断。
- [FACT] 已新增 3 份脱敏/裁剪后的 GraphQL JSON 响应样本（用于解析/测试夹具）：
  - `artifacts/samples/x_timeline_user_media_sample.json`（含 photo + video，包含 `original_info.width/height` 与 `video_info.variants`）
  - `artifacts/samples/x_timeline_user_by_login_sample.json`
  - `artifacts/samples/x_timeline_user_by_id_sample.json`
- [FACT] 已更新依赖：`requirements.txt` 增加 `twscrape>=0.17.0`。
- [FACT] 已增加忽略规则：`.gitignore`（避免 `data/config.json`、Spike 下载产物等误提交）。
- [TEST] 单测通过：`python3 -m unittest -q`
- [TEST] 脚本语法检查通过：`python3 -m py_compile scripts/spike_scrape_sample.py`
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"`

## 3) Spike 脚本能力（实现交付）

- [CONTRACT] 凭证输入对齐 ADR-0003：最小必填 `auth_token` + `ct0`，可选 `twid`；来源支持 CLI/env/`data/config.json`（WebUI 保存后生成）。
- [CONTRACT] 账号池可持久化复用：指定 `--accounts-db` 后，重复运行会复用/更新同名 `--account-username` 的 cookies/user-agent，避免 username 唯一约束导致启动失败。
- [CONTRACT] 抓取路径：通过 `twscrape` 调用 `user_by_login` → `user_media_raw`（GraphQL UserMedia），收集至少 N 条“含媒体”推文；可保存前 N 个原始响应样本（默认 3）。
- [CONTRACT] 下载样本：从推文媒体中提取图片/视频（视频选最高 bitrate 的 mp4 变体），落盘到 `artifacts/spike_downloads/<handle>/{images|videos}/`。
- [CONTRACT] 最小可复现日志（脱敏）：输出 `artifacts/samples/run_*_log.jsonl` 与 `artifacts/samples/run_*_report.json`，不记录 `auth_token/ct0` 明文。

## 4) 使用方法（需要用户提供有效登录态 Cookie）

- 方式 A（推荐）：先用 WebUI 保存凭证到 `data/config.json`，再运行：
  - `python3 scripts/spike_scrape_sample.py --handle <HANDLE> --limit 50`
- 方式 B：直接用参数传入（不会落盘到配置文件）：
  - `python3 scripts/spike_scrape_sample.py --handle <HANDLE> --auth-token '...' --ct0 '...' --limit 50`

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 本仓库内提交的 JSON 样本为“脱敏/裁剪后的响应片段”（用于字段解析与测试夹具）；不代表已在当前环境使用真实 Cookie 完成 24h 风控观察。
- [TODO] 真实 Spike 运行（需用户本机提供有效 Cookie）：观察 401/403/429 触发频率、退避策略是否需要调整，并用运行产出的 `run_*_report.json` 作为后续 `T-20260113-research-video-download-fallback` / `T-20260113-design-min-short-side-filter-approach` 的依据。
- [RISK] 使用真实账号 Cookies 调用内部接口存在触发风控/封禁风险；建议使用非主账号、控制频率、必要时使用代理；严禁分享 `data/config.json`。
