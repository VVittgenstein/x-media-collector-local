/* global fetch, AccountRowUrlInput, GlobalSettingsPanel, AccountRowConfig, AccountRowStats, configClipboard */

/**
 * Helper to create DOM elements
 */
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
 * Show a toast notification
 */
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const iconMap = {
    success: "check_circle",
    error: "error",
    info: "info",
  };
  const colorMap = {
    success: "text-emerald-400",
    error: "text-red-400",
    info: "text-blue-400",
  };

  const toast = el("div", {
    class: "bg-slate-800 text-white px-4 py-2 rounded-lg shadow-xl text-sm font-medium flex items-center gap-2 toast-enter pointer-events-auto",
  }, [
    el("span", { class: `material-symbols-outlined text-[18px] ${colorMap[type]}`, text: iconMap[type] }),
    el("span", { text: message }),
  ]);

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove("toast-enter");
    toast.classList.add("toast-exit");
    setTimeout(() => toast.remove(), 200);
  }, 2000);
}

/**
 * Task status enumeration
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
 * Check if task is locked (cannot edit config)
 */
function isLockedStatus(status) {
  return status === TaskStatus.QUEUED || status === TaskStatus.RUNNING;
}

/**
 * AccountRow - Individual account row component
 */
class AccountRow {
  constructor(container, { getSettings, onDelete }) {
    this.container = container;
    this.getSettings = getSettings;
    this.onDelete = onDelete;
    this._validation = { valid: false, handle: null, error: "URL cannot be empty" };
    this._taskStatus = TaskStatus.IDLE;
    this._queuedPosition = null;
    this._unsubscribeClipboard = null;
    this._render();
  }

