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
import threading
from pathlib import Path
import sys
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import duckdb
from rapidfuzz import fuzz

# Garante que o diretório raiz do projeto esteja em sys.path, para que
# possamos importar access_convert.py e create_fulltext.py mesmo rodando
# este app a partir da pasta "interface".
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Optional modules
try:
    import pyodbc
except Exception:
    pyodbc = None

try:
    from access_convert import convert_access_to_duckdb
except Exception:
    convert_access_to_duckdb = None

try:
    from create_fulltext import create_or_resume_fulltext
except Exception:
    create_or_resume_fulltext = None

try:
    from utils import normalize_text, serialize_value
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
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CONFIG_FILE = BASE_DIR / "config.json"
ALLOWED_EXTENSIONS = {".duckdb", ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"}

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

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"db_path": str(BASE_DIR / "minha.duckdb"), "priority_tables": [], "auto_index_after_convert": True}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

cfg = load_config()
# sanitize priority_tables
if not isinstance(cfg.get("priority_tables"), list):
    cfg["priority_tables"] = []
else:
    cfg["priority_tables"] = [t for t in cfg["priority_tables"] if t and t != "None"]
save_config(cfg)

def get_db_path():
    return os.environ.get("DB_PATH") or cfg.get("db_path")

def set_db_path(p):
    cfg["db_path"] = str(p)
    save_config(cfg)

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "static"), static_url_path="")

# ---------------- Static files ----------------
@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

# ---------------- Helpers ----------------
def duckdb_connect(path):
    # return connection (caller must close)
    return duckdb.connect(str(path))

def list_tables_duckdb(path):
    """Lista tabelas de um arquivo DuckDB/SQLite."""
    try:
        conn = duckdb_connect(path)
        try:
            rows = conn.execute("SHOW TABLES").fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()
    except Exception as e:
        raise

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
            files.append({"name": p.name, "path": str(p), "size": p.stat().st_size})
    return jsonify({
        "uploads": files,
        "current_db": cfg.get("db_path"),
        "priority_tables": cfg.get("priority_tables", []),
        "auto_index_after_convert": cfg.get("auto_index_after_convert", True)
    })

