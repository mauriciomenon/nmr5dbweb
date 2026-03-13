// app.js
// Core da aba "Busca" (painel DuckDB):
// - estado compartilhado
// - utilitarios base
// - renderizacao de listas/abas/status
// - refresh de tabelas e status
(function () {
  if (typeof window.normalizeFlow === 'function') {
    return;
  }
  window.normalizeFlow = function (flow) {
    return flow === 'access' ? 'access' : 'duckdb';
  };
  window.isAccessFile = function (name) {
    var lower = (name || '').toLowerCase();
    return lower.endsWith('.mdb') || lower.endsWith('.accdb');
  };
  window.isDuckdbFile = function (name) {
    var lower = (name || '').toLowerCase();
    return (
      lower.endsWith('.duckdb') ||
      lower.endsWith('.db') ||
      lower.endsWith('.sqlite') ||
      lower.endsWith('.sqlite3')
    );
  };
  window.getFlowFromName = function (name) {
    if (window.isAccessFile(name)) return 'access';
    if (window.isDuckdbFile(name)) return 'duckdb';
    return '';
  };
  window.isSupportedFileName = function (name) {
    return window.isAccessFile(name) || window.isDuckdbFile(name);
  };
  window.getFileStem = function (name) {
    var lower = (name || '').toLowerCase();
    return lower
      .replace(/\.(mdb|accdb)$/, '')
      .replace(/\.(duckdb|db|sqlite|sqlite3)$/, '');
  };
  window.getDateKeyFromFileName = function (name) {
    if (!name) return null;
    var m = String(name).match(/(\d{4})[-_]?(\d{2})[-_]?(\d{2})/);
    if (!m) return null;
    var y = Number(m[1]);
    var mo = Number(m[2]);
    var d = Number(m[3]);
    if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d))
      return null;
    var t = Date.UTC(y, mo - 1, d);
    return Number.isFinite(t) ? t : null;
  };
  window.buildAccessStemSet = function (list) {
    var stems = new Set();
    (list || []).forEach(function (f) {
      if (!f || !f.name) return;
      if (window.isAccessFile(f.name)) stems.add(window.getFileStem(f.name));
    });
    return stems;
  };
  window.isConvertedDuckdb = function (name, accessStems) {
    if (!window.isDuckdbFile(name)) return false;
    if (!accessStems || !accessStems.has) return false;
    return accessStems.has(window.getFileStem(name));
  };
  window.isFileAllowedForFlow = function (fileName, flow) {
    if (window.normalizeFlow(flow) === 'access') {
      return window.isAccessFile(fileName);
    }
    return window.isDuckdbFile(fileName);
  };
  window.formatBytes = function (size) {
    var num = Number(size);
    if (!Number.isFinite(num) || num < 0) return '0 B';
    if (num < 1024) return num + ' B';
    var kb = num / 1024;
    if (kb < 1024) return kb.toFixed(1) + ' KB';
    var mb = kb / 1024;
    if (mb < 1024) return mb.toFixed(1) + ' MB';
    var gb = mb / 1024;
    return gb.toFixed(1) + ' GB';
  };
  window.formatDate = function (isoText) {
    if (!isoText) return '';
    var d = new Date(isoText);
    if (!Number.isFinite(d.getTime())) return '';
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var hh = String(d.getHours()).padStart(2, '0');
    var min = String(d.getMinutes()).padStart(2, '0');
    return yyyy + '-' + mm + '-' + dd + ' ' + hh + ':' + min;
  };
})();
var normalizeFlow = window.normalizeFlow;
var isAccessFile = window.isAccessFile;
var isDuckdbFile = window.isDuckdbFile;
var getFlowFromName = window.getFlowFromName;
var isSupportedFileName = window.isSupportedFileName;
var buildAccessStemSet = window.buildAccessStemSet;
var isConvertedDuckdb = window.isConvertedDuckdb;
var isFileAllowedForFlow = window.isFileAllowedForFlow;
var formatBytes = window.formatBytes;
var formatDate = window.formatDate;
var getDateKeyFromFileName = window.getDateKeyFromFileName;
const $ = (id) => document.getElementById(id);
function shortName(pathValue) {
  if (!pathValue) return '';
  const parts = String(pathValue).split(/[\\/]+/);
  return parts[parts.length - 1] || String(pathValue);
}
let lastResults = null;
let lastQuery = '';
let currentDb = null;
let currentFlow = 'duckdb';
let manualFlowOverride = '';
let lastStatus = null; // status mais recente vindo de /admin/status
let priorityTables = []; // lista atual de tabelas prioritarias
let lastUploads = [];
let accessStems = new Set();
let lastConversionRunning = false;
let lastIndexingRunning = false;
let conversionCompletionTimer = null;
let indexCompletionTimer = null;
let activeModalId = null;
let statusPollTimer = null;
let lastTablesByDb = {};
let filesPanelOpen = false;
let uiLogItems = [];
let lastAlerts = { critical: [], warn: [], info: [] };
let lastServerLogs = [];
let lastServerAlerts = { critical: [], warn: [], info: [] };
const STATUS_POLL_ACTIVE_MS = 3000;
const STATUS_POLL_MODAL_MS = 15000;
const STATUS_POLL_IDLE_MS = 45000;
const STATUS_POLL_NO_DB_MS = 60000;
const LOG_LIMIT = 6;
let uiLogEntries = [];
let serverOnline = true;

function logUi(level, msg) {
  const now = new Date();
  const ts =
    String(now.getHours()).padStart(2, '0') +
    ':' +
    String(now.getMinutes()).padStart(2, '0') +
    ':' +
    String(now.getSeconds()).padStart(2, '0');
  const line = ts + ' ' + level + ' ' + msg;
  uiLogEntries.push(line);
  uiLogItems.push({ ts: ts, level: level, msg: msg });
  if (uiLogEntries.length > LOG_LIMIT) uiLogEntries.shift();
  if (uiLogItems.length > 80) uiLogItems.shift();
  const el = $('uiLog');
  if (el) el.textContent = uiLogEntries.join('\n');
  if (level === 'ERROR') console.error(line);
  else if (level === 'WARN') console.warn(line);
  else console.log(line);
  if (level === 'ERROR' || level === 'WARN') {
    try {
      fetch('/client/log', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ level: level, msg: msg }),
      });
    } catch (e) {
      /* ignored */
    }
  }
}

function setServerOnline(isOnline, reason) {
  serverOnline = isOnline;
  if (!isOnline) {
    if ($('indexStatus')) $('indexStatus').textContent = 'Offline';
    if ($('modeBadge')) $('modeBadge').textContent = 'Modo: -';
    setFlowHint('Servidor offline. Inicie python main.py.', true);
    if (reason) logUi('ERROR', 'offline ' + reason);
  }
}

function setDbTypeClass(flow) {
  document.body.classList.remove('db-duckdb', 'db-access', 'db-none');
  if (flow === 'duckdb') document.body.classList.add('db-duckdb');
  else if (flow === 'access') document.body.classList.add('db-access');
  else document.body.classList.add('db-none');
}

function updateFlowControls() {
  const fi = $('fileInput');
  if (!fi) return;
  if (currentFlow === 'access') {
    fi.accept = '.mdb,.accdb';
    fi.title = 'Aceita .mdb, .accdb';
  } else {
    fi.accept = '.duckdb,.db,.sqlite,.sqlite3';
    fi.title = 'Aceita .duckdb, .db, .sqlite, .sqlite3';
  }
}

function setIndexControlsEnabled(enabled) {
  const ids = [
    'startIndex',
    'dropCheckbox',
    'chunk',
    'batch',
    'resetIndexDefaults',
  ];
  ids.forEach((id) => {
    const el = $(id);
    if (el) el.disabled = !enabled;
  });
}

window.addEventListener('error', (e) => {
  const msg = e && e.message ? e.message : 'js error';
  logUi('ERROR', 'js ' + msg);
});
window.addEventListener('unhandledrejection', (e) => {
  const msg = e && e.reason ? e.reason : 'promise error';
  logUi('ERROR', 'promise ' + msg);
});

function hasDbSelected() {
  return currentDb && currentDb !== 'none';
}

function setFlowHint(text, show) {
  const el = $('flowHint');
  if (!el) return;
  if (typeof text === 'string') el.textContent = text;
  el.style.display = show ? 'block' : 'none';
}

function setFlowBanner(text, level) {
  const el = $('flowBanner');
  if (!el) return;
  if (!text) {
    el.textContent = '';
    el.style.display = 'none';
    el.classList.remove('info', 'warn', 'error');
    return;
  }
  el.textContent = text;
  el.style.display = 'block';
  el.classList.remove('info', 'warn', 'error');
  if (level) el.classList.add(level);
}