  _render() {
    this.card = el("div", { class: "account-row bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 group" });

    // Main Row Content
    const mainRow = el("div", { class: "flex flex-col md:flex-row items-start md:items-center p-4 gap-4" });

    // 1. URL Input Section
    const urlSection = el("div", { class: "flex-1 w-full md:w-auto min-w-[240px]" });
    this.urlContainer = el("div", { class: "url-input-wrapper" });
    this.urlInput = new AccountRowUrlInput(this.urlContainer, {
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
    urlSection.appendChild(this.urlContainer);
    mainRow.appendChild(urlSection);

    // 2. Status & Config Section
    const statusSection = el("div", { class: "flex items-center gap-3 w-full md:w-auto shrink-0" });

    // Status pill
    this.statusPill = el("span", { class: "status-pill status-idle", text: "Idle" });
    statusSection.appendChild(this.statusPill);

    // Config toggle + summary
    const configToggle = el("div", { class: "flex items-center gap-1 bg-slate-50 rounded-lg p-1 border border-slate-100" });
    this.btnConfigToggle = el("button", {
      class: "p-1.5 rounded hover:bg-white hover:shadow-sm text-slate-400 hover:text-blue-600 transition",
      title: "Expand Config",
    }, [el("span", { class: "material-symbols-outlined text-[18px]", text: "tune" })]);
    configToggle.appendChild(this.btnConfigToggle);
    configToggle.appendChild(el("div", { class: "w-px h-4 bg-slate-200" }));
    this.configSummary = el("span", { class: "config-summary text-[10px] font-medium text-slate-500 px-1 truncate max-w-[80px]", text: "Default" });
    configToggle.appendChild(this.configSummary);
    statusSection.appendChild(configToggle);
    mainRow.appendChild(statusSection);

    // 3. Actions Section
    const actionsSection = el("div", { class: "actions-container flex items-center gap-1 w-full md:w-auto justify-end flex-1 ml-auto" });

    // Folder button
    this.btnFolder = el("button", {
      class: "p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition",
      title: "Open Folder",
    }, [el("span", { class: "material-symbols-outlined text-[20px]", text: "folder" })]);
    actionsSection.appendChild(this.btnFolder);

    actionsSection.appendChild(el("div", { class: "w-px h-5 bg-slate-200 mx-1" }));

    // Copy button
    this.btnCopy = el("button", {
      class: "p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition",
      title: "Copy Config",
    }, [el("span", { class: "material-symbols-outlined text-[20px]", text: "content_copy" })]);
    actionsSection.appendChild(this.btnCopy);

    // Paste button
    this.btnPaste = el("button", {
      class: "p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed",
      title: "Paste Config",
      disabled: "disabled",
    }, [el("span", { class: "material-symbols-outlined text-[20px]", text: "content_paste" })]);
    actionsSection.appendChild(this.btnPaste);

    actionsSection.appendChild(el("div", { class: "w-px h-5 bg-slate-200 mx-1" }));

    // Main action button (Start/Continue/Stop)
    this.btnMain = el("button", {
      class: "flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition shadow-sm hover:shadow active:scale-95 disabled:opacity-50 mx-1",
    }, [
      el("span", { class: "material-symbols-outlined text-[18px] action-icon", text: "play_arrow" }),
      el("span", { class: "action-text", text: "Start" }),
    ]);
    actionsSection.appendChild(this.btnMain);

    // Delete button
    this.btnDelete = el("button", {
      class: "p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition disabled:opacity-30",
      title: "Delete Row",
    }, [el("span", { class: "material-symbols-outlined text-[20px]", text: "delete" })]);
    actionsSection.appendChild(this.btnDelete);

    mainRow.appendChild(actionsSection);
    this.card.appendChild(mainRow);

    // Config Panel (collapsible)
    this.configContainer = el("div", { class: "config-panel hidden border-t border-slate-100 bg-slate-50/50 animate-fade-in" });
    this.card.appendChild(this.configContainer);

    // Stats Section (inside config panel or separate)
    this.statsContainer = el("div", { class: "stats-container" });

    // Meta/Reason Section
    this.reasonEl = el("div", { class: "px-4 pb-2 text-xs text-slate-500 hidden" });
    this.card.appendChild(this.reasonEl);

    this.container.appendChild(this.card);

    // Initialize sub-components
    this._initConfigComponent();
    this._initStatsComponent();
    this._bindEvents();
    this._updateGating();
  }

  _initConfigComponent() {
    this.configComponent = new AccountRowConfig(this.configContainer, {
      locked: isLockedStatus(this._taskStatus),
      onChange: (config) => {
        this._updateConfigSummary();
      },
      onCopy: (config) => {
        configClipboard.copy(config);
        showToast("Config copied!", "success");
      },
      onPaste: () => {
        const config = configClipboard.paste();
        if (config) {
          this.configComponent.setConfig(config);
          this._updateConfigSummary();
          showToast("Config pasted!", "success");
        }
      },
      canPaste: () => configClipboard.hasContent(),
    });

    this._unsubscribeClipboard = configClipboard.subscribe(() => {
      this._updatePasteButton();
      this.configComponent.refreshPasteAvailability();
    });

    this._updateConfigSummary();
  }

  _initStatsComponent() {
    this.statsComponent = new AccountRowStats(this.statsContainer, {
      getSettings: () => this.getSettings(),
      getHandle: () => this.getHandle(),
    });
  }

  _bindEvents() {
    // Config toggle
    this.btnConfigToggle.onclick = () => {
      this.configContainer.classList.toggle("hidden");
    };

    // Folder
    this.btnFolder.onclick = () => {
      if (this.statsComponent) {
        this.statsComponent._onOpenFolder();
      }
    };

    // Copy
    this.btnCopy.onclick = () => {
      if (this.configComponent) {
        const config = this.configComponent.getConfig();
        configClipboard.copy(config);
        showToast("Config copied!", "success");
      }
    };

    // Paste
    this.btnPaste.onclick = () => {
      if (isLockedStatus(this._taskStatus)) return;
      if (!configClipboard.hasContent()) return;
      const config = configClipboard.paste();
      if (config && this.configComponent) {
        this.configComponent.setConfig(config);
        this._updateConfigSummary();
        showToast("Config pasted!", "success");
      }
    };

    // Main action
    this.btnMain.onclick = () => {
      if (isLockedStatus(this._taskStatus)) {
        this._onCancel();
      } else {
        this._onStart("start");
      }
    };

    // Delete
    this.btnDelete.onclick = () => this._onDeleteClick();
  }

  _updateConfigSummary() {
    if (!this.configComponent) return;
    const config = this.configComponent.getConfig();
    let summary = "Default";

    // Build summary based on config
    const parts = [];
    if (config.mediaType === "images") parts.push("Images");
    else if (config.mediaType === "videos") parts.push("Videos");
    else parts.push("All");

    if (config.startDate || config.endDate) parts.push("Date");
    if (config.minShortSide && config.minShortSide > 0) parts.push(`>${config.minShortSide}px`);

    summary = parts.length > 0 ? parts.join(", ") : "Default";
    this.configSummary.textContent = summary;
    this.configSummary.title = summary;
  }

  _updatePasteButton() {
    const canPaste = configClipboard.hasContent() && !isLockedStatus(this._taskStatus);
    this.btnPaste.disabled = !canPaste;
    this.btnPaste.title = canPaste ? "Paste Config" : "Copy a config first";
  }

  _onStart(kind) {
    const settings = this.getSettings();
    const credsOk = Boolean(settings?.credentials?.configured);
    if (!credsOk) {
      this._setStatus(TaskStatus.IDLE);
      this._showReason("Credentials not configured. Please configure in Global Settings.");
      return;
    }
    if (!this._validation.valid) {
      this._setStatus(TaskStatus.IDLE);
      this._showReason(this._validation.error || "Invalid URL");
      return;
    }
    const handle = this._validation.handle;
    const config = this.getConfig() || {};

    if (kind === "start") {
      this._checkExistingAndStart(handle, config);
    } else {
      this._startOrContinue(kind, { handle, config });
    }
  }

  async _checkExistingAndStart(handle, config) {
    try {
      const res = await fetch(`/api/lifecycle/check/${encodeURIComponent(handle)}`);
      if (!res.ok) {
        const detail = await this._readError(res);
        this._showReason(`Check failed (HTTP ${res.status}): ${detail}`);
        return;
      }

      const info = await res.json();

      if (info.has_files) {
        const modal = ConfirmModals.showStartNewModal({
          handle,
          imageCount: info.image_count,
          videoCount: info.video_count,
          onConfirm: async (mode) => {
            await this._prepareAndStart(handle, config, mode);
          },
          onCancel: () => {},
        });
        document.body.appendChild(modal);
      } else {
        this._startOrContinue("start", { handle, config });
      }
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._showReason(`Check failed: ${message}`);
    }
  }

  async _prepareAndStart(handle, config, mode) {
    try {
      const prepRes = await fetch("/api/lifecycle/prepare-start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle, mode }),
      });

      if (!prepRes.ok) {
        const detail = await this._readError(prepRes);
        this._showReason(`Prepare failed (HTTP ${prepRes.status}): ${detail}`);
        return;
      }

      this._startOrContinue("start", { handle, config, startMode: mode });
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._showReason(`Prepare failed: ${message}`);
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
          this._showReason(`Account already has active task: ${detail}`);
          return;
        }
        this._showReason(`Start failed (HTTP ${res.status}): ${detail}`);
        return;
      }
      const data = await res.json();
      this._queuedPosition = data.queued_position ?? null;
      this.setTaskStatus(data.status);
      this._hideReason();
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._showReason(`Start failed: ${message}`);
    }
  }

  _onDeleteClick() {
    if (isLockedStatus(this._taskStatus)) return;
    if (this.onDelete) {
      this.onDelete(this);
    }
  }

  async _onCancel() {
    if (!isLockedStatus(this._taskStatus)) return;
    const handle = this._validation.handle;
    if (!handle) return;

    if (this._taskStatus === TaskStatus.RUNNING) {
      const modal = ConfirmModals.showCancelRunningModal({
        handle,
        onConfirm: async (mode) => {
          await this._performCancel(handle, mode);
        },
        onCancel: () => {},
      });
      document.body.appendChild(modal);
    } else {
      await this._performCancel(handle, null);
    }
  }

  async _performCancel(handle, cancelMode) {
    try {
      const res = await fetch("/api/scheduler/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle }),
      });
      if (!res.ok) {
        const detail = await this._readError(res);
        this._showReason(`Cancel failed (HTTP ${res.status}): ${detail}`);
        return;
      }
      const data = await res.json();
      this._queuedPosition = data.queued_position ?? null;
      this.setTaskStatus(data.status);

      if (cancelMode === ConfirmModals.CancelMode.DELETE) {
        try {
          const cleanupRes = await fetch("/api/lifecycle/prepare-cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ handle, mode: cancelMode }),
          });
          if (!cleanupRes.ok) {
            const detail = await this._readError(cleanupRes);
            this._showReason(`Cancelled, but file deletion failed (HTTP ${cleanupRes.status}): ${detail}`);
          }
        } catch (cleanupErr) {
          console.error("Cleanup failed:", cleanupErr);
          this._showReason(`Cancelled, but file deletion failed: ${cleanupErr.message || cleanupErr}`);
        }
      }
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._showReason(`Cancel failed: ${message}`);
    }
  }

  _setStatus(status) {
    this._taskStatus = status;
    const statusLower = status.toLowerCase();
    this.statusPill.className = `status-pill status-${statusLower}`;
    this.statusPill.textContent = status;
  }

  _showReason(text) {
    this.reasonEl.textContent = text;
    this.reasonEl.classList.remove("hidden");
  }

  _hideReason() {
    this.reasonEl.textContent = "";
    this.reasonEl.classList.add("hidden");
  }

  setTaskStatus(status) {
    this._taskStatus = status;
    if (!isLockedStatus(status)) this._queuedPosition = null;
    this._updateGating();
    if (this.configComponent) {
      this.configComponent.setLocked(isLockedStatus(status));
    }
  }

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

  getConfig() {
    return this.configComponent ? this.configComponent.getConfig() : null;
  }

  setConfig(config) {
    if (this.configComponent) {
      this.configComponent.setConfig(config);
      this._updateConfigSummary();
    }
  }

  _updateGating() {
    const settings = this.getSettings();
    const credsOk = Boolean(settings?.credentials?.configured);
    const isLocked = isLockedStatus(this._taskStatus);

    // Update status pill
    this._setStatus(this._taskStatus);

    // Update main button
    const actionIcon = this.btnMain.querySelector(".action-icon");
    const actionText = this.btnMain.querySelector(".action-text");

    if (isLocked) {
      actionIcon.textContent = "stop";
      actionText.textContent = "Stop";
      this.btnMain.classList.remove("bg-slate-800", "hover:bg-slate-700");
      this.btnMain.classList.add("bg-red-600", "hover:bg-red-700");
      this.btnMain.disabled = false;
    } else {
      actionIcon.textContent = "play_arrow";
      actionText.textContent = "Start";
      this.btnMain.classList.remove("bg-red-600", "hover:bg-red-700");
      this.btnMain.classList.add("bg-slate-800", "hover:bg-slate-700");

      // Disable if creds not configured or URL invalid
      const shouldDisable = !credsOk || !this._validation.valid;
      this.btnMain.disabled = shouldDisable;
    }

    // Update delete button
    this.btnDelete.disabled = isLocked;
    this.btnDelete.title = isLocked ? "Cannot delete while task is running" : "Delete Row";

    // Update paste button
    this._updatePasteButton();

    // Lock URL input
    if (this.urlInput) {
      this.urlInput.setDisabled(isLocked);
    }

    // Update reason
    if (!isLocked) {
      if (!credsOk) {
        this._showReason("Credentials not configured. Please configure in Global Settings.");
      } else if (!this._validation.valid) {
        this._showReason(this._validation.error || "Invalid URL");
      } else {
        this._hideReason();
      }
    } else {
      if (this._taskStatus === TaskStatus.QUEUED && this._queuedPosition) {
        this._showReason(`Queued (#${this._queuedPosition})`);
      } else if (this._taskStatus === TaskStatus.QUEUED) {
        this._showReason("Queued");
      } else {
        this._hideReason();
      }
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
        return "Unknown error";
      }
    }
  }

  destroy() {
    if (this._unsubscribeClipboard) {
      this._unsubscribeClipboard();
      this._unsubscribeClipboard = null;
    }
    if (this.card && this.card.parentNode) {
      this.card.parentNode.removeChild(this.card);
    }
  }
}

