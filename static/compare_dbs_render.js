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

