# STANDARD OPERATING PROCEDURE (SOP)

**Document Control Information**  
- **Document ID**: SOP-QA-FOTA-001  
- **Title**: Continuous FOTA Automation Utility — User Interface & System Operating Procedure  
- **Version**: 1.0.0  
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

The user interface is divided into 5 distinct functional panels:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FOTA UTILITY  ● ONLINE   [Target State: Maharashtra ▾] [Port: COM5 ▾] [↻] [🌙]  [ Start / Stop ] │  <- Header Bar
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ IMEI: 861564069404575  | UIN: ACON4NA... | VIN: MAT... | ICCID: 899... | STATE: Maharashtra      │  <- Telemetry Bar
│ FIRMWARE: 5.2.8_REL25  | [ Clear Info ]                                                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FOTA Status: In-Progress | Progress: 45.20% | Pings: 2 | Attempts: 1/3                            │  <- Status Banner
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ [2026-08-20 22:15:01] [INFO]: Connected to COM5 at 115200 baud                                  │
│ [2026-08-20 22:15:04] [INFO]: Abstracted UIN: ACON4NA202400004575, Version: 5.2.8_REL25          │  <- Terminal Console
│ [2026-08-20 22:15:06] [INFO]: FOTA trigger accepted for ACON4NA202400004575 -> Target 5.2.9... │  (Auto-Scroll)
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ > Type serial/AT command and press Enter (e.g. *SET#CRST#1#)... Use Up/Down arrows  [ Send ]     │  <- Command Line
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Header Navigation & Controls Bar
- **Application Title (`FOTA UTILITY`)**: Displays standard workspace header.
- **Online Connection Status Indicator (`● ONLINE` / `● OFFLINE`)**: Color-coded indicator displaying real-time API authentication and server connectivity status.
- **Target State Dropdown (`Target State:`)**: Populated dynamically from backend server matrices (e.g., *Maharashtra*, *Bihar*, *Assam*, *Default*). Dictates the server target state for FOTA upgrade resolution.
- **COM Port Selector (`Port:`)**: Lists available hardware serial communication ports discovered on the Windows workstation.
- **Port Refresh Button (`↻`)**: Scans system hardware and updates the COM port dropdown.
- **Theme Switcher (`🌙` / `☀️`)**: Toggles instantly between **Light Theme** and **Cyber-Dark Theme** QSS stylesheets.
- **Engine Start/Stop Button (`Start` / `Stop`)**: Controls the opening and closing of the COM port connection.

### 3.2 Telemetry Summary Bar
Displays live abstracted hardware parameters captured from device serial boot logs:
- **IMEI**: 13-15 digit cellular module serial identifier.
- **UIN**: Accolade unique unit identification number (`ACON...`).
- **VIN**: Vehicle chassis identification number.
- **ICCID**: SIM card identification number.
- **CURRENT STATE**: Target server state active for the device.
- **FIRMWARE**: Current active firmware version parsed from device logs (e.g., `5.2.8_REL25`).
- **`Clear Info` Button**: Resets captured telemetry fields and clears the internal log accumulator for a fresh test cycle.

### 3.3 Dynamic Status Message Banner
- Displays real-time operational messages, validation warnings, and live FOTA polling statistics:
  ```text
  FOTA Status: In-Progress | Progress: 45.20% | Pings: 2 | Attempts: 1/3
  ```

### 3.4 Interactive Terminal Console (`InteractiveTerminalConsole`)
- Renders color-formatted serial logs received from the device hardware.
- **Smart Auto-Scroll**: Automatically scrolls down as new serial lines arrive; pauses auto-scroll when the operator manually scrolls up to inspect historical logs.
- **Performance Buffer**: Driven by a high-frequency `QTimer(50ms)` buffer flusher that prevents Qt UI rendering freezes during high-speed serial outputs.

### 3.5 Serial Command Line & History (`CommandHistoryLineEdit`)
- Allows operators to send direct AT commands or configuration strings to the TCU device (e.g., `*SET#CRST#1#` or `AT+CSQ`).
- **Up / Down Arrow Navigation**: Maintains an in-memory history ring buffer allowing operators to cycle through previously executed commands using the Up and Down arrow keys.

### 3.6 Floating Snackbar Toast Notifications (`SnackbarWidget`)
- Displays non-intrusive floating toast alerts in the bottom-right corner during critical background events:
  - `🌙 Device Sleep / Soft Shutdown Detected!`: Triggered automatically when device sleep signals (`[PLA] SLEEP`, `GSM soft shutdown pass`, `synchronized suspend ok`) are detected in serial logs.

---

## 4. PREREQUISITES & ENVIRONMENT CONFIGURATION

### 4.1 Hardware Setup
1. **Accolade 4G TCU Device**: Connected to a regulated 12V / 24V DC power supply (minimum 2A output).
2. **Serial Cable**: USB-to-RS232 / TTL converter cable connected from the PC to the TCU debug port.

### 4.2 Environment Configuration File (`.env`)
Create or verify the `.env` file in the workspace root directory with your QA portal credentials:
```ini
PORTAL_URL=https://aepl-tcu4g-qa.accoladeelectronics.com/login
PORTAL_LOGIN_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/user/login
PORTAL_USER=your_qa_email@accoladeelectronics.com
PORTAL_PASS=your_password_here
USER_ID=64116e41c56760941baea6ac

FETCH_SERVERS_API_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerData?page=1&size=100&search=
FETCH_SERVER_DATA_BY_ID=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerDataByUId?id={id}
FETCH_FOTA_HISTORY_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/fota/getFOTADevicesHistory?imei={imei}
FOTA_TRIGGER_API_URL=https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/fota/createManualFota

SERIAL_PORT=COM5
SERIAL_BAUD=115200
DEFAULT_STATE=Maharashtra
```

---

## 5. STANDARD OPERATING PROCEDURE (STEP-BY-STEP EXECUTION)

### Phase 1: Application Launch & Matrix Sync
1. Launch the utility by executing `Continuos_Fota.exe` (or running `python main.py` in terminal).
2. On startup, `ApiSyncWorker` will automatically run in the background to sync state matrices from the REST API into `input/servers.json`.
3. Verify that the **Target State** dropdown is populated with state names (e.g. *Maharashtra*).

### Phase 2: Serial Engine Connection
1. Select the connected COM port (e.g. `COM5`) from the **Port** dropdown.
2. Ensure the baud rate matches device parameters (`115200`).
3. Click the **Start** button.
4. Verify that the status indicator changes to **● ONLINE** and serial log streams begin appearing in the Terminal Console.

### Phase 3: Telemetry Abstraction & 5-Field Gating
1. Power cycle the TCU unit or send `*SET#CRST#1#` via the command line to generate boot log lines.
2. The `MessageParser` and `TelemetryAccumulator` will abstract the 5 required fields:
   1. **UIN**: Must match `ACON...`
   2. **IMEI**: 13-15 numeric digits
   3. **VIN**: 14-18 alphanumeric chassis ID
   4. **Firmware Version**: Active version (e.g., `5.2.8_REL25`)
   5. **Target State**: Selected state from UI dropdown
3. Once all 5 fields are captured, the Telemetry Summary Bar updates and the system automatically initiates the FOTA trigger workflow.

### Phase 4: History Evaluation & 3-Status Execution Logic
The background worker (`FotaAsyncTriggerWorker`) queries the FOTA History API (`getFOTADevicesHistory?imei={imei}`) and evaluates the **3 Server Statuses**:

```
                               ┌──────────────────────────────────┐
                               │   Fetch FOTA Device History API  │
                               └────────────────┬─────────────────┘
                                                │
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                      ▼                                      ▼
┌──────────────────┐                   ┌──────────────────┐                   ┌──────────────────┐
│  STATUS 1:       │                   │  STATUS 2:       │                   │  STATUS 3:       │
│  PENDING         │                   │  ABORTED         │                   │  COMPLETED       │
└────────┬─────────┘                   └────────┬─────────┘                   └────────┬─────────┘
         │                                      │                                      │
         ▼                                      ▼                                      ▼
┌──────────────────┐                   ┌──────────────────┐                   ┌──────────────────┐
│1. Save active_   │                   │1. Log ABORTED    │                   │1. Log COMPLETED  │
│   fota.json      │                   │   in audit logs  │                   │   in audit logs  │
│2. Log IN_PROGRESS│                   │2. Resolve next   │                   │2. Base = target_ │
│3. Re-attach live │                   │   ver after      │                   │   ver from history│
│   poller worker  │                   │   aborted target │                   │3. Resolve next   │
│4. SKIP NEW POST  │                   │3. Post NEW POST  │                   │   ver (idx + 1)  │
│   TRIGGER CALL   │                   │   API trigger    │                   │4. Post NEW POST  │
└──────────────────┘                   └──────────────────┘                   └──────────────────┘
```

1. **If Status is `Pending` / `In-Progress`**:
   - The task is actively running on the backend server.
   - **The utility SKIPS issuing a new API call** (prevents server task cancellation).
   - Re-attaches background status poller (`FotaApiPollerWorker`).

2. **If Status is `Aborted`**:
   - Reads `abortReason` and logs `ABORTED` in audit files.
   - Calls `resolver.resolve_next_version_after_aborted()` to locate the aborted target in `input/servers.json` and advance to the next available firmware object.
   - Submits a new FOTA REST API trigger (`createManualFota`).

3. **If Status is `Completed`**:
   - Logs `COMPLETED` in audit files.
   - Uses the history item's `targetFirmwareVersion` (e.g. `5.2.8_REL25`) as the base version.
   - Calls `resolver.resolve_next_version()` to match `5.2.8_REL25` in `input/servers.json` and select the **NEXT object in sequence (`idx + 1`)** (e.g. `5.2.9_REL05`).
   - Submits a new FOTA REST API trigger (`createManualFota`) with `ufw = "5.2.9_REL05"`.

### Phase 5: Live FOTA Polling & Completion
1. During active upgrades, `FotaApiPollerWorker` polls status on an adaptive interval:
   - **Every 10 minutes (600s)**: While download `progress < 95%`.
   - **Every 2 minutes (120s)**: When download `progress >= 95%` up to `100%`.
2. Live status, progress percentage, ping count, and attempt count are updated on the UI banner.
3. Upon reaching 100% progress or `deviceFotaCompletionStatus == true`:
   - Writes `COMPLETED` audit record.
   - Updates `results/active_fota.json`.
   - Clears upgrade lock for the next sequential upgrade.

---

## 6. AUDIT LOGGING & RESULTS VERIFICATION

The utility automatically generates and maintains 3 persistent audit files in the `results/` directory:

1. **`results/fota_results.csv`**:
   CSV audit log storing execution records:
   ```csv
   Timestamp,UIN,IMEI,VIN,InitialVersion,TargetVersion,State,Status,Remarks
   2026-08-20 22:15:06,ACON4NA202400004575,861564069404575,MAT00000000000000,5.2.8_REL25,5.2.9_REL05,Maharashtra,IN_PROGRESS,FOTA trigger accepted
   2026-08-20 22:35:12,ACON4NA202400004575,861564069404575,MAT00000000000000,5.2.8_REL25,5.2.9_REL05,Maharashtra,COMPLETED,Downloaded 100% and validated successfully
   ```

2. **`results/fota_results.json`**:
   JSON structured array containing complete historical execution logs.

3. **`results/active_fota.json`**:
   Stores real-time state parameters for the currently active FOTA session (`progress`, `pingCount`, `attemptCount`, `deviceFotaStatus`, `lastUpdated`).

---

## 7. ERROR RECOVERY & TROUBLESHOOTING MATRIX

| Error Message / Condition | Root Cause | Corrective Action |
| :--- | :--- | :--- |
| `Failed to open port COM5: Access is denied` | COM port occupied by another terminal (TeraTerm, PuTTY, RealTERM). | Close all external serial terminal programs, click `↻` to refresh ports, and click **Start**. |
| `BLOCKED_VERSION_NOT_FOUND` | Current device firmware version is not defined under the selected state in `input/servers.json`. | Verify the selected **Target State** in the UI dropdown or update `input/servers.json` with the required version mapping. |
| `API FOTA Trigger Error: HTTP 401` | Expired Bearer authentication token or invalid credentials in `.env`. | Verify `PORTAL_USER` and `PORTAL_PASS` in `.env`. Restart application to re-authenticate. |
| `Attempt count reached limit (3/3)` | Hardware failed to download binary chunks after 3 server attempts. | Power cycle the TCU unit (12V DC), type `*SET#CRST#1#` in the AT command line, press Enter, and re-test. |
| `🌙 Device Sleep / Soft Shutdown Detected!` | Device entered low-power sleep mode or suspend state (`[PLA] SLEEP`). | Non-critical notification. The utility maintains background listener; device will resume monitoring automatically upon wake-up. |

---

## 8. BUILDING STANDALONE EXECUTABLE (`Continuos_Fota.exe`)

To package the application into a single standalone Windows `.exe` executable:

1. Ensure Python 3.10+ and PyInstaller are installed (`pip install pyinstaller`).
2. Run the build command in terminal:
   ```powershell
   pyinstaller --noconfirm --noconsole --onefile --icon="assets/logo.ico" --name "Continuos_Fota" --add-data ".env;." --add-data "input;input" --add-data "assets;assets" --hidden-import PyQt6 --hidden-import serial --hidden-import serial.tools.list_ports --hidden-import requests --hidden-import urllib3 --hidden-import dotenv main.py
   ```
3. The generated executable will be located at `dist/Continuos_Fota.exe`.
