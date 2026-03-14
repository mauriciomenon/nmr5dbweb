from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb

from tools.auto_compare_report import (
    build_table_detail_compact,
    render_report_html,
    list_candidate_files,
    prepare_source,
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


def _write_duckdb(db_path: Path, rows: list[tuple[int, str]]) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS T1 (id INTEGER, value VARCHAR)")
        conn.execute("DELETE FROM T1")
        conn.executemany("INSERT INTO T1 (id, value) VALUES (?, ?)", rows)
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
    cache_dir = docs / ".auto_compare_cache"
    assert cache_dir.exists()
    assert len(list(cache_dir.glob("*.duckdb"))) >= 2

    md_text = outputs["md"].read_text(encoding="utf-8")
    assert "diff_tables" in md_text
    assert "T1" in md_text
    assert "fonte_a_size" in md_text


def test_prepare_source_nao_colide_quando_stem_e_igual(tmp_path: Path) -> None:
    docs = tmp_path / "documentos"
    docs.mkdir()
    sqlite_path = docs / "foo.sqlite"
    duck_path = docs / "foo.duckdb"
    _write_sqlite(sqlite_path, [(1, "S")])
    _write_duckdb(duck_path, [(1, "D")])

    prepared_sqlite = prepare_source(sqlite_path, docs)
    prepared_duck = prepare_source(duck_path, docs)

    assert prepared_sqlite.duckdb_path.exists()
    assert prepared_sqlite.duckdb_path != duck_path.resolve()
    assert prepared_duck.sqlite_path.exists()
    assert prepared_duck.sqlite_path != sqlite_path.resolve()

    conn = duckdb.connect(str(duck_path), read_only=True)
    try:
        row = conn.execute("SELECT value FROM T1 WHERE id = 1").fetchone()
    finally:
        conn.close()
    assert row and row[0] == "D"


def test_build_table_detail_compact_usa_uniao_de_colunas_alteradas() -> None:
    payload = {
        "table": "SOSTAT",
        "key_columns": ["ID"],
        "compare_columns": ["C1", "C2", "C3", "C4"],
        "rows": [
            {
                "type": "changed",
                "key": {"ID": 1},
                "a": {"C1": "a", "C2": "b", "C3": "x", "C4": "m"},
                "b": {"C1": "a", "C2": "b", "C3": "y", "C4": "m"},
            },
            {
                "type": "changed",
                "key": {"ID": 2},
                "a": {"C1": "d", "C2": "e", "C3": "f", "C4": "g"},
                "b": {"C1": "d", "C2": "e", "C3": "f", "C4": "z"},
            },
            {
                "type": "added",
                "key": {"ID": 3},
                "a": {"C1": "", "C2": "", "C3": "", "C4": ""},
                "b": {"C1": "n1", "C2": "n2", "C3": "n3", "C4": "n4"},
            },
        ],
    }
    detail = build_table_detail_compact(payload, ["ID", "C1", "C2", "C3", "C4"])
    assert detail["visible_columns"] == ["C3", "C4"]
    assert len(detail["records"]) == 3
    added = detail["records"][2]
    assert set(added["new"].keys()) == {"C3", "C4"}
    assert str(added["key_values"]["ID"]) == "3"


def test_report_nao_exibe_tabela_same_no_bloco_de_alteracoes(tmp_path: Path) -> None:
    docs = tmp_path / "documentos"
    reports = docs / "reports"
    docs.mkdir()
    db1 = docs / "2026-01-29 DB2.sqlite"
    db2 = docs / "2026-02-27 DB4.sqlite"
    conn1 = sqlite3.connect(str(db1))
    conn2 = sqlite3.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE T1 (id INTEGER, value TEXT)")
        conn1.execute("CREATE TABLE T2 (id INTEGER, value TEXT)")
        conn2.execute("CREATE TABLE T1 (id INTEGER, value TEXT)")
        conn2.execute("CREATE TABLE T2 (id INTEGER, value TEXT)")
        conn1.executemany("INSERT INTO T1 VALUES (?, ?)", [(1, "A"), (2, "B")])
        conn2.executemany("INSERT INTO T1 VALUES (?, ?)", [(1, "A"), (2, "C")])
        conn1.executemany("INSERT INTO T2 VALUES (?, ?)", [(1, "X"), (2, "Y")])
        conn2.executemany("INSERT INTO T2 VALUES (?, ?)", [(1, "X"), (2, "Y")])
        conn1.commit()
        conn2.commit()
    finally:
        conn1.close()
        conn2.close()

    outputs = run_compare_pipeline(db1, db2, docs, reports)
    md_text = outputs["md"].read_text(encoding="utf-8")
    assert "| T1 | alterado |" in md_text
    assert "| T2 | igual |" not in md_text


def test_build_table_detail_compact_sostat_forca_colunas_padrao() -> None:
    payload = {
        "table": "RANGER_SOSTAT",
        "key_columns": ["UNIQID"],
        "compare_columns": ["RTUNO", "PNTNO", "PNTNAM", "STTYPE", "BITBYT", "ITEMNB"],
        "rows": [
            {
                "type": "changed",
                "key": {"UNIQID": "X1"},
                "a": {"RTUNO": 1, "PNTNO": 2, "PNTNAM": "A", "STTYPE": "S", "BITBYT": 0, "ITEMNB": 10},
                "b": {"RTUNO": 1, "PNTNO": 2, "PNTNAM": "A", "STTYPE": "T", "BITBYT": 0, "ITEMNB": 10},
            }
        ],
    }
    detail = build_table_detail_compact(
        payload,
        ["RTUNO", "PNTNO", "PNTNAM", "STTYPE", "BITBYT", "UNIQID", "ITEMNB"],
    )
    assert detail["visible_columns"] == [
        "RTUNO",
        "PNTNO",
        "PNTNAM",
        "STTYPE",
        "BITBYT",
        "UNIQID",
        "ITEMNB",
    ]


def test_build_table_detail_compact_soanlg_forca_colunas_padrao() -> None:
    payload = {
        "table": "RANGER_SOANLG",
        "key_columns": ["UNIQID"],
        "compare_columns": ["BIAS", "SCALE", "HLIM5", "LLIM5", "ITEMNB"],
        "rows": [
            {
                "type": "changed",
                "key": {"UNIQID": "X2"},
                "a": {
                    "RTUNO": "105.",
                    "PNTNO": "172.",
                    "BIAS": 0.0,
                    "SCALE": 1.0,
                    "HLIM5": 2.0,
                    "LLIM5": 0.0,
                    "ITEMNB": 5,
                },
                "b": {
                    "RTUNO": "105.",
                    "PNTNO": "172.",
                    "BIAS": 0.1,
                    "SCALE": 1.0,
                    "HLIM5": 2.0,
                    "LLIM5": 0.0,
                    "ITEMNB": 5,
                },
            }
        ],
    }
    detail = build_table_detail_compact(
        payload,
        ["RTUNO", "PNTNO", "PNTNAM", "BIAS", "SCALE", "ENGINX", "HLIM5", "HLIM6", "LLIM5", "LLIM6", "ITEMNB"],
    )
    assert detail["visible_columns"] == [
        "RTUNO",
        "PNTNO",
        "PNTNAM",
        "BIAS",
        "SCALE",
        "ENGINX",
        "HLIM6",
        "LLIM6",
        "ITEMNB",
    ]
    row_new = detail["records"][0]["new"]
    row_old = detail["records"][0]["old"]
    assert row_new["RTUNO"] == "105"
    assert row_new["PNTNO"] == "172"
    assert row_old["BIAS"] == "0"
    assert row_new["BIAS"] == "0.1"


def test_build_table_detail_compact_soanlg_mantem_hlim5_llim5_quando_mudam() -> None:
    payload = {
        "table": "RANGER_SOANLG",
        "key_columns": ["UNIQID"],
        "compare_columns": ["BIAS", "SCALE", "HLIM5", "LLIM5", "ITEMNB"],
        "rows": [
            {
                "type": "changed",
                "key": {"UNIQID": "X3"},
                "a": {"RTUNO": 101, "PNTNO": 202, "BIAS": 0.0, "SCALE": 1.0, "HLIM5": 1.5, "LLIM5": 0.0, "ITEMNB": 7},
                "b": {"RTUNO": 101, "PNTNO": 202, "BIAS": 0.0, "SCALE": 1.0, "HLIM5": 2.5, "LLIM5": -1.0, "ITEMNB": 7},
            }
        ],
    }
    detail = build_table_detail_compact(
        payload,
        ["RTUNO", "PNTNO", "PNTNAM", "BIAS", "SCALE", "ENGINX", "HLIM5", "HLIM6", "LLIM5", "LLIM6", "ITEMNB"],
    )
    assert "HLIM5" in detail["visible_columns"]
    assert "LLIM5" in detail["visible_columns"]


def test_render_report_html_sem_pintura_de_linha_e_com_classes_de_texto() -> None:
    payload = {
        "generated_at": "2026-03-13T15:00:00",
        "source_a": {
            "file": "A.accdb",
            "path": "/tmp/A.accdb",
            "engine": "access",
            "size_bytes": 1,
            "mtime": "2026-03-13T10:00:00",
            "iso_date": "2026-03-13",
            "duckdb": "/tmp/A.duckdb",
            "sqlite": "/tmp/A.sqlite",
            "steps": ["x"],
        },
        "source_b": {
            "file": "B.accdb",
            "path": "/tmp/B.accdb",
            "engine": "access",
            "size_bytes": 1,
            "mtime": "2026-03-13T10:00:00",
            "iso_date": "2026-03-13",
            "duckdb": "/tmp/B.duckdb",
            "sqlite": "/tmp/B.sqlite",
            "steps": ["x"],
        },
        "summary": {
            "total_tables": 1,
            "same_tables": 0,
            "diff_tables": 1,
            "no_key_tables": 0,
            "error_tables": 0,
        },
        "rows": [{"table": "T1", "status": "diff", "row_count_a": 1, "row_count_b": 1, "diff_count": 1}],
        "table_details": [
            {
                "table": "T1",
                "key_columns": ["UNIQID"],
                "visible_columns": ["C1"],
                "rows_total": 1,
                "rows_returned": 1,
                "records": [
                    {
                        "type": "changed",
                        "key_values": {"UNIQID": "1"},
                        "old": {"C1": "OLD"},
                        "new": {"C1": "NEW"},
                        "changed": {"C1": True},
                    }
                ],
            }
        ],
    }
    html = render_report_html(payload)
    assert "Comparacao banco A.accdb com banco B.accdb" in html
    assert "value-added" in html
    assert "value-removed" in html
    assert "background: #fee2e2" not in html
    assert "col-filter-input" in html
    assert "db 2026-03-13" in html
    assert "<th>UNIQID</th>" in html
    assert "<strong>" not in html
    assert "font-weight: 700" not in html
    assert "pipeline tecnico" in html
    assert "Bancos utilizados no fluxo" in html
    assert "duckdb: base SQL principal da comparacao" in html
    assert "nao_contem" in html
    assert "crescente" in html
    assert "sem_ordenacao" in html
