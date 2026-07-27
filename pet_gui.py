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
    Supports multiple pet species (Blob, Cat, Robo, Panda, Custom Image/Colors).
    Moves towards the cursor (Level 1), knocks on the screen (Level 2), 
    and wiggles/shakes violently (Level 3).
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
        self.pet_type = "BLOB"  # "BLOB", "CAT", "ROBO", "PANDA", "CUSTOM"
        self.theme_name = "Tokyo Night"
        self.custom_primary = "#a18cd1"
        self.custom_secondary = "#fbc2eb"
        self.custom_pixmap = None
        self.custom_image_path = ""

        # Procedural sprite renderer delegate
        self.procedural_pet = ProceduralPetWidget(self.pet_type, self.theme_name, self)
        self.procedural_pet.hide()
        
        # Sleep particles (Zzz) for Level 0
        self.sleep_particles = []
        
        # Dialog speech bubble for Level 1
        self.bubble_text = ""
        self.bubble_timer = 0
        self.speech_phrases = [
            "Get back to work!",
            "Distraction spotted!",
            "Hey, look here!",
            "Focused? Sure?",
            "Eyes on the code!"
        ]
        
        # Knocking state variables for Level 2
        self.is_knocking = False
        self.knock_phase = 0.0
        self.last_knock_time = 0
        
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
        self.timer.start(30) # ~33 FPS

    def set_pet_style(self, pet_type: str = "BLOB", custom_image_path: str = "", custom_primary: str = "#a18cd1", custom_secondary: str = "#fbc2eb", theme_name: str = "Tokyo Night"):
        self.pet_type = pet_type.upper()
        self.custom_image_path = custom_image_path
        self.custom_primary = custom_primary
        self.custom_secondary = custom_secondary
        self.theme_name = theme_name
        self.custom_pixmap = None

        if hasattr(self, 'procedural_pet') and self.procedural_pet:
            self.procedural_pet.set_character(self.pet_type)
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
            if hasattr(self, 'procedural_pet') and self.procedural_pet:
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


    def update_animation(self):
        self.anim_tick += 1
        
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
                    self.screen_overlay.add_ripple(pet_center)
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
            if move_dist < 5:  # Click without dragging
                self.pet_clicked.emit()
            event.accept()


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Breathing effect coordinates scaling
        scale_y = 1.0 + 0.05 * math.sin(self.anim_tick * 0.1) if self.level == 0 else 1.0 + 0.06 * math.sin(self.anim_tick * 0.25)
        scale_x = 1.0 - 0.02 * math.sin(self.anim_tick * 0.1) if self.level == 0 else 1.0 - 0.03 * math.sin(self.anim_tick * 0.25)
        
        # Pet dimensions
        w = int(90 * scale_x)
        h = int(90 * scale_y)
        
        # Shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(90 - int(w/2), 140 - 10, w, 15))
        
        # Body coordinates
        x = 90 - w // 2
        y = 135 - h
        
        # Delegate to ProceduralPetWidget for procedural species (CAT, DRAGON, BOT/MECHA)
        if self.pet_type in ["CAT", "CYBER CAT", "DRAGON", "TERMINAL DRAGON", "BOT", "MECHA", "MECHA BOT"]:
            self.procedural_pet.render(painter)
            self.draw_overlay_effects(painter, x, y, w, h)
            return

        # Handle CUSTOM image rendering
        if self.pet_type == "CUSTOM" and self.custom_pixmap:
            scaled_pix = self.custom_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            px = 90 - scaled_pix.width() // 2
            py = 135 - scaled_pix.height()
            painter.drawPixmap(px, py, scaled_pix)
            self.draw_overlay_effects(painter, x, y, w, h)
            return


        # Radial Color Gradient setup
        gradient = QRadialGradient(90, 135 - h//2, int(w/2))
        
        if self.pet_type == "CUSTOM":
            c1 = QColor(self.custom_primary)
            c2 = QColor(self.custom_secondary)
            if not c1.isValid(): c1 = QColor("#a18cd1")
            if not c2.isValid(): c2 = QColor("#fbc2eb")
        elif self.level == 0:  # Sleeping
            c1, c2 = QColor("#a18cd1"), QColor("#fbc2eb")
        elif self.level == 1:  # Waking
            c1, c2 = QColor("#8fd3f4"), QColor("#84fab0")
        elif self.level == 2:  # Warning
            c1, c2 = QColor("#f6d365"), QColor("#fda085")
        else:  # Total Zone-Out
            c1, c2 = QColor("#ff0844"), QColor("#ffb199")

        gradient.setColorAt(0.0, c1)
        gradient.setColorAt(1.0, c2)

        # Render Specific Pet Species Body & Ears
        if self.pet_type == "ROBO":
            # Cyber Robot Chassis
            painter.setBrush(QBrush(QColor("#2a2e3d") if self.level < 2 else c1))
            painter.setPen(QPen(QColor("#84fab0" if self.level < 2 else "#ff0844"), 2))
            painter.drawRoundedRect(QRect(x, y, w, h), 16, 16)
            
            # Antenna
            painter.drawLine(90, y, 90, y - 14)
            antenna_color = QColor("#00ffcc") if (self.anim_tick // 10) % 2 == 0 else QColor("#ff0055")
            painter.setBrush(QBrush(antenna_color))
            painter.drawEllipse(85, y - 20, 10, 10)

        elif self.pet_type == "PANDA":
            # Panda Ears (Black circles)
            painter.setBrush(QBrush(QColor("#202025")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x - 4, y - 6, 28, 28))
            painter.drawEllipse(QRect(x + w - 24, y - 6, 28, 28))

            # Panda Head (White / Cream Body)
            painter.setBrush(QBrush(QColor("#f5f5f7")))
            painter.setPen(QPen(QColor(180, 180, 180), 1.5))
            painter.drawEllipse(QRect(x, y, w, h))

        elif self.pet_type == "CAT":
            # Cat Body
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x, y, w, h))

            # Sharp Cat Ears
            painter.setBrush(QBrush(c1))
            # Left ear
            cat_l = QPainterPath()
            cat_l.moveTo(x + int(w * 0.15), y + int(h * 0.2))
            cat_l.lineTo(x - 8, y - 16)
            cat_l.lineTo(x + int(w * 0.4), y + int(h * 0.05))
            cat_l.closeSubpath()
            painter.drawPath(cat_l)
            
            # Inner pink ear
            painter.setBrush(QBrush(QColor(255, 170, 190)))
            cat_l_inner = QPainterPath()
            cat_l_inner.moveTo(x + int(w * 0.18), y + int(h * 0.18))
            cat_l_inner.lineTo(x - 2, y - 8)
            cat_l_inner.lineTo(x + int(w * 0.35), y + int(h * 0.08))
            cat_l_inner.closeSubpath()
            painter.drawPath(cat_l_inner)

            # Right ear
            painter.setBrush(QBrush(c1))
            cat_r = QPainterPath()
            cat_r.moveTo(x + int(w * 0.85), y + int(h * 0.2))
            cat_r.lineTo(x + w + 8, y - 16)
            cat_r.lineTo(x + int(w * 0.6), y + int(h * 0.05))
            cat_r.closeSubpath()
            painter.drawPath(cat_r)
            
            # Right Inner pink ear
            painter.setBrush(QBrush(QColor(255, 170, 190)))
            cat_r_inner = QPainterPath()
            cat_r_inner.moveTo(x + int(w * 0.82), y + int(h * 0.18))
            cat_r_inner.lineTo(x + w + 2, y - 8)
            cat_r_inner.lineTo(x + int(w * 0.65), y + int(h * 0.08))
            cat_r_inner.closeSubpath()
            painter.drawPath(cat_r_inner)

        else:
            # BLOB / Default Slime
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x, y, w, h))
            
            # Blob ears
            painter.setBrush(QBrush(c1))
            path_l = QPainterPath()
            path_l.moveTo(x + w * 0.2, y + h * 0.1)
            path_l.lineTo(x - 5, y - 12)
            path_l.lineTo(x + w * 0.05, y + h * 0.3)
            path_l.closeSubpath()
            painter.drawPath(path_l)
            
            path_r = QPainterPath()
            path_r.moveTo(x + w * 0.8, y + h * 0.1)
            path_r.lineTo(x + w + 5, y - 12)
            path_r.lineTo(x + w * 0.95, y + h * 0.3)
            path_r.closeSubpath()
            painter.drawPath(path_r)


        # Draw Face Details (Eyes, Mouth, Whiskers, Accessories)
        eye_y = y + int(h * 0.45)
        eye_w = int(w * 0.16)

        # Panda Black Eye Patches
        if self.pet_type == "PANDA":
            painter.setBrush(QBrush(QColor("#202025")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x + int(w*0.14), eye_y - eye_w//2 - 2, int(eye_w*1.5), int(eye_w*1.5)))
            painter.drawEllipse(QRect(x + int(w*0.58), eye_y - eye_w//2 - 2, int(eye_w*1.5), int(eye_w*1.5)))

        # Robo Visor Overlay
        if self.pet_type == "ROBO":
            painter.setBrush(QBrush(QColor("#10121a")))
            painter.setPen(QPen(QColor("#00ffcc"), 1))
            painter.drawRoundedRect(QRect(x + int(w*0.12), eye_y - 12, int(w*0.76), 24), 6, 6)

        # Eyes Drawing
        if self.level == 0:
            # Sleeping curves
            painter.setPen(QPen(QColor("#00ffcc" if self.pet_type == "ROBO" else "#404050"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRect(x + int(w*0.22), eye_y - eye_w//2, eye_w, eye_w), 180 * 16, 180 * 16)
            painter.drawArc(QRect(x + int(w*0.62), eye_y - eye_w//2, eye_w, eye_w), 180 * 16, 180 * 16)
        else:
            # Open eyes
            eye_color = QColor("#00ffcc") if self.pet_type == "ROBO" else Qt.GlobalColor.white
            painter.setBrush(QBrush(eye_color))
            painter.setPen(QPen(QColor(80, 80, 80, 100), 1))
            painter.drawEllipse(QRect(x + int(w*0.20), eye_y - eye_w//2, eye_w, eye_w))
            painter.drawEllipse(QRect(x + int(w*0.64), eye_y - eye_w//2, eye_w, eye_w))
            
            # Pupils
            pupil_color = QColor("#ff0055") if self.pet_type == "ROBO" else Qt.GlobalColor.black
            painter.setBrush(QBrush(pupil_color))
            pupil_w = int(eye_w * 0.5)
            
            p_offset_x, p_offset_y = 0, 0
            if self.level == 1:
                cursor_pos = QCursor.pos()
                pet_global = self.mapToGlobal(QPoint(90, 90))
                dx = cursor_pos.x() - pet_global.x()
                dy = cursor_pos.y() - pet_global.y()
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 0:
                    p_offset_x = int(3 * dx / dist)
                    p_offset_y = int(3 * dy / dist)
            elif self.level == 2:
                p_offset_x = int(1.5 * math.sin(self.anim_tick * 0.5))
                p_offset_y = int(1.5 * math.cos(self.anim_tick * 0.5))
            elif self.level == 3:
                p_offset_x = int(3 * math.sin(self.anim_tick * 0.8))
                p_offset_y = int(3 * math.cos(self.anim_tick * 0.8))
                
            painter.drawEllipse(QRect(x + int(w*0.20) + eye_w//2 - pupil_w//2 + p_offset_x, 
                                      eye_y - pupil_w//2 + p_offset_y, pupil_w, pupil_w))
            painter.drawEllipse(QRect(x + int(w*0.64) + eye_w//2 - pupil_w//2 + p_offset_x, 
                                      eye_y - pupil_w//2 + p_offset_y, pupil_w, pupil_w))
            
            # Highlights
            if self.pet_type != "ROBO":
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRect(x + int(w*0.20) + eye_w//2 - 1 + p_offset_x, eye_y - 3 + p_offset_y, 2, 2))
                painter.drawEllipse(QRect(x + int(w*0.64) + eye_w//2 - 1 + p_offset_x, eye_y - 3 + p_offset_y, 2, 2))

        # Cat Whiskers
        if self.pet_type == "CAT":
            painter.setPen(QPen(QColor(60, 60, 60, 180), 1.5))
            # Left Whiskers
            painter.drawLine(x + 4, eye_y + 4, x - 12, eye_y)
            painter.drawLine(x + 4, eye_y + 8, x - 14, eye_y + 8)
            # Right Whiskers
            painter.drawLine(x + w - 4, eye_y + 4, x + w + 12, eye_y)
            painter.drawLine(x + w - 4, eye_y + 8, x + w + 14, eye_y + 8)

        # Mouth
        mouth_y = y + int(h * 0.65)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        if self.level == 0:
            painter.setPen(QPen(QColor(100, 100, 150, 150), 2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 80)))
            painter.drawEllipse(QRect(90 - 4, mouth_y - 3, 8, 6))
        elif self.level == 1:
            painter.setPen(QPen(QColor(60, 60, 60, 200), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(QRect(90 - 7, mouth_y - 4, 14, 8), 180 * 16, 180 * 16)
        elif self.level == 2:
            painter.setPen(QPen(QColor(60, 60, 60, 200), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(90 - 6, mouth_y, 90 + 6, mouth_y)
        else:
            painter.setPen(QPen(QColor(60, 60, 60, 200), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            path_m = QPainterPath()
            path_m.moveTo(90 - 8, mouth_y)
            path_m.quadTo(90 - 4, mouth_y - 3, 90, mouth_y)
            path_m.quadTo(90 + 4, mouth_y + 3, 90 + 8, mouth_y)
            painter.drawPath(path_m)

        # Cheeks
        if self.level > 0 and self.pet_type != "ROBO":
            painter.setBrush(QBrush(QColor(255, 120, 120, 90)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(x + int(w*0.12), eye_y + 2, 7, 4))
            painter.drawEllipse(QRect(x + int(w*0.78), eye_y + 2, 7, 4))

        self.draw_overlay_effects(painter, x, y, w, h)

    def draw_overlay_effects(self, painter, x, y, w, h):
        """Draws sleep particles, dialogue speech bubbles, and knocking paws."""
        # Level 0 Zzz particles
        if self.level == 0:
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            for p in self.sleep_particles:
                painter.setPen(QColor(180, 180, 255, int(p['alpha'])))
                painter.drawText(int(p['x']), int(p['y']), p['text'])

        # Level 1 Dialogue speech bubble
        if self.level == 1 and self.bubble_text:
            bubble_w = 130
            bubble_h = 30
            bx = 90 - bubble_w // 2
            by = 8
            
            painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
            painter.setPen(QPen(QColor(180, 180, 180, 200), 1))
            painter.drawRoundedRect(bx, by, bubble_w, bubble_h, 8, 8)
            
            pointer = QPolygonF([
                QPointF(90.0, float(by + bubble_h + 5)),
                QPointF(85.0, float(by + bubble_h)),
                QPointF(95.0, float(by + bubble_h))
            ])

            painter.drawPolygon(pointer)
            
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor(50, 50, 50))
            painter.drawText(QRect(bx, by, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, self.bubble_text)

        # Level 2 Knocking Arm/Paw Overlay
        if self.level == 2 and self.is_knocking:
            paw_y_offset = int(12 * math.sin(self.knock_phase))
            paw_grad = QLinearGradient(90, 135, 90, 135 - paw_y_offset)
            paw_grad.setColorAt(0, QColor("#84fab0"))
            paw_grad.setColorAt(1, QColor("#8fd3f4"))
            
            painter.setBrush(QBrush(paw_grad))
            painter.setPen(QPen(QColor(0,0,0,50), 1))
            painter.drawEllipse(QRect(90 - 12, 135 - h - paw_y_offset, 24, 24))

class ScreenOverlay(QWidget):
    """
    Full screen visual effects overlay:
    - Click-through transparent window.
    - Level 2: Glass ripple effects when the pet knocks on the screen.
    - Level 3: Slow flashing red overlay (Visual Blitz).
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
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(30) # ~33 FPS

    def set_level(self, level: int):
        self.level = level
        if level != 3:
            self.flash_alpha = 0.0

    def add_ripple(self, global_pos: QPoint):
        local_pos = self.mapFromGlobal(global_pos)
        self.ripples.append({
            'x': local_pos.x(),
            'y': local_pos.y(),
            'radius': 5.0,
            'max_radius': 80.0,
            'alpha': 230.0
        })

    def update_overlay(self):
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
        
        if self.level == 3 and self.flash_alpha > 0.0:
            painter.fillRect(self.rect(), QColor(230, 20, 20, int(self.flash_alpha * 255)))
            
        for rip in self.ripples:
            alpha = int(rip['alpha'])
            r = int(rip['radius'])
            rx = int(rip['x'])
            ry = int(rip['y'])
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(100, 200, 255, alpha), 2))
            painter.drawEllipse(QPoint(rx, ry), r, r)
            painter.setPen(QPen(QColor(150, 220, 255, int(alpha * 0.6)), 1))
            painter.drawEllipse(QPoint(rx, ry), int(r * 0.75), int(r * 0.75))
            
            if r > 20:
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

