# STANDARD OPERATING PROCEDURE (SOP)

**Document Control Information**  
- **Document ID**: SOP-QA-FOTA-001  
- **Title**: Continuous FOTA Automation Utility — User Interface & System Operating Procedure  
- **Version**: 2.0.0  
- **Effective Date**: August 2026  
- **Target Hardware**: Accolade 4G Telematics / TCU Units (AIS-140 Compliant)  
- **Author**: QA Automation & Hardware Testing Engineering Team  

---

## 1. PURPOSE & SCOPE

This Standard Operating Procedure (SOP) provides exhaustive, step-by-step instructions for operating the **Continuous FOTA Automation Utility**. The utility automates continuous Firmware Over-The-Air (FOTA) testing, serial boot log telemetry abstraction, 10-stage progression validation, state matrix verification, and REST API job triggering for Accolade 4G TCU hardware units.

This procedure applies to QA Automation Engineers, Hardware Test Technicians, Embedded Firmware Developers, and Production Staging Personnel.

---

## 2. SYSTEM ARCHITECTURE & THREADING MODEL

The utility is built on a multi-threaded architecture using **PyQt6** and **PySerial** to ensure the User Interface (UI) remains 100% responsive and never freezes during high-volume serial stream reads or network API calls:

```text
                                  ┌─────────────────────────────────────────────────────────────┐
                                  │           1. Main GUI Event Loop (PyQt6 UI)                 │
                                  │       (ui/app.py -> MinimalFotaWindow Controller)           │
                                  └──────────────────────────────┬──────────────────────────────┘
                                                                 │
         ┌──────────────────────────────────────┬────────────────┴──────────────────────┬──────────────────────────────────────┐
         ▼                                      ▼                                       ▼                                      ▼
┌──────────────────────────┐         ┌──────────────────────────┐            ┌──────────────────────────┐           ┌──────────────────────────┐
│  2. ApiSyncWorker Thread │         │ 3. SerialWorker Thread   │            │ 4. FotaAsyncTriggerWorker│           │ 5. FotaApiPollerWorker   │
│  (Syncs state matrix from│         │ (Reads live COM port data│            │ (Queries history, handles│           │ (Adaptive polling: 60s   │
│  API to servers.json)    │         │ & feeds MessageParser)   │            │ 3 statuses, posts POST)  │           │ <95%, 2s >=95%)          │
└──────────────────────────┘         └──────────────────────────┘            └──────────────────────────┘           └──────────────────────────┘
```

---

## 3. USER INTERFACE (UI) LAYOUT & INTERACTIVE CONTROLS

