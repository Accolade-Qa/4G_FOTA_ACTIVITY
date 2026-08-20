# STANDARD OPERATING PROCEDURE (SOP)

**Document Control Information**  
- **Document ID**: SOP-QA-FOTA-001  
- **Title**: Continuous FOTA Automation Utility — User Interface & System Operating Procedure  
- **Version**: 1.1.0  
- **Effective Date**: August 2026  
- **Target Hardware**: Accolade 4G Telematics / TCU Units (AIS-140 Compliant)  
- **Author**: QA Automation & Hardware Testing Engineering Team  

---

## 1. PURPOSE & SCOPE

This Standard Operating Procedure (SOP) provides exhaustive, step-by-step instructions for operating the **Continuous FOTA Automation Utility**. The utility automates continuous Firmware Over-The-Air (FOTA) testing, serial boot log telemetry abstraction, state matrix validation, and REST API job triggering for Accolade 4G TCU hardware units.

This procedure applies to QA Automation Engineers, Hardware Test Technicians, Embedded Firmware Developers, and Production Staging Personnel.

---

## 2. SYSTEM ARCHITECTURE & THREADING MODEL

The utility is built on a multi-threaded architecture using **PyQt6** and **PySerial** to ensure the User Interface (UI) remains 100% responsive and never freezes during high-volume serial stream reads or network API calls:

```
                                  ┌─────────────────────────────────────────────────────────────┐
                                  │           1. Main GUI Event Loop (PyQt6 UI)                 │
                                  │       (ui/app.py -> MinimalFotaWindow Controller)           │
                                  └──────────────────────────────┬──────────────────────────────┘
                                                                 │
         ┌──────────────────────────────────────┬────────────────┴──────────────────────┬──────────────────────────────────────┐
         ▼                                      ▼                                       ▼                                      ▼
┌──────────────────────────┐         ┌──────────────────────────┐            ┌──────────────────────────┐           ┌──────────────────────────┐
│  2. ApiSyncWorker Thread │         │ 3. SerialWorker Thread   │            │ 4. FotaAsyncTriggerWorker│           │ 5. FotaApiPollerWorker   │
│  (Syncs state matrix from│         │ (Reads live COM port data│            │ (Queries history, handles│           │ (Monitors active FOTA job│
│  API to servers.json)    │         │ & feeds MessageParser)   │            │ 3 statuses, posts POST)  │           │ progress until 100%)     │
└──────────────────────────┘         └──────────────────────────┘            └──────────────────────────┘           └──────────────────────────┘
```

---

## 3. USER INTERFACE (UI) LAYOUT & INTERACTIVE CONTROLS

The user interface is organized into a clean 3-Tab Architecture:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FOTA UTILITY  ● ONLINE (COM5 @ 115200) [Target State: Maharashtra ▾] [Port: COM5 ▾] [↻] [🌙] [Start] │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ 🖥️ Live Serial Console & Control ]   [ 📊 Audit Log History ]   [ 📈 Analytics & Reporting ]   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Header Navigation & Controls Bar
- **Application Title (`FOTA UTILITY`)**: Displays standard workspace header.
- **Online Connection Status Indicator (`● ONLINE (COM5 @ 115200)` / `● OFFLINE`)**: Color-coded indicator displaying real-time serial port connection and baud rate details.
- **Target State Dropdown (`Target State:`)**: Populated dynamically from backend server matrices (e.g., *Maharashtra*, *Bihar*, *Assam*, *Default*). Dictates the server target state for FOTA upgrade resolution.
- **COM Port Selector (`Port:`)**: Lists available hardware serial communication ports discovered on the Windows workstation.
- **Port Refresh Button (`↻`)**: Scans system hardware and updates the COM port dropdown (`Ctrl+R`).
- **Theme Switcher (`🌙` / `☀️`)**: Toggles instantly between **Light Theme** and **Cyber-Dark Theme** QSS stylesheets (`Ctrl+T`).
- **Engine Start/Stop Button (`Start` / `Stop`)**: Controls the opening and closing of the COM port connection.

### 3.2 Telemetry Summary Bar (Tab 1)
Displays live abstracted hardware parameters captured from device serial boot logs:
- **IMEI**: 13-15 digit cellular module serial identifier.
- **UIN**: Accolade unique unit identification number (`ACON...`).
- **VIN**: Vehicle chassis identification number.
- **ICCID**: SIM card identification number.
- **CURRENT STATE**: Target server state active for the device.
- **FIRMWARE**: Current active firmware version parsed from device logs (e.g., `5.2.8_REL25`).
- **`Clear Info` Button**: Resets captured telemetry fields and clears the internal log accumulator for a fresh test cycle.

### 3.3 Visual Progress Bar (`QProgressBar`)
- Dedicated visual progress bar configured with 2-decimal precision (`0-100.00%`).
- Smoothly chunk-filled with QSS gradient highlights (`#0284c7` to `#818cf8`) during active FOTA downloads and background status polling.

