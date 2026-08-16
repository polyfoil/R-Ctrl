@echo off
echo ============================================
echo  R-Ctrl Server Setup (local browser UI)
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python from python.org.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install -r "%~dp0requirements_server.txt"
if errorlevel 1 (
    echo ERROR: Installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  To run: rctrl_server.bat
echo  Then open: http://localhost:5000
echo.
echo  NOTE: The server binds to localhost only.
echo        Other devices cannot reach it.
echo ============================================
pause
