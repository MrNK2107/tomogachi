"""
Clipboard Tracker - Monitors Windows clipboard activity.
Frequent clipboard usage (copy/paste) is a positive indicator of productive work
such as coding, writing, or editing documents.
"""

import sys
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal


# Windows clipboard API
user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32


def get_clipboard_sequence_number() -> int:
    """
    Returns the clipboard sequence number which increments on every clipboard update.
    This is a lightweight operation that doesn't open the clipboard.
    Returns -1 on error.
    """
    try:
        if hasattr(user32, 'GetClipboardSequenceNumber'):
            return user32.GetClipboardSequenceNumber()
    except Exception:
        pass
    return -1


class ClipboardTrackerWorker(QThread):
    """
    QThread worker that monitors clipboard activity.
    Emits clipboard_update(was_used: bool, change_count: int) every 500ms.
    
    Clipboard usage (copy/cut) is a positive focus indicator:
    - Copying code, text, or data = active work
    - No clipboard activity = could be reading or idle
    """
    clipboard_update = pyqtSignal(bool, int)  # (was_used_since_last_check, total_change_count)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self._last_sequence = get_clipboard_sequence_number()
        self._total_changes = 0
        self._last_was_active = False
        self._still_counter = 0
    
    def run(self):
        # Initialize clipboard sequence
        self._last_sequence = get_clipboard_sequence_number()
        
        while self.running:
            current_seq = get_clipboard_sequence_number()
            
            if current_seq < 0:
                # API not available, emit false
                self.clipboard_update.emit(False, 0)
            else:
                was_used = current_seq != self._last_sequence
                if was_used:
                    self._total_changes += 1
                    self._last_sequence = current_seq
                    self._still_counter = 0
                else:
                    self._still_counter = min(self._still_counter + 1, 10)
                
                # Only emit active if clipboard was used recently (within last 3 checks)
                is_active = was_used or self._still_counter < 3
                
                self.clipboard_update.emit(is_active, self._total_changes)
            
            self.msleep(500)
    
    def stop(self):
        self.running = False
        self.wait()
"""