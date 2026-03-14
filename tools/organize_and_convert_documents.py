#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from access_convert import convert_access_to_duckdb


ACCESS_EXTS = {".accdb", ".mdb"}
SQLITE_SYSTEM_PREFIXES = ("sqlite_",)
DUCKDB_SYSTEM_PREFIXES = ("duckdb_",)


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _map_sqlite_type(duck_type: str) -> str:
    t = (duck_type or "").upper()
    if any(k in t for k in ("INT", "HUGEINT", "UBIGINT")):
        return "INTEGER"
    if any(k in t for k in ("DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")):
        return "REAL"
    if any(k in t for k in ("BLOB", "BYTEA", "BINARY")):
        return "BLOB"
    return "TEXT"


def list_duckdb_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    tables = [str(row[0]) for row in conn.execute("SHOW TABLES").fetchall()]
    out: list[str] = []
    for table in tables:
        low = table.lower()
        if low == "_fulltext":
            continue
        if low.startswith("msys"):
            continue
        if low.startswith(SQLITE_SYSTEM_PREFIXES) or low.startswith(DUCKDB_SYSTEM_PREFIXES):
            continue
        out.append(table)
    return out


def list_sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    out: list[str] = []
    for row in rows:
        name = str(row[0])
        low = name.lower()
        if low == "_fulltext":
            continue
        if low.startswith("msys"):
            continue
        if low.startswith(SQLITE_SYSTEM_PREFIXES) or low.startswith(DUCKDB_SYSTEM_PREFIXES):
            continue
        out.append(name)
    return out


def duckdb_to_sqlite(duckdb_path: Path, sqlite_path: Path) -> tuple[bool, str]:
    if sqlite_path.exists():
        sqlite_path.unlink()
    src = duckdb.connect(str(duckdb_path), read_only=True)
    dst = sqlite3.connect(str(sqlite_path))
    try:
        tables = list_duckdb_tables(src)
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
    except Exception as exc:  # noqa: BLE001
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


def table_count(path: Path, engine: str) -> int:
    try:
        if engine == "duckdb":
            conn = duckdb.connect(str(path), read_only=True)
            try:
                return len(list_duckdb_tables(conn))
            finally:
                conn.close()
        if engine == "sqlite":
            conn = sqlite3.connect(str(path))
            try:
                return len(list_sqlite_tables(conn))
            finally:
                conn.close()
    except Exception:
        return -1
    return -1


def resolve_unique_dest(target_dir: Path, filename: str) -> Path:
    candidate = target_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    ext = Path(filename).suffix
    for idx in range(1, 1000):
        alt = target_dir / f"{stem}_{idx}{ext}"
        if not alt.exists():
            return alt
    raise RuntimeError(f"nao foi possivel reservar destino unico para {filename}")


@dataclass
class ItemReport:
    source_path: str
    access_path: str
    moved: bool
    duckdb_path: str
    sqlite_path: str
    access_to_duckdb_ok: bool
    access_to_duckdb_msg: str
    access_to_duckdb_seconds: float
    duckdb_to_sqlite_ok: bool
    duckdb_to_sqlite_msg: str
    duckdb_to_sqlite_seconds: float
    duckdb_table_count: int
    sqlite_table_count: int
    reliability_ok: bool


