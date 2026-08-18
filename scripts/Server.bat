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

python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Installing server dependencies...
    python -m pip install -r "%ROOT%\requirements_server.txt"
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
)

echo Starting R-Ctrl Server...
python -m rctrl.server
pause
