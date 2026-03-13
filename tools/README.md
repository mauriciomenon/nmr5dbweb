# Tools — Guia de Uso e Relações

Este diretório contém utilitários para:
- analisar uma tabela por coluna (por arquivo e em lote);
- consolidar relatórios interativos (por arquivo e global, agregando múltiplos bancos);
- localizar a presença de um registro ao longo de vários bancos.

## Visão Geral do Fluxo
1. **Análise por arquivo/tabela**: `analyze_single_table_by_column.py` gera CSVs e gráficos por coluna.
2. **Lote (vários bancos)**: `batch_analyze_all_dbs.py` executa o script acima para muitos arquivos.
3. **Relatório interativo (por arquivo)**: `build_consolidated_interactive_report_pt.py` compila a última análise em um HTML navegável.
4. **Relatório global (vários bancos)**: `build_global_report_from_analyses.py` agrega todas as análises (CSV, HTML interativo e um SQLite global).
5. **Busca de registro**: `encontrar_registro_em_bds.py` verifica em quais bancos um registro aparece/desaparece.

## Scripts

### `auto_compare_report.py`
- **O que faz**: compara 2 bancos e gera report em `HTML`, `MD` e `TXT` com foco em leitura operacional.
- **Engines**: aceita fonte Access (`.mdb/.accdb`), DuckDB e SQLite; prepara derivados quando necessario.
- **Saidas**:
  - `documentos/reports/db_compare_<timestamp>_<a>_vs_<b>.html`
  - `documentos/reports/db_compare_<timestamp>_<a>_vs_<b>.md`
  - `documentos/reports/db_compare_<timestamp>_<a>_vs_<b>.txt`
  - atalhos `latest_db_compare_report.*`
- **Modo default (2 ultimos Access)**:
```bash
PYTHONPATH=. uv run python tools/auto_compare_report.py
```
  - no prompt `Comandos: Enter=manter | m=alterar | q=sair` e `>`, pressione `Enter` para seguir direto com o default dos 2 ultimos `.accdb`.
- **Modo direto (sem menu)**:
```bash
PYTHONPATH=. uv run python tools/auto_compare_report.py \
  --db1 "documentos/2026-01-29 DB2.accdb" \
  --db2 "documentos/2026-02-27 DB4.accdb"
```

### `analyze_single_table_by_column.py`
- **O que faz**: para uma tabela de um arquivo de banco, calcula por coluna: nulos, distintos, top valores (CSV) e gráfico de barras (PNG).
- **Engines**: DuckDB (`.duckdb/.db`), SQLite (`.sqlite/.db/.sqlite3`), Access (`.mdb/.accdb` via `pyodbc`).
- **Saídas** (em `<outdir>/<table>__<timestamp>/`):
  - `summary_by_column.csv`
  - `columns/<COL>__top_N.csv`
  - `charts/<COL>__top_N.png`
- **Exemplos**:
```pwsh
python .\tools\analyze_single_table_by_column.py `
  --db "C:\caminho\meu.duckdb" `
  --table "RANGER_SOSTAT" `
  --outdir "C:\saida" --top 20 -v
```

### `batch_analyze_all_dbs.py`
- **O que faz**: percorre um diretório, encontra bancos por extensão e roda `analyze_single_table_by_column.py` para cada arquivo.
- **Saída**: cria subpastas por banco dentro de `--outdir`.
- **Exemplo**:
```pwsh
python .\tools\batch_analyze_all_dbs.py `
  --db-dir "C:\mdb2sql_fork\import_folder\Bancos atuais" `
  --table "RANGER_SOSTAT" `
  --outdir "C:\mdb2sql_fork\import_folder\Analises" `
  --extensions .accdb .mdb .duckdb -v
