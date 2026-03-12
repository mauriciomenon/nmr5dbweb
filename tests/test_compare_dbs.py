import duckdb
from pathlib import Path
import sys


# garante que o diretório raiz do projeto (onde fica a pasta "interface")
# esteja no sys.path mesmo quando os testes são executados a partir de locais diferentes
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.compare_dbs import compare_table_content_duckdb, compare_table_duckdb, compare_table_duckdb_paged  # noqa: E402


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


def test_compare_table_content_ignores_order(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a"), (2, "b"), (3, "c")])
    _make_db(db2, [(3, "c"), (1, "a"), (2, "b")])

    result = compare_table_content_duckdb(db1, db2, "T")

    assert result == {"table": "T", "row_count_a": 3, "row_count_b": 3, "diff_count": 0}


def test_compare_table_content_detects_distinct_rows(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a"), (2, "b"), (4, "x")])
    _make_db(db2, [(1, "a"), (3, "c"), (4, "y")])

    result = compare_table_content_duckdb(db1, db2, "T")

    assert result["row_count_a"] == 3
    assert result["row_count_b"] == 3
    assert result["diff_count"] == 4


def test_compare_table_content_ignores_duplicate_only_difference(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a"), (1, "a"), (2, "b")])
    _make_db(db2, [(1, "a"), (2, "b")])

    result = compare_table_content_duckdb(db1, db2, "T")

    assert result["row_count_a"] == 3
    assert result["row_count_b"] == 2
    assert result["diff_count"] == 0


def test_compare_table_content_without_common_columns_returns_minus_one(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE T(id INTEGER, valor TEXT)")
        conn2.execute("CREATE TABLE T(outro INTEGER, descricao TEXT)")
        conn1.execute("INSERT INTO T VALUES (1, 'a')")
        conn2.execute("INSERT INTO T VALUES (1, 'a')")
    finally:
        conn1.close()
        conn2.close()

    result = compare_table_content_duckdb(db1, db2, "T")

    assert result == {"table": "T", "row_count_a": 0, "row_count_b": 0, "diff_count": -1}


def test_compare_with_quoted_identifiers(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    table = 'T weird"name'
    key_col = 'key id'
    value_col = 'value-name'

    def q(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute(f"CREATE TABLE {q(table)} ({q(key_col)} INTEGER, {q(value_col)} TEXT)")
        conn2.execute(f"CREATE TABLE {q(table)} ({q(key_col)} INTEGER, {q(value_col)} TEXT)")
        conn1.execute(f"INSERT INTO {q(table)} VALUES (1, 'a'), (2, 'x')")
        conn2.execute(f"INSERT INTO {q(table)} VALUES (1, 'a'), (2, 'y')")
    finally:
        conn1.close()
        conn2.close()

    result = compare_table_duckdb(
        db1,
        db2,
        table,
        key_columns=[key_col],
        compare_columns=[value_col],
    )
    content_result = compare_table_content_duckdb(db1, db2, table)

    assert result["summary"]["changed_count"] == 1
    assert result["rows"][0]["key"][key_col] == 2
    assert result["rows"][0]["a"][value_col] == "x"
    assert result["rows"][0]["b"][value_col] == "y"
    assert content_result["diff_count"] == 2


def test_compare_table_duckdb_rejects_missing_key_column(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "a")])
    _make_db(db2, [(1, "a")])

    try:
        compare_table_duckdb(db1, db2, "T", key_columns=["nao_existe"], compare_columns=["valor"])
    except ValueError as exc:
        assert "key_columns ausentes" in str(exc)
    else:
        raise AssertionError("compare_table_duckdb deveria rejeitar key_columns ausentes")


def test_compare_table_duckdb_paged_filters_and_paginates(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"
    _make_db(db1, [(1, "x"), (2, "b"), (4, "z")])
    _make_db(db2, [(1, "y"), (3, "c"), (4, "z")])

    result = compare_table_duckdb_paged(
        db1,
        db2,
        "T",
        key_columns=["id"],
        compare_columns=["valor"],
        change_types=["changed", "removed", "added"],
        page=2,
        page_size=1,
    )

    assert result["summary"]["keys_total"] == 4
    assert result["summary"]["changed_count"] == 1
    assert result["summary"]["removed_count"] == 1
    assert result["summary"]["added_count"] == 1
    assert result["total_filtered_rows"] == 3
    assert result["total_pages"] == 3
    assert result["page"] == 2
    assert result["row_count"] == 1
    assert result["rows"][0]["key"]["id"] == 2
    assert result["rows"][0]["type"] == "removed"


def test_compare_table_duckdb_paged_changed_column_keeps_added_removed(tmp_path):
    db1 = tmp_path / "db1.duckdb"
    db2 = tmp_path / "db2.duckdb"

    conn1 = duckdb.connect(str(db1))
    conn2 = duckdb.connect(str(db2))
    try:
        conn1.execute("CREATE TABLE T(id INTEGER, v1 TEXT, v2 TEXT)")
        conn2.execute("CREATE TABLE T(id INTEGER, v1 TEXT, v2 TEXT)")
        conn1.execute("INSERT INTO T VALUES (1, 'a', 'x')")
        conn2.execute("INSERT INTO T VALUES (1, 'b', 'x')")
        conn1.execute("INSERT INTO T VALUES (2, 'c', 'y')")
        conn2.execute("INSERT INTO T VALUES (2, 'c', 'z')")
        conn2.execute("INSERT INTO T VALUES (3, 'n', 'm')")
    finally:
        conn1.close()
        conn2.close()

    result = compare_table_duckdb_paged(
        db1,
        db2,
        "T",
        key_columns=["id"],
        compare_columns=["v1", "v2"],
        changed_column="v1",
        page=1,
        page_size=10,
    )

    assert result["summary"]["changed_count"] == 2
    assert result["summary"]["added_count"] == 1
    assert result["total_filtered_rows"] == 2
    assert [row["key"]["id"] for row in result["rows"]] == [1, 3]
