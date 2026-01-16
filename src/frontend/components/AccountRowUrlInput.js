/**
 * X 账号 URL 输入组件
 *
 * 功能：
 * - 严格校验 URL 格式（仅接受 https://x.com/<handle>）
 * - 合法输入自动解析并展示 handle
 * - 非法输入显示错误原因并标红
 * - 提供校验状态供外部判断是否可启动任务
 */

/**
 * @typedef {Object} ValidationResult
 * @property {boolean} valid - 是否校验通过
 * @property {string|null} handle - 解析出的 handle（成功时）
 * @property {string|null} error - 错误信息（失败时）
 */

// X handle 合法字符：字母、数字、下划线，长度 1-15
const HANDLE_PATTERN = /^[A-Za-z0-9_]{1,15}$/;

/**
 * 严格校验 X 账号 URL 并提取 handle
 *
 * @param {string} url - 待校验的 URL 字符串
 * @returns {ValidationResult} 校验结果
 */
function validateXUrl(url) {
  if (!url) {
    return { valid: false, handle: null, error: "URL 不能为空" };
  }

  url = url.trim();

  if (!url) {
    return { valid: false, handle: null, error: "URL 不能为空" };
  }

  // 检查是否以 @ 开头（@handle 格式）
  if (url.startsWith("@")) {
    return {
      valid: false,
      handle: null,
      error: "请输入完整 URL，不要使用 @handle 格式（应为 https://x.com/handle）",
    };
  }

  // 尝试解析 URL
  let parsed;
  try {
    parsed = new URL(url);
  } catch (e) {
    // 可能缺少协议
    if (!url.includes("://")) {
      return {
        valid: false,
        handle: null,
        error: "URL 缺少协议，应为 https://x.com/handle",
      };
    }
    return { valid: false, handle: null, error: "URL 格式无效" };
  }

  // 检查 scheme（必须是 https）
  if (parsed.protocol !== "https:") {
    if (parsed.protocol === "http:") {
      return {
        valid: false,
        handle: null,
        error: "请使用 https:// 协议（不支持 http://）",
      };
    }
    return {
      valid: false,
      handle: null,
      error: `不支持的协议 ${parsed.protocol}，请使用 https://`,
    };
  }

  // 检查域名（必须是 x.com）
  const hostLower = parsed.hostname.toLowerCase();
  if (hostLower !== "x.com") {
    if (hostLower === "twitter.com" || hostLower === "www.twitter.com") {
      return {
        valid: false,
        handle: null,
        error: "请使用 x.com 域名（不支持 twitter.com）",
      };
    }
    if (hostLower === "www.x.com") {
      return {
        valid: false,
        handle: null,
        error: "请使用 x.com 域名（不要带 www）",
      };
    }
    return {
      valid: false,
      handle: null,
      error: `域名必须是 x.com（当前为 ${parsed.hostname}）`,
    };
  }

  // 检查端口（不允许）
  if (parsed.port) {
    return {
      valid: false,
      handle: null,
      error: "URL 不能包含端口号",
    };
  }

  // 检查 query 参数（不允许）
  if (parsed.search) {
    return {
      valid: false,
      handle: null,
      error: "URL 不能包含查询参数（? 后的内容）",
    };
  }

  // 检查 fragment（不允许）
  if (parsed.hash) {
    return {
      valid: false,
      handle: null,
      error: "URL 不能包含锚点（# 后的内容）",
    };
  }

  // 解析路径
  let path = parsed.pathname;

  // 检查末尾斜杠
  if (path.endsWith("/") && path.length > 1) {
    return {
      valid: false,
      handle: null,
      error: "URL 末尾不能有斜杠 /",
    };
  }

  // 去掉开头的 /
  if (path.startsWith("/")) {
    path = path.substring(1);
  }

  // 检查是否为空路径
  if (!path) {
    return {
      valid: false,
      handle: null,
      error: "缺少用户名，请输入完整 URL（如 https://x.com/elonmusk）",
    };
  }

  // 检查是否有额外路径段
  if (path.includes("/")) {
    return {
      valid: false,
      handle: null,
      error: "URL 包含额外路径（如 /media、/likes 等），请仅保留账号主页 URL",
    };
  }

  // 此时 path 应该就是 handle
  const handle = path;

  // 校验 handle 格式
  if (!HANDLE_PATTERN.test(handle)) {
    // 检查具体原因
    if (handle.length > 15) {
      return {
        valid: false,
        handle: null,
        error: `用户名过长（最多 15 字符，当前 ${handle.length} 字符）`,
      };
    }
    if (!handle) {
      return {
        valid: false,
        handle: null,
        error: "用户名不能为空",
      };
    }
    // 检查非法字符
    const invalidChars = handle.match(/[^A-Za-z0-9_]/g);
    if (invalidChars) {
      const uniqueChars = [...new Set(invalidChars)].sort().join(", ");
      return {
        valid: false,
        handle: null,
        error: `用户名包含非法字符：${uniqueChars}（仅允许字母、数字、下划线）`,
      };
    }
    return {
      valid: false,
      handle: null,
      error: "用户名格式无效（仅允许字母、数字、下划线，长度 1-15）",
    };
  }

  return { valid: true, handle: handle, error: null };
}

