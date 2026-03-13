// Compare page state and shared helpers.

const compareDbState =
  window.compareDbState ||
  (window.compareDbState = {
    tablesMeta: [],
    lastComparePayload: null,
    lastCompareMeta: null,
    uploadTimeouts: { A: null, B: null },
    tablesTimeout: null,
    currentOpenStep: 1,
    tablesLoadedOnce: false,
    compareStateKey: 'duckdb_compare_dbs_state_v1',
    tablesOverviewCache: null,
    tablesOverviewVisible: false,
  });

function setFlowHint(message, variant = 'info') {
  const hintEl = document.getElementById('flowHint');
  if (!hintEl) return;
  hintEl.textContent = message || '';
  hintEl.className = 'flow-hint';
  if (['info', 'warn', 'error'].includes(variant)) {
    hintEl.classList.add(variant);
  }
}

function setStepState(stepId, statusText, state) {
  let cardId = null;
  let statusSpanId = null;
  if (stepId === 'stepPickFiles') {
    cardId = 'step1Card';
    statusSpanId = 'step1Status';
  } else if (stepId === 'stepLoadTables') {
    cardId = 'step2Card';
    statusSpanId = 'step2Status';
  } else if (stepId === 'stepCompare') {
    cardId = 'step3Card';
    statusSpanId = 'step3Status';
  } else {
    return;
  }
  const card = document.getElementById(cardId);
  const statusEl = document.getElementById(statusSpanId);
  if (!card || !statusEl) return;
  if (typeof statusText === 'string' && statusText.length) {
    statusEl.textContent = statusText;
  }
  card.classList.remove('step-done', 'step-active', 'step-warn');
  if (state === 'done') card.classList.add('step-done');
  if (state === 'active') card.classList.add('step-active');
  if (state === 'warn') card.classList.add('step-warn');
}

function setStepOpen(step) {
  compareDbState.currentOpenStep = step;
  [1, 2, 3].forEach((n) => {
    const card = document.getElementById('step' + n + 'Card');
    if (!card) return;
    if (step === n) card.classList.add('step-open');
    else card.classList.remove('step-open');
  });
}

function toggleStep(step) {
  if (compareDbState.currentOpenStep === step) {
    setStepOpen(null);
  } else {
    setStepOpen(step);
  }
}

function resetFlowToInitial() {
  setFlowHint('Comece escolhendo os arquivos A e B em .duckdb.', 'info');
  setStepState('stepPickFiles', 'Pendente', 'active');
  setStepState('stepLoadTables', 'Aguardando', null);
  setStepState('stepCompare', 'Aguardando', null);
  setStepOpen(1);
}

function updateRowLimitState() {
  const cb = document.getElementById('rowLimitEnabled');
  const input = document.getElementById('rowLimit');
  if (!cb || !input) return;
  const enabled = cb.checked;
  input.disabled = !enabled;
  input.style.opacity = enabled ? '1' : '0.6';
}

function setUploadStatus(message, isError = false) {
  const el = document.getElementById('uploadStatus');
  if (!el) return;
  el.textContent = message || '';
  el.style.color = isError ? '#fecaca' : '#9ca3af';
}

function getRunCompareButton() {
  return document.getElementById('runCompareBtn');
}

function getCompareActionButtons() {
  return {
    loadTables: document.getElementById('btnLoadTables'),
    runCompare: document.getElementById('runCompareBtn'),
    tablesOverview: document.getElementById('btnTablesOverview'),
    exportComparison: document.getElementById('btnExportComparison'),
    exportReportJson: document.getElementById('btnExportReportJson'),
  };
}

function setButtonBusy(btn, busyText, idleText) {
  if (!btn) return () => {};
  const original = idleText || btn.textContent;
  btn.disabled = true;
  btn.textContent = busyText;
  return () => {
    btn.disabled = false;
    btn.textContent = original;
  };
}

async function postJson(path, payload) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let data = null;
  try {
    data = await resp.json();
  } catch (error) {
    data = null;
  }
  if (!resp.ok) {
    const apiMsg = data && (data.message || data.error);
    const err = new Error(apiMsg || 'resposta HTTP ' + resp.status);
    err.payload = data;
    err.status = resp.status;
    throw err;
  }
  return data;
}

function setCompareBusy(statusText, flowText, stepText, slowText) {
  const statusEl = document.getElementById('statusCompare');
  const btn = getRunCompareButton();
  if (statusEl) statusEl.textContent = statusText;
  setFlowHint(flowText, 'info');
  setStepState('stepCompare', stepText, 'active');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Comparando...';
  }
  return setTimeout(() => {
    if (statusEl) statusEl.textContent = slowText;
  }, 60000);
}

