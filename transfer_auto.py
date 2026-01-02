#!/usr/bin/env python3
"""
Transfer Automation
Reads from/to sublocations and IMEIs from transfer_data.txt and automates the Transfer flow.
Cross-platform compatible (Windows, macOS, Linux).

Data format in transfer_data.txt:
- Line 1: From sublocation
- Line 2: To sublocation
- Lines 3+: IMEIs (one per line)

App flow:
1. 5x DOWN + ENTER (navigate to Transfer menu)
2. 2x DOWN + ENTER (select Transfer from option)
3. Type from sublocation + ENTER
4. Type to sublocation + ENTER
5. For each IMEI: type + ENTER
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

# Timing constants
DELAY_TAP = 0.1
DELAY_TYPE = 0.02
DELAY_SCREEN = 0.25


def write_progress(current, total):
    """Write progress to file for server to poll."""
    progress_file = get_data_file_path("transfer_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


def run_adb(*args):
    """Run ADB command."""
    cmd = [ADB] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def type_text(text):
    """Type text via ADB with proper escaping."""
    escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
    escaped = escaped.replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
    escaped = escaped.replace("(", "\\(").replace(")", "\\)").replace("|", "\\|")
    escaped = escaped.replace(";", "\\;").replace("$", "\\$").replace("+", "\\+")
    subprocess.run([ADB, "shell", "input", "text", escaped], capture_output=True)


def press_enter():
    """Press Enter key via ADB."""
    run_adb("shell", "input", "keyevent", "KEYCODE_ENTER")
    time.sleep(DELAY_TAP)


def press_down():
    """Press DOWN key via ADB."""
    run_adb("shell", "input", "keyevent", "KEYCODE_DPAD_DOWN")
    time.sleep(0.02)


def navigate_to_transfer():
    """
    Navigate from main menu to Transfer screen.
    Method: 5x DOWN + ENTER, then 2x DOWN + ENTER
    """
    print("\n=== NAVIGATING TO TRANSFER ===")
    
    # First: 5x DOWN + ENTER
    for i in range(5):
        print(f"  DOWN {i + 1}/5")
        press_down()
    
    time.sleep(0.1)
    print("  -> Pressing ENTER...")
    press_enter()
    time.sleep(DELAY_SCREEN)
    
    # Second: 2x DOWN + ENTER
    for i in range(2):
        print(f"  DOWN {i + 1}/2")
        press_down()
    
    time.sleep(0.1)
    print("  -> Pressing ENTER...")
    press_enter()
    time.sleep(DELAY_SCREEN)
    
    print("=== NAVIGATION COMPLETE ===\n")


def main():
    """Main automation loop."""
    # Get data file path (cross-platform)
    data_file = get_data_file_path("transfer_data.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    # Read data from file
    with open(data_file, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if len(lines) < 3:
        print("ERROR: transfer_data.txt must have at least 3 lines (from, to, and at least one IMEI)")
        sys.exit(1)
    
    # Parse data
    from_loc = lines[0]
    to_loc = lines[1]
    imeis = lines[2:]
    
    total = len(imeis)
    print(f"\n{'='*60}")
    print(f"TRANSFER AUTOMATION")
    print(f"ADB path: {ADB}")
    print(f"From: {from_loc}")
    print(f"To: {to_loc}")
    print(f"IMEIs to transfer: {total}")
    print(f"{'='*60}")
    
    # Show preview
    print("\nPreview:")
    for i, imei in enumerate(imeis[:3], 1):
        print(f"  {i}. {imei}")
    if total > 3:
        print(f"  ... and {total - 3} more")
    
    print("\nGO!")
    
    # Initialize progress
    write_progress(0, total)
    
    # Navigate to Transfer screen
    navigate_to_transfer()
    
    # Type from sublocation + ENTER
    print(f"[FROM] {from_loc}")
    type_text(from_loc)
    time.sleep(DELAY_TYPE)
    press_enter()
    time.sleep(DELAY_SCREEN)
    
    # Type to sublocation + ENTER
    print(f"[TO] {to_loc}")
    type_text(to_loc)
    time.sleep(DELAY_TYPE)
    press_enter()
    time.sleep(DELAY_SCREEN)
    
    # Type each IMEI + ENTER
    for i, imei in enumerate(imeis, 1):
        print(f"[{i}/{total}] {imei}")
        type_text(imei)
        time.sleep(DELAY_TYPE)
        press_enter()
        time.sleep(0.3)
        # Update progress after each IMEI
        write_progress(i, total)
    
    print(f"\n{'='*60}")
    print(f"ALL DONE! Transferred {total} items from {from_loc} to {to_loc}.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
