#!/usr/bin/env python3
"""
Pick Typing - Types IMEIs for pick operations from Excel data.
Cross-platform compatible (Windows, macOS, Linux).

Reads pick_data.txt where each line is an IMEI or empty (for ENTER only).
Empty lines trigger just ENTER press without typing.
"""
import subprocess
import time
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from adb_utils import get_adb_path, get_data_file_path, check_stop_signal, clear_stop_signal
except ImportError:
    from src.adb_utils import get_adb_path, get_data_file_path, check_stop_signal, clear_stop_signal

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
    progress_file = get_data_file_path("pick_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


def main():
    # A stop file left over from a previous (stopped/crashed) run must not
    # kill this run: the stop signal only targets a live process.
    clear_stop_signal('pick')

    # Get data file path (cross-platform)
    data_file = get_data_file_path("pick_data.txt")

    if not os.path.exists(data_file):
        # stderr so the server surfaces this in the UI instead of a silent stop
        sys.stderr.write(f"Data file not found: {data_file}. "
                         "Upload an Excel file via the web interface first.\n")
        sys.exit(1)

    # Read ALL lines including empty ones (don't strip/filter)
    with open(data_file, "r") as f:
        items = [line.rstrip('\n\r') for line in f]

    # Remove trailing empty lines only
    while items and items[-1] == '':
        items.pop()

    if not items:
        print("ERROR: No data found in pick_data.txt")
        sys.exit(1)

    total = len(items)
    print(f"ADB path: {ADB}")
    print(f"Processing {total} items...")
    print("-" * 40)

    # Initialize progress
    write_progress(0, total)

    for i, item in enumerate(items, 1):
        # Check for stop signal BEFORE processing this item
        if check_stop_signal('pick'):
            print(f"Stop signal received. Stopping at item {i-1}/{total}")
            sys.exit(0)

        if item.strip():
            # Has content - type IMEI then ENTER
            print(f"[{i}/{total}] {item}")
            type_text(item)
            time.sleep(0.1)
            press_enter()
        else:
            # Empty line - just press ENTER
            print(f"[{i}/{total}] (ENTER)")
            press_enter()

        time.sleep(0.3)

        # Update progress after each item
        write_progress(i, total)

    print("-" * 40)
    print(f"DONE! Processed {total} items.")


if __name__ == "__main__":
    main()
