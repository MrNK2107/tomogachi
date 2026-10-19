import threading
import sys
import logging
from typing import Optional

import audio_guard

logger = logging.getLogger("VoiceAlert")

class VoiceAlert:
    """
    Multimodal audio & speech attention engine.
    Uses Windows SAPI text-to-speech and synthesizer beeps to creatively
    grab user attention when deep distraction or alarm conditions occur.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._speech_lock = threading.Lock()
        self._is_speaking = False

    def speak(self, phrase: str, force: bool = False):
        """Speaks phrase asynchronously via Windows Text-to-Speech (SAPI)."""
        if not self.enabled or sys.platform != "win32":
            return
        if audio_guard.is_audio_silent_mode():
            # Completely respect silent/class/lecture mode
            return

        def _worker():
            with self._speech_lock:
                try:
                    import pythoncom
                    import win32com.client

                    pythoncom.CoInitialize()
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Rate = 1
                    speaker.Volume = 95 if force else 85
                    speaker.Speak(phrase)
                except Exception as e:
                    logger.debug(f"Voice alert exception: {e}")
                finally:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()

    def play_tone(self, tone_type: str = "alert", force: bool = False):
        """Plays distinctive procedural chime or siren."""
        if not self.enabled:
            return

        def _worker():
            try:
                # System audio chime fallback
                if sys.platform == "win32" and force and self.enabled:
                    try:
                        import ctypes
                        ctypes.windll.user32.MessageBeep(0x00000010)  # MB_ICONHAND / system critical alert
                    except Exception:
                        pass

                if tone_type in ("alarm", "siren"):
                    for freq in (700.0, 950.0, 1200.0, 950.0, 1200.0, 700.0):
                        audio_guard.play_alert_tone(frequency=freq, duration=0.10, volume=0.35)
                        import time
                        time.sleep(0.10)
                elif tone_type == "happy":
                    for freq in (523.25, 659.25, 783.99, 1046.50):  # C Major Arpeggio
                        audio_guard.play_alert_tone(frequency=freq, duration=0.08, volume=0.2)
                        import time
                        time.sleep(0.08)
                elif tone_type == "warning":
                    audio_guard.play_alert_tone(frequency=440.0, duration=0.25, volume=0.25)
                else:  # default alert
                    audio_guard.play_alert_tone(frequency=880.0, duration=0.15, volume=0.2)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()
