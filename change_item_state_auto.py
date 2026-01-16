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


def type_text_with_verify(text, normalize=None, max_retries=5, delay=0.12):
    """Type text and verify before pressing enter."""
    normalize = normalize or (lambda s: s)
    expected = normalize(text)
    for attempt in range(1, max_retries + 1):
        clear_focused_field(len(expected))
        type_text(text)
        time.sleep(delay)
        focused = get_focused_text()
        if focused is None:
            print(f"  WARNING: Unable to read focused field (attempt {attempt}/{max_retries})")
            delay = min(delay + 0.05, 0.5)
            continue
        if normalize(focused) == expected:
            return True
        print(f"  WARNING: Field mismatch (attempt {attempt}/{max_retries}) -> '{focused}'")
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

    # Type IMEI and verify before Enter
    if not type_text_with_verify(imei, normalize=lambda s: s.replace(" ", "")):
        print("  ERROR: Unable to verify IMEI in input field. Stopping to avoid wrong entry.")
        raise SystemExit(1)
    press_enter()
    time.sleep(DELAY_SCREEN)
    if detect_error_screen():
        print("  ERROR: Error screen detected after IMEI submit. Stopping to avoid wrong entry.")
        raise SystemExit(1)
    
    # Type Product ID and verify before Enter
    if not type_text_with_verify(product_id, normalize=None):
        print("  ERROR: Unable to verify product ID in input field. Stopping to avoid wrong entry.")
        raise SystemExit(1)
    press_enter()
    time.sleep(DELAY_SCREEN)
    if detect_error_screen():
        print("  ERROR: Error screen detected after product ID submit. Stopping to avoid wrong entry.")
        raise SystemExit(1)
    
    # Tap Confirm
    tap_confirm()
    time.sleep(DELAY_SCREEN)
    if detect_error_screen():
        print("  ERROR: Error screen detected after confirm. Stopping to avoid wrong entry.")
        raise SystemExit(1)
    
    print(f"  Done!")


def normalize_imei(raw_value):
    """Normalize a single IMEI line (no validation)."""
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    return cleaned


def load_pairs(data_file):
    """Load IMEI/Product ID pairs from file."""
    with open(data_file, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    pairs = []
    invalid = []
    if len(lines) % 2 != 0:
        invalid.append((len(lines), "", "missing product ID for last IMEI"))

    for i in range(0, len(lines) - 1, 2):
        raw_imei = lines[i]
        product_id = lines[i + 1]
        imei = normalize_imei(raw_imei)
        if not imei:
            invalid.append((i + 1, raw_imei, "empty IMEI"))
            continue
        if not product_id:
            invalid.append((i + 2, product_id, "empty product ID"))
            continue
        pairs.append((imei, product_id))

    return pairs, invalid


def main():
    """Main automation loop."""
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    pairs, invalid = load_pairs(data_file)
    
    total = len(pairs)
    print(f"\n{'='*60}")
    print(f"CHANGE ITEM STATE AUTOMATION")
    print(f"ADB path: {ADB}")
    print(f"Found {total} IMEI/Product ID pairs to process")
    print(f"{'='*60}")
    
    if total == 0:
        print("ERROR: No valid pairs found in receive.txt")
        return

    if invalid:
        print("WARNING: Some lines were skipped due to empty values or missing pairs:")
        for line_no, value, reason in invalid[:10]:
            print(f"  Line {line_no}: '{value}' -> {reason}")
        if len(invalid) > 10:
            print(f"  ... and {len(invalid) - 10} more")
    
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
