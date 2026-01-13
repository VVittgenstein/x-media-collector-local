# Compact — T-20260113-test-url-validation

- generated_at_utc: 2026-01-13T14:30:00Z
- subtask_type: test
- record_status: done

## 1) Scope（对齐范围）

- 目标：为账号 URL 严格校验模块（`src/shared/validators/x_handle_url.py`）补齐自动化测试用例，锁住边界行为，避免后续改动引入回归。
- 非目标：不涉及 UI 层测试，仅覆盖后端校验逻辑。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-test-url-validation` 已更新为 `status: done`，`updated_at: 2026-01-13T14:30:00Z`，`owner: codex`。
- [FACT] 已新增测试模块：`tests/validators/__init__.py`、`tests/validators/test_x_handle_url.py`。
- [TEST] 测试套件包含 35 个测试用例，全部通过：`python3 -m unittest tests.validators.test_x_handle_url -v`。

## 3) 已落实的"契约/决策"（测试覆盖）

- [CONTRACT] 合法 URL 测试（7 个用例）：
  - `https://x.com/shanghaixc2` 验收通过
  - 单字符/最大长度（15 字符）/包含下划线/纯数字 handle 均通过
  - 前后空白自动去除
  - handle 大小写保留

- [CONTRACT] 非法 URL 测试 — 末尾斜杠（1 个用例）：
  - `https://x.com/shanghaixc2/` 失败，错误信息包含"斜杠"

- [CONTRACT] 非法 URL 测试 — twitter.com（2 个用例）：
  - `https://twitter.com/...` 和 `https://www.twitter.com/...` 失败
  - 错误信息明确指出需使用 `x.com`

- [CONTRACT] 非法 URL 测试 — Query 参数（3 个用例）：
  - 带 `?ref=home`、空 `?`、多参数 `?a=1&b=2` 均失败
  - 错误信息包含"查询参数"

- [CONTRACT] 非法 URL 测试 — @handle 格式（2 个用例）：
  - `@shanghaixc2` 和 `@ shanghaixc2` 失败
  - 错误信息引导用户使用完整 URL 格式

- [CONTRACT] 非法 URL 测试 — 额外路径（4 个用例）：
  - `/media`、`/likes`、`/status/<id>`、`/with_replies` 均失败
  - 错误信息包含"额外路径"

- [CONTRACT] 其他边界测试（14 个用例）：
  - 空 URL / 仅空白 / http 协议 / www.x.com / 缺少 handle / 仅根 URL
  - handle 过长（>15 字符）/ 特殊字符 / 中文字符 / fragment / 其他域名 / 无协议

- [CONTRACT] 错误消息用户友好性（2 个用例）：
  - 所有错误消息包含中文
  - 不包含技术术语（exception, null, traceback 等）

## 4) 接口/行为变更对其他模块的影响

- [IMPACT] 无新增接口变更。测试用例锁定现有校验行为，后续修改 `x_handle_url.py` 必须保持测试通过。
- [IMPACT] 本模块完成了 `T-20260113-act-003-url-validate-handle` 中遗留的 `[TODO] 单元测试用例待补齐` 项。

## 5) Code Review 修复

- [REVIEW-FIX] **P2: 拒绝空 query string 的 x.com URL**
  - **问题**：原校验仅检查 `parsed.query` 非空时拒绝，导致 `https://x.com/user?`（尾部 `?` 但无参数）被错误接受。`urlparse` 对此类 URL 返回空字符串，绕过了校验。
  - **修复**：在 `x_handle_url.py:107` 增加 `or "?" in url` 条件，同时检测原始 URL 中的 `?` 字符。
  - **测试**：`test_invalid_with_empty_query` 用例已更新为严格断言（`assertFalse(result.valid)`），不再使用 conditional check。
  - **验证**：35 个测试用例全部通过。

## 6) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 仅覆盖后端 Python 校验逻辑，前端 JS 校验（`AccountRowUrlInput.js`）未在此测试范围。
- [LIMIT] 未使用 pytest（环境未安装），使用 unittest 运行测试。
- [TODO] 如需 CI 集成，建议在 `requirements.txt` 或 `requirements-dev.txt` 添加 pytest 依赖。
