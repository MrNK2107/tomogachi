"""
Context Scanner - Productivity App Classification System.
Classifies the active foreground window as PRODUCTIVE, NEUTRAL, or DISTRACTING
based on window title analysis and known application patterns.
"""

import re
import sys
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal


# ---- Category Definitions ----

PRODUCTIVITY_KEYWORDS = {
    # IDEs & Code Editors
    'visual studio code', 'vscode', 'vs code', 'visual studio', 'code',
    'intellij', 'pycharm', 'webstorm', 'phpstorm', 'rubymine', 'goland',
    'clion', 'datagrip', 'android studio', 'xcode', 'eclipse', 'netbeans',
    'sublime text', 'atom', 'notepad++', 'vim', 'neovim', 'emacs',
    'jetbrains', 'cursor', 'zed', 'windsurf',
    # Terminals
    'terminal', 'command prompt', 'powershell', 'cmd', 'bash', 'wsl',
    'windows terminal', 'git bash', 'putty', 'ssh',
    # Productivity & Office
    'microsoft word', 'word -', 'excel', 'powerpoint', 'outlook',
    'onenote', 'notion', 'obsidian', 'evernote', 'todoist',
    'slack', 'teams', 'discord', 'zoom', 'meet', 'webex',
    # Documentation & Reading
    'pdf', 'acrobat', 'readme', 'markdown', 'docs', 'documentation',
    # Development Tools
    'docker', 'kubectl', 'postman', 'insomnia', 'figma',
    'unity', 'unreal', 'blender', 'gimp',
    'mysql workbench', 'pgadmin', 'dbeaver', 'tableplus',
    'filezilla', 'winscp', 'cyberduck',
    # Browsers (when on work-appropriate sites, detected via title patterns)
}

DISTRACTION_KEYWORDS = {
    # Social Media & Entertainment
    'youtube', 'netflix', 'hulu', 'disney+', 'prime video', 'twitch',
    'facebook', 'twitter', 'x.com', 'instagram', 'tiktok', 'snapchat',
    'reddit', 'pinterest', 'tumblr', 'discord', 'whatsapp',
    'telegram', 'signal', 'messenger',
    # Gaming
    'game', 'minecraft', 'fortnite', 'league of legends', 'valorant',
    'csgo', 'counter-strike', 'dota', 'overwatch', 'apex legends',
    'steam', 'epic games', 'battle.net', 'origin', 'roblox',
    # Shopping
    'amazon', 'ebay', 'etsy', 'walmart', 'target', 'best buy',
    'aliexpress', 'shopify',
    # Video Streaming
    'crunchyroll', 'funimation', 'hbomax', 'paramount+', 'appletv',
    # News & Gossip
    'tmz', 'buzzfeed', '9gag', 'imgur',
}

NEUTRAL_KEYWORDS = {
    # File Managers
    'file explorer', 'finder', 'total commander',
    'this pc', 'my computer',
    # System
    'settings', 'control panel', 'task manager', 'system',
    'calculator', 'calendar', 'clock',
    # Browsers (generic - specific sites caught above)
    'microsoft edge', 'google chrome', 'chromium', 'mozilla firefox',
    'brave', 'opera', 'safari',
}


def classify_window_title(title: str) -> str:
    """
    Classify an active window title as PRODUCTIVE, DISTRACTING, or NEUTRAL.
    
    Uses keyword matching against the window title (case-insensitive).
    Browsers and generic tools get NEUTRAL by default, with specific
    site names being caught by the keywords.
    
    Returns: 'PRODUCTIVE', 'DISTRACTING', or 'NEUTRAL'
    """
    if not title or title == 'Desktop':
        return 'NEUTRAL'
    
    title_lower = title.lower().strip()
    
    # Check distraction keywords first (more specific)
    for keyword in DISTRACTION_KEYWORDS:
        if keyword in title_lower:
            return 'DISTRACTING'
    
    # Check productivity keywords
    for keyword in PRODUCTIVITY_KEYWORDS:
        if keyword in title_lower:
            return 'PRODUCTIVE'
    
    # Check neutral keywords
    for keyword in NEUTRAL_KEYWORDS:
        if keyword in title_lower:
            return 'NEUTRAL'
    
    # Default: if the title has file extensions or code patterns, mark productive
    code_patterns = [r'\.py$', r'\.js$', r'\.ts$', r'\.jsx$', r'\.tsx$',
                     r'\.html$', r'\.css$', r'\.scss$', r'\.cpp$', r'\.c$',
                     r'\.h$', r'\.java$', r'\.go$', r'\.rs$', r'\.rb$',
                     r'\.php$', r'\.swift$', r'\.kt$', r'\.vue$', r'\.svelte$']
    for pattern in code_patterns:
        if re.search(pattern, title_lower):
            return 'PRODUCTIVE'
    
    # Check if title contains typical work-related patterns
    work_patterns = [r'\[.*\]', r'- .*@.*', r'(PR|MR|issue|ticket)\s*#?\d+',
                     r'(commit|branch|merge|review)', r'(debug|compile|build|deploy)',
                     r'(api|endpoint|route|schema|query)', r'(test|spec|unit|e2e)']
    for pattern in work_patterns:
        if re.search(pattern, title_lower):
            return 'PRODUCTIVE'
    
    return 'NEUTRAL'


def get_active_window_info():
    """
    Get the active foreground window title and process name on Windows.
    Returns (title: str, classification: str)
    """
    if sys.platform != 'win32':
        return 'Active Workspace', 'NEUTRAL'
    
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        
        # Get window title
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        title = ''
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
        
        if not title:
            return 'Desktop', 'NEUTRAL'
        
        classification = classify_window_title(title)
        return title, classification
    except Exception:
        return 'Desktop', 'NEUTRAL'


class ContextScannerWorker(QThread):
    """
    QThread worker that periodically scans the active window and classifies
    it as PRODUCTIVE, NEUTRAL, or DISTRACTING.
    Emits context_update(title: str, classification: str) every 500ms.
    """
    context_update = pyqtSignal(str, str)  # (title, classification)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.last_title = ''
        self.last_classification = ''
    
    def run(self):
        while self.running:
            title, classification = get_active_window_info()
            if title != self.last_title or classification != self.last_classification:
                self.last_title = title
                self.last_classification = classification
                self.context_update.emit(title, classification)
            self.msleep(500)
    
    def stop(self):
        self.running = False
        self.wait()
"""