@app.route("/admin/status", methods=["GET"])
def admin_status():
    status = {"indexing": False, "db": get_db_path(), "fulltext_count": 0, "top_tables": []}
    with index_lock:
        if index_thread and index_thread.is_alive():
            status["indexing"] = True
    # try _fulltext info
    try:
        conn = duckdb_connect(get_db_path())
        try:
            total = conn.execute("SELECT COUNT(*) FROM _fulltext").fetchone()[0]
            status["fulltext_count"] = int(total)
            rows = conn.execute("SELECT table_name, COUNT(*) as c FROM _fulltext GROUP BY table_name ORDER BY c DESC LIMIT 50").fetchall()
            status["top_tables"] = [{"table": r[0], "count": int(r[1])} for r in rows]
        except Exception:
            status["fulltext_count"] = 0
            status["top_tables"] = []
        finally:
            conn.close()
    except Exception as e:
        status["error_fulltext"] = str(e)
    with convert_lock:
        status["conversion"] = dict(convert_status)
    status["priority_tables"] = cfg.get("priority_tables", [])
    status["auto_index_after_convert"] = cfg.get("auto_index_after_convert", True)
    return jsonify(status)

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    global convert_thread
    if 'file' not in request.files:
        return jsonify({"error": "arquivo não enviado"}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({"error": "nome de arquivo inválido"}), 400
    filename = secure_filename(f.filename)
    ext = Path(filename).suffix.lower()
    dest = UPLOAD_DIR / filename
    f.save(dest)
    # duckdb -> select immediately
    if ext == ".duckdb":
        set_db_path(str(dest))
        return jsonify({"ok": True, "db_path": str(dest)})
    # access -> convert in background if converter available
    if ext in (".mdb", ".accdb"):
        if convert_access_to_duckdb is None:
            return jsonify({"error": "Conversão não disponível: access_convert.py ausente ou dependências não instaladas"}), 500
        with convert_lock:
            if convert_status.get("running"):
                return jsonify({"error": "Já existe uma conversão em execução"}), 409
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
                    ok, msg = convert_access_to_duckdb(str(dest), str(out_duckdb), chunk_size=20000, progress_callback=progress_cb)
                    with convert_lock:
                        convert_status["running"] = False
                        convert_status["ok"] = bool(ok)
                        convert_status["msg"] = msg
                        convert_status["percent"] = 100 if ok else convert_status.get("percent", 0)
                    if ok:
                        set_db_path(str(out_duckdb))
                        # optional auto-index with create_or_resume_fulltext
                        if cfg.get("auto_index_after_convert", True) and create_or_resume_fulltext:
                            # reutiliza o mesmo mecanismo de indexação monitorado por /admin/status
                            global index_thread
                            with index_lock:
                                if not index_thread or not index_thread.is_alive():
                                    def run_index_auto():
                                        try:
                                            create_or_resume_fulltext(str(out_duckdb), drop=False, chunk=2000, batch_insert=1000)
                                        except Exception as e:
                                            print("auto index failed:", e)
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
    fpath = UPLOAD_DIR / secure_filename(filename)
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
    safe = secure_filename(filename)
    target = UPLOAD_DIR / safe
    try:
        target.resolve().relative_to(UPLOAD_DIR.resolve())
    except Exception:
        return jsonify({"error": "invalid filename or path"}), 400
    if not target.exists():
        return jsonify({"error": "arquivo não encontrado"}), 404
    try:
        current = cfg.get("db_path")
        if current and Path(current).resolve() == target.resolve():
            cfg["db_path"] = ""
            save_config(cfg)
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
    if create_fulltext is None and create_or_resume_fulltext is None:
        return jsonify({"error": "indexador não disponível (create_fulltext.py ausente)"}), 500
    data = request.get_json() or {}
    drop = bool(data.get("drop", False))
    chunk = int(data.get("chunk", 2000))
    batch = int(data.get("batch", 1000))
    global index_thread
    with index_lock:
        if index_thread and index_thread.is_alive():
            return jsonify({"error": "indexação já em execução"}), 409
        dbpath = get_db_path()
        def run_index():
            try:
                if create_or_resume_fulltext:
                    create_or_resume_fulltext(dbpath, drop=drop, chunk=chunk, batch_insert=batch)
                else:
                    # attempt both names
                    try:
                        from create_fulltext import create_or_resume_fulltext as cf
                        cf(dbpath, drop=drop, chunk=chunk, batch_insert=batch)
                    except Exception as e:
                        print("index error:", e)
            except Exception as e:
                print("Indexação falhou:", e)
        index_thread = threading.Thread(target=run_index, daemon=True)
        index_thread.start()
    return jsonify({"ok": True, "started": True, "db": get_db_path()})

# ---------------- Search + table endpoints ----------------
@app.route("/api/tables", methods=["GET"])
def api_tables():
    dbpath = get_db_path()
    if not dbpath:
        return jsonify({"error": "No DB selected"}), 400
    ext = Path(dbpath).suffix.lower()
    try:
        if ext in (".duckdb", ".db", ".sqlite", ".sqlite3"):
            tables = list_tables_duckdb(dbpath)
        elif ext in (".mdb", ".accdb"):
            # Para Access, usamos o helper específico
            tables = list_tables_access(dbpath)
        else:
            return jsonify({"error": f"Unsupported DB format: {dbpath}"}), 400
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/table", methods=["GET"])
def api_table():
    table = request.args.get("name")
    if not table:
        return jsonify({"error": "table name required (?name=TABLE_NAME)"}), 400
    dbpath = get_db_path()
    if not dbpath:
        return jsonify({"error": "No DB selected"}), 400
    ext = Path(dbpath).suffix.lower()
    if ext not in (".duckdb", ".db", ".sqlite", ".sqlite3"):
        return jsonify({"error": f"Table view only supported for DuckDB/SQLite. Current DB: {dbpath}"}), 400
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except Exception:
        return jsonify({"error": "limit and offset must be integers"}), 400

    col = request.args.get("col")
    q = request.args.get("q")
    sort = request.args.get("sort")
    order = request.args.get("order", "ASC").upper()
    if order not in ("ASC", "DESC"):
        order = "ASC"

    try:
        conn = duckdb_connect(dbpath)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if table not in tables:
            conn.close()
            return jsonify({"error": f"table not found: {table}"}), 404

        # obter colunas
        cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
        cols = [c[0] for c in cur.description]

        params = []
        where_clause = ""
        if col and q:
            if col not in cols:
                conn.close()
                return jsonify({"error": f"column not found: {col}"}), 400
            where_clause = f'WHERE CAST("{col}" AS VARCHAR) ILIKE ?'
            params.append(f"%{q}%")

        order_clause = ""
        if sort:
            if sort not in cols:
                conn.close()
                return jsonify({"error": f"sort column not found: {sort}"}), 400
            order_clause = f'ORDER BY "{sort}" {order}'

        count_sql = f'SELECT COUNT(*) FROM "{table}"'
        if where_clause:
            count_sql += f" {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        data_sql = f'SELECT * FROM "{table}"'
        if where_clause:
            data_sql += f" {where_clause}"
        if order_clause:
            data_sql += f" {order_clause}"
        # LIMIT só se limit > 0 (0 significa ilimitado)
        if limit > 0:
            data_sql += f" LIMIT {limit} OFFSET {offset}"

        rows = conn.execute(data_sql, params).fetchall()
        conn.close()

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
            "limit": limit,
            "offset": offset,
            "columns": cols,
            "rows": data,
        })
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


