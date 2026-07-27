class IntensityEngine:
    """
    State machine keeping track of a Distraction Score (0.0 to 100.0) 
    and mapping it to four distinct behavioral intensity levels.
    Fuses Vision Tracking, Keyboard/Mouse Input, and Microphone Voice Activity.
    """
    def __init__(self):
        self.distraction_score = 0.0

    def reset(self):
        """Resets the distraction score to 0.0."""
        self.distraction_score = 0.0

    def update_fused(self, is_vision_focused: bool, is_input_active: bool, is_mic_active: bool, dt: float) -> float:
        """
        Multimodal Fused Focus Calculation:
        - Typing/Clicking (is_input_active=True) OR
        - Voice/Meeting Speaking (is_mic_active=True) OR
        - Vision Camera Focus (is_vision_focused=True)
        => FOCUSED.
        """
        is_focused = is_input_active or is_mic_active or is_vision_focused

        if is_focused:
            self.distraction_score = max(0.0, self.distraction_score - 20.0 * dt)
        else:
            self.distraction_score = min(100.0, self.distraction_score + 15.0 * dt)
            
        return self.distraction_score

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