function setModalBanner(elId, text, level) {
  const el = $(elId);
  if (!el) return;
  if (!text) {
    el.textContent = '';
    el.style.display = 'none';
    el.classList.remove('info', 'warn', 'error');
    return;
  }
  el.textContent = text;
  el.style.display = 'block';
  el.classList.remove('info', 'warn', 'error');
  if (level) el.classList.add(level);
}

function scheduleModalClose(nextModalId) {
  if (conversionCompletionTimer) {
    clearTimeout(conversionCompletionTimer);
    conversionCompletionTimer = null;
  }
  conversionCompletionTimer = setTimeout(() => {
    closeModal();
    if (nextModalId) {
      openModalById(nextModalId);
      if (nextModalId === 'searchModal') {
        const q = $('q');
        if (q && !q.disabled) {
          q.focus();
          q.select();
        }
      }
    }
  }, 1600);
}

function scheduleIndexModalClose(nextModalId) {
  if (indexCompletionTimer) {
    clearTimeout(indexCompletionTimer);
    indexCompletionTimer = null;
  }
  indexCompletionTimer = setTimeout(() => {
    closeModal();
    if (nextModalId) {
      openModalById(nextModalId);
      if (nextModalId === 'searchModal') {
        const q = $('q');
        if (q && !q.disabled) {
          q.focus();
          q.select();
        }
      }
    }
  }, 1600);
}

function setSearchControlsEnabled(enabled) {
  const ids = [
    'q',
    'searchBtn',
    'per_table',
    'candidate_limit',
    'total_limit',
    'token_mode',
    'min_score',
    'tablesFilter',
    'clearTablesFilter',
  ];
  ids.forEach((id) => {
    const el = $(id);
    if (el) el.disabled = !enabled;
  });
  const advanced = $('advancedPanel');
  if (advanced) {
    if (enabled) advanced.classList.remove('controls-disabled');
    else advanced.classList.add('controls-disabled');
  }
}

function setStatusTile(valueId, metaId, valueText, metaText) {
  const valEl = $(valueId);
  if (valEl) valEl.textContent = valueText || '-';
  const metaEl = $(metaId);
  if (metaEl) metaEl.textContent = metaText || '';
}

function setStepState(stepId, state) {
  const el = $(stepId);
  if (!el) return;
  el.classList.remove('done', 'active', 'warn');
  if (state) el.classList.add(state);
}

function updateConversionModeText(status) {
  const el = $('conversionModeText');
  if (!el) return;
  if (!status) {
    el.textContent = '';
    return;
  }
  const precheck = status.access_precheck || null;
  const backendPreferred = status.conversion_backend_preferred || '';
  const backendLast = status.conversion_backend_last || '';
  const lastText = backendLast
    ? `Ultima conversao: ${backendLast}. `
    : '';
  if (precheck && precheck.ready === false) {
    const reason = precheck.reason || 'ambiente incompleto';
    el.textContent =
      lastText + 'Conversao Access indisponivel neste ambiente: ' + reason + '.';
    return;
  }
  if (backendPreferred === 'odbc') {
    el.textContent =
      lastText + 'Modo atual: ODBC preferencial com fallback.';
    return;
  }
  if (backendPreferred === 'access_parser') {
    el.textContent =
      lastText + 'Modo atual: access-parser (sem dependencia de ODBC).';
    return;
  }
  if (backendPreferred === 'mdbtools') {
    el.textContent =
      lastText + 'Modo atual: mdbtools (suporte principal para .mdb).';
    return;
  }
  const mode = status.conversion_mode || 'odbc_preferred';
  const odbcEnabled = status.odbc_enabled !== false;
  if (!odbcEnabled) {
    el.textContent = lastText + 'Modo atual: ODBC indisponivel.';
    return;
  }
  if (mode === 'pure_only') {
    el.textContent = lastText + 'Modo atual: conversao sem ODBC.';
    return;
  }
  el.textContent = lastText + 'Modo atual: ODBC preferencial com fallback.';
}

function updatePrimaryHint(status, showHint) {
  const shouldShow = showHint !== false;
  if (!status) {
    setFlowHint('Selecione um DB para começar.', shouldShow);
    return;
  }
  const db = status.db || '';
  const dbType = getFlowFromName(db);
  const converted =
    dbType === 'duckdb' && isConvertedDuckdb(shortName(db), accessStems);
  if (!db) {
    setFlowHint(
      'Selecione um DB em Configurar/Upload para liberar busca e indexacao.',
      shouldShow
    );
    return;
  }
  if (status.conversion && status.conversion.running) {
    setFlowHint(
      'Conversao em andamento. Aguarde o termino para indexar.',
      shouldShow
    );
    return;
  }
  if (status.indexing) {
    setFlowHint(
      'Indexacao em andamento. Busca liberada ao terminar.',
      shouldShow
    );
    return;
  }
  if (dbType === 'access' && !converted) {
    setFlowHint(
      'Access selecionado. Converta para DuckDB antes de buscar.',
      shouldShow
    );
    return;
  }
  if (status.db_engine === 'sqlite') {
    setFlowHint(
      'SQLite selecionado. Busca textual ativa sem _fulltext.',
      shouldShow
    );
    return;
  }
  if (dbType === 'duckdb' && !status.fulltext_count) {
    setFlowHint(
      'DuckDB selecionado. Crie o indice _fulltext para buscar.',
      shouldShow
    );
    return;
  }
  setFlowHint(
    'Pronto para buscar. Use filtros, prioridade e selecao de tabelas.',
    shouldShow
  );
}

function updateFilesHelpText(status) {
  const el = $('filesHelpText');
  if (!el) return;
  if (!status || !status.db) {
    el.textContent =
      'Gerencie uploads aqui. A selecao de tabelas fica na barra lateral.';
    return;
  }
  const dbType = getFlowFromName(status.db);
  if (dbType === 'access') {
    el.textContent =
      'Access: uploads (.mdb/.accdb) aparecem aqui. A conversao cria um .duckdb com o mesmo nome.';
    return;
  }
  el.textContent =
    'DuckDB: esta lista e apenas para gestao de arquivos (upload/baixar/excluir).';
}

function shortenText(text, maxLen) {
  if (!text) return '';
  const t = String(text);
  if (t.length <= maxLen) return t;
  return t.slice(0, Math.max(0, maxLen - 3)) + '...';
}

function buildStatusAlerts(status) {
  const critical = [];
  const warn = [];
  const info = [];
  if (!status) {
    info.push('Sem status do servidor.');
    return { critical: critical, warn: warn, info: info };
  }
  if (status.indexer_available === false) {
    critical.push(
      'Indexador indisponivel: ' + (status.indexer_error || 'erro')
    );
  }
  if (status.conversion && status.conversion.ok === false) {
    critical.push('Conversao: ' + (status.conversion.msg || 'falhou'));
  }
  if (status.conversion && status.conversion.running) {
    info.push('Conversao em andamento.');
  }
  const db = status.db || '';
  const dbType = getFlowFromName(db);
  const converted =
    dbType === 'duckdb' && isConvertedDuckdb(shortName(db), accessStems);
  if (
    dbType === 'access' &&
    !converted &&
    !(status.conversion && status.conversion.running)
  ) {
    warn.push('Access selecionado: aguarde conversao ou troque para DuckDB.');
  }
  if (status.db_engine === 'sqlite') {
    info.push('SQLite selecionado: busca textual ativa sem _fulltext.');
  }
  if (dbType === 'duckdb' && !status.fulltext_count) {
    warn.push('Indice _fulltext ausente: a busca esta bloqueada.');
  }
  return { critical: critical, warn: warn, info: info };
}

function classifyServerLog(entry) {
  const level = String((entry && entry.level) || '').toLowerCase();
  const msg = String((entry && entry.message) || '');
  if (level === 'error' || level === 'critical') return 'critical';
  if (level === 'warn' || level === 'warning') return 'warn';
  if (/error|exception|traceback|failed/i.test(msg)) return 'critical';
  if (/warn|missing|timeout/i.test(msg)) return 'warn';
  return 'info';
}

function buildServerAlertsFromLogs(logs) {
  const critical = [];
  const warn = [];
  const info = [];
  (logs || []).forEach((entry) => {
    const msg = String((entry && entry.message) || '').trim();
    if (!msg) return;
    const bucket = classifyServerLog(entry);
    if (bucket === 'critical') critical.push(msg);
    else if (bucket === 'warn') warn.push(msg);
    else info.push(msg);
  });
  return { critical: critical, warn: warn, info: info };
}

function mergeAlerts(base, extra) {
  const seen = new Set();
  const mergeList = (a, b) => {
    const out = [];
    (a || []).forEach((item) => {
      const key = String(item);
      if (!seen.has(key)) {
        seen.add(key);
        out.push(item);
      }
    });
    (b || []).forEach((item) => {
      const key = String(item);
      if (!seen.has(key)) {
        seen.add(key);
        out.push(item);
      }
    });
    return out;
  };
  return {
    critical: mergeList(base.critical, extra.critical),
    warn: mergeList(base.warn, extra.warn),
    info: mergeList(base.info, extra.info),
  };
}

