#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_global_report_from_analyses.py

Versão completa com:
 - Estatísticas completas (média, desvio padrão, variância, CV e nº de amostras)
 - Preenchimento consistente (quando não há amostras, mostra 0 e n_amostras = 0)
 - Colunas em Português e nome "Distinto" (global / média / std / var / n)
 - CSV final com todas as métricas e HTML interativo que mostra as métricas
 - Heurística robusta para ler summary_by_column.csv de múltiplos formatos

Uso:
 python tools/build_global_report_from_analyses.py \
   --analises "C:\mdb2sql_fork\import_folder\analises2" \
   --out-db "C:\mdb2sql_fork\import_folder\analises2\global_freq_RANGER_SOSTAT.db" \
   --out-csv "C:\mdb2sql_fork\import_folder\analises2\global_summary_by_column.csv" \
   --out-html "C:\mdb2sql_fork\import_folder\analises2\relatorio_global_RANGER_SOSTAT_pt.html" \
   --table "RANGER_SOSTAT" --top-n 50

Requisitos:
 pip install pandas plotly numpy
"""
from pathlib import Path
import argparse
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import plotly.io as pio
import html
import io
import base64
import numpy as np
from collections import Counter

pio.templates.default = "plotly_white"

# ---------------- util estatísticas ----------------
def stats_from_list(lst):
    """
    Recebe lista de números (potencialmente vazia) e retorna dict com:
    n, mean, std (populacional ddof=0), var (populacional), cv (std/mean ou 0 se mean==0)
    Para consistência com sua escolha, quando a lista estiver vazia retornamos zeros e n=0.
    """
    if not lst:
        return {'n': 0, 'mean': 0.0, 'std': 0.0, 'var': 0.0, 'cv': 0.0}
    arr = np.array(lst, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=0))
    var = float(np.var(arr, ddof=0))
    cv = float(std / mean) if mean != 0 else 0.0
    return {'n': int(len(arr)), 'mean': mean, 'std': std, 'var': var, 'cv': cv}

def fmt_num(x, decimals=3):
    """Formata número para exibição no HTML (mantém padrão quando x é None)."""
    try:
        if x is None:
            return "0"
        if isinstance(x, (int, np.integer)):
            return str(int(x))
        v = float(x)
        # se for inteiro, mostrar sem casas decimais
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.{decimals}f}"
    except Exception:
        return str(x)

# ---------------- util: localizar arquivos ----------------
def encontrar_csvs_top_recursivo(diretorio_base: Path):
    return list(diretorio_base.rglob("*__top_*.csv"))

def encontrar_summary_recursivo(diretorio_base: Path):
    return list(diretorio_base.rglob("summary_by_column.csv"))

# ---------------- util: agregar top-values CSVs ----------------
def agregar_csvs_top(csv_paths):
    """
    Agrega os CSVs de top-values:
    - df_global: DataFrame(coluna, valor, count_total, files_count)
    - folder_ids: lista de paths (strings) de pastas de análise encontradas
    - mapa_top1_counts: dict[coluna] -> lista de top1_count por arquivo
    """
    agreg = {}
    pastas_vistas = {}
    mapa_top1 = {}

    for csv_path in csv_paths:
        parent = csv_path.parent
        if parent.name.lower() == "columns" and parent.parent.exists():
            pasta_analise = parent.parent
        else:
            pasta_analise = parent
        pasta_id = str(pasta_analise.resolve())
        pastas_vistas.setdefault(pasta_id, pasta_analise.name)

        nome_col = csv_path.name.split("__top_")[0]

        # ler CSV de forma robusta
        try:
            df = pd.read_csv(csv_path, usecols=[0,1], header=0, dtype={0:str,1:object}, names=['valor','contagem'])
        except Exception:
            try:
                df = pd.read_csv(csv_path, header=0, dtype={0:str,1:object})
                cols = list(df.columns)
                if len(cols) >= 2:
                    df = df.rename(columns={cols[0]:'valor', cols[1]:'contagem'})[['valor','contagem']]
                else:
                    continue
            except Exception:
                continue

        # agregar counts por valor
        for _, r in df.iterrows():
            val = r['valor']
            try:
                cnt = int(r['contagem']) if pd.notna(r['contagem']) else 0
            except Exception:
                try:
                    cnt = int(float(r['contagem']))
                except Exception:
                    cnt = 0
            chave = (nome_col, None if pd.isna(val) else str(val))
            ent = agreg.get(chave)
            if ent is None:
                ent = {'count_total': 0, 'files_set': set()}
                agreg[chave] = ent
            ent['count_total'] += cnt
            ent['files_set'].add(pasta_id)

        # extrair top1_count do arquivo (primeira linha útil)
        top1_cnt = None
        if not df.empty:
            for _, rr in df.iterrows():
                if pd.notna(rr['valor']):
                    try:
                        top1_cnt = int(rr['contagem']) if pd.notna(rr['contagem']) else 0
                    except Exception:
                        try:
                            top1_cnt = int(float(rr['contagem']))
                        except Exception:
                            top1_cnt = 0
                    break
        if top1_cnt is not None:
            mapa_top1.setdefault(nome_col, []).append(top1_cnt)

    rows = []
    for (col, val), v in agreg.items():
        rows.append({'coluna': col, 'valor': val, 'count_total': v['count_total'], 'files_count': len(v['files_set'])})
    df_global = pd.DataFrame(rows)
    folder_ids = list(pastas_vistas.keys())
    return df_global, folder_ids, mapa_top1

# ---------------- util: agregar summaries por pasta ----------------
def identificar_colunas_possiveis(columns):
    mapping = {}
    lower = [c.lower() for c in columns]
    for c in columns:
        lc = c.lower()
        if 'distinct' in lc or 'distint' in lc or 'distinct_est' in lc or 'distintos' in lc:
            mapping['distinct'] = c
        elif 'null' in lc or 'nulos' in lc:
            mapping['nulls'] = c
        elif 'linh' in lc or 'row' in lc or 'count' in lc or 'linhas' in lc:
            mapping['linhas'] = c
        elif 'tipo' in lc or 'type' in lc:
            mapping['tipo'] = c
        elif 'coluna' in lc or 'column' in lc:
            mapping['coluna'] = c
    return mapping

def agregar_summaries_por_pasta(diretorio_base: Path):
    """
    Lê todos summary_by_column.csv e agrega listas de distinct/nulls por coluna.
    Retorna:
      df_stats (com média/std/var e n_amostras)
      lists_map (listas brutas)
    """
    paths = encontrar_summary_recursivo(diretorio_base)
    if not paths:
        return pd.DataFrame(columns=['coluna']), {}

    acc_nulls = {}
    acc_distinct = {}
    acc_tipo = {}

    for p in paths:
        try:
            try:
                df = pd.read_csv(p, dtype=str, encoding='utf-8')
            except Exception:
                df = pd.read_csv(p, dtype=str, encoding='latin1')
        except Exception:
            continue

        cols_map = identificar_colunas_possiveis(list(df.columns))
        col_field = cols_map.get('coluna') or (df.columns[0] if len(df.columns)>0 else None)
        if col_field is None:
            continue

        for _, r in df.iterrows():
            coluna = str(r.get(col_field) or "").strip()
            if not coluna:
                continue

            # nulls
            nnulls = None
            if 'nulls' in cols_map:
                try:
                    raw = r.get(cols_map['nulls'])
                    nnulls = int(float(raw)) if raw not in (None,"","nan") else None
                except Exception:
                    nnulls = None
            else:
                # tentativa por nomes comuns
                for k in ['nulls','nulos','nulo','nulos_total']:
                    if k in df.columns:
                        try:
                            v = r.get(k); nnulls = int(float(v)) if v not in (None,"","nan") else None; break
                        except Exception:
                            nnulls = None
            if nnulls is not None:
                acc_nulls.setdefault(coluna, []).append(nnulls)

            # distinct
            dval = None
            if 'distinct' in cols_map:
                try:
                    raw = r.get(cols_map['distinct'])
                    dval = int(float(raw)) if raw not in (None,"","nan") else None
                except Exception:
                    dval = None
            else:
                for k in ['distinct_est','distinct','distincto','distintos']:
                    if k in df.columns:
                        try:
                            v = r.get(k); dval = int(float(v)) if v not in (None,"","nan") else None; break
                        except:
                            dval = None
            if dval is not None:
                acc_distinct.setdefault(coluna, []).append(dval)

            # tipo aparente
            tipo_field = cols_map.get('tipo')
            tipo_val = None
            if tipo_field:
                tipo_val = r.get(tipo_field)
            else:
                for k in ['tipo_aparente','tipo','type']:
                    if k in df.columns:
                        tipo_val = r.get(k); break
            if isinstance(tipo_val, str) and tipo_val.strip():
                acc_tipo.setdefault(coluna, Counter())[tipo_val.strip()] += 1

    rows = []
    lists_map = {}
    todas_cols = set(list(acc_nulls.keys()) + list(acc_distinct.keys()) + list(acc_tipo.keys()))
    for col in todas_cols:
        nulls_list = acc_nulls.get(col, [])
        distinct_list = acc_distinct.get(col, [])
        tipo_counter = acc_tipo.get(col, Counter())

        stats_nulls = stats_from_list(nulls_list)
        stats_distinct = stats_from_list(distinct_list)
        tipo_mais = tipo_counter.most_common(1)[0][0] if tipo_counter else ""

        rows.append({
            'coluna': col,
            'tipo_aparente_mais_comum': tipo_mais,
            'nulls_média': stats_nulls['mean'],
            'nulls_std': stats_nulls['std'],
            'nulls_var': stats_nulls['var'],
            'nulls_n': stats_nulls['n'],
            'distinct_média': stats_distinct['mean'],
            'distinct_std': stats_distinct['std'],
            'distinct_var': stats_distinct['var'],
            'distinct_n': stats_distinct['n']
        })
        lists_map[col] = {'nulls': nulls_list, 'distinct': distinct_list}
    df_stats = pd.DataFrame(rows)
    return df_stats, lists_map

# ---------------- util: escrever DB global ----------------
def gravar_db_global(df_global: pd.DataFrame, caminho_sqlite: Path):
    conn = sqlite3.connect(str(caminho_sqlite))
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS global_counts (
        coluna TEXT NOT NULL,
        valor TEXT,
        count_total INTEGER NOT NULL DEFAULT 0,
        files_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(coluna, valor)
    )
    """)
    conn.commit()
    cur.execute("DELETE FROM global_counts")
    conn.commit()
    ins = []
    for _, r in df_global.iterrows():
        ins.append((r['coluna'], r['valor'], int(r['count_total']), int(r['files_count'])))
    if ins:
        cur.executemany("INSERT INTO global_counts(coluna, valor, count_total, files_count) VALUES (?,?,?,?)", ins)
        conn.commit()
    conn.close()

