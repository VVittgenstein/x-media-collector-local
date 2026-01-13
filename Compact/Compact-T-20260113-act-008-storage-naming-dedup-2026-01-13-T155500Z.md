# Compact — T-20260113-act-008-storage-naming-dedup

- generated_at_utc: 2026-01-13T15:55:00Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：实现落盘规则的完整后端模块，包括目录结构管理、文件命名规范、内容 hash 计算与账号内去重（first wins）。
- 非目标：本 Subtask 不实现实际的网络下载/HTTP 请求；下载函数由调用方注入。仅交付文件系统层与去重逻辑。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-008-storage-naming-dedup` 已更新为 `status: done`，`updated_at: 2026-01-13T15:55:00Z`，`owner: codex`。
- [FACT] 已新增 `src/backend/fs/` 模块：
  - `__init__.py` - 模块导出
  - `storage.py` - 目录结构管理（AccountStorageManager）
  - `naming.py` - 文件命名规范（generate_media_filename/parse_media_filename）
  - `hashing.py` - 内容 hash 计算（SHA-256、hash6、StreamHasher）
- [FACT] 已新增 `src/backend/downloader/` 模块：
  - `__init__.py` - 模块导出
  - `dedup.py` - 去重索引（DedupIndex）
  - `downloader.py` - 媒体下载器（MediaDownloader）
- [FACT] 已新增测试 `tests/downloader/test_naming_dedup.py`（含 naming、hashing、dedup、downloader 完整用例）。
- [TEST] 核心验证通过：文件命名可正确解析 tweetId/date/hash6；hash6 正确等于内容 hash 前 6 位；first-wins 去重行为正确。

## 3) 已落实的"契约/行为"（实现交付）

- [CONTRACT] 目录结构（AccountStorageManager）：
  - 固定为 `<download_root>/<handle>/images/` 与 `<download_root>/<handle>/videos/`
  - `ensure_account_dirs()` 自动创建目录
  - `has_existing_files()` 检测是否有历史文件
- [CONTRACT] 文件命名（naming.py）：
  - 格式：`<tweetId>_<YYYY-MM-DD>_<hash6>.<ext>`
  - `generate_media_filename()` 生成符合规范的文件名
  - `parse_media_filename()` 解析文件名提取 tweetId/date/hash6/extension
  - hash6 必须是 6 位十六进制字符
- [CONTRACT] 内容 hash（hashing.py）：
  - 使用 SHA-256 算法
  - `compute_file_hash()` / `compute_bytes_hash()` 计算完整 hash
  - `compute_hash6()` 提取前 6 位
  - `StreamHasher` 支持流式计算（边下载边 hash）
- [CONTRACT] 账号内去重（dedup.py + downloader.py）：
  - First wins 规则：先处理的内容保留，后遇到相同 hash 的跳过
  - 处理顺序：从新到旧（created_at 降序），保证"最新的留下"可解释
  - 重复跳过时：不写入文件，计入 `skipped_duplicate` 统计
  - `load_existing_files()` 可加载已有文件 hash 用于跨 run 去重

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] `T-20260113-act-009-scrape-and-apply-filters` 需使用 `MediaDownloader` 进行下载，传入 `MediaIntent` 列表。
- [IMPACT] 调用方需提供 `download_func: (url) -> bytes` 实现实际下载逻辑。
- [IMPACT] `T-20260113-act-007-lifecycle-start-continue-cancel` 在 Start New 时可调用 `has_existing_files()` 检测是否需要弹出三选弹窗。
- [IMPACT] `T-20260113-test-naming-dedup` 任务已有完整测试框架，可直接在有 pytest 环境中运行。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前 `MediaDownloader` 接收同步的 `download_func`；如需异步下载，后续可扩展。
- [LIMIT] 测试需要 pytest 环境；基础验证已通过 Python 内置 assert。
- [TODO] 跨 run 的 Ignore+Replace 行为需在 `T-20260113-act-012-ignore-history-replace-rule` 和 `T-20260113-build-ignore-history-replace` 中落地。

## 6) 关键代码位置

| 功能 | 文件 | 关键函数/类 |
|------|------|------------|
| 目录结构 | `src/backend/fs/storage.py` | `AccountStorageManager`, `AccountPaths`, `MediaType` |
| 文件命名 | `src/backend/fs/naming.py` | `generate_media_filename`, `parse_media_filename` |
| 内容 hash | `src/backend/fs/hashing.py` | `compute_file_hash`, `compute_hash6`, `StreamHasher` |
| 去重索引 | `src/backend/downloader/dedup.py` | `DedupIndex`, `DedupResult` |
| 下载器 | `src/backend/downloader/downloader.py` | `MediaDownloader`, `MediaIntent`, `DownloadStats` |
| 测试 | `tests/downloader/test_naming_dedup.py` | 全部测试类 |

