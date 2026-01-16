/* global fetch */

/**
 * Account Row Stats Component
 *
 * Handles:
 * - Tracking download statistics from backend state
 * - Open folder functionality
 *
 * Note: In the new UI design, stats are not prominently displayed in the main row.
 * This component mainly provides the _onOpenFolder API call functionality.
 */

function _formatHms(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = String(Math.floor(total / 3600)).padStart(2, "0");
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function _formatSpeed(speed) {
  const v = Number(speed);
  if (!Number.isFinite(v) || v <= 0) return "0.00";
  return v.toFixed(2);
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
    this._stats = {
      images_downloaded: 0,
      videos_downloaded: 0,
      skipped_duplicate: 0,
      runtime_s: 0,
      avg_speed: 0,
    };
  }

  _getOutputPath() {
    const settings = this.getSettings ? this.getSettings() : null;
    const handle = this.getHandle ? this.getHandle() : null;
    return _joinPath(settings?.download_root, handle);
  }

  refresh() {
    // No visible UI to refresh in new design
    // Stats are tracked internally
  }

  reset() {
    this._stats = {
      images_downloaded: 0,
      videos_downloaded: 0,
      skipped_duplicate: 0,
      runtime_s: 0,
      avg_speed: 0,
    };
  }

  applyBackendState(state) {
    this._stats.images_downloaded = Number(state?.images_downloaded ?? 0) || 0;
    this._stats.videos_downloaded = Number(state?.videos_downloaded ?? 0) || 0;
    this._stats.skipped_duplicate = Number(state?.skipped_duplicate ?? 0) || 0;
    this._stats.runtime_s = Number(state?.runtime_s ?? 0) || 0;
    this._stats.avg_speed = Number(state?.avg_speed ?? 0) || 0;
  }

  getStats() {
    return { ...this._stats };
  }

  getFormattedStats() {
    return {
      images: this._stats.images_downloaded,
      videos: this._stats.videos_downloaded,
      skipped: this._stats.skipped_duplicate,
      runtime: _formatHms(this._stats.runtime_s),
      speed: _formatSpeed(this._stats.avg_speed),
      total: this._stats.images_downloaded + this._stats.videos_downloaded,
    };
  }

  async _onOpenFolder() {
    const path = this._getOutputPath();
    if (!path) {
      if (typeof showToast === "function") {
        showToast("No output path - please enter a valid URL first", "error");
      }
      return;
    }

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
        if (typeof showToast === "function") {
          showToast(`Failed to open folder (HTTP ${res.status}): ${detail}`, "error");
        }
        return;
      }

      if (typeof showToast === "function") {
        showToast("Opening folder...", "success");
      }
    } catch (err) {
      const message = err?.message ? String(err.message) : String(err);
      if (typeof showToast === "function") {
        showToast(`Failed to open folder: ${message}`, "error");
      }
    }
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { AccountRowStats };
} else {
  window.AccountRowStats = AccountRowStats;
}