def api_search_duckdb(q, per_table, candidate_limit, total_limit, token_mode, min_score, tables=None):
    q_norm = normalize_text(q)
    tokens = [t for t in q_norm.split() if t]
    if tokens:
        if token_mode == "any":
            where_parts = ["content_norm LIKE ?" for _ in tokens]
            where_sql = " OR ".join(where_parts)
            params = [f"%{t}%" for t in tokens]
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
    try:
        conn = duckdb_connect(get_db_path())
        rows = conn.execute(sql, sql_params).fetchall()
        conn.close()
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return {"error": f"search failed: {e}"}

    # Filtro opcional por lista de tabelas (tables=[...])
    allowed_tables = None
    if tables:
        allowed_tables = {str(t).strip() for t in tables if str(t).strip()}
        if allowed_tables:
            rows = [r for r in rows if r[0] in allowed_tables]
    candidates = []
    for r in rows:
        table_name, pk_col, pk_value, row_offset, content_norm, row_json = r
        score = fuzz.token_set_ratio(q_norm, content_norm)
        if min_score is not None and score < min_score:
            continue
        candidates.append({"score": score, "table": table_name, "pk_col": pk_col, "pk_value": pk_value, "row_json": row_json})
    candidates.sort(key=lambda x: x["score"], reverse=True)
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
                    if best is None or c["score"] > best["score"]:
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
                except:
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
            if not tokens: return None
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
                    except:
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
                    row_vals = [("" if v is None else str(v)) for v in r]; row_text = " ".join(row_vals).lower()
                except:
                    row_text = str(r).lower()
                score = fuzz.token_set_ratio(q_norm, row_text)
                if min_score is not None and score < min_score:
                    continue
                pk_col = None; pk_val = None
                try:
                    if "id" in [c.lower() for c in desc]:
                        idx = [c.lower() for c in desc].index("id"); pk_col = desc[idx]; pk_val = r[idx]
                    else:
                        pk_col = desc[0] if desc else None; pk_val = r[0] if len(r)>0 else None
                except:
                    pass
                row_json = {}
                try:
                    for i, cname in enumerate(desc):
                        row_json[cname] = r[i]
                except:
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
        try:
            conn.close()
        except:
            pass
        priority_tables = cfg.get("priority_tables", []) or []
        ordered = {}
        for p in priority_tables:
            if p in results:
                ordered[p] = results.pop(p)
        for t in sorted(results.keys(), key=lambda x: max([it["score"] for it in results[x]]) if results[x] else 0, reverse=True):
            ordered[t] = results[t]
        return {"q": q, "q_norm": q_norm, "candidate_count": candidate_count, "returned_count": returned_count, "results": ordered}
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return {"error": str(e)}

@app.route("/api/search", methods=["GET"])
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "query param q required"}), 400
    try:
        per_table = int(request.args.get("per_table", 10))
        candidate_limit = int(request.args.get("candidate_limit", 1000))
        total_limit = int(request.args.get("total_limit", 500))
    except:
        return jsonify({"error": "per_table/candidate_limit/total_limit must be integers"}), 400
    token_mode = request.args.get("token_mode", "any").lower()
    if token_mode not in ("any", "all"):
        token_mode = "any"
    try:
        min_score = request.args.get("min_score", None)
        min_score = int(min_score) if min_score is not None else None
    except:
        min_score = None

    # Filtro opcional de tabelas: ?tables=TAB1,TAB2
    tables_param = request.args.get("tables")
    tables = None
    if tables_param:
        tables = [t.strip() for t in tables_param.split(",") if t.strip()]
    dbpath = get_db_path()
    if not dbpath:
        return jsonify({"error": "No DB selected"}), 400
    ext = Path(dbpath).suffix.lower()
    if ext in (".duckdb", ".db", ".sqlite", ".sqlite3"):
        return jsonify(api_search_duckdb(q, per_table, candidate_limit, total_limit, token_mode, min_score, tables=tables))
    elif ext in (".mdb", ".accdb"):
        fb = fallback_search_access(dbpath, q, per_table=per_table, candidate_limit=candidate_limit, total_limit=total_limit, token_mode=token_mode, min_score=min_score)
        if isinstance(fb, dict) and fb.get("error"):
            return jsonify({"error": fb.get("error")}), 500
        return jsonify(fb)
    else:
        return jsonify({"error": f"Unsupported DB format: {dbpath}"}), 400

if __name__ == "__main__":
    save_config(cfg)
    app.run(host="127.0.0.1", port=5000, debug=True)