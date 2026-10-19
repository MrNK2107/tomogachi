import os
import json
import logging
import threading
import time
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger("PhoneAlert")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "phone_config.json")

DEFAULT_PHONE_CONFIG = {
    "enabled": True,
    "ntfy_topic": "awaken_phantom_832313259",
    "ntfy_server": "https://ntfy.sh",
    "webhook_url": os.getenv("MACRODROID_WEBHOOK_URL", "https://trigger.macrodroid.com/a61b3516-109b-4e8d-95ea-cc1e6d428d07/id1"),
    "vibrate_pattern": "1000,300,1000,300,1000,500,2000",
    "last_alert_time": 0.0,
    "cooldown_seconds": 300.0,  # 5 minutes minimum between buzzes to avoid spam
}

class PhoneAlertManager:
    """
    Dispatches out-of-band mobile alerts that physically vibrate, buzz, and manipulate
    the user's smartphone when they are away from their laptop for too long.
    
    Supports:
    1. ntfy.sh: Free, zero-signup Android & iOS app. Supports high-priority alerts,
       custom aggressive vibration patterns, deep-links, and persistent heads-up notifications.
    2. MacroDroid / Tasker Webhook: Can trigger continuous phone vibration, flash camera LED,
       turn screen on, or open apps directly on Android.
    """

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    merged = DEFAULT_PHONE_CONFIG.copy()
                    merged.update(cfg)
                    return merged
        except Exception as e:
            logger.warning(f"Could not load phone config: {e}")
        return DEFAULT_PHONE_CONFIG.copy()

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save phone config: {e}")

    def set_topic(self, topic: str):
        self.config["ntfy_topic"] = topic.strip().replace(" ", "_")
        self.save_config()

    def set_webhook(self, url: str):
        self.config["webhook_url"] = url.strip()
        self.save_config()

    def set_enabled(self, enabled: bool):
        self.config["enabled"] = bool(enabled)
        self.save_config()

    def get_ntfy_url(self) -> str:
        topic = self.config.get("ntfy_topic", "awaken_phantom_832313259")
        server = self.config.get("ntfy_server", "https://ntfy.sh").rstrip("/")
        return f"{server}/{topic}"

    def send_phone_alert(
        self,
        title: str,
        message: str,
        priority: int = 4,
        tags: Optional[list] = None,
        click_url: Optional[str] = None,
        vibrate: Optional[str] = None,
        bypass_cooldown: bool = False,
    ) -> bool:
        """
        Dispatches mobile buzz and notification asynchronously in a background thread.
        """
        if not self.config.get("enabled", True):
            logger.info("Phone alerts are disabled in config.")
            return False

        now = time.time()
        last = self.config.get("last_alert_time", 0.0)
        cooldown = self.config.get("cooldown_seconds", 300.0)

        if not bypass_cooldown and (now - last < cooldown):
            logger.info(f"Skipping phone alert (cooldown active: {int(now - last)}s < {int(cooldown)}s)")
            return False

        self.config["last_alert_time"] = now
        self.save_config()

        def _worker():
            # 1. Dispatch via ntfy.sh
            topic = self.config.get("ntfy_topic", "awaken_phantom_832313259")
            server = self.config.get("ntfy_server", "https://ntfy.sh").rstrip("/")
            ntfy_endpoint = f"{server}/{topic}"
            
            headers = {
                "Title": title.encode("utf-8"),
                "Priority": str(priority),
                "Tags": ",".join(tags or ["warning", "skull"]),
                "X-Vibrate": vibrate or self.config.get("vibrate_pattern", "1000,300,1000,300,1000,500,2000"),
            }
            if click_url:
                headers["Click"] = click_url
            else:
                headers["Click"] = "https://awaken-sentinel.onrender.com/mobile-alarm"
            
            headers["Actions"] = (
                "view, 🚨 View Intervention, https://awaken-sentinel.onrender.com/mobile-alarm; "
                "view, 💻 LeetCode, https://leetcode.com"
            )

            try:
                resp = requests.post(ntfy_endpoint, data=message.encode("utf-8"), headers=headers, timeout=8)
                if resp.status_code == 200:
                    logger.info(f"Successfully sent ntfy mobile alert to {ntfy_endpoint}")
                else:
                    logger.warning(f"ntfy returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to send ntfy mobile alert: {e}")

            # 2. Dispatch custom webhook (MacroDroid / Tasker / Shortcuts)
            webhook_url = self.config.get("webhook_url", "").strip()
            if webhook_url:
                try:
                    payload = {
                        "event": "slacking_alert",
                        "title": title,
                        "message": message,
                        "priority": priority,
                        "timestamp": now,
                    }
                    w_resp = requests.post(webhook_url, json=payload, timeout=8)
                    if w_resp.status_code != 200:
                        w_resp = requests.get(webhook_url, timeout=8)
                    logger.info(f"Triggered custom mobile webhook ({webhook_url}) with status {w_resp.status_code}")
                except Exception as e:
                    logger.error(f"Failed to trigger custom mobile webhook: {e}")

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def trigger_away_phone_nuisance(self, idle_minutes: float, agents_summary: str = "") -> bool:
        """
        Escalating mobile nuisance based on how long the user has been away from their PC.
        """
        agents_text = f"Active AI Agents: {agents_summary}\n" if agents_summary else ""

        if idle_minutes < 25.0:
            # Stage 1: Initial alert (High priority + vibration)
            title = f"🚨 DESK INACTIVITY: {idle_minutes:.0f} Mins Away"
            message = (
                f"You've stepped away from your laptop for {idle_minutes:.0f} minutes!\n\n"
                f"{agents_text}"
                "Your computer is waiting for you. Return to your desk or open LeetCode to resume your streak!"
            )
            return self.send_phone_alert(
                title=title,
                message=message,
                priority=4,
                tags=["warning", "eyes"],
                vibrate="800,200,800,200,1200",
            )
        elif idle_minutes < 45.0:
            # Stage 2: Urgent vibration + aggressive notification
            title = f"💀 SLACKING DETECTED: {idle_minutes:.0f} Mins Idle!"
            message = (
                f"WAKE UP! You have been away for {idle_minutes:.0f} straight minutes!\n\n"
                f"{agents_text}"
                "Put your phone down, get back to your laptop, and lock in right now!"
            )
            return self.send_phone_alert(
                title=title,
                message=message,
                priority=5,  # Maximum priority overrides silent/DND on Android
                tags=["rotating_light", "skull", "fire"],
                vibrate="1500,200,1500,200,1500,500,2500",
            )
        else:
            # Stage 3: Maximum Emergency Intervention
            title = f"🔥 CODE RED: {idle_minutes:.0f} MINS OF COMPLETE SLACKING!"
            message = (
                f"🚨 EMERGENCY INTERVENTION! 🚨\n"
                f"You have been away from your computer for {idle_minutes:.0f} minutes!\n\n"
                f"{agents_text}"
                "Tap below to open your mobile emergency challenge or return to your laptop immediately!"
            )
            return self.send_phone_alert(
                title=title,
                message=message,
                priority=5,
                tags=["sos", "bomb", "zap"],
                vibrate="2000,150,2000,150,2000,150,3000",
            )

    def trigger_asleep_phone_nuisance(self, offline_minutes: float) -> bool:
        """Fires mobile alert when laptop powers off or goes to sleep."""
        title = f"💤 LAPTOP WENT TO SLEEP ({offline_minutes:.0f}m ago)"
        message = (
            f"Your laptop has gone to sleep or shut down for {offline_minutes:.0f} minutes.\n"
            "If you're in class or taking a break, keep learning on your phone!"
        )
        return self.send_phone_alert(
            title=title,
            message=message,
            priority=4,
            tags=["sleeping", "alarm_clock"],
            vibrate="1000,400,1000",
        )

# Global singleton
phone_alert_manager = PhoneAlertManager()
