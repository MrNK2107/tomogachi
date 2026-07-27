import os
import sys
import json
import logging

APP_NAME = "DesktopFocusPet"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "autostart": False,
    "pet_type": "CAT",  # "CAT", "DRAGON", "BOT", "BLOB", "PANDA", "CUSTOM"
    "theme_name": "Tokyo Night",  # "Tokyo Night", "Dracula", "Catppuccin", "One Dark Pro"
    "custom_image_path": "",
    "custom_primary_color": "#a18cd1",
    "custom_secondary_color": "#fbc2eb",
    "vision_sensitivity": "RELAXED"  # "STRICT", "NORMAL", "RELAXED", "ULTRA_TOLERANT"
}



def load_config() -> dict:
    """Loads configuration from config.json, returning defaults if missing or invalid."""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
        except Exception as e:
            print(f"[ConfigManager] Error reading config file: {e}")
    return config

def save_config(config: dict) -> bool:
    """Saves dictionary to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"[ConfigManager] Error saving config file: {e}")
        return False

def get_launch_command() -> str:
    """Returns the executable command line for Windows startup."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_script = os.path.join(base_dir, "run.py")
    
    # Check for pythonw.exe in virtual environment or sys.executable directory
    venv_pythonw = os.path.join(base_dir, "venv", "Scripts", "pythonw.exe")
    if os.path.exists(venv_pythonw):
        python_exe = venv_pythonw
    else:
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
            
    return f'"{python_exe}" "{run_script}" --daemon'


def set_windows_autostart(enable: bool) -> bool:
    """
    Configures Windows registry HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 
    to launch Desktop Focus Pet on startup.
    Returns True if successfully set/removed, False otherwise.
    """
    if sys.platform != "win32":
        print("[ConfigManager] Autostart registry key is only applicable on Windows.")
        return False

    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                cmd = get_launch_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                print(f"[ConfigManager] Set Windows Auto-Start: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("[ConfigManager] Removed Windows Auto-Start key.")
                except FileNotFoundError:
                    pass  # Key didn't exist
        return True
    except Exception as e:
        print(f"[ConfigManager] Failed to update Windows registry: {e}")
        return False

def check_windows_autostart_active() -> bool:
    """Checks whether the Windows Startup registry key is present."""
    if sys.platform != "win32":
        return False

    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except Exception:
        return False
