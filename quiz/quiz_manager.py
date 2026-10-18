import json
import random
from datetime import datetime, date
from typing import Dict, Any, Optional
from config import STATS_FILE
from quiz.question_bank import QUESTIONS, LEETCODE_DAILY_PROBLEMS, TOPIC_CHEATSHEETS

class QuizManager:
    """Manages placement questions, user answer streaks, and statistics."""

    def __init__(self):
        self.stats = self._load_stats()
        self.active_quiz_map: Dict[str, Dict[str, Any]] = {}  # poll_id -> question_data

    def _load_stats(self) -> Dict[str, Any]:
        """Loads persistent user statistics."""
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "total_attempted": 0,
            "total_correct": 0,
            "streak": 0,
            "best_streak": 0,
            "last_active_date": str(date.today()),
            "asked_ids": [],
            "category_scores": {}
        }

    def _save_stats(self):
        """Saves statistics to disk."""
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"[!] Error saving stats: {e}")

    def get_question(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves a question, prioritizing unasked questions."""
        candidates = QUESTIONS
        if category:
            cat_upper = category.upper()
            filtered = [q for q in QUESTIONS if q["category"].upper() == cat_upper]
            if filtered:
                candidates = filtered

        asked_ids = set(self.stats.get("asked_ids", []))
        unasked = [q for q in candidates if q["id"] not in asked_ids]

        # Reset asked if all questions were viewed
        if not unasked:
            unasked = candidates
            self.stats["asked_ids"] = []

        chosen = random.choice(unasked)
        self.stats.setdefault("asked_ids", []).append(chosen["id"])
        self._save_stats()
        return chosen

    def register_active_poll(self, poll_id: str, question: Dict[str, Any]):
        """Associates a Telegram poll ID with its corresponding question."""
        self.active_quiz_map[poll_id] = question

    def record_answer(self, poll_id: str, selected_option_idx: int) -> Optional[Dict[str, Any]]:
        """Processes a user's answer, updates streak and category scores."""
        question = self.active_quiz_map.get(poll_id)
        if not question:
            return None

        is_correct = (selected_option_idx == question["correct_index"])
        self.stats["total_attempted"] = self.stats.get("total_attempted", 0) + 1

        cat = question["category"]
        if cat not in self.stats.setdefault("category_scores", {}):
            self.stats["category_scores"][cat] = {"attempted": 0, "correct": 0}
        self.stats["category_scores"][cat]["attempted"] += 1

        if is_correct:
            self.stats["total_correct"] = self.stats.get("total_correct", 0) + 1
            self.stats["streak"] = self.stats.get("streak", 0) + 1
            self.stats["category_scores"][cat]["correct"] += 1
            if self.stats["streak"] > self.stats.get("best_streak", 0):
                self.stats["best_streak"] = self.stats["streak"]
        else:
            self.stats["streak"] = 0

        self.stats["last_active_date"] = str(date.today())
        self._save_stats()

        return {
            "is_correct": is_correct,
            "correct_option": question["options"][question["correct_index"]],
            "explanation": question["explanation"],
            "current_streak": self.stats["streak"]
        }

    def get_daily_leetcode(self) -> Dict[str, Any]:
        """Returns a curated LeetCode problem."""
        # Pick based on day of year for deterministic daily rotation
        day_of_year = datetime.now().timetuple().tm_yday
        index = day_of_year % len(LEETCODE_DAILY_PROBLEMS)
        return LEETCODE_DAILY_PROBLEMS[index]

    def get_topic_cheatsheet(self, topic: str) -> Optional[str]:
        """Returns a high-yield cheatsheet for a topic."""
        return TOPIC_CHEATSHEETS.get(topic.upper())

    def get_stats_summary(self) -> str:
        """Formats the user's placement stats for Telegram display."""
        attempted = self.stats.get("total_attempted", 0)
        correct = self.stats.get("total_correct", 0)
        streak = self.stats.get("streak", 0)
        best_streak = self.stats.get("best_streak", 0)
        accuracy = (correct / attempted * 100) if attempted > 0 else 0.0

        lines = [
            "📊 *Placement Prep Statistics*",
            f"🎯 *Questions Solved:* {attempted}",
            f"✅ *Accuracy:* {accuracy:.1f}% ({correct}/{attempted})",
            f"🔥 *Current Streak:* {streak} correct in a row",
            f"🏆 *Best Streak:* {best_streak}",
            ""
        ]

        cat_scores = self.stats.get("category_scores", {})
        if cat_scores:
            lines.append("*Domain Performance:*")
            for cat, data in cat_scores.items():
                att = data.get("attempted", 0)
                cor = data.get("correct", 0)
                pct = (cor / att * 100) if att > 0 else 0.0
                lines.append(f"• {cat}: {pct:.0f}% ({cor}/{att})")

        return "\n".join(lines)
