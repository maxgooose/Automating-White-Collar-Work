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

REM Configure ADB and Emulator paths
set ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe
if not exist "%ADB%" (
    set ADB=adb
)
set EMULATOR=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe
set EMULATOR_NAME=InventoryDevice

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
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies.
        echo Retrying with --user flag...
        python -m pip install --user -r requirements.txt
        if %errorlevel% neq 0 (
            echo ERROR: Failed to install dependencies.
            pause
            exit /b 1
        )
    )
    echo. > .deps_installed
    echo Dependencies installed successfully.
)

REM Verify Flask is importable before starting server
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Flask not found. Installing dependencies...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        python -m pip install --user -r requirements.txt
    )
    python -c "import flask" >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Flask still not found after install.
        echo Try running: python -m pip install flask
        pause
        exit /b 1
    )
)

REM Start emulator if not already running
echo Checking Android emulator...
"%ADB%" devices 2>nul | findstr "emulator" >nul
if %errorlevel%==0 (
    echo Emulator already running.
) else (
    if not exist "%EMULATOR%" (
        echo ERROR: Android Emulator not found at:
        echo   %EMULATOR%
        echo.
        echo Please install Android Studio and create an emulator named '%EMULATOR_NAME%'.
        echo See WINDOWS_IT_GUIDE.md for instructions.
        echo.
        pause
        exit /b 1
    )

    set EMULATOR_NAME_FOUND=
    for /f "usebackq delims=" %%a in (`"%EMULATOR%" -list-avds`) do (
        if /I "%%a"=="InventoryDevice" set EMULATOR_NAME_FOUND=%%a
        if /I "%%a"=="Inventorydevice" set EMULATOR_NAME_FOUND=%%a
    )

    if not defined EMULATOR_NAME_FOUND (
        echo ERROR: Emulator device 'InventoryDevice' not found.
        echo.
        echo Available devices:
        "%EMULATOR%" -list-avds
        echo.
        echo Please create a device named 'InventoryDevice' in Android Studio.
        echo See WINDOWS_IT_GUIDE.md for instructions.
        pause
        exit /b 1
    )

    echo Starting Android emulator...
    echo (Network fix applied: -dns-server 8.8.8.8)
    echo.
    start "" /min "%EMULATOR%" -avd %EMULATOR_NAME_FOUND% -dns-server 8.8.8.8 -no-snapshot-load

    echo Waiting for emulator to boot...
    echo (This takes about 30-60 seconds)
    echo.
    :wait_loop
    timeout /t 5 >nul
    "%ADB%" shell getprop sys.boot_completed 2>nul | findstr "1" >nul
    if errorlevel 1 (
        echo   Still booting...
        goto :wait_loop
    )
    echo.
    echo Emulator ready!
)

REM Check ADB
echo.
echo Checking ADB connection...
"%ADB%" devices 2>nul | findstr "device$" >nul
if %errorlevel% neq 0 (
    echo.
    echo WARNING: No device connected. Make sure the emulator is running.
    echo.
)
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
