function buildCompareSummary(data, rows, changedRows) {
  const s = data.summary || {};
  const same = s.same_count ?? 0;
  const onlyInB = s.added_count ?? rows.added.length;
  const onlyInA = s.removed_count ?? rows.removed.length;
  const changed = s.changed_count ?? changedRows.length;
  const totalKeys = s.keys_total ?? same + onlyInA + onlyInB + changed;
  const colDiffCounts = {};

  for (const row of changedRows) {
    for (const column of data.compare_columns || []) {
      if (!valuesDifferent(row.a[column], row.b[column])) continue;
      colDiffCounts[column] = (colDiffCounts[column] || 0) + 1;
    }
  }

  return {
    same,
    onlyInA,
    onlyInB,
    changed,
    totalKeys,
    colDiffList: Object.entries(colDiffCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([col, count]) => `${col}: ${count}`)
      .join(', '),
  };
}

function buildCompareHighlights(data, rows, changedRows) {
  const highlights = [];
  const keyColumns = data.key_columns || [];
  if (rows.added.length) {
    const first = rows.added[0];
    const keyText = keyColumns
      .map((key) => `${key}=${JSON.stringify((first.key || {})[key])}`)
      .join(', ');
    highlights.push(
      `Primeiro registro removido do banco novo: ${keyText || 'sem chave visivel'}`
    );
  }
  if (rows.removed.length) {
    const first = rows.removed[0];
    const keyText = keyColumns
      .map((key) => `${key}=${JSON.stringify((first.key || {})[key])}`)
      .join(', ');
    highlights.push(
      `Primeiro registro novo no banco atual: ${keyText || 'sem chave visivel'}`
    );
  }
  if (changedRows.length) {
    const firstChanged = changedRows[0];
    const changedCols = (data.compare_columns || []).filter((column) =>
      valuesDifferent(
        (firstChanged.a || {})[column],
        (firstChanged.b || {})[column]
      )
    );
    const keyText = keyColumns
      .map((key) => `${key}=${JSON.stringify((firstChanged.key || {})[key])}`)
      .join(', ');
    highlights.push(
      `Primeira chave alterada: ${keyText || 'sem chave visivel'}${changedCols.length ? ' · colunas: ' + changedCols.join(', ') : ''}`
    );
  }
  return highlights;
}

function buildCompareAlerts(data, changedRows) {
  const alerts = [];
  const columnExamples = {};
  const compareColumns = data.compare_columns || [];
  const keyColumns = data.key_columns || [];

  for (const row of changedRows) {
    const keyText = keyColumns
      .map((key) => `${key}=${JSON.stringify((row.key || {})[key])}`)
      .join(', ');
    for (const column of compareColumns) {
      if (!valuesDifferent((row.a || {})[column], (row.b || {})[column]))
        continue;
      if (!columnExamples[column]) {
        columnExamples[column] = keyText || 'sem chave visivel';
      }
    }
  }

  Object.entries(columnExamples)
    .slice(0, 4)
    .forEach(([column, example]) => {
      alerts.push(`${column}: primeira chave impactada ${example}`);
    });

  return alerts;
}

function buildComparePriorityReview(data, changedRows) {
  const compareColumns = data.compare_columns || [];
  const keyColumns = data.key_columns || [];
  const keyImpacts = {};
  const columnImpacts = {};

  for (const row of changedRows) {
    const keyText =
      keyColumns
        .map((key) => `${key}=${JSON.stringify((row.key || {})[key])}`)
        .join(', ') || 'sem chave visivel';
    let rowImpact = 0;
    const changedColumns = [];

    for (const column of compareColumns) {
      if (!valuesDifferent((row.a || {})[column], (row.b || {})[column])) {
        continue;
      }
      rowImpact += 1;
      changedColumns.push(column);
      columnImpacts[column] = (columnImpacts[column] || 0) + 1;
    }

    if (!rowImpact) continue;
    keyImpacts[keyText] = {
      count: rowImpact,
      columns: changedColumns,
    };
  }

  return {
    topKeys: Object.entries(keyImpacts)
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 5),
    topColumns: Object.entries(columnImpacts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6),
  };
}

