"""
Error Detector - Monitor Android emulator screen for red error indicators
Uses MSS for fast screen capture and numpy for color analysis
Thread-safe, non-blocking background monitoring
"""
import threading
import time
import numpy as np
from typing import Callable, Optional

try:
    import mss
except ImportError:
    mss = None
    print("Warning: mss not installed. Error detection will be disabled.")


class ErrorDetector:
    """
    Monitors screen for red color indicators that signal errors.
    Runs in background thread during automation execution.
    """

    # Red color detection thresholds (RGB)
    RED_THRESHOLD = {
        'r_min': 150,  # Red channel minimum
        'g_max': 100,  # Green channel maximum
        'b_max': 100   # Blue channel maximum
    }

    # Trigger error when this percentage of screen pixels are red
    ERROR_THRESHOLD = 0.05  # 5% of screen area

    # Sampling rate (seconds between captures)
    SAMPLE_RATE = 1.0  # 1 FPS

    def __init__(self, callback: Optional[Callable] = None, monitor_index: int = 0):
        """
        Initialize error detector.

        Args:
            callback: Function to call when error is detected
            monitor_index: Which monitor to capture (0 = primary)
        """
        self.callback = callback
        self.monitor_index = monitor_index
        self._running = False
        self._thread = None
        self._error_detected = False
        self._sct = None

        if mss is None:
            print("ERROR: mss library not available. Install with: pip install mss")

    def start(self):
        """Start monitoring in background thread"""
        if mss is None:
            print("Error detection disabled - mss not installed")
            return

        if self._running:
            print("Error detector already running")
            return

        self._running = True
        self._error_detected = False
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("Error detector started")

    def stop(self):
        """Stop monitoring and clean up"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

        if self._sct:
            try:
                self._sct.close()
            except:
                pass
            self._sct = None

        print("Error detector stopped")

    def is_error_detected(self) -> bool:
        """Check if error has been detected"""
        return self._error_detected

    def _monitor_loop(self):
        """Main monitoring loop (runs in background thread)"""
        try:
            self._sct = mss.mss()

            while self._running:
                try:
                    # Capture screen
                    monitor = self._sct.monitors[self.monitor_index + 1]  # +1 because 0 is all monitors
                    screenshot = self._sct.grab(monitor)

                    # Convert to numpy array (RGB)
                    img = np.array(screenshot)

                    # Check for red pixels
                    if self._detect_red(img):
                        self._error_detected = True
                        print("⚠️ ERROR DETECTED: Red screen indicator found!")

                        # Call callback if provided
                        if self.callback:
                            try:
                                self.callback()
                            except Exception as e:
                                print(f"Error in detector callback: {e}")

                        # Stop monitoring after detection
                        self._running = False
                        break

                    # Wait before next sample
                    time.sleep(self.SAMPLE_RATE)

                except Exception as e:
                    print(f"Error in monitor loop: {e}")
                    time.sleep(self.SAMPLE_RATE)

        except Exception as e:
            print(f"Fatal error in error detector: {e}")
        finally:
            if self._sct:
                try:
                    self._sct.close()
                except:
                    pass

    def _detect_red(self, img: np.ndarray) -> bool:
        """
        Detect if image contains significant red pixels.

        Args:
            img: Image as numpy array (H x W x 4) - BGRA format from mss

        Returns:
            True if red pixels exceed threshold
        """
        try:
            # MSS returns BGRA format, convert to RGB
            # img shape: (height, width, 4) where channels are B, G, R, A
            b = img[:, :, 0]
            g = img[:, :, 1]
            r = img[:, :, 2]

            # Find pixels matching red criteria
            # Red pixel: R > 150, G < 100, B < 100
            red_mask = (
                (r > self.RED_THRESHOLD['r_min']) &
                (g < self.RED_THRESHOLD['g_max']) &
                (b < self.RED_THRESHOLD['b_max'])
            )

            # Calculate percentage of red pixels
            total_pixels = r.size
            red_pixels = np.sum(red_mask)
            red_percentage = red_pixels / total_pixels if total_pixels > 0 else 0

            # Debug output (only when red detected)
            if red_percentage > 0.01:  # 1% threshold for logging
                print(f"Red pixels detected: {red_percentage:.2%} of screen")

            # Trigger if exceeds threshold
            return red_percentage > self.ERROR_THRESHOLD

        except Exception as e:
            print(f"Error in red detection: {e}")
            return False


# Quick test
if __name__ == "__main__":
    print("Testing Error Detector...")
    print(f"Monitoring for red screens (threshold: {ErrorDetector.ERROR_THRESHOLD:.0%})")

    def on_error():
        print("ERROR CALLBACK: Red screen detected!")

    detector = ErrorDetector(callback=on_error)
    detector.start()

    try:
        print("Monitoring... Press Ctrl+C to stop")
        while True:
            time.sleep(1)
            if detector.is_error_detected():
                print("Error was detected - stopping test")
                break
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        detector.stop()
        print("Test complete")
