import sys
import os
import random
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QProgressBar, QCheckBox, 
                             QGroupBox, QComboBox, QFileDialog, QColorDialog, QLineEdit,
                             QSystemTrayIcon, QMenu)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QColor, QGuiApplication, QPainter, QBrush, QPainterPath
from PyQt6.QtCore import QRectF

from cv_tracker import CVTrackerWorker
from activity_tracker import ActivityTrackerWorker
from mic_tracker import MicTrackerWorker
from window_tracker import WindowTrackerWorker
from context_scanner import ContextScannerWorker
from mouse_analytics import MouseAnalyticsWorker
from clipboard_tracker import ClipboardTrackerWorker
from intensity_engine import IntensityEngine
from pet_gui import PetWindow, ScreenOverlay, FakePopup
import audio_guard
import config_manager
import config
from agent_tracker import AgentTrackerWorker
from telegram_worker import TelegramBotWorker
from core.power_monitor import PowerMonitor
from core.heartbeat_client import HeartbeatClient
from core.idle_detector import IdleDetector
from core.agent_detector import AgentDetector
from quiz.quiz_manager import QuizManager
from core.git_tracker import GitTracker
from core.voice_alert import VoiceAlert
from core.system_sentinel import SystemSentinel

class FocusHistory:
    """Tracks focus scores over time for statistics display."""
    def __init__(self, max_samples: int = 600):  # 600 samples = ~1 minute at 100ms
        self.max_samples = max_samples
        self.scores = []
        self.timestamps = []
        self.focused_time = 0.0
        self.total_time = 0.0
        self.session_start = time.time()
        
    def add_sample(self, score: float):
        self.scores.append(score)
        self.timestamps.append(time.time())
        if len(self.scores) > self.max_samples:
            self.scores.pop(0)
            self.timestamps.pop(0)
        
    def update_time(self, is_focused: bool, dt: float):
        self.total_time += dt
        if is_focused:
            self.focused_time += dt

    def get_focus_percentage(self) -> float:
        if self.total_time <= 0:
            return 100.0
        return (self.focused_time / self.total_time) * 100.0

    def get_current_streak(self) -> str:
        """Return a formatted streak string."""
        if self.total_time < 60:
            return "Just started"
        mins = int(self.focused_time // 60)
        secs = int(self.focused_time % 60)
        return f"{mins}m {secs}s focused"

    def get_recent_mood(self) -> float:
        """
        Calculate pet mood based on recent focus history (last 2 minutes).
        Returns 0 (angry) to 100 (ecstatic).
        Uses a rolling window + exponential decay for responsiveness.
        """
        if not self.scores:
            return 50.0
        
        # Use last 120 samples (~2 minutes at 1 sample/second)
        recent = self.scores[-120:]
        if not recent:
            return 50.0
        
        # Weight: more recent samples matter more
        total_weight = 0
        weighted_sum = 0
        for i, score in enumerate(recent):
            weight = 1.0 + (i / len(recent))  # Later samples weigh up to 2x
            total_weight += weight
            # Invert distraction score for mood (0 distraction = 100 mood)
            weighted_sum += (100.0 - score) * weight
        
        return weighted_sum / total_weight if total_weight > 0 else 50.0

    def reset(self):
        self.scores.clear()
        self.timestamps.clear()
        self.focused_time = 0.0
        self.total_time = 0.0
        self.session_start = time.time()


class SettingsPanel(QWidget):
    """
    Ultra-Premium Multimodal Control Dashboard for Desktop Focus Pet.
    Runs as a background daemon process with Windows System Tray integration
    and Pet click-to-toggle visibility.
    """
    def __init__(self, engine, pet_window, screen_overlay, cv_worker, activity_worker, mic_worker, window_worker,
                 context_worker=None, mouse_worker=None, clipboard_worker=None,
                 agent_worker=None, telegram_worker=None,
                 git_tracker=None, voice_alert=None, system_sentinel=None):
        super().__init__()
        self.engine = engine
        self.pet_window = pet_window
        self.screen_overlay = screen_overlay
        self.cv_worker = cv_worker
        self.activity_worker = activity_worker
        self.mic_worker = mic_worker
        self.window_worker = window_worker
        self.context_worker = context_worker
        self.mouse_worker = mouse_worker
        self.clipboard_worker = clipboard_worker
        self.agent_worker = agent_worker
        self.telegram_worker = telegram_worker
        self.git_tracker = git_tracker or GitTracker()
        self.voice_alert = voice_alert or VoiceAlert(enabled=True)
        self.system_sentinel = system_sentinel or SystemSentinel(
            git_tracker=self.git_tracker,
            idle_detector=IdleDetector(),
            agent_detector=AgentDetector(),
        )
        
        self.config = config_manager.load_config()
        self.latest_is_focused = True
        self.latest_distraction_type = "NONE"
        self.latest_input_active = True
        self.latest_idle_sec = 0.0
        self.latest_mic_active = False
        self.latest_mic_rms = 0.0
        self.latest_window_title = "Desktop"
        # New sensor states
        self.latest_app_context = "NEUTRAL"
        self.latest_mouse_steady = True
        self.latest_mouse_velocity = 0.0
        self.latest_clipboard_active = False
        self.latest_clipboard_changes = 0
        self.latest_agent_active = False
        self.latest_agents_summary = "None"
        self.away_alert_tick_counter = 0

        self.active_popups = []
        self.popup_spawn_ticks = 0
        
        # Focus history tracking
        self.focus_history = FocusHistory()
        self.stats_tick_counter = 0

        if self.agent_worker:
            self.agent_worker.agent_update.connect(self.on_agent_update)
        if self.telegram_worker:
            self.telegram_worker.quiz_solved.connect(self.on_quiz_solved)
            self.telegram_worker.pet_action.connect(self.on_pet_action)
            self.telegram_worker.set_pet_state_getter(self.get_live_pet_state)

        self.setWindowTitle("Desktop Focus Pet - Control Dashboard")
        self.setFixedSize(500, 960)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowStaysOnTopHint)
        
        # Premium Dark Obsidian & Neon Glassmorphic Stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #0b0c12;
                color: #e2e4ed;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                font-size: 12px;
            }
            QGroupBox {
                background-color: rgba(20, 23, 36, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                margin-top: 14px;
                padding: 14px 12px 12px 12px;
                font-weight: bold;
                font-size: 12px;
                color: #00f5d4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
            }
            QPushButton {
                background-color: #181b2c;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: bold;
                font-size: 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #232840;
                border-color: #00f5d4;
                color: #00f5d4;
            }
            QPushButton:pressed {
                background-color: #10121d;
            }
            QLineEdit {
                background-color: #121420;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 5px;
                color: #ffffff;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 5px;
                background-color: #121420;
            }
            QCheckBox::indicator:checked {
                background-color: #00f5d4;
                border-color: #00f5d4;
            }
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                text-align: center;
                background-color: #07080d;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f5d4, stop:1 #7b2cbf);
                border-radius: 7px;
            }
            QComboBox {
                background-color: #181b2c;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 8px;
                padding: 5px 10px;
                color: #ffffff;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #141624;
                selection-background-color: #232840;
                selection-color: #00f5d4;
            }
            QLabel#StatValue {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#StatLabel {
                font-size: 10px;
                color: #8f94a8;
            }
        """)

        self.setup_ui()
        self.setup_system_tray()
        self.apply_current_pet_style()
        self.apply_saved_sensitivity()

        # Connect Worker signals
        self.cv_worker.focus_update.connect(self.on_focus_update)
        self.cv_worker.status_message.connect(self.on_status_message)
        self.cv_worker.frame_ready.connect(self.on_frame_ready)
        self.activity_worker.activity_update.connect(self.on_activity_update)
        self.mic_worker.mic_update.connect(self.on_mic_update)
        self.window_worker.window_update.connect(self.on_window_update)
        
        # Connect new sensor signals
        if self.context_worker:
            self.context_worker.context_update.connect(self.on_context_update)
        if self.mouse_worker:
            self.mouse_worker.mouse_update.connect(self.on_mouse_update)
        if self.clipboard_worker:
            self.clipboard_worker.clipboard_update.connect(self.on_clipboard_update)

        # 100ms Interval Core Update Loop
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.on_tick)
        self.loop_timer.start(100)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # Render clean system tray icon pixmap
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#7aa2f7")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setBrush(QBrush(QColor("#15161e")))
        painter.drawEllipse(10, 10, 12, 12)
        painter.end()
        
        self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip("Desktop Focus Pet - Background Daemon")

        tray_menu = QMenu(self)
        
        show_action = tray_menu.addAction("⚙️ Open Control Dashboard")
        show_action.triggered.connect(self.show_and_activate)
        
        reset_action = tray_menu.addAction("🔄 Reset Distraction Score (0%)")
        reset_action.triggered.connect(self.on_reset_score_clicked)
        
        calib_action = tray_menu.addAction("📷 Start Auto-Calibration")
        calib_action.triggered.connect(self.cv_worker.start_calibration)

        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("❌ Exit Application")
        quit_action.triggered.connect(self.force_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_and_activate()

    def show_and_activate(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # Header Title Banner
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 2)
        
        title_lbl = QLabel("DESKTOP FOCUS PET")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; letter-spacing: 1.5px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Multimodal Vision, Input, Mic & Context Focus Engine")
        subtitle_lbl.setFont(QFont("Segoe UI", 9))
        subtitle_lbl.setStyleSheet("color: #8f94a8;")
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle_lbl)

        main_layout.addWidget(header_widget)

        # Group 0: Session Statistics & Focus History
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(6)
        
        # Stats row with 3 stat cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        
        # Stat: Focus %
        focus_stat_widget = QWidget()
        focus_stat_layout = QVBoxLayout(focus_stat_widget)
        focus_stat_layout.setContentsMargins(4, 2, 4, 2)
        focus_stat_layout.setSpacing(1)
        self.stat_focus_label = QLabel("Focus Rate")
        self.stat_focus_label.setObjectName("StatLabel")
        self.stat_focus_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        focus_stat_layout.addWidget(self.stat_focus_label)
        self.stat_focus_val = QLabel("100%")
        self.stat_focus_val.setObjectName("StatValue")
        self.stat_focus_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stat_focus_val.setStyleSheet("color: #00f5d4; font-size: 20px; font-weight: bold;")
        focus_stat_layout.addWidget(self.stat_focus_val)
        stats_row.addWidget(focus_stat_widget)
        
        # Stat: Streak
        streak_stat_widget = QWidget()
        streak_stat_layout = QVBoxLayout(streak_stat_widget)
        streak_stat_layout.setContentsMargins(4, 2, 4, 2)
        streak_stat_layout.setSpacing(1)
        self.stat_streak_label = QLabel("Focus Streak")
        self.stat_streak_label.setObjectName("StatLabel")
        self.stat_streak_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        streak_stat_layout.addWidget(self.stat_streak_label)
        self.stat_streak_val = QLabel("0m 0s")
        self.stat_streak_val.setObjectName("StatValue")
        self.stat_streak_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stat_streak_val.setStyleSheet("color: #4facfe; font-size: 20px; font-weight: bold;")
        streak_stat_layout.addWidget(self.stat_streak_val)
        stats_row.addWidget(streak_stat_widget)
        
        # Stat: Session Time
        session_stat_widget = QWidget()
        session_stat_layout = QVBoxLayout(session_stat_widget)
        session_stat_layout.setContentsMargins(4, 2, 4, 2)
        session_stat_layout.setSpacing(1)
        self.stat_session_label = QLabel("Session")
        self.stat_session_label.setObjectName("StatLabel")
        self.stat_session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        session_stat_layout.addWidget(self.stat_session_label)
        self.stat_session_val = QLabel("0s")
        self.stat_session_val.setObjectName("StatValue")
        self.stat_session_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stat_session_val.setStyleSheet("color: #bb9af7; font-size: 20px; font-weight: bold;")
        session_stat_layout.addWidget(self.stat_session_val)
        stats_row.addWidget(session_stat_widget)
        
        stats_layout.addLayout(stats_row)
        
        # Pet Mood Indicator
        self.mood_widget = QWidget()
        mood_layout = QHBoxLayout(self.mood_widget)
        mood_layout.setContentsMargins(4, 2, 4, 2)
        mood_layout.setSpacing(8)
        
        mood_label = QLabel("Pet Mood:")
        mood_label.setStyleSheet("color: #8f94a8; font-size: 11px;")
        mood_layout.addWidget(mood_label)
        
        self.mood_emoticon_lbl = QLabel("😐")
        self.mood_emoticon_lbl.setFont(QFont("Segoe UI", 18))
        mood_layout.addWidget(self.mood_emoticon_lbl)
        
        self.mood_name_lbl = QLabel("Neutral")
        self.mood_name_lbl.setStyleSheet("color: #8f94a8; font-size: 11px; font-weight: bold;")
        mood_layout.addWidget(self.mood_name_lbl)
        
        mood_layout.addStretch()
        stats_layout.addWidget(self.mood_widget)
        
        # Mini focus history bar (custom widget with paintEvent)
        self.history_bar = HistoryBarWidget()
        self.history_bar.setFixedHeight(20)
        stats_layout.addWidget(self.history_bar)
        
        main_layout.addWidget(stats_group)
        
        # Group 1: Live Multimodal Sensor Matrix & Metrics
        metrics_group = QGroupBox("Multimodal Focus Sensor Matrix")
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setSpacing(6)

        # Distraction Score Progress Bar
        score_header_layout = QHBoxLayout()
        self.score_title_lbl = QLabel("Distraction Score:")
        self.score_title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        score_header_layout.addWidget(self.score_title_lbl)

        self.score_val_lbl = QLabel("0.0%")
        self.score_val_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.score_val_lbl.setStyleSheet("color: #00f5d4;")
        self.score_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        score_header_layout.addWidget(self.score_val_lbl)
        metrics_layout.addLayout(score_header_layout)

        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        self.score_bar.setFixedHeight(16)
        metrics_layout.addWidget(self.score_bar)

        # Multimodal Badges Stack
        sensor_badges_layout = QVBoxLayout()
        sensor_badges_layout.setSpacing(3)

        self.vision_badge_lbl = QLabel("📷 Vision Sensor: Initializing...")
        self.vision_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        sensor_badges_layout.addWidget(self.vision_badge_lbl)

        self.activity_badge_lbl = QLabel("⌨️ Input Activity: Listening to typing & mouse...")
        self.activity_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        sensor_badges_layout.addWidget(self.activity_badge_lbl)

        self.mic_badge_lbl = QLabel("🎙️ Voice Activity: Listening to mic level...")
        self.mic_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        sensor_badges_layout.addWidget(self.mic_badge_lbl)

        self.window_badge_lbl = QLabel("💻 Active Context: Desktop")
        self.window_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.window_badge_lbl)

        self.audio_status_lbl = QLabel("🎧 Audio Guard: Loading...")
        self.audio_status_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.audio_status_lbl)

        # New sensor badges
        self.context_badge_lbl = QLabel("💻 App Context: Waiting for data...")
        self.context_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.context_badge_lbl)

        self.mouse_badge_lbl = QLabel("🖱️ Mouse Analytics: Waiting for data...")
        self.mouse_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.mouse_badge_lbl)

        self.clipboard_badge_lbl = QLabel("📋 Clipboard: Waiting for data...")
        self.clipboard_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.clipboard_badge_lbl)

        self.agent_badge_lbl = QLabel("⚡ AI Agents: Scanning processes...")
        self.agent_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.agent_badge_lbl)

        self.telegram_badge_lbl = QLabel("📱 Telegram Sentinel: @idle_alerter_bot (Linked)")
        self.telegram_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        sensor_badges_layout.addWidget(self.telegram_badge_lbl)

        self.git_badge_lbl = QLabel("🌱 Git: Detecting repository...")
        self.git_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.git_badge_lbl)

        self.hardware_badge_lbl = QLabel("💻 Hardware: Checking status...")
        self.hardware_badge_lbl.setStyleSheet("color: #8f94a8;")
        sensor_badges_layout.addWidget(self.hardware_badge_lbl)

        metrics_layout.addLayout(sensor_badges_layout)

        # Reset Score Button
        reset_score_btn = QPushButton("Reset Distraction Score (0%)")
        reset_score_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 245, 212, 0.1);
                border: 1px solid #00f5d4;
                color: #00f5d4;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(0, 245, 212, 0.25);
            }
        """)
        reset_score_btn.clicked.connect(self.on_reset_score_clicked)
        metrics_layout.addWidget(reset_score_btn)

        main_layout.addWidget(metrics_group)

        # Group 2: Vision Tracking Sensitivity & Calibration
        vision_group = QGroupBox("Camera Tracker & Sensitivity Controls")
        vision_layout = QVBoxLayout(vision_group)
        vision_layout.setSpacing(6)

        sens_row = QHBoxLayout()
        sens_lbl = QLabel("Face Sensitivity:")
        sens_lbl.setFixedWidth(110)
        sens_row.addWidget(sens_lbl)

        self.sens_combo = QComboBox()
        self.sens_combo.addItems([
            "Relaxed (Wide / Default)",
            "Normal (Standard)",
            "Strict (Tight Tolerances)",
            "Ultra-Tolerant (Widescreen Monitor)"
        ])
        
        sens_map = {"RELAXED": 0, "NORMAL": 1, "STRICT": 2, "ULTRA_TOLERANT": 3}
        saved_sens = self.config.get("vision_sensitivity", "RELAXED")
        self.sens_combo.setCurrentIndex(sens_map.get(saved_sens, 0))
        self.sens_combo.currentIndexChanged.connect(self.on_sensitivity_changed)
        sens_row.addWidget(self.sens_combo)
        vision_layout.addLayout(sens_row)

        ctrl_btn_row = QHBoxLayout()
        self.calib_btn = QPushButton("Start Auto-Calibration")
        self.calib_btn.clicked.connect(self.cv_worker.start_calibration)
        ctrl_btn_row.addWidget(self.calib_btn)

        self.sim_check = QCheckBox("Demo Mode")
        self.sim_check.toggled.connect(self.on_sim_toggled)
        ctrl_btn_row.addWidget(self.sim_check)
        vision_layout.addLayout(ctrl_btn_row)

        mock_controls_layout = QHBoxLayout()
        mock_lbl = QLabel("Mock State:")
        mock_lbl.setFixedWidth(80)
        mock_controls_layout.addWidget(mock_lbl)

        self.mock_combo = QComboBox()
        self.mock_combo.addItems([
            "Fully Focused (Level 0)",
            "Looking Away (Level 1)",
            "Eyes Closed (Level 2)",
            "Zoned Out (Level 3)"
        ])
        self.mock_combo.currentIndexChanged.connect(self.on_mock_changed)
        self.mock_combo.setEnabled(False)
        mock_controls_layout.addWidget(self.mock_combo)
        vision_layout.addLayout(mock_controls_layout)

        main_layout.addWidget(vision_group)

        # Group 3: Pet Selection & Customization
        pet_group = QGroupBox("Pet Species & Custom Skin")
        pet_layout = QVBoxLayout(pet_group)
        pet_layout.setSpacing(6)

        pet_type_layout = QHBoxLayout()
        pet_type_lbl = QLabel("Choose Pet:")
        pet_type_lbl.setFixedWidth(80)
        pet_type_layout.addWidget(pet_type_lbl)

        self.pet_combo = QComboBox()
        self.pet_combo.addItems([
            "The Cyber Cat",
            "The Terminal Dragon",
            "The Mecha Bot",
            "Classic Blob Slime",
            "Cute Panda Bear",
            "Custom Pet (Image / Colors)"
        ])
        
        pet_type_map = {"CAT": 0, "DRAGON": 1, "BOT": 2, "BLOB": 3, "PANDA": 4, "CUSTOM": 5}
        saved_pet = self.config.get("pet_type", "CAT")
        self.pet_combo.setCurrentIndex(pet_type_map.get(saved_pet, 0))
        self.pet_combo.currentIndexChanged.connect(self.on_pet_changed)
        pet_type_layout.addWidget(self.pet_combo)
        pet_layout.addLayout(pet_type_layout)

        # Developer Theme Palette Selector
        theme_layout = QHBoxLayout()
        theme_lbl = QLabel("Color Palette:")
        theme_lbl.setFixedWidth(80)
        theme_layout.addWidget(theme_lbl)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems([
            "Tokyo Night",
            "Dracula",
            "Catppuccin",
            "One Dark Pro"
        ])
        theme_map = {"Tokyo Night": 0, "Dracula": 1, "Catppuccin": 2, "One Dark Pro": 3}
        saved_theme = self.config.get("theme_name", "Tokyo Night")
        self.theme_combo.setCurrentIndex(theme_map.get(saved_theme, 0))
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        pet_layout.addLayout(theme_layout)

        self.custom_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_widget)
        custom_layout.setContentsMargins(0, 2, 0, 2)
        custom_layout.setSpacing(6)

        img_row = QHBoxLayout()
        self.img_path_edit = QLineEdit()
        self.img_path_edit.setPlaceholderText("Custom image file path...")
        self.img_path_edit.setText(self.config.get("custom_image_path", ""))
        self.img_path_edit.setReadOnly(True)
        img_row.addWidget(self.img_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse_image)
        img_row.addWidget(browse_btn)
        custom_layout.addLayout(img_row)

        color_row = QHBoxLayout()
        color_primary_btn = QPushButton("Primary Color")
        color_primary_btn.clicked.connect(self.on_pick_primary_color)
        color_row.addWidget(color_primary_btn)

        color_secondary_btn = QPushButton("Secondary Color")
        color_secondary_btn.clicked.connect(self.on_pick_secondary_color)
        color_row.addWidget(color_secondary_btn)
        custom_layout.addLayout(color_row)

        pet_layout.addWidget(self.custom_widget)
        self.custom_widget.setVisible(saved_pet == "CUSTOM")

        main_layout.addWidget(pet_group)

        # Group 4: Startup & Camera Feed Preview
        bottom_group = QGroupBox("Startup & Camera Feed Preview")
        bottom_layout = QVBoxLayout(bottom_group)
        bottom_layout.setSpacing(6)

        self.autostart_check = QCheckBox("Launch automatically when Windows starts")
        self.autostart_check.setChecked(self.config.get("autostart", False))
        self.autostart_check.toggled.connect(self.on_autostart_toggled)
        bottom_layout.addWidget(self.autostart_check)

        self.preview_check = QCheckBox("Show Camera Feed Preview")
        bottom_layout.addWidget(self.preview_check)
        
        self.preview_lbl = QLabel("Preview feed disabled.")
        self.preview_lbl.setFixedHeight(95)
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.12); background-color: #06070a; border-radius: 8px;")
        bottom_layout.addWidget(self.preview_lbl)
        
        main_layout.addWidget(bottom_group)

        # Exit Button
        quit_btn = QPushButton("Exit Application")
        quit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 75, 114, 0.15);
                border: 1px solid #ff4b72;
                color: #ff4b72;
                padding: 7px;
            }
            QPushButton:hover {
                background-color: rgba(255, 75, 114, 0.3);
            }
        """)
        quit_btn.clicked.connect(self.force_exit)
        main_layout.addWidget(quit_btn)

        self.setLayout(main_layout)

    def apply_current_pet_style(self):
        pet_type = self.config.get("pet_type", "CAT")
        theme_name = self.config.get("theme_name", "Tokyo Night")
        img_path = self.config.get("custom_image_path", "")
        c1 = self.config.get("custom_primary_color", "#a18cd1")
        c2 = self.config.get("custom_secondary_color", "#fbc2eb")
        self.pet_window.set_pet_style(pet_type, img_path, c1, c2, theme_name)

    def apply_saved_sensitivity(self):
        saved_sens = self.config.get("vision_sensitivity", "RELAXED")
        self.cv_worker.set_sensitivity_preset(saved_sens)

    def on_sensitivity_changed(self, index):
        presets = ["RELAXED", "NORMAL", "STRICT", "ULTRA_TOLERANT"]
        preset = presets[index]
        self.config["vision_sensitivity"] = preset
        config_manager.save_config(self.config)
        self.cv_worker.set_sensitivity_preset(preset)

    def on_theme_changed(self, index):
        themes = ["Tokyo Night", "Dracula", "Catppuccin", "One Dark Pro"]
        theme_name = themes[index]
        self.config["theme_name"] = theme_name
        config_manager.save_config(self.config)
        self.apply_current_pet_style()

    def on_pet_changed(self, index):
        type_list = ["CAT", "DRAGON", "BOT", "BLOB", "PANDA", "CUSTOM"]
        pet_type = type_list[index]
        self.config["pet_type"] = pet_type
        self.custom_widget.setVisible(pet_type == "CUSTOM")
        config_manager.save_config(self.config)
        self.apply_current_pet_style()

    def on_browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Custom Pet Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.config["custom_image_path"] = file_path
            self.img_path_edit.setText(file_path)
            config_manager.save_config(self.config)
            self.apply_current_pet_style()

    def on_pick_primary_color(self):
        color = QColorDialog.getColor(QColor(self.config.get("custom_primary_color", "#a18cd1")), self, "Choose Primary Color")
        if color.isValid():
            self.config["custom_primary_color"] = color.name()
            config_manager.save_config(self.config)
            self.apply_current_pet_style()

    def on_pick_secondary_color(self):
        color = QColorDialog.getColor(QColor(self.config.get("custom_secondary_color", "#fbc2eb")), self, "Choose Secondary Color")
        if color.isValid():
            self.config["custom_secondary_color"] = color.name()
            config_manager.save_config(self.config)
            self.apply_current_pet_style()

    def on_autostart_toggled(self, checked):
        self.config["autostart"] = checked
        config_manager.save_config(self.config)
        config_manager.set_windows_autostart(checked)

    def on_sim_toggled(self, checked):
        self.cv_worker.set_simulation_mode(checked)
        self.mock_combo.setEnabled(checked)
        if checked:
            self.on_mock_changed(self.mock_combo.currentIndex())
        else:
            self.calib_btn.setEnabled(True)

    def on_mock_changed(self, index):
        if not self.sim_check.isChecked():
            return
            
        if index == 0:
            self.cv_worker.trigger_mock_state(is_focused=True, distraction_type="NONE")
        elif index == 1:
            self.cv_worker.trigger_mock_state(is_focused=False, distraction_type="LOOKING_AWAY")
        elif index == 2:
            self.cv_worker.trigger_mock_state(is_focused=False, distraction_type="CLOSED_EYES")
        elif index == 3:
            self.cv_worker.trigger_mock_state(is_focused=False, distraction_type="ZONED_OUT")

    def on_focus_update(self, is_focused: bool, distraction_type: str):
        self.latest_is_focused = is_focused
        self.latest_distraction_type = distraction_type

    def on_activity_update(self, is_active: bool, idle_seconds: float):
        self.latest_input_active = is_active
        self.latest_idle_sec = idle_seconds

    def on_mic_update(self, is_speaking: bool, rms_level: float):
        self.latest_mic_active = is_speaking
        self.latest_mic_rms = rms_level

    def on_window_update(self, window_title: str):
        self.latest_window_title = window_title
        disp_title = window_title if len(window_title) <= 35 else window_title[:32] + "..."
        self.window_badge_lbl.setText(f"💻 Active Context: {disp_title}")

    def on_context_update(self, title: str, classification: str):
        """Handle active window context classification."""
        self.latest_app_context = classification
        if hasattr(self, 'context_badge_lbl'):
            emoji = "✅" if classification == "PRODUCTIVE" else "⚠️" if classification == "DISTRACTING" else "💻"
            color = "#00f5d4" if classification == "PRODUCTIVE" else "#ff0844" if classification == "DISTRACTING" else "#8f94a8"
            self.context_badge_lbl.setText(f"{emoji} App Context: {classification}")
            self.context_badge_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

    def on_mouse_update(self, is_steady: bool, velocity: float, erraticness: float):
        """Handle mouse movement analytics."""
        self.latest_mouse_steady = is_steady
        self.latest_mouse_velocity = velocity
        if hasattr(self, 'mouse_badge_lbl'):
            if is_steady:
                self.mouse_badge_lbl.setText(f"🖱️ Mouse: STEADY ({velocity:.0f} px/s)")
                self.mouse_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
            else:
                self.mouse_badge_lbl.setText(f"🖱️ Mouse: ERRATIC ({velocity:.0f} px/s, {erraticness:.1f}e)")
                self.mouse_badge_lbl.setStyleSheet("color: #f6d365; font-weight: bold;")

    def on_clipboard_update(self, was_used: bool, total_changes: int):
        """Handle clipboard activity updates."""
        self.latest_clipboard_active = was_used
        self.latest_clipboard_changes = total_changes
        if hasattr(self, 'clipboard_badge_lbl'):
            if was_used:
                self.clipboard_badge_lbl.setText(f"📋 Clipboard: ACTIVE ({total_changes} changes)")
                self.clipboard_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
            else:
                self.clipboard_badge_lbl.setText(f"📋 Clipboard: INACTIVE")
                self.clipboard_badge_lbl.setStyleSheet("color: #8f94a8;")

    def on_status_message(self, message: str):
        pass

    def on_agent_update(self, is_active: bool, summary: str, agents: list):
        """Handle background AI agent updates."""
        self.latest_agent_active = is_active
        self.latest_agents_summary = summary
        if hasattr(self, 'agent_badge_lbl'):
            if is_active:
                self.agent_badge_lbl.setText(f"⚡ AI Agents: ACTIVE ({summary})")
                self.agent_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
            else:
                self.agent_badge_lbl.setText("⚡ AI Agents: Inactive / Idle")
                self.agent_badge_lbl.setStyleSheet("color: #8f94a8;")

    def on_quiz_solved(self, is_correct: bool, explanation: str):
        """Called when user answers a placement quiz over Telegram on their phone."""
        if is_correct:
            self.engine.heal_focus(25.0)
            self.focus_history.focused_time += 120.0
            self.pet_window.trigger_feed_animation()
            self.voice_alert.play_tone("happy")
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage(
                    "🐾 Pet Fed via Telegram!",
                    "Placement Question Solved! +15 Mood, Focus Restored! ✨",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500
                )
        else:
            self.engine.penalize_focus(10.0)
            self.pet_window.show_custom_bubble("Wrong answer! Keep grinding! 💢", 100)
            self.voice_alert.play_tone("warning")

    def on_pet_action(self, action: str):
        """Handles remote action commands sent from phone via Telegram or Cloud Heartbeat."""
        action = str(action).strip()
        if action == "alarm":
            self.pet_window.trigger_alarm_animation()
            self.voice_alert.play_tone("alarm")
            self.voice_alert.speak("Attention! Wake up and focus on your work!")
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage(
                    "🚨 Desk Alarm Triggered via Phone!",
                    "Telegram companion sounded desk alarm!",
                    QSystemTrayIcon.MessageIcon.Warning,
                    4000
                )
        elif action == "feed":
            self.engine.heal_focus(20.0)
            self.pet_window.trigger_feed_animation()
            self.voice_alert.play_tone("happy")
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage(
                    "🐾 Pet Fed via Telegram!",
                    "Desktop pet fed with treats! Focus boosted. ✨",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500
                )
        elif action == "poke":
            self.pet_window.trigger_poke_animation()
            self.voice_alert.play_tone("warning")
        elif action.startswith("focus:"):
            try:
                val = float(action.split(":", 1)[1])
                self.engine.heal_focus(val)
                self.pet_window.show_custom_bubble(f"Focus Sprint +{int(val)}m! ✨", 120)
                self.voice_alert.play_tone("happy")
            except Exception:
                pass
        elif action == "boss":
            self.engine.distraction_score = 100.0
            self.pet_window.show_custom_bubble("🚨 BOSS APPROACHING! 🚨", 150)
            self.pet_window.set_level(3)
            self.voice_alert.speak("Boss mode activated. Focus immediately.")
        elif action == "sound:off":
            self.voice_alert.enabled = False
            self.pet_window.show_custom_bubble("🔇 Audio Muted", 80)
        elif action == "sound:on":
            self.voice_alert.enabled = True
            self.pet_window.show_custom_bubble("🔊 Audio Enabled", 80)
            self.voice_alert.play_tone("happy")

    def get_live_pet_state(self) -> dict:
        """Returns live pet telemetry for Telegram companion bot and cloud heartbeat."""
        hw = self.system_sentinel.get_hardware_telemetry() if hasattr(self, 'system_sentinel') else {}
        git_info = hw.get("git", {})
        git_sum = git_info.get("summary", "Git: Not detected") if isinstance(git_info, dict) else str(git_info)

        return {
            "pet_type": getattr(self.pet_window, 'species', 'Cyber Pet'),
            "mood": self.focus_history.get_recent_mood(),
            "distraction_score": self.engine.distraction_score,
            "level": self.engine.get_level(),
            "streak": self.focus_history.get_current_streak(),
            "agents_summary": self.latest_agents_summary,
            "active_window": self.latest_window_title,
            "active_window_class": self.latest_app_context,
            "cpu_percent": hw.get("cpu_percent", 0.0),
            "ram_percent": hw.get("ram_percent", 0.0),
            "battery_percent": hw.get("battery_percent", 100),
            "is_plugged": hw.get("is_plugged", True),
            "git_summary": git_sum,
        }

    def on_frame_ready(self, frame):
        if not self.preview_check.isChecked():
            self.preview_lbl.clear()
            self.preview_lbl.setText("Preview feed disabled.")
            return
            
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(q_img)
        self.preview_lbl.setPixmap(pix.scaled(self.preview_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def on_tick(self):
        # Update window context in system sentinel
        if hasattr(self, 'system_sentinel') and self.system_sentinel:
            self.system_sentinel.update_window_context(self.latest_window_title, self.latest_app_context)

        # Update Multimodal Fused Distraction Score with 8 Sensors
        score = self.engine.update_fused(
            is_vision_focused=self.latest_is_focused, 
            is_input_active=self.latest_input_active, 
            is_mic_active=self.latest_mic_active,
            app_context=self.latest_app_context,
            is_mouse_steady=self.latest_mouse_steady,
            is_clipboard_active=self.latest_clipboard_active,
            is_agent_active=self.latest_agent_active,
            dt=0.1
        )
        level = self.engine.get_level()
        state_name = self.engine.get_state_name()
        is_focused = level == 0

        # Update focus history (once per second to avoid flooding)
        self.stats_tick_counter += 1
        if self.stats_tick_counter >= 10:  # Every 10 ticks = 1 second
            self.stats_tick_counter = 0
            self.focus_history.add_sample(score)
            self.focus_history.update_time(is_focused, 1.0)
            self.update_statistics()
            
            # Calculate mood from recent focus history and pass to pet
            # Uses rolling 2-minute window for responsive mood changes
            mood_value = self.focus_history.get_recent_mood()
            self.pet_window.set_mood(mood_value)
            
            # Update mood display
            self.update_mood_display(mood_value)

            # Update Git status badge
            git_data = self.git_tracker.get_summary()
            if hasattr(self, 'git_badge_lbl'):
                self.git_badge_lbl.setText(git_data.get("summary", "🌱 Git: Idle"))
                if git_data.get("is_repo"):
                    self.git_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
                else:
                    self.git_badge_lbl.setStyleSheet("color: #8f94a8;")

            # Update Hardware status badge
            hw = self.system_sentinel.get_hardware_telemetry()
            if hasattr(self, 'hardware_badge_lbl'):
                bat_pct = hw.get("battery_percent", 100)
                plugged = hw.get("is_plugged", True)
                pwr_str = f"⚡ {bat_pct}%" if plugged else f"🔋 {bat_pct}%"
                self.hardware_badge_lbl.setText(f"💻 HW: CPU {hw.get('cpu_percent', 0.0):.0f}% | RAM {hw.get('ram_percent', 0.0):.0f}% | {pwr_str}")
                if bat_pct <= 20 and not plugged:
                    self.hardware_badge_lbl.setStyleSheet("color: #ff0844; font-weight: bold;")
                else:
                    self.hardware_badge_lbl.setStyleSheet("color: #00f5d4;")

            # System Sentinel event evaluation & creative attention-grabbing alerts
            events = self.system_sentinel.tick(self.latest_input_active, dt=1.0)
            for event in events:
                etype = event.get("type")
                if etype == "DOOMSCROLL_DETECTED":
                    win_title = event.get("window_title", "Distraction")
                    dwell = event.get("dwell_seconds", 120.0)
                    self.pet_window.show_custom_bubble(f"Doomscrolling on {win_title[:18]}? Focus up! 🚨", 150)
                    self.voice_alert.speak(f"Distraction alert! You have spent over two minutes on {win_title[:25]}. Return to work.")
                    self.voice_alert.play_tone("warning")
                    if self.telegram_worker:
                        self.telegram_worker.dispatch_doomscroll_alert(win_title, dwell)
                elif etype == "AGENT_FINISHED":
                    agent_name = event.get("previous_agent", "Agent")
                    self.pet_window.show_custom_bubble(f"AI Task Finished: {agent_name[:18]}! Check output ⚡", 150)
                    self.voice_alert.speak("Notice: Background AI agent task has completed.")
                    self.voice_alert.play_tone("happy")
                    if self.telegram_worker:
                        self.telegram_worker.dispatch_agent_finished_alert(agent_name)
                elif etype == "BATTERY_LOW":
                    pct = event.get("percent", 15)
                    self.pet_window.show_custom_bubble(f"Battery Critical ({pct}%)! Plug in charger! 🔋", 150)
                    self.voice_alert.speak(f"Warning: Laptop battery is at {pct} percent. Please connect charger.")
                    self.voice_alert.play_tone("alarm")
                    if self.telegram_worker:
                        self.telegram_worker.dispatch_battery_alert(pct)
                elif etype == "ERGONOMIC_BREAK":
                    sess_min = event.get("session_minutes", 60.0)
                    self.pet_window.show_custom_bubble("Time to stretch and hydrate! 💧", 150)
                    self.voice_alert.speak("Time for a quick stretch and water break. Great focus session.")
                    self.voice_alert.play_tone("happy")
                    if self.telegram_worker:
                        self.telegram_worker.dispatch_break_reminder(sess_min)

        # Update Audio safeguard status
        is_silent = audio_guard.is_audio_silent_mode()
        if is_silent:
            self.audio_status_lbl.setText("🎧 Audio Guard: SILENT (Speakers Active)")
            self.audio_status_lbl.setStyleSheet("color: #fda085;")
        else:
            self.audio_status_lbl.setText("🎧 Audio Guard: SAFE (Headset Active)")
            self.audio_status_lbl.setStyleSheet("color: #00f5d4;")

        # Update Multimodal Badges
        if self.latest_input_active:
            self.activity_badge_lbl.setText(f"⌨️ Input Activity: ACTIVE WORKING ({self.latest_idle_sec:.1f}s idle)")
            self.activity_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        else:
            self.activity_badge_lbl.setText(f"⌨️ Input Activity: IDLE ({self.latest_idle_sec:.1f}s idle)")
            self.activity_badge_lbl.setStyleSheet("color: #f6d365; font-weight: bold;")

        if self.latest_mic_active:
            self.mic_badge_lbl.setText(f"🎙️ Voice Activity: SPEAKING IN CALL / MEETING")
            self.mic_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        else:
            self.mic_badge_lbl.setText(f"🎙️ Voice Activity: SILENT / QUIET")
            self.mic_badge_lbl.setStyleSheet("color: #8f94a8;")

        if self.latest_is_focused:
            self.vision_badge_lbl.setText(f"📷 Vision Sensor: FOCUSED ({self.config.get('vision_sensitivity', 'RELAXED')})")
            self.vision_badge_lbl.setStyleSheet("color: #00f5d4; font-weight: bold;")
        else:
            self.vision_badge_lbl.setText(f"📷 Vision Sensor: {self.latest_distraction_type}")
            self.vision_badge_lbl.setStyleSheet("color: #ff0844; font-weight: bold;")

        # Update Score Metrics UI
        self.score_val_lbl.setText(f"{score:.1f}%")
        self.score_bar.setValue(int(score))
        
        if level == 0:
            self.score_val_lbl.setStyleSheet("color: #00f5d4;")
            self.score_bar.setStyleSheet("QProgressBar::chunk { background-color: #00f5d4; }")
        elif level == 1:
            self.score_val_lbl.setStyleSheet("color: #4facfe;")
            self.score_bar.setStyleSheet("QProgressBar::chunk { background-color: #4facfe; }")
        elif level == 2:
            self.score_val_lbl.setStyleSheet("color: #f6d365;")
            self.score_bar.setStyleSheet("QProgressBar::chunk { background-color: #f6d365; }")
        else:
            self.score_val_lbl.setStyleSheet("color: #ff0844;")
            self.score_bar.setStyleSheet("QProgressBar::chunk { background-color: #ff0844; }")

        # Sync Pet Window & Screen Overlay
        self.pet_window.set_level(level)
        self.screen_overlay.set_level(level)

        if level == 3:
            self.popup_spawn_ticks += 1
            if self.popup_spawn_ticks >= 40:
                self.popup_spawn_ticks = 0
                self.spawn_fake_popup()
        else:
            self.popup_spawn_ticks = 0
            self.clear_all_popups()

        # Check desk inactivity away alert (idle > IDLE_THRESHOLD_MINUTES)
        idle_min = self.latest_idle_sec / 60.0
        if idle_min >= config.IDLE_THRESHOLD_MINUTES:
            self.away_alert_tick_counter += 1
            # Dispatch at threshold, then every 15 minutes (9000 ticks at 100ms)
            if self.away_alert_tick_counter == 1 or self.away_alert_tick_counter % 9000 == 0:
                if self.telegram_worker:
                    self.telegram_worker.dispatch_away_alert(idle_min, self.latest_agents_summary)
        else:
            self.away_alert_tick_counter = 0

    def update_statistics(self):
        """Update the statistics panel with latest focus data."""
        # Focus percentage
        focus_pct = self.focus_history.get_focus_percentage()
        self.stat_focus_val.setText(f"{focus_pct:.0f}%")
        if focus_pct >= 80:
            self.stat_focus_val.setStyleSheet("color: #00f5d4; font-size: 20px; font-weight: bold;")
        elif focus_pct >= 50:
            self.stat_focus_val.setStyleSheet("color: #f6d365; font-size: 20px; font-weight: bold;")
        else:
            self.stat_focus_val.setStyleSheet("color: #ff0844; font-size: 20px; font-weight: bold;")
        
        # Focus streak
        streak_text = self.focus_history.get_current_streak()
        self.stat_streak_val.setText(streak_text)
        
        # Session time
        session_secs = int(time.time() - self.focus_history.session_start)
        if session_secs < 60:
            session_text = f"{session_secs}s"
        elif session_secs < 3600:
            session_text = f"{session_secs // 60}m {session_secs % 60}s"
        else:
            hours = session_secs // 3600
            mins = (session_secs % 3600) // 60
            session_text = f"{hours}h {mins}m"
        self.stat_session_val.setText(session_text)
        
        # Draw mini history bar (simple colored blocks)
        self.draw_history_bar()

    def update_mood_display(self, mood_value: float):
        """Update the mood indicator in the dashboard."""
        if mood_value >= 85:
            emoticon, name, color = "😄", "Ecstatic", "#ffd700"
        elif mood_value >= 65:
            emoticon, name, color = "🙂", "Happy", "#00f5d4"
        elif mood_value >= 40:
            emoticon, name, color = "😐", "Neutral", "#8f94a8"
        elif mood_value >= 20:
            emoticon, name, color = "😒", "Grumpy", "#4facfe"
        else:
            emoticon, name, color = "😤", "Angry", "#ff0844"
        
        self.mood_emoticon_lbl.setText(emoticon)
        self.mood_name_lbl.setText(name)
        self.mood_name_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

    def draw_history_bar(self):
        """Update the history bar widget with latest scores."""
        if hasattr(self, 'history_bar') and self.history_bar:
            self.history_bar.set_scores(self.focus_history.scores)
            self.history_bar.update()

    def on_reset_score_clicked(self):
        self.engine.reset()
        self.clear_all_popups()

    def on_popup_acknowledged(self):
        self.engine.reset()
        self.clear_all_popups()

    def spawn_fake_popup(self):
        popup = FakePopup(index=len(self.active_popups))
        popup.acknowledged.connect(self.on_popup_acknowledged)
        screen_geo = QGuiApplication.primaryScreen().geometry()
        px = random.randint(50, screen_geo.width() - 350)
        py = random.randint(50, screen_geo.height() - 200)
        popup.move(px, py)
        popup.show()
        self.active_popups.append(popup)

    def clear_all_popups(self):
        for p in self.active_popups:
            p.close()
        self.active_popups.clear()

    def closeEvent(self, event):
        if hasattr(self, 'tray_icon') and self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.force_exit()

    def force_exit(self):
        self.loop_timer.stop()
        self.clear_all_popups()
        self.cv_worker.stop()
        self.activity_worker.stop()
        self.mic_worker.stop()
        self.window_worker.stop()
        if self.context_worker:
            self.context_worker.stop()
        if self.mouse_worker:
            self.mouse_worker.stop()
        if self.clipboard_worker:
            self.clipboard_worker.stop()
        self.pet_window.close()
        self.screen_overlay.close()
        QApplication.quit()


class HistoryBarWidget(QWidget):
    """Custom widget that renders a color-coded focus history bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scores = []
        self.setMinimumHeight(16)
        
    def set_scores(self, scores):
        self.scores = list(scores) if scores else []
        
    def paintEvent(self, event):
        if not self.scores:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bar_width = self.width()
        bar_height = self.height()
        num_samples = len(self.scores)
        
        if num_samples < 1 or bar_width <= 0:
            painter.end()
            return
        
        # Bar background
        painter.fillRect(self.rect(), QColor(20, 22, 30))
        
        # Draw rounded rect clip
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(self.rect()), 4, 4)
        painter.setClipPath(clip_path)
        
        block_width = max(2, bar_width // num_samples)
        
        for i, score in enumerate(self.scores):
            x = i * block_width
            if score <= 20:
                color = QColor(0, 245, 212, 180)  # Green
            elif score <= 50:
                color = QColor(79, 172, 254, 180)  # Blue
            elif score <= 80:
                color = QColor(246, 211, 101, 180)  # Yellow
            else:
                color = QColor(255, 8, 68, 180)  # Red
            
            painter.fillRect(QRect(x, 0, block_width, bar_height), QBrush(color))
        
        painter.end()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running daemon when main window is hidden
    
    config = config_manager.load_config()
    if config.get("autostart", False):
        config_manager.set_windows_autostart(True)
    
    # Initialize Core Engines & Sentinels
    engine = IntensityEngine()
    git_tracker = GitTracker()
    voice_alert = VoiceAlert(enabled=True)
    idle_det = IdleDetector()
    agent_det = AgentDetector()
    system_sentinel = SystemSentinel(
        git_tracker=git_tracker,
        idle_detector=idle_det,
        agent_detector=agent_det,
    )
    
    # Initialize Overlay Windows
    screen_overlay = ScreenOverlay()
    screen_overlay.show()
    
    pet_window = PetWindow(screen_overlay=screen_overlay)
    pet_window.show()
    
    # Initialize background Worker Threads
    cv_worker = CVTrackerWorker(camera_index=0)
    cv_worker.start()

    activity_worker = ActivityTrackerWorker(idle_threshold_seconds=3.0)
    activity_worker.start()

    mic_worker = MicTrackerWorker()
    mic_worker.start()

    window_worker = WindowTrackerWorker()
    window_worker.start()
    
    # Initialize focus sensor workers
    context_worker = ContextScannerWorker()
    context_worker.start()
    
    mouse_worker = MouseAnalyticsWorker()
    mouse_worker.start()
    
    # Initialize AI Agent Tracker & Telegram Companion Workers
    quiz_manager = QuizManager()
    agent_worker = AgentTrackerWorker()
    agent_worker.start()

    telegram_worker = TelegramBotWorker(quiz_manager)
    telegram_worker.start()

    # Start Hardware Sleep & Power Interceptor
    power_monitor = PowerMonitor()
    power_monitor.start()

    # Initialize Main Controller Settings Panel with merged Awaken workers
    settings_panel = SettingsPanel(
        engine, pet_window, screen_overlay, cv_worker, activity_worker, mic_worker, window_worker,
        context_worker=context_worker, mouse_worker=mouse_worker, clipboard_worker=clipboard_worker,
        agent_worker=agent_worker, telegram_worker=telegram_worker,
        git_tracker=git_tracker, voice_alert=voice_alert, system_sentinel=system_sentinel,
    )

    # Record PID for status and stop utilities
    pid_file = config.DATA_DIR / "awaken.pid"
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    def cleanup_pid():
        try:
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass

    # Clean shutdown of workers
    app.aboutToQuit.connect(cleanup_pid)
    app.aboutToQuit.connect(agent_worker.stop)
    app.aboutToQuit.connect(telegram_worker.stop)
    app.aboutToQuit.connect(power_monitor.stop)

    # Start periodic heartbeat to cloud server if configured
    if config.CLOUD_SERVER_URL:
        heartbeat_client = HeartbeatClient(
            idle_det,
            agent_det,
            state_provider=settings_panel.get_live_pet_state,
            action_callback=settings_panel.on_pet_action,
        )
        heartbeat_timer = QTimer()
        heartbeat_timer.timeout.connect(heartbeat_client.send_heartbeat)
        heartbeat_timer.start(config.HEARTBEAT_INTERVAL_SECONDS * 1000)
        QTimer.singleShot(1000, heartbeat_client.send_heartbeat)
    
    # Click on Desktop Pet opens/toggles the Control Dashboard!
    pet_window.pet_clicked.connect(settings_panel.toggle_visibility)
    
    # Connect system events to pet idle reactions
    last_window_title = ""
    def on_window_changed_for_pet(title: str):
        nonlocal last_window_title
        if title != last_window_title:
            last_window_title = title
            pet_window.notify_window_changed()
    window_worker.window_update.connect(on_window_changed_for_pet)
    
    def on_typing_for_pet(is_active: bool, idle_sec: float):
        if is_active:
            pet_window.notify_typing_detected()
    activity_worker.activity_update.connect(on_typing_for_pet)

    # Check for --daemon or --minimized command line flag
    daemon_mode = "--daemon" in sys.argv or "--minimized" in sys.argv
    if not daemon_mode:
        settings_panel.show_and_activate()
    else:
        settings_panel.hide()
        if hasattr(settings_panel, 'tray_icon'):
            settings_panel.tray_icon.showMessage(
                "Desktop Focus Pet",
                "Running as background daemon. Click your desktop pet or tray icon to open dashboard.",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
