import asyncio
import logging
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from modbus_handler import get_modbus_handler
from camera_handler import get_camera_handler
from yolo_processor import get_yolo_processor
from state_manager import StateManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

app = FastAPI()

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
SYSTEM_MODE = "MOCK" 
logger.info(f"System Starting in Mode: {SYSTEM_MODE}")

# Global Components
state_manager = StateManager()
modbus = get_modbus_handler(SYSTEM_MODE)
camera = get_camera_handler(SYSTEM_MODE)
yolo = get_yolo_processor(SYSTEM_MODE)

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
            # 1. Read Modbus Triggers
            triggers = modbus.read_triggers()
            
            # Handle Unit Enter/Exit
            if triggers["unit_enter"]:
                logger.info("Unit ENTER signal received.")
                state_manager.system_status["unit_present"] = True
                
            if triggers["unit_exit"]:
                logger.info("Unit EXIT signal received. Resetting state.")
                state_manager.reset()

            # 2. Handle Capture Logic
            if triggers["capture_step_1"] or triggers["capture_step_2"]:
                step = 1 if triggers["capture_step_1"] else 2
                logger.info(f"Capture Step {step} triggered.")
                
                # Capture Frames (All Cameras)
                frames = camera.capture_all()
                
                # Update State with ALL Images for THIS step
                for cam_key, frame in frames.items():
                    state_manager.update_image(cam_key, step, frame)
                
                # Run Detection (Simulate passing frames)
                # We assume yolo detects labels present in the frames 
                detected_bolts = yolo.process(None)
                
                logger.info(f"Detected bolts: {detected_bolts}")
                
                # Update status for detected bolts to OK
                for bolt_id in detected_bolts:
                    state_manager.update_bolt_status(bolt_id, "OK")

                # If Step 2 finished, finalize results (Pending -> NG)
                if step == 2:
                    logger.info("Step 2 finished. Finalizing results.")
                    state_manager.finalize_results()

            time.sleep(0.1) # Prevent CPU hogging
            
        except Exception as e:
            logger.error(f"Error in control loop: {e}")
            time.sleep(1)

# Start Control Loop in Background
@app.on_event("startup")
async def startup_event():
    loop_thread = threading.Thread(target=control_loop, daemon=True)
    loop_thread.start()

@app.on_event("shutdown")
async def shutdown_event():
    camera.release()

# --- Endpoints ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Push updates periodically or on demand?
            # Ideally, the client just listens. 
            # But the server needs to push when state changes.
            # For simplicity, we push every 500ms from here OR rely on frontend polling?
            # Better: let the frontend wait for messages. 
            # We will run a loop here to send state every X ms.
            
            await manager.broadcast_state()
            await asyncio.sleep(0.5) 
            
            # Keep connection alive checking
            # await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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

# --- Serve Frontend (Static Files) ---
import os
from fastapi.staticfiles import StaticFiles

# Resolve path to frontend relative to this file
# This file is in backend/, so frontend is in ../frontend
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(current_dir, "../frontend")

# Mount at root (must be last to not override API routes)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
