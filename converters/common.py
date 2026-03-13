#!/usr/bin/env python3

import re
from pathlib import Path
from typing import Optional, List


def extract_date_from_filename(filename: str) -> Optional[str]:
    patterns = [
        r"(\d{2})[_-](\d{2})[_-](\d{4})",
        r"(\d{4})[_-](\d{2})[_-](\d{2})",
        r"(\d{2})(\d{2})(\d{4})",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if not match:
            continue
        groups = match.groups()
        if len(groups[0]) == 4:
            return f"{groups[0]}-{groups[1]}-{groups[2]}"
        return f"{groups[2]}-{groups[1]}-{groups[0]}"
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
