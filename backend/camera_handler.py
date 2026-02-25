import cv2
import logging
import numpy as np
import time
import os
import random

logger = logging.getLogger("camera_handler")

# Abstract Base Class
class CameraHandlerBase:
    def __init__(self):
        self.cam_names = ["left", "right", "upper"]
        
    def initialize(self):
        pass
        
    def capture_all(self, step=1):
        raise NotImplementedError
        
    def release(self):
        pass

# Mock Implementation (Noise/Colors)
class MockCameraHandler(CameraHandlerBase):
    def initialize(self):
        logger.info("MOCK Camera: Initialized.")

    def capture_all(self, step=1):
        frames = {}
        for name in self.cam_names:
            frames[name] = self._generate_mock_frame(f"{name} Step {step}")
        return frames

    def _generate_mock_frame(self, text):
        img = np.zeros((480, 640, 3), np.uint8)
        color = np.random.randint(0, 255, (3,)).tolist()
        img[:] = color
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, f"Simulated {text}", (50, 240), font, 1.5, (255, 255, 255), 3, cv2.LINE_AA)
        ts = time.strftime("%H:%M:%S")
        cv2.putText(img, ts, (50, 400), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        return img

# File Implementation (From Directory)
class FileCameraHandler(CameraHandlerBase):
    def __init__(self, base_dir="test_images"):
        super().__init__()
        self.base_dir = base_dir
        self.last_upper_frame = None
        
    def initialize(self):
        logger.info(f"TEST Camera: Reading from step-specific directories in {self.base_dir}")

    def capture_all(self, step=1):
        frames = {}
        for name in self.cam_names:
            # Special case: Upper camera in Step 2 uses the exact same image from Step 1
            if step == 2 and name == "upper":
                if self.last_upper_frame is not None:
                    frames[name] = self.last_upper_frame
                else:
                    logger.warning("Step 2 Upper camera triggered, but no Step 1 image was found. Using error frame.")
                    frames[name] = self._generate_error_frame(f"No Step 1 {name}")
                continue

            # Construct path: e.g., test_images/step1/right
            dir_path = os.path.join(self.base_dir, f"step{step}", name)
            
            if os.path.exists(dir_path):
                files = [f for f in os.listdir(dir_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                if files:
                    chosen_file = random.choice(files)
                    img_path = os.path.join(dir_path, chosen_file)
                    img = cv2.imread(img_path)
                    if img is not None:
                         frames[name] = img
                         # Cache upper camera image if this is step 1
                         if step == 1 and name == "upper":
                             self.last_upper_frame = img
                    else:
                        logger.warning(f"Failed to read image: {img_path}")
                        frames[name] = self._generate_error_frame(f"Read Error {name}")
                else:
                    frames[name] = self._generate_error_frame(f"No Files {name}")
            else:
                frames[name] = self._generate_error_frame(f"No Dir step{step}/{name}")
        return frames

    def _generate_error_frame(self, text):
        img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(img, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return img

# Real Implementation (Hardware)
class RealCameraHandler(CameraHandlerBase):
    def __init__(self):
        super().__init__()
        self.cam_indices = {
            "left": 0,
            "right": 1,
            "upper": 2
        }
        self.caps = {}

    def initialize(self):
        for name, idx in self.cam_indices.items():
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                self.caps[name] = cap
                logger.info(f"REAL Camera {name} (Idx {idx}) Opened.")
            else:
                logger.error(f"Failed to open Camera {name} (Idx {idx})")

    def capture_all(self, step=1):
        frames = {}
        for name, cap in self.caps.items():
            # In Real Mode, we capture fresh frames for everything unless upper requires caching?
            # Assuming real cameras also just capture whatever is live.
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    frames[name] = frame
                else:
                    frames[name] = self._generate_error_frame()
            else:
                frames[name] = self._generate_error_frame()
        return frames

    def release(self):
        for cap in self.caps.values():
            cap.release()
            
    def _generate_error_frame(self):
        img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(img, "CAM ERROR", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        return img

# Factory Function
def get_camera_handler(mode="MOCK", **kwargs):
    if mode == "REAL":
        logger.info("Initializing REAL Camera Handler")
        return RealCameraHandler()
    elif mode == "TEST":
        logger.info("Initializing TEST Camera Handler (File Based)")
        return FileCameraHandler(**kwargs)
    else:
        logger.info("Initializing MOCK Camera Handler")
        return MockCameraHandler()
