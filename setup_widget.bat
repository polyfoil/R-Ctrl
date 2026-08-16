@echo off
echo ============================================
echo  R-Ctrl Widget Setup (no API key required)
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python from python.org.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install -r "%~dp0requirements_widget.txt"
if errorlevel 1 (
    echo ERROR: Installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  To run: rctrl_widget.bat
echo.
echo  NOTE: The speech model is downloaded on the
echo        first run (up to ~3 GB for large-v3).
echo        After that it runs fully offline.
echo ============================================
pause
