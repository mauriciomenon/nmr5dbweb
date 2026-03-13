#!/usr/bin/env python3
"""Interactive POC to compare two database files and generate rich reports.

Supported input engines:
- Access (.accdb/.mdb)
- DuckDB (.duckdb)
- SQLite (.sqlite/.sqlite3/.db when sqlite header is present)

Flow:
1) Suggest two latest Access files in documentos.
2) Allow user to keep or change each file with a paginated selector.
3) Ensure derived duckdb/sqlite files exist when needed.
4) Compare using backend compare logic (duckdb overview).
5) Save HTML, Markdown and TXT reports with timestamp.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sqlite3
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import duckdb

from access_convert import convert_access_to_duckdb
from interface.compare_dbs import (
    compare_table_duckdb_paged,
    compare_tables_overview_duckdb,
    list_common_tables,
    list_table_columns,
)

SUPPORTED_INPUT_EXTS = {".accdb", ".mdb", ".duckdb", ".sqlite", ".sqlite3", ".db"}
ACCESS_EXTS = {".accdb", ".mdb"}
SQLITE_EXTS = {".sqlite", ".sqlite3"}
DUCKDB_EXTS = {".duckdb"}
DEFAULT_PAGE_SIZE = 10
DEFAULT_DETAIL_ROW_LIMIT = 200
ISO_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
KEY_NAME_HINTS = [
    "INHPRO",
    "ITEMNB",
    "RTUNO",
    "PNTNO",
    "UNIQID",
    "OID",
    "ID",
    "KEY",
    "COD",
    "NO",
    "NB",
]
GLOBAL_ALWAYS_COLUMNS = [
    "RTUNO",
    "PNTNO",
    "PTNAM",
    "PNTNAM",
    "STTYPE",
    "BITBYT",
    "UNIQID",
    "ITEMNB",
]
SOSTAT_ALWAYS_COLUMNS = [
    "RTUNO",
    "PNTNO",
    "PTNAM",
    "PNTNAM",
    "STTYPE",
    "BITBYT",
    "UNIQID",
    "ITEMNB",
]
SOANLG_ALWAYS_COLUMNS = [
    "RTUNO",
    "PNTNO",
    "PTNAM",
    "PNTNAM",
    "BIAS",
    "SCALE",
    "ENGINX",
    "HLIM5",
    "HLIM6",
    "LLIM5",
    "LLIM6",
    "ITEMNB",
]
INTEGER_DISPLAY_COLUMNS = {"RTUNO", "PNTNO", "UNIQID"}


@dataclass(frozen=True)
class FileItem:
    path: Path
    engine: str
    iso_date: dt.date | None
    mtime: float
    size_bytes: int


@dataclass
class PreparedSource:
    source: Path
    source_engine: str
    source_size: int
    source_mtime: str
    source_iso_date: str
    duckdb_path: Path
    sqlite_path: Path
    steps: list[str]


def parse_iso_prefix(name: str) -> dt.date | None:
    match = ISO_PREFIX_RE.match(name.strip())
    if not match:
        return None
    try:
        return dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None


def detect_engine(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in ACCESS_EXTS:
        return "access"
    if ext in DUCKDB_EXTS:
        return "duckdb"
    if ext in SQLITE_EXTS:
        return "sqlite"
    if ext == ".db":
        try:
            with path.open("rb") as fh:
                header = fh.read(16)
            if header.startswith(b"SQLite format 3"):
                return "sqlite"
        except OSError:
            return "unknown"
        try:
            conn = duckdb.connect(str(path), read_only=True)
            conn.execute("SELECT 1")
            conn.close()
            return "duckdb"
        except Exception:
            return "unknown"
    return "unknown"


def list_candidate_files(docs_dir: Path) -> list[FileItem]:
    items: list[FileItem] = []
    for path in docs_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_INPUT_EXTS:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        engine = detect_engine(path)
        if engine == "unknown":
            continue
        items.append(
            FileItem(
                path=path.resolve(),
                engine=engine,
                iso_date=parse_iso_prefix(path.name),
                mtime=st.st_mtime,
                size_bytes=st.st_size,
            )
        )
    items.sort(
        key=lambda it: (
            it.iso_date or dt.date(1900, 1, 1),
            dt.datetime.fromtimestamp(it.mtime),
            it.path.name.lower(),
        ),
        reverse=True,
    )
    return items


def suggest_two_sources(items: Sequence[FileItem]) -> tuple[FileItem, FileItem]:
    if len(items) < 2:
        raise RuntimeError("menos de dois arquivos suportados em documentos")
    access_items = [it for it in items if it.engine == "access"]
    if len(access_items) >= 2:
        return access_items[0], access_items[1]
    return items[0], items[1]


def _fmt_size(size_bytes: int) -> str:
    step = 1024.0
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < step or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= step
    return f"{size_bytes}B"


def _format_size_mb(size_bytes: int) -> str:
    mb = float(size_bytes) / (1024.0 * 1024.0)
    return f"{mb:.2f} MB"


def _format_mtime_short(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt_value = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt_value.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        pass
    return text[:16].replace("T", " ")


def _file_uri(path_text: str) -> str:
    try:
        return Path(str(path_text)).expanduser().resolve().as_uri()
    except Exception:
        return ""


def _html_link_for_path(path_text: str) -> str:
    text = html.escape(str(path_text))
    uri = _file_uri(path_text)
    if not uri:
        return text
    return f"<a href='{html.escape(uri)}' target='_blank' rel='noopener'>{text}</a>"


def _item_line(item: FileItem) -> str:
    date_label = item.iso_date.isoformat() if item.iso_date else "sem-data"
    return (
        f"{item.path.name} | {item.engine} | {date_label} | "
        f"{_fmt_size(item.size_bytes)}"
    )


def _print_page(items: Sequence[FileItem], page: int, page_size: int, label: str) -> None:
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = min(len(items), start + page_size)
    print("")
    print(
        f"Arquivos {label}[{start + 1}-{end}] de {len(items)} "
        f"(pagina {page + 1}/{total_pages})"
    )
    for idx in range(start, end):
        local_num = idx - start + 1
        global_num = idx + 1
        print(f"  {local_num:>2}. [{global_num:>3}] {_item_line(items[idx])}")
    print(
        "Comandos: numero=selecionar | n=proxima | p=anterior | "
        "/texto=filtrar | *=limpar filtro | b=voltar | q=sair"
    )


def _filter_items(items: Sequence[FileItem], term: str) -> list[FileItem]:
    needle = term.strip().lower()
    if not needle:
        return list(items)
    filtered: list[FileItem] = []
    for item in items:
        hay = (
            f"{item.path.name} {item.engine} "
            f"{item.iso_date.isoformat() if item.iso_date else ''}"
        ).lower()
        if needle in hay:
            filtered.append(item)
    return filtered


def pick_file_interactive(items: Sequence[FileItem], title: str, page_size: int = DEFAULT_PAGE_SIZE) -> FileItem | None:
    if not items:
        return None
    page = 0
    filtered_items = list(items)
    filter_term = ""
    while True:
        print("")
        print(title)
        label = f"(filtro='{filter_term}') " if filter_term else ""
        _print_page(filtered_items, page, page_size, label)
        raw = input("> ").strip().lower()
        if raw in {"q", "quit", "sair"}:
            return None
        if raw in {"b", "back", "voltar"}:
            return None
        if raw.startswith("/"):
            filter_term = raw[1:].strip()
            filtered_items = _filter_items(items, filter_term)
            page = 0
            if not filtered_items:
                print("Nenhum arquivo para o filtro informado.")
            continue
        if raw == "*":
            filter_term = ""
            filtered_items = list(items)
            page = 0
            continue
        if raw in {"n", "next", "proxima"}:
            max_page = max(0, (len(filtered_items) - 1) // page_size)
            page = min(max_page, page + 1)
            continue
        if raw in {"p", "prev", "anterior"}:
            page = max(0, page - 1)
            continue
        if raw.isdigit():
            local_num = int(raw)
            if local_num < 1 or local_num > page_size:
                print("Opcao invalida.")
                continue
            idx = page * page_size + (local_num - 1)
            if idx >= len(filtered_items):
                print("Opcao invalida.")
                continue
            return filtered_items[idx]
        print("Comando invalido.")


def _quote_identifier(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("identificador invalido")
    return '"' + name.replace('"', '""') + '"'


def _map_duck_to_sqlite_type(dtype: str) -> str:
    t = (dtype or "").upper()
    if any(token in t for token in ("INT", "HUGEINT", "UBIGINT")):
        return "INTEGER"
    if any(token in t for token in ("DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")):
        return "REAL"
    if any(token in t for token in ("BLOB", "BYTEA", "BINARY")):
        return "BLOB"
    return "TEXT"


def _map_sqlite_to_duck_type(dtype: str) -> str:
    t = (dtype or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(token in t for token in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return "DOUBLE"
    if "BLOB" in t:
        return "BLOB"
    if any(token in t for token in ("DATE", "TIME")):
        return "TIMESTAMP"
    return "VARCHAR"


def _list_duck_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.execute("SHOW TABLES").fetchall()
    names = []
    for row in rows:
        name = str(row[0])
        low = name.lower()
        if low == "_fulltext" or low.startswith("duckdb_") or low.startswith("sqlite_"):
            continue
        names.append(name)
    return sorted(names)


def _list_sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows if str(row[0]).lower() != "_fulltext"]


def convert_duckdb_to_sqlite(duck_path: Path, sqlite_path: Path) -> tuple[bool, str]:
    src = None
    dst = None
    try:
        if sqlite_path.exists():
            sqlite_path.unlink()
        src = duckdb.connect(str(duck_path), read_only=True)
        dst = sqlite3.connect(str(sqlite_path))
        tables = _list_duck_tables(src)
        if not tables:
            return False, "duckdb sem tabelas de usuario"
        for table in tables:
            info_rows = src.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
            columns = [str(row[1]) for row in info_rows]
            types = [_map_duck_to_sqlite_type(str(row[2] or "")) for row in info_rows]
            if not columns:
                continue
            col_defs = ", ".join(
                f"{_quote_identifier(col)} {dtype}" for col, dtype in zip(columns, types)
            )
            dst.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")
            dst.execute(f"CREATE TABLE {_quote_identifier(table)} ({col_defs})")
            col_list = ", ".join(_quote_identifier(col) for col in columns)
            select_q = src.execute(f"SELECT {col_list} FROM {_quote_identifier(table)}")
            insert_sql = (
                f"INSERT INTO {_quote_identifier(table)} ({col_list}) VALUES ("
                + ", ".join(["?"] * len(columns))
                + ")"
            )
            while True:
                chunk = select_q.fetchmany(2000)
                if not chunk:
                    break
                dst.executemany(insert_sql, chunk)
        dst.commit()
        return True, "duckdb_to_sqlite_ok"
    except Exception as exc:
        return False, f"duckdb_to_sqlite_failed: {exc}"
    finally:
        if src is not None:
            try:
                src.close()
            except Exception:
                pass
        if dst is not None:
            try:
                dst.close()
            except Exception:
                pass


def convert_sqlite_to_duckdb(sqlite_path: Path, duckdb_path: Path) -> tuple[bool, str]:
    scon = None
    dcon = None
    try:
        if duckdb_path.exists():
            duckdb_path.unlink()
        scon = sqlite3.connect(str(sqlite_path))
        dcon = duckdb.connect(str(duckdb_path))
        tables = _list_sqlite_tables(scon)
        if not tables:
            return False, "sqlite sem tabelas de usuario"
        for table in tables:
            info_rows = scon.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
            columns = [str(row[1]) for row in info_rows]
            types = [_map_sqlite_to_duck_type(str(row[2] or "")) for row in info_rows]
            if not columns:
                continue
            col_defs = ", ".join(
                f"{_quote_identifier(col)} {dtype}" for col, dtype in zip(columns, types)
            )
            dcon.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")
            dcon.execute(f"CREATE TABLE {_quote_identifier(table)} ({col_defs})")
            col_list = ", ".join(_quote_identifier(col) for col in columns)
            rows = scon.execute(f"SELECT {col_list} FROM {_quote_identifier(table)}")
            insert_sql = (
                f"INSERT INTO {_quote_identifier(table)} ({col_list}) VALUES ("
                + ", ".join(["?"] * len(columns))
                + ")"
            )
            while True:
                chunk = rows.fetchmany(2000)
                if not chunk:
                    break
                dcon.executemany(insert_sql, chunk)
        dcon.close()
        dcon = None
        return True, "sqlite_to_duckdb_ok"
    except Exception as exc:
        return False, f"sqlite_to_duckdb_failed: {exc}"
    finally:
        if scon is not None:
            try:
                scon.close()
            except Exception:
                pass
        if dcon is not None:
            try:
                dcon.close()
            except Exception:
                pass


def _needs_rebuild(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    try:
        return target.stat().st_mtime < source.stat().st_mtime
    except OSError:
        return True


def prepare_source(path: Path, docs_dir: Path) -> PreparedSource:
    source = path.resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source)
    engine = detect_engine(source)
    steps: list[str] = []
    stem = source.stem
    duck_target = docs_dir / f"{stem}.duckdb"
    sqlite_target = docs_dir / f"{stem}.sqlite"
    st = source.stat()
    source_size = int(st.st_size)
    source_mtime = dt.datetime.fromtimestamp(st.st_mtime).isoformat()
    source_iso = parse_iso_prefix(source.name)
    source_iso_date = source_iso.isoformat() if source_iso else ""

    if engine == "access":
        if _needs_rebuild(source, duck_target):
            ok, msg = convert_access_to_duckdb(
                str(source),
                str(duck_target),
                chunk_size=20000,
                prefer_odbc=(os.name == "nt"),
            )
            steps.append(f"access_to_duckdb: {msg}")
            if not ok:
                raise RuntimeError(f"falha na conversao Access->DuckDB: {msg}")
        else:
            steps.append("access_to_duckdb: reutilizado")
        if _needs_rebuild(duck_target, sqlite_target):
            ok, msg = convert_duckdb_to_sqlite(duck_target, sqlite_target)
            steps.append(f"duckdb_to_sqlite: {msg}")
            if not ok:
                raise RuntimeError(f"falha na conversao DuckDB->SQLite: {msg}")
        else:
            steps.append("duckdb_to_sqlite: reutilizado")
        return PreparedSource(
            source,
            engine,
            source_size,
            source_mtime,
            source_iso_date,
            duck_target.resolve(),
            sqlite_target.resolve(),
            steps,
        )

    if engine == "duckdb":
        if _needs_rebuild(source, sqlite_target):
            ok, msg = convert_duckdb_to_sqlite(source, sqlite_target)
            steps.append(f"duckdb_to_sqlite: {msg}")
            if not ok:
                raise RuntimeError(f"falha na conversao DuckDB->SQLite: {msg}")
        else:
            steps.append("duckdb_to_sqlite: reutilizado")
        return PreparedSource(
            source,
            engine,
            source_size,
            source_mtime,
            source_iso_date,
            source,
            sqlite_target.resolve(),
            steps,
        )

    if engine == "sqlite":
        if _needs_rebuild(source, duck_target):
            ok, msg = convert_sqlite_to_duckdb(source, duck_target)
            steps.append(f"sqlite_to_duckdb: {msg}")
            if not ok:
                raise RuntimeError(f"falha na conversao SQLite->DuckDB: {msg}")
        else:
            steps.append("sqlite_to_duckdb: reutilizado")
        return PreparedSource(
            source,
            engine,
            source_size,
            source_mtime,
            source_iso_date,
            duck_target.resolve(),
            source,
            steps,
        )

    raise RuntimeError(f"engine nao suportada para {source.name}")


def _score_key_name(column: str) -> int:
    key = str(column or "").upper()
    score = 0
    for idx, hint in enumerate(KEY_NAME_HINTS):
        if hint in key:
            score += 1000 - idx * 10
    if key.endswith("ID") or key.endswith("NO") or key.endswith("NB"):
        score += 200
    return score


def _count_rows(conn: duckdb.DuckDBPyConnection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").fetchone()
    return int(row[0] or 0) if row else 0


def _count_distinct_tuple(
    conn: duckdb.DuckDBPyConnection, table: str, columns: Sequence[str]
) -> int:
    if not columns:
        return 0
    cols_sql = ", ".join(_quote_identifier(c) for c in columns)
    row = conn.execute(
        f"SELECT COUNT(*) FROM (SELECT {cols_sql} FROM {_quote_identifier(table)} GROUP BY {cols_sql}) t"
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _is_unique_key(
    conn: duckdb.DuckDBPyConnection, table: str, key_columns: Sequence[str]
) -> bool:
    total = _count_rows(conn, table)
    if total == 0:
        return False
    distinct = _count_distinct_tuple(conn, table, key_columns)
    return distinct == total


def infer_key_columns(db1_path: Path, db2_path: Path, table: str, common_columns: Sequence[str]) -> list[str]:
    ordered = sorted(
        [str(col) for col in common_columns],
        key=lambda col: (-_score_key_name(col), str(col)),
    )
    if not ordered:
        raise RuntimeError(f"tabela sem colunas comuns: {table}")
    top = ordered[:10]

    c1 = duckdb.connect(str(db1_path), read_only=True)
    c2 = duckdb.connect(str(db2_path), read_only=True)
    try:
        for col in top:
            key = [col]
            if _is_unique_key(c1, table, key) and _is_unique_key(c2, table, key):
                return key
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                key = [top[i], top[j]]
                if _is_unique_key(c1, table, key) and _is_unique_key(c2, table, key):
                    return key
    finally:
        c1.close()
        c2.close()

    return [ordered[0]]


def _build_key_values_map(key_map: dict, key_columns: Sequence[str]) -> dict:
    result = {}
    key_dict = key_map if isinstance(key_map, dict) else {}
    for key_col in key_columns:
        result[key_col] = _format_display_value(key_col, key_dict.get(key_col, ""))
    return result


def _normalize_col_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name or "").upper())


def _resolve_desired_columns(desired: Sequence[str], available: Sequence[str]) -> list[str]:
    by_norm = {}
    for col in available:
        norm = _normalize_col_key(col)
        if norm and norm not in by_norm:
            by_norm[norm] = str(col)
    resolved: list[str] = []
    seen = set()
    for desired_col in desired:
        col = by_norm.get(_normalize_col_key(desired_col))
        if not col or col in seen:
            continue
        seen.add(col)
        resolved.append(col)
    return resolved


def _forced_columns_for_table(table_name: str, table_columns: Sequence[str]) -> list[str]:
    upper_name = str(table_name or "").upper()
    if upper_name.endswith("SOANLG"):
        return _resolve_desired_columns(SOANLG_ALWAYS_COLUMNS, table_columns)
    if upper_name.endswith("SOSTAT"):
        return _resolve_desired_columns(SOSTAT_ALWAYS_COLUMNS, table_columns)
    return _resolve_desired_columns(GLOBAL_ALWAYS_COLUMNS, table_columns)


def _format_numeric_as_int_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        normalized = format(value.normalize(), "f")
        return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
    text = str(value).strip()
    if not text:
        return ""
    if re.match(r"^-?\d+\.0+$", text):
        return str(int(float(text)))
    if re.match(r"^-?\d+\.$", text):
        return text[:-1]
    return text


def _format_generic_numeric_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = format(value, ".15g")
        return text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        text = format(value.normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    text = str(value).strip()
    if not text:
        return ""
    if re.match(r"^-?\d+\.0+$", text):
        return str(int(float(text)))
    if re.match(r"^-?\d+\.$", text):
        return text[:-1]
    if re.match(r"^-?\d+\.\d+$", text):
        stripped = text.rstrip("0").rstrip(".")
        return stripped if stripped else "0"
    return text


def _format_display_value(column: str, value):
    norm_col = _normalize_col_key(column)
    if norm_col in INTEGER_DISPLAY_COLUMNS:
        return _format_numeric_as_int_text(value)
    return _format_generic_numeric_text(value)


def build_table_detail_compact(compare_payload: dict, table_columns: Sequence[str]) -> dict:
    table = str(compare_payload.get("table") or "")
    key_columns = list(compare_payload.get("key_columns") or [])
    rows = list(compare_payload.get("rows") or [])
    compare_columns = list(compare_payload.get("compare_columns") or [])
    changed_cols: list[str] = []
    changed_set = set()

    for item in rows:
        if str(item.get("type") or "") != "changed":
            continue
        a_vals = item.get("a") or {}
        b_vals = item.get("b") or {}
        for col in compare_columns:
            if a_vals.get(col) != b_vals.get(col) and col not in changed_set:
                changed_set.add(col)
                changed_cols.append(col)

    forced_cols = _forced_columns_for_table(table, table_columns)
    visible_cols: list[str] = []
    seen_visible = set()
    for col in forced_cols:
        if col in seen_visible:
            continue
        seen_visible.add(col)
        visible_cols.append(col)
    for col in changed_cols:
        if col in seen_visible:
            continue
        seen_visible.add(col)
        visible_cols.append(col)
    if not visible_cols:
        fallback = [c for c in table_columns if c not in (compare_payload.get("key_columns") or [])]
        visible_cols = fallback[: min(4, len(fallback))]

    records = []
    for item in rows:
        row_type = str(item.get("type") or "")
        key_values = _build_key_values_map(item.get("key") or {}, key_columns)
        a_vals = item.get("a") or {}
        b_vals = item.get("b") or {}
        old_row = {}
        new_row = {}
        changed_map = {}
        for col in visible_cols:
            old_v = a_vals.get(col, "")
            new_v = b_vals.get(col, "")
            old_row[col] = _format_display_value(col, old_v)
            new_row[col] = _format_display_value(col, new_v)
            if row_type == "changed":
                changed_map[col] = old_v != new_v
            elif row_type == "added":
                changed_map[col] = bool(str(new_v))
            elif row_type == "removed":
                changed_map[col] = bool(str(old_v))
            else:
                changed_map[col] = old_v != new_v
        records.append(
            {
                "type": row_type,
                "key_values": key_values,
                "old": old_row,
                "new": new_row,
                "changed": changed_map,
            }
        )

    return {
        "table": table,
        "key_columns": key_columns,
        "visible_columns": visible_cols,
        "rows_total": int(compare_payload.get("total_filtered_rows") or len(rows)),
        "rows_returned": len(records),
        "summary": compare_payload.get("summary") or {},
        "records": records,
    }


def collect_table_details(
    db1_path: Path,
    db2_path: Path,
    overview_rows: Sequence[dict],
    *,
    detail_row_limit: int = DEFAULT_DETAIL_ROW_LIMIT,
) -> list[dict]:
    details = []
    for row in overview_rows:
        if str(row.get("status") or "") != "diff":
            continue
        table = str(row.get("table") or "")
        if not table:
            continue
        cols1 = list_table_columns(db1_path, table)
        cols2 = set(list_table_columns(db2_path, table))
        common_columns = [c for c in cols1 if c in cols2]
        if not common_columns:
            continue
        key_columns = infer_key_columns(db1_path, db2_path, table, common_columns)
        page_size = min(100, max(1, detail_row_limit))
        page = 1
        collected_rows = []
        compare_payload = None
        while len(collected_rows) < detail_row_limit:
            payload = compare_table_duckdb_paged(
                db1_path,
                db2_path,
                table,
                key_columns=key_columns,
                compare_columns=[c for c in common_columns if c not in key_columns],
                page=page,
                page_size=page_size,
            )
            compare_payload = payload
            collected_rows.extend(payload.get("rows") or [])
            if page >= int(payload.get("total_pages") or 1):
                break
            page += 1

        if compare_payload is None:
            continue
        compare_payload = dict(compare_payload)
        compare_payload["rows"] = collected_rows[:detail_row_limit]
        detail = build_table_detail_compact(compare_payload, common_columns)
        details.append(detail)
    return details


def summarize_overview(rows: Sequence[dict]) -> dict:
    summary = {
        "total_tables": len(rows),
        "same_tables": 0,
        "diff_tables": 0,
        "no_key_tables": 0,
        "error_tables": 0,
    }
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status == "same":
            summary["same_tables"] += 1
        elif status == "diff":
            summary["diff_tables"] += 1
        elif status == "no_key":
            summary["no_key_tables"] += 1
        else:
            summary["error_tables"] += 1
    return summary


def build_report_payload(
    a: PreparedSource,
    b: PreparedSource,
    overview_rows: Sequence[dict],
    table_details: Sequence[dict],
) -> dict:
    now = dt.datetime.now()
    summary = summarize_overview(overview_rows)
    changed_rows = [row for row in overview_rows if str(row.get("status") or "") != "same"]
    sorted_rows = sorted(
        changed_rows,
        key=lambda row: (
            str(row.get("status") or "") != "diff",
            -(int(row.get("diff_count") or 0) if str(row.get("status") or "") == "diff" else -1),
            str(row.get("table") or ""),
        ),
    )
    return {
        "generated_at": now.isoformat(),
        "generated_stamp": now.strftime("%Y%m%d_%H%M%S"),
        "source_a": {
            "file": a.source.name,
            "path": str(a.source),
            "engine": a.source_engine,
            "size_bytes": a.source_size,
            "mtime": a.source_mtime,
            "iso_date": a.source_iso_date,
            "duckdb": str(a.duckdb_path),
            "sqlite": str(a.sqlite_path),
            "steps": a.steps,
        },
        "source_b": {
            "file": b.source.name,
            "path": str(b.source),
            "engine": b.source_engine,
            "size_bytes": b.source_size,
            "mtime": b.source_mtime,
            "iso_date": b.source_iso_date,
            "duckdb": str(b.duckdb_path),
            "sqlite": str(b.sqlite_path),
            "steps": b.steps,
        },
        "summary": summary,
        "common_tables": [str(row.get("table") or "") for row in overview_rows],
        "changed_tables": [str(row.get("table") or "") for row in sorted_rows],
        "rows": list(sorted_rows),
        "table_details": list(table_details),
    }


def _html_rows(rows: Sequence[dict]) -> str:
    cells = []
    for row in rows:
        status = str(row.get("status") or "")
        css = "same"
        if status == "diff":
            css = "diff"
        elif status == "error":
            css = "error"
        elif status == "no_key":
            css = "warn"
        cells.append(
            "<tr class='"
            + css
            + "'>"
            + f"<td>{html.escape(str(row.get('table') or ''))}</td>"
            + f"<td>{html.escape(_status_label(status))}</td>"
            + f"<td>{html.escape(str(row.get('row_count_a', '')))}</td>"
            + f"<td>{html.escape(str(row.get('row_count_b', '')))}</td>"
            + f"<td>{html.escape(str(row.get('diff_count', '')))}</td>"
            + f"<td>{html.escape(str(row.get('error', '')))}</td>"
            + "</tr>"
        )
    return "\n".join(cells)


def _html_cell(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _value_css(row_type: str, line_kind: str, changed: bool) -> str:
    if not changed:
        return ""
    if row_type == "changed":
        return "value-removed" if line_kind == "old" else "value-added"
    if row_type == "added" and line_kind == "new":
        return "value-added"
    if row_type == "removed" and line_kind == "old":
        return "value-removed"
    return ""


def _type_label(row_type: str) -> str:
    if row_type == "changed":
        return "modificado"
    if row_type == "added":
        return "novo"
    if row_type == "removed":
        return "excluido"
    return row_type


def _status_label(status: str) -> str:
    if status == "diff":
        return "alterado"
    if status == "same":
        return "igual"
    if status == "no_key":
        return "sem_chave"
    if status == "error":
        return "erro"
    return status


def _source_line_labels(payload: dict) -> tuple[str, str]:
    src_a = payload.get("source_a") or {}
    src_b = payload.get("source_b") or {}
    iso_a = str(src_a.get("iso_date") or "").strip()
    iso_b = str(src_b.get("iso_date") or "").strip()
    if not iso_a:
        iso_a = (parse_iso_prefix(str(src_a.get("file") or "")) or "").isoformat() if parse_iso_prefix(str(src_a.get("file") or "")) else ""
    if not iso_b:
        iso_b = (parse_iso_prefix(str(src_b.get("file") or "")) or "").isoformat() if parse_iso_prefix(str(src_b.get("file") or "")) else ""
    label_a = f"db {iso_a}" if iso_a else "velho"
    label_b = f"db {iso_b}" if iso_b else "novo"
    return label_a, label_b


def _report_title(payload: dict) -> str:
    src_a = payload.get("source_a") or {}
    src_b = payload.get("source_b") or {}
    name_a = str(src_a.get("file") or "A")
    name_b = str(src_b.get("file") or "B")
    return f"Comparacao banco {name_a} com banco {name_b}"


def _source_steps(payload: dict) -> list[str]:
    src_a = payload.get("source_a") or {}
    src_b = payload.get("source_b") or {}
    return [str(step) for step in (list(src_a.get("steps") or []) + list(src_b.get("steps") or []))]


def _used_engine_lines(payload: dict) -> list[str]:
    src_a = payload.get("source_a") or {}
    src_b = payload.get("source_b") or {}
    engines = {str(src_a.get("engine") or "").lower(), str(src_b.get("engine") or "").lower()}
    steps = _source_steps(payload)
    lines: list[str] = []

    if "access" in engines:
        lines.append(
            "db (access mdb/accdb): entrada de dados da comparacao e etapa de conversao inicial."
        )
    if "duckdb" in engines:
        lines.append(
            "duckdb: origem direta quando informado e base SQL principal da comparacao (overview/detalhe)."
        )
    else:
        lines.append("duckdb: base SQL principal da comparacao (overview/detalhe).")

    sqlite_used = "sqlite" in engines or any(
        ("duckdb_to_sqlite" in step) or ("sqlite_to_duckdb" in step) for step in steps
    )
    if sqlite_used:
        lines.append(
            "sqlite: formato de interoperabilidade e etapa de conversao/materializacao quando necessario."
        )
    return lines


def _html_table_detail(detail: dict, line_a_label: str, line_b_label: str, table_idx: int) -> str:
    key_cols = list(detail.get("key_columns") or [])
    if not key_cols:
        key_cols = ["KEY"]
    cols = detail.get("visible_columns") or []
    if not cols:
        return "<div class='meta'>Sem colunas para exibir no modo compacto.</div>"
    key_header_cells = "".join([f"<th>{html.escape(str(col))}</th>" for col in key_cols])
    header_cells = "".join([f"<th>{html.escape(str(col))}</th>" for col in cols])
    key_filter_cells = "".join(
        [
            f"<th><input class='col-filter-input' data-col='{html.escape(str(col))}' "
            "type='text' placeholder='filtro'></th>"
            for col in key_cols
        ]
    )
    filter_cells = "".join(
        [
            f"<th><input class='col-filter-input' data-col='{html.escape(str(col))}' "
            "type='text' placeholder='filtro'></th>"
            for col in cols
        ]
    )
    all_cols = key_cols + ["tipo", "linha"] + list(cols)
    unique_cols: list[str] = []
    seen_cols: set[str] = set()
    for col in all_cols:
        col_name = str(col)
        if col_name in seen_cols:
            continue
        seen_cols.add(col_name)
        unique_cols.append(col_name)
    option_html = "".join(
        [f"<option value='{html.escape(str(col))}'>{html.escape(str(col))}</option>" for col in unique_cols]
    )
    table_id = f"detail-table-{table_idx}"
    body_rows = []
    for row_idx, item in enumerate(detail.get("records") or []):
        row_type = str(item.get("type") or "")
        row_type_label = _type_label(row_type)
        key_values = item.get("key_values") or {}
        key_cells = "".join(
            [
                f"<td data-col='{html.escape(str(col))}' rowspan='2'>{_html_cell(key_values.get(col, ''))}</td>"
                for col in key_cols
            ]
        )
        old_vals = item.get("old") or {}
        new_vals = item.get("new") or {}
        changed_map = item.get("changed") or {}
        old_cells = []
        new_cells = []
        for col in cols:
            old_css = _value_css(row_type, "old", bool(changed_map.get(col)))
            new_css = _value_css(row_type, "new", bool(changed_map.get(col)))
            old_class = f" class='{old_css}'" if old_css else ""
            new_class = f" class='{new_css}'" if new_css else ""
            old_cells.append(
                f"<td data-col='{html.escape(str(col))}'{old_class}>{_html_cell(old_vals.get(col, ''))}</td>"
            )
            new_cells.append(
                f"<td data-col='{html.escape(str(col))}'{new_class}>{_html_cell(new_vals.get(col, ''))}</td>"
            )
        status_class = ""
        if row_type == "added":
            status_class = " class='value-added'"
        elif row_type == "removed":
            status_class = " class='value-removed'"
        elif row_type == "changed":
            status_class = " class='value-changed'"
        body_rows.append(
            f"<tr data-pair='{row_idx}'>"
            + key_cells
            + f"<td data-col='tipo' rowspan='2'{status_class}>{html.escape(row_type_label)}</td>"
            + f"<td data-col='linha'>{html.escape(line_a_label)}</td>"
            + "".join(old_cells)
            + "</tr>"
        )
        body_rows.append(
            f"<tr data-pair='{row_idx}'>"
            + f"<td data-col='linha'>{html.escape(line_b_label)}</td>"
            + "".join(new_cells)
            + "</tr>"
        )
    controls_html = (
        "<div class='detail-controls'>"
        + "<label>coluna "
        + f"<select class='ctrl-filter-col'>{option_html}</select></label>"
        + "<label>filtro "
        + "<select class='ctrl-filter-mode'><option value='contains'>contem</option>"
        + "<option value='not_contains'>nao_contem</option></select></label>"
        + "<label>texto <input type='text' class='ctrl-filter-text' placeholder='valor'></label>"
        + "<label>ordenar por "
        + "<select class='ctrl-sort-col'><option value=''>sem_ordenacao</option>"
        + option_html
        + "</select></label>"
        + "<label>ordem "
        + "<select class='ctrl-sort-order'><option value='asc'>crescente</option>"
        + "<option value='desc'>decrescente</option></select></label>"
        + "<button type='button' class='ctrl-reset'>limpar</button>"
        + "</div>"
    )
    return (
        controls_html
        + f"<table class='detail' id='{table_id}'>"
        "<thead><tr>"
        + key_header_cells
        + "<th>tipo</th><th>linha</th>"
        + header_cells
        + "</tr><tr class='filter-row'>"
        + key_filter_cells
        + "<th><input class='col-filter-input' data-col='tipo' type='text' placeholder='filtro'></th>"
        + "<th><input class='col-filter-input' data-col='linha' type='text' placeholder='filtro'></th>"
        + filter_cells
        + "</tr></thead><tbody>"
        + "\n".join(body_rows)
        + "</tbody></table>"
    )


def render_report_html(payload: dict) -> str:
    s = payload["summary"]
    a = payload["source_a"]
    b = payload["source_b"]
    rows = payload["rows"]
    details = payload.get("table_details") or []
    line_a_label, line_b_label = _source_line_labels(payload)
    report_title = _report_title(payload)
    used_engines = _used_engine_lines(payload)
    used_engines_html = "".join([f"<li>{html.escape(item)}</li>" for item in used_engines])
    details_blocks = []
    for idx, detail in enumerate(details):
        details_blocks.append(
            "<div class='card'>"
            f"<h2>Tabela: {html.escape(str(detail.get('table') or ''))}</h2>"
            f"<div class='meta'>colunas compactas: {html.escape(', '.join(detail.get('visible_columns') or []))}</div>"
            f"<div class='meta'>linhas diff retornadas: {detail.get('rows_returned', 0)} "
            f"(total detectado: {detail.get('rows_total', 0)})</div>"
            + _html_table_detail(detail, line_a_label, line_b_label, idx)
            + "</div>"
        )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>DB Compare Report</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, Arial, sans-serif; margin: 24px; color: #1f2937; background: #ffffff; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    .card {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    h1 {{ margin: 0 0 10px; font-size: 24px; font-weight: 500; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; font-weight: 500; }}
    .meta {{ color: #4b5563; font-size: 13px; }}
    .meta a {{ color: #1d4ed8; text-decoration: none; }}
    .meta a:hover {{ text-decoration: underline; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 12px; }}
    .kpi {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{ background: #eef2ff; border: 1px solid #c7d2fe; color: #1e3a8a; border-radius: 999px; padding: 6px 10px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
    th, td {{ border: 1px solid #dbe3ef; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eff6ff; position: sticky; top: 0; }}
    table.detail th {{ position: static; }}
    .value-added {{ color: #0b7a0b; font-weight: 400; }}
    .value-removed {{ color: #c00000; font-weight: 400; }}
    .value-changed {{ color: #7a1f1f; font-weight: 400; }}
    code {{ background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }}
    .filter-row th {{ background: #ffffff; }}
    .col-filter-input {{ width: 95%; min-width: 90px; font-size: 12px; padding: 3px 4px; border: 1px solid #cbd5e1; border-radius: 6px; }}
    .detail-controls {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 6px; align-items: center; }}
    .detail-controls label {{ font-size: 12px; color: #334155; display: flex; gap: 4px; align-items: center; }}
    .detail-controls select, .detail-controls input {{ font-size: 12px; padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 6px; }}
    .detail-controls button {{ font-size: 12px; padding: 4px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; cursor: pointer; }}
    details.meta-detail {{ margin-top: 6px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>{html.escape(report_title)}</h1>
      <div class="meta">Gerado em: {html.escape(payload["generated_at"])}</div>
    </div>
    <div class="card">
      <h2>Fontes</h2>
      <div class="grid">
        <div>
          A: {html.escape(a["file"])} ({html.escape(a["engine"])})<br/>
          <span class="meta">source: {_html_link_for_path(a["path"])}</span><br/>
          <span class="meta">size: {html.escape(_format_size_mb(int(a["size_bytes"])))} | mtime: {html.escape(_format_mtime_short(a["mtime"]))}</span><br/>
          <span class="meta">duckdb: {_html_link_for_path(a["duckdb"])}</span><br/>
          <span class="meta">sqlite: {_html_link_for_path(a["sqlite"])}</span><br/>
          <details class="meta meta-detail"><summary>pipeline tecnico</summary>{html.escape(" | ".join(a["steps"]))}</details>
        </div>
        <div>
          B: {html.escape(b["file"])} ({html.escape(b["engine"])})<br/>
          <span class="meta">source: {_html_link_for_path(b["path"])}</span><br/>
          <span class="meta">size: {html.escape(_format_size_mb(int(b["size_bytes"])))} | mtime: {html.escape(_format_mtime_short(b["mtime"]))}</span><br/>
          <span class="meta">duckdb: {_html_link_for_path(b["duckdb"])}</span><br/>
          <span class="meta">sqlite: {_html_link_for_path(b["sqlite"])}</span><br/>
          <details class="meta meta-detail"><summary>pipeline tecnico</summary>{html.escape(" | ".join(b["steps"]))}</details>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>Bancos utilizados no fluxo</h2>
      <ul>
        {used_engines_html}
      </ul>
    </div>
    <div class="card">
      <h2>Resumo</h2>
      <div class="kpi">
        <span class="pill">Tabelas comuns: {s["total_tables"]}</span>
        <span class="pill">Iguais: {s["same_tables"]}</span>
        <span class="pill">Com diferenca: {s["diff_tables"]}</span>
        <span class="pill">Sem colunas comuns: {s["no_key_tables"]}</span>
        <span class="pill">Erros: {s["error_tables"]}</span>
      </div>
    </div>
    <div class="card">
      <h2>Tabelas com alteracao (sem tabelas iguais)</h2>
      <table>
        <thead>
          <tr>
            <th>Tabela</th>
            <th>Status</th>
            <th>Rows A</th>
            <th>Rows B</th>
            <th>Diff count</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {_html_rows(rows)}
        </tbody>
      </table>
    </div>
    {"".join(details_blocks)}
  </div>
  <script>
  (function() {{
    function getPairRows(table) {{
      const rows = Array.from(table.querySelectorAll('tbody tr[data-pair]'));
      const pairMap = new Map();
      rows.forEach((tr) => {{
        const id = tr.getAttribute('data-pair') || '';
        if (!pairMap.has(id)) pairMap.set(id, []);
        pairMap.get(id).push(tr);
      }});
      return Array.from(pairMap.entries())
        .sort((a, b) => Number(a[0]) - Number(b[0]))
        .map((it) => it[1]);
    }}

    function cellValues(pairRows, col) {{
      const vals = [];
      pairRows.forEach((row) => {{
        const cells = Array.from(row.querySelectorAll(`td[data-col="${{col}}"]`));
        cells.forEach((cell) => {{
          const text = (cell.textContent || '').trim();
          if (text) vals.push(text);
        }});
      }});
      return vals;
    }}

    function pairValue(pairRows, col) {{
      const vals = cellValues(pairRows, col);
      if (!vals.length) return '';
      return vals[vals.length - 1];
    }}

    function textHas(pairRows, col, term) {{
      if (!term) return true;
      const lowered = term.toLowerCase();
      const vals = cellValues(pairRows, col);
      if (!vals.length) return false;
      return vals.some((v) => v.toLowerCase().includes(lowered));
    }}

    function parseNum(text) {{
      const clean = String(text || '').trim().replace(',', '.');
      if (!clean) return NaN;
      return Number(clean);
    }}

    function comparePairValues(aRows, bRows, col, order) {{
      const a = pairValue(aRows, col);
      const b = pairValue(bRows, col);
      const aNum = parseNum(a);
      const bNum = parseNum(b);
      let cmp = 0;
      if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) {{
        cmp = aNum - bNum;
      }} else {{
        cmp = String(a).localeCompare(String(b), undefined, {{ numeric: true, sensitivity: 'base' }});
      }}
      return order === 'desc' ? -cmp : cmp;
    }}

    function applyFilters(table) {{
      const inputs = Array.from(table.querySelectorAll('.col-filter-input'));
      const active = inputs
        .map((inp) => [inp.getAttribute('data-col') || '', (inp.value || '').trim().toLowerCase()])
        .filter((it) => it[0] && it[1]);
      const ctrlCol = table.parentElement.querySelector('.ctrl-filter-col');
      const ctrlMode = table.parentElement.querySelector('.ctrl-filter-mode');
      const ctrlText = table.parentElement.querySelector('.ctrl-filter-text');
      const sortCol = table.parentElement.querySelector('.ctrl-sort-col');
      const sortOrder = table.parentElement.querySelector('.ctrl-sort-order');
      const quickCol = ctrlCol ? (ctrlCol.value || '') : '';
      const quickMode = ctrlMode ? (ctrlMode.value || 'contains') : 'contains';
      const quickText = ctrlText ? (ctrlText.value || '').trim().toLowerCase() : '';
      const orderCol = sortCol ? (sortCol.value || '') : '';
      const orderMode = sortOrder ? (sortOrder.value || 'asc') : 'asc';

      let pairs = getPairRows(table);
      pairs = pairs.filter((pairRows) => {{
        let ok = true;
        for (const item of active) {{
          if (!textHas(pairRows, item[0], item[1])) {{
            ok = false;
            break;
          }}
        }}
        if (!ok) return false;
        if (!quickText || !quickCol) return true;
        const has = textHas(pairRows, quickCol, quickText);
        return quickMode === 'not_contains' ? !has : has;
      }});

      if (orderCol) {{
        pairs.sort((aRows, bRows) => comparePairValues(aRows, bRows, orderCol, orderMode));
      }}

      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      while (tbody.firstChild) {{
        tbody.removeChild(tbody.firstChild);
      }}
      pairs.forEach((pairRows) => {{
        pairRows.forEach((row) => {{
          row.style.display = '';
          tbody.appendChild(row);
        }});
      }});
    }}

    const tables = Array.from(document.querySelectorAll('table.detail'));
    tables.forEach((table) => {{
      const inputs = Array.from(table.querySelectorAll('.col-filter-input'));
      inputs.forEach((input) => {{
        input.addEventListener('input', function() {{
          applyFilters(table);
        }});
      }});
      const controls = [
        table.parentElement.querySelector('.ctrl-filter-col'),
        table.parentElement.querySelector('.ctrl-filter-mode'),
        table.parentElement.querySelector('.ctrl-filter-text'),
        table.parentElement.querySelector('.ctrl-sort-col'),
        table.parentElement.querySelector('.ctrl-sort-order'),
      ].filter(Boolean);
      controls.forEach((el) => {{
        const evt = el.tagName === 'INPUT' ? 'input' : 'change';
        el.addEventListener(evt, function() {{
          applyFilters(table);
        }});
      }});
      const resetBtn = table.parentElement.querySelector('.ctrl-reset');
      if (resetBtn) {{
        resetBtn.addEventListener('click', function() {{
          inputs.forEach((input) => {{
            input.value = '';
          }});
          const filterCol = table.parentElement.querySelector('.ctrl-filter-col');
          const filterMode = table.parentElement.querySelector('.ctrl-filter-mode');
          const filterText = table.parentElement.querySelector('.ctrl-filter-text');
          const sortCol = table.parentElement.querySelector('.ctrl-sort-col');
          const sortOrder = table.parentElement.querySelector('.ctrl-sort-order');
          if (filterCol) filterCol.selectedIndex = 0;
          if (filterMode) filterMode.value = 'contains';
          if (filterText) filterText.value = '';
          if (sortCol) sortCol.value = '';
          if (sortOrder) sortOrder.value = 'asc';
          applyFilters(table);
        }});
      }}
    }});
  }})();
  </script>
</body>
</html>
"""


