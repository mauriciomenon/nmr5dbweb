import types

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
    assert "access-parser strict mode" in msg
    assert "skipped 1/" in msg


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
    assert "no tables converted" in msg
