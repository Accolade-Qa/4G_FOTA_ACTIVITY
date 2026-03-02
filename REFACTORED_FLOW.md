# FOTA Automation - Simplified Workflow

## Overview
The FOTA (Firmware Over-The-Air) automation tool has been refactored to follow a **clean, linear workflow** without unnecessary complexity. The tool automates device firmware updates by monitoring serial communication and managing version upgrades through a web portal.

---

## Simplified 12-Step Workflow

### **STEP 1-3: Initialize Serial Communication & Receive Login Packet**
- Serial reader starts and monitors device logs
- **OTA command is fired** which triggers device reboot
- Device generates and sends a **login packet** containing device information
- Login packet is parsed and stored

**Device Information Extracted:**
- IMEI (International Mobile Equipment Identity)
- ICCID (Integrated Circuit Card Identifier)
- UIN (Unique Identification Number)
- VIN (Vehicle Identification Number)
- State/Region (e.g., Maharashtra, Bihar)
- Current firmware version

---

### **STEP 4: Store Login Packet**
- Complete login packet information is cached in memory
- Available for all subsequent operations in the cycle

---

### **STEP 5-6: Compare Version with JSON & Determine Next Version**
- Extract device state from login packet
- Look up state in `input/servers.json` firmware mapping
- Compare current device version with firmware sequence for that state
- If current version is older than next version in sequence:
  - **Return next version to install**
- If device is on latest version:
  - **Mark device as COMPLETED**
  - Write audit report and exit

**JSON Structure Example:**
```json
[
  {
    "state": "Maharashtra",
    "firmware": [
      { "firmwareVersion": "5.2.12", "fileName": "..." },
      { "firmwareVersion": "5.2.15", "fileName": "..." },
      { "firmwareVersion": "5.2.18", "fileName": "..." }
    ]
  }
]
```

---

### **STEP 7: Prepare FOTA Batch Payload**
- Create CSV batch file with device information:
  - UIN, Version, Model, State, IMEI
- Output written to `output/fota_batch_[timestamp].csv`
- Batch is ready for upload to web portal

---

### **STEP 8: Fire FOTA Batch to Web Endpoint**
- Web client (Selenium-based) authenticates with web portal
- Creates new FOTA batch with:
  - Batch name (AutoFota_[timestamp])
  - Description (FOTA to version X.X.X)
  - CSV file containing device data
- Portal processes batch and initiates download on device

---

### **STEP 9: Monitor OTA Request/Response**
- Serial reader listens for OTA-related log lines:
  - "OTA request sent"
  - "OTA response received"
  - "Downloading..." messages

---

### **STEP 10: Monitor Download Progress → Reboot**
- Track download progress from serial logs
- When progress reaches **100%:**
  - Device firmware update completes
  - **Device automatically reboots** (once)
  - Wait for reboot to complete (~20 seconds)

---

### **STEP 11: Observe Post-Reboot Login Packet**
- After reboot, device sends new login packet
- Extract version number from new login packet
- **Verify version matches** the target version
- If verification succeeds:
  - **Mark upgrade as SUCCESS**
  - Write audit report
- If verification fails:
  - **Mark upgrade as FAILED**
  - Write audit report with error details

---

### **STEP 12: Repeat or Mark Complete**
- Return to STEP 1 with same device
- Repeat until no more versions available in JSON for that state
- When JSON has no next version:
  - **Mark device as DONE**
  - Write final audit report to `results/fota_audit.csv`
  - Break from loop

---

## Key Improvements Over Previous Version

### **Complexity Removed:**
❌ Parallel async task execution (CompleteableFuture)  
❌ Artificial state map management  
❌ aeplFwVer special handling (now uses login packet version directly)  
❌ Dual monitoring (Serial + Web) complexity  
❌ Unnecessary fallback logic chains  

### **Simplified Architecture:**
✅ **Linear, single-threaded flow** - easier to understand and debug  
✅ **Direct serial monitoring** - focus on device login packets  
✅ **Clear decision points** - version comparison → upgrade → verify  
✅ **Audit trail** - every action logged to audit CSV  
✅ **Minimal web automation** - only create batch, no complex monitoring  

---

## Configuration Files

