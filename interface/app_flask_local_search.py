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
import shutil
import sqlite3
import threading
import importlib.util
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
    compare_tables_overview_duckdb,
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
COMPARE_PAGE_SIZE_DEFAULT = 100
COMPARE_PAGE_SIZE_MAX = 1000

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


def ensure_config_defaults(config):
    if "db_path" not in config:
        config["db_path"] = ""
    if "priority_tables" not in config:
        config["priority_tables"] = []
    if "auto_index_after_convert" not in config:
        config["auto_index_after_convert"] = True
    return config


def sanitize_loaded_config(config):
    config = ensure_config_defaults(dict(config))
    if not isinstance(config.get("priority_tables"), list):
        config["priority_tables"] = []
    else:
        config["priority_tables"] = [item for item in config["priority_tables"] if item and item != "None"]

    db_path = config.get("db_path") or ""
    try:
        if db_path and not Path(db_path).exists():
            startup_warnings.append(f"db_path configurado nao existe mais: {db_path}")
            config["db_path"] = ""
    except Exception:
        startup_warnings.append("db_path configurado e invalido e foi descartado")
        config["db_path"] = ""
    return config


def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    else:
        cfg = {}
    return ensure_config_defaults(cfg)

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

cfg = sanitize_loaded_config(load_config())
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
    access_odbc = get_access_odbc_status()
    return {
        "access_fallback": pyodbc is not None,
        "access_conversion": convert_access_to_duckdb is not None,
        "access_parser_available": bool(has_access_parser_module()),
        "duckdb_fulltext": create_or_resume_fulltext is not None,
        "access_odbc_ready": bool(access_odbc.get("pyodbc_available") and access_odbc.get("access_driver_available")),
        "access_mdbtools_available": bool(has_mdbtools_binaries()),
    }


def has_mdbtools_binaries():
    return bool(shutil.which("mdb-tables") and shutil.which("mdb-export"))


def has_access_parser_module():
    return bool(
        importlib.util.find_spec("access_parser")
        or importlib.util.find_spec("access_parser_access")
    )


def get_access_odbc_status():
    status = {
        "platform": os.name,
        "pyodbc_available": pyodbc is not None,
        "access_driver_available": False,
        "drivers": [],
        "error": "",
    }
    if pyodbc is None:
        status["error"] = OPTIONAL_IMPORT_ERRORS.get("pyodbc", "pyodbc not installed")
        return status
    try:
        drivers = [str(d) for d in pyodbc.drivers()]
    except Exception as exc:
        status["error"] = f"cannot list ODBC drivers: {exc}"
        return status
    status["drivers"] = drivers
    status["access_driver_available"] = any(
        ("Access Driver" in d) or ("ACEODBC" in d.upper())
        for d in drivers
    )
    if not status["access_driver_available"]:
        status["error"] = "Access ODBC driver not found"
    return status


def evaluate_access_conversion_support(ext):
    ext_l = str(ext or "").lower().strip()
    if ext_l not in ACCESS_EXTENSIONS:
        return {"ready": False, "reason": f"unsupported access extension: {ext_l}"}

    odbc = get_access_odbc_status()
    mdbtools_ok = has_mdbtools_binaries()
    parser_ok = has_access_parser_module()
    converter_ok = convert_access_to_duckdb is not None
    if not converter_ok:
        reason = "access_convert module not available"
    elif ext_l == ".accdb":
        if odbc["pyodbc_available"] and odbc["access_driver_available"]:
            reason = ""
        elif parser_ok:
            reason = ""
        else:
            reason = "need pyodbc+Access ODBC or access-parser for .accdb"
    else:
        if odbc["pyodbc_available"] and odbc["access_driver_available"]:
            reason = ""
        elif mdbtools_ok:
            reason = ""
        elif parser_ok:
            reason = ""
        else:
            reason = "need pyodbc+Access ODBC or mdbtools or access-parser for .mdb"

    return {
        "ready": reason == "",
        "reason": reason,
        "converter_available": converter_ok,
        "odbc": odbc,
        "mdbtools_available": mdbtools_ok,
        "access_parser_available": parser_ok,
    }


def get_conversion_backend_preferred(accdb_precheck, mdb_precheck):
    accdb_precheck = accdb_precheck or {}
    mdb_precheck = mdb_precheck or {}
    accdb_odbc_ready = bool(
        accdb_precheck.get("odbc", {}).get("pyodbc_available")
        and accdb_precheck.get("odbc", {}).get("access_driver_available")
    )
    if accdb_odbc_ready:
        return "odbc"
    if bool(accdb_precheck.get("access_parser_available")):
        return "access_parser"
    if bool(mdb_precheck.get("mdbtools_available")):
        return "mdbtools"
    return "unavailable"


