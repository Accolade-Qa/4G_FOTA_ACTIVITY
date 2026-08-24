<style>
  @page {
    size: A4 portrait;
    margin: 15mm 12mm 15mm 12mm;
    @bottom-right {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #475569;
    }
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #0f172a;
    line-height: 1.45;
    font-size: 9.5pt;
  }

  h1, h2, h3, h4 {
    color: #0f172a;
    font-weight: 700;
    page-break-after: avoid;
  }

  h1 { font-size: 16pt; margin-top: 0; margin-bottom: 8px; border-bottom: 2px solid #0f172a; padding-bottom: 4px; }
  h2 { font-size: 12pt; margin-top: 18px; margin-bottom: 8px; border-bottom: 1px solid #94a3b8; padding-bottom: 3px; background-color: #f1f5f9; padding-left: 6px; }
  h3 { font-size: 10pt; margin-top: 12px; margin-bottom: 6px; color: #1e293b; }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    margin-bottom: 12px;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }

  th {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 6px 8px;
    border: 1px solid #0f172a;
  }

  td {
    padding: 5px 8px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
  }

  tr:nth-child(even) td {
    background-color: #f8fafc;
  }

  .sop-header-table th, .sop-header-table td {
    border: 1px solid #0f172a !important;
  }

  code {
    font-family: "Consolas", "Courier New", monospace;
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 8pt;
  }

  pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 10px;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8pt;
    line-height: 1.35;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin-top: 6px;
    margin-bottom: 12px;
    page-break-inside: avoid;
  }

  .box-info {
    background-color: #eff6ff;
    border-left: 4px solid #2563eb;
    padding: 8px 12px;
    margin: 10px 0;
    font-size: 8.5pt;
  }

  .box-warning {
    background-color: #fffbeb;
    border-left: 4px solid #d97706;
    padding: 8px 12px;
    margin: 10px 0;
    font-size: 8.5pt;
  }

  .box-danger {
    background-color: #fef2f2;
    border-left: 4px solid #dc2626;
    padding: 8px 12px;
    margin: 10px 0;
    font-size: 8.5pt;
  }

  .page-break {
    page-break-after: always;
    break-after: page;
  }

  .badge-pass { color: #15803d; font-weight: bold; }
  .badge-fail { color: #b91c1c; font-weight: bold; }
  .badge-warn { color: #b45309; font-weight: bold; }
  .badge-info { color: #1d4ed8; font-weight: bold; }
</style>

<!-- CORPORATE SOP HEADER BLOCK -->
<table class="sop-header-table" style="margin-bottom: 15px;">
  <tr>
    <td rowspan="4" width="22%" align="center" style="vertical-align: middle; background-color: #0f172a; color: #ffffff; font-weight: bold; font-size: 16pt;">
      AEPL
    </td>
    <td colspan="2" align="center" style="font-size: 12pt; font-weight: bold; background-color: #e2e8f0; color: #0f172a;">
      STANDARD OPERATING PROCEDURE
    </td>
    <td width="28%" style="font-size: 8.5pt;">
      <b>SOP No:</b> AEPL/SOP/QA/FOTA-001<br>
      <b>Rev No:</b> 2.0.0
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" style="font-size: 10.5pt; font-weight: bold;">
      CONTINUOUS FOTA AUTOMATION UTILITY — USER & OPERATOR MANUAL
    </td>
    <td style="font-size: 8.5pt;">
      <b>Effective Date:</b> 24-08-2026<br>
      <b>Review Date:</b> 24-08-2027
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center" style="font-size: 8.5pt;">
      <b>DEPARTMENT:</b> QUALITY ASSURANCE & TESTING ENGINEERING
    </td>
    <td style="font-size: 8.5pt;">
      <b>Target Device:</b> Accolade 4G TCU (AIS-140)
    </td>
  </tr>
</table>

## 1.0 UTILITY OVERVIEW & PURPOSE

### 1.1 What is the FOTA Automation Utility?
The **Continuous FOTA Automation Utility** is a desktop application designed for testing and validating **Firmware Over-The-Air (FOTA)** updates on **Accolade 4G Telematics / TCU Units (AIS-140 compliant)**. 

Instead of manually typing commands, monitoring terminal logs for hours, and tracking firmware updates by hand, this utility connects directly to your device via a USB-to-Serial cable and automates the entire process:
- **Captures Device Telemetry**: Automatically reads IMEI, UIN, VIN, ICCID, active state, and current firmware version from boot logs.
- **Automates FOTA Upgrades**: Resolves firmware versions, triggers upgrade jobs on the server, and tracks download progress in real-time.
- **10-Stage Progression Bar**: Shows a visual 10-card pipeline (`S1` through `S10`) indicating exactly which stage the device is in.
- **Verifies State & IP Configurations**: Checks whether state server settings (`*GET#SWEMP#`, `*GET#CHTP#`, `*GET#CIP1#`) match target server matrix rules.
- **Logs & Exports Results**: Records full audit logs, login packet histories, and enables single-click **Export CSV** reporting.

---

## 2.0 PREREQUISITES & PRE-START HARDWARE SETUP

Before launching the utility, ensure your test bench hardware is physically connected and powered correctly.

### 2.1 Required Equipment
1. **Workstation PC**: Windows 10 or 11 (64-bit).
2. **Target Device**: Accolade 4G TCU Unit (AIS-140 Compliant).
3. **Power Supply**: DC Power Supply (`12V` or `24V DC`, minimum `2A` output).
4. **USB-to-Serial Converter Cable**: FTDI, Prolific, or CH340 USB-Serial Cable connected to the TCU debug serial port (TX/RX/GND).
5. **SIM Card & Antennas**: Active cellular SIM card inserted, with 4G LTE and GNSS (GPS) antennas connected.

```text
 ┌─────────────────┐       +12V / GND Power      ┌──────────────────────────────┐
 │ Regulated DC    ├────────────────────────────►│ Accolade 4G TCU Unit (DUT)   │
 │ Power Supply    │                             │ (AIS-140 Compliant)          │
 └─────────────────┘                             └──────────────┬───────────────┘
                                                                │ Serial Debug Cable
                                                                ▼ (TX / RX / GND)
 ┌─────────────────┐       USB Connection        ┌──────────────┴───────────────┐
 │ Workstation PC  │◄────────────────────────────┤ USB-to-Serial Adapter Cable  │
 │ (FOTA Utility)  │                             │ (FTDI / CH340 / Prolific)    │
 └─────────────────┘                             └──────────────────────────────┘
```

<div class="box-warning">
  <b>HARDWARE HANDLING PRECAUTIONS:</b>
  <ol style="margin:4px 0; padding-left: 20px;">
    <li><b>ESD Protection:</b> Wear an Anti-Static Electrostatic Discharge (ESD) wrist strap when touching bare TCU circuit boards.</li>
    <li><b>Power Supply Polarity:</b> Verify +12V/24V (Red) and GND (Black) before turning on the power supply.</li>
    <li><b>Close Other Serial Terminals:</b> Close TeraTerm, PuTTY, RealTerm, or Arduino Serial Monitor before opening the FOTA Utility.</li>
  </ol>
</div>

---

<div class="page-break"></div>

## 3.0 CONFIGURATION FILES & INITIAL SETUP

The utility uses two configuration files located in your application folder: `.env` and `input/servers.json`.

### 3.1 `.env` File (Application Credentials & Settings)
Located in the main application root folder. Ensure the following parameters are configured:

```ini
# Server API Connection Settings
API_BASE_URL=https://api.accolade-telematics.com
API_USER=your_qa_username
API_PASS=your_qa_password

# Serial Communication Default Baud Rate
SERIAL_BAUD=115200
```

### 3.2 `input/servers.json` File (State Server Matrix)
Located in the `input/` folder. This file contains server IP addresses, state abbreviations, state OTA enable strings, and available firmware versions per state:

```json
[
  {
    "state": "Maharashtra",
    "stateAbbreviation": "MH",
    "govtIp1": "103.211.218.66",
    "govtPort1": "8086",
    "govtIp2": "103.211.218.67",
    "govtPort2": "8086",
    "stateEnable": "STATUS#SET#SWEMP#1#OK#",
    "firmwares": ["5.2.8_REL25", "5.2.9_REL25", "5.2.12_REL25"]
  }
]
```

<div class="box-info">
  <b>Automatic Matrix Sync:</b> The utility automatically syncs <code>input/servers.json</code> with the live server API whenever the application launches. You can also edit <code>servers.json</code> manually if working offline.
</div>

---

<div class="page-break"></div>

## 4.0 USER INTERFACE (UI) & OPERATOR CONTROL GUIDE

The user interface is designed for high visibility and single-click operation.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FOTA UTILITY  ● ONLINE (COM5 @ 115200)             Target State: [ Maharashtra ▾ ]  Port: [ COM5 ▾ ] [Refresh] [Theme] [Stop Engine] │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ 🖥️ Live Serial Console ]   [ 📊 Audit Log History ]   [ 📈 Analytics & Reporting ]   [ 📦 Login Packets ]        │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ IMEI: 861564069210428 | UIN: ACON4NA... | VIN: ACC... | ICCID: 899... | STATE: Maharashtra | FW: 5.2.9   │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FOTA Download Progress: 100.00% [======================================================================] │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [S1: Telemetry] [S2: Matrix] [S3: Sync] [S4: Audit] [S5: 100%] [S6: Reboot] [S7: State] [S8: IP1] [S9: IP2] [S10: Config] │
│   ✓ PASSED       ✓ PASSED     ✓ PASSED   ✓ PASSED   ✓ PASSED   ✓ PASSED     ✓ PASSED   ✓ PASSED  ✓ PASSED   ✓ PASSED  │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ℹ️ STATUS | FOTA Downloading: 100.00% | Status: Completed                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Header Bar & Port Selection Controls
- **Target State Dropdown (`Target State:`)**: Selects the target state server (*Maharashtra*, *Bihar*, *Assam*, *Default*).
- **Port Dropdown (`Port:`)**: Lists all connected workstation COM ports with hardware classification:
  - `COM5 [Serial] - USB Serial Port` <span class="badge-pass">[VALID PHYSICAL SERIAL PORT]</span>
  - `COM4 [Bluetooth] - Standard Serial over Bluetooth` <span class="badge-fail">[DISALLOWED BLUETOOTH PORT]</span>
- **Refresh Button (`Refresh`)**: Scans workstation USB ports quietly without triggering popup errors (`Ctrl+R`).
- **Theme Button (`Theme: Light` / `Theme: Dark`)**: Toggles visual dark and light UI color schemes (`Ctrl+T`).
- **Engine Button (`Start Engine` / `Stop Engine`)**: Starts or stops serial log reading and FOTA monitoring.

<div class="box-danger">
  <b>BLUETOOTH PORT GUARD:</b> Selecting a Bluetooth port (e.g. <code>COM4 [Bluetooth]</code>) displays a warning alert and blocks starting the engine. Always select a physical USB-to-Serial COM port (e.g. <code>COM5 [Serial]</code>).
</div>

### 4.2 Telemetry Summary Card
Displays live hardware information extracted automatically from boot logs:
- **IMEI**: 15-digit cellular module serial number.
- **UIN**: Accolade unit identification number (`ACON...`).
- **VIN**: Vehicle identification number.
- **ICCID**: SIM card identification number.
- **CURRENT STATE**: Target server state active on the unit.
- **FIRMWARE**: Current active firmware version (e.g. `5.2.9 5th IP`).
- **Clear Info Button**: Clears the displayed telemetry summary fields.

### 4.3 Visual Download Progress Bar
- Shows live download percentage (`0.00%` to `100.00%`) with 2-decimal precision.
- Updates in real-time as `[FOT] downloading XX.XX%` log lines are received from the device.

---

<div class="page-break"></div>

### 4.4 10-Stage Progression Bar (Cards Guide)

The **10-Stage Progression Widget (`StageProgressionWidget`)** displays 10 visual cards showing the status of each validation stage:

| Card # | Stage Name | What Happens in This Stage | Badge Statuses & What They Mean |
| :---: | :--- | :--- | :--- |
| **S1** | `S1: Telemetry` | Reads UIN, IMEI, VIN, Version, and State from serial boot logs. Saves pre-upgrade snapshot. | <span class="badge-pass">PASSED</span>: Telemetry captured.<br><span class="badge-info">WAITING</span>: Waiting for boot logs. |
| **S2** | `S2: Servers Matrix` | Verifies if current firmware version and state exist in `input/servers.json`. | <span class="badge-pass">PASSED</span>: Target found in matrix.<br><span class="badge-fail">FAILED</span>: Version not in matrix. |
| **S3** | `S3: Progress Sync` | Checks server history for existing FOTA jobs. | <span class="badge-pass">PASSED</span>: Sync complete.<br><span class="badge-info">RUNNING</span>: Attaching to active run. |
| **S4** | `S4: Audit Report` | Creates run record in CSV, JSON, and session log files. | <span class="badge-pass">PASSED</span>: Audit record created. |
| **S5** | `S5: 100% Download` | Tracks FOTA download progress until it reaches `100.00%`. | <span class="badge-pass">PASSED</span>: Download complete.<br><span class="badge-info">RUNNING</span>: Download in progress. |
| **S6** | `S6: Device Reboot` | Monitors post-download device reset log lines (`GSM soft shutdown pass`, `MQTT disconnect`). | <span class="badge-pass">PASSED</span>: Device rebooted.<br><span class="badge-info">RUNNING</span>: Waiting for reboot. |
| **S7** | `S7: State OTA Fired` | Issues `*GET#SWEMP#`. Verifies if state OTA is enabled on device. | <span class="badge-pass">PASSED</span>: State verified.<br><span class="badge-info">ALREADY SET</span>: Pre-configured.<br><span class="badge-warn">NOT PRESENT</span>: Parameter missing. |
| **S8** | `S8: IP1 & Port Set` | Issues `*GET#CHTP#`. Verifies primary server IP and port configuration. | <span class="badge-pass">PASSED</span>: IP1 verified.<br><span class="badge-info">ALREADY SET</span>: Pre-configured.<br><span class="badge-warn">NOT PRESENT</span>: Parameter missing. |
| **S9** | `S9: IP2 & Port Set` | Issues `*GET#CIP1#`. Verifies secondary server IP and port configuration. | <span class="badge-pass">PASSED</span>: IP2 verified.<br><span class="badge-info">ALREADY SET</span>: Pre-configured.<br><span class="badge-warn">NOT PRESENT</span>: Parameter missing. |
| **S10**| `S10: Config Verified` | Verifies post-upgrade version from `55AA` Login Packet matches target version. | <span class="badge-pass">PASSED</span>: Version verified.<br><span class="badge-fail">FAILED</span>: Version mismatch. |

<div class="box-info">
  <b>UNDERSTANDING STAGE BADGES:</b>
  <ul>
    <li><b class="badge-pass">PASSED:</b> Stage completed successfully.</li>
    <li><b class="badge-info">ALREADY SET:</b> Device is already configured with target state/IP; stage passed automatically.</li>
    <li><b class="badge-warn">NOT PRESENT:</b> Parameter absent in <code>servers.json</code> matrix; stage skipped safely.</li>
    <li><b class="badge-fail">FAILED:</b> Stage validation failed (check Troubleshooting guide).</li>
  </ul>
</div>

---

<div class="page-break"></div>

## 5.0 TAB-BY-TAB USER DASHBOARDS GUIDE

### 5.1 Tab 1: Live Serial Console & Control
- **Monospace Log Terminal**: Displays live serial boot logs in white text on obsidian dark background.
- **Interactive Command Bar**: Allows sending custom serial commands (`*SET#CRST#1#`, `*GET#CHTP#`) directly to the device. Press `Up`/`Down` arrow keys to recall previous commands.
- **Clear Buttons**:
  - `Clear Info`: Resets telemetry summary fields.
  - `Clear Log`: Clears terminal log console (`Ctrl+K`).

### 5.2 Tab 2: Audit Log History
- **4 Metric Cards**: Displays **TOTAL EXECUTIONS**, **COMPLETED**, **ABORTED / FAILED**, and **SUCCESS RATE %**.
- **Search & Status Filter**: Filter audit records by IMEI, UIN, or Status (`ALL`, `COMPLETED`, `ABORTED`, `IN_PROGRESS`).
- **Export CSV Button**: Single-click export saving audit logs to `results/fota_results.csv`.

### 5.3 Tab 3: Executive Analytics & Reporting
- **State Server Distribution Matrix**: Shows total runs, passed runs, and pass rate % per state server.
- **Firmware Version Progression Table**: Tracks firmware upgrade transitions and attempt history.
- **Export CSV Button**: Exports combined analytics report to `results/fota_analytics_report.csv`.

### 5.4 Tab 4: Login Packets
- **Real-Time Login Capture**: Automatically logs incoming `55AA` GSM login packets with millisecond timestamps, IMEI, UIN, VIN, and Firmware Version.
- **Export CSV Button**: Exports login packet history to `results/login_packets.csv`.

---

<div class="page-break"></div>

## 6.0 STEP-BY-STEP OPERATING WORKFLOW

Follow these simple steps to perform a complete FOTA validation test cycle:

```text
  STEP 1: Connect Hardware & DC Power Supply (12V/24V)
    │
    ▼
  STEP 2: Launch Utility Application (Continuos_Fota.exe)
    │
    ▼
  STEP 3: Select Target State (e.g. Maharashtra) & Physical Serial Port (COM5 [Serial])
    │
    ▼
  STEP 4: Click "Start Engine"
    │     (App locks port dropdown & automatically sends soft reboot *SET#CRST#1#)
    ▼
  STEP 5: Monitor 10-Stage Progression Bar (S1 ➔ S10)
    │
    ▼
  STEP 6: Verify Stage S10 (Config Verified) & View Audit History
    │
    ▼
  STEP 7: Click "Export CSV" to Save Official Test Report
```

### Detailed Operator Instructions
1. **Connect Device**: Connect TCU to DC power supply (`12V/24V`) and plug USB-Serial cable into workstation.
2. **Launch Application**: Double-click `Continuos_Fota.exe` (or run `python main.py`).
3. **Select State**: Pick your target state in the **Target State Dropdown** (e.g. *Maharashtra*).
4. **Select Port**: Click the **Port Dropdown** and select a physical USB Serial port (e.g. `COM5 [Serial] - USB Serial Port`). Do not select Bluetooth ports.
5. **Start Engine**: Click **Start Engine**. The utility connects, locks the port dropdown, and automatically fires soft reboot command `*SET#CRST#1#`.
6. **Observe Progression**: Watch boot telemetry populate in the top card and track cards `S1` through `S10`.
7. **Export Report**: After `S10: Config Verified` passes, switch to **Tab 2** or **Tab 3** and click **Export CSV** to save your test records.

---

<div class="page-break"></div>

## 7.0 HARDWARE SERIAL COMMAND QUICK REFERENCE

| Command | Action / Description | Expected Device Response |
| :--- | :--- | :--- |
| `*SET#CRST#1#` | Soft reboots the TCU hardware unit. | `STATUS#SET#CRST#1#OK#` / `GSM soft shutdown pass` |
| `*GET#SWEMP#` | Queries active state OTA status. | `STATUS#SWEMP#<state>#OK#` |
| `*GET#CHTP#` | Queries primary server IP1 and Port1. | `STATUS#CHTP#<ip>:<port>#OK#` |
| `*GET#CIP1#` | Queries secondary server IP2 and Port2. | `STATUS#CIP1#<ip>:<port>#OK#` |
| `*CLR#FOTA#` | Clears active FOTA update state on device. | `STATUS#CLR#FOTA#OK#` |

---

## 8.0 COMPLETE TROUBLESHOOTING & SELF-HELP GUIDE

If you encounter any issue or get stuck while using the utility, locate your symptom below to resolve it quickly:

| Problem / Error Message | What Caused It | How to Fix It (Step-by-Step) |
| :--- | :--- | :--- |
| **"Cannot Start Engine: COM4 is a Bluetooth port"** | A Bluetooth serial link was selected in the Port dropdown. | 1. Open **Port Dropdown**.<br>2. Select a physical USB Serial port (e.g. `COM5 [Serial]`).<br>3. Click **Start Engine**. |
| **"COM Port Access Denied" or Serial Connection Error** | The COM port is occupied by TeraTerm, PuTTY, or another app. | 1. Close TeraTerm / PuTTY / Arduino IDE.<br>2. Unplug and re-plug USB serial cable.<br>3. Click **Refresh** (`Ctrl+R`) and click **Start Engine**. |
| **"No COM Ports Found" in Dropdown** | Workstation cannot detect USB-Serial adapter cable. | 1. Verify USB cable is firmly plugged in.<br>2. Ensure FTDI / CH340 device drivers are installed in Windows Device Manager.<br>3. Click **Refresh** (`Ctrl+R`). |
| **"WARNING: Version X.X.X not found in servers.json"** | Active firmware version on device is not listed in server matrix. | 1. Check **Target State Dropdown** to ensure correct state is selected.<br>2. Open `input/servers.json` and add missing firmware version to `firmwares` list. |
| **"API HTTP 401 Unauthorized Error"** | API username or password in `.env` file is incorrect or expired. | 1. Open `.env` file in Notepad.<br>2. Update `API_USER` and `API_PASS` with valid credentials.<br>3. Restart the FOTA Utility. |
| **Device Reboot Not Detected (Stage S6 Timeout)** | Power supply turned off or device failed to soft shutdown. | 1. Verify DC Power Supply is outputting `12V/24V DC`.<br>2. Type `*SET#CRST#1#` in the bottom Command Bar and press Enter. |
| **Stage S7 / S8 / S9 Shows "NOT PRESENT"** | State parameter missing in `input/servers.json` for selected state. | 1. Open `input/servers.json`.<br>2. Ensure `govtIp1`, `govtPort1`, `govtIp2`, `govtPort2`, and `stateEnable` fields are populated. |
| **Login Packet Not Capturing in Tab 4** | Device SIM card has no network signal or GSM registration pending. | 1. Verify cellular antenna is connected.<br>2. Ensure SIM card has active 4G data subscription.<br>3. Wait 30-60 seconds for GSM network registration. |

---

<div class="page-break"></div>

## 9.0 OPERATOR CHECKLIST & BEST PRACTICES

### 9.1 Daily Pre-Testing Checklist
- [ ] DC Power Supply set to `12V` or `24V DC` (`2A` minimum).
- [ ] USB-to-Serial Debug Cable connected firmly to PC and DUT.
- [ ] Cellular (4G) and GNSS (GPS) antennas connected.
- [ ] Close external serial software (TeraTerm, PuTTY).
- [ ] Selected physical COM port (`COMx [Serial]`) in FOTA Utility.

### 9.2 Operational Do's and Don'ts
- <span class="badge-pass">DO</span> verify your Target State dropdown selection before clicking **Start Engine**.
- <span class="badge-pass">DO</span> export CSV reports at the end of each testing shift.
- <span class="badge-fail">DON'T</span> disconnect serial cable or power off DUT during active FOTA download (Stage S5).
- <span class="badge-fail">DON'T</span> select Bluetooth serial ports.

---

## 10.0 DOCUMENT REVISION LOG

| Revision | Date | Section Changed | Description of Changes | Approved By |
| :---: | :---: | :---: | :--- | :--- |
| `1.0.0` | 15-01-2026 | All | Initial release for manual serial testing. | QA Lead |
| `1.5.0` | 10-05-2026 | Sec 4, 5 | Added 3-status logic engine and automated REST polling. | QA Manager |
| `2.0.0` | 24-08-2026 | All | Complete user-focused rewrite: 10-Stage Progression Cards guide, Bluetooth guard rules, troubleshooting self-help table, and AEPL corporate PDF header. | Engineering Lead |

---

## 11.0 PREPARATION, REVIEW & APPROVAL SIGN-OFF

<table style="margin-top: 15px;">
  <thead>
    <tr>
      <th width="30%">Action / Designation</th>
      <th width="30%">Name</th>
      <th width="25%">Signature</th>
      <th width="15%">Date</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>PREPARED BY:</b><br>Lead QA Automation Engineer</td>
      <td>Suraj Bhalerao</td>
      <td>____________________</td>
      <td>24 / 08 / 2026</td>
    </tr>
    <tr>
      <td><b>CHECKED BY:</b><br>Embedded Hardware Manager</td>
      <td>Accolade R&D Team</td>
      <td>____________________</td>
      <td>24 / 08 / 2026</td>
    </tr>
    <tr>
      <td><b>APPROVED BY:</b><br>Quality Assurance Director</td>
      <td>AEPL Quality Management</td>
      <td>____________________</td>
      <td>24 / 08 / 2026</td>
    </tr>
  </tbody>
</table>
