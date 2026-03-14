async function openSearchWorkspace() {
  openModalById('searchModal');
  await refreshStatus();
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
    el.addEventListener('click', handler);
  }
}

function setupModalBindings() {
  bindClick('openConfig', () => {
    openModalById('configModal');
    refreshUiState({ sync: true });
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
    refreshUiState({ sync: true });
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
    const closeHandler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      forceCloseModals();
    };
    overlayEl.addEventListener('pointerdown', closeHandler, true);
    overlayEl.addEventListener('click', closeHandler, true);
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
    if (el) el.addEventListener('click', () => scheduleStatusPoll());
  });
}

window.openSearchWorkspace = openSearchWorkspace;
window.openStatusModal = openStatusModal;
window.setupModalBindings = setupModalBindings;
