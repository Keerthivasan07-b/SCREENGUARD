import logging
from typing import Optional
import mss
import numpy as np

logger = logging.getLogger("student_agent.capture")


class ScreenCapturer:
    """Fast screen capturer using mss."""

    def __init__(self, monitor_index: int = 1):
        self.monitor_index = monitor_index
        self._sct: Optional[mss.mss] = None

    def start(self):
        if self._sct is None:
            self._sct = mss.mss()
            logger.info("ScreenCapturer initialized with mss.")

    def stop(self):
        if self._sct is not None:
            self._sct.close()
            self._sct = None
            logger.info("ScreenCapturer stopped.")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures the primary monitor screen and returns it as a BGR NumPy array."""
        if self._sct is None:
            self.start()

        try:
            monitors = self._sct.monitors
            idx = self.monitor_index if self.monitor_index < len(monitors) else 1
            monitor = monitors[idx]

            sct_img = self._sct.grab(monitor)
            # mss returns BGRA array, convert to BGR for OpenCV
            frame_bgra = np.array(sct_img, dtype=np.uint8)
            frame_bgr = frame_bgra[:, :, :3]  # Drop alpha channel
            return frame_bgr
        except Exception as e:
            logger.error(f"Error capturing screen frame: {e}")
            return None
