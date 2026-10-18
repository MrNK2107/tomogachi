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

# Toy definitions for play animation
TOYS = {
    "BALL": {"emoji": "⚪", "color": "#ff6b81", "size": 10},
    "MOUSE": {"emoji": "🐭", "color": None, "size": 14},
    "STAR": {"emoji": "⭐", "color": None, "size": 14},
    "BUTTERFLY": {"emoji": "🦋", "color": None, "size": 14},
    "SPARKLE": {"emoji": "✦", "color": "#ffd700", "size": 8},
    "LASER_DOT": {"emoji": "🔴", "color": None, "size": 10},
}


class ProceduralPetWidget(QWidget):
    """
    Procedural Vector/Pixel-Style Desktop Pet Widget.
    Renders all pet species at 12-15 FPS with DPI crispness.
    Supports external rendering via render() for integration into PetWindow.
    """
    IDLE = 0       # Score 0-20
    ALERT = 1      # Score 21-50
    ATTENTION = 2  # Score 51-80
    CHAOS = 3      # Score 81-100

    # Idle action types
    IDLE_ACTIONS = ["blink", "look_around", "yawn", "stretch", "scratch", "play"]
    
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
        
        # Pet interaction state
        self.is_happy = False
        self.happy_timer = 0
        self.is_waving = False
        self.wave_timer = 0
        
        # --- IDLE ANIMATION SYSTEM ---
        self._idle_action = None         # Current idle action name
        self._idle_action_frame = 0      # Frame within current action
        self._idle_action_duration = 0   # Total duration of current action
        self._idle_cooldown = 60         # Frames until next idle action can trigger
        self._boredom_level = 0          # Increases over time, resets on action
        
        # Idle action data
        self._idle_look_dir = 0.0        # Look direction (-1 to 1, for "look_around")
        self._idle_scratch_side = 0      # Which side to scratch (0=left, 1=right)
        self._idle_toy = None            # Current toy for play action
        self._idle_toy_x = 0.0           # Toy position X
        self._idle_toy_y = 0.0           # Toy position Y
        self._idle_toy_bat = 0           # Toy batting animation frame
        
        # --- SYSTEM EVENT REACTION ---
        self._recent_window_change = False
        self._window_change_timer = 0
        self._cursor_near = False
        self._typing_detected = False
        self._typing_timer = 0
        
        # --- MOOD/EMOTION SYSTEM ---
        self._mood = 50.0           # 0 (angry) to 100 (ecstatic), based on focus history
        self._mood_target = 50.0    # Target mood for smooth transitions
        self._mood_indicator_timer = 0  # Cooldown for changing mood emoticon
        self._mood_emoticon = "😐"   # Current displayed emoticon
        
        # 12 FPS Animation Timer (~83ms interval) - only used for standalone mode
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
            if state != self.IDLE:
                self.is_happy = False
                self.is_waving = False
        self.update()

    def trigger_happy(self):
        """Trigger a happy reaction animation."""
        self.is_happy = True
        self.happy_timer = 30
        self.is_waving = True
        self.wave_timer = 20
        self._idle_action = None  # Cancel idle when happy
        self.update()

    # ----- IDLE ANIMATION SYSTEM -----
    def trigger_idle_action(self, action_name: str = None, look_dir: float = 0.0):
        """Trigger a specific idle animation. If action_name is None, picks one randomly."""
        # Don't override happy or non-idle states
        if self.is_happy or self.state != self.IDLE:
            return
        
        if action_name is None:
            # Weighted random pick - adjusted by mood
            weights = self._get_mood_idle_weights()
            total = sum(weights.values())
            r = random.randint(1, total)
            cumulative = 0
            for action, weight in weights.items():
                cumulative += weight
                if r <= cumulative:
                    action_name = action
                    break
            if action_name is None:
                action_name = random.choice(self.IDLE_ACTIONS)
        
        durations = {
            "blink": 8, "look_around": 15, "yawn": 22, 
            "stretch": 28, "scratch": 18, "play": 40
        }
        
        self._idle_action = action_name
        self._idle_action_frame = 0
        self._idle_action_duration = durations.get(action_name, 20)
        self._idle_look_dir = look_dir if action_name == "look_around" else random.uniform(-1, 1)
        self._idle_scratch_side = random.randint(0, 1)
        self._boredom_level = 0
        
        # Setup toy for play action
        if action_name == "play":
            toy_names = list(TOYS.keys())
            self._idle_toy = random.choice(toy_names)
            self._idle_toy_x = 90 + random.randint(-30, -10)
            self._idle_toy_y = 110
            self._idle_toy_bat = 0
        
        self.update()

    def trigger_window_change_reaction(self):
        """React to a window change event - look around curiously."""
        self._recent_window_change = True
        self._window_change_timer = 30
        dir = random.uniform(-0.8, 0.8)
        self.trigger_idle_action("look_around", look_dir=dir)

    def trigger_cursor_near(self):
        """React when cursor is near the pet."""
        self._cursor_near = True
        if self.state == self.IDLE and not self._idle_action:
            self.trigger_idle_action("play")
        self.update()

    def trigger_cursor_far(self):
        self._cursor_near = False
        self.update()

    def trigger_typing_detected(self):
        """Perk up when typing is detected."""
        self._typing_detected = True
        self._typing_timer = 40
        # Quick perky look around
        if self.state == self.IDLE and not self._idle_action:
            self.trigger_idle_action("look_around", look_dir=random.uniform(-0.3, 0.3))
        self.update()

    def update_animation(self):
        self.anim_frame = (self.anim_frame + 1) % 120
        
        # Update mood (smooth transition)
        self._update_mood()
        
        # Update happy/wave timers
        if self.is_happy and self.happy_timer > 0:
            self.happy_timer -= 1
            if self.happy_timer <= 0:
                self.is_happy = False
        if self.is_waving and self.wave_timer > 0:
            self.wave_timer -= 1
            if self.wave_timer <= 0:
                self.is_waving = False
        
        # Update typing/react timers
        if self._typing_detected and self._typing_timer > 0:
            self._typing_timer -= 1
            if self._typing_timer <= 0:
                self._typing_detected = False
        if self._window_change_timer > 0:
            self._window_change_timer -= 1
            if self._window_change_timer <= 0:
                self._recent_window_change = False
        
        # ----- IDLE ACTION STATE MACHINE -----
        if self.state == self.IDLE and not self.is_happy:
            if self._idle_action:
                # Currently performing an idle action
                self._idle_action_frame += 1
                
                # Update toy position during play
                if self._idle_action == "play":
                    self._update_play_action()
                
                # Check if action is done
                if self._idle_action_frame >= self._idle_action_duration:
                    self._idle_action = None
                    self._idle_action_frame = 0
                    self._idle_cooldown = random.randint(40, 100)
            else:
                # Not currently doing an action - decide if we should
                if self._idle_cooldown > 0:
                    self._idle_cooldown -= 1
                    # Increase boredom slowly
                    if self.anim_frame % 10 == 0:
                        self._boredom_level = min(self._boredom_level + 1, 100)
                
                # Trigger idle action based on cooldown + boredom
                should_trigger = self._idle_cooldown <= 0
                # Higher boredom = higher chance
                if not should_trigger and self._boredom_level > 50 and random.random() < 0.02:
                    should_trigger = True
                if not should_trigger and self._boredom_level > 80 and random.random() < 0.05:
                    should_trigger = True
                    
                if should_trigger:
                    self.trigger_idle_action()
        else:
            # Cancel idle actions when not in IDLE state
            if self._idle_action:
                self._idle_action = None
                self._idle_action_frame = 0
        
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

        # Sleep particles for IDLE state (only when not doing an idle action)
        if self.state == self.IDLE and not self._idle_action and self.anim_frame % 25 == 0:
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

    def _update_play_action(self):
        """Update the toy position and bat animation during play."""
        f = self._idle_action_frame
        if f < 8:
            # Toy drops in
            self._idle_toy_y = 80 + int(30 * (f / 8))
            self._idle_toy_x = 90 + int(20 * math.sin(f * 0.8))
        elif f < 14:
            # Pet looks at toy
            pass
        elif f < 22:
            # Batting motion (toy bounces)
            self._idle_toy_bat = f - 14
            bounce = abs(math.sin((f - 14) * 0.8))
            self._idle_toy_y = 110 - int(20 * bounce)
            self._idle_toy_x = 60 + int(25 * math.sin((f - 14) * 0.5))
        elif f < 30:
            # Toy settles
            self._idle_toy_y = 100 + int(10 * math.sin(f * 0.3))
        else:
            # Toy fades out
            pass

    def render(self, painter: QPainter, offset_x: int = 0, offset_y: int = 0):
        """
        Public render method for external use.
        Renders the pet onto an external QPainter at the given offset.
        This is the primary method used by PetWindow.
        """
        painter.save()
        painter.translate(offset_x, offset_y)
        
        palette = PALETTES.get(self.theme_name, PALETTES["Tokyo Night"])

        # Apply stretch/yawn idle offset (body elongates upward)
        idle_stretch_y = self._get_idle_stretch_offset()
        painter.translate(0, idle_stretch_y)

        # Apply jitter shake for CHAOS state
        shake_x, shake_y = 0, 0
        if self.state == self.CHAOS:
            shake_x = random.randint(-4, 4)
            shake_y = random.randint(-4, 4)
        painter.translate(shake_x, shake_y)

        # Apply look_around head tilt
        idle_tilt = self._get_idle_tilt()
        if idle_tilt != 0:
            painter.rotate(idle_tilt)

        # Draw shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 45)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(45, 142, 90, 16))

        # Reset rotation for shadow
        if idle_tilt != 0:
            painter.rotate(-idle_tilt)

        # Render active character species
        if "DRAGON" in self.character_type:
            self.draw_dragon(painter, palette)
        elif "BOT" in self.character_type or "MECHA" in self.character_type:
            self.draw_mecha_bot(painter, palette)
        elif "PANDA" in self.character_type:
            self.draw_panda(painter, palette)
        elif "BLOB" in self.character_type or "SLIME" in self.character_type:
            self.draw_slime(painter, palette)
        else:
            self.draw_cyber_cat(painter, palette)

        # Draw Overlay Icons & Particles
        self.draw_effects(painter, palette)
        
        # Apply mood color tint (semi-transparent overlay for emotional feel)
        mood = self._mood
        if self.state == self.IDLE and not self.is_happy:
            tint_r, tint_g, tint_b = self._get_mood_tint()
            if tint_r != 0 or tint_g != 0 or tint_b != 0:
                alpha = min(abs(tint_r) + abs(tint_g) + abs(tint_b), 40)
                overlay = QColor(
                    max(0, min(255, 128 + tint_r)),
                    max(0, min(255, 128 + tint_g)),
                    max(0, min(255, 128 + tint_b)),
                    alpha
                )
                painter.setBrush(QBrush(overlay))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRect(40, 55, 100, 85), 22, 22)
        
        painter.restore()

    # ----- IDLE ANIMATION DRAWING HELPERS -----
    def _get_idle_stretch_offset(self) -> int:
        """Return vertical offset for stretch/yawn idle actions."""
        if self._idle_action in ("stretch", "yawn"):
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            if progress < 0.25:
                return int(-6 * (progress / 0.25))
            elif progress < 0.6:
                return -6
            else:
                return int(-6 * (1 - (progress - 0.6) / 0.4))
        return 0

    def _get_idle_tilt(self) -> float:
        """Return rotation degrees for head tilt during look_around."""
        if self._idle_action == "look_around":
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            if progress < 0.3:
                return self._idle_look_dir * 6 * (progress / 0.3)
            elif progress < 0.7:
                return self._idle_look_dir * 6
            else:
                return self._idle_look_dir * 6 * (1 - (progress - 0.7) / 0.3)
        if self._cursor_near:
            return 1.5 * math.sin(self.anim_frame * 0.15)
        return 0.0

    def _get_idle_pupil_offset(self) -> tuple:
        """Return (dx, dy) for pupil position during idle actions."""
        if self._idle_action == "look_around":
            # Eyes track in the look direction
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            if progress < 0.3:
                t = progress / 0.3
            elif progress < 0.7:
                t = 1.0
            else:
                t = 1 - (progress - 0.7) / 0.3
            return (int(self._idle_look_dir * 4 * t), 0)
        if self._cursor_near:
            return (int(2 * math.sin(self.anim_frame * 0.1)), int(-1 + math.sin(self.anim_frame * 0.08)))
        return (0, 0)

    def _should_idle_blink(self) -> bool:
        """Return True if eyes should be drawn as closed for blink.
        Eyes close quickly, stay closed briefly, then open quickly.
        """
        if self._idle_action == "blink":
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            # Eyes closed during middle 40% of blink duration only
            # First 30%: eyes open (start closing), 30%-70%: closed, 70%-100%: opening back
            return 0.3 <= progress <= 0.7
        return False

    # ----- MOOD/EMOTION SYSTEM -----
    def set_mood(self, mood_value: float):
        """
        Set pet's mood based on focus history.
        mood_value: 0 (very distracted/angry) to 100 (very focused/ecstatic)
        """
        self._mood_target = max(0.0, min(100.0, mood_value))
    
    def _update_mood(self):
        """Smoothly transition mood toward target."""
        diff = self._mood_target - self._mood
        if abs(diff) > 0.5:
            self._mood += diff * 0.05  # Smooth lerp
        else:
            self._mood = self._mood_target
        
        # Update mood emoticon periodically
        self._mood_indicator_timer += 1
        if self._mood_indicator_timer > 30:
            self._mood_indicator_timer = 0
            mood = self._mood
            if mood >= 85:
                self._mood_emoticon = "😄"
            elif mood >= 65:
                self._mood_emoticon = "🙂"
            elif mood >= 40:
                self._mood_emoticon = "😐"
            elif mood >= 20:
                self._mood_emoticon = "😒"
            else:
                self._mood_emoticon = "😤"
    
    def _get_mood_tint(self) -> tuple:
        """Return (red_boost, green_boost, blue_boost) color modifier based on mood.
        Happy (high focus): warm, bright
        Grumpy (low focus): cool, dark, red-tinted
        """
        m = self._mood
        if m >= 80:
            # Ecstatic: warm golden glow
            return (30, 20, -10)
        elif m >= 60:
            # Happy: slight warm boost
            return (15, 10, 0)
        elif m >= 40:
            # Neutral: no change
            return (0, 0, 0)
        elif m >= 20:
            # Grumpy: slightly blue/cool
            return (-5, -10, 15)
        else:
            # Angry: red tint
            return (20, -15, -15)
    
    def _get_mood_idle_weights(self) -> dict:
        """Get idle action weights adjusted by mood."""
        m = self._mood
        base = {"blink": 40, "look_around": 25, "yawn": 12, "stretch": 10, "scratch": 8, "play": 5}
        
        if m >= 70:
            # Happy: more play, less scratch/yawn
            base["play"] = 20
            base["scratch"] = 3
            base["yawn"] = 5
            base["blink"] = 30
        elif m >= 40:
            # Neutral: default
            pass
        else:
            # Grumpy/Angry: more scratch, yawn, less play
            base["play"] = 2
            base["scratch"] = 20
            base["yawn"] = 20
            base["blink"] = 25
            base["stretch"] = 18
        
        return base

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.render(painter)
        
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
        
        # Idle pupil offsets for look_around
        idle_pupil_x, idle_pupil_y = self._get_idle_pupil_offset()
        should_idle_blink = self._should_idle_blink()
        
        if st == self.IDLE or should_idle_blink:
            # Blinking closed eye arcs
            painter.setPen(QPen(c_eye if st == self.IDLE else c_dark, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(x + 18, eye_y - 6, 18, 14), 180 * 16, 180 * 16)
            painter.drawArc(QRect(x + 54, eye_y - 6, 18, 14), 180 * 16, 180 * 16)
        else:
            # Glowing open cyber eyes
            painter.setBrush(QBrush(c_eye))
            painter.setPen(QPen(c_dark, 1.5))
            painter.drawEllipse(QRect(x + 18, eye_y - 6, 18, 18))
            painter.drawEllipse(QRect(x + 54, eye_y - 6, 18, 18))

            # Vertical Cat Pupil with idle offset
            painter.setBrush(QBrush(c_dark))
            pupil_w = 4 if st == self.CHAOS else 6
            painter.drawRoundedRect(QRect(x + 27 - pupil_w//2 + idle_pupil_x, eye_y - 2 + idle_pupil_y, pupil_w, 10), 2, 2)
            painter.drawRoundedRect(QRect(x + 63 - pupil_w//2 + idle_pupil_x, eye_y - 2 + idle_pupil_y, pupil_w, 10), 2, 2)

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
        idle_pupil_x, idle_pupil_y = self._get_idle_pupil_offset()
        should_idle_blink = self._should_idle_blink()
        
        if st == self.IDLE or should_idle_blink:
            painter.setPen(QPen(c_eye if st == self.IDLE else c_dark, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(x + 20, eye_y - 4, 16, 12), 180 * 16, 180 * 16)
            painter.drawArc(QRect(x + 54, eye_y - 4, 16, 12), 180 * 16, 180 * 16)
        else:
            painter.setBrush(QBrush(c_eye))
            painter.setPen(QPen(c_dark, 1.5))
            painter.drawEllipse(QRect(x + 20, eye_y - 6, 18, 18))
            painter.drawEllipse(QRect(x + 52, eye_y - 6, 18, 18))
            painter.setBrush(QBrush(c_dark))
            painter.drawEllipse(QRect(x + 27 + idle_pupil_x, eye_y - 1 + idle_pupil_y, 5, 8))
            painter.drawEllipse(QRect(x + 59 + idle_pupil_x, eye_y - 1 + idle_pupil_y, 5, 8))

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

    # ----------------- 4. THE CUTE PANDA BEAR -----------------
    def draw_panda(self, painter: QPainter, palette: dict):
        f = self.anim_frame
        st = self.state

        c_primary = QColor(palette["accent"] if st == self.CHAOS and (f % 4 < 2) else palette["primary"])
        c_secondary = QColor(palette["secondary"])
        c_dark = QColor(palette["dark"])
        c_eye = QColor("#ff0055" if st == self.CHAOS else palette["eye"])

        breath_y = int(3 * math.sin(f * 0.2)) if st == self.IDLE else int(4 * math.sin(f * 0.5))
        bounce_y = int(6 * math.sin(f * 0.8)) if st in [self.ATTENTION, self.CHAOS] else 0
        if st == self.CHAOS:
            bounce_y = int(10 * math.sin(f * 0.7))
        x, y, w, h = 45, 65 + breath_y - bounce_y, 90, 75

        # Fluffy Panda Ears (outer dark circles)
        ear_size = 24
        ear_offset = 8
        painter.setBrush(QBrush(QColor("#1a1a20")))
        painter.setPen(QPen(c_secondary, 1.5))
        painter.drawEllipse(QRect(x - ear_offset, y - ear_offset, ear_size, ear_size))
        painter.drawEllipse(QRect(x + w - ear_size + ear_offset, y - ear_offset, ear_size, ear_size))

        # Inner ear (smaller pink/light circles)
        inner_ear = int(ear_size * 0.55)
        inner_off = ear_offset + (ear_size - inner_ear) // 2
        painter.setBrush(QBrush(QColor(255, 180, 190, 150)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(x - ear_offset + inner_off, y - ear_offset + inner_off, inner_ear, inner_ear))
        painter.drawEllipse(QRect(x + w - ear_size + ear_offset + inner_off, y - ear_offset + inner_off, inner_ear, inner_ear))

        # Panda Body (Rounded Rectangle - chubby)
        painter.setBrush(QBrush(QColor("#f5f5f0")))
        painter.setPen(QPen(QColor(180, 180, 175), 1.5))
        painter.drawRoundedRect(QRect(x, y, w, h), 30, 30)

        # Dark shoulder patches / arms
        painter.setBrush(QBrush(QColor("#1a1a20")))
        painter.setPen(Qt.PenStyle.NoPen)
        # Left arm
        arm_path_l = QPainterPath()
        arm_path_l.moveTo(x + 5, y + int(h * 0.3))
        arm_path_l.quadTo(x - 15, y + int(h * 0.5), x + 2, y + int(h * 0.85))
        arm_path_l.quadTo(x + 10, y + int(h * 0.9), x + 18, y + int(h * 0.7))
        arm_path_l.closeSubpath()
        painter.drawPath(arm_path_l)
        # Right arm
        arm_path_r = QPainterPath()
        arm_path_r.moveTo(x + w - 5, y + int(h * 0.3))
        arm_path_r.quadTo(x + w + 15, y + int(h * 0.5), x + w - 2, y + int(h * 0.85))
        arm_path_r.quadTo(x + w - 10, y + int(h * 0.9), x + w - 18, y + int(h * 0.7))
        arm_path_r.closeSubpath()
        painter.drawPath(arm_path_r)

        # Little feet
        painter.drawRoundedRect(QRect(x + 15, y + h - 8, 20, 14), 6, 6)
        painter.drawRoundedRect(QRect(x + w - 35, y + h - 8, 20, 14), 6, 6)

        # Panda Eye Patches (dark circles around eyes)
        patch_w = int(w * 0.35)
        patch_h = int(h * 0.25)
        patch_y = y + int(h * 0.22)
        painter.setBrush(QBrush(QColor("#2a2a30")))
        painter.setPen(QPen(QColor("#1a1a20"), 1))
        painter.drawEllipse(QRect(x + int(w * 0.08), patch_y, patch_w, patch_h))
        painter.drawEllipse(QRect(x + w - int(w * 0.08) - patch_w, patch_y, patch_w, patch_h))

        # Eyes
        eye_y = patch_y + patch_h // 2
        eye_center_l = x + int(w * 0.25)
        eye_center_r = x + int(w * 0.75)
        
        idle_pupil_x, idle_pupil_y = self._get_idle_pupil_offset()
        should_idle_blink = self._should_idle_blink()

        if self.is_happy:
            # Happy squint eyes (^ ^)
            painter.setPen(QPen(QColor("#1a1a20"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(eye_center_l - 7, eye_y - 3, 14, 10), 0 * 16, -180 * 16)
            painter.drawArc(QRect(eye_center_r - 7, eye_y - 3, 14, 10), 0 * 16, -180 * 16)
        elif st == self.IDLE or should_idle_blink:
            # Sleepy arcs (or idle blink)
            painter.setPen(QPen(QColor("#1a1a20"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(eye_center_l - 7, eye_y - 4, 14, 10), 180 * 16, 180 * 16)
            painter.drawArc(QRect(eye_center_r - 7, eye_y - 4, 14, 10), 180 * 16, 180 * 16)
        else:
            # Cute round eyes with idle pupil offset
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#1a1a20"), 1.5))
            painter.drawEllipse(QRect(eye_center_l - 6, eye_y - 6, 12, 12))
            painter.drawEllipse(QRect(eye_center_r - 6, eye_y - 6, 12, 12))
            # Pupils
            pupil_off_x = idle_pupil_x
            pupil_off_y = idle_pupil_y
            if st == self.CHAOS:
                pupil_off_x += int(3 * math.sin(f * 0.8))
                pupil_off_y += int(2 * math.cos(f * 0.6))
            painter.setBrush(QBrush(c_primary))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(eye_center_l - 3 + pupil_off_x, eye_y - 3 + pupil_off_y, 6, 6))
            painter.drawEllipse(QRect(eye_center_r - 3 + pupil_off_x, eye_y - 3 + pupil_off_y, 6, 6))
            # Highlights
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QRect(eye_center_l - 1 + pupil_off_x, eye_y - 4 + pupil_off_y, 2, 2))
            painter.drawEllipse(QRect(eye_center_r - 1 + pupil_off_x, eye_y - 4 + pupil_off_y, 2, 2))

        # Cute Nose & Mouth
        nose_y = y + int(h * 0.52)
        painter.setBrush(QBrush(QColor("#1a1a20")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(90 - 3, nose_y - 3, 6, 5))

        # Mouth
        painter.setPen(QPen(QColor("#1a1a20"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if st == self.IDLE:
            # Small 'o' mouth
            painter.drawEllipse(QRect(90 - 3, nose_y + 4, 6, 4))
        elif self.is_happy:
            # Big smile
            painter.drawArc(QRect(90 - 8, nose_y + 2, 16, 10), 0 * 16, -180 * 16)
        elif st == self.CHAOS:
            # Open scared mouth
            painter.drawArc(QRect(90 - 6, nose_y + 2, 12, 10), 0 * 16, -180 * 16)
            painter.setBrush(QBrush(c_dark))
            painter.drawEllipse(QRect(90 - 4, nose_y + 4, 8, 6))
        else:
            # Cute smile
            painter.drawArc(QRect(90 - 7, nose_y + 2, 14, 8), 180 * 16, 180 * 16)

        # Red cheeks
        if st > self.IDLE or self.is_happy:
            painter.setBrush(QBrush(QColor(255, 130, 130, 80)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x + int(w * 0.05), eye_y + 4, 10, 8))
            painter.drawEllipse(QRect(x + w - int(w * 0.05) - 10, eye_y + 4, 10, 8))

        # Bamboo treat if happy
        if self.is_happy:
            painter.save()
            # Bamboo stick
            px = x + w + 4
            py = y + int(h * 0.1)
            painter.setPen(QPen(QColor("#4a7c3f"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(px + 2, py + 25, px + 2, py + 2)
            # Bamboo leaves
            painter.setBrush(QBrush(QColor("#5a9c4f")))
            painter.setPen(Qt.PenStyle.NoPen)
            leaf = QPainterPath()
            leaf.moveTo(px + 2, py + 2)
            leaf.quadTo(px + 12, py - 4, px + 8, py + 4)
            leaf.closeSubpath()
            painter.drawPath(leaf)
            leaf2 = QPainterPath()
            leaf2.moveTo(px + 2, py + 8)
            leaf2.quadTo(px - 8, py + 2, px - 4, py + 10)
            leaf2.closeSubpath()
            painter.drawPath(leaf2)
            painter.restore()

    # ----------------- 5. THE CLASSIC BLOB SLIME -----------------
    def draw_slime(self, painter: QPainter, palette: dict):
        f = self.anim_frame
        st = self.state

        c_primary = QColor(palette["accent"] if st == self.CHAOS and (f % 4 < 2) else palette["primary"])
        c_secondary = QColor(palette["secondary"])
        c_dark = QColor(palette["dark"])
        c_eye = QColor("#ff0055" if st == self.CHAOS else palette["eye"])

        # Squishy slime deformation
        squish = 0.04 * math.sin(f * 0.3)
        stretch = 0.06 * math.sin(f * 0.2 + 1.0)
        breath_y = int(3 * math.sin(f * 0.2)) if st == self.IDLE else int(4 * math.sin(f * 0.5))
        bounce_y = 0
        if st in [self.ALERT, self.ATTENTION]:
            bounce_y = int(4 * math.sin(f * 0.5))
        elif st == self.CHAOS:
            bounce_y = int(8 * math.sin(f * 0.7))

        w = int(90 * (1.0 + stretch))
        h = int(75 * (1.0 - squish))
        x = 90 - w // 2
        y = 72 - h + breath_y - bounce_y

        # Gooey shadow/drop
        shadow_y = y + h + 2
        painter.setBrush(QBrush(QColor(c_dark.red(), c_dark.green(), c_dark.blue(), 35)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(x + 6, shadow_y, w - 12, 16))

        # Slime body - squishy rounded rect with gradient
        grad = QRadialGradient(90, y + h * 0.3, int(w * 0.7))
        grad.setColorAt(0.0, c_primary.lighter(130))
        grad.setColorAt(0.6, c_primary)
        grad.setColorAt(1.0, c_primary.darker(120))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(c_dark, 1.5))
        painter.drawRoundedRect(QRect(x, y, w, h), int(w * 0.35), int(h * 0.35))

        # Gooey drip at bottom
        drip_count = 3 if st < self.CHAOS else 5
        for i in range(drip_count):
            drip_x = x + int(w * (0.2 + i * 0.15))
            drip_h = int(6 + 4 * math.sin(f * 0.5 + i * 2.0))
            painter.setBrush(QBrush(c_primary))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(drip_x - 3, y + h - 2, 7, drip_h + 4))

        # Little slime horns/antennae
        painter.setBrush(QBrush(c_secondary))
        painter.setPen(Qt.PenStyle.NoPen)
        # Left antenna
        ant_l = QPainterPath()
        ant_l.moveTo(x + int(w * 0.25), y + 2)
        ant_l.quadTo(x + int(w * 0.2), y - 18, x + int(w * 0.15), y - 14)
        painter.drawPath(ant_l)
        painter.drawEllipse(QRect(x + int(w * 0.1), y - 18, 8, 8))
        # Right antenna
        ant_r = QPainterPath()
        ant_r.moveTo(x + int(w * 0.75), y + 2)
        ant_r.quadTo(x + int(w * 0.8), y - 18, x + int(w * 0.85), y - 14)
        painter.drawPath(ant_r)
        painter.drawEllipse(QRect(x + int(w * 0.78), y - 18, 8, 8))

        # Antenna glow
        glow = QColor(c_eye)
        glow.setAlpha(60)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QRect(x + int(w * 0.08), y - 20, 12, 12))
        painter.drawEllipse(QRect(x + int(w * 0.76), y - 20, 12, 12))

        # Eyes
        eye_y = y + int(h * 0.35)
        eye_spacing = int(w * 0.22)
        eye_center_l = x + eye_spacing
        eye_center_r = x + w - eye_spacing
        eye_size = 11
        
        idle_pupil_x, idle_pupil_y = self._get_idle_pupil_offset()
        should_idle_blink = self._should_idle_blink()

        # Eye whites
        if st == self.IDLE or should_idle_blink:
            # Sleepy closed eyes or idle blink
            painter.setPen(QPen(c_dark if should_idle_blink else c_eye, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(eye_center_l - 6, eye_y - 3, 12, 8), 180 * 16, 180 * 16)
            painter.drawArc(QRect(eye_center_r - 6, eye_y - 3, 12, 8), 180 * 16, 180 * 16)
        else:
            # Big cute eyes
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(c_dark, 1.5))
            painter.drawEllipse(QRect(eye_center_l - eye_size // 2, eye_y - eye_size // 2, eye_size, eye_size))
            painter.drawEllipse(QRect(eye_center_r - eye_size // 2, eye_y - eye_size // 2, eye_size, eye_size))
            # Pupils with idle offset
            pupil_off_x, pupil_off_y = idle_pupil_x, idle_pupil_y
            if st == self.ATTENTION or st == self.CHAOS:
                pupil_off_x += int(2 * math.sin(f * 0.5 + 1))
                pupil_off_y += int(2 * math.cos(f * 0.5))
            painter.setBrush(QBrush(c_eye))
            painter.setPen(Qt.PenStyle.NoPen)
            pupil_s = 5
            painter.drawEllipse(QRect(eye_center_l - pupil_s // 2 + pupil_off_x, eye_y - pupil_s // 2 + pupil_off_y, pupil_s, pupil_s))
            painter.drawEllipse(QRect(eye_center_r - pupil_s // 2 + pupil_off_x, eye_y - pupil_s // 2 + pupil_off_y, pupil_s, pupil_s))
            # Highlights
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QRect(eye_center_l - 1 + pupil_off_x, eye_y - 3 + pupil_off_y, 2, 2))
            painter.drawEllipse(QRect(eye_center_r - 1 + pupil_off_x, eye_y - 3 + pupil_off_y, 2, 2))

        # Blush cheeks
        if st > self.IDLE:
            painter.setBrush(QBrush(QColor(255, 130, 130, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x + int(w * 0.02), eye_y - 1, 10, 8))
            painter.drawEllipse(QRect(x + w - int(w * 0.02) - 10, eye_y - 1, 10, 8))

        # Mouth
        mouth_y = y + int(h * 0.58)
        painter.setPen(QPen(c_dark, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if st == self.IDLE:
            painter.drawEllipse(QRect(90 - 3, mouth_y - 2, 6, 5))
        elif self.is_happy:
            painter.drawArc(QRect(90 - 8, mouth_y - 2, 16, 10), 0 * 16, -180 * 16)
        elif st == self.CHAOS:
            path_m = QPainterPath()
            path_m.moveTo(90 - 7, mouth_y)
            path_m.quadTo(90 - 3, mouth_y - 4, 90, mouth_y)
            path_m.quadTo(90 + 3, mouth_y + 4, 90 + 7, mouth_y)
            painter.drawPath(path_m)
        else:
            painter.drawArc(QRect(90 - 6, mouth_y - 2, 12, 8), 180 * 16, 180 * 16)

    # ----------------- OVERLAY EFFECTS -----------------
    def draw_effects(self, painter: QPainter, palette: dict):
        st = self.state
        f = self.anim_frame
        
        # Zzz Particles for IDLE (only when not doing idle actions)
        if st == self.IDLE and not self._idle_action:
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

        # Happy reaction - heart particles
        if self.is_happy and f % 4 == 0:
            heart_x = 90 + random.randint(-20, 20)
            heart_y = 50 + random.randint(-15, 5)
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#ff6b81"))
            painter.drawText(heart_x, heart_y, "♥")
            painter.setPen(QColor("#ffb8c6"))
            painter.drawText(heart_x - 8, heart_y + 2, "♥")

        # Wave effect when waving
        if self.is_waving:
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            wave_x = 135
            wave_y = 55 + int(3 * math.sin(f * 0.8))
            painter.setPen(QColor(palette["text"]))
            painter.drawText(wave_x, wave_y, "👋")

        # ----- IDLE ACTION EFFECTS -----
        # Toy rendering for play action
        if self._idle_action == "play" and self._idle_toy:
            toy = TOYS[self._idle_toy]
            toy_x = int(self._idle_toy_x)
            toy_y = int(self._idle_toy_y)
            
            # Toy shadow
            painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(toy_x - 6, 130, 12, 6))
            
            # Toy body
            if toy["color"]:
                painter.setBrush(QBrush(QColor(toy["color"])))
                painter.setPen(QPen(QColor(toy["color"]).darker(130), 1))
                painter.drawEllipse(QRect(toy_x - toy["size"]//2, toy_y - toy["size"]//2, toy["size"], toy["size"]))
                # Glow/highlight
                painter.setBrush(QBrush(QColor(toy["color"]).lighter(160)))
                painter.drawEllipse(QRect(toy_x - 2, toy_y - 2, 4, 4))
            else:
                painter.setFont(QFont("Segoe UI", toy["size"]))
                painter.drawText(toy_x - toy["size"]//2, toy_y + toy["size"]//2, toy["emoji"])
            
            # Batting motion lines
            if self._idle_toy_bat > 0:
                painter.setPen(QPen(QColor(palette["text"]), 1.5))
                for i in range(3):
                    lx = 80 + int(20 * (i / 3))
                    ly = 85 + int(10 * math.sin(self._idle_toy_bat * 0.5 + i))
                    painter.drawLine(lx, ly, lx - 4, ly + 2)
        
        # Scratch motion lines
        if self._idle_action == "scratch":
            painter.setPen(QPen(QColor(palette["text"]), 1, Qt.PenStyle.DotLine))
            side = self._idle_scratch_side
            sx = 40 if side == 0 else 140
            sy = 70 + int(5 * math.sin(self._idle_action_frame * 0.8))
            painter.drawLine(sx - 5, sy - 5, sx + 5, sy + 5)
            painter.drawLine(sx - 3, sy - 7, sx + 7, sy + 3)
        
        # Yawn text effect
        if self._idle_action == "yawn":
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            if 0.25 < progress < 0.75:
                painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                painter.setPen(QColor(palette["accent"]))
                painter.drawText(QRect(55, 40, 70, 20), Qt.AlignmentFlag.AlignCenter, "O")

        # Stretch stars (little sparkles during stretch)
        if self._idle_action == "stretch":
            progress = self._idle_action_frame / max(self._idle_action_duration, 1)
            if 0.2 < progress < 0.6 and f % 6 == 0:
                painter.setFont(QFont("Segoe UI", 10))
                painter.setPen(QColor("#ffd700"))
                sx = 90 + random.randint(-25, 25)
                sy = 35 + random.randint(-10, 10)
                painter.drawText(sx, sy, "✦")
        
        # Cursor near effect - little attention ripple
        if self._cursor_near and self.state == self.IDLE:
            ripple_alpha = int(40 + 30 * math.sin(f * 0.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(palette["eye"]), 1.5))
            painter.drawEllipse(QPoint(60, 130), 15, 8)
            painter.drawEllipse(QPoint(120, 130), 15, 8)

        # ----- MOOD EMOTICON -----
        # Show mood indicator above pet's head (only in IDLE state when not doing an action)
        if st == self.IDLE and not self._idle_action and not self.is_happy:
            emoticon = self._mood_emoticon
            if emoticon != "😐":  # Don't show for neutral mood
                # Subtle floating animation
                float_y = int(2 * math.sin(f * 0.08))
                painter.setFont(QFont("Segoe UI", 11))
                painter.setPen(QColor(palette["text"]))
                painter.drawText(QRect(60, 28 + float_y, 60, 20), Qt.AlignmentFlag.AlignCenter, emoticon)
        
        # Mood color border (subtle glow ring when mood is extreme)
        if st == self.IDLE:
            m = self._mood
            if m >= 85 or m <= 15:
                glow_alpha = int(20 + 15 * math.sin(f * 0.1))
                r, g, b = 0, 0, 0
                if m >= 85:
                    r, g, b = 255, 215, 0  # Gold for happy
                else:
                    r, g, b = 255, 50, 50  # Red for angry
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(r, g, b, glow_alpha), 2))
                painter.drawRoundedRect(QRect(10, 10, 160, 160), 18, 18)

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
        self.char_combo.addItems(["Cyber Cat", "Terminal Dragon", "Mecha Bot", "Cute Panda", "Classic Slime"])
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
        chars = ["CAT", "DRAGON", "BOT", "PANDA", "BLOB"]
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
