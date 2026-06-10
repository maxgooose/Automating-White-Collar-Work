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
    from adb_utils import (get_adb_path, get_data_file_path, check_stop_signal,
                           clear_stop_signal, PRODUCT_MARKER)
except ImportError:
    from src.adb_utils import (get_adb_path, get_data_file_path, check_stop_signal,
                               clear_stop_signal, PRODUCT_MARKER)

try:
    import screen_inspect
except ImportError:
    from src import screen_inspect

# Get cross-platform ADB path
ADB = get_adb_path()

# --- Duplicate-barcode ("Barcode already exists!") handling ---
# After each IMEI we screenshot and look for the red error screen. These tune the
# speed/reliability tradeoff: more attempts / a longer interval catches a
# late-rendering error but slows the (common) success path. Lower them if the
# device renders the error quickly.
DUP_SETTLE_ATTEMPTS = 2
DUP_SETTLE_INTERVAL = 0.3
# Heavier settle waits so the app fully records the dismissal before we move on.
DUP_DISMISS_WAIT = 1.0       # after pressing Back, before checking it cleared
DUP_POST_SKIP_WAIT = 2.0     # after a confirmed skip, before typing the next IMEI

# Fallback product detection for receive_data.txt files written before the
# server started marking product lines with PRODUCT_MARKER.
LEGACY_PRODUCT_PREFIXES = ("ipad", "good", "iphone", "accep", "galaxy")


def parse_receive_items(lines):
    """Classify data-file lines into ('product'|'imei', value) tuples.

    Files written by the current server mark product lines with PRODUCT_MARKER;
    everything else is an IMEI. Files without any marker (older deployments /
    hand-made) fall back to the legacy prefix heuristic.
    """
    has_markers = any(line.startswith(PRODUCT_MARKER) for line in lines)
    items = []
    for line in lines:
        if has_markers:
            if line.startswith(PRODUCT_MARKER):
                items.append(("product", line[len(PRODUCT_MARKER):].strip()))
            else:
                items.append(("imei", line))
        elif line.lower().startswith(LEGACY_PRODUCT_PREFIXES):
            items.append(("product", line))
        else:
            items.append(("imei", line))
    return items


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


def tap(x, y):
    """Tap at device coordinates via ADB."""
    subprocess.run([ADB, "shell", "input", "tap", str(x), str(y)], capture_output=True)


def press_back_key():
    """Press the hardware Back key via ADB."""
    subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_BACK"], capture_output=True)


def append_skipped(imei, product=""):
    """Record a skipped duplicate IMEI (tab-separated: imei, product, time).

    One line per skip, so line-count consumers keep working; the server's
    Excel download parses the columns.
    """
    skipped_file = get_data_file_path("receive_skipped.txt")
    with open(skipped_file, "a") as f:
        f.write(f"{imei}\t{product}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")


def dismiss_error_screen(back_xy):
    """Dismiss the 'Barcode already exists!' screen and confirm it cleared.

    Attempt order (screenshot-verified between attempts):
      1. the OCR-located on-screen Back button (rotation-mapped tap coords),
      2. the live-verified fixed Back position (screen_inspect.BACK_TAP_FALLBACK),
      3. the hardware Back key (last resort; the app ignores it on this screen,
         but it costs nothing to try).
    Returns True once the red error screen is gone.
    """
    attempts = []
    if back_xy:
        attempts.append(lambda: tap(*back_xy))
    attempts.append(lambda: tap(*screen_inspect.BACK_TAP_FALLBACK))
    attempts.append(press_back_key)
    for attempt in attempts:
        attempt()
        time.sleep(DUP_DISMISS_WAIT)
        if screen_inspect.is_clear(ADB):
            return True
    return False


