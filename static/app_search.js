// === Funcoes utilitarias exportadas para HTML / inline_handlers ===

function onSelectRowClick(ev, nameEnc) {
  if (ev && ev.target && ev.target.closest && ev.target.closest('.file-actions')) return;
  selectUpload(nameEnc, null);
}

async function deleteUpload(nameEnc, btn) {
  if (!confirm('Deseja realmente excluir este arquivo?')) return;
  const name = decodeURIComponent(nameEnc);
  const msg = $('uploadMsg');
  const prevText = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Excluindo...';
  }
  if (msg) msg.textContent = 'Excluindo: ' + name;
  try {
    const j = await apiJSON('/admin/delete', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: name })
    });
    if (j && j.ok) {
      alert('Arquivo apagado');
      setFlowBanner('', '');
      await refreshUiState();
    } else {
      const err = (j && j.error) || 'falha ao excluir';
      setFlowBanner('Nao foi possivel excluir. Verifique se o arquivo esta em uso.', 'warn');
      alert('Erro: ' + err);
    }
  } catch (e) {
    if (msg) msg.textContent = 'Erro ao excluir';
    setFlowBanner('Erro ao excluir. Tente novamente.', 'error');
    logUi('ERROR', 'delete falhou');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevText || 'Excluir';
    }
  }
}

async function selectUpload(nameEnc, btn) {
  const name = decodeURIComponent(nameEnc);
  const msg = $('uploadMsg');
  const prevText = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Selecionando...';
  }
  if (msg) msg.textContent = 'Selecionando: ' + name;
  try {
    const j = await apiJSON('/admin/select', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: name })
    });
    if (j && j.ok) {
      if (msg) msg.textContent = 'DB selecionado: ' + name;
      manualFlowOverride = '';
      setFlowBanner('', '');
      await refreshUiState();
      closeModal();
    } else {
      const err = (j && j.error) || 'falha ao selecionar';
      if (msg) msg.textContent = 'Erro ao selecionar: ' + err;
      setFlowBanner('Nao foi possivel selecionar o arquivo. Tente novamente.', 'error');
      logUi('ERROR', 'select db falhou');
    }
  } catch (e) {
    if (msg) msg.textContent = 'Erro ao selecionar DB';
    setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
    logUi('ERROR', 'select db falhou');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevText || 'Selecionar';
    }
  }
}

async function selectDbFromTab(nameEnc) {
  const name = decodeURIComponent(nameEnc);
  const msg = $('uploadMsg');
  if (msg) msg.textContent = 'Selecionando: ' + name;
  try {
    const j = await apiJSON('/admin/select', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: name })
    });
    if (j && j.ok) {
      if (msg) msg.textContent = 'DB selecionado: ' + name;
      manualFlowOverride = '';
      setFlowBanner('', '');
      await refreshUiState();
    } else {
      const err = (j && j.error) || 'falha ao selecionar';
      if (msg) msg.textContent = 'Erro ao selecionar: ' + err;
      setFlowBanner('Nao foi possivel selecionar o arquivo. Tente novamente.', 'error');
      logUi('ERROR', 'select db falhou');
    }
  } catch (e) {
    if (msg) msg.textContent = 'Erro ao selecionar DB';
    setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
    logUi('ERROR', 'select db falhou');
  }
}

async function loadPriorityModal() {
  const allEl = $('allTablesList');
  const selEl = $('priorityListModal');
  if (!allEl || !selEl) return;
  if (!hasDbSelected()) {
    allEl.innerHTML = '<li class="muted">Nenhum DB selecionado</li>';
    selEl.innerHTML = '';
    $('priorityMsg').textContent = 'Nenhum DB selecionado';
    return;
  }
  allEl.innerHTML = '';
  selEl.innerHTML = '';
  $('priorityMsg').textContent = 'Carregando...';
  try {
    const t = await apiJSON('/api/tables');
    if (t.error) {
      allEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
      selEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
      $('priorityMsg').textContent = '';
      logUi('ERROR', 'priority tabelas ' + t.error);
      return;
    }
    const tables = t.tables || [];
    const visible = tables.filter(n => !/^MSys/i.test(n));
    const st = await apiJSON('/admin/list_uploads');
    const saved = st.priority_tables || [];
    const remaining = visible.filter(x => !saved.includes(x));
    remaining.forEach(name => {
      const li = document.createElement('li');
      li.dataset.table = name;
      li.innerHTML = `<label style="display:flex;align-items:center;gap:8px;width:100%"><input type="checkbox" data-name="${encodeURIComponent(
        name
      )}" onchange="onTableCheckboxChange(this)"> <span style="flex:1">${escapeHtml(
        name
      )}</span></label>`;
      allEl.appendChild(li);
    });
    saved.forEach(name => {
      const li = document.createElement('li');
      li.draggable = true;
      li.dataset.table = name;
      li.innerHTML = `<div style="flex:1">${escapeHtml(
        name
      )}</div><div style="display:flex;gap:6px"><button class="btn ghost" onclick="prioMoveUp(this)" title="Mover para cima">Up</button><button class="btn ghost" onclick="prioMoveDown(this)" title="Mover para baixo">Down</button><button class="btn ghost" onclick="prioRemove(this)" title="Remover">X</button></div>`;
      selEl.appendChild(li);
    });
    enableDragAndDrop(selEl);
    $('priorityMsg').textContent = '';
  } catch (e) {
    allEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
    selEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
    $('priorityMsg').textContent = '';
    logUi('ERROR', 'priority modal falhou');
  }
}

