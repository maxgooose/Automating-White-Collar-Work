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
import xml.etree.ElementTree as ET
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

def get_focused_text():
    """Return text from currently focused input field or EditText."""
    run_adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    ui_xml = run_adb("shell", "cat", "/sdcard/ui.xml")
    run_adb("shell", "rm", "/sdcard/ui.xml")
    if not ui_xml:
        return None
    try:
        root = ET.fromstring(ui_xml)
    except ET.ParseError:
        return None
    # First try: element with focused="true"
    for elem in root.iter("node"):
        if elem.attrib.get("focused") == "true":
            return elem.attrib.get("text", "")
    # Fallback: find EditText fields (common on Pixel/modern Android)
    for elem in root.iter("node"):
        class_name = elem.attrib.get("class", "")
        if "EditText" in class_name:
            return elem.attrib.get("text", "")
    return None


def clear_focused_field(max_len):
    """Clear focused field by deleting characters."""
    run_adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(max_len + 5):
        run_adb("shell", "input", "keyevent", "KEYCODE_DEL")


def type_imei_with_verify(imei, max_retries=5, delay=0.12):
    """Type IMEI and verify before pressing enter."""
    expected = imei.replace(" ", "")
    for attempt in range(1, max_retries + 1):
        clear_focused_field(len(expected))
        type_text(expected)
        time.sleep(delay)
        focused = get_focused_text()
        if focused is None:
            print(f"  WARNING: Unable to read focused field (attempt {attempt}/{max_retries})")
            delay = min(delay + 0.05, 0.5)
            continue
        if focused.replace(" ", "") == expected:
            return True
        print(f"  WARNING: IMEI mismatch (attempt {attempt}/{max_retries}) -> '{focused}'")
        delay = min(delay + 0.05, 0.5)
    return False


def detect_error_screen():
    """
    Detect known error UI by scanning UIAutomator text.
    Looks for barcode echo and common error keywords.
    """
    run_adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    ui_xml = run_adb("shell", "cat", "/sdcard/ui.xml")
    run_adb("shell", "rm", "/sdcard/ui.xml")
    if not ui_xml:
        return False
    try:
        root = ET.fromstring(ui_xml)
    except ET.ParseError:
        return False

    keywords = ("error", "invalid", "failed", "barcode:")
    for elem in root.iter("node"):
        text = (elem.attrib.get("text", "") or "").strip().lower()
        desc = (elem.attrib.get("content-desc", "") or "").strip().lower()
        combined = f"{text} {desc}"
        if any(k in combined for k in keywords):
            return True
    return False


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

def normalize_imei(raw_value):
    """Normalize a single IMEI line (no validation)."""
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    return cleaned


def load_transfer_data(data_file):
    """Load transfer data from file."""
    with open(data_file, "r") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    if len(raw_lines) < 3:
        return None, "transfer_data.txt must have at least 3 lines (from, to, and at least one IMEI)"

    from_loc = raw_lines[0]
    to_loc = raw_lines[1]
    raw_imeis = raw_lines[2:]

    if not from_loc or not to_loc:
        return None, "from/to sublocation cannot be empty"

    imeis = []
    for raw in raw_imeis:
        imei = normalize_imei(raw)
        if not imei:
            continue
        imeis.append(imei)

    return {
        "from_loc": from_loc,
        "to_loc": to_loc,
        "imeis": imeis,
    }, None


def main():
    """Main automation loop."""
    # Get data file path (cross-platform)
    data_file = get_data_file_path("transfer_data.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    data, error = load_transfer_data(data_file)
    if error:
        print(f"ERROR: {error}")
        sys.exit(1)

    from_loc = data["from_loc"]
    to_loc = data["to_loc"]
    imeis = data["imeis"]
    if not imeis:
        print("ERROR: No valid IMEIs found in transfer_data.txt")
        sys.exit(1)
    
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
        if not type_imei_with_verify(imei):
            print("ERROR: Unable to verify IMEI in input field. Stopping to avoid wrong entry.")
            sys.exit(1)
        press_enter()
        time.sleep(0.3)
        if detect_error_screen():
            print("ERROR: Error screen detected after submit. Stopping to avoid wrong entry.")
            sys.exit(1)
        # Update progress after each IMEI
        write_progress(i, total)
    
    print(f"\n{'='*60}")
    print(f"ALL DONE! Transferred {total} items from {from_loc} to {to_loc}.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
