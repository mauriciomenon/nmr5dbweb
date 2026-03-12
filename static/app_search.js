// === Funcoes utilitarias exportadas para HTML / inline_handlers ===

function setBusyButton(btn, busyText, idleText) {
  if (!btn) return () => {};
  const original = idleText || btn.textContent;
  btn.disabled = true;
  btn.textContent = busyText;
  return () => {
    btn.disabled = false;
    btn.textContent = original;
  };
}

function setSearchMeta(text, level) {
  const el = $('searchMeta');
  if (!el) return;
  el.textContent = text || '';
  el.classList.remove('warn', 'error');
  if (level === 'warn' || level === 'error') {
    el.classList.add(level);
  }
}

function onSelectRowClick(ev, nameEnc) {
  if (
    ev &&
    ev.target &&
    ev.target.closest &&
    ev.target.closest('.file-actions')
  )
    return;
  selectUpload(nameEnc, null);
}

async function deleteUpload(nameEnc, btn) {
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
}

async function selectUpload(nameEnc, btn) {
  const name = decodeURIComponent(nameEnc);
  const msg = $('uploadMsg');
  const restoreBtn = setBusyButton(
    btn,
    'Selecionando...',
    btn ? btn.textContent : 'Selecionar'
  );
  if (msg) msg.textContent = 'Selecionando: ' + name;
  try {
    const j = await apiJSON('/admin/select', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: name }),
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
      setFlowBanner(
        'Nao foi possivel selecionar o arquivo. Tente novamente.',
        'error'
      );
      logUi('ERROR', 'select db falhou');
    }
  } catch (e) {
    if (msg) msg.textContent = 'Erro ao selecionar DB';
    setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
    logUi('ERROR', 'select db falhou');
  } finally {
    restoreBtn();
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
      body: JSON.stringify({ filename: name }),
    });
    if (j && j.ok) {
      if (msg) msg.textContent = 'DB selecionado: ' + name;
      manualFlowOverride = '';
      setFlowBanner('', '');
      await refreshUiState();
    } else {
      const err = (j && j.error) || 'falha ao selecionar';
      if (msg) msg.textContent = 'Erro ao selecionar: ' + err;
      setFlowBanner(
        'Nao foi possivel selecionar o arquivo. Tente novamente.',
        'error'
      );
      logUi('ERROR', 'select db falhou');
    }
  } catch (e) {
    if (msg) msg.textContent = 'Erro ao selecionar DB';
    setFlowBanner('Erro ao selecionar DB. Verifique o servidor.', 'error');
    logUi('ERROR', 'select db falhou');
  }
}

async function doSearch(opts) {
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
}

function tableTagId(name) {
  return 'tag-' + encodeURIComponent(name);
}

window.setBusyButton = setBusyButton;
window.setSearchMeta = setSearchMeta;
window.onSelectRowClick = onSelectRowClick;
window.deleteUpload = deleteUpload;
window.selectUpload = selectUpload;
window.selectDbFromTab = selectDbFromTab;
window.doSearch = doSearch;
window.tableTagId = tableTagId;
