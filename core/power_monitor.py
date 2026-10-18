import threading
import logging
import time
import requests
import win32gui
import win32con
import win32ts
from typing import Callable, Optional
import config
from quiz.roast_bank import get_shutdown_roast

logger = logging.getLogger("PowerMonitor")

WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016

class PowerMonitor:
    """Listens for Windows Sleep, Lid Closed, Shutdown, and Screen Lock events."""

    PBT_APMSUSPEND = 0x0004
    PBT_APMRESUMEAUTOMATIC = 0x0012
    WTS_SESSION_LOCK = 0x7
    WTS_SESSION_UNLOCK = 0x8

    def __init__(self, on_sleep_or_shutdown: Optional[Callable] = None):
        self.on_sleep_or_shutdown = on_sleep_or_shutdown
        self.hwnd = None
        self.thread = None
        self.running = False
        self._last_event_time = 0

    def start(self):
        """Starts background Windows message pump in a daemon thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_window, daemon=True, name="PowerMonitorThread")
        self.thread.start()
        logger.info("Windows Power & Screen Lock monitor thread started.")

    def _run_window(self):
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "AwakenPowerMonitorWindow"
        wc.lpfnWndProc = self._wnd_proc

        try:
            atom = win32gui.RegisterClass(wc)
        except Exception:
            atom = win32gui.GetClassInfo(0, "AwakenPowerMonitorWindow")

        self.hwnd = win32gui.CreateWindow(
            atom,
            "AwakenPowerMonitor",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            None
        )

        try:
            win32ts.WTSRegisterSessionNotification(self.hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
        except Exception as e:
            logger.warning(f"Could not register session lock notification: {e}")

        # Windows message loop
        while self.running:
            try:
                win32gui.PumpWaitingMessages()
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in power message pump: {e}")
                break

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        now = time.time()
        # Debounce multiple consecutive events
        if now - self._last_event_time < 5.0:
            return 0

        # 1. System Sleep / Lid Close
        if msg == WM_POWERBROADCAST:
            if wparam == self.PBT_APMSUSPEND:
                self._last_event_time = now
                logger.warning("[!] System sleep / lid close event detected!")
                self._trigger_shutdown_roast("Lid Closed / Sleep Mode")
            return 1

        # 2. System Shutdown / Restart / Logoff
        elif msg in (WM_QUERYENDSESSION, WM_ENDSESSION):
            self._last_event_time = now
            logger.warning("[!] System shutdown / logoff event detected!")
            self._trigger_shutdown_roast("System Shutdown")
            return 1

        # 3. Windows Session Lock (Win + L)
        elif msg == WM_WTSSESSION_CHANGE:
            if wparam == self.WTS_SESSION_LOCK:
                self._last_event_time = now
                logger.warning("[!] Screen locked (Win+L) detected!")
                self._trigger_shutdown_roast("Screen Locked")
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _trigger_shutdown_roast(self, trigger_reason: str):
        """Immediately fires a synchronous roast to Telegram before system power cuts off."""
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            return

        roast_text = get_shutdown_roast()
        full_msg = f"{roast_text}\n\n_(Triggered by: {trigger_reason})_"

        try:
            # Synchronous request so Windows doesn't cut execution before it's sent
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": full_msg,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=4.0)
            logger.info(f"Shutdown/Sleep roast dispatched via HTTP: {resp.status_code}")
        except Exception as e:
            logger.error(f"Failed to send shutdown roast: {e}")

    def stop(self):
        self.running = False
        if self.hwnd:
            try:
                win32ts.WTSUnRegisterSessionNotification(self.hwnd)
                win32gui.DestroyWindow(self.hwnd)
            except Exception:
                pass
