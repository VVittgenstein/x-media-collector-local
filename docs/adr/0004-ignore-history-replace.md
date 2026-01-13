# ADR-0004：Ignore History + Replace 规则设计

- Status: **Accepted**
- Date: 2026-01-13

## 背景 / Context

当用户对某个账号执行 "Start New" 操作时，如果账号目录已存在历史文件，系统会弹出三选弹窗：

1. **Delete & Restart**：清空后重跑
2. **Ignore History + Replace**：保留历史，新 run 优先覆盖
3. **Pack & Restart**：打包为 zip 后重跑

本 ADR 详细定义 **Ignore History + Replace** 模式下的行为规则，确保：
- 相同内容的判定标准清晰
- 跨 run 的覆盖语义可解释
- 与账号内去重（first wins）交互明确
- 规则可落地为可测试的算法

## 决策 / Decision

### 1) 相同文件判定：仅按内容 hash，不看文件名

**规则**：两个文件被判定为"相同"，当且仅当它们的 SHA-256 内容 hash 完全相同。

**不考虑的因素**：
- 文件名（即使 `tweetId` 或日期不同）
- 文件路径
- 修改时间
- 文件大小（hash 相同则大小必然相同）

**理由**：
- 内容 hash 是最可靠的重复判定依据
- 避免因命名规则变化（如日期格式调整）导致误判
- 符合"训练数据采集"场景的本质需求：内容去重

### 2) 跨 run 覆盖语义：新 run 优先

**规则**：当用户选择 Ignore+Replace 模式时：
- **历史文件**（上次 run 遗留）被视为"待覆盖候选"
- **当前 run** 的下载结果享有优先权
- 若当前 run 下载的内容与某历史文件内容 hash 相同，则**先保存新文件**（确保写入成功），**后删除历史文件**

**直观理解**：用户主动选择 Ignore+Replace 即表示"以最新 run 为准"。

### 3) 与账号内去重（first wins）的交互

现有的账号内去重规则：
- 同一 run 内按 `created_at` 从新到旧处理
- 首次出现的 hash 被保留（first wins）
- 后续相同 hash 的媒体被跳过（计入 `skipped_duplicate`）

**Ignore+Replace 模式下的交互**：
- **账号内去重仍然生效**：同一 run 内的重复内容只保留一份
- **跨 run 覆盖发生在账号内去重之后**：
  - 若当前 run 某内容 hash 是新的（本 run 首次出现），检查历史文件
  - 若历史文件存在相同 hash，删除历史文件后保存新文件
  - 若当前 run 某内容 hash 已在本 run 内出现过，直接跳过（不触发跨 run 覆盖）

### 4) 算法描述

```
Ignore+Replace 模式下的下载处理算法：

输入：
  - existing_files: 目录中已存在的文件列表
  - new_intents: 本次 run 要下载的媒体意图列表（按 created_at 从新到旧排序）

预处理：
  1. 构建 existing_hash_map: {content_hash -> file_path}
     - 遍历 existing_files
     - 对每个文件计算 content_hash
     - 存入 map

  2. 初始化 current_run_hashes: Set<content_hash>（空集合）

主循环：
  for each intent in new_intents:
    1. 下载内容，计算 content_hash

    2. 检查账号内去重（当前 run）
       if content_hash in current_run_hashes:
         -> SKIP（计入 skipped_duplicate）
         -> continue

    3. 注册当前 run 的 hash
       current_run_hashes.add(content_hash)

    4. 先写入新文件（确保数据安全）
       filename = generate_media_filename(tweet_id, created_at, hash6, ext)
       temp_path = target_dir / (filename + ".tmp")
       write(temp_path, content)  # 写入临时文件
       rename(temp_path, target_dir / filename)  # 原子重命名到最终路径
       -> 新文件已安全落盘

    5. 检查跨 run 覆盖（仅在新文件写入成功后删除旧文件）
       if content_hash in existing_hash_map:
         old_file_path = existing_hash_map[content_hash]
         if old_file_path != (target_dir / filename):  # 避免删除刚写入的文件
           try:
             delete(old_file_path)
           except:
             log_warning("Failed to delete old file, continuing...")
             # 不阻塞整个 run，仅记录警告
       -> SUCCESS
```

### 5) 关键行为说明

| 场景 | 历史文件 | 新 run 行为 | 结果 |
|------|----------|-------------|------|
| 全新内容 | 无 | 下载并保存 | 新增 1 个文件 |
| 相同内容 | hash=X | 下载并覆盖 | 删除旧文件，保存新文件（总数不变） |
| 同内容不同 tweet | hash=X（来自 tweetA） | 下载 tweetB（hash 也=X） | 删除 tweetA 的文件，保存 tweetB 的文件 |
| 同 run 内重复 | 无 | 多次下载相同内容 | 只保留首次（newest first wins） |
| 混合场景 | hash=X, hash=Y | 下载 hash=X 和 hash=Z | X 被覆盖，Y 保留，Z 新增 |

## 示例场景

### 场景 1：旧文件存在，新 run 下载相同内容

