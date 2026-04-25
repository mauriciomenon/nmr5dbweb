async function openSearchWorkspace() {
  openModalById('searchModal');
  try {
    await refreshStatus();
  } catch (e) {
    const errMsg = e && e.message ? e.message : 'falha';
    logUi('ERROR', 'refresh status falhou ao abrir busca: ' + errMsg);
  }
  const q = $('q');
  if (q && !q.disabled) {
    q.focus();
    q.select();
  }
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
    const errMsg = e && e.message ? e.message : 'falha';
    logUi('ERROR', 'detalhes falhou: ' + errMsg);
  }
}

function bindClick(id, handler) {
  const el = $(id);
  if (el) {
    const key = `boundClick_${String(id).replace(/[^a-zA-Z0-9_]/g, '_')}`;
    if (el.dataset && el.dataset[key] === '1') return;
    el.addEventListener('click', handler);
    if (el.dataset) el.dataset[key] = '1';
  }
}

function setupModalBindings() {
  bindClick('openConfig', () => {
    openModalById('configModal');
    refreshUiState();
  });
  bindClick('openPriority', () => {
    openModalById('priorityModal');
    loadPriorityModal();
  });
  bindClick('refreshPriorityBtnModal', () => loadPriorityModal());
  bindClick('savePriorityBtnModal', () => savePriority());
  bindClick('openIndex', () => {
    openModalById('indexModal');
    refreshStatus();
  });
  bindClick('openIndexInline', (ev) => {
    ev.preventDefault();
    openModalById('indexModal');
    refreshStatus();
  });
  bindClick('openSelectInline', (ev) => {
    ev.preventDefault();
    openModalById('configModal');
    refreshUiState();
  });
  bindClick('openConvertInline', async (ev) => {
    ev.preventDefault();
    await openStatusModal();
  });
  bindClick('stepConvert', async (ev) => {
    if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
    await openStatusModal();
  });
  bindClick('openSearchInline', async (ev) => {
    ev.preventDefault();
    await openSearchWorkspace();
  });
  bindClick('stepIndex', (ev) => {
    if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
    openModalById('indexModal');
    refreshStatus();
  });
  bindClick('stepSearch', async (ev) => {
    if (ev && ev.target && ev.target.tagName === 'BUTTON') return;
    await openSearchWorkspace();
  });
  bindClick('dbSearchBtn', async (ev) => {
    ev.preventDefault();
    await openSearchWorkspace();
  });
  bindClick('openStatus', async () => {
    await openStatusModal();
  });
  bindClick('statusAlerts', async () => {
    await openStatusModal();
  });
  bindClick('openHelpBusca', () => {
    const box = $('helpBuscaBox');
    if (!box) return;
    const isHidden = box.style.display === 'none' || box.style.display === '';
    box.style.display = isHidden ? 'block' : 'none';
  });

  [
    'closeStatus',
    'closeConfig',
    'closePriority',
    'closeIndex',
    'closeSearch',
  ].forEach((id) => {
    bindClick(id, () => closeModal());
  });

  const overlayEl = $('overlay');
  if (overlayEl) {
    if (!(overlayEl.dataset && overlayEl.dataset.overlayCloseBound === '1')) {
      const closeHandler = (e) => {
        e.preventDefault();
        e.stopPropagation();
        forceCloseModals();
      };
      overlayEl.addEventListener('click', closeHandler, true);
      if (overlayEl.dataset) overlayEl.dataset.overlayCloseBound = '1';
    }
  }

  [
    'openConfig',
    'openPriority',
    'openIndex',
    'closeConfig',
    'closePriority',
    'closeIndex',
    'closeSearch',
    'overlay',
  ].forEach((id) => {
    const el = $(id);
    if (!el) return;
    if (el.dataset && el.dataset.boundStatusPoll === '1') return;
    el.addEventListener('click', () => scheduleStatusPoll());
    if (el.dataset) el.dataset.boundStatusPoll = '1';
  });
}

window.openSearchWorkspace = openSearchWorkspace;
window.openStatusModal = openStatusModal;
window.setupModalBindings = setupModalBindings;
