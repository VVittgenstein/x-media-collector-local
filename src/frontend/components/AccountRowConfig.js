/**
 * 账号行配置组件
 *
 * 功能：
 * - 提供每账号的筛选配置项
 * - 日期范围、媒体类型、来源类型、MIN_SHORT_SIDE、Quote开关
 * - 支持 Copy/Paste Config 功能
 * - Locked 状态下禁用输入和 Paste
 */

/**
 * @typedef {Object} AccountConfig
 * @property {string|null} startDate - 开始日期（YYYY-MM-DD）
 * @property {string|null} endDate - 结束日期（YYYY-MM-DD）
 * @property {'images'|'videos'|'both'} mediaType - 媒体类型
 * @property {Object} sourceTypes - 来源类型选择
 * @property {boolean} sourceTypes.Original
 * @property {boolean} sourceTypes.Retweet
 * @property {boolean} sourceTypes.Reply
 * @property {boolean} sourceTypes.Quote
 * @property {number|null} minShortSide - 最小短边像素
 * @property {boolean} includeQuoteMediaInReply - Reply 中是否包含被引用推文的媒体
 */

/**
 * 默认配置
 * @returns {AccountConfig}
 */
function getDefaultConfig() {
  return {
    startDate: null,
    endDate: null,
    mediaType: "both",
    sourceTypes: {
      Original: true,
      Retweet: true,
      Reply: true,
      Quote: true,
    },
    minShortSide: null,
    includeQuoteMediaInReply: false,
  };
}

/**
 * 深拷贝配置对象
 * @param {AccountConfig} config
 * @returns {AccountConfig}
 */
function cloneConfig(config) {
  return {
    startDate: config.startDate,
    endDate: config.endDate,
    mediaType: config.mediaType,
    sourceTypes: { ...config.sourceTypes },
    minShortSide: config.minShortSide,
    includeQuoteMediaInReply: config.includeQuoteMediaInReply,
  };
}

/**
 * AccountRowConfig 组件类
 */
class AccountRowConfig {
  /**
   * @param {HTMLElement} container - 组件容器元素
   * @param {Object} options - 配置选项
   * @param {Function} [options.onChange] - 配置变化回调
   * @param {Function} [options.onCopy] - 点击复制按钮回调
   * @param {Function} [options.onPaste] - 点击粘贴按钮回调
   * @param {Function} [options.canPaste] - 是否可以粘贴（返回布尔值）
   * @param {boolean} [options.locked] - 是否锁定（Queued/Running 状态）
   * @param {AccountConfig} [options.initialConfig] - 初始配置
   */
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this._config = options.initialConfig
      ? cloneConfig(options.initialConfig)
      : getDefaultConfig();
    this._locked = options.locked || false;
    this._expanded = false;

