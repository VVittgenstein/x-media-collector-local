/* global fetch, AccountRowUrlInput, GlobalSettingsPanel, AccountRowConfig, AccountRowStats, configClipboard */

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    node.appendChild(child);
  }
  return node;
}

/**
 * 任务状态枚举
 */
const TaskStatus = {
  IDLE: "Idle",
  QUEUED: "Queued",
  RUNNING: "Running",
  DONE: "Done",
  CANCELLED: "Cancelled",
  FAILED: "Failed",
};

/**
 * 判断任务是否锁定（不可编辑配置）
 * @param {string} status
 * @returns {boolean}
 */
function isLockedStatus(status) {
  return status === TaskStatus.QUEUED || status === TaskStatus.RUNNING;
}

class AccountRow {
  constructor(container, { getSettings }) {
    this.container = container;
    this.getSettings = getSettings;
    this._validation = { valid: false, handle: null, error: "URL 不能为空" };
    this._taskStatus = TaskStatus.IDLE;
    this._queuedPosition = null;
    this._unsubscribeClipboard = null;
    this._render();
  }

  _render() {
    this.card = el("div", { class: "account-card" });
    const row = el("div", { class: "row" });

    const urlContainer = el("div", { style: "flex: 1;" });
    this.urlInput = new AccountRowUrlInput(urlContainer, {
      onValidationChange: (result) => {
        const prevHandle = this._validation?.handle;
        this._validation = result;
        if (!isLockedStatus(this._taskStatus) && prevHandle && prevHandle !== result.handle) {
          this._taskStatus = TaskStatus.IDLE;
          this._queuedPosition = null;
          if (this.statsComponent) this.statsComponent.reset();
        }
        this._updateGating();
        if (this.statsComponent) this.statsComponent.refresh();
      },
    });

    const actions = el("div", { class: "account-actions" });
    this.startBtn = el("button", {
      class: "btn btn-primary",
      text: "Start",
      onclick: () => this._onStart("start"),
    });
    this.continueBtn = el("button", {
      class: "btn",
      text: "Continue",
      onclick: () => this._onStart("continue"),
    });
    this.cancelBtn = el("button", {
      class: "btn btn-danger",
      text: "Cancel",
      onclick: () => this._onCancel(),
    });
    actions.appendChild(this.startBtn);
    actions.appendChild(this.continueBtn);
    actions.appendChild(this.cancelBtn);

    row.appendChild(urlContainer);
    row.appendChild(actions);

    // 配置组件容器
    this.configContainer = el("div", { class: "account-config-container" });
    this.statsContainer = el("div", { class: "account-stats-container" });

    this.meta = el("div", { class: "account-meta" });
    this.reasonEl = el("div", { class: "reason" });
    this.statusPill = el("div", { class: "pill muted", text: "Idle" });
    this.meta.appendChild(this.reasonEl);
    this.meta.appendChild(this.statusPill);

    this.card.appendChild(row);
    this.card.appendChild(this.configContainer);
    this.card.appendChild(this.statsContainer);
    this.card.appendChild(this.meta);
    this.container.appendChild(this.card);

    // 初始化配置组件
    this._initConfigComponent();
    this._initStatsComponent();
    this._updateGating();
  }

  _initConfigComponent() {
    this.configComponent = new AccountRowConfig(this.configContainer, {
      locked: isLockedStatus(this._taskStatus),
      onChange: (config) => {
        // 配置变化时的回调（可用于未来的持久化）
      },
      onCopy: (config) => {
        configClipboard.copy(config);
        this._showCopyFeedback();
      },
      onPaste: () => {
        const config = configClipboard.paste();
        if (config) {
          this.configComponent.setConfig(config);
          this._showPasteFeedback();
        }
      },
      canPaste: () => configClipboard.hasContent(),
    });

    // 订阅剪贴板变化，更新 Paste 按钮状态
    this._unsubscribeClipboard = configClipboard.subscribe(() => {
      this.configComponent.refreshPasteAvailability();
    });
  }