# ---------------- util: resumo por coluna (global) ----------------
def gerar_csv_resumo_global(df_global: pd.DataFrame, folder_ids, caminho_csv: Path):
    rows = []
    for col, g in df_global.groupby('coluna'):
        distinct_global = int(g['valor'].nunique(dropna=True))
        top = g.sort_values(['files_count','count_total'], ascending=[False,False]).head(1)
        if not top.empty:
            top_row = top.iloc[0]
            top1_val = top_row['valor']
            top1_cnt_total = int(top_row['count_total'])
        else:
            top1_val = ""
            top1_cnt_total = 0
        rows.append({
            'coluna': col,
            'distinct_global': distinct_global,
            'top1_value': top1_val,
            'top1_count_total': top1_cnt_total
        })
    df_summary = pd.DataFrame(rows).sort_values(['distinct_global','top1_count_total'], ascending=[False,False])
    df_summary.to_csv(caminho_csv, index=False, encoding='utf-8')
    return df_summary

# ---------------- util: CSV em data URI ----------------
def csv_para_data_uri(df: pd.DataFrame):
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding='utf-8')
    enc = base64.b64encode(buf.getvalue().encode('utf-8')).decode('ascii')
    return f"data:text/csv;base64,{enc}"

# ---------------- util: gráfico HTML ----------------
def gerar_html_grafico_top(df_top: pd.DataFrame, coluna: str, top_n:int=50):
    if df_top is None or df_top.empty:
        return "<p><em>Sem dados para gráfico.</em></p>"
    dfv = df_top.head(top_n)
    labels = dfv['valor'].astype(str).tolist()
    counts = dfv['count_total'].astype(int).tolist()
    filesc = dfv['files_count'].astype(int).tolist()
    hover = [f"{html.escape(str(v))}<br>contagem_total: {ct}<br>apareceu_em_arquivos: {fc}" for v,ct,fc in zip(labels, counts, filesc)]
    fig = go.Figure(go.Bar(x=counts, y=labels, orientation='h', marker_color='steelblue', hovertext=hover, hoverinfo='text'))
    fig.update_layout(title=f"Top valores agregados em {coluna}", height=max(300, 25*len(labels)), margin=dict(l=250, r=30, t=40, b=30), xaxis_title="Contagem total (soma nos bancos)", yaxis_title="Valor")
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

