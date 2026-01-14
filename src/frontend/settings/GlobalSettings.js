/* global fetch */

class GlobalSettingsPanel {
  constructor(container, { onChange } = {}) {
    this.container = container;
    this.onChange = typeof onChange === "function" ? onChange : null;
    this.settings = null;
    this._renderSkeleton();
  }

  getSettings() {
    return this.settings;
  }

  async load() {
    try {
      const res = await fetch("/api/settings");
      if (!res.ok) {
        this._setBanner("error", `无法加载设置（HTTP ${res.status}）`);
        this._render();
        return;
      }
      const data = await res.json();
      this._applySettings(data);
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._setBanner("error", `无法加载设置（${message}）`);
      this._render();
    }
  }

  _applySettings(next) {
    this.settings = next;
    this._render();
    if (this.onChange) this.onChange(next);
  }

  _renderSkeleton() {
    this.container.innerHTML = `
      <div class="settings-grid">
        <div class="settings-block" data-block="credentials"></div>
        <div class="settings-block" data-block="downloadRoot"></div>
        <div class="settings-block" data-block="maxConcurrent"></div>
      </div>
      <div class="divider"></div>
      <div class="settings-section-title">Rate Limiting &amp; Proxy</div>
      <div class="settings-grid">
        <div class="settings-block" data-block="throttle"></div>
        <div class="settings-block" data-block="retry"></div>
        <div class="settings-block" data-block="proxy"></div>
      </div>
      <div class="divider"></div>
      <div data-el="banner"></div>
    `;
    this.bannerEl = this.container.querySelector('[data-el="banner"]');
    this.credentialsEl = this.container.querySelector('[data-block="credentials"]');
    this.downloadRootEl = this.container.querySelector('[data-block="downloadRoot"]');
    this.maxConcurrentEl = this.container.querySelector('[data-block="maxConcurrent"]');
    this.throttleEl = this.container.querySelector('[data-block="throttle"]');
    this.retryEl = this.container.querySelector('[data-block="retry"]');
    this.proxyEl = this.container.querySelector('[data-block="proxy"]');
  }

  _render() {
    const s = this.settings || {
      credentials: { configured: false, auth_token_set: false, ct0_set: false, twid_set: false },
      download_root: "downloads",
      max_concurrent: 3,
      throttle: { min_interval_s: 1.5, jitter_max_s: 1.0, enabled: true },
      retry: { max_retries: 3, base_delay_s: 2.0, max_delay_s: 60.0, enabled: true },
      proxy: { enabled: false, url_configured: false },
    };

    this._renderCredentials(s);
    this._renderDownloadRoot(s);
    this._renderMaxConcurrent(s);
    this._renderThrottle(s);
    this._renderRetry(s);
    this._renderProxy(s);
  }

