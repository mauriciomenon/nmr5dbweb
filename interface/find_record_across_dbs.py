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
import os
import re
import sqlite3
from interface.access_parser_utils import (
    load_access_parser_module,
    list_access_tables_from_parser,
    normalize_access_parser_rows,
)
from interface.sql_identifiers import quote_engine_identifier, select_known_identifier

try:  # opcionais
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None  # type: ignore

try:
    import pyodbc as _pyodbc  # ty: ignore[unresolved-import]
    pyodbc: Any = _pyodbc
except Exception:  # pragma: no cover
    pyodbc = None


SUPPORTED_EXTS = [".duckdb", ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"]
DATE_RE = re.compile(r"(?P<y>\d{4})[-_]? ?(?P<m>\d{2})[-_]? ?(?P<d>\d{2})")


def values_equal(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if right is None:
        return left is None
    if isinstance(right, bool):
        return bool(left) == right
    if isinstance(right, int) and not isinstance(right, bool):
        try:
            return int(left) == right
        except Exception:
            return str(left) == str(right)
    if isinstance(right, float):
        try:
            return float(left) == right
        except Exception:
            return str(left) == str(right)
    return str(left) == str(right)


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
    for root, _dirs, names in os.walk(base_dir):
        root_path = Path(root)
        for name in names:
            path = root_path / name
            if path.suffix.lower() in SUPPORTED_EXTS:
                files.append(path)

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
        if sfx == ".db":
            return "sqlite" if looks_like_sqlite_file(path) else "duckdb"
        return "sqlite"
    if sfx in (".mdb", ".accdb"):
        return "access"
    return "sqlite"


def looks_like_sqlite_file(path: Path) -> bool:
    try:
        with Path(path).open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def list_tables_sqlite(path: Path) -> List[str]:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_columns_sqlite(path: Path, table: str, known_tables: Optional[List[str]] = None) -> List[str]:
    tables = known_tables if known_tables is not None else list_tables_sqlite(path)
    matched_table = select_known_identifier(table, tables)
    if matched_table is None:
        raise RuntimeError(f"tabela nao encontrada: {table}")
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        # Table name is quoted and validated against the live table list by callers.
        # codeql[py/sql-injection]
        cur.execute(f"SELECT * FROM {quote_engine_identifier('sqlite', matched_table)} LIMIT 0")
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


def list_columns_duckdb(path: Path, table: str, known_tables: Optional[List[str]] = None) -> List[str]:
    if duckdb is None:
        raise RuntimeError("duckdb nao esta instalado")
    tables = known_tables if known_tables is not None else list_tables_duckdb(path)
    matched_table = select_known_identifier(table, tables)
    if matched_table is None:
        raise RuntimeError(f"tabela nao encontrada: {table}")
    conn = duckdb.connect(str(path))
    try:
        cur = conn.execute(f"SELECT * FROM {quote_engine_identifier('duckdb', matched_table)} LIMIT 0")
        return [c[0] for c in cur.description]
    finally:
        conn.close()


def list_tables_access(path: Path) -> List[str]:
    odbc_error = None
    if pyodbc is not None:
        try:
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
        except Exception as exc:
            odbc_error = str(exc)

    tables, parser_err = list_tables_access_parser(path)
    if tables:
        return tables
    if odbc_error and parser_err:
        raise RuntimeError(f"falha ODBC: {odbc_error}; falha access-parser: {parser_err}")
    if odbc_error:
        raise RuntimeError(f"falha ODBC: {odbc_error}")
    if parser_err:
        raise RuntimeError(f"falha access-parser: {parser_err}")
    return []


def list_columns_access(path: Path, table: str, known_tables: Optional[List[str]] = None) -> List[str]:
    tables = known_tables if known_tables is not None else list_tables_access(path)
    matched_table = select_known_identifier(table, tables)
    if matched_table is None:
        raise RuntimeError(f"tabela nao encontrada: {table}")
    odbc_error = None
    if pyodbc is not None:
        try:
            conn = connect_access(path)
            try:
                cols: List[str] = []
                cur = conn.cursor()
                try:
                    for c in cur.columns(table=matched_table):
                        name = getattr(c, "column_name", None) or (c[3] if len(c) > 3 else None)
                        if name:
                            cols.append(name)
                except Exception:
                    cur = conn.cursor()
                    # Table name is quoted and validated against the live table list by callers.
                    # codeql[py/sql-injection]
                    cur.execute(f"SELECT TOP 0 * FROM {quote_engine_identifier('access', matched_table)}")
                    cols = [d[0] for d in cur.description]
                return cols
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as exc:
            odbc_error = str(exc)

    cols, parser_err = list_columns_access_parser(path, matched_table)
    if cols:
        return cols
    if odbc_error and parser_err:
        raise RuntimeError(f"falha ODBC: {odbc_error}; falha access-parser: {parser_err}")
    if odbc_error:
        raise RuntimeError(f"falha ODBC: {odbc_error}")
    if parser_err:
        raise RuntimeError(f"falha access-parser: {parser_err}")
    return []


def connect_access(path: Path):
    if pyodbc is None:
        raise RuntimeError("pyodbc nao esta instalado")
    conn = None
    last_err: Optional[Exception] = None
    errors: List[str] = []
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
            errors.append(str(exc))
            conn = None
    if conn is None:
        if errors:
            raise RuntimeError("Falha ao conectar via ODBC: " + "; ".join(errors)) from last_err
        if last_err is not None:
            raise last_err
        raise RuntimeError("Falha ao conectar via ODBC")
    return conn


def list_tables_access_parser(path: Path) -> Tuple[List[str], Optional[str]]:
    module, err = load_access_parser_module()
    if module is None:
        return [], f"modulo access-parser indisponivel: {err}"
    try:
        parser = module.AccessParser(str(path))
    except Exception as exc:
        return [], str(exc)
    try:
        return list_access_tables_from_parser(parser), None
    except Exception as exc:
        return [], str(exc)


def list_columns_access_parser(path: Path, table: str) -> Tuple[List[str], Optional[str]]:
    module, err = load_access_parser_module()
    if module is None:
        return [], f"modulo access-parser indisponivel: {err}"
    try:
        parser = module.AccessParser(str(path))
        rows = normalize_access_parser_rows(parser.parse_table(table))
    except Exception as exc:
        return [], str(exc)
    if not rows:
        return [], None
    columns = [str(col) for col in rows[0].keys()]
    return columns, None


def search_in_table_access_parser(path: Path, table: str, filters: List[Tuple[str, Any]]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    module, err = load_access_parser_module()
    if module is None:
        return False, None, f"modulo access-parser indisponivel: {err}"
    try:
        parser = module.AccessParser(str(path))
        rows = normalize_access_parser_rows(parser.parse_table(table))
    except Exception as exc:
        return False, None, f"erro access-parser: {exc}"
    if not rows:
        return False, None, None

    first = rows[0]
    lookup = {str(col).lower(): str(col) for col in first.keys()}
    for col, _val in filters:
        if str(col).lower() not in lookup:
            return False, None, f"coluna '{col}' nao encontrada na tabela {table}"

    for row in rows:
        matched = True
        for col, expected in filters:
            real_col = lookup[str(col).lower()]
            if not values_equal(row.get(real_col), expected):
                matched = False
                break
        if not matched:
            continue
        row_dict: Dict[str, Any] = {}
        for cname, value in row.items():
            if isinstance(value, (datetime.date, datetime.datetime)):
                row_dict[str(cname)] = value.isoformat()
            else:
                row_dict[str(cname)] = value
        return True, row_dict, None
    return False, None, None


def list_tables_for_engine(engine: str, path: Path) -> List[str]:
    if engine == "sqlite":
        return list_tables_sqlite(path)
    if engine == "duckdb":
        return list_tables_duckdb(path)
    if engine == "access":
        return list_tables_access(path)
    raise RuntimeError(f"engine nao suportada: {engine}")


def list_columns_for_engine(
    engine: str,
    path: Path,
    table: str,
    known_tables: Optional[List[str]] = None,
) -> List[str]:
    if engine == "sqlite":
        return list_columns_sqlite(path, table, known_tables)
    if engine == "duckdb":
        return list_columns_duckdb(path, table, known_tables)
    if engine == "access":
        return list_columns_access(path, table, known_tables)
    raise RuntimeError(f"engine nao suportada: {engine}")


def build_engine_where_parts(engine: str, filters: List[Tuple[str, Any]], columns: List[str], table: str):
    column_lookup = {column.lower(): column for column in columns}
    where_parts: List[str] = []
    params: List[Any] = []
    for col, val in filters:
        real = column_lookup.get(col.lower())
        if not real:
            raise ValueError(f"coluna '{col}' nao encontrada na tabela {table}")
        where_parts.append(f"{quote_engine_identifier(engine, real)} = ?")
        params.append(val)
    if not where_parts:
        raise ValueError("nenhum filtro informado")
    return where_parts, params


def search_in_table(
    engine: str,
    path: Path,
    table: str,
    filters: List[Tuple[str, Any]],
    known_tables: Optional[List[str]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Retorna (found, sample_row_dict, error).

    - found: True/False se algum registro foi encontrado
    - sample_row_dict: dicionario simples com a linha encontrada
    - error: mensagem de erro (se algo deu errado ao acessar o arquivo/tabela)
    """
    try:
        tables = known_tables if known_tables is not None else list_tables_for_engine(engine, path)
        matched_table = select_known_identifier(table, tables)
        if matched_table is None:
            return False, None, f"tabela '{table}' nao encontrada"
    except Exception as exc:
        return False, None, f"erro ao validar tabela: {exc}"

    if engine == "access" and pyodbc is None:
        # Fast path on non-Windows without ODBC: parse validated table once.
        return search_in_table_access_parser(path, matched_table, filters)

    try:
        cols = list_columns_for_engine(engine, path, matched_table, tables)
    except Exception as exc:
        return False, None, f"erro ao listar colunas: {exc}"

    try:
        where_parts, params = build_engine_where_parts(engine, filters, cols, matched_table)
    except ValueError as exc:
        return False, None, str(exc)

    if engine == "sqlite":
        conn = sqlite3.connect(str(path))
        sql = (
            f"SELECT * FROM {quote_engine_identifier(engine, matched_table)} WHERE "
            + " AND ".join(where_parts)
            + " LIMIT 1"
        )
        try:
            cur = conn.cursor()
            # Table and column identifiers are allow-listed and quoted; values are bound.
            # codeql[py/sql-injection]
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
        sql = (
            f"SELECT * FROM {quote_engine_identifier(engine, matched_table)} WHERE "
            + " AND ".join(where_parts)
            + " LIMIT 1"
        )
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                return False, None, None
            row = rows[0]
            desc = [c[0] for c in cur.description]
        finally:
            conn.close()
    else:  # access via pyodbc, com fallback access-parser
        if pyodbc is None:
            return search_in_table_access_parser(path, table, filters)
        try:
            conn = connect_access(path)
            try:
                cur = conn.cursor()
                sql = (
                    f"SELECT TOP 1 * FROM {quote_engine_identifier(engine, matched_table)} WHERE "
                    + " AND ".join(where_parts)
                )
                # Table and column identifiers are allow-listed and quoted; values are bound.
                # codeql[py/sql-injection]
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
        except Exception as exc:
            found, sample, parser_err = search_in_table_access_parser(path, matched_table, filters)
            if parser_err is not None:
                return False, None, f"falha ODBC: {exc}; falha access-parser: {parser_err}"
            return found, sample, None

    # Converte a linha em dict simples preservando as colunas retornadas.
    row_dict: Dict[str, Any] = {}
    for cname, v in zip(desc, row):
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
            "sample": {..linha completa..} ou null,
            "error": "msg" ou null
          }, ...
        ]
      }
    """
    try:
        filters = parse_filters_string(filters_str)
    except Exception as exc:
        return {"error": f"filtros invalidos: {exc}"}
    if not filters:
        return {"error": "nenhum filtro informado"}

    files = list_db_files(base_dir)
    if not files:
        return {"error": "nenhum arquivo de banco encontrado"}

    files_scanned = 0
    results: List[Dict[str, Any]] = []
    for idx, f in enumerate(files, start=1):
        if idx > max_files:
            break
        files_scanned += 1
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
            available_tables = list_tables_for_engine(engine, f)
            tables: List[str] = [table] if table else available_tables

            table_errors: List[str] = []
            for t in tables:
                found, sample, err = search_in_table(engine, f, t, filters, known_tables=available_tables)
                if err is not None:
                    # erro especifico de tabela; registra e segue para as demais
                    if len(table_errors) < 3:
                        table_errors.append(f"{t}: {err}")
                    continue
                if found:
                    info["found"] = True
                    info["table"] = t
                    info["sample"] = sample
                    info["error"] = None
                    break
            if not info["found"] and table_errors:
                info["error"] = "; ".join(table_errors)
        except Exception as exc:
            info["error"] = str(exc)
        results.append(info)

    return {
        "dir": str(base_dir),
        "total_files": len(files),
        "files_scanned": files_scanned,
        "limit_reached": len(files) > max_files,
        "results": results,
    }
