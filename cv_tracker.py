import time
import math
import collections
import numpy as np
import cv2
import mediapipe as mp
from PyQt6.QtCore import QThread, pyqtSignal

class CVTrackerWorker(QThread):
    """
    QThread worker running OpenCV and MediaPipe Face Mesh.
    Extracts head pose and eye metrics to determine focus.
    Includes a fallback simulation mode if no webcam is available.
    """
    # Signals to communicate with the Main GUI
    focus_update = pyqtSignal(bool, str)  # (is_focused, distraction_type)
    status_message = pyqtSignal(str)       # Status info for the settings panel
    frame_ready = pyqtSignal(np.ndarray)   # Emitted for settings debug preview (if open)

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self.camera_index = camera_index
        self.running = True
        
        # Calibration baseline offsets (Pitch and Yaw)
        self.base_yaw = 0.0
        self.base_pitch = 0.0
        self.calibrating = False
        self.auto_calibrated = False
        self.calibration_frames = []

        # Exponential low-pass filter states
        self.filtered_yaw = 0.0
        self.filtered_pitch = 0.0
        self.filter_alpha = 0.15

        # Buffers for state tracking
        self.ear_history = collections.deque(maxlen=150)  # ~5 seconds of EAR values at 30fps
        self.gaze_history = collections.deque(maxlen=120)  # ~4 seconds of Iris Offsets at 30fps
        self.head_pose_history = collections.deque(maxlen=120) # For movement checking
        
        # Distraction thresholds (Ultra-tolerant defaults)
        self.sensitivity_preset = "RELAXED"
        self.YAW_THRESHOLD = 48.0       # Degrees to turn head left/right
        self.PITCH_THRESHOLD = 36.0     # Degrees to look up/down
        self.EAR_CLOSED_THRESHOLD = 0.18 # Eye Aspect Ratio suggesting closed eyes
        self.CLOSED_DURATION = 2.0      # Seconds eyes must be closed to trigger distraction
        self.GAZE_STATIC_DURATION = 5.0  # Seconds gaze must remain static for zone-out
        self.GAZE_STATIC_STD_MAX = 0.003 # Maximum standard deviation of iris displacement to trigger zone-out

        # State tracking times
        self.eyes_closed_start_time = None
        self.gaze_static_start_time = None

        # Simulation Mode fields
        self.simulation_mode = False
        self.sim_is_focused = True
        self.sim_distraction_type = "NONE"

    def set_sensitivity_preset(self, preset: str):
        preset = preset.upper()
        self.sensitivity_preset = preset
        if preset == "STRICT":
            self.YAW_THRESHOLD, self.PITCH_THRESHOLD = 25.0, 18.0
        elif preset == "NORMAL":
            self.YAW_THRESHOLD, self.PITCH_THRESHOLD = 35.0, 25.0
        elif preset == "ULTRA_TOLERANT":
            self.YAW_THRESHOLD, self.PITCH_THRESHOLD = 60.0, 45.0
        else:  # RELAXED (Default)
            self.YAW_THRESHOLD, self.PITCH_THRESHOLD = 48.0, 36.0
        self.status_message.emit(f"Vision sensitivity set to {preset} (Yaw: {self.YAW_THRESHOLD}°, Pitch: {self.PITCH_THRESHOLD}°)")

    def set_simulation_mode(self, enabled: bool):
        self.simulation_mode = enabled
        if enabled:
            self.status_message.emit("Simulation (Demo) Mode Active")
        else:
            self.status_message.emit("Resuming webcam tracking...")

    def trigger_mock_state(self, is_focused: bool, distraction_type: str):
        self.sim_is_focused = is_focused
        self.sim_distraction_type = distraction_type

    def start_calibration(self):
        self.calibrating = True
        self.calibration_frames = []
        self.status_message.emit("Calibrating... Look directly at your monitor.")


    def run(self):
        """Main execution thread loop."""
        self.status_message.emit("Initializing computer vision tracker...")
        
        # Standard 3D Face Model Points for solvePnP
        # Coordinates in mm, relative to nose tip at (0,0,0) in a right-handed coordinate system
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip (landmark 4)
            (0.0, -330.0, -65.0),        # Chin (landmark 152)
            (-225.0, 170.0, -135.0),     # Left eye outer corner (landmark 33)
            (225.0, 170.0, -135.0),      # Right eye outer corner (landmark 263)
            (-150.0, -150.0, -125.0),    # Left mouth corner (landmark 61)
            (150.0, -150.0, -125.0)      # Right mouth corner (landmark 291)
        ], dtype=np.float32)

        # Initialize MediaPipe Face Mesh safely
        face_mesh = None
        try:
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
                mp_face_mesh = mp.solutions.face_mesh
                face_mesh = mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,  # Crucial for iris tracking
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            else:
                try:
                    import mediapipe.python.solutions.face_mesh as mp_face_mesh
                    face_mesh = mp_face_mesh.FaceMesh(
                        max_num_faces=1,
                        refine_landmarks=True,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5
                    )
                except Exception:
                    self.status_message.emit("MediaPipe solutions API unavailable in this environment. Defaulting to Simulation Demo Mode.")
                    self.simulation_mode = True
        except Exception as e:
            self.status_message.emit(f"MediaPipe Init Warning ({e}). Defaulting to Simulation Demo Mode.")
            self.simulation_mode = True

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.status_message.emit("Error: Could not open camera. Starting in Simulation Mode.")
            self.simulation_mode = True


        last_time = time.time()

        while self.running:
            # Handle simulation mode
            if self.simulation_mode:
                time.sleep(0.033)  # Loop at ~30 FPS
                self.focus_update.emit(self.sim_is_focused, self.sim_distraction_type)
                # Create a black/dummy frame to emit so UI debug view doesn't break
                dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(dummy_frame, "SIMULATION DEMO ACTIVE", (120, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(dummy_frame, f"Focus: {self.sim_is_focused}", (120, 290),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(dummy_frame, f"Type: {self.sim_distraction_type}", (120, 330),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                self.frame_ready.emit(dummy_frame)
                continue

            ret, frame = cap.read()
            if not ret:
                self.status_message.emit("Warning: Frame grab failed. Fallback to Simulation.")
                self.simulation_mode = True
                continue

            # Flip frame for mirror display and convert to RGB
            frame = cv2.flip(frame, 1)
            img_h, img_w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process face mesh landmarks
            results = face_mesh.process(rgb_frame)
            
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            is_focused = True
            distraction_type = "NONE"

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                
                # ----------------- 1. HEAD POSE ESTIMATION -----------------
                # Extract coordinates of key landmarks in pixel space
                key_indices = [4, 152, 33, 263, 61, 291]
                image_points = []
                for idx in key_indices:
                    lm = landmarks[idx]
                    image_points.append([lm.x * img_w, lm.y * img_h])
                image_points = np.array(image_points, dtype=np.float32)

                # Solve Perspective-n-Point
                focal_length = img_w
                center = (img_w / 2, img_h / 2)
                camera_matrix = np.array([
                    [focal_length, 0, center[0]],
                    [0, focal_length, center[1]],
                    [0, 0, 1]
                ], dtype=np.float32)
                dist_coeffs = np.zeros((4, 1), dtype=np.float32)

                success, rvec, tvec = cv2.solvePnP(
                    model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
                )

                if success:
                    # Decompose rotation vector to Euler angles (yaw, pitch, roll)
                    rmat, _ = cv2.Rodrigues(rvec)
                    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
                    
                    if sy >= 1e-6:
                        pitch = math.atan2(rmat[2, 1], rmat[2, 2])
                        yaw = math.atan2(-rmat[2, 0], sy)
                        roll = math.atan2(rmat[1, 0], rmat[0, 0])
                    else:
                        pitch = math.atan2(-rmat[1, 2], rmat[1, 1])
                        yaw = math.atan2(-rmat[2, 0], sy)
                        roll = 0.0

                    pitch = math.degrees(pitch)
                    yaw = math.degrees(yaw)
                    roll = math.degrees(roll)

                    # Manage Calibration (manual or initial auto-calibration)
                    if self.calibrating:
                        self.calibration_frames.append((yaw, pitch))
                        if len(self.calibration_frames) >= 60:  # ~2 seconds
                            yaws = [f[0] for f in self.calibration_frames]
                            pitches = [f[1] for f in self.calibration_frames]
                            self.base_yaw = sum(yaws) / len(yaws)
                            self.base_pitch = sum(pitches) / len(pitches)
                            self.calibrating = False
                            self.auto_calibrated = True
                            self.status_message.emit(f"Calibrated successfully! Baselines - Yaw: {self.base_yaw:.1f}, Pitch: {self.base_pitch:.1f}")
                    elif not self.auto_calibrated:
                        self.calibration_frames.append((yaw, pitch))
                        if len(self.calibration_frames) >= 15:  # Initial ~0.5s auto-baseline
                            yaws = [f[0] for f in self.calibration_frames]
                            pitches = [f[1] for f in self.calibration_frames]
                            self.base_yaw = sum(yaws) / len(yaws)
                            self.base_pitch = sum(pitches) / len(pitches)
                            self.auto_calibrated = True
                            self.status_message.emit(f"Auto-calibrated initial baseline pose: Yaw {self.base_yaw:.1f}°, Pitch {self.base_pitch:.1f}°")
                    
                    # Calculate deviation from calibrated baseline
                    dev_yaw = yaw - self.base_yaw
                    dev_pitch = pitch - self.base_pitch

                    
                    # Store head pose in history
                    self.head_pose_history.append((dev_yaw, dev_pitch))

                    # Check head pose threshold
                    if abs(dev_yaw) > self.YAW_THRESHOLD or abs(dev_pitch) > self.PITCH_THRESHOLD:
                        is_focused = False
                        distraction_type = "LOOKING_AWAY"

                    # Draw head direction vector for debug review
                    # Project nose point into 2D space
                    nose_end_point2D, _ = cv2.projectPoints(
                        np.array([(0.0, 0.0, 1000.0)]), rvec, tvec, camera_matrix, dist_coeffs
                    )
                    p1 = (int(image_points[0][0]), int(image_points[0][1]))
                    p2 = (int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1]))
                    cv2.line(frame, p1, p2, (255, 0, 0), 2)
                else:
                    dev_yaw, dev_pitch = 0.0, 0.0

                # ----------------- 2. EYE CLOSED DETECTION (EAR) -----------------
                # Left eye landmarks: 33 (outer corner), 160, 158, 133 (inner corner), 153, 144
                # Right eye landmarks: 362 (inner corner), 385, 387, 263 (outer corner), 373, 380
                def get_eye_ear(p_idx):
                    pts = np.array([[landmarks[i].x * img_w, landmarks[i].y * img_h] for i in p_idx])
                    v1 = np.linalg.norm(pts[1] - pts[5]) # Vertical top-outer to bottom-outer
                    v2 = np.linalg.norm(pts[2] - pts[4]) # Vertical top-inner to bottom-inner
                    h = np.linalg.norm(pts[0] - pts[3])  # Horizontal corners
                    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

                left_ear = get_eye_ear([33, 160, 158, 133, 153, 144])
                right_ear = get_eye_ear([362, 385, 387, 263, 373, 380])
                avg_ear = (left_ear + right_ear) / 2.0
                self.ear_history.append(avg_ear)

                # Process eye closure durations
                if avg_ear < self.EAR_CLOSED_THRESHOLD:
                    if self.eyes_closed_start_time is None:
                        self.eyes_closed_start_time = current_time
                    elif current_time - self.eyes_closed_start_time > self.CLOSED_DURATION:
                        is_focused = False
                        distraction_type = "ZONED_OUT"
                else:
                    self.eyes_closed_start_time = None

                # ----------------- 3. GAZE FIXATION DETECTION -----------------
                # Iris centers: Left (468), Right (473)
                # Compute displacement relative to eye centers
                left_eye_center = np.array([(landmarks[33].x + landmarks[133].x)/2.0, (landmarks[33].y + landmarks[133].y)/2.0])
                right_eye_center = np.array([(landmarks[362].x + landmarks[263].x)/2.0, (landmarks[362].y + landmarks[263].y)/2.0])
                
                left_iris = np.array([landmarks[468].x, landmarks[468].y])
                right_iris = np.array([landmarks[473].x, landmarks[473].y])
                
                left_disp = left_iris - left_eye_center
                right_disp = right_iris - right_eye_center
                
                # Combine displacement features
                gaze_vector = np.array([left_disp[0], left_disp[1], right_disp[0], right_disp[1]])
                self.gaze_history.append(gaze_vector)

                # Monitor gaze fixation: static eye position for > 4s with open eyes
                # Verify user is facing forward, eyes are open, and gaze history has enough elements
                if is_focused and avg_ear >= self.EAR_CLOSED_THRESHOLD and len(self.gaze_history) >= 100:
                    gaze_std = np.std(self.gaze_history, axis=0)
                    avg_std = np.mean(gaze_std)
                    
                    if avg_std < self.GAZE_STATIC_STD_MAX:
                        if self.gaze_static_start_time is None:
                            self.gaze_static_start_time = current_time
                        elif current_time - self.gaze_static_start_time > self.GAZE_STATIC_DURATION:
                            is_focused = False
                            distraction_type = "ZONED_OUT"
                    else:
                        self.gaze_static_start_time = None
                else:
                    self.gaze_static_start_time = None

                # Visual debugging markers on webcam frame
                # Draw green points on eyes/iris if focused, red if closed/distracted
                eye_color = (0, 255, 0) if is_focused else (0, 0, 255)
                cv2.circle(frame, (int(landmarks[468].x * img_w), int(landmarks[468].y * img_h)), 2, (255, 255, 0), -1)
                cv2.circle(frame, (int(landmarks[473].x * img_w), int(landmarks[473].y * img_h)), 2, (255, 255, 0), -1)
                cv2.circle(frame, (int(landmarks[4].x * img_w), int(landmarks[4].y * img_h)), 4, eye_color, -1)
                
                cv2.putText(frame, f"EAR: {avg_ear:.2f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.putText(frame, f"Yaw/Pitch: {dev_yaw:.1f}/{dev_pitch:.1f}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.putText(frame, f"Focus: {is_focused} ({distraction_type})", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, eye_color, 2)
            else:
                # No face detected
                is_focused = False
                distraction_type = "LOOKING_AWAY"
                cv2.putText(frame, "NO FACE DETECTED", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                self.eyes_closed_start_time = None
                self.gaze_static_start_time = None

            # Emit state parameters
            self.focus_update.emit(is_focused, distraction_type)
            self.frame_ready.emit(frame)
            
            # Control frame rate at ~30 FPS (33ms interval)
            time.sleep(0.03)

        # Release resources when thread completes
        cap.release()
        if face_mesh is not None:
            try:
                face_mesh.close()
            except Exception:
                pass


    def stop(self):
        """Stops the thread loop."""
        self.running = False
        self.wait()
