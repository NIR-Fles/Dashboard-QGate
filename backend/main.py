import os
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
# Force the AI to look at our local project folder for models
backend_dir = os.path.dirname(os.path.abspath(__file__))
# Note: PADDLE_PDX_HOME should be the folder CONTAINING the .paddlex folder
os.environ['PADDLE_PDX_HOME'] = backend_dir
os.environ['PADDLE_HOME'] = backend_dir
import asyncio
import logging
import threading
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from modbus_handler import get_modbus_handler
from camera_handler import get_camera_handler
from yolo_processor import get_yolo_processor
from ocr_processor import get_ocr_processor
from state_manager import StateManager
from database import init_db, save_inspection, get_history, export_to_csv

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

# Resolve absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
test_images_path = os.path.join(current_dir, "test_images")
model_path = os.path.join(current_dir, "best.pt")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    loop_thread = threading.Thread(target=control_loop, daemon=True)
    loop_thread.start()
    yield
    # Shutdown logic
    camera.release()

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
# Modes: "MOCK", "TEST", "REAL"
SYSTEM_MODE = "TEST" 
logger.info(f"System Starting in Mode: {SYSTEM_MODE}")

# Global Components
state_manager = StateManager()
modbus = get_modbus_handler(SYSTEM_MODE, state_manager=state_manager)
camera = get_camera_handler(SYSTEM_MODE, base_dir=test_images_path)
yolo = get_yolo_processor(SYSTEM_MODE, model_path=model_path)
ocr = get_ocr_processor(SYSTEM_MODE)

# Websocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_state(self):
        state = state_manager.get_full_state()
        # Iterate over a copy to allow removal
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(state)
            except Exception as e:
                logger.warning(f"Connection closed, removing: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# --- Control Loop ---
def control_loop():
    logger.info("Control loop started.")
    camera.initialize()
    
    while True:
        try:
            # Check if system is unpaused/running
            if not state_manager.system_status["engine_active"]:
                modbus.read_triggers() # FLUSH/IGNORE all incoming triggers for safety
                time.sleep(0.5) 
                continue

            # 1. Read Modbus Triggers
            triggers = modbus.read_triggers()
            
            # 2. Handle Capture Logic
            if triggers["capture_step_1"] or triggers["capture_step_2"]:
                step = 1 if triggers["capture_step_1"] else 2
                logger.info(f"Capture Step {step} triggered.")
                
                # Capture Frames (All Cameras) specific to the step
                frames = camera.capture_all(step=step)
                logger.info(f"Frames captured for step {step}")
                
                # Run Detection and Update State with Annotated Images
                detected_bolts = []
                upper_detection_details = []
                temp_annotated_frames = {}
                
                for cam_key, frame in frames.items():
                    if frame is not None:
                        # Process frame and get image with bounding boxes + raw info
                        bolts, annotated_img, details = yolo.process(frame)
                        detected_bolts.extend(bolts)
                        temp_annotated_frames[cam_key] = annotated_img
                        
                        if cam_key == "upper":
                            upper_detection_details = details
                    else:
                        temp_annotated_frames[cam_key] = None

                # Perform OCR to read Frame ID if Step = 1
                if step == 1:
                    logger.info("Attempting to read Frame ID via Crop + OCR.")
                    extracted_id = None
                    
                    # Look for FRAME_ID or similar label in the detections
                    frame_id_info = next((d for d in upper_detection_details if "FRAME_ID" in d["label"]), None)
                    
                    if frame_id_info and frames.get("upper") is not None:
                        try:
                            upper_img = frames["upper"]
                            h, w = upper_img.shape[:2]
                            logger.info(f"Upper Frame Resolution: {w}x{h}")
                            
                            # d["box"] is [x1, y1, x2, y2]
                            box = frame_id_info["box"]
                            x1, y1, x2, y2 = map(int, box)
                            
                            # Bounds checking
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(w, x2), min(h, y2)
                            
                            if x2 > x1 and y2 > y1:
                                # Add a small margin
                                margin = 15
                                x1_m = max(0, x1 - margin)
                                y1_m = max(0, y1 - margin)
                                x2_m = min(w, x2 + margin)
                                y2_m = min(h, y2 + margin)
                                
                                crop = upper_img[y1_m:y2_m, x1_m:x2_m]
                                logger.info(f"Targeting OCR Crop: Label={frame_id_info['label']} Crop Shape={crop.shape}")
                                extracted_id = ocr.process(crop)
                            else:
                                logger.warning(f"Invalid crop coordinates: {x1, y1, x2, y2} for frame {w}x{h}")
                        except Exception as e:
                            logger.error(f"Error during OCR cropping: {e}")
                    
                    if extracted_id:
                        logger.info(f"OCR Success. Frame ID Set: {extracted_id}")
                        state_manager.set_frame_id(extracted_id)
                    else:
                        logger.warning("OCR Failed (or no Frame ID label detected). Generating Fallback UUID.")
                        state_manager.generate_frame_id()

                # Now that Frame ID is set (for Step 1) or already exists (for Step 2),
                # save and update the images.
                for cam_key, annotated_img in temp_annotated_frames.items():
                    state_manager.update_image(cam_key, step, annotated_img)
                
                # Deduplicate the list (in case a bolt is seen by multiple cameras)
                detected_bolts = list(set(detected_bolts))
                
                logger.info(f"Detected bolts: {detected_bolts}")
                
                # Update status for detected bolts to OK
                for bolt_id in detected_bolts:
                    state_manager.update_bolt_status(bolt_id, "OK")

                # If Step 2 finished, finalize results (Pending -> NG)
                if step == 2:
                    logger.info("Step 2 finished. Finalizing results and saving to DB.")
                    db_payload = state_manager.finalize_results()
                    
                    # Save to Database
                    save_inspection(
                        frame_id=db_payload["frame_id"],
                        model=db_payload["model"],
                        final_result=db_payload["final_result"],
                        bolt_data=db_payload["bolt_data"],
                        images=db_payload["images"]
                    )

                    # If result is NG, send alarm signal to PLC via Modbus Register 2
                    if db_payload["final_result"] == "NG":
                        logger.warning(f"Unit {db_payload['frame_id']} is NG. Triggering PLC Alarm on Register 2.")
                        modbus.send_ng_alarm()

            # 3. Handle Unit Enter/Exit (Exit MUST happen after save)
            if triggers["unit_enter"]:
                logger.info("Unit ENTER signal received.")
                state_manager.system_status["unit_present"] = True
                
            if triggers["unit_exit"]:
                logger.info("Unit EXIT signal received. Resetting state.")
                state_manager.reset()

            time.sleep(0.1) # Prevent CPU hogging
            
        except Exception as e:
            logger.error(f"Error in control loop: {e}")
            time.sleep(1)

# Startup and Shutdown logic now handled by lifespan asynccontextmanager above.

# --- Endpoints ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We fetch state and send only to THIS connection.
            # manager.broadcast_state() was redundant and N^2 complex.
            state = state_manager.get_full_state()
            await websocket.send_json(state)
            await asyncio.sleep(0.2) # Faster updates (5fps)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.post("/api/engine/toggle")
async def toggle_engine():
    """Toggle the master start/stop state of the inspection engine."""
    current = state_manager.system_status["engine_active"]
    state_manager.system_status["engine_active"] = not current
    status_text = "RUNNING" if not current else "STOPPED"
    logger.info(f"Engine state toggled to: {status_text}")
    return {"status": "success", "engine_active": not current}

@app.post("/api/export/csv")
async def export_csv():
    """Export the entire inspection database to a timestamped CSV file."""
    filepath, error = export_to_csv()
    if error:
        return {"status": "error", "message": error}
    return {"status": "success", "file": filepath}

@app.post("/api/system/quit")
async def quit_system():
    """Remotely shut down the entire backend service."""
    logger.info("SYSTEM QUIT: Shutdown requested from dashboard.")
    def kill_soon():
        time.sleep(0.5) # Give the web response time to send
        os._exit(0)
    
    threading.Thread(target=kill_soon).start()
    return {"status": "success", "message": "System shutting down..."}

@app.post("/debug/trigger/{signal}")
async def debug_trigger(signal: str):
    """
    Manually trigger a modbus signal for testing.
    Options: unit_enter, unit_exit, capture_step_1, capture_step_2
    """
    if signal in modbus.addresses:
        modbus.set_mock_signal(signal)
        return {"status": "success", "triggered": signal}
    return {"status": "error", "message": "Invalid signal"}

@app.get("/api/history")
async def fetch_history(limit: int = 50):
    """Fetch recent inspection history from database."""
    history = get_history(limit)
    return {"status": "success", "data": history}

@app.get("/api/history/{record_id}")
async def fetch_history_detail(record_id: int):
    """Fetch specific history detail (optional if all data is in list, but good for future expansion)"""
    history = get_history(limit=100) # Quick hack to find it locally. In production, query DB directly by ID.
    for record in history:
        if record["id"] == record_id:
            return {"status": "success", "data": record}
    return {"status": "error", "message": "Record not found"}

# Resolve path to frontend relative to this file
frontend_dir = os.path.join(current_dir, "../frontend")

# Mount historical images. Ensure this is BEFORE the catch-all frontend mount.
history_images_dir = os.path.join(current_dir, "history_images")
app.mount("/history_images", StaticFiles(directory=history_images_dir), name="history_images")

# Mount at root (must be last to not override API routes)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
