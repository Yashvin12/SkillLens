/**
 * SkillLens Theme Manager
 * ========================
 * Reads/writes "sl_theme" in localStorage.
 * Applies "dark" or "light" class to <html> immediately on page load
 * (place script tag BEFORE body to prevent flash).
 *
 * Usage:
 *   Theme.init()           — call on every page load (in <head> or top of body)
 *   Theme.toggle()         — flip current theme
 *   Theme.set('dark')      — set explicitly
 *   Theme.get()            — returns 'dark' | 'light'
 *   Theme.sync(prefs)      — sync from backend preferences object
 */

const Theme = (() => {
  const KEY    = 'sl_theme';
  const ROOT   = document.documentElement;
  const DARK   = 'dark';
  const LIGHT  = 'light';

  function get() {
    return localStorage.getItem(KEY) || DARK;
  }

  function set(theme) {
    const t = theme === LIGHT ? LIGHT : DARK;
    localStorage.setItem(KEY, t);
    _apply(t);
    _updateToggles(t);
  }

  function toggle() {
    set(get() === DARK ? LIGHT : DARK);
  }

  function init() {
    _apply(get());
  }

  /** Called after loading backend prefs — syncs without overriding local state */
  function sync(prefs) {
    if (prefs?.theme) set(prefs.theme);
  }

  function _apply(theme) {
    if (theme === LIGHT) {
      ROOT.classList.add('light-mode');
      ROOT.classList.remove('dark-mode');
    } else {
      ROOT.classList.add('dark-mode');
      ROOT.classList.remove('light-mode');
    }
  }

  function _updateToggles(theme) {
    document.querySelectorAll('[data-theme-toggle]').forEach(el => {
      el.dataset.themeToggle = theme;
      const moon = el.querySelector('.icon-moon');
      const sun  = el.querySelector('.icon-sun');
      const lbl  = el.querySelector('.theme-label');
      if (theme === LIGHT) {
        moon?.classList.add('hidden');
        sun?.classList.remove('hidden');
        if (lbl) lbl.textContent = 'Light Mode';
      } else {
        sun?.classList.add('hidden');
        moon?.classList.remove('hidden');
        if (lbl) lbl.textContent = 'Dark Mode';
      }
      // Checkbox/switch style toggles
      if (el.tagName === 'INPUT') el.checked = (theme === LIGHT);
    });
  }

  return { get, set, toggle, init, sync };
})();

// Auto-init (runs when script is parsed)
Theme.init();