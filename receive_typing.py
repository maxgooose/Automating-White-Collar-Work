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
# first item handled separately
type_text(imeis[0])
time.sleep(0.1)
press_enter()
time.sleep(0.1)
# receiving items in amazon sku, good conditions start with good and its variations
# acceptable starts with acceptable and its variations
startCases = ["Good", "good","GOOD","goood", "Acceptable", "acceptable", "ACCEPTABLE","Accep","accep"]
# receiving in Excellent condition amazon SKU, they always contain '/' inside the SKU
containCases = ["/"]
# in the case we receive in generic SKU's we check for two spaces in the entire string
# count of spaces inside string must be 2 to trigger this case
# imei.count(' ') == 2 used for that case
for i, imei in enumerate(imeis[1::], 1):
    print(f"[{i}/{len(imeis)}] {imei}")
    if imei.startswith(startCases) or imei.contains(containCases) or imei.count(' ') == 2:
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