async function fetchServerLogs() {
  try {
    const data = await apiJSON('/admin/logs');
    if (data && data.ok && Array.isArray(data.logs)) {
      lastServerLogs = data.logs;
      lastServerAlerts = buildServerAlertsFromLogs(lastServerLogs);
      updateStatusAlerts(lastStatus);
    }
  } catch (e) {
    logUi('WARN', 'logs falhou');
  }
}

function updateStatusAlerts(status) {
  lastAlerts = buildStatusAlerts(status);
  const merged = mergeAlerts(lastAlerts, lastServerAlerts);
  const badge = $('statusAlerts');
  if (!badge) return;
  if (merged.critical.length) {
    if (merged.critical.length === 1) {
      badge.textContent = 'Alertas: ' + shortenText(merged.critical[0], 42);
    } else {
      badge.textContent = 'Alertas: ' + merged.critical.length + ' criticos';
    }
  } else if (merged.warn.length) {
    if (merged.warn.length === 1) {
      badge.textContent = 'Alertas: ' + shortenText(merged.warn[0], 42);
    } else {
      badge.textContent = 'Alertas: ' + merged.warn.length + ' avisos';
    }
  } else if (merged.info.length) {
    badge.textContent = 'Alertas: info';
  } else {
    badge.textContent = 'Alertas: ok';
  }
}

function setStatusList(el, items, emptyText) {
  if (!el) return;
  if (!items || !items.length) {
    el.innerHTML = '<li class="muted">' + (emptyText || 'Nenhum') + '</li>';
    return;
  }
  el.innerHTML = items
    .map((item) => '<li>' + escapeHtml(String(item)) + '</li>')
    .join('');
}

function renderStatusModal() {
  const merged = mergeAlerts(lastAlerts, lastServerAlerts);
  setStatusList(
    $('statusCriticalList'),
    merged.critical,
    'Nenhum alerta critico.'
  );
  setStatusList($('statusWarnList'), merged.warn, 'Nenhum aviso.');
  setStatusList(
    $('statusInfoList'),
    merged.info,
    'Sem informacoes adicionais.'
  );
  const logEl = $('statusLogList');
  if (logEl) {
    const serverLines = (lastServerLogs || [])
      .map((entry) => {
        const ts = entry && entry.ts ? entry.ts : '';
        const level =
          entry && entry.level ? String(entry.level).toUpperCase() : 'INFO';
        const msg = entry && entry.message ? entry.message : '';
        return `${ts} ${level} ${msg}`.trim();
      })
      .filter(Boolean);
    const clientLines = uiLogEntries.slice();
    if (serverLines.length || clientLines.length) {
      const parts = [];
      if (serverLines.length) {
        parts.push('[server]\n' + serverLines.join('\n'));
      }
      if (clientLines.length) {
        parts.push('[client]\n' + clientLines.join('\n'));
      }
      logEl.textContent = parts.join('\n\n');
    } else {
      logEl.textContent = 'Nenhum log recente.';
    }
  }
}

function resetAdvancedDefaults() {
  if ($('per_table')) $('per_table').value = 10;
  if ($('candidate_limit')) $('candidate_limit').value = 1000;
  if ($('total_limit')) $('total_limit').value = 500;
  if ($('token_mode')) $('token_mode').value = 'any';
  if ($('min_score')) $('min_score').value = 70;
  if ($('minScoreVal')) $('minScoreVal').textContent = '70';
  const sel = $('tablesFilter');
  if (sel) Array.from(sel.options).forEach((o) => (o.selected = false));
}

function buildSearchState() {
  const tablesSel = $('tablesFilter');
  const selectedTables = tablesSel
    ? Array.from(tablesSel.selectedOptions)
        .map((o) => o.value)
        .filter(Boolean)
    : [];
  return {
    q: $('q') ? $('q').value.trim() : '',
    per_table: parseInt($('per_table').value) || 10,
    candidate_limit: parseInt($('candidate_limit').value) || 1000,
    total_limit: parseInt($('total_limit').value) || 500,
    token_mode: $('token_mode') ? $('token_mode').value : 'any',
    min_score: parseInt($('min_score').value) || 70,
    tables: selectedTables,
  };
}

function applySearchState(state) {
  if (!state) return;
  if ($('q')) $('q').value = state.q || '';
  if ($('per_table')) $('per_table').value = state.per_table || 10;
  if ($('candidate_limit'))
    $('candidate_limit').value = state.candidate_limit || 1000;
  if ($('total_limit')) $('total_limit').value = state.total_limit || 500;
  if ($('token_mode')) $('token_mode').value = state.token_mode || 'any';
  if ($('min_score')) $('min_score').value = state.min_score || 70;
  if ($('minScoreVal'))
    $('minScoreVal').textContent = String(state.min_score || 70);
  const sel = $('tablesFilter');
  if (sel) {
    const set = new Set(state.tables || []);
    Array.from(sel.options).forEach((o) => (o.selected = set.has(o.value)));
  }
}

function getStatusPollDelay() {
  const active =
    lastStatus &&
    ((lastStatus.conversion && lastStatus.conversion.running) ||
      lastStatus.indexing);
  if (active) return STATUS_POLL_ACTIVE_MS;
  if (!hasDbSelected()) return STATUS_POLL_NO_DB_MS;
  const modalOpen = document.body.classList.contains('modal-open');
  if (modalOpen) return STATUS_POLL_MODAL_MS;
  return STATUS_POLL_IDLE_MS;
}

function scheduleStatusPoll() {
  if (statusPollTimer) clearTimeout(statusPollTimer);
  statusPollTimer = setTimeout(async () => {
    await refreshStatus();
    scheduleStatusPoll();
  }, getStatusPollDelay());
}

function forceModalStyles(modal, overlay) {
  if (overlay) {
    overlay.style.display = 'block';
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.background = 'rgba(0,0,0,0.35)';
    overlay.style.zIndex = '5000';
    overlay.style.pointerEvents = 'auto';
    overlay.style.visibility = 'visible';
  }
  if (modal) {
    const card =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--card')
        .trim() || '#fff';
    modal.setAttribute('aria-hidden', 'false');
    modal.style.display = 'block';
    modal.style.visibility = 'visible';
    modal.style.position = 'fixed';
    modal.style.left = '50%';
    modal.style.top = '50%';
    modal.style.transform = 'translate(-50%,-50%)';
    modal.style.width = '960px';
    modal.style.maxWidth = '95%';
    modal.style.maxHeight = '90vh';
    modal.style.overflow = 'auto';
    modal.style.background = card;
    modal.style.padding = '16px';
    modal.style.borderRadius = '8px';
    modal.style.boxShadow = '0 8px 20px rgba(0,0,0,0.2)';
    modal.style.zIndex = '6000';
  }
}

function closeAllModals() {
  [
    'configModal',
    'priorityModal',
    'indexModal',
    'statusModal',
    'searchModal',
  ].forEach((id) => resetModalStyles($(id)));
  activeModalId = null;
}

function openModalById(modalId) {
  const modal = $(modalId);
  const overlay = $('overlay');
  if (!modal) return;
  closeAllModals();
  activeModalId = modalId;
  document.body.classList.add('modal-open');
  forceModalStyles(modal, overlay);
  if (overlay) {
    overlay.onclick = () => closeModal();
  }
  const display = getComputedStyle(modal).display;
  logUi('INFO', 'modal open id=' + modalId + ' display=' + display);
  try {
    fetch('/client/log', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        level: 'info',
        msg: 'modal open id=' + modalId + ' display=' + display,
      }),
    });
  } catch (e) {
    /* ignored */
  }
  setTimeout(() => {
    if (activeModalId !== modalId) return;
    const m = $(modalId);
    if (!m) {
      logUi('ERROR', 'modal missing');
      return;
    }
    const d = getComputedStyle(m).display;
    if (d === 'none') {
      logUi('ERROR', 'modal not visible');
      forceModalStyles(m, $('overlay'));
    }
    const r = m.getBoundingClientRect();
    logUi(
      'INFO',
      'modal rect ' +
        Math.round(r.width) +
        'x' +
        Math.round(r.height) +
        ' top ' +
        Math.round(r.top) +
        ' left ' +
        Math.round(r.left)
    );
    if (r.width === 0 || r.height === 0) {
      logUi('ERROR', 'modal size zero');
      forceModalStyles(m, $('overlay'));
    }
    try {
      fetch('/client/log', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          level: 'info',
          msg:
            'modal rect ' +
            Math.round(r.width) +
            'x' +
            Math.round(r.height) +
            ' top ' +
            Math.round(r.top) +
            ' left ' +
            Math.round(r.left),
        }),
      });
    } catch (e) {
      /* ignored */
    }
  }, 50);
}

