import duckdb
from pathlib import Path
import sys


# garante que o diretório raiz do projeto (onde fica a pasta "interface")
# esteja no sys.path mesmo quando os testes são executados a partir de locais diferentes
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.compare_dbs import compare_table_duckdb


def _make_db(path: Path, rows):
    """Cria um pequeno banco DuckDB com tabela T(id INT, valor TEXT)."""
    conn = duckdb.connect(str(path))
    try:
        conn.execute("CREATE TABLE T(id INTEGER, valor TEXT)")
        if rows:
            conn.executemany("INSERT INTO T(id, valor) VALUES (?, ?)", rows)
    finally:
        conn.close()


def test_compare_no_differences(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    data = [(1, "a"), (2, "b"), (3, "c")]
    _make_db(db1, data)
    _make_db(db2, data)

    result = compare_table_duckdb(db1, db2, "T", key_columns=["id"], compare_columns=["valor"])

    assert result["summary"]["rows_a"] == 3
    assert result["summary"]["rows_b"] == 3
    assert result["summary"]["keys_total"] == 3
    assert result["summary"]["changed_count"] == 0
    assert result["summary"]["added_count"] == 0
    assert result["summary"]["removed_count"] == 0
    assert result["row_count"] == 0


def test_compare_added_removed_changed(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    # id=1: igual; id=2: só em A (removed); id=3: só em B (added); id=4: mudou valor (changed)
    _make_db(db1, [(1, "a"), (2, "b"), (4, "x")])
    _make_db(db2, [(1, "a"), (3, "c"), (4, "y")])

    result = compare_table_duckdb(db1, db2, "T", key_columns=["id"], compare_columns=["valor"])

    summary = result["summary"]
    assert summary["rows_a"] == 3
    assert summary["rows_b"] == 3
    assert summary["keys_total"] == 4
    assert summary["added_count"] == 1
    assert summary["removed_count"] == 1
    assert summary["changed_count"] == 1
    assert summary["same_count"] == 1

    types = sorted(r["type"] for r in result["rows"])
    assert types == ["added", "changed", "removed"]


def test_compare_limit_applied_to_results_only(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    # 10 linhas diferentes para exercitar o LIMIT
    data1 = [(i, f"a-{i}") for i in range(10)]
    data2 = [(i, f"b-{i}") for i in range(10)]
    _make_db(db1, data1)
    _make_db(db2, data2)

    result = compare_table_duckdb(db1, db2, "T", key_columns=["id"], compare_columns=["valor"], limit=3)

    summary = result["summary"]
    # resumo continua olhando para a tabela inteira
    assert summary["rows_a"] == 10
    assert summary["rows_b"] == 10
    assert summary["keys_total"] == 10
    assert summary["changed_count"] == 10
    # mas os detalhes são limitados pelo parâmetro
    assert result["row_count"] == 3


def test_compare_with_composite_key(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE T(rtuno INTEGER, pntno INTEGER, valor TEXT)")
        conn2.execute("CREATE TABLE T(rtuno INTEGER, pntno INTEGER, valor TEXT)")
        # mesma chave (1, 10) igual
        conn1.execute("INSERT INTO T VALUES (1, 10, 'a')")
        conn2.execute("INSERT INTO T VALUES (1, 10, 'a')")
        # mesma chave (1, 20) mudou
        conn1.execute("INSERT INTO T VALUES (1, 20, 'x')")
        conn2.execute("INSERT INTO T VALUES (1, 20, 'y')")
        # chave (2, 10) só em A
        conn1.execute("INSERT INTO T VALUES (2, 10, 'foo')")
        # chave (3, 10) só em B
        conn2.execute("INSERT INTO T VALUES (3, 10, 'bar')")
    finally:
        conn1.close()
        conn2.close()

    result = compare_table_duckdb(
        db1,
        db2,
        "T",
        key_columns=["rtuno", "pntno"],
        compare_columns=["valor"],
    )

    summary = result["summary"]
    assert summary["keys_total"] == 4
    assert summary["added_count"] == 1
    assert summary["removed_count"] == 1
    assert summary["changed_count"] == 1
    assert summary["same_count"] == 1

    # garante que as chaves compostas estão sendo montadas corretamente
    keys = {tuple(r["key"].values()) for r in result["rows"]}
    assert (1, 10) not in keys
    assert (1, 20) in keys
    assert (2, 10) in keys
    assert (3, 10) in keys
