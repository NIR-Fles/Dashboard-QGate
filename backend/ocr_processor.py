import logging
import random
import uuid

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger("ocr_processor")

class OcrProcessorBase:
    def process(self, frame):
        raise NotImplementedError

class MockOcrProcessor(OcrProcessorBase):
    def __init__(self):
        logger.info("MOCK OCR: Initialized.")

    def process(self, frame):
        # MOCK logic: generate a random frame ID
        logger.info("MOCK OCR: Generating synthetic Frame ID.")
        return "MH1" + uuid.uuid4().hex[:12].upper()

class RealOcrProcessor(OcrProcessorBase):
    def __init__(self):
        self.ocr = None
        if PaddleOCR:
            try:
                # FORCE environment variables before anything else
                import os
                os.environ['FLAGS_use_onednn'] = '0'
                os.environ['FLAGS_enable_pir_in_executor'] = '0'
                os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
                
                # Absolute local paths to ensure zero internet dependence
                base_dir = os.path.dirname(os.path.abspath(__file__))
                # Correct Path: inside the .paddlex hidden folder
                local_model_path = os.path.join(base_dir, ".paddlex", "official_models")
                
                self.ocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    det_model_dir=os.path.join(local_model_path, "PP-OCRv4_mobile_det"),
                    rec_model_dir=os.path.join(local_model_path, "en_PP-OCRv4_mobile_rec"),
                    ocr_version='PP-OCRv4', # MATCH the folders exactly
                    use_angle_cls=False, 
                    lang='en',
                    device='cpu',
                    enable_mkldnn=False
                )
                logger.info("REAL OCR: Lightweight PP-OCRv4 Initialized (Safest Mode).")
            except Exception as e:
                logger.exception(f"REAL OCR: Error initializing PaddleOCR {e}")
        else:
            logger.error("paddleocr not installed! Real OCR mode will fail.")

    def process(self, frame):
        if not self.ocr or frame is None:
            return None
            
        try:
            # Perform OCR on the frame
            result = self.ocr.ocr(frame)
            logger.info(f"REAL OCR: Raw result -> {result}")
            
            candidates = []
            if result and isinstance(result, list) and len(result) > 0:
                item = result[0]
                # Format A: High-level dict (seen in logs)
                if isinstance(item, dict) and 'rec_texts' in item:
                    candidates = [str(t) for t in item.get('rec_texts', [])]
                # Format B: Classic list hierarchy
                elif isinstance(item, list):
                    for line in item:
                        try:
                            if len(line) >= 2 and len(line[1]) >= 2:
                                text = line[1][0]
                                confidence = line[1][1]
                                if confidence > 0.4:  # Match typical threshold
                                    candidates.append(str(text))
                        except (IndexError, TypeError):
                            continue

            # Clean and sanitize each candidate
            import re
            cleaned_candidates = []
            for cand in candidates:
                cleaned = re.sub(r'[^A-Z0-9]', '', cand.upper())
                if cleaned:
                    cleaned_candidates.append(cleaned)
            
            # Step A: Look for candidate matching Indonesian Honda VIN (Starts with MH1 and is exactly 17 chars)
            for cand in cleaned_candidates:
                if cand.startswith("MH1") and len(cand) == 17:
                    logger.info(f"REAL OCR: Found exact MH1 17-char VIN -> {cand}")
                    return cand
                    
            # Step B: Look for any candidate that is exactly 17 chars
            for cand in cleaned_candidates:
                if len(cand) == 17:
                    logger.info(f"REAL OCR: Found general 17-char VIN -> {cand}")
                    return cand
                    
            # Step C: Look for a substring inside any candidate that matches the 17-char VIN pattern
            for cand in cleaned_candidates:
                match = re.search(r'MH1[A-Z0-9]{14}', cand)
                if match:
                    found = match.group(0)
                    logger.info(f"REAL OCR: Found MH1 pattern in candidate -> {found}")
                    return found

            # Step D: Fallback to joining all cleaned candidates if no exact pattern is found
            extracted_text = "".join(cleaned_candidates)
            safe_text = re.sub(r'[^A-Z0-9]', '', str(extracted_text).upper())
            
            if len(safe_text) >= 3: 
                logger.info(f"REAL OCR: Fallback Detected Text -> {safe_text}")
                return safe_text
            return None
                
        except Exception as e:
            logger.error(f"OCR Inference Error: {e}")
            return None

def get_ocr_processor(mode="MOCK"):
    if mode == "REAL" or mode == "TEST": 
        if PaddleOCR:
            logger.info("Initializing REAL OCR Processor for Mode: " + mode)
            return RealOcrProcessor()
        else:
            logger.warning("paddleocr missing, falling back to MOCK OCR for Mode: " + mode)
            return MockOcrProcessor()
    else:
        logger.info("Initializing MOCK OCR Processor")
        return MockOcrProcessor()
