class IntensityEngine:
    """
    State machine keeping track of a Distraction Score (0.0 to 100.0) 
    and mapping it to four distinct behavioral intensity levels.
    
    Fuses 7 sensors into a single focus score:
    - Vision/Camera (head pose, eye tracking)
    - Keyboard/Mouse Activity (system idle time)
    - Microphone Voice Activity (speaking in calls)
    - Active Window Context (productivity app classification)
    - Mouse Movement Analytics (steady vs erratic)
    - Clipboard Activity (copy/paste frequency)
    - Scroll Activity (rapid scrolling detection)
    """
    def __init__(self):
        self.distraction_score = 0.0

    def reset(self):
        """Resets the distraction score to 0.0."""
        self.distraction_score = 0.0

    def update_fused(self, 
                     is_vision_focused: bool = False, 
                     is_input_active: bool = False, 
                     is_mic_active: bool = False,
                     app_context: str = "NEUTRAL",
                     is_mouse_steady: bool = True,
                     is_clipboard_active: bool = False,
                     is_agent_active: bool = False,
                     dt: float = 0.1) -> float:
        """
        Multimodal Fused Focus Calculation with 8 sensors:
        
        Focus signals (any = focused):
        - Typing/Clicking (is_input_active=True)
        - Voice/Meeting Speaking (is_mic_active=True)
        - Vision Camera Focus (is_vision_focused=True)
        - Clipboard usage (is_clipboard_active=True)
        - Background AI Agent Working (is_agent_active=True)
        
        Distraction signals:
        - App context is DISTRACTING (overrides input/clipboard)
        - Mouse movement is erratic (not steady)
        
        Neutral signals:
        - App context is PRODUCTIVE (boosts focus recovery)
        - Mouse movement is steady (neutral to positive)
        - App context is NEUTRAL (no effect)
        """
        # Start with core sensors + AI agent active signal
        core_focused = is_input_active or is_mic_active or is_vision_focused or is_agent_active
        
        # Enhance with new sensors
        clipboard_focused = is_clipboard_active and not is_input_active
        
        # Determine if app context overrides
        is_distracting_app = (app_context == "DISTRACTING")
        is_productive_app = (app_context == "PRODUCTIVE")
        
        # Mouse: erratic movement in a distracting app is a strong distraction signal
        mouse_distracted = not is_mouse_steady and is_distracting_app
        
        # Final fusion logic (weighted)
        if is_distracting_app and not core_focused:
            # In a distracting app AND not actively working = definitely distracted
            is_focused = False
            decay_rate = 25.0
        elif is_productive_app:
            # In a productive app = more forgiving
            is_focused = core_focused or clipboard_focused
            decay_rate = 18.0
        elif mouse_distracted:
            is_focused = False
            decay_rate = 20.0
        elif core_focused:
            is_focused = True
            decay_rate = 20.0
        else:
            is_focused = clipboard_focused
            decay_rate = 15.0

        if is_focused:
            self.distraction_score = max(0.0, self.distraction_score - decay_rate * dt)
        else:
            self.distraction_score = min(100.0, self.distraction_score + 15.0 * dt)
            
        return self.distraction_score

    def heal_focus(self, amount: float = 20.0):
        """Immediately reduces distraction score (called when placement quiz is solved)."""
        self.distraction_score = max(0.0, self.distraction_score - amount)

    def penalize_focus(self, amount: float = 15.0):
        """Immediately increases distraction score (called on incorrect placement quiz)."""
        self.distraction_score = min(100.0, self.distraction_score + amount)

    def update(self, is_focused: bool, dt: float) -> float:
        """Backward-compatible update method."""
        return self.update_fused(is_vision_focused=is_focused, is_input_active=False, is_mic_active=False, dt=dt)

    def get_level(self) -> int:
        """
        Maps distraction score to 4 state levels:
        - Level 0 (0-20): Focused.
        - Level 1 (21-50): Slight Distraction.
        - Level 2 (51-80): Sustained Distraction.
        - Level 3 (81-100): Total Zone-Out / Visual Blitz.
        """
        score = self.distraction_score
        if score <= 20.0:
            return 0
        elif score <= 50.0:
            return 1
        elif score <= 80.0:
            return 2
        else:
            return 3

    def get_state_name(self) -> str:
        """Returns the string name of the current state."""
        level = self.get_level()
        mapping = {
            0: "FOCUSED",
            1: "SLIGHT_DISTRACTION",
            2: "SUSTAINED_DISTRACTION",
            3: "TOTAL_ZONE_OUT"
        }
        return mapping.get(level, "FOCUSED")
