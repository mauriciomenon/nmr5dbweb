from io import BytesIO

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


def test_admin_start_index_sem_indexador_retorna_erro(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "create_or_resume_fulltext", None)

    resp = client.post("/admin/start_index", json={})

    assert resp.status_code == 500
    assert "indexador não disponível" in resp.get_json()["error"]


def test_admin_start_index_rejeita_chunk_invalido(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "create_or_resume_fulltext", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_search, "index_thread", None)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(tmp_path / "db.duckdb"))

    resp = client.post("/admin/start_index", json={"chunk": "x"})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "chunk/batch must be integers"


def test_api_search_rejeita_parametros_invalidos():
    client = app.test_client()

    resp = client.get("/api/search?q=test&per_table=abc")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "per_table/candidate_limit/total_limit must be integers"
