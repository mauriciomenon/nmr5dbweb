#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_record_across_dbs.py

Utilitário de backend (sem interface) para varrer vários arquivos de banco
(DuckDB / SQLite / Access) em um diretório e verificar, para cada arquivo,
se um determinado registro existe em uma tabela.

Este módulo é uma versão enxuta da lógica do script tools/encontrar_registro_em_bds.py,
exposta via funções Python para ser usada pelo app Flask.

Suporta apenas o modo baseado em filtros compostos (COL=VAL,...), que é o
caso de uso principal para rastrear inconsistências de registros ao longo do
tempo entre bancos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import csv
import datetime
import re
import sqlite3

try:  # opcionais
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None  # type: ignore

try:
    import pyodbc
except Exception:  # pragma: no cover
    pyodbc = None  # type: ignore


SUPPORTED_EXTS = [".duckdb", ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"]
DATE_RE = re.compile(r"(?P<y>\d{4})[-_]? ?(?P<m>\d{2})[-_]? ?(?P<d>\d{2})")


def parse_filters_string(s: str) -> List[Tuple[str, Any]]:
    """Converte string 'COL1=VAL1,COL2=VAL2' para lista [(col, val), ...].

    Valores são inferidos como int/float quando possível, senão string.
    """
    if not s:
        return []
    reader = csv.reader([s], skipinitialspace=True)
    parts = next(reader)
    filters: List[Tuple[str, Any]] = []
    for token in parts:
        if "=" not in token:
            raise ValueError(f"filtro invalido (espera COL=VAL): {token}")
        col, val = token.split("=", 1)
        col = col.strip()
        val = val.strip()
        # valores entre aspas são tratados como string literal
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            filters.append((col, val[1:-1]))
            continue
        # tenta int/float
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


def extract_date_from_filename(name: str) -> Optional[datetime.date]:
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        year = int(m.group("y"))
        month = int(m.group("m"))
        day = int(m.group("d"))
        return datetime.date(year, month, day)
    except Exception:
        return None


def list_db_files(base_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in base_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)

    # ordena preferindo datas no nome; se não tiver data, ordena por nome
    def sort_key(p: Path):
        dt = extract_date_from_filename(p.name)
        if dt:
            return (dt.toordinal(), p.name.lower())
        return (9999999, p.name.lower())

    return sorted(files, key=sort_key)


def detect_engine(path: Path) -> str:
    sfx = path.suffix.lower()
    if sfx == ".duckdb":
        return "duckdb"
    if sfx in (".sqlite", ".sqlite3", ".db"):
        return "sqlite"
    if sfx in (".mdb", ".accdb"):
        return "access"
    return "sqlite"


def list_tables_sqlite(path: Path) -> List[str]:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_columns_sqlite(path: Path, table: str) -> List[str]:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM "{table}" LIMIT 0')
        return [d[0] for d in cur.description]
    finally:
        conn.close()


def list_tables_duckdb(path: Path) -> List[str]:
    if duckdb is None:
        raise RuntimeError("duckdb nao esta instalado")
    conn = duckdb.connect(str(path))
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_columns_duckdb(path: Path, table: str) -> List[str]:
    if duckdb is None:
        raise RuntimeError("duckdb nao esta instalado")
    conn = duckdb.connect(str(path))
    try:
        cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
        return [c[0] for c in cur.description]
    finally:
        conn.close()


def list_tables_access(path: Path) -> List[str]:
    conn = connect_access(path)
    try:
        cur = conn.cursor()
        tables: List[str] = []
        for r in cur.tables():
            try:
                name = getattr(r, "table_name", None) or (r[2] if len(r) > 2 else None)
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


def list_columns_access(path: Path, table: str) -> List[str]:
    conn = connect_access(path)
    try:
        cols: List[str] = []
        cur = conn.cursor()
        try:
            for c in cur.columns(table=table):
                name = getattr(c, "column_name", None) or (c[3] if len(c) > 3 else None)
                if name:
                    cols.append(name)
        except Exception:
            # fallback: SELECT * LIMIT 0
            cur = conn.cursor()
            cur.execute(f"SELECT TOP 0 * FROM [{table}]")
            cols = [d[0] for d in cur.description]
        return cols
    finally:
        try:
            conn.close()
        except Exception:
            pass


def connect_access(path: Path):
    if pyodbc is None:
        raise RuntimeError("pyodbc nao esta instalado")
    conn = None
    last_err: Optional[Exception] = None
    conn_strs = [
        rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};",
        rf"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={path};",
    ]
    for cs in conn_strs:
        try:
            conn = pyodbc.connect(cs, autocommit=True, timeout=30)
            break
        except Exception as exc:  # pragma: no cover
            last_err = exc
            conn = None
    if conn is None:
        if last_err is not None:
            raise last_err
        raise RuntimeError("Falha ao conectar via ODBC")
    return conn


def list_tables_for_engine(engine: str, path: Path) -> List[str]:
    if engine == "sqlite":
        return list_tables_sqlite(path)
    if engine == "duckdb":
        return list_tables_duckdb(path)
    if engine == "access":
        return list_tables_access(path)
    raise RuntimeError(f"engine nao suportada: {engine}")


def list_columns_for_engine(engine: str, path: Path, table: str) -> List[str]:
    if engine == "sqlite":
        return list_columns_sqlite(path, table)
    if engine == "duckdb":
        return list_columns_duckdb(path, table)
    if engine == "access":
        return list_columns_access(path, table)
    raise RuntimeError(f"engine nao suportada: {engine}")


