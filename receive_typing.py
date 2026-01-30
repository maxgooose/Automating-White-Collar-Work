#!/usr/bin/env python3
"""
Receive Typing - Types product names and IMEIs for receive operations.
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
    from adb_utils import get_adb_path, get_data_file_path, check_stop_signal
except ImportError:
    from src.adb_utils import get_adb_path, get_data_file_path, check_stop_signal

# Get cross-platform ADB path
ADB = get_adb_path()


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


def write_progress(current, total):
    """Write progress to file for server to poll."""
    progress_file = get_data_file_path("receive_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


def main():
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive_data.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    # Ask user for sublocation (not used, just for confirmation)
    sublocation = input("Enter sublocation (press Enter to continue): ").strip()
    # Sublocation is intentionally not stored or sent anywhere
    
    # Read data from file
    with open(data_file, "r") as f:
        items = [line.strip() for line in f if line.strip()]
    
    if not items:
        print("ERROR: No data found in receive_data.txt")
        sys.exit(1)
    
    total = len(items)
    print(f"ADB path: {ADB}")
    print(f"Processing {total} items...")
    print("-" * 40)
    
    # Initialize progress
    write_progress(0, total)
    
    # Sublocation typing disabled - not sending to device
    # print(f"[SUBLOCATION] {sublocation}")
    # type_text(sublocation)
    # time.sleep(0.1)
    # press_enter()
    # time.sleep(0.1)
    
    # First item handled separately
    print(f"[1/{total}] {items[0]}")
    type_text(items[0])
    time.sleep(1)
    press_enter()
    time.sleep(1)
    current = 1
    write_progress(current, total)
    
    for i, item in enumerate(items[1:], 2):
        # Check for stop signal BEFORE processing this item
        if check_stop_signal('receive'):
            print(f"Stop signal received. Stopping at item {i-1}/{total}")
            sys.exit(0)

        print(f"[{i}/{total}] {item}")

        # Special handling for non IMEI items
        if item.lower().startswith('ipad') or item.lower().startswith('good') or item.lower().startswith('iphone') or item.lower().startswith('accep') or item.lower().startswith('galaxy'):
            print("  Non IMEI item found - special handling")
            time.sleep(1)
            press_enter()
            print("  Enter pressed")
            time.sleep(1)
            type_text(item)
            press_enter()
            time.sleep(1)
            print("  Item typed")
        else:
            time.sleep(0.1)
            type_text(item)
            time.sleep(0.1)
            press_enter()
            time.sleep(0.1)
        
        # Update progress after each item
        current += 1
        write_progress(current, total)
    
    print("-" * 40)
    print(f"DONE! Processed {total} items.")


if __name__ == "__main__":
    main()
