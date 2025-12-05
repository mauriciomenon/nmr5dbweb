#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_single_table_by_column.py

Análise inicial "do zero" conforme sua solicitação:
- Trabalhar em UM único arquivo de banco de dados e UMA tabela.
- Para cada coluna da tabela:
  - Contar quantas vezes cada valor aparece (freqência por valor).
  - Gerar CSV com os top-N valores por coluna (ordenado por número de ocorrências).
  - Gerar gráfico (PNG) de barras horizontais com os top-N valores.
  - Gerar um summary CSV com métricas simples por coluna:
      coluna, tipo_aparente, linhas_lidas, nulls, distinct_count_est, top1_val, top1_count, top1_pct

Objetivo: ter um relatório por coluna fácil de entender e visualizar (contagens absolutas),
sem tentar comparar entre bancos ainda. Depois, com esses artefatos, será fácil avançar
para comparar entre bancos, mas por enquanto trabalhamos em um arquivo / tabela apenas.

Requisitos:
- Python 3.8+
- pip install pandas matplotlib duckdb pyodbc   (pyodbc só se precisar Access)
  - duckdb é opcional mas recomendado para .duckdb/.db
  - se só usar SQLite, duckdb não é obrigatório
- Suporta engines: sqlite (.sqlite, .db), duckdb (.duckdb, .db), access (.mdb/.accdb) via pyodbc
  (para Access, certifique-se de ter o driver ODBC correto instalado)

Uso (exemplos):
- Analisar tudo numa tabela e salvar em C:\saida:
  python tools\analyze_single_table_by_column.py --db "C:\caminho\meu.db" --table RANGER_SOSTAT --outdir "C:\saida" -v

- Apenas top 15 valores por coluna:
  python tools\analyze_single_table_by_column.py --db "C:\meu.db" --table RANGER_SOSTAT --outdir "C:\saida" --top 15 -v

Comportamento para colunas com muitos valores distintos:
- O script calcula distinct_count via query no banco (eficiente) quando possível.
- Se distinct_count for maior que --distinct-cap (default 200000), o script NÃO tenta listar todos,
  apenas pega os top-N (por frequência) e cria um gráfico com os top-N + um agrupamento "OUTROS".
  Isso evita estourar memória / gerar gráficos inúteis.

