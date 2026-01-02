# Inventory Tools - Windows IT Setup Guide

Complete guide for IT department to set up Inventory Tools on Windows machines.

---

## Overview

This application automates inventory operations in the Finale Inventory Android app. It requires:
- Android Emulator (from Android Studio)
- Python 3.8+ (can be embedded/portable)
- ADB (Android Debug Bridge)

**Time required:** ~30 minutes per machine (mostly download time)

---

## Step 1: Install Android Studio

1. Download Android Studio from: https://developer.android.com/studio
2. Run the installer with default settings
3. Complete the setup wizard (downloads ~2GB of components)
4. **Important:** Make sure "Android Virtual Device" is checked during installation

---

## Step 2: Create the Emulator Device

The emulator MUST be named exactly `InventoryDevice` for the launcher to work.

### Using Android Studio GUI:

1. Open Android Studio
2. Click **More Actions** (or Tools menu) → **Device Manager**
3. Click **Create Device**
4. Select **Pixel 4** → Click **Next**
5. Select **Tiramisu** (API 33) → Click **Download** if needed → Click **Next**
6. Change **AVD Name** to exactly: `InventoryDevice`
7. Click **Finish**

### Using Command Line (Alternative):

```cmd
"%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\avdmanager.bat" create avd -n InventoryDevice -k "system-images;android-33;google_apis;x86_64" -d pixel_4
```

---

## Step 3: Test the Emulator

1. In Device Manager, click the **Play** button next to InventoryDevice
2. Wait for Android to boot (~1-2 minutes first time)
3. Verify the emulator has internet:
   - Open Chrome in the emulator
   - Navigate to google.com
   - If it works, internet is configured correctly

### If Internet Doesn't Work:

The launcher script includes a fix (`-dns-server 8.8.8.8`), but if you need to test manually:

```cmd
"%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe" -avd InventoryDevice -dns-server 8.8.8.8
```

---

## Step 4: Install Finale Inventory App

With the emulator running:

1. Open Google Play Store in the emulator
2. Sign in with a Google account (can use a company account)
3. Search for "Finale Inventory"
4. Install the app
5. Open the app and log in with company credentials
6. Close the emulator

---

## Step 5: Prepare the Package

The `package/` folder contains everything needed for distribution:

```
package/
├── START.bat           # Main launcher (users double-click this)
├── SETUP_FOR_IT.bat    # Run this to install on user's machine
├── QUICK_START.txt     # Simple instructions for users
├── platform-tools/     # ADB binaries (you need to add these)
├── python/             # Embedded Python (you need to add this)
└── app/                # Application code (copy from src/)
```

### Add Platform Tools (ADB):

1. Download from: https://developer.android.com/studio/releases/platform-tools
2. Extract to `package/platform-tools/`
3. Verify `package/platform-tools/adb.exe` exists

### Add Embedded Python:

1. Download Python 3.11 embeddable package from: https://www.python.org/downloads/windows/
   - Choose "Windows embeddable package (64-bit)"
2. Extract to `package/python/`
3. Install pip and dependencies:

```cmd
cd package\python
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python.exe get-pip.py
python.exe -m pip install flask==3.0.3 openpyxl==3.1.2
```

### Add Application Code:

1. Create `package/app/` folder
2. Copy these from the project:
   - `src/` folder → `package/app/src/`
   - `requirements.txt` → `package/app/`
   - `change_item_state_auto.py` → `package/app/`
   - `transfer_auto.py` → `package/app/`
   - `receive_typing.py` → `package/app/`

---

## Step 6: Deploy to User Machine

On each user's Windows machine:

1. Copy the entire `package/` folder to the machine
2. Right-click `SETUP_FOR_IT.bat` → **Run as Administrator**
3. Follow the prompts
4. Verify "Inventory Tools" shortcut appears on desktop

---

## Step 7: First-Time User Setup

After IT setup, users need to do this once:

1. Double-click "Inventory Tools" on desktop
2. Wait for emulator to boot
3. In the emulator, open Finale Inventory app
4. Log in with their credentials
5. Done - the app remembers the login

---

## Troubleshooting

### "Emulator not found" Error

- Verify Android Studio is installed
- Check emulator exists: Run `%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe -list-avds`
- Ensure device is named exactly `InventoryDevice`

### "Device not connected" Error

- Emulator is still booting, wait longer
- Try restarting ADB: `adb kill-server && adb start-server`

### Emulator Has No Internet

The launcher includes `-dns-server 8.8.8.8` which should fix this. If still not working:
- Check corporate firewall isn't blocking the emulator
- Try `-dns-server 1.1.1.1` instead

### Emulator is Slow

- Enable hardware acceleration in BIOS (VT-x / AMD-V)
- Allocate more RAM to the AVD in Device Manager
- Use x86_64 system images, not ARM

### Python Errors

- Verify embedded Python has flask and openpyxl installed
- Check `package/python/Lib/site-packages/` contains flask and openpyxl folders

---

## Network Requirements

The following need network access:

| Component | Destination | Port |
|-----------|-------------|------|
| Emulator | Google DNS (8.8.8.8) | 53 |
| Finale App | Finale Inventory servers | 443 |
| Flask Server | localhost only | 5000 |

The Flask server runs locally and doesn't require internet.

---

## Uninstallation

To remove from a user's machine:

1. Delete `C:\InventoryTools\` folder
2. Delete desktop shortcut
3. (Optional) Uninstall Android Studio

---

## Package Checklist

Before distributing, verify your package contains:

- [ ] `START.bat` - Main launcher
- [ ] `SETUP_FOR_IT.bat` - IT setup script
- [ ] `QUICK_START.txt` - User instructions
- [ ] `platform-tools/adb.exe` - ADB binary
- [ ] `python/python.exe` - Embedded Python
- [ ] `python/Lib/site-packages/flask/` - Flask installed
- [ ] `python/Lib/site-packages/openpyxl/` - openpyxl installed
- [ ] `app/src/transferer_server.py` - Main application
- [ ] `app/src/templates/` - HTML templates
- [ ] `app/src/static/` - Static files

---

## Support

For issues not covered here:
1. Check `SETUP_AND_LAUNCH.md` for general setup info
2. Check `USAGE.md` for application usage
3. Check `FLOWCHART.md` for automation flow details