  _initStatsComponent() {
    this.statsComponent = new AccountRowStats(this.statsContainer, {
      getSettings: () => this.getSettings(),
      getHandle: () => this.getHandle(),
    });
  }

  _showCopyFeedback() {
    const copyBtn = this.configContainer.querySelector(".config-copy-btn");
    if (copyBtn) {
      const originalText = copyBtn.innerHTML;
      copyBtn.innerHTML = '<span class="btn-icon">✓</span> Copied';
      copyBtn.classList.add("btn-success");
      setTimeout(() => {
        copyBtn.innerHTML = originalText;
        copyBtn.classList.remove("btn-success");
      }, 1500);
    }
  }

  _showPasteFeedback() {
    const pasteBtn = this.configContainer.querySelector(".config-paste-btn");
    if (pasteBtn) {
      const originalText = pasteBtn.innerHTML;
      pasteBtn.innerHTML = '<span class="btn-icon">✓</span> Pasted';
      pasteBtn.classList.add("btn-success");
      setTimeout(() => {
        pasteBtn.innerHTML = originalText;
        pasteBtn.classList.remove("btn-success");
      }, 1500);
    }
  }

  _onStart(kind) {
    const settings = this.getSettings();
    const credsOk = Boolean(settings?.credentials?.configured);
    if (!credsOk) {
      this._setStatus("Blocked", "btn btn-danger");
      this.reasonEl.textContent = "凭证未配置，无法启动任务";
      return;
    }
    if (!this._validation.valid) {
      this._setStatus("Blocked", "btn btn-danger");
      this.reasonEl.textContent = this._validation.error || "URL 无效";
      return;
    }
    const handle = this._validation.handle;
    const config = this.getConfig() || {};

    if (kind === "start") {
      // For Start New, check if there are existing files first
      this._checkExistingAndStart(handle, config);
    } else {
      // For Continue, proceed directly
      this._startOrContinue(kind, { handle, config });
    }
  }

  async _checkExistingAndStart(handle, config) {
    try {
      // Check for existing files
      const res = await fetch(`/api/lifecycle/check/${encodeURIComponent(handle)}`);
      if (!res.ok) {
        const detail = await this._readError(res);
        this.reasonEl.textContent = `检查失败（HTTP ${res.status}）：${detail}`;
        return;
      }

      const info = await res.json();

      if (info.has_files) {
        // Show the Start New modal with three options
        const modal = ConfirmModals.showStartNewModal({
          handle,
          imageCount: info.image_count,
          videoCount: info.video_count,
          onConfirm: async (mode) => {
            // Prepare (delete/pack) then start
            await this._prepareAndStart(handle, config, mode);
          },
          onCancel: () => {
            // User cancelled, do nothing
          },
        });
        document.body.appendChild(modal);
      } else {
        // No existing files, start directly
        this._startOrContinue("start", { handle, config });
      }
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this.reasonEl.textContent = `检查失败（${message}）`;
    }
  }