Saídas geradas em --outdir (por padrão "<outdir>/<table>__<timestamp>"):
- summary_by_column.csv : resumo por coluna (linhas_lidas, nulls, distinct_est, top1_count, top1_pct)
- columns/<COLUNA>__top_values.csv : CSV com os top-N valores e counts por coluna
- charts/<COLUNA>__top_values.png : gráfico de barras horizontais com os top-N valores por coluna
"""
from pathlib import Path
import argparse
import csv
import sqlite3
import sys
import time
import math
import statistics
from collections import OrderedDict, Counter
import pandas as pd
import matplotlib.pyplot as plt

# tentar importar duckdb e pyodbc (opcionais)
try:
    import duckdb
except Exception:
    duckdb = None

try:
    import pyodbc
except Exception:
    pyodbc = None

# ---------------- utilitários ----------------
def detect_engine(db_path: Path):
    sfx = db_path.suffix.lower()
    if sfx in ['.duckdb', '.db'] and duckdb is not None:
        # prefer duckdb for .duckdb or .db if duckdb disponível
        if sfx == '.duckdb':
            return 'duckdb'
        # .db ambiguous: try duckdb first, otherwise sqlite
        return 'duckdb' if duckdb is not None else 'sqlite'
    if sfx in ['.sqlite', '.sqlite3']:
        return 'sqlite'
    if sfx in ['.mdb', '.accdb']:
        return 'access'
    # fallback: try sqlite
    return 'sqlite'

def open_conn(db_path: Path, engine: str):
    if engine == 'duckdb':
        if duckdb is None:
            raise RuntimeError("duckdb não está instalado")
        return duckdb.connect(str(db_path))
    elif engine == 'sqlite':
        conn = sqlite3.connect(str(db_path))
        return conn
    elif engine == 'access':
        if pyodbc is None:
            raise RuntimeError("pyodbc necessário para .mdb/.accdb")
        # tenta conexão ODBC (usuário precisa ter driver instalado)
        conn_strs = [
            fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={str(db_path)};",
            fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={str(db_path)};"
        ]
        last = None
        for cs in conn_strs:
            try:
                return pyodbc.connect(cs, autocommit=True, timeout=30)
            except Exception as e:
                last = e
        raise last
    else:
        raise RuntimeError("engine desconhecida")

def list_columns(db_path: Path, table: str, engine: str):
    # retorna lista de colunas no esquema (ordem de definição)
    try:
        if engine == 'duckdb':
            conn = duckdb.connect(str(db_path))
            try:
                cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
                desc = [c[0] for c in cur.description]
                return desc
            finally:
                conn.close()
        elif engine == 'sqlite':
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute(f'PRAGMA table_info("{table}")')
            cols = [r[1] for r in cur.fetchall()]
            conn.close()
            return cols
        elif engine == 'access':
            conn = open_conn(db_path, engine)
            try:
                cur = conn.cursor()
                cur.execute(f"SELECT TOP 1 * FROM [{table}]")
                cols = [d[0] for d in cur.description] if cur.description else []
                return cols
            finally:
                try: conn.close()
                except: pass
    except Exception as e:
        raise RuntimeError(f"Erro ao listar colunas da tabela {table}: {e}")

def sql_count_total(db_path: Path, table: str, engine: str):
    q = f'SELECT COUNT(*) FROM "{table}"'
    if engine == 'access':
        q = f'SELECT COUNT(*) FROM [{table}]'
    conn = open_conn(db_path, engine)
    try:
        if engine == 'duckdb':
            r = conn.execute(q).fetchone()[0]
            conn.close()
            return int(r)
        else:
            cur = conn.cursor()
            cur.execute(q)
            r = cur.fetchone()[0]
            conn.close()
            return int(r)
    except Exception as e:
        raise RuntimeError(f"Erro ao contar linhas na tabela {table}: {e}")

def sql_count_nulls(db_path: Path, table: str, col: str, engine: str):
    if engine == 'duckdb':
        q = f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL'
    elif engine == 'sqlite':
        q = f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL'
    elif engine == 'access':
        q = f'SELECT COUNT(*) FROM [{table}] WHERE [{col}] IS NULL'
    conn = open_conn(db_path, engine)
    try:
        if engine == 'duckdb':
            r = conn.execute(q).fetchone()[0]
            conn.close()
            return int(r)
        else:
            cur = conn.cursor()
            cur.execute(q)
            r = cur.fetchone()[0]
            conn.close()
            return int(r)
    except Exception as e:
        raise RuntimeError(f"Erro ao contar NULLs para {col}: {e}")

def sql_count_distinct(db_path: Path, table: str, col: str, engine: str):
    # COUNT(DISTINCT ...) pode ser pesado, mas bancos fazem isso internamente
    if engine == 'duckdb' or engine == 'sqlite':
        q = f'SELECT COUNT(DISTINCT "{col}") FROM "{table}"'
    elif engine == 'access':
        q = f"SELECT COUNT(*) FROM (SELECT DISTINCT [{col}] FROM [{table}])"
    conn = open_conn(db_path, engine)
    try:
        if engine == 'duckdb':
            r = conn.execute(q).fetchone()[0]
            conn.close()
            return int(r)
        else:
            cur = conn.cursor()
            cur.execute(q)
            r = cur.fetchone()[0]
            conn.close()
            return int(r)
    except Exception as e:
        # se falhar por falta de recursos, retorna None
        return None

def sql_top_values(db_path: Path, table: str, col: str, engine: str, limit: int = 50):
    """
    Retorna lista de tuplas (value, count) ordenada por count desc limit.
    Tenta usar GROUP BY no banco; se der erro (ex.: Access restritivo), faz fallback:
    SELECT col FROM table WHERE col IS NOT NULL  -> contar em Python (streaming).
    """
    # tentativa 1: GROUP BY direto (mais eficiente)
    try:
        if engine in ('duckdb', 'sqlite'):
            q = f'SELECT "{col}" AS value, COUNT(*) AS cnt FROM "{table}" GROUP BY "{col}" ORDER BY cnt DESC LIMIT {limit}'
        elif engine == 'access':
            q = f"SELECT TOP {limit} [{col}] AS value, COUNT(*) AS cnt FROM [{table}] GROUP BY [{col}] ORDER BY COUNT(*) DESC"
        else:
            raise RuntimeError("engine desconhecida")

        conn = open_conn(db_path, engine)
        try:
            if engine == 'duckdb':
                cur = conn.execute(q)
                rows = cur.fetchall()
                conn.close()
                return [(r[0], int(r[1])) for r in rows]
            else:
                cur = conn.cursor()
                cur.execute(q)
                rows = cur.fetchall()
                conn.close()
                res = []
                for r in rows:
                    res.append((r[0], int(r[1])))
                return res
        except Exception:
            # se falhar na execução do GROUP BY, fechamos e caímos no fallback abaixo
            try:
                conn.close()
            except Exception:
                pass
            raise
    except Exception:
        # fallback robusto: iterar valores da coluna e contar em Python (streaming)
        try:
            if engine == 'duckdb':
                conn = open_conn(db_path, engine)
                cur = conn.execute(f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL')
                cnt = Counter()
                for row in cur.fetchall():
                    v = row[0]
                    cnt[str(v)] += 1
                try:
                    conn.close()
                except Exception:
                    pass
            else:
                conn = open_conn(db_path, engine)
                cur = conn.cursor()
                if engine == 'access':
                    q2 = f'SELECT [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL'
                else:
                    q2 = f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL'
                cur.execute(q2)
                cnt = Counter()
                # iterar em streaming
                while True:
                    batch = cur.fetchmany(1000)
                    if not batch:
                        break
                    for r in batch:
                        v = r[0]
                        cnt[str(v)] += 1
                try:
                    conn.close()
                except Exception:
                    pass
            most = cnt.most_common(limit)
            return [(None if v is None else v, c) for v, c in most]
        except Exception as ex:
            raise RuntimeError(f"Erro ao obter top values para {col} (fallback): {ex}") from ex

def infer_tipo_aparente_from_sample(db_path: Path, table: str, col: str, engine: str):
    # tenta inferir tipo simples usando primeiro top non-null value
    vals = sql_top_values(db_path, table, col, engine, limit=1)
    if not vals:
        return "desconhecido"
    v = vals[0][0]
    if v is None:
        return "desconhecido"
    try:
        float(v)
        return "numérico"
    except Exception:
        s = str(v)
        if len(s) >= 8 and any(c.isalpha() for c in s):
            return "texto"
        return "texto"

# ---------------- fluxo principal ----------------
def analyze_table(db_path: Path, table: str, outdir: Path, engine: str=None, top:int=20, distinct_cap:int=200000, verbose:bool=False):
    db_path = Path(db_path)
    if engine is None:
        engine = detect_engine(db_path)
        if verbose:
            print(f"[info] engine detectada: {engine}")

    cols = list_columns(db_path, table, engine)
    if not cols:
        raise RuntimeError(f"Tabela {table} não encontrada ou sem colunas.")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_out = outdir / f"{table}__{timestamp}"
    cols_dir = base_out / "columns"
    charts_dir = base_out / "charts"
    base_out.mkdir(parents=True, exist_ok=True)
    cols_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    total_rows_in_table = None
    try:
        total_rows_in_table = sql_count_total(db_path, table, engine)
    except Exception:
        total_rows_in_table = None

    if verbose:
        print(f"[info] tabela {table} -> {len(cols)} colunas detectadas. Linhas na tabela (estimado): {total_rows_in_table}")

    for col in cols:
        if verbose:
            print(f"[processando] coluna: {col}")
        try:
            nulls = sql_count_nulls(db_path, table, col, engine)
        except Exception as e:
            nulls = None
            if verbose:
                print(f"  [aviso] não foi possível contar NULLs para {col}: {e}")

        try:
            distinct = sql_count_distinct(db_path, table, col, engine)
            # se None (falha), deixamos como None
        except Exception as e:
            distinct = None
            if verbose:
                print(f"  [aviso] distinct falhou para {col}: {e}")

        # se distinct é grande demais, apenas pedimos top-N
        to_fetch = top
        capped_flag = False
        if isinstance(distinct, int) and distinct > distinct_cap:
            capped_flag = True
            to_fetch = top  # apenas top
            if verbose:
                print(f"  [info] distinct ({distinct}) > distinct_cap ({distinct_cap}); será retornado apenas top {top} + marcar 'capped'")

        # obter top values
        try:
            top_vals = sql_top_values(db_path, table, col, engine, limit=to_fetch)
        except Exception as e:
            top_vals = []
            if verbose:
                print(f"  [erro] falha ao obter top values para {col}: {e}")
            # se falhar aqui, interrompemos para evitar resultados incompletos
            raise RuntimeError(f"Erro ao obter top values para {col}: {e}")

        # salvar CSV dos top values
        top_csv_path = cols_dir / f"{col}__top_{to_fetch}.csv"
        with open(top_csv_path, "w", newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(["valor","contagem"])
            for v,cnt in top_vals:
                w.writerow([("" if v is None else v), cnt])

        # salvar gráfico (horizontal bar)
        # preparar dados para plotting; se muitos valores, também adicionar "OUTROS"
        labels = [("" if v is None else str(v)) for v,cnt in top_vals]
        counts = [cnt for v,cnt in top_vals]
        others_count = None
        if isinstance(distinct, int) and distinct > len(top_vals):
            # tentar estimar total - sum(top) if we know total rows
            if total_rows_in_table is not None:
                others_count = max(0, total_rows_in_table - sum(counts))
            else:
                others_count = None
        if others_count and others_count>0:
            labels.append("OUTROS")
            counts.append(others_count)

        # plot horizontal bar (inverte a ordem para mostrar maior no topo)
        if counts:
            fig, ax = plt.subplots(figsize=(8, max(2, 0.4 * len(labels))))
            y_pos = list(range(len(labels)))
            ax.barh(y_pos, counts, color='steelblue')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=9)
            ax.invert_yaxis()
            ax.set_xlabel("Contagem absoluta")
            ax.set_title(f"Top {len(labels)} valores em {col}")
            plt.tight_layout()
            chart_path = charts_dir / f"{col}__top_{to_fetch}.png"
            try:
                fig.savefig(str(chart_path), dpi=150)
            except Exception as e:
                if verbose:
                    print(f"  [aviso] falha ao salvar gráfico para {col}: {e}")
            plt.close(fig)
        else:
            chart_path = None

        # top1 info
        top1_val = top_vals[0][0] if top_vals else None
        top1_count = top_vals[0][1] if top_vals else 0
        top1_pct = None
        if total_rows_in_table and top1_count:
            try:
                top1_pct = round(100.0 * top1_count / total_rows_in_table, 3)
            except Exception:
                top1_pct = None

        # inferir tipo aparente
        tipo = infer_tipo_aparente_from_sample(db_path, table, col, engine)

        summary_rows.append({
            'coluna': col,
            'tipo_aparente': tipo,
            'linhas_estimadas_tabela': total_rows_in_table if total_rows_in_table is not None else "",
            'nulls': nulls if nulls is not None else "",
            'distinct_est': distinct if distinct is not None else "",
            'distinct_capped': bool(capped_flag),
            'top1_val': "" if top1_val is None else top1_val,
            'top1_count': top1_count,
            'top1_pct_of_table': top1_pct,
            'top_values_csv': str(top_csv_path),
            'chart_png': str(chart_path) if chart_path else ""
        })

    # salvar summary CSV
    summary_csv = base_out / "summary_by_column.csv"
    pd.DataFrame(summary_rows).to_csv(summary_csv, index=False, encoding='utf-8')

    print("\nConcluído. Saída em:", base_out)
    print("Arquivos gerados (exemplos):")
    print(" - resumo por coluna:", summary_csv)
    print(" - CSVs top values por coluna:", cols_dir)
    print(" - gráficos PNG por coluna:", charts_dir)
    return base_out

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Analisar uma tabela por coluna e gerar contagens e gráficos (top values).")
    p.add_argument("--db", required=True, help="Caminho para o arquivo de banco (SQLite / DuckDB / Access).")
    p.add_argument("--table", required=True, help="Nome da tabela a analisar.")
    p.add_argument("--engine", choices=['sqlite','duckdb','access'], help="Forçar engine (opcional).")
    p.add_argument("--outdir", default=".", help="Diretório base de saída (será criado subpasta com timestamp).")
    p.add_argument("--top", type=int, default=20, help="Top N valores por coluna a listar/plotar.")
    p.add_argument("--distinct-cap", type=int, default=200000, help="Cap para considerar distinct muito grande (não listar todos).")
    p.add_argument("--verbose","-v", action="store_true", help="Verbose")
    return p.parse_args()

def main():
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print("Arquivo de banco não encontrado:", db_path); sys.exit(1)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        res = analyze_table(db_path, args.table, outdir, engine=args.engine, top=args.top, distinct_cap=args.distinct_cap, verbose=args.verbose)
    except Exception as e:
        print("Erro durante a análise:", e)
        raise
    return 0

if __name__ == "__main__":
    main()