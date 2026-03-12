#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ferramentas de comparação entre dois bancos DuckDB.

MVP: compara uma tabela por vez, assumindo que ambos os arquivos são
bancos DuckDB (.duckdb). Para outros formatos, a ideia é converter
antes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import duckdb


def _connect_memory() -> duckdb.DuckDBPyConnection:
    """Cria uma conexão DuckDB em memória."""
    return duckdb.connect()


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("identificador SQL invalido")
    return '"' + name.replace('"', '""') + '"'


def _qualify_identifier(alias: str, name: str) -> str:
    return f"{alias}.{_quote_identifier(name)}"


def _attach_db(
    conn: duckdb.DuckDBPyConnection,
    alias: str,
    path: Path,
    *,
    read_only: bool = False,
) -> None:
    suffix = " (READ_ONLY)" if read_only else ""
    conn.execute(f"ATTACH {_quote_sql_literal(path.as_posix())} AS {alias}{suffix}")


@dataclass(frozen=True)
class _KeyedComparePlan:
    db1: Path
    db2: Path
    table: str
    key_columns: list[str]
    compare_columns: list[str]
    table_a_sql: str
    table_b_sql: str
    join_condition: str
    diff_condition_sql: str
    select_cols: str


def _resolve_duckdb_compare_paths(db1: Path, db2: Path) -> tuple[Path, Path]:
    db1 = db1.resolve()
    db2 = db2.resolve()
    if not db1.exists():
        raise FileNotFoundError(db1)
    if not db2.exists():
        raise FileNotFoundError(db2)
    return db1, db2


def _resolve_common_table_columns(db1: Path, db2: Path, table: str) -> list[str]:
    cols_a = list_table_columns(db1, table)
    cols_b = list_table_columns(db2, table)
    missing_tables = []
    if not cols_a:
        missing_tables.append("db1")
    if not cols_b:
        missing_tables.append("db2")
    if missing_tables:
        raise ValueError(f"tabela '{table}' nao encontrada em: {', '.join(missing_tables)}")

    cols_b_set = set(cols_b)
    return [c for c in cols_a if c in cols_b_set]


def _resolve_keyed_compare_columns(
    common_columns: Sequence[str],
    key_columns: Sequence[str],
    compare_columns: Sequence[str] | None,
) -> tuple[list[str], list[str]]:
    if not key_columns:
        raise ValueError("key_columns vazio; e necessario informar pelo menos uma coluna-chave")

    key_columns_list = list(key_columns)
    common_columns_set = set(common_columns)
    missing_keys = [c for c in key_columns_list if c not in common_columns_set]
    if missing_keys:
        raise ValueError(
            "key_columns ausentes nas duas tabelas: " + ", ".join(sorted(missing_keys))
        )

    if compare_columns is None:
        compare_columns_list = [c for c in common_columns if c not in key_columns_list]
    else:
        compare_columns_list = list(compare_columns)
        missing_compare = [c for c in compare_columns_list if c not in common_columns_set]
        if missing_compare:
            raise ValueError(
                "compare_columns ausentes nas duas tabelas: "
                + ", ".join(sorted(missing_compare))
            )

    return key_columns_list, compare_columns_list


