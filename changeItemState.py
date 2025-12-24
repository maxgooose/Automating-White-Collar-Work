#!/usr/bin/env python3
import subprocess
import time

ADB = "/Users/hamza/Library/Android/sdk/platform-tools/adb"

def type_text(text):
    subprocess.run([ADB, "shell", "input", "text", text], capture_output=True)

def press_enter():
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)

# Read IMEI/NEW_ID pairs from file
with open("next_productID.txt", "r") as f:
    lines = [line.strip() for line in f if line.strip()]

print(f"Processing {len(lines)} items...")

for i, line in enumerate(lines, 1):
    # Parse "IMEI, NEW_ID" format
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 2:
        print(f"[{i}/{len(lines)}] Skipping invalid line: {line}")
        continue
    
    imei, new_id = parts
    print(f"[{i}/{len(lines)}] IMEI: {imei} -> NEW_ID: {new_id}")
    
    # Type IMEI and press enter
    type_text(imei)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.3)
    
    # Type NEW_ID and press enter
    type_text(new_id)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.3)

print(f"DONE! Processed {len(lines)} items.")
