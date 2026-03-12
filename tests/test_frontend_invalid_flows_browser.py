import threading
from contextlib import contextmanager

import pytest
import duckdb
import sqlite3
from playwright.sync_api import sync_playwright
from playwright._impl._errors import Error as PlaywrightError
from werkzeug.serving import make_server

import interface.app_flask_local_search as local_search


app = local_search.app


class _ServerThread(threading.Thread):
    def __init__(self, host, port):
        super().__init__(daemon=True)
        self._server = make_server(host, port, app)
        self.host = host
        self.port = self._server.server_port

    def run(self):
        self._server.serve_forever()

    def stop(self):
        self._server.shutdown()
        self.join(timeout=5)


@pytest.fixture()
def ui_server(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setattr(local_search, "UPLOAD_DIR", upload_dir)
    monkeypatch.setitem(local_search.cfg, "db_path", "")
    monkeypatch.setitem(local_search.cfg, "priority_tables", [])
    monkeypatch.setitem(local_search.cfg, "auto_index_after_convert", True)
    monkeypatch.setattr(local_search, "index_thread", None)
    monkeypatch.setattr(local_search, "convert_thread", None)
    monkeypatch.setitem(local_search.runtime_state, "db_path", "")
    monkeypatch.setattr(local_search, "startup_warnings", [])
    monkeypatch.setitem(local_search.convert_status, "running", False)
    monkeypatch.setitem(local_search.convert_status, "ok", None)
    monkeypatch.setitem(local_search.convert_status, "msg", None)
    monkeypatch.setitem(local_search.convert_status, "input", None)
    monkeypatch.setitem(local_search.convert_status, "output", None)
    monkeypatch.setitem(local_search.convert_status, "total_tables", 0)
    monkeypatch.setitem(local_search.convert_status, "processed_tables", 0)
    monkeypatch.setitem(local_search.convert_status, "current_table", "")
    monkeypatch.setitem(local_search.convert_status, "percent", 0)

    server = _ServerThread("127.0.0.1", 0)
    server.start()
    try:
        yield f"http://{server.host}:{server.port}"
    finally:
        server.stop()


@pytest.fixture()
def sample_data(tmp_path, monkeypatch):
    search_db = tmp_path / "search.duckdb"
    conn = duckdb.connect(str(search_db))
    conn.execute(
        "CREATE TABLE _fulltext (table_name VARCHAR, pk_col VARCHAR, pk_value VARCHAR, row_offset BIGINT, content_norm VARCHAR, row_json VARCHAR)"
    )
    conn.execute(
        "INSERT INTO _fulltext VALUES (?, ?, ?, ?, ?, ?)",
        ["signals", "id", "1", 0, "alpha aux_unidad svp", '{"id": 1, "name": "alpha"}'],
    )
    conn.close()

    sqlite_search_db = tmp_path / "search.sqlite3"
    sqlite_search_conn = sqlite3.connect(sqlite_search_db)
    sqlite_search_conn.execute("CREATE TABLE signals (id INTEGER, name TEXT, note TEXT)")
    sqlite_search_conn.execute("INSERT INTO signals VALUES (1, 'alpha sqlite', 'aux unidad sqlite')")
    sqlite_search_conn.commit()
    sqlite_search_conn.close()

    db_a = tmp_path / "compare_a.duckdb"
    db_b = tmp_path / "compare_b.duckdb"
    for path, rows in (
        (db_a, [(1, "alpha"), (2, "beta-new"), (3, "gamma-new")]),
        (db_b, [(1, "alpha"), (2, "beta-old"), (3, "gamma-old"), (4, "delta-old")]),
    ):
        compare_conn = duckdb.connect(str(path))
        compare_conn.execute("CREATE TABLE items (id INTEGER, name VARCHAR)")
        compare_conn.executemany("INSERT INTO items VALUES (?, ?)", rows)
        compare_conn.close()

    track_dir = tmp_path / "track"
    track_dir.mkdir()
    track_db = track_dir / "sample.sqlite3"
    sqlite_conn = sqlite3.connect(track_db)
    sqlite_conn.execute("CREATE TABLE RANGER_SOSTAT (RTUNO INTEGER, PNTNO INTEGER, PNTNAM TEXT)")
    sqlite_conn.execute("INSERT INTO RANGER_SOSTAT VALUES (1, 2304, 'aux unidad')")
    sqlite_conn.commit()
    sqlite_conn.close()

    monkeypatch.setitem(local_search.runtime_state, "db_path", str(search_db))
    monkeypatch.setitem(local_search.cfg, "db_path", str(search_db))
    return {
        "search_db": search_db,
        "sqlite_search_db": sqlite_search_db,
        "db_a": db_a,
        "db_b": db_b,
        "track_dir": track_dir,
    }


@contextmanager
def with_browser():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Playwright browser not installed")
            raise
        browser_context = browser.new_context(accept_downloads=True)
        page = browser_context.new_page()
        try:
            yield browser, browser_context, page
        finally:
            browser_context.close()
            browser.close()


def test_invalid_frontend_flows_render_inline_feedback(ui_server):
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/")
        page.wait_for_selector("#searchMeta", state="attached")
        assert "Selecione um DB para buscar." in (page.locator("#searchMeta").text_content() or "")
        assert page.locator("#searchBtn").is_disabled()

        page.goto(ui_server + "/admin.html")
        page.wait_for_selector("#startIndex")
        page.locator("#startIndex").click()
        page.wait_for_function(
            "() => document.getElementById('indexMsg').textContent.includes('Selecione um DB ativo antes de iniciar a indexacao.')"
        )
        assert "Selecione um DB ativo antes de iniciar a indexacao." in (
            page.locator("#indexMsg").text_content() or ""
        )

        page.goto(ui_server + "/compare_dbs")
        page.wait_for_selector("#btnLoadTables")
        page.locator("#btnLoadTables").click()
        page.wait_for_function(
            "() => document.getElementById('statusMeta').textContent.includes('Informe os caminhos de ambos os bancos')"
        )
        assert "Informe os caminhos de ambos os bancos" in (page.locator("#statusMeta").text_content() or "")

        page.goto(ui_server + "/track_record")
        page.wait_for_selector("#runBtn")
        page.locator("#customDirInput").fill("")
        page.locator("#filtersInput").fill("")
        page.locator("#runBtn").click()
        page.wait_for_function(
            "() => document.getElementById('statusText').textContent.includes('Preencha os filtros antes de executar.')"
        )
        assert "Preencha os filtros antes de executar." in (page.locator("#statusText").text_content() or "")


def test_success_frontend_smoke_search_page(ui_server, sample_data):
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/")
        page.locator("#openSearchInlineMirror").click()
        page.wait_for_selector("#searchBtn")
        page.locator("#q").fill("alpha")
        page.locator("#searchBtn").click()
        page.wait_for_function(
            "() => (document.getElementById('searchMeta').textContent || '').includes('Resultados: 1')"
        )
        assert "signals" in (page.locator("#resultsArea").text_content() or "")

        page.goto(ui_server + "/admin.html")
        page.wait_for_selector("#statusBox")
        page.wait_for_function(
            "() => (document.getElementById('statusBox').textContent || '').includes('search.duckdb')"
        )


def test_success_frontend_smoke_search_page_sqlite(ui_server, sample_data):
    local_search.runtime_state["db_path"] = str(sample_data["sqlite_search_db"])
    local_search.cfg["db_path"] = str(sample_data["sqlite_search_db"])
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/")
        page.locator("#openSearchInlineMirror").click()
        page.wait_for_selector("#searchBtn")
        page.locator("#q").fill("alpha")
        page.locator("#searchBtn").click()
        page.wait_for_function(
            "() => (document.getElementById('searchMeta').textContent || '').includes('Resultados: 1')"
        )
        assert "alpha sqlite" in (page.locator("#resultsArea").text_content() or "")


def test_success_frontend_smoke_compare_page(ui_server, sample_data):
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/compare_dbs")
        page.wait_for_selector("#db1Path")
        page.locator("#db1Path").fill(str(sample_data["db_a"]))
        page.locator("#db2Path").fill(str(sample_data["db_b"]))
        page.locator("#btnLoadTables").click()
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('#tableSelect option')).some(o => o.value === 'items')"
        )
        page.locator("#keyColumns").fill("id")
        page.locator("#runCompareBtn").click()
        page.wait_for_function(
            "() => (document.getElementById('statusCompare').textContent || '').includes('Comparacao concluida.')"
        )
        assert "items" in (page.locator("#summary").text_content() or "")
        assert "beta-old" in (page.locator("#results").text_content() or "")
        assert "Pistas operacionais" in (page.locator("#summary").text_content() or "")


