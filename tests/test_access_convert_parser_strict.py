import types
import sys
import subprocess

import duckdb

import access_convert as conv


def _build_fake_module(parse_table_impl):
    class FakeParser:
        def __init__(self, _path):
            self.catalog = {"t_ok": object(), "t_bad": object()}

        def parse_table(self, table_name):
            return parse_table_impl(table_name)

    return types.SimpleNamespace(AccessParser=FakeParser)


def test_access_parser_strict_fails_on_skipped_table(tmp_path, monkeypatch):
    monkeypatch.delenv("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", raising=False)

    def parse_impl(table_name):
        if table_name == "t_bad":
            raise RuntimeError("forced parser failure")
        return {"id": [1], "name": ["ok"]}

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (_build_fake_module(parse_impl), None))

    out = tmp_path / "strict_fail.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is False
    assert msg == "Conversion failed in strict mode. See logs for details."


def test_access_parser_allow_skips_enables_partial_conversion(tmp_path, monkeypatch):
    monkeypatch.setenv("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", "1")

    def parse_impl(table_name):
        if table_name == "t_bad":
            raise RuntimeError("forced parser failure")
        return {"id": [1], "name": ["ok"]}

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (_build_fake_module(parse_impl), None))

    out = tmp_path / "allow_skips.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is True
    assert "converted via access-parser" in msg
    assert "skipped=1" in msg
    conn = duckdb.connect(str(out), read_only=True)
    try:
        names = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        assert "t_ok" in names
    finally:
        conn.close()


def test_access_parser_strict_fails_when_no_table_has_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", raising=False)

    def parse_impl(_table_name):
        return {}

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (_build_fake_module(parse_impl), None))

    out = tmp_path / "no_rows.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is False
    assert msg == "Conversion failed in strict mode. See logs for details."


def test_access_parser_no_data_errors_are_not_counted_as_skips(tmp_path, monkeypatch):
    monkeypatch.delenv("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", raising=False)

    def parse_impl(table_name):
        if table_name == "t_bad":
            raise RuntimeError("table t_bad has no data")
        return {"id": [1], "name": ["ok"]}

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (_build_fake_module(parse_impl), None))

    out = tmp_path / "no_data_ok.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is True
    assert "converted via access-parser" in msg
    assert "skipped" not in msg


def test_access_parser_complex_values_are_sanitized(tmp_path, monkeypatch):
    monkeypatch.delenv("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", raising=False)

    def parse_impl(_table_name):
        return {
            "id": [1],
            "meta": [{"a": 1, "b": [2, 3]}],
            "raw": [b"\x01\x02"],
        }

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (_build_fake_module(parse_impl), None))

    out = tmp_path / "complex_values.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is True
    assert "converted via access-parser" in msg
    conn = duckdb.connect(str(out), read_only=True)
    try:
        row = conn.execute('SELECT meta, raw FROM "t_ok"').fetchone()
    finally:
        conn.close()
    assert isinstance(row[0], str)
    assert '"a": 1' in row[0]
    assert row[1] == "0102"


def test_convert_access_to_duckdb_hides_backend_details_on_total_failure(tmp_path, monkeypatch):
    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "mdbtools unavailable"

    class _PyodbcFail:
        @staticmethod
        def connect(*_args, **_kwargs):
            raise RuntimeError("driver missing /tmp/secret-path")

    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (None, "parser import fail"))
    monkeypatch.setattr(conv.subprocess, "run", lambda *_a, **_k: _FakeProc())
    monkeypatch.setitem(sys.modules, "pyodbc", _PyodbcFail())
    monkeypatch.setitem(sys.modules, "pypyodbc", _PyodbcFail())

    out = tmp_path / "all_fail.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=False)

    assert ok is False
    assert msg == "All conversion methods failed. See logs for details."
    assert "secret-path" not in msg


def test_convert_access_to_duckdb_pyodbc_empty_tables_fail_strict(tmp_path, monkeypatch):
    class _FakeCursor:
        @staticmethod
        def tables():
            return [("x", "y", "T_EMPTY", "TABLE")]

    class _FakeConn:
        @staticmethod
        def cursor():
            return _FakeCursor()

        @staticmethod
        def close():
            return None

    class _PyodbcOk:
        @staticmethod
        def connect(*_args, **_kwargs):
            return _FakeConn()

    class _PyodbcFail:
        @staticmethod
        def connect(*_args, **_kwargs):
            raise RuntimeError("driver unavailable")

    monkeypatch.setattr(conv.pd, "read_sql_query", lambda *_a, **_k: [])
    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (None, "parser import fail"))
    monkeypatch.setitem(sys.modules, "pyodbc", _PyodbcOk())
    monkeypatch.setitem(sys.modules, "pypyodbc", _PyodbcFail())

    out = tmp_path / "pyodbc_empty.duckdb"
    ok, msg = conv.convert_access_to_duckdb("fake.accdb", str(out), prefer_odbc=True)

    assert ok is False
    assert msg == "Conversion failed in strict mode. See logs for details."


def test_ensure_clean_duckdb_falha_quando_saida_existente_nao_pode_ser_removida(tmp_path, monkeypatch):
    out = tmp_path / "locked.duckdb"
    out.write_bytes(b"old")

    def fail_remove(_path):
        raise PermissionError("locked")

    monkeypatch.setattr(conv.os, "remove", fail_remove)

    try:
        conv._ensure_clean_duckdb(str(out))
    except RuntimeError as exc:
        assert "could not clear existing duckdb output" in str(exc)
    else:
        raise AssertionError("_ensure_clean_duckdb deveria falhar")


def test_mdbtools_usa_timeout_para_evitar_limpo_indefinido(tmp_path, monkeypatch):
    calls = []

    class _PyodbcFail:
        @staticmethod
        def connect(*_args, **_kwargs):
            raise RuntimeError("driver unavailable")

    def fake_run(args, **kwargs):
        calls.append((args[0], kwargs.get("timeout")))
        raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))

    monkeypatch.setattr(conv.subprocess, "run", fake_run)
    monkeypatch.setattr(conv, "load_access_parser_module", lambda: (None, "parser import fail"))
    monkeypatch.setitem(sys.modules, "pyodbc", _PyodbcFail())
    monkeypatch.setitem(sys.modules, "pypyodbc", _PyodbcFail())

    ok, msg = conv.convert_access_to_duckdb(
        "fake.mdb",
        str(tmp_path / "timeout.duckdb"),
        prefer_odbc=False,
    )

    assert ok is False
    assert msg == "All conversion methods failed. See logs for details."
    assert calls == [("mdb-tables", conv.MDBTOOLS_TIMEOUT_SECONDS)]
