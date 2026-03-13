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


def test_admin_upload_accdb_rejeita_quando_precheck_falha(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", lambda _path: None)
    monkeypatch.setattr(local_search, "convert_access_to_duckdb", lambda *_args, **_kwargs: (True, "ok"))
    monkeypatch.setattr(
        local_search,
        "evaluate_access_conversion_support",
        lambda _ext: {
            "ready": False,
            "reason": "pyodbc missing",
            "converter_available": True,
            "odbc": {
                "pyodbc_available": False,
                "access_driver_available": False,
                "drivers": [],
                "error": "pyodbc not installed",
                "platform": "nt",
            },
            "mdbtools_available": False,
        },
    )

    resp = client.post(
        "/admin/upload",
        data={"file": (BytesIO(b"accdb"), "sample.accdb")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["error"] == "Conversao Access indisponivel neste ambiente"
    assert payload["reason"] == "pyodbc missing"
    assert payload["precheck"]["ready"] is False
    assert list(tmp_path.iterdir()) == []


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
    assert payload["current_db_exists"] is True


def test_admin_access_precheck_retorna_relatorio(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(
        local_search,
        "evaluate_access_conversion_support",
        lambda ext: {
            "ready": ext == ".mdb",
            "reason": "" if ext == ".mdb" else "Access ODBC driver missing",
            "converter_available": True,
            "odbc": {
                "pyodbc_available": True,
                "access_driver_available": ext == ".mdb",
                "drivers": ["Microsoft Access Driver (*.mdb, *.accdb)"],
                "error": "",
                "platform": "nt",
            },
            "mdbtools_available": False,
        },
    )

    resp = client.get("/admin/access_precheck?ext=.accdb")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["ext"] == ".accdb"
    assert payload["precheck"]["ready"] is False
    assert payload["precheck"]["reason"] == "Access ODBC driver missing"


def test_evaluate_access_support_accdb_liberado_com_access_parser(monkeypatch):
    monkeypatch.setattr(local_search, "convert_access_to_duckdb", object())
    monkeypatch.setattr(local_search, "has_mdbtools_binaries", lambda: False)
    monkeypatch.setattr(local_search, "has_access_parser_module", lambda: True)
    monkeypatch.setattr(
        local_search,
        "get_access_odbc_status",
        lambda: {
            "platform": "posix",
            "pyodbc_available": False,
            "access_driver_available": False,
            "drivers": [],
            "error": "pyodbc not installed",
        },
    )

    precheck = local_search.evaluate_access_conversion_support(".accdb")

    assert precheck["ready"] is True
    assert precheck["reason"] == ""
    assert precheck["access_parser_available"] is True


def test_admin_list_uploads_indica_db_inexistente(tmp_path, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(tmp_path / "missing.sqlite3"))

    resp = client.get("/admin/list_uploads")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["current_db"] == str(tmp_path / "missing.sqlite3")
    assert payload["current_db_exists"] is False


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
    monkeypatch.setitem(local_search.cfg, "db_path", "/tmp/persisted.duckdb")

    resp = client.get("/admin/status")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["persisted_db"] == "/tmp/persisted.duckdb"
    assert payload["startup_warnings"] == ["db_path configurado nao existe mais: /tmp/lost.duckdb"]
    assert payload["capabilities"]["duckdb_fulltext"] in {True, False}
    assert payload["capabilities"]["access_conversion"] in {True, False}
    assert payload["capabilities"]["access_fallback"] in {True, False}
    assert payload["capabilities"]["access_parser_available"] in {True, False}
    assert payload["conversion_backend_preferred"] in {
        "odbc",
        "access_parser",
        "mdbtools",
        "unavailable",
    }
    assert isinstance(payload["conversion_backend_last"], str)
    assert isinstance(payload["indexer_available"], bool)
    if payload["indexer_available"]:
        assert payload["indexer_error"] == ""
    else:
        assert isinstance(payload["indexer_error"], str)


def test_client_log_e_admin_logs_expoem_count(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(local_search, "_CLIENT_LOGS", [])
    monkeypatch.setattr(local_search, "_SERVER_LOGS", [])

    resp = client.post("/client/log", json={"level": "warn", "msg": "algo aconteceu"})

    assert resp.status_code == 200
    logs_resp = client.get("/admin/logs")
    assert logs_resp.status_code == 200
    payload = logs_resp.get_json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["logs"][0]["message"] == "algo aconteceu"


def test_admin_set_auto_index_persiste_valor(monkeypatch):
    client = app.test_client()
    saved = []
    monkeypatch.setattr(local_search, "save_config", lambda data: saved.append(dict(data)))

    resp = client.post("/admin/set_auto_index", json={"enabled": True})

    assert resp.status_code == 200
    assert resp.get_json()["auto_index_after_convert"] is True
    assert local_search.cfg["auto_index_after_convert"] is True
    assert saved[-1]["auto_index_after_convert"] is True


def test_admin_set_auto_index_aceita_false_como_texto(monkeypatch):
    client = app.test_client()
    saved = []
    monkeypatch.setattr(local_search, "save_config", lambda data: saved.append(dict(data)))

    resp = client.post("/admin/set_auto_index", json={"enabled": "false"})

    assert resp.status_code == 200
    assert resp.get_json()["auto_index_after_convert"] is False
    assert local_search.cfg["auto_index_after_convert"] is False
    assert saved[-1]["auto_index_after_convert"] is False


def test_admin_set_auto_index_rejeita_valor_invalido(monkeypatch):
    client = app.test_client()

    resp = client.post("/admin/set_auto_index", json={"enabled": "talvez"})

    assert resp.status_code == 400
    assert "booleano valido" in resp.get_json()["error"]


def test_admin_set_auto_index_rejeita_campo_obrigatorio(monkeypatch):
    client = app.test_client()

    resp = client.post("/admin/set_auto_index", json={})

    assert resp.status_code == 400
    assert "obrigatorio" in resp.get_json()["error"]


def test_admin_set_priority_normaliza_lista(monkeypatch):
    client = app.test_client()
    saved = []
    monkeypatch.setattr(local_search, "save_config", lambda data: saved.append(dict(data)))

    resp = client.post("/admin/set_priority", json={"tables": [" alpha ", "", "beta"]})

    assert resp.status_code == 200
    assert resp.get_json()["priority_tables"] == ["alpha", "beta"]
    assert local_search.cfg["priority_tables"] == ["alpha", "beta"]
    assert saved[-1]["priority_tables"] == ["alpha", "beta"]


def test_admin_set_priority_rejeita_payload_invalido():
    client = app.test_client()

    resp = client.post("/admin/set_priority", json={"tables": None})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "tables param required"


def test_api_record_dirs_lista_apenas_existentes(tmp_path, monkeypatch):
    client = app.test_client()
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"
    monkeypatch.setattr(
        local_search,
        "RECORD_DIRS",
        {
            "ok": {"label": "OK", "path": existing},
            "gone": {"label": "Gone", "path": missing},
        },
    )

    resp = client.get("/api/record_dirs")

    assert resp.status_code == 200
    assert resp.get_json()["dirs"] == [{
        "id": "ok",
        "label": "OK",
        "path": str(existing.resolve()),
        "has_db": False,
    }]


def test_api_record_dirs_lista_com_status_has_db(tmp_path, monkeypatch):
    client = app.test_client()
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "sample.sqlite3").write_bytes(b"SQLite format 3\x00")
    monkeypatch.setattr(
        local_search,
        "RECORD_DIRS",
        {
            "ok": {"label": "OK", "path": existing},
        },
    )

    resp = client.get("/api/record_dirs")

    assert resp.status_code == 200
    assert resp.get_json()["dirs"] == [{
        "id": "ok",
        "label": "OK",
        "path": str(existing.resolve()),
        "has_db": True,
    }]


def test_api_browse_dirs_rejeita_diretorio_invalido(tmp_path):
    client = app.test_client()

    resp = client.get(f"/api/browse_dirs?path={tmp_path / 'missing'}")

    assert resp.status_code == 400
    assert "diretorio invalido" in resp.get_json()["error"]


def test_api_browse_dirs_rejeita_path_malformado():
    client = app.test_client()

    resp = client.get("/api/browse_dirs?path=%00")

    assert resp.status_code == 400
    assert "caractere invalido" in resp.get_json()["error"]


def test_api_browse_dirs_lista_subdiretorios_e_has_db(tmp_path):
    client = app.test_client()
    with_db = tmp_path / "with_db"
    with_db.mkdir()
    (with_db / "sample.sqlite3").write_bytes(b"SQLite format 3\x00")
    empty = tmp_path / "empty"
    empty.mkdir()

    resp = client.get(f"/api/browse_dirs?path={tmp_path}")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["path"] == str(tmp_path)
    by_name = {entry["name"]: entry for entry in payload["entries"]}
    assert by_name["with_db"]["has_db"] is True
    assert by_name["empty"]["has_db"] is False


def test_api_tables_rejeita_db_ativo_ausente(tmp_path, monkeypatch):
    client = app.test_client()
    missing = tmp_path / "missing.duckdb"
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(missing))

    resp = client.get("/api/tables")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == f"DB ativo nao encontrado: {missing}"


def test_api_tables_rejeita_access_para_browse(tmp_path, monkeypatch):
    client = app.test_client()
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(access_path))

    resp = client.get("/api/tables")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Engine nao suportada para esta operacao: access"


def test_api_tables_access_resolve_para_duckdb_derivado(tmp_path, monkeypatch):
    client = app.test_client()
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access")
    duck_path = tmp_path / "sample.duckdb"
    conn = duckdb.connect(str(duck_path))
    conn.execute("CREATE TABLE resolved_table (id INTEGER)")
    conn.close()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(access_path))

    resp = client.get("/api/tables")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["db_engine"] == "duckdb"
    assert payload["tables"] == ["resolved_table"]


def test_api_search_rejeita_db_ativo_ausente(tmp_path, monkeypatch):
    client = app.test_client()
    missing = tmp_path / "missing.duckdb"
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(missing))

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == f"DB ativo nao encontrado: {missing}"