    this._render();
    this._bindEvents();
  }

  _render() {
    // Config panel content (toggle button is handled in app.js main row)
    this.container.innerHTML = `
      <div class="account-config-wrapper p-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

          <!-- Date Range -->
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Date Range</label>
            <div class="flex items-center gap-2">
              <input type="date" class="config-start-date w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:border-blue-500 outline-none bg-white disabled:bg-slate-50 disabled:text-slate-400" />
              <span class="text-slate-400 text-xs">to</span>
              <input type="date" class="config-end-date w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:border-blue-500 outline-none bg-white disabled:bg-slate-50 disabled:text-slate-400" />
            </div>
          </div>

          <!-- Media Types -->
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Media Type</label>
            <div class="flex gap-2 flex-wrap">
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400 has-[:checked]:text-blue-600">
                <input type="radio" name="mediaType" value="images" class="accent-blue-600" /> Images
              </label>
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400 has-[:checked]:text-blue-600">
                <input type="radio" name="mediaType" value="videos" class="accent-blue-600" /> Videos
              </label>
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400 has-[:checked]:text-blue-600">
                <input type="radio" name="mediaType" value="both" class="accent-blue-600" /> All
              </label>
            </div>
          </div>

          <!-- Source Types -->
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Source Type</label>
            <div class="flex gap-2 flex-wrap">
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400">
                <input type="checkbox" name="sourceType" value="Original" class="accent-blue-600" /> Original
              </label>
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400">
                <input type="checkbox" name="sourceType" value="Retweet" class="accent-blue-600" /> Retweet
              </label>
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400">
                <input type="checkbox" name="sourceType" value="Reply" class="accent-blue-600" /> Reply
              </label>
              <label class="flex items-center gap-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded px-2 py-1.5 cursor-pointer hover:border-blue-400 select-none has-[:checked]:bg-blue-50 has-[:checked]:border-blue-400">
                <input type="checkbox" name="sourceType" value="Quote" class="accent-blue-600" /> Quote
              </label>
            </div>
          </div>

          <!-- Filters -->
          <div>
            <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Filters</label>
            <div class="space-y-2">
              <div>
                <label class="text-xs text-slate-600">Min Short Side (px)</label>
                <input type="number" class="config-min-short-side w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:border-blue-500 outline-none bg-white disabled:bg-slate-50 disabled:text-slate-400 mt-1" min="0" step="1" placeholder="No limit" />
              </div>
              <label class="flex items-center justify-between text-xs text-slate-600 cursor-pointer">
                <span>Include quote media in replies</span>
                <input type="checkbox" class="config-include-quote accent-blue-600" />
              </label>
            </div>
          </div>
        </div>
      </div>
    `;

    // Cache DOM references
    this._wrapperEl = this.container.querySelector(".account-config-wrapper");
    this._panelEl = this._wrapperEl; // The wrapper is the panel in this new design
    this._copyBtn = null; // Copy/Paste handled in app.js now
    this._pasteBtn = null;

    this._startDateInput = this.container.querySelector(".config-start-date");
    this._endDateInput = this.container.querySelector(".config-end-date");
    this._mediaTypeRadios = this.container.querySelectorAll(
      'input[name="mediaType"]'
    );
    this._sourceTypeCheckboxes = this.container.querySelectorAll(
      'input[name="sourceType"]'
    );
    this._minShortSideInput = this.container.querySelector(
      ".config-min-short-side"
    );
    this._includeQuoteCheckbox =
      this.container.querySelector(".config-include-quote");

    // Add unique name for radio buttons (support multiple rows)
    const uniqueId = Math.random().toString(36).substring(2, 9);
    this._mediaTypeRadios.forEach((radio) => {
      radio.name = `mediaType_${uniqueId}`;
    });

    this._applyConfigToUI();
    this._updateLockedState();
  }

  _bindEvents() {
    // Toggle/Copy/Paste buttons are now handled in app.js main row

    // Date inputs
    this._startDateInput.addEventListener("change", () => this._onInputChange());
    this._endDateInput.addEventListener("change", () => this._onInputChange());
    // Some browsers don't trigger change before blur; add input event to ensure config is synced before Start
    this._startDateInput.addEventListener("input", () => this._onInputChange());
    this._endDateInput.addEventListener("input", () => this._onInputChange());

    // Media type radios
    this._mediaTypeRadios.forEach((radio) => {
      radio.addEventListener("change", () => this._onInputChange());
    });

    // Source type checkboxes
    this._sourceTypeCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => this._onInputChange());
    });

    // Min short side input
    this._minShortSideInput.addEventListener("change", () =>
      this._onInputChange()
    );
    this._minShortSideInput.addEventListener("input", () =>
      this._onInputChange()
    );

    // Include quote checkbox
    this._includeQuoteCheckbox.addEventListener("change", () =>
      this._onInputChange()
    );
  }

  _onInputChange() {
    this._readConfigFromUI();
    if (this.options.onChange) {
      this.options.onChange(this.getConfig());
    }
  }

  _readConfigFromUI() {
    // 日期
    this._config.startDate = this._startDateInput.value || null;
    this._config.endDate = this._endDateInput.value || null;

    // 媒体类型
    for (const radio of this._mediaTypeRadios) {
      if (radio.checked) {
        this._config.mediaType = radio.value;
        break;
      }
    }

    // 来源类型
    this._sourceTypeCheckboxes.forEach((checkbox) => {
      this._config.sourceTypes[checkbox.value] = checkbox.checked;
    });

    // 最小短边
    const minShortSide = parseInt(this._minShortSideInput.value, 10);
    this._config.minShortSide =
      !isNaN(minShortSide) && minShortSide > 0 ? minShortSide : null;

    // Quote 开关
    this._config.includeQuoteMediaInReply = this._includeQuoteCheckbox.checked;
  }

  _applyConfigToUI() {
    // 日期
    this._startDateInput.value = this._config.startDate || "";
    this._endDateInput.value = this._config.endDate || "";

    // 媒体类型
    this._mediaTypeRadios.forEach((radio) => {
      radio.checked = radio.value === this._config.mediaType;
    });

    // 来源类型
    this._sourceTypeCheckboxes.forEach((checkbox) => {
      checkbox.checked = this._config.sourceTypes[checkbox.value] ?? true;
    });

    // 最小短边
    this._minShortSideInput.value =
      this._config.minShortSide !== null ? this._config.minShortSide : "";

    // Quote 开关
    this._includeQuoteCheckbox.checked = this._config.includeQuoteMediaInReply;
  }

  _updateExpandState() {
    // Expand/collapse is handled by parent (app.js) via classList.toggle("hidden")
    // This method kept for API compatibility
  }

  _updateLockedState() {
    // Disable all inputs when locked
    const inputs = this._wrapperEl.querySelectorAll("input");
    inputs.forEach((input) => {
      input.disabled = this._locked;
    });

    // Add visual locked state with opacity
    this._wrapperEl.classList.toggle("opacity-50", this._locked);
    this._wrapperEl.classList.toggle("pointer-events-none", this._locked);
  }

  _updatePasteAvailability() {
    // Copy/Paste buttons are now handled in app.js
    // This method kept for API compatibility
  }

  /**
   * 获取当前配置
   * @returns {AccountConfig}
   */
  getConfig() {
    // 兜底：确保在用户刚输入但尚未触发 change 的情况下（例如直接点击 Start），仍能拿到最新配置。
    this._readConfigFromUI();
    return cloneConfig(this._config);
  }

  /**
   * 设置配置
   * @param {AccountConfig} config
   */
  setConfig(config) {
    this._config = cloneConfig(config);
    this._applyConfigToUI();
    if (this.options.onChange) {
      this.options.onChange(this.getConfig());
    }
  }

  /**
   * 设置锁定状态
   * @param {boolean} locked
   */
  setLocked(locked) {
    this._locked = locked;
    this._updateLockedState();
  }

  /**
   * 获取锁定状态
   * @returns {boolean}
   */
  isLocked() {
    return this._locked;
  }

  /**
   * 刷新 Paste 按钮可用性
   */
  refreshPasteAvailability() {
    this._updatePasteAvailability();
  }

  /**
   * 展开配置面板
   */
  expand() {
    this._expanded = true;
    this._updateExpandState();
  }

  /**
   * 收起配置面板
   */
  collapse() {
    this._expanded = false;
    this._updateExpandState();
  }

  /**
   * 切换展开状态
   */
  toggle() {
    this._expanded = !this._expanded;
    this._updateExpandState();
  }

  /**
   * 是否已展开
   * @returns {boolean}
   */
  isExpanded() {
    return this._expanded;
  }
}

// 导出
if (typeof module !== "undefined" && module.exports) {
  module.exports = { AccountRowConfig, getDefaultConfig, cloneConfig };
} else {
  window.AccountRowConfig = AccountRowConfig;
  window.getDefaultConfig = getDefaultConfig;
  window.cloneConfig = cloneConfig;
}
