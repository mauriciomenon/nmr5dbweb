async function loadTables() {
  const db1 = document.getElementById('db1Path').value.trim();
  const db2 = document.getElementById('db2Path').value.trim();
  const statusEl = document.getElementById('statusMeta');
  const tableSelect = document.getElementById('tableSelect');
  const btn = document.getElementById('btnLoadTables');
  compareDbState.tablesMeta = [];
  compareDbState.tablesLoadedOnce = false;
  compareDbState.tablesOverviewCache = null;
  compareDbState.tablesOverviewVisible = false;
  updateTablesOverviewVisibility();
  tableSelect.innerHTML = '<option value="">carregando...</option>';
  statusEl.textContent = 'Carregando tabelas em comum...';
  const restoreBtn = setButtonBusy(
    btn,
    'Carregando...',
    btn ? btn.textContent : 'Mapear tabelas comuns'
  );

  if (compareDbState.tablesTimeout) {
    clearTimeout(compareDbState.tablesTimeout);
    compareDbState.tablesTimeout = null;
  }
  compareDbState.tablesTimeout = setTimeout(() => {
    statusEl.textContent =
      'A carga das tabelas em comum esta levando mais de 60 segundos. Se continuar assim, pode ter ocorrido algum travamento ou os bancos sao muito grandes.';
  }, 60000);

  if (!db1 || !db2) {
    statusEl.textContent = 'Informe os caminhos de ambos os bancos (.duckdb).';
    applyCompareMissingDbState();
    tableSelect.innerHTML =
      '<option value="">-- informe os caminhos acima --</option>';
    if (compareDbState.tablesTimeout) {
      clearTimeout(compareDbState.tablesTimeout);
      compareDbState.tablesTimeout = null;
    }
    restoreBtn();
    return;
  }

  setFlowHint('Carregando tabelas em comum entre os dois bancos...', 'info');
  setStepState('stepPickFiles', 'Concluido', 'done');
  setStepState('stepLoadTables', 'Carregando...', 'active');

  try {
    const data = await postJson('/api/compare_db_tables', {
      db1_path: db1,
      db2_path: db2,
    });
    compareDbState.tablesMeta = data.tables || [];
    if (!compareDbState.tablesMeta.length) {
      statusEl.textContent =
        'Nenhuma tabela em comum encontrada entre os dois bancos.';
      tableSelect.innerHTML =
        '<option value="">-- nenhuma tabela em comum --</option>';
      setFlowHint(
        'Nenhuma tabela em comum encontrada entre os dois bancos.',
        'warn'
      );
      setStepState('stepLoadTables', 'Nenhuma tabela em comum', 'warn');
      return;
    }
    tableSelect.innerHTML = '';
    const preferredTable = 'RANGER_SOSTAT';
    for (const t of compareDbState.tablesMeta) {
      const opt = document.createElement('option');
      opt.value = t.name;
      opt.textContent = t.name;
      if (t.name && t.name.toUpperCase() === preferredTable) {
        opt.selected = true;
      }
      tableSelect.appendChild(opt);
    }
    statusEl.textContent = `Tabelas em comum: ${compareDbState.tablesMeta.length}`;
    compareDbState.tablesLoadedOnce = true;
    setFlowHint(
      'Tabelas em comum carregadas. Selecione a tabela, defina a chave K e clique em "Comparar tabela".',
      'info'
    );
    setStepState('stepLoadTables', 'Concluido', 'done');
    setStepState('stepCompare', 'Pronto para comparar', 'active');
    setStepOpen(2);
    onTableChange();
    saveCompareState();
  } catch (err) {
    console.error(err);
    statusEl.textContent = 'Erro: ' + err.message;
    tableSelect.innerHTML =
      '<option value="">-- erro ao carregar tabelas --</option>';
    setFlowHint('Erro ao carregar tabelas: ' + err.message, 'error');
    setStepState('stepLoadTables', 'Erro ao carregar', 'warn');
  } finally {
    restoreBtn();
    if (compareDbState.tablesTimeout) {
      clearTimeout(compareDbState.tablesTimeout);
      compareDbState.tablesTimeout = null;
    }
  }
}

