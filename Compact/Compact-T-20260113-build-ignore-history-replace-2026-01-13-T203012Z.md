# Compact — T-20260113-build-ignore-history-replace

- generated_at_utc: 2026-01-13T20:30:12Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：把 ADR-0004 的 Ignore+Replace 规则落地到 Start New 流程，并提供可回归的自动化测试用例。
- 非目标：不改动抓取/过滤策略本身；不引入额外 UI 展示字段（如 replaced_count 统计项）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] Start New 三选弹窗的选择会透传到调度器：`src/frontend/app.js` 在 Start New 路径向 `/api/scheduler/start` 发送 `start_mode`。
- [FACT] Scheduler/Run 模型支持持久化 `start_mode`：见 `src/backend/scheduler/api.py`、`src/backend/scheduler/scheduler.py`、`src/backend/scheduler/models.py`。
- [FACT] Runner 会按 `start_mode` 选择 Ignore+Replace 下载路径：见 `src/backend/pipeline/account_runner.py`。
- [FACT] Downloader 实现 Ignore+Replace 规则（预扫历史 hash、写入成功后删除旧文件、同 run 内 first-wins 去重）：见 `src/backend/downloader/downloader.py`。
- [FACT] `src/backend/lifecycle/__init__.py` 调整为延迟导入 FastAPI router，避免仅引用枚举/操作函数时触发 FastAPI 依赖。
- [TEST] 新增单测覆盖 ADR 场景 1/2/4：`tests/lifecycle/test_ignore_replace.py`。
- [TEST] 全部测试通过：`python3 -m unittest discover -s tests`。

## 3) 关键行为（实现与 ADR-0004 对齐）

- 相同文件判定：仅按内容 SHA-256 hash（不看文件名/路径）。
- 与账号内去重交互：同一 run 内 newest-first first-wins；重复 hash 直接 `SKIPPED_DUPLICATE`，不触发跨 run 删除。
- 跨 run 覆盖语义：新 run 优先；仅在新文件“安全落盘”（临时文件 + `os.replace`）后，才删除历史同 hash 文件；删除失败只 warning 不阻塞 run。

## 4) 关键代码位置

| 功能 | 文件 | 关键点 |
|------|------|--------|
| 透传 start_mode | `src/frontend/app.js` | `_prepareAndStart()` -> `_startOrContinue()` 增加 `start_mode` |
| 接收/持久化 | `src/backend/scheduler/api.py` | `RunRequestIn.start_mode` |
| 运行时选择策略 | `src/backend/pipeline/account_runner.py` | `ignore_replace` 判定与 loader 分支 |
| Ignore+Replace 落盘 | `src/backend/downloader/downloader.py` | `load_existing_files_for_replace()` + 原子写入 + 写后删旧 |
| 回归测试 | `tests/lifecycle/test_ignore_replace.py` | 覆盖 ADR 场景 1/2/4 |