def _build_keyed_compare_plan(
    db1: Path,
    db2: Path,
    table: str,
    key_columns: Sequence[str],
    compare_columns: Sequence[str] | None,
) -> _KeyedComparePlan:
    db1, db2 = _resolve_duckdb_compare_paths(db1, db2)
    common_columns = _resolve_common_table_columns(db1, db2, table)
    key_columns_list, compare_columns_list = _resolve_keyed_compare_columns(
        common_columns,
        key_columns,
        compare_columns,
    )

    coalesced_keys = ", ".join([
        f"COALESCE({_qualify_identifier('a', c)}, {_qualify_identifier('b', c)}) AS {_quote_identifier(c)}"
        for c in key_columns_list
    ])

    compare_cols_sql_parts: List[str] = []
    diff_conditions: List[str] = []
    for c in compare_columns_list:
        compare_cols_sql_parts.append(
            f"{_qualify_identifier('a', c)} AS {_quote_identifier(f'a_{c}')}"
        )
        compare_cols_sql_parts.append(
            f"{_qualify_identifier('b', c)} AS {_quote_identifier(f'b_{c}')}"
        )
        diff_conditions.append(
            f"{_qualify_identifier('a', c)} IS DISTINCT FROM {_qualify_identifier('b', c)}"
        )

    compare_cols_sql = ", ".join(compare_cols_sql_parts) if compare_cols_sql_parts else ""
    diff_condition_sql = " OR ".join(diff_conditions) if diff_conditions else "FALSE"
    join_condition = " AND ".join([
        f"{_qualify_identifier('a', c)} = {_qualify_identifier('b', c)}"
        for c in key_columns_list
    ])
    change_type_case = (
        "CASE "
        f"WHEN {_qualify_identifier('a', key_columns_list[0])} IS NULL THEN 'added' "
        f"WHEN {_qualify_identifier('b', key_columns_list[0])} IS NULL THEN 'removed' "
        f"WHEN {diff_condition_sql} THEN 'changed' "
        "ELSE 'same' END AS change_type"
    )

    select_cols = coalesced_keys
    if compare_cols_sql:
        select_cols += ", " + compare_cols_sql
    select_cols += ", " + change_type_case

    return _KeyedComparePlan(
        db1=db1,
        db2=db2,
        table=table,
        key_columns=key_columns_list,
        compare_columns=compare_columns_list,
        table_a_sql=_qualify_identifier("db1", table),
        table_b_sql=_qualify_identifier("db2", table),
        join_condition=join_condition,
        diff_condition_sql=diff_condition_sql,
        select_cols=select_cols,
    )


def _build_keyed_diff_rows_cte_sql(plan: _KeyedComparePlan) -> str:
    return f"""
    WITH diff_rows AS (
      SELECT
        {plan.select_cols}
      FROM {plan.table_a_sql} AS a
      FULL OUTER JOIN {plan.table_b_sql} AS b
        ON {plan.join_condition}
      WHERE
        {_qualify_identifier('a', plan.key_columns[0])} IS NULL
        OR {_qualify_identifier('b', plan.key_columns[0])} IS NULL
        OR ({plan.diff_condition_sql})
    )
    """


