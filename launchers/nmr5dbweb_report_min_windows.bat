@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0nmr5dbweb_report_min_windows.ps1"
exit /b %ERRORLEVEL%
