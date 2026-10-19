import unittest
from unittest.mock import patch, MagicMock
from intensity_engine import IntensityEngine
from audio_guard import is_audio_silent_mode

class TestIntensityEngine(unittest.TestCase):
    def setUp(self):
        self.engine = IntensityEngine()
        
    def test_initial_state(self):
        self.assertEqual(self.engine.distraction_score, 0.0)
        self.assertEqual(self.engine.get_level(), 0)
        self.assertEqual(self.engine.get_state_name(), "FOCUSED")
        
    def test_accumulation(self):
        # Accumulate score by +15 per second when distracted
        score = self.engine.update(is_focused=False, dt=1.0)
        self.assertEqual(score, 15.0)
        self.assertEqual(self.engine.get_level(), 0) # 15 <= 20 -> Level 0
        
        # Accumulate more to transition to Level 1
        score = self.engine.update(is_focused=False, dt=2.0)
        self.assertEqual(score, 45.0)
        self.assertEqual(self.engine.get_level(), 1) # 45 is in (20, 50] -> Level 1
        self.assertEqual(self.engine.get_state_name(), "SLIGHT_DISTRACTION")
        
        # Accumulate more to transition to Level 2
        score = self.engine.update(is_focused=False, dt=2.0)
        self.assertEqual(score, 75.0)
        self.assertEqual(self.engine.get_level(), 2) # 75 is in (50, 80] -> Level 2
        self.assertEqual(self.engine.get_state_name(), "SUSTAINED_DISTRACTION")

        # Accumulate more to transition to Level 3
        score = self.engine.update(is_focused=False, dt=1.0)
        self.assertEqual(score, 90.0)
        self.assertEqual(self.engine.get_level(), 3) # 90 is in (80, 100] -> Level 3
        self.assertEqual(self.engine.get_state_name(), "TOTAL_ZONE_OUT")

    def test_decay(self):
        # Set high distraction score
        self.engine.distraction_score = 50.0
        
        # Decay score by -20 per second when focused
        score = self.engine.update(is_focused=True, dt=1.0)
        self.assertEqual(score, 30.0)
        
        # Decay past zero (should be floored at 0.0)
        score = self.engine.update(is_focused=True, dt=2.0)
        self.assertEqual(score, 0.0)
        self.assertEqual(self.engine.get_level(), 0)
        
    def test_max_score_cap(self):
        self.engine.distraction_score = 95.0
        score = self.engine.update(is_focused=False, dt=1.0)
        self.assertEqual(score, 100.0)
        self.assertEqual(self.engine.get_level(), 3)
        self.assertEqual(self.engine.get_state_name(), "TOTAL_ZONE_OUT")

    def test_level_boundaries(self):
        # Exact boundary at 20.0 -> Level 0
        self.engine.distraction_score = 20.0
        self.assertEqual(self.engine.get_level(), 0)
        self.assertEqual(self.engine.get_state_name(), "FOCUSED")

        # 20.1 -> Level 1
        self.engine.distraction_score = 20.1
        self.assertEqual(self.engine.get_level(), 1)
        self.assertEqual(self.engine.get_state_name(), "SLIGHT_DISTRACTION")

        # Exact boundary at 50.0 -> Level 1
        self.engine.distraction_score = 50.0
        self.assertEqual(self.engine.get_level(), 1)

        # 50.1 -> Level 2
        self.engine.distraction_score = 50.1
        self.assertEqual(self.engine.get_level(), 2)
        self.assertEqual(self.engine.get_state_name(), "SUSTAINED_DISTRACTION")

        # Exact boundary at 80.0 -> Level 2
        self.engine.distraction_score = 80.0
        self.assertEqual(self.engine.get_level(), 2)

        # 80.1 -> Level 3
        self.engine.distraction_score = 80.1
        self.assertEqual(self.engine.get_level(), 3)
        self.assertEqual(self.engine.get_state_name(), "TOTAL_ZONE_OUT")