def build_engine_where_parts(engine: str, filters: List[Tuple[str, Any]], columns: List[str], table: str):
    column_lookup = {column.lower(): column for column in columns}
    where_parts: List[str] = []
    params: List[Any] = []
    for col, val in filters:
        real = column_lookup.get(col.lower())
        if not real:
            raise ValueError(f"coluna '{col}' nao encontrada na tabela {table}")
        if engine in ("sqlite", "duckdb"):
            where_parts.append(f'"{real}" = ?')
        else:
            where_parts.append(f"[{real}] = ?")
        params.append(val)
    if not where_parts:
        raise ValueError("nenhum filtro informado")
    return where_parts, params


def search_in_table(engine: str, path: Path, table: str, filters: List[Tuple[str, Any]]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Retorna (found, sample_row_dict, error).

    - found: True/False se algum registro foi encontrado
    - sample_row_dict: dicionário simples com alguns campos da linha encontrada
    - error: mensagem de erro (se algo deu errado ao acessar o arquivo/tabela)
    """
    try:
        cols = list_columns_for_engine(engine, path, table)
    except Exception as exc:
        return False, None, f"erro ao listar colunas: {exc}"

    try:
        where_parts, params = build_engine_where_parts(engine, filters, cols, table)
    except ValueError as exc:
        return False, None, str(exc)

    if engine == "sqlite":
        conn = sqlite3.connect(str(path))
        sql = f'SELECT * FROM "{table}" WHERE ' + " AND ".join(where_parts) + " LIMIT 1"
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return False, None, None
            desc = [d[0] for d in cur.description]
        finally:
            conn.close()
    elif engine == "duckdb":
        if duckdb is None:
            return False, None, "duckdb nao instalado"
        conn = duckdb.connect(str(path))
        sql = f'SELECT * FROM "{table}" WHERE ' + " AND ".join(where_parts) + " LIMIT 1"
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                return False, None, None
            row = rows[0]
            desc = [c[0] for c in cur.description]
        finally:
            conn.close()
    else:  # access via pyodbc
        if pyodbc is None:
            return False, None, "pyodbc nao instalado"
        try:
            conn = connect_access(path)
        except Exception as exc:
            return False, None, f"falha ao conectar via ODBC: {exc}"
        try:
            cur = conn.cursor()
            sql = (
                "SELECT TOP 1 * FROM [" + table + "] WHERE " + " AND ".join(where_parts)
            )
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return False, None, None
            desc = [d[0] for d in cur.description]
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # converte linha em dict simples, mas limitando a alguns campos mais úteis
    row_dict: Dict[str, Any] = {}
    for i, cname in enumerate(desc):
        if i >= len(row):
            break
        v = row[i]
        # serialização simples; a interface pode decidir o que exibir
        if isinstance(v, (datetime.date, datetime.datetime)):
            row_dict[cname] = v.isoformat()
        else:
            row_dict[cname] = v
    return True, row_dict, None


def find_record_across_dbs(
    base_dir: Path,
    filters_str: str,
    table: Optional[str] = None,
    max_files: int = 500,
) -> Dict[str, Any]:
    """Varre arquivos de banco em base_dir usando filtros compostos.

    Retorna um dicionário serializável em JSON com uma lista de resultados:
      {
        "dir": "...",
        "total_files": N,
        "results": [
          {
            "filename": "2025-11-05_DB4.accdb",
            "relpath": "Bancos atuais/2025-11-05_DB4.accdb",
            "engine": "access" | "sqlite" | "duckdb",
            "date": "2025-11-05" ou null,
            "size_bytes": 123456,
            "found": true/false,
            "table": "RANGER_SOSTAT" ou tabela em que achou,
            "sample": {..linha..} ou null,
            "error": "msg" ou null
          }, ...
        ]
      }
    """
    base_dir = base_dir.resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        return {"error": f"diretorio invalido: {base_dir}"}

    try:
        filters = parse_filters_string(filters_str)
    except Exception as exc:
        return {"error": f"filtros invalidos: {exc}"}
    if not filters:
        return {"error": "nenhum filtro informado"}

    files = list_db_files(base_dir)
    if not files:
        return {"error": "nenhum arquivo de banco encontrado"}

    results: List[Dict[str, Any]] = []
    for idx, f in enumerate(files, start=1):
        if idx > max_files:
            break
        engine = detect_engine(f)
        dt = extract_date_from_filename(f.name)
        relpath = str(f.relative_to(base_dir))
        info: Dict[str, Any] = {
            "filename": f.name,
            "relpath": relpath,
            "engine": engine,
            "date": dt.isoformat() if dt else None,
            "size_bytes": f.stat().st_size,
            "found": False,
            "table": None,
            "sample": None,
            "error": None,
        }
        try:
            # determina tabela(s) a examinar
            tables: List[str]
            if table:
                tables = [table]
            else:
                tables = list_tables_for_engine(engine, f)

            for t in tables:
                found, sample, err = search_in_table(engine, f, t, filters)
                if err is not None:
                    # erro específico de tabela/arquivo; registra e para este arquivo
                    info["error"] = err
                    break
                if found:
                    info["found"] = True
                    info["table"] = t
                    info["sample"] = sample
                    break
        except Exception as exc:
            info["error"] = str(exc)
        results.append(info)

    return {"dir": str(base_dir), "total_files": len(files), "results": results}
