# Continuous FOTA Automation Utility

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt-6.0%2B-green.svg)](https://pypi.org/project/PyQt6/)

Enterprise-grade desktop automation utility for continuous FOTA firmware upgrades, serial boot log telemetry abstraction, and state matrix validation on Accolade 4G Telematics / TCU units.

---

## ⚡ Quick Start Guide

### 1. Installation
Clone the repository and install required dependencies:
```bash
pip install -r requirements.txt
```

### 2. Environment Setup (`.env`)
Create or edit `.env` in the root workspace directory with your credentials:
```ini
PORTAL_URL=https://aepl-tcu4g-qa.accoladeelectronics.com/login
PORTAL_LOGIN_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/user/login
PORTAL_USER=your_username@accoladeelectronics.com
PORTAL_PASS=your_password_here
USER_ID=your_user_id_here

FETCH_SERVERS_API_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerData?page=1&size=100&search=
FETCH_SERVER_DATA_BY_ID=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerDataByUId?id={id}
FETCH_FOTA_HISTORY_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/fota/getFOTADevicesHistory?imei={imei}
FOTA_TRIGGER_API_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/fota/createManualFota

SERIAL_PORT=COM5
SERIAL_BAUD=115200
DEFAULT_STATE=Bihar
```

### 3. Launch Application
```bash
python main.py
```

### 4. Run API Diagnostic Test Script
To test authentication and state server matrix fetch from the REST API:
```bash
python scratch/test_api_sync.py
```

---

## 📂 Project Structure

```text
FOTA_ACTIVITY/
├── main.py                     # Root entry point
├── info.md                     # Comprehensive in-depth architecture guide
├── README.md                   # Quick start & usage guide
├── .env                        # Environment credentials (Git-ignored)
├── requirements.txt            # Python package dependencies
│
├── backend/                    # Core automation & business logic
│   ├── api_client.py           # REST API client (/login, /getServerData, /createManualFota)
│   ├── config.py               # Environment configuration loader (.env)
│   ├── extensions.py           # Plugin & hook extension framework
│   ├── firmware_resolver.py    # Target version resolution against servers.json
│   ├── message_parser.py       # Serial boot log telemetry parser & VIN validator
│   ├── models.py               # Data models (LoginPacketInfo, FotaTriggerPayload, FotaAuditRecord)
│   ├── orchestrator.py         # Lifecycle orchestrator & adaptive poller worker
│   └── serial_worker.py        # Asynchronous PySerial COM reader thread
│
├── ui/                         # PyQt6 User Interface
│   ├── app.py                  # Main window layout, state selector & controls
│   ├── styles.py               # Light & Cyber-Dark QSS theme engine
│   └── widgets.py              # Custom UI widgets (Terminal, Snackbar, ApiSyncWorker)
│
├── input/
│   └── servers.json            # State server matrix & firmware versions cache
│
├── logs/
│   ├── fota_activity.log       # System activity log file
│   └── terminal_session.log    # Raw serial terminal log stream
│
├── results/
│   ├── active_fota.json        # Active running FOTA session persistence
│   ├── fota_results.csv        # Execution audit records (CSV)
│   └── fota_results.json       # Execution audit records (JSON)
│
└── scratch/
    └── test_api_sync.py        # Diagnostic script testing API endpoints
```

---

## 🛠 Key Features

- **Automated Boot Telemetry Abstraction**: Extracts `UIN`, `IMEI`, `VIN`, `ICCID`, and `Firmware Version` across reboot cycles.
- **Strict 5-Field Gating Barrier**: FOTA batch execution is blocked until all 5 required fields (UIN, IMEI, VIN, Firmware Version, Selected State) are validated.
- **Active Session Preservation**: Queries device history before posting API triggers to avoid cancelling in-progress server jobs. Saves state to `results/active_fota.json`.
- **Adaptive Polling Worker**: Polls server status every 10 minutes when `< 95%` progress, and every 2 minutes when `>= 95%` up to completion.
- **Cyber-Dark Theme Engine**: Real-time theme switching between Light and Cyber-Dark modes.
- **Silent Sleep / Soft Shutdown Monitoring**: Detects device sleep states and displays Snackbar toast alerts.


# Build Executable (PyInstaller)
Before building, ensure `input` directory exists by running `python main.py` or creating `input/servers.json`.

```bash
pyinstaller --noconfirm --noconsole --onefile --icon="assets/logo.ico" --name "Continuos_Fota" --add-data ".env;." --add-data "input;input" --add-data "assets;assets" --hidden-import PyQt6 --hidden-import serial --hidden-import serial.tools.list_ports --hidden-import requests --hidden-import urllib3 --hidden-import dotenv main.py
```