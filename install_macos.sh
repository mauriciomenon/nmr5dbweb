#!/usr/bin/env bash
set -euo pipefail

echo "[nmr5dbweb] macOS setup"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found in PATH"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Creating .venv with Python 3.13.12 (fallback 3.13.11)..."
  uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv
fi

echo "Installing Python dependencies from requirements-dev.txt ..."
uv pip install --python .venv -r requirements-dev.txt

echo
echo "Setup complete."
echo "Activate with: source .venv/bin/activate"
echo "Run app with:  python main.py"
echo
echo "Note: ACCDB conversion on macOS usually needs external ODBC/driver setup."

