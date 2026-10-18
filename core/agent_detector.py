import os
import psutil
from typing import List, Dict, Any

class AgentDetector:
    """Detects if AI agents or development background tasks are running on the system."""

    EXCLUDED_PROCESS_NAMES = {
        "discord.exe", "slack.exe", "spotify.exe", "steam.exe",
        "epicwebhelper.exe", "msedgewebview2.exe", "msedge.exe",
        "chrome.exe", "firefox.exe", "brave.exe", "explorer.exe",
        "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe"
    }

    AGENT_KEYWORDS = [
        "antigravity",
        "claude",
        "cursor",
        "gemini",
        "langchain",
        "crewai",
        "autogen",
        "ollama",
        "vllm",
        "codex",
        "copilot",
    ]

    DEV_TASK_KEYWORDS = [
        "pytest",
        "unittest",
        "streamlit",
        "uvicorn",
        "gunicorn",
        "jupyter",
        "locust",
        "docker",
        "cargo",
    ]

    def __init__(self):
        self.own_pid = os.getpid()

    def get_running_agents(self) -> List[Dict[str, Any]]:
        """Scans running processes and returns active agents or development jobs."""
        detected = []

        for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent"]):
            try:
                pid = proc.info["pid"]
                if pid == self.own_pid:
                    continue

                proc_name = (proc.info["name"] or "").lower()
                if proc_name in self.EXCLUDED_PROCESS_NAMES:
                    continue

                cmdline_list = proc.info["cmdline"] or []
                cmdline = " ".join(cmdline_list).lower()

                # Ignore awaken's own script
                if "awaken" in cmdline:
                    continue

                label = self._classify(proc_name, cmdline)
                if label:
                    detected.append({
                        "pid": pid,
                        "name": proc.info["name"],
                        "label": label,
                        "cpu": proc.info.get("cpu_percent", 0.0),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Deduplicate by label to provide clean output
        unique = {}
        for item in detected:
            lbl = item["label"]
            if lbl not in unique:
                unique[lbl] = item

        return list(unique.values())

    def _classify(self, name: str, cmdline: str) -> str | None:
        """Categorizes process into a readable descriptor if it's an agent or dev task."""
        # 1. Check AI agent keywords
        if "antigravity" in cmdline or "antigravity" in name:
            return "Antigravity Agent"
        if "cursor" in cmdline or "cursor" in name:
            return "Cursor AI"
        if "claude" in cmdline or "claude" in name:
            return "Claude Code Agent"
        if "codex" in cmdline or "codex" in name:
            return "Codex Agent"
        if "ollama" in name or "ollama" in cmdline:
            return "Ollama Local LLM"
        if "crewai" in cmdline:
            return "CrewAI Multi-Agent"
        if "autogen" in cmdline:
            return "AutoGen Multi-Agent"
        if "gemini" in cmdline:
            return "Gemini CLI / Agent"

        # 2. Check dev / build / training tasks
        if "pytest" in cmdline or "test" in cmdline:
            if "python" in name or "pytest" in name:
                return "Python Test Suite"
        if "streamlit" in cmdline:
            return "Streamlit App"
        if "uvicorn" in cmdline:
            return "FastAPI / Uvicorn Server"
        if "docker" in name:
            return "Docker Container Service"
        if "jupyter" in cmdline:
            return "Jupyter Notebook Server"

        # 3. Check Python scripts
        if "python" in name:
            parts = cmdline.split()
            script_name = next((p for p in parts if p.endswith(".py")), None)
            if script_name:
                filename = os.path.basename(script_name)
                # Ignore internal system scripts
                if not filename.startswith("_"):
                    return f"Python ({filename})"
            return None

        # 4. Check Node / npm scripts
        if "node" in name:
            if any(k in cmdline for k in ["build", "dev", "start", "watch", "server", "worker"]):
                return "Node.js Build / Server"
            return None

        return None

    def is_agent_active(self) -> bool:
        """Returns True if at least one agent or dev task is currently detected."""
        return len(self.get_running_agents()) > 0

    def get_summary_text(self) -> str:
        """Returns a string describing the running agent status."""
        agents = self.get_running_agents()
        if not agents:
            return "No background AI agents detected"

        agent_names = [a["label"] for a in agents[:3]]
        if len(agents) > 3:
            agent_names.append(f"+{len(agents) - 3} more")
        return ", ".join(agent_names)
