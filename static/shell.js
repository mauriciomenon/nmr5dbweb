(function () {
  if (typeof window.initShellChrome === 'function') {
    return;
  }

  var STORAGE_KEY = 'mdb_theme';
  var THEMES = ['system', 'dark', 'light'];

  function normalizeTheme(value) {
    return THEMES.indexOf(value) >= 0 ? value : 'system';
  }

  function applyTheme(pref) {
    var root = document.documentElement;
    if (!pref || pref === 'system') {
      root.removeAttribute('data-theme');
      return;
    }
    root.setAttribute('data-theme', pref === 'light' ? 'light' : 'dark');
  }

  function initThemeButton(button) {
    var saved = normalizeTheme(localStorage.getItem(STORAGE_KEY) || 'system');
    applyTheme(saved);
    if (!button || button.dataset.shellBound === '1') {
      return;
    }
    button.dataset.shellBound = '1';
    button.addEventListener('click', function () {
      var current = normalizeTheme(
        localStorage.getItem(STORAGE_KEY) || saved || 'system'
      );
      var idx = THEMES.indexOf(current);
      var next = THEMES[(idx + 1) % THEMES.length];
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
    });
  }

  function initOptionsMenu(button, menu) {
    if (!button || !menu || button.dataset.shellBound === '1') {
      return;
    }
    function closeMenu() {
      menu.setAttribute('hidden', 'hidden');
    }
    button.dataset.shellBound = '1';
    button.addEventListener('click', function (e) {
      e.stopPropagation();
      if (menu.hasAttribute('hidden')) {
        menu.removeAttribute('hidden');
      } else {
        closeMenu();
      }
    });
    document.addEventListener('click', closeMenu);
    menu.addEventListener('click', function (e) {
      e.stopPropagation();
    });
  }

  function initShellChrome() {
    initThemeButton(document.getElementById('themeToggle'));
    initOptionsMenu(
      document.getElementById('optionsBtn'),
      document.getElementById('optionsMenu')
    );
  }

  window.applyShellTheme = applyTheme;
  window.initShellChrome = initShellChrome;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShellChrome);
  } else {
    initShellChrome();
  }
})();
