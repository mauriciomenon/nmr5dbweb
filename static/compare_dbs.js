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

function getCompareFormRefs() {
  return {
    db1Input: document.getElementById('db1Path'),
    db2Input: document.getElementById('db2Path'),
    tableSelect: document.getElementById('tableSelect'),
    keyCols: document.getElementById('keyColumns'),
    cmpCols: document.getElementById('compareColumns'),
    keyFilterEl: document.getElementById('keyFilter'),
    cbChanged: document.getElementById('filterChanged'),
    cbAdded: document.getElementById('filterAdded'),
    cbRemoved: document.getElementById('filterRemoved'),
    colSelect: document.getElementById('filterColumn'),
    rowLimitEl: document.getElementById('rowLimit'),
    rowLimitEnabledEl: document.getElementById('rowLimitEnabled'),
  };
}

function buildCompareFormState() {
  const {
    db1Input,
    db2Input,
    tableSelect,
    keyCols,
    cmpCols,
    keyFilterEl,
    cbChanged,
    cbAdded,
    cbRemoved,
    colSelect,
    rowLimitEl,
    rowLimitEnabledEl,
  } = getCompareFormRefs();
  return {
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
  };
}

function applyCompareFormState(saved) {
  const {
    db1Input,
    db2Input,
    keyCols,
    cmpCols,
    keyFilterEl,
    cbChanged,
    cbAdded,
    cbRemoved,
    colSelect,
    rowLimitEl,
    rowLimitEnabledEl,
  } = getCompareFormRefs();
  if (db1Input && typeof saved.db1Path === 'string')
    db1Input.value = saved.db1Path;
  if (db2Input && typeof saved.db2Path === 'string')
    db2Input.value = saved.db2Path;
  if (keyCols && typeof saved.keyColumns === 'string')
    keyCols.value = saved.keyColumns;
  if (cmpCols && typeof saved.compareColumns === 'string')
    cmpCols.value = saved.compareColumns;
  if (keyFilterEl && typeof saved.keyFilter === 'string')
    keyFilterEl.value = saved.keyFilter;
  if (cbChanged && typeof saved.filterChanged === 'boolean')
    cbChanged.checked = saved.filterChanged;
  if (cbAdded && typeof saved.filterAdded === 'boolean')
    cbAdded.checked = saved.filterAdded;
  if (cbRemoved && typeof saved.filterRemoved === 'boolean')
    cbRemoved.checked = saved.filterRemoved;
  if (colSelect && typeof saved.filterColumn === 'string')
    colSelect.value = saved.filterColumn;
  if (rowLimitEl && typeof saved.rowLimit === 'string')
    rowLimitEl.value = saved.rowLimit;
  if (rowLimitEnabledEl && typeof saved.rowLimitEnabled === 'boolean') {
    rowLimitEnabledEl.checked = saved.rowLimitEnabled;
  }
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
  let resp = null;
  try {
    resp = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (networkError) {
    const err = new Error(
      'falha de rede ao chamar ' +
        path +
        ': ' +
        (networkError && networkError.message
          ? networkError.message
          : String(networkError))
    );
    err.status = 0;
    err.payload = null;
    throw err;
  }
  let data = null;
  let rawText = '';
  try {
    rawText = await resp.text();
    data = rawText ? JSON.parse(rawText) : null;
  } catch (error) {
    data = null;
  }
  if (!resp.ok) {
    const apiMsg = data && (data.message || data.error);
    const tail = rawText ? String(rawText).trim().slice(0, 180) : '';
    const err = new Error(
      apiMsg ||
        (tail
          ? `resposta HTTP ${resp.status}: ${tail}`
          : 'resposta HTTP ' + resp.status)
    );
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
    const state = {
      ...buildCompareFormState(),
      tablesLoadedOnce: compareDbState.tablesLoadedOnce,
      currentOpenStep: compareDbState.currentOpenStep,
      lastComparePayload: compareDbState.lastComparePayload,
      lastCompareMeta: compareDbState.lastCompareMeta,
    };
    localStorage.setItem(compareDbState.compareStateKey, JSON.stringify(state));
  } catch (e) {
    console.warn('Nao foi possivel salvar estado da comparacao:', e);
    try {
      setFlowHint(
        'Nao foi possivel salvar estado local da comparacao neste navegador.',
        'warn'
      );
    } catch (ignore) {}
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
window.getCompareFormRefs = getCompareFormRefs;
window.buildCompareFormState = buildCompareFormState;
window.applyCompareFormState = applyCompareFormState;
window.setButtonBusy = setButtonBusy;
window.postJson = postJson;
window.setCompareBusy = setCompareBusy;
window.clearCompareBusy = clearCompareBusy;
window.setCompareStatus = setCompareStatus;
window.updateLastCompareMeta = updateLastCompareMeta;
window.saveCompareState = saveCompareState;
window.updateTablesOverviewVisibility = updateTablesOverviewVisibility;
