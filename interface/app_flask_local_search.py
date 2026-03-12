# app_flask_local_search.py
# Complete Flask app for local fuzzy search over DuckDB (and optional Access fallback).
# Features:
# - Upload / list / select / delete uploaded DB files (.duckdb, .mdb, .accdb)
# - Background conversion (.mdb/.accdb -> .duckdb) when access_convert.convert_access_to_duckdb is available
# - Progress reporting for conversion (admin/status)
# - Optional automatic _fulltext index creation via create_fulltext.create_or_resume_fulltext
# - /api/tables, /api/table, /api/search endpoints
# - Priority tables support via /admin/set_priority
# - Fallback search against Access via pyodbc (if installed)
#
# Replace your existing app_flask_local_search.py with this file.
# Requirements: pip install flask duckdb rapidfuzz pandas pyodbc (pyodbc optional)
# Optional helpers (place in same folder):
# - access_convert.py with convert_access_to_duckdb(access_path, duckdb_path, chunk_size=..., progress_callback=...)
# - create_fulltext.py with create_or_resume_fulltext(dbpath, drop=False, chunk=2000, batch_insert=1000)
# - utils.py with normalize_text(value) and serialize_value(value) if you want custom behavior (fallbacks included)
import os
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Any, Callable
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import duckdb
from rapidfuzz import fuzz

from interface.find_record_across_dbs import find_record_across_dbs, SUPPORTED_EXTS
from interface.compare_dbs import (
    list_common_tables,
    list_table_columns,
    compare_table_duckdb_paged,
    compare_table_content_duckdb,
)

# Optional modules
OPTIONAL_IMPORT_ERRORS = {}
pyodbc: Any | None = None
try:
    import pyodbc as _pyodbc
except Exception as exc:
    OPTIONAL_IMPORT_ERRORS["pyodbc"] = str(exc)
else:
    pyodbc = _pyodbc

convert_access_to_duckdb: Callable[..., Any] | None = None
try:
    from access_convert import convert_access_to_duckdb as _convert_access_to_duckdb
except Exception as exc:
    OPTIONAL_IMPORT_ERRORS["access_convert"] = str(exc)
else:
    convert_access_to_duckdb = _convert_access_to_duckdb

create_or_resume_fulltext: Callable[..., Any] | None = None
try:
    from interface.create_fulltext import create_or_resume_fulltext as _create_or_resume_fulltext
except Exception as exc:
    OPTIONAL_IMPORT_ERRORS["create_fulltext"] = str(exc)
else:
    create_or_resume_fulltext = _create_or_resume_fulltext

try:
    from interface.utils import normalize_text, serialize_value
except Exception:
    def normalize_text(s):
        return str(s).lower() if s is not None else ""
    def serialize_value(v):
        if v is None:
            return ""
        try:
            return str(v)
        except Exception:
            return repr(v)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
# Pasta de uploads da interface web (interface/uploads),
# onde o endpoint /admin/upload grava os arquivos usados na pesquisa.
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CONFIG_FILE = BASE_DIR / "config.json"
ALLOWED_EXTENSIONS = {".duckdb", ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"}
ACCESS_EXTENSIONS = {".mdb", ".accdb"}
SQLITE_EXTENSIONS = {".sqlite", ".sqlite3"}
DUCKDB_EXTENSIONS = {".duckdb"}

# Conversion & index state
convert_lock = threading.Lock()
convert_status = {
    "running": False,
    "ok": None,
    "msg": None,
    "input": None,
    "output": None,
    "total_tables": 0,
    "processed_tables": 0,
    "current_table": "",
    "percent": 0
}
convert_thread = None

index_lock = threading.Lock()
index_thread = None
runtime_lock = threading.Lock()
startup_warnings = []


# Diretórios "seguros" para varrer bancos ao rastrear registros.
# A interface usa os IDs abaixo para não expor caminhos arbitrários.
RECORD_DIRS = {
    "bancos_atuais": {
        "label": "Bancos atuais (.accdb)",
        "path": PROJECT_ROOT / "import_folder" / "Bancos atuais",
    },
    "bancos_historicos": {
        "label": "Bancos históricos (.accdb)",
        "path": PROJECT_ROOT / "import_folder" / "bancos",
    },
    "uploads_duckdb": {
        "label": "Uploads convertidos (.duckdb)",
        "path": BASE_DIR / "uploads",
    },
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    else:
        cfg = {}

    # valores padrão seguros para novo ambiente
    if "db_path" not in cfg:
        cfg["db_path"] = ""
    if "priority_tables" not in cfg:
        cfg["priority_tables"] = []
    if "auto_index_after_convert" not in cfg:
        cfg["auto_index_after_convert"] = True
    return cfg

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

cfg = load_config()
# sanitize priority_tables
if not isinstance(cfg.get("priority_tables"), list):
    cfg["priority_tables"] = []
else:
    cfg["priority_tables"] = [t for t in cfg["priority_tables"] if t and t != "None"]

# se o caminho do DB configurado não existir (por exemplo, em outro computador),
# limpamos para evitar erros ao abrir a interface em um ambiente novo
db_cfg = cfg.get("db_path") or ""
try:
    if db_cfg and not Path(db_cfg).exists():
        startup_warnings.append(f"db_path configurado nao existe mais: {db_cfg}")
        cfg["db_path"] = ""
except Exception:
    startup_warnings.append("db_path configurado e invalido e foi descartado")
    cfg["db_path"] = ""
runtime_state = {"db_path": str(cfg.get("db_path") or "")}

def get_db_path():
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return env_path
    with runtime_lock:
        return runtime_state.get("db_path", "")

def set_db_path(p):
    value = str(p) if p else ""
    with runtime_lock:
        runtime_state["db_path"] = value
    cfg["db_path"] = value
    save_config(cfg)


def clear_db_path():
    set_db_path("")


def get_runtime_capabilities():
    return {
        "access_fallback": pyodbc is not None,
        "access_conversion": convert_access_to_duckdb is not None,
        "duckdb_fulltext": create_or_resume_fulltext is not None,
    }


def get_current_db_context(*, require_selected=False, require_exists=False, allowed_engines=None):
    db_path = get_db_path()
    if not db_path:
        if require_selected:
            raise ValueError("No DB selected")
        return {"db_path": "", "db_engine": "", "db_exists": False}

    db_exists = Path(db_path).exists()
    if require_exists and not db_exists:
        raise FileNotFoundError(f"DB ativo nao encontrado: {db_path}")

    db_engine = detect_db_engine(db_path) if db_exists else ""
    if allowed_engines is not None and db_engine not in set(allowed_engines):
        raise ValueError(f"Engine nao suportada para esta operacao: {db_engine or 'desconhecida'}")

    return {"db_path": db_path, "db_engine": db_engine, "db_exists": db_exists}


def build_admin_status():
    ctx = get_current_db_context()
    status = {
        "indexing": False,
        "db": ctx["db_path"],
        "db_exists": ctx["db_exists"],
        "db_engine": ctx["db_engine"],
        "fulltext_count": 0,
        "top_tables": [],
        "startup_warnings": list(startup_warnings),
        "capabilities": get_runtime_capabilities(),
    }
    with index_lock:
        if index_thread and index_thread.is_alive():
            status["indexing"] = True
    with convert_lock:
        status["conversion"] = dict(convert_status)
    status["priority_tables"] = cfg.get("priority_tables", [])
    status["auto_index_after_convert"] = cfg.get("auto_index_after_convert", True)

    if not ctx["db_path"] or not ctx["db_exists"]:
        return status
    if ctx["db_engine"] != "duckdb":
        return status

    try:
        conn = duckdb_connect(ctx["db_path"])
        try:
            total = conn.execute("SELECT COUNT(*) FROM _fulltext").fetchone()[0]
            status["fulltext_count"] = int(total)
            rows = conn.execute(
                "SELECT table_name, COUNT(*) as c FROM _fulltext GROUP BY table_name ORDER BY c DESC LIMIT 50"
            ).fetchall()
            status["top_tables"] = [{"table": r[0], "count": int(r[1])} for r in rows]
        except Exception:
            status["fulltext_count"] = 0
            status["top_tables"] = []
        finally:
            conn.close()
    except Exception as exc:
        status["error_fulltext"] = str(exc)
    return status


def get_current_db_context_response(*, require_selected=False, require_exists=False, allowed_engines=None):
    try:
        return get_current_db_context(
            require_selected=require_selected,
            require_exists=require_exists,
            allowed_engines=allowed_engines,
        ), None
    except (ValueError, FileNotFoundError) as exc:
        return None, (jsonify({"error": str(exc)}), 400)


def parse_int_query_arg(raw_value, field_name, *, default=None, minimum=None):
    if raw_value is None or raw_value == "":
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return value


def parse_search_request_args(args):
    q = (args.get("q") or "").strip()
    if not q:
        raise ValueError("query param q required")
    per_table = parse_int_query_arg(args.get("per_table", 10), "per_table", default=10, minimum=1)
    candidate_limit = parse_int_query_arg(
        args.get("candidate_limit", 1000),
        "candidate_limit",
        default=1000,
        minimum=1,
    )
    total_limit = parse_int_query_arg(args.get("total_limit", 500), "total_limit", default=500, minimum=1)
    token_mode = (args.get("token_mode", "any") or "any").lower()
    if token_mode not in ("any", "all"):
        token_mode = "any"
    min_score_raw = args.get("min_score")
    min_score = None
    if min_score_raw not in (None, ""):
        min_score = parse_int_query_arg(min_score_raw, "min_score", minimum=0)
    tables_param = args.get("tables")
    tables = None
    if tables_param:
        tables = [t.strip() for t in tables_param.split(",") if t.strip()]
    return {
        "q": q,
        "per_table": per_table,
        "candidate_limit": candidate_limit,
        "total_limit": total_limit,
        "token_mode": token_mode,
        "min_score": min_score,
        "tables": tables,
    }


def parse_table_request_args(args):
    try:
        limit = parse_int_query_arg(args.get("limit", 50), "limit", default=50, minimum=0)
        offset = parse_int_query_arg(args.get("offset", 0), "offset", default=0, minimum=0)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    order = (args.get("order", "ASC") or "ASC").upper()
    if order not in ("ASC", "DESC"):
        order = "ASC"
    return {
        "limit": limit,
        "offset": offset,
        "col": args.get("col"),
        "q": args.get("q"),
        "sort": args.get("sort"),
        "order": order,
    }


def sanitize_filename(value):
    if value is None:
        return ""
    return secure_filename(str(value))

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "static"), static_url_path="")

