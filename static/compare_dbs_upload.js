async function restoreFromSavedState() {
  resetFlowToInitial();
  let saved = null;
  try {
    const raw = localStorage.getItem(compareDbState.compareStateKey);
    if (!raw) return;
    saved = JSON.parse(raw);
    if (!saved || typeof saved !== 'object') return;
  } catch (e) {
    console.warn('Estado salvo invalido, ignorando.', e);
    return;
  }

  const {
    db1Input,
    db2Input,
    tableSelect,
  } = getCompareFormRefs();
  applyCompareFormState(saved);

  compareDbState.tablesLoadedOnce = !!saved.tablesLoadedOnce;
  compareDbState.currentOpenStep = saved.currentOpenStep || 1;
  compareDbState.lastComparePayload = saved.lastComparePayload || null;
  compareDbState.lastCompareMeta = saved.lastCompareMeta || null;

  updateRowLimitState();
  if (compareDbState.currentOpenStep) {
    setStepOpen(compareDbState.currentOpenStep);
  } else {
    setStepOpen(1);
  }

  if (
    saved.tablesLoadedOnce &&
    db1Input &&
    db2Input &&
    db1Input.value &&
    db2Input.value
  ) {
    try {
      const selectedBefore = saved.table || (tableSelect ? tableSelect.value : '');
      const headData = await postJson('/api/compare_db_tables', {
        db1_path: db1Input.value,
        db2_path: db2Input.value,
      });
      compareDbState.tablesMeta = headData.tables || [];
      if (compareDbState.tablesMeta.length) {
        tableSelect.innerHTML = '';
        let restoredSelection = false;
        for (const t of compareDbState.tablesMeta) {
          const opt = document.createElement('option');
          opt.value = t.name;
          opt.textContent = t.name;
          if (selectedBefore && t.name === selectedBefore) {
            opt.selected = true;
            restoredSelection = true;
          }
          tableSelect.appendChild(opt);
        }
        if (!restoredSelection && tableSelect.options.length) {
          tableSelect.selectedIndex = 0;
        }
      }
    } catch (e) {
      console.warn(
        'Falha ao recarregar tabelas em comum a partir do estado salvo.',
        e
      );
    }
  }

  if (
    compareDbState.lastComparePayload &&
    compareDbState.lastComparePayload.table
  ) {
    try {
      const data = await postJson(
        '/api/compare_db_rows',
        compareDbState.lastComparePayload
      );
      renderResult(data);
      setFlowHint(
        'Ultima comparacao restaurada. Voce pode ajustar filtros ou comparar novamente.',
        'info'
      );
      setStepState('stepPickFiles', 'Concluido', 'done');
      setStepState(
        'stepLoadTables',
        compareDbState.tablesLoadedOnce ? 'Concluido' : 'Aguardando',
        compareDbState.tablesLoadedOnce ? 'done' : null
      );
      setStepState('stepCompare', 'Concluido', 'done');
      setStepOpen(3);
    } catch (e) {
      console.warn(
        'Nao foi possivel restaurar resultado anterior da comparacao.',
        e
      );
    }
  }
}