function resetModalStyles(modal) {
  if (!modal) return;
  modal.setAttribute('aria-hidden', 'true');
  modal.style.display = 'none';
  modal.style.visibility = '';
  modal.style.zIndex = '';
  modal.style.position = '';
  modal.style.left = '';
  modal.style.top = '';
  modal.style.transform = '';
  modal.style.width = '';
  modal.style.maxWidth = '';
  modal.style.maxHeight = '';
  modal.style.overflow = '';
  modal.style.background = '';
  modal.style.padding = '';
  modal.style.borderRadius = '';
  modal.style.boxShadow = '';
}

function closeModal() {
  const modalId = activeModalId;
  const overlay = $('overlay');
  document.body.classList.remove('modal-open');
  closeAllModals();
  if (overlay) {
    overlay.style.display = 'none';
    overlay.style.zIndex = '';
    overlay.style.position = '';
    overlay.style.inset = '';
    overlay.style.background = '';
    overlay.style.pointerEvents = '';
    overlay.style.visibility = '';
  }
  if (modalId === 'configModal') {
    manualFlowOverride = '';
  }
  logUi('INFO', 'modal close');
  try {
    fetch('/client/log', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ level: 'info', msg: 'modal close' }),
    });
  } catch (e) {
    /* ignored */
  }
  activeModalId = null;
}

function forceCloseModals() {
  const overlay = $('overlay');
  document.body.classList.remove('modal-open');
  closeAllModals();
  if (overlay) {
    overlay.style.display = 'none';
    overlay.style.zIndex = '';
    overlay.style.position = '';
    overlay.style.inset = '';
    overlay.style.background = '';
    overlay.style.pointerEvents = '';
    overlay.style.visibility = '';
  }
  manualFlowOverride = '';
  activeModalId = null;
}

function setFlow(flow) {
  currentFlow = normalizeFlow(flow);
  document.body.classList.remove('flow-duckdb', 'flow-access');
  if (currentFlow === 'access') document.body.classList.add('flow-access');
  else document.body.classList.add('flow-duckdb');
  const tabs = document.querySelectorAll('#flowTabs .tab-btn');
  tabs.forEach((btn) => {
    const active = btn.getAttribute('data-flow') === currentFlow;
    if (active) btn.classList.add('active');
    else btn.classList.remove('active');
  });
  updateFlowControls();
}

function setNoDbState(opts) {
  const showHint = !opts || opts.showHint !== false;
  const flow = opts && opts.flow ? normalizeFlow(opts.flow) : currentFlow;
  lastStatus = null;
  document.body.classList.add('needs-selection');
  setFlow(flow);
  setDbTypeClass('none');
  setIndexControlsEnabled(false);
  if ($('currentDb')) $('currentDb').textContent = 'DB: none';
  if ($('cfgCurrentDb')) $('cfgCurrentDb').textContent = '(none)';
  if ($('selectedFileInfo')) $('selectedFileInfo').textContent = '';
  if ($('selectedMainInfo')) $('selectedMainInfo').textContent = '';
  if ($('modeBadge')) $('modeBadge').textContent = 'Modo: -';
  if ($('indexStatus')) $('indexStatus').textContent = 'Status: -';
  if ($('adminStatus')) $('adminStatus').innerHTML = 'DB: none';
  updatePrimaryHint(null, showHint);
  updateFilesHelpText(null);
  updateStatusAlerts(null);
  const exportBtn = $('exportAllBtn');
  if (exportBtn) exportBtn.disabled = true;
  if ($('resultsArea')) $('resultsArea').innerHTML = '';
  if ($('searchMeta'))
    $('searchMeta').textContent = 'Selecione um DB para buscar.';
  if ($('openConfig')) $('openConfig').classList.add('attention');
  if ($('tableList'))
    $('tableList').innerHTML = '<div class="muted">Nenhum DB selecionado</div>';
  const tablesFilter = $('tablesFilter');
  if (tablesFilter) tablesFilter.innerHTML = '';
  setFlowBanner('Selecione um arquivo para liberar busca e indexacao.', 'info');
  setSearchControlsEnabled(false);
  setStatusTile(
    'statusDbValue',
    'statusDbMeta',
    'nenhum',
    'Selecione um arquivo'
  );
  setStatusTile('statusConvValue', 'statusConvMeta', '-', 'Nenhuma conversao');
  setStatusTile('statusIndexValue', 'statusIndexMeta', '-', 'Sem DB');
  setStatusTile('statusSearchValue', 'statusSearchMeta', '-', 'Sem DB');
  setStepState('stepSelect', 'active');
  setStepState('stepConvert', '');
  setStepState('stepIndex', '');
  setStepState('stepSearch', '');
  const convText = $('convStatusText');
  if (convText) convText.textContent = 'Nenhum DB selecionado';
  const convPercent = $('convPercentText');
  if (convPercent) convPercent.textContent = '0%';
  const convBar = $('convBar');
  if (convBar) convBar.style.width = '0%';
  scheduleStatusPoll();
}

async function apiJSON(path, opts) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    setServerOnline(false, e && e.message ? e.message : 'fetch error');
    throw e;
  }
  if (!serverOnline) setServerOnline(true);
  let data = null;
  try {
    data = await r.json();
  } catch (e) {
    logUi('ERROR', 'json parse fail ' + path);
    throw e;
  }
  if (!r.ok) {
    const errMsg = data && data.error ? data.error : 'http ' + r.status;
    logUi('ERROR', path + ' ' + errMsg);
  }
  return data;
}

function setFilesPanelOpen(open) {
  filesPanelOpen = !!open;
  const panel = $('filesPanel');
  const btn = $('openFilesBtn');
  if (panel) {
    panel.hidden = !filesPanelOpen;
    if (filesPanelOpen) {
      try {
        renderFilesMain();
      } catch (e) {
        console.error('Erro ao renderizar lista de arquivos:', e);
      }
    }
  }
  if (btn) {
    btn.setAttribute('aria-expanded', filesPanelOpen ? 'true' : 'false');
  }
  try {
    console.log('setFilesPanelOpen', filesPanelOpen);
  } catch (e) {
    /* ignore */
  }
}

function apiJSONSync(path) {
  const req = new XMLHttpRequest();
  try {
    req.open('GET', path, false);
    req.send(null);
  } catch (e) {
    setServerOnline(false, e && e.message ? e.message : 'fetch error');
    throw e;
  }
  if (!serverOnline) setServerOnline(true);
  let data = null;
  try {
    data = JSON.parse(req.responseText || '{}');
  } catch (e) {
    logUi('ERROR', 'json parse fail ' + path);
    throw e;
  }
  if (req.status < 200 || req.status >= 300) {
    const errMsg = data && data.error ? data.error : 'http ' + req.status;
    logUi('ERROR', path + ' ' + errMsg);
  }
  return data;
}

function filterUploadsByFlow(list, flow) {
  if (!Array.isArray(list)) return [];
  const normalized = normalizeFlow(flow);
  if (normalized === 'duckdb') {
    return list.filter((f) => isDuckdbFile(f && f.name));
  }
  return list.filter((f) => {
    if (!f || !f.name) return false;
    if (isAccessFile(f.name)) return true;
    if (isConvertedDuckdb(f.name, accessStems)) return true;
    const currentName = shortName(currentDb || '').toLowerCase();
    return currentName && currentName === String(f.name).toLowerCase();
  });
}

function getSortedUploads(list) {
  const sortEl = $('filesSort');
  const sortKey = sortEl ? sortEl.value : 'name_asc';
  const items = (list || []).slice();
  items.sort((a, b) => {
    const nameA = a && a.name ? a.name.toLowerCase() : '';
    const nameB = b && b.name ? b.name.toLowerCase() : '';
    if (sortKey === 'name_desc')
      return nameA < nameB ? 1 : nameA > nameB ? -1 : 0;
    return nameA > nameB ? 1 : nameA < nameB ? -1 : 0;
  });
  return items;
}

function getFileMetaText(file) {
  const size = file && Number.isFinite(file.size) ? file.size : 0;
  const sizeText = 'tamanho ' + formatBytes(size);
  const dateText = file && file.modified ? formatDate(file.modified) : '';
  const parts = [sizeText];
  if (dateText) parts.push('data ' + dateText);
  return parts.join(' | ');
}

function getFileStatusText(file) {
  const name = file && file.name ? file.name : '';
  const size = file && Number.isFinite(file.size) ? file.size : 0;
  const flags = [];
  if (!isSupportedFileName(name)) flags.push('ext invalida');
  if (size === 0) flags.push('tamanho 0');
  if (flags.length === 0) flags.push('ok');
  if (isConvertedDuckdb(name, accessStems)) flags.push('convertido');
  return flags.join(', ');
}

