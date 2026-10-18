import asyncio
import logging
import threading
from typing import Optional, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal, QObject

import config
from quiz.quiz_manager import QuizManager
from quiz.roast_bank import get_brutal_roast
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes,
)

logger = logging.getLogger("TelegramWorker")

class TelegramBotWorker(QThread):
    """
    QThread worker running python-telegram-bot polling alongside PyQt6.
    Enables bidirectional interaction between desktop pet and mobile Telegram.
    """
    # Signals to PyQt6 main thread
    quiz_solved = pyqtSignal(bool, str)  # (is_correct, explanation) -> heals pet
    pet_action = pyqtSignal(str)         # ("feed", "pet", "poke")

    def __init__(self, quiz_manager: QuizManager, parent=None):
        super().__init__(parent)
        self.quiz_manager = quiz_manager
        self.app: Optional[Application] = None
        self.chat_id = config.TELEGRAM_CHAT_ID or None
        self.running = True
        self.loop = None
        self.snooze_until = None
        self.pet_state_getter = None  # Callable returning dict of pet state

    def set_pet_state_getter(self, getter_fn):
        """Sets a callback function to get live pet metrics from Qt main thread."""
        self.pet_state_getter = getter_fn

    def run(self):
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("No TELEGRAM_BOT_TOKEN set. TelegramBotWorker disabled.")
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._run_bot())
        except Exception as e:
            logger.error(f"Telegram worker crashed: {e}", exc_info=True)
        finally:
            self.loop.close()

    async def _run_bot(self):
        builder = Application.builder().token(config.TELEGRAM_BOT_TOKEN)
        self.app = builder.build()

        # Commands
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("pet", self._cmd_pet))
        self.app.add_handler(CommandHandler("status", self._cmd_pet))
        self.app.add_handler(CommandHandler("quiz", self._cmd_quiz))
        self.app.add_handler(CommandHandler("leetcode", self._cmd_leetcode))
        self.app.add_handler(CommandHandler("topic", self._cmd_topic))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("roast", self._cmd_roast))
        self.app.add_handler(CommandHandler("snooze", self._cmd_snooze))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))

        # Callbacks & Polls
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(PollAnswerHandler(self._handle_poll_answer))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram Bot worker polling started.")

        while self.running:
            await asyncio.sleep(1)

        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    def stop(self):
        self.running = False
        self.wait()

    def is_snoozed(self) -> bool:
        if not self.snooze_until:
            return False
        import datetime
        return datetime.datetime.now() < self.snooze_until

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        self.chat_id = chat_id
        config.TELEGRAM_CHAT_ID = chat_id

        # Auto-persist chat_id in .env
        try:
            env_file = config.BASE_DIR / ".env"
            if env_file.exists():
                text = env_file.read_text(encoding="utf-8")
                if "TELEGRAM_CHAT_ID=" in text:
                    import re
                    text = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", text)
                else:
                    text += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
                env_file.write_text(text, encoding="utf-8")
        except Exception:
            pass

        keyboard = [
            [
                InlineKeyboardButton("🐾 Pet Status", callback_data="btn_pet_status"),
                InlineKeyboardButton("🧠 Quick Quiz", callback_data="btn_quiz"),
            ],
            [
                InlineKeyboardButton("💻 Daily LeetCode", callback_data="btn_leetcode"),
                InlineKeyboardButton("🔥 Roast Me", callback_data="btn_roast"),
            ]
        ]
        text = (
            "🐾 *Tomogachi Awaken Companion is Online!*\n\n"
            f"✅ Linked to Chat ID: `{chat_id}`\n\n"
            "I am your live desktop focus pet and placement sentinel.\n\n"
            "*Available Commands:*\n"
            "• `/pet` — Check live desktop pet mood, level & running agents\n"
            "• `/quiz` — Solve placement MCQs to *heal and feed your pet*\n"
            "• `/leetcode` — Daily curated placement coding challenge\n"
            "• `/roast` — Merciless reality check on demand\n"
            "• `/stats` — Accuracy, answer streaks, focus stats\n"
            "• `/snooze <mins>` — Pause alerts (e.g. `/snooze 30`)"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_start(update, context)

    async def _cmd_pet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = self._build_pet_status_text()
        keyboard = [
            [
                InlineKeyboardButton("🥩 Feed with Quiz", callback_data="btn_quiz"),
                InlineKeyboardButton("🔄 Refresh Status", callback_data="btn_pet_status"),
            ]
        ]
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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
            await update.message.reply_text("Topic cheatsheets available: DSA, OS, DBMS, CN, APTITUDE.\nUsage: `/topic os`", parse_mode="Markdown")

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        summary = self.quiz_manager.get_stats_summary()
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def _cmd_roast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        roast = get_brutal_roast(35.0)
        await update.message.reply_text(roast, parse_mode="Markdown")

    async def _cmd_snooze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import datetime
        minutes = 30.0
        if context.args:
            try:
                minutes = float(context.args[0])
            except ValueError:
                pass
        self.snooze_until = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        await update.message.reply_text(f"⏸️ Alerts snoozed for *{minutes:.0f} minutes*.", parse_mode="Markdown")

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.snooze_until = None
        await update.message.reply_text("▶️ Alerts resumed! Your pet is actively monitoring you.", parse_mode="Markdown")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = str(query.message.chat_id)

        if data == "btn_pet_status":
            await query.message.reply_text(self._build_pet_status_text(), parse_mode="Markdown")
        elif data == "btn_quiz":
            await self.send_quiz(chat_id=chat_id)
        elif data == "btn_leetcode":
            problem = self.quiz_manager.get_daily_leetcode()
            text = (
                f"🔥 *Daily Placement Challenge*\n\n"
                f"📌 *{problem['title']}* (`{problem['difficulty']}`)\n"
                f"💡 {problem['key_takeaway']}\n\n"
                f"👉 [Solve on LeetCode]({problem['link']})"
            )
            await query.message.reply_text(text, parse_mode="Markdown")
        elif data == "btn_roast":
            await query.message.reply_text(get_brutal_roast(30.0), parse_mode="Markdown")
        elif data == "heading_back":
            await query.message.reply_text("🏃 Awesome! Head back to the desk and let's get into the flow zone 💻🔥", parse_mode="Markdown")

    async def _handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "🥩 *Your desktop pet was fed!* (+15 Mood points, Focus restored! ✨)"
            )
            # Emit signal to heal pet in PyQt6 GUI!
            self.quiz_solved.emit(True, result["explanation"])
        else:
            msg = (
                f"❌ *Incorrect.* Correct was: *{result['correct_option']}*\n"
                f"💡 _{result['explanation']}_\n\n"
                "🥀 *Your pet is sad from your mistake.* (-5 Mood points)"
            )
            self.quiz_solved.emit(False, result["explanation"])

        try:
            await self.app.bot.send_message(chat_id=user_chat_id, text=msg, parse_mode="Markdown")
        except Exception:
            pass

    async def send_quiz(self, chat_id: Optional[str] = None, category: Optional[str] = None):
        target_chat = chat_id or self.chat_id
        if not target_chat or not self.app:
            return

        q = self.quiz_manager.get_question(category)
        raw_explanation = q.get("explanation", "")
        trimmed_explanation = (raw_explanation[:195] + "...") if len(raw_explanation) > 195 else raw_explanation

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

    def _build_pet_status_text(self) -> str:
        state = self.pet_state_getter() if self.pet_state_getter else {}
        pet_type = state.get("pet_type", "Cyber Pet")
        mood = state.get("mood", 85.0)
        distraction = state.get("distraction_score", 0.0)
        level = state.get("level", 0)
        streak = state.get("streak", "Active")
        agents = state.get("agents_summary", "None")

        mood_emoji = "😸 Ecstatic" if mood >= 80 else ("😺 Happy" if mood >= 50 else ("😿 Sad" if mood >= 25 else "😾 Enraged"))
        level_desc = ["🟢 Level 0: Pure Focus", "🟡 Level 1: Minor Drift", "🟠 Level 2: Distracted", "🔴 Level 3: Maximum Blitz"][min(level, 3)]

        return (
            f"🐾 *Desktop Pet Status: {pet_type}*\n\n"
            f"• *Mood:* {mood_emoji} ({mood:.0f}%)\n"
            f"• *Current State:* {level_desc}\n"
            f"• *Distraction Score:* `{distraction:.1f}%`\n"
            f"• *Focus Streak:* {streak}\n"
            f"• *Active AI Agents:* `{agents}`\n"
            f"• *Quiz Accuracy:* {self.quiz_manager.stats.get('streak', 0)} correct in a row"
        )