def test_api_find_record_across_dbs_rejeita_max_files_invalido(tmp_path):
    client = app.test_client()

    resp = client.post(
        "/api/find_record_across_dbs",
        json={"custom_path": str(tmp_path), "filters": "RTUNO=1", "max_files": "bad"},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "max_files deve ser inteiro"


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


def test_api_table_ler_tabela_duckdb(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute('CREATE TABLE "event log" (id INTEGER, note VARCHAR)')
    conn.executemany(
        'INSERT INTO "event log" VALUES (?, ?)',
        [(1, "alpha"), (2, "beta"), (3, "alphabet")],
    )
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
    assert payload["search_backend"] == "sqlite_scan"
    assert payload["results"]["alpha"][0]["row"]["name"] == "alpha unit"


def test_api_search_busca_textual_duckdb_prioriza_tabela(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        "CREATE TABLE _fulltext (table_name VARCHAR, pk_col VARCHAR, pk_value VARCHAR, row_offset BIGINT, content_norm VARCHAR, row_json VARCHAR)"
    )
    conn.executemany(
        "INSERT INTO _fulltext VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("zeta", "id", "1", 0, "alpha result", '{"id": 1, "name": "zeta row"}'),
            ("alpha", "id", "2", 0, "alpha result", '{"id": 2, "name": "alpha row"}'),
        ],
    )
    conn.close()
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))
    monkeypatch.setitem(local_search.cfg, "priority_tables", ["alpha"])

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["search_backend"] == "duckdb_fulltext"
    assert list(payload["results"].keys())[0] == "alpha"