def render_report_md(payload: dict) -> str:
    s = payload["summary"]
    details = payload.get("table_details") or []
    line_a_label, line_b_label = _source_line_labels(payload)
    report_title = _report_title(payload)
    used_engines = _used_engine_lines(payload)
    src_a_uri = _file_uri(payload["source_a"]["path"])
    src_b_uri = _file_uri(payload["source_b"]["path"])
    duck_a_uri = _file_uri(payload["source_a"]["duckdb"])
    duck_b_uri = _file_uri(payload["source_b"]["duckdb"])
    sqlite_a_uri = _file_uri(payload["source_a"]["sqlite"])
    sqlite_b_uri = _file_uri(payload["source_b"]["sqlite"])
    fonte_a_path = (
        f"[{payload['source_a']['path']}]({src_a_uri})"
        if src_a_uri
        else payload["source_a"]["path"]
    )
    fonte_b_path = (
        f"[{payload['source_b']['path']}]({src_b_uri})"
        if src_b_uri
        else payload["source_b"]["path"]
    )
    duck_a_path = (
        f"[{payload['source_a']['duckdb']}]({duck_a_uri})"
        if duck_a_uri
        else payload["source_a"]["duckdb"]
    )
    duck_b_path = (
        f"[{payload['source_b']['duckdb']}]({duck_b_uri})"
        if duck_b_uri
        else payload["source_b"]["duckdb"]
    )
    sqlite_a_path = (
        f"[{payload['source_a']['sqlite']}]({sqlite_a_uri})"
        if sqlite_a_uri
        else payload["source_a"]["sqlite"]
    )
    sqlite_b_path = (
        f"[{payload['source_b']['sqlite']}]({sqlite_b_uri})"
        if sqlite_b_uri
        else payload["source_b"]["sqlite"]
    )
    lines = [
        f"# {report_title}",
        "",
        f"- gerado_em: {payload['generated_at']}",
        f"- fonte_a: {fonte_a_path} ({payload['source_a']['engine']})",
        f"- fonte_a_size: {_format_size_mb(int(payload['source_a']['size_bytes']))}",
        f"- fonte_a_mtime: {_format_mtime_short(payload['source_a']['mtime'])}",
        f"- fonte_b: {fonte_b_path} ({payload['source_b']['engine']})",
        f"- fonte_b_size: {_format_size_mb(int(payload['source_b']['size_bytes']))}",
        f"- fonte_b_mtime: {_format_mtime_short(payload['source_b']['mtime'])}",
        f"- duckdb_a: {duck_a_path}",
        f"- duckdb_b: {duck_b_path}",
        f"- sqlite_a: {sqlite_a_path}",
        f"- sqlite_b: {sqlite_b_path}",
        "",
        "## Bancos utilizados no fluxo",
        "",
    ]
    lines.extend([f"- {item}" for item in used_engines])
    lines.extend(
        [
            "",
        "## Resumo",
        "",
        f"- tabelas_comuns: {s['total_tables']}",
        f"- same_tables: {s['same_tables']}",
        f"- diff_tables: {s['diff_tables']}",
        f"- no_key_tables: {s['no_key_tables']}",
        f"- error_tables: {s['error_tables']}",
        "",
        "## Tabelas com alteracao (sem tabelas iguais)",
        "",
        "| tabela | status | rows_a | rows_b | diff_count | error |",
        "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload["rows"]:
        status_label = _status_label(str(row.get("status") or ""))
        lines.append(
            f"| {row.get('table','')} | {status_label} | {row.get('row_count_a','')} | "
            f"{row.get('row_count_b','')} | {row.get('diff_count','')} | {row.get('error','')} |"
        )
    lines.append("")
    lines.append("## Detalhe compacto por tabela")
    for detail in details:
        key_cols = detail.get("key_columns") or []
        if not key_cols:
            key_cols = ["KEY"]
        lines.append("")
        lines.append(f"### {detail.get('table', '')}")
        lines.append(f"- colunas_visiveis: {', '.join(detail.get('visible_columns') or [])}")
        lines.append(
            f"- linhas_diff: {detail.get('rows_returned', 0)} de {detail.get('rows_total', 0)}"
        )
        lines.append("")
        lines.append(
            "| "
            + " | ".join(key_cols)
            + " | tipo | linha | "
            + " | ".join(detail.get("visible_columns") or [])
            + " |"
        )
        lines.append(
            "|"
            + "|".join(["---"] * (len(key_cols) + 2 + len(detail.get("visible_columns") or [])))
            + "|"
        )
        for item in detail.get("records") or []:
            cols = detail.get("visible_columns") or []
            key_values = item.get("key_values") or {}
            key_out = [str(key_values.get(col, "")) for col in key_cols]
            old_vals = [str((item.get("old") or {}).get(c, "")) for c in cols]
            new_vals = [str((item.get("new") or {}).get(c, "")) for c in cols]
            row_type = _type_label(str(item.get("type") or ""))
            lines.append(
                "| "
                + " | ".join(key_out)
                + f" | {row_type} | {line_a_label} | "
                + " | ".join(old_vals)
                + " |"
            )
            lines.append(
                "| "
                + " | ".join(key_out)
                + f" | {row_type} | {line_b_label} | "
                + " | ".join(new_vals)
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_report_txt(payload: dict) -> str:
    s = payload["summary"]
    details = payload.get("table_details") or []
    line_a_label, line_b_label = _source_line_labels(payload)
    report_title = _report_title(payload)
    used_engines = _used_engine_lines(payload)
    out = [
        report_title,
        f"Gerado em: {payload['generated_at']}",
        "",
        f"A: {payload['source_a']['path']} ({payload['source_a']['engine']})",
        f"   size: {_format_size_mb(int(payload['source_a']['size_bytes']))} | mtime: {_format_mtime_short(payload['source_a']['mtime'])}",
        f"   duckdb: {payload['source_a']['duckdb']}",
        f"   sqlite: {payload['source_a']['sqlite']}",
        f"B: {payload['source_b']['path']} ({payload['source_b']['engine']})",
        f"   size: {_format_size_mb(int(payload['source_b']['size_bytes']))} | mtime: {_format_mtime_short(payload['source_b']['mtime'])}",
        f"   duckdb: {payload['source_b']['duckdb']}",
        f"   sqlite: {payload['source_b']['sqlite']}",
        "",
        "BANCOS UTILIZADOS NO FLUXO",
    ]
    out.extend([f"  - {item}" for item in used_engines])
    out.extend(
        [
            "",
        "RESUMO",
        f"  tabelas_comuns: {s['total_tables']}",
        f"  same_tables: {s['same_tables']}",
        f"  diff_tables: {s['diff_tables']}",
        f"  no_key_tables: {s['no_key_tables']}",
        f"  error_tables: {s['error_tables']}",
        "",
        "TABELAS COM ALTERACAO",
        ]
    )
    for row in payload["rows"]:
        status_label = _status_label(str(row.get("status") or ""))
        out.append(
            "  - "
            + f"{row.get('table','')} | status={status_label} "
            + f"| rows_a={row.get('row_count_a','')} rows_b={row.get('row_count_b','')} "
            + f"| diff={row.get('diff_count','')} "
            + (f"| error={row.get('error','')}" if row.get("error") else "")
        )
    out.append("")
    out.append("DETALHE COMPACTO POR TABELA")
    for detail in details:
        key_cols = detail.get("key_columns") or []
        if not key_cols:
            key_cols = ["KEY"]
        out.append("")
        out.append(f"TABELA {detail.get('table','')}")
        out.append("  key_columns: " + ", ".join(key_cols))
        out.append(
            "  colunas_visiveis: " + ", ".join(detail.get("visible_columns") or [])
        )
        out.append(
            f"  linhas_diff: {detail.get('rows_returned', 0)} de {detail.get('rows_total', 0)}"
        )
        for item in detail.get("records") or []:
            row_type = _type_label(str(item.get("type") or ""))
            key_values = item.get("key_values") or {}
            key_out = " | ".join([f"{col}={key_values.get(col, '')}" for col in key_cols])
            out.append(f"  key={key_out} tipo={row_type}")
            cols = detail.get("visible_columns") or []
            old_pairs = [f"{c}={str((item.get('old') or {}).get(c, ''))}" for c in cols]
            new_pairs = [f"{c}={str((item.get('new') or {}).get(c, ''))}" for c in cols]
            out.append(f"    {line_a_label}: " + " | ".join(old_pairs))
            out.append(f"    {line_b_label}: " + " | ".join(new_pairs))
    return "\n".join(out) + "\n"


def write_report_files(payload: dict, reports_dir: Path) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = payload["generated_stamp"]
    a_name = re.sub(r"[^A-Za-z0-9._-]+", "_", payload["source_a"]["file"])
    b_name = re.sub(r"[^A-Za-z0-9._-]+", "_", payload["source_b"]["file"])
    base = reports_dir / f"db_compare_{stamp}_{a_name}_vs_{b_name}"

    html_path = base.with_suffix(".html")
    md_path = base.with_suffix(".md")
    txt_path = base.with_suffix(".txt")

    html_path.write_text(render_report_html(payload), encoding="utf-8")
    md_path.write_text(render_report_md(payload), encoding="utf-8")
    txt_path.write_text(render_report_txt(payload), encoding="utf-8")
    latest_html = reports_dir / "latest_db_compare_report.html"
    latest_md = reports_dir / "latest_db_compare_report.md"
    latest_txt = reports_dir / "latest_db_compare_report.txt"
    latest_html.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_txt.write_text(txt_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {"html": html_path, "md": md_path, "txt": txt_path}


def pick_two_sources_interactive(items: Sequence[FileItem]) -> tuple[FileItem, FileItem] | None:
    a, b = suggest_two_sources(items)
    while True:
        print("")
        print("Sugestao inicial (2 ultimos Access):")
        print(f"  A: {_item_line(a)}")
        print(f"  B: {_item_line(b)}")
        print("Comandos: Enter=manter | m=alterar | q=sair")
        cmd = input("> ").strip().lower()
        if cmd == "":
            return a, b
        if cmd in {"q", "quit", "sair"}:
            return None
        if cmd not in {"m", "mudar", "alterar"}:
            print("Comando invalido.")
            continue
        while True:
            print("")
            print("Selecao atual:")
            print(f"  A: {_item_line(a)}")
            print(f"  B: {_item_line(b)}")
            print("Comandos: 1=alterar A | 2=alterar B | c=confirmar | q=sair")
            sub = input("> ").strip().lower()
            if sub == "1":
                picked = pick_file_interactive(items, "Escolha arquivo A:")
                if picked is not None:
                    a = picked
            elif sub == "2":
                picked = pick_file_interactive(items, "Escolha arquivo B:")
                if picked is not None:
                    b = picked
            elif sub in {"c", "confirmar"}:
                if a.path == b.path:
                    print("A e B nao podem ser o mesmo arquivo.")
                    continue
                return a, b
            elif sub in {"q", "quit", "sair"}:
                return None
            else:
                print("Comando invalido.")


def run_compare_pipeline(source_a: Path, source_b: Path, docs_dir: Path, reports_dir: Path) -> dict[str, Path]:
    prepared_a = prepare_source(source_a, docs_dir)
    prepared_b = prepare_source(source_b, docs_dir)
    common_tables = list_common_tables(prepared_a.duckdb_path, prepared_b.duckdb_path)
    overview = compare_tables_overview_duckdb(
        prepared_a.duckdb_path,
        prepared_b.duckdb_path,
        tables=common_tables,
    )
    details = collect_table_details(prepared_a.duckdb_path, prepared_b.duckdb_path, overview)
    payload = build_report_payload(prepared_a, prepared_b, overview, details)
    return write_report_files(payload, reports_dir)


def _resolve_default_dirs(project_root: Path) -> tuple[Path, Path]:
    docs_dir = (project_root / "documentos").resolve()
    reports_dir = (docs_dir / "reports").resolve()
    return docs_dir, reports_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "POC interativa para comparar dois bancos e gerar report html/md/txt "
            "com conversao automatica quando necessario."
        )
    )
    parser.add_argument("--docs-dir", default="", help="Pasta de documentos")
    parser.add_argument("--reports-dir", default="", help="Pasta de relatorios")
    parser.add_argument("--db1", default="", help="Arquivo A (opcional, caminho completo)")
    parser.add_argument("--db2", default="", help="Arquivo B (opcional, caminho completo)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    default_docs, default_reports = _resolve_default_dirs(project_root)
    docs_dir = Path(args.docs_dir).expanduser().resolve() if args.docs_dir else default_docs
    reports_dir = (
        Path(args.reports_dir).expanduser().resolve() if args.reports_dir else default_reports
    )
    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"diretorio de documentos invalido: {docs_dir}")
        return 2

    try:
        if args.db1 and args.db2:
            src_a = Path(args.db1).expanduser().resolve()
            src_b = Path(args.db2).expanduser().resolve()
            if src_a == src_b:
                print("db1 e db2 nao podem ser iguais")
                return 2
        else:
            items = list_candidate_files(docs_dir)
            picked = pick_two_sources_interactive(items)
            if picked is None:
                print("Operacao cancelada.")
                return 0
            src_a, src_b = picked[0].path, picked[1].path
        outputs = run_compare_pipeline(src_a, src_b, docs_dir, reports_dir)
    except Exception as exc:
        print(f"Erro: {exc}")
        return 1

    print("")
    print("Report gerado com sucesso:")
    print(f"  HTML: {outputs['html']}")
    print(f"  MD  : {outputs['md']}")
    print(f"  TXT : {outputs['txt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
