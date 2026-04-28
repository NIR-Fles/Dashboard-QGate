# QGate: Final Bolt Inspection Monitoring System

An industrial-grade automated inspection system designed for quality gate (Q-Gate) control. This system utilizes AI (YOLO11 & OCR) to verify bolt presence/tightness and track Frame IDs, communicating directly with a PLC via Modbus TCP.

## 🚀 Features

- **Real-time Monitoring**: Live camera feeds with AI detection overlays (Bolts & Labels).
- **Dual-AI Architecture**:
  - **YOLOv8**: High-speed bolt detection across multiple camera steps.
  - **PaddleOCR**: Automatic extraction of 17-character Frame IDs from stamped metal.
- **Modbus TCP Integration**: 
  - Listens for PLC triggers (Unit Enter/Capture/Exit).
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
- **AI/ML**: Ultralytics (YOLO11), PaddleOCR.
- **Frontend**: Vanilla HTML5, CSS3 (Modern Dark Theme), JavaScript (ES6+).
- **Communication**: WebSockets (Real-time data), Modbus TCP (PLC).

## 📋 Modbus Register Mapping

The system operates as a **Modbus TCP Server** (Default Port: 5020).

### Holding Register 1: PLC → Python (Triggers)
| Value | Action |
|---|---|
| `1` | **Unit Enter**: Initializes new inspection cycle. |
| `2` | **Capture Step 1**: Triggers cameras and YOLO for first set of bolts. |
| `3` | **Capture Step 2**: Triggers cameras, YOLO, and OCR for final validation. |
| `4` | **Unit Exit**: Resets system state for the next unit. |

### Holding Register 2: Python → PLC (Alarms)
| Value | Meaning |
|---|---|
| `1` | **NG Alarm**: Pulse sent for 5 seconds if inspection fails. |
| `0` | **Normal**: Default state. |

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
