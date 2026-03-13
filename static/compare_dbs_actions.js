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
    setFlowHint(
      'Informe os caminhos de ambos os bancos A e B para continuar.',
      'warn'
    );
    setStepState('stepPickFiles', 'Caminhos faltando', 'warn');
    setStepState('stepLoadTables', 'Aguardando', null);
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

async function runCompare() {
  const summaryEl = document.getElementById('summary');
  const resultsEl = document.getElementById('results');
  const compareRequest = collectCompareRequest(1);

  summaryEl.innerHTML = '';
  resultsEl.innerHTML = '';
  setCompareStatus('', 'info');

  if (!compareRequest.db1 || !compareRequest.db2) {
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
    return;
  }
  if (!compareRequest.table) {
    setCompareStatus('Selecione uma tabela.', 'warn');
    setFlowHint(
      'Carregue as tabelas em comum e selecione uma tabela antes de comparar.',
      'warn'
    );
    setStepState('stepLoadTables', 'Tabela nao selecionada', 'warn');
    setStepState('stepCompare', 'Aguardando', null);
    return;
  }
  if (!compareRequest.keyColsStr) {
    setCompareStatus('Informe pelo menos uma coluna-chave K.', 'warn');
    setFlowHint(
      'Informe pelo menos uma coluna-chave K para identificar os registros unicos.',
      'warn'
    );
    setStepState('stepCompare', 'Chave K faltando', 'warn');
    return;
  }

  compareDbState.lastComparePayload = compareRequest.payload;
  compareDbState.lastCompareMeta = null;
  saveCompareState();

  const compareTimeout = setCompareBusy(
    'Comparando tabela completa entre A e B (pode levar alguns segundos)...',
    'Comparando tabela completa entre A e B. Aguarde, dependendo do tamanho pode levar alguns segundos ou minutos.',
    'Comparando...',
    'A comparacao esta levando mais de 60 segundos. Se o banco ou a tabela forem muito grandes, isso pode ser esperado. Se travar, tente restringir por chave K.'
  );

  try {
    const data = await postJson('/api/compare_db_rows', compareRequest.payload);
    renderResult(data);
    updateLastCompareMeta(data, 1);
    saveCompareState();
    setCompareStatus('Comparacao concluida.', 'info');
    setFlowHint(
      'Comparacao concluida. Revise o resumo e os detalhes de diferencas abaixo.',
      'info'
    );
    setStepState('stepCompare', 'Concluido', 'done');
    setStepOpen(3);
  } catch (err) {
    console.error(err);
    setCompareStatus(
      'Erro ao comparar: ' + (err && err.message ? err.message : String(err)),
      'error'
    );
    setFlowHint(
      'Erro ao comparar bancos: ' +
        (err && err.message ? err.message : String(err)),
      'error'
    );
    setStepState('stepCompare', 'Erro ao comparar', 'warn');
  } finally {
    clearCompareBusy(compareTimeout);
  }
}

async function changePage(newPage) {
  if (!compareDbState.lastComparePayload) return;
  const payload = { ...compareDbState.lastComparePayload, page: newPage };
  compareDbState.lastComparePayload = payload;
  saveCompareState();

  const compareTimeout = setCompareBusy(
    `Carregando pagina ${newPage}...`,
    `Carregando pagina ${newPage} dos resultados de comparacao...`,
    `Carregando pagina ${newPage}...`,
    'A troca de pagina esta levando mais de 60 segundos. Se a tabela for grande, isso pode ser esperado.'
  );

  try {
    const data = await postJson('/api/compare_db_rows', payload);
    renderResult(data);
    updateLastCompareMeta(data, newPage);
    saveCompareState();
    setCompareStatus('Comparacao concluida.', 'info');
    setFlowHint(
      'Resultados atualizados. Continue revisando as diferencas.',
      'info'
    );
    setStepState('stepCompare', 'Concluido', 'done');
  } catch (err) {
    console.error(err);
    setCompareStatus(
      'Erro ao carregar pagina: ' +
        (err && err.message ? err.message : String(err)),
      'error'
    );
    setFlowHint(
      'Erro ao buscar pagina de resultados: ' +
        (err && err.message ? err.message : String(err)),
      'error'
    );
    setStepState('stepCompare', 'Erro ao carregar pagina', 'warn');
  } finally {
    clearCompareBusy(compareTimeout);
  }
}