# Simple in-memory logs for UI status modal
_CLIENT_LOGS = []
_SERVER_LOGS = []

# ---------------- Static files ----------------
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/track_record")
def track_record():
    """Página dedicada para rastrear um registro em vários bancos.

    O HTML correspondente fica em static/track_record.html.
    """
    return app.send_static_file("track_record.html")


@app.route("/compare_dbs")
def compare_dbs_page():
    """Página para comparar diferenças entre dois bancos DuckDB.

    O HTML correspondente fica em static/compare_dbs.html.
    """
    return app.send_static_file("compare_dbs.html")


@app.route("/client/log", methods=["POST"])
def client_log():
    """Recebe logs da UI (nivel + mensagem) e guarda em memoria.

    Usado apenas pelo modal "Alertas e logs" da tela principal.
    """
    try:
        data = request.get_json(silent=True) or {}
        level = str(data.get("level", "info")).lower()
        msg = str(data.get("msg", "")).strip()
        if not msg:
            return jsonify({"ok": False, "error": "mensagem vazia"}), 400

        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": msg,
        }

        _CLIENT_LOGS.append(entry)
        if len(_CLIENT_LOGS) > 500:
            del _CLIENT_LOGS[: len(_CLIENT_LOGS) - 500]

        # espelha em _SERVER_LOGS para aparecer junto no modal
        _SERVER_LOGS.append(entry)
        if len(_SERVER_LOGS) > 500:
            del _SERVER_LOGS[: len(_SERVER_LOGS) - 500]

        # também registra no log do Flask
        if level == "error":
            app.logger.error("CLIENT: %s", msg)
        elif level in ("warn", "warning"):
            app.logger.warning("CLIENT: %s", msg)
        else:
            app.logger.info("CLIENT: %s", msg)

        return jsonify({"ok": True})
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Erro em /client/log: %s", exc)
        return jsonify({"ok": False, "error": "exception"}), 500


@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    """Snapshot simples de logs para o modal de status."""
    try:
        return jsonify({"ok": True, "logs": list(_SERVER_LOGS[-500:])})
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Erro em /admin/logs: %s", exc)
        return jsonify({"ok": False, "error": "exception"}), 500


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

# ---------------- Helpers ----------------
def duckdb_connect(path):
    # return connection (caller must close)
    return duckdb.connect(str(path))

def sqlite_connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = None
    return conn


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def looks_like_sqlite_file(path):
    try:
        with Path(path).open("rb") as fh:
            return fh.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def detect_db_engine(path):
    ext = Path(path).suffix.lower()
    if ext in ACCESS_EXTENSIONS:
        return "access"
    if ext in SQLITE_EXTENSIONS:
        return "sqlite"
    if ext in DUCKDB_EXTENSIONS:
        return "duckdb"
    if ext == ".db":
        return "sqlite" if looks_like_sqlite_file(path) else "duckdb"
    return ""


