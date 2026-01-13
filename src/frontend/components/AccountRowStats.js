/* global fetch */

function _formatHms(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = String(Math.floor(total / 3600)).padStart(2, "0");
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function _formatSpeed(speed) {
  const v = Number(speed);
  if (!Number.isFinite(v) || v <= 0) return "0.00 /s";
  return `${v.toFixed(2)} /s`;
}

function _joinPath(root, handle) {
  const r = String(root || "").trim();
  const h = String(handle || "").trim().replace(/^@/, "");
  if (!r || !h) return "";
  const sep = r.endsWith("/") || r.endsWith("\\") ? "" : "/";
  return `${r}${sep}${h}`;
}

class AccountRowStats {
  constructor(container, { getSettings, getHandle }) {
    this.container = container;
    this.getSettings = getSettings;
    this.getHandle = getHandle;
    this._messageTimer = null;
    this._render();
    this.reset();
  }

  _render() {
    this.root = document.createElement("div");
    this.root.className = "account-stats";

    this.grid = document.createElement("div");
    this.grid.className = "account-stats-grid";

    const makeStat = (label) => {
      const wrap = document.createElement("div");
      wrap.className = "account-stat";
      const l = document.createElement("div");
      l.className = "label";
      l.textContent = label;
      const v = document.createElement("div");
      v.className = "value";
      v.textContent = "-";
      wrap.appendChild(l);
      wrap.appendChild(v);
      return { wrap, valueEl: v };
    };

    const sImages = makeStat("images_downloaded");
    const sVideos = makeStat("videos_downloaded");
    const sSkipped = makeStat("skipped_duplicate");
    const sRuntime = makeStat("runtime");
    const sSpeed = makeStat("avg_speed");

    this.imagesValue = sImages.valueEl;
    this.videosValue = sVideos.valueEl;
    this.skippedValue = sSkipped.valueEl;
    this.runtimeValue = sRuntime.valueEl;
    this.speedValue = sSpeed.valueEl;

    this.grid.appendChild(sImages.wrap);
    this.grid.appendChild(sVideos.wrap);
    this.grid.appendChild(sSkipped.wrap);
    this.grid.appendChild(sRuntime.wrap);
    this.grid.appendChild(sSpeed.wrap);

    this.pathRow = document.createElement("div");
    this.pathRow.className = "account-stats-path";

    const pathLabel = document.createElement("div");
    pathLabel.className = "path-label";
    pathLabel.textContent = "output";

    this.pathValue = document.createElement("div");
    this.pathValue.className = "path-value";
    this.pathValue.textContent = "-";

    this.openBtn = document.createElement("button");
    this.openBtn.className = "btn btn-small";
    this.openBtn.textContent = "Open Folder";
    this.openBtn.addEventListener("click", () => this._onOpenFolder());

    this.pathRow.appendChild(pathLabel);
    this.pathRow.appendChild(this.pathValue);
    this.pathRow.appendChild(this.openBtn);

    this.messageEl = document.createElement("div");
    this.messageEl.className = "account-stats-message muted";
    this.messageEl.textContent = "";

    this.root.appendChild(this.grid);
    this.root.appendChild(this.pathRow);
    this.root.appendChild(this.messageEl);
    this.container.appendChild(this.root);
  }

  _setMessage(text, kind) {
    if (this._messageTimer) clearTimeout(this._messageTimer);
    const cls = kind === "error" ? "error" : kind === "ok" ? "ok" : "muted";
    this.messageEl.className = `account-stats-message ${cls}`.trim();
    this.messageEl.textContent = text || "";
    if (text) {
      this._messageTimer = setTimeout(() => {
        this.messageEl.textContent = "";
        this.messageEl.className = "account-stats-message muted";
      }, 3500);
    }
  }

  _getOutputPath() {
    const settings = this.getSettings ? this.getSettings() : null;
    const handle = this.getHandle ? this.getHandle() : null;
    return _joinPath(settings?.download_root, handle);
  }

  refresh() {
    const path = this._getOutputPath();
    this.pathValue.textContent = path || "-";
    this.pathValue.title = path || "";
    this.openBtn.disabled = !path;
  }

  reset() {
    this.imagesValue.textContent = "0";
    this.videosValue.textContent = "0";
    this.skippedValue.textContent = "0";
    this.runtimeValue.textContent = "00:00:00";
    this.speedValue.textContent = "0.00 /s";
    this._setMessage("", "muted");
    this.refresh();
  }

  applyBackendState(state) {
    const images = Number(state?.images_downloaded ?? 0) || 0;
    const videos = Number(state?.videos_downloaded ?? 0) || 0;
    const skipped = Number(state?.skipped_duplicate ?? 0) || 0;
    const runtime = Number(state?.runtime_s ?? 0) || 0;
    const speed = Number(state?.avg_speed ?? 0) || 0;

    this.imagesValue.textContent = String(images);
    this.videosValue.textContent = String(videos);
    this.skippedValue.textContent = String(skipped);
    this.runtimeValue.textContent = _formatHms(runtime);
    this.speedValue.textContent = _formatSpeed(speed);
    this.refresh();
  }

  async _onOpenFolder() {
    const path = this._getOutputPath();
    if (!path) {
      this._setMessage("未解析到输出目录（请先填写有效 URL/handle）", "error");
      return;
    }

    this.openBtn.disabled = true;
    try {
      const res = await fetch("/api/os/open-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });

      if (!res.ok) {
        let detail = "";
        try {
          const data = await res.json();
          detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data);
        } catch (e) {
          detail = await res.text();
        }
        this._setMessage(`打开失败（HTTP ${res.status}）：${detail}`, "error");
        return;
      }

      this._setMessage("已请求打开文件夹", "ok");
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      this._setMessage(`打开失败（${message}）`, "error");
    } finally {
      this.openBtn.disabled = !path;
    }
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { AccountRowStats };
} else {
  window.AccountRowStats = AccountRowStats;
}
