@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://www.python.org/
    pause
    exit /b 1
)

python -c "import PyQt6, faster_whisper" >nul 2>&1
if errorlevel 1 (
    echo Installing widget dependencies...
    python -m pip install -r "%ROOT%\requirements_widget.txt"
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
)

net session >nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

pythonw -m rctrl.launch