/**
 * AccountsPanel - Manages list of account rows
 */
class AccountsPanel {
  constructor(container, { getSettings }) {
    this.container = container;
    this.getSettings = getSettings;
    this.rows = [];
    this._render();
    this._startSchedulerPolling();
  }

  _render() {
    this.list = el("div", { class: "accounts-list space-y-3" });
    this.container.appendChild(this.list);
    this.addRow();
  }

  addRow() {
    const row = new AccountRow(this.list, {
      getSettings: this.getSettings,
      onDelete: (rowToDelete) => this.deleteRow(rowToDelete),
    });
    this.rows.push(row);
    this._updateEmptyState();
    return row;
  }

  deleteRow(row) {
    const index = this.rows.indexOf(row);
    if (index === -1) return;

    this.rows.splice(index, 1);
    row.destroy();

    if (this.rows.length === 0) {
      this.addRow();
    }
    this._updateEmptyState();
  }

  _updateEmptyState() {
    const emptyState = document.getElementById("empty-state");
    if (emptyState) {
      if (this.rows.length === 0) {
        emptyState.classList.remove("hidden");
        emptyState.classList.add("flex");
      } else {
        emptyState.classList.add("hidden");
        emptyState.classList.remove("flex");
      }
    }
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

    setInterval(tick, 800);
  }
}

/**
 * Main Application
 */
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

  // Settings panel collapse/expand
  const settingsSection = document.getElementById("global-settings-section");
  const settingsToggleBtn = document.getElementById("settings-toggle");
  const settingsCloseBtn = document.getElementById("settings-close");

  function toggleSettings() {
    const isCollapsed = settingsSection.classList.toggle("collapsed");
    settingsToggleBtn.classList.toggle("active", !isCollapsed);
  }

  settingsToggleBtn.addEventListener("click", toggleSettings);
  settingsCloseBtn.addEventListener("click", () => {
    settingsSection.classList.add("collapsed");
    settingsToggleBtn.classList.remove("active");
  });

  // Add Account button
  const addRowBtn = document.getElementById("btn-add-row");
  if (addRowBtn) {
    addRowBtn.addEventListener("click", () => accountsPanel.addRow());
  }

  // Empty state add button
  const addFirstBtn = document.getElementById("btn-add-first");
  if (addFirstBtn) {
    addFirstBtn.addEventListener("click", () => accountsPanel.addRow());
  }
})();
