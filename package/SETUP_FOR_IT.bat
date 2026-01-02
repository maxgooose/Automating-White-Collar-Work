@echo off
REM ============================================
REM  INVENTORY TOOLS - IT SETUP SCRIPT
REM ============================================
REM  Run this ONCE on each user's machine after
REM  installing Android Studio and creating the
REM  emulator device.
REM ============================================

echo ============================================
echo  INVENTORY TOOLS - IT SETUP
echo ============================================
echo.

REM Check for Android Studio / Emulator
set EMULATOR=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe
if not exist "%EMULATOR%" (
    echo ERROR: Android Emulator not found.
    echo.
    echo Please install Android Studio first:
    echo   https://developer.android.com/studio
    echo.
    echo After installation, create a virtual device named 'InventoryDevice'
    pause
    exit /b 1
)

REM Check for InventoryDevice AVD
echo Checking for 'InventoryDevice' emulator...
"%EMULATOR%" -list-avds | findstr "InventoryDevice" >nul
if errorlevel 1 (
    echo.
    echo WARNING: 'InventoryDevice' not found.
    echo.
    echo Please create it in Android Studio:
    echo   1. Open Android Studio
    echo   2. Go to Tools ^> Device Manager
    echo   3. Click 'Create Device'
    echo   4. Select 'Pixel 4' and click Next
    echo   5. Download 'Tiramisu' ^(API 33^) and click Next
    echo   6. Name it EXACTLY: InventoryDevice
    echo   7. Click Finish
    echo.
    echo Available emulators:
    "%EMULATOR%" -list-avds
    echo.
    pause
    exit /b 1
)
echo Found 'InventoryDevice' - OK
echo.

REM Copy to C:\InventoryTools
echo Copying files to C:\InventoryTools...
if exist "C:\InventoryTools\" (
    echo Removing old installation...
    rmdir /s /q "C:\InventoryTools" 2>nul
)
xcopy /E /I /Y "%~dp0" "C:\InventoryTools\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy files.
    echo Try running this script as Administrator.
    pause
    exit /b 1
)
echo Files copied successfully.
echo.

REM Create desktop shortcut
echo Creating desktop shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Inventory Tools.lnk'); $s.TargetPath = 'C:\InventoryTools\START.bat'; $s.WorkingDirectory = 'C:\InventoryTools'; $s.IconLocation = 'shell32.dll,12'; $s.Description = 'Inventory Tools - Click to start'; $s.Save()"
if errorlevel 1 (
    echo WARNING: Could not create desktop shortcut.
    echo You can manually create a shortcut to C:\InventoryTools\START.bat
) else (
    echo Desktop shortcut created.
)
echo.

REM Done
echo ============================================
echo  SETUP COMPLETE!
echo ============================================
echo.
echo Next steps:
echo   1. Double-click 'Inventory Tools' on desktop
echo   2. Wait for emulator to start ^(~30 seconds^)
echo   3. Open Finale app on the emulator
echo   4. Use the web interface that opens
echo.
echo If this is the first time, you'll need to:
echo   - Install Finale Inventory app from Play Store
echo   - Log in to the app
echo.
pause
