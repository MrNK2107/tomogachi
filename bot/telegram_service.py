import asyncio
import datetime
import logging
import re
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes,
)

import config
from quiz.quiz_manager import QuizManager
from quiz.roast_bank import get_brutal_roast
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector

logger = logging.getLogger("TelegramService")


class TelegramService:
    """
    Core Telegram bot service for notification dispatch, interactive quiz polls,
    and placement accountability commands. Used by cloud sentinel, diagnostics,
    and background orchestrator.
    """

    def __init__(
        self,
        quiz_manager: QuizManager,
        idle_detector: IdleDetector,
        agent_detector: AgentDetector,
    ):
        self.quiz_manager = quiz_manager
        self.idle_detector = idle_detector
        self.agent_detector = agent_detector
        self.app: Optional[Application] = None
        self.chat_id: Optional[str] = config.TELEGRAM_CHAT_ID or None
        self.snooze_until: Optional[datetime.datetime] = None

    def initialize_bot(self) -> Application:
        """Builds and registers handlers for the Telegram Application."""
        if not config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured in .env!")

        builder = Application.builder().token(config.TELEGRAM_BOT_TOKEN)
        self.app = builder.build()

        # Command handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("pet", self._cmd_status))
        self.app.add_handler(CommandHandler("quiz", self._cmd_quiz))
        self.app.add_handler(CommandHandler("leetcode", self._cmd_leetcode))
        self.app.add_handler(CommandHandler("topic", self._cmd_topic))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("roast", self._cmd_roast))
        self.app.add_handler(CommandHandler("snooze", self._cmd_snooze))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))

        # Interactive callbacks and quiz poll answers
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(PollAnswerHandler(self._handle_poll_answer))

        return self.app

    def is_snoozed(self) -> bool:
        """Returns True if alerts are currently snoozed."""
        if not self.snooze_until:
            return False
        return datetime.datetime.now() < self.snooze_until

    async def send_away_alert(
        self, idle_minutes: float, agents_summary: str, is_followup: bool = False
    ):
        """Sends away alert with savage roast and placement quiz poll."""
        target_chat = self.chat_id or config.TELEGRAM_CHAT_ID
        if not target_chat or not self.app or self.is_snoozed():
            return

        roast = get_brutal_roast(idle_minutes)
        if is_followup:
            header = f"🚨 *STILL AWAY ({idle_minutes:.0f} MINS)* 🛑"
        else:
            header = f"⚠️ *DESK INACTIVITY DETECTED ({idle_minutes:.0f} MINS)* 💻"

        text = (
            f"{header}\n\n"
            f"• *Background Agents:* `{agents_summary}`\n"
            f"• *Idle Duration:* `{idle_minutes:.0f} minutes`\n\n"
            f"{roast}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🧠 *Solve this quiz to get back in the zone:*"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔥 New Quiz", callback_data="btn_quiz"),
                InlineKeyboardButton("💻 Daily LeetCode", callback_data="btn_leetcode"),
            ],
            [
                InlineKeyboardButton("🏃 Heading Back to Desk", callback_data="heading_back"),
            ],
        ]

        try:
            await self.app.bot.send_message(
                chat_id=target_chat,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            # Send accompanying quiz poll
            await self.send_quiz(chat_id=target_chat)
        except Exception as e:
            logger.error(f"Failed to send away alert: {e}")

    async def send_welcome_back(self, idle_minutes: float):
        """Sends welcome back message when user returns to their desk."""
        target_chat = self.chat_id or config.TELEGRAM_CHAT_ID
        if not target_chat or not self.app:
            return

        text = (
            f"🎉 *Welcome back to your desk!*\n"
            f"You were away for *{idle_minutes:.1f} minutes*.\n\n"
            "🔥 Let's enter deep focus mode and conquer today's goals!"
        )
        try:
            await self.app.bot.send_message(
                chat_id=target_chat,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send welcome back: {e}")

    async def send_quiz(
        self, chat_id: Optional[str] = None, category: Optional[str] = None
    ):
        """Dispatches an interactive placement MCQ poll."""
        target_chat = chat_id or self.chat_id or config.TELEGRAM_CHAT_ID
        if not target_chat or not self.app:
            return

        q = self.quiz_manager.get_question(category)
        raw_explanation = q.get("explanation", "")
        trimmed_explanation = (
            (raw_explanation[:195] + "...")
            if len(raw_explanation) > 195
            else raw_explanation
        )

        poll_title = f"[{q['category']}] {q['question']}"
        if len(poll_title) > 300:
            poll_title = poll_title[:295] + "..."

        try:
            poll_msg = await self.app.bot.send_poll(
                chat_id=target_chat,
                question=poll_title,
                options=q["options"],
                type=Poll.QUIZ,
                correct_option_id=q["correct_index"],
                is_anonymous=False,
                explanation=trimmed_explanation,
            )
            self.quiz_manager.register_active_poll(poll_msg.poll.id, q)
        except Exception as e:
            logger.error(f"Failed to send quiz poll: {e}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        self.chat_id = chat_id
        config.TELEGRAM_CHAT_ID = chat_id

        # Auto-persist chat_id into .env
        try:
            env_file = config.BASE_DIR / ".env"
            if env_file.exists():
                text = env_file.read_text(encoding="utf-8")
                if "TELEGRAM_CHAT_ID=" in text:
                    text = re.sub(
                        r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", text
                    )
                else:
                    text += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
                env_file.write_text(text, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist TELEGRAM_CHAT_ID to .env: {e}")

        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="btn_status"),
                InlineKeyboardButton("🧠 Quick Quiz", callback_data="btn_quiz"),
            ],
            [
                InlineKeyboardButton("💻 Daily LeetCode", callback_data="btn_leetcode"),
                InlineKeyboardButton("🔥 Roast Me", callback_data="btn_roast"),
            ],
        ]
        text = (
            "🐾 *Awaken Placement Sentinel is Online!*\n\n"
            f"✅ Linked to Chat ID: `{chat_id}`\n\n"
            "Your placement companion is actively tracking your accountability.\n\n"
            "*Available Commands:*\n"
            "• `/status` — Check active agents & desktop idle status\n"
            "• `/quiz` — Solve curated placement MCQs (DSA, OS, DBMS, CN)\n"
            "• `/leetcode` — Curated problem of the day with key patterns\n"
            "• `/roast` — Brutal reality check on demand\n"
            "• `/stats` — Accuracy streaks and stats\n"
            "• `/snooze <mins>` — Pause alerts (e.g. `/snooze 30`)\n"
            "• `/resume` — Resume alerts immediately"
        )
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_start(update, context)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        idle_mins = self.idle_detector.get_idle_minutes()
        agents = self.agent_detector.get_summary_text()
        state = "Active" if idle_mins < config.IDLE_THRESHOLD_MINUTES else f"Away ({idle_mins:.1f}m)"

        msg = (
            "📊 *Sentinel System Status:*\n\n"
            f"• *User State:* `{state}`\n"
            f"• *Idle Time:* `{idle_mins:.1f} minutes`\n"
            f"• *Background Agents:* `{agents}`\n"
            f"• *Alerts Snoozed:* `{'Yes' if self.is_snoozed() else 'No'}`\n"
            f"• *Quiz Streak:* 🔥 `{self.quiz_manager.stats.get('streak', 0)} in a row`"
        )
        keyboard = [
            [
                InlineKeyboardButton("🧠 Quick Quiz", callback_data="btn_quiz"),
                InlineKeyboardButton("🔄 Refresh", callback_data="btn_status"),
            ]
        ]
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        category = context.args[0] if context.args else None
        await self.send_quiz(chat_id=str(update.effective_chat.id), category=category)

    async def _cmd_leetcode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        problem = self.quiz_manager.get_daily_leetcode()
        text = (
            f"🔥 *Daily Placement LeetCode Challenge*\n\n"
            f"📌 *Problem:* {problem['title']}\n"
            f"⚡ *Difficulty:* `{problem['difficulty']}`\n"
            f"🧩 *Pattern:* {problem['pattern']}\n"
            f"💡 *Key Takeaway:* {problem['key_takeaway']}\n\n"
            f"👉 [Solve on LeetCode]({problem['link']})"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        topic = context.args[0] if context.args else ""
        sheet = self.quiz_manager.get_topic_cheatsheet(topic)
        if sheet:
            await update.message.reply_text(sheet, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "Topic cheatsheets available: DSA, OS, DBMS, CN, APTITUDE.\nUsage: `/topic os`",
                parse_mode="Markdown",
            )

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        summary = self.quiz_manager.get_stats_summary()
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def _cmd_roast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        roast = get_brutal_roast(35.0)
        await update.message.reply_text(roast, parse_mode="Markdown")

    async def _cmd_snooze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        minutes = 30.0
        if context.args:
            try:
                minutes = float(context.args[0])
            except ValueError:
                pass
        self.snooze_until = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        await update.message.reply_text(
            f"⏸️ Alerts snoozed for *{minutes:.0f} minutes*.", parse_mode="Markdown"
        )

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.snooze_until = None
        await update.message.reply_text(
            "▶️ Alerts resumed! Sentinel is actively monitoring you.",
            parse_mode="Markdown",
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = str(query.message.chat_id)

        if data in ("btn_status", "btn_pet_status"):
            idle_mins = self.idle_detector.get_idle_minutes()
            agents = self.agent_detector.get_summary_text()
            state = "Active" if idle_mins < config.IDLE_THRESHOLD_MINUTES else f"Away ({idle_mins:.1f}m)"
            msg = (
                "📊 *Sentinel Status:*\n\n"
                f"• *User State:* `{state}`\n"
                f"• *Idle Time:* `{idle_mins:.1f} minutes`\n"
                f"• *Background Agents:* `{agents}`\n"
                f"• *Quiz Streak:* 🔥 `{self.quiz_manager.stats.get('streak', 0)}`"
            )
            await query.message.reply_text(msg, parse_mode="Markdown")
        elif data in ("btn_quiz", "quiz_random"):
            await self.send_quiz(chat_id=chat_id)
        elif data in ("btn_leetcode", "daily_leetcode"):
            problem = self.quiz_manager.get_daily_leetcode()
            text = (
                f"🔥 *Daily Placement Challenge*\n\n"
                f"📌 *{problem['title']}* (`{problem['difficulty']}`)\n"
                f"💡 {problem['key_takeaway']}\n\n"
                f"👉 [Solve on LeetCode]({problem['link']})"
            )
            await query.message.reply_text(text, parse_mode="Markdown")
        elif data in ("btn_roast", "roast"):
            await query.message.reply_text(get_brutal_roast(30.0), parse_mode="Markdown")
        elif data == "heading_back":
            await query.message.reply_text(
                "🏃 Awesome! Head back to the desk and let's get into the flow zone 💻🔥",
                parse_mode="Markdown",
            )

    async def _handle_poll_answer(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        answer = update.poll_answer
        poll_id = answer.poll_id
        if not answer.option_ids:
            return

        selected_idx = answer.option_ids[0]
        result = self.quiz_manager.record_answer(poll_id, selected_idx)
        if not result:
            return

        user_chat_id = str(answer.user.id)
        if result["is_correct"]:
            msg = (
                f"🎉 *Correct!* Current streak: 🔥 *{result['current_streak']} in a row!*\n\n"
                "🥩 *Your pet is proud!* (+15 Mood, Focus restored! ✨)"
            )
        else:
            msg = (
                f"❌ *Incorrect.* Correct was: *{result['correct_option']}*\n"
                f"💡 _{result['explanation']}_\n\n"
                "🥀 *Your pet is disappointed.* Focus and try the next one!"
            )

        try:
            await self.app.bot.send_message(
                chat_id=user_chat_id, text=msg, parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send poll answer feedback: {e}")
