import threading

import pytest
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


def test_invalid_frontend_flows_render_inline_feedback(ui_server):
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Playwright browser not installed")
            raise
        page = browser.new_page()

        page.goto(ui_server + "/")
        page.wait_for_selector("#searchMeta")
        assert "Selecione um DB para buscar." in (page.locator("#searchMeta").text_content() or "")
        assert page.locator("#searchBtn").is_disabled()

        page.goto(ui_server + "/admin.html")
        page.wait_for_selector("#startIndex")
        page.locator("#startIndex").click()
        page.wait_for_function(
            "() => document.getElementById('indexMsg').textContent.includes('Selecione um DB primeiro.')"
        )
        assert "Selecione um DB primeiro." in (page.locator("#indexMsg").text_content() or "")

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

        browser.close()
