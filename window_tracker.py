import sys
import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal

def get_active_window_title() -> str:
    """Returns the title string of the currently active OS foreground window."""
    if sys.platform != "win32":
        return "Active Workspace"
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            return title if title else "Desktop"
    except Exception:
        pass
    return "Desktop"

class WindowTrackerWorker(QThread):
    """
    QThread worker tracking system foreground application window context.
    Emits window_update(window_title: str) every 500ms.
    """
    window_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.last_title = ""

    def run(self):
        while self.running:
            title = get_active_window_title()
            if title != self.last_title:
                self.last_title = title
                self.window_update.emit(title)
            time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()
