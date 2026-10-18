import sys
import psutil
from pathlib import Path

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
import config

console = Console()

def stop():
    pid_file = config.DATA_DIR / "awaken.pid"
    if not pid_file.exists():
        console.print("[yellow]No active Awaken background instance found.[/yellow]")
        return

    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            console.print(f"[bold green]Stopped Awaken background process (PID {pid}).[/bold green]")
        else:
            console.print(f"[yellow]PID {pid} was not running.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error stopping process:[/bold red] {e}")
    finally:
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass

if __name__ == "__main__":
    stop()