# ---------------- monta HTML final (Português) ----------------
def montar_html(df_summary: pd.DataFrame, df_global: pd.DataFrame, df_stats: pd.DataFrame, mapa_top1: dict, folder_ids, caminho_html: Path, nome_tabela: str, top_n:int=50):
    total_files = len(folder_ids)
    stats_map = {}
    if not df_stats.empty:
        for _, r in df_stats.iterrows():
            stats_map[r['coluna']] = r.to_dict()

    linhas_html = []
    secoes_html = []
    for _, r in df_summary.iterrows():
        col = r['coluna']
        distinct_global = r.get('distinct_global', 0)
        top1_val = r.get('top1_value') or ""
        top1_cnt_total = r.get('top1_count_total', 0)

        stat = stats_map.get(col, {})
        tipo_aparente = stat.get('tipo_aparente_mais_comum', "")
        distinct_mean = stat.get('distinct_média', 0.0)
        distinct_std = stat.get('distinct_std', 0.0)
        distinct_n = stat.get('distinct_n', 0)
        nulls_mean = stat.get('nulls_média', 0.0)
        nulls_std = stat.get('nulls_std', 0.0)
        nulls_n = stat.get('nulls_n', 0)

        top1_list = mapa_top1.get(col, [])
        top1_stats = stats_from_list(top1_list)
        top1_mean = top1_stats['mean']; top1_std = top1_stats['std']; top1_var = top1_stats['var']; top1_cv = top1_stats['cv']; top1_n = top1_stats['n']

        # observação (consistência)
        observacao = ""
        if distinct_n > 0 and distinct_mean > distinct_global:
            observacao = "Verificar: Distinto(média) > Distinto(global)"
        if distinct_n == 1:
            observacao = (observacao + " | 1 amostra - estatística limitada").strip(" |")

        # recomendação simples baseada em estabilidade
        rec = "NÃO"; rec_class = "recommend-nao"
        nm = nulls_mean if nulls_mean is not None else 0.0
        t1m = top1_mean if top1_mean is not None else 0.0
        t1s = top1_std if top1_std is not None else 0.0
        if t1m >= 1 and (t1s+1e-9) > 0 and (t1m / (t1s+1e-9) >= 1.5) and nm < 0.5:
            rec = "MOSTRAR"; rec_class = "recommend-mostrar"
        elif t1m >= 1:
            rec = "CONSIDERAR"; rec_class = "recommend-considerar"

        linha = f"""
        <tr class="{rec_class}" data-col="{html.escape(str(col))}">
          <td>{html.escape(str(col))}</td>
          <td style="text-align:center">{html.escape(str(tipo_aparente))}</td>
          <td style="text-align:right">{fmt_num(distinct_global,0)}</td>
          <td style="text-align:right">{fmt_num(distinct_mean,3)}</td>
          <td style="text-align:right">{fmt_num(distinct_std,3)}</td>
          <td style="text-align:right">{fmt_num(distinct_n,0)}</td>
          <td>{html.escape(str(top1_val))}</td>
          <td style="text-align:right">{fmt_num(top1_cnt_total,0)}</td>
          <td style="text-align:right">{fmt_num(top1_mean,3)}</td>
          <td style="text-align:right">{fmt_num(top1_std,3)}</td>
          <td style="text-align:right">{fmt_num(top1_var,3)}</td>
          <td style="text-align:right">{fmt_num(top1_cv,3)}</td>
          <td style="text-align:right">{fmt_num(top1_n,0)}</td>
          <td style="text-align:right">{fmt_num(nulls_mean,3)}</td>
          <td style="text-align:right">{fmt_num(nulls_std,3)}</td>
          <td style="text-align:right">{fmt_num(nulls_n,0)}</td>
          <td style="text-align:center"><strong>{html.escape(rec)}</strong></td>
          <td style="text-align:left">{html.escape(observacao)}</td>
          <td style="text-align:center"><button class="btn-open" data-col="{html.escape(str(col))}">Abrir</button></td>
        </tr>
        """
        linhas_html.append(linha)

        # seção por coluna
        df_top = df_global[df_global['coluna'] == col].copy()
        if not df_top.empty:
            df_top = df_top[['valor','count_total','files_count']].sort_values(['files_count','count_total'], ascending=[False,False])
        csv_uri = csv_para_data_uri(df_top) if not df_top.empty else ""
        graf_html = gerar_html_grafico_top(df_top, col, top_n=top_n)
        tabela_top_html = df_top.head(top_n).to_html(index=False, escape=False) if not df_top.empty else "<p><em>Sem valores</em></p>"
        download_html = f"<a class='download-link' href='{csv_uri}' download='{col}__top_{top_n}.csv'>Baixar CSV (top {top_n})</a>" if csv_uri else "<em>CSV não disponível</em>"

        sec = f"""
        <div class="col-section" id="section_{html.escape(col)}">
          <h3>{html.escape(col)}</h3>
          <p><strong>Top1 (valor):</strong> {html.escape(str(top1_val))} — total {fmt_num(top1_cnt_total,0)} ocorrências (soma nos bancos)</p>
          <p>Tipo aparente: <strong>{html.escape(str(tipo_aparente))}</strong> | Distinto (média/std/n): {fmt_num(distinct_mean,3)}/{fmt_num(distinct_std,3)}/{fmt_num(distinct_n,0)}</p>
          <p>{download_html}</p>
          <div style="display:flex;gap:18px;align-items:flex-start">
            <div style="flex:1">{graf_html}</div>
            <div style="width:420px;max-width:420px;overflow:auto">{tabela_top_html}</div>
          </div>
        </div>
        """
        secoes_html.append(sec)

    # HTML final (rótulos em Português)
    html_final = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Relatório Global Consolidado — {html.escape(nome_tabela)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
  <link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.4.1/css/buttons.dataTables.min.css">
  <style>
    body{{font-family:Arial,Helvetica,sans-serif;margin:18px}}
    h1{{font-size:20pt}}
    .legend{{padding:10px;background:#f6f6f6;border-radius:6px;margin-bottom:10px}}
    .recommend-mostrar{{background:#dff0d8}}
    .recommend-considerar{{background:#fff7bf}}
    .recommend-nao{{background:#ffffff}}
    .col-section{{margin-bottom:28px;padding:10px;border:1px solid #eee;border-radius:6px}}
    .controls{{margin:12px 0}}
    table.dataTable thead th{{background:#eee}}
    .small{{font-size:0.9em;color:#444}}
    .download-link{{font-weight:600}}
    .btn-open{{padding:6px 8px;}}
  </style>

  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
  <script src="https://cdn.datatables.net/buttons/2.4.1/js/dataTables.buttons.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
  <script src="https://cdn.datatables.net/buttons/2.4.1/js/buttons.html5.min.js"></script>
</head>
<body>
  <h1>Relatório Global Consolidado — {html.escape(nome_tabela)}</h1>
  <div class="legend">
    <strong>O que este relatório mostra</strong>
    <ul>
      <li><strong>Distinto (global)</strong>: número de valores distintos na união de todos os bancos.</li>
      <li><strong>Distinto (média / std / n)</strong>: média, desvio padrão e nº de amostras da cardinalidade por arquivo.</li>
      <li><strong>Top1 (contagem total)</strong>: soma das ocorrências do valor Top1 em todos os bancos.</li>
      <li><strong>Top1 (média/std/var/cv/n)</strong>: estatísticas das contagens top1 por arquivo (estabilidade).</li>
      <li><strong>Nulos (média/std/n)</strong>: média e desvio padrão dos nulos reportados por arquivo.</li>
    </ul>
    <p class="small">Observação: quando "Distinto (média)" for maior que "Distinto (global)" o script marca para verificar — geralmente indica inconsitência no summary_by_column.csv de algum banco (campo lido errado).</p>
  </div>

  <div class="controls">
    Mostrar top <input id="topN" type="number" value="{top_n}" min="1" step="1" style="width:70px"/> valores por coluna nos gráficos (alterar requer re-execução do script)
  </div>

  <h2>Tabela Resumo</h2>
  <table id="summary" class="display" style="width:100%">
    <thead>
      <tr>
        <th>Coluna</th>
        <th>Tipo aparente</th>
        <th>Distinto (global)</th>
        <th>Distinto (média)</th>
        <th>Distinto (std)</th>
        <th>Distinto (n)</th>
        <th>Top1 (valor)</th>
        <th>Top1 (contagem total)</th>
        <th>Top1 (média)</th>
        <th>Top1 (std)</th>
        <th>Top1 (var)</th>
        <th>Top1 (CV)</th>
        <th>Top1 (n)</th>
        <th>Nulos (média)</th>
        <th>Nulos (std)</th>
        <th>Nulos (n)</th>
        <th>Recomendação</th>
        <th>Observação</th>
        <th>Ações</th>
      </tr>
    </thead>
    <tbody>
      {''.join(linhas_html)}
    </tbody>
  </table>

  <hr/>
  <h2>Seções por coluna</h2>
  <div id="columns">
    {''.join(secoes_html)}
  </div>

<script>
$(document).ready(function() {{
  var tabela = $('#summary').DataTable({{
    "pageLength": 25,
    "dom": 'Bfrtip',
    "buttons": ['copy', 'csv', 'excel'],
    "fixedHeader": true,
    "columnDefs": [
      {{ "targets": [2,3,4,5,7,8,9,10,11,12,13,14,15], "className": 'dt-body-right' }}
    ],
    "language": {{
      "search": "Buscar:",
      "lengthMenu": "Mostrar _MENU_ linhas",
      "info": "Mostrando _START_ a _END_ de _TOTAL_",
      "paginate": {{
        "first": "Primeiro",
        "last": "Último",
        "next": "Próximo",
        "previous": "Anterior"
      }}
    }}
  }});

  $('#summary tbody').on('click', 'tr', function () {{
    var col = $(this).attr('data-col');
    if (!col) return;
    var id = '#section_' + col;
    var el = $(id);
    if (el.length) {{
      $('html, body').animate({{scrollTop: el.offset().top - 20}}, 400);
      el.css('box-shadow','0 0 0 3px rgba(0,123,255,0.12)');
      setTimeout(function(){{ el.css('box-shadow',''); }}, 1600);
    }}
  }});

  $(document).on('click', '.btn-open', function(e) {{
    var col = $(this).data('col');
    var id = '#section_' + col;
    var el = $(id);
    if (el.length) {{
      $('html, body').animate({{scrollTop: el.offset().top - 20}}, 400);
    }}
  }});
}});
</script>
</body>
</html>
"""
    caminho_html.write_text(html_final, encoding='utf-8')

# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(description="Construir relatório global a partir das pastas de análise por banco (busca recursiva).")
    p.add_argument("--analises", required=True, help="Diretório base onde as saídas por banco foram salvas (cada subpasta = um banco).")
    p.add_argument("--out-db", required=True, help="SQLite de saída (global_freq).")
    p.add_argument("--out-csv", required=True, help="CSV de sumário global por coluna.")
    p.add_argument("--out-html", required=True, help="HTML interativo de saída consolidado.")
    p.add_argument("--table", required=True, help="Nome da tabela (aparece no título do relatório).")
    p.add_argument("--top-n", type=int, default=50, help="Top N mostrado por coluna no HTML.")
    return p.parse_args()

# ---------------- main ----------------
def main():
    args = parse_args()
    analises_dir = Path(args.analises)
    if not analises_dir.exists():
        print("Diretório de análises não encontrado:", analises_dir)
        return 1

    csv_paths = encontrar_csvs_top_recursivo(analises_dir)
    if not csv_paths:
        print("Nenhum arquivo *__top_*.csv encontrado recursivamente em:", analises_dir)
        return 1

    print(f"Arquivos *__top_*.csv encontrados: {len(csv_paths)}. Iniciando agregação...")
    df_global, folder_ids, mapa_top1 = agregar_csvs_top(csv_paths)
    if df_global.empty:
        print("Nenhum dado agregável encontrado."); return 1

    caminho_sqlite = Path(args.out_db)
    gravar_db_global(df_global, caminho_sqlite)
    print("Banco global gravado em:", caminho_sqlite)

    caminho_csv = Path(args.out_csv)
    df_summary = gerar_csv_resumo_global(df_global, folder_ids, caminho_csv)
    print("CSV de sumário global gerado em:", caminho_csv)

    df_stats, lists_map = agregar_summaries_por_pasta(analises_dir)
    if not df_stats.empty:
        df_summary = df_summary.merge(df_stats, on='coluna', how='left')
    else:
        # garantir colunas
        for c in ['tipo_aparente_mais_comum','nulls_média','nulls_std','nulls_var','nulls_n','distinct_média','distinct_std','distinct_var','distinct_n']:
            df_summary[c] = 0 if 'n' in c else 0.0

    # calcular estatísticas top1 e adicionar ao df_summary
    top1_media = []; top1_std = []; top1_var = []; top1_cv = []; top1_n = []
    for _, row in df_summary.iterrows():
        col = row['coluna']
        lst = mapa_top1.get(col, [])
        st = stats_from_list(lst)
        top1_media.append(st['mean']); top1_std.append(st['std']); top1_var.append(st['var']); top1_cv.append(st['cv']); top1_n.append(st['n'])
    df_summary['top1_count_média'] = top1_media
    df_summary['top1_count_std'] = top1_std
    df_summary['top1_count_var'] = top1_var
    df_summary['top1_count_cv'] = top1_cv
    df_summary['top1_count_n'] = top1_n

    # garantir colunas numéricas preenchidas (safety)
    numeric_cols = ['distinct_global','distinct_média','distinct_std','distinct_n',
                    'top1_count_total','top1_count_média','top1_count_std','top1_count_var','top1_count_cv','top1_count_n',
                    'nulls_média','nulls_std','nulls_n']
    for c in numeric_cols:
        if c not in df_summary.columns:
            df_summary[c] = 0

    # salvar CSV final (com estatísticas)
    df_summary.to_csv(caminho_csv, index=False, encoding='utf-8')
    print("CSV de sumário global final (com estatísticas) gravado em:", caminho_csv)

    # gerar HTML
    caminho_html = Path(args.out_html)
    montar_html(df_summary, df_global, df_stats, mapa_top1, folder_ids, caminho_html, args.table, top_n=args.top_n)
    print("Relatório HTML global gerado em:", caminho_html)
    print("Banco global criado em:", caminho_sqlite)
    return 0

if __name__ == "__main__":
    exit(main())