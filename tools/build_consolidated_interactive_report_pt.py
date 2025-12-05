#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_consolidated_interactive_report_pt.py

Gera um único HTML interativo e autoexplicativo (Português) a partir da
saída do script analyze_single_table_by_column.py para uma tabela.

Entrada: diretório base de análises (ex.: C:\mdb2sql_fork\import_folder\Analises)
       e nome da tabela (ex.: RANGER_SOSTAT). O script procura a pasta
       mais recente que começa com "<tabela>__" e lê:
         - summary_by_column.csv
         - columns/*.csv (top values por coluna)
         - charts/*.png (opcional)

Saída: arquivo HTML (auto-conteúdo) com:
 - Tabela resumo (ordenável/filtrável) em Português
 - Seção por coluna com gráfico Plotly interativo (barras) e link para CSV
 - Metodologia e instruções em Português

Requisitos:
  pip install pandas plotly
Uso:
  python tools/build_consolidated_interactive_report_pt.py --analises "C:\mdb2sql_fork\import_folder\Analises" --table RANGER_SOSTAT --out "C:\...\relatorio_sostat_interativo.html"
"""
from pathlib import Path
import argparse
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import base64

pio.templates.default = "plotly_white"

def find_latest_analysis_folder(base_dir: Path, table_name: str):
    candidates = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith(f"{table_name}__")],
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

def read_summary_folder(folder: Path):
    summary_csv = folder / "summary_by_column.csv"
    if not summary_csv.exists():
        raise FileNotFoundError(f"summary_by_column.csv não encontrado em {folder}")
    df = pd.read_csv(summary_csv, dtype=str)
    # conversões numéricas necessárias
    for col in ['top1_count','top1_pct_of_table','nulls','distinct_est','linhas_estimadas_tabela']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def read_top_values_csv(csv_path: Path):
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, header=0, dtype={0:str,1:int})
        # garantir nomes
        cols = list(df.columns)
        if len(cols) >= 2:
            df = df.rename(columns={cols[0]:'valor', cols[1]:'contagem'})[['valor','contagem']]
        else:
            df.columns = ['valor','contagem']
        return df
    except Exception:
        # fallback leitura simples
        rows = []
        import csv
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as fh:
            r = csv.reader(fh)
            hdr = next(r, None)
            for row in r:
                if not row: continue
                val = row[0]
                try:
                    cnt = int(row[1])
                except Exception:
                    cnt = 0
                rows.append({'valor': val, 'contagem': cnt})
        return pd.DataFrame(rows)

def fig_from_top_values(df_top: pd.DataFrame, title: str):
    # df_top: columns valor, contagem
    if df_top is None or df_top.empty:
        return None
    labels = df_top['valor'].astype(str).tolist()
    counts = df_top['contagem'].astype(int).tolist()
    fig = go.Figure(go.Bar(
        x=counts,
        y=labels,
        orientation='h',
        marker_color='steelblue',
        hovertemplate='%{y}: %{x}<extra></extra>'
    ))
    fig.update_layout(
        title=title,
        height=max(300, 25*len(labels)),
        margin=dict(l=250, r=30, t=40, b=30),
        xaxis_title="Contagem absoluta",
        yaxis_title="Valor"
    )
    return fig

def embed_png_base64(png_path: Path):
    if not png_path.exists():
        return ""
    b = png_path.read_bytes()
    enc = base64.b64encode(b).decode('ascii')
    return f"data:image/png;base64,{enc}"

def build_html(summary_df: pd.DataFrame, analysis_folder: Path, table_name: str, out_file: Path, top_n_show:int=25):
    # Colunas que exibimos (em ordem)
    display_cols = [
        'coluna',
        'tipo_aparente',
        'linhas_estimadas_tabela',
        'nulls',
        'distinct_est',
        'top1_val',
        'top1_count',
        'top1_pct_of_table',
        'top_values_csv'
    ]
    present_cols = [c for c in display_cols if c in summary_df.columns]

    # Cabeçalhos em Português
    header = [
        "COLUNA",
        "TIPO APARENTE",
        "LINHAS (estimado)",
        "NULOS",
        "DISTINTOS (est.)",
        "TOP1 (valor)",
        "TOP1 (contagem)",
        "TOP1 (% da tabela)",
        "CSV (top valores)"
    ][:len(present_cols)]

    # células (valores)
    cells = [summary_df[c].fillna("").astype(str).tolist() for c in present_cols]

    # cor de fundo por linha com base no top1_pct_of_table
    fill_colors = []
    for _, r in summary_df.iterrows():
        pct = r.get('top1_pct_of_table') if 'top1_pct_of_table' in summary_df.columns else None
        try:
            pctf = float(pct) if pct not in (None,'') else 0.0
        except Exception:
            pctf = 0.0
        if pctf >= 10.0:
            fill_colors.append('#dff0d8')  # verde claro
        elif pctf >= 2.0:
            fill_colors.append('#fff7bf')  # amarelo claro
        else:
            fill_colors.append('#ffffff')  # branco

    table_fig = go.Figure(go.Table(
        header=dict(values=header, fill_color='lightgrey', align='left'),
        cells=dict(values=cells, fill_color=[fill_colors], align='left', font_size=12)
    ))
    table_html = pio.to_html(table_fig, full_html=False, include_plotlyjs='cdn')

    # Seções por coluna
    col_sections = []
    for _, row in summary_df.iterrows():
        col = row['coluna']
        title = f"Coluna: {col}"
        top_csv = Path(str(row.get('top_values_csv') or "")).expanduser()
        if top_csv and not top_csv.is_absolute():
            top_csv = analysis_folder / (top_csv.name if top_csv.name else "")
        df_top = read_top_values_csv(top_csv) if top_csv and top_csv.exists() else None
        if df_top is not None:
            # limitar exibição ao top_n_show
            df_show = df_top.head(top_n_show)
        else:
            df_show = None

        fig = fig_from_top_values(df_show, f"Top valores em {col}") if df_show is not None else None
        fig_html = pio.to_html(fig, full_html=False, include_plotlyjs=False) if fig is not None else "<p><em>Sem dados para gráfico.</em></p>"

        # thumbnail PNG se existir
        png_path = Path(str(row.get('chart_png') or ""))
        if png_path and not png_path.is_absolute():
            png_path = analysis_folder / (png_path.name if png_path.name else "")
        png_data = embed_png_base64(png_path) if png_path and png_path.exists() else ""
        png_html = f"<img src='{png_data}' style='max-width:320px;border:1px solid #ccc'/>" if png_data else ""

        download_link = ""
        if top_csv and top_csv.exists():
            # link para abrir/baixar o CSV (file://)
            download_link = f"<a href='file:///{top_csv.as_posix()}' target='_blank'>Baixar CSV (top valores)</a>"

        top1 = row.get('top1_val') or ""
        top1_cnt = row.get('top1_count') or ""
        top1_pct = row.get('top1_pct_of_table') or ""
        try:
            top1_cnt_display = int(top1_cnt) if pd.notna(top1_cnt) and top1_cnt!='' else top1_cnt
        except Exception:
            top1_cnt_display = top1_cnt

        summary_txt = f"<p><strong>Top1:</strong> {top1} — {top1_cnt_display} ocorrências ({top1_pct} % da tabela)</p>"

        section_html = f"""
        <section id="col_{col}">
          <h2>{title}</h2>
          {summary_txt}
          <p>{download_link}</p>
          <div style="display:flex;gap:20px;align-items:flex-start">
            <div style="flex:1">{fig_html}</div>
            <div style="width:340px">{png_html}</div>
          </div>
          <hr/>
        </section>
        """
        col_sections.append(section_html)

    # Metodologia e legenda em Português
    methodology_html = f"""
    <h2>Metodologia (resumida)</h2>
    <p>Este relatório mostra, para cada coluna da tabela <strong>{table_name}</strong> do banco analisado:</p>
    <ul>
      <li>Contagem absoluta dos valores (frequência) — exibida no gráfico interativo por coluna.</li>
      <li>Top1: valor mais frequente e sua contagem absoluta e porcentagem em relação ao total de linhas da tabela.</li>
      <li>CSV de top values por coluna: contém as colunas "valor" e "contagem" (ordenado por contagem).</li>
      <li>As cores na tabela resumo destacam colunas cujo Top1 representa uma parcela significativa da tabela (verde claro >=10%, amarelo >=2%).</li>
    </ul>
    <h3>Como interpretar rapidamente</h3>
    <ul>
      <li>Colunas com Top1_count alto e Top1_pct_of_table alto: sinalizam que existe um valor dominante (ex.: STATUS='ATIVO' em 60% dos registros) — útil para exibição resumida.</li>
      <li>Colunas com muitos <em>distinct</em> (alto cardinalidade): atenção — podem ser identificadores (IDs) que não são úteis em listagem principal.</li>
      <li>Colunas com muitos nulos: indicar menor cobertura; cuidado ao exibir na UI.</li>
      <li>Use os gráficos interativos para ver o top-N e decidir quais valores devem ser mostrados como filtros/painéis.</li>
    </ul>
    """

    # Montagem final do HTML
    html_parts = []
    html_parts.append("<html><head><meta charset='utf-8'><title>Relatório Consolidado - Interativo (PT)</title></head><body style='font-family:Arial,Helvetica,sans-serif;margin:20px'>")
    html_parts.append(f"<h1>Relatório Consolidado — Tabela {table_name}</h1>")
    html_parts.append("<p>Arquivo interativo com resumo por coluna e gráficos. Use a busca do navegador (Ctrl+F) para localizar colunas rapidamente.</p>")
    html_parts.append("<h2>Tabela Resumo</h2>")
    html_parts.append(table_html)
    html_parts.append("<hr/>")
    html_parts.append(methodology_html)
    html_parts.append("<h2>Seções por coluna</h2>")
    html_parts.extend(col_sections)
    html_parts.append("<p style='font-size:0.9em;color:#666'>Gerado automaticamente. Se precisar de outro formato (Excel/ZIP de imagens/CSV consolidado), peça.</p>")
    html_parts.append("</body></html>")

    out_html = "\n".join(html_parts)
    out_file.write_text(out_html, encoding='utf-8')
    return out_file

def parse_args():
    p = argparse.ArgumentParser(description="Gerar relatório interativo consolidado (PT) a partir da pasta Analises da análise por coluna.")
    p.add_argument("--analises", required=True, help="Diretório base onde as saídas do analyze_single_table_by_column.py foram salvas")
    p.add_argument("--table", required=True, help="Nome da tabela analisada (ex.: RANGER_SOSTAT)")
    p.add_argument("--out", required=True, help="Arquivo HTML de saída (ex.: C:\\...\\relatorio_interativo_sostat.html)")
    p.add_argument("--top-n", type=int, default=25, help="Top N mostrado nos gráficos (somente leitura, os CSVs já têm top N)")
    return p.parse_args()

def main():
    args = parse_args()
    analises_dir = Path(args.analises)
    if not analises_dir.exists():
        print("Diretório de análises não encontrado:", analises_dir)
        return 1
    folder = find_latest_analysis_folder(analises_dir, args.table)
    if not folder:
        print(f"Nenhuma pasta de análise encontrada para a tabela {args.table} em {analises_dir}")
        return 1
    try:
        summary_df = read_summary_folder(folder)
    except Exception as e:
        print("Erro lendo summary:", e)
        return 1
    out_file = Path(args.out)
    try:
        res = build_html(summary_df, folder, args.table, out_file, top_n_show=args.top_n)
        print("Relatório consolidado gerado em:", res)
        return 0
    except Exception as e:
        print("Erro ao construir HTML:", e)
        return 1

if __name__ == "__main__":
    main()