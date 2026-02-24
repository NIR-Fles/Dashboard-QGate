import logging
import random

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logger = logging.getLogger("yolo_processor")

# Abstract Base Class
class YoloProcessorBase:
    def __init__(self, model_path="yolo11n.pt"):
        self.model_path = model_path
        
    def process(self, frame):
        raise NotImplementedError

# Mock Implementation
class MockYoloProcessor(YoloProcessorBase):
    def __init__(self, model_path="yolo11n.pt"):
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
            if random.random() > 0.2: # 80% chance of detection
                detected.append(bolt)
        return detected

# Real Implementation
class RealYoloProcessor(YoloProcessorBase):
    def __init__(self, model_path="yolo11n.pt"):
        super().__init__(model_path)
        self.model = None
        if YOLO:
            try:
                self.model = YOLO(model_path)
                logger.info(f"REAL YOLO: Loaded model from {model_path}")
            except Exception as e:
                logger.error(f"REAL YOLO Error loading model: {e}")
        else:
            logger.error("ultralytics not installed! Real mode will fail.")

    def process(self, frame):
        if not self.model:
            return []
            
        detected = []
        try:
            results = self.model(frame)
            for result in results:
                for box in result.boxes:
                     class_id = int(box.cls)
                     label = self.model.names[class_id]
                     detected.append(label)
        except Exception as e:
            logger.error(f"YOLO Inference Error: {e}")
            
        return detected

# Factory Function
def get_yolo_processor(mode="MOCK", model_path="yolo11n.pt"):
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