  async _prepareAndStart(handle, config, mode) {
    try {
      // Perform the prepare operation (delete/pack/ignore)
      const prepRes = await fetch("/api/lifecycle/prepare-start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle, mode }),
      });

      if (!prepRes.ok) {
        const detail = await this._readError(prepRes);
        this.reasonEl.textContent = `准备失败（HTTP ${prepRes.status}）：${detail}`;
        return;
      }

      // Now start the task
      this._startOrContinue("start", { handle, config, startMode: mode });
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this.reasonEl.textContent = `准备失败（${message}）`;
    }
  }

  async _startOrContinue(kind, { handle, config, startMode }) {
    const endpoint = kind === "continue" ? "/api/scheduler/continue" : "/api/scheduler/start";
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle: handle, account_config: config, start_mode: startMode }),
      });
      if (!res.ok) {
        const detail = await this._readError(res);
        if (res.status === 409) {
          this.reasonEl.textContent = `该账号已有活跃任务：${detail}`;
          return;
        }
        this.reasonEl.textContent = `启动失败（HTTP ${res.status}）：${detail}`;
        return;
      }
      const data = await res.json();
      this._queuedPosition = data.queued_position ?? null;
      this.setTaskStatus(data.status);
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this.reasonEl.textContent = `启动失败（${message}）`;
    }
  }

  async _onCancel() {
    if (!isLockedStatus(this._taskStatus)) return;
    const handle = this._validation.handle;
    if (!handle) return;

    if (this._taskStatus === TaskStatus.RUNNING) {
      // Running tasks require confirmation with Keep/Delete options
      const modal = ConfirmModals.showCancelRunningModal({
        handle,
        onConfirm: async (mode) => {
          await this._performCancel(handle, mode);
        },
        onCancel: () => {
          // User cancelled the dialog, do nothing
        },
      });
      document.body.appendChild(modal);
    } else {
      // Queued tasks cancel immediately without modal
      await this._performCancel(handle, null);
    }
  }

  async _performCancel(handle, cancelMode) {
    try {
      // First cancel the task in the scheduler
      const res = await fetch("/api/scheduler/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle }),
      });
      if (!res.ok) {
        const detail = await this._readError(res);
        this.reasonEl.textContent = `取消失败（HTTP ${res.status}）：${detail}`;
        return;
      }
      const data = await res.json();
      this._queuedPosition = data.queued_position ?? null;
      this.setTaskStatus(data.status);

      // If a cancel mode was specified and it's DELETE, clean up files
      if (cancelMode === ConfirmModals.CancelMode.DELETE) {
        try {
          const cleanupRes = await fetch("/api/lifecycle/prepare-cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ handle, mode: cancelMode }),
          });
          if (!cleanupRes.ok) {
            const detail = await this._readError(cleanupRes);
            this.reasonEl.textContent = `任务已取消，但删除文件失败（HTTP ${cleanupRes.status}）：${detail}`;
          }
        } catch (cleanupErr) {
          // Log but don't fail the cancel operation
          console.error("Cleanup failed:", cleanupErr);
          this.reasonEl.textContent = `任务已取消，但删除文件失败：${cleanupErr.message || cleanupErr}`;
        }
      }
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this.reasonEl.textContent = `取消失败（${message}）`;
    }
  }

  _setStatus(text, className = "pill") {
    this.statusPill.textContent = text;
    this.statusPill.className = `pill ${className}`.trim();
  }

  /**
   * 设置任务状态
   * @param {string} status - TaskStatus 枚举值
   */
  setTaskStatus(status) {
    this._taskStatus = status;
    if (!isLockedStatus(status)) this._queuedPosition = null;
    this._updateGating();
    // 更新配置组件锁定状态
    if (this.configComponent) {
      this.configComponent.setLocked(isLockedStatus(status));
    }
  }

  /**
   * 获取任务状态
   * @returns {string}
   */
  getTaskStatus() {
    return this._taskStatus;
  }

  getHandle() {
    return this._validation?.valid ? this._validation.handle : null;
  }

  applyBackendState(state) {
    if (!state || state.handle !== this._validation.handle) return;
    this._queuedPosition = state.queued_position ?? null;
    this.setTaskStatus(state.status);
    if (this.statsComponent) this.statsComponent.applyBackendState(state);
  }

  /**
   * 获取当前配置
   * @returns {AccountConfig}
   */
  getConfig() {
    return this.configComponent ? this.configComponent.getConfig() : null;
  }

  /**
   * 设置配置
   * @param {AccountConfig} config
   */
  setConfig(config) {
    if (this.configComponent) {
      this.configComponent.setConfig(config);
    }
  }

  _updateGating() {
    const settings = this.getSettings();
    const credsOk = Boolean(settings?.credentials?.configured);
    const isLocked = isLockedStatus(this._taskStatus);

    let disabled = false;
    let reason = "";

    if (isLocked) {
      disabled = true;
      if (this._taskStatus === TaskStatus.QUEUED && this._queuedPosition) {
        reason = `任务排队中（#${this._queuedPosition}）`;
      } else {
        reason = this._taskStatus === TaskStatus.QUEUED ? "任务排队中" : "任务运行中";
      }
    } else if (!credsOk) {
      disabled = true;
      reason = "凭证未配置：请先在 Global Settings 中填写 auth_token/ct0";
    } else if (!this._validation.valid) {
      disabled = true;
      reason = this._validation.error || "URL 无效";
    }

    this.startBtn.disabled = disabled;
    this.continueBtn.disabled = disabled;
    this.cancelBtn.disabled = !isLocked;
    this.reasonEl.textContent = reason;

    // 更新状态标签
    if (isLocked) {
      this._setStatus(this._taskStatus, this._taskStatus === TaskStatus.RUNNING ? "pill running" : "pill queued");
    } else if (disabled) {
      this._setStatus("Idle", "muted");
    } else {
      // 非锁定且非禁用状态：显示完成/取消/失败/空闲
      const statusClassMap = {
        [TaskStatus.DONE]: "completed",
        [TaskStatus.CANCELLED]: "cancelled",
        [TaskStatus.FAILED]: "failed",
        [TaskStatus.IDLE]: "",
      };
      const statusClass = statusClassMap[this._taskStatus] ?? "";
      this._setStatus(this._taskStatus, statusClass);
    }

    // 锁定时禁用 URL 输入
    if (this.urlInput) {
      this.urlInput.setDisabled(isLocked);
    }

    if (this.statsComponent) this.statsComponent.refresh();
  }

  async _readError(res) {
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") return data.detail;
      return JSON.stringify(data);
    } catch (e) {
      try {
        return await res.text();
      } catch (e2) {
        return "未知错误";
      }
    }
  }

  /**
   * 清理资源
   */
  destroy() {
    if (this._unsubscribeClipboard) {
      this._unsubscribeClipboard();
      this._unsubscribeClipboard = null;
    }
  }
}