async function handleFileUpload(side) {
  const input = document.getElementById(
    side === 'A' ? 'fileInputA' : 'fileInputB'
  );
  const nameSpan = document.getElementById(
    side === 'A' ? 'fileNameA' : 'fileNameB'
  );
  const pathInput = document.getElementById(
    side === 'A' ? 'db1Path' : 'db2Path'
  );
  const previousPath = pathInput && pathInput.value ? String(pathInput.value).trim() : '';
  const btn = document.getElementById(
    side === 'A' ? 'btnUploadA' : 'btnUploadB'
  );
  if (!input || !input.files || !input.files.length) return;
  if (!nameSpan || !pathInput) return;
  const file = input.files[0];
  nameSpan.textContent = file.name;

  const fd = new FormData();
  fd.append('file', file);
  nameSpan.textContent = file.name + ' (enviando...)';
  setUploadStatus(
    `Enviando "${file.name}" para Banco ${side}... Aguarde, o upload pode levar alguns segundos ou minutos dependendo do tamanho.`
  );
  setFlowHint(`Enviando arquivo do Banco ${side}...`, 'info');
  setStepState('stepPickFiles', 'Enviando arquivo...', 'active');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Enviando...';
  }

  if (compareDbState.uploadTimeouts[side]) {
    clearTimeout(compareDbState.uploadTimeouts[side]);
  }
  compareDbState.uploadTimeouts[side] = setTimeout(() => {
    setUploadStatus(
      `O upload do Banco ${side} esta levando mais de 60 segundos. Se continuar assim, pode ter havido um travamento. Verifique a conexao e o tamanho do arquivo.`,
      true
    );
  }, 60000);

  try {
    const res = await fetch('/admin/upload', { method: 'POST', body: fd });
    const rawBody = await res.text();
    let data = {};
    if (rawBody) {
      try {
        data = JSON.parse(rawBody);
      } catch (parseErr) {
        const statusLabel = `${res.status} ${res.statusText}`.trim();
        const parseError = new Error(
          `Resposta invalida do servidor no upload (${statusLabel || 'sem status'}).`
        );
        parseError.parseCause = parseErr;
        throw parseError;
      }
    }
    if (!res.ok || data.error) {
      const fallbackMsg = res.statusText || `HTTP ${res.status}`;
      throw new Error(data.error || fallbackMsg);
    }
    if (!data.db_path && !data.output) {
      throw new Error('Upload sem caminho de banco retornado pelo servidor.');
    }
    if (data.db_path) {
      pathInput.value = data.db_path;
      nameSpan.textContent = file.name + ' (carregado)';
      setUploadStatus(`Upload do Banco ${side} concluido com sucesso.`);
    } else if (data.output) {
      pathInput.value = data.output;
      nameSpan.textContent = file.name + ' (carregado)';
      setUploadStatus(`Upload do Banco ${side} concluido com sucesso.`);
    }
    const currentPathValue = String(pathInput.value || '').trim();
    const nextPath = currentPathValue;
    if (nextPath !== previousPath) {
      compareDbState.lastComparePayload = null;
      compareDbState.lastCompareMeta = null;
      compareDbState.tablesMeta = [];
      compareDbState.tablesLoadedOnce = false;
      compareDbState.tablesOverviewCache = null;
      compareDbState.tablesOverviewVisible = false;
      const localTableSelect = document.getElementById('tableSelect');
      if (localTableSelect) {
        localTableSelect.innerHTML =
          '<option value="">carregue os arquivos A e B e clique em "1) Carregar tabelas em comum"</option>';
      }
      const overviewContainer = document.getElementById('tablesOverview');
      if (overviewContainer) {
        overviewContainer.style.display = 'none';
      }
      const overviewBtn = document.getElementById('btnTablesOverview');
      if (overviewBtn) {
        overviewBtn.textContent = 'Mapa geral das tabelas';
      }
    }

    const otherPathInput = document.getElementById(
      side === 'A' ? 'db2Path' : 'db1Path'
    );
    if (
      currentPathValue &&
      otherPathInput &&
      otherPathInput.value.trim()
    ) {
      setFlowHint(
        'Arquivos A e B ja informados. Agora carregue as tabelas em comum.',
        'info'
      );
      setStepState('stepPickFiles', 'Concluido', 'done');
      setStepState('stepLoadTables', 'Pronto para carregar', 'active');
    }
    saveCompareState();
  } catch (err) {
    console.error(err);
    nameSpan.textContent = file.name + ' (erro ao enviar)';
    setUploadStatus(`Erro ao enviar Banco ${side}: ${err.message}`, true);
    setFlowHint(`Erro ao enviar Banco ${side}: ${err.message}`, 'error');
    setStepState('stepPickFiles', 'Erro no upload', 'warn');
    alert('Erro ao enviar arquivo: ' + err.message);
  } finally {
    if (compareDbState.uploadTimeouts[side]) {
      clearTimeout(compareDbState.uploadTimeouts[side]);
      compareDbState.uploadTimeouts[side] = null;
    }
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Escolher arquivo...';
    }
  }
}

function setupCompareUploadBindings() {
  const fa = document.getElementById('fileInputA');
  const fb = document.getElementById('fileInputB');
  if (fa) fa.addEventListener('change', () => handleFileUpload('A'));
  if (fb) fb.addEventListener('change', () => handleFileUpload('B'));

  const rowLimitCb = document.getElementById('rowLimitEnabled');
  if (rowLimitCb) {
    rowLimitCb.addEventListener('change', updateRowLimitState);
    updateRowLimitState();
  }
  const statefulInputs = [
    'db1Path',
    'db2Path',
    'keyColumns',
    'compareColumns',
    'keyFilter',
    'filterChanged',
    'filterAdded',
    'filterRemoved',
    'filterColumn',
    'rowLimit',
    'rowLimitEnabled',
    'tableSelect',
  ];
  for (const id of statefulInputs) {
    const el = document.getElementById(id);
    if (!el) continue;
    const evt =
      el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input';
    el.addEventListener(evt, () => saveCompareState());
  }

  const helpBtn = document.getElementById('openHelpCompare');
  if (helpBtn) {
    helpBtn.addEventListener('click', () => {
      const box = document.getElementById('helpCompareBox');
      if (!box) return;
      const isHidden = box.style.display === 'none' || box.style.display === '';
      box.style.display = isHidden ? 'block' : 'none';
    });
  }
}

window.restoreFromSavedState = restoreFromSavedState;
window.handleFileUpload = handleFileUpload;
window.setupCompareUploadBindings = setupCompareUploadBindings;