def list_tables_duckdb(path):
    """Lista tabelas de um arquivo DuckDB."""
    conn = duckdb_connect(path)
    try:
        rows = conn.execute("SHOW TABLES").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_tables_sqlite(path):
    """Lista tabelas de um arquivo SQLite."""
    conn = sqlite_connect(path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_tables_for_path(path):
    engine = detect_db_engine(path)
    if engine == "duckdb":
        return list_tables_duckdb(path)
    if engine == "sqlite":
        return list_tables_sqlite(path)
    if engine == "access":
        return list_tables_access(path)
    raise ValueError(f"Unsupported DB format: {path}")


def read_table_page_duckdb(path, table, limit, offset, col, q, sort, order):
    conn = duckdb_connect(path)
    try:
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if table not in tables:
            raise LookupError(f"table not found: {table}")

        quoted_table = quote_identifier(table)
        cur = conn.execute(f"SELECT * FROM {quoted_table} LIMIT 0")
        cols = [c[0] for c in cur.description]

        params = []
        where_clause = ""
        if col and q:
            if col not in cols:
                raise ValueError(f"column not found: {col}")
            where_clause = f"WHERE CAST({quote_identifier(col)} AS VARCHAR) ILIKE ?"
            params.append(f"%{q}%")

        order_clause = ""
        if sort:
            if sort not in cols:
                raise ValueError(f"sort column not found: {sort}")
            order_clause = f"ORDER BY {quote_identifier(sort)} {order}"

        count_sql = f"SELECT COUNT(*) FROM {quoted_table}"
        if where_clause:
            count_sql += f" {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        data_sql = f"SELECT * FROM {quoted_table}"
        if where_clause:
            data_sql += f" {where_clause}"
        if order_clause:
            data_sql += f" {order_clause}"
        if limit > 0:
            data_sql += f" LIMIT {limit} OFFSET {offset}"

        rows = conn.execute(data_sql, params).fetchall()
        return cols, rows, int(total)
    finally:
        conn.close()


def read_table_page_sqlite(path, table, limit, offset, col, q, sort, order):
    conn = sqlite_connect(path)
    try:
        tables = list_tables_sqlite(path)
        if table not in tables:
            raise LookupError(f"table not found: {table}")

        quoted_table = quote_identifier(table)
        cur = conn.execute(f"SELECT * FROM {quoted_table} LIMIT 0")
        cols = [desc[0] for desc in cur.description or []]

        params = []
        where_clause = ""
        if col and q:
            if col not in cols:
                raise ValueError(f"column not found: {col}")
            where_clause = f"WHERE CAST({quote_identifier(col)} AS TEXT) LIKE ? COLLATE NOCASE"
            params.append(f"%{q}%")

        order_clause = ""
        if sort:
            if sort not in cols:
                raise ValueError(f"sort column not found: {sort}")
            order_clause = f"ORDER BY {quote_identifier(sort)} {order}"

        count_sql = f"SELECT COUNT(*) FROM {quoted_table}"
        if where_clause:
            count_sql += f" {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        data_sql = f"SELECT * FROM {quoted_table}"
        if where_clause:
            data_sql += f" {where_clause}"
        if order_clause:
            data_sql += f" {order_clause}"
        if limit > 0:
            data_sql += " LIMIT ? OFFSET ?"
            params = [*params, limit, offset]

        rows = conn.execute(data_sql, params).fetchall()
        return cols, rows, int(total)
    finally:
        conn.close()


def read_table_page_for_path(path, table, limit, offset, col, q, sort, order):
    engine = detect_db_engine(path)
    if engine == "duckdb":
        return read_table_page_duckdb(path, table, limit, offset, col, q, sort, order)
    if engine == "sqlite":
        return read_table_page_sqlite(path, table, limit, offset, col, q, sort, order)
    raise ValueError(f"Table view only supported for DuckDB/SQLite. Current DB: {path}")


def build_sqlite_search_where(columns, tokens, token_mode):
    if not tokens or not columns:
        return "", []
    token_clauses = []
    params = []
    for token in tokens:
        column_checks = []
        for column in columns:
            column_checks.append(f"CAST({quote_identifier(column)} AS TEXT) LIKE ? COLLATE NOCASE")
            params.append(f"%{token}%")
        token_clauses.append("(" + " OR ".join(column_checks) + ")")
    joiner = " OR " if token_mode == "any" else " AND "
    return "WHERE " + joiner.join(token_clauses), params


def fallback_search_sqlite(
    sqlite_path,
    q,
    per_table=10,
    candidate_limit=1000,
    total_limit=500,
    token_mode="any",
    min_score=None,
    tables=None,
    max_tables=250,
    max_rows_per_table=2000,
):
    q_norm = normalize_text(q)
    tokens = [t for t in q_norm.split() if t]
    allowed_tables = {str(t).strip() for t in tables or [] if str(t).strip()} or None
    results = {}
    candidate_count = 0
    returned_count = 0
    conn = None
    try:
        conn = sqlite_connect(sqlite_path)
        table_names = list_tables_sqlite(sqlite_path)
        if allowed_tables is not None:
            table_names = [name for name in table_names if name in allowed_tables]
        table_names = table_names[:max_tables]
        if not table_names:
            return {"q": q, "q_norm": q_norm, "candidate_count": 0, "returned_count": 0, "results": {}}

        for table_name in table_names:
            pragma_rows = conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
            cols = [row[1] for row in pragma_rows if len(row) > 1 and row[1]]
            if not cols:
                continue
            where_sql, params = build_sqlite_search_where(cols, tokens, token_mode)
            sql = f"SELECT * FROM {quote_identifier(table_name)}"
            if where_sql:
                sql += f" {where_sql}"
            sql += f" LIMIT {max_rows_per_table}"
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                continue

            table_results = []
            for row in rows:
                row_json = {}
                row_text_parts = []
                for index, column in enumerate(cols):
                    value = row[index] if index < len(row) else None
                    row_json[column] = value
                    row_text_parts.append(normalize_text(serialize_value(value)))
                row_text = " ".join(part for part in row_text_parts if part)
                score = fuzz.token_set_ratio(q_norm, row_text)
                if min_score is not None and score < min_score:
                    continue
                table_results.append({"score": int(score), "row": row_json})
                candidate_count += 1
                if candidate_count >= candidate_limit:
                    break
            if table_results:
                table_results.sort(key=lambda item: item["score"], reverse=True)
                results[table_name] = table_results[:per_table]
                returned_count += len(results[table_name])
                if returned_count >= total_limit or candidate_count >= candidate_limit:
                    break

        priority_tables = cfg.get("priority_tables", []) or []
        ordered = {}
        for table_name in priority_tables:
            if table_name in results:
                ordered[table_name] = results.pop(table_name)
        for table_name in sorted(
            results.keys(),
            key=lambda name: max([item["score"] for item in results[name]]) if results[name] else 0,
            reverse=True,
        ):
            ordered[table_name] = results[table_name]
        return {
            "q": q,
            "q_norm": q_norm,
            "candidate_count": candidate_count,
            "returned_count": returned_count,
            "results": ordered,
        }
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        if conn is not None:
            conn.close()

def list_tables_access(path):
    """Lista tabelas de um banco Access via ODBC (pyodbc)."""
    if pyodbc is None:
        raise RuntimeError("pyodbc not installed")
    conn = None
    conn_strs = [
        fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};",
        fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={path};",
    ]
    last_err = None
    for cs in conn_strs:
        try:
            conn = pyodbc.connect(cs, autocommit=True, timeout=30)
            break
        except Exception as e:
            last_err = e
            conn = None
    if conn is None:
        raise RuntimeError(f"ODBC connect failed: {last_err}")
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
            # fallback via MSysObjects
            try:
                rows = cur.execute("SELECT Name FROM MSysObjects WHERE Type In (1,4) AND Flags = 0").fetchall()
                tables = [r[0] for r in rows]
            except Exception:
                tables = []
        return tables
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ---------------- Admin endpoints ----------------
@app.route("/admin/list_uploads", methods=["GET"])
def admin_list_uploads():
    files = []
    for p in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.name):
        if p.is_file():
            st = p.stat()
            files.append({
                "name": p.name,
                "path": str(p),
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
    return jsonify({
        "uploads": files,
        "current_db": get_db_path(),
        "priority_tables": cfg.get("priority_tables", []),
        "auto_index_after_convert": cfg.get("auto_index_after_convert", True),
    })

@app.route("/admin/status", methods=["GET"])
def admin_status():
    return jsonify(build_admin_status())


@app.route("/api/record_dirs", methods=["GET"])
def api_record_dirs():
    """Lista diretórios pré-configurados para rastrear registros em vários bancos.

    Apenas diretórios existentes são retornados, para evitar opções quebradas na UI.
    """
    items = []
    for key, meta in RECORD_DIRS.items():
        path = Path(meta["path"]).resolve()
        if path.exists() and path.is_dir():
            items.append({
                "id": key,
                "label": meta.get("label", key),
                "path": str(path),
            })
    return jsonify({"dirs": items})


@app.route("/api/browse_dirs", methods=["GET"])
def api_browse_dirs():
    """Explorador simples de diretórios para escolha de pasta de bancos.

    Semelhante a um file picker, mas rodando no backend. Quando
    `path` não é informado, em Windows lista as unidades disponíveis
    (C:\\, D:\\, ...). Quando `path` é um diretório válido, lista
    os subdiretórios imediatos e indica se cada um contém arquivos
    com extensões suportadas (SUPPORTED_EXTS).
    """
    base = (request.args.get("path") or "").strip()
    entries = []
    parent = None

    # Sem caminho: listar unidades no Windows ou raiz em outros SOs
    if not base:
        roots = []
        if os.name == "nt":  # Windows
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{c}:\\"
                if os.path.exists(drive):
                    roots.append(drive)
        else:
            roots.append(str(Path("/")))
        for r in roots:
            entries.append({"name": r, "path": r, "has_db": False})
    else:
        p = Path(base)
        if not p.exists() or not p.is_dir():
            return jsonify({"error": f"diretorio invalido: {base}"}), 400
        # calcula pasta pai (se existir)
        if p.parent != p:
            parent = str(p.parent)
        # lista subdiretórios
        try:
            for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
                if not child.is_dir():
                    continue
                has_db = False
                try:
                    for sub in child.iterdir():
                        if sub.is_file() and sub.suffix.lower() in SUPPORTED_EXTS:
                            has_db = True
                            break
                except Exception:
                    has_db = False
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "has_db": has_db,
                })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return jsonify({"entries": entries, "parent": parent, "path": base or None})

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    global convert_thread
    if 'file' not in request.files:
        return jsonify({"error": "arquivo não enviado"}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({"error": "nome de arquivo inválido"}), 400
    filename = sanitize_filename(f.filename)
    if not filename:
        return jsonify({"error": "nome de arquivo inválido"}), 400
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"extensão não permitida: {ext}"}), 400
    converter = convert_access_to_duckdb
    if ext in (".mdb", ".accdb") and converter is None:
        return jsonify({"error": "Conversão não disponível: access_convert.py ausente ou dependências não instaladas"}), 500
    dest = UPLOAD_DIR / filename
    f.save(dest)
    # duckdb -> select immediately
    if ext in (".duckdb", ".db", ".sqlite", ".sqlite3"):
        set_db_path(str(dest))
        return jsonify({"ok": True, "db_path": str(dest)})
    # access -> convert in background if converter available
    if ext in (".mdb", ".accdb"):
        with convert_lock:
            if convert_status.get("running"):
                return jsonify({"error": "Já existe uma conversão em execução"}), 409
            active_converter = converter
            if active_converter is None:
                return jsonify({"error": "Conversão não disponível: access_convert.py ausente ou dependências não instaladas"}), 500
            out_duckdb = UPLOAD_DIR / f"{Path(filename).stem}.duckdb"
            convert_status.update({
                "running": True, "ok": None, "msg": "started",
                "input": str(dest), "output": str(out_duckdb),
                "total_tables": 0, "processed_tables": 0, "current_table": "", "percent": 0
            })
            def progress_cb(p):
                with convert_lock:
                    convert_status.update({k: v for k, v in p.items() if k in ("total_tables", "processed_tables", "current_table", "percent", "msg")})
            def run_convert():
                global convert_status
                try:
                    ok, msg = active_converter(str(dest), str(out_duckdb), chunk_size=20000, progress_callback=progress_cb)
                    with convert_lock:
                        convert_status["running"] = False
                        convert_status["ok"] = bool(ok)
                        convert_status["msg"] = msg
                        convert_status["percent"] = 100 if ok else convert_status.get("percent", 0)
                    if ok:
                        set_db_path(str(out_duckdb))
                        # optional auto-index with create_or_resume_fulltext
                        indexer = create_or_resume_fulltext
                        if cfg.get("auto_index_after_convert", True) and indexer is not None:
                            # reutiliza o mesmo mecanismo de indexação monitorado por /admin/status
                            global index_thread
                            with index_lock:
                                if not index_thread or not index_thread.is_alive():
                                    def run_index_auto():
                                        try:
                                            indexer(str(out_duckdb), drop=False, chunk=2000, batch_insert=1000)
                                        except Exception as e:
                                            app.logger.exception("auto index failed: %s", e)
                                    index_thread = threading.Thread(target=run_index_auto, daemon=True)
                                    index_thread.start()
                except Exception as e:
                    with convert_lock:
                        convert_status["running"] = False
                        convert_status["ok"] = False
                        convert_status["msg"] = f"exception: {e}"
            convert_thread = threading.Thread(target=run_convert, daemon=True)
            convert_thread.start()
        return jsonify({"ok": True, "status": "converting", "input": str(dest), "output": str(out_duckdb)})
    return jsonify({"error": f"extensão não permitida: {ext}"}), 400

