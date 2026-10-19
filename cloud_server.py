import asyncio
import logging
import time
import sys
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
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
    active_window: Optional[str] = "Desktop"
    battery_percent: Optional[float] = None
    battery_plugged: Optional[bool] = None
    cpu_percent: Optional[float] = None
    git_summary: Optional[Any] = None
    pet_mood: Optional[float] = 100.0
    energy: Optional[float] = 100.0
    hunger: Optional[float] = 0.0
    snapshot_base64: Optional[str] = None

    model_config = {"extra": "allow"}

# Singletons
heartbeat_storage = HeartbeatStorage()
quiz_manager = QuizManager()
dummy_idle = IdleDetector()
dummy_agent = AgentDetector()
telegram_service = TelegramService(quiz_manager, dummy_idle, dummy_agent, heartbeat_storage=heartbeat_storage)
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

    git_info = hb.get("git_summary") if hb else None
    return {
        "service": "⚡ Awaken Cloud Sentinel",
        "status": "online",
        "telegram_bot": "@idle_alerter_bot",
        "laptop_status": laptop_state,
        "last_heartbeat_minutes_ago": mins_ago,
        "active_window": hb.get("active_window") if hb else "None",
        "battery_percent": hb.get("battery_percent") if hb else None,
        "agents_summary": hb.get("agents_summary") if hb else "None",
        "git_summary": git_info.get("summary") if isinstance(git_info, dict) else (str(git_info) if git_info else "None"),
    }

@app.post("/api/heartbeat")
async def receive_heartbeat(payload: HeartbeatPayload):
    if payload.secret != config.HEARTBEAT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid heartbeat secret")

    heartbeat_storage.save_heartbeat(payload.model_dump())
    actions = heartbeat_storage.pop_pending_actions()
    logger.info(f"Heartbeat received: idle={payload.idle_seconds:.1f}s | agents={payload.agents_summary} | actions={len(actions)}")
    return {"ok": True, "message": "Heartbeat recorded", "actions": actions}

@app.get("/api/status")
async def get_status():
    hb = heartbeat_storage.get_heartbeat()
    return {
        "heartbeat": hb,
        "sentinel_state": cloud_sentinel.state,
        "alert_count": cloud_sentinel.alert_count,
    }

@app.post("/api/action")
async def trigger_action(req: Request):
    try:
        data = await req.json()
        action = data.get("action", "")
        if action:
            heartbeat_storage.queue_action(action)
            return {"ok": True, "action": action}
    except Exception:
        pass
    return {"ok": False}

