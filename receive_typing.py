#!/usr/bin/env python3
"""
Receive Typing - Types product names and IMEIs for receive operations.
Cross-platform compatible (Windows, macOS, Linux).
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

def run_adb(*args):
    """Run ADB command and return stdout."""
    result = subprocess.run([ADB] + list(args), capture_output=True, text=True)
    return result.stdout.strip()


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


def write_progress(current, total):
    """Write progress to file for server to poll."""
    progress_file = get_data_file_path("receive_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


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

def normalize_receive_item(raw_value):
    """
    Normalize a receive item.
    Heuristic: if an item looks like an IMEI (>=12 digits),
    mark as IMEI to enable input verification.
    """
    if raw_value is None:
        return None, False, "empty value"
    cleaned = raw_value.strip()
    if not cleaned:
        return None, False, "empty line"

    compact = cleaned.replace(" ", "")
    digit_count = sum(ch.isdigit() for ch in compact)
    if digit_count >= 12:
        return cleaned, True, None

    return cleaned, False, None


def load_items(data_file):
    """Load receive items from file (skip empty lines only)."""
    items = []
    with open(data_file, "r") as f:
        for line_no, line in enumerate(f, 1):
            item, is_imei, error = normalize_receive_item(line)
            if error:
                continue
            items.append((item, is_imei))
    return items


def main():
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive_data.txt")
    sublocation_file = get_data_file_path("receive_sublocation.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Upload an Excel file via the web interface first.")
        sys.exit(1)
    
    # Read sublocation from file (required)
    sublocation = ""
    if os.path.exists(sublocation_file):
        with open(sublocation_file, "r") as f:
            sublocation = f.read().strip()
    
    if not sublocation:
        print("ERROR: No sublocation found in receive_sublocation.txt")
        print("Enter a sublocation in the web interface before executing.")
        sys.exit(1)
    
    # Read data from file
    items = load_items(data_file)
    
    if not items:
        print("ERROR: No data found in receive_data.txt")
        sys.exit(1)

    total = len(items)
    print(f"ADB path: {ADB}")
    print(f"Sublocation: {sublocation}")
    print(f"Processing {total} items...")
    print("-" * 40)
    
    # Initialize progress
    write_progress(0, total)
    
    # Type sublocation first and press enter
    print(f"[SUBLOCATION] {sublocation}")
    type_text(sublocation)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.1)
    if detect_error_screen():
        print("ERROR: Error screen detected after sublocation submit. Stopping to avoid wrong entry.")
        sys.exit(1)
    
    # First item handled separately
    first_item, first_is_imei = items[0]
    print(f"[1/{total}] {first_item}")
    if first_is_imei:
        if not type_imei_with_verify(first_item):
            print("ERROR: Unable to verify IMEI in input field. Stopping to avoid wrong entry.")
            sys.exit(1)
    else:
        type_text(first_item)
    time.sleep(0.1)
    press_enter()
    time.sleep(0.1)
    if detect_error_screen():
        print("ERROR: Error screen detected after item submit. Stopping to avoid wrong entry.")
        sys.exit(1)
    write_progress(1, total)
    
    for i, (item, is_imei) in enumerate(items[1:], 2):
        print(f"[{i}/{total}] {item}")
        
        # Special handling for iPad items
        if item.lower().startswith('ipad') or item.lower().startswith('good'):
            print("  SKU  found - special handling")
            time.sleep(0.1)
            press_enter()
            print("  Enter pressed")
            time.sleep(0.1)
            type_text(item)
            press_enter()
            print("  Item typed")
            time.sleep(0.1)
            if detect_error_screen():
                print("ERROR: Error screen detected after item submit. Stopping to avoid wrong entry.")
                sys.exit(1)
        else:
            time.sleep(0.1)
            if is_imei:
                if not type_imei_with_verify(item):
                    print("ERROR: Unable to verify IMEI in input field. Stopping to avoid wrong entry.")
                    sys.exit(1)
            else:
                type_text(item)
            time.sleep(0.1)
            press_enter()
            time.sleep(0.1)
            if detect_error_screen():
                print("ERROR: Error screen detected after item submit. Stopping to avoid wrong entry.")
                sys.exit(1)
        
        # Update progress after each item
        write_progress(i, total)
    
    print("-" * 40)
    print(f"DONE! Processed {total} items.")


if __name__ == "__main__":
    main()
