#!/usr/bin/env python3
"""Prepare validation artifacts from local DB files.

Generates canonical DuckDB and SQLite files under artifacts/validation/derived.
Input sources are read from output/ by default.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import duckdb

from access_convert import convert_access_to_duckdb

ACCESS_EXTS = {".mdb", ".accdb"}
DUCK_EXTS = {".duckdb"}
SQLITE_EXTS = {".sqlite", ".sqlite3", ".db"}


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _sanitize_stem(path: Path) -> str:
    text = path.stem.strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    cleaned = "".join(out).strip("_")
    return cleaned or "db"


def _build_source_id(src: Path, input_dir: Path) -> str:
    rel = src.relative_to(input_dir)
    rel_key = "_".join(rel.parts[:-1]) if len(rel.parts) > 1 else ""
    base = _sanitize_stem(src)
    suffix = src.suffix.lower().lstrip(".")
    if rel_key:
        return f"{_sanitize_stem(Path(rel_key))}_{base}_{suffix}"
    return f"{base}_{suffix}"


def _list_duckdb_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.execute("SHOW TABLES").fetchall()
    tables = []
    for row in rows:
        if not row:
            continue
        name = str(row[0])
        low = name.lower()
        if low.startswith("sqlite_") or low.startswith("duckdb_"):
            continue
        tables.append(name)
    return tables


def _list_sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [str(row[0]) for row in cur.fetchall() if row and row[0]]


def _map_sqlite_type(type_name: str) -> str:
    t = (type_name or "").upper()
    if "INT" in t:
        return "INTEGER"
    if "DOUBLE" in t or "FLOAT" in t or "REAL" in t or "DECIMAL" in t or "NUMERIC" in t:
        return "REAL"
    if "BOOL" in t:
        return "INTEGER"
    if "BLOB" in t or "BYTEA" in t:
        return "BLOB"
    return "TEXT"


def _map_duck_type(type_name: str) -> str:
    t = (type_name or "").upper()
    if "INT" in t:
        return "BIGINT"
    if "DOUBLE" in t or "FLOAT" in t or "REAL" in t or "DECIMAL" in t or "NUMERIC" in t:
        return "DOUBLE"
    if "BOOL" in t:
        return "BOOLEAN"
    if "BLOB" in t or "BYTEA" in t:
        return "BLOB"
    return "VARCHAR"


def _sqlite_to_duckdb(sqlite_path: Path, duckdb_path: Path) -> tuple[bool, str]:
    if duckdb_path.exists():
        duckdb_path.unlink()

    src = sqlite3.connect(str(sqlite_path))
    dst = duckdb.connect(str(duckdb_path))
    try:
        tables = _list_sqlite_tables(src)
        if not tables:
            return False, "sqlite sem tabelas de usuario"

        for table in tables:
            info_rows = src.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
            cols = [str(row[1]) for row in info_rows]
            types = [_map_duck_type(str(row[2] or "")) for row in info_rows]
            if not cols:
                continue

            create_cols = ", ".join(
                f"{_quote_ident(col)} {col_type}" for col, col_type in zip(cols, types)
            )
            dst.execute(f"DROP TABLE IF EXISTS {_quote_ident(table)}")
            dst.execute(f"CREATE TABLE {_quote_ident(table)} ({create_cols})")

            placeholders = ", ".join(["?"] * len(cols))
            ins_sql = (
                f"INSERT INTO {_quote_ident(table)} ("
                + ", ".join(_quote_ident(c) for c in cols)
                + f") VALUES ({placeholders})"
            )
            cur = src.execute(f"SELECT * FROM {_quote_ident(table)}")
            while True:
                chunk = cur.fetchmany(2000)
                if not chunk:
                    break
                dst.executemany(ins_sql, chunk)
        return True, "sqlite->duckdb ok"
    except Exception as exc:  # pragma: no cover
        return False, f"sqlite->duckdb falhou: {exc}"
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def _duckdb_to_sqlite(duckdb_path: Path, sqlite_path: Path) -> tuple[bool, str]:
    if sqlite_path.exists():
        sqlite_path.unlink()

    src = duckdb.connect(str(duckdb_path), read_only=True)
    dst = sqlite3.connect(str(sqlite_path))
    try:
        tables = _list_duckdb_tables(src)
        if not tables:
            return False, "duckdb sem tabelas de usuario"

        for table in tables:
            info_rows = src.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
            cols = [str(row[1]) for row in info_rows]
            types = [_map_sqlite_type(str(row[2] or "")) for row in info_rows]
            if not cols:
                continue

            create_cols = ", ".join(
                f"{_quote_ident(col)} {col_type}" for col, col_type in zip(cols, types)
            )
            dst.execute(f"DROP TABLE IF EXISTS {_quote_ident(table)}")
            dst.execute(f"CREATE TABLE {_quote_ident(table)} ({create_cols})")

            col_list = ", ".join(_quote_ident(c) for c in cols)
            sel_sql = f"SELECT {col_list} FROM {_quote_ident(table)}"
            ins_sql = (
                f"INSERT INTO {_quote_ident(table)} ({col_list}) VALUES ("
                + ", ".join(["?"] * len(cols))
                + ")"
            )
            cur = src.execute(sel_sql)
            while True:
                chunk = cur.fetchmany(2000)
                if not chunk:
                    break
                dst.executemany(ins_sql, chunk)
        dst.commit()
        return True, "duckdb->sqlite ok"
    except Exception as exc:  # pragma: no cover
        return False, f"duckdb->sqlite falhou: {exc}"
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def _table_count(path: Path, engine: str) -> int:
    try:
        if engine == "duckdb":
            conn = duckdb.connect(str(path), read_only=True)
            try:
                return len(_list_duckdb_tables(conn))
            finally:
                conn.close()
        if engine == "sqlite":
            conn = sqlite3.connect(str(path))
            try:
                return len(_list_sqlite_tables(conn))
            finally:
                conn.close()
    except Exception:
        return -1
    return -1


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare validation DB artifacts from local input files.")
    parser.add_argument("--input-dir", default="output", help="Source folder with .accdb/.mdb/.duckdb/.sqlite files")
    parser.add_argument(
        "--out-root",
        default="artifacts/validation",
        help="Output root for canonical artifacts and reports",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    input_dir = (repo_root / args.input_dir).resolve()
    out_root = (repo_root / args.out_root).resolve()
    in_copy_dir = out_root / "input"
    duck_dir = out_root / "derived" / "duckdb"
    sqlite_dir = out_root / "derived" / "sqlite"
    reports_dir = out_root / "reports"

    for d in (in_copy_dir, duck_dir, sqlite_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    sources = sorted(
        [
            p
            for p in input_dir.rglob("*")
            if p.is_file()
            and not p.name.startswith(".")
            and p.suffix.lower() in (ACCESS_EXTS | DUCK_EXTS | SQLITE_EXTS)
        ]
    )

    manifest: dict[str, Any] = {
        "generated_at_epoch": time.time(),
        "input_dir": str(input_dir),
        "out_root": str(out_root),
        "items": [],
    }

    for src in sources:
        suffix = src.suffix.lower()
        id_name = _build_source_id(src, input_dir)
        canonical_input = in_copy_dir / src.name
        duck_path = duck_dir / f"{id_name}.duckdb"
        sqlite_path = sqlite_dir / f"{id_name}.sqlite3"

        item: dict[str, Any] = {
            "id": id_name,
            "source": str(src),
            "source_suffix": suffix,
            "canonical_input": str(canonical_input),
            "duckdb_path": str(duck_path),
            "sqlite_path": str(sqlite_path),
            "duckdb_ok": False,
            "sqlite_ok": False,
            "duckdb_msg": "",
            "sqlite_msg": "",
            "duckdb_tables": -1,
            "sqlite_tables": -1,
        }

        try:
            shutil.copy2(src, canonical_input)
        except Exception as exc:
            item["copy_error"] = str(exc)

        if suffix in ACCESS_EXTS:
            ok, msg = convert_access_to_duckdb(str(src), str(duck_path), prefer_odbc=True)
            item["duckdb_ok"] = bool(ok)
            item["duckdb_msg"] = str(msg)
        elif suffix in DUCK_EXTS:
            try:
                shutil.copy2(src, duck_path)
                item["duckdb_ok"] = True
                item["duckdb_msg"] = "duckdb copiado"
            except Exception as exc:
                item["duckdb_msg"] = f"copia duckdb falhou: {exc}"
        elif suffix in SQLITE_EXTS:
            ok, msg = _sqlite_to_duckdb(src, duck_path)
            item["duckdb_ok"] = bool(ok)
            item["duckdb_msg"] = str(msg)

        if item["duckdb_ok"] and duck_path.exists():
            ok, msg = _duckdb_to_sqlite(duck_path, sqlite_path)
            item["sqlite_ok"] = bool(ok)
            item["sqlite_msg"] = str(msg)
        elif suffix in SQLITE_EXTS:
            try:
                shutil.copy2(src, sqlite_path)
                item["sqlite_ok"] = True
                item["sqlite_msg"] = "sqlite copiado"
            except Exception as exc:
                item["sqlite_msg"] = f"copia sqlite falhou: {exc}"

        if item["duckdb_ok"] and duck_path.exists():
            item["duckdb_tables"] = _table_count(duck_path, "duckdb")
        if item["sqlite_ok"] and sqlite_path.exists():
            item["sqlite_tables"] = _table_count(sqlite_path, "sqlite")

        manifest["items"].append(item)

    manifest_path = reports_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Manifesto gerado: {manifest_path}")
    print(f"Total de fontes: {len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
