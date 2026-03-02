# FOTA Automation System

Java automation for continuous firmware updates on ATCU devices using serial communication and web portal integration.

## Quick Start

### Prerequisites
- Java 21+
- Maven 3.6+
- Device connected to serial port (e.g., COM3)
- Web portal credentials
- Required input files:
  - `input/servers.json` - Firmware version mappings by state

### Configuration

Edit [Launcher.java](src/main/java/com/aepl/atcu/Launcher.java) to set:

```java
private static final String SERIAL_PORT = "COM3";
private static final int BAUD_RATE = 115200;

private static final String FIRMWARE_JSON = "input/servers.json";
private static final String AUDIT_CSV = "results/fota_audit.csv";
private static final String LOGIN_JSON = "results/login_packets.json";

private static final String PORTAL_URL = "http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login";
private static final String PORTAL_USER = "suraj.bhalerao@accoladeelectronics.com";
private static final String PORTAL_PASS = "79hqelye";
private static final String DEFAULT_STATE = "Default";
```

### Run

```bash
mvn clean compile exec:java -Dexec.mainClass="com.aepl.atcu.Launcher"
```

## Input Files

### input/servers.json
Defines firmware sequences by state (with optional two-letter abbreviations):

```json
[
  {
    "state": "Maharashtra",
    "stateAbbreviation": "MH",
    "firmware": [
      { "firmwareVersion": "5.2.11", "fileName": "ATCU_5.2.8_REL24.bin" },
      { "firmwareVersion": "5.2.12", "fileName": "ATCU_5.2.9_REL04.bin" }
    ]
  }
]
```

## Output Files

- **logs/** - Device serial communication logs (per IMEI)
- **results/login_packets.json** - Captured device login information
- **results/fota_audit.csv** - Upgrade history and results
- **output/** - Generated batch CSVs
- **screenshots/** - Web portal automation screenshots

## Device Serial Log Format

The system recognizes:
- **Standard state messages**: `STATE=STABLE` or `VERSION: 5.2.8_REL24`
- **Statewise protocol**: `.  statewise prtcl    |  SWEMP     MH` (extracts `MH` abbreviation)
- **Login packets**: `55AA,0,0,0,IMEI,ICCID,UIN,VERSION,VIN`

State abbreviations are automatically mapped to full names using `servers.json`.

## Architecture

```
Launcher
  ↓
Orchestrator (main loop)
  ├→ SerialReader (device communication)
  ├→ MessageParser (serial log parsing)
  ├→ FirmwareResolver (version mapping)
  ├→ FotaWebClient (portal automation)
  └→ FotaFileGenerator (CSV/audit generation)
```

## Features

- ✅ Dual verification: Serial logs + Web portal batch status
- ✅ Automatic state abbreviation mapping (MH → Maharashtra)
- ✅ Multi-format log parsing
- ✅ Per-device IMEI-based logging
- ✅ Audit trail for all upgrades
- ✅ Retry logic for robustness

## Troubleshooting

### Serial port not found
Verify port in Device Manager and update `SERIAL_PORT` in `Launcher.java`.

### Login packet shows default state
Ensure device sends state in logs before login packet. Check `servers.json` has `stateAbbreviation` entries.

### Version not matched in servers.json
Verify binary filename follows pattern `ATCU_X.X.X_RELMM.bin` and device reports matching version from that filename.
