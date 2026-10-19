import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
import config
from quiz.roast_bank import get_brutal_roast, get_shutdown_roast
from core.phone_alert import phone_alert_manager

logger = logging.getLogger("CloudSentinel")

class CloudSentinel:
    """Monitors incoming laptop heartbeats in the cloud and fires roasts when the laptop sleeps or powers off."""

    STATE_ONLINE = "ONLINE"
    STATE_OFFLINE = "OFFLINE_ASLEEP"

    def __init__(self, telegram_service, heartbeat_storage):
        self.telegram = telegram_service
        self.storage = heartbeat_storage
        self.state = self.STATE_ONLINE
        self.offline_start_time: Optional[float] = None
        self.last_alert_time: Optional[float] = None
        self.alert_count = 0
        self.is_running = False

    async def start(self):
        """Main cloud loop evaluating laptop liveness every 30 seconds."""
        self.is_running = True
        logger.info(
            f"Cloud Sentinel started. Offline threshold: {config.OFFLINE_ASLEEP_THRESHOLD_MINUTES}m, "
            f"Alert interval: {config.REMINDER_INTERVAL_MINUTES}m"
        )

        while self.is_running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in Cloud Sentinel tick: {e}", exc_info=True)

            await asyncio.sleep(30)

    def stop(self):
        self.is_running = False

    async def _tick(self):
        hb = self.storage.get_heartbeat()
        now = time.time()

        if not hb:
            # No heartbeat ever recorded yet
            return

        last_hb_time = hb.get("timestamp", 0)
        time_since_hb_sec = now - last_hb_time
        time_since_hb_min = time_since_hb_sec / 60.0

        is_offline = time_since_hb_min >= config.OFFLINE_ASLEEP_THRESHOLD_MINUTES

        # ----------------------------------------------------
        # Transition: ONLINE -> OFFLINE / ASLEEP
        # ----------------------------------------------------
        if self.state == self.STATE_ONLINE:
            if is_offline:
                self.state = self.STATE_OFFLINE
                self.offline_start_time = last_hb_time
                self.last_alert_time = now
                self.alert_count = 1

                logger.warning(f"[!] Laptop is ASLEEP / TURNED OFF! Last heartbeat was {time_since_hb_min:.1f} mins ago.")
                await self._send_asleep_roast(time_since_hb_min, is_followup=False)

        # ----------------------------------------------------
        # State: OFFLINE / ASLEEP
        # ----------------------------------------------------
        elif self.state == self.STATE_OFFLINE:
            # Check if laptop came back online! (Heartbeat received within last 2 minutes)
            if time_since_hb_sec < 120:
                offline_duration_min = (now - self.offline_start_time) / 60.0 if self.offline_start_time else time_since_hb_min
                self.state = self.STATE_ONLINE
                logger.info(f"[*] Laptop WOKE UP / POWERED ON after {offline_duration_min:.1f} minutes offline.")

                await self._send_resume_welcome(offline_duration_min)

                self.offline_start_time = None
                self.last_alert_time = None
                self.alert_count = 0

            # Still offline: check follow-up reminders
            elif self.last_alert_time:
                mins_since_last_alert = (now - self.last_alert_time) / 60.0
                if (
                    mins_since_last_alert >= config.REMINDER_INTERVAL_MINUTES
                    and self.alert_count < config.MAX_AWAY_REMINDERS
                ):
                    self.last_alert_time = now
                    self.alert_count += 1
                    logger.warning(f"[!] Sending follow-up offline/asleep roast #{self.alert_count} ({time_since_hb_min:.0f} mins offline).")
                    await self._send_asleep_roast(time_since_hb_min, is_followup=True)

    async def _send_asleep_roast(self, offline_minutes: float, is_followup: bool = False):
        """Dispatches savage roast for laptop sleeping / powered off."""
        if not self.telegram.chat_id or not self.telegram.app or self.telegram.is_snoozed():
            return

        roast_body = get_brutal_roast(offline_minutes)

        if is_followup:
            header = f"🚨 *LAPTOP STILL OFF / ASLEEP ({offline_minutes:.0f} MINS)* 🛑"
        else:
            header = "🚪 *LAPTOP ASLEEP OR POWERED OFF DETECTED!* 😴"

        text = (
            f"{header}\n\n"
            f"Your laptop has sent ZERO heartbeats for *{offline_minutes:.0f} minutes*.\n"
            f"You closed your screen and you're doomscrolling on your phone right now like you've already received a joining letter.\n\n"
            f"{roast_body}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *REDEEM YOURSELF:* Put the phone down, open your laptop back up, or solve this question right now:"
        )

        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [
                    InlineKeyboardButton("🔥 Solve Quiz (Prove Yourself)", callback_data="quiz_random"),
                    InlineKeyboardButton("💻 Daily LeetCode", callback_data="daily_leetcode"),
                ],
                [
                    InlineKeyboardButton("🏃 Heading Back To Desk", callback_data="heading_back"),
                ]
            ]
            await self.telegram.app.bot.send_message(
                chat_id=self.telegram.chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # Send quiz poll
            await self.telegram.send_quiz()

            # Trigger out-of-band mobile buzz & push alert
            phone_alert_manager.trigger_asleep_phone_nuisance(offline_minutes)
        except Exception as e:
            logger.error(f"Failed to send asleep roast from cloud: {e}")

    async def _send_resume_welcome(self, offline_minutes: float):
        """Sends encouragement when laptop is powered back on."""
        if not self.telegram.chat_id or not self.telegram.app:
            return

        text = (
            f"🎉 *Laptop powered back on & active!*\n"
            f"It was asleep / turned off for *{offline_minutes:.0f} minutes*.\n\n"
            "💻 You're back at the controls. Don't close that laptop until you crush today's placement goals! 🚀"
        )
        try:
            await self.telegram.app.bot.send_message(
                chat_id=self.telegram.chat_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send resume welcome from cloud: {e}")