function renderFilesMain() {
  const list = getSortedUploads(lastUploads);
  const currentName = shortName(currentDb || '').toLowerCase();
  const el = $('filesList');
  const meta = $('filesMeta');
  if (meta) meta.textContent = list.length ? '(' + list.length + ')' : '(0)';
  if (!el) return;
  if (!list.length) {
    el.textContent = 'Nenhum arquivo encontrado.';
    return;
  }
  el.innerHTML = list
    .map((f) => {
      const name = f && f.name ? f.name : '';
      const isSelected =
        currentName && currentName === String(name).toLowerCase();
      const metaText = escapeHtml(getFileMetaText(f));
      const statusText = escapeHtml(getFileStatusText(f));
      const typeLabel = escapeHtml(getFlowFromName(name) || 'outro');
      const badge = '<span class="file-badge">' + typeLabel + '</span>';
      const selectedBadge = isSelected
        ? '<span class="selected-badge">Selecionado</span>'
        : '';
      return `<div class="file-row${isSelected ? ' selected' : ''}">
      <div>
        <div class="file-name"><span class="file-name-text">${escapeHtml(name)}</span> ${badge} ${selectedBadge}</div>
        <div class="file-meta">${metaText}</div>
        <div class="file-status">${statusText}</div>
      </div>
      <div class="file-actions">
        <a href="/uploads/${encodeURIComponent(name)}" download class="btn ghost small" title="Salvar arquivo">Salvar</a>
        <button class="btn ghost small" onclick="deleteUpload('${encodeURIComponent(name)}')" title="Excluir arquivo">Excluir</button>
      </div>
    </div>`;
    })
    .join('');
}

function renderFilesSelect() {
  const list = filterUploadsByFlow(lastUploads, currentFlow);
  const currentName = shortName(currentDb || '').toLowerCase();
  const el = $('uploadsList');
  if (!el) return;
  if (!list.length) {
    el.textContent = lastUploads.length
      ? 'Nenhum arquivo para este fluxo.'
      : 'Nenhum upload encontrado.';
    return;
  }
  el.innerHTML = list
    .map((f) => {
      const name = f && f.name ? f.name : '';
      const isSelected =
        currentName && currentName === String(name).toLowerCase();
      const metaText = escapeHtml(getFileMetaText(f));
      const statusText = escapeHtml(getFileStatusText(f));
      const selectLabel = isSelected ? 'Selecionado' : 'Selecionar';
      const selectClass = isSelected
        ? 'btn select-btn selected'
        : 'btn ghost select-btn';
      const selectAction = isSelected
        ? 'disabled'
        : `onclick="selectUpload('${encodeURIComponent(name)}', this)"`;
      const rowClick = isSelected
        ? ''
        : `onclick="onSelectRowClick(event,'${encodeURIComponent(name)}')"`;
      return `<div class="upload-row${isSelected ? ' selected' : ''}" ${rowClick}>
      <div>
        <div style="font-weight:600">${escapeHtml(name)} ${isSelected ? '<span class="selected-badge">Selecionado</span>' : ''}</div>
        <div class="file-meta">${metaText}</div>
        <div class="file-status">${statusText}</div>
      </div>
      <div class="file-actions">
        <button class="${selectClass}" ${selectAction} title="Selecionar este DB">${selectLabel}</button>
        <a href="/uploads/${encodeURIComponent(name)}" download class="btn ghost small" title="Salvar arquivo">Salvar</a>
        <button class="btn ghost small" onclick="deleteUpload('${encodeURIComponent(name)}', this)" title="Excluir arquivo">Excluir</button>
      </div>
    </div>`;
    })
    .join('');
}

function renderSelectedInfo() {
  const el = $('selectedFileInfo');
  const mainEl = $('selectedMainInfo');
  if (!currentDb) {
    if (el) el.textContent = '';
    if (mainEl) mainEl.textContent = '';
    return;
  }
  const name = shortName(currentDb);
  const match = (lastUploads || []).find(
    (f) => f && f.name && f.name.toLowerCase() === name.toLowerCase()
  );
  if (!match) {
    const text = 'Arquivo selecionado: ' + name;
    if (el) el.textContent = text;
    if (mainEl) mainEl.textContent = text;
    return;
  }
  const text =
    'Arquivo selecionado: ' +
    name +
    ' | ' +
    getFileMetaText(match) +
    ' | ' +
    getFileStatusText(match);
  if (el) el.textContent = text;
  if (mainEl) mainEl.textContent = text;
}

async function refreshUiState(opts) {
  try {
    const useSync = opts && opts.sync === true;
    const uploads = useSync
      ? apiJSONSync('/admin/list_uploads')
      : await apiJSON('/admin/list_uploads');
    currentDb = uploads.current_db || '';
    priorityTables = uploads.priority_tables || [];
    lastUploads = uploads.uploads || [];
    accessStems = buildAccessStemSet(lastUploads);
    const hasDb = hasDbSelected();
    const currentDbName = hasDb ? shortName(currentDb) : '';
    if ($('currentDb')) {
      $('currentDb').textContent = 'DB: ' + (hasDb ? currentDbName : 'none');
      $('currentDb').title = hasDb ? currentDb : '';
    }
    if ($('cfgCurrentDb')) {
      $('cfgCurrentDb').textContent = hasDb ? currentDbName : '(none)';
      $('cfgCurrentDb').title = hasDb ? currentDb : '';
    }
    const autoIndexToggle = $('autoIndexToggle');
    if (
      autoIndexToggle &&
      typeof uploads.auto_index_after_convert !== 'undefined'
    ) {
      autoIndexToggle.checked = !!uploads.auto_index_after_convert;
    }
    renderFilesMain();
    renderDbTabs();
  } catch (e) {
    const filesList = $('filesList');
    if (filesList) filesList.textContent = 'Erro ao listar arquivos';
    try {
      const msg = e && e.message ? e.message : String(e || 'erro');
      logUi('ERROR', 'list uploads falhou: ' + msg);
    } catch (_) {
      logUi('ERROR', 'list uploads falhou');
    }
  }
  await refreshStatus();
  renderFilesSelect();
  renderSelectedInfo();
  const hasDb = hasDbSelected();
  if (hasDb) {
    document.body.classList.remove('needs-selection');
    if ($('searchMeta'))
      $('searchMeta').textContent = 'Digite um termo e clique em Pesquisar.';
    if ($('openConfig')) $('openConfig').classList.remove('attention');
    refreshTables();
  } else {
    if ($('openConfig')) $('openConfig').classList.add('attention');
  }
  scheduleStatusPoll();
}

function renderDbTabs() {
  const el = $('dbTabs');
  const help = $('dbTabHelp');
  if (!el) return;
  // Na coluna "Tabelas" queremos mostrar apenas bancos utilizáveis na busca,
  // ou seja, arquivos DuckDB (resultado final da conversão ou nativos).
  const items = (lastUploads || []).filter(
    (f) => f && f.name && isDuckdbFile(f.name)
  );
  if (!items.length) {
    el.innerHTML = '';
    if (help) help.textContent = 'Nenhum banco enviado ainda.';
    return;
  }
  const sortEl = $('dbSort');
  const sortKey = sortEl ? sortEl.value : 'name_asc';
  const sorted = items.slice().sort((a, b) => {
    const nameA = a && a.name ? String(a.name).toLowerCase() : '';
    const nameB = b && b.name ? String(b.name).toLowerCase() : '';
    if (sortKey === 'name_desc')
      return nameA < nameB ? 1 : nameA > nameB ? -1 : 0;
    return nameA > nameB ? 1 : nameA < nameB ? -1 : 0;
  });
  const currentName = shortName(currentDb || '').toLowerCase();
  el.innerHTML = sorted
    .map((f) => {
      const name = f.name;
      const isActive =
        currentName && currentName === String(name).toLowerCase();
      const cls = isActive ? 'db-tab active' : 'db-tab';
      return `<button class="${cls}" onclick="selectDbFromTab('${encodeURIComponent(name)}')" title="${escapeAttr(name)}">${escapeHtml(name)}</button>`;
    })
    .join('');
  if (help) {
    help.textContent =
      'Abas por banco: clique para trocar as tabelas exibidas.';
  }
}

