function setPriorityStatus(text, level) {
  const el = $('priorityMsg');
  if (!el) return;
  el.textContent = text || '';
  el.classList.remove('warn', 'error');
  if (level === 'warn' || level === 'error') {
    el.classList.add(level);
  }
}

async function loadPriorityModal() {
  const allEl = $('allTablesList');
  const selEl = $('priorityListModal');
  if (!allEl || !selEl) return;
  if (!hasDbSelected()) {
    allEl.innerHTML = '<li class="muted">Nenhum DB selecionado</li>';
    selEl.innerHTML = '';
    setPriorityStatus('Nenhum DB selecionado', 'warn');
    setModalBanner(
      'priorityModalBanner',
      'Selecione um DB antes de editar a ordem das tabelas.',
      'warn'
    );
    return;
  }
  allEl.innerHTML = '';
  selEl.innerHTML = '';
  setPriorityStatus('Carregando...', '');
  setModalBanner(
    'priorityModalBanner',
    'Carregando tabelas do DB ativo...',
    'info'
  );
  try {
    const t = await apiJSON('/api/tables');
    if (t.error) {
      allEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
      selEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
      setPriorityStatus('Erro ao listar tabelas.', 'error');
      setModalBanner(
        'priorityModalBanner',
        'Nao foi possivel listar as tabelas do DB ativo.',
        'error'
      );
      logUi('ERROR', 'priority tabelas ' + t.error);
      return;
    }
    const tables = t.tables || [];
    const visible = tables.filter((n) => !/^MSys/i.test(n));
    const st = await apiJSON('/admin/list_uploads');
    const saved = st.priority_tables || [];
    const remaining = visible.filter((x) => !saved.includes(x));
    remaining.forEach((name) => {
      const li = document.createElement('li');
      li.dataset.table = name;
      li.innerHTML = `<label style="display:flex;align-items:center;gap:8px;width:100%"><input type="checkbox" data-name="${encodeURIComponent(
        name
      )}" onchange="onTableCheckboxChange(this)"> <span style="flex:1">${escapeHtml(
        name
      )}</span></label>`;
      allEl.appendChild(li);
    });
    saved.forEach((name) => {
      const li = document.createElement('li');
      li.draggable = true;
      li.dataset.table = name;
      li.innerHTML = `<div style="flex:1">${escapeHtml(
        name
      )}</div><div style="display:flex;gap:6px"><button class="btn ghost" onclick="prioMoveUp(this)" title="Mover para cima">Up</button><button class="btn ghost" onclick="prioMoveDown(this)" title="Mover para baixo">Down</button><button class="btn ghost" onclick="prioRemove(this)" title="Remover">X</button></div>`;
      selEl.appendChild(li);
    });
    enableDragAndDrop(selEl);
    setPriorityStatus(
      `Tabelas carregadas: ${visible.length}. Prioritarias: ${saved.length}.`,
      ''
    );
    setModalBanner(
      'priorityModalBanner',
      'Ajuste a ordem e salve quando terminar.',
      'info'
    );
  } catch (e) {
    allEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
    selEl.innerHTML = '<li class="muted">Erro ao listar tabelas</li>';
    setPriorityStatus('Erro ao listar tabelas.', 'error');
    setModalBanner(
      'priorityModalBanner',
      'Falha ao carregar as tabelas prioritarias.',
      'error'
    );
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
    const it = Array.from(selEl.children).find(
      (li) => li.dataset.table === name
    );
    if (it) selEl.removeChild(it);
  }
}

function enableDragAndDrop(listEl) {
  let dragSrc = null;
  Array.from(listEl.children).forEach((li) => {
    if (li.dataset.dndBound === '1') return;
    li.dataset.dndBound = '1';
    li.addEventListener('dragstart', (e) => {
      dragSrc = li;
      li.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    li.addEventListener('dragend', () => {
      li.classList.remove('dragging');
    });
    li.addEventListener('dragover', (e) => {
      e.preventDefault();
      const target = e.currentTarget;
      if (target === dragSrc) return;
      const rect = target.getBoundingClientRect();
      const next = e.clientY - rect.top > rect.height / 2;
      if (next) target.parentNode.insertBefore(dragSrc, target.nextSibling);
      else target.parentNode.insertBefore(dragSrc, target);
    });
    li.addEventListener('drop', (e) => {
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
  if (!li || !li.parentNode) return;
  const name = li.dataset.table;
  li.parentNode.removeChild(li);
  if (!name) return;
  const leftChk = Array.from(
    document.querySelectorAll('#allTablesList input[type=checkbox]')
  ).find((c) => c.getAttribute('data-name') === encodeURIComponent(name));
  if (leftChk) {
    leftChk.checked = false;
    return;
  }
  const allEl = $('allTablesList');
  if (!allEl) return;
  const liOpt = document.createElement('li');
  liOpt.dataset.table = name;
  liOpt.innerHTML = `<label style="display:flex;align-items:center;gap:8px;width:100%"><input type="checkbox" data-name="${encodeURIComponent(
    name
  )}" onchange="onTableCheckboxChange(this)"> <span style="flex:1">${escapeHtml(
    name
  )}</span></label>`;
  allEl.appendChild(liOpt);
}

async function savePriority() {
  const listEl = $('priorityListModal');
  if (!listEl) return;
  const tables = Array.from(listEl.querySelectorAll('li'))
    .map((li) => li.dataset.table)
    .filter((name) => typeof name === 'string' && name.length > 0);
  setPriorityStatus('Salvando prioridades...', '');
  setModalBanner(
    'priorityModalBanner',
    'Salvando a nova ordem das tabelas...',
    'info'
  );
  try {
    const res = await fetch('/admin/set_priority', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ tables }),
    });
    const j = await res.json();
    if (j && j.ok) {
      setPriorityStatus('Prioridades salvas: ' + tables.length, '');
      setModalBanner('priorityModalBanner', 'Ordem salva com sucesso.', 'info');
    } else {
      setPriorityStatus('Erro ao salvar prioridades.', 'error');
      setModalBanner(
        'priorityModalBanner',
        'Nao foi possivel salvar a ordem das tabelas.',
        'error'
      );
    }
    await refreshUiState();
  } catch (e) {
    setPriorityStatus('Erro ao salvar prioridades.', 'error');
    setModalBanner(
      'priorityModalBanner',
      'Falha de rede ao salvar prioridades.',
      'error'
    );
  }
}

window.setPriorityStatus = setPriorityStatus;
window.loadPriorityModal = loadPriorityModal;
window.onTableCheckboxChange = onTableCheckboxChange;
window.enableDragAndDrop = enableDragAndDrop;
window.prioMoveUp = prioMoveUp;
window.prioMoveDown = prioMoveDown;
window.prioRemove = prioRemove;
window.savePriority = savePriority;
