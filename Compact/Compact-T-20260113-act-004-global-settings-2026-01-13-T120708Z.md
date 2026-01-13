# Compact — T-20260113-act-004-global-settings

- generated_at_utc: 2026-01-13T12:07:08Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：交付可用的全局设置能力（凭证输入与保存、Download Root 校验与保存、Max Concurrent 默认 3 且可修改），并在 UI 层对“未配置凭证”进行 Start/Continue 阻止提示。
- 非目标：不交付完整的 Scheduler/Runner 与实际下载流程（后续任务实现）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-004-global-settings` 已更新为 `status: done`，`updated_at: 2026-01-13T12:07:08Z`，`owner: codex`。
- [FACT] 已新增后端全局设置存储与 API：
  - `src/backend/settings/models.py`（Settings/Credentials 数据模型）
  - `src/backend/settings/store.py`（`data/config.json` 持久化；原子写入）
  - `src/backend/settings/api.py`（`/api/settings/*` 读写端点；不回传明文凭证）
  - `src/backend/scheduler/config.py`（`max_concurrent` 配置容器，供后续 Scheduler 读取）
  - `src/backend/app.py`（FastAPI app：挂载 API + 托管静态前端）
- [FACT] 已新增前端全局设置页与最小 Accounts 骨架用于验证联动：
  - `src/frontend/index.html`、`src/frontend/app.js`、`src/frontend/app.css`
  - `src/frontend/settings/GlobalSettings.js`、`src/frontend/settings/GlobalSettings.css`
- [TEST] 单测通过：`python3 -m unittest -q`
- [TEST] Python 语法检查通过：`python3 -m py_compile src/backend/app.py src/backend/settings/api.py`
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"`

## 3) 已落实的关键行为（实现交付）

- [CONTRACT] 凭证输入与保存：
  - UI 分字段输入 `auth_token`、`ct0`（必填）、`twid`（可选）
  - 保存后 UI 仅展示“已设置/未设置”，不回显明文；后端 `GET /api/settings` 仅返回字段是否已设置的状态
  - 凭证落盘到 `data/config.json`（本地明文存储，符合 ADR-0003 决策）
- [CONTRACT] 未配置凭证时阻止启动：
  - Accounts 最小骨架中，所有行的 Start/Continue 按钮在 `credentials.configured === false` 时禁用，并提示“凭证未配置…”
- [CONTRACT] Download Root：
  - `POST /api/settings/download-root` 保存前对目录进行创建/可写性探测；不可写返回 400 + 明确错误
  - 保存后返回更新后的 `download_root`（用于后续落盘模块消费）
- [CONTRACT] Max Concurrent：
  - 默认 3；`POST /api/settings/max-concurrent` 更新 `data/config.json` 并同步更新进程内 `SchedulerConfig`（供后续调度器即时生效）

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 后续 Scheduler（`T-20260113-act-006-scheduler-fifo-locking`）应读取/订阅 `app.state.scheduler_config.max_concurrent` 或同等机制，以保证 MaxConcurrent 动态生效。
- [IMPACT] 后续 Accounts/Start/Continue API（`T-20260113-act-005-*`、`T-20260113-act-006-*`）需复用“凭证未配置即阻止”的同一判断标准（`auth_token` + `ct0`）。
- [IMPACT] Downloader（`T-20260113-act-008-storage-naming-dedup`）应以 `download_root` 为根路径拼装 `<root>/<handle>/{images|videos}/`。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前 Start/Continue 仅为前端最小骨架按钮（用于验证全局设置联动）；真实任务启动/队列/状态机将在后续任务交付。
- [LIMIT] 后端依赖 FastAPI/Uvicorn，已写入 `requirements.txt`，但本仓库运行环境需自行安装依赖后才能启动 Web 服务。
- [RISK] `data/config.json` 明文保存凭证（符合已拍板 ADR-0003）；需在后续 README/风险提示中再次强调不要分享该文件。