def test_api_search_access_driver_error_retorna_503(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))
    monkeypatch.setattr(
        local_search,
        "fallback_search_access",
        lambda *_args, **_kwargs: {"error": "pyodbc not installed; fallback unavailable"},
    )

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 503
    payload = resp.get_json()
    assert "pyodbc not installed" in payload["error"]
    assert "Convert to DuckDB first" in payload["hint"]


def test_api_search_access_com_duckdb_derivado_usa_duckdb(tmp_path, monkeypatch):
    client = app.test_client()
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access-placeholder")
    duck_path = tmp_path / "sample.duckdb"
    conn = duckdb.connect(str(duck_path))
    conn.execute(
        "CREATE TABLE _fulltext (table_name VARCHAR, pk_col VARCHAR, pk_value VARCHAR, row_offset BIGINT, content_norm VARCHAR, row_json VARCHAR)"
    )
    conn.execute(
        "INSERT INTO _fulltext VALUES ('alpha', 'id', '1', 0, 'alpha result', '{\"id\": 1, \"name\": \"alpha row\"}')"
    )
    conn.close()
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(access_path))

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("fallback_search_access nao deveria ser chamado")

    monkeypatch.setattr(local_search, "fallback_search_access", should_not_run)

    resp = client.get("/api/search?q=alpha")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["returned_count"] == 1
    assert payload["results"]["alpha"][0]["row"]["name"] == "alpha row"


