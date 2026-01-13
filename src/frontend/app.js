/* global AccountRowUrlInput, GlobalSettingsPanel */

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

class AccountRow {
  constructor(container, { getSettings }) {
    this.container = container;
    this.getSettings = getSettings;
    this._validation = { valid: false, handle: null, error: "URL 不能为空" };
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

    this.meta = el("div", { class: "account-meta" });
    this.reasonEl = el("div", { class: "reason" });
    this.statusPill = el("div", { class: "pill muted", text: "Idle" });
    this.meta.appendChild(this.reasonEl);
    this.meta.appendChild(this.statusPill);

    this.card.appendChild(row);
    this.card.appendChild(this.meta);
    this.container.appendChild(this.card);

    this._updateGating();
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

  _updateGating() {
    const settings = this.getSettings();
    const credsOk = Boolean(settings?.credentials?.configured);

    let disabled = false;
    let reason = "";

    if (!credsOk) {
      disabled = true;
      reason = "凭证未配置：请先在 Global Settings 中填写 auth_token/ct0";
    } else if (!this._validation.valid) {
      disabled = true;
      reason = this._validation.error || "URL 无效";
    }

    this.startBtn.disabled = disabled;
    this.continueBtn.disabled = disabled;
    this.reasonEl.textContent = reason;
    if (disabled) this._setStatus("Idle", "muted");
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