@app.route("/admin/select", methods=["POST"])
def admin_select():
    data = request.get_json() or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        return jsonify({"error": "filename required"}), 400
    fpath = UPLOAD_DIR / safe_filename
    if not fpath.exists():
        return jsonify({"error": "arquivo não encontrado"}), 404
    # set as current DB (duckdb or access). Frontend /api/tables will handle listing with fallback.
    set_db_path(str(fpath))
    return jsonify({"ok": True, "db_path": str(fpath)})

@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    data = request.get_json() or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    safe = sanitize_filename(filename)
    if not safe:
        return jsonify({"error": "invalid filename or path"}), 400
    target = UPLOAD_DIR / safe
    try:
        target.resolve().relative_to(UPLOAD_DIR.resolve())
    except Exception:
        return jsonify({"error": "invalid filename or path"}), 400
    if not target.exists():
        return jsonify({"error": "arquivo não encontrado"}), 404
    try:
        current = get_db_path()
        if current and Path(current).resolve() == target.resolve():
            clear_db_path()
        target.unlink()
        # remove converted duckdb with same stem
        duck_out = UPLOAD_DIR / f"{target.stem}.duckdb"
        if duck_out.exists():
            try:
                duck_out.unlink()
            except Exception:
                pass
        return jsonify({"ok": True, "deleted": str(target.name)})
    except Exception as e:
        return jsonify({"error": f"falha ao apagar: {e}"}), 500


