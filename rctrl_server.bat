@echo off
rem Elevation is required because keystroke injection needs it.
rem Dependencies are installed by setup_server.bat, not here: running pip as
rem Administrator on every launch is slow and needlessly broadens the
rem trust surface.
net session >nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
echo Starting R-Ctrl Server...
python "%~dp0rctrl_server.py"
pause
