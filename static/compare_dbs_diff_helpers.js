function valuesDifferent(a, b) {
  if (a == null && b == null) return false;
  return JSON.stringify(a) !== JSON.stringify(b);
}

function shortValue(v, maxLen = 80) {
  let s;
  try {
    s = JSON.stringify(v);
  } catch (e) {
    s = String(v);
  }
  if (s.length > maxLen) {
    return s.slice(0, maxLen - 3) + '...';
  }
  return s;
}

function showRowSegment(rowId, which) {
  const important = document.getElementById(rowId + '-important');
  const all = document.getElementById(rowId + '-all');
  if (!important || !all) return;
  if (which === 'all') {
    important.style.display = 'none';
    all.style.display = 'block';
  } else {
    important.style.display = 'block';
    all.style.display = 'none';
  }
}

function guessKeyColumnsForTable(tableName, columns) {
  const upperName = (tableName || '').toUpperCase();
  const cols = (columns || []).map(c => String(c));
  const upperCols = cols.map(c => c.toUpperCase());

  if (upperName === 'RANGER_SOSTAT') {
    const idxRtuno = upperCols.indexOf('RTUNO');
    const idxPntno = upperCols.indexOf('PNTNO');
    if (idxRtuno !== -1 && idxPntno !== -1) {
      return [cols[idxRtuno], cols[idxPntno]];
    }
  }

  const idxId = upperCols.indexOf('ID');
  if (idxId !== -1) {
    return [cols[idxId]];
  }

  const candidates = cols.filter(c => /_id$/i.test(c));
  if (candidates.length === 1) {
    return [candidates[0]];
  }

  return [];
}

window.valuesDifferent = valuesDifferent;
window.shortValue = shortValue;
window.showRowSegment = showRowSegment;
window.guessKeyColumnsForTable = guessKeyColumnsForTable;
