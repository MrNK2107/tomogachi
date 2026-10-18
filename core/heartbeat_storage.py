import json
import time
from typing import Dict, Any, Optional
import config

class HeartbeatStorage:
    """Thread-safe persistent storage for the latest laptop heartbeat state."""

    def __init__(self):
        self.file_path = config.HEARTBEAT_FILE
        self._memory_cache: Optional[Dict[str, Any]] = self._load()

    def _load(self) -> Optional[Dict[str, Any]]:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_heartbeat(self, data: Dict[str, Any]):
        """Persists the latest heartbeat from the laptop."""
        data["received_at"] = time.time()
        self._memory_cache = data
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_heartbeat(self) -> Optional[Dict[str, Any]]:
        """Returns the latest heartbeat dictionary."""
        if self._memory_cache:
            return self._memory_cache
        return self._load()
