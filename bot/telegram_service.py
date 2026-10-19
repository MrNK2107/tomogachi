import asyncio
import datetime
import logging
import random
import re
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    MessageHandler,
    filters,
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
        heartbeat_storage=None,
    ):
        self.quiz_manager = quiz_manager
        self.idle_detector = idle_detector
        self.agent_detector = agent_detector
        self.heartbeat_storage = heartbeat_storage
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
        self.app.add_handler(CommandHandler("pet", self._cmd_pet))
        self.app.add_handler(CommandHandler("show", self._cmd_show_pet))
        self.app.add_handler(CommandHandler("hide", self._cmd_hide_pet))
        self.app.add_handler(CommandHandler("snap", self._cmd_snap))
        self.app.add_handler(CommandHandler("screen", self._cmd_snap))
        self.app.add_handler(CommandHandler("screenshot", self._cmd_snap))
        self.app.add_handler(CommandHandler("alarm", self._cmd_alarm))
        self.app.add_handler(CommandHandler("ping", self._cmd_alarm))
        self.app.add_handler(CommandHandler("strobe", self._cmd_strobe))
        self.app.add_handler(CommandHandler("flash", self._cmd_strobe))
        self.app.add_handler(CommandHandler("open", self._cmd_open))
        self.app.add_handler(CommandHandler("lock", self._cmd_lock))
        self.app.add_handler(CommandHandler("phone", self._cmd_phone))
        self.app.add_handler(CommandHandler("mobile", self._cmd_phone))
        self.app.add_handler(CommandHandler("focus", self._cmd_focus))
        self.app.add_handler(CommandHandler("feed", self._cmd_feed))
        self.app.add_handler(CommandHandler("poke", self._cmd_poke))
        self.app.add_handler(CommandHandler("boss", self._cmd_boss))
        self.app.add_handler(CommandHandler("quiz", self._cmd_quiz))
        self.app.add_handler(CommandHandler("leetcode", self._cmd_leetcode))
        self.app.add_handler(CommandHandler("topic", self._cmd_topic))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("roast", self._cmd_roast))
        self.app.add_handler(CommandHandler("sleep", self._cmd_sleep))
        self.app.add_handler(CommandHandler("class", self._cmd_class))
        self.app.add_handler(CommandHandler("snooze", self._cmd_snooze))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))
        self.app.add_handler(CommandHandler("wake", self._cmd_resume))

        # Interactive callbacks and quiz poll answers
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(PollAnswerHandler(self._handle_poll_answer))

        # Natural language processor
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_natural_language))

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
                InlineKeyboardButton("📸 Desktop Snap", callback_data="btn_snap"),
                InlineKeyboardButton("🧠 Quick Quiz", callback_data="btn_quiz"),
            ],
            [
                InlineKeyboardButton("🚨 Desk Alarm", callback_data="btn_alarm"),
                InlineKeyboardButton("🥩 Feed Pet", callback_data="btn_feed"),
            ],
            [
                InlineKeyboardButton("💻 Daily LeetCode", callback_data="btn_leetcode"),
                InlineKeyboardButton("🔥 Roast Me", callback_data="btn_roast"),
            ],
        ]
        text = (
            "🐾 *Awaken Placement Sentinel is Online!*\n\n"
            f"✅ Linked to Chat ID: `{chat_id}`\n\n"
            "Your 24/7 cloud placement sentinel & desktop companion.\n\n"
            "*Available Commands:*\n"
            "• `/snap` — Real-time snapshot of your desktop (active window, hardware, Git)\n"
            "• `/alarm` — Remotely trigger sound, voice alarm & pet jump on laptop\n"
            "• `/focus <mins>` — Start a Pomodoro deep work sprint (e.g. `/focus 25`)\n"
            "• `/feed` / `/poke` — Interact directly with your desktop pet\n"
            "• `/boss` — Sudden Death Boss Fight: 3 rapid-fire placement questions\n"
            "• `/quiz` — Solve curated placement MCQs (DSA, OS, DBMS, CN)\n"
            "• `/leetcode` — Curated problem of the day with key patterns\n"
            "• `/roast` — Contextual reality check on demand\n"
            "• `/stats` — Accuracy streaks, repository stats, focus hours\n"
            "• `/snooze <mins>` — Pause alerts (e.g. `/snooze 30`)\n"
            "• `/resume` — Resume alerts immediately"
        )
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_start(update, context)

    async def _cmd_snap(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        hb = self.heartbeat_storage.get_heartbeat() if self.heartbeat_storage else {}
        win = hb.get("active_window", "Desktop") if hb else "Desktop"
        win_class = hb.get("active_window_class", "NEUTRAL") if hb else "NEUTRAL"
        cpu = hb.get("cpu_percent", 0.0) if hb else 0.0
        ram = hb.get("ram_percent", 0.0) if hb else 0.0
        bat = hb.get("battery_percent", 100) if hb else 100
        plugged = hb.get("is_plugged", True) if hb else True
        git_summary = hb.get("git_summary", "Git: Not detected") if hb else "Git: Not detected"
        mood = hb.get("pet_mood", 85.0) if hb else 85.0
        agents = hb.get("agents_summary", "None") if hb else self.agent_detector.get_summary_text()

        class_emoji = "🟢 PRODUCTIVE" if win_class == "PRODUCTIVE" else ("🔴 DISTRACTING" if win_class == "DISTRACTING" else "⚪ NEUTRAL")
        pwr_str = f"⚡ {bat}% (Charging)" if plugged else f"🔋 {bat}% (Battery)"
        disp_win = win if len(win) <= 40 else win[:37] + "..."

        msg = (
            "📸 *Desktop Live Snapshot:*\n\n"
            f"🪟 *Foreground Window:*\n`{disp_win}`\n"
            f"📊 *Context:* {class_emoji}\n\n"
            f"💻 *Hardware:* CPU: `{cpu:.0f}%` | RAM: `{ram:.0f}%` | {pwr_str}\n"
            f"🌿 *Git:* `{git_summary}`\n"
            f"🤖 *Active Agents:* `{agents}`\n"
            f"🐾 *Pet Mood:* `{mood:.0f}%`"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Snap", callback_data="btn_snap"),
                InlineKeyboardButton("🚨 Desk Alarm", callback_data="btn_alarm"),
            ],
            [
                InlineKeyboardButton("🐾 Show Pet", callback_data="btn_show_pet"),
                InlineKeyboardButton("🙈 Hide Pet", callback_data="btn_hide_pet"),
            ],
            [
                InlineKeyboardButton("🥩 Feed Pet", callback_data="btn_feed"),
                InlineKeyboardButton("💻 Open LeetCode", callback_data="btn_open_leetcode"),
            ]
        ]
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _cmd_show_pet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("pet:show")
        await update.message.reply_text("🐾 *Desktop Pet Summoned!* Queued for your desktop screen.", parse_mode="Markdown")

    async def _cmd_hide_pet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("pet:hide")
        await update.message.reply_text("🐾 *Desktop Pet Dismissed!* Running silently in background.", parse_mode="Markdown")

    async def _cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        target = context.args[0] if context.args else "leetcode"
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action(f"open:{target}")
        await update.message.reply_text(f"🚀 *Opened `{target}` on your laptop browser!*", parse_mode="Markdown")

    async def _cmd_lock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔒 *Workstation locking is disabled* per your safety configuration to protect background tasks and active sessions.", parse_mode="Markdown")

    async def _cmd_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manages out-of-band mobile phone alerts."""
        from core.phone_alert import phone_alert_manager

        if context.args:
            sub = context.args[0].lower()
            if sub == "test":
                phone_alert_manager.send_phone_alert(
                    "⚡ TEST PHONE BUZZ!",
                    "Your Awaken Sentinel mobile nuisance is successfully connected and buzzing!",
                    priority=5,
                    bypass_cooldown=True
                )
                await update.message.reply_text("📳 *Dispatched test buzz to your phone!* Check your ntfy app.", parse_mode="Markdown")
                return
            elif sub in ("off", "disable", "mute"):
                phone_alert_manager.set_enabled(False)
                await update.message.reply_text("🔕 *Phone alerts turned OFF.* Sentinel will not buzz your phone.", parse_mode="Markdown")
                return
            elif sub in ("on", "enable", "unmute"):
                phone_alert_manager.set_enabled(True)
                phone_alert_manager.resume()
                self.snooze_until = None
                await update.message.reply_text("🔔 *Phone alerts turned ON & Resumed.* Monitoring is active.", parse_mode="Markdown")
                return
            elif sub in ("sleep", "night"):
                await self._cmd_sleep(update, context)
                return
            elif sub in ("class", "lecture"):
                await self._cmd_class(update, context)
                return
            elif sub == "topic" and len(context.args) > 1:
                topic = context.args[1]
                phone_alert_manager.set_topic(topic)
                await update.message.reply_text(f"✅ *Updated ntfy topic to:* `{topic}`", parse_mode="Markdown")
                return
            elif sub == "webhook" and len(context.args) > 1:
                wh = context.args[1]
                phone_alert_manager.set_webhook(wh)
                await update.message.reply_text(f"✅ *Configured custom mobile webhook:* `{wh}`", parse_mode="Markdown")
                return

        topic = phone_alert_manager.config.get("ntfy_topic", "awaken_phantom_832313259")
        ntfy_url = phone_alert_manager.get_ntfy_url()
        webhook_status = "Configured" if phone_alert_manager.config.get("webhook_url") else "Not configured"
        muted, mute_reason = phone_alert_manager.is_muted()
        status_badge = f"⏸ *MUTED:* `{mute_reason}`" if muted else "🟢 *ACTIVE (Guarding)*"
        q_start = phone_alert_manager.config.get("quiet_hours_start", "23:00")
        q_end = phone_alert_manager.config.get("quiet_hours_end", "07:30")

        keyboard = [
            [
                InlineKeyboardButton("🌙 Sleep Mode (8h)", callback_data="btn_sleep_mode"),
                InlineKeyboardButton("🎓 Class Mode (1h)", callback_data="btn_class_mode"),
            ],
            [
                InlineKeyboardButton("▶️ Resume All Alerts", callback_data="btn_resume_alerts"),
                InlineKeyboardButton("⚡ Buzz Test", callback_data="btn_phone_test"),
            ],
            [
                InlineKeyboardButton("🚨 Mobile Alarm Web", url="https://awaken-sentinel.onrender.com/mobile-alarm"),
                InlineKeyboardButton("📲 Open ntfy", url=ntfy_url),
            ]
        ]
        text = (
            "📱 *MOBILE PHONE CONTROL & ALERTS* 📳\n\n"
            f"• *Status:* {status_badge}\n"
            f"• *Night Quiet Hours:* `{q_start}` - `{q_end}` (Auto-sleep)\n"
            f"• *ntfy Topic:* `{topic}`\n"
            f"• *MacroDroid Webhook:* `{webhook_status}`\n\n"
            "🎛 *Quick Commands:*\n"
            "• `/sleep [hours]` - Mute for sleep (default 8h)\n"
            "• `/class [mins]` - Mute for class / lecture (default 60m)\n"
            "• `/snooze <mins>` - Pause alerts (e.g. `/snooze 30`)\n"
            "• `/resume` - Unmute and re-activate alerts\n"
            "• `/phone off` / `/phone on` - Toggle phone alerts\n"
            "• `/phone test` - Test phone vibration"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

    async def _cmd_strobe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("strobe")
        await update.message.reply_text("🚨 *Screen Alert Strobe Dispatched!*", parse_mode="Markdown")

    async def _cmd_pet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.args:
            sub = context.args[0].lower()
            if sub in ("show", "unhide", "summon"):
                await self._cmd_show_pet(update, context)
                return
            elif sub in ("hide", "dismiss", "close"):
                await self._cmd_hide_pet(update, context)
                return
            elif sub == "say":
                phrase = " ".join(context.args[1:]) if len(context.args) > 1 else "Hello!"
                if self.heartbeat_storage:
                    self.heartbeat_storage.queue_action(f"pet:say:{phrase}")
                await update.message.reply_text(f"🐾 *Pet speech bubble dispatched:* \"{phrase}\"", parse_mode="Markdown")
                return
            elif sub in ("feed", "treat"):
                await self._cmd_feed(update, context)
                return
            elif sub in ("poke", "prod"):
                await self._cmd_poke(update, context)
                return
            elif sub in ("dance", "jump"):
                if self.heartbeat_storage:
                    self.heartbeat_storage.queue_action("dance")
                await update.message.reply_text("🐾 *Pet dance dispatched!*", parse_mode="Markdown")
                return
            elif sub == "alarm":
                await self._cmd_alarm(update, context)
                return
        await self._cmd_snap(update, context)

    async def _cmd_alarm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("alarm")
        from core.phone_alert import phone_alert_manager
        phone_alert_manager.send_phone_alert("🚨 DESK ALARM TRIGGERED", "Manual desk alarm triggered from cloud bot! Phone buzzing.", priority=5, bypass_cooldown=True)
        await update.message.reply_text("🚨 *DESK ALARM DISPATCHED!* Monitor border will strobe red neon, and your mobile phone has been buzzed!", parse_mode="Markdown")

    async def _cmd_focus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mins = 25
        if context.args:
            try:
                mins = int(context.args[0])
            except ValueError:
                pass
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action(f"focus:{mins}")
        await update.message.reply_text(f"🎯 *Focus Sprint Started ({mins} mins)!* Lock in!", parse_mode="Markdown")

    async def _cmd_feed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("feed")
        await update.message.reply_text("🥩 *You fed your desktop pet!* (+10 Mood points ✨)", parse_mode="Markdown")

    async def _cmd_poke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.heartbeat_storage:
            self.heartbeat_storage.queue_action("poke")
        await update.message.reply_text("👉 *Poked your pet remotely!*", parse_mode="Markdown")

    async def _cmd_boss(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "⚔️ *SUDDEN DEATH BOSS FIGHT!* 🐲\n\n"
            "Placement MCQs incoming! Clear your mind and solve accurately! 🔥",
            parse_mode="Markdown"
        )
        await self.send_quiz(chat_id=str(update.effective_chat.id))

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_snap(update, context)

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

    async def _cmd_sleep(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.phone_alert import phone_alert_manager
        hours = 8.0
        if context.args:
            try:
                raw = context.args[0].lower().replace("h", "")
                hours = float(raw)
            except ValueError:
                pass
        phone_alert_manager.sleep_mode(hours)
        self.snooze_until = datetime.datetime.now() + datetime.timedelta(hours=hours)
        keyboard = [[InlineKeyboardButton("▶️ Wake Up / Resume Alerts", callback_data="btn_resume_alerts")]]
        target = update.message if hasattr(update, 'message') and update.message else getattr(update, 'callback_query', update)
        if hasattr(target, 'message') and target.message:
            target = target.message
        await target.reply_text(
            f"🌙 *Sleep Mode Activated ({hours:.0f} hours)* 😴\n\n"
            "• Mobile phone vibrations & webhooks are completely muted.\n"
            "• Desktop sentinel notifications are paused.\n"
            "• Safe until morning! Tap below or send /resume when you wake up.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_class(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.phone_alert import phone_alert_manager
        mins = 60.0
        if context.args:
            try:
                raw = context.args[0].lower()
                if raw.endswith("h"):
                    mins = float(raw[:-1]) * 60.0
                elif raw.endswith("m"):
                    mins = float(raw[:-1])
                else:
                    mins = float(raw)
            except ValueError:
                pass
        phone_alert_manager.class_mode(mins)
        self.snooze_until = datetime.datetime.now() + datetime.timedelta(minutes=mins)
        keyboard = [[InlineKeyboardButton("▶️ Class Over / Resume Alerts", callback_data="btn_resume_alerts")]]
        target = update.message if hasattr(update, 'message') and update.message else getattr(update, 'callback_query', update)
        if hasattr(target, 'message') and target.message:
            target = target.message
        await target.reply_text(
            f"🎓 *Class Mode Activated ({mins:.0f} mins)* 📚\n\n"
            "• Mobile phone alerts & MacroDroid triggers are silenced.\n"
            "• PC alerts are silent to prevent any disruption in lecture.\n"
            "• Tap below or send /resume when your class is over.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_snooze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.phone_alert import phone_alert_manager
        minutes = 30.0
        if context.args:
            try:
                raw = context.args[0].lower()
                if raw.endswith("h"):
                    minutes = float(raw[:-1]) * 60.0
                elif raw.endswith("m"):
                    minutes = float(raw[:-1])
                else:
                    minutes = float(raw)
            except ValueError:
                pass
        self.snooze_until = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        phone_alert_manager.snooze(minutes, reason="Snoozed")
        keyboard = [[InlineKeyboardButton("▶️ Resume Alerts", callback_data="btn_resume_alerts")]]
        await update.message.reply_text(
            f"⏸️ *Alerts snoozed for {minutes:.0f} minutes*.\n"
            "Both PC notifications and phone alerts are muted.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.phone_alert import phone_alert_manager
        self.snooze_until = None
        phone_alert_manager.resume()
        target = update.message if hasattr(update, 'message') and update.message else getattr(update, 'callback_query', update)
        if hasattr(target, 'message') and target.message:
            target = target.message
        await target.reply_text("⚡ *Alerts Resumed!* All quiet modes cleared. Monitoring is active.", parse_mode="Markdown")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = str(query.message.chat_id)

        if data in ("btn_status", "btn_pet_status", "btn_snap"):
            await self._cmd_snap(query, context)
        elif data == "btn_show_pet":
            await self._cmd_show_pet(query, context)
        elif data == "btn_hide_pet":
            await self._cmd_hide_pet(query, context)
        elif data == "btn_open_leetcode":
            if self.heartbeat_storage:
                self.heartbeat_storage.queue_action("open:leetcode")
            await query.message.reply_text("🚀 *Launched LeetCode on your laptop browser!*", parse_mode="Markdown")
        elif data == "btn_alarm":
            await self._cmd_alarm(query, context)
        elif data == "btn_phone_test":
            from core.phone_alert import phone_alert_manager
            phone_alert_manager.send_phone_alert(
                "⚡ TEST PHONE BUZZ!",
                "Your Awaken Sentinel mobile alert is active and vibrating!",
                priority=5,
                bypass_cooldown=True
            )
            await query.message.reply_text("📳 *Dispatched test buzz to your phone!*", parse_mode="Markdown")
        elif data == "btn_sleep_mode":
            await self._cmd_sleep(query, context)
        elif data == "btn_class_mode":
            await self._cmd_class(query, context)
        elif data == "btn_resume_alerts":
            await self._cmd_resume(query, context)
        elif data == "btn_feed":
            await self._cmd_feed(query, context)
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

    async def _handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes plain-text conversational intent matching for seamless remote control."""
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        lower = text.lower()
        chat_id = str(update.effective_chat.id)

        # 1. Pet Visibility Controls
        if any(p in lower for p in ["show pet", "summon pet", "bring out", "where is pet", "where's my pet", "come here", "open pet", "unhide pet"]):
            await self._cmd_show_pet(update, context)
            return

        if any(p in lower for p in ["hide pet", "dismiss pet", "dismiss", "go away", "bye pet", "close pet", "leave me alone"]):
            await self._cmd_hide_pet(update, context)
            return

        # 2. Pet Speech / Dialogue
        if lower.startswith("say ") or lower.startswith("tell him ") or lower.startswith("pet say "):
            msg = text.split(" ", 1)[1] if " " in text else "Hello!"
            if self.heartbeat_storage:
                self.heartbeat_storage.queue_action(f"pet:say:{msg}")
            await update.message.reply_text(f"🐾 Pet will display on desktop: *\"{msg}\"*", parse_mode="Markdown")
            return

        # 3. Screenshot / Live Desktop View
        if any(w in lower for w in ["screenshot", "screen", "what's on my screen", "what is on my screen", "snap", "desktop photo"]):
            await self._cmd_snap(update, context)
            return

        # 4. Alarms & Wake-up Calls
        if any(w in lower for w in ["alarm", "wake me up", "make noise", "ring", "buzz", "bell", "loud"]):
            await self._cmd_alarm(update, context)
            return

        # 5. Visual Flash / Screen Strobe
        if any(w in lower for w in ["flash", "strobe", "blink screen"]):
            await self._cmd_strobe(update, context)
            return

        # 6. Lock Workstation (Disabled per user safety constraint)
        if any(w in lower for w in ["lock pc", "lock laptop", "lock screen", "lock workstation"]):
            await update.message.reply_text("🔒 *Workstation locking is disabled* per your safety configuration to protect background tasks and active sessions.", parse_mode="Markdown")
            return

        # 6.5 Mobile Phone Nuisance & Alerts
        if any(w in lower for w in ["test phone", "buzz phone", "buzz my phone", "mess with my phone", "phone alert", "vibrate phone"]):
            await self._cmd_phone(update, context)
            return

        # 6.6 Sleep Mode (Mute for sleeping)
        if any(w in lower for w in ["going to sleep", "sleep mode", "goodnight", "good night", "bedtime", "sleep for", "i am sleeping", "im sleeping", "sleeping"]):
            await self._cmd_sleep(update, context)
            return

        # 6.7 Class Mode (Mute for lectures / class)
        if any(w in lower for w in ["in class", "class mode", "lecture", "in lecture", "class for", "studying in class", "i am in class", "im in class"]):
            await self._cmd_class(update, context)
            return

        # 6.8 Resume / Wake Up
        if any(w in lower for w in ["wake up", "class over", "back from class", "i'm awake", "im awake", "i am awake", "resume alerts", "resume", "unmute"]):
            await self._cmd_resume(update, context)
            return

        # 6.9 Snooze
        if any(w in lower for w in ["snooze", "pause alerts", "pause alert", "don't disturb", "dont disturb"]):
            await self._cmd_snooze(update, context)
            return

        # 7. Browser Launchers
        if "open leetcode" in lower or lower == "leetcode":
            if self.heartbeat_storage:
                self.heartbeat_storage.queue_action("open:leetcode")
            await update.message.reply_text("🚀 *Launched LeetCode on your laptop browser!* Time to grind.", parse_mode="Markdown")
            return

        if "open github" in lower or lower == "github":
            if self.heartbeat_storage:
                self.heartbeat_storage.queue_action("open:github")
            await update.message.reply_text("🌿 *Launched GitHub on your laptop browser!*", parse_mode="Markdown")
            return

        # 8. Feed / Pet / Poke
        if any(w in lower for w in ["feed", "snack", "treat", "give food"]):
            await self._cmd_feed(update, context)
            return

        if any(w in lower for w in ["poke", "wake up"]):
            await self._cmd_poke(update, context)
            return

        if any(w in lower for w in ["dance", "jump", "play"]):
            if self.heartbeat_storage:
                self.heartbeat_storage.queue_action("dance")
            await update.message.reply_text("🐾 *Pet is dancing happily!*", parse_mode="Markdown")
            return

        # 9. Status & Metrics
        if any(w in lower for w in ["status", "how am i doing", "stats", "today", "streak", "battery"]):
            await self._cmd_snap(update, context)
            return

        # 10. Reality Check / Roast
        if any(w in lower for w in ["roast", "am i slacking", "be honest", "truth"]):
            await self._cmd_roast(update, context)
            return

        # 11. Quiz / Question
        if any(w in lower for w in ["quiz", "question", "dsa", "mcq", "test me"]):
            await self.send_quiz(chat_id=chat_id)
            return

        # Default intelligent response with quick actions
        keyboard = [
            [
                InlineKeyboardButton("🐾 Show Pet", callback_data="btn_show_pet"),
                InlineKeyboardButton("🙈 Hide Pet", callback_data="btn_hide_pet"),
            ],
            [
                InlineKeyboardButton("📸 Desktop Snapshot", callback_data="btn_snap"),
                InlineKeyboardButton("⚡ Buzz My Phone", callback_data="btn_phone_test"),
            ],
            [
                InlineKeyboardButton("💻 Open LeetCode", callback_data="btn_open_leetcode"),
                InlineKeyboardButton("🔥 Roast Me", callback_data="btn_roast"),
            ]
        ]
        await update.message.reply_text(
            f"🤖 *Awaken Cloud Sentinel received:* \"{text}\"\n\n"
            "I'm continuously monitoring your desktop from the cloud. What would you like to do?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
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