function onTableCheckboxChange(chk) {
  const raw = chk.getAttribute('data-name') || '';
  const name = decodeURIComponent(raw);
  if (chk.checked) {
    const selEl = $('priorityListModal');
    const li = document.createElement('li');
    li.draggable = true;
    li.dataset.table = name;
    li.innerHTML = `<div style="flex:1">${escapeHtml(
      name
    )}</div><div style="display:flex;gap:6px"><button class="btn ghost" onclick="prioMoveUp(this)" title="Mover para cima">Up</button><button class="btn ghost" onclick="prioMoveDown(this)" title="Mover para baixo">Down</button><button class="btn ghost" onclick="prioRemove(this)" title="Remover">X</button></div>`;
    selEl.appendChild(li);
    enableDragAndDrop(selEl);
  } else {
    const selEl = $('priorityListModal');
    const it = Array.from(selEl.children).find(li => li.dataset.table === name);
    if (it) selEl.removeChild(it);
  }
}

function enableDragAndDrop(listEl) {
  let dragSrc = null;
  Array.from(listEl.children).forEach(li => {
    li.addEventListener('dragstart', e => {
      dragSrc = li;
      li.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    li.addEventListener('dragend', () => {
      li.classList.remove('dragging');
    });
    li.addEventListener('dragover', e => {
      e.preventDefault();
      const target = e.currentTarget;
      if (target === dragSrc) return;
      const rect = target.getBoundingClientRect();
      const next = e.clientY - rect.top > rect.height / 2;
      if (next) target.parentNode.insertBefore(dragSrc, target.nextSibling);
      else target.parentNode.insertBefore(dragSrc, target);
    });
    li.addEventListener('drop', e => {
      e.preventDefault();
    });
  });
}

function prioMoveUp(btn) {
  const li = btn.closest('li');
  const prev = li.previousElementSibling;
  if (prev) li.parentNode.insertBefore(li, prev);
}

function prioMoveDown(btn) {
  const li = btn.closest('li');
  const next = li.nextElementSibling;
  if (next) li.parentNode.insertBefore(li, next.nextElementSibling);
}

function prioRemove(btn) {
  const li = btn.closest('li');
  const name = li.dataset.table;
  li.parentNode.removeChild(li);
  const leftChk = Array.from(
    document.querySelectorAll('#allTablesList input[type=checkbox]')
  ).find(c => c.getAttribute('data-name') === encodeURIComponent(name));
  if (leftChk) leftChk.checked = false;
}

async function savePriority() {
  const listEl = $('priorityListModal');
  const tables = Array.from(listEl.querySelectorAll('li')).map(li => li.dataset.table);
  const res = await fetch('/admin/set_priority', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ tables })
  });
  const j = await res.json();
  const msg = $('priorityMsg');
  if (j && j.ok) {
    if (msg) msg.textContent = 'Prioridades salvas: ' + tables.length;
  } else if (msg) {
    msg.textContent = 'Erro ao salvar prioridades';
  }
  await refreshUiState();
}

