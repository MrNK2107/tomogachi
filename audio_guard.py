import sounddevice as sd
import numpy as np

def is_audio_silent_mode() -> bool:
    """
    Checks the default output device to see if it is safe to play audio alerts.
    Returns True if we must remain silent (SAFE_SILENT_MODE), False if we can play sound (headphones).
    """
    try:
        default_out_idx = sd.default.device[1]
        if default_out_idx is None or default_out_idx < 0:
            return True  # No valid output device, default to silent
        
        device_info = sd.query_devices(default_out_idx)
        device_name = device_info.get('name', '').lower()
        
        # Keywords indicating a private headset/headphones/bluetooth device
        headphone_keywords = ['headphone', 'headset', 'airpods', 'earphone', 'buds', 'bluetooth', 'hands-free']
        
        is_headphone = any(kw in device_name for kw in headphone_keywords)
        is_speaker = 'speaker' in device_name
        
        # Must have headphone keyword and NOT speaker keyword to play sound
        if is_headphone and not is_speaker:
            return False
        return True
    except Exception as e:
        # Default to safe silent mode on any error/exception
        print(f"[AudioGuard] Fallback to SAFE_SILENT_MODE due to query failure: {e}")
        return True

def play_alert_tone(frequency: float = 880.0, duration: float = 0.25, volume: float = 0.2) -> bool:
    """
    Synthesizes and plays a beep alert tone asynchronously if we are not in silent mode.
    Returns True if sound was played, False if suppressed or failed.
    """
    if is_audio_silent_mode():
        # Safeguard: suppress sound
        return False
    
    try:
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # Smooth attack/decay envelope to avoid clicking sounds
        envelope = np.ones_like(t)
        fade_len = int(sample_rate * 0.02)  # 20ms fade
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
        
        # Sine wave tone
        wave = np.sin(2 * np.pi * frequency * t) * envelope * volume
        
        # Play asynchronously
        sd.play(wave, sample_rate)
        return True
    except Exception as e:
        print(f"[AudioGuard] Failed to play tone: {e}")
        return False
