from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_min_compare_report.py"
_SPEC = spec_from_file_location("run_min_compare_report", _SCRIPT_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
mod = module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_main_uses_suggested_sources(monkeypatch, tmp_path, capsys):
    docs = tmp_path / "documentos"
    reports = docs / "reports"
    docs.mkdir(parents=True)
    reports.mkdir(parents=True)

    a = docs / "a.duckdb"
    b = docs / "b.duckdb"
    a.write_text("x", encoding="utf-8")
    b.write_text("y", encoding="utf-8")

    class Item:
        def __init__(self, path):
            self.path = path

    monkeypatch.setattr(mod, "list_candidate_files", lambda _d: [Item(a), Item(b)])
    monkeypatch.setattr(mod, "suggest_two_sources", lambda _i: (Item(a), Item(b)))

    def _fake_run(src_a, src_b, docs_dir, reports_dir):
        assert src_a == a
        assert src_b == b
        assert docs_dir == docs
        assert reports_dir == reports
        return {
            "html": reports / "latest_db_compare_report.html",
            "md": reports / "latest_db_compare_report.md",
            "txt": reports / "latest_db_compare_report.txt",
        }

    monkeypatch.setattr(mod, "run_compare_pipeline", _fake_run)

    rc = mod.main(["--docs-dir", str(docs), "--reports-dir", str(reports)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "minimal report generated" in out


def test_main_rejects_equal_inputs(tmp_path):
    docs = tmp_path / "documentos"
    docs.mkdir(parents=True)
    same = docs / "same.duckdb"
    same.write_text("x", encoding="utf-8")

    rc = mod.main(["--docs-dir", str(docs), "--db1", str(same), "--db2", str(same)])
    assert rc == 1
