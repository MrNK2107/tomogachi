import asyncio
import logging
import time
import requests
import config
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector

logger = logging.getLogger("HeartbeatClient")

class HeartbeatClient:
    """Sends periodic heartbeats from the laptop to the Cloud Sentinel."""

    def __init__(self, idle_detector: IdleDetector, agent_detector: AgentDetector):
        self.idle_detector = idle_detector
        self.agent_detector = agent_detector
        self.is_running = False

    async def start(self):
        """Continuous loop sending heartbeat pings every HEARTBEAT_INTERVAL_SECONDS."""
        if not config.CLOUD_SERVER_URL:
            logger.info("CLOUD_SERVER_URL is not set. Heartbeat client is running in standalone local mode.")
            return

        self.is_running = True
        logger.info(f"Cloud Heartbeat Client active. Target: {config.CLOUD_SERVER_URL}/api/heartbeat")

        while self.is_running:
            try:
                self.send_heartbeat()
            except Exception as e:
                logger.warning(f"Failed to ping cloud heartbeat: {e}")

            await asyncio.sleep(config.HEARTBEAT_INTERVAL_SECONDS)

    def stop(self):
        self.is_running = False

    def send_heartbeat(self):
        """Dispatches single heartbeat payload to cloud server."""
        if not config.CLOUD_SERVER_URL:
            return

        payload = {
            "secret": config.HEARTBEAT_SECRET,
            "idle_seconds": self.idle_detector.get_idle_seconds(),
            "is_idle": self.idle_detector.is_idle(config.IDLE_THRESHOLD_MINUTES),
            "has_agents": self.agent_detector.is_agent_active(),
            "agents_summary": self.agent_detector.get_summary_text(),
            "timestamp": time.time()
        }

        url = f"{config.CLOUD_SERVER_URL}/api/heartbeat"
        try:
            resp = requests.post(url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                logger.debug("Cloud heartbeat acknowledged (200 OK).")
            else:
                logger.warning(f"Cloud heartbeat returned status: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Could not reach cloud server at {url}: {e}")
