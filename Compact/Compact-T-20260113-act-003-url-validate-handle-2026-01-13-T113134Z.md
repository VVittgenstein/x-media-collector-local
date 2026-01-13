# Compact — T-20260113-act-003-url-validate-handle

- generated_at_utc: 2026-01-13T11:31:34Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：实现账号 URL 严格校验与 handle 解析，确保仅接受 `https://x.com/<handle>` 格式，并在 UI 层提供清晰的错误反馈与状态展示。
- 非目标：本 Subtask 不交付完整的账号行 UI（筛选配置、状态管理等），仅聚焦 URL 输入校验组件。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-act-003-url-validate-handle` 已更新为 `status: done`，`updated_at: 2026-01-13T11:31:34Z`，`owner: codex`。
- [FACT] 已新增后端校验模块：`src/shared/validators/__init__.py`、`src/shared/validators/x_handle_url.py`。
- [FACT] 已新增前端组件：`src/frontend/components/AccountRowUrlInput.js`、`src/frontend/components/AccountRowUrlInput.css`。
- [TEST] 后端模块可导入：`python3 -c "from src.shared.validators import validate_x_url, ValidationResult; print('OK')"`。

## 3) 已落实的"契约/决策"（实现交付）

- [CONTRACT] URL 校验严格规则（后端 `validate_x_url` + 前端 `validateXUrl`）：
  - 必须 `https://` 协议（拒绝 `http://`）
  - 必须 `x.com` 域名（拒绝 `twitter.com`、`www.x.com`）
  - 不允许末尾 `/`、query 参数、fragment、额外路径段
  - Handle 仅允许字母、数字、下划线，长度 1-15
- [CONTRACT] 校验结果数据结构：`ValidationResult { valid: bool, handle?: string, error?: string }`
- [CONTRACT] 前端组件 `AccountRowUrlInput` 提供：
  - 实时校验（input/blur/paste 事件触发）
  - 有效时显示绿色边框 + `@handle` 徽章
  - 无效时显示红色边框 + 行内错误信息
  - `onValidationChange` 回调供外层判断是否可启动任务
  - `isValid()` / `getHandle()` 方法供外层查询状态

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 账号行 UI（`T-20260113-act-005-account-row-config-copy-paste`）需集成 `AccountRowUrlInput` 组件，并在 `isValid() === false` 时禁用 Start/Continue 按钮。
- [IMPACT] 后端账号行管理 API 需调用 `validate_x_url()` 进行服务端校验，拒绝非法 URL 加入队列（返回 400 + 错误信息）。
- [IMPACT] 测试任务（`T-20260113-test-url-validation`）需覆盖本模块的边界用例。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 前端组件为纯 JS 实现，未绑定具体框架；集成到完整页面时需引入 CSS 文件。
- [TODO] 后端 API 层的服务端校验尚未实现（仅提供校验函数，需在后续 API 实现任务中调用）。
- [TODO] 单元测试用例待 `T-20260113-test-url-validation` 任务补齐。