  _renderCredentials(settings) {
    const status = settings.credentials;
    const configured = Boolean(status?.configured);

    if (configured) {
      this.credentialsEl.innerHTML = `
        <div class="settings-block-title">Credentials</div>
        <div class="status-line">
          <div class="kv"><b>状态</b>：<span class="ok">已设置</span>（UI 不回显明文）</div>
        </div>
        <div class="status-line">
          <div class="kv"><b>auth_token</b>：${status.auth_token_set ? "已设置" : "未设置"}</div>
          <div class="kv"><b>ct0</b>：${status.ct0_set ? "已设置" : "未设置"}</div>
          <div class="kv"><b>twid</b>：${status.twid_set ? "已设置" : "未设置"}</div>
        </div>
        <div class="actions">
          <button class="btn btn-danger" data-action="clearCreds">清除并重新输入</button>
        </div>
        <div class="help">
          凭证会保存在本地 <code>data/config.json</code>（不加密）。请注意保管，且不要分享该文件。
        </div>
      `;
      this.credentialsEl.querySelector('[data-action="clearCreds"]').addEventListener("click", () => {
        this._clearCredentials();
      });
      return;
    }

    this.credentialsEl.innerHTML = `
      <div class="settings-block-title">Credentials</div>
      <div class="form-row">
        <div class="label">auth_token *</div>
        <div>
          <input class="input" type="password" autocomplete="off" spellcheck="false" data-el="authToken" placeholder="来自 Cookie: auth_token" />
          <div class="help">必填：来自浏览器 Cookie <code>auth_token</code>。</div>
        </div>
      </div>
      <div class="form-row">
        <div class="label">ct0 *</div>
        <div>
          <input class="input" type="password" autocomplete="off" spellcheck="false" data-el="ct0" placeholder="来自 Cookie: ct0" />
          <div class="help">必填：来自浏览器 Cookie <code>ct0</code>（CSRF token）。</div>
        </div>
      </div>
      <div class="form-row">
        <div class="label">twid</div>
        <div>
          <input class="input" type="password" autocomplete="off" spellcheck="false" data-el="twid" placeholder="可选：来自 Cookie: twid" />
          <div class="help">可选：用于调试（非必需）。</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" data-action="saveCreds">保存</button>
      </div>
      <div class="help">
        如何获取：登录 <code>x.com</code> → 按 <code>F12</code> → Application → Cookies → <code>x.com</code> → 找到 <code>auth_token</code>/<code>ct0</code>。
      </div>
    `;

    this.credentialsEl.querySelector('[data-action="saveCreds"]').addEventListener("click", () => {
      this._saveCredentials();
    });
  }

  _renderDownloadRoot(settings) {
    this.downloadRootEl.innerHTML = `
      <div class="settings-block-title">Download Root</div>
      <div class="form-row">
        <div class="label">Path</div>
        <div>
          <input class="input" type="text" autocomplete="off" spellcheck="false" data-el="downloadRoot" />
          <div class="help">所有账号输出都会落在该目录下：<code>&lt;root&gt;/&lt;handle&gt;/{images|videos}/</code></div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" data-action="saveRoot">保存</button>
      </div>
    `;
    const input = this.downloadRootEl.querySelector('[data-el="downloadRoot"]');
    input.value = settings.download_root || "";
    this.downloadRootEl.querySelector('[data-action="saveRoot"]').addEventListener("click", () => {
      this._saveDownloadRoot(input.value);
    });
  }

  _renderMaxConcurrent(settings) {
    this.maxConcurrentEl.innerHTML = `
      <div class="settings-block-title">Max Concurrent</div>
      <div class="form-row">
        <div class="label">Value</div>
        <div>
          <input class="input" type="number" min="1" max="100" step="1" data-el="maxConcurrent" />
          <div class="help">默认 3；修改后立即影响调度器的并发上限（MVP）。</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" data-action="saveMax">保存</button>
      </div>
    `;
    const input = this.maxConcurrentEl.querySelector('[data-el="maxConcurrent"]');
    input.value = String(settings.max_concurrent ?? 3);
    this.maxConcurrentEl.querySelector('[data-action="saveMax"]').addEventListener("click", () => {
      this._saveMaxConcurrent(input.value);
    });
  }

  _renderThrottle(settings) {
    const t = settings.throttle || { min_interval_s: 1.5, jitter_max_s: 1.0, enabled: true };
    this.throttleEl.innerHTML = `
      <div class="settings-block-title">Throttle (Request Spacing)</div>
      <div class="form-row">
        <div class="label">Enabled</div>
        <div>
          <label class="checkbox-label">
            <input type="checkbox" data-el="throttleEnabled" ${t.enabled ? "checked" : ""} />
            <span>Enable request throttling</span>
          </label>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Min Interval (s)</div>
        <div>
          <input class="input" type="number" min="0" max="60" step="0.1" data-el="minInterval" value="${t.min_interval_s}" />
          <div class="help">Minimum seconds between requests (default: 1.5s)</div>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Jitter Max (s)</div>
        <div>
          <input class="input" type="number" min="0" max="30" step="0.1" data-el="jitterMax" value="${t.jitter_max_s}" />
          <div class="help">Random delay added to min interval (default: 1.0s)</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" data-action="saveThrottle">保存</button>
      </div>
      <div class="help">Conservative defaults to avoid rate limiting. Adjust based on your experience.</div>
    `;
    this.throttleEl.querySelector('[data-action="saveThrottle"]').addEventListener("click", () => {
      this._saveThrottle();
    });
  }

