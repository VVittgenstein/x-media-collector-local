/**
 * 配置剪贴板状态管理
 *
 * 功能：
 * - 存储复制的账号配置（不含 URL/handle）
 * - 通知订阅者剪贴板状态变化
 * - 提供 Copy/Paste 接口
 */

/**
 * @typedef {import('../components/AccountRowConfig.js').AccountConfig} AccountConfig
 */

/**
 * 配置剪贴板单例
 */
class ConfigClipboard {
  constructor() {
    /** @type {AccountConfig|null} */
    this._config = null;
    /** @type {Set<Function>} */
    this._listeners = new Set();
  }

  /**
   * 复制配置到剪贴板
   * @param {AccountConfig} config - 要复制的配置
   */
  copy(config) {
    // 深拷贝配置
    this._config = {
      startDate: config.startDate,
      endDate: config.endDate,
      mediaType: config.mediaType,
      sourceTypes: { ...config.sourceTypes },
      minShortSide: config.minShortSide,
      includeQuoteMediaInReply: config.includeQuoteMediaInReply,
    };
    this._notifyListeners();
  }

  /**
   * 从剪贴板获取配置
   * @returns {AccountConfig|null} 剪贴板中的配置，如果为空则返回 null
   */
  paste() {
    if (!this._config) {
      return null;
    }
    // 返回深拷贝
    return {
      startDate: this._config.startDate,
      endDate: this._config.endDate,
      mediaType: this._config.mediaType,
      sourceTypes: { ...this._config.sourceTypes },
      minShortSide: this._config.minShortSide,
      includeQuoteMediaInReply: this._config.includeQuoteMediaInReply,
    };
  }

  /**
   * 检查剪贴板是否有内容
   * @returns {boolean}
   */
  hasContent() {
    return this._config !== null;
  }

  /**
   * 清空剪贴板
   */
  clear() {
    this._config = null;
    this._notifyListeners();
  }

  /**
   * 订阅剪贴板变化
   * @param {Function} listener - 变化回调函数
   * @returns {Function} 取消订阅函数
   */
  subscribe(listener) {
    this._listeners.add(listener);
    return () => {
      this._listeners.delete(listener);
    };
  }

  /**
   * 通知所有订阅者
   * @private
   */
  _notifyListeners() {
    for (const listener of this._listeners) {
      try {
        listener(this.hasContent());
      } catch (e) {
        console.error("ConfigClipboard listener error:", e);
      }
    }
  }
}

// 创建全局单例
const configClipboard = new ConfigClipboard();

// 导出
if (typeof module !== "undefined" && module.exports) {
  module.exports = { ConfigClipboard, configClipboard };
} else {
  window.ConfigClipboard = ConfigClipboard;
  window.configClipboard = configClipboard;
}
