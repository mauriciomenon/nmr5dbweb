import interface.find_record_across_dbs as track


class FakeParser:
    def __init__(self, _path):
        self.catalog = {"RANGER_SOSTAT": {}}

    def parse_table(self, table):
        if table != "RANGER_SOSTAT":
            return {}
        return {
            "RTUNO": [1, 2],
            "PNTNO": [2304, 2305],
            "PNTNAM": ["aux unidad", "other"],
        }


class FakeAccessModule:
    AccessParser = FakeParser


def test_list_tables_access_fallback_para_access_parser(tmp_path, monkeypatch):
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access")
    monkeypatch.setattr(track, "pyodbc", None)
    monkeypatch.setattr(track, "load_access_parser_module", lambda: (FakeAccessModule, None))

    tables = track.list_tables_access(db_path)

    assert tables == ["RANGER_SOSTAT"]


def test_search_in_table_access_sem_odbc_usa_access_parser(tmp_path, monkeypatch):
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access")
    monkeypatch.setattr(track, "pyodbc", None)
    monkeypatch.setattr(track, "load_access_parser_module", lambda: (FakeAccessModule, None))

    found, sample, err = track.search_in_table(
        "access",
        db_path,
        "RANGER_SOSTAT",
        [("RTUNO", 1), ("PNTNO", 2304)],
    )

    assert err is None
    assert found is True
    assert sample is not None
    assert sample["RTUNO"] == 1
    assert sample["PNTNO"] == 2304
    assert sample["PNTNAM"] == "aux unidad"


def test_search_in_table_access_fallback_quando_odbc_falha(tmp_path, monkeypatch):
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access")
    monkeypatch.setattr(track, "pyodbc", object())
    monkeypatch.setattr(track, "connect_access", lambda _path: (_ for _ in ()).throw(RuntimeError("odbc fail")))
    monkeypatch.setattr(track, "load_access_parser_module", lambda: (FakeAccessModule, None))

    found, sample, err = track.search_in_table(
        "access",
        db_path,
        "RANGER_SOSTAT",
        [("RTUNO", 1), ("PNTNO", 2304)],
    )

    assert err is None
    assert found is True
    assert sample is not None
    assert sample["RTUNO"] == 1


def test_search_in_table_access_sem_odbc_nao_lista_colunas(tmp_path, monkeypatch):
    db_path = tmp_path / "sample.accdb"
    db_path.write_bytes(b"access")
    monkeypatch.setattr(track, "pyodbc", None)
    monkeypatch.setattr(track, "load_access_parser_module", lambda: (FakeAccessModule, None))
    monkeypatch.setattr(
        track,
        "list_columns_for_engine",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("nao deveria listar colunas")),
    )

    found, sample, err = track.search_in_table(
        "access",
        db_path,
        "RANGER_SOSTAT",
        [("RTUNO", 1), ("PNTNO", 2304)],
    )

    assert err is None
    assert found is True
    assert sample is not None
    assert sample["RTUNO"] == 1
