import time
import logging
from typing import Optional, Dict, Any, Callable
import psutil

from core.git_tracker import GitTracker
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector

logger = logging.getLogger("SystemSentinel")

class SystemSentinel:
    """
    Intelligent system monitor evaluating hardware health, continuous session
    fatigue, distracting app dwell times, and agent workflow transitions.
    """

    def __init__(
        self,
        git_tracker: Optional[GitTracker] = None,
        idle_detector: Optional[IdleDetector] = None,
        agent_detector: Optional[AgentDetector] = None,
    ):
        self.git = git_tracker or GitTracker()
        self.idle = idle_detector or IdleDetector()
        self.agents = agent_detector or AgentDetector()

        # Session tracking
        self.session_start = time.time()
        self.last_break_time = time.time()
        self.continuous_work_seconds = 0.0

        # Window dwell tracking
        self.current_window = ""
        self.current_window_class = "NEUTRAL"
        self.window_dwell_start = time.time()
        self.last_doomscroll_alert = 0.0

        # Agent tracking
        self.was_agent_active = False
        self.last_agent_summary = ""

        # Battery tracking
        self.last_battery_alert = 0.0

        # Event callbacks
        self.on_doomscroll_callback: Optional[Callable[[str, float], None]] = None
        self.on_agent_finished_callback: Optional[Callable[[str], None]] = None
        self.on_battery_low_callback: Optional[Callable[[int], None]] = None
        self.on_break_due_callback: Optional[Callable[[float], None]] = None

    def update_window_context(self, window_title: str, classification: str):
        """Called whenever the active window context updates."""
        now = time.time()
        if window_title != self.current_window:
            self.current_window = window_title
            self.current_window_class = classification
            self.window_dwell_start = now

    def tick(self, is_input_active: bool, dt: float) -> list:
        """
        Main evaluation tick called every few seconds.
        Returns a list of triggered event dicts: [{"event": "...", "data": ...}].
        """
        now = time.time()
        events = []

        # 1. Update continuous work time vs break
        idle_sec = self.idle.get_idle_seconds()
        if idle_sec >= 180.0:  # 3 minutes away counts as a mini-break
            self.last_break_time = now
            self.continuous_work_seconds = 0.0
        else:
            self.continuous_work_seconds += dt

        # Ergonomic break check (60 minutes continuous)
        if (now - self.last_break_time >= 3600.0) and (self.continuous_work_seconds >= 3000.0):
            self.last_break_time = now
            events.append({
                "type": "ERGONOMIC_BREAK",
                "session_minutes": round((now - self.session_start) / 60.0, 1)
            })

        # 2. Check for Distracting App Dwell Time (> 120s in DISTRACTING window)
        if self.current_window_class == "DISTRACTING":
            dwell_time = now - self.window_dwell_start
            if dwell_time >= 120.0 and (now - self.last_doomscroll_alert >= 600.0):
                self.last_doomscroll_alert = now
                events.append({
                    "type": "DOOMSCROLL_DETECTED",
                    "window_title": self.current_window,
                    "dwell_seconds": dwell_time
                })

        # 3. Check for Agent Completion (Transitions from active -> idle)
        is_agent_now = self.agents.is_agent_active()
        agent_summary = self.agents.get_summary_text()

        if self.was_agent_active and not is_agent_now:
            events.append({
                "type": "AGENT_FINISHED",
                "previous_agent": self.last_agent_summary
            })

        self.was_agent_active = is_agent_now
        self.last_agent_summary = agent_summary

        # 4. Check Battery Health
        try:
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged:
                if battery.percent <= 20 and (now - self.last_battery_alert >= 900.0):
                    self.last_battery_alert = now
                    events.append({
                        "type": "BATTERY_LOW",
                        "percent": int(battery.percent)
                    })
        except Exception:
            pass

        return events

    def get_hardware_telemetry(self) -> Dict[str, Any]:
        """Collects current hardware performance metrics."""
        battery = None
        battery_pct = 100
        is_plugged = True
        try:
            battery = psutil.sensors_battery()
            if battery:
                battery_pct = int(battery.percent)
                is_plugged = bool(battery.power_plugged)
        except Exception:
            pass

        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent,
            "battery_percent": battery_pct,
            "is_plugged": is_plugged,
            "active_window": self.current_window,
            "active_window_class": self.current_window_class,
            "idle_minutes": self.idle.get_idle_minutes(),
            "git": self.git.get_summary(),
            "agents_summary": self.agents.get_summary_text(),
        }
