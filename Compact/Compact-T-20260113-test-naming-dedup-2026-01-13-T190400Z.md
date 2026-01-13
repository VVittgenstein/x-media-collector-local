# Compact — T-20260113-test-naming-dedup

- generated_at_utc: 2026-01-13T19:04:00Z
- subtask_type: test
- record_status: done

## 1) Scope（对齐范围）

- 目标：为命名模块（`src/backend/fs/naming.py`）和内容 hash 去重模块（`src/backend/downloader/dedup.py`、`src/backend/fs/hashing.py`）补齐自动化测试用例，锁定格式与 first-wins 行为。
- 非目标：不涉及网络下载/抓取功能测试，仅覆盖本地命名规则与去重逻辑。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-test-naming-dedup` 已更新为 `status: done`，`updated_at: 2026-01-13T19:04:00Z`，`owner: codex`。
- [FACT] 测试文件：`tests/downloader/__init__.py`、`tests/downloader/test_naming_dedup.py`。
- [TEST] 测试套件包含 26 个测试用例，全部通过：`python3 -m unittest tests.downloader.test_naming_dedup -v`。

## 3) 已落实的"契约/决策"（测试覆盖）

### 验收条件1：断言生成文件名可解析出 tweetId 与 YYYY-MM-DD

- [CONTRACT] `test_generate_filename_format`：
  - 验证生成文件名格式为 `<tweetId>_<YYYY-MM-DD>_<hash6>.<ext>`
  - 示例：`1234567890123456789_2026-01-13_a1b2c3.jpg`

- [CONTRACT] `test_parse_filename_extracts_tweet_id`：
  - 从文件名正确解析出 tweetId
  - 示例：`1234567890123456789`

- [CONTRACT] `test_parse_filename_extracts_date`：
  - 从文件名正确解析出日期 YYYY-MM-DD
  - 示例：`2026-01-13`

- [CONTRACT] `test_generate_and_parse_roundtrip`：
  - 生成后解析，完整恢复原始组件（tweetId、date、hash6、extension）

### 验收条件2：断言 hash6 等于内容 hash 前 6 位

- [CONTRACT] `test_hash6_equals_first_6_chars`：
  - 明确断言 `hash6 == full_hash[:6]`
  - 断言长度为 6

- [CONTRACT] `test_hash6_is_lowercase`：
  - hash6 始终为小写十六进制

- [CONTRACT] `test_filename_contains_correct_hash6`：
  - 下载后文件名中的 hash6 与内容 hash 前 6 位一致
  - 通过 `compute_bytes_hash(content)[:6]` 验证

### 验收条件3：模拟两次写入相同内容：第一次保留，第二次删除临时文件并 skipped_duplicate+1

- [CONTRACT] `test_first_content_is_new`：
  - 首次内容标记为 `DedupResult.NEW`

- [CONTRACT] `test_second_content_is_duplicate`：
  - 相同内容第二次检查标记为 `DedupResult.DUPLICATE`
  - 返回第一次文件的路径 (`existing_file`)

- [CONTRACT] `test_first_wins_keeps_first_download`：
  - 完整下载流程：第一次 `DownloadStatus.SUCCESS`，第二次 `DownloadStatus.SKIPPED_DUPLICATE`
  - 验证 `stats.images_downloaded == 1`、`stats.skipped_duplicate == 1`

- [CONTRACT] `test_skipped_duplicate_count_increments`：
  - 5 次相同内容下载：`images_downloaded == 1`、`skipped_duplicate == 4`

- [CONTRACT] `test_newest_first_sorting`：
  - `download_all(sort_newest_first=True)` 按 created_at 从新到旧排序处理
  - 保证 first-wins 行为可解释（最新推文的媒体优先保留）

### 其他覆盖

- [CONTRACT] `test_stats_track_duplicates`：统计正确追踪 total_checked 和 duplicates_found
- [CONTRACT] `test_load_from_directory`：从目录加载已有文件 hash，支持跨 run 去重
- [CONTRACT] `test_account_directory_structure`：目录结构固定为 `<root>/<handle>/{images,videos}/`
- [CONTRACT] `test_media_type_routing`：图片和视频正确路由到各自目录
- [CONTRACT] `test_hash6_must_be_6_chars`：hash6 必须恰好 6 字符
- [CONTRACT] `test_hash6_must_be_hex`：hash6 必须为十六进制字符

## 4) 接口/行为变更对其他模块的影响

- [IMPACT] 无新增接口变更。测试用例锁定现有命名与去重行为。
- [IMPACT] 后续修改 `naming.py`、`dedup.py`、`hashing.py`、`downloader.py` 必须保持测试通过。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 使用 unittest 运行测试（环境未安装 pytest）。
- [LIMIT] 测试使用 mock download function，未涉及真实网络请求。
- [TODO] 如需 CI 集成，建议添加 pytest 依赖。
