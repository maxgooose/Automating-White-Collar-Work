@echo off
REM ============================================================
REM Finale Inventory Automation - Windows Launcher
REM ============================================================
setlocal enabledelayedexpansion

echo ============================================================
echo  FINALE INVENTORY AUTOMATION
echo ============================================================
echo.

REM Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Python: %PYVER%

REM Change to script directory
cd /d "%~dp0"
echo Working directory: %CD%
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found, using system Python.
    echo To create one, run: python -m venv venv
)

REM Install dependencies if needed
if not exist ".deps_installed" (
    echo.
    echo Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo Dependencies installed successfully.
)

REM Check ADB
echo.
echo Checking ADB connection...
python -c "from src.adb_utils import verify_adb_connection; r=verify_adb_connection(); print('ADB:', r.get('adb_path', 'NOT FOUND')); print('Devices:', len(r.get('devices', [])))"
if %errorlevel% neq 0 (
    echo.
    echo WARNING: ADB check failed. Make sure Android SDK is installed.
    echo See SETUP_AND_LAUNCH.md for installation instructions.
    echo.
)

REM Start the server
echo.
echo ============================================================
echo  Starting server on http://localhost:5000
echo  Press Ctrl+C to stop
echo ============================================================
echo.

python src/transferer_server.py

pause