def test_api_search_access_encaminha_filtro_tables(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    captured = {}

    def fake_access_search(
        _db_path,
        _q,
        per_table=10,
        candidate_limit=1000,
        total_limit=500,
        token_mode="any",
        min_score=None,
        tables=None,
        **_kwargs,
    ):
        captured["tables"] = tables
        return {
            "q": _q,
            "q_norm": _q,
            "candidate_count": 0,
            "returned_count": 0,
            "results": {},
        }

    monkeypatch.setattr(local_search, "fallback_search_access", fake_access_search)

    resp = client.get("/api/search?q=alpha&tables=t1,t2")

    assert resp.status_code == 200
    assert captured["tables"] == ["t1", "t2"]


def test_api_search_access_sem_odbc_usa_parser(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))
    monkeypatch.setattr(local_search, "pyodbc", None)

    class FakeParser:
        def __init__(self, _path):
            self.catalog = {"t1": {}, "t2": {}}

        def parse_table(self, table):
            if table == "t1":
                return {"id": [1], "text": ["foo needle"]}
            if table == "t2":
                return {"id": [2], "text": ["needle bar"]}
            return {}

    class FakeModule:
        AccessParser = FakeParser

    monkeypatch.setattr(local_search, "load_access_parser_module", lambda: (FakeModule, None))

    resp = client.get("/api/search?q=needle&tables=t2")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["search_backend"] == "access_parser"
    assert payload["returned_count"] == 1
    assert list(payload["results"].keys()) == ["t2"]
    assert payload["results"]["t2"][0]["row"]["id"] == 2


