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

      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Carregando...';
      }

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
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Mapear tabelas comuns';
        }
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
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Mapear tabelas comuns';
        }
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
      // Se a tabela padrão RANGER_SOSTAT estiver selecionada, usa RTUNO,PNTNO como chave K
      if (table.toUpperCase() === 'RANGER_SOSTAT') {
        keyInput.value = 'RTUNO,PNTNO';
      } else {
        // sugestão simples: se houver coluna ID, assume-a como chave
        const cols = meta.columns || [];
        const lower = cols.map(c => c.toLowerCase());
        let suggestedKey = '';
        if (lower.includes('id')) {
          suggestedKey = cols[lower.indexOf('id')];
        }
        keyInput.value = suggestedKey;
      }
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
      const statusEl = document.getElementById('statusCompare');
      const summaryEl = document.getElementById('summary');
      const resultsEl = document.getElementById('results');
      const compareRequest = collectCompareRequest(1);

      summaryEl.innerHTML = '';
      resultsEl.innerHTML = '';
      statusEl.textContent = '';

      if (!compareRequest.db1 || !compareRequest.db2) {
        statusEl.textContent = 'Informe os caminhos de ambos os bancos (.duckdb).';
        setFlowHint('Informe os caminhos de ambos os bancos A e B para conseguir comparar.', 'warn');
        setStepState('stepPickFiles', 'Caminhos faltando', 'warn');
        setStepState('stepLoadTables', 'Aguardando', null);
        setStepState('stepCompare', 'Aguardando', null);
        return;
      }
      if (!compareRequest.table) {
        statusEl.textContent = 'Selecione uma tabela.';
        setFlowHint('Carregue as tabelas em comum e selecione uma tabela antes de comparar.', 'warn');
        setStepState('stepLoadTables', 'Tabela nao selecionada', 'warn');
        setStepState('stepCompare', 'Aguardando', null);
        return;
      }
      if (!compareRequest.keyColsStr) {
        statusEl.textContent = 'Informe pelo menos uma coluna-chave K.';
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
        statusEl.textContent = 'Comparacao concluida.';
        setFlowHint('Comparacao concluida. Revise o resumo e os detalhes de diferencas abaixo.', 'info');
        setStepState('stepCompare', 'Concluido', 'done');
        setStepOpen(3);
      } catch (err) {
        console.error(err);
        statusEl.textContent = 'Erro ao comparar: ' + (err && err.message ? err.message : String(err));
        setFlowHint('Erro ao comparar bancos: ' + (err && err.message ? err.message : String(err)), 'error');
        setStepState('stepCompare', 'Erro ao comparar', 'warn');
      } finally {
        clearCompareBusy(compareTimeout);
      }
    }

    function valuesDifferent(a, b) {
      // Comparação simples, tratando null/undefined como iguais quando ambos "vazios".
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

    function renderResult(data) {
      const summaryEl = document.getElementById('summary');
      const resultsEl = document.getElementById('results');
      const colSelect = document.getElementById('filterColumn');
      const rows = data.rows || [];
      const isRangerSostat = (data.table || '').toUpperCase() === 'RANGER_SOSTAT';

      const byType = { added: [], removed: [], changed: [] };
      for (const r of rows) {
        if (r.type === 'added') byType.added.push(r);
        else if (r.type === 'removed') byType.removed.push(r);
        else byType.changed.push(r);
      }
      const s = data.summary || {};
      const same = s.same_count ?? 0;
      // Atenção: no backend, "added" = existe só em B e "removed" = existe só em A.
      // Como na UI o Banco A é o NOVO e o B é o ANTIGO, aqui invertemos os rótulos
      // para que "novos" signifique "só em A" e "removidos" signifique "só em B".
      const onlyInB = s.added_count ?? byType.added.length;   // só no B (ANTIGO)
      const onlyInA = s.removed_count ?? byType.removed.length; // só no A (NOVO)
      const changed = s.changed_count ?? byType.changed.length;
      const totalKeys = s.keys_total ?? (same + onlyInA + onlyInB + changed);

      // Resumo por coluna: em quantos registros cada coluna mudou
      const colDiffCounts = {};
      for (const r of byType.changed) {
        for (const c of data.compare_columns || []) {
          if (!valuesDifferent(r.a[c], r.b[c])) continue;
          colDiffCounts[c] = (colDiffCounts[c] || 0) + 1;
        }
      }
      const colDiffList = Object.entries(colDiffCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([col, cnt]) => `${col}: ${cnt}`)
        .join(', ');

      summaryEl.innerHTML = `
        <div class="result-summary-card">
          <div class="result-summary-grid">
            <div><strong>Tabela analisada:</strong> ${data.table}</div>
            <div><strong>Chaves (K):</strong> ${(data.key_columns || []).join(', ')}</div>
            <div>
              <strong>Visão geral:</strong> ${totalKeys} registros (chaves) analisados
              <div class="result-badges-row">
                <span class="badge same">${same} mantidos (iguais em A e B)</span>
                <span class="badge added">+${onlyInA} novos (existem só em A — banco NOVO)</span>
                <span class="badge removed">-${onlyInB} removidos (existiam só em B — banco ANTIGO)</span>
                <span class="badge changed">±${changed} alterados (chave existe em ambos, mas com diferença)</span>
              </div>
            </div>
            ${colDiffList ? `<div class="result-col-diff"><strong>Colunas com diferença (qtd. de registros alterados):</strong> ${colDiffList}</div>` : ''}
          </div>
        </div>
      `;

      // Controles de visualização (linear vs blocos)
      const viewMode = window.diffViewMode || 'list';
      window.diffViewMode = viewMode;
      const controlsDiv = document.createElement('div');
      controlsDiv.style.marginTop = '4px';
      controlsDiv.style.fontSize = '11px';
      controlsDiv.style.color = '#9ca3af';
      controlsDiv.textContent = 'Visualização dos campos: ';

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

      const summaryCard = summaryEl.querySelector('.result-summary-card .result-summary-grid > div:nth-child(3)');
      if (summaryCard) {
        summaryCard.appendChild(controlsDiv);
      }

      renderPaginationControls(data);

      // atualiza as opções de filtro de coluna com base nas colunas realmente comparadas
      if (colSelect) {
        const prev = colSelect.value;
        colSelect.innerHTML = '<option value="">-- todas as colunas --</option>';
        for (const c of data.compare_columns || []) {
          const opt = document.createElement('option');
          opt.value = c;
          opt.textContent = c;
          colSelect.appendChild(opt);
        }
        // tenta restaurar a seleção anterior, se ainda existir
        if (prev && Array.from(colSelect.options).some(o => o.value === prev)) {
          colSelect.value = prev;
        }
      }

      const sections = [
        { type: 'changed', title: 'Alteradas (existem em A e B, mas com diferenças)', rows: byType.changed },
        // Para cores: "Novas" devem usar o estilo verde (added) e
        // "Removidas" o estilo vermelho (removed), independentemente
        // dos nomes internos do backend.
        { type: 'added', title: 'Novas — só em A (banco NOVO)', rows: byType.removed },
        { type: 'removed', title: 'Removidas — só em B (banco ANTIGO)', rows: byType.added }
      ];

      resultsEl.innerHTML = '';
      const maxPerSection = 50;
      let rowCounter = 0;
      window.lastCompareResult = data;
      const viewModeNow = window.diffViewMode || 'list';
      for (const section of sections) {
        if (!section.rows.length) continue;
        const details = document.createElement('details');
        details.className = `diff-section ${section.type}`;
        // por padrão, deixamos "Alteradas" abertas e as demais recolhidas
        if (section.type === 'changed') {
          details.open = true;
        }
        const extraInfo = section.rows.length > maxPerSection
          ? ` · mostrando primeiras ${maxPerSection} chaves`
          : '';
        const summary = document.createElement('summary');
        summary.className = 'diff-section-header';
        summary.innerHTML = `<span class="diff-section-title">${section.title} (${section.rows.length})</span>${extraInfo ? `<span class="diff-section-extra">${extraInfo}</span>` : ''}`;
        details.appendChild(summary);

        const rowsToShow = section.rows.slice(0, maxPerSection);
        const listContainer = document.createElement('div');
        listContainer.className = 'diff-section-body';

        for (const r of rowsToShow) {
          const rowDetails = document.createElement('details');
          rowDetails.className = `diff-row diff-row-${section.type}`;
          const rowId = `row-${++rowCounter}`;

          const keyParts = [];
          for (const k of data.key_columns || []) {
            keyParts.push(`${k}=${JSON.stringify(r.key[k])}`);
          }

          let extraParts = [];
          if (isRangerSostat) {
            const primaryFields = ['SUBNAM', 'PNTNAM', 'BITBYT', 'UNIQID', 'ITEMNB'];
            const pickSide = (col) => {
              const bv = (r.b || {})[col];
              const av = (r.a || {})[col];
              return typeof bv !== 'undefined' ? bv : av;
            };
            for (const f of primaryFields) {
              const v = pickSide(f);
              if (typeof v !== 'undefined') {
                extraParts.push(`${f}=${shortValue(v, 40)}`);
              }
            }
          }

          const rowSummary = document.createElement('summary');
          // Backend: "added" = só em B (ANTIGO), "removed" = só em A (NOVO).
          // Para o usuário: queremos ver "Nova" quando existe só no banco NOVO (A)
          // e "Removida" quando existia só no banco ANTIGO (B).
          const visualType = r.type === 'removed' ? 'added'   // só em A => Nova
            : r.type === 'added' ? 'removed'                  // só em B => Removida
            : 'changed';
          const typeLabel = r.type === 'removed' ? 'Nova'
            : r.type === 'added' ? 'Removida'
            : 'Alterada';
          rowSummary.innerHTML = `
            <span class="badge ${visualType}" style="margin-right:6px;">${typeLabel}</span>
            <span style="font-size:12px;">
              ${keyParts.join(', ')}
              ${isRangerSostat && extraParts.length ? ' · ' + extraParts.join(' · ') : ''}
            </span>
          `;
          rowDetails.appendChild(rowSummary);

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
            btnMain.textContent = 'Campos principais (2ª etapa)';
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
            const allLabel = document.createElement('div');
            allLabel.textContent = 'Diferenças nos campos principais:';
            importantDiv.appendChild(allLabel);

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
          const importantCols = isRangerSostat ? new Set(['PSEUDO','STTYPE','STACON','CLASS','PRIORT','ACRONM','NORMST','CTLFLG','HISFLG','HWADR2','HWTYPE','SOEHIS','INHPRO','PNLNAM','DEVNAM']) : null;

          if (section.type === 'changed') {
            for (const c of data.compare_columns || []) {
              const av = r.a[c];
              const bv = r.b[c];
              const diff = valuesDifferent(av, bv);
              if (!isRangerSostat || !allDiv) {
                if (!diff) continue;  // mantém comportamento antigo para outras tabelas
              }
              const line = document.createElement('div');
              line.className = 'diff-field-line';
              if (diff) {
                line.innerHTML = `<strong>${c}:</strong> ${shortValue(av)} → ${shortValue(bv)}`;
              } else {
                line.innerHTML = `<span style="opacity:0.7;"><strong>${c}:</strong> ${shortValue(av)} (sem diferença)</span>`;
              }
              targetAll.appendChild(line);
              if (importantDiv && importantCols && importantCols.has(c) && diff) {
                const impLine = document.createElement('div');
                impLine.className = 'diff-field-line';
                impLine.innerHTML = `<strong>${c}:</strong> ${shortValue(av)} → ${shortValue(bv)}`;
                importantDiv.appendChild(impLine);
              }
            }
          } else if (section.type === 'added') {
            for (const c of data.compare_columns || []) {
              const bv = r.b[c];
              const line = document.createElement('div');
              line.className = 'diff-field-line';
              line.innerHTML = `<strong>${c}:</strong> ${shortValue(bv)}`;
              targetAll.appendChild(line);
              if (importantDiv && importantCols && importantCols.has(c)) {
                const impLine = document.createElement('div');
                impLine.className = 'diff-field-line';
                impLine.innerHTML = line.innerHTML;
                importantDiv.appendChild(impLine);
              }
            }
          } else if (section.type === 'removed') {
            for (const c of data.compare_columns || []) {
              const av = r.a[c];
              const line = document.createElement('div');
              line.className = 'diff-field-line';
              line.innerHTML = `<strong>${c}:</strong> ${shortValue(av)}`;
              targetAll.appendChild(line);
              if (importantDiv && importantCols && importantCols.has(c)) {
                const impLine = document.createElement('div');
                impLine.innerHTML = line.innerHTML;
                importantDiv.appendChild(impLine);
              }
            }
          }

          if (importantDiv) {
            if (!importantDiv.childElementCount || importantDiv.childElementCount === 1) {
              const none = document.createElement('div');
              none.style.color = '#9ca3af';
              none.textContent = 'Nenhuma diferença relevante nos campos principais selecionados.';
              importantDiv.appendChild(none);
            }
            importantDiv.style.display = 'block';
            allDiv.style.display = 'none';
            body.appendChild(actions);
            body.appendChild(importantDiv);
            body.appendChild(allDiv);
          } else {
            if (!body.childElementCount && !targetAll.childElementCount) {
              const none = document.createElement('div');
              none.style.color = '#9ca3af';
              none.textContent = 'Nenhuma diferença relevante nas colunas selecionadas.';
              targetAll.appendChild(none);
            }
          }

          rowDetails.appendChild(body);
          listContainer.appendChild(rowDetails);
        }

        details.appendChild(listContainer);

        if (section.rows.length > maxPerSection) {
          const note = document.createElement('div');
          note.style.fontSize = '11px';
          note.style.color = '#9ca3af';
          note.style.marginTop = '4px';
          note.textContent = `Existem mais ${section.rows.length - maxPerSection} registros nesta categoria não exibidos aqui para manter a visualização enxuta.`;
          details.appendChild(note);
        }

        resultsEl.appendChild(details);
      }

      if (!rows.length) {
        resultsEl.innerHTML = '<div style="font-size:13px; color:#9ca3af;">Nenhuma diferença encontrada (dentro do limite configurado).</div>';
      }
    }

    function renderPaginationControls(data) {
      const pagEl = document.getElementById('pagination');
      if (!pagEl) return;

      const totalRows = typeof data.total_filtered_rows === 'number' ? data.total_filtered_rows : (data.row_count || 0);
      const page = data.page || 1;
      const totalPages = data.total_pages || 1;

      pagEl.innerHTML = '';

      if (!totalRows) {
        return;
      }

      const info = document.createElement('span');
      info.textContent = `Total de ${totalRows} registros com diferença` + (totalPages > 1 ? ` · página ${page} de ${totalPages}` : '');
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
        nextBtn.textContent = 'Próxima';
        nextBtn.className = 'secondary';
        nextBtn.disabled = page >= totalPages;

        controls.appendChild(prevBtn);
        controls.appendChild(nextBtn);
        pagEl.appendChild(controls);
      }
    }

    async function changePage(newPage) {
      if (!lastComparePayload) return;
      const statusEl = document.getElementById('statusCompare');

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
        statusEl.textContent = 'Comparacao concluida.';
        setFlowHint('Resultados atualizados. Continue revisando as diferencas.', 'info');
        setStepState('stepCompare', 'Concluido', 'done');
      } catch (err) {
        console.error(err);
        statusEl.textContent = 'Erro ao carregar pagina: ' + (err && err.message ? err.message : String(err));
        setFlowHint('Erro ao buscar pagina de resultados: ' + (err && err.message ? err.message : String(err)), 'error');
        setStepState('stepCompare', 'Erro ao carregar pagina', 'warn');
      } finally {
        clearCompareBusy(compareTimeout);
      }
    }

    async function exportComparison() {
      if (!lastComparePayload) {
        alert('Nenhuma comparação para exportar. Execute a comparação primeiro.');
        return;
      }
      const statusEl = document.getElementById('statusCompare');
      try {
        statusEl.textContent = 'Preparando exportação (carregando todas as páginas)...';
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
          alert('Nenhum dado para exportar.');
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
        statusEl.textContent = 'Exportação concluída. Arquivo CSV baixado.';
      } catch (err) {
        console.error(err);
        alert('Erro inesperado ao exportar: ' + (err && err.message ? err.message : String(err)));
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

      if (!db1Input || !db2Input || !db1Input.value.trim() || !db2Input.value.trim()) {
        alert('Informe os caminhos de ambos os bancos (.duckdb) e carregue as tabelas em comum antes de gerar o mapa.');
        return;
      }
      if (!tablesMeta || !tablesMeta.length) {
        alert('Carregue as tabelas em comum primeiro (passo 1).');
        return;
      }

      container.innerHTML = '<div class="tables-overview-card">Gerando mapa geral das tabelas... Isso pode levar alguns segundos.</div>';

      if (tablesOverviewCache && tablesOverviewCache.db1 === db1Input.value && tablesOverviewCache.db2 === db2Input.value) {
        renderTablesOverview(tablesOverviewCache.result);
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