def parse_conversion_backend_from_msg(message):
    text = str(message or "").strip().lower()
    if not text:
        return ""
    if "via pyodbc" in text:
        return "pyodbc"
    if "via pypyodbc" in text:
        return "pypyodbc"
    if "via mdbtools" in text:
        return "mdbtools"
    if "via access-parser" in text:
        return "access_parser"
    return ""


def get_persisted_db_path():
    return str(cfg.get("db_path") or "")


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
    capabilities = get_runtime_capabilities()
    access_precheck = evaluate_access_conversion_support(".accdb")
    mdb_precheck = evaluate_access_conversion_support(".mdb")
    ctx = get_current_db_context()
    status = {
        "indexing": False,
        "db": ctx["db_path"],
        "persisted_db": get_persisted_db_path(),
        "db_exists": ctx["db_exists"],
        "db_engine": ctx["db_engine"],
        "fulltext_count": 0,
        "top_tables": [],
        "startup_warnings": list(startup_warnings),
        "capabilities": capabilities,
        "indexer_available": capabilities.get("duckdb_fulltext", False),
        "indexer_error": "",
        "access_precheck": access_precheck,
        "mdb_precheck": mdb_precheck,
        "odbc_enabled": bool(access_precheck.get("odbc", {}).get("pyodbc_available")),
        "conversion_mode": "odbc_preferred" if access_precheck.get("ready") else "pure_only",
        "conversion_backend_preferred": get_conversion_backend_preferred(
            access_precheck, mdb_precheck
        ),
        "conversion_backend_last": "",
    }
    if not capabilities.get("duckdb_fulltext", False):
        status["indexer_error"] = OPTIONAL_IMPORT_ERRORS.get(
            "create_fulltext", "indexador indisponivel"
        )
    with index_lock:
        if index_thread and index_thread.is_alive():
            status["indexing"] = True
    with convert_lock:
        status["conversion"] = dict(convert_status)
    status["conversion_backend_last"] = parse_conversion_backend_from_msg(
        status.get("conversion", {}).get("msg")
    )
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


def normalize_priority_tables(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("tables param required")


def parse_enabled_flag(data, field_name="enabled"):
    """Converte um campo booleano da requisicao com validação explicita."""
    if not isinstance(data, dict):
        raise ValueError(f"{field_name} invalido")
    if field_name not in data:
        raise ValueError(f"{field_name} e obrigatorio")

    value = data.get(field_name)
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "on", "ativado", "sim", "s", "v"}:
            return True
        if normalized in {"0", "false", "f", "no", "off", "desativado", "nao", "n"}:
            return False
    if value is None:
        raise ValueError(f"{field_name} e obrigatorio")
    raise ValueError(f"{field_name} precisa ser um booleano valido")


def list_existing_record_dirs():
    items = []
    for key, meta in RECORD_DIRS.items():
        path = Path(meta["path"]).resolve()
        if path.exists() and path.is_dir():
            items.append({
                "id": key,
                "label": meta.get("label", key),
                "path": str(path),
                "has_db": dir_has_supported_file(path),
            })
    return items


def list_directory_roots():
    roots = []
    if os.name == "nt":
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{c}:\\"
            if os.path.exists(drive):
                roots.append(drive)
    else:
        roots.append(str(Path("/")))
    return [{"name": root, "path": root, "has_db": False} for root in roots]


def list_child_directories(base_path):
    if not isinstance(base_path, str):
        raise ValueError("base_path deve ser texto")
    if "\x00" in base_path:
        raise ValueError("base_path possui caractere invalido")

    path = Path(base_path).expanduser()
    path = path.resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ValueError(f"diretorio invalido: {base_path}")

    parent = str(path.parent) if path.parent != path else None
    entries = []
    try:
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
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
        raise RuntimeError(str(exc)) from exc

    return {"entries": entries, "parent": parent, "path": str(path)}


def validate_compare_db_inputs(db1_path, db2_path, route_name, *, allowed_engines=None):
    if not db1_path or not db2_path:
        raise ValueError("db1_path e db2_path sao obrigatorios")

    if allowed_engines is None:
        allowed_engines = {"duckdb"}
    allowed_engines = {str(engine).strip().lower() for engine in allowed_engines if str(engine).strip()}

    raw_paths = {
        "db1_path": Path(db1_path).expanduser().resolve(strict=False),
        "db2_path": Path(db2_path).expanduser().resolve(strict=False),
    }
    missing = []
    not_files = []
    unsupported = []
    for field, path in raw_paths.items():
        if not path.exists():
            missing.append(str(path))
            continue
        if not path.is_file():
            not_files.append(f"{field}={path}")
            continue
        engine = detect_db_engine(path)
        if allowed_engines and engine not in allowed_engines:
            engine_name = engine or "desconhecido"
            unsupported.append(f"{field}={path} ({engine_name})")

    if missing:
        message = "arquivo(s) não encontrado(s): " + ", ".join(missing)
        app.logger.warning("%s: %s", route_name, message)
        raise FileNotFoundError(message)
    if not_files:
        message = "caminho invalido (esperado arquivo): " + ", ".join(not_files)
        app.logger.warning("%s: %s", route_name, message)
        raise ValueError(message)
    if unsupported:
        allowed = ", ".join(sorted(allowed_engines))
        message = (
            "engine nao suportada para comparacao direta; converta para DuckDB antes de comparar. "
            f"Permitido(s): {allowed}. Recebido(s): {', '.join(unsupported)}"
        )
        app.logger.warning("%s: %s", route_name, message)
        raise ValueError(message)

    return raw_paths["db1_path"], raw_paths["db2_path"]


