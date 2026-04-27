#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
encontrar_registro_em_bds.py

Versão atualizada: adiciona mensagens explícitas quando a TABELA ou as COLUNAS
necessárias para os filtros não existem no arquivo. Essas mensagens aparecem
na saída (como [ERRO]) e na coluna 'error' do CSV.

Uso geral: veja os exemplos e a documentação em docs/USO-encontrar_registro_em_bds.md
(assume-se que agora o modo composto usa --filters; não há atalhos --rtuno/--pntno).
"""
from pathlib import Path
import argparse
import sys
import time
import json
import traceback
from decimal import Decimal
import datetime
import re
import csv
import hashlib
import sqlite3
from typing import Any

# libs opcionais
duckdb: Any | None = None
try:
    import duckdb as _duckdb
except Exception:
    pass
else:
    duckdb = _duckdb

pyodbc: Any | None = None
try:
    import pyodbc as _pyodbc  # ty: ignore[unresolved-import]
except Exception:
    pass
else:
    pyodbc = _pyodbc

EXTS_PADRAO = [".duckdb", ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"]
DATE_RE = re.compile(r'(?P<y>\d{4})[-_]? ?(?P<m>\d{2})[-_]? ?(?P<d>\d{2})')


def require_duckdb():
    if duckdb is None:
        raise RuntimeError("duckdb nao esta instalado")
    return duckdb

# ---------- utilitários ----------
def to_json_serializable(obj):
    try:
        if obj is None:
            return None
        if isinstance(obj, Decimal):
            if obj == obj.to_integral_value():
                return int(obj)
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except Exception:
                return obj.hex()
        if isinstance(obj, (list, tuple)):
            return [to_json_serializable(v) for v in obj]
        if isinstance(obj, dict):
            return {str(k): to_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (int, float, str, bool)):
            return obj
        try:
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)
    except Exception:
        try:
            return str(obj)
        except Exception:
            return None

def extract_date_from_filename(name: str):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        y = int(m.group('y'))
        mm = int(m.group('m'))
        d = int(m.group('d'))
        return datetime.date(y, mm, d)
    except Exception:
        return None

def ordenar_arquivos(lista_paths, order='name'):
    if order == 'mtime':
        return sorted(lista_paths, key=lambda p: p.stat().st_mtime)
    def keyfn(p):
        dt = extract_date_from_filename(p.name)
        if dt:
            return (dt.toordinal(), p.name.lower())
        return (9999999, p.name.lower())
    return sorted(lista_paths, key=keyfn)

def quick_sha1(path, nbytes=65536):
    try:
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            data = fh.read(nbytes)
            if not data:
                return None
            h.update(data)
        return h.hexdigest()
    except Exception:
        return None

# ---------- parsing de --filters ----------
def parse_filters_string(s: str):
    """
    Parse string like: 'COL1=VAL1,COL2=VAL2' or 'SUBNAM="U,05",RTUNO=1'
    Returns a list of tuples: [(col, value), ...], where value is Python str/int/float.
    """
    if not s:
        return []
    reader = csv.reader([s], skipinitialspace=True)
    parts = next(reader)
    filters = []
    for token in parts:
        if '=' not in token:
            raise ValueError(f"filtro inválido (espera COL=VAL): {token}")
        col, val = token.split('=', 1)
        col = col.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
            filters.append((col, val))
            continue
        try:
            ival = int(val)
            filters.append((col, ival))
            continue
        except Exception:
            pass
        try:
            fval = float(val)
            filters.append((col, fval))
            continue
        except Exception:
            pass
        filters.append((col, val))
    return filters

# ---------- funções para listar/colunas (por engine) ----------
def listar_tabelas_duckdb(path):
    conn = require_duckdb().connect(str(path))
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

def colunas_tabela_duckdb(path, tabela):
    conn = require_duckdb().connect(str(path))
    try:
        cur = conn.execute(f'SELECT * FROM "{tabela}" LIMIT 0')
        return [c[0] for c in cur.description]
    finally:
        conn.close()

def listar_tabelas_sqlite(path):
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

def colunas_tabela_sqlite(path, tabela):
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM "{tabela}" LIMIT 0')
        return [d[0] for d in cur.description]
    finally:
        conn.close()

def listar_tabelas_access(path):
    if pyodbc is None:
        raise RuntimeError("pyodbc não está instalado")
    conn = None
    conn_strs = [
        fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};",
        fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={path};"
    ]
    last_err = None
    for cs in conn_strs:
        try:
            conn = pyodbc.connect(cs, autocommit=True, timeout=30)
            break
        except Exception as e:
            last_err = e
            conn = None
    if conn is None:
        if last_err is not None:
            raise last_err
        raise RuntimeError("nao foi possivel conectar ao Access")
    try:
        cur = conn.cursor()
        tables=[]
        for r in cur.tables():
            try:
                name = getattr(r,"table_name",None) or (r[2] if len(r)>2 else None)
            except Exception:
                name = None
            if name and not str(name).startswith("MSys"):
                tables.append(name)
        return tables
    finally:
        try:
            conn.close()
        except Exception:
            pass

def colunas_tabela_access(path, tabela):
    if pyodbc is None:
        raise RuntimeError("pyodbc não está instalado")
    conn = None
    conn_strs = [
        fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};",
        fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={path};"
    ]
    last_err = None
    for cs in conn_strs:
        try:
            conn = pyodbc.connect(cs, autocommit=True, timeout=30)
            break
        except Exception as e:
            last_err = e
            conn = None
    if conn is None:
        if last_err is not None:
            raise last_err
        raise RuntimeError("nao foi possivel conectar ao Access")
    try:
        cols=[]
        cur = conn.cursor()
        try:
            for c in cur.columns(table=tabela):
                n = getattr(c,"column_name",None) or (c[3] if len(c)>3 else None)
                if n:
                    cols.append(n)
        except Exception:
            try:
                cur.execute(f"SELECT TOP 1 * FROM [{tabela}]")
                cols = [d[0] for d in cur.description]
            except Exception:
                cols = []
        return cols
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ---------- construir SQL WHERE e placeholders por engine ----------
def build_where_clause_and_params(engine: str, filters):
    if not filters:
        return "", [], []
    params = []
    col_names = []
    parts = []
    for col, val in filters:
        col_names.append(col)
        if engine == "access":
            parts.append(f'[{col}] = ?')
        else:
            parts.append(f'"{col}" = ?')
        params.append(val)
    where = " AND ".join(parts)
    return where, params, col_names

# ---------- checagens usando filtros (genérica) ----------
def checar_com_filtros(path, engine, tabela, filters, sample, show_cols):
    where_sql, params, cols = build_where_clause_and_params(engine, filters)
    if where_sql == "":
        return 0, None, None
    try:
        if engine == "duckdb":
            conn = require_duckdb().connect(str(path))
            try:
                sql_sample = f'SELECT * FROM "{tabela}" WHERE {where_sql} LIMIT 1'
                try:
                    row = conn.execute(sql_sample, params).fetchone()
                except Exception:
                    try:
                        count_row = conn.execute(
                            f'SELECT COUNT(*) FROM "{tabela}" WHERE {where_sql}',
                            params,
                        ).fetchone()
                        count_value = count_row[0] if count_row else 0
                        return int(count_value), None, None
                    except Exception as e2:
                        return 0, None, str(e2)
                if row:
                    cols_all = [c[0] for c in conn.execute(f'SELECT * FROM "{tabela}" LIMIT 0').description]
                    obj = {cols_all[i]: to_json_serializable(row[i]) for i in range(len(cols_all))}
                    if show_cols:
                        obj = {k: obj.get(k) for k in show_cols if k in obj}
                    return 1, obj if sample else {}, None
                count_row = conn.execute(
                    f'SELECT COUNT(*) FROM "{tabela}" WHERE {where_sql}',
                    params,
                ).fetchone()
                count_value = count_row[0] if count_row else 0
                return int(count_value), None, None
            finally:
                conn.close()

        if engine == "sqlite":
            conn = sqlite3.connect(str(path))
            try:
                cur = conn.cursor()
                try:
                    cur.execute(f'SELECT * FROM "{tabela}" WHERE {where_sql} LIMIT 1', tuple(params))
                    row = cur.fetchone()
                except Exception:
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{tabela}" WHERE {where_sql}', tuple(params))
                        return int(cur.fetchone()[0]), None, None
                    except Exception as e2:
                        return 0, None, str(e2)
                if row:
                    cols_all = [d[0] for d in cur.execute(f'SELECT * FROM "{tabela}" LIMIT 0').description]
                    obj = {cols_all[i]: to_json_serializable(row[i]) for i in range(len(cols_all))}
                    if show_cols:
                        obj = {k: obj.get(k) for k in show_cols if k in obj}
                    return 1, obj if sample else {}, None
                cur.execute(f'SELECT COUNT(*) FROM "{tabela}" WHERE {where_sql}', tuple(params))
                return int(cur.fetchone()[0]), None, None
            finally:
                conn.close()

        if engine == "access":
            if pyodbc is None:
                return 0, None, "pyodbc não está instalado"
            conn = None
            conn_strs = [
                fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={str(path)};",
                fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={str(path)};"
            ]
            last_err = None
            for cs in conn_strs:
                try:
                    conn = pyodbc.connect(cs, autocommit=True, timeout=30)
                    break
                except Exception as e:
                    last_err = e
                    conn = None
            if conn is None:
                return 0, None, str(last_err)
            try:
                cur = conn.cursor()
                try:
                    sql_sample = f"SELECT TOP 1 * FROM [{tabela}] WHERE {where_sql}"
                    cur.execute(sql_sample, tuple(params))
                    row = cur.fetchone()
                except Exception:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM [{tabela}] WHERE {where_sql}", tuple(params))
                        r = cur.fetchone()
                        return int(r[0] if r else 0), None, None
                    except Exception as e2:
                        return 0, None, str(e2)
                if row:
                    cols_all = [d[0] for d in cur.description] if cur.description else []
                    obj = {cols_all[i]: to_json_serializable(row[i]) for i in range(len(cols_all))}
                    if show_cols:
                        obj = {k: obj.get(k) for k in show_cols if k in obj}
                    return 1, obj if sample else {}, None
                try:
                    cur.execute(f"SELECT COUNT(*) FROM [{tabela}] WHERE {where_sql}", tuple(params))
                    r = cur.fetchone()
                    return int(r[0] if r else 0), None, None
                except Exception:
                    return 0, None, None
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return 0, None, "engine não suportada"
    except Exception as e:
        return 0, None, str(e)

# ---------- busca generica por valor ----------
def buscar_generico_em_tabela(path, engine, tabela, chave, col_cand, try_all_cols, sample, show_cols):
    try:
        if engine == "duckdb":
            cols_all = colunas_tabela_duckdb(path, tabela)
        elif engine == "sqlite":
            cols_all = colunas_tabela_sqlite(path, tabela)
        elif engine == "access":
            cols_all = colunas_tabela_access(path, tabela)
        else:
            return False, None, None
    except Exception:
        return False, None, None

    cols_map = {str(col).lower(): col for col in cols_all}
    ordered_cols = []
    seen = set()

    for col in col_cand or []:
        key = str(col).lower()
        actual = cols_map.get(key)
        if actual is not None and key not in seen:
            ordered_cols.append(actual)
            seen.add(key)

    if try_all_cols:
        for col in cols_all:
            key = str(col).lower()
            if key not in seen:
                ordered_cols.append(col)
                seen.add(key)

    candidate_values = [chave]
    try:
        parsed_int = int(chave)
    except Exception:
        parsed_int = None
    else:
        candidate_values.append(parsed_int)

    try:
        parsed_float = float(chave)
    except Exception:
        parsed_float = None
    else:
        if parsed_float not in candidate_values:
            candidate_values.append(parsed_float)

    for col in ordered_cols:
        for value in candidate_values:
            count, sample_row, _err = checar_com_filtros(
                path,
                engine,
                tabela,
                [(col, value)],
                sample,
                show_cols,
            )
            if count:
                return True, col, sample_row if sample else {}

    return False, None, None

# ---------- análise de CSV (função integrada) ----------
def analyze_csv_file(path_csv):
    rows=[]
    with open(path_csv, encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            r['order_idx'] = int(r.get('order_idx') or 0)
            r['found'] = (str(r.get('found','')).lower() in ('1','true','yes'))
            rows.append(r)
    rows_sorted = sorted(rows, key=lambda x: x['order_idx'])
    if not rows_sorted:
        print("CSV vazio ou inválido.")
        return
    found_indices = [i for i,r in enumerate(rows_sorted) if r['found']]
    if not found_indices:
        print("Registro NÃO encontrado em nenhum arquivo do CSV.")
        return
    first_i = found_indices[0]
    last_i = found_indices[-1]
    print("Primeiro encontrado (pela ordem):")
    print(" ", rows_sorted[first_i]['path'])
    if first_i>0 and not rows_sorted[first_i-1]['found']:
        print("Apareceu entre:")
        print("  anterior ausente:", rows_sorted[first_i-1]['path'])
        print("  primeiro presente:", rows_sorted[first_i]['path'])
    else:
        print("Apareceu no primeiro arquivo da lista (ou anterior também presente).")
    print("\nÚltimo encontrado (pela ordem):")
    print(" ", rows_sorted[last_i]['path'])
    disappeared_at=None
    for j in range(last_i+1, len(rows_sorted)):
        if not rows_sorted[j]['found']:
            disappeared_at = j
            break
    if disappeared_at:
        print("Desapareceu entre:")
        print("  último presente:", rows_sorted[last_i]['path'])
        print("  primeiro ausente após isso:", rows_sorted[disappeared_at]['path'])
    else:
        print("Registro presente na última base escaneada (nenhum desaparecimento detectado).")

# ---------- fluxo principal (scan) ----------
def scan_and_optionally_save(diretorio: Path, args):
    exts = args.exts
    arquivos = [p for p in diretorio.iterdir() if p.is_file() and p.suffix.lower() in exts]
    arquivos = ordenar_arquivos(arquivos, order=args.order)
    if not arquivos:
        print("Nenhum arquivo encontrado em", diretorio)
        return None

    results_for_csv=[]
    resultados=[]
    # determine mode: filters or key
    filters = []
    if args.filters:
        try:
            filters = parse_filters_string(args.filters)
        except Exception as e:
            print("Erro ao parsear --filters:", e, file=sys.stderr)
            return None
    rapido_filters = bool(filters)

    order_map = {str(p): idx for idx,p in enumerate(arquivos)}

    for idx, f in enumerate(arquivos):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
        ext = f.suffix.lower()
        found = False
        table_used = None
        sample = None
        count = 0
        error = None
        try:
            if rapido_filters:
                # Determine tables to try. If --table given, validate it exists.
                if args.table:
                    # check existence
                    try:
                        if ext in (".duckdb", ".db"):
                            all_tables = listar_tabelas_duckdb(f)
                        elif ext in (".sqlite", ".sqlite3"):
                            all_tables = listar_tabelas_sqlite(f)
                        elif ext in (".mdb", ".accdb"):
                            all_tables = listar_tabelas_access(f)
                        else:
                            all_tables = []
                    except Exception as e:
                        all_tables = []
                        if args.verbose:
                            print(f"[aviso] não foi possível listar tabelas em {f}: {e}", file=sys.stderr)
                    if args.table not in all_tables:
                        error = "TABELA AUSENTE"
                        # do not try further tables in this file
                        tabelas_to_try = []
                    else:
                        tabelas_to_try = [args.table]
                else:
                    # list all tables
                    try:
                        if ext in (".duckdb", ".db"):
                            tabelas_to_try = listar_tabelas_duckdb(f)
                        elif ext in (".sqlite", ".sqlite3"):
                            tabelas_to_try = listar_tabelas_sqlite(f)
                        elif ext in (".mdb", ".accdb"):
                            tabelas_to_try = listar_tabelas_access(f)
                        else:
                            tabelas_to_try = []
                    except Exception as e:
                        tabelas_to_try = []
                        if args.verbose:
                            print(f"[aviso] não foi possível listar tabelas em {f}: {e}", file=sys.stderr)

                # if we have tables, filter to the ones that contain all required columns
                if tabelas_to_try:
                    required_cols = [c for c,_ in filters]
                    tables_with_cols = []
                    for tabela in tabelas_to_try:
                        try:
                            if ext in (".duckdb", ".db"):
                                cols = [c.lower() for c in colunas_tabela_duckdb(f, tabela)]
                            elif ext in (".sqlite", ".sqlite3"):
                                cols = [c.lower() for c in colunas_tabela_sqlite(f, tabela)]
                            elif ext in (".mdb", ".accdb"):
                                cols = [c.lower() for c in colunas_tabela_access(f, tabela)]
                            else:
                                cols = []
                        except Exception:
                            cols = []
                        missing = [c for c in required_cols if c.lower() not in cols]
                        if not missing:
                            tables_with_cols.append(tabela)
                    if not tables_with_cols:
                        # no table had all required columns
                        # If user specified a table, prefer TABELA exists but COLUNA AUSENTE
                        if args.table:
                            error = (error or "") + ("; COLUNA AUSENTE" if error is None else " COLUNA AUSENTE")
                        else:
                            error = "COLUNA AUSENTE"
                        # nothing to try
                        tabelas_to_try = []
                    else:
                        tabelas_to_try = tables_with_cols

                # try filters on eligible tables
                for tabela in tabelas_to_try:
                    if ext in (".duckdb", ".db"):
                        cnt, samp, err = checar_com_filtros(f, "duckdb", tabela, filters, args.sample, args.show_cols)
                    elif ext in (".sqlite", ".sqlite3"):
                        cnt, samp, err = checar_com_filtros(f, "sqlite", tabela, filters, args.sample, args.show_cols)
                    elif ext in (".mdb", ".accdb"):
                        try:
                            cnt, samp, err = checar_com_filtros(f, "access", tabela, filters, args.sample, args.show_cols)
                        except Exception as e:
                            cnt, samp, err = 0, None, str(e)
                    else:
                        cnt, samp, err = 0, None, f"extensão não suportada: {ext}"
                    if err and not error:
                        # record first error but keep trying other tables
                        error = err
                    if cnt:
                        count = cnt
                        found = True
                        sample = samp
                        table_used = tabela
                        break
            else:
                # modo genérico por --key (coluna ou colunas comuns)
                chave = args.key
                col_cand = []
                if args.col:
                    col_cand = [args.col]
                col_cand.extend(
                    ["id", "code", "codigo", "cod", "codigo_id", "pk", "codigo_pk", "record_id", "key", "uid"]
                )
                if ext in (".duckdb", ".db"):
                    try:
                        tabelas = listar_tabelas_duckdb(f)
                    except Exception as e:
                        if args.verbose:
                            print(f"[aviso] não foi possível listar tabelas em {f}: {e}", file=sys.stderr)
                        tabelas = []
                    if args.table:
                        tabelas = [t for t in tabelas if args.table.lower() in t.lower()]
                    for t in tabelas:
                        ok, used_col, samp = buscar_generico_em_tabela(
                            f, "duckdb", t, chave, col_cand, args.try_all_cols, args.sample, args.show_cols
                        )
                        if ok:
                            found = True
                            table_used = t
                            sample = samp
                            break
                elif ext in (".sqlite", ".sqlite3"):
                    try:
                        tabelas = listar_tabelas_sqlite(f)
                    except Exception as e:
                        if args.verbose:
                            print(f"[aviso] não foi possível listar tabelas em {f}: {e}", file=sys.stderr)
                        tabelas = []
                    if args.table:
                        tabelas = [t for t in tabelas if args.table.lower() in t.lower()]
                    for t in tabelas:
                        ok, used_col, samp = buscar_generico_em_tabela(
                            f, "sqlite", t, chave, col_cand, args.try_all_cols, args.sample, args.show_cols
                        )
                        if ok:
                            found = True
                            table_used = t
                            sample = samp
                            break
                elif ext in (".mdb", ".accdb"):
                    try:
                        tabelas = listar_tabelas_access(f)
                    except Exception as e:
                        if args.verbose:
                            print(f"[aviso] não foi possível listar tabelas Access em {f}: {e}", file=sys.stderr)
                        tabelas = []
                    if args.table:
                        tabelas = [t for t in tabelas if args.table.lower() in t.lower()]
                    for t in tabelas:
                        ok, used_col, samp = buscar_generico_em_tabela(
                            f, "access", t, chave, col_cand, args.try_all_cols, args.sample, args.show_cols
                        )
                        if ok:
                            found = True
                            table_used = t
                            sample = samp
                            break
                else:
                    if args.verbose:
                        print(f"[pular] extensão não suportada: {ext}", file=sys.stderr)
        except Exception as e:
            error = str(e)
            if args.verbose:
                traceback.print_exc()

        file_mtime = f.stat().st_mtime
        file_size_kb = f.stat().st_size // 1024
        file_sha1 = quick_sha1(f)
        # print outputs: prefer explicit ERRO when error set and no found
        if args.brief:
            if error and not found:
                print(f"[ERRO]    {ts} {f} -> {error}")
            elif found:
                print(f"[ENCONTRADO] {ts} {f} tabela={table_used} count={count if count else 1}")
            else:
                print(f"[AUSENTE]   {ts} {f}")
        else:
            if error and not found:
                print(f"[ERRO]    {ts} {f} -> {error}")
            elif found:
                print(f"[ENCONTRADO] {ts} {f} tabela={table_used}")
                if args.sample and sample:
                    print("  amostra:", json.dumps(to_json_serializable(sample), ensure_ascii=False))
            else:
                print(f"[AUSENTE]   {ts} {f}")

        resultados.append({
            "path": str(f),
            "mtime": file_mtime,
            "size_kb": file_size_kb,
            "quick_sha1": file_sha1,
            "found": bool(found),
            "table": table_used,
            "count": count,
            "sample": to_json_serializable(sample) if sample else None,
            "error": error,
            "order_idx": order_map.get(str(f), idx)
        })
        if args.out_csv:
            results_for_csv.append(resultados[-1])

    # resumo baseado na ordem usada (order_idx)
    presentes=[r for r in resultados if r["found"]]
    if not presentes:
        print("\nResumo: registro NÃO encontrado em nenhum BD escaneado.")
    else:
        presentes_sorted = sorted(presentes, key=lambda r: r["order_idx"])
        primeiro = presentes_sorted[0]
        ultimo = presentes_sorted[-1]
        print("\nResumo:")
        print(f"  Primeiro encontrado (pela ordem usada) em: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(primeiro['mtime']))}  {primeiro['path']}")
        print(f"  Último encontrado (pela ordem usada) em:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ultimo['mtime']))}  {ultimo['path']}")
        resultados_ordered = sorted(resultados, key=lambda r: r["order_idx"])
        indices = [i for i, r in enumerate(resultados_ordered) if r["found"]]
        last_i = indices[-1]
        disappeared_at = None
        for j in range(last_i+1, len(resultados_ordered)):
            if not resultados_ordered[j]["found"]:
                disappeared_at = j
                break
        if disappeared_at is not None:
            print("  Desapareceu entre:")
            print(f"    {resultados_ordered[last_i]['path']}")
            print(f"    {resultados_ordered[disappeared_at]['path']}")
        else:
            print("  Registro presente na última base escaneada (nenhum desaparecimento detectado).")

    # salvar CSV se solicitado
    if args.out_csv:
        try:
            with open(args.out_csv, "w", newline='', encoding='utf-8') as fh:
                writer = csv.DictWriter(fh, fieldnames=["path","mtime","size_kb","quick_sha1","found","table","count","sample","error","order_idx"], extrasaction='ignore')
                writer.writeheader()
                for r in results_for_csv:
                    row = dict(r)
                    row["sample"] = json.dumps(r["sample"], ensure_ascii=False) if r.get("sample") else ""
                    writer.writerow(row)
            print(f"\nCSV salvo em: {args.out_csv}")
        except Exception as e:
            print("Falha ao salvar CSV:", e)
    return args.out_csv if args.out_csv else None

# ---------- CLI ----------
def parse_args():
    p=argparse.ArgumentParser(description="Localizar registro em múltiplos arquivos de BD (use --filters para filtros compostos).")
    p.add_argument("--dir","-d", help="Diretório contendo os arquivos de BD")
    p.add_argument("--key","-k", help="(modo genérico) Valor da chave a buscar (string).")
    p.add_argument("--col","-c", help="(modo genérico) Nome da coluna da chave (se souber).")
    p.add_argument("--table","-t", help="Nome (ou substring) da tabela a procurar.")
    p.add_argument("--ext","-e", nargs="*", help="Extensões a incluir (ex.: .accdb .duckdb).")
    p.add_argument("--try-all-cols", action="store_true", help="(modo genérico) tentar todas as colunas se necessário.")
    p.add_argument("--sample", action="store_true", help="Mostrar uma amostra da linha encontrada.")
    p.add_argument("--verbose","-v", action="store_true", help="Verbose")
    p.add_argument("--order", choices=["name","mtime"], default="name", help="Ordenação: por nome/data no nome (padrão) ou mtime (sistema).")
    p.add_argument("--brief", action="store_true", help="Saída compacta.")
    p.add_argument("--show-cols", help="Colunas a mostrar na amostra (RTUNO,PNTNO,...)")
    p.add_argument("--out-csv", help="Gravar resumo em CSV (path).")
    p.add_argument("--analyze-csv", help="Analisar um CSV existente (path) - imprime onde apareceu/desapareceu.")
    p.add_argument("--analyze-after", action="store_true", help="Se usado com --out-csv, analisa o CSV gerado ao final.")
    p.add_argument("--filters", help='Filtros compostos: "COL1=VAL1,COL2=VAL2". Valores com vírgula devem estar entre aspas.')
    return p.parse_args()

def main():
    args = parse_args()
    # modo análise de CSV puro
    if args.analyze_csv and not args.dir:
        analyze_csv_file(args.analyze_csv)
        return
    if not args.dir:
        print("Se não for analisar CSV existente, informe --dir DIR")
        sys.exit(2)
    directory = Path(args.dir)
    if not directory.exists() or not directory.is_dir():
        print("Diretório não encontrado:", directory, file=sys.stderr)
        sys.exit(2)
    args.exts = [e.lower() for e in args.ext] if args.ext else EXTS_PADRAO
    args.show_cols = [c.strip() for c in args.show_cols.split(",")] if args.show_cols else None

    csv_path = scan_and_optionally_save(directory, args)
    if args.analyze_after and csv_path:
        print("\n==== Analisando CSV gerado ==== \n")
        analyze_csv_file(csv_path)

if __name__ == "__main__":
    main()