class TestAudioGuard(unittest.TestCase):
    @patch('sounddevice.default')
    @patch('sounddevice.query_devices')
    def test_speakers_active(self, mock_query, mock_default):
        # Mock default output device index
        mock_default.device = [1, 3]
        # Mock speaker device info
        mock_query.return_value = {
            'name': 'Speakers (Realtek(R) Audio)',
            'max_output_channels': 2
        }
        # Speakers active should return True (Silent Mode)
        self.assertTrue(is_audio_silent_mode())
        
    @patch('sounddevice.default')
    @patch('sounddevice.query_devices')
    def test_headphones_active(self, mock_query, mock_default):
        # Mock default output device index
        mock_default.device = [1, 3]
        # Mock headphone device info
        mock_query.return_value = {
            'name': 'Headphones (Realtek High Definition Audio)',
            'max_output_channels': 2
        }
        # Headphones active should return False (Not Silent Mode, sound allowed)
        self.assertFalse(is_audio_silent_mode())
        
    @patch('sounddevice.default')
    @patch('sounddevice.query_devices')
    def test_bluetooth_buds_active(self, mock_query, mock_default):
        mock_default.device = [1, 3]
        mock_query.return_value = {
            'name': 'soundcore V30i Hands-Free Bluetooth Buds',
            'max_output_channels': 2
        }
        # Bluetooth / Buds should return False (Not Silent Mode, sound allowed)
        self.assertFalse(is_audio_silent_mode())
        
    @patch('sounddevice.default')
    @patch('sounddevice.query_devices')
    def test_failure_fallback(self, mock_query, mock_default):
        # Throw an error to test the try-except block
        mock_default.device = [1, 3]
        mock_query.side_effect = Exception("Query error")
        # Should default to True (Silent Mode)
        self.assertTrue(is_audio_silent_mode())

    @patch('audio_guard.is_audio_silent_mode')
    def test_play_alert_tone_suppression(self, mock_silent_mode):
        from audio_guard import play_alert_tone
        # When silent mode is True, play_alert_tone returns False without playing sound
        mock_silent_mode.return_value = True
        self.assertFalse(play_alert_tone())

class TestCVTrackerWorker(unittest.TestCase):
    def test_worker_initialization_and_simulation(self):
        from cv_tracker import CVTrackerWorker
        worker = CVTrackerWorker(camera_index=0)
        self.assertFalse(worker.simulation_mode)
        self.assertTrue(worker.sim_is_focused)
        self.assertEqual(worker.sim_distraction_type, "NONE")

        # Test simulation mode toggle
        status_updates = []
        worker.status_message.connect(lambda msg: status_updates.append(msg))
        worker.set_simulation_mode(True)
        self.assertTrue(worker.simulation_mode)
        self.assertIn("Simulation (Demo) Mode Active", status_updates)

        # Test mock state trigger
        worker.trigger_mock_state(False, "LOOKING_AWAY")
        self.assertFalse(worker.sim_is_focused)
        self.assertEqual(worker.sim_distraction_type, "LOOKING_AWAY")

    def test_calibration_trigger(self):
        from cv_tracker import CVTrackerWorker
        worker = CVTrackerWorker(camera_index=0)
        status_updates = []
        worker.status_message.connect(lambda msg: status_updates.append(msg))
        worker.start_calibration()
        self.assertTrue(worker.calibrating)
        self.assertEqual(len(worker.calibration_frames), 0)
        self.assertTrue(any("Calibrating..." in msg for msg in status_updates))

class TestPetGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_pet_window_and_overlay_levels(self):
        from pet_gui import PetWindow, ScreenOverlay
        overlay = ScreenOverlay()
        pet = PetWindow(screen_overlay=overlay)

        self.assertEqual(pet.level, 0)
        self.assertEqual(overlay.level, 0)

        # Test level 1 state transition
        pet.set_level(1)
        overlay.set_level(1)
        self.assertEqual(pet.level, 1)
        self.assertNotEqual(pet.bubble_text, "")

        # Test level 2 state transition
        pet.set_level(2)
        overlay.set_level(2)
        self.assertEqual(pet.level, 2)
        self.assertEqual(pet.bubble_text, "")

        # Test level 3 state transition
        pet.set_level(3)
        overlay.set_level(3)
        self.assertEqual(pet.level, 3)

        # Clean up
        pet.close()
        overlay.close()

    def test_pet_styles(self):
        from pet_gui import PetWindow
        pet = PetWindow()
        for p_type in ["BLOB", "CAT", "ROBO", "PANDA", "CUSTOM"]:
            pet.set_pet_style(p_type)
            self.assertEqual(pet.pet_type, p_type)
        pet.close()

