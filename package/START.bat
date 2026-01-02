@echo off
title Inventory Tools
cd /d "%~dp0"

REM ============================================
REM  INVENTORY TOOLS - One-Click Launcher
REM ============================================
REM  This script:
REM  1. Checks if emulator is already running
REM  2. Starts emulator with network fix if needed
REM  3. Waits for Android to boot
REM  4. Opens the web interface
REM ============================================

echo ============================================
echo  INVENTORY TOOLS - Starting...
echo ============================================
echo.

REM Use bundled Python and ADB
set PATH=%~dp0platform-tools;%~dp0python;%PATH%
set EMULATOR_NAME=InventoryDevice

REM Check if emulator already running
adb devices 2>nul | findstr "emulator" >nul
if %errorlevel%==0 (
    echo Emulator already running.
    goto :start_app
)

REM Find emulator path
set EMULATOR=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe
if not exist "%EMULATOR%" (
    echo ERROR: Android Emulator not found at:
    echo   %EMULATOR%
    echo.
    echo Please install Android Studio first.
    echo See WINDOWS_IT_GUIDE.md for instructions.
    pause
    exit /b 1
)

REM Check if AVD exists
"%EMULATOR%" -list-avds | findstr "%EMULATOR_NAME%" >nul
if errorlevel 1 (
    echo ERROR: Emulator device '%EMULATOR_NAME%' not found.
    echo.
    echo Available devices:
    "%EMULATOR%" -list-avds
    echo.
    echo Please create a device named '%EMULATOR_NAME%' in Android Studio.
    echo See WINDOWS_IT_GUIDE.md for instructions.
    pause
    exit /b 1
)

REM Start emulator with DNS fix (THIS FIXES THE WIFI ISSUE!)
echo Starting Android emulator...
echo (Network fix applied: -dns-server 8.8.8.8)
echo.
start "" /min "%EMULATOR%" -avd %EMULATOR_NAME% -dns-server 8.8.8.8 -no-snapshot-load

REM Wait for emulator to boot (check every 5 seconds)
echo Waiting for emulator to boot...
echo (This takes about 30-60 seconds)
echo.
:wait_loop
timeout /t 5 >nul
adb shell getprop sys.boot_completed 2>nul | findstr "1" >nul
if errorlevel 1 (
    echo   Still booting...
    goto :wait_loop
)
echo.
echo Emulator ready!
echo.

:start_app
REM Check ADB connection
echo Checking device connection...
adb devices | findstr "device$" >nul
if errorlevel 1 (
    echo ERROR: No device connected.
    echo Please ensure the emulator is running.
    pause
    exit /b 1
)
echo Device connected!
echo.

REM Start the Flask server and open browser
echo Starting Inventory Tools server...
echo.
echo ============================================
echo  Opening http://localhost:5000
echo  Press Ctrl+C to stop the server
echo ============================================
echo.

start http://localhost:5000
python app\src\transferer_server.py

pause