function buildComparePatterns(data, changedRows) {
  const compareColumns = data.compare_columns || [];
  const keyColumns = data.key_columns || [];
  const patterns = {};

  for (const row of changedRows) {
    const changedColumns = compareColumns.filter((column) =>
      valuesDifferent((row.a || {})[column], (row.b || {})[column])
    );
    if (!changedColumns.length) continue;
    const label = changedColumns.join(', ');
    const keyText =
      keyColumns
        .map((key) => `${key}=${JSON.stringify((row.key || {})[key])}`)
        .join(', ') || 'sem chave visivel';
    if (!patterns[label]) {
      patterns[label] = {
        count: 0,
        sample: keyText,
      };
    }
    patterns[label].count += 1;
  }

  return Object.entries(patterns)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5);
}

function pickDomainField(row, candidates) {
  for (const candidate of candidates) {
    const valueA = (row.a || {})[candidate];
    const valueB = (row.b || {})[candidate];
    if (valueA !== undefined && valueA !== null && valueA !== '') {
      return String(valueA);
    }
    if (valueB !== undefined && valueB !== null && valueB !== '') {
      return String(valueB);
    }
  }
  return '';
}

function buildCompareDomainSignals(changedRows) {
  const familyCounts = {};
  const stateTransitions = {};

  for (const row of changedRows) {
    const family =
      pickDomainField(row, ['PNLNAM', 'SUBNAM', 'DEVNAM']) ||
      'familia nao identificada';
    familyCounts[family] = (familyCounts[family] || 0) + 1;

    const oldState = pickDomainField(row, ['STACON', 'NORMST', 'SOEHIS']);
    const newState = pickDomainField(
      {
        a: row.b || {},
        b: row.a || {},
      },
      ['STACON', 'NORMST', 'SOEHIS']
    );
    if (oldState || newState) {
      const label = `${oldState || '-'} -> ${newState || '-'}`;
      stateTransitions[label] = (stateTransitions[label] || 0) + 1;
    }
  }

  return {
    topFamilies: Object.entries(familyCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5),
    topTransitions: Object.entries(stateTransitions)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5),
  };
}

