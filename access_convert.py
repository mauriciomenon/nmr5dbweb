# access_convert.py
# Conversor Access (.mdb / .accdb) -> DuckDB (.duckdb)
# Now supports progress_callback(progress_dict) to report progress during conversion.
#
import os
import json
import subprocess
import tempfile
import shutil
import duckdb
import pandas as pd
import logging
from interface.access_parser_utils import (
    ensure_access_parser_logging,
    is_access_parser_no_data_error,
    list_access_tables_from_parser,
    load_access_parser_module,
    normalize_access_parser_rows,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("access_convert")
ensure_access_parser_logging()
MDBTOOLS_TIMEOUT_SECONDS = 300


def _access_parser_allow_skips() -> bool:
    raw = str(os.environ.get("NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS", "")).strip().lower()
    return raw in ("1", "true", "yes", "on")


def _sanitize_parser_value(value):
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        except Exception:
            return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return bytes(value).hex()
        except Exception:
            return str(value)
    return value


def _sanitize_parser_rows(rows):
    safe_rows = []
    for row in rows:
        if not isinstance(row, dict):
            safe_rows.append({"value": _sanitize_parser_value(row)})
            continue
        safe_rows.append(
            {str(col): _sanitize_parser_value(val) for col, val in row.items()}
        )
    return safe_rows


def _ensure_clean_duckdb(path):
    try:
        if os.path.exists(path):
            logger.info("Removing existing .duckdb output before conversion: %s", path)
            os.remove(path)
    except Exception as e:
        logger.warning("Could not remove existing .duckdb output %s: %s", path, e)
        raise RuntimeError(f"could not clear existing duckdb output: {path}") from e


def _public_failure_message(primary_message: str) -> str:
    text = str(primary_message or "").strip()
    if not text:
        return "All conversion methods failed. See logs for details."
    if "strict mode" in text.lower():
        return "Conversion failed in strict mode. See logs for details."
    return "All conversion methods failed. See logs for details."


def _select_primary_failure_message(*messages: str) -> str:
    for msg in messages:
        if isinstance(msg, str) and "strict mode" in msg.lower():
            return msg
    for msg in messages:
        if isinstance(msg, str) and msg.strip():
            return msg
    return ""


def convert_access_to_duckdb(access_path: str, duckdb_path: str, chunk_size: int = 50000, prefer_odbc: bool = True, progress_callback=None):
    """
    Convert an Access DB (.mdb or .accdb) to a DuckDB file.
    progress_callback: optional callable(dict) where dict contains keys:
      - total_tables (int), processed_tables (int), current_table (str), percent (0..100), msg (str)
    Returns (ok: bool, message: str)
    """
    access_path = os.path.abspath(access_path)
    duckdb_path = os.path.abspath(duckdb_path)
    logger.info("convert_access_to_duckdb: %s -> %s", access_path, duckdb_path)

    def _report(**kw):
        try:
            if callable(progress_callback):
                progress_callback(kw)
        except Exception:
            pass

    def try_pyodbc():
        try:
            import pyodbc  # ty: ignore[unresolved-import]
        except Exception as e:
            return False, f"pyodbc not installed: {e}"

        conn_strings = [
            fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};",
            fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={access_path};",
        ]
        conn = None
        last_err = None
        for cs in conn_strings:
            try:
                conn = pyodbc.connect(cs, autocommit=True)
                logger.info("Conectado via pyodbc com conn string: %s", cs)
                break
            except Exception as e:
                last_err = e
                conn = None
        if conn is None:
            return False, f"ODBC connect failed: {last_err}"

        dconn = None
        try:
            cur = conn.cursor()
            tables = []
            try:
                for row in cur.tables():
                    try:
                        tname = getattr(row, "table_name", None) or (row[2] if len(row) > 2 else None)
                    except Exception:
                        tname = None
                    if tname and not str(tname).startswith("MSys"):
                        tables.append(tname)
            except Exception:
                try:
                    rows = cur.execute("SELECT Name FROM MSysObjects WHERE Type In (1,4) AND Flags = 0").fetchall()
                    tables = [r[0] for r in rows]
                except Exception:
                    pass

            if not tables:
                return False, "No user tables found in Access DB."

            total = len(tables)
            _ensure_clean_duckdb(duckdb_path)
            dconn = duckdb.connect(duckdb_path)
            materialized_tables = 0
            skipped_tables = []

            for i, t in enumerate(tables):
                safe_table = str(t).replace('"', '""')
                _report(total_tables=total, processed_tables=i, current_table=str(t), percent=int((i/total)*100), msg="starting_table")
                logger.info("Convertendo tabela %d/%d: %s", i+1, total, t)
                try:
                    sql = f"SELECT * FROM [{t}]"
                    # drop if exists to avoid errors
                    dconn.execute(f'DROP TABLE IF EXISTS "{safe_table}"')
                    table_materialized = False
                    try:
                        it = pd.read_sql_query(sql, conn, chunksize=chunk_size)
                        first = True
                        for j, df_chunk in enumerate(it):
                            if df_chunk is None or df_chunk.shape[0] == 0:
                                continue
                            tmp_name = f"tmp_{abs(hash((t, j)))}"
                            dconn.register(tmp_name, df_chunk)
                            if first:
                                dconn.execute(f'CREATE TABLE "{safe_table}" AS SELECT * FROM {tmp_name}')
                                first = False
                                table_materialized = True
                            else:
                                dconn.execute(f'INSERT INTO "{safe_table}" SELECT * FROM {tmp_name}')
                            dconn.unregister(tmp_name)
                            # report progress within table (approx)
                            _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i + (j+1)/(1+ (df_chunk.shape[0]/max(1,chunk_size))))/total)*100), msg="in_table_chunk")
                    except ValueError:
                        # chunksize not supported: read all
                        df = pd.read_sql_query(sql, conn)
                        if df is None or df.shape[0] == 0:
                            logger.info("Tabela vazia: %s", t)
                        else:
                            tmp_name = f"tmp_{abs(hash((t,0)))}"
                            dconn.register(tmp_name, df)
                            dconn.execute(f'CREATE TABLE "{safe_table}" AS SELECT * FROM {tmp_name}')
                            dconn.unregister(tmp_name)
                            table_materialized = True
                    if table_materialized:
                        materialized_tables += 1
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg="table_done")
                except Exception as e:
                    logger.warning("Skipping table %s after errors: %s", t, e)
                    skipped_tables.append((str(t), str(e)))
                    # continue with next table
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg=f"skipped:{e}")
                    continue

            if skipped_tables and not _access_parser_allow_skips():
                sample = "; ".join(f"{name}: {err}" for name, err in skipped_tables[:3])
                return (
                    False,
                    "strict mode: "
                    f"skipped {len(skipped_tables)}/{total} table(s). "
                    "Set NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS=1 to allow partial conversion. "
                    f"samples: {sample}",
                )
            if materialized_tables == 0 and skipped_tables:
                return False, "strict mode: no tables materialized via pyodbc"
            _report(total_tables=total, processed_tables=total, current_table="", percent=100, msg="converted")
            if skipped_tables:
                return True, f"converted via pyodbc (skipped={len(skipped_tables)})"
            if materialized_tables == 0:
                return False, "strict mode: no tables materialized via pyodbc"
            return True, "converted via pyodbc"
        except Exception as e:
            return False, f"pyodbc error: {e}"
        finally:
            try:
                if dconn is not None:
                    dconn.close()
            except Exception:
                pass
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def try_pypyodbc():
        try:
            import pypyodbc as pyodbc  # ty: ignore[unresolved-import]
        except Exception as e:
            return False, f"pypyodbc not installed: {e}"
        conn = None
        dconn = None
        try:
            cs = fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};"
            conn = pyodbc.connect(cs)
            cur = conn.cursor()
            tables = [r[2] for r in cur.tables() if (r[3].upper()=='TABLE' and not str(r[2]).startswith("MSys"))]
            if not tables:
                return False, "No user tables found (pypyodbc)."
            total = len(tables)
            _ensure_clean_duckdb(duckdb_path)
            dconn = duckdb.connect(duckdb_path)
            materialized_tables = 0
            skipped_tables = []
            for i, t in enumerate(tables):
                safe_table = str(t).replace('"', '""')
                _report(total_tables=total, processed_tables=i, current_table=str(t), percent=int((i/total)*100), msg="starting_table")
                try:
                    dconn.execute(f'DROP TABLE IF EXISTS "{safe_table}"')
                    it = pd.read_sql_query(f"SELECT * FROM [{t}]", conn, chunksize=chunk_size)
                    first = True
                    table_materialized = False
                    for j, df_chunk in enumerate(it):
                        if df_chunk is None or df_chunk.shape[0] == 0:
                            continue
                        tmp_name = f"tmp_{abs(hash((t, j)))}"
                        dconn.register(tmp_name, df_chunk)
                        if first:
                            dconn.execute(f'CREATE TABLE "{safe_table}" AS SELECT * FROM {tmp_name}')
                            first = False
                            table_materialized = True
                        else:
                            dconn.execute(f'INSERT INTO "{safe_table}" SELECT * FROM {tmp_name}')
                        dconn.unregister(tmp_name)
                        _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i + (j+1)/1)/total)*100), msg="in_table_chunk")
                    if table_materialized:
                        materialized_tables += 1
                except Exception as e:
                    logger.warning("Skipping %s: %s", t, e)
                    skipped_tables.append((str(t), str(e)))
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg=f"skipped:{e}")
                    continue
            if skipped_tables and not _access_parser_allow_skips():
                sample = "; ".join(f"{name}: {err}" for name, err in skipped_tables[:3])
                return (
                    False,
                    "strict mode: "
                    f"skipped {len(skipped_tables)}/{total} table(s). "
                    "Set NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS=1 to allow partial conversion. "
                    f"samples: {sample}",
                )
            if materialized_tables == 0 and skipped_tables:
                return False, "strict mode: no tables materialized via pypyodbc"
            _report(total_tables=total, processed_tables=total, current_table="", percent=100, msg="converted")
            if skipped_tables:
                return True, f"converted via pypyodbc (skipped={len(skipped_tables)})"
            if materialized_tables == 0:
                return False, "strict mode: no tables materialized via pypyodbc"
            return True, "converted via pypyodbc"
        except Exception as e:
            return False, f"pypyodbc error: {e}"
        finally:
            try:
                if dconn is not None:
                    dconn.close()
            except Exception:
                pass
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def try_mdbtools():
        if not access_path.lower().endswith('.mdb'):
            return False, "mdbtools supports only .mdb"
        try:
            proc = subprocess.run(
                ["mdb-tables", "-1", access_path],
                capture_output=True,
                text=True,
                check=True,
                timeout=MDBTOOLS_TIMEOUT_SECONDS,
            )
            tbls = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        except subprocess.TimeoutExpired:
            return False, f"mdb-tables timeout after {MDBTOOLS_TIMEOUT_SECONDS}s"
        except Exception as e:
            return False, f"mdb-tables failed: {e}"
        total = len(tbls)
        if total == 0:
            try:
                _ensure_clean_duckdb(duckdb_path)
            except Exception as cleanup_exc:
                logger.warning(
                    "Could not clear stale output %s after empty mdbtools source: %s",
                    duckdb_path,
                    cleanup_exc,
                )
            return False, "No user tables found via mdbtools."
        _ensure_clean_duckdb(duckdb_path)
        dconn = duckdb.connect(duckdb_path)
        tmpdir = tempfile.mkdtemp(prefix="mdbtools_")
        materialized_tables = 0
        skipped_tables = []
        try:
            for i, t in enumerate(tbls):
                csv_path = os.path.join(tmpdir, f"{t}.csv")
                _report(total_tables=total, processed_tables=i, current_table=str(t), percent=int((i/total)*100), msg="starting_table")
                try:
                    with open(csv_path, "w", encoding="utf-8") as out:
                        subprocess.run(
                            ["mdb-export", access_path, t],
                            stdout=out,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True,
                            timeout=MDBTOOLS_TIMEOUT_SECONDS,
                        )
                    csv_path_unix = csv_path.replace("\\", "/").replace("'", "''")
                    safe_table = str(t).replace('"', '""')
                    dconn.execute(f'DROP TABLE IF EXISTS "{safe_table}"')
                    dconn.execute(f"CREATE TABLE \"{safe_table}\" AS SELECT * FROM read_csv_auto('{csv_path_unix}')")
                    materialized_tables += 1
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg="table_done")
                except subprocess.TimeoutExpired:
                    err_msg = f"mdb-export timeout after {MDBTOOLS_TIMEOUT_SECONDS}s"
                    logger.warning("Failed to export/import table %s: %s", t, err_msg)
                    skipped_tables.append((str(t), err_msg))
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg=f"skipped:{err_msg}")
                    continue
                except Exception as e:
                    logger.warning("Failed to export/import table %s: %s", t, e)
                    skipped_tables.append((str(t), str(e)))
                    _report(total_tables=total, processed_tables=i+1, current_table=str(t), percent=int(((i+1)/total)*100), msg=f"skipped:{e}")
                    continue
            if skipped_tables and not _access_parser_allow_skips():
                sample = "; ".join(f"{name}: {err}" for name, err in skipped_tables[:3])
                return (
                    False,
                    "strict mode: "
                    f"skipped {len(skipped_tables)}/{total} table(s). "
                    "Set NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS=1 to allow partial conversion. "
                    f"samples: {sample}",
                )
            if materialized_tables == 0:
                return False, "strict mode: no tables materialized via mdbtools"
            _report(total_tables=total, processed_tables=total, current_table="", percent=100, msg="converted")
            if skipped_tables:
                return True, f"converted via mdbtools (skipped={len(skipped_tables)})"
            return True, "converted via mdbtools"
        except Exception as e:
            return False, f"mdbtools error: {e}"
        finally:
            try:
                dconn.close()
            except Exception as close_exc:
                logger.warning("Failed to close DuckDB connection in mdbtools path: %s", close_exc)
            try:
                shutil.rmtree(tmpdir)
            except Exception as cleanup_exc:
                logger.warning("Failed to cleanup mdbtools temp dir %s: %s", tmpdir, cleanup_exc)

    def try_access_parser():
        ap, mod_err = load_access_parser_module()
        if ap is None:
            return False, f"access-parser not installed: {mod_err}"

        try:
            db = ap.AccessParser(access_path)
        except Exception as e:
            return False, f"access-parser open failed: {e}"

        dconn = None
        try:
            tables = list_access_tables_from_parser(db)
            if not tables:
                return False, "No user tables found via access-parser."

            total = len(tables)
            _ensure_clean_duckdb(duckdb_path)
            dconn = duckdb.connect(duckdb_path)
            converted_tables = 0
            skipped_tables = []
            no_data_tables = 0
            no_data_samples = []

            for i, table_name in enumerate(tables):
                safe_table = str(table_name).replace('"', '""')
                _report(
                    total_tables=total,
                    processed_tables=i,
                    current_table=str(table_name),
                    percent=int((i / total) * 100),
                    msg="starting_table",
                )
                try:
                    parsed = db.parse_table(table_name)
                    rows = normalize_access_parser_rows(parsed)
                    if rows:
                        frame = pd.DataFrame(_sanitize_parser_rows(rows))
                    elif isinstance(parsed, dict) and parsed:
                        frame = pd.DataFrame(
                            columns=pd.Index([str(col) for col in parsed.keys()])
                        )
                    else:
                        _report(
                            total_tables=total,
                            processed_tables=i + 1,
                            current_table=str(table_name),
                            percent=int(((i + 1) / total) * 100),
                            msg="table_empty",
                        )
                        continue

                    dconn.execute(f'DROP TABLE IF EXISTS "{safe_table}"')

                    if frame.shape[1] == 0:
                        _report(
                            total_tables=total,
                            processed_tables=i + 1,
                            current_table=str(table_name),
                            percent=int(((i + 1) / total) * 100),
                            msg="table_no_columns",
                        )
                        continue

                    tmp_name = f"tmp_{abs(hash((table_name, i, frame.shape[0])))}"
                    dconn.register(tmp_name, frame)
                    dconn.execute(f'CREATE TABLE "{safe_table}" AS SELECT * FROM {tmp_name}')
                    dconn.unregister(tmp_name)
                    converted_tables += 1

                    _report(
                        total_tables=total,
                        processed_tables=i + 1,
                        current_table=str(table_name),
                        percent=int(((i + 1) / total) * 100),
                        msg="table_done",
                    )
                except Exception as e:
                    err_msg = str(e)
                    if is_access_parser_no_data_error(err_msg):
                        no_data_tables += 1
                        if len(no_data_samples) < 5:
                            no_data_samples.append(str(table_name))
                        _report(
                            total_tables=total,
                            processed_tables=i + 1,
                            current_table=str(table_name),
                            percent=int(((i + 1) / total) * 100),
                            msg="table_no_data",
                        )
                        continue
                    logger.warning("Skipping table %s after access-parser error: %s", table_name, err_msg)
                    skipped_tables.append((str(table_name), err_msg))
                    _report(
                        total_tables=total,
                        processed_tables=i + 1,
                        current_table=str(table_name),
                        percent=int(((i + 1) / total) * 100),
                        msg=f"skipped:{err_msg}",
                    )
                    continue

            if no_data_tables:
                logger.info(
                    "access-parser no-data tables: %s/%s sample=%s",
                    no_data_tables,
                    total,
                    ",".join(no_data_samples),
                )

            dconn.close()
            if skipped_tables and not _access_parser_allow_skips():
                sample = "; ".join(f"{name}: {err}" for name, err in skipped_tables[:3])
                return (
                    False,
                    "access-parser strict mode: "
                    f"skipped {len(skipped_tables)}/{total} table(s). "
                    "Set NMR5DBWEB_ACCESS_PARSER_ALLOW_SKIPS=1 to allow partial conversion. "
                    f"samples: {sample}",
                )
            if converted_tables == 0 and total > 0:
                if no_data_tables == total:
                    _report(
                        total_tables=total,
                        processed_tables=total,
                        current_table="",
                        percent=100,
                        msg="converted_no_data",
                    )
                    return True, "converted via access-parser (all tables without data)"
                return False, "access-parser strict mode: no tables converted"
            _report(
                total_tables=total,
                processed_tables=total,
                current_table="",
                percent=100,
                msg="converted",
            )
            if skipped_tables:
                return True, f"converted via access-parser (skipped={len(skipped_tables)})"
            return True, "converted via access-parser"
        except Exception as e:
            try:
                if dconn is not None:
                    dconn.close()
            except Exception:
                pass
            return False, f"access-parser error: {e}"

    # Try methods by preference
    if prefer_odbc:
        ok, msg = try_pyodbc()
        if ok:
            return True, msg
        ok2, msg2 = try_pypyodbc()
        if ok2:
            return True, msg2
        ok3, msg3 = try_mdbtools()
        if ok3:
            return True, msg3
        ok4, msg4 = try_access_parser()
        if ok4:
            return True, msg4
        logger.error(
            "All conversion methods failed. pyodbc=%s; pypyodbc=%s; mdbtools=%s; access-parser=%s",
            msg,
            msg2,
            msg3,
            msg4,
        )
        primary = _select_primary_failure_message(msg, msg2, msg3, msg4)
        return False, _public_failure_message(primary)
    else:
        # Non-ODBC preferred path (used in non-Windows runtime):
        # - .mdb: mdbtools first, then access-parser
        # - .accdb: access-parser first
        ext = os.path.splitext(access_path)[1].lower()
        if ext == ".mdb":
            ok, msg = try_mdbtools()
            if ok:
                return True, msg
            ok2, msg2 = try_access_parser()
            if ok2:
                return True, msg2
            ok3, msg3 = try_pyodbc()
            if ok3:
                return True, msg3
            ok4, msg4 = try_pypyodbc()
            if ok4:
                return True, msg4
            logger.error(
                "No conversion backend succeeded (.mdb path). mdbtools=%s; access-parser=%s; pyodbc=%s; pypyodbc=%s",
                msg,
                msg2,
                msg3,
                msg4,
            )
            primary = _select_primary_failure_message(msg, msg2, msg3, msg4)
            return False, _public_failure_message(primary)

        ok, msg = try_access_parser()
        if ok:
            return True, msg
        ok2, msg2 = try_mdbtools()
        if ok2:
            return True, msg2
        ok3, msg3 = try_pyodbc()
        if ok3:
            return True, msg3
        ok4, msg4 = try_pypyodbc()
        if ok4:
            return True, msg4
        logger.error(
            "No conversion backend succeeded (.accdb path). access-parser=%s; mdbtools=%s; pyodbc=%s; pypyodbc=%s",
            msg,
            msg2,
            msg3,
            msg4,
        )
        primary = _select_primary_failure_message(msg, msg2, msg3, msg4)
        return False, _public_failure_message(primary)