async function refreshStatus() {
  try {
    const s = await apiJSON('/admin/status');
    lastStatus = s;
    const prevDb = String(currentDb || '');
    const db = s.db || '';
    if (db) {
      currentDb = db;
    }
    const dbChanged = prevDb !== String(db || '');
    const dbName = shortName(db);
    const conversionRunning = !!(s.conversion && s.conversion.running);
    const dbType = getFlowFromName(db);
    const converted =
      dbType === 'duckdb' && isConvertedDuckdb(dbName, accessStems);
    const indexReady = !!(s.fulltext_count && dbType === 'duckdb');
    const uiFlow = conversionRunning
      ? 'access'
      : converted
        ? 'access'
        : dbType || currentFlow;
    const indexFlow = conversionRunning ? '' : dbType;
    const modalOpen = activeModalId === 'configModal';
    const conversionJustFinished = lastConversionRunning && !conversionRunning;
    const indexingJustFinished = lastIndexingRunning && !s.indexing;
    if (!modalOpen && manualFlowOverride) {
      manualFlowOverride = '';
    }
    if (
      !db &&
      !conversionRunning &&
      !manualFlowOverride &&
      currentFlow !== 'duckdb'
    ) {
      setFlow('duckdb');
    }
    const manualFlow =
      modalOpen && manualFlowOverride ? manualFlowOverride : '';
    const desiredFlow = manualFlow || uiFlow;

    if (conversionRunning) {
      setFlow('access');
      setDbTypeClass('none');
    } else if (dbType) {
      if (currentFlow !== desiredFlow) {
        setFlow(desiredFlow);
      }
      setDbTypeClass(dbType);
    } else {
      if (manualFlow && currentFlow !== manualFlow) {
        setFlow(manualFlow);
      }
      setDbTypeClass('none');
    }

    if (!db && !conversionRunning) {
      const noDbFlow = manualFlow || currentFlow;
      setNoDbState({ showHint: true, flow: noDbFlow });
      return;
    }

    const indexerAvailable = s.indexer_available !== false;
    const indexerErr = s.indexer_error || '';
    const indexerStatus = $('indexerStatus');
    if (indexerStatus) {
      if (indexerAvailable) {
        indexerStatus.textContent = 'Indexador: ok';
      } else {
        indexerStatus.textContent =
          'Indexador indisponivel: ' + (indexerErr || 'erro');
      }
    }

    updateConversionModeText(s);
    updatePrimaryHint(s, true);
    updateFilesHelpText(s);
    updateStatusAlerts(s);

    if (indexFlow === 'duckdb') {
      if (s.indexing) $('indexStatus').textContent = 'Indexando...';
      else
        $('indexStatus').textContent = s.fulltext_count
          ? 'Pronto'
          : 'Necessario';
    } else {
      $('indexStatus').textContent = conversionRunning ? 'Convertendo' : 'N/A';
    }

    setStatusTile(
      'statusDbValue',
      'statusDbMeta',
      db ? dbName : 'nenhum',
      db ? (dbType === 'duckdb' ? 'DuckDB' : 'Access') : 'Selecione um arquivo'
    );
    if (conversionRunning) {
      const conversionStatus = s.conversion || {};
      const pct = conversionStatus.percent
        ? conversionStatus.percent + '%'
        : '0%';
      setStatusTile(
        'statusConvValue',
        'statusConvMeta',
        'Convertendo',
        pct + ' ' + (conversionStatus.current_table || '')
      );
    } else if (s.conversion && s.conversion.ok) {
      setStatusTile(
        'statusConvValue',
        'statusConvMeta',
        'Concluida',
        s.conversion.msg || 'Conversao ok'
      );
    } else if (dbType === 'duckdb' && !converted) {
      setStatusTile(
        'statusConvValue',
        'statusConvMeta',
        'Nao precisa',
        'DuckDB nativo'
      );
    } else {
      setStatusTile(
        'statusConvValue',
        'statusConvMeta',
        'Inativa',
        s.conversion && s.conversion.msg
          ? s.conversion.msg
          : 'Nenhuma conversao'
      );
    }
    if (indexFlow === 'duckdb') {
      if (s.indexing) {
        setStatusTile(
          'statusIndexValue',
          'statusIndexMeta',
          'Indexando',
          'Construindo _fulltext'
        );
      } else if (s.fulltext_count) {
        setStatusTile(
          'statusIndexValue',
          'statusIndexMeta',
          'Pronto',
          s.fulltext_count + ' linhas'
        );
      } else {
        setStatusTile(
          'statusIndexValue',
          'statusIndexMeta',
          'Necessario',
          'Indice ausente'
        );
      }
    } else {
      setStatusTile(
        'statusIndexValue',
        'statusIndexMeta',
        'N/A',
        'Somente DuckDB'
      );
    }
    if (indexReady && !conversionRunning && !s.indexing) {
      setStatusTile(
        'statusSearchValue',
        'statusSearchMeta',
        'Disponivel',
        'Pronto para buscar'
      );
    } else if (conversionRunning) {
      setStatusTile(
        'statusSearchValue',
        'statusSearchMeta',
        'Bloqueada',
        'Aguardando conversao'
      );
    } else if (s.indexing) {
      setStatusTile(
        'statusSearchValue',
        'statusSearchMeta',
        'Bloqueada',
        'Indexando _fulltext'
      );
    } else {
      setStatusTile(
        'statusSearchValue',
        'statusSearchMeta',
        'Bloqueada',
        'Indice necessario'
      );
    }

    setStepState('stepSelect', db || conversionRunning ? 'done' : 'active');
    if (conversionRunning) {
      setStepState('stepConvert', 'active');
    } else if (dbType === 'access') {
      setStepState('stepConvert', 'warn');
    } else {
      setStepState('stepConvert', 'done');
    }
    if (indexFlow === 'duckdb') {
      if (s.indexing) setStepState('stepIndex', 'active');
      else if (s.fulltext_count) setStepState('stepIndex', 'done');
      else setStepState('stepIndex', 'active');
    } else {
      setStepState('stepIndex', 'warn');
    }

    let searchEnabled = false;
    if (conversionRunning) {
      setFlowBanner(
        'Conversao em andamento. Aguarde para indexar e buscar.',
        'warn'
      );
      setSearchControlsEnabled(false);
      searchEnabled = false;
    } else if (dbType === 'access' && !converted) {
      setFlowBanner(
        'Banco Access selecionado. Converta para DuckDB para liberar busca completa.',
        'warn'
      );
      setSearchControlsEnabled(false);
      searchEnabled = false;
    } else if (s.db_engine === 'sqlite') {
      setFlowBanner(
        'SQLite ativo. Busca textual disponivel neste modo sem _fulltext.',
        'info'
      );
      setSearchControlsEnabled(true);
      searchEnabled = true;
    } else if (dbType === 'access' && converted && s.odbc_enabled === false) {
      setFlowBanner(
        'Conversao pura ativada. ODBC desativado no servidor.',
        'info'
      );
      setSearchControlsEnabled(false);
      searchEnabled = false;
    } else if (indexFlow === 'duckdb' && !s.fulltext_count) {
      setFlowBanner('Indice _fulltext necessario antes de buscar.', 'info');
      setSearchControlsEnabled(false);
      searchEnabled = false;
    } else if (s.indexing) {
      setFlowBanner(
        'Indexacao em andamento. Busca liberada ao terminar.',
        'info'
      );
      setSearchControlsEnabled(false);
      searchEnabled = false;
    } else {
      setFlowBanner('', '');
      setSearchControlsEnabled(true);
      searchEnabled = true;
    }

    if (!searchEnabled) {
      setStepState('stepSearch', 'warn');
    } else if (indexReady && !conversionRunning && !s.indexing) {
      setStepState('stepSearch', 'done');
    } else {
      setStepState('stepSearch', 'active');
    }

    // Atualiza hint/botao de busca direto na coluna Tabelas
    const dbSearchHint = $('dbSearchHint');
    const dbSearchBtn = $('dbSearchBtn');
    const dbSearchText = $('dbSearchText');
    if (dbSearchHint) {
      if (searchEnabled && db) {
        const label = shortName(db) || 'este DB';
        if (dbSearchText) {
          dbSearchText.textContent = 'Pronto para buscar em ' + label + '.';
        }
        dbSearchHint.style.display = '';
        if (dbSearchBtn) dbSearchBtn.disabled = false;
      } else {
        dbSearchHint.style.display = 'none';
      }
    }

    if ($('searchMeta')) {
      if (conversionRunning) {
        $('searchMeta').textContent =
          'Busca bloqueada: conversao em andamento.';
      } else if (dbType === 'access' && !converted) {
        $('searchMeta').textContent = 'Busca bloqueada: converta para DuckDB.';
      } else if (s.db_engine === 'sqlite') {
        $('searchMeta').textContent =
          'Digite um termo e clique em Pesquisar. SQLite busca sem _fulltext.';
      } else if (indexFlow === 'duckdb' && !s.fulltext_count) {
        $('searchMeta').textContent =
          'Busca bloqueada: crie o indice _fulltext.';
      } else if (s.indexing) {
        $('searchMeta').textContent =
          'Busca bloqueada: indexacao em andamento.';
      } else {
        $('searchMeta').textContent = 'Digite um termo e clique em Pesquisar.';
      }
    }

    const canIndex = indexFlow === 'duckdb' && !s.indexing && indexerAvailable;
    setIndexControlsEnabled(canIndex);
    const indexMsg = $('indexMsg');
    if (indexMsg) {
      if (!indexerAvailable) {
        indexMsg.textContent =
          'Indexador indisponivel: ' + (indexerErr || 'erro');
      } else if (indexFlow !== 'duckdb') {
        indexMsg.textContent = conversionRunning
          ? 'Aguarde conversao.'
          : 'Indice _fulltext disponivel apenas para DuckDB.';
      }
    }
    if (s.indexing) {
      const idxPct = s.indexing_percent || s.index_progress || s.index_percent;
      const pctText =
        typeof idxPct === 'number' ? ' Progresso: ' + idxPct + '%' : '';
      setModalBanner(
        'indexModalBanner',
        'Indexacao em andamento.' + pctText,
        'info'
      );
    }
    if (s.conversion && s.conversion.running) {
      const percent = s.conversion.percent || 0;
      $('convBar').style.width = percent + '%';
      $('convPercentText').textContent = (percent || 0) + '%';
      $('convStatusText').textContent =
        `Convertendo: ${s.conversion.current_table || ''} (${s.conversion.processed_tables || 0}/${s.conversion.total_tables || 0})`;
      $('modeBadge').textContent = 'Modo: convertendo...';
      const topHint = $('convTopHint');
      if (topHint) {
        topHint.textContent = s.auto_index_after_convert
          ? 'Auto indexacao apos conversao: ativa.'
          : 'Auto indexacao apos conversao: desativada.';
      }
    } else {
      if (converted) $('modeBadge').textContent = 'Modo: access convertido';
      else if (dbType === 'duckdb')
        $('modeBadge').textContent = 'Modo: duckdb (rapido)';
      else if (dbType === 'access')
        $('modeBadge').textContent = 'Modo: access (fallback)';
      else $('modeBadge').textContent = 'Modo: -';
      if (s.indexing) {
        const baseMsg =
          s.conversion && s.conversion.ok
            ? s.conversion.msg || 'Conversao finalizada'
            : 'Banco carregado';
        $('convStatusText').textContent = baseMsg + ' - indexando _fulltext...';
        $('convBar').style.width = '100%';
        $('convPercentText').textContent = '100%';
      } else if (s.conversion && s.conversion.ok && s.fulltext_count) {
        const msg = s.conversion.msg || 'Conversao finalizada';
        $('convStatusText').textContent = msg + ' - indexacao concluida';
        $('convBar').style.width = '100%';
        $('convPercentText').textContent = '100%';
      } else if (s.conversion && s.conversion.ok && !s.fulltext_count) {
        const msg = s.conversion.msg || 'Conversao finalizada';
        $('convStatusText').textContent =
          msg + ' - aguarda indexacao (_fulltext)';
        $('convBar').style.width = '100%';
        $('convPercentText').textContent = '100%';
      } else {
        $('convStatusText').textContent =
          s.conversion && s.conversion.msg
            ? s.conversion.msg
            : 'Nenhuma conversao em andamento';
        $('convBar').style.width =
          s.conversion && s.conversion.percent
            ? s.conversion.percent + '%'
            : '0%';
        $('convPercentText').textContent =
          s.conversion && s.conversion.percent
            ? s.conversion.percent + '%'
            : '0%';
      }
      const topHint = $('convTopHint');
      if (topHint) {
        topHint.textContent = '';
      }
    }

    const upEl = $('uploadMsg');
    if (upEl && s.conversion) {
      if (lastConversionRunning && !s.conversion.running) {
        if (s.conversion.ok) {
          const outName = shortName(s.conversion.output || '');
          upEl.textContent = 'Conversao concluida: ' + (outName || 'ok');
        } else if (s.conversion.ok === false) {
          upEl.textContent =
            'Conversao falhou: ' + (s.conversion.msg || 'erro');
        }
      }
    }

    if (conversionJustFinished) {
      const ok = s.conversion && s.conversion.ok;
      const message = ok
        ? 'Conversao concluida. Encaminhando para o proximo passo.'
        : 'Conversao falhou. Veja detalhes em Alertas e logs.';
      setModalBanner('convModalBanner', message, ok ? 'info' : 'error');
      if (activeModalId === 'configModal') {
        const nextModal =
          ok && (s.indexing || s.fulltext_count === 0) ? 'indexModal' : '';
        scheduleModalClose(nextModal || '');
      }

      // Dispara um refresh completo de UI apos conversao, em paralelo,
      // para atualizar lista de uploads, abas de DB e tabelas.
      if (ok) {
        try {
          setTimeout(() => {
            try {
              refreshUiState();
            } catch (e) {}
          }, 0);
        } catch (e) {
          /* ignored */
        }
      }
    } else if (!conversionRunning) {
      setModalBanner('convModalBanner', '', '');
    }

    if (indexingJustFinished) {
      const okIndex = !!s.fulltext_count;
      const msg = okIndex
        ? 'Indexacao concluida. Busca liberada.'
        : 'Indexacao terminou sem _fulltext.';
      setModalBanner('indexModalBanner', msg, okIndex ? 'info' : 'warn');
      if (activeModalId === 'indexModal') {
        const next = okIndex ? 'searchModal' : '';
        scheduleIndexModalClose(next || '');
      }
    } else if (!s.indexing) {
      setModalBanner('indexModalBanner', '', '');
    }

    lastConversionRunning = !!(s.conversion && s.conversion.running);
    lastIndexingRunning = !!s.indexing;
    const dbLabel = escapeHtml(s.db || '(nenhum)');
    let html = `<div>DB: ${dbLabel}<br/>_fulltext linhas: ${s.fulltext_count || 0}</div>`;
    if (s.top_tables && s.top_tables.length) {
      html +=
        '<div style="margin-top:8px"><strong>Top tabelas:</strong><ul>' +
        s.top_tables
          .map((t) => `<li>${escapeHtml(t.table)} - ${t.count}</li>`)
          .join('') +
        '</ul></div>';
    }
    const adminStatus = $('adminStatus');
    if (adminStatus) adminStatus.innerHTML = html;
    if (document.body.classList.contains('modal-open')) {
      renderFilesSelect();
      renderSelectedInfo();
    }
    // Atualiza lista de tabelas/abas quando o DB muda ou apos conversao
    if (dbChanged || conversionJustFinished) {
      refreshTables();
    }
  } catch (e) {
    const adminStatus = $('adminStatus');
    if (adminStatus) adminStatus.textContent = 'Erro no status';
    logUi('ERROR', 'status falhou');
  }
}