function onTableChange() {
  const table = document.getElementById('tableSelect').value;
  const keyInput = document.getElementById('keyColumns');
  const cmpInput = document.getElementById('compareColumns');
  if (!table) return;
  const meta = compareDbState.tablesMeta.find((t) => t.name === table);
  if (!meta) return;
  const suggestedKeys = guessKeyColumnsForTable(table, meta.columns || []);
  keyInput.value = suggestedKeys.join(',');
  cmpInput.value = '';
}

const COMPARE_UI_TO_BACKEND_TYPES = {
  added: 'removed',
  removed: 'added',
  changed: 'changed',
};

function collectCompareRequest(page = 1) {
  const db1 = document.getElementById('db1Path').value.trim();
  const db2 = document.getElementById('db2Path').value.trim();
  const table = document.getElementById('tableSelect').value;
  const keyColsStr = document.getElementById('keyColumns').value.trim();
  const cmpColsStr = document.getElementById('compareColumns').value.trim();
  const keyFilterStr = document.getElementById('keyFilter').value.trim();
  const cbChanged = document.getElementById('filterChanged');
  const cbAdded = document.getElementById('filterAdded');
  const cbRemoved = document.getElementById('filterRemoved');
  const colSelect = document.getElementById('filterColumn');
  const rowLimitEl = document.getElementById('rowLimit');
  const rowLimitEnabledEl = document.getElementById('rowLimitEnabled');

  const key_columns = keyColsStr
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const compare_columns = cmpColsStr
    ? cmpColsStr
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    : null;
  let row_limit = null;
  const limitEnabled = !rowLimitEnabledEl || rowLimitEnabledEl.checked;
  if (limitEnabled && rowLimitEl) {
    const raw = String(rowLimitEl.value || '').trim();
    if (raw) {
      const parsed = parseInt(raw, 10);
      if (!Number.isNaN(parsed) && parsed >= 1) {
        row_limit = parsed;
      }
    }
  }

  const change_types = [];
  if (!cbChanged || cbChanged.checked) change_types.push(COMPARE_UI_TO_BACKEND_TYPES.changed);
  if (!cbAdded || cbAdded.checked)
    change_types.push(COMPARE_UI_TO_BACKEND_TYPES.added);
  if (!cbRemoved || cbRemoved.checked)
    change_types.push(COMPARE_UI_TO_BACKEND_TYPES.removed);

  const changed_column = colSelect && colSelect.value ? colSelect.value : null;
  const page_size = row_limit || null;

  return {
    db1,
    db2,
    table,
    keyColsStr,
    payload: {
      db1_path: db1,
      db2_path: db2,
      table,
      key_columns,
      compare_columns,
      row_limit,
      key_filter: keyFilterStr || null,
      change_types,
      changed_column,
      page,
      page_size,
    },
  };
}

function getErrorText(err) {
  if (err && err.message) return err.message;
  return String(err || 'erro desconhecido');
}

function applyCompareMissingDbState() {
  setCompareStatus(
    'Informe os caminhos de ambos os bancos (.duckdb).',
    'warn'
  );
  setFlowHint(
    'Informe os caminhos de ambos os bancos A e B para conseguir comparar.',
    'warn'
  );
  setStepState('stepPickFiles', 'Caminhos faltando', 'warn');
  setStepState('stepLoadTables', 'Aguardando', null);
  setStepState('stepCompare', 'Aguardando', null);
}

function validateCompareRequest(compareRequest) {
  if (!compareRequest.db1 || !compareRequest.db2) {
    applyCompareMissingDbState();
    return false;
  }
  if (!compareRequest.table) {
    setCompareStatus('Selecione uma tabela.', 'warn');
    setFlowHint(
      'Carregue as tabelas em comum e selecione uma tabela antes de comparar.',
      'warn'
    );
    setStepState('stepLoadTables', 'Tabela nao selecionada', 'warn');
    setStepState('stepCompare', 'Aguardando', null);
    return false;
  }
  if (!compareRequest.keyColsStr) {
    setCompareStatus('Informe pelo menos uma coluna-chave K.', 'warn');
    setFlowHint(
      'Informe pelo menos uma coluna-chave K para identificar os registros unicos.',
      'warn'
    );
    setStepState('stepCompare', 'Chave K faltando', 'warn');
    return false;
  }
  return true;
}

