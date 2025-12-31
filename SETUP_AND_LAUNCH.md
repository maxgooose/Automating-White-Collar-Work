# Finale Inventory Automation - Setup and Launch Guide

Complete setup, launch, and troubleshooting guide for Windows, macOS, and Linux.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Requirements](#requirements)
3. [Installation](#installation)
   - [Windows](#windows-installation)
   - [macOS](#macos-installation)
   - [Linux](#linux-installation)
4. [Android Device Setup](#android-device-setup)
5. [Running the Application](#running-the-application)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)

---

## Quick Start

### Fastest Launch Method

**Windows:**
```
Double-click start.bat
```

**macOS/Linux:**
```bash
./start.sh
```

**Cross-Platform (Python):**
```bash
python launcher.py
```

The application opens automatically at `http://localhost:5000`.

---

## Requirements

### Software Requirements

| Component | Minimum Version | Download |
|-----------|-----------------|----------|
| Python | 3.8+ | https://www.python.org/downloads/ |
| Android SDK Platform Tools | Latest | https://developer.android.com/studio/releases/platform-tools |

### Python Packages

Installed automatically by the launcher:
- Flask 3.0+
- openpyxl 3.1+

---

## Installation

### Windows Installation

#### Step 1: Install Python

1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" at the bottom of the installer
4. Click "Install Now"
5. Verify installation:
   ```cmd
   python --version
   ```

#### Step 2: Install Android SDK Platform Tools

**Option A: Standalone Platform Tools (Recommended)**

1. Download from https://developer.android.com/studio/releases/platform-tools
2. Extract to `C:\platform-tools` or `%LOCALAPPDATA%\Android\Sdk\platform-tools`
3. Add to PATH:
   - Press Win+X, select "System"
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "User variables", select "Path" and click "Edit"
   - Click "New" and add: `C:\platform-tools` (or your extraction path)
   - Click OK on all dialogs
4. Open new Command Prompt and verify:
   ```cmd
   adb version
   ```

**Option B: Via Android Studio**

1. Install Android Studio from https://developer.android.com/studio
2. Open Android Studio > Tools > SDK Manager
3. Select "SDK Tools" tab
4. Check "Android SDK Platform-Tools"
5. Click Apply
6. ADB will be at: `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`

#### Step 3: Download and Run

1. Download or clone this project
2. Open the project folder in Explorer
3. Double-click `start.bat`

---

### macOS Installation

#### Step 1: Install Python

Python 3 is pre-installed on modern macOS. Verify:
```bash
python3 --version
```

If not installed, use Homebrew:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python3
```

#### Step 2: Install Android SDK Platform Tools

**Option A: Homebrew (Recommended)**
```bash
brew install --cask android-platform-tools
```

**Option B: Manual Installation**

1. Download from https://developer.android.com/studio/releases/platform-tools
2. Extract to `~/Library/Android/sdk/platform-tools`
3. Add to PATH (add to `~/.zshrc` or `~/.bash_profile`):
   ```bash
   export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"
   ```
4. Reload:
   ```bash
   source ~/.zshrc
   ```

#### Step 3: Run

```bash
cd "/path/to/Programma Uscita Pulita"
./start.sh
```

Or:
```bash
python3 launcher.py
```

---

### Linux Installation

#### Step 1: Install Python

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip
```

**Arch:**
```bash
sudo pacman -S python python-pip
```

#### Step 2: Install Android SDK Platform Tools

**Ubuntu/Debian:**
```bash
sudo apt install android-sdk-platform-tools
```

**Manual Installation:**
```bash
# Download
wget https://dl.google.com/android/repository/platform-tools-latest-linux.zip

# Extract
unzip platform-tools-latest-linux.zip -d ~/

# Add to PATH (add to ~/.bashrc)
echo 'export PATH="$HOME/platform-tools:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Step 3: USB Permissions (Linux Only)

Create udev rules for Android devices:
```bash
sudo tee /etc/udev/rules.d/51-android.rules << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0fce", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev"
EOF

sudo udevadm control --reload-rules
sudo usermod -aG plugdev $USER
```

Log out and back in for group changes to take effect.

#### Step 4: Run

```bash
cd "/path/to/Programma Uscita Pulita"
chmod +x start.sh
./start.sh
```

---

## Android Device Setup

### Physical Device

1. **Enable Developer Options**
   - Go to Settings > About Phone
   - Tap "Build Number" 7 times
   - "Developer mode enabled" will appear

2. **Enable USB Debugging**
   - Go to Settings > Developer Options
   - Enable "USB Debugging"
   - (Optional) Enable "Stay awake" to prevent screen timeout

3. **Connect Device**
   - Connect phone via USB cable
   - Accept "Allow USB debugging?" prompt on phone
   - If prompted for computer fingerprint, check "Always allow" and tap OK

4. **Verify Connection**
   ```bash
   adb devices
   ```
   Should show your device as "device" (not "unauthorized").

### Android Emulator

1. **Install Android Studio** (if not already installed)

2. **Create Virtual Device**
   - Open Android Studio
   - Go to Tools > Device Manager
   - Click "Create Device"
   - Select a phone (e.g., Pixel 4)
   - Select a system image (API 30+ recommended)
   - Click Finish

3. **Start Emulator**
   ```bash
   # List available emulators
   emulator -list-avds
   
   # Start emulator (replace with your AVD name)
   emulator -avd Pixel_4_API_30 -dns-server 8.8.8.8
   ```

4. **Verify Connection**
   ```bash
   adb devices
   ```

---

## Running the Application

### Method 1: Launcher Scripts (Recommended)

**Windows:**
```
Double-click start.bat
```

**macOS/Linux:**
```bash
./start.sh
```

### Method 2: Python Launcher

```bash
# Start server (opens browser automatically)
python launcher.py

# Start without opening browser
python launcher.py --no-browser

# Check system requirements
python launcher.py --check

# Install dependencies only
python launcher.py --install
```

### Method 3: Direct Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python src/transferer_server.py
```

### Method 4: Virtual Environment (Recommended for Development)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python src/transferer_server.py
```

---

## Troubleshooting

### Installation Issues

#### Python Not Found

**Windows:**
1. Reinstall Python, ensuring "Add Python to PATH" is checked
2. Or manually add to PATH:
   - Find Python installation (usually `C:\Users\<name>\AppData\Local\Programs\Python\Python3x`)
   - Add both the main folder and `Scripts` subfolder to PATH

**macOS/Linux:**
- Use `python3` instead of `python`
- Install via package manager if missing

#### Pip Not Found

```bash
# Install pip
python -m ensurepip --upgrade

# Or on Linux
sudo apt install python3-pip
```

#### Permission Denied (Linux/macOS)

```bash
# Make launcher executable
chmod +x start.sh
chmod +x launcher.py

# If pip fails with permission error
pip install --user -r requirements.txt
```

---

### ADB Issues

#### ADB Not Found

**Symptom:** "ADB not found" error

**Solution:**
1. Install Android SDK Platform Tools (see Installation section)
2. Add to system PATH
3. Or set environment variable:
   ```bash
   # Windows (Command Prompt)
   set ADB_PATH=C:\path\to\adb.exe
   
   # macOS/Linux
   export ADB_PATH=/path/to/adb
   ```

#### No Devices Found

**Symptom:** `adb devices` returns empty list

**Solutions:**
1. Check USB cable connection
2. Try different USB port (USB 2.0 often works better than USB 3.0)
3. Use original manufacturer cable
4. Restart ADB server:
   ```bash
   adb kill-server
   adb start-server
   adb devices
   ```

#### Device Shows "Unauthorized"

**Symptom:** Device listed as "unauthorized"

**Solutions:**
1. Check phone screen for USB debugging prompt
2. Revoke USB debugging authorizations and reconnect:
   - On phone: Settings > Developer Options > Revoke USB debugging authorizations
   - Disconnect and reconnect USB
   - Accept new prompt

#### Device Shows "Offline"

**Symptom:** Device listed as "offline"

**Solutions:**
1. Toggle USB debugging off and on
2. Restart ADB:
   ```bash
   adb kill-server
   adb start-server
   ```
3. Restart phone
4. Try different USB mode (File Transfer/MTP vs Charging)

---

### Server Issues

#### Port Already in Use

**Symptom:** "Address already in use" error

**Solution:**
```bash
# Find process using port 5000
# Windows
netstat -ano | findstr :5000

# macOS/Linux
lsof -i :5000

# Kill the process
# Windows (replace PID with actual PID)
taskkill /PID <PID> /F

# macOS/Linux
kill -9 <PID>
```

#### Server Crashes on Start

**Symptom:** Server exits immediately

**Solutions:**
1. Check all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
2. Run with debug output:
   ```bash
   python src/transferer_server.py
   ```
3. Check for syntax errors in configuration

---

### Automation Issues

#### Taps Hit Wrong Locations

**Symptom:** Automation taps wrong buttons/menu items

**Cause:** Screen resolution or orientation mismatch

**Solution:**
1. Ensure phone is in landscape mode
2. Ensure resolution is 2400x1080 (or adjust coordinates in `android_controller.py`)
3. Check orientation:
   ```bash
   adb shell wm size
   ```

#### Automation Too Slow/Fast

**Symptom:** Steps get skipped or lag behind

**Solution:** Adjust timing constants in `android_controller.py`:
```python
DELAY_AFTER_TAP = 1.0       # Increase if steps are skipped
DELAY_AFTER_TYPE = 0.5      # Increase for slower typing
DELAY_SCREEN_TRANSITION = 1.5  # Increase for slower screens
DELAY_AFTER_IMEI = 2.0      # Increase for server sync
```

#### Text Input Issues

**Symptom:** Special characters not typed correctly

**Solution:** Special characters are escaped automatically. If issues persist, simplify input data (remove special characters where possible).

---

### Network Issues

#### Cannot Access localhost:5000

**Solutions:**
1. Check server is running (look for "Running on http://localhost:5000" message)
2. Try http://127.0.0.1:5000 instead
3. Check firewall is not blocking port 5000
4. Disable VPN temporarily

#### Emulator Has No Internet

**Symptom:** Apps on emulator cannot connect to internet

**Solution:** Start emulator with DNS flag:
```bash
emulator -avd YOUR_AVD_NAME -dns-server 8.8.8.8
```

---

## Advanced Configuration

### Custom ADB Path

Set the `ADB_PATH` environment variable to use a custom ADB location:

**Windows (permanent):**
1. Open System Properties > Environment Variables
2. Add new User variable: `ADB_PATH` = `C:\your\path\to\adb.exe`

**macOS/Linux (add to shell profile):**
```bash
export ADB_PATH="/your/path/to/adb"
```

### Multiple Devices

When multiple devices are connected, specify device ID:
```bash
adb -s DEVICE_ID shell input text hello
```

To list devices:
```bash
adb devices
```

### Running on Different Port

Edit `src/transferer_server.py`, change the last line:
```python
app.run(debug=True, port=8080, threaded=True)  # Change 5000 to desired port
```

### Screen Coordinates

For different screen resolutions, adjust coordinates in `src/android_controller.py`:

```python
# Current settings (2400x1080 landscape)
BTN_Y = 950
BTN_LEFT_X = 120
BTN_CENTER_X = 390
BTN_RIGHT_X = 660
MENU_X = 400
MENU_ITEM_1_Y = 185
# ... etc
```

To find coordinates on your device:
```bash
# Enable pointer location in Developer Options
# Or use:
adb shell getevent -l
# Then tap screen to see coordinates
```

---

## Support

For issues not covered here:
1. Check existing documentation in `USAGE.md` and `FLOWCHART.md`
2. Review error messages carefully - they often indicate the exact problem
3. Ensure all prerequisites are correctly installed
4. Try restarting ADB server and reconnecting device