async function refreshTables() {
  const tableList = $('tableList');
  if (!tableList) return;
  if (!hasDbSelected()) {
    tableList.innerHTML = '<div class="muted">Nenhum DB selecionado</div>';
    return;
  }
  try {
    const t = await apiJSON('/api/tables');
    if (t.error) {
      $('tableList').innerHTML =
        '<div class="muted">Erro: ' + escapeHtml(t.error) + '</div>';
      logUi('ERROR', 'tabelas ' + t.error);
      return;
    }
    const list = t.tables || [];
    const filterEl = $('filterTables');
    const filter = filterEl ? filterEl.value.toLowerCase() : '';
    const dbKey = String(currentDb || '');
    const prev = lastTablesByDb[dbKey] || [];
    const prevSet = new Set(prev);
    const currentSet = new Set(list);
    const newOnes = list.filter((name) => !prevSet.has(name));
    const oldOnes = list.filter((name) => prevSet.has(name));
    lastTablesByDb[dbKey] = list.slice();
    const ordered = newOnes.concat(oldOnes);
    const container = $('tableList');
    container.innerHTML = '';
    ordered
      .filter((name) => name.toLowerCase().includes(filter))
      .forEach((name) => {
        const isNew = currentSet.has(name) && !prevSet.has(name);
        const badge = isNew ? ' <span class="file-badge">novo</span>' : '';
        const li = document.createElement('li');
        li.className = 'table-item';
        li.innerHTML = `<div>${escapeHtml(name)}${badge}</div><div><button class="btn ghost" onclick="openTable(event,'${encodeURIComponent(
          name
        )}')">Abrir</button></div>`;
        li.onclick = () => openTable(null, encodeURIComponent(name));
        container.appendChild(li);
      });

    const sel = $('tablesFilter');
    if (sel) {
      const previouslySelected = Array.from(sel.selectedOptions).map(
        (o) => o.value
      );
      sel.innerHTML = '';
      const visibleForFilter = list.filter((n) => !/^MSys/i.test(n));
      visibleForFilter.forEach((name) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (previouslySelected.includes(name)) opt.selected = true;
        sel.appendChild(opt);
      });
    }
  } catch (e) {
    $('tableList').innerHTML =
      '<div class="muted">Erro ao carregar tabelas</div>';
    logUi('ERROR', 'tabelas falhou');
  }
}

