@echo off
REM Launch the packaged widget as administrator (global hotkey + paste).
set "DIR=%~dp0"
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%DIR%R-Ctrl-Whisperer.exe' -WorkingDirectory '%DIR%' -Verb RunAs"
    exit /b
)
cd /d "%DIR%"
start "" "%DIR%R-Ctrl-Whisperer.exe"
