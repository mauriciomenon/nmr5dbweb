import sys
from pathlib import Path

import duckdb

# garante que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import interface.app_flask_local_search as local_search  # noqa: E402


app = local_search.app


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


def test_api_compare_change_types_empty_returns_400(tmp_path):
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
            "change_types": [],
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "change_types deve conter ao menos um tipo"


def test_api_compare_key_columns_duplicadas_returns_400(tmp_path):
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
            "key_columns": ["id", "id"],
            "compare_columns": ["valor"],
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "key_columns nao pode conter colunas duplicadas"


def test_api_compare_compare_columns_duplicadas_returns_400(tmp_path):
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
            "compare_columns": ["valor", "valor"],
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "compare_columns nao pode conter colunas duplicadas"


def test_api_compare_same_db_paths_returns_400(tmp_path):
    client = app.test_client()

    db1 = tmp_path / "db1.duckdb"
    _make_db(db1, [(1, "a")])

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db1),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "db1_path e db2_path nao podem ser o mesmo arquivo"


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


def test_api_compare_row_limit_does_not_truncate_key_filter(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()

    seen_args = []

    def fake_compare_paged(
        _db1,
        _db2,
        _table,
        _keys,
        _compare,
        *,
        key_filter=None,
        change_types=None,
        changed_column=None,
        page=1,
        page_size=100,
    ):
        seen_args.append({
            "key_filter": key_filter,
            "change_types": change_types,
            "changed_column": changed_column,
            "page": page,
            "page_size": page_size,
        })
        return {
            "table": "T",
            "db1": str(db1),
            "db2": str(db2),
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "row_count": 1,
            "rows": [{"type": "changed", "key": {"id": 3}, "a": {"valor": "m"}, "b": {"valor": "n"}}],
            "page": 1,
            "page_size": 1,
            "total_filtered_rows": 1,
            "total_pages": 1,
            "summary": {
                "rows_a": 3,
                "rows_b": 3,
                "keys_total": 3,
                "same_count": 0,
                "added_count": 0,
                "removed_count": 1,
                "changed_count": 2,
            },
        }

    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", fake_compare_paged)

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "key_filter": "id=3",
            "row_limit": 1,
            "page_size": 1,
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert seen_args == [{
        "key_filter": {"id": "3"},
        "change_types": None,
        "changed_column": None,
        "page": 1,
        "page_size": 1,
    }]
    assert data["total_filtered_rows"] == 1
    assert data["row_count"] == 1
    assert data["rows"][0]["key"]["id"] == 3


def test_api_compare_row_limit_does_not_truncate_changed_column_filter(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()

    seen_args = []

    def fake_compare_paged(
        _db1,
        _db2,
        _table,
        _keys,
        _compare,
        *,
        key_filter=None,
        change_types=None,
        changed_column=None,
        page=1,
        page_size=100,
    ):
        seen_args.append({
            "key_filter": key_filter,
            "change_types": change_types,
            "changed_column": changed_column,
            "page": page,
            "page_size": page_size,
        })
        return {
            "table": "T",
            "db1": str(db1),
            "db2": str(db2),
            "key_columns": ["id"],
            "compare_columns": ["v1", "v2"],
            "row_count": 1,
            "rows": [{"type": "changed", "key": {"id": 2}, "a": {"v1": "c", "v2": "z"}, "b": {"v1": "d", "v2": "z"}}],
            "page": 1,
            "page_size": 1,
            "total_filtered_rows": 1,
            "total_pages": 1,
            "summary": {
                "rows_a": 2,
                "rows_b": 2,
                "keys_total": 2,
                "same_count": 0,
                "added_count": 0,
                "removed_count": 0,
                "changed_count": 2,
            },
        }

    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", fake_compare_paged)

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["v1", "v2"],
            "changed_column": "v1",
            "row_limit": 1,
            "page_size": 1,
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert seen_args == [{
        "key_filter": {},
        "change_types": None,
        "changed_column": "v1",
        "page": 1,
        "page_size": 1,
    }]
    assert data["total_filtered_rows"] == 1
    assert data["rows"][0]["key"]["id"] == 2


def test_api_compare_row_limit_does_not_truncate_change_types_filter(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()

    seen_args = []

    def fake_compare_paged(
        _db1,
        _db2,
        _table,
        _keys,
        _compare,
        *,
        key_filter=None,
        change_types=None,
        changed_column=None,
        page=1,
        page_size=100,
    ):
        seen_args.append({
            "key_filter": key_filter,
            "change_types": change_types,
            "changed_column": changed_column,
            "page": page,
            "page_size": page_size,
        })
        return {
            "table": "T",
            "db1": str(db1),
            "db2": str(db2),
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "row_count": 1,
            "rows": [{"type": "added", "key": {"id": 3}, "a": {"valor": None}, "b": {"valor": "z"}}],
            "page": 1,
            "page_size": 1,
            "total_filtered_rows": 1,
            "total_pages": 1,
            "summary": {
                "rows_a": 2,
                "rows_b": 2,
                "keys_total": 3,
                "same_count": 0,
                "added_count": 1,
                "removed_count": 1,
                "changed_count": 1,
            },
        }

    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", fake_compare_paged)

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "change_types": ["added"],
            "row_limit": 1,
            "page_size": 1,
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert seen_args == [{
        "key_filter": {},
        "change_types": ["added"],
        "changed_column": None,
        "page": 1,
        "page_size": 1,
    }]
    assert data["total_filtered_rows"] == 1
    assert data["rows"][0]["type"] == "added"
    assert data["rows"][0]["key"]["id"] == 3


def test_api_compare_pagination_uses_full_diff_set(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()

    seen_args = []

    def fake_compare_paged(
        _db1,
        _db2,
        _table,
        _keys,
        _compare,
        *,
        key_filter=None,
        change_types=None,
        changed_column=None,
        page=1,
        page_size=100,
    ):
        seen_args.append({
            "key_filter": key_filter,
            "change_types": change_types,
            "changed_column": changed_column,
            "page": page,
            "page_size": page_size,
        })
        return {
            "table": "T",
            "db1": str(db1),
            "db2": str(db2),
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "row_count": 1,
            "rows": [{"type": "removed", "key": {"id": 2}, "a": {"valor": "x"}, "b": {"valor": None}}],
            "page": page,
            "page_size": page_size,
            "total_filtered_rows": 3,
            "total_pages": 3,
            "summary": {
                "rows_a": 2,
                "rows_b": 2,
                "keys_total": 3,
                "same_count": 0,
                "added_count": 1,
                "removed_count": 1,
                "changed_count": 1,
            },
        }

    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", fake_compare_paged)

    payload = {
        "db1_path": str(db1),
        "db2_path": str(db2),
        "table": "T",
        "key_columns": ["id"],
        "compare_columns": ["valor"],
        "row_limit": 1,
        "page_size": 1,
    }
    resp_page_1 = client.post("/api/compare_db_rows", json=payload | {"page": 1})
    resp_page_2 = client.post("/api/compare_db_rows", json=payload | {"page": 2})

    assert resp_page_1.status_code == 200
    assert resp_page_2.status_code == 200
    data_page_1 = resp_page_1.get_json()
    data_page_2 = resp_page_2.get_json()

    assert seen_args == [
        {"key_filter": {}, "change_types": None, "changed_column": None, "page": 1, "page_size": 1},
        {"key_filter": {}, "change_types": None, "changed_column": None, "page": 2, "page_size": 1},
    ]
    assert data_page_1["total_filtered_rows"] == 3
    assert data_page_1["total_pages"] == 3
    assert data_page_1["page"] == 1
    assert data_page_2["total_filtered_rows"] == 3
    assert data_page_2["total_pages"] == 3
    assert data_page_2["page"] == 2
    assert data_page_1["rows"][0]["key"]["id"] == 2
    assert data_page_2["rows"][0]["key"]["id"] == 2


def test_api_compare_page_invalid_returns_400(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "page": "abc",
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "page deve ser um inteiro"


def test_api_compare_page_size_excessivo_eh_rejeitado(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()
    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", lambda *_args, **_kwargs: {})

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "page_size": 5000,
        },
    )

    assert resp.status_code == 400
    assert "page_size deve ser no maximo" in resp.get_json()["error"]


def test_api_compare_row_limit_muito_alto_eh_rejeitado(monkeypatch, tmp_path):
    client = app.test_client()
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    db1.touch()
    db2.touch()
    monkeypatch.setattr(local_search, "compare_table_duckdb_paged", lambda *_args, **_kwargs: {})

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
            "row_limit": 5000,
        },
    )

    assert resp.status_code == 400
    assert "row_limit deve ser no maximo" in resp.get_json()["error"]
