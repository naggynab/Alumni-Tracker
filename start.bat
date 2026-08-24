@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 (
    echo.
    echo Failed to start Alumni Tracker. See the message above.
    pause
    exit /b 1
)
start "" "http://127.0.0.1:8000/"
