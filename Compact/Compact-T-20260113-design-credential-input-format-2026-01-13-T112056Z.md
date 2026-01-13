# Compact — T-20260113-design-credential-input-format

- generated_at_utc: 2026-01-13T11:20:56Z
- subtask_type: design
- record_status: done

## 1) Scope（对齐范围）

- 目标：定义凭证输入格式、最小可用字段集合、校验策略与存储规则，产出 ADR 设计文档供后续实现任务参照。
- 非目标：本 Subtask 不交付凭证输入 UI 组件或后端校验 API 的实现代码（仅产出设计文档与记录更新）。

## 2) 已确认事实（Repo 落地 + 自测覆盖）

- [FACT] `record.json` 中 `T-20260113-design-credential-input-format` 已更新为 `status: done`，并写入 `updated_at: 2026-01-13T11:20:35Z`、`owner: codex`。
- [FACT] 已新增设计文档：`docs/adr/0003-credentials-format.md`。
- [TEST] JSON 可解析：`python3 -c "import json; json.load(open('record.json'))"` → 预期 OK。

## 3) 已落实的"契约/决策"（文档定义；待后续实现落地）

- [CONTRACT] 凭证输入方式（ADR-0003）：分字段输入，每字段独立填写。
- [CONTRACT] 最小可用字段集合（ADR-0003）：`auth_token`（主认证令牌，约 40 字符）+ `ct0`（CSRF 防护令牌，约 32 字符）为必填；`twid` 为可选。
- [CONTRACT] 缺失字段提示（ADR-0003）：必填字段缺失时阻止所有任务启动，展示明确提示指出缺失字段与格式要求。
- [CONTRACT] 轻量校验（ADR-0003）：保存凭证时触发一次轻量 GraphQL 请求验证登录态；200 为通过，401/403/429/网络错误分别给出可解释错误提示。
- [CONTRACT] 存储策略（ADR-0003）：凭证允许本地存储于 `data/config.json`，不加密；保存后 UI 仅显示脱敏形式（如 `abc***xyz`），不回显明文；日志中不输出凭证值。
- [CONTRACT] User-Agent 策略（ADR-0003）：由系统内置固定值（常见桌面浏览器 UA），不可用户配置。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] Settings UI 需实现：分字段凭证输入表单、格式示例提示、保存并验证按钮、已配置状态展示（脱敏）、"如何获取凭证"帮助文案。
- [IMPACT] Backend Settings API 需实现：凭证保存端点、凭证校验端点（轻量 GraphQL 请求）、校验结果缓存与过期策略。
- [IMPACT] 请求层需遵循：所有抓取请求携带 `Cookie: auth_token=...; ct0=...` 与 `x-csrf-token: {ct0}`；使用内置 User-Agent。
- [IMPACT] 日志与错误报告需遵循：不输出 `auth_token`、`ct0` 等凭证原文；脱敏或完全省略。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 当前仅完成设计文档输出；凭证输入 UI、后端校验 API、存储逻辑尚未实现。
- [TODO] 凭证过期后的用户引导流程（如自动检测过期、提示重新配置）需在实现任务中落地。
- [RISK] 不加密存储意味着任何能读取 `data/config.json` 的进程都能获取凭证（需在文档/UI 中明确告知用户）。
- [RISK] 校验请求本身可能触发限流（429），需在实现时控制校验频率。
