from pathlib import Path
import importlib.util

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "tools" / "encontrar_registro_em_bds.py"


def load_module():
    spec = importlib.util.spec_from_file_location("find_record_tool", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_busca_generica_encontra_coluna_candidata(tmp_path):
    module = load_module()
    db_path = tmp_path / "sample.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE people (
                id INTEGER,
                code VARCHAR,
                label VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO people VALUES
                (1, 'A10', 'foo'),
                (2, 'B20', 'bar')
            """
        )
    finally:
        conn.close()

    found, used_col, sample = module.buscar_generico_em_tabela(
        db_path,
        "duckdb",
        "people",
        "B20",
        ["id", "code"],
        False,
        True,
        ["code", "label"],
    )

    assert found is True
    assert used_col == "code"
    assert sample == {"code": "B20", "label": "bar"}


def test_busca_generica_com_try_all_cols_acha_coluna_fora_da_lista(tmp_path):
    module = load_module()
    db_path = tmp_path / "sample_try_all.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE events (
                code VARCHAR,
                descr VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO events VALUES
                ('X1', 'needle'),
                ('X2', 'other')
            """
        )
    finally:
        conn.close()

    found, used_col, sample = module.buscar_generico_em_tabela(
        db_path,
        "duckdb",
        "events",
        "needle",
        ["id"],
        True,
        True,
        ["descr"],
    )

    assert found is True
    assert used_col == "descr"
    assert sample == {"descr": "needle"}
