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

window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;
window.escapeRegExp = escapeRegExp;
window.highlightText = highlightText;
window.renderResults = renderResults;
window.openTable = openTable;
window.exportTableCsv = exportTableCsv;
window.exportResultsCsv = exportResultsCsv;
window.backToResults = backToResults;
