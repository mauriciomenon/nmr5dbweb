const COMPARE_UI_DIFF_TYPES = {
  added: {
    sourceLabel: 'banco ANTIGO (B)',
    directionLabel: 'no banco ANTIGO',
    uiLabel: 'Removida',
    badgeClass: 'removed',
  },
  removed: {
    sourceLabel: 'banco NOVO (A)',
    directionLabel: 'no banco NOVO',
    uiLabel: 'Nova',
    badgeClass: 'added',
  },
  changed: {
    sourceLabel: 'A e B',
    directionLabel: 'em ambos os bancos',
    uiLabel: 'Alterada',
    badgeClass: 'changed',
  },
};

function escapeHtmlText(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function shortDbLabel(pathValue) {
  const raw = String(pathValue || '').trim();
  if (!raw) return '-';
  const normalized = raw.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : raw;
}

function buildCompareSummary(data, rows, changedRows) {
  const s = data.summary || {};
  const same = s.same_count ?? 0;
  const onlyInDbA = s.removed_count ?? rows.removed.length;
  const onlyInDbB = s.added_count ?? rows.added.length;
  const changed = s.changed_count ?? changedRows.length;
  const totalKeys = s.keys_total ?? same + onlyInDbA + onlyInDbB + changed;
  const colDiffCounts = {};

  for (const row of changedRows) {
    for (const column of data.compare_columns || []) {
      if (!valuesDifferent(row.a[column], row.b[column])) continue;
      colDiffCounts[column] = (colDiffCounts[column] || 0) + 1;
    }
  }

  const sortedColDiff = Object.entries(colDiffCounts).sort((a, b) => b[1] - a[1]);
  const previewLimit = 12;
  const shownCols = sortedColDiff.slice(0, previewLimit);
  const hiddenCols = Math.max(0, sortedColDiff.length - shownCols.length);

  return {
    same,
    onlyInDbA,
    onlyInDbB,
    changed,
    totalKeys,
    netDelta: onlyInDbA - onlyInDbB,
    colDiffList: shownCols.map(([col, count]) => `${col}: ${count}`).join(', '),
    colDiffHiddenCount: hiddenCols,
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
      `Primeiro registro ${COMPARE_UI_DIFF_TYPES.added.directionLabel}: ${keyText || 'sem chave visivel'}`
    );
  }
  if (rows.removed.length) {
    const first = rows.removed[0];
    const keyText = keyColumns
      .map((key) => `${key}=${JSON.stringify((first.key || {})[key])}`)
      .join(', ');
    highlights.push(
      `Primeiro registro ${COMPARE_UI_DIFF_TYPES.removed.directionLabel}: ${keyText || 'sem chave visivel'}`
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

function buildCompareAnomalySignals(data, changedRows) {
  const compareColumns = data.compare_columns || [];
  const keyColumns = data.key_columns || [];
  const stateCols = ['STACON', 'NORMST', 'SOEHIS', 'CLASS'];
  const highImpactThreshold = 6;
  const stateTransitions = {};
  const keyMissing = [];
  const highImpact = [];
  const criticalCols = {};

  changedRows.forEach((row, index) => {
    const changedColumns = compareColumns.filter((column) =>
      valuesDifferent((row.a || {})[column], (row.b || {})[column])
    );
    if (!changedColumns.length) return;

    const keyText =
      keyColumns
        .map((key) => `${key}=${JSON.stringify((row.key || {})[key])}`)
        .join(', ') || `index_${index + 1}`;

    if (changedColumns.length >= highImpactThreshold) {
      highImpact.push({ key: keyText, count: changedColumns.length });
    }

    const hasKeyValue = keyColumns.some((key) => {
      const value = (row.key || {})[key];
      return value !== undefined && value !== null && String(value).trim() !== '';
    });
    if (!hasKeyValue) {
      keyMissing.push(keyText);
    }

    for (const col of changedColumns) {
      if (!criticalCols[col]) criticalCols[col] = 0;
      criticalCols[col] += 1;
    }

    const oldState = pickDomainField(row, stateCols);
    const newState = pickDomainField(
      {
        a: row.b || {},
        b: row.a || {},
      },
      stateCols
    );
    if (oldState || newState) {
      const transition = `${oldState || '-'} -> ${newState || '-'}`;
      stateTransitions[transition] = (stateTransitions[transition] || 0) + 1;
    }
  });

  const criticalTransition = Object.entries(stateTransitions)
    .map(([label, count]) => [label, count])
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  const topCriticalCols = Object.entries(criticalCols)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return {
    highImpact: highImpact.slice(0, 6),
    keyMissing: keyMissing.slice(0, 4),
    criticalTransition,
    topCriticalCols,
  };
}

function buildCompareValueSignals(data, changedRows) {
  const compareColumns = data.compare_columns || [];
  const nullTransitions = {};
  const numericDrift = {};

  changedRows.forEach((row) => {
    compareColumns.forEach((column) => {
      const valueA = (row.a || {})[column];
      const valueB = (row.b || {})[column];
      if (!valuesDifferent(valueA, valueB)) return;
      updateCompareValueSignals(
        column,
        valueA,
        valueB,
        nullTransitions,
        numericDrift
      );
    });
  });

  const topNullTransitions = Object.entries(nullTransitions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const topNumericDrift = Object.entries(numericDrift)
    .map(([column, info]) => ({
      column,
      count: info.count,
      sumAbsDelta: info.sumAbsDelta,
      maxAbsDelta: info.maxAbsDelta,
      maxSignedDelta: info.maxSignedDelta,
    }))
    .sort((a, b) => b.sumAbsDelta - a.sumAbsDelta)
    .slice(0, 6);

  return {
    topNullTransitions,
    topNumericDrift,
    nullTransitionsTotal: Object.values(nullTransitions).reduce(
      (acc, value) => acc + Number(value || 0),
      0
    ),
    numericDriftColumnsCount: Object.keys(numericDrift).length,
  };
}

function buildCompareDomainRiskSignals(changedRows) {
  const stateCols = ['STACON', 'NORMST', 'SOEHIS', 'CLASS'];
  const families = {};
  const transitions = {};

  changedRows.forEach((row, index) => {
    const changedColumns = (row && row.changed_columns) || [];
    const compareColumns = [
      ...new Set(
        Object.keys((row || {}).a || {}).concat(
          Object.keys((row || {}).b || {})
        )
      ),
    ];
    const diffCols = changedColumns.length
      ? changedColumns
      : compareColumns.filter((column) =>
          valuesDifferent((row.a || {})[column], (row.b || {})[column])
        );
    if (!diffCols.length) return;

    const oldState = pickDomainField(
      row,
      stateCols
    );
    const newState = pickDomainField(
      {
        a: row.b || {},
        b: row.a || {},
      },
      stateCols
    );
    const family =
      pickDomainField(row, ['PNLNAM', 'SUBNAM', 'DEVNAM']) || 'familia nao identificada';
    const signal = families[family] || {
      count: 0,
      score: 0,
      sample: `registro_${index + 1}`,
      transitions: {},
    };
    signal.count += 1;
    signal.score += diffCols.length + (oldState && newState && oldState !== newState ? 3 : 0);
    signal.sample = signal.sample || `registro_${index + 1}`;
    const transition = oldState || newState ? `${oldState || '-'} => ${newState || '-'}` : 'sem transicao';
    signal.transitions[transition] = (signal.transitions[transition] || 0) + 1;
    families[family] = signal;

    transitions[transition] = (transitions[transition] || 0) + 1;
  });

  const familyRisk = Object.entries(families)
    .map(([family, info]) => ({
      family,
      count: info.count,
      score: info.score,
      sample: info.sample,
      transitions: Object.entries(info.transitions || {}).sort((a, b) => b[1] - a[1]),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  const transitionRisk = Object.entries(transitions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return {
    familyRisk,
    transitionRisk,
  };
}

function buildCompareRiskSignals(data, changedRows) {
  const compareColumns = data.compare_columns || [];
  const keyColumns = data.key_columns || [];
  const stateCols = ['STACON', 'NORMST', 'SOEHIS', 'CLASS'];
  const riskRows = [];
  const domainIndex = {};

  changedRows.forEach((row, index) => {
    const changedColumns = compareColumns.filter((column) =>
      valuesDifferent((row.a || {})[column], (row.b || {})[column])
    );
    if (!changedColumns.length) return;

    const keyText =
      keyColumns.length
        ? keyColumns
            .map((key) => `${key}=${JSON.stringify((row.key || {})[key])}`)
            .join(', ')
        : `index_${index + 1}`;

    const oldState = pickDomainField(row, stateCols);
    const newState = pickDomainField(
      {
        a: row.b || {},
        b: row.a || {},
      },
      stateCols
    );
    const stateScore =
      oldState && newState && oldState !== newState ? 2 : 0;
    const changedScore = changedColumns.length;
    const riskScore = changedScore + stateScore;

    if (riskScore >= 4) {
      riskRows.push({
        key: keyText,
        score: riskScore,
        columns: changedColumns.slice(0, 5).join(', ') || 'sem coluna',
        transition:
          oldState && newState ? `${oldState} => ${newState}` : 'sem transicao',
      });
      domainIndex[keyText] = (domainIndex[keyText] || 0) + riskScore;
    }
  });

  const topRiskRows = riskRows
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);
  const repeatedRiskKeys = Object.entries(domainIndex)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return {
    topRiskRows,
    repeatedRiskKeys,
    riskRowCount: riskRows.length,
  };
}

function buildCompareSeveritySignals(summaryData, valueSignals, riskSignals) {
  const totalKeys = Number(summaryData.totalKeys || 0);
  const impactedKeys = Number(
    (summaryData.onlyInDbA || 0) + (summaryData.onlyInDbB || 0) + (summaryData.changed || 0)
  );
  const impactedPct = totalKeys > 0 ? (impactedKeys / totalKeys) * 100 : 0;
  const riskRowCount = Number((riskSignals && riskSignals.riskRowCount) || 0);
  const nullTransitionsTotal = Number(
    (valueSignals && valueSignals.nullTransitionsTotal) || 0
  );
  const numericDriftColumnsCount = Number(
    (valueSignals && valueSignals.numericDriftColumnsCount) || 0
  );

  let label = 'baixa';
  let badgeClass = 'same';
  if (impactedPct >= 50 || riskRowCount >= 4) {
    label = 'critica';
    badgeClass = 'removed';
  } else if (impactedPct >= 25 || riskRowCount >= 2 || nullTransitionsTotal >= 4) {
    label = 'alta';
    badgeClass = 'changed';
  } else if (impactedPct >= 10 || numericDriftColumnsCount >= 2) {
    label = 'media';
    badgeClass = 'added';
  } else if (impactedKeys === 0) {
    label = 'estavel';
    badgeClass = 'same';
  }

  const reasons = [];
  reasons.push(
    `${impactedKeys}/${totalKeys || 0} chave(s) impactadas (${impactedPct.toFixed(1)}%)`
  );
  if (riskRowCount > 0) reasons.push(`${riskRowCount} chave(s) com risco >= 4`);
  if (nullTransitionsTotal > 0) reasons.push(`${nullTransitionsTotal} transicao(oes) vazio/preenchido`);
  if (numericDriftColumnsCount > 0) reasons.push(`${numericDriftColumnsCount} coluna(s) com drift numerico`);
  return {
    label,
    badgeClass,
    reasonText: reasons.join(' · '),
  };
}

function buildCompareRecommendedActions(summaryData, anomalySignals, valueSignals, riskSignals) {
  const actions = [];
  const impactedPct = Number(summaryData && summaryData.totalKeys)
    ? ((Number(summaryData.changed || 0) + Number(summaryData.onlyInDbA || 0) + Number(summaryData.onlyInDbB || 0)) /
        Number(summaryData.totalKeys)) *
      100
    : 0;

  if ((anomalySignals.highImpact || []).length) {
    actions.push(
      `Revisar primeiro as chaves com alto impacto (topo da lista de anomalias prioritarias).`
    );
  }
  if ((riskSignals.topRiskRows || []).length) {
    actions.push(`Validar manualmente as chaves com risco operacional acima de 3.`);
  }
  if ((valueSignals.topNullTransitions || []).length) {
    actions.push(`Conferir transicoes de vazio/preenchido antes de promover alteracoes.`);
  }
  if ((valueSignals.topNumericDrift || []).length) {
    actions.push(`Auditar os maiores deltas numericos para evitar regressao de valores.`);
  }
  if (impactedPct >= 25) {
    actions.push(
      `Volume de mudanca alto (${impactedPct.toFixed(1)}%). Executar validacao por lote antes de aplicar em producao.`
    );
  }
  if (!actions.length) {
    actions.push('Sem sinal critico no recorte atual; manter monitoramento por amostragem.');
  }
  return actions.slice(0, 6);
}

function buildPriorityAnomalyItems(
  anomalySignals,
  riskSignals,
  valueSignals,
  domainRiskSignals
) {
  const items = [];

  (anomalySignals.highImpact || []).forEach((item) => {
    items.push({
      score: Number(item.count || 0) * 4,
      label: `Chave com alto impacto: ${item.key}`,
      detail: `${item.count} colunas alteradas`,
    });
  });

  (riskSignals.topRiskRows || []).forEach((item) => {
    items.push({
      score: Number(item.score || 0) * 3,
      label: `Risco operacional: ${item.key}`,
      detail: `${item.score} pontos · ${item.columns || 'sem colunas'}`,
    });
  });

  (valueSignals.topNumericDrift || []).forEach((item) => {
    items.push({
      score: Number(item.sumAbsDelta || 0),
      label: `Drift numerico: ${item.column}`,
      detail: `soma abs ${Number(item.sumAbsDelta || 0).toFixed(2)} · pico ${Number(item.maxSignedDelta || 0).toFixed(2)}`,
    });
  });

  (domainRiskSignals.transitionRisk || []).forEach((item) => {
    const label = item[0];
    const count = Number(item[1] || 0);
    items.push({
      score: count * 2,
      label: `Transicao concentrada: ${label}`,
      detail: `${count} ocorrencia(s)`,
    });
  });

  return items
    .sort((a, b) => b.score - a.score)
    .slice(0, 8);
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
  if (!summaryEl) return;
  const safe = escapeHtmlText;
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
  const anomalySignals = buildCompareAnomalySignals(data, changedRows);
  const domainSignals = buildCompareDomainSignals(changedRows);
  const riskSignals = buildCompareRiskSignals(data, changedRows);
  const domainRiskSignals = buildCompareDomainRiskSignals(changedRows);
  const valueSignals = buildCompareValueSignals(data, changedRows);
  const severitySignals = buildCompareSeveritySignals(
    summaryData,
    valueSignals,
    riskSignals
  );
  const recommendedActions = buildCompareRecommendedActions(
    summaryData,
    anomalySignals,
    valueSignals,
    riskSignals
  );
  const priorityAnomalies = buildPriorityAnomalyItems(
    anomalySignals,
    riskSignals,
    valueSignals,
    domainRiskSignals
  );
  const totalChanged = Number(summaryData.changed || changedRows.length || 0);
  const totalKeys = Number(summaryData.totalKeys || 0);
  const changedDensity = totalKeys > 0 ? ((totalChanged / totalKeys) * 100).toFixed(1) : '0.0';
  const dbALabel = shortDbLabel(data.db1);
  const dbBLabel = shortDbLabel(data.db2);
  const rowsA = Number((data.summary || {}).rows_a || 0);
  const rowsB = Number((data.summary || {}).rows_b || 0);
  const netDelta = Number(summaryData.netDelta || 0);
  const topKeysHtml = review.topKeys.length
    ? `<div class="report-review-list">${review.topKeys
        .map(
          ([keyText, meta]) =>
            `<div class="report-review-item"><strong>${safe(keyText)}</strong><span>${meta.count} campos mudaram${meta.columns.length ? ' · ' + meta.columns.slice(0, 5).map((item) => safe(item)).join(', ') : ''}</span></div>`
        )
        .join('')}</div>`
    : '';
  const topColumnsHtml = review.topColumns.length
    ? `<div class="report-review-list">${review.topColumns
        .map(
          ([column, count]) =>
            `<div class="report-review-item"><strong>${safe(column)}</strong><span>${count} chaves alteradas</span></div>`
        )
        .join('')}</div>`
    : '';
  const patternsHtml = patterns.length
    ? `<div class="report-review-list">${patterns
        .map(
          ([label, meta]) =>
            `<div class="report-review-item"><strong>${safe(label)}</strong><span>${meta.count} chave(s) · exemplo: ${safe(meta.sample)}</span></div>`
        )
        .join('')}</div>`
    : '';
  const familyHtml = domainSignals.topFamilies.length
    ? `<div class="report-review-list">${domainSignals.topFamilies
        .map(
          ([family, count]) =>
            `<div class="report-review-item"><strong>${safe(family)}</strong><span>${count} chave(s) alteradas</span></div>`
        )
        .join('')}</div>`
    : '';
  const transitionsHtml = domainSignals.topTransitions.length
    ? `<div class="report-review-list">${domainSignals.topTransitions
        .map(
          ([label, count]) =>
            `<div class="report-review-item"><strong>${safe(label)}</strong><span>${count} ocorrencia(s)</span></div>`
        )
        .join('')}</div>`
    : '';
  const anomalyHighImpactHtml = anomalySignals.highImpact.length
    ? `<div class="result-col-diff"><strong>Mudancas com alto impacto (chaves com mais alteracoes):</strong>${anomalySignals.highImpact
        .map(
          (it) =>
            `<div class="report-review-item"><strong>${safe(it.key)}</strong><span>${it.count} colunas alteradas</span></div>`
        )
        .join('')}</div>`
    : '';
  const anomalyMissingKeysHtml = anomalySignals.keyMissing.length
    ? `<div class="result-col-diff"><strong>Chaves sem identificacao primaria completa:</strong>${anomalySignals.keyMissing
        .map((item) => `<div class="report-review-item">${safe(item)}</div>`)
        .join('')}</div>`
    : '';
  const anomalyTransitionHtml = anomalySignals.criticalTransition.length
    ? `<div class="result-col-diff"><strong>Transicoes de estado mais impactantes:</strong>${anomalySignals.criticalTransition
        .map(
          ([label, count]) =>
            `<div class="report-review-item"><strong>${safe(label)}</strong><span>${count} registro(s)</span></div>`
        )
        .join('')}</div>`
    : '';
  const anomalyColsHtml = anomalySignals.topCriticalCols.length
    ? `<div class="result-col-diff"><strong>Colunas com maior concentracao de mudanca:</strong>${anomalySignals.topCriticalCols
        .map(
          ([col, count]) =>
            `<div class="report-review-item"><strong>${safe(col)}</strong><span>${count} mudancas</span></div>`
        )
        .join('')}</div>`
    : '';
  const anomalyRiskRowsHtml = riskSignals.topRiskRows.length
    ? `<div class="result-col-diff"><strong>Chaves com risco operacional acima de 3:</strong>${riskSignals.topRiskRows
        .map(
          (item) =>
            `<div class="report-review-item"><strong>${safe(item.key)}</strong><span>${item.score} ponto(s) · ${safe(item.columns)} · ${safe(item.transition)}</span></div>`
        )
        .join('')}</div>`
    : '';
  const anomalyConcentrationHtml = riskSignals.repeatedRiskKeys.length
    ? `<div class="result-col-diff"><strong>Concentracao repetitiva de risco:</strong>${riskSignals.repeatedRiskKeys
        .map(
          ([keyText, score]) =>
            `<div class="report-review-item"><strong>${safe(keyText)}</strong><span>${score} pontos concentrados</span></div>`
        )
        .join('')}</div>`
    : '';
  const domainRiskHtml = domainRiskSignals.familyRisk.length
    ? `<div class="result-col-diff"><strong>Familias com risco operacional:</strong>${domainRiskSignals.familyRisk
        .map((item) => {
          const transitionText = item.transitions.length
            ? ` · transicao principal ${safe(item.transitions[0][0])} (${item.transitions[0][1]})`
            : '';
          return `<div class="report-review-item"><strong>${safe(item.family)}</strong><span>${item.score} pontos · ${item.count} chave(s)${transitionText}</span></div>`;
        })
        .join('')}</div>`
    : '';
  const domainTransitionHtml = domainRiskSignals.transitionRisk.length
    ? `<div class="result-col-diff"><strong>Transicoes operacionais com concentracao:</strong>${domainRiskSignals.transitionRisk
        .map(
          ([transition, count]) =>
            `<div class="report-review-item"><strong>${safe(transition)}</strong><span>${count} ocorrencia(s)</span></div>`
        )
        .join('')}</div>`
    : '';
  const nullTransitionsHtml = valueSignals.topNullTransitions.length
    ? `<div class="result-col-diff"><strong>Mudancas vazio/preenchido (top):</strong>${valueSignals.topNullTransitions
        .map(
          ([label, count]) =>
            `<div class="report-review-item"><strong>${safe(label)}</strong><span>${count} ocorrencia(s)</span></div>`
        )
        .join('')}</div>`
    : '';
  const numericDriftHtml = valueSignals.topNumericDrift.length
    ? `<div class="result-col-diff"><strong>Deltas numericos relevantes (top):</strong>${valueSignals.topNumericDrift
        .map(
          (item) =>
            `<div class="report-review-item"><strong>${safe(item.column)}</strong><span>${item.count} mudanca(s) · soma abs ${safe(item.sumAbsDelta.toFixed(2))} · pico ${safe(item.maxSignedDelta.toFixed(2))}</span></div>`
        )
        .join('')}</div>`
    : '';
  const priorityAnomaliesHtml = priorityAnomalies.length
    ? `<div class="result-col-diff"><strong>Anomalias prioritarias (ordenadas por impacto):</strong>${priorityAnomalies
        .map(
          (item) =>
            `<div class="report-review-item"><strong>${safe(item.label)}</strong><span>${safe(item.detail)} · score ${safe(item.score.toFixed(2))}</span></div>`
        )
        .join('')}</div>`
    : '';
  const recommendedActionsHtml = recommendedActions.length
    ? `<div class="result-col-diff"><strong>Acoes recomendadas:</strong>${recommendedActions
        .map(
          (action) => `<div class="report-review-item"><span>${safe(action)}</span></div>`
        )
        .join('')}</div>`
    : '';
  summaryEl.innerHTML = `
    <div class="result-summary-card">
      <div class="result-summary-grid">
        <div><strong>Tabela analisada:</strong> ${escapeHtmlText(data.table)}</div>
        <div><strong>Chaves (K):</strong> ${(data.key_columns || []).map((key) => escapeHtmlText(key)).join(', ')}</div>
        <div><strong>A (NOVO):</strong> ${escapeHtmlText(dbALabel)} · <strong>B (ANTIGO):</strong> ${escapeHtmlText(dbBLabel)}</div>
        <div><strong>Volume bruto:</strong> ${rowsA} registros em A · ${rowsB} registros em B · saldo ${netDelta >= 0 ? '+' : ''}${netDelta}</div>
        <div id="compareViewModeAnchor"></div>
        <div>
          <strong>Visao geral:</strong> ${summaryData.totalKeys} registros (chaves) analisados
          <div class="result-badges-row">
            <span class="badge same">${summaryData.same} mantidos (iguais em A e B)</span>
            <span class="badge added">+${summaryData.onlyInDbA} novos (apenas em A - banco NOVO)</span>
            <span class="badge removed">-${summaryData.onlyInDbB} removidos (apenas em B - banco ANTIGO)</span>
            <span class="badge changed">±${summaryData.changed} alterados (chave existe em ambos, mas com diferenca)</span>
          </div>
        </div>
        ${summaryData.colDiffList ? `<div class="result-col-diff"><strong>Colunas com diferenca (qtd. de registros alterados):</strong> ${escapeHtmlText(summaryData.colDiffList)}${summaryData.colDiffHiddenCount ? ` · (+${summaryData.colDiffHiddenCount} coluna(s) adicionais)` : ''}</div>` : ''}
        ${highlights.length ? `<div class="result-col-diff"><strong>Pistas operacionais:</strong><br>${highlights.map((item) => escapeHtmlText(item)).join('<br>')}</div>` : ''}
        ${alerts.length ? `<div class="result-col-diff"><strong>Colunas sensiveis para revisar:</strong><br>${alerts.map((item) => escapeHtmlText(item)).join('<br>')}</div>` : ''}
        ${topKeysHtml ? `<div class="result-col-diff"><strong>Chaves para revisar primeiro:</strong>${topKeysHtml}</div>` : ''}
        ${topColumnsHtml ? `<div class="result-col-diff"><strong>Colunas mais impactadas:</strong>${topColumnsHtml}</div>` : ''}
        ${patternsHtml ? `<div class="result-col-diff"><strong>Padroes de alteracao:</strong>${patternsHtml}</div>` : ''}
        ${familyHtml ? `<div class="result-col-diff"><strong>Familias mais afetadas:</strong>${familyHtml}</div>` : ''}
        ${transitionsHtml ? `<div class="result-col-diff"><strong>Transicoes de estado observadas:</strong>${transitionsHtml}</div>` : ''}
        <div class="result-col-diff"><strong>Indice de divergencia:</strong> ${changedDensity}% das chaves por status alterado</div>
        <div class="result-col-diff"><strong>Prioridade de revisao:</strong> <span class="badge ${severitySignals.badgeClass}">${safe(severitySignals.label)}</span> ${safe(severitySignals.reasonText)}</div>
        ${recommendedActionsHtml}
        ${priorityAnomaliesHtml}
        ${anomalyHighImpactHtml}
        ${anomalyColsHtml}
        ${anomalyTransitionHtml}
        ${anomalyMissingKeysHtml}
        ${domainRiskHtml}
        ${domainTransitionHtml}
        ${nullTransitionsHtml}
        ${numericDriftHtml}
        ${anomalyRiskRowsHtml}
        ${anomalyConcentrationHtml}
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
      title: `Novas - so em A (${COMPARE_UI_DIFF_TYPES.removed.sourceLabel})`,
      rows: rows.removed,
    },
    {
      type: 'removed',
      title: `Removidas - so em B (${COMPARE_UI_DIFF_TYPES.added.sourceLabel})`,
      rows: rows.added,
    },
  ];
}

function buildRowSummary(data, row, isRangerSostat) {
  const keyParts = [];
  for (const key of data.key_columns || []) {
    keyParts.push(
      `${escapeHtmlText(key)}=${escapeHtmlText(JSON.stringify(row.key[key]))}`
    );
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
        extraParts.push(
          `${escapeHtmlText(field)}=${escapeHtmlText(shortValue(value, 40))}`
        );
      }
    }
  }

  return { keyParts, extraParts };
}

function appendFieldLine(target, column, valueA, valueB, changed) {
  const line = document.createElement('div');
  line.className = 'diff-field-line';
  const safeColumn = escapeHtmlText(column);
  const safeA = escapeHtmlText(shortValue(valueA));
  const safeB = escapeHtmlText(shortValue(valueB));
  if (changed) {
    line.innerHTML = `<strong>${safeColumn}:</strong> ${safeA} -> ${safeB}`;
  } else {
    line.innerHTML = `<span style="opacity:0.7;"><strong>${safeColumn}:</strong> ${safeA} (sem diferenca)</span>`;
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

    let sideValue;
    if (sectionType === 'added') {
      sideValue = row.a[column];
    } else {
      sideValue = row.b[column];
    }
    const line = document.createElement('div');
    line.className = 'diff-field-line';
    line.innerHTML = `<strong>${escapeHtmlText(column)}:</strong> ${escapeHtmlText(shortValue(sideValue))}`;
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
    const typeConfig = COMPARE_UI_DIFF_TYPES[row.type] || COMPARE_UI_DIFF_TYPES.changed;
    const visualType = typeConfig.badgeClass || row.type;
    const typeLabel = escapeHtmlText(
      `${typeConfig.uiLabel} (${typeConfig.directionLabel})`
    );
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
  const summaryCard = document.getElementById('compareViewModeAnchor');
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