async function executeCompareRequest(payload, options) {
  const compareTimeout = setCompareBusy(
    options.busyStatus,
    options.busyFlow,
    options.busyStep,
    options.busySlow
  );
  try {
    const data = await postJson('/api/compare_db_rows', payload);
    renderResult(data);
    updateLastCompareMeta(data, options.pageForMeta || payload.page || 1);
    saveCompareState();
    setCompareStatus(options.successStatus, 'info');
    setFlowHint(options.successFlow, 'info');
    setStepState('stepCompare', 'Concluido', 'done');
    if (options.openStepOnSuccess) {
      setStepOpen(3);
    }
    return true;
  } catch (err) {
    console.error(err);
    const errorText = getErrorText(err);
    setCompareStatus(options.errorStatusPrefix + ': ' + errorText, 'error');
    setFlowHint(options.errorFlowPrefix + ': ' + errorText, 'error');
    setStepState('stepCompare', options.errorStepText, 'warn');
    return false;
  } finally {
    clearCompareBusy(compareTimeout);
  }
}

async function runCompare() {
  const summaryEl = document.getElementById('summary');
  const resultsEl = document.getElementById('results');
  const compareRequest = collectCompareRequest(1);

  summaryEl.innerHTML = '';
  resultsEl.innerHTML = '';
  setCompareStatus('', 'info');

  if (!validateCompareRequest(compareRequest)) return;

  compareDbState.lastComparePayload = compareRequest.payload;
  compareDbState.lastCompareMeta = null;
  saveCompareState();

  await executeCompareRequest(compareRequest.payload, {
    busyStatus: 'Comparando tabela completa entre A e B (pode levar alguns segundos)...',
    busyFlow:
      'Comparando tabela completa entre A e B. Aguarde, dependendo do tamanho pode levar alguns segundos ou minutos.',
    busyStep: 'Comparando...',
    busySlow:
      'A comparacao esta levando mais de 60 segundos. Se o banco ou a tabela forem muito grandes, isso pode ser esperado. Se travar, tente restringir por chave K.',
    successStatus: 'Comparacao concluida.',
    successFlow:
      'Comparacao concluida. Revise o resumo e os detalhes de diferencas abaixo.',
    errorStatusPrefix: 'Erro ao comparar',
    errorFlowPrefix: 'Erro ao comparar bancos',
    errorStepText: 'Erro ao comparar',
    openStepOnSuccess: true,
    pageForMeta: 1,
  });
}

async function changePage(newPage) {
  if (!compareDbState.lastComparePayload) return;
  const payload = { ...compareDbState.lastComparePayload, page: newPage };
  compareDbState.lastComparePayload = payload;
  saveCompareState();

  await executeCompareRequest(payload, {
    busyStatus: `Carregando pagina ${newPage}...`,
    busyFlow: `Carregando pagina ${newPage} dos resultados de comparacao...`,
    busyStep: `Carregando pagina ${newPage}...`,
    busySlow:
      'A troca de pagina esta levando mais de 60 segundos. Se a tabela for grande, isso pode ser esperado.',
    successStatus: 'Comparacao concluida.',
    successFlow: 'Resultados atualizados. Continue revisando as diferencas.',
    errorStatusPrefix: 'Erro ao carregar pagina',
    errorFlowPrefix: 'Erro ao buscar pagina de resultados',
    errorStepText: 'Erro ao carregar pagina',
    openStepOnSuccess: false,
    pageForMeta: newPage,
  });
}

