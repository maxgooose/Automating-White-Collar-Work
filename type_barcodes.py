#!/usr/bin/env python3
import subprocess
import time

ADB = "/Users/hamza/Library/Android/sdk/platform-tools/adb"

def type_text(text):
    subprocess.run([ADB, "shell", "input", "text", text], capture_output=True)

def press_enter():
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)

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

print(f"DONE! Processed {len(imeis)} barcodes.")

