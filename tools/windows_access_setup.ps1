Param(
  [string]$PythonVersion = "3.13.12",
  [string]$SmokeAccdb = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "== nmr5dbweb Windows Access setup =="
Write-Host "Repo: $repo"
Write-Host "Python target: $PythonVersion"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv not found in PATH. Install uv first."
}

if (-not (Test-Path ".venv")) {
  Write-Host "Creating .venv with Python $PythonVersion ..."
  uv venv --python $PythonVersion .venv
}

Write-Host "Installing runtime deps in .venv ..."
uv pip install --python .venv -r requirements.txt

Write-Host "Checking pyodbc and ODBC drivers ..."
$driverOut = uv run --python .venv python -c "import pyodbc;print(pyodbc.drivers())"
Write-Host "ODBC drivers: $driverOut"

if ($SmokeAccdb -ne "") {
  if (-not (Test-Path $SmokeAccdb)) {
    throw "Smoke ACCDB file not found: $SmokeAccdb"
  }
  Write-Host "Running Access conversion smoke ..."
  uv run --python .venv python tools/windows_access_smoke.py --input $SmokeAccdb
} else {
  Write-Host "Skipping smoke conversion (no -SmokeAccdb provided)."
  Write-Host "Example:"
  Write-Host "  .\tools\windows_access_setup.ps1 -SmokeAccdb C:\dados\sample.accdb"
}

Write-Host "Done."

