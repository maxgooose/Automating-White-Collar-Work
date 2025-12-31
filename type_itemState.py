#!/usr/bin/env python3
"""
Type Item State - Types barcodes and confirms state changes.
Cross-platform compatible (Windows, macOS, Linux).
"""
import subprocess
import time
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from adb_utils import get_adb_path, get_data_file_path
except ImportError:
    from src.adb_utils import get_adb_path, get_data_file_path

# Get cross-platform ADB path
ADB = get_adb_path()

# Coordinates of the Confirm button (2400x1080 landscape)
CONFIRM_X = 1310
CONFIRM_Y = 580


def type_text(text):
    """Type text via ADB with proper escaping."""
    escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
    escaped = escaped.replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
    escaped = escaped.replace("(", "\\(").replace(")", "\\)").replace("|", "\\|")
    escaped = escaped.replace(";", "\\;").replace("$", "\\$").replace("+", "\\+")
    subprocess.run([ADB, "shell", "input", "text", escaped], capture_output=True)


def press_enter():
    """Press Enter key via ADB."""
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_ENTER"], capture_output=True)


def tap_confirm():
    """Tap the Confirm button at the specified coordinates."""
    subprocess.run([ADB, "shell", "input", "tap", str(CONFIRM_X), str(CONFIRM_Y)], capture_output=True)


def main():
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Create receive.txt with one barcode/IMEI per line.")
        sys.exit(1)
    
    # Read IMEIs from file
    with open(data_file, "r") as f:
        imeis = [line.strip() for line in f if line.strip()]
    
    if not imeis:
        print("ERROR: No barcodes found in receive.txt")
        sys.exit(1)
    
    print(f"ADB path: {ADB}")
    print(f"Processing {len(imeis)} barcodes...")
    print("-" * 40)
    
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
    
    # Handle remaining IMEI if odd number
    if len(imeis) % 2 == 1:
        print(f"  -> Pressing Confirm button for last IMEI...")
        tap_confirm()
        time.sleep(0.5)
    
    print("-" * 40)
    print(f"DONE! Processed {len(imeis)} barcodes.")


if __name__ == "__main__":
    main()
