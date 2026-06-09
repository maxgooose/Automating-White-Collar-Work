"""
Screen Inspector - read the Finale Inventory app screen via screenshot + OCR.

The Finale app renders to a SurfaceView, so `uiautomator` returns no text
(see TEXT_EXTRACTION_TRIAL.md). To detect the "Barcode already exists!" duplicate
screen during the Receive flow we therefore:
  1. take a quick device screenshot and do a cheap red-pixel check, and
  2. ONLY when red is present, OCR the screen to confirm the message before
     skipping the IMEI.

Capture uses `adb exec-out screencap -p` (raw PNG on stdout) to avoid the Windows
CRLF corruption that affects `adb shell screencap -p`; a screencap+pull fallback
covers old adb builds.

Coordinate note: the device framebuffer is portrait (e.g. 1080x2400) while the
app and `adb input tap` use a landscape (2400x1080) space, and the framebuffer's
text is rotated 90 degrees. The exact rotation sign is device-specific, so OCR is
attempted on BOTH landscape rotations and we accept whichever yields the expected
text. That same orientation is the one in which an OCR-located "Back" box maps
onto input-tap coordinates.

Pillow + pytesseract + the Tesseract engine are required for the OCR step. If any
is missing, OCR_AVAILABLE is False and callers must fall back to stop-on-red
(they cannot confirm a duplicate, so they must not skip).
"""
import io
import os
import re
import subprocess
import tempfile
import time

import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

# Allow pointing at a Tesseract engine that isn't on PATH (e.g. a portable
# Windows deployment): set TESSERACT_CMD to the tesseract executable path.
if pytesseract is not None:
    _tess_cmd = os.environ.get("TESSERACT_CMD")
    if _tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tess_cmd

OCR_AVAILABLE = (Image is not None) and (pytesseract is not None)

# Red-pixel thresholds mirror ErrorDetector (src/error_detector.py). NOTE: a PIL
# image is RGB, unlike mss's BGRA, so the channel indices differ here.
RED_R_MIN = 150
RED_G_MAX = 100
RED_B_MAX = 100
RED_RATIO_THRESHOLD = 0.001  # >0.1% red pixels => an error screen is showing

# Landscape logical resolution that `adb input tap` expects (android_controller.py).
TAP_WIDTH = 2400
TAP_HEIGHT = 1080

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _run_binary(adb_path, *args, timeout=10):
    """Run an adb command and return raw stdout bytes (best-effort)."""
    try:
        return subprocess.run(
            [adb_path, *args], capture_output=True, timeout=timeout
        ).stdout
    except Exception as e:
        print(f"screen_inspect: adb {' '.join(args)} failed: {e}")
        return b""


def _capture_via_pull(adb_path):
    """Fallback capture for old adb builds without exec-out: screencap + pull."""
    remote = "/sdcard/_si_capture.png"
    try:
        subprocess.run(
            [adb_path, "shell", "screencap", "-p", remote],
            capture_output=True, timeout=10,
        )
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "cap.png")
            subprocess.run(
                [adb_path, "pull", remote, local], capture_output=True, timeout=10
            )
            subprocess.run(
                [adb_path, "shell", "rm", remote], capture_output=True, timeout=5
            )
            if os.path.exists(local):
                with open(local, "rb") as f:
                    return f.read()
    except Exception as e:
        print(f"screen_inspect: fallback capture failed: {e}")
    return b""


def capture_raw(adb_path):
    """Capture the current screen as a PIL RGB Image (no rotation), or None."""
    if Image is None:
        return None

    png = _run_binary(adb_path, "exec-out", "screencap", "-p")
    if not png.startswith(_PNG_MAGIC):
        # exec-out unavailable or output got mangled -> try the file-based path.
        png = _capture_via_pull(adb_path)
    if not png.startswith(_PNG_MAGIC):
        return None

    try:
        return Image.open(io.BytesIO(png)).convert("RGB")
    except Exception as e:
        print(f"screen_inspect: PNG decode failed: {e}")
        return None


