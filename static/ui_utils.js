// ui_utils.js
// Utilitarios puros para deteccao de tipo de arquivo, fluxo (Access/DuckDB)
// e formatacao de tamanhos/datas. Nao acessa DOM.
// Versao identica a fix_branch_ui_utils.js, exposta em window.*
(function () {
  if (typeof window.normalizeFlow === 'function') {
    return;
  }
  function normalizeFlow(flow) {
    return flow === 'access' ? 'access' : 'duckdb';
  }
  function isAccessFile(name) {
    const lower = (name || '').toLowerCase();
    return lower.endsWith('.mdb') || lower.endsWith('.accdb');
  }
  function isDuckdbFile(name) {
    const lower = (name || '').toLowerCase();
    return (
      lower.endsWith('.duckdb') ||
      lower.endsWith('.db') ||
      lower.endsWith('.sqlite') ||
      lower.endsWith('.sqlite3')
    );
  }
  function getFlowFromName(name) {
    if (isAccessFile(name)) return 'access';
    if (isDuckdbFile(name)) return 'duckdb';
    return '';
  }
  function isSupportedFileName(name) {
    return isAccessFile(name) || isDuckdbFile(name);
  }
  function getFileStem(name) {
    const lower = (name || '').toLowerCase();
    return lower
      .replace(/\.(mdb|accdb)$/, '')
      .replace(/\.(duckdb|db|sqlite|sqlite3)$/, '');
  }
  function buildAccessStemSet(list) {
    const stems = new Set();
    (list || []).forEach((f) => {
      if (!f || !f.name) return;
      if (isAccessFile(f.name)) stems.add(getFileStem(f.name));
    });
    return stems;
  }
  function isConvertedDuckdb(name, accessStems) {
    if (!isDuckdbFile(name)) return false;
    if (!accessStems || !accessStems.has) return false;
    return accessStems.has(getFileStem(name));
  }
  function isFileAllowedForFlow(fileName, flow) {
    if (normalizeFlow(flow) === 'access') {
      return isAccessFile(fileName);
    }
    return isDuckdbFile(fileName);
  }
  function formatBytes(size) {
    const num = Number(size);
    if (!Number.isFinite(num) || num < 0) return '0 B';
    if (num < 1024) return num + ' B';
    const kb = num / 1024;
    if (kb < 1024) return kb.toFixed(1) + ' KB';
    const mb = kb / 1024;
    if (mb < 1024) return mb.toFixed(1) + ' MB';
    const gb = mb / 1024;
    return gb.toFixed(1) + ' GB';
  }
  function formatDate(isoText) {
    if (!isoText) return '';
    const d = new Date(isoText);
    if (!Number.isFinite(d.getTime())) return '';
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
  }
  window.normalizeFlow = normalizeFlow;
  window.isAccessFile = isAccessFile;
  window.isDuckdbFile = isDuckdbFile;
  window.getFlowFromName = getFlowFromName;
  window.isSupportedFileName = isSupportedFileName;
  window.getFileStem = getFileStem;
  window.buildAccessStemSet = buildAccessStemSet;
  window.isConvertedDuckdb = isConvertedDuckdb;
  window.isFileAllowedForFlow = isFileAllowedForFlow;
  window.formatBytes = formatBytes;
  window.formatDate = formatDate;
})();
