# Continuous FOTA Utility (Pure Python Architecture)

## Overview
**Continuous FOTA Utility** is a high-performance Windows desktop application designed for Accolade Telematics Control Units (TCUs / 4G Devices). 
It automates continuous Firmware Over-The-Air (FOTA) testing and upgrading by reading live serial logs, parsing boot packets, synchronizing state/firmware matrices via REST API, and triggering FOTA jobs.

---

## 🛠 Technology Stack
- **UI Framework**: Python 3.10+ & PyQt6
- **Serial Communication**: `pyserial` (`QThread` async log listener)
- **API & HTTP Automation**: `requests` REST client
- **Environment Management**: `python-dotenv`
- **Packaging**: PyInstaller (standalone Windows `.exe`)

---

## 📂 Directory Layout
- `backend/`: Core Python engine modules
  - `api_client.py`: API matrix synchronization & REST POST FOTA triggers
  - `config.py`: Environment configuration loader (`.env`)
  - `extensions.py`: Modular plugin hooks for custom feature additions
  - `firmware_resolver.py`: Version matrix lookup & next upgrade resolution
  - `message_parser.py`: Telemetry parser & VIN regex (`MAT` + 14 chars)
  - `models.py`: Strongly-typed domain models
  - `orchestrator.py`: Main state machine controller
  - `serial_worker.py`: Async PySerial `QThread` listener
- `ui/`: PyQt6 desktop interface
  - `main.py`: Modern dark-theme dashboard & terminal log viewer
  - `styles.py`: Industrial dark theme QSS stylesheet
  - `requirements.txt`: Python dependencies
- `input/`: Synced state & firmware JSON (`servers.json`)
- `output/`: Timestamped FOTA batch manifests
- `results/`: Audit logs (`fota_audit.csv`)
- `tests/`: Automated unit test suite

---

## ⚙️ Configuration (`.env`)
Create a `.env` file in the project root:
```env
PORTAL_URL=http://aepl-tcu4g-qa.accoladeelectronics.com:6102
PORTAL_USER=suraj.bhalerao@accoladeelectronics.com
PORTAL_PASS=79hqelye

SERIAL_PORT=
SERIAL_BAUD=115200

DEFAULT_STATE=DO NOT DELETE
```

---

## 🚀 Execution & Packaging

### Run Application
```powershell
pip install -r ui/requirements.txt
python ui/main.py
```

### Run Unit Tests
```powershell
python -m unittest discover tests/
```

### Build Standalone Executable
```powershell
pyinstaller FOTA_UI.spec
```
Executable output: `dist/Continuous_FOTA_Utility/Continuous_FOTA_Utility.exe`