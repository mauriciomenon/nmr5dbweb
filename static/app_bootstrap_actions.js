function setupFilePanelBindings() {
  const openFilesBtn = $('openFilesBtn');
  if (openFilesBtn) {
    openFilesBtn.addEventListener('click', () => {
      try { forceCloseModals(); } catch (e) {}
      setFilesPanelOpen(!filesPanelOpen);
      if (filesPanelOpen) {
        const panel = $('filesPanel');
        if (panel && typeof panel.scrollIntoView === 'function') {
          panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    });
  }
  const closeFilesBtn = $('closeFilesBtn');
  if (closeFilesBtn) {
    closeFilesBtn.addEventListener('click', () => setFilesPanelOpen(false));
  }
  const refreshFilesBtn = $('refreshFilesBtn');
  if (refreshFilesBtn) refreshFilesBtn.addEventListener('click', () => refreshUiState());
  const filesSort = $('filesSort');
  if (filesSort) filesSort.addEventListener('change', () => renderFilesMain());
  const dbSort = $('dbSort');
  if (dbSort) dbSort.addEventListener('change', () => renderDbTabs());
}

function setupUploadBindings() {
  const uploadBtn = $('uploadBtn');
  if (!uploadBtn) return;
  uploadBtn.addEventListener('click', async () => {
    const fi = $('fileInput');
    const msg = $('uploadMsg');
    if (!fi || !fi.files.length) {
      if (msg) msg.textContent = 'Selecione um arquivo.';
      return;
    }
    const f = fi.files[0];
    if (!isFileAllowedForFlow(f.name, currentFlow)) {
      const flowMsg =
        currentFlow === 'access'
          ? 'Use .mdb ou .accdb neste fluxo.'
          : 'Use .duckdb, .db, .sqlite, .sqlite3 neste fluxo.';
      if (msg) msg.textContent = flowMsg;
      setFlowBanner(flowMsg + ' Voce pode alternar o fluxo acima.', 'warn');
      return;
    }
    const sizeText = formatBytes(f.size || 0);
    const fd = new FormData();
    fd.append('file', f);
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Enviando...';
    if (msg) msg.textContent = 'Enviando...';
    try {
      const res = await fetch('/admin/upload', { method: 'POST', body: fd });
      const j = await res.json();
      const nameHint = shortName(
        (j && (j.db_path || j.db || j.output || j.input)) || f.name || ''
      );
      if (j && j.ok) {
        if (msg) {
          if (j.status === 'converting') {
            msg.textContent = 'Conversao iniciada: ' + (nameHint || f.name) + ' (' + sizeText + ')';
          } else {
            msg.textContent = 'Upload ok: ' + (nameHint || f.name) + ' (' + sizeText + ')';
          }
        }
        setFlowBanner('', '');
      } else if (j && j.error) {
        if (msg) msg.textContent = 'Erro: ' + j.error;
        setFlowBanner('Falha no upload. Verifique o arquivo e tente novamente.', 'error');
      } else {
        if (msg) msg.textContent = 'Falha no upload';
        setFlowBanner('Falha ao enviar arquivo. Tente novamente.', 'error');
      }
      await refreshUiState();
    } catch (e) {
      if (msg) msg.textContent = 'Erro no upload';
      setFlowBanner('Erro no upload. Verifique o servidor e tente novamente.', 'error');
      logUi('ERROR', 'upload falhou');
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.textContent = 'Enviar';
    }
  });
}

function setupFlowBindings() {
  const flowTabButtons = document.querySelectorAll('#flowTabs .tab-btn');
  flowTabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const flow = btn.getAttribute('data-flow') || 'duckdb';
      manualFlowOverride = normalizeFlow(flow);
      setFlow(manualFlowOverride);
      if (!lastUploads.length) {
        refreshUiState();
        return;
      }
      renderFilesSelect();
      renderSelectedInfo();
    });
  });
}

