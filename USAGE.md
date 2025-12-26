# Quick Transfer - Usage Guide

Automate inventory transfers in Finale Inventory app via ADB.

---

## Setup

### Requirements
```bash
pip install flask openpyxl
```

### Emulator Setup (with DNS fix)

#### Start Emulator
```bash
# Kill any existing emulators first
pkill -9 -f "emulator"

# Start emulator with DNS fix (required for internet access)
~/Library/Android/sdk/emulator/emulator -avd "Medium_Phone_API_36.1" -dns-server 8.8.8.8 -no-snapshot-load &
```

#### Wait for Boot
```bash
~/Library/Android/sdk/platform-tools/adb wait-for-device
# Check boot completion
~/Library/Android/sdk/platform-tools/adb shell getprop sys.boot_completed
# Returns "1" when fully booted
```

#### Kill Emulator
```bash
# Method 1: Via ADB
~/Library/Android/sdk/platform-tools/adb emu kill

# Method 2: Force kill all emulators
pkill -9 -f "qemu-system"
pkill -9 -f "emulator"
```

### Physical Phone Setup
1. Enable **Developer Options** on the Android device
2. Enable **USB Debugging** in Developer Options
3. Connect phone via USB cable
4. Accept the "Allow USB debugging" prompt on the phone
5. Open **Finale Inventory** app and navigate to the **Main Menu**

### Verify Connection
```bash
~/Library/Android/sdk/platform-tools/adb devices
```
Should show your device as "device" (not "unauthorized").

---

## Running the Server

### Start
```bash
cd /Users/hamza/Desktop/Programma\ Uscita\ Pulita/src
python transferer_server.py
```
Open **http://localhost:5000** in your browser.

### Stop
Press `Ctrl+C` in the terminal running the server.

---

## Using Quick Transfer

### Manual Transfer (Left Panel)
1. Enter **From Sublocation** (case-sensitive)
2. Enter **To Sublocation** (case-sensitive)
3. Enter **IMEI**
4. Click **Execute**
5. For multiple IMEIs with same locations: just enter next IMEI and press Enter

### Excel Batch Transfer (Right Panel)
1. Prepare Excel file (.xlsx):
   - **Column A**: From location (only row 1 is read)
   - **Column B**: To location (only row 1 is read)
   - **Column C**: IMEIs (all rows)

   Example:
   | A | B | C |
   |---|---|---|
   | Warehouse-A | Store-1 | 356789012345678 |
   | | | 356789012345679 |
   | | | 356789012345680 |

2. Drag & drop or click to upload the Excel file
3. Click **Execute All**
4. Use **Pause/Resume** or **Stop** as needed

---

## Barcode Typing Script (type_barcodes.py)

A simple script to type barcodes from a file, press enter after each, and proceed.

### Setup
1. Create `receive.txt` with one barcode/IMEI per line
2. Navigate the Finale app to the scan input screen

### Run Script
```bash
python3 /Users/hamza/Desktop/Programma\ Uscita\ Pulita/type_barcodes.py
```

### Run in Background
```bash
python3 /Users/hamza/Desktop/Programma\ Uscita\ Pulita/type_barcodes.py &
```

### Stop Script
```bash
# Kill the script
pkill -f "type_barcodes.py"

# Or kill all Python processes
pkill -f "python3"
```

### Adjust Timing
Edit `type_barcodes.py` and change the `time.sleep(0.7)` value:
- Faster: 0.5 seconds
- Slower: 1.0 seconds

---

## Timing

The automation uses these delays (adjustable in `android_controller.py`):
- After button tap: 0.5s
- After menu selection: 0.8s
- After typing: 0.3s
- Screen transition: 1.0s
- After each IMEI: 2.0s (server sync)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No device connected" | Check USB cable, enable USB debugging |
| "unauthorized" in adb devices | Accept prompt on phone, or revoke & re-authorize |
| Wrong taps/buttons | Phone must be in **landscape mode**, screen 2400x1080 |
| Transfer fails | Ensure Finale app is on Main Menu before starting |

### Kill ADB Server (if stuck)
```bash
~/Library/Android/sdk/platform-tools/adb kill-server
~/Library/Android/sdk/platform-tools/adb start-server
```

### Kill Everything (Nuclear Option)
```bash
# Kill all emulators
pkill -9 -f "emulator"
pkill -9 -f "qemu-system"

# Kill all Python scripts
pkill -f "python3"

# Kill ADB server
~/Library/Android/sdk/platform-tools/adb kill-server

# Start fresh
~/Library/Android/sdk/platform-tools/adb start-server
```

### DNS Not Working on Emulator
If websites don't load on the emulator:
1. Kill the emulator
2. Restart with DNS flag: `-dns-server 8.8.8.8`
3. Test: `adb shell ping google.com`

bulk add stock :
press the following in order :
4. Stock change
1. Add
then enter sublocation from excel sheet Column A



### Receive :
step1 : Navigate 3 buttons down, enter `easier navigation than pressing buttons`
step2 : Type order ID from cell   