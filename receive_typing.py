#!/usr/bin/env python3
import subprocess
import time

ADB = "/Users/hamza/Library/Android/sdk/platform-tools/adb"

def type_text(text):
    # Escape special characters for ADB input text
    # Spaces must be encoded as %s, other special chars also escaped
    escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"').replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("(", "\\(").replace(")", "\\)").replace("|", "\\|").replace(";", "\\;").replace("$", "\\$").replace("+", "\\+")
    subprocess.run([ADB, "shell", "input", "text", escaped], capture_output=True)

def press_enter():
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)

# Read IMEIs from file
with open("/Users/hamza/Desktop/Programma Uscita Pulita/receive_data.txt", "r") as f:
    imeis = [line.strip() for line in f if line.strip()]

print(f"Processing {len(imeis)} barcodes...")

type_text(imeis[0])
time.sleep(0.1)
press_enter()
time.sleep(0.1)
for i, imei in enumerate(imeis[1::], 1):
    print(f"[{i}/{len(imeis)}] {imei}")
    if imei.startswith("G") or imei.startswith("g") :
        time.sleep(0.1)
        print("iphone found")
        time.sleep(0.1)
        press_enter()
        print("enter pressed")
        time.sleep(0.1)
        type_text(imei)
        press_enter()
        print("imei typed")
    else:
        time.sleep(0.1)
        type_text(imei)
        time.sleep(0.1)
        press_enter()
        time.sleep(0.1)

print(f"DONE! Processed {len(imeis)} barcodes.")

