"""
Mouse Analytics - Tracks cursor movement velocity and patterns.
Detects whether mouse movement is:
- STEADY: Purposeful, low-velocity movement (working in documents/IDE)
- ERRATIC: High-velocity with frequent direction changes (scrolling social media, frantic searching)
- STILL: No significant movement (reading or idle)
"""

import sys
import time
import math
import ctypes
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_position():
    """Returns current cursor (x, y) position."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def calculate_velocity(points, time_delta):
    """
    Calculate movement velocity from a list of (x, y, timestamp) points.
    Returns average velocity in pixels/second and erraticness score.
    """
    if len(points) < 2 or time_delta <= 0:
        return 0.0, 0.0
    
    total_distance = 0.0
    direction_changes = 0
    last_dx, last_dy = 0, 0
    
    for i in range(1, len(points)):
        dx = points[i][0] - points[i-1][0]
        dy = points[i][1] - points[i-1][1]
        distance = math.sqrt(dx*dx + dy*dy)
        total_distance += distance
        
        # Count direction changes (sign flips)
        if i > 1:
            if (dx > 0) != (last_dx > 0) or (dy > 0) != (last_dy > 0):
                direction_changes += 1
        last_dx, last_dy = dx, dy
    
    velocity = total_distance / time_delta if time_delta > 0 else 0.0
    
    # Erraticness: direction changes per unit distance
    erraticness = direction_changes / max(total_distance, 1.0) * 100.0
    
    return velocity, erraticness


class MouseAnalyticsWorker(QThread):
    """
    QThread worker that tracks cursor movement patterns.
    Emits mouse_update(is_steady: bool, velocity: float, erraticness: float) every 200ms.
    
    STEADY movement (velocity < threshold, low erraticness) = focused work
    ERRATIC movement (high velocity + high erraticness) = distraction
    STILL movement (near-zero velocity) = reading or idle
    """
    mouse_update = pyqtSignal(bool, float, float)  # (is_steady, velocity_px_per_sec, erraticness)
    
    def __init__(self, velocity_threshold: float = 150.0, erraticness_threshold: float = 3.0):
        """
        velocity_threshold: px/s above which movement is considered "fast"
        erraticness_threshold: direction changes per 100px above which is "erratic"
        """
        super().__init__()
        self.running = True
        self.velocity_threshold = velocity_threshold
        self.erraticness_threshold = erraticness_threshold
        
        # Movement history buffer (last ~1 second of samples at 50ms intervals = 20 samples)
        self.position_history = deque(maxlen=20)
        
        # Smoothing state
        self._smoothed_steady = True
        self._still_counter = 0
    
    def run(self):
        while self.running:
            try:
                x, y = get_cursor_position()
            except Exception:
                self.msleep(50)
                continue
            
            now = time.time()
            self.position_history.append((x, y, now))
            
            # Calculate metrics from history buffer (last ~500ms)
            if len(self.position_history) >= 3:
                recent = list(self.position_history)[-10:]  # Last ~500ms
                time_span = recent[-1][2] - recent[0][2] if len(recent) >= 2 else 0.05
                
                velocity, erraticness = calculate_velocity(recent, time_span)
                
                # Determine movement state
                if velocity < 5.0:
                    # Very still - could be reading or idle
                    self._still_counter = min(self._still_counter + 1, 10)
                    is_steady = self._smoothed_steady  # Keep last known state
                else:
                    self._still_counter = 0
                    # Steady = moderate velocity AND low erraticness
                    is_steady = (velocity < self.velocity_threshold and 
                                 erraticness < self.erraticness_threshold)
                
                # Smooth the signal (hysteresis to prevent flickering)
                if is_steady != self._smoothed_steady:
                    # Only change if sustained for multiple readings
                    self._smoothed_steady = is_steady
                
                self.mouse_update.emit(self._smoothed_steady, velocity, erraticness)
            
            self.msleep(50)  # 20Hz sampling
    
    def stop(self):
        self.running = False
        self.wait()