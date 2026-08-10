# Continuous FOTA Automation Utility - System & Architecture Guide

## 📖 System Overview

The **Continuous FOTA Automation Utility** is an enterprise-grade Python & PyQt6 desktop automation platform designed for Accolade 4G Telematics / TCU hardware units.

The application continuously monitors serial COM port boot streams, dynamically abstracts device telemetry parameters (`UIN`, `IMEI`, `VIN`, `ICCID`, `Firmware Version`), validates hardware configuration against backend state servers (`servers.json`), re-attaches or triggers FOTA upgrade jobs via REST API endpoints, and tracks download progress to 100% with automated audit logging.

---

## 🏗 System Architecture & Component Design

```
                     ┌──────────────────────────────┐
                     │    PyQt6 Graphical UI App    │
                     │         (ui/app.py)          │
                     └──────────────┬───────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│    SerialWorker     │  │   FotaOrchestrator  │  │    FotaApiClient    │
│(backend/serial_w...)│  │(backend/orchestr...)│  │ (backend/api_cli...)│
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │
           ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│    MessageParser    │  │  FirmwareResolver   │  │ Accolade REST Portal│
│(backend/message_p..)│  │(backend/firmware...)│  │   (HTTPS Endpoints) │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### 1. Root Entry Point (`main.py`)
- Configures global file logging (`logs/fota_activity.log`) and stdout stream handlers.
- Initializes environment configuration loader (`backend.config.Config`).
- Instantiates Qt Application event loop (`QApplication`) and launches main window (`ui.app.MinimalFotaWindow`).

### 2. Graphical User Interface (`ui/app.py` & `ui/widgets.py`)
- **Theme Engine**: Real-time high-contrast Light/Dark mode switcher with custom QSS (`ui/styles.py`).
- **Telemetry Card Bar**: Displays live abstracted fields: `IMEI`, `UIN`, `VIN`, `ICCID`, `CURRENT STATE`, `FIRMWARE`.
- **Interactive Terminal Console**: Embedded high-performance log view supporting keyword search, auto-scroll freeze toggling, AT command execution history, and raw session logging to `logs/terminal_session.log`.
- **Snackbar Alerts**: Floating non-blocking toast notifications for sleep detection and system alerts.

### 3. Asynchronous Serial COM Engine (`backend/serial_worker.py`)
- Operates inside a background `QThread` reading PySerial COM port byte streams.
- **Telemetry Accumulator**: Multi-line boot log parser that aggregates UIN, IMEI, VIN, and Firmware Version across reboot cycles.
- **Sleep & Suspend Monitoring**: Detects sleep / soft shutdown log signals (`[PLA] SLEEP`, `GSM soft shutdown pass`, `synchronized suspend ok`).

### 4. Continuous FOTA Orchestrator (`backend/orchestrator.py`)
- **Strict 5-Field Validation Barrier**: FOTA execution is GATED until all 5 required fields are present:
  1. `UIN` (Valid `ACON...`)
  2. `IMEI` (13-15 digits)
  3. `VIN` (14-18 char alphanumeric chassis ID with numeric digits)
  4. `Firmware Version` (Valid version string, e.g. `5.2.9 5th IP`)
  5. `Selected State` (Selected by user from UI dropdown)
- **Active FOTA Session Detection**: Queries history API (`getFOTADevicesHistory?imei={imei}`). If a FOTA job is already active on the server (`addedToBatch: true`, `isAborted: false`, `attemptCount < 3`), skips posting new API triggers to avoid server aborts and re-attaches monitoring.
- **Session Persistence**: Saves active FOTA state into `results/active_fota.json`.
- **Adaptive API Poller Worker (`FotaApiPollerWorker`)**:
  - Polls API every **10 minutes (600s)** while download progress is `< 95%`.
  - Polls API every **2 minutes (120s)** when progress is `>= 95%` up to `100%`.
  - Monitors `attemptCount` (auto-aborts if `>= 3`) and `pingCount` (download resume counts).
- **Audit Logging**: Automatically records execution records to `results/fota_results.csv` and `results/fota_results.json`.

### 5. REST API Client (`backend/api_client.py`)
- Authenticates against portal endpoint (`/api/user/login`) using credentials loaded from `.env`.
- Synchronizes state server list & firmware IDs into `input/servers.json`.
- Posts manual FOTA trigger requests (`/api/fota/createManualFota`).
- Queries device FOTA execution history (`/api/fota/getFOTADevicesHistory?imei={imei}`).

---

## 🔒 Security & Environment Credentials

All sensitive credentials and API URLs are loaded strictly from `.env` with **zero hardcoded passwords, tokens, or personal emails** in source code files.

Required `.env` Parameters:
```ini
PORTAL_URL=https://aepl-tcu4g-qa.accoladeelectronics.com/login
PORTAL_LOGIN_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/user/login
PORTAL_USER=your_username_here
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

---

## 📂 Output Artifacts & Log Directories

- **`logs/fota_activity.log`**: System terminal and background event log.
- **`logs/terminal_session.log`**: Raw serial COM port log stream.
- **`results/active_fota.json`**: Active FOTA session status.
- **`results/fota_results.csv`**: CSV audit records.
- **`results/fota_results.json`**: JSON audit records.
- **`input/servers.json`**: Local state server & firmware matrix cache.
