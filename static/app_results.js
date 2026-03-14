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
const OPEN_TABLE_CHUNK = 120;
const OPEN_TABLE_EXPORT_CHUNK = 250;
const DEFAULT_VISIBLE_COLUMNS = 12;
const openTableStates = new Map();
const openTableRequestSeq = new Map();
const TABLE_COLUMN_GROUPS = [
  {
    name: 'IDENTIFICACAO',
    keys: ['INH', 'ITEM', 'PNL', 'PNT', 'RTU', 'SUB', 'UNIQ', 'NAME', 'NOME', 'COD'],
  },
  {
    name: 'STATUS',
    keys: ['STAT', 'STACON', 'NORMST', 'SOEHIS', 'PRIORT', 'CLASS'],
  },
  {
    name: 'TIPO_E_HIERARQUIA',
    keys: ['PSEUDO', 'SOETYP', 'ACRONM', 'MEASID', 'PHISID', 'BITBYT'],
  },
  {
    name: 'LOCAL',
    keys: ['HWADR', 'HW', 'SITE', 'AREA', 'REGIAO', 'REGION'],
  },
];

function escapeHtml(s) {
  return (s + '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function appendTextWithBreaks(parent, text) {
  const parts = String(text).split('\n');
  parts.forEach((part, index) => {
    parent.appendChild(document.createTextNode(part));
    if (index < parts.length - 1) {
      parent.appendChild(document.createElement('br'));
    }
  });
}

function buildHighlightedFragment(text, tokens) {
  const fragment = document.createDocumentFragment();
  const source = String(text || '');
  if (!tokens || !tokens.length) {
    appendTextWithBreaks(fragment, source);
    return fragment;
  }
  try {
    const parts = tokens
      .map((t) => escapeRegExp(String(t)))
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    if (!parts.length) {
      appendTextWithBreaks(fragment, source);
      return fragment;
    }
    const re = new RegExp('(' + parts.join('|') + ')', 'ig');
    let cursor = 0;
    let match;
    while ((match = re.exec(source)) !== null) {
      const matchText = match[0];
      const start = match.index;
      if (start > cursor) {
        appendTextWithBreaks(fragment, source.slice(cursor, start));
      }
      const mark = document.createElement('mark');
      mark.textContent = matchText;
      fragment.appendChild(mark);
      cursor = start + matchText.length;
      if (matchText.length === 0) {
        re.lastIndex += 1;
      }
    }
    if (cursor < source.length) {
      appendTextWithBreaks(fragment, source.slice(cursor));
    }
    return fragment;
  } catch (e) {
    appendTextWithBreaks(fragment, source);
    return fragment;
  }
}

function normalizeColumnKey(name) {
  return String(name || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
}

function normalizeForMap(value) {
  if (value === undefined || value === null) return '';
  return String(value).trim();
}

function buildGroupLegendChip(name, columns) {
  const chip = document.createElement('button');
  chip.type = 'button';
  chip.className = 'group-chip';
  chip.textContent = `${name} (${columns.length})`;
  chip.title = columns.join(', ');
  return chip;
}

function buildColumnGroupLegend(columnGroups) {
  if (!columnGroups || !columnGroups.length) return null;
  const shell = document.createElement('div');
  shell.className = 'results-group-legend';
  columnGroups.forEach((group) => {
    const chip = buildGroupLegendChip(group.name, group.columns || []);
    shell.appendChild(chip);
  });
  return shell;
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

function normalizeTableRowPayload(payload, fallbackColumns = null) {
  if (!payload || typeof payload !== 'object') return {};
  if (payload.row && typeof payload.row === 'object' && !Array.isArray(payload.row)) {
    return payload.row;
  }
  if (typeof payload.row_json === 'string') {
    try {
      const parsed = JSON.parse(payload.row_json);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed;
      }
    } catch (e) {
      return {};
    }
  }
  if (
    payload.row_json &&
    typeof payload.row_json === 'object' &&
    !Array.isArray(payload.row_json)
  ) {
    return payload.row_json;
  }
  if (Array.isArray(payload) && Array.isArray(fallbackColumns)) {
    const mapped = {};
    fallbackColumns.forEach((column, index) => {
      mapped[column] = payload[index];
    });
    return mapped;
  }
  if (!Array.isArray(payload) && !payload.row && !payload.row_json) {
    return payload;
  }
  return {};
}

function buildColumnGroups(columns) {
  const groups = new Map(
    TABLE_COLUMN_GROUPS.map((group) => [group.name, { name: group.name, columns: [] }])
  );
  const unknownColumns = [];

  const orderedColumns = columns || [];
  orderedColumns.forEach((column) => {
    const key = normalizeColumnKey(column);
    const normalized = String(column || '').toUpperCase();
    let assignedName = null;
    for (const groupDef of TABLE_COLUMN_GROUPS) {
      if (groupDef.keys.some((needle) => key.includes(needle) || normalized.includes(needle))) {
        assignedName = groupDef.name;
        break;
      }
    }
    if (assignedName) {
      groups.get(assignedName).columns.push(column);
      return;
    }
    unknownColumns.push(column);
  });

  const grouped = [];
  TABLE_COLUMN_GROUPS.forEach((groupDef) => {
    const group = groups.get(groupDef.name);
    if (group.columns.length) {
      grouped.push(group);
    }
  });
  if (unknownColumns.length) {
    grouped.push({ name: 'OUTROS', columns: unknownColumns });
  }
  return grouped;
}

function escapeCsvValue(v) {
  return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
}

function makeCsvText(columns, rows, mapRow) {
  const cols = Array.isArray(columns) ? columns : Array.from(columns || []);
  const lines = [cols.map(escapeCsvValue).join(',')];
  rows.forEach((row) => {
    const mapped = mapRow ? mapRow(row) : row;
    lines.push(cols.map((c) => escapeCsvValue((mapped || {})[c])).join(','));
  });
  return lines.join('\n');
}

function downloadCsv(filename, text) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function fetchAllTableRowsForExport(table) {
  const initialState = getOpenTableState(table);
  const columnsSet = new Set();
  const rows = [];
  let offset = 0;
  let expectedTotal =
    Number.isFinite(initialState.total) && initialState.total > 0
      ? initialState.total
      : null;

  (initialState.columns || []).forEach((column) => columnsSet.add(column));
  if (Array.isArray(initialState.rows) && initialState.rows.length) {
    initialState.rows.forEach((row) => {
      const rowObj = normalizeTableRowPayload(row, initialState.columns || []);
      if (rowObj && typeof rowObj === 'object') {
        Object.keys(rowObj).forEach((column) => columnsSet.add(column));
      }
      rows.push(rowObj);
    });
    offset = initialState.rows.length;
  }

  if (expectedTotal !== null && rows.length >= expectedTotal) {
    return { columns: Array.from(columnsSet), rows: rows.slice(0) };
  }

  const maxPages = 500;
  let maxPagesHit = true;
  for (let page = 0; page < maxPages; page += 1) {
    const data = await apiJSON(
      `/api/table?name=${encodeURIComponent(table)}&limit=${OPEN_TABLE_EXPORT_CHUNK}&offset=${offset}`
    );
    if (data.error) {
      throw new Error(data.error);
    }

    const cols = data.columns || [];
    cols.forEach((column) => columnsSet.add(column));

    const rawRows = data.rows || [];
    const rowObjs = rawRows.map((row) => normalizeTableRowPayload(row, cols));
    rowObjs.forEach((rowObj) => {
      if (rowObj && typeof rowObj === 'object') {
        Object.keys(rowObj).forEach((column) => columnsSet.add(column));
      }
      rows.push(rowObj);
    });

    const totalRows = Number.isFinite(data.total) ? Number(data.total) : null;
    if (totalRows !== null) {
      expectedTotal = totalRows;
    }
    if (expectedTotal !== null && rows.length >= expectedTotal) {
      maxPagesHit = false;
      break;
    }
    if (!rawRows.length || rawRows.length < OPEN_TABLE_EXPORT_CHUNK) {
      maxPagesHit = false;
      break;
    }

    offset += rawRows.length;
  }

  if (maxPagesHit && expectedTotal !== null && rows.length < expectedTotal) {
    throw new Error(
      `exportacao parcial bloqueada: limite de ${maxPages} paginas atingido`
    );
  }

  return { columns: Array.from(columnsSet), rows };
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
    const scoreA = getColumnPriorityScore(a, (columns || []).indexOf(a));
    const scoreB = getColumnPriorityScore(b, (columns || []).indexOf(b));
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
    const safeScore =
      item.score == null ? '' : escapeHtml(serializeCellValue(item.score));
    card.innerHTML = `
      <div class="row-preview-title">Linha ${index + 1}${item.score != null ? ` · score ${safeScore}` : ''}</div>
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
  content.replaceChildren(buildHighlightedFragment(text, tokens));
  td.appendChild(content);
  return td;
}

function buildResultsTable(tableName, rowObjs, rawColumns, options) {
  const includeScore = !!(options && options.includeScore);
  const tokens = (options && options.tokens) || [];
  const orderedCols = orderColumnsForDisplay(tableName, rawColumns);
  const pinnedCols = pickPinnedColumns(orderedCols);
  const pinnedSet = new Set(pinnedCols);
  const hiddenColumns = new Set();
  if (!tokens.length && orderedCols.length > DEFAULT_VISIBLE_COLUMNS) {
    orderedCols.forEach((column, index) => {
      if (index >= DEFAULT_VISIBLE_COLUMNS && !pinnedSet.has(column)) {
        hiddenColumns.add(column);
      }
    });
  }
  const columnGroups = buildColumnGroups(orderedCols);
  const shell = document.createElement('div');
  shell.className = 'results-table-shell';
  if (hiddenColumns.size) {
    const toolbar = document.createElement('div');
    toolbar.className = 'results-table-toolbar';
    const info = document.createElement('span');
    info.className = 'table-note';
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'btn ghost small';
    const updateCompactUi = () => {
      const expanded = shell.classList.contains('show-all-cols');
      if (expanded) {
        info.textContent = `Exibindo todas as ${orderedCols.length} colunas.`;
        toggleBtn.textContent = 'Mostrar menos colunas';
      } else {
        const visibleCount = orderedCols.length - hiddenColumns.size;
        info.textContent = `Modo compacto ativo: ${visibleCount}/${orderedCols.length} colunas visiveis.`;
        toggleBtn.textContent = 'Mostrar todas as colunas';
      }
    };
    toggleBtn.addEventListener('click', () => {
      shell.classList.toggle('show-all-cols');
      updateCompactUi();
    });
    toolbar.appendChild(info);
    toolbar.appendChild(toggleBtn);
    shell.appendChild(toolbar);
    updateCompactUi();
  }

  const table = document.createElement('table');
  table.className = 'results results-enhanced';
  const thead = document.createElement('thead');
  if (columnGroups.length > 1 && !hiddenColumns.size) {
    const groupRow = document.createElement('tr');
    if (includeScore) {
      const scoreTh = document.createElement('th');
      scoreTh.className = 'results-score-col results-group-cell';
      scoreTh.rowSpan = 2;
      scoreTh.textContent = 'pontuacao';
      groupRow.appendChild(scoreTh);
    }
    columnGroups.forEach((group) => {
      const th = document.createElement('th');
      th.className = 'results-group-header';
      th.colSpan = Math.max(1, group.columns.length);
      th.textContent = group.name;
      groupRow.appendChild(th);
    });
    thead.appendChild(groupRow);
  }
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
    if (hiddenColumns.has(column)) classes.push('results-col-hidden');
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
      const td = buildTableCell(value, tokens, wide, extraClass);
      if (hiddenColumns.has(column)) {
        td.classList.add('results-col-hidden');
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  shell.appendChild(table);
  return { shell, orderedCols, columnGroups };
}

function collectRowObjects(rows, fallbackColumns = null) {
  const colsSet = new Set();
  const rowObjs = [];
  rows.forEach((it) => {
    const row = normalizeTableRowPayload(it, fallbackColumns);
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
    const titleWrap = document.createElement('div');
    const tag = document.createElement('span');
    tag.id = tagId;
    tag.className = 'priority-tag';
    tag.textContent = 'PRIORITARIO';
    const strong = document.createElement('strong');
    strong.textContent = tbl;
    const count = document.createElement('span');
    count.className = 'muted';
    count.textContent = `(${results[tbl].length})`;
    titleWrap.appendChild(tag);
    titleWrap.appendChild(document.createTextNode(' '));
    titleWrap.appendChild(strong);
    titleWrap.appendChild(document.createTextNode(' '));
    titleWrap.appendChild(count);

    const actions = document.createElement('div');
    actions.className = 'result-card-actions';
    const openBtn = document.createElement('button');
    openBtn.className = 'btn ghost';
    openBtn.type = 'button';
    openBtn.textContent = 'Abrir';
    openBtn.addEventListener('click', (event) =>
      openTable(event, encodeURIComponent(tbl))
    );
    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn ghost';
    exportBtn.type = 'button';
    exportBtn.textContent = 'Export CSV';
    exportBtn.addEventListener('click', () =>
      exportTableCsv(encodeURIComponent(tbl))
    );
    actions.appendChild(openBtn);
    actions.appendChild(exportBtn);

    header.appendChild(titleWrap);
    header.appendChild(actions);
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
    const groupLegend = buildColumnGroupLegend(tableView.columnGroups || []);
    if (groupLegend) block.appendChild(groupLegend);
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

function getOpenTableState(table) {
  return (
    openTableStates.get(table) || {
      table: table,
      rows: [],
      columns: [],
      total: 0,
      offset: 0,
      dbEngine: '',
      loading: false,
    }
  );
}

function setOpenTableState(table, patch) {
  const state = getOpenTableState(table);
  const merged = { ...state, ...patch };
  openTableStates.set(table, merged);
  return merged;
}

function hasOpenTableRows(state) {
  return state.total > 0 && state.rows.length < state.total;
}

function mergeUniqueColumns(base, extra) {
  const set = new Set(base);
  const merged = base.slice();
  (extra || []).forEach((name) => {
    if (!set.has(name)) {
      set.add(name);
      merged.push(name);
    }
  });
  return merged;
}

function buildOpenTableHeader(table, state) {
  const card = document.createElement('div');
  card.className = 'card';
  const details = [`linhas: ${state.total}`, `engine: ${escapeHtml(state.dbEngine || '')}`];
  if (hasOpenTableRows(state)) {
    details.unshift(`carregadas: ${state.rows.length}`);
  }
  card.innerHTML = `<h3>Tabela: ${escapeHtml(
    table
  )} <span class="muted">${details.join(' · ')}</span></h3>`;
  return card;
}

function renderOpenTablePager(table, state, container) {
  const footer = document.createElement('div');
  footer.className = 'controls-footer open-table-pager';
  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn ghost';
  nextBtn.type = 'button';
  const loading = !!state.loading;
  const canLoadMore = hasOpenTableRows(state);

  if (canLoadMore) {
    const remain = Math.max(0, state.total - state.rows.length);
    const loadCount = Math.min(OPEN_TABLE_CHUNK, remain);
    nextBtn.textContent = `Carregar mais ${loadCount} linha(s)`;
    nextBtn.disabled = loading;
    nextBtn.addEventListener('click', async () => {
      const currentState = getOpenTableState(table);
      if (currentState.loading) {
        return;
      }
      await loadOpenTable(table, {
        clear: false,
        offset: currentState.rows.length,
      });
    });
  } else {
    nextBtn.textContent = 'Todos os registros carregados';
    nextBtn.disabled = true;
  }

  const backBtn = document.createElement('button');
  backBtn.className = 'btn ghost small';
  backBtn.type = 'button';
  backBtn.textContent = 'Voltar';
  backBtn.addEventListener('click', () => backToResults());

  const exportBtn = document.createElement('button');
  exportBtn.className = 'btn ghost';
  exportBtn.type = 'button';
  exportBtn.textContent = 'Export CSV';
  exportBtn.disabled = loading || !state.total;
  exportBtn.addEventListener('click', () => exportTableCsv(encodeURIComponent(table)));

  footer.appendChild(nextBtn);
  footer.appendChild(exportBtn);
  footer.appendChild(backBtn);
  container.appendChild(footer);
}

async function loadOpenTable(table, options) {
  const currentState = getOpenTableState(table);
  const clear = !options || options.clear !== false;
  const requestedOffset =
    options && Number.isFinite(options.offset) ? options.offset : 0;
  const offset = clear ? requestedOffset : currentState.rows.length;

  if (!clear && currentState.loading) {
    return;
  }

  const state = setOpenTableState(table, {
    loading: true,
    offset,
  });
  const requestSeq = (openTableRequestSeq.get(table) || 0) + 1;
  openTableRequestSeq.set(table, requestSeq);

  try {
    const data = await apiJSON(
      `/api/table?name=${encodeURIComponent(table)}&limit=${OPEN_TABLE_CHUNK}&offset=${offset}`
    );
    if (data.error) {
      alert('Erro ao abrir tabela: ' + data.error);
      state.loading = false;
      openTableStates.set(table, state);
      return;
    }

    const { cols, rowObjs } = collectRowObjects(
      data.rows || [],
      data.columns || []
    );
    const mergedColumns = clear
      ? cols
      : mergeUniqueColumns(state.columns.slice(), cols);
    const mergedRows = clear
      ? rowObjs
      : state.rows.concat(rowObjs);
    const nextState = setOpenTableState(table, {
      columns: mergedColumns.slice(0, 200),
      rows: mergedRows,
      total: Number.isFinite(data.total) ? data.total : mergedRows.length,
      dbEngine: data.db_engine || state.dbEngine,
      loading: false,
    });
    if (openTableRequestSeq.get(table) !== requestSeq) {
      return;
    }

    const area = $('resultsArea');
    if (!area) return;
    area.innerHTML = '';
    if (!mergedRows.length) {
      area.innerHTML =
        '<div class="card small">Sem linhas para mostrar.</div>';
      return;
    }

    const hdr = buildOpenTableHeader(table, nextState);
    const tableView = buildResultsTable(table, mergedRows, nextState.columns, {
      includeScore: false,
      tokens: [],
    });
    const groupLegend = buildColumnGroupLegend(tableView.columnGroups || []);
    if (groupLegend) hdr.appendChild(groupLegend);
    hdr.appendChild(
      buildTableOverview(
        table,
        tableView.orderedCols,
        mergedRows.length,
        nextState.total || mergedRows.length
      )
    );
    hdr.appendChild(buildRowPreviewBand(mergedRows.slice(0, 3), tableView.orderedCols));
    hdr.appendChild(tableView.shell);
    area.appendChild(hdr);
    renderOpenTablePager(table, nextState, area);
  } catch (e) {
    logUi('ERROR', 'abrir tabela falhou');
    alert('Erro ao abrir tabela');
  } finally {
    if (openTableRequestSeq.get(table) === requestSeq) {
      setOpenTableState(table, { loading: false });
    }
  }
}

async function openTable(ev, tableEnc) {
  if (ev) ev.stopPropagation();
  const table = decodeURIComponent(tableEnc);
  setOpenTableState(table, {
    table,
    rows: [],
    columns: [],
    total: 0,
    offset: 0,
    dbEngine: '',
    loading: false,
  });
  await loadOpenTable(table, { clear: true, offset: 0 });
}

async function exportTableCsv(tableEnc) {
  const table = decodeURIComponent(tableEnc);
  try {
    const { columns, rows } = await fetchAllTableRowsForExport(table);
    if (!rows.length) {
      alert('Sem dados para exportar');
      return;
    }
    const normalizedRows = rows.map((row) =>
      row && typeof row === 'object' ? row : {}
    );
    const csvText = makeCsvText(columns, normalizedRows, (row) => row);
    downloadCsv(`${table}.csv`, csvText);
  } catch (e) {
    const errMsg = e && e.message ? e.message : 'falha na requisicao';
    alert('Erro ao exportar tabela');
    if (typeof setFlowBanner === 'function') {
      setFlowBanner('Erro ao exportar tabela.', 'error');
    }
    logUi('ERROR', 'export csv falhou: ' + errMsg);
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
      let rowObj = normalizeTableRowPayload(item);
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
  const csvText = makeCsvText(cols, rowsOut, (r) => {
    const rowOut = {};
    cols.forEach((c) => {
      if (c === 'table') {
        rowOut[c] = r.table;
      } else if (c === 'score') {
        rowOut[c] = r.score;
      } else {
        const v = r.row && Object.prototype.hasOwnProperty.call(r.row, c) ? r.row[c] : '';
        rowOut[c] = v && typeof v === 'object' ? JSON.stringify(v) : v;
      }
    });
    return rowOut;
  });
  downloadCsv('resultados.csv', csvText);
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
window.renderResults = renderResults;
window.openTable = openTable;
window.exportTableCsv = exportTableCsv;
window.exportResultsCsv = exportResultsCsv;
window.backToResults = backToResults;
