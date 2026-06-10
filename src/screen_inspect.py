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

Coordinate note: the device framebuffer is portrait (e.g. 1080x2400) and that is
ALSO the space `adb shell input tap` uses on this device (verified live: view
point (332,193) on the duplicate screen maps to portrait (193,2067), which
dismissed it). The app's landscape content is rotated inside that portrait
buffer, and the rotation sign is device-specific, so OCR is attempted on BOTH
landscape rotations and we accept whichever yields the expected text - then an
OCR-located "Back" box is mapped back through the inverse rotation into
portrait tap coordinates.

Pillow + pytesseract + the Tesseract engine are required for the OCR step. If any
is missing, OCR_AVAILABLE is False and callers must fall back to stop-on-red
(they cannot confirm a duplicate, so they must not skip).
"""
import io
import os
import re
import shutil
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

# Standard Windows install dirs for the Tesseract engine (winget / UB-Mannheim
# installer puts it in one of these depending on per-user vs all-users install).
_TESSERACT_DIRS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR"),
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
]


def _locate_tesseract():
    """Resolve the tesseract executable: TESSERACT_CMD env var (portable
    deployments) > PATH (pytesseract's default) > standard install dirs.
    Returns an explicit path to set, or None to keep pytesseract's default."""
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd:
        return env_cmd
    if shutil.which("tesseract"):
        return None
    for d in _TESSERACT_DIRS:
        exe = os.path.join(d, "tesseract.exe")
        if os.path.isfile(exe):
            return exe
    return None


def _engine_works():
    """True if the Tesseract engine binary actually answers."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        print(f"screen_inspect: Tesseract engine not usable: {e}")
        return False


if pytesseract is not None:
    _tess_cmd = _locate_tesseract()
    if _tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tess_cmd

# "Available" means the Python bindings import AND the engine binary answers;
# a missing engine must degrade to stop-on-red, not a misleading 'other_red'.
OCR_AVAILABLE = (Image is not None) and (pytesseract is not None) and _engine_works()

# Red-pixel thresholds mirror ErrorDetector (src/error_detector.py). NOTE: a PIL
# image is RGB, unlike mss's BGRA, so the channel indices differ here.
RED_R_MIN = 150
RED_G_MAX = 100
RED_B_MAX = 100
RED_RATIO_THRESHOLD = 0.001  # >0.1% red pixels => an error screen is showing

# Verified live on the Finale duplicate-barcode screen (portrait 1080x2400
# framebuffer): tapping this point dismisses it. Used whenever OCR confirms a
# duplicate but cannot locate the "Back" word itself.
BACK_TAP_FALLBACK = (193, 2067)

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
    """Yield (image, rotation) pairs likely to be upright-landscape.

    The device buffer is portrait but the app is landscape; the rotation sign is
    device-specific, so we try both 90-degree rotations and let OCR decide. If
    the capture is already landscape we use it as-is. `rotation` records how the
    buffer was rotated to produce the view ('cw', 'ccw' or 'none') so points can
    be mapped back into buffer/tap coordinates.
    """
    w, h = img.size
    if w >= h:
        yield img, "none"
    else:
        yield img.rotate(-90, expand=True), "cw"   # clockwise
        yield img.rotate(90, expand=True), "ccw"   # counter-clockwise


def _view_to_tap_xy(xv, yv, rotation, buffer_size):
    """Map a point in the upright view back to `input tap` coordinates.

    Taps are injected in the native (portrait) framebuffer space - verified
    live on the duplicate screen. Inverse of the view rotation:
      cw  (view = buffer rotated clockwise):  x = yv, y = bufH - 1 - xv
      ccw (view = buffer rotated ccw):        x = bufW - 1 - yv, y = xv
      none (buffer already landscape):        view == buffer
    """
    bw, bh = buffer_size
    if rotation == "cw":
        return int(yv), int(bh - 1 - xv)
    if rotation == "ccw":
        return int(bw - 1 - yv), int(xv)
    return int(xv), int(yv)


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
    """Return the (x, y) center of the on-screen 'Back' word in VIEW pixels."""
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        print(f"screen_inspect: image_to_data failed: {e}")
        return None
    for i, word in enumerate(data.get("text", [])):
        if word.strip().lower() == "back":
            cx = data["left"][i] + data["width"][i] / 2
            cy = data["top"][i] + data["height"][i] / 2
            return cx, cy
    return None


def classify_frame(img):
    """Classify a frame already known to be red.

    Returns a state dict; for duplicates, back_xy is in input-tap coordinates
    (OCR-located and rotation-mapped, with the live-verified fixed position as
    fallback when the word itself can't be found).
    """
    for candidate, rotation in _landscape_candidates(img):
        if _looks_like_duplicate(_ocr(candidate)):
            view_xy = _find_back_xy(candidate)
            if view_xy:
                back_xy = _view_to_tap_xy(view_xy[0], view_xy[1], rotation, img.size)
            else:
                back_xy = BACK_TAP_FALLBACK
            return {"state": "duplicate", "back_xy": back_xy}
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
    any_capture_ok = False
    for _ in range(max(1, attempts)):
        time.sleep(interval)
        img = capture_raw(adb_path)
        if img is None:
            continue
        any_capture_ok = True
        if is_screen_red(img):
            red_img = img
            break

    if red_img is None:
        if not any_capture_ok:
            # Every capture failed: we know nothing about the screen, so the
            # caller must stop rather than keep typing into an unknown state.
            return {"state": "unknown", "back_xy": None}
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
            for c, rot in _landscape_candidates(frame):
                txt = _normalize(_ocr(c)).strip()
                print(f"  rotation {rot} {c.size} OCR -> {txt[:120]!r}")
