import time
from PyQt6.QtCore import QThread, pyqtSignal
from core.agent_detector import AgentDetector

class AgentTrackerWorker(QThread):
    """
    QThread worker monitoring background AI agents and dev tasks.
    Emits agent_update(is_active: bool, summary: str, agents: list) every 3 seconds.
    """
    agent_update = pyqtSignal(bool, str, list)

    def __init__(self, check_interval: float = 3.0):
        super().__init__()
        self.check_interval = check_interval
        self.detector = AgentDetector()
        self.running = True

    def run(self):
        while self.running:
            try:
                agents = self.detector.get_running_agents()
                is_active = len(agents) > 0
                summary = self.detector.get_summary_text()
                self.agent_update.emit(is_active, summary, agents)
            except Exception:
                pass
            time.sleep(self.check_interval)

    def stop(self):
        self.running = False
        self.wait()
