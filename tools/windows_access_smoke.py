#!/usr/bin/env python3
"""Windows smoke test for Access (.accdb/.mdb) -> DuckDB conversion."""

from __future__ import annotations

import argparse
import json
import os
import platform
import tempfile
from pathlib import Path

import duckdb

from access_convert import convert_access_to_duckdb


def list_tables(db_path: Path) -> list[str]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        out = []
        for row in rows:
            if not row:
                continue
            name = str(row[0])
            low = name.lower()
            if low.startswith("msys") or low.startswith("sqlite_") or low.startswith("duckdb_"):
                continue
            out.append(name)
        return out
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Access->DuckDB smoke conversion on Windows.")
    parser.add_argument("--input", required=True, help="Path to .accdb/.mdb sample file")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output .duckdb path. If empty, a temporary file is used.",
    )
    args = parser.parse_args()

    result = {
        "platform": platform.platform(),
        "ok": False,
        "input": args.input,
        "output": "",
        "details": "",
        "drivers": [],
        "table_count": 0,
    }

    if os.name != "nt":
        result["details"] = "windows_only"
        print(json.dumps(result, ensure_ascii=True))
        return 2

    try:
        import pyodbc  # type: ignore
    except Exception as exc:  # pragma: no cover
        result["details"] = f"pyodbc_missing: {exc}"
        print(json.dumps(result, ensure_ascii=True))
        return 3

    drivers = [str(d) for d in pyodbc.drivers()]
    result["drivers"] = drivers
    access_driver = any("Access Driver" in d for d in drivers)
    if not access_driver:
        result["details"] = "access_odbc_driver_missing"
        print(json.dumps(result, ensure_ascii=True))
        return 4

    src = Path(args.input).resolve()
    if not src.exists():
        result["details"] = "input_not_found"
        print(json.dumps(result, ensure_ascii=True))
        return 5

    if args.output:
        out = Path(args.output).resolve()
    else:
        fd, tmp_name = tempfile.mkstemp(prefix="accdb_smoke_", suffix=".duckdb")
        os.close(fd)
        out = Path(tmp_name)
    if out == src:
        result["details"] = "output_equals_input_not_allowed"
        result["output"] = str(out)
        print(json.dumps(result, ensure_ascii=True))
        return 8
    if out.exists():
        out.unlink()
    result["output"] = str(out)

    ok, msg = convert_access_to_duckdb(str(src), str(out), prefer_odbc=True)
    result["details"] = str(msg)
    if not ok or not out.exists():
        print(json.dumps(result, ensure_ascii=True))
        return 6

    tables = list_tables(out)
    result["table_count"] = len(tables)
    if not tables:
        result["details"] = "converted_without_user_tables"
        print(json.dumps(result, ensure_ascii=True))
        return 7

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
