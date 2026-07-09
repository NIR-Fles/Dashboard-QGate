import threading
import json
import base64
import cv2
import os
import uuid
from datetime import datetime
import time

class StateManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(StateManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.lock = threading.Lock()
        
        # Initial State
        self.system_status = {
            "plc_connected": False,
            "engine_active": False, # Master Switch: False = STOPPED, True = RUNNING
            "unit_present": False,
            "model": "PCX 160",
            "final_result": "-"
        }
        
        self.current_frame_id = "-"
        
        # Bolt List & Statuses using descriptive IDs
        self.bolt_data = {
            "right": [
                "NUT_FLANGE_6MM_GROUNDING",
                "BOLT_FIXING_RADIATOR_RESERVE",
                "BOLT_AXLE_FRONT_WHEEL",
                "BF_10X55_LINK_ASSY_ENG_HANGER_R",
                "BF_10X38_REAR_CUSHION_R",
                "BF_10X65_MUFFLER_CENTER_UPPER",
                "BF_10X65_MUFFLER_REAR_UNDER",
                "BF_10X65_MUFFLER_FRONT_UNDER"
            ],
            "upper": [
                "BS_6X18_FENDER_C_REAR_FRONT",
                "BS_6X18_FENDER_C_REAR_REAR"
            ],
            "left": [
                "NUT_FRONT_AXLE_12MM",
                "BOLT_TORX_8X28_CALIPER_UNDER",
                "BOLT_TORX_8X28_CALIPER_UPPER",
                "BF_8X12_HORN_COMP",
                "BOLT_SIDE_STAND_PIVOT",
                "BF_6X12_CLAMP_THROTTLE_CABLE",
                "BF_10X55_LINK_ASSY_ENG_HANGER_L",
                "BF_10X38_REAR_CUSHION_L",
                "BOLT_WASHER_6X12_REAR_FENDER",
                "BF_10X255_LINK_ASSY_ENG_HANGER_L"
            ]
        }
        
        # Status Map: { "NUT_FLANGE_6MM_GROUNDING": "-", ... }
        self.bolt_statuses = {bolt: "-" for sublist in self.bolt_data.values() for bolt in sublist}
        
        # Images (Base64 strings)
        # Images (Base64 strings for frontend, File paths for DB)
        # 6 slots: 3 cameras * 2 steps
        self.images = {
            "right_step1": None, "right_step2": None,
            "upper_step1": None, "upper_step2": None,
            "left_step1": None,  "left_step2": None
        }
        self.image_paths = {k: None for k in self.images}
        
        # Ensure history directory exists
        self.history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_images")
        os.makedirs(self.history_dir, exist_ok=True)
        
        # Ensure live images directory exists for static fast routing
        self.live_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_images")
        os.makedirs(self.live_dir, exist_ok=True)

    def set_plc_connected(self, status: bool):
        with self.lock:
            self.system_status["plc_connected"] = status

    def reset(self):
        with self.lock:
            for key in self.bolt_statuses:
                self.bolt_statuses[key] = "-"
            
            self.system_status["final_result"] = "-"
            self.system_status["unit_present"] = False
            
            self.current_frame_id = "-"
            
            # Reset all image slots
            self.images = {k: None for k in self.images}
            self.image_paths = {k: None for k in self.images}

    def generate_frame_id(self):
        with self.lock:
            if self.current_frame_id == "-":
                self.current_frame_id = "MH1" + uuid.uuid4().hex[:12].upper()

    def set_frame_id(self, frame_id):
        with self.lock:
            self.current_frame_id = frame_id

    def update_bolt_status(self, bolt_id, status):
        with self.lock:
            if bolt_id in self.bolt_statuses:
                self.bolt_statuses[bolt_id] = status

    def finalize_results(self):
        """Checks for any pending bolts and sets them to NG"""
        with self.lock:
            for bolt_id, status in self.bolt_statuses.items():
                if status == "-":
                    self.bolt_statuses[bolt_id] = "NG"
                    
            # Return payload for DB save
            return {
                 "frame_id": self.current_frame_id, # Use strictly generated ID
                 "model": self.system_status["model"],
                 "final_result": "OK" if "NG" not in self.bolt_statuses.values() else "NG",
                 "bolt_data": dict(self.bolt_statuses),
                 "images": dict(self.image_paths)
            }
                
    def update_image(self, camera_key, step, frame):
        """
        Full image update: saves history to disk AND updates live dashboard.
        Used by Step 2 where frame_id is already finalized.
        key: 'right', 'left', 'upper'
        step: 1 or 2
        """
        if frame is not None:
            # Save full-res file to disk for history
            side_dir = os.path.join(self.history_dir, camera_key)
            os.makedirs(side_dir, exist_ok=True)
            capture_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{self.current_frame_id}-{camera_key}_step_{step}-{capture_time}.jpg"
            filepath = os.path.join(side_dir, filename)
            cv2.imwrite(filepath, frame)
            
            # Downscale for live dashboard to reduce bandwidth/latency
            # Max width 640px is plenty for dashboard display
            h, w = frame.shape[:2]
            max_w = 640
            if w > max_w:
                scale = max_w / w
                display_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            else:
                display_frame = frame

            storage_key = f"{camera_key}_step{step}"
            live_filename = f"latest_{storage_key}.jpg"
            live_filepath = os.path.join(self.live_dir, live_filename)
            cv2.imwrite(live_filepath, display_frame)

            with self.lock:
                if storage_key in self.images:
                    # Serve statically to avoid massive Base64 JSON overhead
                    self.images[storage_key] = f"/live_images/{live_filename}?t={int(time.time()*1000)}"
                    # Store relative filepath to history_images folder
                    self.image_paths[storage_key] = f"{camera_key}/{filename}"

    def update_live_view(self, camera_key, step, frame):
        """
        Fast path: Updates ONLY the live dashboard image (downscaled).
        Does NOT save history to disk. Used by Step 1 to instantly show
        inspection results on dashboard without waiting for OCR.
        """
        if frame is not None:
            h, w = frame.shape[:2]
            max_w = 640
            if w > max_w:
                scale = max_w / w
                display_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            else:
                display_frame = frame

            storage_key = f"{camera_key}_step{step}"
            live_filename = f"latest_{storage_key}.jpg"
            live_filepath = os.path.join(self.live_dir, live_filename)
            cv2.imwrite(live_filepath, display_frame)

            with self.lock:
                if storage_key in self.images:
                    self.images[storage_key] = f"/live_images/{live_filename}?t={int(time.time()*1000)}"

    def save_history_image(self, camera_key, step, frame):
        """
        Deferred path: Saves full-resolution image to history folder
        using the current (OCR-corrected) frame_id.
        Called from background thread after OCR has completed.
        """
        if frame is not None:
            side_dir = os.path.join(self.history_dir, camera_key)
            os.makedirs(side_dir, exist_ok=True)
            capture_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{self.current_frame_id}-{camera_key}_step_{step}-{capture_time}.jpg"
            filepath = os.path.join(side_dir, filename)
            cv2.imwrite(filepath, frame)

            storage_key = f"{camera_key}_step{step}"
            with self.lock:
                if storage_key in self.images:
                    self.image_paths[storage_key] = f"{camera_key}/{filename}"

    def get_full_state(self):
        with self.lock:
            # Calculate Final Result
            if not self.system_status["unit_present"]:
                final = "-"
            else:
                statuses = list(self.bolt_statuses.values())
                if "NG" in statuses:
                    final = "NG"
                elif "-" in statuses:
                    final = "PENDING"
                else:
                    final = "OK"
                
            self.system_status["final_result"] = final
            self.system_status["frame_id"] = self.current_frame_id

            return {
                "system": self.system_status,
                "timestamp": time.time(),
                "bolt_data": self.bolt_data,
                "statuses": self.bolt_statuses,
                "images": self.images
            }
