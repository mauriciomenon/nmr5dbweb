from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _access_parser_verbose_enabled() -> bool:
    return str(os.environ.get("NMR5DBWEB_ACCESS_PARSER_VERBOSE", "")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class _AccessParserNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _access_parser_verbose_enabled():
            return True
        name = str(getattr(record, "name", "") or "")
        if not name.startswith("access_parser"):
            return True
        try:
            message = record.getMessage()
        except Exception:
            return True
        if is_access_parser_no_data_message(message):
            return False
        return True


def _attach_noise_filter_once(target: Any) -> None:
    has_filter = any(
        isinstance(existing, _AccessParserNoiseFilter)
        for existing in getattr(target, "filters", [])
    )
    if not has_filter and hasattr(target, "addFilter"):
        target.addFilter(_AccessParserNoiseFilter())


def ensure_access_parser_logging() -> None:
    if _access_parser_verbose_enabled():
        return
    parser_logger = logging.getLogger("access_parser")
    parser_logger.setLevel(logging.WARNING)
    _attach_noise_filter_once(parser_logger)
    root = logging.getLogger()
    for handler in root.handlers:
        _attach_noise_filter_once(handler)
    for handler in parser_logger.handlers:
        _attach_noise_filter_once(handler)


def load_access_parser_module():
    ensure_access_parser_logging()
    try:
        return importlib.import_module("access_parser"), None
    except Exception as exc1:
        try:
            return importlib.import_module("access_parser_access"), None
        except Exception as exc2:
            return None, f"{exc1}; {exc2}"


def list_access_tables_from_parser(parser) -> List[str]:
    tables: List[str] = []
    try:
        catalog = getattr(parser, "catalog", None)
        if catalog is not None and hasattr(catalog, "keys"):
            tables = [str(name) for name in catalog.keys()]
        elif hasattr(parser, "tables"):
            parsed_tables = getattr(parser, "tables", {})
            if hasattr(parsed_tables, "keys"):
                tables = [str(name) for name in parsed_tables.keys()]
            elif isinstance(parsed_tables, (list, tuple, set)):
                tables = [str(name) for name in parsed_tables]
        elif hasattr(parser, "table_names"):
            parsed_tables = getattr(parser, "table_names")
            if callable(parsed_tables):
                values = parsed_tables()
                if isinstance(values, (list, tuple, set)):
                    tables = [str(name) for name in values]
            elif isinstance(parsed_tables, (list, tuple, set)):
                tables = [str(name) for name in parsed_tables]
        elif hasattr(parser, "get_table_names"):
            values = parser.get_table_names()
            if isinstance(values, (list, tuple, set)):
                tables = [str(name) for name in values]
    except Exception:
        tables = []
    seen = set()
    out = []
    for name in tables:
        text = str(name or "").strip()
        if not text:
            continue
        if text.lower().startswith("msys"):
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def is_access_parser_no_data_message(message: Any) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    patterns = (
        "has no data",
        "no data",
        "sem dados",
        "tabela vazia",
        "table empty",
        "no rows",
        "contains no records",
        "0 rows",
    )
    return any(token in text for token in patterns)


def is_access_parser_no_data_error(error: Any) -> bool:
    if isinstance(error, BaseException):
        return is_access_parser_no_data_message(str(error))
    return is_access_parser_no_data_message(error)


def _normalize_access_row_object(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, Mapping):
        return {str(key): value for key, value in row.items()}
    if hasattr(row, "_asdict"):
        try:
            return dict(row._asdict())
        except Exception as exc:
            logger.debug("row _asdict conversion failed: %s", exc)
    if isinstance(row, (list, tuple)):
        return {f"col_{idx}": value for idx, value in enumerate(row)}
    if hasattr(row, "__dict__"):
        try:
            raw = dict(vars(row))
            if raw:
                filtered = {
                    str(key): value
                    for key, value in raw.items()
                    if not str(key).startswith("_")
                }
                if filtered:
                    return filtered
        except Exception as exc:
            logger.debug("row __dict__ conversion failed: %s", exc)
    return {"value": row}


def normalize_access_parser_rows(parsed: Any) -> List[Dict[str, Any]]:
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        normalized: Dict[str, List[Any]] = {}
        max_len = 0
        for col_name, col_data in parsed.items():
            if isinstance(col_data, (list, tuple)):
                seq = list(col_data)
            elif col_data is None:
                seq = []
            else:
                seq = [col_data]
            normalized[str(col_name)] = seq
            if len(seq) > max_len:
                max_len = len(seq)
        if max_len == 0:
            return []
        rows: List[Dict[str, Any]] = []
        for idx in range(max_len):
            row_obj: Dict[str, Any] = {}
            for col_name, seq in normalized.items():
                row_obj[col_name] = seq[idx] if idx < len(seq) else None
            rows.append(row_obj)
        return rows
    if isinstance(parsed, list):
        if not parsed:
            return []
        normalized_rows: List[Dict[str, Any]] = []
        for row in parsed:
            normalized_rows.append(_normalize_access_row_object(row))
        return normalized_rows
    if hasattr(parsed, "to_dict"):
        try:
            data = parsed.to_dict(orient="records")
            if isinstance(data, list):
                return [dict(row) for row in data if isinstance(row, dict)]
        except Exception as exc:
            logger.warning("Failed converting parser rows via to_dict: %s", exc)
    if isinstance(parsed, Iterable) and not isinstance(parsed, (str, bytes, bytearray)):
        items = list(parsed)
        if not items:
            return []
        return [_normalize_access_row_object(row) for row in items]
    return []