async function fetchAllComparisonRows(basePayload, onProgress) {
  let page = 1;
  let totalPages = 1;
  let allRows = [];
  let meta = null;

  while (page <= totalPages) {
    if (typeof onProgress === 'function') {
      onProgress({ page, totalPages });
    }
    const payload = { ...basePayload, page };
    const data = await postJson('/api/compare_db_rows', payload);
    if (!meta) meta = data;
    allRows = allRows.concat(data.rows || []);
    totalPages = data.total_pages || 1;
    page += 1;
  }
  return { meta, allRows, totalPages };
}

function normalizeExportTableName(meta) {
  return (meta.table || 'tabela').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function triggerBlobDownload(content, mimeType, filename) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeCsvCell(val) {
  if (val === null || typeof val === 'undefined') return '';
  let s = String(val);
  if (s.includes('"')) s = s.replace(/"/g, '""');
  if (s.includes(';') || s.includes('\n') || s.includes('\r')) {
    s = '"' + s + '"';
  }
  return s;
}

function buildCompareCsvLines(meta, allRows) {
  const keyCols = meta.key_columns || [];
  const cmpCols = meta.compare_columns || [];
  const headers = [];
  for (const k of keyCols) headers.push('K_' + k);
  headers.push('type');
  for (const c of cmpCols) {
    headers.push('A_' + c);
    headers.push('B_' + c);
  }
  const lines = [headers.join(';')];
  for (const r of allRows) {
    const rowCells = [];
    for (const k of keyCols) rowCells.push(escapeCsvCell((r.key || {})[k]));
    rowCells.push(escapeCsvCell(r.type));
    for (const c of cmpCols) {
      rowCells.push(escapeCsvCell((r.a || {})[c]));
      rowCells.push(escapeCsvCell((r.b || {})[c]));
    }
    lines.push(rowCells.join(';'));
  }
  return lines;
}

function isBlankExportValue(value) {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  return false;
}

function toFiniteExportNumber(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().replace(',', '.');
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function buildCompareReportSummary(meta, allRows) {
  const compareColumns = meta.compare_columns || [];
  const byType = { added: 0, removed: 0, changed: 0, same: 0 };
  const changedColumnsCount = {};
  const nullTransitions = {};
  const numericDrift = {};

  allRows.forEach((row) => {
    const rowType = String(row.type || '').toLowerCase();
    if (Object.prototype.hasOwnProperty.call(byType, rowType)) {
      byType[rowType] += 1;
    }
    if (rowType !== 'changed') return;
    compareColumns.forEach((column) => {
      const valueA = (row.a || {})[column];
      const valueB = (row.b || {})[column];
      if (!valuesDifferent(valueA, valueB)) return;

      changedColumnsCount[column] = (changedColumnsCount[column] || 0) + 1;

      const oldBlank = isBlankExportValue(valueB);
      const newBlank = isBlankExportValue(valueA);
      if (oldBlank !== newBlank) {
        const direction = oldBlank ? 'vazio -> preenchido' : 'preenchido -> vazio';
        const key = `${column} | ${direction}`;
        nullTransitions[key] = (nullTransitions[key] || 0) + 1;
      }

      const numA = toFiniteExportNumber(valueA);
      const numB = toFiniteExportNumber(valueB);
      if (numA === null || numB === null) return;
      const delta = numA - numB;
      const absDelta = Math.abs(delta);
      if (!absDelta) return;
      const stat = numericDrift[column] || {
        count: 0,
        sumAbsDelta: 0,
        maxAbsDelta: 0,
        maxSignedDelta: 0,
      };
      stat.count += 1;
      stat.sumAbsDelta += absDelta;
      if (absDelta > stat.maxAbsDelta) {
        stat.maxAbsDelta = absDelta;
        stat.maxSignedDelta = delta;
      }
      numericDrift[column] = stat;
    });
  });

  const totalKeys = allRows.length;
  const impactedKeys = byType.added + byType.removed + byType.changed;
  const impactedPct = totalKeys > 0 ? (impactedKeys / totalKeys) * 100 : 0;
  const topChangedColumns = Object.entries(changedColumnsCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([column, count]) => ({ column, count }));
  const topNullTransitions = Object.entries(nullTransitions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([label, count]) => ({ label, count }));
  const topNumericDrift = Object.entries(numericDrift)
    .map(([column, info]) => ({
      column,
      count: info.count,
      sum_abs_delta: Number(info.sumAbsDelta.toFixed(4)),
      max_signed_delta: Number(info.maxSignedDelta.toFixed(4)),
    }))
    .sort((a, b) => b.sum_abs_delta - a.sum_abs_delta)
    .slice(0, 8);

  const priorityAnomalies = [];
  topChangedColumns.forEach((item) => {
    priorityAnomalies.push({
      score: Number(item.count || 0) * 4,
      label: `coluna impactada: ${item.column}`,
      detail: `${item.count} chave(s) alteradas`,
    });
  });
  topNullTransitions.forEach((item) => {
    priorityAnomalies.push({
      score: Number(item.count || 0) * 3,
      label: `transicao nulo/preenchido: ${item.label}`,
      detail: `${item.count} ocorrencia(s)`,
    });
  });
  topNumericDrift.forEach((item) => {
    priorityAnomalies.push({
      score: Number(item.sum_abs_delta || 0),
      label: `drift numerico: ${item.column}`,
      detail: `soma abs ${item.sum_abs_delta} · pico ${item.max_signed_delta}`,
    });
  });
  const topPriorityAnomalies = priorityAnomalies
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map((item) => ({
      score: Number(item.score.toFixed(4)),
      label: item.label,
      detail: item.detail,
    }));

  let priority = 'baixa';
  if (impactedPct >= 50 || byType.changed >= 10) {
    priority = 'critica';
  } else if (impactedPct >= 25 || byType.changed >= 5 || topNullTransitions.length >= 3) {
    priority = 'alta';
  } else if (impactedPct >= 10 || topNumericDrift.length >= 2) {
    priority = 'media';
  } else if (impactedKeys === 0) {
    priority = 'estavel';
  }

  return {
    total_keys: totalKeys,
    impacted_keys: impactedKeys,
    impacted_pct: Number(impactedPct.toFixed(2)),
    by_type: byType,
    priority,
    top_changed_columns: topChangedColumns,
    top_null_transitions: topNullTransitions,
    top_numeric_drift: topNumericDrift,
    top_priority_anomalies: topPriorityAnomalies,
  };
}

function buildCompareReportPayload(meta, allRows, basePayload) {
  return {
    report_version: "1.1",
    generated_at: new Date().toISOString(),
    source: {
      db1_path: meta.db1 || basePayload.db1_path || '',
      db2_path: meta.db2 || basePayload.db2_path || '',
      table: meta.table || basePayload.table || '',
      key_columns: meta.key_columns || basePayload.key_columns || [],
      compare_columns: meta.compare_columns || basePayload.compare_columns || [],
      filters: {
        key_filter: basePayload.key_filter || null,
        change_types: basePayload.change_types || [],
        changed_column: basePayload.changed_column || null,
      },
    },
    export: {
      rows_exported: allRows.length,
      total_pages: Number(meta.total_pages || 1),
      page_size: Number(meta.page_size || 0),
      generated_from: 'compare_db_rows_fast_path',
    },
    summary: buildCompareReportSummary(meta, allRows),
    rows: allRows,
  };
}

async function collectCompareExportData(progressPrefix) {
  if (!compareDbState.lastComparePayload) {
    setCompareStatus(
      'Nenhuma comparacao para exportar. Execute a comparacao primeiro.',
      'warn'
    );
    return null;
  }
  const basePayload = { ...compareDbState.lastComparePayload };
  const { meta, allRows, totalPages } = await fetchAllComparisonRows(
    basePayload,
    ({ page, totalPages }) => {
      setCompareStatus(
        `${progressPrefix} (pagina ${page} de ${totalPages || '?'})...`,
        'info'
      );
    }
  );
  if (!meta) {
    setCompareStatus('Nenhum dado disponivel para exportacao.', 'warn');
    return null;
  }
  return {
    basePayload,
    meta: { ...meta, total_pages: totalPages },
    allRows,
  };
}

function setExportUnexpectedError(prefix, err, flowText) {
  const detail = err && err.message ? err.message : String(err);
  setCompareStatus(`${prefix}: ${detail}`, 'error');
  setFlowHint(flowText, 'error');
}

async function exportComparison() {
  const exportBtn = document.getElementById('btnExportComparison');
  const restoreBtn = setButtonBusy(
    exportBtn,
    'Exportando...',
    exportBtn ? exportBtn.textContent : 'Exportar CSV'
  );
  try {
    const exportData = await collectCompareExportData(
      'Preparando exportacao CSV'
    );
    if (!exportData) return;
    const { meta, allRows } = exportData;
    const lines = buildCompareCsvLines(meta, allRows);
    const tableName = normalizeExportTableName(meta);
    triggerBlobDownload(
      lines.join('\r\n'),
      'text/csv;charset=utf-8;',
      `comparacao_${tableName}.csv`
    );
    setCompareStatus('Exportacao concluida. Arquivo CSV baixado.', 'info');
    setFlowHint(
      'Exportacao concluida. O CSV foi baixado com o recorte atual.',
      'info'
    );
  } catch (err) {
    console.error(err);
    setExportUnexpectedError(
      'Erro inesperado ao exportar',
      err,
      'Falha ao exportar a comparacao.'
    );
  } finally {
    restoreBtn();
  }
}

async function exportComparisonReport() {
  const exportBtn = document.getElementById('btnExportReportJson');
  const restoreBtn = setButtonBusy(
    exportBtn,
    'Exportando relatorio...',
    exportBtn ? exportBtn.textContent : 'Exportar relatorio JSON'
  );
  try {
    const exportData = await collectCompareExportData(
      'Preparando relatorio JSON'
    );
    if (!exportData) return;
    const { basePayload, meta, allRows } = exportData;
    const report = buildCompareReportPayload(meta, allRows, basePayload);
    const tableName = normalizeExportTableName(meta);
    triggerBlobDownload(
      JSON.stringify(report, null, 2),
      'application/json;charset=utf-8;',
      `comparacao_${tableName}_report.json`
    );
    setCompareStatus('Exportacao concluida. Relatorio JSON baixado.', 'info');
    setFlowHint(
      'Relatorio JSON exportado com resumo, prioridade e dados de diferenca.',
      'info'
    );
  } catch (err) {
    console.error(err);
    setExportUnexpectedError(
      'Erro inesperado ao exportar relatorio',
      err,
      'Falha ao exportar relatorio JSON.'
    );
  } finally {
    restoreBtn();
  }
}

async function generateTablesOverview() {
  const container = document.getElementById('tablesOverview');
  const db1Input = document.getElementById('db1Path');
  const db2Input = document.getElementById('db2Path');
  const overviewBtn = document.getElementById('btnTablesOverview');
  const restoreBtn = setButtonBusy(
    overviewBtn,
    'Gerando mapa...',
    overviewBtn ? overviewBtn.textContent : 'Mapa geral das tabelas'
  );

  if (
    !db1Input ||
    !db2Input ||
    !db1Input.value.trim() ||
    !db2Input.value.trim()
  ) {
    setCompareStatus(
      'Informe os caminhos de ambos os bancos e carregue as tabelas antes de gerar o mapa.',
      'warn'
    );
    restoreBtn();
    return;
  }
  if (!compareDbState.tablesMeta || !compareDbState.tablesMeta.length) {
    setCompareStatus('Carregue as tabelas em comum primeiro.', 'warn');
    restoreBtn();
    return;
  }

  container.innerHTML =
    '<div class="tables-overview-card">Gerando mapa geral das tabelas... Isso pode levar alguns segundos.</div>';
  if (
    compareDbState.tablesOverviewCache &&
    compareDbState.tablesOverviewCache.db1 === db1Input.value &&
    compareDbState.tablesOverviewCache.db2 === db2Input.value
  ) {
    renderTablesOverview(compareDbState.tablesOverviewCache.result);
    restoreBtn();
    return;
  }

  const overview = [];
  const db1 = db1Input.value.trim();
  const db2 = db2Input.value.trim();
  const tableNames = compareDbState.tablesMeta
    .map((item) => item && item.name)
    .filter(Boolean);
  try {
    const payload = await postJson('/api/compare_db_overview', {
      db1_path: db1,
      db2_path: db2,
      tables: tableNames,
    });
    (payload.overview || []).forEach((item) => {
      overview.push({
        table: item.table,
        status: item.status || 'error',
        diffCount:
          typeof item.diff_count === 'number' ? item.diff_count : -1,
        row_count_a: item.row_count_a,
        row_count_b: item.row_count_b,
        error: item.error || '',
      });
    });
  } catch (err) {
    console.error('Erro ao gerar mapa geral via endpoint unico', err);
    setCompareStatus(
      'Falha ao gerar mapa geral: ' +
        (err && err.message ? err.message : String(err)),
      'error'
    );
    restoreBtn();
    return;
  }

  compareDbState.tablesOverviewCache = { db1: db1, db2: db2, result: overview };
  renderTablesOverview(overview);
  restoreBtn();
}

async function toggleTablesOverview() {
  if (compareDbState.tablesOverviewVisible) {
    compareDbState.tablesOverviewVisible = false;
    updateTablesOverviewVisibility();
    return;
  }
  const container = document.getElementById('tablesOverview');
  if (container && !compareDbState.tablesOverviewCache) {
    await generateTablesOverview();
  }
  compareDbState.tablesOverviewVisible = true;
  updateTablesOverviewVisibility();
}

function renderTablesOverview(overview) {
  const container = document.getElementById('tablesOverview');
  if (!container) return;
  if (!overview || !overview.length) {
    container.innerHTML = '';
    return;
  }

  const withDiff = overview.filter((o) => o.status === 'diff');
  const withoutDiff = overview.filter((o) => o.status === 'same');
  const noKey = overview.filter((o) => o.status === 'no_key');
  const errors = overview.filter((o) => o.status === 'error');

  let html = '<div class="tables-overview-card">';
  html += '<div><strong>Mapa geral das tabelas em comum</strong></div>';
  html += '<div class="tables-overview-grid">';

  if (withDiff.length) {
    html += '<div><strong>Tabelas com diferencas de conteudo:</strong></div>';
    for (const o of withDiff) {
      html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">${o.diffCount} linhas diferentes · A: ${o.row_count_a} · B: ${o.row_count_b}</span></div>`;
    }
  }
  if (withoutDiff.length) {
    html +=
      '<div style="margin-top:4px;"><strong>Tabelas sem diferencas relevantes:</strong></div>';
    for (const o of withoutDiff) {
      html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">conteudo identico · A: ${o.row_count_a} · B: ${o.row_count_b}</span></div>`;
    }
  }
  if (noKey.length) {
    html +=
      '<div style="margin-top:4px;"><strong>Tabelas nao avaliadas (chave nao identificada automaticamente):</strong></div>';
    for (const o of noKey) {
      html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">defina uma chave manualmente no passo 2 para comparar esta tabela.</span></div>`;
    }
  }
  if (errors.length) {
    html +=
      '<div style="margin-top:4px;"><strong>Tabelas com erro ao comparar:</strong></div>';
    for (const o of errors) {
      html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">${o.error || 'Erro ao comparar.'}</span></div>`;
    }
  }

  html += '</div></div>';
  container.innerHTML = html;
}

window.loadTables = loadTables;
window.onTableChange = onTableChange;
window.collectCompareRequest = collectCompareRequest;
window.runCompare = runCompare;
window.changePage = changePage;
window.exportComparison = exportComparison;
window.exportComparisonReport = exportComparisonReport;
window.generateTablesOverview = generateTablesOverview;
window.toggleTablesOverview = toggleTablesOverview;
window.renderTablesOverview = renderTablesOverview;
