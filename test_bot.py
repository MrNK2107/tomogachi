import asyncio
import sys
from rich.console import Console
from rich.panel import Panel

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector
from quiz.quiz_manager import QuizManager
from bot.telegram_service import TelegramService

console = Console()

async def run_diagnostics():
    console.print(Panel("[bold cyan]🧪 Awaken Diagnostics & Test Notification[/bold cyan]"))

    if not config.TELEGRAM_BOT_TOKEN:
        console.print("[bold red]❌ TELEGRAM_BOT_TOKEN is missing in .env![/bold red]")
        return

    idle_detector = IdleDetector()
    agent_detector = AgentDetector()
    quiz_manager = QuizManager()
    telegram = TelegramService(quiz_manager, idle_detector, agent_detector)

    console.print(f"• Current idle time: [bold yellow]{idle_detector.get_idle_minutes():.2f} minutes[/bold yellow]")
    console.print(f"• Running agents: [bold cyan]{agent_detector.get_summary_text()}[/bold cyan]")

    app = telegram.initialize_bot()
    await app.initialize()

    bot_info = await app.bot.get_me()
    console.print(f"[bold green]✓ Telegram Bot connected:[/bold green] @{bot_info.username} ({bot_info.first_name})")

    if not config.TELEGRAM_CHAT_ID:
        console.print(Panel(
            f"[bold yellow]⚠️ No TELEGRAM_CHAT_ID found in .env![/bold yellow]\n\n"
            f"1. Open Telegram and search for [bold cyan]@{bot_info.username}[/bold cyan]\n"
            f"2. Send [bold green]/start[/bold green] to your bot\n"
            f"3. Run [bold white]python main.py[/bold white] (it will automatically record your Chat ID!)",
            border_style="yellow"
        ))
        await app.shutdown()
        return

    console.print(f"• Sending test alert & quiz to chat ID: [bold white]{config.TELEGRAM_CHAT_ID}[/bold white]...")
    await telegram.send_away_alert(
        idle_minutes=15.0,
        agents_summary=agent_detector.get_summary_text(),
        is_followup=False
    )
    console.print("[bold green]✓ Test alert & interactive quiz sent successfully! Check your Telegram phone app.[/bold green]")

    await app.shutdown()

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
