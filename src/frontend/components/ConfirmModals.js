/**
 * Confirmation modals for task lifecycle operations.
 *
 * Provides:
 * - StartNewModal: Three-choice modal for handling existing files on Start New
 * - CancelRunningModal: Two-choice modal for handling files on Cancel Running
 */

/**
 * Start mode options for handling existing files.
 */
const StartMode = {
  DELETE: "delete",
  IGNORE_REPLACE: "ignore_replace",
  PACK: "pack",
};

/**
 * Cancel mode options for handling files.
 */
const CancelMode = {
  KEEP: "keep",
  DELETE: "delete",
};

/**
 * Create a modal overlay element.
 * @param {HTMLElement} content - The modal content element.
 * @returns {HTMLElement} The modal overlay element.
 */
function createModalOverlay(content) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.appendChild(content);
  return overlay;
}

/**
 * Create a modal container element.
 * @returns {HTMLElement} The modal container element.
 */
function createModalContainer() {
  const container = document.createElement("div");
  container.className = "modal-container";
  return container;
}

/**
 * Create a modal header element.
 * @param {string} title - The modal title.
 * @returns {HTMLElement} The modal header element.
 */
function createModalHeader(title) {
  const header = document.createElement("div");
  header.className = "modal-header";
  header.textContent = title;
  return header;
}

/**
 * Create a modal body element.
 * @param {string|HTMLElement} content - The body content (string or element).
 * @returns {HTMLElement} The modal body element.
 */
function createModalBody(content) {
  const body = document.createElement("div");
  body.className = "modal-body";
  if (typeof content === "string") {
    body.innerHTML = content;
  } else {
    body.appendChild(content);
  }
  return body;
}

/**
 * Create a modal footer with buttons.
 * @param {Array<{text: string, className: string, onClick: function}>} buttons - Button configs.
 * @returns {HTMLElement} The modal footer element.
 */
function createModalFooter(buttons) {
  const footer = document.createElement("div");
  footer.className = "modal-footer";
  for (const btn of buttons) {
    const button = document.createElement("button");
    button.className = `btn ${btn.className || ""}`.trim();
    button.textContent = btn.text;
    button.addEventListener("click", btn.onClick);
    footer.appendChild(button);
  }
  return footer;
}

/**
 * Show the Start New confirmation modal.
 *
 * This modal is shown when the user clicks "Start" and the account
 * already has existing files. It presents three options:
 * - Delete & Restart: Delete all existing files and start fresh
 * - Ignore & Replace: Keep files, new run will replace by hash
 * - Pack & Restart: Archive files to zip, then start fresh
 *
 * @param {Object} options - Modal options.
 * @param {string} options.handle - The Twitter handle.
 * @param {number} options.imageCount - Number of existing images.
 * @param {number} options.videoCount - Number of existing videos.
 * @param {function(StartMode): void} options.onConfirm - Called when user selects a mode.
 * @param {function(): void} options.onCancel - Called when user cancels.
 * @returns {HTMLElement} The modal overlay element (add to DOM to show).
 */
function showStartNewModal({ handle, imageCount, videoCount, onConfirm, onCancel }) {
  const totalCount = imageCount + videoCount;

  const container = createModalContainer();

  container.appendChild(createModalHeader("Start New - Existing Files Found"));

  const bodyContent = document.createElement("div");
  bodyContent.innerHTML = `
    <p>Account <strong>@${escapeHtml(handle)}</strong> has existing files:</p>
    <ul>
      <li>Images: <strong>${imageCount}</strong></li>
      <li>Videos: <strong>${videoCount}</strong></li>
      <li>Total: <strong>${totalCount}</strong></li>
    </ul>
    <p>How would you like to handle these files?</p>
  `;
  container.appendChild(createModalBody(bodyContent));

  let overlay = null;

  const closeModal = () => {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  };

  const footer = createModalFooter([
    {
      text: "Delete & Restart",
      className: "btn-danger",
      onClick: () => {
        closeModal();
        onConfirm(StartMode.DELETE);
      },
    },
    {
      text: "Ignore & Replace",
      className: "btn-warning",
      onClick: () => {
        closeModal();
        onConfirm(StartMode.IGNORE_REPLACE);
      },
    },
    {
      text: "Pack & Restart",
      className: "btn-primary",
      onClick: () => {
        closeModal();
        onConfirm(StartMode.PACK);
      },
    },
    {
      text: "Cancel",
      className: "",
      onClick: () => {
        closeModal();
        onCancel();
      },
    },
  ]);
  container.appendChild(footer);

  overlay = createModalOverlay(container);

  // Close on overlay click (outside modal)
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      closeModal();
      onCancel();
    }
  });

  // Close on Escape key
  const handleEscape = (e) => {
    if (e.key === "Escape") {
      closeModal();
      onCancel();
      document.removeEventListener("keydown", handleEscape);
    }
  };
  document.addEventListener("keydown", handleEscape);

  return overlay;
}

/**
 * Show the Cancel Running confirmation modal.
 *
 * This modal is shown when the user clicks "Cancel" on a running task.
 * It presents two options:
 * - Keep: Keep all downloaded files (partial progress preserved)
 * - Delete: Delete all downloaded files
 *
 * Note: This is NOT shown for Queued tasks - those are cancelled immediately
 * without a modal.
 *
 * @param {Object} options - Modal options.
 * @param {string} options.handle - The Twitter handle.
 * @param {function(CancelMode): void} options.onConfirm - Called when user selects a mode.
 * @param {function(): void} options.onCancel - Called when user cancels the dialog.
 * @returns {HTMLElement} The modal overlay element (add to DOM to show).
 */
function showCancelRunningModal({ handle, onConfirm, onCancel }) {
  const container = createModalContainer();

  container.appendChild(createModalHeader("Cancel Running Task"));

  const bodyContent = document.createElement("div");
  bodyContent.innerHTML = `
    <p>You are about to cancel the running task for <strong>@${escapeHtml(handle)}</strong>.</p>
    <p>What would you like to do with the downloaded files?</p>
  `;
  container.appendChild(createModalBody(bodyContent));

  let overlay = null;

  const closeModal = () => {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  };

  const footer = createModalFooter([
    {
      text: "Keep Files",
      className: "btn-primary",
      onClick: () => {
        closeModal();
        onConfirm(CancelMode.KEEP);
      },
    },
    {
      text: "Delete Files",
      className: "btn-danger",
      onClick: () => {
        closeModal();
        onConfirm(CancelMode.DELETE);
      },
    },
    {
      text: "Don't Cancel",
      className: "",
      onClick: () => {
        closeModal();
        onCancel();
      },
    },
  ]);
  container.appendChild(footer);

  overlay = createModalOverlay(container);

  // Close on overlay click (outside modal)
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      closeModal();
      onCancel();
    }
  });

  // Close on Escape key
  const handleEscape = (e) => {
    if (e.key === "Escape") {
      closeModal();
      onCancel();
      document.removeEventListener("keydown", handleEscape);
    }
  };
  document.addEventListener("keydown", handleEscape);

  return overlay;
}

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} text - The text to escape.
 * @returns {string} The escaped text.
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Export for use in other modules
// eslint-disable-next-line no-unused-vars
const ConfirmModals = {
  StartMode,
  CancelMode,
  showStartNewModal,
  showCancelRunningModal,
};
