import logging
import sys
from typing import Optional

logger = logging.getLogger("student_agent.monitor")

# Check pywin32 availability for Windows active window detection
IS_WINDOWS = sys.platform == "win32"
win32gui = None

if IS_WINDOWS:
    try:
        import win32gui
    except ImportError:
        logger.warning("pywin32 library not found on Windows platform.")


class WindowMonitor:
    """Monitors currently active/focused foreground window."""

    def __init__(self):
        self.last_title: Optional[str] = None

    def get_active_window_title(self) -> str:
        """Returns the title of the active focused window."""
        title = ""
        if IS_WINDOWS and win32gui is not None:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd)
            except Exception as e:
                logger.debug(f"Error fetching foreground window: {e}")

        # Fallback or non-windows placeholder logic
        if not title:
            title = self.last_title or "Active Desktop Session"

        self.last_title = title
        return title