async function exportComparison() {
  const exportBtn = document.getElementById('btnExportComparison');
  const restoreBtn = setButtonBusy(
    exportBtn,
    'Exportando...',
    exportBtn ? exportBtn.textContent : 'Exportar CSV'
  );
  if (!compareDbState.lastComparePayload) {
    setCompareStatus(
      'Nenhuma comparacao para exportar. Execute a comparacao primeiro.',
      'warn'
    );
    restoreBtn();
    return;
  }
  try {
    setCompareStatus(
      'Preparando exportacao (carregando todas as paginas)...',
      'info'
    );
    const basePayload = { ...compareDbState.lastComparePayload };
    let page = 1;
    let totalPages = 1;
    let allRows = [];
    let meta = null;

    while (page <= totalPages) {
      const payload = { ...basePayload, page };
      const data = await postJson('/api/compare_db_rows', payload);
      if (!meta) meta = data;
      allRows = allRows.concat(data.rows || []);
      totalPages = data.total_pages || 1;
      page += 1;
    }

    if (!meta) {
      setCompareStatus('Nenhum dado disponivel para exportacao.', 'warn');
      return;
    }

    const keyCols = meta.key_columns || [];
    const cmpCols = meta.compare_columns || [];
    const headers = [];
    for (const k of keyCols) headers.push('K_' + k);
    headers.push('type');
    for (const c of cmpCols) {
      headers.push('A_' + c);
      headers.push('B_' + c);
    }

    const escapeCell = (val) => {
      if (val === null || typeof val === 'undefined') return '';
      let s = String(val);
      if (s.includes('"')) s = s.replace(/"/g, '""');
      if (s.includes(';') || s.includes('\n') || s.includes('\r')) {
        s = '"' + s + '"';
      }
      return s;
    };

    const lines = [headers.join(';')];
    for (const r of allRows) {
      const rowCells = [];
      for (const k of keyCols) rowCells.push(escapeCell((r.key || {})[k]));
      rowCells.push(escapeCell(r.type));
      for (const c of cmpCols) {
        rowCells.push(escapeCell((r.a || {})[c]));
        rowCells.push(escapeCell((r.b || {})[c]));
      }
      lines.push(rowCells.join(';'));
    }

    const blob = new Blob([lines.join('\r\n')], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const tableName = (meta.table || 'tabela').replace(/[^a-zA-Z0-9_-]/g, '_');
    a.href = url;
    a.download = `comparacao_${tableName}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setCompareStatus('Exportacao concluida. Arquivo CSV baixado.', 'info');
    setFlowHint(
      'Exportacao concluida. O CSV foi baixado com o recorte atual.',
      'info'
    );
  } catch (err) {
    console.error(err);
    setCompareStatus(
      'Erro inesperado ao exportar: ' +
        (err && err.message ? err.message : String(err)),
      'error'
    );
    setFlowHint('Falha ao exportar a comparacao.', 'error');
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
  for (const t of compareDbState.tablesMeta) {
    const name = t.name;
    try {
      const data = await postJson('/api/compare_db_table_content', {
        db1_path: db1,
        db2_path: db2,
        table: name,
      });
      const diffCount =
        typeof data.diff_count === 'number' ? data.diff_count : -1;
      overview.push({
        table: name,
        status: diffCount > 0 ? 'diff' : 'same',
        diffCount,
        row_count_a: data.row_count_a,
        row_count_b: data.row_count_b,
      });
    } catch (err) {
      console.error('Erro ao gerar resumo da tabela', name, err);
      overview.push({
        table: name,
        status: 'error',
        error: err && err.message ? err.message : String(err),
      });
    }
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
window.generateTablesOverview = generateTablesOverview;
window.toggleTablesOverview = toggleTablesOverview;
window.renderTablesOverview = renderTablesOverview;