function renderCompareSummary(data, summaryData) {
  const summaryEl = document.getElementById('summary');
  const changedRows = data.rows
    ? data.rows.filter((row) => row.type === 'changed')
    : [];
  const highlights = buildCompareHighlights(
    data,
    {
      added: data.rows ? data.rows.filter((row) => row.type === 'added') : [],
      removed: data.rows
        ? data.rows.filter((row) => row.type === 'removed')
        : [],
      changed: data.rows
        ? data.rows.filter((row) => row.type === 'changed')
        : [],
    },
    changedRows
  );
  const alerts = buildCompareAlerts(data, changedRows);
  const review = buildComparePriorityReview(data, changedRows);
  const patterns = buildComparePatterns(data, changedRows);
  const domainSignals = buildCompareDomainSignals(changedRows);
  const topKeysHtml = review.topKeys.length
    ? `<div class="report-review-list">${review.topKeys
        .map(
          ([keyText, meta]) =>
            `<div class="report-review-item"><strong>${keyText}</strong><span>${meta.count} campos mudaram${meta.columns.length ? ' · ' + meta.columns.slice(0, 5).join(', ') : ''}</span></div>`
        )
        .join('')}</div>`
    : '';
  const topColumnsHtml = review.topColumns.length
    ? `<div class="report-review-list">${review.topColumns
        .map(
          ([column, count]) =>
            `<div class="report-review-item"><strong>${column}</strong><span>${count} chaves alteradas</span></div>`
        )
        .join('')}</div>`
    : '';
  const patternsHtml = patterns.length
    ? `<div class="report-review-list">${patterns
        .map(
          ([label, meta]) =>
            `<div class="report-review-item"><strong>${label}</strong><span>${meta.count} chave(s) · exemplo: ${meta.sample}</span></div>`
        )
        .join('')}</div>`
    : '';
  const familyHtml = domainSignals.topFamilies.length
    ? `<div class="report-review-list">${domainSignals.topFamilies
        .map(
          ([family, count]) =>
            `<div class="report-review-item"><strong>${family}</strong><span>${count} chave(s) alteradas</span></div>`
        )
        .join('')}</div>`
    : '';
  const transitionsHtml = domainSignals.topTransitions.length
    ? `<div class="report-review-list">${domainSignals.topTransitions
        .map(
          ([label, count]) =>
            `<div class="report-review-item"><strong>${label}</strong><span>${count} ocorrencia(s)</span></div>`
        )
        .join('')}</div>`
    : '';
  summaryEl.innerHTML = `
    <div class="result-summary-card">
      <div class="result-summary-grid">
        <div><strong>Tabela analisada:</strong> ${data.table}</div>
        <div><strong>Chaves (K):</strong> ${(data.key_columns || []).join(', ')}</div>
        <div>
          <strong>Visao geral:</strong> ${summaryData.totalKeys} registros (chaves) analisados
          <div class="result-badges-row">
            <span class="badge same">${summaryData.same} mantidos (iguais em A e B)</span>
            <span class="badge added">+${summaryData.onlyInA} novos (existem so em A - banco NOVO)</span>
            <span class="badge removed">-${summaryData.onlyInB} removidos (existiam so em B - banco ANTIGO)</span>
            <span class="badge changed">±${summaryData.changed} alterados (chave existe em ambos, mas com diferenca)</span>
          </div>
        </div>
        ${summaryData.colDiffList ? `<div class="result-col-diff"><strong>Colunas com diferenca (qtd. de registros alterados):</strong> ${summaryData.colDiffList}</div>` : ''}
        ${highlights.length ? `<div class="result-col-diff"><strong>Pistas operacionais:</strong><br>${highlights.join('<br>')}</div>` : ''}
        ${alerts.length ? `<div class="result-col-diff"><strong>Colunas sensiveis para revisar:</strong><br>${alerts.join('<br>')}</div>` : ''}
        ${topKeysHtml ? `<div class="result-col-diff"><strong>Chaves para revisar primeiro:</strong>${topKeysHtml}</div>` : ''}
        ${topColumnsHtml ? `<div class="result-col-diff"><strong>Colunas mais impactadas:</strong>${topColumnsHtml}</div>` : ''}
        ${patternsHtml ? `<div class="result-col-diff"><strong>Padroes de alteracao:</strong>${patternsHtml}</div>` : ''}
        ${familyHtml ? `<div class="result-col-diff"><strong>Familias mais afetadas:</strong>${familyHtml}</div>` : ''}
        ${transitionsHtml ? `<div class="result-col-diff"><strong>Transicoes de estado observadas:</strong>${transitionsHtml}</div>` : ''}
      </div>
    </div>
  `;
}

function createViewModeControls() {
  const controlsDiv = document.createElement('div');
  controlsDiv.style.marginTop = '4px';
  controlsDiv.style.fontSize = '11px';
  controlsDiv.style.color = '#9ca3af';
  controlsDiv.textContent = 'Visualizacao dos campos: ';

  const listBtn = document.createElement('button');
  listBtn.type = 'button';
  listBtn.className = 'pill-btn';
  listBtn.textContent = 'Linear';

  const gridBtn = document.createElement('button');
  gridBtn.type = 'button';
  gridBtn.className = 'pill-btn';
  gridBtn.style.marginLeft = '4px';
  gridBtn.textContent = 'Em blocos';

  const refreshButtons = () => {
    if (window.diffViewMode === 'grid') {
      gridBtn.classList.add('pill-btn-active');
      listBtn.classList.remove('pill-btn-active');
    } else {
      listBtn.classList.add('pill-btn-active');
      gridBtn.classList.remove('pill-btn-active');
    }
  };

  listBtn.onclick = () => {
    window.diffViewMode = 'list';
    if (window.lastCompareResult) {
      renderResult(window.lastCompareResult);
    }
  };
  gridBtn.onclick = () => {
    window.diffViewMode = 'grid';
    if (window.lastCompareResult) {
      renderResult(window.lastCompareResult);
    }
  };

  refreshButtons();
  controlsDiv.appendChild(listBtn);
  controlsDiv.appendChild(gridBtn);
  return controlsDiv;
}

