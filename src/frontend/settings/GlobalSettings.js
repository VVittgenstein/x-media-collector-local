/* global fetch, showToast */

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
        this._setBanner("error", `Failed to load settings (HTTP ${res.status})`);
        this._render();
        return;
      }
      const data = await res.json();
      this._applySettings(data);
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._setBanner("error", `Failed to load settings: ${message}`);
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
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="credentials"></div>
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="downloadRoot"></div>
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="maxConcurrent"></div>
      </div>
      <div class="border-t border-slate-200 my-6"></div>
      <h3 class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
        <span class="material-symbols-outlined text-lg text-slate-400">speed</span>
        Rate Limiting &amp; Proxy
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="throttle"></div>
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="retry"></div>
        <div class="bg-white border border-slate-200 rounded-xl p-4" data-block="proxy"></div>
      </div>
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
        <div class="flex items-center gap-2 mb-3">
          <span class="material-symbols-outlined text-lg text-emerald-500">verified_user</span>
          <h4 class="text-sm font-bold text-slate-700">Credentials</h4>
          <span class="ml-auto px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Configured</span>
        </div>
        <div class="space-y-1 text-xs text-slate-600 mb-3">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-sm ${status.auth_token_set ? "text-emerald-500" : "text-slate-300"}">check_circle</span>
            <span>auth_token</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-sm ${status.ct0_set ? "text-emerald-500" : "text-slate-300"}">check_circle</span>
            <span>ct0</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-sm ${status.twid_set ? "text-emerald-500" : "text-slate-300"}">check_circle</span>
            <span>twid</span>
          </div>
        </div>
        <button class="w-full px-3 py-2 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition" data-action="clearCreds">
          Clear &amp; Re-enter
        </button>
        <p class="mt-3 text-[10px] text-slate-400">
          Stored in <code class="bg-slate-100 px-1 rounded">data/config.json</code> (unencrypted).
        </p>
      `;
      this.credentialsEl.querySelector('[data-action="clearCreds"]').addEventListener("click", () => {
        this._clearCredentials();
      });
      return;
    }

    this.credentialsEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-amber-500">key</span>
        <h4 class="text-sm font-bold text-slate-700">Credentials</h4>
        <span class="ml-auto px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">Required</span>
      </div>
      <div class="space-y-3">
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">auth_token *</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="password" autocomplete="off" spellcheck="false" data-el="authToken" placeholder="From Cookie: auth_token" />
        </div>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">ct0 *</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="password" autocomplete="off" spellcheck="false" data-el="ct0" placeholder="From Cookie: ct0" />
        </div>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">twid (optional)</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="password" autocomplete="off" spellcheck="false" data-el="twid" placeholder="From Cookie: twid" />
        </div>
      </div>
      <button class="w-full mt-4 px-3 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition" data-action="saveCreds">
        Save Credentials
      </button>
      <p class="mt-3 text-[10px] text-slate-400">
        Get from: x.com &rarr; F12 &rarr; Application &rarr; Cookies &rarr; x.com
      </p>
    `;

    this.credentialsEl.querySelector('[data-action="saveCreds"]').addEventListener("click", () => {
      this._saveCredentials();
    });
  }

  _renderDownloadRoot(settings) {
    this.downloadRootEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-blue-500">folder</span>
        <h4 class="text-sm font-bold text-slate-700">Download Root</h4>
      </div>
      <div class="space-y-3">
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Path</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="text" autocomplete="off" spellcheck="false" data-el="downloadRoot" />
        </div>
      </div>
      <button class="w-full mt-4 px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition" data-action="saveRoot">
        Save
      </button>
      <p class="mt-3 text-[10px] text-slate-400">
        Output: <code class="bg-slate-100 px-1 rounded">&lt;root&gt;/&lt;handle&gt;/{images|videos}/</code>
      </p>
    `;
    const input = this.downloadRootEl.querySelector('[data-el="downloadRoot"]');
    input.value = settings.download_root || "";
    this.downloadRootEl.querySelector('[data-action="saveRoot"]').addEventListener("click", () => {
      this._saveDownloadRoot(input.value);
    });
  }

  _renderMaxConcurrent(settings) {
    this.maxConcurrentEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-purple-500">stacks</span>
        <h4 class="text-sm font-bold text-slate-700">Max Concurrent</h4>
      </div>
      <div class="space-y-3">
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Value</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="1" max="100" step="1" data-el="maxConcurrent" />
        </div>
      </div>
      <button class="w-full mt-4 px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition" data-action="saveMax">
        Save
      </button>
      <p class="mt-3 text-[10px] text-slate-400">
        Default: 3. Changes apply immediately to scheduler.
      </p>
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
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-orange-500">timer</span>
        <h4 class="text-sm font-bold text-slate-700">Throttle</h4>
      </div>
      <div class="space-y-3">
        <label class="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input type="checkbox" class="accent-blue-600" data-el="throttleEnabled" ${t.enabled ? "checked" : ""} />
          <span>Enable request throttling</span>
        </label>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Min Interval (s)</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="0" max="60" step="0.1" data-el="minInterval" value="${t.min_interval_s}" />
        </div>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Jitter Max (s)</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="0" max="30" step="0.1" data-el="jitterMax" value="${t.jitter_max_s}" />
        </div>
      </div>
      <button class="w-full mt-4 px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition" data-action="saveThrottle">
        Save
      </button>
      <p class="mt-3 text-[10px] text-slate-400">
        Conservative defaults to avoid rate limiting.
      </p>
    `;
    this.throttleEl.querySelector('[data-action="saveThrottle"]').addEventListener("click", () => {
      this._saveThrottle();
    });
  }

  _renderRetry(settings) {
    const r = settings.retry || { max_retries: 3, base_delay_s: 2.0, max_delay_s: 60.0, enabled: true };
    this.retryEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-teal-500">replay</span>
        <h4 class="text-sm font-bold text-slate-700">Retry</h4>
      </div>
      <div class="space-y-3">
        <label class="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input type="checkbox" class="accent-blue-600" data-el="retryEnabled" ${r.enabled ? "checked" : ""} />
          <span>Enable retry on 429/5xx errors</span>
        </label>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Max Retries</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="0" max="10" step="1" data-el="maxRetries" value="${r.max_retries}" />
        </div>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Base Delay (s)</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="0.1" max="60" step="0.1" data-el="baseDelay" value="${r.base_delay_s}" />
        </div>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Max Delay (s)</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="number" min="1" max="300" step="1" data-el="maxDelay" value="${r.max_delay_s}" />
        </div>
      </div>
      <button class="w-full mt-4 px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition" data-action="saveRetry">
        Save
      </button>
      <p class="mt-3 text-[10px] text-slate-400">
        Exponential backoff: delay doubles each retry.
      </p>
    `;
    this.retryEl.querySelector('[data-action="saveRetry"]').addEventListener("click", () => {
      this._saveRetry();
    });
  }

  _renderProxy(settings) {
    const p = settings.proxy || { enabled: false, url_configured: false };
    this.proxyEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-indigo-500">vpn_key</span>
        <h4 class="text-sm font-bold text-slate-700">Proxy</h4>
        ${p.url_configured ? '<span class="ml-auto px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">Configured</span>' : '<span class="ml-auto px-2 py-0.5 bg-slate-100 text-slate-500 text-xs font-medium rounded-full">Optional</span>'}
      </div>
      <div class="space-y-3">
        <label class="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input type="checkbox" class="accent-blue-600" data-el="proxyEnabled" ${p.enabled ? "checked" : ""} />
          <span>Route requests through proxy</span>
        </label>
        <div>
          <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Proxy URL</label>
          <input class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" type="text" autocomplete="off" spellcheck="false" data-el="proxyUrl" placeholder="http://host:port or socks5://host:port" />
        </div>
      </div>
      <div class="flex gap-2 mt-4">
        <button class="flex-1 px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition" data-action="saveProxy">
          Save
        </button>
        <button class="px-3 py-2 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition" data-action="clearProxy">
          Clear
        </button>
      </div>
      <p class="mt-3 text-[10px] text-slate-400">
        Supports http, https, socks4, socks5. URL hidden after saving.
      </p>
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
    if (kind === "ok") {
      this.bannerEl.innerHTML = `
        <div class="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
          <span class="material-symbols-outlined text-lg">check_circle</span>
          <span>${message}</span>
        </div>
      `;
    } else if (kind === "error") {
      this.bannerEl.innerHTML = `
        <div class="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <span class="material-symbols-outlined text-lg">error</span>
          <span>${message}</span>
        </div>
      `;
    } else {
      this.bannerEl.innerHTML = `
        <div class="flex items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-600">
          <span class="material-symbols-outlined text-lg">info</span>
          <span>${message}</span>
        </div>
      `;
    }
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
