import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Idle and Monitoring Settings
# Time in minutes of no keyboard/mouse input before triggering away status
IDLE_THRESHOLD_MINUTES = float(os.getenv("IDLE_THRESHOLD_MINUTES", "15"))

# Follow-up reminder interval in minutes if still away
REMINDER_INTERVAL_MINUTES = float(os.getenv("REMINDER_INTERVAL_MINUTES", "25"))

# Maximum number of reminders to send while away (to avoid infinite spam)
MAX_AWAY_REMINDERS = int(os.getenv("MAX_AWAY_REMINDERS", "3"))

# Polling interval in seconds to check system idle status
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "5"))

# Agent / Task process names to inspect
AGENT_PROCESS_NAMES = [
    "python",
    "pythonw",
    "node",
    "cursor",
    "code",
    "antigravity",
    "claude",
    "git",
    "docker",
    "wsl",
    "cargo",
    "go",
    "java",
]

# High CPU threshold (%) to qualify a process as actively running work
AGENT_CPU_THRESHOLD = float(os.getenv("AGENT_CPU_THRESHOLD", "1.0"))

# Cloud Server & Heartbeat Settings
CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL", "").strip().rstrip("/")
HEARTBEAT_SECRET = os.getenv("HEARTBEAT_SECRET", "awaken-secret-key-2026").strip()
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60"))
OFFLINE_ASLEEP_THRESHOLD_MINUTES = float(os.getenv("OFFLINE_ASLEEP_THRESHOLD_MINUTES", "15"))

# State & Stats persistence
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATS_FILE = DATA_DIR / "user_stats.json"
STATE_FILE = DATA_DIR / "bot_state.json"
HEARTBEAT_FILE = DATA_DIR / "cloud_heartbeat.json"
