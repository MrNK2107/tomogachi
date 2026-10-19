import os
import math
import random
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QSize, pyqtSignal


from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, 
                           QLinearGradient, QCursor, QGuiApplication, QPainterPath, 
                           QPolygonF, QPixmap)
import audio_guard
from pet_sprites import ProceduralPetWidget


class PetWindow(QWidget):
    """
    Transparent, frameless overlay window containing the animated desktop pet.
    All pet rendering is delegated to ProceduralPetWidget from pet_sprites.py.
    Supports Custom Image (CUSTOM) in addition to all procedural pets.
    """
    pet_clicked = pyqtSignal()

    def __init__(self, screen_overlay=None):
        super().__init__()
        self.screen_overlay = screen_overlay
        
        # Transparent, stays on top, tool window (hidden from taskbar)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Fixed size for the pet bounding box
        self.setFixedSize(180, 180)
        
        # Physics / Movement parameters
        self.level = 0
        self.anim_tick = 0
        
        # Pet customization fields
        self.pet_type = "BLOB"  # "BLOB", "CAT", "DRAGON", "BOT", "PANDA", "CUSTOM"
        self.theme_name = "Tokyo Night"
        self.custom_primary = "#a18cd1"
        self.custom_secondary = "#fbc2eb"
        self.custom_pixmap = None
        self.custom_image_path = ""

        # Procedural sprite renderer delegate - handles all pet drawing
        self.procedural_pet = ProceduralPetWidget(self._map_pet_type(self.pet_type), self.theme_name, self)
        self.procedural_pet.hide()
        
        # Sleep particles (Zzz) for Level 0
        self.sleep_particles = []
        
        # Dialog speech bubble for Level 1
        self.bubble_text = ""
        self.bubble_timer = 0
        self.speech_phrases = [
            "Get back to work!",
            "Focus up! 💪",
            "Distraction spotted!",
            "Hey, look here! 👀",
            "Eyes on the code! ",
            "Don't zone out! ✨"
        ]
        
        # Knocking state variables for Level 2
        self.is_knocking = False
        self.knock_phase = 0.0
        self.last_knock_time = 0
        
        # Pet interaction state
        self.is_hovered = False
        self.pet_was_petted = False
        self.pet_reaction_timer = 0
        
        # Cursor proximity detection
        self._last_cursor_near = False
        self._cursor_proximity_cooldown = 0
        
        # Target position on the screen
        screen_geo = QGuiApplication.primaryScreen().geometry()
        self.screen_width = screen_geo.width()
        self.screen_height = screen_geo.height()
        
        # Start at bottom-right corner
        self.target_x = self.screen_width - 200
        self.target_y = self.screen_height - 230
        self.move(self.target_x, self.target_y)
        
        # Smooth animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)  # ~33 FPS

    def _map_pet_type(self, pet_type: str) -> str:
        """Map pet_gui pet types to pet_sprites character types."""
        mapping = {
            "BLOB": "BLOB",
            "CAT": "CAT",
            "CYBER CAT": "CAT",
            "DRAGON": "DRAGON",
            "TERMINAL DRAGON": "DRAGON",
            "BOT": "BOT",
            "MECHA": "BOT",
            "MECHA BOT": "BOT",
            "ROBO": "BOT",
            "PANDA": "PANDA",
            "CUSTOM": "CAT",  # Fallback - CUSTOM uses image rendering
        }
        return mapping.get(pet_type.upper(), "BLOB")

    def set_pet_style(self, pet_type: str = "BLOB", custom_image_path: str = "", custom_primary: str = "#a18cd1", custom_secondary: str = "#fbc2eb", theme_name: str = "Tokyo Night"):
        self.pet_type = pet_type.upper()
        self.custom_image_path = custom_image_path
        self.custom_primary = custom_primary
        self.custom_secondary = custom_secondary
        self.theme_name = theme_name
        self.custom_pixmap = None

        sprite_type = self._map_pet_type(self.pet_type)
        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.set_character(sprite_type)
            self.procedural_pet.set_theme(self.theme_name)

        if self.pet_type == "CUSTOM" and custom_image_path and os.path.exists(custom_image_path):
            pix = QPixmap(custom_image_path)
            if not pix.isNull():
                self.custom_pixmap = pix
        self.update()

    def set_level(self, level: int):
        if self.level != level:
            self.level = level
            self.anim_tick = 0
            if hasattr(self, 'procedural_pet') and self.procedural_pet and self.pet_type != "CUSTOM":
                self.procedural_pet.set_state(level)
            if level == 0:
                self.sleep_particles = []
                self.bubble_text = ""
            elif level == 1:
                self.bubble_text = random.choice(self.speech_phrases)
                self.bubble_timer = 0
            elif level == 2:
                self.bubble_text = ""
                self.is_knocking = False
            elif level == 3:
                self.bubble_text = ""

    def trigger_pet_reaction(self):
        """Trigger a happy reaction when pet is clicked/petted."""
        self.pet_was_petted = True
        self.pet_reaction_timer = 40
        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.trigger_happy()
        if self.screen_overlay:
            pet_center = self.mapToGlobal(QPoint(90, 90))
            self.screen_overlay.add_ripple(pet_center, color=QColor("#ff6b81"), max_radius=40)
        self.update()

    def show_custom_bubble(self, text: str, duration_ticks: int = 120):
        """Display an immediate custom speech bubble."""
        self.bubble_text = text
        self.force_bubble = True
        self.bubble_timer = 0
        self.bubble_max_duration = duration_ticks
        self.update()

    def trigger_alarm_animation(self):
        """Trigger an aggressive attention-grabbing alert animation."""
        self.is_knocking = True
        self.knock_phase = 0.0
        self.show_custom_bubble("🚨 WAKE UP! ALARM! 🚨", 150)
        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.set_state(3)
        if self.screen_overlay:
            pet_center = self.mapToGlobal(QPoint(90, 90))
            self.screen_overlay.add_ripple(pet_center, color=QColor("#ff0844"), max_radius=120)
        self.move(self.x(), max(0, self.y() - 25))
        self.update()

    def trigger_feed_animation(self):
        """Trigger fed animation with sparkles & food bubble."""
        self.pet_was_petted = True
        self.pet_reaction_timer = 60
        self.show_custom_bubble("🥩 Yum! Focus boosted! ✨", 120)
        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.trigger_happy()
        if self.screen_overlay:
            pet_center = self.mapToGlobal(QPoint(90, 90))
            self.screen_overlay.add_ripple(pet_center, color=QColor("#00f5d4"), max_radius=60)
        self.update()

    def trigger_poke_animation(self):
        """Trigger poke reaction."""
        self.show_custom_bubble("Ouch! Go code! 😾", 100)
        self.move(self.x() + random.choice([-20, 20]), max(0, self.y() - 15))
        self.update()

    def set_mood(self, mood_value: float):
        """Set the pet's mood based on focus history (0=angry, 100=ecstatic)."""
        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.set_mood(mood_value)

    def notify_window_changed(self):
        """Called when the active window changes - pet looks around curiously."""
        if hasattr(self, 'procedural_pet') and self.procedural_pet and self.level == 0:
            self.procedural_pet.trigger_window_change_reaction()

    def notify_typing_detected(self):
        """Called when typing is detected - pet perks up."""
        if hasattr(self, 'procedural_pet') and self.procedural_pet and self.level == 0:
            self.procedural_pet.trigger_typing_detected()

    def update_animation(self):
        self.anim_tick += 1
        
        # Update pet reaction timer
        if self.pet_was_petted:
            self.pet_reaction_timer -= 1
            if self.pet_reaction_timer <= 0:
                self.pet_was_petted = False

        # Update custom speech bubble timer
        if getattr(self, 'force_bubble', False):
            self.bubble_timer += 1
            if self.bubble_timer > getattr(self, 'bubble_max_duration', 120):
                self.force_bubble = False
                self.bubble_text = ""
                self.bubble_timer = 0
        
        # Cursor proximity detection (only at IDLE level)
        if self.level == 0 and hasattr(self, 'procedural_pet') and self.procedural_pet:
            self._cursor_proximity_cooldown = max(0, self._cursor_proximity_cooldown - 1)
            cursor_pos = QCursor.pos()
            dx = cursor_pos.x() - (self.x() + 90)
            dy = cursor_pos.y() - (self.y() + 90)
            dist = math.sqrt(dx*dx + dy*dy)
            
            is_near = dist < 120
            if is_near and not self._last_cursor_near and self._cursor_proximity_cooldown == 0:
                self._last_cursor_near = True
                self.procedural_pet.trigger_cursor_near()
                self._cursor_proximity_cooldown = 30
            elif not is_near and self._last_cursor_near:
                self._last_cursor_near = False
                self.procedural_pet.trigger_cursor_far()
        
        # Get current position
        curr_x = self.x()
        curr_y = self.y()
        
        # Screen bounds constraint
        screen_geo = QGuiApplication.primaryScreen().geometry()
        self.screen_width = screen_geo.width()
        self.screen_height = screen_geo.height()

        # Update target position based on focus level
        if self.level == 0:
            # Level 0 (Sleeping): Stay in bottom-right corner
            self.target_x = self.screen_width - 200
            self.target_y = self.screen_height - 230
            
            # Slow movement to corner
            dx = self.target_x - curr_x
            dy = self.target_y - curr_y
            self.move(int(curr_x + dx * 0.1), int(curr_y + dy * 0.1))
            
            # Manage Zzz sleep particles
            if self.anim_tick % 40 == 0:
                self.sleep_particles.append({
                    'x': 95.0,
                    'y': 90.0,
                    'alpha': 255.0,
                    'text': random.choice(['z', 'Z', 'Zz'])
                })
            
            for p in list(self.sleep_particles):
                p['y'] -= 0.8
                p['x'] += 0.4 * math.sin(p['y'] * 0.1)
                p['alpha'] -= 2.0
                if p['alpha'] <= 0:
                    self.sleep_particles.remove(p)

        elif self.level == 1:
            # Level 1 (Slight Distraction): Walk towards active cursor, keeping offset
            cursor_pos = QCursor.pos()
            self.target_x = cursor_pos.x() - 130
            self.target_y = cursor_pos.y() - 130
            
            # Ensure pet stays on screen bounds
            self.target_x = max(0, min(self.screen_width - 180, self.target_x))
            self.target_y = max(0, min(self.screen_height - 180, self.target_y))
            
            # Smooth interpolation walking
            dx = self.target_x - curr_x
            dy = self.target_y - curr_y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 5:
                speed = 3.5
                self.move(int(curr_x + dx * speed / dist), int(curr_y + dy * speed / dist))
            
            # Cycle speech bubble text
            self.bubble_timer += 1
            if self.bubble_timer > 100:
                self.bubble_text = random.choice(self.speech_phrases)
                self.bubble_timer = 0

        elif self.level == 2:
            # Level 2 (Sustained Distraction): Sit near screen center and knock on glass
            self.target_x = self.screen_width // 2 - 90
            self.target_y = self.screen_height // 2 - 90
            
            dx = self.target_x - curr_x
            dy = self.target_y - curr_y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 5:
                self.move(int(curr_x + dx * 6.0 / dist), int(curr_y + dy * 6.0 / dist))
            
            # Execute glass knocking
            if self.anim_tick % 50 == 0:
                self.is_knocking = True
                self.knock_phase = 0.0
                if self.screen_overlay:
                    pet_center = self.mapToGlobal(QPoint(90, 90))
                    self.screen_overlay.add_ripple(pet_center, color=QColor("#4facfe"), max_radius=80)
                audio_guard.play_alert_tone(frequency=660.0, duration=0.15, volume=0.2)
                
            if self.is_knocking:
                self.knock_phase += 0.2
                if self.knock_phase >= math.pi:
                    self.is_knocking = False
                    self.knock_phase = 0.0

        elif self.level == 3:
            # Level 3 (Total Zone-Out): Shake violently around cursor position
            cursor_pos = QCursor.pos()
            self.target_x = cursor_pos.x() - 90
            self.target_y = cursor_pos.y() - 90
            
            self.target_x = max(0, min(self.screen_width - 180, self.target_x))
            self.target_y = max(0, min(self.screen_height - 180, self.target_y))
            
            dx = self.target_x - curr_x
            dy = self.target_y - curr_y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 5:
                self.move(int(curr_x + dx * 10.0 / dist), int(curr_y + dy * 10.0 / dist))
            
            shake_x = random.randint(-7, 7)
            shake_y = random.randint(-7, 7)
            self.move(self.x() + shake_x, self.y() + shake_y)
            
            if self.anim_tick % 30 == 0:
                audio_guard.play_alert_tone(frequency=1000.0, duration=0.1, volume=0.25)
                
        self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.click_start_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, 'click_start_pos'):
            move_dist = (event.globalPosition().toPoint() - self.click_start_pos).manhattanLength()
            if move_dist < 5:  # Click without dragging = pet/interact
                self.trigger_pet_reaction()
                self.pet_clicked.emit()
            event.accept()

    def draw_breathing_body(self, painter):
        """Draw the breathing/shadow effect behind the pet."""
        scale_y = 1.0 + 0.05 * math.sin(self.anim_tick * 0.1) if self.level == 0 else 1.0 + 0.06 * math.sin(self.anim_tick * 0.25)
        scale_x = 1.0 - 0.02 * math.sin(self.anim_tick * 0.1) if self.level == 0 else 1.0 - 0.03 * math.sin(self.anim_tick * 0.25)
        
        w = int(90 * scale_x)
        
        # Shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(90 - int(w/2), 140 - 10, w, 15))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw breathing shadow
        self.draw_breathing_body(painter)
        
        # Handle CUSTOM image rendering
        if self.pet_type == "CUSTOM" and self.custom_pixmap:
            scale_y = 1.0 + 0.05 * math.sin(self.anim_tick * 0.1)
            scale_x = 1.0 - 0.02 * math.sin(self.anim_tick * 0.1)
            w = int(90 * scale_x)
            h = int(90 * scale_y)
            scaled_pix = self.custom_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            px = 90 - scaled_pix.width() // 2
            py = 135 - scaled_pix.height()
            painter.drawPixmap(px, py, scaled_pix)
        else:
            # Delegate all procedural rendering to ProceduralPetWidget
            self.procedural_pet.render(painter)
        
        # Draw overlay effects on top
        self.draw_overlay_effects(painter)

    def draw_overlay_effects(self, painter):
        """Draws sleep particles, dialogue speech bubbles, knocking paws, and hover glow."""
        # Hover glow ring
        if self.is_hovered:
            alpha = int(60 + 40 * math.sin(self.anim_tick * 0.15))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 2))
            painter.drawEllipse(QRect(8, 8, 164, 164))
        
        # Level 0 Zzz particles
        if self.level == 0:
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            for p in self.sleep_particles:
                painter.setPen(QColor(180, 180, 255, int(p['alpha'])))
                painter.drawText(int(p['x']), int(p['y']), p['text'])

        # Dialogue speech bubble (renders on Level 1 or when custom bubble triggered)
        if (self.level == 1 or getattr(self, 'force_bubble', False)) and self.bubble_text:
            bubble_w = 140
            bubble_h = 32
            bx = 90 - bubble_w // 2
            by = 4
            
            # Bubble shadow
            painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bx + 1, by + 2, bubble_w, bubble_h, 8, 8)
            
            # Bubble body with gradient
            painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
            painter.setPen(QPen(QColor(200, 200, 220, 180), 1))
            painter.drawRoundedRect(bx, by, bubble_w, bubble_h, 8, 8)
            
            # Pointer triangle
            pointer = QPolygonF([
                QPointF(90.0, float(by + bubble_h + 6)),
                QPointF(83.0, float(by + bubble_h)),
                QPointF(97.0, float(by + bubble_h))
            ])
            painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
            painter.setPen(QPen(QColor(200, 200, 220, 180), 1))
            painter.drawPolygon(pointer)
            
            # Bubble text
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor(40, 40, 60))
            painter.drawText(QRect(bx, by, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, self.bubble_text)
            
            # Emoji sparkles
            if self.anim_tick % 30 < 15:
                painter.setFont(QFont("Segoe UI", 14))
                painter.setPen(QColor(255, 200, 50, 100))
                painter.drawText(bx + bubble_w - 2, by - 4, "✨")

        # Level 2 Knocking Arm/Paw Overlay
        if self.level == 2 and self.is_knocking:
            paw_y_offset = int(12 * math.sin(self.knock_phase))
            paw_grad = QLinearGradient(90, 135, 90, 135 - paw_y_offset)
            paw_grad.setColorAt(0, QColor("#84fab0"))
            paw_grad.setColorAt(1, QColor("#8fd3f4"))
            
            painter.setBrush(QBrush(paw_grad))
            painter.setPen(QPen(QColor(0, 0, 0, 50), 1.5))
            painter.drawEllipse(QRect(90 - 14, 60 - paw_y_offset, 28, 22))

class ScreenOverlay(QWidget):
    """
    Full screen visual effects overlay:
    - Click-through transparent window.
    - Level 2: Glass ripple effects when the pet knocks on the screen.
    - Level 3: Slow flashing red overlay (Visual Blitz) with vignette.
    - Pet interaction: Heart/color ripples when pet is petted.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        screen_geo = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)
        
        self.level = 0
        self.flash_alpha = 0.0
        self.flash_dir = 1
        self.ripples = []
        self.anim_tick = 0
        
        # Vignette effect for Level 3
        self.vignette_alpha = 0.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(30)  # ~33 FPS

    def set_level(self, level: int):
        if self.level != level:
            self.level = level
            self.anim_tick = 0
            if level != 3:
                self.flash_alpha = 0.0
                self.vignette_alpha = 0.0
            elif level == 3:
                self.vignette_alpha = 0.4

    def add_ripple(self, global_pos: QPoint, color: QColor = None, max_radius: int = 80):
        if color is None:
            color = QColor("#4facfe")
        local_pos = self.mapFromGlobal(global_pos)
        self.ripples.append({
            'x': local_pos.x(),
            'y': local_pos.y(),
            'radius': 5.0,
            'max_radius': float(max_radius),
            'alpha': 230.0,
            'color': color,
            'crack': max_radius > 50  # Only show cracks for larger ripples
        })

    def update_overlay(self):
        self.anim_tick += 1
        
        if self.level == 3:
            self.flash_alpha += self.flash_dir * 0.008
            if self.flash_alpha >= 0.16:
                self.flash_alpha = 0.16
                self.flash_dir = -1
            elif self.flash_alpha <= 0.03:
                self.flash_alpha = 0.03
                self.flash_dir = 1
                
        for rip in list(self.ripples):
            rip['radius'] += 3.5
            rip['alpha'] -= 8.0
            if rip['alpha'] <= 0 or rip['radius'] >= rip['max_radius']:
                self.ripples.remove(rip)
                
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Level 3: Red flash + vignette
        if self.level == 3 and self.flash_alpha > 0.0:
            # Red flash overlay
            painter.fillRect(self.rect(), QColor(230, 20, 20, int(self.flash_alpha * 255)))
            
            # Dark vignette edges
            if self.vignette_alpha > 0:
                w, h = self.width(), self.height()
                # Corner vignettes
                vg = QRadialGradient(w/2, h/2, max(w, h) * 0.6)
                vg.setColorAt(0.0, QColor(0, 0, 0, 0))
                vg.setColorAt(0.7, QColor(0, 0, 0, 0))
                vg.setColorAt(1.0, QColor(0, 0, 0, int(200 * self.vignette_alpha)))
                painter.fillRect(self.rect(), QBrush(vg))
            
        # Level 2: Warning border pulse
        if self.level == 2:
            border_alpha = int(20 + 15 * math.sin(self.anim_tick * 0.15))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 200, 50, border_alpha), 4))
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
            
        # Draw all active ripples
        for rip in self.ripples:
            alpha = int(rip['alpha'])
            r = int(rip['radius'])
            rx = int(rip['x'])
            ry = int(rip['y'])
            color = rip['color']
            
            # Outer ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), alpha), 2))
            painter.drawEllipse(QPoint(rx, ry), r, r)
            
            # Inner ring
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(alpha * 0.6)), 1))
            painter.drawEllipse(QPoint(rx, ry), int(r * 0.75), int(r * 0.75))
            
            # Crack-style lines for knock ripples
            if rip['crack'] and r > 20:
                painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.8)), 1.5))
                num_cracks = 6
                for i in range(num_cracks):
                    angle = (i * 2 * math.pi / num_cracks) + (rx * 0.01)
                    x1 = rx + int((r - 10) * math.cos(angle))
                    y1 = ry + int((r - 10) * math.sin(angle))
                    x2 = rx + int((r + 15) * math.cos(angle + 0.1))
                    y2 = ry + int((r + 15) * math.sin(angle + 0.1))
                    painter.drawLine(x1, y1, x2, y2)

class FakePopup(QWidget):
    """
    Custom draggable glassmorphic dialogue warnings spawned in Level 3.
    """
    acknowledged = pyqtSignal()

    def __init__(self, index: int = 0):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.setFixedSize(300, 140)
        self.drag_pos = QPoint()
        
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(22, 22, 29, 215);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background-color: transparent;
                color: #ffffff;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff0844, stop:1 #ffb199);
                color: white;
                font-family: 'Segoe UI', Arial;
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff3366, stop:1 #ffc2b3);
            }
            QPushButton:pressed {
                background: #e6003c;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("""
            QWidget#TitleBar {
                background-color: rgba(255, 255, 255, 12);
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 25);
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        
        title_lbl = QLabel("SYSTEM FOCUS ALERT")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: rgba(255, 255, 255, 190);")
        tb_layout.addWidget(title_lbl)
        
        main_layout.addWidget(title_bar)
        
        body_widget = QWidget()
        body_widget.setStyleSheet("border: none; background: transparent;")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(15, 12, 15, 12)
        body_layout.setSpacing(10)
        
        messages = [
            "Procrastination alert! Get back to coding.",
            "Warning: Brain activity zapping off course.",
            "Are you still paying attention? Focus!",
            "Extreme zoning out detected! Clear this popup.",
            "Visual Blitz Mode is ENGAGED. Stay focused!"
        ]
        
        msg_lbl = QLabel(messages[index % len(messages)])
        msg_lbl.setFont(QFont("Segoe UI", 10))
        msg_lbl.setWordWrap(True)
        body_layout.addWidget(msg_lbl)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ack_btn = QPushButton("Acknowledge")
        ack_btn.clicked.connect(self.on_ack_clicked)
        btn_layout.addWidget(ack_btn)
        
        body_layout.addLayout(btn_layout)
        main_layout.addWidget(body_widget)
        
        self.setLayout(main_layout)

    def on_ack_clicked(self):
        self.acknowledged.emit()
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

