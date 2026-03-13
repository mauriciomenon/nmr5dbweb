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
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import duckdb

from access_convert import convert_access_to_duckdb
from interface.compare_dbs import compare_tables_overview_duckdb, list_common_tables

SUPPORTED_INPUT_EXTS = {".accdb", ".mdb", ".duckdb", ".sqlite", ".sqlite3", ".db"}
ACCESS_EXTS = {".accdb", ".mdb"}
SQLITE_EXTS = {".sqlite", ".sqlite3"}
DUCKDB_EXTS = {".duckdb"}
DEFAULT_PAGE_SIZE = 10
ISO_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


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


def build_report_payload(a: PreparedSource, b: PreparedSource, overview_rows: Sequence[dict]) -> dict:
    now = dt.datetime.now()
    summary = summarize_overview(overview_rows)
    sorted_rows = sorted(
        overview_rows,
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
        "rows": list(sorted_rows),
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
            + f"<td>{html.escape(status)}</td>"
            + f"<td>{html.escape(str(row.get('row_count_a', '')))}</td>"
            + f"<td>{html.escape(str(row.get('row_count_b', '')))}</td>"
            + f"<td>{html.escape(str(row.get('diff_count', '')))}</td>"
            + f"<td>{html.escape(str(row.get('error', '')))}</td>"
            + "</tr>"
        )
    return "\n".join(cells)


def render_report_html(payload: dict) -> str:
    s = payload["summary"]
    a = payload["source_a"]
    b = payload["source_b"]
    rows = payload["rows"]
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>DB Compare Report</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, Arial, sans-serif; margin: 24px; color: #1f2937; background: #f8fafc; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    .card {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    h1 {{ margin: 0 0 10px; font-size: 24px; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; }}
    .meta {{ color: #4b5563; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 12px; }}
    .kpi {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{ background: #eef2ff; border: 1px solid #c7d2fe; color: #1e3a8a; border-radius: 999px; padding: 6px 10px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #dbe3ef; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eff6ff; position: sticky; top: 0; }}
    tr.diff td {{ background: #fff7ed; }}
    tr.same td {{ background: #f0fdf4; }}
    tr.warn td {{ background: #fffbeb; }}
    tr.error td {{ background: #fef2f2; }}
    code {{ background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Comparacao automatizada de bancos</h1>
      <div class="meta">Gerado em: {html.escape(payload["generated_at"])}</div>
    </div>
    <div class="card">
      <h2>Fontes</h2>
      <div class="grid">
        <div>
          <strong>A:</strong> {html.escape(a["file"])} ({html.escape(a["engine"])})<br/>
          <span class="meta">{html.escape(a["path"])}</span><br/>
          <span class="meta">size: {html.escape(str(a["size_bytes"]))} bytes | mtime: {html.escape(a["mtime"])}</span><br/>
          <span class="meta">duckdb: {html.escape(a["duckdb"])}</span><br/>
          <span class="meta">sqlite: {html.escape(a["sqlite"])}</span><br/>
          <span class="meta">steps: {html.escape(" | ".join(a["steps"]))}</span>
        </div>
        <div>
          <strong>B:</strong> {html.escape(b["file"])} ({html.escape(b["engine"])})<br/>
          <span class="meta">{html.escape(b["path"])}</span><br/>
          <span class="meta">size: {html.escape(str(b["size_bytes"]))} bytes | mtime: {html.escape(b["mtime"])}</span><br/>
          <span class="meta">duckdb: {html.escape(b["duckdb"])}</span><br/>
          <span class="meta">sqlite: {html.escape(b["sqlite"])}</span><br/>
          <span class="meta">steps: {html.escape(" | ".join(b["steps"]))}</span>
        </div>
      </div>
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
      <h2>Detalhe por tabela</h2>
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
  </div>
</body>
</html>
"""


def render_report_md(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        "# Comparacao automatizada de bancos",
        "",
        f"- gerado_em: {payload['generated_at']}",
        f"- fonte_a: {payload['source_a']['path']} ({payload['source_a']['engine']})",
        f"- fonte_a_size_bytes: {payload['source_a']['size_bytes']}",
        f"- fonte_a_mtime: {payload['source_a']['mtime']}",
        f"- fonte_a_steps: {' | '.join(payload['source_a']['steps'])}",
        f"- fonte_b: {payload['source_b']['path']} ({payload['source_b']['engine']})",
        f"- fonte_b_size_bytes: {payload['source_b']['size_bytes']}",
        f"- fonte_b_mtime: {payload['source_b']['mtime']}",
        f"- fonte_b_steps: {' | '.join(payload['source_b']['steps'])}",
        f"- duckdb_a: {payload['source_a']['duckdb']}",
        f"- duckdb_b: {payload['source_b']['duckdb']}",
        f"- sqlite_a: {payload['source_a']['sqlite']}",
        f"- sqlite_b: {payload['source_b']['sqlite']}",
        "",
        "## Resumo",
        "",
        f"- tabelas_comuns: {s['total_tables']}",
        f"- same_tables: {s['same_tables']}",
        f"- diff_tables: {s['diff_tables']}",
        f"- no_key_tables: {s['no_key_tables']}",
        f"- error_tables: {s['error_tables']}",
        "",
        "## Tabelas",
        "",
        "| tabela | status | rows_a | rows_b | diff_count | error |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row.get('table','')} | {row.get('status','')} | {row.get('row_count_a','')} | "
            f"{row.get('row_count_b','')} | {row.get('diff_count','')} | {row.get('error','')} |"
        )
    return "\n".join(lines) + "\n"


def render_report_txt(payload: dict) -> str:
    s = payload["summary"]
    out = [
        "COMPARACAO AUTOMATIZADA DE BANCOS",
        f"Gerado em: {payload['generated_at']}",
        "",
        f"A: {payload['source_a']['path']} ({payload['source_a']['engine']})",
        f"   size_bytes: {payload['source_a']['size_bytes']} | mtime: {payload['source_a']['mtime']}",
        f"   duckdb: {payload['source_a']['duckdb']}",
        f"   sqlite: {payload['source_a']['sqlite']}",
        f"   steps: {' | '.join(payload['source_a']['steps'])}",
        f"B: {payload['source_b']['path']} ({payload['source_b']['engine']})",
        f"   size_bytes: {payload['source_b']['size_bytes']} | mtime: {payload['source_b']['mtime']}",
        f"   duckdb: {payload['source_b']['duckdb']}",
        f"   sqlite: {payload['source_b']['sqlite']}",
        f"   steps: {' | '.join(payload['source_b']['steps'])}",
        "",
        "RESUMO",
        f"  tabelas_comuns: {s['total_tables']}",
        f"  same_tables: {s['same_tables']}",
        f"  diff_tables: {s['diff_tables']}",
        f"  no_key_tables: {s['no_key_tables']}",
        f"  error_tables: {s['error_tables']}",
        "",
        "DETALHE POR TABELA",
    ]
    for row in payload["rows"]:
        out.append(
            "  - "
            + f"{row.get('table','')} | status={row.get('status','')} "
            + f"| rows_a={row.get('row_count_a','')} rows_b={row.get('row_count_b','')} "
            + f"| diff={row.get('diff_count','')} "
            + (f"| error={row.get('error','')}" if row.get("error") else "")
        )
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
    payload = build_report_payload(prepared_a, prepared_b, overview)
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