def get_current_db_context_response(*, require_selected=False, require_exists=False, allowed_engines=None):
    try:
        return get_current_db_context(
            require_selected=require_selected,
            require_exists=require_exists,
            allowed_engines=allowed_engines,
        ), None
    except (ValueError, FileNotFoundError) as exc:
        return None, (jsonify({"error": str(exc)}), 400)


def get_browse_db_context_response():
    return get_current_db_context_response(
        require_selected=True,
        require_exists=True,
        allowed_engines={"duckdb", "sqlite"},
    )


def get_search_db_context_response():
    return get_current_db_context_response(
        require_selected=True,
        require_exists=True,
        allowed_engines={"duckdb", "sqlite", "access"},
    )


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


def parse_track_request_args(data):
    filters_str = (data.get("filters") or "").strip()
    if not filters_str:
        raise ValueError("filters obrigatorio")

    custom_path = (data.get("custom_path") or "").strip()
    if not custom_path:
        raise ValueError("custom_path obrigatorio")

    table = (data.get("table") or "").strip() or None
    max_files = data.get("max_files", 500)
    try:
        max_files = int(max_files)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_files deve ser inteiro") from exc
    if max_files <= 0:
        raise ValueError("max_files deve ser > 0")

    base_dir = Path(custom_path).expanduser().resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise ValueError(f"diretorio invalido: {base_dir}")

    return {
        "base_dir": base_dir,
        "filters": filters_str,
        "table": table,
        "max_files": max_files,
    }


def parse_compare_key_filter(key_filter_str, key_columns):
    key_filter = {}
    if not key_filter_str:
        return key_filter
    for part in key_filter_str.split(","):
        p = part.strip()
        if not p:
            continue
        if "=" not in p:
            raise ValueError("key_filter deve usar o formato COL=VAL")
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise ValueError("key_filter contem coluna vazia")
        if not v:
            raise ValueError(f"key_filter sem valor para a coluna {k}")
        if k not in key_columns:
            raise ValueError(f"key_filter usa coluna fora de key_columns: {k}")
        if k in key_filter:
            raise ValueError(f"key_filter repetiu a coluna {k}")
        key_filter[k] = v
    return key_filter