def is_screen_red(img):
    """True if the screenshot has enough pure-red pixels to be an error screen."""
    if img is None:
        return False
    arr = np.asarray(img)  # (H, W, 3) RGB
    if arr.ndim != 3 or arr.shape[2] < 3:
        return False
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    red_mask = (r > RED_R_MIN) & (g < RED_G_MAX) & (b < RED_B_MAX)
    total = red_mask.size
    if total == 0:
        return False
    return (np.count_nonzero(red_mask) / total) > RED_RATIO_THRESHOLD


def _landscape_candidates(img):
    """Yield images likely to be upright-landscape.

    The device buffer is portrait but the app is landscape; the rotation sign is
    device-specific, so we try both 90-degree rotations and let OCR decide. If
    the capture is already landscape we use it as-is.
    """
    w, h = img.size
    if w >= h:
        yield img
    else:
        yield img.rotate(-90, expand=True)  # clockwise
        yield img.rotate(90, expand=True)   # counter-clockwise


def _normalize(text):
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def _ocr(img):
    try:
        return pytesseract.image_to_string(img)
    except Exception as e:
        print(f"screen_inspect: OCR failed: {e}")
        return ""


def _looks_like_duplicate(text):
    t = _normalize(text)
    return ("already exists" in t) or ("barcode" in t and "exists" in t)


def _find_back_xy(img):
    """Return (x, y) tap coordinates for the on-screen 'Back' word, or None."""
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        print(f"screen_inspect: image_to_data failed: {e}")
        return None
    w, h = img.size
    scale_x = TAP_WIDTH / w if w else 1
    scale_y = TAP_HEIGHT / h if h else 1
    for i, word in enumerate(data.get("text", [])):
        if word.strip().lower() == "back":
            cx = data["left"][i] + data["width"][i] / 2
            cy = data["top"][i] + data["height"][i] / 2
            return int(cx * scale_x), int(cy * scale_y)
    return None


def classify_frame(img):
    """Classify a frame already known to be red. Returns a state dict."""
    for candidate in _landscape_candidates(img):
        if _looks_like_duplicate(_ocr(candidate)):
            return {"state": "duplicate", "back_xy": _find_back_xy(candidate)}
    return {"state": "other_red", "back_xy": None}


def read_screen_state(adb_path, attempts=2, interval=0.3):
    """Poll the screen after an action and classify it.

    Returns {'state': <str>, 'back_xy': (x, y) | None}:
      'clear'      - no error screen detected within the settle window (success)
      'duplicate'  - red + OCR-confirmed "Barcode already exists!"
      'other_red'  - red, but not the duplicate message (genuine error)
      'red_no_ocr' - red, but OCR unavailable (cannot confirm -> caller stops)
      'unknown'    - screen capture failed
    """
    red_img = None
    for _ in range(max(1, attempts)):
        time.sleep(interval)
        img = capture_raw(adb_path)
        if img is None:
            continue
        if is_screen_red(img):
            red_img = img
            break

    if red_img is None:
        # capture may have failed every time, or there was simply no red screen.
        return {"state": "clear", "back_xy": None}

    if not OCR_AVAILABLE:
        return {"state": "red_no_ocr", "back_xy": None}

    return classify_frame(red_img)


def is_clear(adb_path):
    """True if the screen currently shows no red error (used to confirm dismissal)."""
    img = capture_raw(adb_path)
    if img is None:
        return False  # can't confirm -> treat as not-clear (fail safe)
    return not is_screen_red(img)


# Quick manual test / calibration helper:
#   python src/screen_inspect.py
# Put the emulator on the screen you want to check, then run this.
if __name__ == "__main__":
    try:
        from adb_utils import get_adb_path
    except ImportError:
        from src.adb_utils import get_adb_path

    adb = get_adb_path()
    print(f"OCR_AVAILABLE: {OCR_AVAILABLE}")
    frame = capture_raw(adb)
    if frame is None:
        print("Capture FAILED (no device / screencap error).")
    else:
        print(f"Captured frame size (w x h): {frame.size}")
        print(f"is_screen_red: {is_screen_red(frame)}")
        if is_screen_red(frame):
            print(f"classify_frame: {classify_frame(frame)}")
        elif OCR_AVAILABLE:
            for c in _landscape_candidates(frame):
                txt = _normalize(_ocr(c)).strip()
                print(f"  rotation {c.size} OCR -> {txt[:120]!r}")
