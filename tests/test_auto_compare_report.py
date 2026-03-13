from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.auto_compare_report import (
    list_candidate_files,
    run_compare_pipeline,
    suggest_two_sources,
)


def _write_sqlite(db_path: Path, rows: list[tuple[int, str]]) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS T1 (id INTEGER, value TEXT)")
        conn.execute("DELETE FROM T1")
        conn.executemany("INSERT INTO T1 (id, value) VALUES (?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def test_suggest_two_sources_prefere_access(tmp_path: Path) -> None:
    docs = tmp_path / "documentos"
    docs.mkdir()
    (docs / "2026-01-20 DB1.accdb").write_bytes(b"access-a")
    (docs / "2026-02-10 DB2.accdb").write_bytes(b"access-b")
    _write_sqlite(docs / "2026-03-01 DB3.sqlite", [(1, "x")])

    items = list_candidate_files(docs)
    a, b = suggest_two_sources(items)
    assert a.path.name == "2026-02-10 DB2.accdb"
    assert b.path.name == "2026-01-20 DB1.accdb"


def test_run_compare_pipeline_sqlite_inputs(tmp_path: Path) -> None:
    docs = tmp_path / "documentos"
    reports = docs / "reports"
    docs.mkdir()
    _write_sqlite(docs / "2026-01-29 DB2.sqlite", [(1, "A"), (2, "B")])
    _write_sqlite(docs / "2026-02-27 DB4.sqlite", [(1, "A"), (2, "C")])

    outputs = run_compare_pipeline(
        docs / "2026-01-29 DB2.sqlite",
        docs / "2026-02-27 DB4.sqlite",
        docs,
        reports,
    )

    assert outputs["html"].exists()
    assert outputs["md"].exists()
    assert outputs["txt"].exists()
    assert (reports / "latest_db_compare_report.html").exists()
    assert (reports / "latest_db_compare_report.md").exists()
    assert (reports / "latest_db_compare_report.txt").exists()
    assert (docs / "2026-01-29 DB2.duckdb").exists()
    assert (docs / "2026-02-27 DB4.duckdb").exists()

    md_text = outputs["md"].read_text(encoding="utf-8")
    assert "diff_tables" in md_text
    assert "T1" in md_text
    assert "fonte_a_steps" in md_text