@app.route("/admin/set_auto_index", methods=["POST"])
def admin_set_auto_index():
    """Ativa ou desativa a indexacao automatica apos conversao de Access.

    Usado pelo toggle "Auto indexacao apos conversao (Access)" na interface.
    """
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", False))
    cfg["auto_index_after_convert"] = enabled
    save_config(cfg)
    return jsonify({"ok": True, "auto_index_after_convert": enabled})

@app.route("/admin/set_priority", methods=["POST"])
def admin_set_priority():
    data = request.get_json() or {}
    tables = data.get("tables")
    if isinstance(tables, str):
        lst = [t.strip() for t in tables.split(",") if t.strip()]
    elif isinstance(tables, list):
        lst = [str(t).strip() for t in tables]
    else:
        return jsonify({"error": "tables param required"}), 400
    cfg["priority_tables"] = lst
    save_config(cfg)
    return jsonify({"ok": True, "priority_tables": lst})

@app.route("/admin/start_index", methods=["POST"])
def admin_start_index():
    # Se não conseguimos importar create_or_resume_fulltext em nenhum lugar, indexador indisponível
    if create_or_resume_fulltext is None:
        return jsonify({"error": "indexador não disponível (create_fulltext.py ausente)"}), 500
    data = request.get_json() or {}
    drop = bool(data.get("drop", False))
    try:
        chunk = int(data.get("chunk", 2000))
        batch = int(data.get("batch", 1000))
    except (TypeError, ValueError):
        return jsonify({"error": "chunk/batch must be integers"}), 400
    global index_thread
    with index_lock:
        if index_thread and index_thread.is_alive():
            return jsonify({"error": "indexação já em execução"}), 409
        ctx, error_response = get_current_db_context_response(require_selected=True, require_exists=True)
        if error_response is not None:
            return error_response
        if ctx["db_engine"] != "duckdb":
            return jsonify({"error": "indexacao _fulltext disponivel apenas para DuckDB"}), 400
        indexer = create_or_resume_fulltext
        def run_index():
            try:
                indexer(ctx["db_path"], drop=drop, chunk=chunk, batch_insert=batch)
            except Exception as e:
                app.logger.exception("Indexação falhou: %s", e)
        index_thread = threading.Thread(target=run_index, daemon=True)
        index_thread.start()
    return jsonify({"ok": True, "started": True, "db": get_db_path()})


@app.route("/api/find_record_across_dbs", methods=["POST"])
def api_find_record_across_dbs():
    """Endpoint que usa find_record_across_dbs para rastrear um registro.

    Espera JSON com pelo menos:
      - custom_path: caminho absoluto de um diretório a varrer (obrigatório)
      - filters: string no formato "COL1=VAL1,COL2=VAL2"
      - table (opcional): restringe a busca a uma tabela específica
    """
    data = request.get_json() or {}
    custom_path = (data.get("custom_path") or "").strip() or None
    filters_str = (data.get("filters") or "").strip()
    table = (data.get("table") or "").strip() or None
    max_files = int(data.get("max_files", 500))

    if not filters_str:
        return jsonify({"error": "filters obrigatorio"}), 400

    if not custom_path:
        return jsonify({"error": "custom_path obrigatorio"}), 400

    base_dir = Path(custom_path).expanduser().resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        return jsonify({"error": f"diretorio invalido: {base_dir}"}), 400

    res = find_record_across_dbs(base_dir, filters_str, table=table, max_files=max_files)
    if isinstance(res, dict) and res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.route("/api/compare_db_tables", methods=["POST"])