function syncFilterColumnOptions(compareColumns) {
  const colSelect = document.getElementById('filterColumn');
  if (!colSelect) return;
  const previousValue = colSelect.value;
  colSelect.innerHTML = '<option value="">-- todas as colunas --</option>';
  for (const column of compareColumns || []) {
    const opt = document.createElement('option');
    opt.value = column;
    opt.textContent = column;
    colSelect.appendChild(opt);
  }
  if (
    previousValue &&
    Array.from(colSelect.options).some((o) => o.value === previousValue)
  ) {
    colSelect.value = previousValue;
  }
}

function buildCompareSections(data, rows) {
  return [
    {
      type: 'changed',
      title: 'Alteradas (existem em A e B, mas com diferencas)',
      rows: rows.changed,
    },
    {
      type: 'added',
      title: 'Novas - so em A (banco NOVO)',
      rows: rows.removed,
    },
    {
      type: 'removed',
      title: 'Removidas - so em B (banco ANTIGO)',
      rows: rows.added,
    },
  ];
}

function buildRowSummary(data, row, isRangerSostat) {
  const keyParts = [];
  for (const key of data.key_columns || []) {
    keyParts.push(`${key}=${JSON.stringify(row.key[key])}`);
  }

  const extraParts = [];
  if (isRangerSostat) {
    const primaryFields = ['SUBNAM', 'PNTNAM', 'BITBYT', 'UNIQID', 'ITEMNB'];
    const pickSide = (column) => {
      const oldValue = (row.b || {})[column];
      const newValue = (row.a || {})[column];
      return typeof oldValue !== 'undefined' ? oldValue : newValue;
    };
    for (const field of primaryFields) {
      const value = pickSide(field);
      if (typeof value !== 'undefined') {
        extraParts.push(`${field}=${shortValue(value, 40)}`);
      }
    }
  }

  return { keyParts, extraParts };
}

function appendFieldLine(target, column, valueA, valueB, changed) {
  const line = document.createElement('div');
  line.className = 'diff-field-line';
  if (changed) {
    line.innerHTML = `<strong>${column}:</strong> ${shortValue(valueA)} -> ${shortValue(valueB)}`;
  } else {
    line.innerHTML = `<span style="opacity:0.7;"><strong>${column}:</strong> ${shortValue(valueA)} (sem diferenca)</span>`;
  }
  target.appendChild(line);
}

function appendSectionFields(
  targetAll,
  importantDiv,
  importantCols,
  sectionType,
  compareColumns,
  row,
  isRangerSostat
) {
  for (const column of compareColumns || []) {
    if (sectionType === 'changed') {
      const valueA = row.a[column];
      const valueB = row.b[column];
      const changed = valuesDifferent(valueA, valueB);
      if (!isRangerSostat || !targetAll.id) {
        if (!changed) continue;
      }
      appendFieldLine(targetAll, column, valueA, valueB, changed);
      if (
        importantDiv &&
        importantCols &&
        importantCols.has(column) &&
        changed
      ) {
        appendFieldLine(importantDiv, column, valueA, valueB, true);
      }
      continue;
    }

    const sideValue = sectionType === 'added' ? row.b[column] : row.a[column];
    const line = document.createElement('div');
    line.className = 'diff-field-line';
    line.innerHTML = `<strong>${column}:</strong> ${shortValue(sideValue)}`;
    targetAll.appendChild(line);
    if (importantDiv && importantCols && importantCols.has(column)) {
      const importantLine = document.createElement('div');
      importantLine.className = 'diff-field-line';
      importantLine.innerHTML = line.innerHTML;
      importantDiv.appendChild(importantLine);
    }
  }
}

