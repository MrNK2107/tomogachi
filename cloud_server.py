import asyncio
import logging
import time
import sys
from contextlib import asynccontextmanager
from typing import Optional

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
from quiz.quiz_manager import QuizManager
from bot.telegram_service import TelegramService
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector
from core.heartbeat_storage import HeartbeatStorage
from core.cloud_sentinel import CloudSentinel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AwakenCloudServer")

# Models
class HeartbeatPayload(BaseModel):
    secret: str
    idle_seconds: float
    is_idle: bool
    has_agents: bool
    agents_summary: str
    timestamp: float

# Singletons
heartbeat_storage = HeartbeatStorage()
quiz_manager = QuizManager()
dummy_idle = IdleDetector()
dummy_agent = AgentDetector()
telegram_service = TelegramService(quiz_manager, dummy_idle, dummy_agent)
cloud_sentinel = CloudSentinel(telegram_service, heartbeat_storage)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Awaken Cloud Sentinel...")
    app_bot = telegram_service.initialize_bot()

    # Start Telegram Bot Polling
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.updater.start_polling()
    logger.info("Telegram Bot polling started on Cloud Server.")

    # Start Cloud Sentinel Loop
    sentinel_task = asyncio.create_task(cloud_sentinel.start())
    logger.info("Cloud Sentinel task started.")

    yield

    # Teardown
    logger.info("Stopping Cloud Sentinel...")
    cloud_sentinel.stop()
    sentinel_task.cancel()
    try:
        await app_bot.updater.stop()
        await app_bot.stop()
        await app_bot.shutdown()
    except Exception:
        pass
    logger.info("Cloud Server shutdown complete.")

app = FastAPI(title="Awaken Cloud Sentinel", lifespan=lifespan)

@app.get("/")
async def root():
    hb = heartbeat_storage.get_heartbeat()
    now = time.time()
    laptop_state = "UNKNOWN"
    mins_ago = None

    if hb:
        mins_ago = round((now - hb.get("timestamp", now)) / 60.0, 1)
        if mins_ago <= config.OFFLINE_ASLEEP_THRESHOLD_MINUTES:
            laptop_state = "ONLINE (Active)" if not hb.get("is_idle") else "ONLINE (Idle at Desk)"
        else:
            laptop_state = f"ASLEEP / TURNED OFF ({mins_ago}m ago)"

    return {
        "service": "⚡ Awaken Cloud Sentinel",
        "status": "online",
        "telegram_bot": "@idle_alerter_bot",
        "laptop_status": laptop_state,
        "last_heartbeat_minutes_ago": mins_ago,
        "agents_summary": hb.get("agents_summary") if hb else "None",
    }

@app.post("/api/heartbeat")
async def receive_heartbeat(payload: HeartbeatPayload):
    if payload.secret != config.HEARTBEAT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid heartbeat secret")

    heartbeat_storage.save_heartbeat(payload.model_dump())
    logger.info(f"Heartbeat received: idle={payload.idle_seconds:.1f}s | agents={payload.agents_summary}")
    return {"ok": True, "message": "Heartbeat recorded"}

@app.get("/api/status")
async def get_status():
    hb = heartbeat_storage.get_heartbeat()
    return {
        "heartbeat": hb,
        "sentinel_state": cloud_sentinel.state,
        "alert_count": cloud_sentinel.alert_count,
    }

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("cloud_server:app", host="0.0.0.0", port=port)
