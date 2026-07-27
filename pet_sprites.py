import sys
import math
import random
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QComboBox, QSlider, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPainterPath, 
                           QPolygonF, QLinearGradient, QRadialGradient)

# High-Contrast Developer Color Palettes
PALETTES = {
    "Tokyo Night": {
        "bg": "#1a1b26", "primary": "#7aa2f7", "secondary": "#bb9af7", 
        "accent": "#f7768e", "eye": "#7dcfff", "dark": "#15161e", "text": "#c0caf5"
    },
    "Dracula": {
        "bg": "#282a36", "primary": "#bd93f9", "secondary": "#ff79c6", 
        "accent": "#ff5555", "eye": "#8be9fd", "dark": "#1e1f29", "text": "#f8f8f2"
    },
    "Catppuccin": {
        "bg": "#1e1e2e", "primary": "#cba6f7", "secondary": "#f5c2e7", 
        "accent": "#f38ba8", "eye": "#89dceb", "dark": "#11111b", "text": "#cdd6f4"
    },
    "One Dark Pro": {
        "bg": "#21252b", "primary": "#61afef", "secondary": "#c678dd", 
        "accent": "#e06c75", "eye": "#56b6c2", "dark": "#1b1d23", "text": "#abb2bf"
    }
}

class ProceduralPetWidget(QWidget):
    """
    Procedural Vector/Pixel-Style Desktop Pet Widget.
    Renders Cyber Cat, Terminal Dragon, and Mecha Bot at 12-15 FPS with DPI crispness.
    """
    IDLE = 0       # Score 0-20
    ALERT = 1      # Score 21-50
    ATTENTION = 2  # Score 51-80
    CHAOS = 3      # Score 81-100

    def __init__(self, character_type="CAT", theme_name="Tokyo Night", parent=None):
        super().__init__(parent)
        self.character_type = character_type.upper()
        self.theme_name = theme_name
        self.state = self.IDLE
        self.scale_factor = 2.0  # Crisp DPI scaling multiplier
        
        self.anim_frame = 0
        self.setFixedSize(180, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Fire / Spark particle systems for Dragon & Mecha Bot
        self.particles = []
        self.sleep_particles = []
        
        # 12 FPS Animation Timer (~83ms interval)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(83)

    def set_character(self, char_type: str):
        self.character_type = char_type.upper()
        self.update()

    def set_theme(self, theme_name: str):
        if theme_name in PALETTES:
            self.theme_name = theme_name
        self.update()

    def set_state(self, state: int):
        if self.state != state:
            self.state = state
            self.anim_frame = 0
            self.particles.clear()
            self.sleep_particles.clear()
        self.update()

    def update_animation(self):
        self.anim_frame = (self.anim_frame + 1) % 120
        
        # Update particles for Dragon/Bot in Chaos state
        if self.state == self.CHAOS:
            if random.random() < 0.6:
                self.particles.append({
                    'x': 90.0 + random.randint(-15, 15),
                    'y': 110.0,
                    'vx': random.uniform(-1.5, 1.5),
                    'vy': random.uniform(-3.0, -1.0),
                    'size': random.randint(3, 6),
                    'alpha': 255
                })
            for p in list(self.particles):
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['alpha'] -= 18
                if p['alpha'] <= 0:
                    self.particles.remove(p)

        # Sleep particles for IDLE state
        if self.state == self.IDLE and self.anim_frame % 25 == 0:
            self.sleep_particles.append({
                'x': 100.0, 'y': 85.0,
                'alpha': 240, 'text': random.choice(['z', 'Z'])
            })
        for p in list(self.sleep_particles):
            p['y'] -= 0.6
            p['x'] += 0.3 * math.sin(p['y'] * 0.1)
            p['alpha'] -= 5
            if p['alpha'] <= 0:
                self.sleep_particles.remove(p)
                
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        palette = PALETTES.get(self.theme_name, PALETTES["Tokyo Night"])
        
        # Apply jitter shake for CHAOS state
        shake_x, shake_y = 0, 0
        if self.state == self.CHAOS:
            shake_x = random.randint(-4, 4)
            shake_y = random.randint(-4, 4)
            
        painter.translate(shake_x, shake_y)

        # Draw shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 45)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(45, 142, 90, 16))

        # Render active character species
        if "DRAGON" in self.character_type:
            self.draw_dragon(painter, palette)
        elif "BOT" in self.character_type or "MECHA" in self.character_type:
            self.draw_mecha_bot(painter, palette)
        else:
            self.draw_cyber_cat(painter, palette)

        # Draw Overlay Icons & Particles
        self.draw_effects(painter, palette)

    # ----------------- 1. THE CYBER CAT -----------------
    def draw_cyber_cat(self, painter: QPainter, palette: dict):
        f = self.anim_frame
        st = self.state
        
        # Colors
        c_primary = QColor(palette["accent"] if st == self.CHAOS and (f % 4 < 2) else palette["primary"])
        c_secondary = QColor(palette["secondary"])
        c_dark = QColor(palette["dark"])
        c_eye = QColor("#ff0055" if st == self.CHAOS else palette["eye"])

        # Breathing / Movement offsets
        breath_y = int(3 * math.sin(f * 0.2)) if st == self.IDLE else int(4 * math.sin(f * 0.5))
        bounce_y = int(6 * math.sin(f * 0.8)) if st == self.ATTENTION else 0
        
        x, y, w, h = 45, 65 + breath_y - bounce_y, 90, 75

        # Reactive S-curve Tail
        tail_path = QPainterPath()
        tail_path.moveTo(x + 10, y + 55)
        sway = 18 * math.sin(f * 0.3) if st < 2 else 25 * math.sin(f * 0.8)
        tail_path.cubicTo(x - 20 + sway, y + 35, x - 15 - sway, y + 10, x - 30 + sway, y + 15)
        painter.setPen(QPen(c_secondary, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(tail_path)

        # Cat Body (Rounded Rect)
        painter.setPen(QPen(c_dark, 2))
        painter.setBrush(QBrush(c_primary))
        painter.drawRoundedRect(QRect(x, y, w, h), 22, 22)

        # Sharp Cyber Cat Ears
        painter.setBrush(QBrush(c_primary))
        # Left Ear
        l_ear = QPolygonF([QPointF(x + 10, y + 12), QPointF(x - 6, y - 16), QPointF(x + 32, y + 2)])
        painter.drawPolygon(l_ear)
        # Left Inner Ear
        painter.setBrush(QBrush(c_secondary))
        l_inner = QPolygonF([QPointF(x + 12, y + 10), QPointF(x - 2, y - 8), QPointF(x + 26, y + 4)])
        painter.drawPolygon(l_inner)

        # Right Ear
        painter.setBrush(QBrush(c_primary))
        r_ear = QPolygonF([QPointF(x + 80, y + 12), QPointF(x + 96, y - 16), QPointF(x + 58, y + 2)])
        painter.drawPolygon(r_ear)
        # Right Inner Ear
        painter.setBrush(QBrush(c_secondary))
        r_inner = QPolygonF([QPointF(x + 78, y + 10), QPointF(x + 92, y - 8), QPointF(x + 64, y + 4)])
        painter.drawPolygon(r_inner)

        # Legs (4-Frame Walking Trot in ALERT / ATTENTION)
        painter.setBrush(QBrush(c_secondary))
        painter.setPen(Qt.PenStyle.NoPen)
        leg_off = int(6 * math.sin(f * 0.6)) if st in [self.ALERT, self.ATTENTION] else 0
        painter.drawRoundedRect(QRect(x + 14 + leg_off, y + h - 6, 16, 16), 5, 5)
        painter.drawRoundedRect(QRect(x + 60 - leg_off, y + h - 6, 16, 16), 5, 5)

        # Cyber Whiskers
        painter.setPen(QPen(c_secondary, 2))
        painter.drawLine(x + 2, y + 40, x - 14, y + 36)
        painter.drawLine(x + 2, y + 46, x - 16, y + 48)
        painter.drawLine(x + w - 2, y + 40, x + w + 14, y + 36)
        painter.drawLine(x + w - 2, y + 46, x + w + 16, y + 48)

        # Eyes & Visor
        eye_y = y + 28
        if st == self.IDLE:
            # Blinking closed eye arcs
            painter.setPen(QPen(c_eye, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(x + 18, eye_y - 6, 18, 14), 180 * 16, 180 * 16)
            painter.drawArc(QRect(x + 54, eye_y - 6, 18, 14), 180 * 16, 180 * 16)
        else:
            # Glowing open cyber eyes
            painter.setBrush(QBrush(c_eye))
            painter.setPen(QPen(c_dark, 1.5))
            painter.drawEllipse(QRect(x + 18, eye_y - 6, 18, 18))
            painter.drawEllipse(QRect(x + 54, eye_y - 6, 18, 18))

            # Vertical Cat Pupil
            painter.setBrush(QBrush(c_dark))
            pupil_w = 4 if st == self.CHAOS else 6
            painter.drawRoundedRect(QRect(x + 27 - pupil_w//2, eye_y - 2, pupil_w, 10), 2, 2)
            painter.drawRoundedRect(QRect(x + 63 - pupil_w//2, eye_y - 2, pupil_w, 10), 2, 2)

        # Cute Cyber Nose & Mouth
        painter.setBrush(QBrush(c_secondary))
        painter.drawPolygon(QPolygonF([QPointF(x + 45, y + 42), QPointF(x + 41, y + 38), QPointF(x + 49, y + 38)]))

    # ----------------- 2. THE TERMINAL DRAGON -----------------
    def draw_dragon(self, painter: QPainter, palette: dict):
        f = self.anim_frame
        st = self.state

        c_primary = QColor(palette["accent"] if st == self.CHAOS and (f % 4 < 2) else palette["primary"])
        c_secondary = QColor(palette["secondary"])
        c_accent = QColor(palette["accent"])
        c_dark = QColor(palette["dark"])
        c_eye = QColor("#ff0055" if st == self.CHAOS else palette["eye"])

        breath_y = int(3 * math.sin(f * 0.2)) if st == self.IDLE else int(4 * math.sin(f * 0.6))
        bounce_y = int(6 * math.sin(f * 0.8)) if st == self.ATTENTION else 0
        x, y, w, h = 45, 65 + breath_y - bounce_y, 90, 75

        # Dragon Spiked Tail
        tail_path = QPainterPath()
        tail_path.moveTo(x + 15, y + 50)
        sway = 20 * math.sin(f * 0.4)
        tail_path.quadTo(x - 25 + sway, y + 65, x - 30 + sway, y + 35)
        painter.setPen(QPen(c_secondary, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(tail_path)

        # Dragon Tail Flame / Spike Tip
        painter.setBrush(QBrush(c_accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(int(x - 36 + sway), y + 28, 12, 12))

        # Animated Wings Flapping
        wing_angle = math.sin(f * 0.7) if st in [self.ALERT, self.CHAOS] else 0.2
        # Left Wing
        l_wing = QPolygonF([
            QPointF(x + 15, y + 25),
            QPointF(x - 22, y - 10 + int(12 * wing_angle)),
            QPointF(x - 5, y + 35)
        ])
        painter.setBrush(QBrush(c_secondary))
        painter.drawPolygon(l_wing)

        # Right Wing
        r_wing = QPolygonF([
            QPointF(x + 75, y + 25),
            QPointF(x + 112, y - 10 + int(12 * wing_angle)),
            QPointF(x + 95, y + 35)
        ])
        painter.drawPolygon(r_wing)

        # Dragon Body (Oval with Spikes)
        painter.setBrush(QBrush(c_primary))
        painter.setPen(QPen(c_dark, 2))
        painter.drawEllipse(QRect(x, y, w, h))

        # Dragon Horns
        painter.setBrush(QBrush(c_accent))
        l_horn = QPolygonF([QPointF(x + 22, y + 8), QPointF(x + 10, y - 16), QPointF(x + 32, y + 4)])
        r_horn = QPolygonF([QPointF(x + 68, y + 8), QPointF(x + 80, y - 16), QPointF(x + 58, y + 4)])
        painter.drawPolygon(l_horn)
        painter.drawPolygon(r_horn)

        # Dragon Eyes & Nostrils
        eye_y = y + 28
        if st == self.IDLE:
            painter.setPen(QPen(c_eye, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(x + 20, eye_y - 4, 16, 12), 180 * 16, 180 * 16)
            painter.drawArc(QRect(x + 54, eye_y - 4, 16, 12), 180 * 16, 180 * 16)
        else:
            painter.setBrush(QBrush(c_eye))
            painter.setPen(QPen(c_dark, 1.5))
            painter.drawEllipse(QRect(x + 20, eye_y - 6, 18, 18))
            painter.drawEllipse(QRect(x + 52, eye_y - 6, 18, 18))
            painter.setBrush(QBrush(c_dark))
            painter.drawEllipse(QRect(x + 27, eye_y - 1, 5, 8))
            painter.drawEllipse(QRect(x + 59, eye_y - 1, 5, 8))

        # Nostrils (Smoke Puffs)
        painter.setBrush(QBrush(c_dark))
        painter.drawEllipse(QRect(x + 38, y + 44, 4, 4))
        painter.drawEllipse(QRect(x + 48, y + 44, 4, 4))

    # ----------------- 3. THE MECHA BOT -----------------
    def draw_mecha_bot(self, painter: QPainter, palette: dict):
        f = self.anim_frame
        st = self.state

        c_primary = QColor(palette["accent"] if st == self.CHAOS and (f % 4 < 2) else palette["primary"])
        c_secondary = QColor(palette["secondary"])
        c_dark = QColor(palette["dark"])
        c_visor = QColor("#ff0055" if st == self.CHAOS else palette["eye"])

        # Sinusoidal Hovering Floating Motion
        hover_y = int(8 * math.sin(f * 0.25))
        x, y, w, h = 45, 60 + hover_y, 90, 70

        # Thruster Flame / Particle Glow Underneath
        thruster_h = int(10 + 6 * math.sin(f * 0.8))
        grad = QLinearGradient(90, y + h, 90, y + h + thruster_h)
        grad.setColorAt(0.0, QColor("#00f5d4"))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(x + 25, y + h - 4, 40, thruster_h))

        # Mecha Chassis Head
        painter.setBrush(QBrush(c_primary))
        painter.setPen(QPen(c_dark, 2))
        painter.drawRoundedRect(QRect(x, y, w, h), 18, 18)

        # Spinning Antenna
        painter.setPen(QPen(c_secondary, 3))
        painter.drawLine(90, y, 90, y - 18)
        antenna_color = QColor("#ff0055" if (f // 6) % 2 == 0 else palette["accent"])
        painter.setBrush(QBrush(antenna_color))
        painter.drawEllipse(QRect(84, y - 24, 12, 12))

        # Cyber Visor Box
        painter.setBrush(QBrush(c_dark))
        painter.setPen(QPen(c_secondary, 1.5))
        painter.drawRoundedRect(QRect(x + 10, y + 18, w - 20, 26), 8, 8)

        # LED Visor Scanning Bar
        if st == self.IDLE:
            painter.setBrush(QBrush(c_visor))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(x + 20, y + 26, 16, 10), 3, 3)
            painter.drawRoundedRect(QRect(x + 54, y + 26, 16, 10), 3, 3)
        else:
            # Sweeping scanning bar
            scan_x = x + 16 + int(24 * (0.5 + 0.5 * math.sin(f * 0.4)))
            painter.setBrush(QBrush(c_visor))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(scan_x, y + 24, 22, 14), 4, 4)

        # Mecha Ear Bolts
        painter.setBrush(QBrush(c_secondary))
        painter.drawEllipse(QRect(x - 6, y + 24, 10, 14))
        painter.drawEllipse(QRect(x + w - 4, y + 24, 10, 14))

    # ----------------- OVERLAY EFFECTS -----------------
    def draw_effects(self, painter: QPainter, palette: dict):
        st = self.state
        
        # Zzz Particles for IDLE
        if st == self.IDLE:
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            for p in self.sleep_particles:
                painter.setPen(QColor(palette["secondary"]))
                painter.drawText(int(p['x']), int(p['y']), p['text'])

        # Fire / Spark Particles for CHAOS
        if st == self.CHAOS:
            for p in self.particles:
                painter.setBrush(QBrush(QColor(255, random.randint(50, 180), 0, int(p['alpha']))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])

        # State Indicator Badges above head (ATTENTION: "?", CHAOS: "!")
        if st == self.ATTENTION:
            bx, by = 90 - 14, 18
            painter.setBrush(QBrush(QColor(palette["secondary"])))
            painter.setPen(QPen(QColor(palette["dark"]), 1.5))
            painter.drawRoundedRect(bx, by, 28, 28, 8, 8)
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            painter.setPen(QColor(palette["dark"]))
            painter.drawText(QRect(bx, by, 28, 28), Qt.AlignmentFlag.AlignCenter, "?")

        elif st == self.CHAOS:
            bx, by = 90 - 14, 14
            painter.setBrush(QBrush(QColor("#ff0844")))
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawRoundedRect(bx, by, 28, 28, 8, 8)
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRect(bx, by, 28, 28), Qt.AlignmentFlag.AlignCenter, "!")

class PetPreviewWindow(QWidget):
    """
    Interactive Live Preview Dashboard for pet_sprites.py.
    Allows selecting character, cycling state, choosing palette, and scaling DPI.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Procedural Desktop Pets - Interactive Live Preview")
        self.setFixedSize(560, 480)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #12131c;
                color: #e2e4ed;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: #7aa2f7;
            }
            QPushButton {
                background-color: #1f2335;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #292e42;
                border-color: #7aa2f7;
                color: #7aa2f7;
            }
            QPushButton:checked {
                background-color: #7aa2f7;
                color: #15161e;
            }
            QComboBox {
                background-color: #1f2335;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 5px 10px;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        
        # Header
        title_lbl = QLabel("VS CODE / CODEX PROCEDURAL PETS PREVIEW")
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #7aa2f7; letter-spacing: 1px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        # Pet Display Canvas
        canvas_box = QGroupBox("Live Render Canvas")
        canvas_layout = QHBoxLayout(canvas_box)
        canvas_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.pet_widget = ProceduralPetWidget("CAT", "Tokyo Night", self)
        canvas_layout.addWidget(self.pet_widget)
        layout.addWidget(canvas_box)

        # Control Panel
        controls_box = QGroupBox("Animation & Character Controls")
        ctrl_layout = QVBoxLayout(controls_box)
        ctrl_layout.setSpacing(10)

        # Character Selector
        char_row = QHBoxLayout()
        char_row.addWidget(QLabel("Character:"))
        self.char_combo = QComboBox()
        self.char_combo.addItems(["Cyber Cat", "Terminal Dragon", "Mecha Bot"])
        self.char_combo.currentIndexChanged.connect(self.on_char_changed)
        char_row.addWidget(self.char_combo)

        char_row.addWidget(QLabel("Theme Palette:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Tokyo Night", "Dracula", "Catppuccin", "One Dark Pro"])
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        char_row.addWidget(self.theme_combo)
        ctrl_layout.addLayout(char_row)

        # State Buttons Row
        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("Animation State:"))
        
        self.btn_idle = QPushButton("IDLE / SLEEP (0-20)")
        self.btn_idle.clicked.connect(lambda: self.set_state(0))
        state_row.addWidget(self.btn_idle)

        self.btn_alert = QPushButton("ALERT (21-50)")
        self.btn_alert.clicked.connect(lambda: self.set_state(1))
        state_row.addWidget(self.btn_alert)

        self.btn_nudge = QPushButton("ATTENTION (51-80)")
        self.btn_nudge.clicked.connect(lambda: self.set_state(2))
        state_row.addWidget(self.btn_nudge)

        self.btn_chaos = QPushButton("CHAOS / RAGE (81-100)")
        self.btn_chaos.clicked.connect(lambda: self.set_state(3))
        state_row.addWidget(self.btn_chaos)

        ctrl_layout.addLayout(state_row)
        layout.addWidget(controls_box)

    def on_char_changed(self, index):
        chars = ["CAT", "DRAGON", "BOT"]
        self.pet_widget.set_character(chars[index])

    def on_theme_changed(self, index):
        themes = ["Tokyo Night", "Dracula", "Catppuccin", "One Dark Pro"]
        self.pet_widget.set_theme(themes[index])

    def set_state(self, state: int):
        self.pet_widget.set_state(state)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PetPreviewWindow()
    window.show()
    sys.exit(app.exec())