function buildRowBody(
  data,
  sectionType,
  row,
  rowId,
  viewModeNow,
  isRangerSostat
) {
  const body = document.createElement('div');
  body.className = 'diff-row-body';
  if (viewModeNow === 'grid') {
    body.classList.add('grid-mode');
  }

  const actions = document.createElement('div');
  actions.className = 'diff-row-actions';
  let importantDiv = null;
  let allDiv = null;

  if (isRangerSostat) {
    const btnMain = document.createElement('button');
    btnMain.type = 'button';
    btnMain.className = 'pill-btn';
    btnMain.textContent = 'Campos principais (2a etapa)';
    btnMain.onclick = () => showRowSegment(rowId, 'important');

    const btnAll = document.createElement('button');
    btnAll.type = 'button';
    btnAll.className = 'pill-btn';
    btnAll.textContent = 'Todos os campos';
    btnAll.onclick = () => showRowSegment(rowId, 'all');

    actions.appendChild(btnMain);
    actions.appendChild(btnAll);

    importantDiv = document.createElement('div');
    importantDiv.id = rowId + '-important';
    importantDiv.className = 'diff-row-body';
    if (viewModeNow === 'grid') {
      importantDiv.classList.add('grid-mode');
    }
    const importantTitle = document.createElement('div');
    importantTitle.textContent = 'Diferencas nos campos principais:';
    importantDiv.appendChild(importantTitle);

    allDiv = document.createElement('div');
    allDiv.id = rowId + '-all';
    allDiv.className = 'diff-row-body';
    if (viewModeNow === 'grid') {
      allDiv.classList.add('grid-mode');
    }
    const allTitle = document.createElement('div');
    allTitle.textContent = 'Todos os campos comparados:';
    allDiv.appendChild(allTitle);
  }

  const targetAll = allDiv || body;
  const importantCols = isRangerSostat
    ? new Set([
        'PSEUDO',
        'STTYPE',
        'STACON',
        'CLASS',
        'PRIORT',
        'ACRONM',
        'NORMST',
        'CTLFLG',
        'HISFLG',
        'HWADR2',
        'HWTYPE',
        'SOEHIS',
        'INHPRO',
        'PNLNAM',
        'DEVNAM',
      ])
    : null;

  appendSectionFields(
    targetAll,
    importantDiv,
    importantCols,
    sectionType,
    data.compare_columns,
    row,
    isRangerSostat
  );

  if (importantDiv) {
    if (
      !importantDiv.childElementCount ||
      importantDiv.childElementCount === 1
    ) {
      const none = document.createElement('div');
      none.style.color = '#9ca3af';
      none.textContent =
        'Nenhuma diferenca relevante nos campos principais selecionados.';
      importantDiv.appendChild(none);
    }
    importantDiv.style.display = 'block';
    allDiv.style.display = 'none';
    body.appendChild(actions);
    body.appendChild(importantDiv);
    body.appendChild(allDiv);
    return body;
  }

  if (!body.childElementCount && !targetAll.childElementCount) {
    const none = document.createElement('div');
    none.style.color = '#9ca3af';
    none.textContent = 'Nenhuma diferenca relevante nas colunas selecionadas.';
    targetAll.appendChild(none);
  }
  return body;
}

