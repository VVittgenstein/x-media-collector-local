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
    this.container.innerHTML = `
      <div class="account-config-wrapper">
        <div class="config-header">
          <button type="button" class="config-toggle-btn">
            <span class="toggle-icon">▶</span>
            <span class="toggle-text">筛选配置</span>
          </button>
          <div class="config-actions">
            <button type="button" class="btn btn-sm config-copy-btn" title="复制配置">
              <span class="btn-icon">📋</span> Copy
            </button>
            <button type="button" class="btn btn-sm config-paste-btn" title="粘贴配置">
              <span class="btn-icon">📥</span> Paste
            </button>
          </div>
        </div>
        <div class="config-panel" style="display: none;">
          <div class="config-section">
            <div class="config-row">
              <div class="config-field">
                <label class="config-label">开始日期</label>
                <input type="date" class="config-input config-start-date" />
              </div>
              <div class="config-field">
                <label class="config-label">结束日期</label>
                <input type="date" class="config-input config-end-date" />
              </div>
            </div>
          </div>

          <div class="config-section">
            <label class="config-label">媒体类型</label>
            <div class="config-radio-group">
              <label class="config-radio">
                <input type="radio" name="mediaType" value="images" />
                <span>仅图片</span>
              </label>
              <label class="config-radio">
                <input type="radio" name="mediaType" value="videos" />
                <span>仅视频</span>
              </label>
              <label class="config-radio">
                <input type="radio" name="mediaType" value="both" />
                <span>全部</span>
              </label>
            </div>
          </div>

          <div class="config-section">
            <label class="config-label">来源类型</label>
            <div class="config-checkbox-group">
              <label class="config-checkbox">
                <input type="checkbox" name="sourceType" value="Original" />
                <span>原创</span>
              </label>
              <label class="config-checkbox">
                <input type="checkbox" name="sourceType" value="Retweet" />
                <span>转推</span>
              </label>
              <label class="config-checkbox">
                <input type="checkbox" name="sourceType" value="Reply" />
                <span>回复</span>
              </label>
              <label class="config-checkbox">
                <input type="checkbox" name="sourceType" value="Quote" />
                <span>引用</span>
              </label>
            </div>
          </div>

          <div class="config-section">
            <div class="config-row">
              <div class="config-field">
                <label class="config-label">最小短边 (px)</label>
                <input type="number" class="config-input config-min-short-side"
                       min="0" step="1" placeholder="不限制" />
                <div class="config-hint">低于此值的媒体不会下载</div>
              </div>
              <div class="config-field">
                <label class="config-label config-switch-label">
                  <span>Reply 中包含引用媒体</span>
                  <input type="checkbox" class="config-switch-input config-include-quote" />
                  <span class="config-switch"></span>
                </label>
                <div class="config-hint">开启后，Reply 推文会同时下载被引用推文的媒体</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // 缓存 DOM 引用
    this._wrapperEl = this.container.querySelector(".account-config-wrapper");
    this._toggleBtn = this.container.querySelector(".config-toggle-btn");
    this._toggleIcon = this.container.querySelector(".toggle-icon");
    this._panelEl = this.container.querySelector(".config-panel");
    this._copyBtn = this.container.querySelector(".config-copy-btn");
    this._pasteBtn = this.container.querySelector(".config-paste-btn");

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

    // 为 radio 添加唯一 name（支持多行）
    const uniqueId = Math.random().toString(36).substring(2, 9);
    this._mediaTypeRadios.forEach((radio) => {
      radio.name = `mediaType_${uniqueId}`;
    });

    this._applyConfigToUI();
    this._updateLockedState();
  }

  _bindEvents() {
    // 展开/收起切换
    this._toggleBtn.addEventListener("click", () => {
      this._expanded = !this._expanded;
      this._updateExpandState();
    });

    // Copy 按钮
    this._copyBtn.addEventListener("click", () => {
      if (this.options.onCopy) {
        this.options.onCopy(this.getConfig());
      }
    });

    // Paste 按钮
    this._pasteBtn.addEventListener("click", () => {
      if (this._locked) return;
      if (this.options.onPaste) {
        this.options.onPaste();
      }
    });

    // 日期输入
    this._startDateInput.addEventListener("change", () => this._onInputChange());
    this._endDateInput.addEventListener("change", () => this._onInputChange());

    // 媒体类型
    this._mediaTypeRadios.forEach((radio) => {
      radio.addEventListener("change", () => this._onInputChange());
    });

    // 来源类型
    this._sourceTypeCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => this._onInputChange());
    });

    // 最小短边
    this._minShortSideInput.addEventListener("change", () =>
      this._onInputChange()
    );
    this._minShortSideInput.addEventListener("input", () =>
      this._onInputChange()
    );

    // Quote 开关
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
    this._panelEl.style.display = this._expanded ? "block" : "none";
    this._toggleIcon.textContent = this._expanded ? "▼" : "▶";
    this._wrapperEl.classList.toggle("expanded", this._expanded);
  }

  _updateLockedState() {
    this._wrapperEl.classList.toggle("locked", this._locked);

    // 禁用所有输入
    const inputs = this._panelEl.querySelectorAll("input");
    inputs.forEach((input) => {
      input.disabled = this._locked;
    });

    // Paste 按钮
    this._pasteBtn.disabled = this._locked;
    if (this._locked) {
      this._pasteBtn.title = "任务进行中，无法粘贴配置";
    } else {
      this._pasteBtn.title = "粘贴配置";
    }

    // Copy 保持可用
    this._copyBtn.disabled = false;

    // 更新 Paste 按钮可用性（检查剪贴板是否有内容）
    this._updatePasteAvailability();
  }

  _updatePasteAvailability() {
    if (this._locked) {
      this._pasteBtn.disabled = true;
      return;
    }

    if (this.options.canPaste) {
      const canPaste = this.options.canPaste();
      this._pasteBtn.disabled = !canPaste;
      if (!canPaste) {
        this._pasteBtn.title = "剪贴板为空";
      } else {
        this._pasteBtn.title = "粘贴配置";
      }
    }
  }

  /**
   * 获取当前配置
   * @returns {AccountConfig}
   */
  getConfig() {
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