async function doSearch(opts) {
  const q = $('q').value.trim();
  if (!q) {
    alert('Digite um termo para pesquisar');
    return;
  }
  if (!hasDbSelected()) {
    setNoDbState({ showHint: true });
    logUi('WARN', 'acao exige DB');
    alert('Selecione um DB primeiro');
    return;
  }
  const btn = $('searchBtn');
  if (btn.disabled) return;
  const exportBtn = $('exportAllBtn');
  if (exportBtn) exportBtn.disabled = true;
  try {
    if (lastStatus && lastStatus.conversion && lastStatus.conversion.running) {
      alert('Aguarde a conversao do banco terminar antes de pesquisar.');
      return;
    }
    if (lastStatus && lastStatus.indexing) {
      alert('Aguarde a indexacao (_fulltext) terminar antes de pesquisar.');
      return;
    }
    if (
      lastStatus &&
      lastStatus.db &&
      lastStatus.db.toLowerCase().endsWith('.duckdb') &&
      !lastStatus.fulltext_count
    ) {
      alert(
        'Este banco DuckDB ainda nao possui indice _fulltext. Inicie a indexacao antes de pesquisar.'
      );
      return;
    }
  } catch (e) {
    // ignore
  }
  const per_table = parseInt($('per_table').value, 10) || 10;
  const candidate_limit = parseInt($('candidate_limit').value, 10) || 1000;
  const total_limit = parseInt($('total_limit').value, 10) || 500;
  const token_mode = $('token_mode').value;
  const min_score = parseInt($('min_score').value, 10) || null;
  lastQuery = q;
  $('searchMeta').textContent = `Buscando: "${q}" ...`;
  const tablesSel = $('tablesFilter');
  let tablesParam = '';
  let selectedTables = [];
  if (tablesSel) {
    selectedTables = Array.from(tablesSel.selectedOptions)
      .map(o => o.value)
      .filter(Boolean);
    if (selectedTables.length) {
      tablesParam = `&tables=${encodeURIComponent(selectedTables.join(','))}`;
    }
  }
  const url =
    `/api/search?q=${encodeURIComponent(q)}&per_table=${per_table}&candidate_limit=${candidate_limit}&total_limit=${total_limit}&token_mode=${token_mode}` +
    (min_score ? `&min_score=${min_score}` : '') +
    tablesParam;
  btn.disabled = true;
  btn.textContent = 'Buscando...';
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) {
      $('searchMeta').textContent = 'Erro: ' + data.error;
      logUi('ERROR', 'search ' + data.error);
      return;
    }
    lastResults = data;
    if (!opts || !opts.skipHistory) {
      const state = buildSearchState();
      try {
        history.pushState(state, '', window.location.pathname);
      } catch (e) {
        // ignore
      }
    }
    $('searchMeta').textContent = `Resultados: ${data.returned_count} (candidatos: ${
      data.candidate_count
    })`;
    if (exportBtn) exportBtn.disabled = !(data && data.returned_count);
    renderResults(q, data.results || {}, per_table);
  } catch (e) {
    $('searchMeta').textContent = 'Erro na busca';
    logUi('ERROR', 'search falhou');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Pesquisar';
  }
}

function tableTagId(name) {
  return 'tag-' + encodeURIComponent(name);
}

