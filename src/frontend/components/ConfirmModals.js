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
  overlay.className = "modal-overlay fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4";
  overlay.appendChild(content);
  return overlay;
}

/**
 * Create a modal container element.
 * @returns {HTMLElement} The modal container element.
 */
function createModalContainer() {
  const container = document.createElement("div");
  container.className = "modal-container bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden";
  return container;
}

/**
 * Create a modal header element.
 * @param {string} title - The modal title.
 * @param {string} icon - Material Symbol icon name.
 * @param {string} iconColor - Tailwind color class for icon.
 * @returns {HTMLElement} The modal header element.
 */
function createModalHeader(title, icon = "warning", iconColor = "text-amber-500") {
  const header = document.createElement("div");
  header.className = "px-6 pt-6 pb-4";
  header.innerHTML = `
    <div class="flex items-center gap-3">
      <span class="material-symbols-outlined text-2xl ${iconColor}">${icon}</span>
      <h3 class="text-lg font-bold text-slate-800">${title}</h3>
    </div>
  `;
  return header;
}

/**
 * Create a modal body element.
 * @param {string|HTMLElement} content - The body content (string or element).
 * @returns {HTMLElement} The modal body element.
 */
function createModalBody(content) {
  const body = document.createElement("div");
  body.className = "px-6 pb-4 text-sm text-slate-600";
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
  footer.className = "px-6 py-4 bg-slate-50 border-t border-slate-100 flex flex-wrap gap-2 justify-end";
  for (const btn of buttons) {
    const button = document.createElement("button");
    button.className = btn.className || "px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition";
    button.textContent = btn.text;
    button.addEventListener("click", btn.onClick);
    footer.appendChild(button);
  }
  return footer;
}

/**
 * Create an option card for modal choices.
 * @param {Object} options - Option config.
 * @param {string} options.icon - Material Symbol icon name.
 * @param {string} options.iconBgColor - Tailwind bg color class.
 * @param {string} options.iconTextColor - Tailwind text color class.
 * @param {string} options.title - Option title.
 * @param {string} options.description - Option description.
 * @param {string} options.hoverColor - Tailwind hover bg and border color classes.
 * @param {function} options.onClick - Click handler.
 * @returns {HTMLElement} The option card element.
 */
function createOptionCard({ icon, iconBgColor, iconTextColor, title, description, hoverColor, onClick }) {
  const card = document.createElement("button");
  card.className = `w-full flex items-start p-3 border border-slate-200 rounded-lg ${hoverColor} group text-left transition mb-2`;
  card.innerHTML = `
    <div class="${iconBgColor} ${iconTextColor} p-2 rounded-md mr-3 group-hover:opacity-90">
      <span class="material-symbols-outlined text-lg">${icon}</span>
    </div>
    <div>
      <div class="text-sm font-semibold text-slate-700">${title}</div>
      <div class="text-xs text-slate-500">${description}</div>
    </div>
  `;
  card.addEventListener("click", onClick);
  return card;
}

/**
 * Show the Start New confirmation modal.
 */
function showStartNewModal({ handle, imageCount, videoCount, onConfirm, onCancel }) {
  const totalCount = imageCount + videoCount;

  const container = createModalContainer();

  container.appendChild(createModalHeader("Existing Files Found", "folder", "text-amber-500"));

  const body = document.createElement("div");
  body.className = "px-6 pb-4";
  body.innerHTML = `
    <p class="text-sm text-slate-600 mb-4">
      Account <span class="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-800">@${escapeHtml(handle)}</span> has
      <strong>${totalCount}</strong> existing files
      (${imageCount} images, ${videoCount} videos).
    </p>
    <p class="text-xs text-slate-500 mb-4">How would you like to handle these files?</p>
  `;

  let overlay = null;

  const closeModal = () => {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  };

  // Option cards
  const optionsContainer = document.createElement("div");

  optionsContainer.appendChild(createOptionCard({
    icon: "update",
    iconBgColor: "bg-blue-100",
    iconTextColor: "text-blue-600",
    title: "Ignore & Replace (Recommended)",
    description: "Keep old files, overwrite if content changes. Newest run wins.",
    hoverColor: "hover:bg-blue-50 hover:border-blue-200",
    onClick: () => {
      closeModal();
      onConfirm(StartMode.IGNORE_REPLACE);
    },
  }));

  optionsContainer.appendChild(createOptionCard({
    icon: "inventory_2",
    iconBgColor: "bg-amber-100",
    iconTextColor: "text-amber-600",
    title: "Pack & Restart",
    description: "Zip existing folder to archive, then clean start.",
    hoverColor: "hover:bg-amber-50 hover:border-amber-200",
    onClick: () => {
      closeModal();
      onConfirm(StartMode.PACK);
    },
  }));

  optionsContainer.appendChild(createOptionCard({
    icon: "delete_forever",
    iconBgColor: "bg-red-100",
    iconTextColor: "text-red-600",
    title: "Delete & Restart",
    description: "Permanently delete all existing files for this account.",
    hoverColor: "hover:bg-red-50 hover:border-red-200",
    onClick: () => {
      closeModal();
      onConfirm(StartMode.DELETE);
    },
  }));

  body.appendChild(optionsContainer);
  container.appendChild(body);

  // Footer with cancel
  const footer = document.createElement("div");
  footer.className = "px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", () => {
    closeModal();
    onCancel();
  });
  footer.appendChild(cancelBtn);
  container.appendChild(footer);

  overlay = createModalOverlay(container);

  // Close on overlay click
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
 */
function showCancelRunningModal({ handle, onConfirm, onCancel }) {
  const container = createModalContainer();

  container.appendChild(createModalHeader("Cancel Running Task", "stop_circle", "text-red-500"));

  const body = document.createElement("div");
  body.className = "px-6 pb-4";
  body.innerHTML = `
    <p class="text-sm text-slate-600 mb-4">
      You are about to cancel the running task for
      <span class="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-800">@${escapeHtml(handle)}</span>.
    </p>
    <p class="text-xs text-slate-500 mb-4">What would you like to do with the downloaded files?</p>
  `;

  let overlay = null;

  const closeModal = () => {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  };

  // Option cards
  const optionsContainer = document.createElement("div");

  optionsContainer.appendChild(createOptionCard({
    icon: "folder",
    iconBgColor: "bg-blue-100",
    iconTextColor: "text-blue-600",
    title: "Keep Files",
    description: "Preserve downloaded files (partial progress saved).",
    hoverColor: "hover:bg-blue-50 hover:border-blue-200",
    onClick: () => {
      closeModal();
      onConfirm(CancelMode.KEEP);
    },
  }));

  optionsContainer.appendChild(createOptionCard({
    icon: "delete",
    iconBgColor: "bg-red-100",
    iconTextColor: "text-red-600",
    title: "Delete Files",
    description: "Delete all files downloaded in this run.",
    hoverColor: "hover:bg-red-50 hover:border-red-200",
    onClick: () => {
      closeModal();
      onConfirm(CancelMode.DELETE);
    },
  }));

  body.appendChild(optionsContainer);
  container.appendChild(body);

  // Footer
  const footer = document.createElement("div");
  footer.className = "px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition";
  cancelBtn.textContent = "Don't Cancel";
  cancelBtn.addEventListener("click", () => {
    closeModal();
    onCancel();
  });
  footer.appendChild(cancelBtn);
  container.appendChild(footer);

  overlay = createModalOverlay(container);

  // Close on overlay click
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