  _renderRetry(settings) {
    const r = settings.retry || { max_retries: 3, base_delay_s: 2.0, max_delay_s: 60.0, enabled: true };
    this.retryEl.innerHTML = `
      <div class="settings-block-title">Retry (Exponential Backoff)</div>
      <div class="form-row">
        <div class="label">Enabled</div>
        <div>
          <label class="checkbox-label">
            <input type="checkbox" data-el="retryEnabled" ${r.enabled ? "checked" : ""} />
            <span>Enable retry on 429/5xx errors</span>
          </label>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Max Retries</div>
        <div>
          <input class="input" type="number" min="0" max="10" step="1" data-el="maxRetries" value="${r.max_retries}" />
          <div class="help">Maximum retry attempts (default: 3)</div>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Base Delay (s)</div>
        <div>
          <input class="input" type="number" min="0.1" max="60" step="0.1" data-el="baseDelay" value="${r.base_delay_s}" />
          <div class="help">Initial delay before first retry (default: 2.0s)</div>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Max Delay (s)</div>
        <div>
          <input class="input" type="number" min="1" max="300" step="1" data-el="maxDelay" value="${r.max_delay_s}" />
          <div class="help">Maximum delay cap (default: 60s)</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" data-action="saveRetry">保存</button>
      </div>
      <div class="help">Exponential backoff: delay doubles each retry up to max delay.</div>
    `;
    this.retryEl.querySelector('[data-action="saveRetry"]').addEventListener("click", () => {
      this._saveRetry();
    });
  }

  _renderProxy(settings) {
    const p = settings.proxy || { enabled: false, url_configured: false };
    this.proxyEl.innerHTML = `
      <div class="settings-block-title">Proxy (Optional)</div>
      <div class="form-row">
        <div class="label">Enabled</div>
        <div>
          <label class="checkbox-label">
            <input type="checkbox" data-el="proxyEnabled" ${p.enabled ? "checked" : ""} />
            <span>Route requests through proxy</span>
          </label>
        </div>
      </div>
      <div class="form-row">
        <div class="label">Proxy URL</div>
        <div>
          <input class="input" type="text" autocomplete="off" spellcheck="false" data-el="proxyUrl" placeholder="http://host:port or socks5://host:port" />
          <div class="help">
            ${p.url_configured ? '<span class="ok">Proxy URL configured</span>' : '<span class="muted">Not configured</span>'}
            (supports http, https, socks4, socks5)
          </div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" data-action="saveProxy">保存</button>
        <button class="btn btn-danger" data-action="clearProxy">清除</button>
      </div>
      <div class="help">Use proxy to avoid rate limiting or access restrictions. URL not shown after saving.</div>
    `;
    this.proxyEl.querySelector('[data-action="saveProxy"]').addEventListener("click", () => {
      this._saveProxy();
    });
    this.proxyEl.querySelector('[data-action="clearProxy"]').addEventListener("click", () => {
      this._clearProxy();
    });
  }

  _setBanner(kind, message) {
    if (!message) {
      this.bannerEl.innerHTML = "";
      return;
    }
    const className = kind === "ok" ? "ok" : kind === "error" ? "error" : "muted";
    this.bannerEl.innerHTML = `<div class="${className}">${message}</div>`;
  }