function setupIndexBindings() {
  const autoIndexToggleEl = $('autoIndexToggle');
  if (autoIndexToggleEl) {
    autoIndexToggleEl.addEventListener('change', async () => {
      const enabled = autoIndexToggleEl.checked;
      const res = await fetch('/admin/set_auto_index', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      const j = await res.json();
      const msg = $('autoIndexMsg');
      if (j && j.ok) {
        if (msg) {
          msg.textContent = 'Auto indexacao: ' + (j.auto_index_after_convert ? 'on' : 'off');
        }
      } else if (msg) {
        msg.textContent = 'Erro ao atualizar auto indexacao';
      }
    });
  }

  const resetIndexDefaultsBtn = $('resetIndexDefaults');
  if (resetIndexDefaultsBtn) {
    resetIndexDefaultsBtn.addEventListener('click', () => {
      if ($('chunk')) $('chunk').value = 2000;
      if ($('batch')) $('batch').value = 1000;
      if ($('dropCheckbox')) $('dropCheckbox').checked = false;
      const msg = $('indexMsg');
      if (msg) {
        msg.textContent = 'Valores padrao restaurados.';
        setTimeout(() => {
          msg.textContent = '';
        }, 2000);
      }
    });
  }

  const startIndexBtn = $('startIndex');
  if (!startIndexBtn) return;
  startIndexBtn.addEventListener('click', async () => {
    const msg = $('indexMsg');
    if (!hasDbSelected()) {
      if (msg) msg.textContent = 'Selecione um DB primeiro.';
      return;
    }
    const statusDbFlow = lastStatus ? getFlowFromName(lastStatus.db || '') : '';
    if (lastStatus && statusDbFlow !== 'duckdb') {
      if (msg) msg.textContent = 'Indice _fulltext disponivel apenas para DuckDB.';
      return;
    }
    if (lastStatus && lastStatus.conversion && lastStatus.conversion.running) {
      if (msg) msg.textContent = 'Aguarde a conversao terminar.';
      return;
    }
    const drop = !!($('dropCheckbox') && $('dropCheckbox').checked);
    const chunkVal = parseInt(($('chunk') || {}).value || '2000', 10);
    const batchVal = parseInt(($('batch') || {}).value || '1000', 10);
    const chunk = Number.isFinite(chunkVal) && chunkVal > 0 ? chunkVal : 2000;
    const batch = Number.isFinite(batchVal) && batchVal > 0 ? batchVal : 1000;
    if (msg) msg.textContent = 'Iniciando indexacao...';
    startIndexBtn.disabled = true;
    startIndexBtn.textContent = 'Iniciando...';
    try {
      const res = await apiJSON('/admin/start_index', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ drop, chunk, batch })
      });
      if (res && res.ok) {
        if (msg) msg.textContent = 'Indexacao iniciada.';
        await refreshStatus();
        scheduleStatusPoll();
      } else if (res && res.error) {
        if (msg) msg.textContent = 'Erro: ' + res.error;
      } else if (msg) {
        msg.textContent = 'Falha ao iniciar indexacao';
      }
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao iniciar indexacao';
      logUi('ERROR', 'indexacao falhou');
    } finally {
      startIndexBtn.disabled = false;
      startIndexBtn.textContent = 'Iniciar indexacao';
    }
  });
}

function setupSearchBindings() {
  const searchBtn = $('searchBtn');
  if (searchBtn) searchBtn.addEventListener('click', () => doSearch());
  const qInput = $('q');
  if (qInput) {
    qInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        doSearch();
      }
    });
  }
  const refreshBtn = $('refreshBtn');
  if (refreshBtn) refreshBtn.addEventListener('click', () => refreshUiState());
  const refreshTablesBtn = $('refreshTables');
  if (refreshTablesBtn) refreshTablesBtn.addEventListener('click', () => refreshTables());
  const filterTablesInput = $('filterTables');
  if (filterTablesInput) filterTablesInput.addEventListener('input', () => refreshTables());
  const exportAllBtn = $('exportAllBtn');
  if (exportAllBtn) exportAllBtn.addEventListener('click', () => exportResultsCsv());
  const minScoreInput = $('min_score');
  if (minScoreInput) {
    minScoreInput.addEventListener('input', () => {
      const minScoreVal = $('minScoreVal');
      if (minScoreVal) minScoreVal.textContent = minScoreInput.value;
    });
  }
  const clearTablesBtn = $('clearTablesFilter');
  if (clearTablesBtn) {
    clearTablesBtn.addEventListener('click', () => {
      const sel = $('tablesFilter');
      if (!sel) return;
      Array.from(sel.options).forEach(o => (o.selected = false));
    });
  }
  const resetAdvancedBtn = $('resetAdvanced');
  if (resetAdvancedBtn) {
    resetAdvancedBtn.addEventListener('click', () => {
      resetAdvancedDefaults();
      const msg = $('advancedMsg');
      if (msg) {
        msg.textContent = 'Valores padrao restaurados.';
        setTimeout(() => {
          msg.textContent = '';
        }, 2000);
      }
    });
  }
}

function setupBootstrapGlobalHandlers() {
  window.addEventListener('popstate', e => {
    if (e.state && e.state.q) {
      applySearchState(e.state);
      doSearch({ skipHistory: true });
    } else {
      refreshUiState();
    }
  });
}

window.setupFilePanelBindings = setupFilePanelBindings;
window.setupUploadBindings = setupUploadBindings;
window.setupFlowBindings = setupFlowBindings;
window.setupIndexBindings = setupIndexBindings;
window.setupSearchBindings = setupSearchBindings;
window.setupBootstrapGlobalHandlers = setupBootstrapGlobalHandlers;