function renderCompareSection(
  data,
  section,
  resultsEl,
  viewModeNow,
  rowCounterRef
) {
  if (!section.rows.length) return;

  const isRangerSostat = (data.table || '').toUpperCase() === 'RANGER_SOSTAT';
  const details = document.createElement('details');
  details.className = `diff-section ${section.type}`;
  if (section.type === 'changed') {
    details.open = true;
  }

  const maxPerSection = 50;
  const extraInfo =
    section.rows.length > maxPerSection
      ? ` · mostrando primeiras ${maxPerSection} chaves`
      : '';
  const summary = document.createElement('summary');
  summary.className = 'diff-section-header';
  summary.innerHTML = `<span class="diff-section-title">${section.title} (${section.rows.length})</span>${extraInfo ? `<span class="diff-section-extra">${extraInfo}</span>` : ''}`;
  details.appendChild(summary);

  const listContainer = document.createElement('div');
  listContainer.className = 'diff-section-body';
  for (const row of section.rows.slice(0, maxPerSection)) {
    const rowDetails = document.createElement('details');
    rowDetails.className = `diff-row diff-row-${section.type}`;
    const rowId = `row-${++rowCounterRef.value}`;
    const rowSummary = document.createElement('summary');
    const summaryData = buildRowSummary(data, row, isRangerSostat);
    const visualType =
      row.type === 'removed'
        ? 'added'
        : row.type === 'added'
          ? 'removed'
          : 'changed';
    const typeLabel =
      row.type === 'removed'
        ? 'Nova'
        : row.type === 'added'
          ? 'Removida'
          : 'Alterada';
    rowSummary.innerHTML = `
      <span class="badge ${visualType}" style="margin-right:6px;">${typeLabel}</span>
      <span style="font-size:12px;">${summaryData.keyParts.join(', ')}${isRangerSostat && summaryData.extraParts.length ? ' · ' + summaryData.extraParts.join(' · ') : ''}</span>
    `;
    rowDetails.appendChild(rowSummary);
    rowDetails.appendChild(
      buildRowBody(data, section.type, row, rowId, viewModeNow, isRangerSostat)
    );
    listContainer.appendChild(rowDetails);
  }

  details.appendChild(listContainer);
  if (section.rows.length > maxPerSection) {
    const note = document.createElement('div');
    note.style.fontSize = '11px';
    note.style.color = '#9ca3af';
    note.style.marginTop = '4px';
    note.textContent = `Existem mais ${section.rows.length - maxPerSection} registros nesta categoria nao exibidos aqui para manter a visualizacao enxuta.`;
    details.appendChild(note);
  }
  resultsEl.appendChild(details);
}

function renderResult(data) {
  const resultsEl = document.getElementById('results');
  const rows = data.rows || [];
  const groupedRows = { added: [], removed: [], changed: [] };
  for (const row of rows) {
    if (row.type === 'added') groupedRows.added.push(row);
    else if (row.type === 'removed') groupedRows.removed.push(row);
    else groupedRows.changed.push(row);
  }

  const summaryData = buildCompareSummary(
    data,
    groupedRows,
    groupedRows.changed
  );
  renderCompareSummary(data, summaryData);
  const controls = createViewModeControls();
  const summaryCard = document.querySelector(
    '.result-summary-card .result-summary-grid > div:nth-child(3)'
  );
  if (summaryCard) {
    summaryCard.appendChild(controls);
  }

  renderPaginationControls(data);
  syncFilterColumnOptions(data.compare_columns || []);

  resultsEl.innerHTML = '';
  if (!rows.length) {
    resultsEl.innerHTML =
      '<div class="tables-overview-card">Nenhuma diferenca encontrada para o recorte atual. Ajuste filtros apenas se precisar inspecao mais especifica.</div>';
    return;
  }

  window.lastCompareResult = data;
  const viewModeNow = window.diffViewMode || 'list';
  const rowCounterRef = { value: 0 };
  for (const section of buildCompareSections(data, groupedRows)) {
    renderCompareSection(data, section, resultsEl, viewModeNow, rowCounterRef);
  }
}

function renderPaginationControls(data) {
  const pagEl = document.getElementById('pagination');
  if (!pagEl) return;

  const totalRows =
    typeof data.total_filtered_rows === 'number'
      ? data.total_filtered_rows
      : data.row_count || 0;
  const page = data.page || 1;
  const totalPages = data.total_pages || 1;

  pagEl.innerHTML = '';
  if (!totalRows) return;

  const info = document.createElement('span');
  info.textContent =
    `Total de ${totalRows} registros com diferenca` +
    (totalPages > 1 ? ` · pagina ${page} de ${totalPages}` : '');
  pagEl.appendChild(info);

  if (totalPages > 1) {
    const controls = document.createElement('span');
    controls.style.marginLeft = '12px';

    const prevBtn = document.createElement('button');
    prevBtn.textContent = 'Anterior';
    prevBtn.className = 'secondary';
    prevBtn.disabled = page <= 1;
    prevBtn.style.marginRight = '4px';
    prevBtn.onclick = () => changePage(page - 1);

    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Proxima';
    nextBtn.className = 'secondary';
    nextBtn.disabled = page >= totalPages;

    controls.appendChild(prevBtn);
    controls.appendChild(nextBtn);
    pagEl.appendChild(controls);
  }
}

window.renderResult = renderResult;
window.renderPaginationControls = renderPaginationControls;
