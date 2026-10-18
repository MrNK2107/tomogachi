import ctypes
import time
from typing import Tuple

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]

class IdleDetector:
    """Detects physical inactivity on Windows via GetLastInputInfo."""

    def __init__(self):
        self._last_input_info = LASTINPUTINFO()
        self._last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)

    def get_idle_seconds(self) -> float:
        """Returns the number of seconds since the last mouse or keyboard input."""
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(self._last_input_info)):
            return 0.0

        current_tick = ctypes.windll.kernel32.GetTickCount()
        elapsed_ms = (current_tick - self._last_input_info.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000.0

    def get_idle_minutes(self) -> float:
        """Returns the number of minutes since the last mouse or keyboard input."""
        return self.get_idle_seconds() / 60.0

    def is_idle(self, threshold_minutes: float) -> bool:
        """Returns True if user has been inactive for >= threshold_minutes."""
        return self.get_idle_minutes() >= threshold_minutes

    def get_status_summary(self, threshold_minutes: float) -> Tuple[bool, float]:
        """Returns (is_idle, idle_minutes)."""
        idle_mins = self.get_idle_minutes()
        return (idle_mins >= threshold_minutes, idle_mins)
