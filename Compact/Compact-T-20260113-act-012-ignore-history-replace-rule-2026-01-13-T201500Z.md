# Compact — T-20260113-act-012-ignore-history-replace-rule

- generated_at_utc: 2026-01-13T20:35:00Z
- subtask_type: design
- record_status: done
- code_review_fixes: 2

## 1) Scope（对齐范围）

- 目标：定义 Ignore+Replace 模式下的行为规则，包括相同文件判定标准、跨 run 覆盖语义、与账号内去重的交互，产出 ADR 设计文档供后续实现任务参照。
- 非目标：本 Subtask 不交付 Ignore+Replace 的实现代码（仅产出设计文档与记录更新），实现代码由 T-20260113-build-ignore-history-replace 负责。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-012-ignore-history-replace-rule` 已更新为 `status: done`，并写入 `updated_at: 2026-01-13T20:35:00Z`、`owner: codex`，包含 2 条 code_review_fixes。
- [FACT] 已新增设计文档：`docs/adr/0004-ignore-history-replace.md`。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → 预期 OK。

## 3) 已落实的"契约/决策"（文档定义；待后续实现落地）

- [CONTRACT] 相同文件判定（ADR-0004）：仅按 SHA-256 内容 hash 判定，不看文件名、路径、修改时间或大小。
- [CONTRACT] 跨 run 覆盖语义（ADR-0004）：选择 Ignore+Replace 模式时，当前 run 优先；若新下载内容与历史文件 hash 相同，先保存新文件（确保写入成功），后删除历史文件。
- [CONTRACT] 与账号内去重交互（ADR-0004）：账号内去重（first wins, newest first）仍然生效；跨 run 覆盖发生在账号内去重判定之后。
- [CONTRACT] 处理算法（ADR-0004）：
  1. 预扫描现有文件，构建 `existing_hash_map: {content_hash -> file_path}`
  2. 初始化 `current_run_hashes` 空集合
  3. 对每个下载意图（按 created_at 从新到旧）：
     - 若 hash 在 current_run_hashes 中 → SKIP（账号内去重）
     - 否则加入 current_run_hashes
     - **先写入新文件**（临时文件 + 原子重命名，确保数据安全）
     - **后删除旧文件**（仅当 hash 在 existing_hash_map 中且新文件写入成功）

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] `MediaDownloader` 需增加 `ignore_replace` 模式参数，控制是否启用跨 run 覆盖行为。
- [IMPACT] 启动时需预扫描现有文件计算 hash（可能有性能开销，但对于本地工具可接受）。
- [IMPACT] 统计口径可考虑新增 `replaced_count` 字段（可选）。
- [IMPACT] 错误处理：删除旧文件失败时应记录日志但不阻塞整个 run。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前仅完成设计文档输出；Ignore+Replace 的实现代码尚未落地（由 T-20260113-build-ignore-history-replace 负责）。
- [TODO] 需在实现中确保"先写入新文件再删除旧文件"的流程（临时文件 + 原子重命名）。
- [RISK] 同一 tweet 内容变更后会产生两个文件（不同 hash6），这是可接受的边界情况。
- [RISK] 预扫描大目录可能耗时，但作为本地工具可接受。

## 6) 设计文档核心场景摘要

| 场景 | 初始状态 | 操作 | 期望结果 |
| ------ | ---------- | ------ | ---------- |
| 场景 1：旧文件存在，新 run 下载相同内容 | `1234567890_2026-01-10_a1b2c3.jpg` | 下载 tweet 1234567890（相同 hash） | 旧文件被删除，新文件保存（文件名相同） |
| 场景 2：重复内容来自不同 tweet | `1111111111_2026-01-05_d4e5f6.jpg` | 下载 tweet 2222222222（相同 hash） | 旧文件被删除，新文件 `2222222222_2026-01-12_d4e5f6.jpg` 保存 |
| 场景 3：同 tweet 不同内容 | `3333333333_2026-01-08_aaaaaa.jpg` | 下载 tweet 3333333333（新 hash） | 两个文件共存（不同 hash6 = 不同文件名） |
| 场景 4：跨 run 与账号内去重交互 | `4444444444_2026-01-01_cccccc.jpg` | 下载 tweet5 + tweet6（都是相同 hash） | 旧文件被删除，仅保留 tweet5（newest first wins） |

## 7) Code Review 修复记录

| # | Issue | 修复内容 |
| --- | --- | --- |
| 1 | [P1] Delete old file before new write risks data loss | 原算法先删除旧文件再写入新文件，修改为：先写入临时文件 + 原子重命名，仅在成功后删除旧文件 |
| 2 | [P1] Cross-run rule still says delete before writing | 决策章节描述与修复后算法矛盾，更新为"先保存新文件，后删除历史文件" |