class AccountsPanel {
  constructor(container, { getSettings }) {
    this.container = container;
    this.getSettings = getSettings;
    this.rows = [];
    this._render();
    this._startSchedulerPolling();
  }

  _render() {
    const toolbar = el("div", { class: "accounts-toolbar" });
    const left = el("div", { class: "hint", text: "提示：这里只是最小 UI 骨架，用于验证全局设置联动。" });
    const addBtn = el("button", { class: "btn", text: "Add Row", onclick: () => this.addRow() });
    toolbar.appendChild(left);
    toolbar.appendChild(addBtn);

    this.list = el("div", { class: "accounts-list" });
    this.container.appendChild(toolbar);
    this.container.appendChild(this.list);

    this.addRow();
  }

  addRow() {
    const row = new AccountRow(this.list, { getSettings: this.getSettings });
    this.rows.push(row);
  }

  refreshGating() {
    for (const row of this.rows) row._updateGating();
  }

  _startSchedulerPolling() {
    const tick = async () => {
      let data = null;
      try {
        const res = await fetch("/api/scheduler/state");
        if (!res.ok) return;
        data = await res.json();
      } catch (e) {
        return;
      }

      const byHandle = new Map();
      for (const h of data?.handles || []) {
        if (h?.handle) byHandle.set(h.handle, h);
      }

      for (const row of this.rows) {
        const handle = row.getHandle();
        if (!handle) continue;
        const state = byHandle.get(handle);
        if (state) row.applyBackendState(state);
      }
    };

    // 轮询足够支撑本任务验收（SSE 将在后续任务完善）。
    setInterval(tick, 800);
  }
}

(async function main() {
  const settingsContainer = document.getElementById("global-settings");
  const accountsContainer = document.getElementById("accounts");

  let settings = null;

  const accountsPanel = new AccountsPanel(accountsContainer, { getSettings: () => settings });

  const settingsPanel = new GlobalSettingsPanel(settingsContainer, {
    onChange: (next) => {
      settings = next;
      accountsPanel.refreshGating();
    },
  });

  await settingsPanel.load();
  settings = settingsPanel.getSettings();
  accountsPanel.refreshGating();
})();