@app.get("/mobile-alarm", response_class=HTMLResponse)
async def mobile_alarm_page():
    hb = heartbeat_storage.get_heartbeat()
    now = time.time()
    laptop_status = "UNKNOWN"
    idle_desc = "Unknown"
    agents_summary = "None detected"
    battery_desc = "Unknown"

    if hb:
        mins_ago = round((now - hb.get("timestamp", now)) / 60.0, 1)
        if mins_ago <= config.OFFLINE_ASLEEP_THRESHOLD_MINUTES:
            laptop_status = "ONLINE (Active)" if not hb.get("is_idle") else "ONLINE (Idle at Desk)"
        else:
            laptop_status = f"ASLEEP ({mins_ago}m ago)"

        idle_sec = hb.get("idle_seconds", 0.0)
        idle_desc = f"{int(idle_sec // 60)}m {int(idle_sec % 60)}s"
        agents_summary = hb.get("agents_summary", "None") or "None"
        bat = hb.get("battery_percent")
        battery_desc = f"{int(bat)}%" if bat is not None else "Plugged In"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>🚨 AWAKEN SENTINEL INTERVENTION</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: #0b0f19;
      color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
      text-align: center;
      animation: pulseAlert 2.5s infinite;
    }}
    @keyframes pulseAlert {{
      0%, 100% {{ background-color: #090d16; }}
      50% {{ background-color: #2b0b14; }}
    }}
    .badge {{
      display: inline-block;
      background: #ff0844;
      color: #fff;
      font-weight: 800;
      font-size: 13px;
      letter-spacing: 1.5px;
      padding: 6px 14px;
      border-radius: 9999px;
      margin-bottom: 16px;
      box-shadow: 0 0 20px rgba(255, 8, 68, 0.6);
      animation: blink 1s infinite alternate;
    }}
    @keyframes blink {{ 0% {{ opacity: 0.6; }} 100% {{ opacity: 1; }} }}
    h1 {{
      font-size: 26px;
      font-weight: 900;
      margin-bottom: 10px;
      color: #ffffff;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .subtitle {{
      font-size: 14px;
      color: #94a3b8;
      margin-bottom: 20px;
      line-height: 1.5;
    }}
    .card {{
      background: rgba(30, 41, 59, 0.85);
      border: 1px solid rgba(255, 8, 68, 0.35);
      border-radius: 16px;
      padding: 18px;
      width: 100%;
      max-width: 420px;
      backdrop-filter: blur(12px);
      margin-bottom: 20px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }}
    .metric {{
      display: flex;
      justify-content: space-between;
      padding: 9px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 14px;
    }}
    .metric:last-child {{ border-bottom: none; }}
    .metric-label {{ color: #94a3b8; }}
    .metric-value {{ font-weight: 700; color: #38bdf8; }}
    .btn {{
      display: block;
      width: 100%;
      max-width: 420px;
      padding: 15px 18px;
      border-radius: 14px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      border: none;
      text-decoration: none;
      margin-bottom: 12px;
      transition: all 0.2s ease;
    }}
    .btn-buzz {{
      background: linear-gradient(135deg, #ff0844 0%, #ff4e50 100%);
      color: #fff;
      box-shadow: 0 4px 20px rgba(255, 8, 68, 0.4);
    }}
    .btn-leetcode {{
      background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
      color: #fff;
      box-shadow: 0 4px 20px rgba(245, 158, 11, 0.3);
    }}
    .btn-return {{
      background: #1e293b;
      color: #e2e8f0;
      border: 1px solid #334155;
    }}
    .status-msg {{
      margin-top: 10px;
      font-size: 13px;
      color: #00f5d4;
      min-height: 18px;
    }}
  </style>
</head>
<body>
  <div class="badge">🚨 AWAY FROM LAPTOP</div>
  <h1>Return To Work!</h1>
  <p class="subtitle">You have stepped away from your desktop. Your background tasks and coding goals are waiting.</p>

  <div class="card">
    <div class="metric">
      <span class="metric-label">💻 Laptop Status:</span>
      <span class="metric-value">{laptop_status}</span>
    </div>
    <div class="metric">
      <span class="metric-label">⏱️ Inactivity Duration:</span>
      <span class="metric-value" style="color: #ff0844;">{idle_desc}</span>
    </div>
    <div class="metric">
      <span class="metric-label">🤖 Active AI Agents:</span>
      <span class="metric-value">{agents_summary}</span>
    </div>
    <div class="metric">
      <span class="metric-label">🔋 Battery Level:</span>
      <span class="metric-value">{battery_desc}</span>
    </div>
  </div>

  <button class="btn btn-buzz" onclick="buzzPhone()">⚡ Shake / Vibrate Phone</button>
  <a class="btn btn-leetcode" href="https://leetcode.com" target="_blank">💻 Solve Daily LeetCode</a>
  <button class="btn btn-return" onclick="dispatchBack()">🏃 I'm Heading Back To Desk</button>

  <div class="status-msg" id="msg"></div>

  <script>
    function buzzPhone() {{
      if (navigator.vibrate) {{
        navigator.vibrate([1000, 200, 1000, 200, 1000, 500, 2000]);
        document.getElementById('msg').innerText = "📳 Phone vibration pattern fired!";
      }} else {{
        document.getElementById('msg').innerText = "Vibration API not supported in this browser.";
      }}
    }}
    try {{
      if (navigator.vibrate) {{
        navigator.vibrate([800, 200, 800, 200, 1500]);
      }}
    }} catch(e) {{}}

    async function dispatchBack() {{
      try {{
        const res = await fetch('/api/action', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ action: 'pet:say:Welcome back! Let\'s crush it!' }})
        }});
        document.getElementById('msg').innerText = "✅ Sent welcome greeting to your laptop!";
      }} catch(e) {{
        document.getElementById('msg').innerText = "Error connecting to cloud server.";
      }}
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("cloud_server:app", host="0.0.0.0", port=port)