/**
 * AccountRowUrlInput 组件类
 *
 * 用法：
 * const input = new AccountRowUrlInput(containerElement, {
 *   onValidationChange: (result) => { ... },
 *   disabled: false
 * });
 */
class AccountRowUrlInput {
  /**
   * @param {HTMLElement} container - 组件容器元素
   * @param {Object} options - 配置选项
   * @param {Function} [options.onValidationChange] - 校验状态变化回调
   * @param {boolean} [options.disabled] - 是否禁用输入
   * @param {string} [options.initialValue] - 初始值
   */
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this._validationResult = { valid: false, handle: null, error: null };
    this._disabled = options.disabled || false;

    this._render();
    this._bindEvents();

    if (options.initialValue) {
      this.setValue(options.initialValue);
    }
  }

  _render() {
    this.container.innerHTML = `
      <div class="account-url-input-wrapper">
        <div class="relative flex items-center">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <span class="material-symbols-outlined text-slate-400 text-[18px]">alternate_email</span>
          </div>
          <input
            type="text"
            class="url-input w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm font-mono text-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition placeholder:text-slate-300 disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
            placeholder="https://x.com/username"
            autocomplete="off"
            spellcheck="false"
            ${this._disabled ? "disabled" : ""}
          />
          <span class="handle-display hidden absolute right-2 px-2 py-0.5 bg-emerald-50 text-emerald-600 text-xs font-medium rounded-full border border-emerald-200"></span>
        </div>
        <div class="error-message hidden mt-1 text-xs text-red-500"></div>
      </div>
    `;

    this._inputEl = this.container.querySelector(".url-input");
    this._handleDisplayEl = this.container.querySelector(".handle-display");
    this._errorEl = this.container.querySelector(".error-message");
    this._wrapperEl = this.container.querySelector(".account-url-input-wrapper");
  }

  _bindEvents() {
    // 输入时实时校验
    this._inputEl.addEventListener("input", () => {
      this._validate();
    });

    // 失焦时校验
    this._inputEl.addEventListener("blur", () => {
      this._validate();
    });

    // 粘贴时校验
    this._inputEl.addEventListener("paste", () => {
      // 延迟执行以获取粘贴后的值
      setTimeout(() => this._validate(), 0);
    });
  }

  _validate() {
    const url = this._inputEl.value;
    const result = validateXUrl(url);
    this._validationResult = result;

    this._updateUI(result);

    if (this.options.onValidationChange) {
      this.options.onValidationChange(result);
    }
  }

  _updateUI(result) {
    const hasInput = this._inputEl.value.trim() !== "";

    // Update input border color based on validation
    this._inputEl.classList.remove("border-emerald-500", "border-red-400");
    if (result.valid) {
      this._inputEl.classList.add("border-emerald-500");
    } else if (hasInput) {
      this._inputEl.classList.add("border-red-400");
    }

    // Update handle badge display
    if (result.valid && result.handle) {
      this._handleDisplayEl.textContent = `@${result.handle}`;
      this._handleDisplayEl.classList.remove("hidden");
    } else {
      this._handleDisplayEl.textContent = "";
      this._handleDisplayEl.classList.add("hidden");
    }

    // Update error message
    if (!result.valid && result.error && hasInput) {
      this._errorEl.textContent = result.error;
      this._errorEl.classList.remove("hidden");
    } else {
      this._errorEl.textContent = "";
      this._errorEl.classList.add("hidden");
    }
  }

  /**
   * 获取当前校验结果
   * @returns {ValidationResult}
   */
  getValidationResult() {
    return this._validationResult;
  }

  /**
   * 校验是否通过
   * @returns {boolean}
   */
  isValid() {
    return this._validationResult.valid;
  }

  /**
   * 获取解析出的 handle
   * @returns {string|null}
   */
  getHandle() {
    return this._validationResult.handle;
  }

  /**
   * 获取当前输入的 URL
   * @returns {string}
   */
  getValue() {
    return this._inputEl.value;
  }

  /**
   * 设置 URL 值
   * @param {string} value
   */
  setValue(value) {
    this._inputEl.value = value;
    this._validate();
  }

  /**
   * 设置禁用状态
   * @param {boolean} disabled
   */
  setDisabled(disabled) {
    this._disabled = disabled;
    this._inputEl.disabled = disabled;
    // Tailwind handles disabled styling via disabled: pseudo-class
  }

  /**
   * 获取禁用状态
   * @returns {boolean}
   */
  isDisabled() {
    return this._disabled;
  }

  /**
   * 聚焦输入框
   */
  focus() {
    this._inputEl.focus();
  }

  /**
   * 清空输入
   */
  clear() {
    this._inputEl.value = "";
    this._validate();
  }
}

// 导出
if (typeof module !== "undefined" && module.exports) {
  module.exports = { validateXUrl, AccountRowUrlInput };
} else {
  window.validateXUrl = validateXUrl;
  window.AccountRowUrlInput = AccountRowUrlInput;
}