```

### `build_consolidated_interactive_report_pt.py`
- **O que faz**: gera um único HTML interativo (Plotly) da **última** pasta de análise para uma tabela.
- **Consome**: `summary_by_column.csv`, `columns/*.csv` e opcional `charts/*.png`.
- **Exemplo**:
```pwsh
python .\tools\build_consolidated_interactive_report_pt.py `
  --analises "C:\mdb2sql_fork\import_folder\Analises" `
  --table "RANGER_SOSTAT" `
  --out "C:\mdb2sql_fork\import_folder\Analises\relatorio_sostat_interativo.html"
```

### `build_global_report_from_analyses.py`
- **O que faz**: agrega **todas** as pastas de análise (múltiplos bancos) e produz:
  - `global_freq_*.db` (SQLite com `global_counts`),
  - `global_summary_by_column.csv` (sumário global),
  - `relatorio_global_*.html` (HTML interativo com DataTables e gráficos por coluna).
- **Consome**: `*__top_*.csv` e `summary_by_column.csv` de cada pasta sob `--analises`.
- **Exemplo**:
```pwsh
python .\tools\build_global_report_from_analyses.py `
  --analises "C:\mdb2sql_fork\import_folder\analises2" `
  --out-db "C:\mdb2sql_fork\import_folder\analises2\global_freq_RANGER_SOSTAT.db" `
  --out-csv "C:\mdb2sql_fork\import_folder\analises2\global_summary_by_column.csv" `
  --out-html "C:\mdb2sql_fork\import_folder\analises2\relatorio_global_RANGER_SOSTAT.html" `
  --table "RANGER_SOSTAT" --top-n 50
```

### `encontrar_registro_em_bds.py`
- **O que faz**: varre um diretório com muitos bancos e indica se um registro aparece/ some ao longo da sequência.
- **Modos**:
  - Com filtros compostos: `--filters "COL1=VAL1,COL2=VAL2"` (recomendado).
  - Genérico por valor: `--key "VALOR"` (opcional).
- **Saída**: imprime no terminal e pode gerar `--out-csv` com metadados (path, found, tabela, sample, error etc.).
- **Exemplos**:
```pwsh
# Filtros compostos em tabela específica
python .\tools\encontrar_registro_em_bds.py `
  --dir "C:\mdbs" --filters "RTUNO=1,PNTNO=2304" `
  --table "RANGER_SOSTAT" --out-csv "C:\saida\resultados.csv" --verbose

# Filtros compostos tentando todas as tabelas
python .\tools\encontrar_registro_em_bds.py `
  --dir "C:\mdbs" --filters 'SUBNAM="U,05",RTUNO=1' `
  --out-csv "C:\saida\resultados_todas.csv" --brief

# Modo genérico por valor
python .\tools\encontrar_registro_em_bds.py `
  --dir "C:\mdbs" --key "U05" --sample --out-csv "C:\saida\resultados_key.csv"
```

## Dependências
- `pandas` (todos os relatórios CSV/HTML),
- `matplotlib` (gráficos por coluna no analyze),
- `plotly` (HTML interativo por arquivo e global),
- `duckdb` (opcional, para `.duckdb/.db`),
- `pyodbc` (opcional, Access ODBC para `.mdb/.accdb`),
- `sqlite3` (stdlib, usado nos scripts e para gerar o SQLite global).

Em Windows, para `.accdb`: instale Microsoft Access Database Engine (ACE) compatível com sua arquitetura (32/64 bits do Python).

## Boas Práticas
- Rode o `batch_analyze_all_dbs.py` antes dos relatórios para ter pastas atualizadas por banco.
- Use `--top` e `--distinct-cap` no analyze para ajustar performance em colunas com alta cardinalidade.
- No relatório global, verifique observações que sinalizam inconsistência (ex.: Distinto(média) > Distinto(global)).
- Sempre versionar os artefatos (`summary_by_column.csv`, `columns/*.csv`, HTMLs) com timestamp/pasta por banco.

## Dicas Rápidas
- Para testar rápido um único banco:
```pwsh
python .\tools\analyze_single_table_by_column.py --db "C:\meu.duckdb" --table RANGER_SOSTAT --outdir "C:\saida" -v
python .\tools\build_consolidated_interactive_report_pt.py --analises "C:\saida" --table RANGER_SOSTAT --out "C:\saida\relatorio.html"
```
- Para consolidar globalmente vários bancos já analisados:
```pwsh
python .\tools\build_global_report_from_analyses.py `
  --analises "C:\mdb2sql_fork\import_folder\analises2" `
  --out-db "C:\mdb2sql_fork\import_folder\analises2\global_freq_RANGER_SOSTAT.db" `
  --out-csv "C:\mdb2sql_fork\import_folder\analises2\global_summary_by_column.csv" `
  --out-html "C:\mdb2sql_fork\import_folder\analises2\relatorio_global_RANGER_SOSTAT.html" `
  --table "RANGER_SOSTAT" --top-n 50
```
