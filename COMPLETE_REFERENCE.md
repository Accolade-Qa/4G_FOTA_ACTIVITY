# FOTA Automation - Complete Reference Guide

> **Consolidation of all documentation into one comprehensive reference**

---

## 📚 Table of Contents
1. **Frequently Asked Questions**
2. **Validation Rules (New in Recent Update)**
3. **Login Packet Structure & Data Flow**
4. **API Payload Reference**
5. **Code Architecture Verification**
6. **Configuration Reference**

---

# ❓ Frequently Asked Questions

## Q1: Does all code follow the same simplified logic?

### ✅ **YES - 100% Aligned**

| Component | Responsibility | Complexity | Status |
|-----------|---|---|---|
| **Orchestrator.java** | 12-step workflow orchestration | ⭐ Simple | ✅ Refactored |
| **SerialReader.java** | Read → Parse → Store | ⭐ V.Simple | ✅ Perfect |
| **MessageParser.java** | Extract data from serial logs | ⭐ V.Simple | ✅ Perfect |
| **FirmwareResolver.java** | Version comparison logic | ⭐ V.Simple | ✅ Perfect |
| **FotaFileGenerator.java** | CSV generation & audit | ⭐ V.Simple | ✅ Perfect |
| **FotaWebClient.java** | Browser automation (Selenium) | ⭐⭐ Light | ✅ Good |
| **SerialConnection.java** | Low-level serial I/O | ⭐ V.Simple | ✅ Perfect |
| **LoginPacketInfo.java** | Device data model | ⭐ V.Simple | ✅ Perfect |
| **LogWriter.java** | IMEI-specific logging | ⭐ V.Simple | ✅ Perfect |
| **Launcher.java** | Configuration & startup | ⭐⭐ Simple | ✅ Good |

**Verdict:** All 10 Java files are simple, focused, and aligned with the simplified workflow. ✨

---

## Q2: What about the API payload and request?

### 📦 **Answer: CSV File Upload (NOT REST API)**

The system uses **Selenium browser automation + CSV file upload**, NOT direct REST calls.

**What Gets Sent:**
```csv
UIN,UFW,MODEL,STATE,IMEI
ACON4NA082300092233,5.2.15,4G,Maharashtra,861564061380138
```

**Columns Explained:**
- **UIN** = Unique device ID (must start with "ACON" ✓)
- **UFW** = Target firmware version
- **MODEL** = Device model (usually "4G")
- **STATE** = Region/state name
- **IMEI** = Device IMEI (must be 13-15 digits ✓)

**Validation Rules (UPDATED):**
- ✅ **UIN must start with "ACON"** - validated at parse time and Orchestrator level
- ✅ **IMEI must be 13-15 numeric digits** - validated at parse time and Orchestrator level
- Invalid data is rejected immediately with detailed logging

---

# 🔐 Validation Rules (New in Recent Update)

## What Gets Validated and Where

### **1. MessageParser Level (First Check)**
When device sends login packet via serial:
```java
- UIN validation: Must start with "ACON"
- IMEI validation: Must be 13-15 digits (numeric only)
- Invalid packets are REJECTED with warnings
```

### **2. Orchestrator Level (Double-Check)**
After receiving device login packet:
```java
- UIN validation: Reconfirm starts with "ACON"
- IMEI validation: Reconfirm 13-15 digits
- Invalid devices SKIPPED to next cycle
```

### **3. FotaFileGenerator Level (Final Check)**
Before writing to CSV batch file:
```java
- UIN validation: Must start with "ACON" 
- Invalid records SKIPPED (not written to CSV)
```

## Example: Invalid Data Rejection

**Scenario:** Device sends invalid data
```
Login Packet from Serial:
UIN = "0000" (❌ doesn't start with ACON)
IMEI = "5.2.8_REL24" (❌ not numeric)
```

**What Happens:**
1. ❌ MessageParser rejects immediately
   ```
   WARN[PARSER]: Invalid UIN (must start with ACON): 0000
   WARN[PARSER]: Invalid IMEI (must be 13-15 digits): 5.2.8_REL24
   ```

2. ❌ Orchestrator also checks and rejects
   ```
   ERROR: Invalid UIN received (must start with ACON): 0000. Rejecting device.
   ERROR: Invalid IMEI received (must be 13-15 digits): 5.2.8_REL24. Rejecting device.
   ```

3. ❌ No CSV is created, device skips to next cycle

**Expected Valid Data:**
```
UIN = "ACON4NA082300092233" (✅ starts with ACON)
IMEI = "861564061380138" (✅ 15 digits, numeric)
```

---

# 📦 Login Packet Structure & Data Flow

## Device Login Packet (Complete Structure)

**Raw Format from Device:**
```
55AA,1,2,1762506165,861564061380138,89916420534724851291,ACON4NA082300092233,5.2.9_REL04,ACCDEV07241580138,UF,...
```