function clearCompareBusy(timeoutId, buttonText = 'Comparar tabela') {
  if (timeoutId) clearTimeout(timeoutId);
  const btn = getRunCompareButton();
  if (btn) {
    btn.disabled = false;
    btn.textContent = buttonText;
  }
}

function setCompareStatus(text, level = 'info') {
  const statusEl = document.getElementById('statusCompare');
  if (!statusEl) return;
  statusEl.textContent = text || '';
  statusEl.classList.remove('warn', 'error');
  if (level === 'warn' || level === 'error') {
    statusEl.classList.add(level);
  }
}

function updateLastCompareMeta(data, fallbackPage = 1) {
  compareDbState.lastCompareMeta = {
    total_filtered_rows:
      typeof data.total_filtered_rows === 'number'
        ? data.total_filtered_rows
        : data.row_count || 0,
    page: data.page || fallbackPage,
    total_pages: data.total_pages || 1,
  };
}

function saveCompareState() {
  try {
    const db1Input = document.getElementById('db1Path');
    const db2Input = document.getElementById('db2Path');
    const tableSelect = document.getElementById('tableSelect');
    const keyCols = document.getElementById('keyColumns');
    const cmpCols = document.getElementById('compareColumns');
    const keyFilterEl = document.getElementById('keyFilter');
    const cbChanged = document.getElementById('filterChanged');
    const cbAdded = document.getElementById('filterAdded');
    const cbRemoved = document.getElementById('filterRemoved');
    const colSelect = document.getElementById('filterColumn');
    const rowLimitEl = document.getElementById('rowLimit');
    const rowLimitEnabledEl = document.getElementById('rowLimitEnabled');

    const state = {
      db1Path: db1Input ? db1Input.value : '',
      db2Path: db2Input ? db2Input.value : '',
      table: tableSelect ? tableSelect.value : '',
      keyColumns: keyCols ? keyCols.value : '',
      compareColumns: cmpCols ? cmpCols.value : '',
      keyFilter: keyFilterEl ? keyFilterEl.value : '',
      filterChanged: cbChanged ? cbChanged.checked : true,
      filterAdded: cbAdded ? cbAdded.checked : true,
      filterRemoved: cbRemoved ? cbRemoved.checked : true,
      filterColumn: colSelect ? colSelect.value : '',
      rowLimit: rowLimitEl ? rowLimitEl.value : '',
      rowLimitEnabled: rowLimitEnabledEl ? rowLimitEnabledEl.checked : true,
      tablesLoadedOnce: compareDbState.tablesLoadedOnce,
      currentOpenStep: compareDbState.currentOpenStep,
      lastComparePayload: compareDbState.lastComparePayload,
      lastCompareMeta: compareDbState.lastCompareMeta,
    };
    localStorage.setItem(compareDbState.compareStateKey, JSON.stringify(state));
  } catch (e) {
    console.warn('Nao foi possivel salvar estado da comparacao:', e);
  }
}

function updateTablesOverviewVisibility() {
  const container = document.getElementById('tablesOverview');
  const btn = document.getElementById('btnTablesOverview');
  if (!container || !btn) return;
  container.style.display = compareDbState.tablesOverviewVisible
    ? 'block'
    : 'none';
  btn.textContent = compareDbState.tablesOverviewVisible
    ? 'Ocultar mapa das tabelas'
    : 'Mapa geral das tabelas';
}

document.addEventListener('DOMContentLoaded', async () => {
  setupCompareUploadBindings();
  await restoreFromSavedState();
});

window.setFlowHint = setFlowHint;
window.setStepState = setStepState;
window.setStepOpen = setStepOpen;
window.toggleStep = toggleStep;
window.resetFlowToInitial = resetFlowToInitial;
window.updateRowLimitState = updateRowLimitState;
window.setUploadStatus = setUploadStatus;
window.getRunCompareButton = getRunCompareButton;
window.getCompareActionButtons = getCompareActionButtons;
window.setButtonBusy = setButtonBusy;
window.postJson = postJson;
window.setCompareBusy = setCompareBusy;
window.clearCompareBusy = clearCompareBusy;
window.setCompareStatus = setCompareStatus;
window.updateLastCompareMeta = updateLastCompareMeta;
window.saveCompareState = saveCompareState;
window.updateTablesOverviewVisibility = updateTablesOverviewVisibility;