def parse_compare_rows_request(data):
    db1_path = (data.get("db1_path") or "").strip()
    db2_path = (data.get("db2_path") or "").strip()
    table = (data.get("table") or "").strip()
    key_columns = data.get("key_columns") or []
    compare_columns = data.get("compare_columns")
    row_limit = data.get("row_limit")
    key_filter_str = (data.get("key_filter") or "").strip()
    change_types = data.get("change_types")
    changed_column = (data.get("changed_column") or "").strip() or None
    page = data.get("page", 1)
    page_size = data.get("page_size")

    db1, db2 = validate_compare_db_inputs(db1_path, db2_path, "compare_db_rows")
    if not table:
        raise ValueError("table é obrigatório")
    if not isinstance(key_columns, list) or not key_columns:
        raise ValueError("key_columns deve ser uma lista não vazia")
    if any(not isinstance(col, str) or not col.strip() for col in key_columns):
        raise ValueError("key_columns deve conter apenas strings nao vazias")
    key_columns = [col.strip() for col in key_columns]

    if compare_columns is not None and not isinstance(compare_columns, list):
        raise ValueError("compare_columns deve ser uma lista")
    if compare_columns is not None:
        if any(not isinstance(col, str) or not col.strip() for col in compare_columns):
            raise ValueError("compare_columns deve conter apenas strings nao vazias")
        compare_columns = [col.strip() for col in compare_columns]

    if row_limit is not None:
        try:
            row_limit = int(row_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("row_limit deve ser um inteiro") from exc
        if row_limit < 0:
            raise ValueError("row_limit deve ser maior ou igual a zero")

    try:
        page = int(page)
    except (TypeError, ValueError) as exc:
        raise ValueError("page deve ser um inteiro") from exc
    if page < 1:
        raise ValueError("page deve ser maior ou igual a 1")

    if page_size is not None:
        try:
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("page_size deve ser um inteiro") from exc
        if page_size < 1:
            raise ValueError("page_size deve ser maior ou igual a 1")
        if page_size > COMPARE_PAGE_SIZE_MAX:
            raise ValueError("page_size deve ser no maximo %d" % COMPARE_PAGE_SIZE_MAX)
    else:
        if isinstance(row_limit, int) and row_limit > 0:
            if row_limit > COMPARE_PAGE_SIZE_MAX:
                raise ValueError("row_limit deve ser no maximo %d" % COMPARE_PAGE_SIZE_MAX)
            page_size = row_limit
        else:
            page_size = COMPARE_PAGE_SIZE_DEFAULT

    valid_types = {"added", "removed", "changed"}
    invalid_change_types = []
    if change_types is not None:
        if not isinstance(change_types, list):
            raise ValueError("change_types deve ser uma lista")
        invalid_change_types = [str(t) for t in change_types if str(t) not in valid_types]
        change_types = [str(t) for t in change_types]

    key_filter = parse_compare_key_filter(key_filter_str, key_columns)
    return {
        "db1": db1,
        "db2": db2,
        "table": table,
        "key_columns": key_columns,
        "compare_columns": compare_columns,
        "key_filter": key_filter,
        "change_types": change_types,
        "changed_column": changed_column,
        "page": page,
        "page_size": page_size,
        "invalid_change_types": invalid_change_types,
    }


def sanitize_filename(value):
    if value is None:
        return ""
    return secure_filename(str(value))


def dir_has_supported_file(path: Path) -> bool:
    """Retorna true se o diretorio contem algum arquivo com extensao suportada."""
    try:
        for entry in path.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTS:
                return True
    except Exception:
        return False
    return False


def list_uploaded_files():
    uploads = []
    for path in sorted(UPLOAD_DIR.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        stat_info = path.stat()
        uploads.append({
            "name": path.name,
            "path": str(path),
            "size": stat_info.st_size,
            "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
        })
    return uploads


def resolve_upload_target(filename, *, required=False):
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        raise ValueError("filename required" if required else "invalid filename or path")
    try:
        safe_path = Path(safe_filename)
        if safe_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("extensao invalida")
        if safe_path.name != safe_filename:
            raise ValueError("invalid filename or path")
    except Exception as exc:
        raise ValueError("invalid filename or path") from exc
    target = UPLOAD_DIR / safe_filename
    try:
        target.resolve().relative_to(UPLOAD_DIR.resolve())
    except Exception as exc:
        raise ValueError("invalid filename or path") from exc
    return target


def next_upload_dest(filename):
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        raise ValueError("invalid filename")

    base = Path(safe_filename).stem
    ext = Path(safe_filename).suffix
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"extensão não permitida: {ext}")

    candidate = UPLOAD_DIR / safe_filename
    if not candidate.exists():
        return candidate

    for idx in range(1, 1000):
        alt_name = f"{base}_{idx}{ext}"
        candidate = UPLOAD_DIR / alt_name
        if not candidate.exists():
            return candidate
    raise ValueError("não foi possivel encontrar nome unico para upload")


def should_select_uploaded_db(extension):
    return extension in {".duckdb", ".db", ".sqlite", ".sqlite3"}


def build_access_conversion_output(filename):
    return UPLOAD_DIR / f"{Path(filename).stem}.duckdb"


def maybe_start_auto_index(db_path):
    global index_thread
    indexer = create_or_resume_fulltext
    if not cfg.get("auto_index_after_convert", True) or indexer is None:
        return
    with index_lock:
        if index_thread and index_thread.is_alive():
            return

        def run_index_auto():
            try:
                indexer(str(db_path), drop=False, chunk=2000, batch_insert=1000)
            except Exception as exc:
                app.logger.exception("auto index failed: %s", exc)

        index_thread = threading.Thread(target=run_index_auto, daemon=True)
        index_thread.start()


def start_access_conversion(source_path, output_path, converter):
    global convert_thread, convert_status

    def progress_cb(progress):
        with convert_lock:
            convert_status.update({
                key: value
                for key, value in progress.items()
                if key in ("total_tables", "processed_tables", "current_table", "percent", "msg")
            })

    def run_convert():
        global convert_status
        try:
            ok, msg = converter(
                str(source_path),
                str(output_path),
                chunk_size=20000,
                progress_callback=progress_cb,
            )
            with convert_lock:
                convert_status["running"] = False
                convert_status["ok"] = bool(ok)
                convert_status["msg"] = msg
                convert_status["percent"] = 100 if ok else convert_status.get("percent", 0)
            if ok:
                set_db_path(str(output_path))
                maybe_start_auto_index(output_path)
        except Exception as exc:
            with convert_lock:
                convert_status["running"] = False
                convert_status["ok"] = False
                convert_status["msg"] = f"exception: {exc}"

    convert_thread = threading.Thread(target=run_convert, daemon=True)
    convert_thread.start()


def delete_upload_target(target):
    current = get_db_path()
    if current and Path(current).resolve() == target.resolve():
        clear_db_path()
    target.unlink()
    derived_duckdb = build_access_conversion_output(target.name)
    if derived_duckdb.exists():
        try:
            derived_duckdb.unlink()
        except Exception:
            pass

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "static"), static_url_path="")

