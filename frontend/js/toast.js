/**
 * Toast Notification System
 * ==========================
 * Lightweight in-page toast notifications.
 * Usage: Toast.show('message', 'success' | 'error' | 'info')
 */

const Toast = (() => {
  let container = null;

  function getContainer() {
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  const ICONS = { success: '✓', error: '✕', info: 'ℹ' };

  function show(message, type = 'info', duration = 4000) {
    const c = getContainer();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon">${ICONS[type] || 'ℹ'}</span>
      <span class="toast-msg">${message}</span>
    `;
    c.appendChild(el);

    // Auto-remove
    setTimeout(() => {
      el.classList.add('out');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, duration);
  }

  return { show, success: (m) => show(m, 'success'), error: (m) => show(m, 'error'), info: (m) => show(m, 'info') };
})();