import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_windows_accdb_conversion_smoke():
    if os.name != "nt":
        pytest.skip("smoke Access->DuckDB apenas em Windows")

    sample = os.environ.get("NMR5DBWEB_ACCDB_SMOKE", "").strip()
    if not sample:
        pytest.skip("defina NMR5DBWEB_ACCDB_SMOKE para executar o smoke real de .accdb")

    sample_path = Path(sample).expanduser().resolve()
    if not sample_path.exists():
        pytest.skip("arquivo de smoke .accdb nao encontrado")

    script = Path(__file__).resolve().parents[1] / "tools" / "windows_access_smoke.py"
    cmd = [sys.executable, str(script), "--input", str(sample_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    assert proc.stdout.strip(), "saida vazia do smoke"
    payload = json.loads(proc.stdout.strip())
    assert payload.get("platform"), "plataforma ausente no payload"
    assert payload.get("table_count", 0) >= 1, proc.stdout
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert payload.get("ok") is True, proc.stdout

