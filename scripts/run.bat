@echo off
REM Praxis Launcher
REM
REM This file is intentionally tiny. All real logic lives in run.ps1 -
REM cmd.exe's quoting rules are notoriously easy to get subtly wrong (that's
REM what broke the previous version of this script), so this batch file's
REM only job is to hand off to PowerShell immediately.
REM
REM What happens next: PowerShell starts the backend and frontend as hidden
REM background processes (no console windows), shows a small "Praxis is
REM starting..." page in your browser, and swaps it for the real app the
REM moment both servers are ready. Use stop.bat to shut everything down.

setlocal

set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>&1
if errorlevel 1 (
    echo Praxis needs PowerShell to run, and it was not found on this system.
    echo PowerShell ships with Windows 10 and Windows 11 by default.
    echo If you deliberately removed it, reinstall it and try again.
    pause
    exit /b 1
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT_DIR%run.ps1" -Action Start

exit /b 0