def api_compare_db_tables():
    """Retorna tabelas em comum e colunas para cada uma.

    Payload esperado:
    {
      "db1_path": "C:/caminho/para/a.duckdb",
      "db2_path": "C:/caminho/para/b.duckdb"
    }
    """
    data = request.get_json(silent=True) or {}
    db1_path = (data.get("db1_path") or "").strip()
    db2_path = (data.get("db2_path") or "").strip()

    if not db1_path or not db2_path:
        return jsonify({"error": "db1_path e db2_path são obrigatórios"}), 400

    try:
        db1 = Path(db1_path)
        db2 = Path(db2_path)

        missing = []
        if not db1.exists():
            missing.append(str(db1))
        if not db2.exists():
            missing.append(str(db2))
        if missing:
            msg = "arquivo(s) não encontrado(s): " + ", ".join(missing)
            app.logger.warning("compare_db_tables: %s", msg)
            return jsonify({"error": msg}), 400

        tables = list_common_tables(db1, db2)
        detailed = []
        for t in tables:
            cols = list_table_columns(db1, t)
            detailed.append({"name": t, "columns": cols})
        return jsonify({"tables": detailed})
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Erro em api_compare_db_tables")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/compare_db_table_content", methods=["POST"])
def api_compare_db_table_content():
    """Compara o conteúdo de uma tabela entre dois bancos DuckDB sem usar chave.

    Payload esperado:
    {
      "db1_path": "...",
      "db2_path": "...",
      "table": "NOME_TABELA"
    }
    """
    data = request.get_json(silent=True) or {}
    db1_path = (data.get("db1_path") or "").strip()
    db2_path = (data.get("db2_path") or "").strip()
    table = (data.get("table") or "").strip()
    if not db1_path or not db2_path:
        return jsonify({"error": "db1_path e db2_path são obrigatórios"}), 400
    if not table:
        return jsonify({"error": "table é obrigatório"}), 400
    try:
        db1 = Path(db1_path)
        db2 = Path(db2_path)

        missing = []
        if not db1.exists():
            missing.append(str(db1))
        if not db2.exists():
            missing.append(str(db2))
        if missing:
            msg = "arquivo(s) não encontrado(s): " + ", ".join(missing)
            app.logger.warning("compare_db_table_content: %s", msg)
            return jsonify({"error": msg}), 400

        result = compare_table_content_duckdb(db1, db2, table)
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Erro em api_compare_db_table_content")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/compare_db_rows", methods=["POST"])
def api_compare_db_rows():
    """Compara linhas de uma tabela entre dois bancos DuckDB.

    Payload esperado:
    {
      "db1_path": "...",
      "db2_path": "...",
      "table": "NOME_TABELA",
    "key_columns": ["COL1", "COL2"],
    "compare_columns": ["COL3", "COL4"]   # opcional
    }
    """
    data = request.get_json(silent=True) or {}
    db1_path = (data.get("db1_path") or "").strip()
    db2_path = (data.get("db2_path") or "").strip()
    table = (data.get("table") or "").strip()
    key_columns = data.get("key_columns") or []
    compare_columns = data.get("compare_columns")
    row_limit = data.get("row_limit")
    key_filter_str = (data.get("key_filter") or "").strip()
    change_types = data.get("change_types")
    changed_column = (data.get("changed_column") or "").strip() or None
    page = data.get("page") or 1
    page_size = data.get("page_size")

    if not db1_path or not db2_path:
        return jsonify({"error": "db1_path e db2_path são obrigatórios"}), 400
    if not table:
        return jsonify({"error": "table é obrigatório"}), 400
    if not isinstance(key_columns, list) or not key_columns:
        return jsonify({"error": "key_columns deve ser uma lista não vazia"}), 400
    if any(not isinstance(col, str) or not col.strip() for col in key_columns):
        return jsonify({"error": "key_columns deve conter apenas strings nao vazias"}), 400
    key_columns = [col.strip() for col in key_columns]
    if compare_columns is not None and not isinstance(compare_columns, list):
        return jsonify({"error": "compare_columns deve ser uma lista"}), 400
    if compare_columns is not None:
        if any(not isinstance(col, str) or not col.strip() for col in compare_columns):
            return jsonify({"error": "compare_columns deve conter apenas strings nao vazias"}), 400
        compare_columns = [col.strip() for col in compare_columns]

    # row_limit é opcional; quando informado deve ser inteiro >= 0
    if row_limit is not None:
        try:
            row_limit = int(row_limit)
        except (TypeError, ValueError):
            return jsonify({"error": "row_limit deve ser um inteiro"}), 400
        if row_limit < 0:
            return jsonify({"error": "row_limit deve ser maior ou igual a zero"}), 400

    # paginação opcional: página (>=1) e tamanho da página (>=1)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    if page_size is not None:
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            return jsonify({"error": "page_size deve ser um inteiro"}), 400
        if page_size < 1:
            return jsonify({"error": "page_size deve ser maior ou igual a 1"}), 400
    else:
        # se não informado, usamos row_limit (quando houver) ou um padrão seguro
        if isinstance(row_limit, int) and row_limit > 0:
            page_size = row_limit
        else:
            page_size = 100

    # valida opcionalmente a lista de tipos de mudança
    valid_types = {"added", "removed", "changed"}
    if change_types is not None:
        if not isinstance(change_types, list):
            return jsonify({"error": "change_types deve ser uma lista"}), 400
        invalid_change_types = [str(t) for t in change_types if str(t) not in valid_types]
        if invalid_change_types:
            return jsonify({
                "error": "change_types contem valores invalidos",
                "invalid": invalid_change_types,
            }), 400
        change_types = [str(t) for t in change_types]

    key_filter = {}
    if key_filter_str:
        for part in key_filter_str.split(","):
            p = part.strip()
            if not p:
                continue
            if "=" not in p:
                return jsonify({"error": "key_filter deve usar o formato COL=VAL"}), 400
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                return jsonify({"error": "key_filter contem coluna vazia"}), 400
            if not v:
                return jsonify({"error": f"key_filter sem valor para a coluna {k}"}), 400
            if k not in key_columns:
                return jsonify({"error": f"key_filter usa coluna fora de key_columns: {k}"}), 400
            if k in key_filter:
                return jsonify({"error": f"key_filter repetiu a coluna {k}"}), 400
            key_filter[k] = v

    try:
        db1 = Path(db1_path)
        db2 = Path(db2_path)

        missing = []
        if not db1.exists():
            missing.append(str(db1))
        if not db2.exists():
            missing.append(str(db2))
        if missing:
            msg = "arquivo(s) não encontrado(s): " + ", ".join(missing)
            app.logger.warning("compare_db_rows: %s", msg)
            return jsonify({"error": msg}), 400

        result = compare_table_duckdb_paged(
            db1,
            db2,
            table,
            key_columns,
            compare_columns,
            key_filter=key_filter,
            change_types=change_types,
            changed_column=changed_column,
            page=page,
            page_size=page_size,
        )
        return jsonify(result)
    except duckdb.IOException as exc:  # erros específicos de acesso ao arquivo DuckDB
        msg = str(exc)
        # Caso mais comum em Windows: arquivo já aberto por outro processo
        if "File is already open" in msg or "já está sendo usado" in msg:
            friendly = (
                "Não foi possível abrir um dos bancos DuckDB porque o arquivo "
                "já está em uso por outro processo. Feche a outra janela/instância "
                "que está usando o arquivo e tente novamente. Detalhes técnicos: "
                f"{msg}"
            )
            app.logger.warning("Banco em uso em api_compare_db_rows: %s", msg)
            return jsonify({"error": "banco_em_uso", "message": friendly}), 409
        app.logger.exception("DuckDB IOException em api_compare_db_rows")
        return jsonify({"error": "duckdb_io", "message": msg}), 500
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Erro em api_compare_db_rows")
        return jsonify({"error": "erro_interno", "message": str(exc)}), 500

