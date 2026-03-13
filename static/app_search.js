(function () {
  if (window.__appSearchFlowDelegated) return;
  window.__appSearchFlowDelegated = true;

  var missing = function (name, fallback) {
    if (typeof window[name] === 'function') return;
    window[name] = fallback;
  };

  missing('setBusyButton', function (btn, busyText, idleText) {
    if (!btn) return function () {};
    var original = typeof idleText === 'string' ? idleText : btn.textContent;
    btn.disabled = true;
    btn.textContent = busyText || 'Aguarde...';
    return function () {
      btn.disabled = false;
      btn.textContent = original;
    };
  });

  missing('setSearchMeta', function (text, level) {
    var el = document.getElementById('searchMeta');
    if (!el) return;
    el.textContent = text || '';
    el.classList.remove('warn', 'error');
    if (level === 'warn' || level === 'error') {
      el.classList.add(level);
    }
  });

  missing('onSelectRowClick', function (ev, nameEnc) {
    if (
      ev &&
      ev.target &&
      ev.target.closest &&
      ev.target.closest('.file-actions')
    )
      return;
    if (!window.selectUpload) return;
    window.selectUpload(nameEnc, null);
  });

  missing('deleteUpload', async function (nameEnc, btn) {
    if (!window.confirm || !window.confirm('Deseja realmente excluir este arquivo?')) {
      return;
    }
    if (!window.selectUpload) return;
    var restoreBtn = window.setBusyButton
      ? window.setBusyButton(btn, 'Excluindo...', 'Excluir')
      : null;
    try {
      var name = decodeURIComponent(nameEnc);
      var j = await window.apiJSON('/admin/delete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ filename: name }),
      });
      if (j && j.ok && window.refreshUiState) {
        window.refreshUiState();
      }
    } catch (e) {
      if (window.setSearchMeta) window.setSearchMeta('Erro ao excluir.', 'error');
      if (window.logUi) window.logUi('ERROR', 'delete falhou');
    } finally {
      if (restoreBtn) restoreBtn();
    }
  });

  missing('selectUpload', async function (nameEnc, btn) {
    var name = decodeURIComponent(nameEnc);
    var msg = document.getElementById('uploadMsg');
    var restoreBtn = window.setBusyButton
      ? window.setBusyButton(btn, 'Selecionando...', 'Selecionar')
      : null;
    if (msg) msg.textContent = 'Selecionando: ' + name;
    try {
      var j = await window.apiJSON('/admin/select', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ filename: name }),
      });
      if (j && j.ok) {
        if (msg) msg.textContent = 'DB selecionado: ' + name;
        if (window.refreshUiState) await window.refreshUiState();
        if (window.closeModal) window.closeModal();
      } else if (msg) {
        msg.textContent = 'Erro ao selecionar: ' + ((j && j.error) || 'falha');
      }
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao selecionar DB';
      if (window.setSearchMeta) window.setSearchMeta('Erro ao selecionar DB.', 'error');
    } finally {
      if (restoreBtn) restoreBtn();
    }
  });

  missing('selectDbFromTab', async function (nameEnc) {
    var name = decodeURIComponent(nameEnc);
    var msg = document.getElementById('uploadMsg');
    if (msg) msg.textContent = 'Selecionando: ' + name;
    try {
      var j = await window.apiJSON('/admin/select', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ filename: name }),
      });
      if (j && j.ok) {
        if (msg) msg.textContent = 'DB selecionado: ' + name;
        if (window.refreshUiState) await window.refreshUiState();
      } else if (msg) {
        msg.textContent = 'Erro ao selecionar: ' + ((j && j.error) || 'falha');
      }
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao selecionar DB';
    }
  });

  missing('tableTagId', function (name) {
    return 'tag-' + encodeURIComponent(name);
  });

  missing('doSearch', function () {
    alert('Fluxo de busca temporariamente indisponivel. Recarregue o sistema.');
  });
})();