def test_api_search_access_odbc_falha_usa_parser(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    class FakePyodbc:
        @staticmethod
        def connect(*_args, **_kwargs):
            raise RuntimeError("odbc connect failed")

    class FakeParser:
        def __init__(self, _path):
            self.catalog = {"t1": {}}

        def parse_table(self, table):
            if table == "t1":
                return {"id": [1], "text": ["needle data"]}
            return {}

    class FakeModule:
        AccessParser = FakeParser

    monkeypatch.setattr(local_search, "pyodbc", FakePyodbc)
    monkeypatch.setattr(local_search, "load_access_parser_module", lambda: (FakeModule, None))

    resp = client.get("/api/search?q=needle")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["search_backend"] == "access_parser"
    assert payload["returned_count"] == 1
    assert list(payload["results"].keys()) == ["t1"]
    assert payload["results"]["t1"][0]["row"]["id"] == 1


def test_api_search_access_odbc_ok_marca_backend(tmp_path, monkeypatch):
    client = app.test_client()
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "get_db_path", lambda: str(db_path))

    class FakeTableRow:
        table_name = "t1"

    class FakeColumnRow:
        def __init__(self, name, type_name="TEXT"):
            self.column_name = name
            self.type_name = type_name

    class FakeCursor:
        def __init__(self):
            self.description = [("id",), ("text",)]
            self._rows = []

        def tables(self):
            return [FakeTableRow()]

        def columns(self, table=None):
            if table == "t1":
                return [FakeColumnRow("id"), FakeColumnRow("text")]
            return []

        def execute(self, sql, _params=None):
            if "SELECT TOP" in sql and "[t1]" in sql:
                self.description = [("id",), ("text",)]
                self._rows = [(1, "needle data"), (2, "other value")]
            else:
                self._rows = []
            return self

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self):
            self._cursor = FakeCursor()

        def cursor(self):
            return self._cursor

        def close(self):
            return None

    class FakePyodbc:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FakeConn()

    monkeypatch.setattr(local_search, "pyodbc", FakePyodbc)

    resp = client.get("/api/search?q=needle&tables=t1")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["search_backend"] == "access_odbc"
    assert payload["returned_count"] >= 1
    assert list(payload["results"].keys()) == ["t1"]
    assert any(item["row"]["id"] == 1 for item in payload["results"]["t1"])