### **config.properties**
```properties
serial.port=COM3                    # Serial port (e.g., COM3, /dev/ttyUSB0)
serial.baud=115200                 # Baud rate for serial communication
firmware.csv=input/fota_batch.csv  # Source device CSV
firmware.json=input/servers.json   # State → Version mapping
audit.csv=results/fota_audit.csv   # Audit report output
login.url=http://...portal.../login # Web portal login URL
login.user=user@email.com          # Portal username
login.pass=password                # Portal password
state=Default                      # Default state if device reports 'Default'
```

### **input/servers.json**
Defines firmware version sequences for each state/region:
- State name
- Array of firmware versions in upgrade order
- File names for each version

### **input/fota_batch.csv**
Source device list (if needed for fallback):
```
UIN, UFW, MODEL, STATE, IMEI
ACON4NA082300092233, 5.2.1, 4G, Maharashtra, 861564061380138
```

---

## Output Folders

| Folder | Purpose |
|--------|---------|
| `input/` | Configuration files (servers.json, fota_batch.csv) |
| `output/` | Generated batch CSV files for each FOTA cycle |
| `logs/` | Serial communication logs (one per IMEI) |
| `results/` | Audit reports and final results |
| `screenshots/` | Portal screenshots (Selenium captures) |

---

## Audit Report (results/fota_audit.csv)

Logs every device upgrade attempt:
```
UIN, FROMVERSION, TOVERSION, STATUS, DETAILS
ACON4NA082300092233, 5.2.1, 5.2.12, SUCCESS, Device rebooted and upgrade verified
ACON4NA082300092234, 5.2.2, 5.2.10, FAILED, Download monitoring timeout
```

---

## Execution Flow Diagram

```
START
  ↓
[Initialize Serial + Web]
  ↓
┌─→ Wait for Login Packet ←──────────────────────┐
│      ↓                                         │
│  Extract Device Info                           │
│   (IMEI, VIN, UIN, ICCID, State, Version)      │
│      ↓                                         │
│  Compare Version with JSON                     │
│      ↓                                         │
│  Decision: Need Upgrade?                       │
│    ├─ NO  → Mark DONE, Write Audit, EXIT      │
│    └─ YES → Continue                           │
│      ↓                                         │
│  Prepare FOTA Batch CSV                        │
│      ↓                                         │
│  Fire to Web Portal                            │
│      ↓                                         │
│  Monitor Serial for Download                   │
│      ├─ Timeout → Mark FAILED ──┐              │
│      └─ 100% Complete → Reboot  │              │
│           ↓                      │              │
│      Wait 20s for Reboot        │              │
│           ↓                      │              │
│      Verify New Version         │              │
│      ├─ Match → Mark SUCCESS ──┤              │
│      └─ No Match → Mark FAILED ┤              │
│           ↓                     │              │
│      Write Audit Report         │              │
│           ↓                     │              │
│      Repeat Cycle ──────────────┘              │
│                                                │
└────────────────────────────────────────────────┘
  ↓
SHUTDOWN
```

---

## How to Run

1. **Configure settings:**
   ```
   Edit config.properties with:
   - Serial port of your device
   - Web portal credentials
   - Path to firmware JSON mapping
   ```

2. **Prepare input files:**
   ```
   - input/servers.json (firmware versions by state)
   - input/fota_batch.csv (optional device source)
   ```

3. **Start automation:**
   ```
   mvn clean compile
   mvn exec:java -Dexec.mainClass="com.aepl.atcu.Launcher"
   ```

4. **Monitor progress:**
   - Console logs show step-by-step progress
   - Serial logs: `logs/` folder
   - Audit reports: `results/fota_audit.csv`
   - Batch files: `output/` folder

---

## Key Classes

| Class | Purpose |
|-------|---------|
| **Orchestrator** | Main orchestration logic - follows 12-step workflow |
| **SerialReader** | Reads device serial logs, parses packets, tracks state |
| **FirmwareResolver** | Compares versions with JSON, determines next version |
| **FotaWebClient** | Selenium automation for web portal batch creation |
| **MessageParser** | Parses serial log lines for version/state info |
| **FotaFileGenerator** | Creates batch CSV files and audit reports |
| **LoginPacketInfo** | Data model for device login packet information |

---

## Summary

This refactored version:
- **Eliminates unnecessary complexity** (async execution, dual monitoring)
- **Follows a clear, linear workflow** (steps 1-12)
- **Focuses on serial communication** (device-centric approach)
- **Provides detailed audit trail** (every action logged)
- **Easier to debug and maintain** (step-by-step progression)

The tool is now a **simple, reliable FOTA automation engine** that achieves your requirements without over-engineering.
