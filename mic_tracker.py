import sys
import time
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSignal

class MicTrackerWorker(QThread):
    """
    QThread worker listening to system audio input (microphone).
    Detects voice activity / speech in calls, meetings, or dictation.
    Emits mic_update(is_speaking: bool, volume_rms: float) every 100ms.
    """
    mic_update = pyqtSignal(bool, float)

    def __init__(self, threshold_rms: float = 0.012):
        super().__init__()
        self.threshold_rms = threshold_rms
        self.running = True
        self.is_speaking = False
        self.current_rms = 0.0

    def run(self):
        def audio_callback(indata, frames, time_info, status):
            if not self.running:
                return
            try:
                rms = np.sqrt(np.mean(indata**2))
                self.current_rms = float(rms)
                self.is_speaking = self.current_rms > self.threshold_rms
            except Exception:
                self.current_rms = 0.0
                self.is_speaking = False

        try:
            with sd.InputStream(channels=1, samplerate=16000, blocksize=1600, callback=audio_callback):
                while self.running:
                    self.mic_update.emit(self.is_speaking, self.current_rms)
                    time.sleep(0.1)
        except Exception as e:
            # Safe fallback if mic is blocked or device query fails
            while self.running:
                self.mic_update.emit(False, 0.0)
                time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()