if (!window.__appSearchFlowBound) {
  window.__appSearchFlowBound = true;

  const setBusyButton = (btn, busyText, idleText) => {
    if (!btn) return () => {};
    const original = idleText || btn.textContent;
    btn.disabled = true;
    btn.textContent = busyText;
    return () => {
      btn.disabled = false;
      btn.textContent = original;
    };
  };

  const setSearchMeta = (text, level) => {
    const el = $('searchMeta');
    if (!el) return;
    el.textContent = text || '';
    el.classList.remove('warn', 'error');
    if (level === 'warn' || level === 'error') {
      el.classList.add(level);
    }
  };

  const onSelectRowClick = (ev, nameEnc) => {
    if (
      ev &&
      ev.target &&
      ev.target.closest &&
      ev.target.closest('.file-actions')
    )
      return;
    selectUpload(nameEnc, null);
  };

  const requestSelectDb = async (name) => {
    return apiJSON('/admin/select', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: name }),
    });
  };

  const handleSelectDbResult = async (name, msg, response, closeOnSuccess) => {
    if (response && response.ok) {
      if (msg) msg.textContent = 'DB selecionado: ' + name;
      manualFlowOverride = '';
      setFlowBanner('', '');
      await refreshUiState();
      if (closeOnSuccess) closeModal();
      return;
    }
    const err = (response && response.error) || 'falha ao selecionar';
    if (msg) msg.textContent = 'Erro ao selecionar: ' + err;
    setFlowBanner(
      'Nao foi possivel selecionar o arquivo. Tente novamente.',
      'error'
    );
    logUi('ERROR', 'select db falhou');
  };

  const deleteUpload = async (nameEnc, btn) => {
    if (!confirm('Deseja realmente excluir este arquivo?')) return;
    const name = decodeURIComponent(nameEnc);
    const msg = $('uploadMsg');
    const restoreBtn = setBusyButton(
      btn,
      'Excluindo...',
      btn ? btn.textContent : 'Excluir'
    );
    if (msg) msg.textContent = 'Excluindo: ' + name;
    try {
      const j = await apiJSON('/admin/delete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ filename: name }),
      });
      if (j && j.ok) {
        if (msg) msg.textContent = 'Arquivo excluido: ' + name;
        setFlowBanner('', '');
        await refreshUiState();
      } else {
        const err = (j && j.error) || 'falha ao excluir';
        if (msg) msg.textContent = 'Erro ao excluir: ' + err;
        setFlowBanner(
          'Nao foi possivel excluir. Verifique se o arquivo esta em uso.',
          'warn'
        );
      }
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao excluir';
      setFlowBanner('Erro ao excluir. Tente novamente.', 'error');
      logUi('ERROR', 'delete falhou');
    } finally {
      restoreBtn();
    }
  };

  const selectUpload = async (nameEnc, btn) => {
    const name = decodeURIComponent(nameEnc);
    const msg = $('uploadMsg');
    const restoreBtn = setBusyButton(
      btn,
      'Selecionando...',
      btn ? btn.textContent : 'Selecionar'
    );
    if (msg) msg.textContent = 'Selecionando: ' + name;
    try {
      const j = await requestSelectDb(name);
      await handleSelectDbResult(name, msg, j, true);
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao selecionar DB';
      setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
      logUi('ERROR', 'select db falhou');
    } finally {
      restoreBtn();
    }
  };

  const selectDbFromTab = async (nameEnc) => {
    const name = decodeURIComponent(nameEnc);
    const msg = $('uploadMsg');
    if (msg) msg.textContent = 'Selecionando: ' + name;
    try {
      const j = await requestSelectDb(name);
      await handleSelectDbResult(name, msg, j, false);
    } catch (e) {
      if (msg) msg.textContent = 'Erro ao selecionar DB';
      setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
      logUi('ERROR', 'select db falhou');
    }
  };

  const doSearch = async (opts) => {
    const q = $('q').value.trim();
    if (!q) {
      setSearchMeta('Digite um termo para pesquisar.', 'warn');
      setFlowBanner('Digite um termo antes de iniciar a busca.', 'warn');
      if ($('q')) $('q').focus();
      return;
    }
    if (!hasDbSelected()) {
      setNoDbState({ showHint: true });
      logUi('WARN', 'acao exige DB');
      setSearchMeta('Selecione um DB antes de pesquisar.', 'warn');
      setFlowBanner('Selecione um DB ativo antes de abrir a busca.', 'warn');
      return;
    }
    const btn = $('searchBtn');
    if (btn.disabled) return;
    const exportBtn = $('exportAllBtn');
    if (exportBtn) exportBtn.disabled = true;
    try {
      if (lastStatus && lastStatus.conversion && lastStatus.conversion.running) {
        setSearchMeta('Busca bloqueada: conversao em andamento.', 'warn');
        setFlowBanner(
          'Aguarde a conversao do banco terminar antes de pesquisar.',
          'warn'
        );
        return;
      }
      if (lastStatus && lastStatus.indexing) {
        setSearchMeta('Busca bloqueada: indexacao em andamento.', 'warn');
        setFlowBanner(
          'Aguarde a indexacao (_fulltext) terminar antes de pesquisar.',
          'warn'
        );
        return;
      }
      if (
        lastStatus &&
        lastStatus.db &&
        lastStatus.db.toLowerCase().endsWith('.duckdb') &&
        !lastStatus.fulltext_count
      ) {
        setSearchMeta('Busca bloqueada: indice _fulltext ausente.', 'warn');
        setFlowBanner(
          'Este banco DuckDB ainda nao possui indice _fulltext. Inicie a indexacao antes de pesquisar.',
          'warn'
        );
        return;
      }
    } catch (e) {
      logUi('WARN', 'falha ao validar status antes da busca');
    }
    const per_table = parseInt($('per_table').value, 10) || 10;
    const candidate_limit = parseInt($('candidate_limit').value, 10) || 1000;
    const total_limit = parseInt($('total_limit').value, 10) || 500;
    const token_mode = $('token_mode').value;
    const min_score = parseInt($('min_score').value, 10) || null;
    lastQuery = q;
    setSearchMeta(`Buscando: "${q}" ...`, '');
    setFlowBanner('Busca em andamento. Aguarde os resultados.', 'info');
    const tablesSel = $('tablesFilter');
    let tablesParam = '';
    let selectedTables = [];
    if (tablesSel) {
      selectedTables = Array.from(tablesSel.selectedOptions)
        .map((o) => o.value)
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
        setSearchMeta('Erro: ' + data.error, 'error');
        $('resultsArea').innerHTML =
          '<div class="card small">Nao foi possivel concluir a busca.</div>';
        setFlowBanner(
          'A busca retornou erro. Revise o termo ou o estado do DB.',
          'error'
        );
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
      if (!data.returned_count) {
        setSearchMeta(
          `Nenhum resultado para "${q}". Candidatos avaliados: ${data.candidate_count || 0}.`,
          'warn'
        );
        setFlowBanner(
          'Nenhum resultado encontrado. Ajuste o termo, a pontuacao minima ou as tabelas selecionadas.',
          'warn'
        );
      } else {
        setSearchMeta(
          `Resultados: ${data.returned_count} (candidatos: ${data.candidate_count})`,
          ''
        );
        setFlowBanner(
          `Busca concluida. ${data.returned_count} resultado(s) retornado(s).`,
          'info'
        );
      }
      if (exportBtn) exportBtn.disabled = !data.returned_count;
      renderResults(q, data.results || {}, per_table);
    } catch (e) {
      setSearchMeta('Erro na busca.', 'error');
      $('resultsArea').innerHTML =
        '<div class="card small">Erro de rede ou servidor ao executar a busca.</div>';
      setFlowBanner(
        'Erro na busca. Verifique o servidor e tente novamente.',
        'error'
      );
      logUi('ERROR', 'search falhou');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Pesquisar';
    }
  };

  const tableTagId = (name) => {
    return 'tag-' + encodeURIComponent(name);
  };

  if (typeof window.setBusyButton !== 'function') window.setBusyButton = setBusyButton;
  if (typeof window.setSearchMeta !== 'function') window.setSearchMeta = setSearchMeta;
  if (typeof window.onSelectRowClick !== 'function')
    window.onSelectRowClick = onSelectRowClick;
  if (typeof window.deleteUpload !== 'function') window.deleteUpload = deleteUpload;
  if (typeof window.selectUpload !== 'function') window.selectUpload = selectUpload;
  if (typeof window.selectDbFromTab !== 'function')
    window.selectDbFromTab = selectDbFromTab;
  if (typeof window.doSearch !== 'function') window.doSearch = doSearch;
  if (typeof window.tableTagId !== 'function') window.tableTagId = tableTagId;
}