function escapeHtml(s) {
  return (s + '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
    const parts = tokens.map(t => escapeRegExp(t)).filter(Boolean);
    if (!parts.length) return text;
    const re = new RegExp('(' + parts.join('|') + ')', 'ig');
    return text.replace(re, m => `<mark>${m}</mark>`);
  } catch (e) {
    return text;
  }
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
    const pri = priorityTables.filter(t => keys.includes(t));
    const others = keys.filter(k => !set.has(k));
    keys = pri.concat(others);
  }
  if (!keys.length) {
    root.innerHTML = '<div class="card small">Nenhum resultado encontrado.</div>';
    return;
  }
  if (exportBtn) exportBtn.disabled = false;
  keys.forEach(tbl => {
    const block = document.createElement('div');
    block.className = 'card';
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    const tagId = tableTagId(tbl);
    header.innerHTML = `
      <div>
        <span id="${tagId}" style="display:none;background:#eef7ff;color:var(--primary);padding:4px 8px;border-radius:999px;margin-right:8px;font-size:12px">PRIORITARIO</span>
        <strong>${escapeHtml(tbl)}</strong> <span class="muted">(${results[tbl].length})</span>
      </div>
      <div>
        <button class="btn ghost" onclick="openTable(event,'${encodeURIComponent(
          tbl
        )}')">Abrir</button>
        <button class="btn ghost" onclick="exportTableCsv('${encodeURIComponent(
          tbl
        )}')">Export CSV</button>
      </div>`;
    block.appendChild(header);
    const rows = results[tbl];
    const colsSet = new Set();
    const rowObjs = [];
    rows.forEach(it => {
      const r = it.row || (it.row_json ? JSON.parse(it.row_json || '{}') : {});
      rowObjs.push({ score: it.score, row: r });
      if (r && typeof r === 'object') Object.keys(r).forEach(c => colsSet.add(c));
    });
    const cols = Array.from(colsSet).slice(0, 200);
    if (!cols.length) {
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(rowObjs, null, 2);
      block.appendChild(pre);
    } else {
      const table = document.createElement('table');
      table.className = 'results';
      const thead = document.createElement('thead');
      thead.innerHTML =
        '<tr><th style="width:90px">pontuacao</th>' +
        cols.map(c => `<th>${escapeHtml(c)}</th>`).join('') +
        '</tr>';
      table.appendChild(thead);
      const tbody = document.createElement('tbody');
      rowObjs.slice(0, per_table).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML =
          `<td>${r.score == null ? '' : r.score}</td>` +
          cols
            .map(c => {
              let v = r.row && Object.prototype.hasOwnProperty.call(r.row, c)
                ? r.row[c]
                : '';
              if (v === null || v === undefined) v = '';
              if (typeof v === 'object') {
                return `<td><pre style="font-size:12px">${escapeHtml(
                  JSON.stringify(v, null, 2)
                )}</pre></td>`;
              }
              return `<td>${highlightText(escapeHtml(String(v)), tokens)}</td>`;
            })
            .join('');
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      block.appendChild(table);
    }
    root.appendChild(block);
  });
  try {
    (priorityTables || []).forEach(p => {
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
    )} <span class="muted">linhas: ${data.total}</span></h3></div>`;
    if (!data.rows || !data.rows.length) {
      const empty = document.createElement('div');
      empty.className = 'card small';
      empty.textContent = 'Sem linhas para mostrar.';
      area.appendChild(empty);
      return;
    }
    const hdr = document.createElement('div');
    hdr.className = 'card';
    const tableEl = document.createElement('table');
    tableEl.className = 'results';
    const thead = document.createElement('thead');
    thead.innerHTML =
      '<tr>' + (data.columns || []).map(c => `<th>${escapeHtml(c)}</th>`).join('') + '</tr>';
    tableEl.appendChild(thead);
    const tbody = document.createElement('tbody');
    data.rows.forEach(row => {
      const tr = document.createElement('tr');
      row.forEach(cell => {
        tr.innerHTML += `<td>${escapeHtml(cell === null ? '' : String(cell))}</td>`;
      });
      tbody.appendChild(tr);
    });
    tableEl.appendChild(tbody);
    hdr.appendChild(tableEl);
    const pager = document.createElement('div');
    pager.className = 'controls-footer';
    pager.innerHTML = '<button class="btn ghost" onclick="backToResults()">Voltar</button>';
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
    const esc = v => '"' + String(v).replace(/"/g, '""') + '"';
    const header = cols.map(esc).join(',') + '\n';
    const body = rows.map(r => r.map(esc).join(',')).join('\n');
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
  const results = lastResults.results || {};
  const colsSet = new Set(['table', 'score']);
  const rowsOut = [];
  Object.keys(results).forEach(tbl => {
    (results[tbl] || []).forEach(item => {
      let rowObj = item && item.row ? item.row : null;
      if (!rowObj && item && item.row_json) {
        try {
          rowObj = JSON.parse(item.row_json || '{}');
        } catch (e) {
          rowObj = {};
        }
      }
      if (!rowObj || typeof rowObj !== 'object') rowObj = {};
      Object.keys(rowObj).forEach(k => colsSet.add(k));
      rowsOut.push({ table: tbl, score: item && item.score != null ? item.score : '', row: rowObj });
    });
  });
  const cols = Array.from(colsSet);
  const esc = v => '"' + String(v).replace(/"/g, '""') + '"';
  const lines = [cols.map(esc).join(',')];
  rowsOut.forEach(r => {
    const line = cols.map(c => {
      if (c === 'table') return r.table;
      if (c === 'score') return r.score;
      const v = r.row && Object.prototype.hasOwnProperty.call(r.row, c) ? r.row[c] : '';
      return v && typeof v === 'object' ? JSON.stringify(v) : v;
    });
    lines.push(line.map(esc).join(','));
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
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
    $('searchMeta').textContent = `Resultados: ${lastResults.returned_count || 0} (candidatos: ${
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