# Simple in-memory logs for UI status modal
_CLIENT_LOGS = []
_SERVER_LOGS = []
LOG_LIMIT = 500

def build_log_entry(level, message):
    return {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": str(level or "info").lower(),
        "message": str(message or "").strip(),
    }


def append_capped_log(logs, entry):
    logs.append(entry)
    if len(logs) > LOG_LIMIT:
        del logs[: len(logs) - LOG_LIMIT]


def record_server_log(level, message, *, mirror_client=False):
    entry = build_log_entry(level, message)
    if not entry["message"]:
        return None
    append_capped_log(_SERVER_LOGS, entry)
    if mirror_client:
        append_capped_log(_CLIENT_LOGS, entry)
    return entry


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

        entry = record_server_log(level, msg, mirror_client=True)
        if entry is None:
            return jsonify({"ok": False, "error": "mensagem vazia"}), 400

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
        return jsonify({"ok": True, "logs": list(_SERVER_LOGS[-LOG_LIMIT:]), "count": len(_SERVER_LOGS)})
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


def get_priority_tables():
    return cfg.get("priority_tables", []) or []


def order_grouped_results(results, score_by_table):
    priority_tables = get_priority_tables()
    ordered = {}
    for table_name in priority_tables:
        if table_name in results:
            ordered[table_name] = results.pop(table_name)
    for table_name in sorted(results.keys(), key=lambda name: score_by_table.get(name, 0), reverse=True):
        ordered[table_name] = results[table_name]
    return ordered


def serialize_table_rows(columns, rows):
    data = []
    for row in rows:
        row_obj = {}
        for index, column in enumerate(columns):
            try:
                row_obj[column] = serialize_value(row[index])
            except Exception:
                row_obj[column] = None
        data.append(row_obj)
    return data


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
        return list_tables_duckdb_conn(conn)
    finally:
        conn.close()


def list_tables_sqlite(path):
    """Lista tabelas de um arquivo SQLite."""
    conn = sqlite_connect(path)
    try:
        return list_tables_sqlite_conn(conn)
    finally:
        conn.close()


def list_tables_duckdb_conn(conn):
    rows = conn.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]


