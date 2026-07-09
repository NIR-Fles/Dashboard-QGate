# Project DevLog: Dashboard QGate (Detailed Chronological Milestones)
* **🏷️ Tags**: `#Project` `#Milestones` `#Changelog` `#Architecture`

---

> 🎯 **Project Evolution Overview**
> From the initial commit to a finalized, air-gapped industrial bolt inspection system. The project evolved from basic UI mockups to a complex dual-AI (YOLO11 + PaddleOCR) architecture integrated directly with factory hardware via Modbus TCP. This document tracks the precise architectural evolution and file modifications across the system's history.

## 📅 2026-05-18
### ⚡ OpenVINO YOLOv11 Acceleration, Thread-Safe Async OCR, and PLC Differential Down Logic
* **OpenVINO Model Optimization (`backend/yolo_processor.py`)**: Migrated the YOLO11 model from standard PyTorch (`best.pt`) to OpenVINO format (`best-p2_openvino_model`). Configured `LATENCY` mode for batch=1 inference on CPU, boosting inference speeds from ~200ms to a blazing fast **16-24ms per frame** (10x performance improvement).
* **Sequential Thread-Safe YOLO Execution**: Reverted multi-threaded YOLO to sequential execution to ensure strict CPU thread safety and prevent any memory contention, while maintaining high speeds due to OpenVINO.
* **Asynchronous Parallel OCR Parsing (`backend/main.py`)**: Moved PaddleOCR inference to a separate background `threading.Thread`. The system now instantly displays Step 2 images on the dashboard with a temporary UUID and updates the Frame ID smoothly via websocket once OCR finishes (~0.5s later), completely decoupling OCR latency from the core inspection loop.
* **Alphanumeric & Astra Honda VIN Pattern Filtering (`backend/ocr_processor.py`)**: Toughened the OCR extraction logic to isolate exactly 17-character alphanumeric codes matching the `MH1` pattern. All casting codes and ambient textual noise (e.g. `13003E32`) are now successfully filtered out.
* **Modbus Holding Register 1 Falling-Edge/Differential Down Integration (`backend/modbus_handler.py`)**: Upgraded `TriggerDataBlock` to support register value `0` and prevent auto-reset when value `4` (Unit Exit) is received. This allows physical PLCs and ModbusPoll to hold value `4` and then write `0` to trigger a perfect falling-edge/differential down reset, matching standard industrial Ladder Diagrams.

### 🛠️ Factory I/O Integration & Sequence Hardening
* **Modbus Coils Simulation (`backend/modbus_handler.py`)**: Added `SensorCoilDataBlock` to support Modbus TCP Coils (Addresses 1, 2, 3) specifically for Factory I/O proximity sensor simulation. The system reads combinations of these 3 sensors to infer the 4 system triggers (Enter, Step 1, Step 2, Exit).
* **Factory I/O Auto-Reset (Coil 4)**: Implemented falling edge detection on Sensor 3. When the unit exits the last sensor, the system dynamically pulses Modbus Coil 4 ON for 1 second. This acts as an output back to Factory I/O to automatically reset the machinery for the next loop.
* **Strict Sequence Validation & Anti-Bouncing (`backend/modbus_handler.py`)**: Elevated the anti-bouncing protection to the global `_on_plc_write` handler. The system now strictly enforces a sequence (1 -> 2 -> 3 -> 4) and rejects out-of-order jumps or double-readings. This protection acts as a universal safeguard, applying to both Factory I/O Coils and direct PLC/ModbusPoll writes to Holding Register 1.
* **Database History Optimization (`backend/database.py`, `backend/main.py`)**: 
  - Increased history retrieval limit from 50 to 1000 to show complete and older data in the dashboard.
  - Implemented `get_inspection_by_id(record_id)` for dynamic SQLite queries by database ID.
  - Eliminated the local search slice hack (limit 100) in `/api/history/{record_id}` endpoint, ensuring reliable retrieval of records no matter how old they are.

## 📅 2026-04-29
### 🛠️ Hardware Reliability & Heartbeat
* **PLC Heartbeat (`backend/modbus_handler.py`)**: Added a background thread to the Modbus server that continuously writes an incrementing counter (0 to 100) to **Holding Register 4** every 1000ms. This acts as a heartbeat signal for the PLC to confirm the Python system is alive and responsive.