  async _saveCredentials() {
    const authToken = (this.credentialsEl.querySelector('[data-el="authToken"]')?.value || "").trim();
    const ct0 = (this.credentialsEl.querySelector('[data-el="ct0"]')?.value || "").trim();
    const twidRaw = (this.credentialsEl.querySelector('[data-el="twid"]')?.value || "").trim();

    if (!authToken || !ct0) {
      this._setBanner("error", "auth_token 与 ct0 为必填");
      return;
    }

    const res = await fetch("/api/settings/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auth_token: authToken, ct0: ct0, twid: twidRaw || null }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }

    const data = await res.json();
    this._setBanner("ok", "已保存：凭证不会在 UI 明文回显");
    this._applySettings(data);
  }

  async _clearCredentials() {
    const res = await fetch("/api/settings/credentials", { method: "DELETE" });
    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `清除失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "已清除凭证");
    this._applySettings(data);
  }

  async _saveDownloadRoot(value) {
    const res = await fetch("/api/settings/download-root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ download_root: value }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Download Root 已更新");
    this._applySettings(data);
  }

  async _saveMaxConcurrent(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 1 || n > 100 || !Number.isInteger(n)) {
      this._setBanner("error", "Max Concurrent 必须是 1-100 的整数");
      return;
    }

    const res = await fetch("/api/settings/max-concurrent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_concurrent: n }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Max Concurrent 已更新");
    this._applySettings(data);
  }

  async _saveThrottle() {
    const enabled = this.throttleEl.querySelector('[data-el="throttleEnabled"]')?.checked ?? true;
    const minInterval = Number(this.throttleEl.querySelector('[data-el="minInterval"]')?.value ?? 1.5);
    const jitterMax = Number(this.throttleEl.querySelector('[data-el="jitterMax"]')?.value ?? 1.0);

    if (!Number.isFinite(minInterval) || minInterval < 0 || minInterval > 60) {
      this._setBanner("error", "Min Interval must be 0-60 seconds");
      return;
    }
    if (!Number.isFinite(jitterMax) || jitterMax < 0 || jitterMax > 30) {
      this._setBanner("error", "Jitter Max must be 0-30 seconds");
      return;
    }

    const res = await fetch("/api/settings/throttle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ min_interval_s: minInterval, jitter_max_s: jitterMax, enabled }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Throttle settings updated");
    this._applySettings(data);
  }

  async _saveRetry() {
    const enabled = this.retryEl.querySelector('[data-el="retryEnabled"]')?.checked ?? true;
    const maxRetries = Number(this.retryEl.querySelector('[data-el="maxRetries"]')?.value ?? 3);
    const baseDelay = Number(this.retryEl.querySelector('[data-el="baseDelay"]')?.value ?? 2.0);
    const maxDelay = Number(this.retryEl.querySelector('[data-el="maxDelay"]')?.value ?? 60.0);

    if (!Number.isFinite(maxRetries) || maxRetries < 0 || maxRetries > 10 || !Number.isInteger(maxRetries)) {
      this._setBanner("error", "Max Retries must be 0-10 (integer)");
      return;
    }
    if (!Number.isFinite(baseDelay) || baseDelay < 0.1 || baseDelay > 60) {
      this._setBanner("error", "Base Delay must be 0.1-60 seconds");
      return;
    }
    if (!Number.isFinite(maxDelay) || maxDelay < 1 || maxDelay > 300) {
      this._setBanner("error", "Max Delay must be 1-300 seconds");
      return;
    }

    const res = await fetch("/api/settings/retry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_retries: maxRetries, base_delay_s: baseDelay, max_delay_s: maxDelay, enabled }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Retry settings updated");
    this._applySettings(data);
  }

  async _saveProxy() {
    const enabled = this.proxyEl.querySelector('[data-el="proxyEnabled"]')?.checked ?? false;
    const url = (this.proxyEl.querySelector('[data-el="proxyUrl"]')?.value || "").trim();

    if (enabled && !url) {
      this._setBanner("error", "Proxy URL is required when enabled");
      return;
    }

    const res = await fetch("/api/settings/proxy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, url }),
    });

    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `保存失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Proxy settings updated");
    this._applySettings(data);
  }

  async _clearProxy() {
    const res = await fetch("/api/settings/proxy", { method: "DELETE" });
    if (!res.ok) {
      const detail = await this._readError(res);
      this._setBanner("error", `清除失败（HTTP ${res.status}）：${detail}`);
      return;
    }
    const data = await res.json();
    this._setBanner("ok", "Proxy settings cleared");
    this._applySettings(data);
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
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { GlobalSettingsPanel };
} else {
  window.GlobalSettingsPanel = GlobalSettingsPanel;
}
