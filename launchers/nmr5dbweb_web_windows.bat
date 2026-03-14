@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0nmr5dbweb_web_windows.ps1"
exit /b %ERRORLEVEL%
