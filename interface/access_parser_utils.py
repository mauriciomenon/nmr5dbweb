from __future__ import annotations

import importlib
import logging
import os
from typing import Any, Dict, List


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
        if "has no data" in str(message):
            return False
        return True


def _configure_access_parser_logging() -> None:
    if _access_parser_verbose_enabled():
        return
    logging.getLogger("access_parser").setLevel(logging.WARNING)
    root = logging.getLogger()
    for handler in root.handlers:
        has_filter = any(
            isinstance(existing, _AccessParserNoiseFilter)
            for existing in getattr(handler, "filters", [])
        )
        if not has_filter:
            handler.addFilter(_AccessParserNoiseFilter())


def load_access_parser_module():
    _configure_access_parser_logging()
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
    except Exception:
        tables = []
    return [name for name in tables if name and not str(name).startswith("MSys")]


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
        if isinstance(parsed[0], dict):
            return [dict(row) for row in parsed]
    if hasattr(parsed, "to_dict"):
        try:
            data = parsed.to_dict(orient="records")
            if isinstance(data, list):
                return [dict(row) for row in data if isinstance(row, dict)]
        except Exception:
            return []
    return []
