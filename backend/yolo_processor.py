import logging
import random
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logger = logging.getLogger("yolo_processor")

# Abstract Base Class
class YoloProcessorBase:
    def __init__(self, model_path="best-p2.pt"):
        self.model_path = model_path
        
    def process(self, frame):
        raise NotImplementedError

# Mock Implementation
class MockYoloProcessor(YoloProcessorBase):
    def __init__(self, model_path="best-p2.pt"):
        super().__init__(model_path)
        logger.info("MOCK YOLO: Initialized.")

    def process(self, frame):
        # Mock Logic: Randomly "detect" some bolts
        detected = []
        all_bolts = [
            # Right
            "NUT_FLANGE_6MM_GROUNDING", "BOLT_FIXING_RADIATOR_RESERVE", "BOLT_AXLE_FRONT_WHEEL",
            "BF_10X55_LINK_ASSY_ENG_HANGER_R", "BF_10X38_REAR_CUSHION_R", "BF_10X65_MUFFLER_CENTER_UPPER",
            "BF_10X65_MUFFLER_REAR_UNDER", "BF_10X65_MUFFLER_FRONT_UNDER",
            # Upper
            "BS_6X18_FENDER_C_REAR_FRONT", "BS_6X18_FENDER_C_REAR_REAR",
            # Left
            "NUT_FRONT_AXLE_12MM", "BOLT_TORX_8X28_CALIPER_UNDER", "BOLT_TORX_8X28_CALIPER_UPPER",
            "BF_8X12_HORN_COMP", "BOLT_SIDE_STAND_PIVOT", "BF_6X12_CLAMP_THROTTLE_CABLE",
            "BF_10X55_LINK_ASSY_ENG_HANGER_L", "BF_10X38_REAR_CUSHION_L", "BOLT_WASHER_6X12_REAR_FENDER",
            "BF_10X255_LINK_ASSY_ENG_HANGER_L"
        ]
        
        for bolt in all_bolts:
            if random.random() > 0.1: # high chance for monitoring
                detected.append(bolt)

        details = []
        # Add a fake FRAME_ID detection so we can test the crop logic
        if frame is not None:
            details.append({
                "label": "FRAME_ID",
                "box": [100, 100, 300, 200]
            })
            
        return detected, frame, details

# Real Implementation
class RealYoloProcessor(YoloProcessorBase):
    def __init__(self, model_path="best-p2.pt"):
        super().__init__(model_path)
        self.model = None
        if YOLO:
            try:
                self.model = YOLO(model_path)
                logger.info(f"REAL YOLO: Loaded model from {model_path}")
            except Exception:
                logger.exception(f"REAL YOLO Error loading model from {model_path}")
        else:
            logger.error("ultralytics not installed! Real mode will fail.")

    def process(self, frame):
        if not self.model or frame is None:
            return [], frame, []
            
        detected = []
        detection_details = [] # Store raw details like boxes for cropping
        annotated_frame = frame
        try:
            results = self.model(frame)
            
            for result in results:
                for box in result.boxes:
                     class_id = int(box.cls)
                     raw_label = self.model.names[class_id]
                     
                     # Format the label to match our dashboard IDs...
                     formatted_label = raw_label.replace(" ", "_").replace("(", "").replace(")", "").upper()
                     detected.append(formatted_label)

                     # Store box coordinates for cropping (xyxy format)
                     detection_details.append({
                         "label": formatted_label,
                         "box": box.xyxy[0].tolist() 
                     })
                     
                # Draw bounding boxes manually for full control over font size
                # Generate unique color per class using a golden-ratio hue spread
                annotated_frame = frame.copy()
                for box in result.boxes:
                    cls_id = int(box.cls)
                    label = self.model.names[cls_id]
                    conf = float(box.conf)
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    
                    # Unique color per class (HSV hue spread -> BGR)
                    hue = int((cls_id * 37) % 180)  # golden-ratio-like spread
                    hsv_color = np.array([[[hue, 200, 255]]], dtype=np.uint8)
                    bgr_color = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0][0]
                    color = tuple(int(c) for c in bgr_color)
                    
                    # Draw box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
                    
                    # Draw label with small font and 50% opacity background
                    text = f"{label} {conf:.2f}"
                    font_scale = 2
                    thickness = 3
                    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                    
                    # Semi-transparent label background (50% opacity)
                    bg_y1 = max(y1 - th - 6, 0)
                    bg_y2 = y1
                    bg_x1 = x1
                    bg_x2 = min(x1 + tw + 4, annotated_frame.shape[1])
                    overlay = annotated_frame.copy()
                    cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)
                    cv2.addWeighted(overlay, 0.5, annotated_frame, 0.5, 0, annotated_frame)
                    
                    # Draw text on top
                    cv2.putText(annotated_frame, text, (x1 + 2, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                
        except Exception as e:
            logger.error(f"YOLO Inference Error: {e}")
            
        return detected, annotated_frame, detection_details

# Factory Function
def get_yolo_processor(mode="MOCK", model_path="best-p2.pt"):
    if mode == "REAL" or mode == "TEST": 
        # TEST mode can utilize REAL YOLO if desired, or Mock YOLO. 
        # User asked for "Mock code", "Testing code (images from dir)", "Real code".
        # Typically Test Mode implies testing the MODEL against stored images.
        # So TEST should use RealYoloProcessor if available, or fall back?
        # Let's assume TEST mode uses Real YOLO to validate the model performance on static images.
        # IF user wants Mock YOLO with stored images, that's a specific mix.
        # Given "testing code using random image ... as image input", usually implies testing vision pipeline.
        
        # Let's verify: "2nd is testing code using random image but the sourcing from my directory..."
        # Does this mean checking the Yolo on it? 
        # Usually yes. But if they just want to test Layout, Mock YOLO is fine.
        # I will default TEST to use RealYolo, but fallback to Mock if import fails logic is inside Real Class?
        # Actually, let's allow "TEST" to use RealYoloProcessor.
        if YOLO:
            logger.info("Initializing REAL YOLO Processor for Mode: " + mode)
            return RealYoloProcessor(model_path)
        else:
            logger.warning("Ultralytics missing, falling back to MOCK YOLO for Mode: " + mode)
            return MockYoloProcessor(model_path)
            
    else:
        logger.info("Initializing MOCK YOLO Processor")
        return MockYoloProcessor(model_path)
