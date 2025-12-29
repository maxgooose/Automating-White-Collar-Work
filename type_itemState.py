#!/usr/bin/env python3
import subprocess
import time

ADB = "/Users/hamza/Library/Android/sdk/platform-tools/adb"

# Coordinates of the Confirm button (2400x1080 landscape)
CONFIRM_X = 1310
CONFIRM_Y = 580

def type_text(text):
    # Escape special characters for ADB input text
    # Spaces must be encoded as %s, other special chars also escaped
    escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"').replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("(", "\\(").replace(")", "\\)").replace("|", "\\|").replace(";", "\\;").replace("$", "\\$").replace("+", "\\+")
    subprocess.run([ADB, "shell", "input", "text", escaped], capture_output=True)

def press_enter():
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)

def tap_confirm():
    """Tap the Confirm button at the specified coordinates"""
    subprocess.run([ADB, "shell", "input", "tap", str(CONFIRM_X), str(CONFIRM_Y)], capture_output=True)

# Read IMEIs from file
with open("/Users/hamza/Desktop/Programma Uscita Pulita/receive.txt", "r") as f:
    imeis = [line.strip() for line in f if line.strip()]

print(f"Processing {len(imeis)} barcodes...")

for i, imei in enumerate(imeis, 1):
    print(f"[{i}/{len(imeis)}] {imei}")
    type_text(imei)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.3)
    
    # Press Confirm button after every 2 IMEIs
    if i % 2 == 0:
        print(f"  -> Pressing Confirm button...")
        tap_confirm()
        time.sleep(0.5)

# Handle remaining IMEI if odd number (press confirm for the last one)
if len(imeis) % 2 == 1:
    print(f"  -> Pressing Confirm button for last IMEI...")
    tap_confirm()
    time.sleep(0.5)

print(f"DONE! Processed {len(imeis)} barcodes.")