def submit_imei_and_handle_dup(imei, index, total, product=""):
    """Type an IMEI, submit it, and handle the duplicate-barcode error screen.

    Returns 'ok' if accepted, or 'skipped' if it already existed and was skipped
    (the IMEI is already in the system, so it is NOT re-typed). Exits the process
    (non-zero) on an unrecognized / unconfirmable error screen so the run stops
    instead of typing the next IMEI into the wrong screen.
    """
    type_text(imei)
    time.sleep(0.1)
    press_enter()

    state = screen_inspect.read_screen_state(
        ADB, attempts=DUP_SETTLE_ATTEMPTS, interval=DUP_SETTLE_INTERVAL
    )

    if state["state"] == "clear":
        return "ok"

    if state["state"] == "duplicate":
        if check_stop_signal("receive"):
            sys.exit(0)
        if not dismiss_error_screen(state["back_xy"]):
            sys.stderr.write(
                f"Could not dismiss 'Barcode already exists' screen for {imei}; stopping.\n"
            )
            sys.exit(1)
        append_skipped(imei, product)
        print(f"  [SKIPPED {index}/{total}] {imei} - already exists")
        time.sleep(DUP_POST_SKIP_WAIT)
        return "skipped"

    # other_red / red_no_ocr / unknown -> stop safely (never silently skip).
    reasons = {
        "other_red": "an unrecognized red error screen",
        "red_no_ocr": "a red error screen (OCR unavailable to confirm duplicates)",
        "unknown": "an unreadable screen",
    }
    reason = reasons.get(state["state"], "an error screen")
    sys.stderr.write(f"Stopped at IMEI {imei}: {reason}.\n")
    sys.exit(1)


def write_progress(current, total):
    """Write progress to file for server to poll."""
    progress_file = get_data_file_path("receive_progress.txt")
    with open(progress_file, 'w') as f:
        f.write(f"{current},{total}")


def main():
    # A stop file left over from a previous (stopped/crashed) run must not
    # kill this run: the stop signal only targets a live process.
    clear_stop_signal("receive")

    # Get data file path (cross-platform)
    data_file = get_data_file_path("receive_data.txt")
    
    if not os.path.exists(data_file):
        # stderr so the server surfaces this in the UI instead of a silent stop
        sys.stderr.write(f"Data file not found: {data_file}. "
                         "Upload an Excel file via the web interface first.\n")
        sys.exit(1)
    
    # Read sublocation from file (written by server)
    sublocation_file = get_data_file_path("receive_sublocation.txt")
    sublocation = ""
    if os.path.exists(sublocation_file):
        with open(sublocation_file, "r") as f:
            sublocation = f.read().strip()
    
    # Read data from file and classify lines as products vs IMEIs
    with open(data_file, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    items = parse_receive_items(lines)

    if not items:
        print("ERROR: No data found in receive_data.txt")
        sys.exit(1)

    total = len(items)
    print(f"ADB path: {ADB}")
    print(f"Processing {total} items...")
    print("-" * 40)
    
    # Initialize progress. NOTE: the skipped log (receive_skipped.txt) is
    # owned by the server - it clears it for fresh runs and keeps it for
    # resumed runs, so the download covers the whole batch.
    write_progress(0, total)


    # Type sublocation and submit
    if sublocation:
        print(f"[SUBLOCATION] {sublocation}")
        type_text(sublocation)
        time.sleep(0.1)
        press_enter()
        time.sleep(0.1)
    
    # Track which product the current IMEIs belong to (for the skipped log)
    current_product = ""

    # First item handled separately (fresh screen: no leading ENTER needed)
    first_kind, first_value = items[0]
    if first_kind == "product":
        current_product = first_value
    print(f"[1/{total}] {first_value}")
    type_text(first_value)
    time.sleep(1)
    press_enter()
    time.sleep(1)
    current = 1
    write_progress(current, total)

    for i, (kind, value) in enumerate(items[1:], 2):
        # Check for stop signal BEFORE processing this item
        if check_stop_signal('receive'):
            print(f"Stop signal received. Stopping at item {i-1}/{total}")
            sys.exit(0)

        print(f"[{i}/{total}] {value}")

        if kind == "product":
            current_product = value
            print("  Product line - special handling")
            press_enter()
            time.sleep(3)  # 3 seconds before text is written
            type_text(value)
            time.sleep(3)  # 3 seconds before pressing enter on it
            press_enter()
            time.sleep(3)  # 3 seconds after pressing enter
            print("  Item typed")
        else:
            time.sleep(0.1)
            submit_imei_and_handle_dup(value, i, total, current_product)

        # Update progress after each item
        current += 1
        write_progress(current, total)
    
    print("-" * 40)
    print(f"DONE! Processed {total} items.")


if __name__ == "__main__":
    main()