def test_success_frontend_smoke_compare_pagination_and_export(ui_server, sample_data):
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/compare_dbs")
        page.wait_for_selector("#db1Path")
        page.locator("#db1Path").fill(str(sample_data["db_a"]))
        page.locator("#db2Path").fill(str(sample_data["db_b"]))
        page.locator("#btnLoadTables").click()
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('#tableSelect option')).some(o => o.value === 'items')"
        )
        page.locator("#keyColumns").fill("id")
        page.locator("#rowLimit").fill("1")
        page.locator("#runCompareBtn").click()
        page.wait_for_function(
            "() => (document.getElementById('pagination').textContent || '').includes('pagina 1 de')"
        )
        with page.expect_download() as download_info:
            page.locator("#btnExportComparison").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".csv")
        assert "comparacao_items" in download.suggested_filename


def test_success_frontend_smoke_track_page(ui_server, sample_data):
    with with_browser() as (_browser, _browser_context, page):
        page.goto(ui_server + "/track_record")
        page.wait_for_selector("#runBtn")
        page.locator("#customDirInput").fill(str(sample_data["track_dir"]))
        page.locator("#filtersInput").fill("RTUNO=1,PNTNO=2304")
        page.locator("#runBtn").click()
        page.wait_for_function(
            "() => (document.getElementById('summary').textContent || '').includes('Encontrado em 1 arquivo')"
        )
        assert "sample.sqlite3" in (page.locator("#resultsTable").text_content() or "")
