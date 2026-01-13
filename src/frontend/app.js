/* global AccountRowUrlInput, GlobalSettingsPanel, AccountRowConfig, configClipboard */

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
  COMPLETED: "Completed",
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
    this._unsubscribeClipboard = null;
    this._render();
  }

  _render() {
    this.card = el("div", { class: "account-card" });
    const row = el("div", { class: "row" });

    const urlContainer = el("div", { style: "flex: 1;" });
    this.urlInput = new AccountRowUrlInput(urlContainer, {
      onValidationChange: (result) => {
        this._validation = result;
        this._updateGating();
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
    actions.appendChild(this.startBtn);
    actions.appendChild(this.continueBtn);

    row.appendChild(urlContainer);
    row.appendChild(actions);

    // 配置组件容器
    this.configContainer = el("div", { class: "account-config-container" });

    this.meta = el("div", { class: "account-meta" });
    this.reasonEl = el("div", { class: "reason" });
    this.statusPill = el("div", { class: "pill muted", text: "Idle" });
    this.meta.appendChild(this.reasonEl);
    this.meta.appendChild(this.statusPill);

    this.card.appendChild(row);
    this.card.appendChild(this.configContainer);
    this.card.appendChild(this.meta);
    this.container.appendChild(this.card);

    // 初始化配置组件
    this._initConfigComponent();
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
    this._setStatus("Not Implemented", "btn");
    this.reasonEl.textContent = `已通过本地前置校验（${kind}）：调度器/Runner 尚未实现`;
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
      reason = this._taskStatus === TaskStatus.QUEUED ? "任务排队中" : "任务运行中";
    } else if (!credsOk) {
      disabled = true;
      reason = "凭证未配置：请先在 Global Settings 中填写 auth_token/ct0";
    } else if (!this._validation.valid) {
      disabled = true;
      reason = this._validation.error || "URL 无效";
    }

    this.startBtn.disabled = disabled;
    this.continueBtn.disabled = disabled;
    this.reasonEl.textContent = reason;

    // 更新状态标签
    if (isLocked) {
      this._setStatus(this._taskStatus, this._taskStatus === TaskStatus.RUNNING ? "pill running" : "pill queued");
    } else if (disabled) {
      this._setStatus("Idle", "muted");
    } else {
      // 非锁定且非禁用状态：显示完成/取消/失败/空闲
      const statusClassMap = {
        [TaskStatus.COMPLETED]: "completed",
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