def list_tables_sqlite_conn(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def list_tables_for_path(path):
    engine = detect_db_engine(path)
    if engine == "duckdb":
        return list_tables_duckdb(path)
    if engine == "sqlite":
        return list_tables_sqlite(path)
    if engine == "access":
        return list_tables_access(path)
    raise ValueError(f"Unsupported DB format: {path}")


def get_table_columns_duckdb(path, table):
    conn = duckdb_connect(path)
    try:
        return get_table_columns_duckdb_conn(conn, table)
    finally:
        conn.close()


def get_table_columns_sqlite(path, table):
    conn = sqlite_connect(path)
    try:
        return get_table_columns_sqlite_conn(conn, table)
    finally:
        conn.close()


def get_table_columns_duckdb_conn(conn, table):
    cur = conn.execute(f"SELECT * FROM {quote_identifier(table)} LIMIT 0")
    return [column[0] for column in cur.description]


def get_table_columns_sqlite_conn(conn, table):
    cur = conn.execute(f"SELECT * FROM {quote_identifier(table)} LIMIT 0")
    return [desc[0] for desc in cur.description or []]


def build_table_filter_clause(columns, col, q, cast_type):
    if not col or not q:
        return "", []
    if col not in columns:
        raise ValueError(f"column not found: {col}")
    if cast_type == "duckdb":
        return f"WHERE CAST({quote_identifier(col)} AS VARCHAR) ILIKE ?", [f"%{q}%"]
    return f"WHERE CAST({quote_identifier(col)} AS TEXT) LIKE ? COLLATE NOCASE", [f"%{q}%"]


def build_table_order_clause(columns, sort, order):
    if not sort:
        return ""
    if sort not in columns:
        raise ValueError(f"sort column not found: {sort}")
    return f"ORDER BY {quote_identifier(sort)} {order}"


def run_table_page_query(conn, quoted_table, columns, limit, offset, col, q, sort, order, cast_type, bind_limit):
    where_clause, params = build_table_filter_clause(columns, col, q, cast_type)
    order_clause = build_table_order_clause(columns, sort, order)

    count_sql = f"SELECT COUNT(*) FROM {quoted_table}"
    if where_clause:
        count_sql += f" {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    data_sql = f"SELECT * FROM {quoted_table}"
    data_params = list(params)
    if where_clause:
        data_sql += f" {where_clause}"
    if order_clause:
        data_sql += f" {order_clause}"
    if limit > 0:
        if bind_limit:
            data_sql += " LIMIT ? OFFSET ?"
            data_params.extend([limit, offset])
        else:
            data_sql += f" LIMIT {limit} OFFSET {offset}"

    rows = conn.execute(data_sql, data_params).fetchall()
    return rows, int(total)


def read_table_page_duckdb(path, table, limit, offset, col, q, sort, order):
    conn = duckdb_connect(path)
    try:
        tables = list_tables_duckdb_conn(conn)
        if table not in tables:
            raise LookupError(f"table not found: {table}")
        quoted_table = quote_identifier(table)
        cols = get_table_columns_duckdb_conn(conn, table)
        rows, total = run_table_page_query(
            conn,
            quoted_table,
            cols,
            limit,
            offset,
            col,
            q,
            sort,
            order,
            "duckdb",
            bind_limit=False,
        )
        return cols, rows, int(total)
    finally:
        conn.close()


def read_table_page_sqlite(path, table, limit, offset, col, q, sort, order):
    conn = sqlite_connect(path)
    try:
        tables = list_tables_sqlite_conn(conn)
        if table not in tables:
            raise LookupError(f"table not found: {table}")
        quoted_table = quote_identifier(table)
        cols = get_table_columns_sqlite_conn(conn, table)
        rows, total = run_table_page_query(
            conn,
            quoted_table,
            cols,
            limit,
            offset,
            col,
            q,
            sort,
            order,
            "sqlite",
            bind_limit=True,
        )
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


def build_search_response(q, q_norm, candidate_count, returned_count, results, score_by_table):
    return {
        "q": q,
        "q_norm": q_norm,
        "candidate_count": candidate_count,
        "returned_count": returned_count,
        "results": order_grouped_results(results, score_by_table),
    }


def score_search_content(q_norm, tokens, content_norm, min_score):
    score = fuzz.token_set_ratio(q_norm, content_norm)
    if min_score is not None and score < min_score:
        return None
    coverage = 0
    has_all = 0
    if tokens:
        for token in tokens:
            if token and token in content_norm:
                coverage += 1
        if coverage == len(tokens):
            has_all = 1
    return {
        "score": int(score),
        "coverage": coverage,
        "has_all": has_all,
    }


def build_score_by_table(results):
    return {
        table_name: max((item["score"] for item in items), default=0)
        for table_name, items in results.items()
    }


def select_access_search_columns(columns):
    text_columns = [
        column_name
        for column_name, data_type in columns
        if any(token in data_type for token in ("CHAR", "TEXT", "VARCHAR", "MEMO"))
    ]
    if text_columns:
        return text_columns
    return [column_name for column_name, _data_type in columns]


def build_access_row_payload(row, columns):
    row_json = {}
    try:
        for index, column_name in enumerate(columns):
            row_json[column_name] = row[index]
    except Exception:
        row_json = {"row": str(row)}
    return row_json


def build_access_row_text(row):
    try:
        row_values = [serialize_value(value) for value in row]
        return normalize_text(" ".join(row_values))
    except Exception:
        return normalize_text(str(row))


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
                scored = score_search_content(q_norm, tokens, row_text, min_score)
                if scored is None:
                    continue
                table_results.append({"score": scored["score"], "row": row_json})
                candidate_count += 1
                if candidate_count >= candidate_limit:
                    break
            if table_results:
                table_results.sort(key=lambda item: item["score"], reverse=True)
                results[table_name] = table_results[:per_table]
                returned_count += len(results[table_name])
                if returned_count >= total_limit or candidate_count >= candidate_limit:
                    break

        score_by_table = build_score_by_table(results)
        return build_search_response(q, q_norm, candidate_count, returned_count, results, score_by_table)
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
    current_db = get_db_path()
    return jsonify({
        "uploads": list_uploaded_files(),
        "current_db": current_db,
        "priority_tables": cfg.get("priority_tables", []),
        "auto_index_after_convert": cfg.get("auto_index_after_convert", True),
        "current_db_exists": bool(current_db) and Path(current_db).exists(),
    })

@app.route("/admin/status", methods=["GET"])
def admin_status():
    return jsonify(build_admin_status())


@app.route("/api/record_dirs", methods=["GET"])
def api_record_dirs():
    """Lista diretórios pré-configurados para rastrear registros em vários bancos.

    Apenas diretórios existentes são retornados, para evitar opções quebradas na UI.
    """
    return jsonify({"dirs": list_existing_record_dirs()})


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
    if not base:
        return jsonify({"entries": list_directory_roots(), "parent": None, "path": None})
    try:
        return jsonify(list_child_directories(base))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
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
    if ext in (".mdb", ".accdb"):
        precheck = evaluate_access_conversion_support(ext)
        if not precheck.get("ready"):
            return jsonify({
                "error": "Conversao Access indisponivel neste ambiente",
                "reason": precheck.get("reason", "precheck_failed"),
                "precheck": precheck,
            }), 503
    try:
        dest = next_upload_dest(filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    f.save(dest)
    if should_select_uploaded_db(ext):
        set_db_path(str(dest))
        return jsonify({"ok": True, "db_path": str(dest)})
    if ext in (".mdb", ".accdb"):
        with convert_lock:
            if convert_status.get("running"):
                return jsonify({"error": "Já existe uma conversão em execução"}), 409
            active_converter = converter
            if active_converter is None:
                return jsonify({"error": "Conversão não disponível: access_convert.py ausente ou dependências não instaladas"}), 500
            out_duckdb = build_access_conversion_output(dest.name)
            convert_status.update({
                "running": True, "ok": None, "msg": "started",
                "input": str(dest), "output": str(out_duckdb),
                "total_tables": 0, "processed_tables": 0, "current_table": "", "percent": 0
            })
            start_access_conversion(dest, out_duckdb, active_converter)
        return jsonify({"ok": True, "status": "converting", "input": str(dest), "output": str(out_duckdb)})
    return jsonify({"error": f"extensão não permitida: {ext}"}), 400


@app.route("/admin/access_precheck", methods=["GET"])
def admin_access_precheck():
    ext = (request.args.get("ext") or ".accdb").strip().lower()
    if ext not in ACCESS_EXTENSIONS:
        return jsonify({"error": f"extensao access invalida: {ext}"}), 400
    report = evaluate_access_conversion_support(ext)
    return jsonify({"ok": True, "ext": ext, "precheck": report})

@app.route("/admin/select", methods=["POST"])
def admin_select():
    data = request.get_json() or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    try:
        fpath = resolve_upload_target(filename, required=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not fpath.exists():
        return jsonify({"error": "arquivo não encontrado"}), 404
    set_db_path(str(fpath))
    return jsonify({"ok": True, "db_path": str(fpath)})

@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    data = request.get_json() or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    try:
        target = resolve_upload_target(filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not target.exists():
        return jsonify({"error": "arquivo não encontrado"}), 404
    try:
        delete_upload_target(target)
        return jsonify({"ok": True, "deleted": str(target.name)})
    except Exception as e:
        return jsonify({"error": f"falha ao apagar: {e}"}), 500


@app.route("/admin/set_auto_index", methods=["POST"])
def admin_set_auto_index():
    """Ativa ou desativa a indexacao automatica apos conversao de Access.

    Usado pelo toggle "Auto indexacao apos conversao (Access)" na interface.
    """
    data = request.get_json() or {}
    try:
        enabled = parse_enabled_flag(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    cfg["auto_index_after_convert"] = enabled
    save_config(cfg)
    return jsonify({"ok": True, "auto_index_after_convert": enabled})

@app.route("/admin/set_priority", methods=["POST"])
def admin_set_priority():
    data = request.get_json() or {}
    try:
        lst = normalize_priority_tables(data.get("tables"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
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
    try:
        track_args = parse_track_request_args(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    res = find_record_across_dbs(
        track_args["base_dir"],
        track_args["filters"],
        table=track_args["table"],
        max_files=track_args["max_files"],
    )
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

    try:
        db1, db2 = validate_compare_db_inputs(db1_path, db2_path, "compare_db_tables")
        tables = list_common_tables(db1, db2)
        detailed = []
        for t in tables:
            cols = list_table_columns(db1, t)
            detailed.append({"name": t, "columns": cols})
        return jsonify({"tables": detailed})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
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
    if not table:
        return jsonify({"error": "table é obrigatório"}), 400
    try:
        db1, db2 = validate_compare_db_inputs(db1_path, db2_path, "compare_db_table_content")
        result = compare_table_content_duckdb(db1, db2, table)
        return jsonify(result)
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Erro em api_compare_db_table_content")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/compare_db_overview", methods=["POST"])
def api_compare_db_overview():
    """Retorna overview de diferenca por tabela para dois bancos DuckDB."""
    data = request.get_json(silent=True) or {}
    db1_path = (data.get("db1_path") or "").strip()
    db2_path = (data.get("db2_path") or "").strip()
    raw_tables = data.get("tables")
    tables = None
    if raw_tables is not None:
        if not isinstance(raw_tables, list):
            return jsonify({"error": "tables deve ser uma lista"}), 400
        tables = [str(item).strip() for item in raw_tables if str(item).strip()]

    try:
        db1, db2 = validate_compare_db_inputs(db1_path, db2_path, "compare_db_overview")
        overview = compare_tables_overview_duckdb(db1, db2, tables=tables)
        return jsonify({"overview": overview})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Erro em api_compare_db_overview")
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
    try:
        compare_request = parse_compare_rows_request(data)
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400

    invalid_change_types = compare_request["invalid_change_types"]
    if invalid_change_types:
        return jsonify({
            "error": "change_types contem valores invalidos",
            "invalid": invalid_change_types,
        }), 400

    try:
        result = compare_table_duckdb_paged(
            compare_request["db1"],
            compare_request["db2"],
            compare_request["table"],
            compare_request["key_columns"],
            compare_request["compare_columns"],
            key_filter=compare_request["key_filter"],
            change_types=compare_request["change_types"],
            changed_column=compare_request["changed_column"],
            page=compare_request["page"],
            page_size=compare_request["page_size"],
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
    ctx, error_response = get_browse_db_context_response()
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
    ctx, error_response = get_browse_db_context_response()
    if error_response is not None:
        return error_response
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

        return jsonify({
            "table": table,
            "total": int(total),
            "limit": page_args["limit"],
            "offset": page_args["offset"],
            "columns": cols,
            "rows": serialize_table_rows(cols, rows),
            "db_engine": ctx["db_engine"],
        })
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def api_search_duckdb(db_path, q, per_table, candidate_limit, total_limit, token_mode, min_score, tables=None):
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
        conn = duckdb_connect(db_path)
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
        scored = score_search_content(q_norm, tokens, content_norm, min_score)
        if scored is None:
            continue
        candidates.append({
            "score": scored["score"],
            "coverage": scored["coverage"],
            "has_all": scored["has_all"],
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

    return build_search_response(q, q_norm, len(candidates), total_count, grouped, table_max)

# Fallback search for Access DBs via ODBC (pyodbc)
def fallback_search_access(
    access_path,
    q,
    per_table=10,
    candidate_limit=1000,
    total_limit=500,
    token_mode="any",
    min_score=None,
    tables=None,
    max_tables=500,
    max_rows_per_table=2000,
):
    if pyodbc is None:
        return {"error": "pyodbc not installed; fallback unavailable"}
    q_norm = normalize_text(q)
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
        allowed_tables = {str(t).strip() for t in tables or [] if str(t).strip()} or None
        if allowed_tables is not None:
            tables = [name for name in tables if name in allowed_tables]
        if not tables:
            return {"q": q, "q_norm": q_norm, "candidate_count": 0, "returned_count": 0, "results": {}}
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
            if candidate_count >= candidate_limit or returned_count >= total_limit:
                break
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
            search_cols = select_access_search_columns(cols) if cols else []
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
                row_text = build_access_row_text(r)
                scored = score_search_content(q_norm, tokens, row_text, min_score)
                if scored is None:
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
                row_json = build_access_row_payload(r, desc)
                table_results.append({"score": scored["score"], "pk_col": pk_col, "pk_value": pk_val, "row": row_json})
                candidate_count += 1
                if candidate_count >= candidate_limit:
                    break
            if table_results:
                table_results.sort(key=lambda x: x["score"], reverse=True)
                results[t] = table_results[:per_table]
                returned_count += len(results[t])
                if returned_count >= total_limit:
                    break
        score_by_table = build_score_by_table(results)
        return build_search_response(q, q_norm, candidate_count, returned_count, results, score_by_table)
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def run_search_for_context(ctx, search_args):
    if ctx["db_engine"] == "duckdb":
        payload = api_search_duckdb(
            ctx["db_path"],
            search_args["q"],
            search_args["per_table"],
            search_args["candidate_limit"],
            search_args["total_limit"],
            search_args["token_mode"],
            search_args["min_score"],
            tables=search_args["tables"],
        )
        return payload, None
    if ctx["db_engine"] == "sqlite":
        payload = fallback_search_sqlite(
            ctx["db_path"],
            search_args["q"],
            per_table=search_args["per_table"],
            candidate_limit=search_args["candidate_limit"],
            total_limit=search_args["total_limit"],
            token_mode=search_args["token_mode"],
            min_score=search_args["min_score"],
            tables=search_args["tables"],
        )
        return payload, None
    if ctx["db_engine"] == "access":
        payload = fallback_search_access(
            ctx["db_path"],
            search_args["q"],
            per_table=search_args["per_table"],
            candidate_limit=search_args["candidate_limit"],
            total_limit=search_args["total_limit"],
            token_mode=search_args["token_mode"],
            min_score=search_args["min_score"],
            tables=search_args["tables"],
        )
        if isinstance(payload, dict) and payload.get("error"):
            error_text = str(payload.get("error") or "")
            lowered = error_text.lower()
            if "pyodbc" in lowered or "odbc" in lowered or "driver" in lowered:
                return {
                    "error": error_text,
                    "hint": "Access search unavailable in this environment. Convert to DuckDB first.",
                }, 503
            return {"error": error_text}, 500
        return payload, None
    return {"error": f"Unsupported DB format: {ctx['db_path']}"}, 400

@app.route("/api/search", methods=["GET"])
def api_search():
    try:
        search_args = parse_search_request_args(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    ctx, error_response = get_search_db_context_response()
    if error_response is not None:
        return error_response
    payload, status_code = run_search_for_context(ctx, search_args)
    if status_code is None:
        return jsonify(payload)
    return jsonify(payload), status_code

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