**初始状态**：
```
<root>/alice/images/
  └── 1234567890_2026-01-10_a1b2c3.jpg  (hash = abc123...)
```

**新 run 操作**：
- 选择 Ignore+Replace
- 下载 tweet 1234567890 的图片（内容相同，hash = abc123...）

**期望结果**：
```
<root>/alice/images/
  └── 1234567890_2026-01-10_a1b2c3.jpg  (新文件，内容相同)
```

**说明**：虽然内容相同，但旧文件被删除后重新保存。文件名相同（因为 tweetId、日期、hash6 都相同）。

---

### 场景 2：重复内容来自不同 tweet

**初始状态**：
```
<root>/bob/images/
  └── 1111111111_2026-01-05_d4e5f6.jpg  (hash = def456...)
```

**新 run 操作**：
- 选择 Ignore+Replace
- 下载 tweet 2222222222 的图片（内容相同，hash = def456...，但 tweet 不同）

**期望结果**：
```
<root>/bob/images/
  └── 2222222222_2026-01-12_d4e5f6.jpg  (新 tweet 的文件)
```

**说明**：
- 旧文件 `1111111111_2026-01-05_d4e5f6.jpg` 被删除
- 新文件 `2222222222_2026-01-12_d4e5f6.jpg` 被保存
- hash6 相同（因为内容相同），但 tweetId 和日期不同

---

### 场景 3：同名不同内容（理论场景）

**初始状态**：
```
<root>/carol/images/
  └── 3333333333_2026-01-08_aaaaaa.jpg  (hash = oldHash...)
```

**新 run 操作**：
- 选择 Ignore+Replace
- 下载 tweet 3333333333（内容已被博主修改/重新上传，新 hash = newHash...）

**期望结果**：
```
<root>/carol/images/
  ├── 3333333333_2026-01-08_aaaaaa.jpg  (旧文件保留，hash 不匹配不触发覆盖)
  └── 3333333333_2026-01-08_bbbbbb.jpg  (新文件，不同 hash6)
```

**说明**：
- 旧文件不会被删除（因为内容 hash 不同，不满足覆盖条件）
- 新文件的 hash6 = bbbbbb（与旧文件不同），所以文件名不冲突
- 同一 tweet 存在两个版本的媒体（这是合理的：博主确实修改过内容）

---

### 场景 4：跨 run 与账号内去重的交互

**初始状态**：
```
<root>/dave/images/
  └── 4444444444_2026-01-01_cccccc.jpg  (hash = xyz789...)
```

**新 run 下载列表**（按 created_at 从新到旧）：
1. tweet 5555555555, 2026-01-12, content hash = xyz789...（与历史相同）
2. tweet 6666666666, 2026-01-11, content hash = xyz789...（与 tweet5 相同）

**期望结果**：
```
<root>/dave/images/
  └── 5555555555_2026-01-12_cccccc.jpg  (新文件)
```

**说明**：
- 处理 tweet 5555555555：hash xyz789 首次出现于本 run，触发跨 run 覆盖，删除旧文件 4444444444，保存新文件
- 处理 tweet 6666666666：hash xyz789 已在本 run 出现（tweet5），触发账号内去重，SKIP
- 最终只保留 tweet5 的文件（newest first wins 生效）

## 备选方案 / Alternatives Considered

### 方案 A：按文件名判定相同

检查新旧文件名是否完全一致。

**否决原因**：
- 同一内容可能来自不同 tweet（文件名不同）
- 命名规则变更会导致判定失效
- 无法识别"相同内容不同来源"的真正重复

### 方案 B：旧文件优先（保守模式）

如果历史文件存在相同 hash，跳过新下载。

**否决原因**：
- 与"Ignore+Replace"的语义不符（用户期望的是"以新为准"）
- 无法更新元数据（如日期）

### 方案 C：不删除旧文件，直接覆写

如果新旧文件名相同则覆写，不相同则两者共存。

**否决原因**：
- 可能导致同内容多文件（浪费存储且统计不准）
- 覆写依赖文件名一致，不够健壮

## 影响 / Consequences

- **正向**：
  - 规则清晰可测试，按内容 hash 判定确保语义一致
  - "新 run 优先"符合用户心智模型（选择 Ignore+Replace 就是要更新）
  - 与账号内去重兼容，不产生冲突或不可解释的状态

- **注意事项**：
  - 需要在下载前扫描现有文件并计算 hash（可能有性能开销，但可接受）
  - **数据安全优先**：必须先写入新文件成功后再删除旧文件，避免写入失败导致数据丢失
  - 同一 tweet 不同版本会共存（极端边界情况，可接受）

## 实现要点

1. **修改 `MediaDownloader`**：增加 `ignore_replace` 模式参数
2. **预扫描现有文件**：构建 hash->path 映射表
3. **安全写入流程**：
   - 先写入临时文件（`.tmp` 后缀）
   - 原子重命名到最终路径
   - 仅在新文件写入成功后删除旧文件
4. **删除失败容错**：删除旧文件失败时记录警告但不阻塞 run
5. **统计口径**：新增 `replaced_count` 统计项（可选）
