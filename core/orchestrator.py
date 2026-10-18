import asyncio
import logging
from datetime import datetime
from typing import Optional
import config
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector
from bot.telegram_service import TelegramService

logger = logging.getLogger("AwakenSentinel")

class ActivitySentinel:
    """Monitors Windows input activity and coordinates alerts when idle or running background agents."""

    STATE_ACTIVE = "ACTIVE"
    STATE_AWAY = "AWAY"

    def __init__(
        self,
        idle_detector: IdleDetector,
        agent_detector: AgentDetector,
        telegram_service: TelegramService
    ):
        self.idle_detector = idle_detector
        self.agent_detector = agent_detector
        self.telegram = telegram_service

        self.current_state = self.STATE_ACTIVE
        self.away_start_time: Optional[datetime] = None
        self.last_alert_time: Optional[datetime] = None
        self.away_followup_count = 0
        self.is_running = False

    async def start(self):
        """Main loop that continuously checks idle time and agent activity."""
        self.is_running = True
        logger.info(
            f"Awaken Sentinel started. Idle threshold: {config.IDLE_THRESHOLD_MINUTES}m, "
            f"Reminder interval: {config.REMINDER_INTERVAL_MINUTES}m"
        )

        while self.is_running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in sentinel tick: {e}", exc_info=True)

            await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)

    def stop(self):
        """Stops the monitoring loop."""
        self.is_running = False

    async def _tick(self):
        idle_mins = self.idle_detector.get_idle_minutes()
        is_idle_threshold = (idle_mins >= config.IDLE_THRESHOLD_MINUTES)
        now = datetime.now()

        # ----------------------------------------------------
        # State: ACTIVE -> Transition to AWAY
        # ----------------------------------------------------
        if self.current_state == self.STATE_ACTIVE:
            if is_idle_threshold:
                self.current_state = self.STATE_AWAY
                self.away_start_time = now
                self.last_alert_time = now
                self.away_followup_count = 0

                agents_summary = self.agent_detector.get_summary_text()
                logger.info(f"[!] User transitioned to AWAY ({idle_mins:.1f} mins idle). Agents: {agents_summary}")

                # Send initial alert & placement quiz
                await self.telegram.send_away_alert(
                    idle_minutes=idle_mins,
                    agents_summary=agents_summary,
                    is_followup=False
                )

        # ----------------------------------------------------
        # State: AWAY -> Handling return or follow-up reminder
        # ----------------------------------------------------
        elif self.current_state == self.STATE_AWAY:
            # Check if user returned (physical input detected, idle time dropped below 1 min)
            if idle_mins < 1.0:
                duration_mins = (now - self.away_start_time).total_seconds() / 60.0 if self.away_start_time else idle_mins
                self.current_state = self.STATE_ACTIVE
                logger.info(f"[*] User RETURNED after {duration_mins:.1f} minutes away.")

                await self.telegram.send_welcome_back(idle_minutes=duration_mins)

                self.away_start_time = None
                self.last_alert_time = None
                self.away_followup_count = 0

            # User is still away: Check for follow-up reminder
            elif self.last_alert_time:
                mins_since_last_alert = (now - self.last_alert_time).total_seconds() / 60.0
                if (
                    mins_since_last_alert >= config.REMINDER_INTERVAL_MINUTES
                    and self.away_followup_count < config.MAX_AWAY_REMINDERS
                ):
                    self.last_alert_time = now
                    self.away_followup_count += 1
                    agents_summary = self.agent_detector.get_summary_text()
                    logger.info(f"[!] Sending follow-up away alert #{self.away_followup_count} ({idle_mins:.1f} mins idle).")

                    await self.telegram.send_away_alert(
                        idle_minutes=idle_mins,
                        agents_summary=agents_summary,
                        is_followup=True
                    )
