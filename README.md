# QGate: Final Bolt Inspection Monitoring System

An industrial-grade automated inspection system designed for quality gate (Q-Gate) control. This system utilizes AI (YOLO11 & OCR) to verify bolt presence/tightness and track Frame IDs, communicating directly with a PLC via Modbus TCP.

## 🚀 Features

- **Real-time Monitoring**: Live camera feeds with AI detection overlays (Bolts & Labels).
- **Dual-AI Architecture**:
  - **YOLO11 (OpenVINO CPU Optimized)**: Ultra-high-speed bolt detection (~16-24ms per frame, 10x speedup).
  - **PaddleOCR (Thread-Safe Async Background Thread)**: Non-blocking automatic extraction of 17-character Frame IDs, decoupled from the core PLC trigger loop.
- **Modbus TCP Integration**: 
  - Listens for PLC triggers (Unit Enter/Capture/Exit/Reset).
  - Sends active alarm signals back to PLC on "NG" results.
- **History & Analytics**:
  - SQLite database storage for all inspection records.
  - Detailed history view with high-resolution image crops.
  - **CSV Export**: One-click data export for research and Excel analysis.
- **Industrial Safety**:
  - "Strict Ignore" logic during Pause mode to prevent accidental triggers.
  - Admin Passcode protection for critical operations.

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, PyModbus, SQLite.
- **AI/ML**: Ultralytics YOLO11 (OpenVINO format), PaddleOCR.
- **Frontend**: Vanilla HTML5, CSS3 (Modern Dark Theme), JavaScript (ES6+).
- **Communication**: WebSockets (Real-time data), Modbus TCP (PLC).

## 📋 Modbus Register Mapping

The system operates as a **Modbus TCP Server** (Default Port: 5020).

### Holding Register 1: PLC → Python (Triggers)
| Value | Action |
|---|---|
| `1` | **Unit Enter**: Initializes new inspection cycle. Auto-resets to `0` after 0.1s. |
| `2` | **Capture Step 1**: Triggers cameras and YOLO for first set of bolts. Auto-resets to `0` after 0.1s. |
| `3` | **Capture Step 2**: Triggers cameras, YOLO, and starts async OCR for final validation. Auto-resets to `0` after 0.1s. |
| `4` | **Unit Exit Armed**: Prepares system for reset. The value **stays `4`** on the register and does not auto-reset. |
| `0` | **Unit Exit Trigger**: Executes the **falling-edge / differential down** reset action when transitioned from `4` to `0`. |

### Holding Register 2: Python → PLC (Alarms)
| Value | Meaning |
|---|---|
| `1` | **NG Alarm**: Pulse sent for 5 seconds if inspection fails. |
| `0` | **Normal**: Default state. |

### Coils 1-3: Factory I/O Proximity Sensors (Inputs)
The system listens to Modbus TCP Coils (Addresses 1, 2, and 3) to simulate a physical conveyor line in **Factory I/O** (Mode: Modbus TCP Client):
- **Coil 1 (Address 1)**: Photosensor Entry
- **Coil 2 (Address 2)**: Photosensor Middle
- **Coil 3 (Address 3)**: Photosensor Exit

**Sensor Combination Logic (Ladder-Logic Style):**
- `[ON, OFF, OFF]` $\rightarrow$ **Trigger 1**: Unit Enter (Unit enters the conveyor)
- `[ON, ON, OFF]` $\rightarrow$ **Trigger 2**: Capture Step 1 (Trigger Camera 1 + YOLO)
- `[OFF, ON, ON]` $\rightarrow$ **Trigger 3**: Capture Step 2 (Trigger Camera 2 + YOLO + OCR, and save to DB)
- `[OFF, OFF, ON]` $\rightarrow$ **Trigger 4**: Unit Exit (Unit exits the conveyor)
- `[OFF, OFF, OFF]` $\rightarrow$ **Reset (0)**: Conveyor is empty / Ready for the next unit

### Coil 4: Factory I/O Sequence Auto-Reset (Output)
- **Coil 4 (Address 4)**: Python dynamically pulses this coil **ON** for 1 second when Sensor 3 turns OFF (detecting a falling edge). You can bind this coil to a physical reset switch/mechanism inside Factory I/O to automatically restart the machinery sequence.

---

## 🛡️ Strict Sequence & Anti-Bouncing Protection
To ensure reliable operation in noise-heavy industrial environments, the system features a robust global sequence guard:
- **Anti-Bouncing (Flicker Prevention)**: Prevents redundant double-triggers if physical sensors flicker or bounce rapidly.
- **Strict Sequence (1 -> 2 -> 3 -> 4)**: The system strictly enforces the sequential step progression. Out-of-order jumps (e.g., skipping from Step 1 directly to Step 3) are automatically ignored to prevent data corruption.
- **Safe Reset**: If a unit is manually lifted off the conveyor halfway, the sensor state `[OFF, OFF, OFF]` triggers a safe reset (`0`), making the system ready to accept a new unit from the beginning.
- **Universal Guard**: This sequence protection is enforced **globally** inside the core server. It validates inputs coming from both **Factory I/O Coils** and direct **Holding Register 1** writes (via hardware PLCs or diagnostic tools like **ModbusPoll**).

### 🔌 Manual Testing via API (Bypass Mode)
For development and debugging without a physical PLC or simulation client, you can trigger the inspection stages directly via HTTP POST endpoints. 

*Note: Since these endpoints are designed for software-level debugging (e.g., testing isolated camera views or AI models), they **bypass** the strict Modbus sequence validation, allowing you to trigger any step instantly at any time.*

Run these triggers from your terminal using `curl`:

* **Initialize Unit Enter:**
  ```bash
  curl -X POST http://localhost:8000/debug/trigger/unit_enter
  ```
* **Trigger Capture Step 1 (Upper & Lower Cameras + YOLO):**
  ```bash
  curl -X POST http://localhost:8000/debug/trigger/capture_step_1
  ```
* **Trigger Capture Step 2 (Cameras + YOLO + PaddleOCR + Save to DB):**
  ```bash
  curl -X POST http://localhost:8000/debug/trigger/capture_step_2
  ```
* **Trigger Unit Exit (Reset Dashboard State):**
  ```bash
  curl -X POST http://localhost:8000/debug/trigger/unit_exit
  ```

---

## 🔐 Security

The following actions are protected by a passcode (Default: `admin`):
- Start / Pause Machine
- System Shutdown (Quit)
- CSV Data Export

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "Dashboard QGate"
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure Cameras**:
   Edit `backend/camera_handler.py` to set your RTSP or USB camera indices.

## 🚦 How to Run

1. **Start the Backend**:
   ```bash
   python backend/main.py
   ```
   The server will start on `http://localhost:8000`.

2. **Open the Dashboard**:
   Open `frontend/index.html` in any modern web browser.

## 📂 Project Structure

- `backend/`: Python server, Modbus logic, AI processors.
- `frontend/`: Dashboard UI (HTML/CSS/JS).
- `csv_export/`: Generated data reports.
- `inspection_history.db`: SQLite database file.

---
**Developed for Advanced Industrial Quality Control.**
