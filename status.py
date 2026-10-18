import os
import sys
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector

console = Console()

def check_status():
    pid_file = config.DATA_DIR / "awaken.pid"
    is_running = False
    proc_info = None

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if "python" in (proc.name() or "").lower():
                    is_running = True
                    proc_info = {
                        "pid": pid,
                        "memory_mb": proc.memory_info().rss / (1024 * 1024),
                        "status": proc.status()
                    }
        except Exception:
            pass

    table = Table(title="⚡ Awaken Background Sentinel Status", border_style="cyan")
    table.add_column("Property", style="bold white")
    table.add_column("Value", style="cyan")

    if is_running and proc_info:
        table.add_row("Execution State", "[bold green]🟢 RUNNING (Background)[/bold green]")
        table.add_row("Process ID (PID)", str(proc_info["pid"]))
        table.add_row("RAM Usage", f"{proc_info['memory_mb']:.1f} MB")
        table.add_row("Process Status", proc_info["status"])
    else:
        table.add_row("Execution State", "[bold red]🔴 NOT RUNNING[/bold red]")

    idle_detector = IdleDetector()
    agent_detector = AgentDetector()

    idle_mins = idle_detector.get_idle_minutes()
    state_desc = f"[yellow]Away ({idle_mins:.1f} mins idle)[/yellow]" if idle_mins >= config.IDLE_THRESHOLD_MINUTES else f"[green]Active ({idle_mins:.1f} mins since input)[/green]"

    table.add_row("Current User State", state_desc)
    table.add_row("Idle Threshold", f"{config.IDLE_THRESHOLD_MINUTES:.0f} minutes")
    table.add_row("Background Agents", agent_detector.get_summary_text())
    table.add_row("Bot Username", "@idle_alerter_bot")
    table.add_row("Registered Chat ID", config.TELEGRAM_CHAT_ID or "[dim]Waiting for /start in Telegram[/dim]")

    console.print(table)

    # Print recent logs
    log_file = config.DATA_DIR / "awaken.log"
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        recent = lines[-6:] if len(lines) >= 6 else lines
        console.print(Panel("\n".join(recent), title="Recent Activity Logs", border_style="dim"))

if __name__ == "__main__":
    check_status()
