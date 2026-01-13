# Compact — T-20260113-act-005-account-row-config-copy-paste

- generated_at_utc: 2026-01-13T16:30:00Z
- subtask_type: build
- record_status: done

## 1) Scope（对齐范围）

- 目标：为每个账号行交付完整的筛选配置 UI（日期范围、媒体类型、来源类型、MIN_SHORT_SIDE、Reply+Quote 开关）并实现 Copy/Paste Config 功能，Locked 状态下禁用 Paste。
- 非目标：不交付 Scheduler/Runner 实际任务执行逻辑（后续任务实现）。

## 2) 已确认事实（Repo 落地 + 实现覆盖）

- [FACT] `record.json` 中 `T-20260113-act-005-account-row-config-copy-paste` 已更新为 `status: done`，`updated_at: 2026-01-13T16:30:00Z`，`owner: codex`。
- [FACT] 已新增账号行配置组件：
  - `src/frontend/components/AccountRowConfig.js`（配置表单组件，包含所有筛选配置项）
  - `src/frontend/components/AccountRowConfig.css`（深色主题样式，适配项目整体风格）
- [FACT] 已新增配置剪贴板状态管理：
  - `src/frontend/state/ConfigClipboard.js`（全局单例，支持订阅/通知机制）
- [FACT] 已更新 AccountRow 组件集成配置和剪贴板：
  - `src/frontend/app.js`（新增 TaskStatus 枚举、isLockedStatus 判断、配置组件初始化与事件绑定）
- [FACT] 已更新 index.html 引入新组件和样式
- [FACT] 已更新 app.css 添加状态标签样式（running/queued/completed/failed/btn-success）

## 3) 已落实的关键行为（实现交付）

- [CONTRACT] 每账号配置项齐全：
  - 日期范围：开始日期/结束日期（date picker，支持 null）
  - 媒体类型：images/videos/both（radio group 单选）
  - 来源类型：Original/Retweet/Reply/Quote（4 个复选框）
  - MIN_SHORT_SIDE：数字输入（null 表示不限制）
  - includeQuoteMediaInReply：开关（Reply 中是否包含被引用推文的媒体）
- [CONTRACT] Copy Config 功能：
  - 点击 Copy 按钮复制当前行筛选参数到全局剪贴板（不含 URL/handle）
  - 复制成功后显示"Copied"反馈提示（1.5 秒后恢复）
  - Locked 状态下 Copy 保持可用
- [CONTRACT] Paste Config 功能：
  - 点击 Paste 按钮从全局剪贴板应用配置（全覆盖，不改变 URL/handle）
  - 剪贴板为空时 Paste 按钮禁用并提示"剪贴板为空"
  - 粘贴成功后显示"Pasted"反馈提示（1.5 秒后恢复）
- [CONTRACT] Locked 状态处理：
  - Queued/Running 状态时配置组件设为 locked
  - locked 状态下所有输入项禁用
  - locked 状态下 Paste 按钮禁用并提示"任务进行中，无法粘贴配置"
  - locked 状态下 URL 输入也禁用

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 后续 Scheduler（`T-20260113-act-006-scheduler-fifo-locking`）需调用 `AccountRow.setTaskStatus()` 来触发 locked 状态变更。
- [IMPACT] 后续抓取与过滤集成（`T-20260113-act-009-scrape-and-apply-filters`）应通过 `AccountRow.getConfig()` 获取筛选配置并转换为 FilterConfig。
- [IMPACT] 配置数据结构 `AccountConfig` 与后端 `FilterConfig` 保持一致：
  - `startDate` ↔ `start_date`
  - `endDate` ↔ `end_date`
  - `mediaType` ↔ `media_type`
  - `sourceTypes` ↔ `source_types`
  - `minShortSide` ↔ `min_short_side`
  - `includeQuoteMediaInReply` ↔ `include_quote_media_in_reply`

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] 配置目前仅存在内存中，页面刷新后丢失；后续可考虑持久化到 localStorage 或后端。
- [LIMIT] 配置面板默认收起，需点击"筛选配置"展开；这是为了保持 UI 简洁。
- [LIMIT] 全局剪贴板 `configClipboard` 是内存单例，页面刷新后清空。
- [TODO] 后续需在任务启动时将 AccountConfig 转换为后端 FilterConfig 并发送到 API。

## Code Review - T-20260113-act-005-account-row-config-copy-paste - 2026-01-13T17:00:00Z

---review-start---
[P2] Status pill not updated for finished tasks
When `setTaskStatus` is invoked with non-locked states such as `Completed`, `Cancelled`, `Failed`, or `Idle`, `_updateGating` never calls `_setStatus`, so the badge remains whatever it was during the last queued/running/idle gate. This leaves the UI showing stale status (often still "Running" or "Idle") and hides the actual outcome after a run completes or fails.
---review-end---

## Code Review Fix - 2026-01-13T17:30:00Z

---fix-start---
[P2] Status pill not updated for finished tasks — FIXED

**Root Cause:** `_updateGating()` 只在 `isLocked`（Queued/Running）或 `disabled` 时调用 `_setStatus()`，当任务完成后进入非锁定且非禁用状态时，不会更新状态标签。

**Fix:**
1. `src/frontend/app.js:237-247` — 在 `_updateGating()` 中添加 `else` 分支，处理非锁定且非禁用的状态（Completed/Cancelled/Failed/Idle），根据 `_taskStatus` 映射到对应的 CSS 类并调用 `_setStatus()`。
2. `src/frontend/app.css:240-244` — 新增 `.pill.cancelled` 样式（灰色中性风格），补全状态标签样式集。

**Verification:** 当 `setTaskStatus()` 被调用为 Completed/Cancelled/Failed/Idle 时，状态标签现在会正确更新显示对应文本和样式。
---fix-end---