The user interface is organized into a clean 3-Tab Architecture with integrated 10-Stage Progression Bar:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FOTA UTILITY  ● ONLINE (COM5 @ 115200)                             Target State: [ Maharashtra ▾ ]   Port: [ COM5 ▾ ]  [↻]  [🌙]  [ Stop ]  │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ 🖥️ Live Serial Console & Control ]   [ 📊 Audit Log History ]   [ 📈 Analytics & Reporting ]                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ IMEI: 861564069210428  | UIN: ACON4NA... | VIN: ACC... | ICCID: 899... | CURRENT STATE: Maharashtra | FIRMWARE: 5.2.9 -> 5.2.12 [Clear Info] │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FOTA Download Progress: 100.00% [=========================================================================================================] │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [S1: Telemetry]  [S2: Servers Matrix]  [S3: Progress]  [S4: Audit]  [S5: 100% Download]  [S6: Reboot]  [S7: IP1]  [S8: IP2]  [S9: OTA]  [S10: Config]│
│   ✓ PASSED          ✓ PASSED             ✓ PASSED        ✓ PASSED      ✓ PASSED          ✓ PASSED      ✓ PASSED   ✓ PASSED   ✓ PASSED    ✓ PASSED   │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚡ IN-PROGRESS | FOTA Downloading: 100.00% | Status: In-Progress                                                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [2026-08-21 19:03:22.519] INFO:  [FOT] tcp ota response: STATUS#CLR#FOTA#OK#861564069210428,                                                │
│ [2026-08-21 19:03:22.519] DEBUG: [CVP] MQTT is disconnecting from GSM soft shutdown pass                                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ > Type serial/AT command and press Enter (e.g. *SET#CRST#1#)...                                                 [ Send Command ] [ Clear ]  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Header Controls Bar
- **Application Title (`FOTA UTILITY`)**: Standard workspace header.
- **Connection Status (`● ONLINE (COM5 @ 115200)` / `● OFFLINE`)**: Real-time connection status.
- **Target State Dropdown (`Target State:`)**: Dynamic server target state selector (*Maharashtra*, *Bihar*, *Assam*, *Default*).
- **COM Port Selector (`Port:`)**: Discovered workstation serial ports.
- **Port Refresh Button (`↻`)**: Scans hardware serial ports (`Ctrl+R`).
- **Theme Switcher (`🌙` / `☀️`)**: Toggles Light / Cyber-Dark Theme QSS (`Ctrl+T`).
- **Engine Start/Stop Button (`Start` / `Stop`)**: Connects/disconnects COM port connection.

### 3.2 Telemetry Summary Bar (Tab 1)
Displays live abstracted hardware parameters captured from device serial boot logs:
- **IMEI**: 13-15 digit cellular module serial identifier.
- **UIN**: Accolade unique unit identification number (`ACON...`).
- **VIN**: Vehicle chassis identification number.
- **ICCID**: SIM card identification number.
- **CURRENT STATE**: Target server state active for the device.
- **FIRMWARE**: Current active firmware version parsed from device logs (e.g., `5.2.9 5th IP`).
- **`Clear Info` Button**: Resets captured telemetry fields.

### 3.3 Visual Progress Bar (`QProgressBar`)
- Dedicated visual progress bar configured with 2-decimal precision (`0-100.00%`).
- Gradient highlights (`#46b023` to `#70e846`).
- Real-time updates driven by direct serial log parsing (`[FOT] downloading XX.XX%`) and background REST API polling.

### 3.4 10-Stage Progression Bar Widget (`StageProgressionWidget`)
Dedicated visual widget displaying 10 sequential execution stage badges with color-coded status badges (`WAITING` ⏱, `RUNNING` ⚡, `PASSED` ✓, `FAILED` ✕):
1. `S1: Telemetry Params`: Abstraction of UIN, IMEI, VIN, Version, State.
2. `S2: Servers Matrix`: Validation against `input/servers.json` metadata.
3. `S3: Progress Sync`: FOTA history scanned & active tracking attached.
4. `S4: Audit Report`: Persistence into CSV, JSON, and session logs.
5. `S5: 100% Downloaded`: Download percentage reaches 100.00%.
6. `S6: Device Reboot`: Post-download reboot/reset log line verification (120s window).
7. `S7: State OTA Fired`: SWEMP State Enabled OTA verification (`STATUS#SET#SWEMP#...#OK#`). *If already set on device, logs `ALREADY SET`, displays `✓ ALREADY SET` on badge card, and passes stage immediately without waiting. If not in `servers.json`, displays `🚫 NOT PRESENT`.*
8. `S8: IP1 & Port Set`: Primary Server CHTP verification (`STATUS#SET#CHTP#...#OK#`). *If log shows `255.255.255.255:65535` unconfigured state, waits for set response. If actual IP is already configured on device, logs `ALREADY SET`, displays `✓ ALREADY SET` on badge card, and passes stage immediately.*
9. `S9: IP2 & Port Set`: Secondary Server CIP1 verification (`STATUS#SET#CIP1#...#OK#`). *If log shows `255.255.255.255:65535` unconfigured state, waits for set response. If actual IP is already configured on device, logs `ALREADY SET`, displays `✓ ALREADY SET` on badge card, and passes stage immediately.*
10. `S10: Config Verified`: Post-upgrade config integrity vs pre-upgrade snapshot & 55AA Login Packet version match.

### 3.5 Enterprise Status Banner Card
Dynamic stage card with background highlights:
- `📋 SCANNING`: `Fetching history from server...`
- `⚡ IN-PROGRESS`: `FOTA Downloading: 45.20% | Pings: 2 | Attempt 1/3`
- `🎉 COMPLETED`: `100.0% Downloaded & Validated`
- `⛔ ABORTED`: `State server configuration invalid`
- `⚠️ WARNING`: `Version 5.2.8_REL25 not found in servers.json`
- `🌙 DEVICE SLEEP`: `Soft shutdown detected. Monitoring for wake-up boot log...`

### 3.6 Dual Continuous Logging System
- **Master Log Stream (`logs/terminal_session.log`)**: Continuously records all terminal session output (never stops).
- **Session Dedicated Log (`logs/{IMEI}_{REL_FETCHED}_TO_{REL_UPDATE}.log`)**: Generated per device FOTA run with millisecond timestamps (`[YYYY-MM-DD HH:MM:SS.fff]`).

### 3.7 Keyboard Shortcuts Reference
- `Ctrl+K` / `Ctrl+L`: Clear live terminal console.
- `Ctrl+R`: Refresh COM ports list.
- `Ctrl+T`: Toggle between Light Theme and Cyber-Dark Theme.
- `Esc`: Clear AT command input bar text.

---

## 4. AUDIT & ANALYTICS DASHBOARD TABS

### 4.1 Tab 2: Audit Log History (`AuditHistoryTableWidget`)
- **4 Metric Cards**: Displays **TOTAL EXECUTIONS**, **COMPLETED**, **ABORTED / FAILED**, and **SUCCESS RATE %**.
- **Dark Yellow Status (`#d97706`)**: Highlights `IN_PROGRESS` runs cleanly in dark yellow text.
- **Interactive Table**: Sortable table loading from `results/fota_results.json`.
- **`📥 Export CSV` Button**: Exports filtered audit entries to CSV.

### 4.2 Tab 3: Analytics & Reporting (`ReportingAnalyticsTabWidget`)
- **State Server Matrix Distribution**: Execution counts and pass rates per state server.
- **Firmware Version Progression Breakdown**: Tracks version transitions and attempt counts.
- **`📥 Export CSV` Button**: Exports combined state distribution matrix and version progression breakdown report to CSV (`results/fota_analytics_report.csv`).

### 4.3 Tab 4: Login Packets (`LoginPacketsTableWidget`)
- **Real-Time Login Packet Capture**: Automatically records every login packet received from serial logs (`55AA` GSM_TX packets or key-value login packets).
- **Detailed Table Columns**: `#` (Sequential Record Number), `Date Time` (Millisecond timestamp), `IMEI`, `UIN`, `VIN`, `Version`, and `Raw Login Packet`.
- **`📥 Export CSV` Button**: Exports all captured login packet records to CSV files (`results/login_packets.csv`).

---

## 5. STANDARD OPERATING PROCEDURE (STEP-BY-STEP EXECUTION)

```text
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                            1. PRE-START VERIFICATION                             │
 │            Listen for: STATUS#CLR#FOTA#OK#{IMEI} in serial log stream            │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                        2. STAGE 1: TELEMETRY PARSING                             │
 │           Parse UIN, IMEI, VIN, Version, State + Save Pre-Upgrade Snapshot        │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                       3. STAGE 2: SERVERS MATRIX CHECK                           │
 │     Validate current version in servers.json & extract CHTP, CIP1, SWEMP params  │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                    4. STAGE 3 & STAGE 4: SYNC & AUDIT REPORT                     │
 │     Scan history (Pending -> Track; Manual Abort -> Retry from active log version;│
 │     System Abort -> Advance past aborted target; Completed -> Advance next ver) │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                        5. STAGE 5: 100% DOWNLOADED                               │
 │   Parse real-time [FOT] downloading 100.00% log line or API poller 100% progress │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                   6. STAGE 6: DEVICE REBOOT (120s Window)                        │
 │  Listen for: "synchronized suspend ok", "GSM soft shutdown pass", "MQTT disconnect"│
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                 7. STAGE 9: SWEMP STATE ENABLED OTA VERIFIED                     │
 │  Listen for: STATUS#SET#SWEMP#<state>#OK# & match stateEnable in servers.json    │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │               8. STAGE 7: PRIMARY SERVER CHTP IP1 & PORT1 VERIFIED               │
 │  Listen for: STATUS#SET#CHTP#<ip>#<port>#OK# & match govtIp1/port1 in servers.json│
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │              9. STAGE 8: SECONDARY SERVER CIP1 IP2 & PORT2 VERIFIED              │
 │  Listen for: STATUS#SET#CIP1#<ip>#<port>#OK# & match govtIp2/port2 in servers.json│
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          ▼
 │                    10. STAGE 10: CONFIG & 55AA VERSION VERIFIED                │
 │    Validate post-upgrade firmware version from 55AA Login Packet (idx 7 == target)│
 │    & compare telemetry vs snapshot ➔ Mark overall flow COMPLETED ➔ Next Trigger  │
 └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. ERROR RECOVERY & TROUBLESHOOTING MATRIX

| Error Condition | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| **Port Failed to Open** | COM port occupied by another app. | Close other apps, press `Ctrl+R` to refresh ports, and click **Start**. |
| **BLOCKED_VERSION_NOT_FOUND** | Version not listed in `input/servers.json`. | Select correct Target State or update `input/servers.json`. |
| **API HTTP 401** | Token expired. | Verify `.env` credentials and restart application. |
| **Aborted Status Received** | Server manually aborted run. | Engine automatically resets progress bar to `0.00%`, logs CSV/JSON audit, and re-initiates FOTA request. |
| **Attempt Limit (3/3)** | 3 server attempts failed. | Power cycle device, send `*SET#CRST#1#`, and retry. |

---

## 7. BUILDING STANDALONE EXECUTABLE (`Continuos_Fota.exe`)

To package the application into a single standalone Windows `.exe`:
```powershell
pyinstaller --noconfirm --noconsole --onefile --icon="assets/logo.ico" --name "Continuos_Fota" --add-data ".env;." --add-data "input;input" --add-data "assets;assets" --hidden-import PyQt6 --hidden-import serial --hidden-import serial.tools.list_ports --hidden-import requests --hidden-import urllib3 --hidden-import dotenv main.py
```
Executable will be saved at `dist/Continuos_Fota.exe`.
