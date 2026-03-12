from io import BytesIO
import sqlite3

import duckdb

import interface.app_flask_local_search as local_search


app = local_search.app


def test_admin_upload_rejeita_nome_invalido_sem_gravar(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", lambda _path: None)

    resp = client.post(
        "/admin/upload",
        data={"file": (BytesIO(b"content"), "..")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "nome de arquivo inválido"
    assert list(tmp_path.iterdir()) == []


def test_admin_upload_rejeita_extensao_nao_permitida_sem_gravar(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", lambda _path: None)

    resp = client.post(
        "/admin/upload",
        data={"file": (BytesIO(b"content"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "extensão não permitida" in resp.get_json()["error"]
    assert list(tmp_path.iterdir()) == []


def test_admin_upload_db_seleciona_imediatamente(tmp_path, monkeypatch):
    client = app.test_client()
    selected = []
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", selected.append)

    resp = client.post(
        "/admin/upload",
        data={"file": (BytesIO(b"duck"), "sample.sqlite3")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    saved_path = tmp_path / "sample.sqlite3"
    assert payload["ok"] is True
    assert payload["db_path"] == str(saved_path)
    assert selected == [str(saved_path)]
    assert saved_path.read_bytes() == b"duck"


def test_admin_list_uploads_retorna_metadados_basicos(tmp_path, monkeypatch):
    client = app.test_client()
    sample = tmp_path / "sample.sqlite3"
    sample.write_bytes(b"duck")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(sample))
    monkeypatch.setitem(local_search.cfg, "priority_tables", ["alpha"])
    monkeypatch.setitem(local_search.cfg, "auto_index_after_convert", False)

    resp = client.get("/admin/list_uploads")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["current_db"] == str(sample)
    assert payload["priority_tables"] == ["alpha"]
    assert payload["auto_index_after_convert"] is False
    assert payload["uploads"][0]["name"] == "sample.sqlite3"
    assert payload["uploads"][0]["size"] == 4


def test_admin_start_index_sem_indexador_retorna_erro(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "create_or_resume_fulltext", None)

    resp = client.post("/admin/start_index", json={})

    assert resp.status_code == 500
    assert "indexador não disponível" in resp.get_json()["error"]


def test_admin_delete_remove_db_convertido_derivado(tmp_path, monkeypatch):
    client = app.test_client()
    source = tmp_path / "sample.accdb"
    derived = tmp_path / "sample.duckdb"
    source.write_bytes(b"accdb")
    derived.write_bytes(b"duck")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(source))
    monkeypatch.setattr(local_search, "clear_db_path", lambda: None)

    resp = client.post("/admin/delete", json={"filename": "sample.accdb"})

    assert resp.status_code == 200
    assert not source.exists()
    assert not derived.exists()


def test_admin_start_index_rejeita_chunk_invalido(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "create_or_resume_fulltext", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_search, "index_thread", None)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(tmp_path / "db.duckdb"))

    resp = client.post("/admin/start_index", json={"chunk": "x"})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "chunk/batch must be integers"


def test_admin_start_index_rejeita_sqlite(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE alpha (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(local_search, "create_or_resume_fulltext", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_search, "index_thread", None)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.post("/admin/start_index", json={})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "indexacao _fulltext disponivel apenas para DuckDB"


def test_api_search_rejeita_parametros_invalidos():
    client = app.test_client()

    resp = client.get("/api/search?q=test&per_table=abc")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "per_table must be an integer"


def test_admin_status_expoe_capacidades_e_warning(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "startup_warnings", ["db_path configurado nao existe mais: /tmp/lost.duckdb"])
    monkeypatch.setitem(local_search.runtime_state, "db_path", "")

    resp = client.get("/admin/status")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["startup_warnings"] == ["db_path configurado nao existe mais: /tmp/lost.duckdb"]
    assert payload["capabilities"]["duckdb_fulltext"] in {True, False}
    assert payload["capabilities"]["access_conversion"] in {True, False}
    assert payload["capabilities"]["access_fallback"] in {True, False}


def test_api_tables_rejeita_db_ativo_ausente(tmp_path, monkeypatch):
    client = app.test_client()
    missing = tmp_path / "missing.duckdb"
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(missing))

    resp = client.get("/api/tables")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == f"DB ativo nao encontrado: {missing}"


def test_api_search_rejeita_db_ativo_ausente(tmp_path, monkeypatch):
    client = app.test_client()
    missing = tmp_path / "missing.duckdb"
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(missing))

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == f"DB ativo nao encontrado: {missing}"


def test_api_tables_lista_tabelas_sqlite(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE alpha (id INTEGER, name TEXT)")
    conn.execute("CREATE TABLE beta (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.get("/api/tables")

    assert resp.status_code == 200
    assert resp.get_json()["tables"] == ["alpha", "beta"]


def test_api_table_ler_tabela_sqlite(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE "event log" (id INTEGER, note TEXT)')
    conn.executemany(
        'INSERT INTO "event log" (id, note) VALUES (?, ?)',
        [(1, "alpha"), (2, "beta"), (3, "alphabet")],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.get("/api/table?name=event%20log&col=note&q=alp&sort=id&order=DESC&limit=2&offset=0")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["columns"] == ["id", "note"]
    assert payload["total"] == 2
    assert payload["rows"] == [
        {"id": 3, "note": "alphabet"},
        {"id": 1, "note": "alpha"},
    ]


def test_api_tables_detecta_sqlite_em_extensao_db(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE app_table (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.get("/api/tables")

    assert resp.status_code == 200
    assert resp.get_json()["tables"] == ["app_table"]


def test_api_tables_detecta_duckdb_em_extensao_db(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.db"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE duck_table (id INTEGER)")
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.get("/api/tables")

    assert resp.status_code == 200
    assert resp.get_json()["tables"] == ["duck_table"]


def test_api_search_busca_textual_sqlite(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE alpha (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO alpha VALUES (1, 'alpha unit')")
    conn.execute("INSERT INTO alpha VALUES (2, 'beta unit')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["returned_count"] == 1
    assert payload["results"]["alpha"][0]["row"]["name"] == "alpha unit"