## 📅 2026-04-28
### 🛠️ Repository Synchronization & Asset Management
* **AI Model Tracking (`backend/.paddlex/`, `backend/best.pt`)**: Explicitly tracked all offline AI weights. Added `.gitattributes`, `config.json`, and `inference.yml` definitions for Paddle models (UVDoc, PP-OCRv4 mobile/server det/rec) to ensure perfect offline portability. Tracked the 5.5MB YOLO11 `best.pt`.
* **Repo Cleanup (`.gitignore`)**: Untracked the `.vscode/` directory to protect local IDE settings.
* **Folder Preservation (`.gitkeep`)**: Deployed `.gitkeep` files in `csv_export/`, `backend/test_images/`, and `backend/history_images/` to maintain the directory structure on clone without leaking local factory data.

## 📅 2026-04-26
### 🛠️ Data Reporting & PLC Alarm Integration
* **CSV Export (`backend/database.py`, `frontend/main.js`)**: Created `export_to_csv` endpoint (`POST /api/export/csv`) to export the entire inspection database. Dynamically flattens unique bolt statuses into distinct CSV columns, secured behind the Level 1 'admin' passcode.
* **NG Alarm Signaling (`backend/modbus_handler.py`)**: Implemented a bidirectional Modbus feature. `ModbusHandler.send_ng_alarm()` now writes a "1" to **Holding Register 2** upon an NG result, holding it for 5 seconds as an alarm pulse for the PLC, then auto-resetting to "0" via a threaded timer.
* **UI Layout (`frontend/style.css`)**: Adjusted export button layout and reduced bolt list panel width to 650px for larger image previews.

## 📅 2026-04-23
### 🛠️ Safety, Access Control, and Offline Industrialization
* **Air-Gapped Setup (`backend/ocr_processor.py`)**: Localized all assets (SVG logos, fonts) and forced PaddleOCR offline loading via absolute path injection to run without internet.
* **Level 1 Security (`frontend/main.js`)**: Gated critical system controls (Start/Pause, System Quit, Export) behind an `'admin'` passcode prompt.
* **Strict Hardware Ignore (`backend/main.py`)**: Upgraded the control loop to aggressively flush incoming Modbus triggers when the engine is set to "STOPPED", preventing unpredictable motion upon restart.
* **WebSocket Analytics (`frontend/main.js`)**: Injected latency/jitter analytics for research reporting.

## 📅 2026-04-10 to 2026-04-11
### 🛠️ OCR Integration & Modbus Polish
* **PaddleOCR Extraction (`backend/ocr_processor.py`)**: Created a new 103-line processor to dynamically crop the upper camera feed (using YOLO bounds) and read the 17-character stamped Frame ID.
* **Modbus Overhaul (`backend/modbus_handler.py`)**: Major 212-line refactor to optimize Modbus logic. Fixed a critical "echo" error in the PyModbus server by adding a slight delay before auto-resetting the trigger registers.
* **Integration (`backend/main.py`, `backend/yolo_processor.py`)**: Orchestrated the timing between YOLO detection and OCR text extraction.

## 📅 2026-02-28
### 🛠️ Database & History Architecture (MAJOR UPDATE)
* **SQLite Integration (`backend/database.py`)**: Transitioned from transient data to a permanent SQLite database (`inspection_history.db`), adding 89 lines of SQL handling logic.
* **History Dashboard (`frontend/index.html`, `frontend/main.js`, `frontend/style.css`)**: Built the dedicated History Tab. Added over 400 lines of HTML and CSS, and nearly 400 lines of JS to query the database, filter results, and render historical images and bounding boxes for operators.

## 📅 2026-02-24 to 2026-02-25
### 🛠️ AI Vision & Scenario Testing
* **YOLO Setup (`backend/yolo_processor.py`, `backend/camera_handler.py`)**: Implemented actual YOLO inference bounding boxes onto the camera frames to feed back to the frontend dashboard.
* **Logic State (`backend/state_manager.py`)**: Upgraded the internal state machine to handle the multi-step inspection sequence (Enter -> Capture 1 -> Capture 2 -> Exit).

## 📅 2026-01-17
### 🛠️ Python Backend Scaffolding
* **Core Architecture**: Transitioned from static UI to a dynamic application by introducing 5 core Python files:
  - `backend/main.py` (168 lines)
  - `backend/camera_handler.py` (138 lines)
  - `backend/modbus_handler.py` (127 lines)
  - `backend/state_manager.py` (108 lines)
  - `backend/yolo_processor.py` (91 lines)
* **API Foundation**: Setup the baseline FastAPI endpoints and WebSocket streaming to pipe mocked camera data to the frontend.

## 📅 2026-01-12
### 🛠️ Genesis & Mock Prototyping
* **Initial Commit**: Project initialized.
* **Mock Environment**: Built the baseline HTML/CSS/JS dashboard (`frontend/index.html` - 142 lines, `frontend/style.css` - 471 lines, `frontend/main.js` - 87 lines) to simulate real-world data flow before factory hardware arrived.
