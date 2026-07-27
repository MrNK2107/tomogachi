import sys
import os
import random
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QProgressBar, QCheckBox, 
                             QGroupBox, QComboBox, QFileDialog, QColorDialog, QLineEdit,
                             QSystemTrayIcon, QMenu)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QColor, QGuiApplication, QPainter, QBrush

from cv_tracker import CVTrackerWorker
from activity_tracker import ActivityTrackerWorker
from mic_tracker import MicTrackerWorker
from window_tracker import WindowTrackerWorker
from intensity_engine import IntensityEngine
from pet_gui import PetWindow, ScreenOverlay, FakePopup
import audio_guard
import config_manager

class SettingsPanel(QWidget):
    """
    Ultra-Premium Multimodal Control Dashboard for Desktop Focus Pet.
    Runs as a background daemon process with Windows System Tray integration
    and Pet click-to-toggle visibility.
    """
    def __init__(self, engine, pet_window, screen_overlay, cv_worker, activity_worker, mic_worker, window_worker):
        super().__init__()
        self.engine = engine
        self.pet_window = pet_window
        self.screen_overlay = screen_overlay
        self.cv_worker = cv_worker
        self.activity_worker = activity_worker
        self.mic_worker = mic_worker
        self.window_worker = window_worker
        
        self.config = config_manager.load_config()
        self.latest_is_focused = True
        self.latest_distraction_type = "NONE"
        self.latest_input_active = True
        self.latest_idle_sec = 0.0
        self.latest_mic_active = False
        self.latest_mic_rms = 0.0
        self.latest_window_title = "Desktop"

        self.active_popups = []
        self.popup_spawn_ticks = 0

        self.setWindowTitle("Desktop Focus Pet - Control Dashboard")
        self.setFixedSize(500, 840)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        
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

    def on_status_message(self, message: str):
        pass

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
        # Update Multimodal Fused Distraction Score
        score = self.engine.update_fused(
            is_vision_focused=self.latest_is_focused, 
            is_input_active=self.latest_input_active, 
            is_mic_active=self.latest_mic_active, 
            dt=0.1
        )
        level = self.engine.get_level()
        state_name = self.engine.get_state_name()

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
        # Minimize to System Tray daemon when top-right window 'X' is clicked
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
        self.pet_window.close()
        self.screen_overlay.close()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running daemon when main window is hidden
    
    config = config_manager.load_config()
    if config.get("autostart", False):
        config_manager.set_windows_autostart(True)
    
    # Initialize Core Engines
    engine = IntensityEngine()
    
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
    
    # Initialize Main Controller Settings Panel
    settings_panel = SettingsPanel(engine, pet_window, screen_overlay, cv_worker, activity_worker, mic_worker, window_worker)
    
    # Click on Desktop Pet opens/toggles the Control Dashboard!
    pet_window.pet_clicked.connect(settings_panel.toggle_visibility)

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
