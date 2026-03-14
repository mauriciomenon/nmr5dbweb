@echo off
setlocal

echo [nmr5dbweb] Windows setup
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo ERROR: uv not found in PATH.
  exit /b 1
)

if not exist tools\windows_access_setup.ps1 (
  echo ERROR: tools\windows_access_setup.ps1 not found.
  exit /b 1
)

echo Running PowerShell setup (venv + requirements-dev + pyodbc/driver check)...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\windows_access_setup.ps1
if errorlevel 1 (
  echo ERROR: setup failed.
  exit /b 1
)

echo.
echo Setup complete.
echo If you have an ACCDB sample, run:
echo   powershell -ExecutionPolicy Bypass -File tools\windows_access_setup.ps1 -SmokeAccdb C:\path\sample.accdb

exit /b 0