class TestConfigManager(unittest.TestCase):
    def test_config_load_save(self):
        import config_manager
        config = config_manager.load_config()
        self.assertIn("autostart", config)
        self.assertIn("pet_type", config)
        
        # Test save
        config["pet_type"] = "CAT"
        success = config_manager.save_config(config)
        self.assertTrue(success)

        reloaded = config_manager.load_config()
        self.assertEqual(reloaded["pet_type"], "CAT")

        # Restore default
        config["pet_type"] = "BLOB"
        config_manager.save_config(config)

    def test_launch_command(self):
        import config_manager
        cmd = config_manager.get_launch_command()
        self.assertIn("run.py", cmd)
        self.assertIn("--daemon", cmd)


class TestMultimodalFusion(unittest.TestCase):
    def test_update_fused(self):
        from intensity_engine import IntensityEngine
        engine = IntensityEngine()

        # Active typing (input=True) overrides vision=False
        score = engine.update_fused(is_vision_focused=False, is_input_active=True, is_mic_active=False, dt=1.0)
        self.assertEqual(score, 0.0)

        # Speaking in call (mic=True) overrides vision=False & input=False
        score = engine.update_fused(is_vision_focused=False, is_input_active=False, is_mic_active=True, dt=1.0)
        self.assertEqual(score, 0.0)

        # Idle input, mic silent, and vision=False increases distraction score
        score = engine.update_fused(is_vision_focused=False, is_input_active=False, is_mic_active=False, dt=1.0)
        self.assertEqual(score, 15.0)

    def test_activity_tracker(self):
        from activity_tracker import ActivityTrackerWorker, get_idle_time_seconds
        idle = get_idle_time_seconds()
        self.assertIsInstance(idle, float)

        worker = ActivityTrackerWorker()
        self.assertTrue(worker.running)

    def test_mic_and_window_trackers(self):
        from mic_tracker import MicTrackerWorker
        from window_tracker import WindowTrackerWorker, get_active_window_title

        title = get_active_window_title()
        self.assertIsInstance(title, str)

        mic_w = MicTrackerWorker()
        win_w = WindowTrackerWorker()
        self.assertTrue(mic_w.running)
        self.assertTrue(win_w.running)

    def test_sensitivity_presets(self):
        from cv_tracker import CVTrackerWorker
        worker = CVTrackerWorker()
        for preset in ["STRICT", "NORMAL", "RELAXED", "ULTRA_TOLERANT"]:
            worker.set_sensitivity_preset(preset)
            self.assertEqual(worker.sensitivity_preset, preset)

class TestProceduralPetSprites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_procedural_pet_widget(self):
        from pet_sprites import ProceduralPetWidget, PALETTES
        
        # Verify themes
        self.assertIn("Tokyo Night", PALETTES)
        self.assertIn("Dracula", PALETTES)
        self.assertIn("Catppuccin", PALETTES)
        self.assertIn("One Dark Pro", PALETTES)

        # Instantiate procedural pet
        pet = ProceduralPetWidget("CAT", "Tokyo Night")
        self.assertEqual(pet.character_type, "CAT")
        self.assertEqual(pet.theme_name, "Tokyo Night")

        # Test character switching
        for char in ["CAT", "DRAGON", "BOT"]:
            pet.set_character(char)
            self.assertEqual(pet.character_type, char)

        # Test state switching
        for st in range(4):
            pet.set_state(st)
            self.assertEqual(pet.state, st)

        # Test animation frame tick
class TestAwakenIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_engine_agent_active(self):
        engine = IntensityEngine()
        engine.distraction_score = 40.0
        # When agent is active, score decays as focused work
        score = engine.update_fused(is_agent_active=True, dt=1.0)
        self.assertLess(score, 40.0)

    def test_engine_heal_and_penalty(self):
        engine = IntensityEngine()
        engine.distraction_score = 50.0
        engine.heal_focus(20.0)
        self.assertEqual(engine.distraction_score, 30.0)
        engine.penalize_focus(10.0)
        self.assertEqual(engine.distraction_score, 40.0)

    def test_agent_detector(self):
        from core.agent_detector import AgentDetector
        detector = AgentDetector()
        agents = detector.get_running_agents()
        self.assertIsInstance(agents, list)
        summary = detector.get_summary_text()
        self.assertIsInstance(summary, str)

    def test_roast_bank(self):
        from quiz.roast_bank import get_brutal_roast, get_shutdown_roast
        r15 = get_brutal_roast(15.0)
        self.assertIn("PHONE", r15.upper())
        r45 = get_brutal_roast(50.0)
        self.assertIsInstance(r45, str)
        r_shut = get_shutdown_roast()
        self.assertIsInstance(r_shut, str)

    def test_quiz_manager(self):
        from quiz.quiz_manager import QuizManager
        qm = QuizManager()
        q = qm.get_question()
        self.assertIn("options", q)
        self.assertEqual(len(q["options"]), 4)

    def test_git_tracker(self):
        from core.git_tracker import GitTracker
        tracker = GitTracker()
        summary = tracker.get_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("branch", summary)
        self.assertIn("summary", summary)

    def test_system_sentinel_doomscroll(self):
        import time
        from core.system_sentinel import SystemSentinel
        sentinel = SystemSentinel()
        sentinel.update_window_context("YouTube - Shorts", "DISTRACTING")
        sentinel.window_dwell_start = time.time() - 130.0  # 130s dwell
        events = sentinel.tick(is_input_active=True, dt=1.0)
        doomscroll_events = [e for e in events if e.get("type") == "DOOMSCROLL_DETECTED"]
        self.assertEqual(len(doomscroll_events), 1)
        self.assertEqual(doomscroll_events[0]["window_title"], "YouTube - Shorts")

    def test_system_sentinel_hardware_telemetry(self):
        from core.system_sentinel import SystemSentinel
        sentinel = SystemSentinel()
        hw = sentinel.get_hardware_telemetry()
        self.assertIn("cpu_percent", hw)
        self.assertIn("ram_percent", hw)
        self.assertIn("battery_percent", hw)
        self.assertIn("git", hw)

    def test_heartbeat_storage_actions(self):
        from core.heartbeat_storage import HeartbeatStorage
        storage = HeartbeatStorage()
        storage.queue_action("alarm")
        storage.queue_action("feed")
        actions = storage.pop_pending_actions()
        self.assertEqual(actions, ["alarm", "feed"])
        self.assertEqual(storage.pop_pending_actions(), [])

    def test_voice_alert_interface(self):
        from core.voice_alert import VoiceAlert
        va = VoiceAlert(enabled=True)
        self.assertTrue(va.enabled)
        va.play_tone("alert")
        va.speak("Test voice")

    def test_pet_gui_actions(self):
        from pet_gui import PetWindow
        pet = PetWindow()
        pet.show_custom_bubble("Focus now!")
        self.assertEqual(pet.bubble_text, "Focus now!")
        pet.trigger_alarm_animation()
        self.assertTrue(pet.is_knocking)
        pet.trigger_feed_animation()
        self.assertTrue(pet.pet_was_petted)
        pet.trigger_poke_animation()
        pet.close()

    def test_cloud_server_heartbeat_and_actions(self):
        import time
        import config
        from fastapi.testclient import TestClient
        from cloud_server import app, heartbeat_storage

        client = TestClient(app)
        heartbeat_storage.queue_action("feed")

        payload = {
            "secret": config.HEARTBEAT_SECRET,
            "idle_seconds": 15.0,
            "is_idle": False,
            "has_agents": True,
            "agents_summary": "Claude Code",
            "timestamp": time.time(),
            "active_window": "PyCharm",
            "battery_percent": 88.0,
            "git_summary": {"summary": "Git: Clean"}
        }

        resp = client.post("/api/heartbeat", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("feed", data.get("actions", []))

        # Root endpoint
        root_resp = client.get("/")
        self.assertEqual(root_resp.status_code, 200)
        root_data = root_resp.json()
        self.assertEqual(root_data.get("active_window"), "PyCharm")

        # Mobile alarm endpoint
        mobile_resp = client.get("/mobile-alarm")
        self.assertEqual(mobile_resp.status_code, 200)
        self.assertIn("vibrate", mobile_resp.text)
        self.assertIn("AWAY FROM LAPTOP", mobile_resp.text)

        # Action endpoint
        act_resp = client.post("/api/action", json={"action": "test_act"})
        self.assertEqual(act_resp.status_code, 200)
        self.assertTrue(act_resp.json().get("ok"))

    def test_phone_alert_manager(self):
        import tempfile
        import os
        from core.phone_alert import PhoneAlertManager
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cfg = os.path.join(tmpdir, "phone_config.json")
            with patch("core.phone_alert.CONFIG_PATH", temp_cfg):
                mgr = PhoneAlertManager()
                self.assertTrue(mgr.config["enabled"])
                self.assertIn("ntfy.sh", mgr.get_ntfy_url())
                
                # Test topic and webhook setters
                mgr.set_topic("test_topic_123")
                self.assertIn("test_topic_123", mgr.get_ntfy_url())
                mgr.set_webhook("https://trigger.macrodroid.com/test")
                self.assertEqual(mgr.config["webhook_url"], "https://trigger.macrodroid.com/test")

                # Test away alerts (mocking requests.post)
                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    res1 = mgr.trigger_away_phone_nuisance(20.0, "Claude Code")
                    self.assertTrue(res1)
                    self.assertTrue(mock_post.called)

    def test_phone_alert_modes_and_quiet_hours(self):
        import tempfile
        import os
        import datetime
        from core.phone_alert import PhoneAlertManager
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cfg = os.path.join(tmpdir, "phone_config.json")
            with patch("core.phone_alert.CONFIG_PATH", temp_cfg):
                mgr = PhoneAlertManager()
                # Disable quiet hours initially to test explicit modes
                mgr.set_quiet_hours("23:00", "07:30", enabled=False)

                # 1. Sleep mode
                mgr.sleep_mode(hours=8)
                muted, reason = mgr.is_muted()
                self.assertTrue(muted)
                self.assertIn("Sleep Mode", reason)

                # 2. Resume clears sleep mode
                mgr.resume()
                muted, _ = mgr.is_muted()
                self.assertFalse(muted)

                # 3. Class mode
                mgr.class_mode(minutes=45)
                muted, reason = mgr.is_muted()
                self.assertTrue(muted)
                self.assertIn("Class Mode", reason)

                # 4. Resume clears class mode
                mgr.resume()
                muted, _ = mgr.is_muted()
                self.assertFalse(muted)

                # 5. Quiet hours check
                mgr.set_quiet_hours("23:00", "07:30", enabled=True)
                # 23:45 (inside quiet hours across midnight)
                self.assertTrue(mgr.is_in_quiet_hours(now_time=datetime.time(23, 45)))
                muted, reason = mgr.is_muted(now_time=datetime.time(23, 45))
                self.assertTrue(muted)
                self.assertIn("Night Quiet Hours", reason)

                # 04:30 (inside quiet hours across midnight)
                self.assertTrue(mgr.is_in_quiet_hours(now_time=datetime.time(4, 30)))

                # 14:00 (outside quiet hours)
                self.assertFalse(mgr.is_in_quiet_hours(now_time=datetime.time(14, 0)))
                muted, _ = mgr.is_muted(now_time=datetime.time(14, 0))
                self.assertFalse(muted)

                # 6. Muted suppression in trigger_away_phone_nuisance
                mgr.sleep_mode(hours=8)
                with patch("requests.post") as mock_post:
                    # When muted, trigger_away_phone_nuisance returns False and does not post
                    res = mgr.trigger_away_phone_nuisance(30.0, "Active agents")
                    self.assertFalse(res)
                    self.assertFalse(mock_post.called)

    def test_voice_alert_silent_constraint(self):
        from core.voice_alert import VoiceAlert
        va = VoiceAlert(enabled=False)
        self.assertFalse(va.enabled)
        # Should cleanly return without sound
        va.speak("Should be silent", force=True)
        va.play_tone("siren", force=True)

if __name__ == '__main__':
    unittest.main()






