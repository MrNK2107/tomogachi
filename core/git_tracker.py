import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

class GitTracker:
    """
    Monitors Git development activity:
    - Active branch
    - Uncommitted modified/untracked files
    - Commits completed today
    - Time elapsed since the last commit
    """

    def __init__(self, repo_dir: Optional[Path] = None, cache_ttl: float = 15.0):
        self.repo_dir = repo_dir or Path(__file__).resolve().parent.parent
        self.cache_ttl = cache_ttl
        self._last_check = 0.0
        self._cached_data: Dict[str, Any] = {
            "is_repo": False,
            "branch": "none",
            "modified_count": 0,
            "untracked_count": 0,
            "total_uncommitted": 0,
            "commits_today": 0,
            "last_commit_text": "None",
            "last_commit_age_min": 999.0,
            "summary": "Git: Not a repo",
        }

    def _run_git(self, args: list) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if res.returncode == 0:
                return res.stdout.strip()
            return None
        except Exception:
            return None

    def get_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force_refresh and (now - self._last_check < self.cache_ttl):
            return self._cached_data

        self._last_check = now

        # Check if inside git work tree
        is_inside = self._run_git(["rev-parse", "--is-inside-work-tree"])
        if is_inside != "true":
            self._cached_data["is_repo"] = False
            self._cached_data["summary"] = "Git: Outside repo"
            return self._cached_data

        branch = self._run_git(["branch", "--show-current"]) or "detached"

        # Check working tree status
        status_out = self._run_git(["status", "--porcelain"]) or ""
        lines = [line.strip() for line in status_out.splitlines() if line.strip()]

        modified_count = sum(1 for l in lines if not l.startswith("??"))
        untracked_count = sum(1 for l in lines if l.startswith("??"))
        total_uncommitted = len(lines)

        # Check commits today
        commits_today_out = self._run_git(["log", "--since=midnight", "--oneline"]) or ""
        commits_today = len([c for c in commits_today_out.splitlines() if c.strip()])

        # Last commit relative time & timestamp
        last_commit_raw = self._run_git(["log", "-1", "--format=%ct|%s"]) or ""
        last_commit_age_min = 999.0
        last_commit_text = "No commits"

        if "|" in last_commit_raw:
            try:
                ct_str, subj = last_commit_raw.split("|", 1)
                last_commit_age_min = max(0.0, (now - float(ct_str)) / 60.0)
                last_commit_text = subj[:40]
            except Exception:
                pass

        if total_uncommitted > 0:
            summary = f"🌱 Git: {branch} ({total_uncommitted} dirty files, {commits_today} commits today)"
        else:
            summary = f"✨ Git: {branch} (Clean, {commits_today} commits today)"

        self._cached_data = {
            "is_repo": True,
            "branch": branch,
            "modified_count": modified_count,
            "untracked_count": untracked_count,
            "total_uncommitted": total_uncommitted,
            "commits_today": commits_today,
            "last_commit_text": last_commit_text,
            "last_commit_age_min": round(last_commit_age_min, 1),
            "summary": summary,
        }
        return self._cached_data