## Field-by-Field Breakdown

| Index | Name | Value | Meaning |
|-------|------|-------|---------|
| 0 | Marker | `55AA` | Binary packet identifier |
| 1 | Protocol Version | `1` | Protocol version |
| 2 | Packet Type | `2` | Login packet type |
| 3 | Timestamp | `1762506165` | Unix epoch |
| **4** | **IMEI** | `861564061380138` | Device ID (15 digits) |
| **5** | **ICCID** | `89916420534724851291` | SIM Card ID |
| **6** | **UIN** | `ACON4NA082300092233` | Unique ID (must start with ACON) |
| **7** | **Version** | `5.2.9_REL04` | Current firmware |
| **8** | **VIN** | `ACCDEV07241580138` | Vehicle ID |
| 9+ | Additional Fields | Various | Status, config, etc. |

## Data Flow Through System

```
┌──────────────────┐
│ Device (Serial)  │ Sends: Login packet 55AA format
└────────┬─────────┘
         ↓
┌──────────────────────────────┐
│ SerialReader                 │ Raw bytes from serial port
└────────┬─────────────────────┘
         ↓
┌──────────────────────────────┐
│ MessageParser.parseLoginPacket() │
│  • Validates UIN (ACON*)     │
│  • Validates IMEI (13-15)    │
│  • Splits by comma           │
│  • Extracts parts[4-8]       │
└────────┬─────────────────────┘
         ↓ (Invalid packets rejected here)
┌──────────────────────────────┐
│ LoginPacketInfo              │ Created only if valid
│  • imei: 861564061380138     │
│  • uin: ACON4NA082300092233  │
│  • version: 5.2.9_REL04      │
│  • model: "4G" (default)     │
│  • state: "Default" (default)│
└────────┬─────────────────────┘
         ↓
┌──────────────────────────────┐
│ Orchestrator.start()         │
│  • Validates UIN again       │
│  • Validates IMEI again      │
│  • Rejects if invalid        │
└────────┬─────────────────────┘
         ↓ (Second filter)
┌──────────────────────────────┐
│ FirmwareResolver             │ Compares with servers.json
│  Determines next version     │
└────────┬─────────────────────┘
         ↓
┌──────────────────────────────┐
│ FotaFileGenerator            │
│  • Validates UIN again       │
│  • Creates CSV with 5 cols   │
│  • Skips invalid records     │
└────────┬─────────────────────┘
         ↓
┌──────────────────────────────┐
│ CSV File (output/)           │ Ready for portal upload
│ UIN,UFW,MODEL,STATE,IMEI     │
│ ACON4NA...,5.2.15,4G,...     │
└────────┬─────────────────────┘
         ↓
┌──────────────────────────────┐
│ FotaWebClient (Selenium)     │ Uploads to web portal
└──────────────────────────────┘
```

---

# 🌐 API Payload Reference

## Current Method: Selenium + CSV (Browser Automation)

The system is **NOT** using direct REST API calls. Instead:

### **Form-Based Upload Process**

1. **Navigate to FOTA Page**
   ```java
   driver.findElement(By.xpath("//*[contains(text(), 'Device Utility')]")).click();
   driver.findElement(By.linkText("FOTA")).click();
   driver.findElement(By.xpath("//*[contains(text(), 'Create New Batch')]")).click();
   ```

2. **Fill Form Fields**
   ```java
   driver.findElement(By.xpath("//input[@placeholder='Batch Name']"))
     .sendKeys("AutoFota_20260227_173048");
   driver.findElement(By.xpath("//input[@placeholder='Batch Description']"))
     .sendKeys("FOTA to version 5.2.15");
   WebElement select = driver.findElement(By.xpath("//mat-select[@formcontrolname='AIS140']"));
   select.click();
   ```

3. **Upload CSV File**
   ```java
   WebElement fileInput = driver.findElement(By.xpath("//input[@type='file']"));
   fileInput.sendKeys("D:\\AEPL_AUTOMATION\\FOTA_ACTIVITY\\output\\fota_batch_20260227_173048.csv");
   driver.findElement(By.xpath("//button[contains(text(), 'Create Batch')]")).click();
   ```

4. **Monitor Progress**
   - Poll batch status table in portal
   - Extract progress percentage
   - Wait for 100% completion

---

## Alternative: REST API (If Portal Supports It)

If a REST API is available, payloads would look like:

### **Create Batch Request**
```json
POST /api/v1/fota/batches
Content-Type: application/json
Authorization: Bearer <token>

{
  "batchName": "AutoFota_20260227_173048",
  "description": "FOTA to version 5.2.15",
  "fotaType": "AIS140 FOTA",
  "devices": [
    {
      "uin": "ACON4NA082300092233",
      "targetVersion": "5.2.15",
      "model": "4G",
      "state": "Maharashtra",
      "imei": "861564061380138"
    }
  ]
}
```

