#!/usr/bin/env python3
"""
Type Item State - Types barcodes and confirms state changes.
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

def normalize_imei(raw_value):
    """Normalize a single IMEI line (no validation)."""
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    return cleaned


def load_imeis(data_file):
    """Load IMEIs from file (skip empty lines only)."""
    imeis = []
    with open(data_file, "r") as f:
        for line in f:
            imei = normalize_imei(line)
            if imei:
                imeis.append(imei)
    return imeis


def main():
    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive.txt")
    
    if not os.path.exists(data_file):
        print(f"ERROR: Data file not found: {data_file}")
        print("Create receive.txt with one barcode/IMEI per line.")
        sys.exit(1)
    
    # Read IMEIs from file
    imeis = load_imeis(data_file)
    
    if not imeis:
        print("ERROR: No barcodes found in receive.txt")
        sys.exit(1)

    print(f"ADB path: {ADB}")
    print(f"Processing {len(imeis)} barcodes...")
    print("-" * 40)
    
    for i, imei in enumerate(imeis, 1):
        print(f"[{i}/{len(imeis)}] {imei}")
        if not type_imei_with_verify(imei):
            print("ERROR: Unable to verify IMEI in input field. Stopping to avoid wrong entry.")
            sys.exit(1)
        press_enter()
        time.sleep(0.3)
        if detect_error_screen():
            print("ERROR: Error screen detected after submit. Stopping to avoid wrong entry.")
            sys.exit(1)
        
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
