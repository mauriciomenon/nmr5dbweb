#!/usr/bin/env bash
set -euo pipefail

echo "[nmr5dbweb] Linux setup"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found in PATH. Install from https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

if [[ ! -f "pyproject.toml" ]]; then
  echo "ERROR: pyproject.toml not found at repository root"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Creating .venv with Python 3.13.12 (fallback 3.13.11)..."
  uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "ERROR: failed to create .venv with Python 3.13.12/3.13.11"
  exit 1
fi

echo "Syncing dependencies from pyproject.toml ..."
uv sync --python .venv/bin/python --all-groups

echo
echo "Setup complete."
echo "Activate with: source .venv/bin/activate"
echo "Run app with:  python main.py"
echo
echo "Optional for .mdb conversion: install mdbtools from your distro packages."
