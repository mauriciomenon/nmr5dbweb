import sys
from pathlib import Path

import duckdb

# garante que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.app_flask_local_search import app  # noqa: E402


def _make_db(path: Path, rows):
    """Cria um pequeno banco DuckDB com tabela T(id INT, valor TEXT)."""
    conn = duckdb.connect(str(path))
    try:
        conn.execute("CREATE TABLE T(id INTEGER, valor TEXT)")
        if rows:
            conn.executemany("INSERT INTO T(id, valor) VALUES (?, ?)", rows)
    finally:
        conn.close()


def test_api_compare_no_filters(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    # id=1 igual, id=2 só em A, id=3 só em B, id=4 mudou
    _make_db(db1, [(1, "a"), (2, "b"), (4, "x")])
    _make_db(db2, [(1, "a"), (3, "c"), (4, "y")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    summary = data["summary"]
    assert summary["keys_total"] == 4
    assert summary["added_count"] == 1
    assert summary["removed_count"] == 1
    assert summary["changed_count"] == 1
    assert summary["same_count"] == 1

    types = sorted(r["type"] for r in data["rows"])
    assert types == ["added", "changed", "removed"]


def test_api_compare_key_filter(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a"), (2, "b"), (4, "x")])
    _make_db(db2, [(1, "a"), (3, "c"), (4, "y")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "key_filter": "id=4",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    # apenas a chave 4 deve aparecer nos detalhes
    assert data["row_count"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["key"]["id"] == 4
    assert data["rows"][0]["type"] == "changed"


def test_api_compare_change_types(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a"), (2, "b"), (4, "x")])
    _make_db(db2, [(1, "a"), (3, "c"), (4, "y")])

    # somente "added" (novos em B)
    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "change_types": ["added"],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["row_count"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["type"] == "added"


def test_api_compare_changed_column_filter(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE T(id INTEGER, v1 TEXT, v2 TEXT)")
        conn2.execute("CREATE TABLE T(id INTEGER, v1 TEXT, v2 TEXT)")
        # id=1: muda v1
        conn1.execute("INSERT INTO T VALUES (1, 'a', 'x')")
        conn2.execute("INSERT INTO T VALUES (1, 'b', 'x')")
        # id=2: muda v2
        conn1.execute("INSERT INTO T VALUES (2, 'c', 'y')")
        conn2.execute("INSERT INTO T VALUES (2, 'c', 'z')")
    finally:
        conn1.close()
        conn2.close()

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["v1", "v2"],
            "change_types": ["changed"],
            "changed_column": "v1",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    # apenas a linha cujo v1 mudou deve aparecer (id=1)
    assert data["row_count"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["key"]["id"] == 1
    assert data["rows"][0]["type"] == "changed"


def test_api_compare_key_filter_invalid_format_returns_400(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a")])
    _make_db(db2, [(1, "a")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "key_filter": "id",
        },
    )

    assert resp.status_code == 400
    assert "key_filter" in resp.get_json()["error"]


def test_api_compare_key_filter_unknown_key_column_returns_400(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a")])
    _make_db(db2, [(1, "a")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "key_filter": "valor=a",
        },
    )

    assert resp.status_code == 400
    assert "fora de key_columns" in resp.get_json()["error"]


def test_api_compare_change_types_invalid_returns_400(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a")])
    _make_db(db2, [(1, "b")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "change_types": ["changed", "foo"],
        },
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "change_types contem valores invalidos"
    assert data["invalid"] == ["foo"]


def test_api_compare_changed_column_outside_compare_columns_returns_400(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a")])
    _make_db(db2, [(1, "b")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "changed_column": "outra_coluna",
        },
    )

    assert resp.status_code == 400
    assert "changed_column" in resp.get_json()["error"]
