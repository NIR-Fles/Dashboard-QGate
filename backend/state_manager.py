import threading
import json
import base64
import cv2

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
            "unit_present": False,
            "model": "PCX 160",  # Hardcoded for now
            "final_result": "-"
        }
        
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
        # 6 slots: 3 cameras * 2 steps
        self.images = {
            "right_step1": None, "right_step2": None,
            "upper_step1": None, "upper_step2": None,
            "left_step1": None,  "left_step2": None
        }

    def reset(self):
        with self.lock:
            for key in self.bolt_statuses:
                self.bolt_statuses[key] = "-"
            
            self.system_status["final_result"] = "-"
            self.system_status["unit_present"] = False
            
            # Reset all image slots
            self.images = {k: None for k in self.images}

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
                
    def update_image(self, camera_key, step, frame):
        """
        Converts CV2 frame to Base64 and stores it.
        key: 'right', 'left', 'upper'
        step: 1 or 2
        """
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            storage_key = f"{camera_key}_step{step}"
            
            with self.lock:
                if storage_key in self.images:
                    self.images[storage_key] = f"data:image/jpeg;base64,{b64_str}"

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

            return {
                "system": self.system_status,
                "bolt_data": self.bolt_data,
                "statuses": self.bolt_statuses,
                "images": self.images
            }