### **Expected Response**
```json
{
  "batchId": "batch_20260227_173048_001",
  "batchName": "AutoFota_20260227_173048",
  "status": "CREATED",
  "deviceCount": 1,
  "createdAt": "2026-02-27T17:30:48Z"
}
```

### **Start Batch Request**
```
POST /api/v1/fota/batches/batch_20260227_173048_001/start
```

### **Status Check Request**
```
GET /api/v1/fota/batches/batch_20260227_173048_001/status
```

---

# ✅ Code Architecture Verification

## Alignment Checklist

### **Data Flow Consistency**
- ✅ SerialReader reads raw bytes
- ✅ MessageParser extracts structured data  
- ✅ Orchestrator applies business logic
- ✅ FotaFileGenerator creates CSV payload
- ✅ FotaWebClient sends to portal
- ✅ Results stored in audit CSV

### **Error Handling**
- ✅ Invalid UIN (not ACON*) → Rejected at parse time
- ✅ Invalid IMEI (not 13-15 digits) → Rejected at parse time
- ✅ Missing device data → Retry cycle
- ✅ Version mismatch → Failed audit entry
- ✅ Download timeout → Failed audit entry

### **Audit Trail**
- ✅ Serial logs: `logs/AUTO_FOTA_{IMEI}_{DATE}.log`
- ✅ Batch files: `output/fota_batch_{TIMESTAMP}.csv`
- ✅ Audit report: `results/fota_audit.csv`
- ✅ Screenshots: `screenshots/*.png`

---

# ⚙️ Configuration Reference

## config.properties

```properties
# Serial Communication
serial.port=COM3                              # Device port (COM3, /dev/ttyUSB0, etc.)
serial.baud=115200                           # Communication speed

# Input Files
firmware.csv=input/fota_batch.csv            # Source device CSV (optional fallback)
firmware.json=input/servers.json             # Version mapping by state

# Output Locations
audit.csv=results/fota_audit.csv             # Audit report destination

# Web Portal
login.url=http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login
login.user=suraj.bhalerao@accoladeelectronics.com
login.pass=79hqelye

# Defaults
state=Default                                # Default state if device reports 'Default'
```

## input/servers.json (Version Mapping)

```json
[
  {
    "state": "Maharashtra",
    "firmware": [
      { "firmwareVersion": "5.2.12", "fileName": "ATCU_5.2.8_REL18.bin" },
      { "firmwareVersion": "5.2.15", "fileName": "ATCU_5.2.9_REL07.bin" },
      { "firmwareVersion": "5.2.18", "fileName": "ATCU_5.2.9_REL05.bin" }
    ]
  },
  {
    "state": "Bihar",
    "firmware": [
      { "firmwareVersion": "5.2.11", "fileName": "ATCU_5.2.8_REL24.bin" }
    ]
  }
]
```

## Log File Naming (NEW FORMAT)

```
logs/AUTO_FOTA_{IMEI}_{DATE}.log

Examples:
- logs/AUTO_FOTA_861564061380138_20260302.log
- logs/AUTO_FOTA_123456789012345_20260302.log
```

## Directory Structure

```
.
├── input/
│   ├── fota_batch.csv             (Device source list)
│   └── servers.json               (Version mappings)
├── output/
│   └── fota_batch_*.csv           (Generated batch files)
├── logs/
│   └── AUTO_FOTA_*.log            (Per-IMEI serial logs)
├── results/
│   └── fota_audit.csv             (Audit report)
├── screenshots/
│   └── *.png                      (Portal screenshots)
├── config.properties              (Configuration)
├── pom.xml                        (Maven config)
└── src/
    ├── main/java/com/aepl/atcu/
    │   ├── Launcher.java
    │   ├── Orchestrator.java
    │   ├── SerialReader.java
    │   └── ...other classes...
    └── main/resources/
        └── log4j2.xml
```

---

## Audit Report Format

**File:** `results/fota_audit.csv`

```csv
Timestamp,UIN,Previous_Version,Target_Version,Status,Details
2026-03-02 11:30:45,ACON4NA082300092233,5.2.1,5.2.15,SUCCESS,Device rebooted and upgrade verified
2026-03-02 11:45:20,ACON4NA082300092234,5.2.2,5.2.10,FAILED,Download monitoring timeout
```

---

## Summary

✅ **All code is simple, focused, and aligned**  
✅ **Validation happens at 3 levels (Parser, Orchestrator, Generator)**  
✅ **Invalid data is rejected immediately with clear logging**  
✅ **CSV payload contains only 5 essential columns**  
✅ **Complete audit trail maintained throughout execution**
