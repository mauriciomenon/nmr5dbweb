#!/usr/bin/env python3
"""Benchmark core flows on validation artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

import duckdb

from interface.app_flask_local_search import (
    fallback_search_sqlite,
    list_tables_duckdb,
    list_tables_sqlite,
    read_table_page_duckdb,
    read_table_page_sqlite,
)
from interface.compare_dbs import compare_table_duckdb_paged, list_common_tables


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _measure(fn, *args, **kwargs) -> tuple[float, Any]:
    start = _now_ms()
    out = fn(*args, **kwargs)
    end = _now_ms()
    return end - start, out


def _pick_table(path: Path, engine: str) -> str | None:
    try:
        if engine == "duckdb":
            names = list_tables_duckdb(path)
        else:
            names = list_tables_sqlite(path)
        if not names:
            return None
        return str(names[0])
    except Exception:
        return None


def _pick_key_columns_duckdb(path: Path, table: str) -> list[str]:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        table_quoted = '"' + str(table).replace('"', '""') + '"'
        rows = conn.execute(f"PRAGMA table_info({table_quoted})").fetchall()
    finally:
        conn.close()
    cols = [str(r[1]) for r in rows if len(r) > 1 and r[1]]
    if not cols:
        return []

    preferred = ("id", "rtuno", "pntno", "itemnb", "inhpro")
    low_map = {c.lower(): c for c in cols}
    chosen = []
    for key in preferred:
        if key in low_map:
            chosen.append(low_map[key])
    if chosen:
        return chosen[:2]
    return [cols[0]]


def _run_file_bench(path: Path, engine: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    list_ms = None
    page_ms = None
    search_ms = None
    table_name = None
    status = "ok"
    error = ""

    try:
        if engine == "duckdb":
            list_ms, tables = _measure(list_tables_duckdb, path)
            table_name = str(tables[0]) if tables else None
            if table_name:
                page_ms, _page = _measure(
                    read_table_page_duckdb,
                    path,
                    table_name,
                    50,
                    0,
                    None,
                    None,
                    None,
                    None,
                )
                search_ms, _search = _measure(
                    read_table_page_duckdb,
                    path,
                    table_name,
                    50,
                    0,
                    None,
                    "1",
                    None,
                    None,
                )
        else:
            list_ms, tables = _measure(list_tables_sqlite, path)
            table_name = str(tables[0]) if tables else None
            if table_name:
                page_ms, _page = _measure(
                    read_table_page_sqlite,
                    path,
                    table_name,
                    50,
                    0,
                    None,
                    None,
                    None,
                    None,
                )
                search_ms, _search = _measure(
                    fallback_search_sqlite,
                    path,
                    "1",
                    10,
                    200,
                    200,
                    "any",
                    None,
                    [table_name],
                )
    except Exception as exc:
        status = "error"
        error = str(exc)

    rows.append(
        {
            "kind": "file_flow",
            "engine": engine,
            "file": str(path),
            "table": table_name or "",
            "status": status,
            "error": error,
            "list_tables_ms": round(list_ms or 0.0, 3),
            "read_page_ms": round(page_ms or 0.0, 3),
            "search_probe_ms": round(search_ms or 0.0, 3),
            "compare_ms": "",
            "compare_table": "",
            "compare_keys": "",
        }
    )
    return rows


def _run_compare_bench(duck_paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if len(duck_paths) < 2:
        return rows

    for idx in range(len(duck_paths) - 1):
        a = duck_paths[idx]
        b = duck_paths[idx + 1]
        status = "ok"
        error = ""
        table = ""
        compare_ms = None
        keys: list[str] = []
        try:
            common = list_common_tables(a, b)
            if not common:
                status = "skip"
                error = "sem tabela em comum"
            else:
                table = str(common[0])
                keys = _pick_key_columns_duckdb(a, table)
                if not keys:
                    status = "skip"
                    error = "sem coluna de chave"
                else:
                    compare_ms, _result = _measure(
                        compare_table_duckdb_paged,
                        a,
                        b,
                        table,
                        keys,
                        None,
                        page=1,
                        page_size=200,
                    )
        except Exception as exc:
            status = "error"
            error = str(exc)

        rows.append(
            {
                "kind": "compare_flow",
                "engine": "duckdb",
                "file": f"{a.name} vs {b.name}",
                "table": table,
                "status": status,
                "error": error,
                "list_tables_ms": "",
                "read_page_ms": "",
                "search_probe_ms": "",
                "compare_ms": round(compare_ms or 0.0, 3),
                "compare_table": table,
                "compare_keys": ",".join(keys),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark validation flows for duckdb/sqlite files.")
    parser.add_argument(
        "--manifest",
        default="artifacts/validation/reports/dataset_manifest.json",
        help="Path to manifest generated by prepare_validation_artifacts.py",
    )
    parser.add_argument(
        "--out-csv",
        default="artifacts/validation/reports/benchmark_times.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--out-md",
        default="artifacts/validation/reports/benchmark_summary.md",
        help="Markdown summary output path",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = (repo_root / args.manifest).resolve()
    out_csv = (repo_root / args.out_csv).resolve()
    out_md = (repo_root / args.out_md).resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = data.get("items", [])

    rows: list[dict[str, Any]] = []
    duck_paths: list[Path] = []
    sqlite_paths: list[Path] = []

    for item in items:
        duck_ok = bool(item.get("duckdb_ok"))
        sqlite_ok = bool(item.get("sqlite_ok"))
        duck_path = Path(str(item.get("duckdb_path", "")))
        sqlite_path = Path(str(item.get("sqlite_path", "")))
        if duck_ok and duck_path.exists():
            duck_paths.append(duck_path)
            rows.extend(_run_file_bench(duck_path, "duckdb"))
        if sqlite_ok and sqlite_path.exists():
            sqlite_paths.append(sqlite_path)
            rows.extend(_run_file_bench(sqlite_path, "sqlite"))

    rows.extend(_run_compare_bench(sorted(duck_paths)))

    fieldnames = [
        "kind",
        "engine",
        "file",
        "table",
        "status",
        "error",
        "list_tables_ms",
        "read_page_ms",
        "search_probe_ms",
        "compare_ms",
        "compare_table",
        "compare_keys",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    err_rows = [r for r in rows if r.get("status") == "error"]
    skip_rows = [r for r in rows if r.get("status") == "skip"]

    def _avg(name: str) -> float:
        vals = []
        for row in ok_rows:
            value = row.get(name, "")
            if value == "":
                continue
            vals.append(float(value))
        if not vals:
            return 0.0
        return sum(vals) / float(len(vals))

    md = [
        "# Benchmark Summary",
        "",
        f"- total_rows: {len(rows)}",
        f"- ok: {len(ok_rows)}",
        f"- errors: {len(err_rows)}",
        f"- skipped: {len(skip_rows)}",
        "",
        "## Average Timing (ms)",
        "",
        f"- list_tables_ms: {_avg('list_tables_ms'):.3f}",
        f"- read_page_ms: {_avg('read_page_ms'):.3f}",
        f"- search_probe_ms: {_avg('search_probe_ms'):.3f}",
        f"- compare_ms: {_avg('compare_ms'):.3f}",
        "",
        "## Output",
        "",
        f"- csv: `{out_csv}`",
    ]
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"CSV gerado: {out_csv}")
    print(f"Resumo gerado: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
