const DISPLAY_PRIORITY_COLUMNS = [
  'INHPRO',
  'ITEMNB',
  'RTUNO',
  'PNTNO',
  'PNTNAM',
  'SUBNAM',
  'BITBYT',
  'UNIQID',
  'PNLNAM',
  'PNLNDX',
  'MEASID',
  'PHISID',
  'STACON',
  'PRIORT',
  'PSEUDO',
  'SOETYP',
  'SOEHIS',
  'NORMST',
  'OVROPT',
  'OID',
  'CLASS',
  'DEVNAM',
  'LPTYPE',
  'PDESCR',
];

function escapeHtml(s) {
  return (s + '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlightText(text, tokens) {
  if (!text) return '';
  if (!tokens || !tokens.length) return text;
  try {
    const parts = tokens.map((t) => escapeRegExp(t)).filter(Boolean);
    if (!parts.length) return text;
    const re = new RegExp('(' + parts.join('|') + ')', 'ig');
    return text.replace(re, (m) => `<mark>${m}</mark>`);
  } catch (e) {
    return text;
  }
}

function normalizeColumnKey(name) {
  return String(name || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
}

function isLikelyWideColumn(name) {
  const key = normalizeColumnKey(name);
  return (
    key.includes('DESC') ||
    key.includes('TEXT') ||
    key.includes('NOTE') ||
    key.includes('MSG') ||
    key.includes('COMM') ||
    key.includes('NAM')
  );
}

function getColumnPriorityScore(name, index) {
  const key = normalizeColumnKey(name);
  let score = 1000 - index;
  const knownIndex = DISPLAY_PRIORITY_COLUMNS.indexOf(key);
  if (knownIndex >= 0) score += 8000 - knownIndex * 20;
  if (
    key.endsWith('ID') ||
    key.endsWith('NO') ||
    key.endsWith('NB') ||
    key.includes('KEY')
  ) {
    score += 400;
  }
  if (key.includes('NAM') || key.includes('DESC') || key.includes('TEXT')) {
    score += 300;
  }
  if (key.includes('STAT') || key.includes('TYPE') || key.includes('FLAG')) {
    score += 160;
  }
  return score;
}

function orderColumnsForDisplay(tableName, columns) {
  return [...(columns || [])].sort((a, b) => {
    const scoreA = getColumnPriorityScore(
      a,
      (columns || []).indexOf(a),
      tableName
    );
    const scoreB = getColumnPriorityScore(
      b,
      (columns || []).indexOf(b),
      tableName
    );
    if (scoreA !== scoreB) return scoreB - scoreA;
    return (columns || []).indexOf(a) - (columns || []).indexOf(b);
  });
}

function pickPinnedColumns(columns) {
  const ordered = columns || [];
  return ordered.slice(0, Math.min(2, ordered.length));
}

function serializeCellValue(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch (e) {
      return String(value);
    }
  }
  return String(value);
}

function buildTableOverview(tableName, orderedCols, shownCount, totalCount) {
  const overview = document.createElement('div');
  overview.className = 'result-table-meta';
  const leadingColumns = orderedCols.slice(0, 5);
  const wideColumns = orderedCols.filter((name) => isLikelyWideColumn(name));
  overview.innerHTML = `
    <div class="table-chip-row">
      <span class="table-chip"><strong>Tabela:</strong> ${escapeHtml(tableName)}</span>
      <span class="table-chip"><strong>Linhas exibidas:</strong> ${shownCount}</span>
      <span class="table-chip"><strong>Total no recorte:</strong> ${totalCount}</span>
    </div>
    ${
      leadingColumns.length
        ? `<div class="table-note"><strong>Campos na frente:</strong> ${leadingColumns.map((name) => escapeHtml(name)).join(', ')}</div>`
        : ''
    }
    ${
      wideColumns.length
        ? `<div class="table-note"><strong>Campos longos para revisar:</strong> ${wideColumns
            .slice(0, 4)
            .map((name) => escapeHtml(name))
            .join(', ')}</div>`
        : ''
    }
  `;
  return overview;
}

function pickRowHeadlineFields(row, orderedCols) {
  const preferred = [
    'PNTNAM',
    'SUBNAM',
    'PNLNAM',
    'ITEMNB',
    'PNTNO',
    'RTUNO',
    'INHPRO',
    'STACON',
    'NORMST',
  ];
  const byKey = new Map(
    orderedCols.map((name) => [normalizeColumnKey(name), name])
  );
  const fields = [];
  preferred.forEach((key) => {
    const column = byKey.get(key);
    if (!column) return;
    const value =
      row && Object.prototype.hasOwnProperty.call(row, column)
        ? row[column]
        : '';
    if (value === '' || value === null || value === undefined) return;
    fields.push([column, value]);
  });
  return fields.slice(0, 4);
}

function buildRowPreviewBand(rowObjs, orderedCols) {
  const preview = document.createElement('div');
  preview.className = 'row-preview-band';
  rowObjs.slice(0, 3).forEach((item, index) => {
    const card = document.createElement('div');
    card.className = 'row-preview-card';
    const fields = pickRowHeadlineFields(item.row || {}, orderedCols);
    card.innerHTML = `
      <div class="row-preview-title">Linha ${index + 1}${item.score != null ? ` · score ${item.score}` : ''}</div>
      ${
        fields.length
          ? fields
              .map(
                ([column, value]) =>
                  `<div class="row-preview-line"><strong>${escapeHtml(column)}:</strong> ${escapeHtml(serializeCellValue(value))}</div>`
              )
              .join('')
          : '<div class="row-preview-line">Sem campos prioritarios preenchidos neste recorte.</div>'
      }
    `;
    preview.appendChild(card);
  });
  return preview;
}

function buildTableCell(value, tokens, wide, extraClass) {
  const td = document.createElement('td');
  td.className = `results-cell${wide ? ' results-cell-wide' : ''}${extraClass ? ' ' + extraClass : ''}`;
  const text = serializeCellValue(value);
  td.title = text;
  if (typeof value === 'object' && value !== null) {
    const pre = document.createElement('pre');
    pre.className = 'results-json';
    pre.textContent = text;
    td.appendChild(pre);
    return td;
  }
  const isMultiline = text.includes('\n') || text.length > 120;
  const content = document.createElement(isMultiline ? 'div' : 'span');
  content.className = `cell-text${isMultiline ? ' multiline' : ''}`;
  content.innerHTML = highlightText(escapeHtml(text), tokens).replace(
    /\n/g,
    '<br>'
  );
  td.appendChild(content);
  return td;
}

function buildResultsTable(tableName, rowObjs, rawColumns, options) {
  const includeScore = !!(options && options.includeScore);
  const tokens = (options && options.tokens) || [];
  const orderedCols = orderColumnsForDisplay(tableName, rawColumns);
  const pinnedCols = pickPinnedColumns(orderedCols);
  const shell = document.createElement('div');
  shell.className = 'results-table-shell';

  const table = document.createElement('table');
  table.className = 'results results-enhanced';
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  if (includeScore) {
    const scoreTh = document.createElement('th');
    scoreTh.className = 'results-score-col';
    scoreTh.textContent = 'pontuacao';
    headRow.appendChild(scoreTh);
  }
  orderedCols.forEach((column) => {
    const th = document.createElement('th');
    const classes = [];
    if (column === pinnedCols[0]) classes.push('results-sticky-main');
    if (column === pinnedCols[1]) classes.push('results-sticky-secondary');
    if (isLikelyWideColumn(column)) classes.push('results-col-wide');
    if (classes.length) th.className = classes.join(' ');
    th.textContent = column;
    th.title = column;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rowObjs.forEach((item) => {
    const tr = document.createElement('tr');
    if (includeScore && Number(item.score || 0) >= 95) {
      tr.className = 'results-row-strong';
    }
    if (includeScore) {
      const scoreTd = document.createElement('td');
      scoreTd.className = 'results-score-col';
      scoreTd.textContent = item.score == null ? '' : String(item.score);
      tr.appendChild(scoreTd);
    }
    orderedCols.forEach((column) => {
      const extraClass =
        column === pinnedCols[0]
          ? 'results-sticky-main'
          : column === pinnedCols[1]
            ? 'results-sticky-secondary'
            : '';
      const wide = isLikelyWideColumn(column);
      const value =
        item.row && Object.prototype.hasOwnProperty.call(item.row, column)
          ? item.row[column]
          : '';
      tr.appendChild(buildTableCell(value, tokens, wide, extraClass));
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  shell.appendChild(table);
  return { shell, orderedCols };
}

function collectRowObjects(rows) {
  const colsSet = new Set();
  const rowObjs = [];
  rows.forEach((it) => {
    const row = it.row || (it.row_json ? JSON.parse(it.row_json) : {});
    rowObjs.push({ score: it.score, row });
    if (row && typeof row === 'object') {
      Object.keys(row).forEach((column) => colsSet.add(column));
    }
  });
  return { cols: Array.from(colsSet).slice(0, 200), rowObjs };
}

function renderResults(q, results, per_table) {
  const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
  const root = $('resultsArea');
  root.innerHTML = '';
  const exportBtn = $('exportAllBtn');
  if (exportBtn) exportBtn.disabled = true;
  let keys = Object.keys(results);
  if (priorityTables && priorityTables.length) {
    const set = new Set(priorityTables);
    const pri = priorityTables.filter((t) => keys.includes(t));
    const others = keys.filter((k) => !set.has(k));
    keys = pri.concat(others);
  }
  if (!keys.length) {
    root.innerHTML =
      '<div class="card small">Nenhum resultado encontrado.</div>';
    return;
  }
  if (exportBtn) exportBtn.disabled = false;
  keys.forEach((tbl) => {
    const block = document.createElement('div');
    block.className = 'card result-card';
    const header = document.createElement('div');
    header.className = 'result-card-header';
    const tagId = tableTagId(tbl);
    header.innerHTML = `
      <div>
        <span id="${tagId}" class="priority-tag">PRIORITARIO</span>
        <strong>${escapeHtml(tbl)}</strong> <span class="muted">(${results[tbl].length})</span>
      </div>
      <div class="result-card-actions">
        <button class="btn ghost" onclick="openTable(event,'${encodeURIComponent(
          tbl
        )}')">Abrir</button>
        <button class="btn ghost" onclick="exportTableCsv('${encodeURIComponent(
          tbl
        )}')">Export CSV</button>
      </div>`;
    block.appendChild(header);

    const { cols, rowObjs } = collectRowObjects(results[tbl]);
    if (!cols.length) {
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(rowObjs, null, 2);
      block.appendChild(pre);
      root.appendChild(block);
      return;
    }

    const shownRows = rowObjs.slice(0, per_table);
    const tableView = buildResultsTable(tbl, shownRows, cols, {
      includeScore: true,
      tokens,
    });
    block.appendChild(
      buildTableOverview(
        tbl,
        tableView.orderedCols,
        shownRows.length,
        rowObjs.length
      )
    );
    block.appendChild(buildRowPreviewBand(shownRows, tableView.orderedCols));
    block.appendChild(tableView.shell);
    if (rowObjs.length > shownRows.length) {
      const note = document.createElement('div');
      note.className = 'table-note';
      note.textContent = `Exibindo ${shownRows.length} de ${rowObjs.length} linha(s) deste recorte. Use "Abrir" para navegar a tabela.`;
      block.appendChild(note);
    }
    root.appendChild(block);
  });
  try {
    (priorityTables || []).forEach((p) => {
      const el = document.getElementById(tableTagId(p));
      if (el) el.style.display = 'inline-block';
    });
  } catch (e) {
    // ignore
  }
}

async function openTable(ev, tableEnc) {
  if (ev) ev.stopPropagation();
  const table = decodeURIComponent(tableEnc);
  const limit = 100;
  const offset = 0;
  try {
    const data = await apiJSON(
      `/api/table?name=${encodeURIComponent(table)}&limit=${limit}&offset=${offset}`
    );
    if (data.error) {
      alert('Erro ao abrir tabela: ' + data.error);
      return;
    }
    const area = $('resultsArea');
    area.innerHTML = `<div class="card"><h3>Tabela: ${escapeHtml(
      table
    )} <span class="muted">linhas: ${data.total}</span> <span class="muted">engine: ${escapeHtml(
      data.db_engine || ''
    )}</span></h3></div>`;
    if (!data.rows || !data.rows.length) {
      const empty = document.createElement('div');
      empty.className = 'card small';
      empty.textContent = 'Sem linhas para mostrar.';
      area.appendChild(empty);
      return;
    }
    const hdr = document.createElement('div');
    hdr.className = 'card';
    const rowObjs = (data.rows || []).map((row) => {
      const mapped = {};
      (data.columns || []).forEach((column, index) => {
        mapped[column] = row[index];
      });
      return { row: mapped };
    });
    const tableView = buildResultsTable(table, rowObjs, data.columns || [], {
      includeScore: false,
      tokens: [],
    });
    hdr.appendChild(
      buildTableOverview(
        table,
        tableView.orderedCols,
        rowObjs.length,
        data.total || rowObjs.length
      )
    );
    hdr.appendChild(buildRowPreviewBand(rowObjs, tableView.orderedCols));
    hdr.appendChild(tableView.shell);
    const pager = document.createElement('div');
    pager.className = 'controls-footer';
    pager.innerHTML =
      '<button class="btn ghost" onclick="backToResults()">Voltar</button>';
    hdr.appendChild(pager);
    area.appendChild(hdr);
  } catch (e) {
    logUi('ERROR', 'abrir tabela falhou');
    alert('Erro ao abrir tabela');
  }
}

async function exportTableCsv(tableEnc) {
  const table = decodeURIComponent(tableEnc);
  try {
    const res = await fetch(
      `/api/table?name=${encodeURIComponent(table)}&limit=1000&offset=0`
    );
    if (!res.ok) {
      alert('Erro ao exportar: http ' + res.status);
      return;
    }
    const data = await res.json();
    if (data.error) {
      alert('Erro ao exportar: ' + data.error);
      return;
    }
    const cols = data.columns;
    const rows = data.rows;
    const esc = (v) => '"' + String(v).replace(/"/g, '""') + '"';
    const header = cols.map(esc).join(',') + '\n';
    const body = rows.map((r) => r.map(esc).join(',')).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${table}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Erro ao exportar: falha na requisicao');
    logUi('ERROR', 'export csv falhou');
  }
}

function exportResultsCsv() {
  if (!lastResults || !lastResults.results) {
    alert('Sem resultados para exportar');
    return;
  }
  const results = lastResults.results;
  const colsSet = new Set(['table', 'score']);
  const rowsOut = [];
  Object.keys(results).forEach((tbl) => {
    (results[tbl] || []).forEach((item) => {
      let rowObj = item && item.row ? item.row : null;
      if (!rowObj && item && item.row_json) {
        try {
          rowObj = JSON.parse(item.row_json);
        } catch (e) {
          rowObj = {};
        }
      }
      if (!rowObj || typeof rowObj !== 'object') rowObj = {};
      Object.keys(rowObj).forEach((k) => colsSet.add(k));
      rowsOut.push({
        table: tbl,
        score: item && item.score != null ? item.score : '',
        row: rowObj,
      });
    });
  });
  const cols = Array.from(colsSet);
  const esc = (v) => '"' + String(v).replace(/"/g, '""') + '"';
  const lines = [cols.map(esc).join(',')];
  rowsOut.forEach((r) => {
    const line = cols.map((c) => {
      if (c === 'table') return r.table;
      if (c === 'score') return r.score;
      const v =
        r.row && Object.prototype.hasOwnProperty.call(r.row, c) ? r.row[c] : '';
      return v && typeof v === 'object' ? JSON.stringify(v) : v;
    });
    lines.push(line.map(esc).join(','));
  });
  const blob = new Blob([lines.join('\n')], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'resultados.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function backToResults() {
  if (lastResults && lastResults.results) {
    const perTable = parseInt($('per_table').value, 10) || 10;
    $('searchMeta').textContent =
      `Resultados: ${lastResults.returned_count || 0} (candidatos: ${
        lastResults.candidate_count || 0
      })`;
    renderResults(
      lastQuery || ($('q') ? $('q').value.trim() : ''),
      lastResults.results || {},
      perTable
    );
  } else {
    refreshUiState();
  }
}

window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;
window.escapeRegExp = escapeRegExp;
window.highlightText = highlightText;
window.renderResults = renderResults;
window.openTable = openTable;
window.exportTableCsv = exportTableCsv;
window.exportResultsCsv = exportResultsCsv;
window.backToResults = backToResults;