def gather_access_files(source_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for source_dir in source_dirs:
        if not source_dir.exists() or not source_dir.is_dir():
            continue
        for item in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
            if not item.is_file():
                continue
            if item.suffix.lower() not in ACCESS_EXTS:
                continue
            files.append(item)
    return files


def write_reports(
    destination_root: Path,
    reports: list[ItemReport],
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Path]:
    reports_dir = destination_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = finished_at.strftime("%Y%m%d_%H%M%S")

    total = len(reports)
    ok = len([r for r in reports if r.reliability_ok])
    fail = total - ok
    access_ok = len([r for r in reports if r.access_to_duckdb_ok])
    sqlite_ok = len([r for r in reports if r.duckdb_to_sqlite_ok])
    total_access_sec = sum(r.access_to_duckdb_seconds for r in reports)
    total_sqlite_sec = sum(r.duckdb_to_sqlite_seconds for r in reports)

    summary: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "target_dir": str(destination_root),
        "total_files": total,
        "reliability_ok": ok,
        "reliability_fail": fail,
        "access_to_duckdb_ok": access_ok,
        "duckdb_to_sqlite_ok": sqlite_ok,
        "total_access_to_duckdb_seconds": round(total_access_sec, 3),
        "total_duckdb_to_sqlite_seconds": round(total_sqlite_sec, 3),
        "items": [asdict(item) for item in reports],
    }

    json_path = reports_dir / f"conversion_report_{stamp}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    csv_path = reports_dir / f"conversion_report_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(reports[0]).keys()) if reports else ["source_path"])
        writer.writeheader()
        for item in reports:
            writer.writerow(asdict(item))

    md_lines = [
        "# Conversion Report",
        "",
        f"- started_at: `{summary['started_at']}`",
        f"- finished_at: `{summary['finished_at']}`",
        f"- target_dir: `{summary['target_dir']}`",
        f"- total_files: `{total}`",
        f"- reliability_ok: `{ok}`",
        f"- reliability_fail: `{fail}`",
        f"- access_to_duckdb_ok: `{access_ok}`",
        f"- duckdb_to_sqlite_ok: `{sqlite_ok}`",
        f"- total_access_to_duckdb_seconds: `{summary['total_access_to_duckdb_seconds']}`",
        f"- total_duckdb_to_sqlite_seconds: `{summary['total_duckdb_to_sqlite_seconds']}`",
        "",
        "## Items",
        "",
        "| access | duckdb_ok | sqlite_ok | reliability | access_sec | sqlite_sec | duck_tables | sqlite_tables |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in reports:
        md_lines.append(
            f"| `{Path(item.access_path).name}` | {int(item.access_to_duckdb_ok)} | {int(item.duckdb_to_sqlite_ok)} "
            f"| {int(item.reliability_ok)} | {item.access_to_duckdb_seconds:.3f} | {item.duckdb_to_sqlite_seconds:.3f} "
            f"| {item.duckdb_table_count} | {item.sqlite_table_count} |"
        )
    md_lines.append("")

    md_path = reports_dir / "latest_conversion_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    latest_json = reports_dir / "latest_conversion_report.json"
    latest_json.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "json": json_path,
        "csv": csv_path,
        "md": md_path,
        "latest_json": latest_json,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move Access files to documentos and generate duckdb/sqlite with timings."
    )
    parser.add_argument(
        "--target-dir",
        default="documentos",
        help="Destination directory for .accdb/.mdb/.duckdb/.sqlite (default: documentos).",
    )
    parser.add_argument(
        "--source-dir",
        action="append",
        default=None,
        help="Source directory to scan for Access files. Can be used multiple times.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy instead of move the Access files.",
    )
    parser.add_argument(
        "--prefer-odbc",
        action="store_true",
        help="Prefer ODBC for Access conversion. Default: enabled only on Windows.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target_dir = (root / args.target_dir).resolve()
    source_dirs_input = args.source_dir or ["output", "interface/uploads"]
    source_dirs = [(root / item).resolve() for item in source_dirs_input]

    target_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    print(f"[info] target_dir={target_dir}")
    print("[info] source_dirs=" + ", ".join(str(p) for p in source_dirs))

    source_access_files = gather_access_files(source_dirs)
    if not source_access_files:
        print("[warn] no access files found in source directories")

    reports: list[ItemReport] = []
    move_mode = "copy" if args.copy else "move"
    prefer_odbc = bool(args.prefer_odbc or os.name == "nt")

    for src in source_access_files:
        access_dest = src
        moved = False
        if src.parent != target_dir:
            access_dest = resolve_unique_dest(target_dir, src.name)
            if args.copy:
                shutil.copy2(src, access_dest)
            else:
                shutil.move(str(src), str(access_dest))
            moved = True
        print(f"[info] {move_mode}: {src} -> {access_dest}")

        duck_path = access_dest.with_suffix(".duckdb")
        sqlite_path = access_dest.with_suffix(".sqlite")

        t0 = time.perf_counter()
        ok_duck, msg_duck = convert_access_to_duckdb(
            str(access_dest),
            str(duck_path),
            chunk_size=20000,
            prefer_odbc=prefer_odbc,
        )
        dt_duck = time.perf_counter() - t0
        print(f"[info] access->duckdb: ok={ok_duck} sec={dt_duck:.3f} file={access_dest.name}")

        ok_sqlite = False
        msg_sqlite = "duckdb nao gerado"
        dt_sqlite = 0.0
        if ok_duck and duck_path.exists():
            t1 = time.perf_counter()
            ok_sqlite, msg_sqlite = duckdb_to_sqlite(duck_path, sqlite_path)
            dt_sqlite = time.perf_counter() - t1
            print(f"[info] duckdb->sqlite: ok={ok_sqlite} sec={dt_sqlite:.3f} file={access_dest.name}")

        duck_tables = table_count(duck_path, "duckdb") if duck_path.exists() else -1
        sqlite_tables = table_count(sqlite_path, "sqlite") if sqlite_path.exists() else -1
        reliability_ok = bool(ok_duck and ok_sqlite and duck_tables >= 0 and duck_tables == sqlite_tables)

        reports.append(
            ItemReport(
                source_path=str(src),
                access_path=str(access_dest),
                moved=moved,
                duckdb_path=str(duck_path),
                sqlite_path=str(sqlite_path),
                access_to_duckdb_ok=bool(ok_duck),
                access_to_duckdb_msg=str(msg_duck),
                access_to_duckdb_seconds=round(float(dt_duck), 6),
                duckdb_to_sqlite_ok=bool(ok_sqlite),
                duckdb_to_sqlite_msg=str(msg_sqlite),
                duckdb_to_sqlite_seconds=round(float(dt_sqlite), 6),
                duckdb_table_count=int(duck_tables),
                sqlite_table_count=int(sqlite_tables),
                reliability_ok=reliability_ok,
            )
        )

    finished_at = datetime.now(timezone.utc)
    report_paths = write_reports(target_dir, reports, started_at, finished_at)
    total = len(reports)
    ok = len([r for r in reports if r.reliability_ok])
    fail = total - ok

    print("[done] conversion completed")
    print(f"[done] total={total} ok={ok} fail={fail}")
    print(f"[done] report_json={report_paths['json']}")
    print(f"[done] report_csv={report_paths['csv']}")
    print(f"[done] report_md={report_paths['md']}")

    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
