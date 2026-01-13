# Compact — T-20260113-act-010-stats-open-folder

- generated_at_utc: 2026-01-13T21:16:02Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：在账号行 UI 中展示可验收的统计指标（images_downloaded / videos_downloaded / skipped_duplicate / runtime / avg_speed）与输出路径，并提供“打开文件夹”按钮。
- 目标：统计口径严格实现：runtime 从进入 Running 开始计时（不包含 Queued 等待），avg_speed=(images_downloaded+videos_downloaded+skipped_duplicate)/runtime（runtime>0）。
- 非目标：不实现媒体预览墙；不做复杂的历史 run 聚合报表（仅展示当前/最近一次运行的统计即可）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-010-stats-open-folder` 已更新为 `status: done`，`updated_at: 2026-01-13T21:16:02Z`，`owner: codex`。
- [FACT] 后端补齐运行期统计基础设施：
  - `src/backend/scheduler/models.py`：Run 增加 `started_at/finished_at/download_stats`，并持久化到 `data/runs/<run_id>.json`。
  - `src/backend/scheduler/scheduler.py`：在进入 Running 时写入 `started_at`，结束时写入 `finished_at`；`/api/scheduler/state` 的 handle 状态返回 `runtime_s/avg_speed` 与下载计数。
  - `src/backend/pipeline/account_runner.py`：每次 download 后把 `MediaDownloader.stats` 写回 `run.download_stats`，用于 UI 轮询展示。
- [FACT] 后端新增打开文件夹能力：
  - `src/backend/os/open_folder.py`：跨平台打开目录（Windows/macOS/Linux；WSL 优先走 `explorer.exe` + `wslpath -w`）。
  - `src/backend/os/api.py`：`POST /api/os/open-folder`，目录不存在/非目录时返回明确错误。
  - `src/backend/app.py`：挂载 `/api/os/*` router。
- [FACT] 前端新增账号行统计展示：
  - `src/frontend/components/AccountRowStats.js` + `src/frontend/components/AccountRowStats.css`：展示统计与输出路径，点击“Open Folder”触发后端打开目录并显示错误提示。
  - `src/frontend/app.js`：账号行绑定 stats 组件，并在轮询 `/api/scheduler/state` 时同步刷新。
  - `src/frontend/index.html`：补充脚本与样式引用。
- [TEST] 全量 unittest：`python3 -m unittest` → OK（新增：`tests/stats/test_metrics.py`、`tests/scheduler/test_stats_runtime_speed.py`）。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → OK。

## 3) 已落实的关键行为（验收对齐）

- [CONTRACT] runtime：Queued 时 `runtime_s=0`；进入 Running 后开始累积；Done/Failed/Cancelled 后固定为 `finished_at-started_at`（不含排队等待）。
- [CONTRACT] avg_speed：严格按 `(images_downloaded+videos_downloaded+skipped_duplicate)/runtime_s` 计算（`runtime_s<=0` 时为 0）。
- [CONTRACT] 打开文件夹：若目录不存在/已删除，后端返回 404 且前端显示明确错误，不静默失败。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 前端依赖 `/api/scheduler/state` 的新增字段：`images_downloaded/videos_downloaded/skipped_duplicate/runtime_s/avg_speed`；后续若切换 SSE 推送也需保持字段语义一致。
- [IMPACT] 统计口径依赖 Scheduler 记录的 `started_at/finished_at`（进入 Running 时写入）；若未来 Runner 改为并行下载，`download_stats` 更新频率可调整但口径不变。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前 UI 仍为 800ms 轮询刷新统计；若未来切换 SSE，建议用事件流推增量 stats 以降低开销。
- [RISK] “打开文件夹”依赖系统命令（WSL/桌面环境差异）；已提供明确错误返回与前端提示，但不同发行版的 opener 可用性仍可能影响体验。

