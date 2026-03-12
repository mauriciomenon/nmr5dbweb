// Compare page logic extracted from compare_dbs.html

    let tablesMeta = [];
    let lastComparePayload = null;
    let lastCompareMeta = null;
    const uploadTimeouts = { A: null, B: null };
    let tablesTimeout = null;
    let currentOpenStep = 1;
    let tablesLoadedOnce = false;
    const compareStateKey = 'duckdb_compare_dbs_state_v1';
    let tablesOverviewCache = null;
    let tablesOverviewVisible = false;

    function setFlowHint(message, variant = 'info') {
      const hintEl = document.getElementById('flowHint');
      if (!hintEl) return;
      hintEl.textContent = message || '';
      hintEl.className = 'flow-hint';
      if (['info', 'warn', 'error'].includes(variant)) {
        hintEl.classList.add(variant);
      }
    }

    function setStepState(stepId, statusText, state) {
      let cardId = null;
      let statusSpanId = null;
      if (stepId === 'stepPickFiles') {
        cardId = 'step1Card';
        statusSpanId = 'step1Status';
      } else if (stepId === 'stepLoadTables') {
        cardId = 'step2Card';
        statusSpanId = 'step2Status';
      } else if (stepId === 'stepCompare') {
        cardId = 'step3Card';
        statusSpanId = 'step3Status';
      } else {
        return;
      }
      const card = document.getElementById(cardId);
      const statusEl = document.getElementById(statusSpanId);
      if (!card || !statusEl) return;
      if (typeof statusText === 'string' && statusText.length) {
        statusEl.textContent = statusText;
      }
      card.classList.remove('step-done', 'step-active', 'step-warn');
      if (state === 'done') card.classList.add('step-done');
      if (state === 'active') card.classList.add('step-active');
      if (state === 'warn') card.classList.add('step-warn');
    }

    function setStepOpen(step) {
      currentOpenStep = step;
      const steps = [1, 2, 3];
      for (const n of steps) {
        const card = document.getElementById('step' + n + 'Card');
        if (!card) continue;
        if (step === n) {
          card.classList.add('step-open');
        } else {
          card.classList.remove('step-open');
        }
      }
    }

    function toggleStep(step) {
      if (currentOpenStep === step) {
        setStepOpen(null);
      } else {
        setStepOpen(step);
      }
    }

    function resetFlowToInitial() {
      setFlowHint('Comece escolhendo os arquivos A e B em .duckdb.', 'info');
      setStepState('stepPickFiles', 'Pendente', 'active');
      setStepState('stepLoadTables', 'Aguardando', null);
      setStepState('stepCompare', 'Aguardando', null);
      setStepOpen(1);
    }

    function updateRowLimitState() {
      const cb = document.getElementById('rowLimitEnabled');
      const input = document.getElementById('rowLimit');
      if (!cb || !input) return;
      const enabled = cb.checked;
      input.disabled = !enabled;
      input.style.opacity = enabled ? '1' : '0.6';
    }

    function setUploadStatus(message, isError = false) {
      const el = document.getElementById('uploadStatus');
      if (!el) return;
      el.textContent = message || '';
      el.style.color = isError ? '#fecaca' : '#9ca3af';
    }

    function getRunCompareButton() {
      return document.getElementById('runCompareBtn');
    }

    function getCompareActionButtons() {
      return {
        loadTables: document.getElementById('btnLoadTables'),
        runCompare: document.getElementById('runCompareBtn'),
        tablesOverview: document.getElementById('btnTablesOverview'),
        exportComparison: document.getElementById('btnExportComparison'),
      };
    }

    function setButtonBusy(btn, busyText, idleText) {
      if (!btn) return () => {};
      const original = idleText || btn.textContent;
      btn.disabled = true;
      btn.textContent = busyText;
      return () => {
        btn.disabled = false;
        btn.textContent = original;
      };
    }

    async function postJson(path, payload) {
      const resp = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      let data = null;
      try {
        data = await resp.json();
      } catch (error) {
        data = null;
      }
      if (!resp.ok) {
        const apiMsg = data && (data.message || data.error);
        const err = new Error(apiMsg || ('resposta HTTP ' + resp.status));
        err.payload = data;
        err.status = resp.status;
        throw err;
      }
      return data;
    }

    function setCompareBusy(statusText, flowText, stepText, slowText) {
      const statusEl = document.getElementById('statusCompare');
      const btn = getRunCompareButton();
      if (statusEl) {
        statusEl.textContent = statusText;
      }
      setFlowHint(flowText, 'info');
      setStepState('stepCompare', stepText, 'active');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Comparando...';
      }
      return setTimeout(() => {
        if (statusEl) {
          statusEl.textContent = slowText;
        }
      }, 60000);
    }

    function clearCompareBusy(timeoutId, buttonText = 'Comparar tabela') {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      const btn = getRunCompareButton();
      if (btn) {
        btn.disabled = false;
        btn.textContent = buttonText;
      }
    }

    function setCompareStatus(text, level = 'info') {
      const statusEl = document.getElementById('statusCompare');
      if (!statusEl) return;
      statusEl.textContent = text || '';
      statusEl.classList.remove('warn', 'error');
      if (level === 'warn' || level === 'error') {
        statusEl.classList.add(level);
      }
    }

    function updateLastCompareMeta(data, fallbackPage = 1) {
      lastCompareMeta = {
        total_filtered_rows: typeof data.total_filtered_rows === 'number' ? data.total_filtered_rows : (data.row_count || 0),
        page: data.page || fallbackPage,
        total_pages: data.total_pages || 1,
      };
    }

    function saveCompareState() {
      try {
        const db1Input = document.getElementById('db1Path');
        const db2Input = document.getElementById('db2Path');
        const tableSelect = document.getElementById('tableSelect');
        const keyCols = document.getElementById('keyColumns');
        const cmpCols = document.getElementById('compareColumns');
        const keyFilterEl = document.getElementById('keyFilter');
        const cbChanged = document.getElementById('filterChanged');
        const cbAdded = document.getElementById('filterAdded');
        const cbRemoved = document.getElementById('filterRemoved');
        const colSelect = document.getElementById('filterColumn');
        const rowLimitEl = document.getElementById('rowLimit');
        const rowLimitEnabledEl = document.getElementById('rowLimitEnabled');

        const state = {
          db1Path: db1Input ? db1Input.value : '',
          db2Path: db2Input ? db2Input.value : '',
          table: tableSelect ? tableSelect.value : '',
          keyColumns: keyCols ? keyCols.value : '',
          compareColumns: cmpCols ? cmpCols.value : '',
          keyFilter: keyFilterEl ? keyFilterEl.value : '',
          filterChanged: cbChanged ? cbChanged.checked : true,
          filterAdded: cbAdded ? cbAdded.checked : true,
          filterRemoved: cbRemoved ? cbRemoved.checked : true,
          filterColumn: colSelect ? colSelect.value : '',
          rowLimit: rowLimitEl ? rowLimitEl.value : '',
          rowLimitEnabled: rowLimitEnabledEl ? rowLimitEnabledEl.checked : true,
          tablesLoadedOnce,
          currentOpenStep,
          lastComparePayload,
          lastCompareMeta,
        };
        localStorage.setItem(compareStateKey, JSON.stringify(state));
      } catch (e) {
        console.warn('Nao foi possivel salvar estado da comparacao:', e);
      }
    }

    async function restoreFromSavedState() {
      resetFlowToInitial();
      let saved = null;
      try {
        const raw = localStorage.getItem(compareStateKey);
        if (!raw) return;
        saved = JSON.parse(raw);
      } catch (e) {
        console.warn('Estado salvo invalido, ignorando.', e);
        return;
      }

      const db1Input = document.getElementById('db1Path');
      const db2Input = document.getElementById('db2Path');
      const tableSelect = document.getElementById('tableSelect');
      const keyCols = document.getElementById('keyColumns');
      const cmpCols = document.getElementById('compareColumns');
      const keyFilterEl = document.getElementById('keyFilter');
      const cbChanged = document.getElementById('filterChanged');
      const cbAdded = document.getElementById('filterAdded');
      const cbRemoved = document.getElementById('filterRemoved');
      const colSelect = document.getElementById('filterColumn');
      const rowLimitEl = document.getElementById('rowLimit');
      const rowLimitEnabledEl = document.getElementById('rowLimitEnabled');

      if (db1Input && typeof saved.db1Path === 'string') db1Input.value = saved.db1Path;
      if (db2Input && typeof saved.db2Path === 'string') db2Input.value = saved.db2Path;
      if (keyCols && typeof saved.keyColumns === 'string') keyCols.value = saved.keyColumns;
      if (cmpCols && typeof saved.compareColumns === 'string') cmpCols.value = saved.compareColumns;
      if (keyFilterEl && typeof saved.keyFilter === 'string') keyFilterEl.value = saved.keyFilter;
      if (cbChanged && typeof saved.filterChanged === 'boolean') cbChanged.checked = saved.filterChanged;
      if (cbAdded && typeof saved.filterAdded === 'boolean') cbAdded.checked = saved.filterAdded;
      if (cbRemoved && typeof saved.filterRemoved === 'boolean') cbRemoved.checked = saved.filterRemoved;
      if (colSelect && typeof saved.filterColumn === 'string') colSelect.value = saved.filterColumn;
      if (rowLimitEl && typeof saved.rowLimit === 'string') rowLimitEl.value = saved.rowLimit;
      if (rowLimitEnabledEl && typeof saved.rowLimitEnabled === 'boolean') rowLimitEnabledEl.checked = saved.rowLimitEnabled;

      tablesLoadedOnce = !!saved.tablesLoadedOnce;
      currentOpenStep = saved.currentOpenStep || 1;
      lastComparePayload = saved.lastComparePayload || null;
      lastCompareMeta = saved.lastCompareMeta || null;

      updateRowLimitState();

      if (currentOpenStep) {
        setStepOpen(currentOpenStep);
      } else {
        setStepOpen(1);
      }

      // se já havia caminhos de bancos e as tabelas foram carregadas antes, podemos
      // tentar recarregar automaticamente, mas apenas se os arquivos ainda existirem.
      if (saved.tablesLoadedOnce && db1Input && db2Input && db1Input.value && db2Input.value) {
        try {
          const headData = await postJson('/api/compare_db_tables', {
            db1_path: db1Input.value,
            db2_path: db2Input.value,
          });
          tablesMeta = headData.tables || [];
          if (!tablesMeta.length) {
            console.warn('Nenhuma tabela em comum ao restaurar estado salvo.');
          } else {
            tableSelect.innerHTML = '';
            for (const t of tablesMeta) {
              const opt = document.createElement('option');
              opt.value = t.name;
              opt.textContent = t.name;
              tableSelect.appendChild(opt);
            }
          }
        } catch (e) {
          console.warn('Falha ao recarregar tabelas em comum a partir do estado salvo.', e);
        }
      }

      // se havia uma comparação concluída antes, tenta reconstruir o resultado
      if (lastComparePayload && lastComparePayload.table) {
        try {
          const data = await postJson('/api/compare_db_rows', lastComparePayload);
          renderResult(data);
          setFlowHint('Ultima comparacao restaurada. Voce pode ajustar filtros ou comparar novamente.', 'info');
          setStepState('stepPickFiles', 'Concluido', 'done');
          setStepState('stepLoadTables', tablesLoadedOnce ? 'Concluido' : 'Aguardando', tablesLoadedOnce ? 'done' : null);
          setStepState('stepCompare', 'Concluido', 'done');
          setStepOpen(3);
        } catch (e) {
          console.warn('Nao foi possivel restaurar resultado anterior da comparacao.', e);
        }
      }
    }

    // Upload de arquivos .duckdb para o servidor, reaproveitando /admin/upload,
    // apenas para obter o caminho salvo e preencher automaticamente os campos
    // de Banco A / Banco B.
    async function handleFileUpload(side) {
      const input = document.getElementById(side === 'A' ? 'fileInputA' : 'fileInputB');
      const nameSpan = document.getElementById(side === 'A' ? 'fileNameA' : 'fileNameB');
      const pathInput = document.getElementById(side === 'A' ? 'db1Path' : 'db2Path');
      const btn = document.getElementById(side === 'A' ? 'btnUploadA' : 'btnUploadB');
      if (!input || !input.files || !input.files.length) return;
      const file = input.files[0];
      nameSpan.textContent = file.name;

      const fd = new FormData();
      fd.append('file', file);
      nameSpan.textContent = file.name + ' (enviando...)';

      // feedback imediato na interface
      setUploadStatus(`Enviando "${file.name}" para Banco ${side}... Aguarde, o upload pode levar alguns segundos ou minutos dependendo do tamanho.`);
      setFlowHint(`Enviando arquivo do Banco ${side}...`, 'info');
      setStepState('stepPickFiles', 'Enviando arquivo...', 'active');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Enviando...';
      }

      // se demorar demais, avisa o usuário que pode ter travado
      if (uploadTimeouts[side]) {
        clearTimeout(uploadTimeouts[side]);
      }
      uploadTimeouts[side] = setTimeout(() => {
        setUploadStatus(`O upload do Banco ${side} está levando mais de 60 segundos. Se continuar assim, pode ter havido um travamento. Verifique a conexão e o tamanho do arquivo.` , true);
      }, 60000);

      try {
        const res = await fetch('/admin/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || res.statusText);
        }
        // Para .duckdb, o backend já salva o arquivo em interface/uploads
        // e devolve o caminho em db_path.
        if (data.db_path) {
          pathInput.value = data.db_path;
          nameSpan.textContent = file.name + ' (carregado)';
          setUploadStatus(`Upload do Banco ${side} concluído com sucesso.`);
        } else if (data.output) {
          // fallback caso no futuro seja usado Access convertido
          pathInput.value = data.output;
          nameSpan.textContent = file.name + ' (carregado)';
          setUploadStatus(`Upload do Banco ${side} concluído com sucesso.`);
        } else {
          nameSpan.textContent = file.name + ' (enviado)';
          setUploadStatus(`Upload do Banco ${side} concluído.`);
        }

        const otherPathInput = document.getElementById(side === 'A' ? 'db2Path' : 'db1Path');
        if (pathInput.value.trim() && otherPathInput && otherPathInput.value.trim()) {
          setFlowHint('Arquivos A e B já informados. Agora carregue as tabelas em comum.', 'info');
          setStepState('stepPickFiles', 'Concluído', 'done');
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
        if (uploadTimeouts[side]) {
          clearTimeout(uploadTimeouts[side]);
          uploadTimeouts[side] = null;
        }
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Escolher arquivo...';
        }
      }
    }

    document.addEventListener('DOMContentLoaded', () => {
      const fa = document.getElementById('fileInputA');
      const fb = document.getElementById('fileInputB');
      if (fa) {
        fa.addEventListener('change', () => handleFileUpload('A'));
      }
      if (fb) {
        fb.addEventListener('change', () => handleFileUpload('B'));
      }

      const rowLimitCb = document.getElementById('rowLimitEnabled');
      if (rowLimitCb) {
        rowLimitCb.addEventListener('change', updateRowLimitState);
        updateRowLimitState();
      }
      const statefulInputs = [
        'db1Path','db2Path','keyColumns','compareColumns','keyFilter',
        'filterChanged','filterAdded','filterRemoved','filterColumn',
        'rowLimit','rowLimitEnabled','tableSelect'
      ];
      for (const id of statefulInputs) {
        const el = document.getElementById(id);
        if (!el) continue;
        const evt = el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input';
        el.addEventListener(evt, () => saveCompareState());
      }

      restoreFromSavedState();

      const helpBtn = document.getElementById('openHelpCompare');
      if (helpBtn) {
        helpBtn.addEventListener('click', () => {
          const box = document.getElementById('helpCompareBox');
          if (!box) return;
          const isHidden = box.style.display === 'none' || box.style.display === '';
          box.style.display = isHidden ? 'block' : 'none';
        });
      }
    });

    async function loadTables() {
      const db1 = document.getElementById('db1Path').value.trim();
      const db2 = document.getElementById('db2Path').value.trim();
      const statusEl = document.getElementById('statusMeta');
      const tableSelect = document.getElementById('tableSelect');
      const btn = document.getElementById('btnLoadTables');
      tablesMeta = [];
      tablesLoadedOnce = false;
      tablesOverviewCache = null;
      tablesOverviewVisible = false;
      updateTablesOverviewVisibility();
      tableSelect.innerHTML = '<option value="">carregando...</option>';
      statusEl.textContent = 'Carregando tabelas em comum...';
      const restoreBtn = setButtonBusy(btn, 'Carregando...', btn ? btn.textContent : 'Mapear tabelas comuns');

      if (tablesTimeout) {
        clearTimeout(tablesTimeout);
        tablesTimeout = null;
      }

      tablesTimeout = setTimeout(() => {
        statusEl.textContent = 'A carga das tabelas em comum está levando mais de 60 segundos. Se continuar assim, pode ter ocorrido algum travamento ou os bancos são muito grandes.';
      }, 60000);

      if (!db1 || !db2) {
        statusEl.textContent = 'Informe os caminhos de ambos os bancos (.duckdb).';
        setFlowHint('Informe os caminhos de ambos os bancos A e B para continuar.', 'warn');
        setStepState('stepPickFiles', 'Caminhos faltando', 'warn');
        setStepState('stepLoadTables', 'Aguardando', null);
        tableSelect.innerHTML = '<option value="">-- informe os caminhos acima --</option>';
        if (tablesTimeout) {
          clearTimeout(tablesTimeout);
          tablesTimeout = null;
        }
        return;
      }

      setFlowHint('Carregando tabelas em comum entre os dois bancos...', 'info');
      setStepState('stepPickFiles', 'Concluído', 'done');
      setStepState('stepLoadTables', 'Carregando...', 'active');

      try {
        const data = await postJson('/api/compare_db_tables', { db1_path: db1, db2_path: db2 });
        tablesMeta = data.tables || [];
        if (!tablesMeta.length) {
          statusEl.textContent = 'Nenhuma tabela em comum encontrada entre os dois bancos.';
          tableSelect.innerHTML = '<option value="">-- nenhuma tabela em comum --</option>';
          setFlowHint('Nenhuma tabela em comum encontrada entre os dois bancos.', 'warn');
          setStepState('stepLoadTables', 'Nenhuma tabela em comum', 'warn');
          return;
        }
        tableSelect.innerHTML = '';
        const preferredTable = 'RANGER_SOSTAT';
        let hasPreferred = false;
        for (const t of tablesMeta) {
          const opt = document.createElement('option');
          opt.value = t.name;
          opt.textContent = t.name;
          if (t.name && t.name.toUpperCase() === preferredTable) {
            opt.selected = true;
            hasPreferred = true;
          }
          tableSelect.appendChild(opt);
        }
        // Se a tabela RANGER_SOSTAT existir, deixamos ela pré-selecionada;
        // caso contrário, o navegador mantém a primeira opção selecionada.
        statusEl.textContent = `Tabelas em comum: ${tablesMeta.length}`;
        tablesLoadedOnce = true;
        setFlowHint('Tabelas em comum carregadas. Selecione a tabela, defina a chave K e clique em "Comparar tabela".', 'info');
        setStepState('stepLoadTables', 'Concluído', 'done');
        setStepState('stepCompare', 'Pronto para comparar', 'active');
        setStepOpen(2);
        onTableChange();
        saveCompareState();
      } catch (err) {
        console.error(err);
        statusEl.textContent = 'Erro: ' + err.message;
        tableSelect.innerHTML = '<option value="">-- erro ao carregar tabelas --</option>';
        setFlowHint('Erro ao carregar tabelas: ' + err.message, 'error');
        setStepState('stepLoadTables', 'Erro ao carregar', 'warn');
      } finally {
        restoreBtn();
        if (tablesTimeout) {
          clearTimeout(tablesTimeout);
          tablesTimeout = null;
        }
      }
    }

    function onTableChange() {
      const table = document.getElementById('tableSelect').value;
      const keyInput = document.getElementById('keyColumns');
      const cmpInput = document.getElementById('compareColumns');
      if (!table) return;
      const meta = tablesMeta.find(t => t.name === table);
      if (!meta) return;
      const suggestedKeys = guessKeyColumnsForTable(table, meta.columns || []);
      keyInput.value = suggestedKeys.join(',');
      cmpInput.value = '';
    }

    function collectCompareRequest(page = 1) {
      const db1 = document.getElementById('db1Path').value.trim();
      const db2 = document.getElementById('db2Path').value.trim();
      const table = document.getElementById('tableSelect').value;
      const keyColsStr = document.getElementById('keyColumns').value.trim();
      const cmpColsStr = document.getElementById('compareColumns').value.trim();
      const keyFilterStr = document.getElementById('keyFilter').value.trim();
      const cbChanged = document.getElementById('filterChanged');
      const cbAdded = document.getElementById('filterAdded');
      const cbRemoved = document.getElementById('filterRemoved');
      const colSelect = document.getElementById('filterColumn');
      const rowLimitEl = document.getElementById('rowLimit');
      const rowLimitEnabledEl = document.getElementById('rowLimitEnabled');

      const key_columns = keyColsStr.split(',').map(s => s.trim()).filter(Boolean);
      const compare_columns = cmpColsStr ? cmpColsStr.split(',').map(s => s.trim()).filter(Boolean) : null;

      let row_limit = null;
      const limitEnabled = !rowLimitEnabledEl || rowLimitEnabledEl.checked;
      if (limitEnabled && rowLimitEl) {
        const raw = String(rowLimitEl.value || '').trim();
        if (raw) {
          const parsed = parseInt(raw, 10);
          if (!Number.isNaN(parsed) && parsed >= 1) {
            row_limit = parsed;
          }
        }
      }

      const change_types = [];
      if (!cbChanged || cbChanged.checked) change_types.push('changed');
      if (!cbAdded || cbAdded.checked) change_types.push('removed');
      if (!cbRemoved || cbRemoved.checked) change_types.push('added');

      const changed_column = (colSelect && colSelect.value) ? colSelect.value : null;
      const page_size = row_limit || null;

      return {
        db1,
        db2,
        table,
        keyColsStr,
        payload: {
          db1_path: db1,
          db2_path: db2,
          table,
          key_columns,
          compare_columns,
          row_limit,
          key_filter: keyFilterStr || null,
          change_types,
          changed_column,
          page,
          page_size,
        },
      };
    }

    async function runCompare() {
      const summaryEl = document.getElementById('summary');
      const resultsEl = document.getElementById('results');
      const compareRequest = collectCompareRequest(1);

      summaryEl.innerHTML = '';
      resultsEl.innerHTML = '';
      setCompareStatus('', 'info');

      if (!compareRequest.db1 || !compareRequest.db2) {
        setCompareStatus('Informe os caminhos de ambos os bancos (.duckdb).', 'warn');
        setFlowHint('Informe os caminhos de ambos os bancos A e B para conseguir comparar.', 'warn');
        setStepState('stepPickFiles', 'Caminhos faltando', 'warn');
        setStepState('stepLoadTables', 'Aguardando', null);
        setStepState('stepCompare', 'Aguardando', null);
        return;
      }
      if (!compareRequest.table) {
        setCompareStatus('Selecione uma tabela.', 'warn');
        setFlowHint('Carregue as tabelas em comum e selecione uma tabela antes de comparar.', 'warn');
        setStepState('stepLoadTables', 'Tabela nao selecionada', 'warn');
        setStepState('stepCompare', 'Aguardando', null);
        return;
      }
      if (!compareRequest.keyColsStr) {
        setCompareStatus('Informe pelo menos uma coluna-chave K.', 'warn');
        setFlowHint('Informe pelo menos uma coluna-chave K para identificar os registros unicos.', 'warn');
        setStepState('stepCompare', 'Chave K faltando', 'warn');
        return;
      }

      lastComparePayload = compareRequest.payload;
      lastCompareMeta = null;
      saveCompareState();

      const compareTimeout = setCompareBusy(
        'Comparando tabela completa entre A e B (pode levar alguns segundos)...',
        'Comparando tabela completa entre A e B. Aguarde, dependendo do tamanho pode levar alguns segundos ou minutos.',
        'Comparando...',
        'A comparacao esta levando mais de 60 segundos. Se o banco ou a tabela forem muito grandes, isso pode ser esperado. Se travar, tente restringir por chave K.'
      );

      try {
        const data = await postJson('/api/compare_db_rows', compareRequest.payload);
        renderResult(data);
        updateLastCompareMeta(data, 1);
        saveCompareState();
        setCompareStatus('Comparacao concluida.', 'info');
        setFlowHint('Comparacao concluida. Revise o resumo e os detalhes de diferencas abaixo.', 'info');
        setStepState('stepCompare', 'Concluido', 'done');
        setStepOpen(3);
      } catch (err) {
        console.error(err);
        setCompareStatus('Erro ao comparar: ' + (err && err.message ? err.message : String(err)), 'error');
        setFlowHint('Erro ao comparar bancos: ' + (err && err.message ? err.message : String(err)), 'error');
        setStepState('stepCompare', 'Erro ao comparar', 'warn');
      } finally {
        clearCompareBusy(compareTimeout);
      }
    }

    async function changePage(newPage) {
      if (!lastComparePayload) return;

      const payload = { ...lastComparePayload, page: newPage };
      lastComparePayload = payload;
      saveCompareState();

      const compareTimeout = setCompareBusy(
        `Carregando pagina ${newPage}...`,
        `Carregando pagina ${newPage} dos resultados de comparacao...`,
        `Carregando pagina ${newPage}...`,
        'A troca de pagina esta levando mais de 60 segundos. Se a tabela for grande, isso pode ser esperado.'
      );

      try {
        const data = await postJson('/api/compare_db_rows', payload);
        renderResult(data);
        updateLastCompareMeta(data, newPage);
        saveCompareState();
        setCompareStatus('Comparacao concluida.', 'info');
        setFlowHint('Resultados atualizados. Continue revisando as diferencas.', 'info');
        setStepState('stepCompare', 'Concluido', 'done');
      } catch (err) {
        console.error(err);
        setCompareStatus('Erro ao carregar pagina: ' + (err && err.message ? err.message : String(err)), 'error');
        setFlowHint('Erro ao buscar pagina de resultados: ' + (err && err.message ? err.message : String(err)), 'error');
        setStepState('stepCompare', 'Erro ao carregar pagina', 'warn');
      } finally {
        clearCompareBusy(compareTimeout);
      }
    }

    async function exportComparison() {
      const exportBtn = document.getElementById('btnExportComparison');
      const restoreBtn = setButtonBusy(exportBtn, 'Exportando...', exportBtn ? exportBtn.textContent : 'Exportar CSV');
      if (!lastComparePayload) {
        setCompareStatus('Nenhuma comparacao para exportar. Execute a comparacao primeiro.', 'warn');
        restoreBtn();
        return;
      }
      try {
        setCompareStatus('Preparando exportacao (carregando todas as paginas)...', 'info');
        const basePayload = { ...lastComparePayload };
        let page = 1;
        let totalPages = 1;
        let allRows = [];
        let meta = null;

        while (page <= totalPages) {
          const payload = { ...basePayload, page };
          const data = await postJson('/api/compare_db_rows', payload);
          if (!meta) {
            meta = data;
          }
          allRows = allRows.concat(data.rows || []);
          totalPages = data.total_pages || 1;
          page += 1;
        }

        if (!meta) {
          setCompareStatus('Nenhum dado disponivel para exportacao.', 'warn');
          return;
        }

        const keyCols = meta.key_columns || [];
        const cmpCols = meta.compare_columns || [];

        const headers = [];
        for (const k of keyCols) headers.push('K_' + k);
        headers.push('type');
        for (const c of cmpCols) {
          headers.push('A_' + c);
          headers.push('B_' + c);
        }

        const escapeCell = (val) => {
          if (val === null || typeof val === 'undefined') return '';
          let s = String(val);
          if (s.includes('"')) s = s.replace(/"/g, '""');
          if (s.includes(';') || s.includes('\n') || s.includes('\r')) {
            s = '"' + s + '"';
          }
          return s;
        };

        const lines = [];
        lines.push(headers.join(';'));
        for (const r of allRows) {
          const rowCells = [];
          for (const k of keyCols) {
            rowCells.push(escapeCell((r.key || {})[k]));
          }
          rowCells.push(escapeCell(r.type));
          for (const c of cmpCols) {
            rowCells.push(escapeCell((r.a || {})[c]));
            rowCells.push(escapeCell((r.b || {})[c]));
          }
          lines.push(rowCells.join(';'));
        }

        const csvContent = lines.join('\r\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const tableName = (meta.table || 'tabela').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.href = url;
        a.download = `comparacao_${tableName}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setCompareStatus('Exportacao concluida. Arquivo CSV baixado.', 'info');
        setFlowHint('Exportacao concluida. O CSV foi baixado com o recorte atual.', 'info');
      } catch (err) {
        console.error(err);
        setCompareStatus('Erro inesperado ao exportar: ' + (err && err.message ? err.message : String(err)), 'error');
        setFlowHint('Falha ao exportar a comparacao.', 'error');
      } finally {
        restoreBtn();
      }
    }

    function updateTablesOverviewVisibility() {
      const container = document.getElementById('tablesOverview');
      const btn = document.getElementById('btnTablesOverview');
      if (!container || !btn) return;
      container.style.display = tablesOverviewVisible ? 'block' : 'none';
      btn.textContent = tablesOverviewVisible ? 'Ocultar mapa das tabelas' : 'Mapa geral das tabelas';
    }

    async function generateTablesOverview() {
      const container = document.getElementById('tablesOverview');
      const db1Input = document.getElementById('db1Path');
      const db2Input = document.getElementById('db2Path');
      const overviewBtn = document.getElementById('btnTablesOverview');
      const restoreBtn = setButtonBusy(overviewBtn, 'Gerando mapa...', overviewBtn ? overviewBtn.textContent : 'Mapa geral das tabelas');

      if (!db1Input || !db2Input || !db1Input.value.trim() || !db2Input.value.trim()) {
        setCompareStatus('Informe os caminhos de ambos os bancos e carregue as tabelas antes de gerar o mapa.', 'warn');
        restoreBtn();
        return;
      }
      if (!tablesMeta || !tablesMeta.length) {
        setCompareStatus('Carregue as tabelas em comum primeiro.', 'warn');
        restoreBtn();
        return;
      }

      container.innerHTML = '<div class="tables-overview-card">Gerando mapa geral das tabelas... Isso pode levar alguns segundos.</div>';

      if (tablesOverviewCache && tablesOverviewCache.db1 === db1Input.value && tablesOverviewCache.db2 === db2Input.value) {
        renderTablesOverview(tablesOverviewCache.result);
        restoreBtn();
        return;
      }

      const overview = [];
      const db1 = db1Input.value.trim();
      const db2 = db2Input.value.trim();

      for (const t of tablesMeta) {
        const name = t.name;
        try {
          const data = await postJson('/api/compare_db_table_content', {
            db1_path: db1,
            db2_path: db2,
            table: name,
          });
          const diffCount = typeof data.diff_count === 'number' ? data.diff_count : -1;
          const hasDiff = diffCount > 0;
          overview.push({
            table: name,
            status: hasDiff ? 'diff' : 'same',
            diffCount,
            row_count_a: data.row_count_a,
            row_count_b: data.row_count_b,
          });
        } catch (err) {
          console.error('Erro ao gerar resumo da tabela', name, err);
          overview.push({ table: name, status: 'error', error: err && err.message ? err.message : String(err) });
        }
      }

      tablesOverviewCache = { db1: db1, db2: db2, result: overview };
      renderTablesOverview(overview);
      restoreBtn();
    }

    async function toggleTablesOverview() {
      // se já estiver visível, apenas oculta
      if (tablesOverviewVisible) {
        tablesOverviewVisible = false;
        updateTablesOverviewVisibility();
        return;
      }

      // se ainda não geramos nada para este par de bancos, gera agora
      const container = document.getElementById('tablesOverview');
      if (container && (!tablesOverviewCache)) {
        await generateTablesOverview();
      }
      tablesOverviewVisible = true;
      updateTablesOverviewVisibility();
    }

    function renderTablesOverview(overview) {
      const container = document.getElementById('tablesOverview');
      if (!container) return;
      if (!overview || !overview.length) {
        container.innerHTML = '';
        return;
      }

      const withDiff = overview.filter(o => o.status === 'diff');
      const withoutDiff = overview.filter(o => o.status === 'same');
      const noKey = overview.filter(o => o.status === 'no_key');
      const errors = overview.filter(o => o.status === 'error');

      let html = '<div class="tables-overview-card">';
      html += '<div><strong>Mapa geral das tabelas em comum</strong></div>';
      html += '<div class="tables-overview-grid">';

      if (withDiff.length) {
        html += '<div><strong>Tabelas com diferenças de conteúdo:</strong></div>';
        for (const o of withDiff) {
          html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">${o.diffCount} linhas diferentes · A: ${o.row_count_a} · B: ${o.row_count_b}</span></div>`;
        }
      }

      if (withoutDiff.length) {
        html += '<div style="margin-top:4px;"><strong>Tabelas sem diferenças relevantes:</strong></div>';
        for (const o of withoutDiff) {
          html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">conteúdo idêntico · A: ${o.row_count_a} · B: ${o.row_count_b}</span></div>`;
        }
      }

      if (noKey.length) {
        html += '<div style="margin-top:4px;"><strong>Tabelas não avaliadas (chave não identificada automaticamente):</strong></div>';
        for (const o of noKey) {
          html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">defina uma chave manualmente no passo 2 para comparar esta tabela.</span></div>`;
        }
      }

      if (errors.length) {
        html += '<div style="margin-top:4px;"><strong>Tabelas com erro ao comparar:</strong></div>';
        for (const o of errors) {
          html += `<div class="tables-overview-row"><span class="tables-overview-name">${o.table}</span><span class="tables-overview-meta">${o.error || 'Erro ao comparar.'}</span></div>`;
        }
      }

      html += '</div></div>';
      container.innerHTML = html;
    }