# ---------------- Search + table endpoints ----------------
@app.route("/api/tables", methods=["GET"])
def api_tables():
    ctx, error_response = get_current_db_context_response(require_selected=True, require_exists=True)
    if error_response is not None:
        return error_response
    try:
        tables = list_tables_for_path(ctx["db_path"])
        return jsonify({"tables": tables, "db_engine": ctx["db_engine"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/table", methods=["GET"])
def api_table():
    table = request.args.get("name")
    if not table:
        return jsonify({"error": "table name required (?name=TABLE_NAME)"}), 400
    ctx, error_response = get_current_db_context_response(require_selected=True, require_exists=True)
    if error_response is not None:
        return error_response
    if ctx["db_engine"] not in {"duckdb", "sqlite"}:
        return jsonify({"error": f"Table view only supported for DuckDB/SQLite. Current DB: {ctx['db_path']}"}), 400
    try:
        page_args = parse_table_request_args(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        cols, rows, total = read_table_page_for_path(
            ctx["db_path"],
            table,
            page_args["limit"],
            page_args["offset"],
            page_args["col"],
            page_args["q"],
            page_args["sort"],
            page_args["order"],
        )

        data = []
        for r in rows:
            row_obj = {}
            for i, cname in enumerate(cols):
                try:
                    row_obj[cname] = serialize_value(r[i])
                except Exception:
                    row_obj[cname] = None
            data.append(row_obj)

        return jsonify({
            "table": table,
            "total": int(total),
            "limit": page_args["limit"],
            "offset": page_args["offset"],
            "columns": cols,
            "rows": data,
            "db_engine": ctx["db_engine"],
        })
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def api_search_duckdb(q, per_table, candidate_limit, total_limit, token_mode, min_score, tables=None):
    q_norm = normalize_text(q)
    tokens = [t for t in q_norm.split() if t]
    if tokens:
        if token_mode == "any":
            # Modo "qualquer": pelo menos um token precisa bater, mas o
            # último termo digitado pelo usuário é tratado como obrigatório.
            # Isso evita resultados que ignorem completamente, por exemplo,
            # o "SVP" em "AUX_UNIDAD SVP".
            where_parts = ["content_norm LIKE ?" for _ in tokens]
            base_where = " OR ".join(where_parts)
            params = [f"%{t}%" for t in tokens]
            last_tok = tokens[-1]
            where_sql = f"({base_where}) AND content_norm LIKE ?"
            params.append(f"%{last_tok}%")
        else:
            where_parts = ["content_norm LIKE ?" for _ in tokens]
            where_sql = " AND ".join(where_parts)
            params = [f"%{t}%" for t in tokens]
    else:
        where_sql = "content_norm LIKE ?"
        params = [f"%{q_norm}%"]
    # Ao montar os candidatos SQL, já priorizamos as tabelas marcadas em priority_tables
    priority_tables = cfg.get("priority_tables", []) or []
    if priority_tables:
        in_placeholders = ",".join(["?"] * len(priority_tables))
        sql = (
            "SELECT table_name, pk_col, pk_value, row_offset, content_norm, row_json "
            f"FROM _fulltext WHERE {where_sql} "
            f"ORDER BY CASE WHEN table_name IN ({in_placeholders}) THEN 0 ELSE 1 END, table_name "
            f"LIMIT {candidate_limit}"
        )
        # Atenção: os parâmetros do WHERE vêm primeiro, depois os do IN, na ordem dos placeholders.
        sql_params = params + list(priority_tables)
    else:
        sql = (
            "SELECT table_name, pk_col, pk_value, row_offset, content_norm, row_json "
            f"FROM _fulltext WHERE {where_sql} LIMIT {candidate_limit}"
        )
        sql_params = params
    conn = None
    try:
        conn = duckdb_connect(get_db_path())
        rows = conn.execute(sql, sql_params).fetchall()
    except Exception as e:
        return {"error": f"search failed: {e}"}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Filtro opcional por lista de tabelas (tables=[...])
    allowed_tables = None
    if tables:
        allowed_tables = {str(t).strip() for t in tables if str(t).strip()}
        if allowed_tables:
            rows = [r for r in rows if r[0] in allowed_tables]
    candidates = []
    for r in rows:
        table_name, pk_col, pk_value, row_offset, content_norm, row_json = r
        # Score principal: similaridade fuzzy entre a query normalizada e o
        # conteúdo normalizado da linha inteira.
        score = fuzz.token_set_ratio(q_norm, content_norm)
        if min_score is not None and score < min_score:
            continue
        # Cobertura/força de match por tokens: quantos tokens da query estão
        # presentes em content_norm e se TODOS estão presentes. Isso ajuda a
        # priorizar, por exemplo, linhas que contenham "svp" quando a consulta
        # é "aux_unidad svp".
        coverage = 0
        has_all = 0
        if tokens:
            try:
                for tok in tokens:
                    if tok and tok in content_norm:
                        coverage += 1
                if coverage == len(tokens):
                    has_all = 1
            except Exception:
                coverage = 0
                has_all = 0
        candidates.append({
            "score": score,
            "coverage": coverage,
            "has_all": has_all,
            "table": table_name,
            "pk_col": pk_col,
            "pk_value": pk_value,
            "row_json": row_json,
        })
    # Ordena dando prioridade para linhas que contenham TODOS os tokens da
    # consulta, depois maior cobertura e, por fim, maior score fuzzy.
    candidates.sort(key=lambda x: (x.get("has_all", 0), x.get("coverage", 0), x["score"]), reverse=True)
    grouped = {}
    table_max = {}
    total_count = 0
    for c in candidates:
        if total_count >= total_limit:
            break
        t = c["table"]
        if t not in grouped:
            grouped[t] = []
            table_max[t] = c["score"]
        if per_table > 0 and len(grouped[t]) >= per_table:
            continue
        try:
            row_obj = json.loads(c["row_json"])
        except Exception:
            row_obj = None
        grouped[t].append({"score": c["score"], "row": row_obj})
        if c["score"] > table_max.get(t, 0):
            table_max[t] = c["score"]
        total_count += 1

    # Garante que cada tabela prioritária com candidatos apareça pelo menos com 1 linha,
    # mesmo que tenha ficado de fora pelo corte de total_limit acima.
    priority_tables = cfg.get("priority_tables", []) or []
    if priority_tables:
        for p in priority_tables:
            if allowed_tables and p not in allowed_tables:
                continue
            if p in grouped:
                continue
            best = None
            for c in candidates:
                if c["table"] == p:
                    # mesmo critério de ordenação usado acima (has_all, coverage, score)
                    if best is None or (c.get("has_all", 0), c.get("coverage", 0), c["score"]) > (best.get("has_all", 0), best.get("coverage", 0), best["score"]):
                        best = c
            if best is not None:
                try:
                    row_obj = json.loads(best["row_json"])
                except Exception:
                    row_obj = None
                grouped[p] = [{"score": best["score"], "row": row_obj}]
                table_max[p] = best["score"]
                total_count += 1

    # apply priority ordering
    ordered = {}
    for p in priority_tables:
        if p in grouped:
            ordered[p] = grouped.pop(p)
    remaining = sorted(grouped.keys(), key=lambda x: table_max.get(x, 0), reverse=True)
    for t in remaining:
        ordered[t] = grouped[t]
    return {"q": q, "q_norm": q_norm, "candidate_count": len(candidates), "returned_count": total_count, "results": ordered}

# Fallback search for Access DBs via ODBC (pyodbc)
def fallback_search_access(access_path, q, per_table=10, candidate_limit=1000, total_limit=500, token_mode="any", min_score=None, max_tables=500, max_rows_per_table=2000):
    if pyodbc is None:
        return {"error": "pyodbc not installed; fallback unavailable"}
    q_norm = q.lower()
    tokens = [t for t in q_norm.split() if t]
    results = {}
    candidate_count = 0
    returned_count = 0
    conn = None
    try:
        conn_strs = [
            fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};",
            fr"Driver={{Microsoft Access Driver (*.mdb)}};DBQ={access_path};",
        ]
        last_err = None
        for cs in conn_strs:
            try:
                conn = pyodbc.connect(cs, autocommit=True, timeout=30)
                break
            except Exception as e:
                last_err = e
                conn = None
        if conn is None:
            return {"error": f"ODBC connect failed: {last_err}"}
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
                tables = []
        if not tables:
            return {"error": "No user tables found in Access DB."}
        tables = tables[:max_tables]
        def build_where_for_columns(cols):
            if not tokens:
                return None
            parts = []
            for col in cols:
                if token_mode == "any":
                    parts.append(" OR ".join([f"{col} LIKE ?" for _ in tokens]))
                else:
                    parts.append(" AND ".join([f"{col} LIKE ?" for _ in tokens]))
            return "(" + " OR ".join(parts) + ")" if parts else None
        for t in tables:
            cols = []
            try:
                cols_info = cur.columns(table=t)
                for c in cols_info:
                    col_name = getattr(c, "column_name", None) or (c[3] if len(c) > 3 else None)
                    data_type = None
                    try:
                        data_type = getattr(c, "type_name", None) or (c[5] if len(c) > 5 else None)
                    except Exception:
                        data_type = None
                    if col_name:
                        cols.append((col_name, str(data_type).upper() if data_type else ""))
            except Exception:
                try:
                    sample = cur.execute(f"SELECT TOP 1 * FROM [{t}]").fetchone()
                    if sample is not None:
                        desc = [d[0] for d in cur.description]
                        cols = [(name, "") for name in desc]
                except Exception:
                    cols = []
            text_cols = [c for c, dt in cols if any(x in dt for x in ("CHAR","TEXT","VARCHAR","MEMO"))] if cols else []
            search_cols = text_cols if text_cols else [c for c, _ in cols] if cols else []
            if not search_cols:
                continue
            where_sql = build_where_for_columns(search_cols)
            params = []
            if where_sql:
                for _ in search_cols:
                    for tok in tokens:
                        params.append(f"%{tok}%")
                sql = f"SELECT TOP {max_rows_per_table} * FROM [{t}] WHERE {where_sql}"
            else:
                sql = f"SELECT TOP {max_rows_per_table} * FROM [{t}]"
            try:
                rows = cur.execute(sql, params).fetchall() if params else cur.execute(sql).fetchall()
            except Exception:
                try:
                    rows = cur.execute(f"SELECT TOP {max_rows_per_table} * FROM [{t}]").fetchall()
                except Exception:
                    rows = []
            if not rows:
                continue
            desc = [d[0] for d in cur.description] if cur.description else []
            table_results = []
            for r in rows:
                try:
                    row_vals = [("" if v is None else str(v)) for v in r]
                    row_text = " ".join(row_vals).lower()
                except Exception:
                    row_text = str(r).lower()
                score = fuzz.token_set_ratio(q_norm, row_text)
                if min_score is not None and score < min_score:
                    continue
                pk_col = None
                pk_val = None
                try:
                    if "id" in [c.lower() for c in desc]:
                        idx = [c.lower() for c in desc].index("id")
                        pk_col = desc[idx]
                        pk_val = r[idx]
                    else:
                        pk_col = desc[0] if desc else None
                        pk_val = r[0] if len(r) > 0 else None
                except Exception:
                    pass
                row_json = {}
                try:
                    for i, cname in enumerate(desc):
                        row_json[cname] = r[i]
                except Exception:
                    row_json = {"row": str(r)}
                table_results.append({"score": int(score), "pk_col": pk_col, "pk_value": pk_val, "row": row_json})
                candidate_count += 1
                if candidate_count >= candidate_limit:
                    break
            if table_results:
                table_results.sort(key=lambda x: x["score"], reverse=True)
                results[t] = table_results[:per_table]
                returned_count += len(results[t])
                if returned_count >= total_limit:
                    break
        priority_tables = cfg.get("priority_tables", []) or []
        ordered = {}
        for p in priority_tables:
            if p in results:
                ordered[p] = results.pop(p)
        for t in sorted(results.keys(), key=lambda x: max([it["score"] for it in results[x]]) if results[x] else 0, reverse=True):
            ordered[t] = results[t]
        return {"q": q, "q_norm": q_norm, "candidate_count": candidate_count, "returned_count": returned_count, "results": ordered}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

@app.route("/api/search", methods=["GET"])
def api_search():
    try:
        search_args = parse_search_request_args(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    ctx, error_response = get_current_db_context_response(require_selected=True, require_exists=True)
    if error_response is not None:
        return error_response
    if ctx["db_engine"] == "duckdb":
        return jsonify(
            api_search_duckdb(
                search_args["q"],
                search_args["per_table"],
                search_args["candidate_limit"],
                search_args["total_limit"],
                search_args["token_mode"],
                search_args["min_score"],
                tables=search_args["tables"],
            )
        )
    if ctx["db_engine"] == "sqlite":
        return jsonify(
            fallback_search_sqlite(
                ctx["db_path"],
                search_args["q"],
                per_table=search_args["per_table"],
                candidate_limit=search_args["candidate_limit"],
                total_limit=search_args["total_limit"],
                token_mode=search_args["token_mode"],
                min_score=search_args["min_score"],
                tables=search_args["tables"],
            )
        )
    if ctx["db_engine"] == "access":
        fb = fallback_search_access(
            ctx["db_path"],
            search_args["q"],
            per_table=search_args["per_table"],
            candidate_limit=search_args["candidate_limit"],
            total_limit=search_args["total_limit"],
            token_mode=search_args["token_mode"],
            min_score=search_args["min_score"],
        )
        if isinstance(fb, dict) and fb.get("error"):
            return jsonify({"error": fb.get("error")}), 500
        return jsonify(fb)
    return jsonify({"error": f"Unsupported DB format: {ctx['db_path']}"}), 400

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
