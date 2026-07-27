import sys
import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_ulong)
    ]

def get_idle_time_seconds() -> float:
    """Returns the time in seconds since the last system-wide keyboard or mouse input."""
    if sys.platform != "win32":
        return 0.0
    try:
        last_input_info = LASTINPUTINFO()
        last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)):
            millis = ctypes.windll.kernel32.GetTickCount64() - last_input_info.dwTime
            return max(0.0, millis / 1000.0)
    except Exception as e:
        pass
    return 0.0

class ActivityTrackerWorker(QThread):
    """
    QThread worker monitoring system-wide keyboard and mouse input activity.
    Emits activity_update(is_active: bool, idle_seconds: float) every 100ms.
    """
    activity_update = pyqtSignal(bool, float)  # (is_active, idle_seconds)

    def __init__(self, idle_threshold_seconds: float = 3.0):
        super().__init__()
        self.idle_threshold = idle_threshold_seconds
        self.running = True

    def run(self):
        while self.running:
            idle_sec = get_idle_time_seconds()
            is_active = idle_sec < self.idle_threshold
            self.activity_update.emit(is_active, idle_sec)
            time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()
