@echo off
REM Stops the backend and frontend started by run.bat.
REM Needed because run.bat starts them as hidden background processes -
REM there's no window to close anymore, so this is the shutdown button.

setlocal

set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>&1
if errorlevel 1 (
    echo PowerShell was not found on this system - cannot stop Praxis automatically.
    echo Close it manually via Task Manager ^(look for "uv", "uvicorn", "node"^).
    pause
    exit /b 1
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT_DIR%run.ps1" -Action Stop

exit /b 0