def _build_compare_rows(
    rows: Sequence[tuple[Any, ...]],
    cols: Sequence[str],
    key_columns: Sequence[str],
    compare_columns: Sequence[str],
) -> list[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for row in rows:
        row_dict = {cols[i]: row[i] for i in range(len(cols))}
        change_type = row_dict.pop("change_type", "changed")
        key: Dict[str, Any] = {}
        for key_column in key_columns:
            key[key_column] = row_dict.pop(key_column, None)
        a_vals: Dict[str, Any] = {}
        b_vals: Dict[str, Any] = {}
        for compare_column in compare_columns:
            a_vals[compare_column] = row_dict.get(f"a_{compare_column}")
            b_vals[compare_column] = row_dict.get(f"b_{compare_column}")
        results.append({
            "type": change_type,
            "key": key,
            "a": a_vals,
            "b": b_vals,
        })
    return results


def compare_table_content_duckdb(db1: Path, db2: Path, table: str) -> dict:
    """Compara o conteúdo de uma tabela entre dois bancos DuckDB sem usar chave.

    Abre cada banco em modo somente leitura e compara o conjunto de linhas da
    tabela, considerando apenas as colunas em comum entre A e B. Isso evita
    manter os arquivos abertos em múltiplas conexões de escrita ao mesmo tempo,
    o que em Windows costuma gerar erros de "arquivo já está sendo usado".

    Retorna um dicionário no formato::

        {
            "table": str,
            "row_count_a": int,
            "row_count_b": int,
            "diff_count": int,  # número de linhas diferentes (ignorando ordem)
        }
    """

    db1 = db1.resolve()
    db2 = db2.resolve()
    if not db1.exists():
        raise FileNotFoundError(db1)
    if not db2.exists():
        raise FileNotFoundError(db2)

    # Conexões em modo somente leitura para minimizar conflitos de lock em Windows.
    conn1 = duckdb.connect(str(db1), read_only=True)
    conn2 = duckdb.connect(str(db2), read_only=True)
    conn_compare = _connect_memory()
    try:
        info_a = conn1.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
        info_b = conn2.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
        cols_a = {r[0] for r in info_a}
        cols_b = {r[0] for r in info_b}
        common_cols = sorted(cols_a & cols_b)

        if not common_cols:
            return {"table": table, "row_count_a": 0, "row_count_b": 0, "diff_count": -1}

        table_a_sql = _qualify_identifier("db1", table)
        table_b_sql = _qualify_identifier("db2", table)
        cols_sql = ", ".join(_quote_identifier(c) for c in common_cols)
        _attach_db(conn_compare, "db1", db1, read_only=True)
        _attach_db(conn_compare, "db2", db2, read_only=True)
        diff_sql = f"""
        WITH
          a_distinct AS (
            SELECT DISTINCT {cols_sql}
            FROM {table_a_sql}
          ),
          b_distinct AS (
            SELECT DISTINCT {cols_sql}
            FROM {table_b_sql}
          ),
          only_a AS (
            SELECT * FROM a_distinct
            EXCEPT
            SELECT * FROM b_distinct
          ),
          only_b AS (
            SELECT * FROM b_distinct
            EXCEPT
            SELECT * FROM a_distinct
          )
        SELECT
          (SELECT COUNT(*) FROM {table_a_sql}) AS row_count_a,
          (SELECT COUNT(*) FROM {table_b_sql}) AS row_count_b,
          ((SELECT COUNT(*) FROM only_a) + (SELECT COUNT(*) FROM only_b)) AS diff_count
        """
        summary_row = conn_compare.execute(diff_sql).fetchone()
        if summary_row is None:
            raise RuntimeError(f"Falha ao resumir diferencas da tabela {table}")

        row_count_a, row_count_b, diff_count = summary_row

        return {
            "table": table,
            "row_count_a": int(row_count_a),
            "row_count_b": int(row_count_b),
            "diff_count": int(diff_count),
        }
    finally:
        conn_compare.close()
        conn1.close()
        conn2.close()


def list_tables(db_path: Path) -> List[str]:
    """Lista tabelas de um arquivo DuckDB."""
    db_path = db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_common_tables(db1: Path, db2: Path) -> List[str]:
    """Retorna a interseção das tabelas entre dois bancos DuckDB."""
    t1 = set(list_tables(db1))
    t2 = set(list_tables(db2))
    return sorted(t1 & t2)


def list_table_columns(db_path: Path, table: str) -> List[str]:
    """Lista colunas de uma tabela DuckDB via information_schema."""
    db_path = db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def compare_table_duckdb(
    db1: Path,
    db2: Path,
    table: str,
    key_columns: Sequence[str],
    compare_columns: Sequence[str] | None = None,
    limit: int | None = None,
) -> Dict[str, Any]:
    """Compara uma tabela entre dois bancos DuckDB.

    Retorna apenas linhas que diferem entre A e B, classificadas como:
      - 'added': existe só em B
      - 'removed': existe só em A
      - 'changed': existe nos dois, mas alguma coluna mudou
    """
    plan = _build_keyed_compare_plan(db1, db2, table, key_columns, compare_columns)

    # CTE "diff_rows" seleciona todas as linhas com diferença.
    # CTE "annotated" adiciona contadores globais via window functions.
    # O LIMIT (se houver) é aplicado só na consulta final, então os totais
    # permanecem baseados em todas as diferenças da tabela.
    sql = _build_keyed_diff_rows_cte_sql(plan) + """
    , annotated AS (
      SELECT
        *,
        COUNT(*) OVER () AS diff_total,
        SUM(CASE WHEN change_type = 'added' THEN 1 ELSE 0 END) OVER () AS added_total,
        SUM(CASE WHEN change_type = 'removed' THEN 1 ELSE 0 END) OVER () AS removed_total,
        SUM(CASE WHEN change_type = 'changed' THEN 1 ELSE 0 END) OVER () AS changed_total
      FROM diff_rows
    )
    SELECT * FROM annotated
    """

    if limit is not None and int(limit) > 0:
        sql += f"\n    LIMIT {int(limit)}"

    conn = _connect_memory()
    try:
        _attach_db(conn, "db1", plan.db1, read_only=True)
        _attach_db(conn, "db2", plan.db2, read_only=True)
        rows = conn.execute(sql).fetchall()
        cols = [c[0] for c in conn.description]

        # Contagens de apoio para o resumo: total em cada tabela e total de chaves analisadas
        total_a_row = conn.execute(f"SELECT COUNT(*) FROM {plan.table_a_sql}").fetchone()
        total_b_row = conn.execute(f"SELECT COUNT(*) FROM {plan.table_b_sql}").fetchone()
        total_keys_row = conn.execute(
            f"SELECT COUNT(*) FROM {plan.table_a_sql} AS a "
            f"FULL OUTER JOIN {plan.table_b_sql} AS b ON {plan.join_condition}"
        ).fetchone()
        if total_a_row is None or total_b_row is None or total_keys_row is None:
            raise RuntimeError(f"Falha ao resumir contagens da tabela {table}")

        total_a = total_a_row[0]
        total_b = total_b_row[0]
        total_keys = total_keys_row[0]
    finally:
        conn.close()

    # Totais globais de diferenças (independentes do LIMIT).
    diff_total = 0
    added_total = 0
    removed_total = 0
    changed_total = 0

    for idx, row in enumerate(rows):
        row_dict = {cols[i]: row[i] for i in range(len(cols))}

        if idx == 0:
            # Lê os totais globais da primeira linha, se existirem.
            diff_total = int(row_dict.get("diff_total", 0) or 0)
            added_total = int(row_dict.get("added_total", 0) or 0)
            removed_total = int(row_dict.get("removed_total", 0) or 0)
            changed_total = int(row_dict.get("changed_total", 0) or 0)

        # Remove colunas auxiliares usadas apenas para o resumo.
        row_dict.pop("diff_total", None)
        row_dict.pop("added_total", None)
        row_dict.pop("removed_total", None)
        row_dict.pop("changed_total", None)

    cleaned_rows = []
    for row in rows:
        row_dict = {cols[i]: row[i] for i in range(len(cols))}
        row_dict.pop("diff_total", None)
        row_dict.pop("added_total", None)
        row_dict.pop("removed_total", None)
        row_dict.pop("changed_total", None)
        cleaned_rows.append(tuple(row_dict[col] for col in row_dict))
    result_cols = [
        col for col in cols
        if col not in {"diff_total", "added_total", "removed_total", "changed_total"}
    ]
    results = _build_compare_rows(
        cleaned_rows,
        result_cols,
        plan.key_columns,
        plan.compare_columns,
    )

    # Se não houver linhas com diferença, os totais permanecem zero.
    added_count = int(added_total)
    removed_count = int(removed_total)
    changed_count = int(changed_total)
    diff_count = int(diff_total)
    same_count = int(total_keys) - int(diff_count)

    return {
        "table": table,
        "db1": str(plan.db1),
        "db2": str(plan.db2),
        "key_columns": list(plan.key_columns),
        "compare_columns": list(plan.compare_columns),
        "row_count": len(results),
        "rows": results,
        "summary": {
            "rows_a": int(total_a),
            "rows_b": int(total_b),
            "keys_total": int(total_keys),
            "same_count": max(0, same_count),
            "added_count": int(added_count),
            "removed_count": int(removed_count),
            "changed_count": int(changed_count),
        },
    }


def compare_table_duckdb_paged(
    db1: Path,
    db2: Path,
    table: str,
    key_columns: Sequence[str],
    compare_columns: Sequence[str] | None = None,
    *,
    key_filter: Dict[str, str] | None = None,
    change_types: Sequence[str] | None = None,
    changed_column: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> Dict[str, Any]:
    """Compara uma tabela entre dois bancos DuckDB com filtros e paginação em SQL."""
    if int(page) < 1:
        raise ValueError("page deve ser maior ou igual a 1")
    if int(page_size) < 1:
        raise ValueError("page_size deve ser maior ou igual a 1")

    plan = _build_keyed_compare_plan(db1, db2, table, key_columns, compare_columns)

    if changed_column and changed_column not in plan.compare_columns:
        raise ValueError("changed_column precisa existir em compare_columns")

    valid_types = {"added", "removed", "changed"}
    change_types_list = list(change_types or [])
    invalid_change_types = [str(t) for t in change_types_list if str(t) not in valid_types]
    if invalid_change_types:
        raise ValueError("change_types contem valores invalidos: " + ", ".join(invalid_change_types))
    change_types_list = [str(t) for t in change_types_list]

    key_filter_map = dict(key_filter or {})
    invalid_filter_keys = [c for c in key_filter_map if c not in key_columns]
    if invalid_filter_keys:
        raise ValueError(
            "key_filter usa coluna fora de key_columns: " + ", ".join(sorted(invalid_filter_keys))
        )

    order_by_parts = [f"{_quote_identifier(c)} NULLS LAST" for c in plan.key_columns]
    order_by_parts.append("change_type")
    order_by_sql = ", ".join(order_by_parts)

    filter_clauses: List[str] = []
    filter_params: List[Any] = []
    for col, val in key_filter_map.items():
        filter_clauses.append(f"CAST({_quote_identifier(col)} AS VARCHAR) = ?")
        filter_params.append(str(val))

    if change_types_list:
        placeholders = ", ".join(["?"] * len(change_types_list))
        filter_clauses.append(f"change_type IN ({placeholders})")
        filter_params.extend(change_types_list)

    if changed_column:
        filter_clauses.append(
            f"(change_type <> 'changed' OR "
            f"{_quote_identifier(f'a_{changed_column}')} IS DISTINCT FROM {_quote_identifier(f'b_{changed_column}')})"
        )

    filtered_where_sql = " AND ".join(filter_clauses) if filter_clauses else "TRUE"

    common_cte_sql = f"""
    {_build_keyed_diff_rows_cte_sql(plan).strip()},
    filtered_rows AS (
      SELECT * FROM diff_rows
      WHERE {filtered_where_sql}
    )
    """

    summary_sql = common_cte_sql + f"""
    SELECT
      (SELECT COUNT(*) FROM {plan.table_a_sql}) AS rows_a,
      (SELECT COUNT(*) FROM {plan.table_b_sql}) AS rows_b,
      (SELECT COUNT(*) FROM {plan.table_a_sql} AS a FULL OUTER JOIN {plan.table_b_sql} AS b ON {plan.join_condition}) AS keys_total,
      (SELECT COUNT(*) FROM diff_rows) AS diff_total,
      (SELECT COUNT(*) FROM diff_rows WHERE change_type = 'added') AS added_total,
      (SELECT COUNT(*) FROM diff_rows WHERE change_type = 'removed') AS removed_total,
      (SELECT COUNT(*) FROM diff_rows WHERE change_type = 'changed') AS changed_total,
      (SELECT COUNT(*) FROM filtered_rows) AS filtered_total
    """

    conn = _connect_memory()
    try:
        _attach_db(conn, "db1", plan.db1, read_only=True)
        _attach_db(conn, "db2", plan.db2, read_only=True)

        summary_row = conn.execute(summary_sql, filter_params).fetchone()
        if summary_row is None:
            raise RuntimeError(f"Falha ao resumir comparacao da tabela {table}")

        (
            total_a,
            total_b,
            total_keys,
            diff_total,
            added_total,
            removed_total,
            changed_total,
            filtered_total,
        ) = summary_row

        filtered_total_int = int(filtered_total or 0)
        page_int = int(page)
        page_size_int = int(page_size)
        total_pages = max(1, (filtered_total_int + page_size_int - 1) // page_size_int)
        if filtered_total_int == 0:
            page_int = 1
        elif page_int > total_pages:
            page_int = total_pages
        offset = (page_int - 1) * page_size_int

        rows: List[tuple[Any, ...]] = []
        cols: List[str] = []
        if filtered_total_int > 0:
            page_sql = common_cte_sql + f"""
            SELECT *
            FROM filtered_rows
            ORDER BY {order_by_sql}
            LIMIT ? OFFSET ?
            """
            page_params = [*filter_params, page_size_int, offset]
            rows = conn.execute(page_sql, page_params).fetchall()
            cols = [c[0] for c in conn.description]
    finally:
        conn.close()

    results = _build_compare_rows(rows, cols, plan.key_columns, plan.compare_columns)

    same_count = int(total_keys or 0) - int(diff_total or 0)

    return {
        "table": table,
        "db1": str(plan.db1),
        "db2": str(plan.db2),
        "key_columns": list(plan.key_columns),
        "compare_columns": list(plan.compare_columns),
        "row_count": len(results),
        "rows": results,
        "page": int(page_int),
        "page_size": int(page_size_int),
        "total_filtered_rows": int(filtered_total_int),
        "total_pages": int(total_pages),
        "summary": {
            "rows_a": int(total_a or 0),
            "rows_b": int(total_b or 0),
            "keys_total": int(total_keys or 0),
            "same_count": max(0, same_count),
            "added_count": int(added_total or 0),
            "removed_count": int(removed_total or 0),
            "changed_count": int(changed_total or 0),
        },
    }