### 3.4 Enterprise Status Banner Card
Padded status card with dynamic stage badges and color-coded background highlights:
- `📋 SCANNING`: `Fetching history from server...`
- `⚡ IN-PROGRESS`: `FOTA Downloading: 45.20% | Pings: 2 | Attempt 1/3`
- `🎉 COMPLETED`: `100.0% Downloaded & Validated`
- `⛔ ABORTED`: `State server configuration invalid`
- `⚠️ WARNING`: `Version 5.2.8_REL25 not found in servers.json`
- `🌙 DEVICE SLEEP`: `Soft shutdown detected. Monitoring for wake-up boot log...`

### 3.5 Interactive Terminal Console & White Log Output
- Monospace console output rendering serial logs in **pure crisp white text (`#f8fafc`)** against a dark obsidian background in Dark Theme.
- Driven by a high-frequency `QTimer(50ms)` buffer flusher to ensure zero UI rendering freezes.

### 3.6 Command Line & Clear Log Controls
- **AT Command Line (`CommandHistoryLineEdit`)**: Input bar for sending AT commands (`*SET#CRST#1#`) with `Up`/`Down` arrow history ring buffer.
- **`Clear Log` Button**: Single-click button beside the command bar to clear terminal logs (`Ctrl+K` / `Ctrl+L`).

### 3.7 Keyboard Shortcuts Reference
- `Ctrl+K` / `Ctrl+L`: Clear live terminal console.
- `Ctrl+R`: Refresh COM ports list.
- `Ctrl+T`: Toggle between Light Theme and Cyber-Dark Theme.
- `Esc`: Clear AT command input bar text.

---

## 4. AUDIT & ANALYTICS DASHBOARD TABS

### 4.1 Tab 2: Audit Log History (`AuditHistoryTableWidget`)
- **4 Metric Cards**: Real-time summary displaying **TOTAL EXECUTIONS**, **COMPLETED**, **ABORTED / FAILED**, and **SUCCESS RATE %**.
- **Interactive Table**: Sortable data table loading records directly from `results/fota_results.json`.
- **Search & Filter Bar**: Search input (`🔍 Filter by UIN, IMEI, VIN...`) + Status filter dropdown (`COMPLETED`, `ABORTED`, `IN_PROGRESS`, `BLOCKED`).
- **`📥 Export CSV` Button**: Export filtered execution records directly to CSV report files.

### 4.2 Tab 3: Analytics & Reporting (`ReportingAnalyticsTabWidget`)
- **State Server Matrix Distribution**: Table showing execution counts and pass rates per state server.
- **Firmware Version Progression Breakdown**: Tracks version transitions (e.g. `5.2.8_REL25` ➔ `5.2.9_REL05`) and attempt counts.

---

## 5. STANDARD OPERATING PROCEDURE (STEP-BY-STEP EXECUTION)

### Phase 1: Launch & Matrix Sync
1. Launch `Continuos_Fota.exe` (or run `python main.py`).
2. `ApiSyncWorker` will automatically run on startup to sync state matrices from the REST API into `input/servers.json`.

### Phase 2: Serial Engine Connection
1. Select the connected COM port (e.g., `COM5`) from the dropdown.
2. Click **Start**. The status badge updates to **● ONLINE (COM5 @ 115200)** and serial logs stream in white text.

### Phase 3: Telemetry Abstraction & 5-Field Gating
1. Power cycle the TCU unit or send `*SET#CRST#1#` via the command bar.
2. `MessageParser` abstracts UIN (`ACON...`), IMEI, VIN, Firmware Version, and State.
3. Once all 5 fields are captured, the system queries the backend history API (`getFOTADevicesHistory`).

### Phase 4: History Evaluation & 3-Status Execution Logic
- **`Pending` / `In-Progress`**: SKIPS issuing a new API POST call (prevents server job aborts) and re-attaches poller.
- **`Aborted`**: Resolves next target version after aborted target and posts NEW FOTA API trigger.
- **`Completed`**: Resolves next sequential version (`idx + 1`) after completed version and posts NEW FOTA API trigger.

### Phase 5: Live FOTA Polling & Completion
1. Adaptive poller tracks active jobs every 10 mins (`<95%`) or 2 mins (`>=95%`).
2. The visual progress bar updates to 100%, and completion audit logs are persisted to `results/fota_results.csv` and `results/fota_results.json`.

---

## 6. ERROR RECOVERY & TROUBLESHOOTING MATRIX

| Error Condition | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| **Port Failed to Open** | COM port occupied by another app. | Close other apps, press `Ctrl+R` to refresh ports, and click **Start**. |
| **BLOCKED_VERSION_NOT_FOUND** | Version not listed in `input/servers.json`. | Select correct Target State or update `input/servers.json`. |
| **API HTTP 401** | Token expired. | Verify `.env` credentials and restart application. |
| **Attempt Limit (3/3)** | 3 server attempts failed. | Power cycle device, send `*SET#CRST#1#`, and retry. |

---

## 7. BUILDING STANDALONE EXECUTABLE (`Continuos_Fota.exe`)

To package the application into a single standalone Windows `.exe`:
```powershell
pyinstaller --noconfirm --noconsole --onefile --icon="assets/logo.ico" --name "Continuos_Fota" --add-data ".env;." --add-data "input;input" --add-data "assets;assets" --hidden-import PyQt6 --hidden-import serial --hidden-import serial.tools.list_ports --hidden-import requests --hidden-import urllib3 --hidden-import dotenv main.py
```
Executable will be saved at `dist/Continuos_Fota.exe`.
