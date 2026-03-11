#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ferramentas de comparação entre dois bancos DuckDB.

MVP: compara uma tabela por vez, assumindo que ambos os arquivos são
bancos DuckDB (.duckdb). Para outros formatos, a ideia é converter
antes.
"""

from __future__ import annotations

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
    if not key_columns:
        raise ValueError("key_columns vazio; é necessário informar pelo menos uma coluna-chave")

    db1 = db1.resolve()
    db2 = db2.resolve()
    if not db1.exists():
        raise FileNotFoundError(db1)
    if not db2.exists():
        raise FileNotFoundError(db2)

    cols_a = list_table_columns(db1, table)
    cols_b = list_table_columns(db2, table)
    missing_tables = []
    if not cols_a:
        missing_tables.append("db1")
    if not cols_b:
        missing_tables.append("db2")
    if missing_tables:
        raise ValueError(f"tabela '{table}' nao encontrada em: {', '.join(missing_tables)}")

    common_columns = [c for c in cols_a if c in set(cols_b)]
    missing_keys = [c for c in key_columns if c not in common_columns]
    if missing_keys:
        raise ValueError(
            "key_columns ausentes nas duas tabelas: " + ", ".join(sorted(missing_keys))
        )

    # Se compare_columns não for informado, usamos todas as colunas exceto as de chave,
    # tomando como referência o schema do primeiro banco.
    if compare_columns is None:
        compare_columns = [c for c in common_columns if c not in key_columns]
    else:
        missing_compare = [c for c in compare_columns if c not in common_columns]
        if missing_compare:
            raise ValueError(
                "compare_columns ausentes nas duas tabelas: " + ", ".join(sorted(missing_compare))
            )

    # usamos COALESCE nas chaves para obter um valor único mesmo em linhas adicionadas/removidas
    coalesced_keys = ", ".join([
        f"COALESCE({_qualify_identifier('a', c)}, {_qualify_identifier('b', c)}) AS {_quote_identifier(c)}"
        for c in key_columns
    ])

    compare_cols_sql_parts: List[str] = []
    diff_conditions: List[str] = []
    for c in compare_columns:
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

    # condição de junção pelas chaves
    join_condition = " AND ".join([
        f"{_qualify_identifier('a', c)} = {_qualify_identifier('b', c)}" for c in key_columns
    ])

    # change_type: classifica adicionados / removidos / alterados
    change_type_case = (
        "CASE "
        f"WHEN {_qualify_identifier('a', key_columns[0])} IS NULL THEN 'added' "
        f"WHEN {_qualify_identifier('b', key_columns[0])} IS NULL THEN 'removed' "
        f"WHEN {diff_condition_sql} THEN 'changed' "
        "ELSE 'same' END AS change_type"
    )

    select_cols = coalesced_keys
    if compare_cols_sql:
        select_cols += ", " + compare_cols_sql
    select_cols += ", " + change_type_case
    table_a_sql = _qualify_identifier("db1", table)
    table_b_sql = _qualify_identifier("db2", table)

    # CTE "diff_rows" seleciona todas as linhas com diferença.
    # CTE "annotated" adiciona contadores globais via window functions.
    # O LIMIT (se houver) é aplicado só na consulta final, então os totais
    # permanecem baseados em todas as diferenças da tabela.
    sql = f"""
    WITH diff_rows AS (
      SELECT
        {select_cols}
      FROM {table_a_sql} AS a
      FULL OUTER JOIN {table_b_sql} AS b
        ON {join_condition}
      WHERE
        {_qualify_identifier('a', key_columns[0])} IS NULL
        OR {_qualify_identifier('b', key_columns[0])} IS NULL
        OR ({diff_condition_sql})
    ), annotated AS (
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
        _attach_db(conn, "db1", db1, read_only=True)
        _attach_db(conn, "db2", db2, read_only=True)
        rows = conn.execute(sql).fetchall()
        cols = [c[0] for c in conn.description]

        # Contagens de apoio para o resumo: total em cada tabela e total de chaves analisadas
        total_a_row = conn.execute(f"SELECT COUNT(*) FROM {table_a_sql}").fetchone()
        total_b_row = conn.execute(f"SELECT COUNT(*) FROM {table_b_sql}").fetchone()
        total_keys_row = conn.execute(
            f"SELECT COUNT(*) FROM {table_a_sql} AS a FULL OUTER JOIN {table_b_sql} AS b ON {join_condition}"
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

    results: List[Dict[str, Any]] = []
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

        change_type = row_dict.pop("change_type", "changed")
        key: Dict[str, Any] = {}
        for k in key_columns:
            key[k] = row_dict.pop(k, None)
        a_vals: Dict[str, Any] = {}
        b_vals: Dict[str, Any] = {}
        for c in compare_columns or []:
            a_vals[c] = row_dict.get(f"a_{c}")
            b_vals[c] = row_dict.get(f"b_{c}")
        results.append({
            "type": change_type,
            "key": key,
            "a": a_vals,
            "b": b_vals,
        })

    # Se não houver linhas com diferença, os totais permanecem zero.
    added_count = int(added_total)
    removed_count = int(removed_total)
    changed_count = int(changed_total)
    diff_count = int(diff_total)
    same_count = int(total_keys) - int(diff_count)

    return {
        "table": table,
        "db1": str(db1),
        "db2": str(db2),
        "key_columns": list(key_columns),
        "compare_columns": list(compare_columns or []),
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
