// ==== Modais e botoes principais ====

document.addEventListener('DOMContentLoaded', () => {
  const openConfigBtn = $('openConfig');
  if (openConfigBtn) {
    openConfigBtn.addEventListener('click', () => {
      openModalById('configModal');
      refreshUiState({ sync: true });
    });
  }

  const openPriorityBtn = $('openPriority');
  if (openPriorityBtn) {
    openPriorityBtn.addEventListener('click', () => {
      openModalById('priorityModal');
      loadPriorityModal();
    });
  }
  const refreshPriorityBtnModal = $('refreshPriorityBtnModal');
  if (refreshPriorityBtnModal)
    refreshPriorityBtnModal.addEventListener('click', () => loadPriorityModal());
  const savePriorityBtnModal = $('savePriorityBtnModal');
  if (savePriorityBtnModal)
    savePriorityBtnModal.addEventListener('click', () => {
      savePriority();
    });

  const openIndexBtn = $('openIndex');
  if (openIndexBtn) {
    openIndexBtn.addEventListener('click', () => {
      openModalById('indexModal');
      refreshStatus();
    });
  }

  const openIndexInline = $('openIndexInline');
  if (openIndexInline) {
    openIndexInline.addEventListener('click', ev => {
      ev.preventDefault();
      openModalById('indexModal');
      refreshStatus();
    });
  }

  const openSelectInline = $('openSelectInline');
  if (openSelectInline) {
    openSelectInline.addEventListener('click', ev => {
      ev.preventDefault();
      openModalById('configModal');
      refreshUiState({ sync: true });
    });
  }

  async function openStatusModal() {
    openModalById('statusModal');
    try {
      await refreshStatus();
      await fetchServerLogs();
      renderStatusModal();
      logUi('INFO', 'detalhes abertos');
    } catch (e) {
      renderStatusModal();
      logUi('ERROR', 'detalhes falhou');
    }
  }
  window.openStatusModal = openStatusModal;

  const openConvertInline = $('openConvertInline');
  if (openConvertInline) {
    openConvertInline.addEventListener('click', async ev => {
      ev.preventDefault();
      await openStatusModal();
    });
  }

  const stepConvert = $('stepConvert');
  if (stepConvert) {
    stepConvert.addEventListener('click', async ev => {
      if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
      await openStatusModal();
    });
  }

  const openSearchInline = $('openSearchInline');
  if (openSearchInline) {
    openSearchInline.addEventListener('click', ev => {
      ev.preventDefault();
      openModalById('searchModal');
      refreshStatus();
      const q = $('q');
      if (q && !q.disabled) {
        q.focus();
        q.select();
      }
    });
  }

  const stepIndex = $('stepIndex');
  if (stepIndex) {
    stepIndex.addEventListener('click', ev => {
      if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
      openModalById('indexModal');
      refreshStatus();
    });
  }

  const stepSearch = $('stepSearch');
  if (stepSearch) {
    stepSearch.addEventListener('click', ev => {
      if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
      openModalById('searchModal');
      refreshStatus();
      const q = $('q');
      if (q && !q.disabled) {
        q.focus();
        q.select();
      }
    });
  }
  const dbSearchBtn = $('dbSearchBtn');
  if (dbSearchBtn) {
    dbSearchBtn.addEventListener('click', ev => {
      ev.preventDefault();
      openModalById('searchModal');
      refreshStatus();
      const q = $('q');
      if (q && !q.disabled) {
        q.focus();
        q.select();
      }
    });
  }

  const openStatusBtn = $('openStatus');
  if (openStatusBtn) {
    openStatusBtn.addEventListener('click', async () => {
      await openStatusModal();
    });
  }

  const statusAlerts = $('statusAlerts');
  if (statusAlerts) {
    statusAlerts.addEventListener('click', async () => {
      await openStatusModal();
    });
  }

  const openHelpBuscaBtn = $('openHelpBusca');
  if (openHelpBuscaBtn) {
    openHelpBuscaBtn.addEventListener('click', () => {
      const box = $('helpBuscaBox');
      if (!box) return;
      const isHidden = box.style.display === 'none' || box.style.display === '';
      box.style.display = isHidden ? 'block' : 'none';
    });
  }

  const closeStatusBtn = $('closeStatus');
  if (closeStatusBtn) closeStatusBtn.addEventListener('click', () => closeModal());
  const closeConfigBtn = $('closeConfig');
  if (closeConfigBtn) closeConfigBtn.addEventListener('click', () => closeModal());
  const closePriorityBtn = $('closePriority');
  if (closePriorityBtn) closePriorityBtn.addEventListener('click', () => closeModal());
  const closeIndexBtn = $('closeIndex');
  if (closeIndexBtn) closeIndexBtn.addEventListener('click', () => closeModal());
  const closeSearchBtn = $('closeSearch');
  if (closeSearchBtn) closeSearchBtn.addEventListener('click', () => closeModal());

  const overlayEl = $('overlay');
  if (overlayEl) {
    const closeHandler = e => {
      e.preventDefault();
      e.stopPropagation();
      forceCloseModals();
    };
    overlayEl.addEventListener('mousedown', closeHandler, true);
    overlayEl.addEventListener('click', closeHandler, true);
    overlayEl.onclick = closeHandler;
    overlayEl.addEventListener('mouseup', closeHandler, true);
    overlayEl.addEventListener('pointerdown', closeHandler, true);
    overlayEl.addEventListener('pointerup', closeHandler, true);
  }

  ['openConfig', 'openPriority', 'openIndex', 'closeConfig', 'closePriority', 'closeIndex', 'closeSearch', 'overlay'].forEach(
    id => {
      const el = $(id);
      if (el) el.addEventListener('click', () => scheduleStatusPoll());
    }
  );

  const openFilesBtn = $('openFilesBtn');
  if (openFilesBtn) {
    openFilesBtn.addEventListener('click', () => {
      // fecha qualquer modal que possa estar tampando o painel de arquivos
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

  // Upload / select / delete
  const uploadBtn = $('uploadBtn');
  if (uploadBtn) {
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
              msg.textContent =
                'Conversao iniciada: ' + (nameHint || f.name) + ' (' + sizeText + ')';
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
      }
    });
  }
  const refreshFilesBtn = $('refreshFilesBtn');
  if (refreshFilesBtn) refreshFilesBtn.addEventListener('click', () => refreshUiState());
  const filesSort = $('filesSort');
  if (filesSort) filesSort.addEventListener('change', () => renderFilesMain());

  const dbSort = $('dbSort');
  if (dbSort) dbSort.addEventListener('change', () => renderDbTabs());

  // Flow tabs
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

  // Auto index toggle
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
        if (msg)
          msg.textContent = 'Auto indexacao: ' + (j.auto_index_after_convert ? 'on' : 'off');
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
  if (startIndexBtn) {
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
      }
    });
  }

  // Busca
  const searchBtn = $('searchBtn');
  if (searchBtn) searchBtn.addEventListener('click', () => doSearch());
  const qInput = $('q');
  if (qInput)
    qInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') doSearch();
    });
  const refreshBtn = $('refreshBtn');
  if (refreshBtn) refreshBtn.addEventListener('click', () => refreshUiState());
  const refreshTablesBtn = $('refreshTables');
  if (refreshTablesBtn) refreshTablesBtn.addEventListener('click', () => refreshTables());
  const filterTablesInput = $('filterTables');
  if (filterTablesInput) filterTablesInput.addEventListener('input', () => refreshTables());
  const exportAllBtn = $('exportAllBtn');
  if (exportAllBtn) exportAllBtn.addEventListener('click', () => exportResultsCsv());
  const minScoreInput = $('min_score');
  if (minScoreInput)
    minScoreInput.addEventListener('input', () => {
      const minScoreVal = $('minScoreVal');
      if (minScoreVal) minScoreVal.textContent = minScoreInput.value;
    });
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

  setFlowHint('', false);
  window.addEventListener('popstate', e => {
    if (e.state && e.state.q) {
      applySearchState(e.state);
      doSearch({ skipHistory: true });
    } else {
      refreshUiState();
    }
  });
  logUi('INFO', 'modal exists=' + !!$('configModal'));
  refreshUiState({ sync: true });
  scheduleStatusPoll();
});

