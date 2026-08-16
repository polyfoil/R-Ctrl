@echo off
echo ============================================
echo  R-Ctrl Setup
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python from python.org.
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Installation failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Checking API key...
if "%OPENAI_API_KEY%"=="" (
    echo.
    echo OPENAI_API_KEY is not set yet.
    echo Run the following command (replace sk-... with your actual API key):
    echo.
    echo   setx OPENAI_API_KEY sk-proj-xxxxxxxxxxxx
    echo.
    echo Then open a new terminal and run rctrl.bat.
) else (
    echo API key found.
)

echo.
echo ============================================
echo  Setup complete!
echo  To run: rctrl.bat
echo ============================================
pause
