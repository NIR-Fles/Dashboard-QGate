# AI Project Context: QGate Final Bolt Inspection

> **AI INSTRUCTION:** Read this file when starting a new session to immediately understand the project architecture, tech stack, and business logic without needing the user to explain past conversations.

## 1. Project Overview
**Name:** Final Bolt Inspection Monitoring System (Dashboard QGate)
**Purpose:** An industrial air-gapped system that uses AI vision (YOLO11 + PaddleOCR) to inspect bolts on manufacturing units. It communicates bidirectionally with a factory PLC via Modbus TCP.

## 2. Tech Stack
- **Backend**: Python 3.10+, FastAPI (API server), PyModbus (PLC comms), SQLite (Database).
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+). No heavy frameworks.
- **AI Models**: 
  - **Ultralytics YOLO11 (OpenVINO optimized)** loaded from `best-p2_openvino_model/` running in batch=1 LATENCY CPU mode (~16-24ms latency per frame).
  - **PaddleOCR** for extracting 17-character Frame IDs, running in a background asynchronous thread to prevent blocking PLC loops.

## 3. Core Architecture & Files
- `backend/main.py`: The heart of the system. Runs the API, the background control loop, handles OCR cropping, and orchestrates inspection finalization.
- `backend/camera_handler.py`: Manages OpenCV video captures (`cv2.VideoCapture`). Supports multiple cameras (e.g., 'upper' and 'lower') and handles reliable frame reading.
- `backend/yolo_processor.py`: Wraps the Ultralytics YOLO11 model (`best.pt`). Responsible for running inference on frames to detect bolts and returning annotated images.
- `backend/ocr_processor.py`: Wraps PaddleOCR. Used during Step 2 to read the 17-character Frame ID from a dynamically cropped region of the 'upper' camera frame.
- `backend/modbus_handler.py`: Runs a Modbus TCP server (Port 5020) in a background thread. Manages custom `TriggerDataBlock` to intercept PLC writes.
- `backend/state_manager.py`: Thread-safe dictionary managing the current state of the machine (engine status, PLC connection, bolt statuses, images).
- `backend/database.py`: Handles saving inspections to `inspection_history.db` and querying history. Also handles CSV export logic.
- `frontend/index.html`: The main dashboard layout, divided into Monitoring (real-time view) and History (database records) tabs.
- `frontend/style.css`: Modern dark theme styling. Includes responsive flexbox layouts and specific UI dimensions (e.g., 650px list panel width).
- `frontend/main.js`: Controls the UI. Polls the backend APIs to refresh dashboard data (images, table, status badges) and handles passcode security.

## 4. Modbus TCP Mapping
The system acts as a **Modbus Server**. The PLC/Factory I/O acts as the Client.

### Coils (Input from Factory I/O Simulation)
Simulates physical sensor logic with edge-detection to infer system triggers:
- `Coil 1`: Photosensor Entry
- `Coil 2`: Photosensor Middle
- `Coil 3`: Photosensor Exit
*Combination Matrix:*
- `[ON, OFF, OFF]` = Unit Enter (1)
- `[ON, ON, OFF]` = Capture Step 1 (2)
- `[OFF, ON, ON]` = Capture Step 2 (3)
- `[OFF, OFF, ON]` = Unit Exit (4)
- `[OFF, OFF, OFF]` = Reset Sequence (0)

### Coils (Output to Factory I/O)
- `Coil 4`: Auto-Reset Pulse. When Sensor 3 turns OFF (unit fully exits), the Python server pulses this coil ON for 1 second to physically reset the Factory I/O machinery sequence.

### Holding Register 1 (Input from PLC to Python)
Triggers system sequences:
- `1` = Unit Enter (Initializes new tracking, auto-resets to `0` after 0.1s)
- `2` = Capture Step 1 (Trigger camera & YOLO, auto-resets to `0` after 0.1s)
- `3` = Capture Step 2 (Trigger camera, YOLO, start async OCR, and finalize inspection, auto-resets to `0` after 0.1s)
- `4` = Unit Exit Armed (Prepares for exit reset. The value **stays `4`** on the register and does not auto-reset)
- `0` = Unit Exit Trigger (When transitioned from `4` to `0`, executes the **falling-edge/differential down** exit action and resets sequence)

*Security/Industrial Note: Both Coils and Holding Register 1 are protected by a global **Strict Sequence Validator**. The system strictly enforces the sequential progression (1 -> 2 -> 3 -> 4 -> 0) and ignores out-of-order jumps or bouncing. Auto-reset to 0 is disabled for 4 to support industrial ladder logic falling edges.*

### Holding Register 2 (Output from Python to PLC)
Alarm signaling:
- `1` = NG Alarm. Python writes this if `final_result` is "NG".
- `0` = Normal. Python auto-resets the alarm back to 0 after 5 seconds.

## 5. Security & Business Logic (Critical Rules)
- **Level 1 Passcode**: Critical frontend buttons (START/PAUSE, QUIT, EXPORT CSV) require the user to input the passcode **`admin`** via a browser prompt.
- **Strict Ignore on Pause**: If the machine state is "STOPPED", the backend control loop flushes/ignores all incoming Modbus triggers. This prevents stale commands from executing when the machine is restarted.
- **CSV Export**: Triggered from the frontend, the backend queries the entire DB, flattens all unique bolt IDs into their own columns, and saves the CSV into `csv_export/`.
- **Asynchronous OCR & VIN Filtering**: OCR crops the 'upper' frame based on YOLO bounds (with 15px margin) and runs on a separate thread to prevent loop blocking. The OCR text parser enforces exactly 17-character alphanumeric length and prioritizes patterns starting with `MH1` (Astra Honda Motor Indonesian VIN) to filter out metallic casting codes or other noise.

## 6. Git & File Management
- Folders `backend/test_images/`, `backend/history_images/`, and `csv_export/` are tracked using `.gitkeep` files, but their contents are ignored via `.gitignore` to prevent uploading local factory data.
- AI assets (`best.pt`, `inspection_history.db`, and `.paddlex/`) are explicitly included in source control for "ready-to-run" portability.
