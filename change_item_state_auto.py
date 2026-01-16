#!/usr/bin/env python3
"""
Change Item State Automation
Reads IMEI/Product ID pairs from receive.txt and automates the Change Item State flow.
Cross-platform compatible (Windows, macOS, Linux).

Data format in receive.txt:
- Line 1: IMEI
- Line 2: Product ID (new state)
- Line 3: IMEI
- Line 4: Product ID (new state)
... and so on
"""
import subprocess
import time
import re
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

# Timing (ULTRA mode - minimal delays)
DELAY_TAP = 0.1
DELAY_TYPE = 0.02
DELAY_SCREEN = 0.25
DELAY_AFTER_CONFIRM = 0.4


def write_progress(current, total):
    """Write progress to file for server to poll."""
    progress_file = get_data_file_path("change_state_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


def run_adb(*args):
    """Run ADB command."""
    cmd = [ADB] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def get_screen_size():
    """Get screen dimensions."""
    output = run_adb("shell", "wm", "size")
    size = output.split(": ")[1]
    w, h = size.split("x")
    return int(w), int(h)


def find_element_by_text(text):
    """
    Find element by text using UI automator dump.
    Returns (x, y) center coordinates or None if not found.
    """
    run_adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    ui_xml = run_adb("shell", "cat", "/sdcard/ui.xml")
    run_adb("shell", "rm", "/sdcard/ui.xml")
    
    if not ui_xml:
        print("  ERROR: UI dump empty")
        return None
    
    try:
        root = ET.fromstring(ui_xml)
    except ET.ParseError as e:
        print(f"  ERROR: XML parse error: {e}")
        return None
    
    for elem in root.iter('node'):
        node_text = elem.attrib.get('text', '')
        if node_text.lower() == text.lower():
            bounds = elem.attrib.get('bounds', '')
            match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                print(f"  Found '{text}' at ({cx}, {cy})")
                return (cx, cy)
    
    print(f"  WARNING: '{text}' not found on screen")
    return None


def tap(x, y):
    """Tap at coordinates."""
    run_adb("shell", "input", "tap", str(x), str(y))
    time.sleep(DELAY_TAP)


def type_text(text):
    """Type text via ADB."""
    escaped = text.replace(" ", "%s")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("&", "\\&")
    escaped = escaped.replace("(", "\\(")
    escaped = escaped.replace(")", "\\)")
    escaped = escaped.replace("+", "\\+")
    subprocess.run([ADB, "shell", "input", "text", escaped], capture_output=True)


def press_enter():
    """Press Enter key."""
    run_adb("shell", "input", "keyevent", "KEYCODE_ENTER")
    time.sleep(DELAY_TAP)


def tap_confirm():
    """Tap Confirm button - portrait mode coordinates (1080x2400)."""
    confirm_x = 900
    confirm_y = 2100
    
    print(f"  -> Tapping CONFIRM at ({confirm_x}, {confirm_y})")
    run_adb("shell", "input", "tap", str(confirm_x), str(confirm_y))
    time.sleep(DELAY_AFTER_CONFIRM)


def press_down():
    """Press DOWN key."""
    run_adb("shell", "input", "keyevent", "KEYCODE_DPAD_DOWN")
    time.sleep(0.02)


def navigate_to_change_item_state():
    """
    Navigate from main menu to Change Item State screen.
    Method: Press DOWN 9 times, then ENTER to select.
    """
    print("\n=== NAVIGATING TO CHANGE ITEM STATE ===")
    
    for i in range(9):
        print(f"  DOWN {i + 1}/9")
        press_down()
    
    time.sleep(0.3)
    
    print("  -> Pressing ENTER to select...")
    press_enter()
    time.sleep(DELAY_SCREEN)
    
    print("=== NAVIGATION COMPLETE ===\n")


def process_item(imei, product_id, index, total):
    """Process a single IMEI/Product ID pair - BATCHED for speed."""
    print(f"\n[{index}/{total}] {imei} -> {product_id[:30]}...")
    
    def escape(t):
        e = t.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        e = e.replace("&", "\\&").replace("(", "\\(").replace(")", "\\)")
        e = e.replace("+", "\\+")
        return e
    
    imei_esc = escape(imei)
    pid_esc = escape(product_id)
    
    # BATCH: Type IMEI + Enter in one call
    subprocess.run([ADB, "shell", f"input text {imei_esc} && input keyevent KEYCODE_ENTER"], capture_output=True)
    time.sleep(DELAY_SCREEN)
    
    # BATCH: Type Product ID + Enter in one call
    subprocess.run([ADB, "shell", f"input text {pid_esc} && input keyevent KEYCODE_ENTER"], capture_output=True)
    time.sleep(DELAY_SCREEN)
    
    # Tap Confirm
    tap_confirm()
    
    print(f"  Done!")


def main():
    """Main automation loop."""
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    with open(data_file, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    # Parse pairs (IMEI, Product ID)
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        imei = lines[i]
        product_id = lines[i + 1]
        pairs.append((imei, product_id))
    
    total = len(pairs)
    print(f"\n{'='*60}")
    print(f"CHANGE ITEM STATE AUTOMATION")
    print(f"ADB path: {ADB}")
    print(f"Found {total} IMEI/Product ID pairs to process")
    print(f"{'='*60}")
    
    if total == 0:
        print("ERROR: No valid pairs found in receive.txt")
        return
    
    # Show preview
    print("\nPreview:")
    for i, (imei, pid) in enumerate(pairs[:3], 1):
        print(f"  {i}. {imei} -> {pid[:40]}...")
    if total > 3:
        print(f"  ... and {total - 3} more")
    
    print("\nGO!")
    
    # Initialize progress
    write_progress(0, total)
    
    # Navigate to Change Item State screen
    navigate_to_change_item_state()
    
    # Process each pair
    for i, (imei, product_id) in enumerate(pairs, 1):
        process_item(imei, product_id, i, total)
        # Update progress after each item
        write_progress(i, total)
    
    print(f"\n{'='*60}")
    print(f"ALL DONE! Processed {total} items.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
