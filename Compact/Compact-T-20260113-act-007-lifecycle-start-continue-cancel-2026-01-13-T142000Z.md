# Compact: T-20260113-act-007-lifecycle-start-continue-cancel

## Task Summary
实现任务生命周期：Start New / Continue / Cancel 与弹窗逻辑

## Acceptance Criteria Status
- [x] Start New 与 Continue 分离为两个动作（非同一按钮复用）
- [x] Running 状态 Cancel 必弹窗：Keep/Delete；Queued Cancel 无弹窗且无副作用
- [x] Start New 时若账号目录存在历史文件，必出三选弹窗（Delete / Ignore+Replace / Pack）
- [x] Pack&Restart：生成 zip 并删除原文件，zip 留在账号目录；Delete&Restart：清空后重跑

## Implementation Summary

### Backend: Lifecycle Module
Created `src/backend/lifecycle/` with:

1. **models.py**: 定义两个枚举类型
   - `StartMode`: DELETE, IGNORE_REPLACE, PACK
   - `CancelMode`: KEEP, DELETE

2. **operations.py**: 核心操作逻辑
   - `check_existing_files()`: 检查账号目录是否有历史文件
   - `prepare_start_new()`: 根据模式执行 Delete/Pack/Ignore 操作
   - `prepare_cancel_running()`: 根据模式执行 Keep/Delete 操作

3. **api.py**: FastAPI 路由
   - `GET /api/lifecycle/check/{handle}`: 检查现有文件
   - `POST /api/lifecycle/prepare-start`: 执行 Start New 准备操作
   - `POST /api/lifecycle/prepare-cancel`: 执行 Cancel 清理操作

### Backend: Archive Module
Created `src/backend/fs/archive_zip.py`:
- `archive_account_files()`: 将账号媒体文件打包为 zip
  - 格式: `{handle}_archive_{YYYYMMDD_HHMMSS}.zip`
  - 打包完成后删除原文件
- `delete_account_files()`: 删除账号目录下所有媒体文件

### Frontend: ConfirmModals Component
Created `src/frontend/components/ConfirmModals.js`:

1. **showStartNewModal()**: 三选弹窗
   - Delete & Restart: 删除所有文件重新开始
   - Ignore & Replace: 保留文件，新 run 按 hash 覆盖
   - Pack & Restart: 打包为 zip 后重新开始

2. **showCancelRunningModal()**: 二选弹窗
   - Keep Files: 保留已下载的文件
   - Delete Files: 删除所有已下载的文件

### Frontend: App.js Integration
Updated `src/frontend/app.js`:

1. **_onStart()**: 修改为检查 kind
   - `start`: 先检查现有文件，有则显示弹窗
   - `continue`: 直接启动

2. **_checkExistingAndStart()**: 新增方法
   - 调用 `/api/lifecycle/check/{handle}`
   - 有文件则显示 StartNewModal

3. **_prepareAndStart()**: 新增方法
   - 调用 `/api/lifecycle/prepare-start`
   - 完成后调用 `_startOrContinue()`

4. **_onCancel()**: 修改为区分状态
   - `RUNNING`: 显示 CancelRunningModal
   - `QUEUED`: 直接取消无弹窗

5. **_performCancel()**: 新增方法
   - 调用 `/api/scheduler/cancel`
   - 如果选择 DELETE，调用 `/api/lifecycle/prepare-cancel`

### CSS Updates
Updated `src/frontend/app.css`:
- Added `.btn-warning` style (yellow button)
- Added modal styles: `.modal-overlay`, `.modal-container`, `.modal-header`, `.modal-body`, `.modal-footer`
- Added animations: `fadeIn`, `slideIn`

## Files Changed
- `src/backend/fs/__init__.py` - Added archive exports
- `src/backend/fs/archive_zip.py` - NEW: Archive utilities
- `src/backend/lifecycle/__init__.py` - NEW: Module init
- `src/backend/lifecycle/models.py` - NEW: StartMode/CancelMode enums
- `src/backend/lifecycle/operations.py` - NEW: File operations
- `src/backend/lifecycle/api.py` - NEW: API routes
- `src/backend/app.py` - Added lifecycle router
- `src/frontend/components/ConfirmModals.js` - NEW: Modal components
- `src/frontend/app.js` - Integrated lifecycle flow
- `src/frontend/app.css` - Added modal styles
- `src/frontend/index.html` - Added ConfirmModals.js script

## Flow Diagrams

### Start New Flow
```
User clicks "Start"
       │
       ▼
Check existing files
GET /api/lifecycle/check/{handle}
       │
       ▼
Has files? ──No──> Start task directly
       │
      Yes
       │
       ▼
Show StartNewModal
[Delete] [Ignore+Replace] [Pack]
       │
       ▼
POST /api/lifecycle/prepare-start
       │
       ▼
POST /api/scheduler/start
```

### Cancel Running Flow
```
User clicks "Cancel" (Running)
       │
       ▼
Show CancelRunningModal
[Keep Files] [Delete Files]
       │
       ▼
POST /api/scheduler/cancel
       │
       ▼
If Delete selected:
POST /api/lifecycle/prepare-cancel
```

### Cancel Queued Flow
```
User clicks "Cancel" (Queued)
       │
       ▼
POST /api/scheduler/cancel
(No modal, immediate cancel)
```

## Key Design Decisions
1. Start 和 Continue 保持为独立按钮（已有实现）
2. Queued 状态取消无副作用，不需要弹窗确认
3. Running 状态取消需要用户决定是否保留已下载文件
4. Pack 操作生成带时间戳的 zip 文件，便于追溯
5. Ignore+Replace 模式在运行时处理，不预处理文件

## Code Review Fixes

### [P2] Cancel-delete silently ignores backend errors
- **Issue**: 取消运行中任务并选择"Delete"时，调用 `/api/lifecycle/prepare-cancel` 后未检查 HTTP 状态码。后端删除文件失败（如权限错误返回 500）时，UI 仍显示取消成功，用户误以为文件已删除但实际仍在磁盘上。
- **Fix**: 在 `_performCancel()` 中检查 `cleanupRes.ok`，非 2xx 响应时显示错误信息"任务已取消，但删除文件失败"。同时改进 catch 块，将网络错误也展示给用户。
- **Files Changed**: `src/frontend/app.js`
- **Fixed At**: 2026-01-13T14:30:00Z
