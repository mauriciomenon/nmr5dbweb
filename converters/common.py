#!/usr/bin/env python3

import re
from datetime import date
from pathlib import Path
from typing import Optional, List


def extract_date_from_filename(filename: str) -> Optional[str]:
    patterns = [
        (r"(\d{2})[_-](\d{2})[_-](\d{4})", "dmy", False),
        (r"(\d{4})[_-](\d{2})[_-](\d{2})", "ymd", False),
        (r"(\d{2})(\d{2})(\d{4})", "dmy", True),
        (r"(\d{4})(\d{2})(\d{2})", "ymd", True),
    ]
    compact_candidates = []
    for pattern, mode, is_compact in patterns:
        match = re.search(pattern, filename)
        if not match:
            continue
        g1, g2, g3 = match.groups()
        if mode == "ymd":
            year, month, day = int(g1), int(g2), int(g3)
        else:
            day, month, year = int(g1), int(g2), int(g3)
        try:
            iso = date(year, month, day).isoformat()
        except ValueError:
            continue
        if is_compact:
            compact_candidates.append((iso, year))
        else:
            return iso
    if compact_candidates:
        in_range = [iso for iso, year in compact_candidates if 1900 <= year <= 2100]
        if in_range:
            return in_range[0]
        return compact_candidates[0][0]
    return None


def list_access_files(input_dir: Path) -> List[Path]:
    return sorted(list(input_dir.glob("*.mdb")) + list(input_dir.glob("*.accdb")))


def validate_cli_input(input_path: Optional[Path], batch: bool) -> Optional[str]:
    if not input_path:
        return "missing_input"
    if not input_path.exists():
        return f"Error: {input_path} not found"
    if batch and not input_path.is_dir():
        return "Error: --batch requires --input to be a directory"
    if not batch and not input_path.is_file():
        return "Error: --input must be a MDB/ACCDB file"
    return None