def test_admin_select_access_resolve_para_duckdb_derivado(tmp_path, monkeypatch):
    client = app.test_client()
    selected = []
    access_path = tmp_path / "sample.accdb"
    duck_path = tmp_path / "sample.duckdb"
    access_path.write_bytes(b"access-placeholder")
    duck_path.write_bytes(b"duck-placeholder")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", selected.append)

    resp = client.post("/admin/select", json={"filename": "sample.accdb"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["db_path"] == str(duck_path.resolve())
    assert payload["selected_path"] == str(access_path)
    assert payload["resolved_from_access"] is True
    assert selected == [str(duck_path.resolve())]


def test_admin_select_access_sem_derivado_inicia_conversao(tmp_path, monkeypatch):
    client = app.test_client()
    selected = []
    started = {}
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "set_db_path", selected.append)
    monkeypatch.setattr(local_search, "convert_access_to_duckdb", object())
    monkeypatch.setattr(
        local_search,
        "evaluate_access_conversion_support",
        lambda _ext: {"ready": True, "reason": "", "odbc": {}, "access_parser_available": True},
    )
    monkeypatch.setattr(
        local_search,
        "start_access_conversion",
        lambda src, out, _converter: started.update({"src": str(src), "out": str(out)}),
    )
    monkeypatch.setitem(local_search.convert_status, "running", False)

    resp = client.post("/admin/select", json={"filename": "sample.accdb"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["status"] == "converting"
    assert payload["input"] == str(access_path)
    assert payload["output"] == str(tmp_path / "sample.duckdb")
    assert payload["resolved_from_access"] is False
    assert started == {"src": str(access_path), "out": str(tmp_path / "sample.duckdb")}
    assert selected == []


def test_admin_select_access_sem_derivado_rejeita_quando_precheck_falha(tmp_path, monkeypatch):
    client = app.test_client()
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        local_search,
        "evaluate_access_conversion_support",
        lambda _ext: {
            "ready": False,
            "reason": "need pyodbc+Access ODBC or access-parser for .accdb",
            "odbc": {"pyodbc_available": False, "access_driver_available": False},
            "access_parser_available": False,
        },
    )

    resp = client.post("/admin/select", json={"filename": "sample.accdb"})

    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["error"] == "Conversao Access indisponivel neste ambiente"
    assert payload["reason"] == "need pyodbc+Access ODBC or access-parser for .accdb"
    assert payload["precheck"]["ready"] is False


def test_admin_select_access_sem_derivado_rejeita_conversao_em_execucao(tmp_path, monkeypatch):
    client = app.test_client()
    access_path = tmp_path / "sample.accdb"
    access_path.write_bytes(b"access-placeholder")
    monkeypatch.setattr(local_search, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(local_search, "convert_access_to_duckdb", object())
    monkeypatch.setattr(
        local_search,
        "evaluate_access_conversion_support",
        lambda _ext: {"ready": True, "reason": "", "odbc": {}, "access_parser_available": True},
    )
    monkeypatch.setitem(local_search.convert_status, "running", True)

    resp = client.post("/admin/select", json={"filename": "sample.accdb"})

    assert resp.status_code == 409
    assert resp.get_json()["error"] == "Já existe uma conversão em execução"


def test_start_access_conversion_repassa_prefer_odbc_false(tmp_path, monkeypatch):
    source = tmp_path / "sample.accdb"
    output = tmp_path / "sample.duckdb"
    source.write_bytes(b"access")
    calls = {}

    class FakeThread:
        def __init__(self, target=None, daemon=False):
            self.target = target
            self.daemon = daemon

        def is_alive(self):
            return False

        def start(self):
            if self.target is not None:
                self.target()

    monkeypatch.setattr(local_search.threading, "Thread", FakeThread)
    monkeypatch.setattr(local_search, "should_prefer_odbc_for_conversion", lambda: False)
    monkeypatch.setattr(local_search, "set_db_path", lambda p: calls.setdefault("db_path", p))
    monkeypatch.setattr(local_search, "maybe_start_auto_index", lambda p: calls.setdefault("index_path", str(p)))
    monkeypatch.setattr(
        local_search,
        "convert_status",
        {
            "running": False,
            "ok": None,
            "msg": "",
            "input": "",
            "output": "",
            "total_tables": 0,
            "processed_tables": 0,
            "current_table": "",
            "percent": 0,
        },
    )

    def fake_converter(src, dst, chunk_size=0, progress_callback=None, prefer_odbc=None):
        calls["src"] = src
        calls["dst"] = dst
        calls["chunk_size"] = chunk_size
        calls["prefer_odbc"] = prefer_odbc
        return True, "converted via access-parser"

    local_search.start_access_conversion(source, output, fake_converter)

    assert calls["src"] == str(source)
    assert calls["dst"] == str(output)
    assert calls["chunk_size"] == 20000
    assert calls["prefer_odbc"] is False
    assert calls["db_path"] == str(output)
    assert calls["index_path"] == str(output)


def test_start_access_conversion_repassa_prefer_odbc_true(tmp_path, monkeypatch):
    source = tmp_path / "sample.accdb"
    output = tmp_path / "sample.duckdb"
    source.write_bytes(b"access")
    calls = {}

    class FakeThread:
        def __init__(self, target=None, daemon=False):
            self.target = target
            self.daemon = daemon

        def is_alive(self):
            return False

        def start(self):
            if self.target is not None:
                self.target()

    monkeypatch.setattr(local_search.threading, "Thread", FakeThread)
    monkeypatch.setattr(local_search, "should_prefer_odbc_for_conversion", lambda: True)
    monkeypatch.setattr(local_search, "set_db_path", lambda p: calls.setdefault("db_path", p))
    monkeypatch.setattr(local_search, "maybe_start_auto_index", lambda p: calls.setdefault("index_path", str(p)))
    monkeypatch.setattr(
        local_search,
        "convert_status",
        {
            "running": False,
            "ok": None,
            "msg": "",
            "input": "",
            "output": "",
            "total_tables": 0,
            "processed_tables": 0,
            "current_table": "",
            "percent": 0,
        },
    )

    def fake_converter(src, dst, chunk_size=0, progress_callback=None, prefer_odbc=None):
        calls["src"] = src
        calls["dst"] = dst
        calls["chunk_size"] = chunk_size
        calls["prefer_odbc"] = prefer_odbc
        return True, "converted via pyodbc"

    local_search.start_access_conversion(source, output, fake_converter)

    assert calls["src"] == str(source)
    assert calls["dst"] == str(output)
    assert calls["chunk_size"] == 20000
    assert calls["prefer_odbc"] is True
    assert calls["db_path"] == str(output)
    assert calls["index_path"] == str(output)


def test_api_search_duckdb_usa_db_path_recebido(tmp_path, monkeypatch):
    active_db = tmp_path / "active.duckdb"
    route_db = tmp_path / "route.duckdb"

    for db_path, table_name in ((active_db, "wrong_table"), (route_db, "right_table")):
        conn = duckdb.connect(str(db_path))
        conn.execute(
            "CREATE TABLE _fulltext (table_name VARCHAR, pk_col VARCHAR, pk_value VARCHAR, row_offset BIGINT, content_norm VARCHAR, row_json VARCHAR)"
        )
        conn.execute(
            "INSERT INTO _fulltext VALUES (?, ?, ?, ?, ?, ?)",
            [table_name, "id", "1", 0, "alpha result", '{"id": 1, "name": "alpha row"}'],
        )
        conn.close()

    monkeypatch.setattr(local_search, "get_db_path", lambda: str(active_db))
    monkeypatch.setitem(local_search.cfg, "priority_tables", [])

    payload = local_search.api_search_duckdb(
        str(route_db), "alpha", 10, 1000, 500, "any", None
    )

    assert list(payload["results"].keys()) == ["right_table"]


def test_api_find_record_across_dbs_sucesso_sqlite(tmp_path):
    client = app.test_client()
    track_dir = tmp_path / "track"
    track_dir.mkdir()
    db_path = track_dir / "sample.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE RANGER_SOSTAT (RTUNO INTEGER, PNTNO INTEGER, PNTNAM TEXT)")
    conn.execute("INSERT INTO RANGER_SOSTAT VALUES (1, 2304, 'aux unidad')")
    conn.commit()
    conn.close()

    resp = client.post(
        "/api/find_record_across_dbs",
        json={"custom_path": str(track_dir), "filters": "RTUNO=1,PNTNO=2304", "max_files": 10},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["total_files"] == 1
    assert payload["results"][0]["found"] is True
    assert payload["results"][0]["table"] == "RANGER_SOSTAT"


def test_api_compare_db_tables_rejeita_arquivo_ausente(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "missing_a.duckdb"
    db2 = tmp_path / "missing_b.duckdb"

    resp = client.post("/api/compare_db_tables", json={"db1_path": str(db1), "db2_path": str(db2)})

    assert resp.status_code == 400
    assert "arquivo(s) não encontrado(s)" in resp.get_json()["error"]


def test_api_compare_db_table_content_rejeita_arquivo_ausente(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "missing_a.duckdb"
    db2 = tmp_path / "missing_b.duckdb"

    resp = client.post(
        "/api/compare_db_table_content",
        json={"db1_path": str(db1), "db2_path": str(db2), "table": "alpha"},
    )

    assert resp.status_code == 400
    assert "arquivo(s) não encontrado(s)" in resp.get_json()["error"]


def test_api_compare_db_overview_sucesso(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "a.duckdb"
    db2 = tmp_path / "b.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn1.execute("CREATE TABLE items(id INTEGER, valor TEXT)")
    conn1.execute("INSERT INTO items VALUES (1, 'x'), (2, 'y')")
    conn1.close()

    conn2 = duckdb.connect(str(db2))
    conn2.execute("CREATE TABLE items(id INTEGER, valor TEXT)")
    conn2.execute("INSERT INTO items VALUES (1, 'x'), (2, 'z')")
    conn2.close()

    resp = client.post(
        "/api/compare_db_overview",
        json={"db1_path": str(db1), "db2_path": str(db2), "tables": ["items"]},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["overview"]
    assert payload["summary"]["total_tables"] == 1
    assert payload["summary"]["diff_tables"] == 1
    assert payload["summary"]["same_tables"] == 0
    assert payload["summary"]["error_tables"] == 0
    assert payload["summary"]["no_key_tables"] == 0
    row = payload["overview"][0]
    assert row["table"] == "items"
    assert row["status"] == "diff"
    assert row["diff_count"] >= 1
    assert row["row_count_a"] == 2
    assert row["row_count_b"] == 2


def test_api_compare_db_overview_rejeita_tables_invalido(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "a.duckdb"
    db2 = tmp_path / "b.duckdb"
    duckdb.connect(str(db1)).close()
    duckdb.connect(str(db2)).close()

    resp = client.post(
        "/api/compare_db_overview",
        json={"db1_path": str(db1), "db2_path": str(db2), "tables": "items"},
    )

    assert resp.status_code == 400
    assert "tables deve ser uma lista" in resp.get_json()["error"]


def test_api_compare_db_overview_rejeita_tables_com_item_nao_string(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "a.duckdb"
    db2 = tmp_path / "b.duckdb"
    duckdb.connect(str(db1)).close()
    duckdb.connect(str(db2)).close()

    resp = client.post(
        "/api/compare_db_overview",
        json={"db1_path": str(db1), "db2_path": str(db2), "tables": ["items", 123]},
    )

    assert resp.status_code == 400
    assert "tables deve conter apenas strings" in resp.get_json()["error"]


def test_api_compare_db_overview_deduplica_lista_de_tabelas(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "a.duckdb"
    db2 = tmp_path / "b.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE items(id INTEGER, valor TEXT)")
        conn2.execute("CREATE TABLE items(id INTEGER, valor TEXT)")
        conn1.execute("INSERT INTO items VALUES (1, 'x')")
        conn2.execute("INSERT INTO items VALUES (1, 'x')")
    finally:
        conn1.close()
        conn2.close()

    resp = client.post(
        "/api/compare_db_overview",
        json={
            "db1_path": str(db1),
            "db2_path": str(db2),
            "tables": ["items", "items", "  items  ", ""],
        },
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["overview"]) == 1
    assert payload["summary"]["total_tables"] == 1
    assert payload["summary"]["same_tables"] == 1
    assert payload["summary"]["diff_tables"] == 0


def test_api_compare_db_rows_rejeita_engine_nao_duckdb(tmp_path):
    client = app.test_client()
    db_sqlite = tmp_path / "a.sqlite3"
    db_duck = tmp_path / "b.duckdb"

    conn_sqlite = sqlite3.connect(db_sqlite)
    conn_sqlite.execute("CREATE TABLE T(id INTEGER, valor TEXT)")
    conn_sqlite.execute("INSERT INTO T VALUES (1, 'a')")
    conn_sqlite.commit()
    conn_sqlite.close()

    conn_duck = duckdb.connect(str(db_duck))
    conn_duck.execute("CREATE TABLE T(id INTEGER, valor TEXT)")
    conn_duck.execute("INSERT INTO T VALUES (1, 'a')")
    conn_duck.close()

    resp = client.post(
        "/api/compare_db_rows",
        json={
            "db1_path": str(db_sqlite),
            "db2_path": str(db_duck),
            "table": "T",
            "key_columns": ["id"],
            "compare_columns": ["valor"],
        },
    )

    assert resp.status_code == 400
    assert "engine nao suportada" in resp.get_json()["error"]


def test_api_compare_db_tables_rejeita_quando_path_nao_e_arquivo(tmp_path):
    client = app.test_client()
    db1_dir = tmp_path / "not_a_file"
    db1_dir.mkdir()
    db2 = tmp_path / "db2.duckdb"
    duckdb.connect(str(db2)).close()

    resp = client.post(
        "/api/compare_db_tables",
        json={"db1_path": str(db1_dir), "db2_path": str(db2)},
    )

    assert resp.status_code == 400
    assert "esperado arquivo" in resp.get_json()["error"]


def test_api_compare_db_tables_rejeita_mesmo_arquivo(tmp_path):
    client = app.test_client()
    db1 = tmp_path / "same.duckdb"
    duckdb.connect(str(db1)).close()

    resp = client.post(
        "/api/compare_db_tables",
        json={"db1_path": str(db1), "db2_path": str(db1)},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "db1_path e db2_path nao podem ser o mesmo arquivo"
