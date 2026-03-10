# FOTA Automation System

Lightweight Java automation that drives firmware-over‑the‑air (FOTA) updates
for ATCU/TCU devices. The service listens to a serial port for login packets,
resolves the next firmware version, kicks off a batch on the web portal, and
keeps a detailed audit trail.

---

## 🔧 Prerequisites

1. **Java 21+** (JDK 21 is recommended)
2. **Apache Maven 3.6+**
3. Device physically connected to a serial port (e.g. `COM3`) and powered on
4. Valid **web portal credentials** with FOTA privileges
5. `input/servers.json` file describing state‑to‑firmware mappings (see below)

> The launcher will create the working directories on first run:
> `input`, `output`, `logs`, `results`, and `screenshots`.

---

## ⚙️ Configuration

All runtime constants are hard‑coded in `src/main/java/com/aepl/atcu/Launcher.java`.
Edit the file to suit your environment before building or running.

Key fields:

```java
private static final String SERIAL_PORT = "";       // blank = auto‑detect
private static final int BAUD_RATE = 115200;

private static final String FIRMWARE_JSON = "input/servers.json";
private static final String AUDIT_CSV    = "results/fota_audit.csv";
private static final String LOGIN_JSON   = "results/login_packets.json";

private static final String PORTAL_URL  =
        "http://aepl-tcu4g-qa.accoladeelectronics.com:6102/login";
private static final String PORTAL_USER = "<your‑user>";
private static final String PORTAL_PASS = "<your‑password>";

private static final String DEFAULT_STATE = "Delhi";
```

> ⚠️ The default state is used when no state information can be parsed from
> the device logs.

---

## ▶️ Running the Application

Build and execute using Maven:

```bash
mvn clean compile exec:java -Dexec.mainClass="com.aepl.atcu.Launcher"
```

Logs are written to `logs/` and results to `results/`.

---

## 📁 Input Files

### `input/servers.json`
The only configuration file the application consumes. It is a JSON array of
state objects. Each object contains:

* **`state`** – the full state/region name used in device logs or defaulted
  when parsing fails.
* **`versions`** – an ordered list of firmware version strings. The code
decides the next release by finding the current device version in this array
and picking the subsequent element. Any order is acceptable but maintaining
chronological progression avoids confusion.

A typical file looks like:

```json
[
  {
    "state": "DO NOT DELETE",
    "versions": ["1.1.1", "1.1.2"]
  },
  {
    "state": "Maharashtra",
    "versions": [
      "5.2.12", "5.2.10", "5.2.15", "5.2.16",
      "5.2.18", "5.2.14", "5.2.13"
    ]
  },
  {
    "state": "Bihar",
    "versions": ["5.2.11", "5.2.12", "5.2.14", "5.2.17", "5.2.19"]
  }
  /* ... more states ... */
]
```

> **Note:** the special `"DO NOT DELETE"` entry is used internally and should
> remain at the top of the array.

> Additional CSVs can be generated automatically by the tool in `output/`
> when batches are created.

---

## 📂 Output Files

| Location                     | Description                                |
|------------------------------|--------------------------------------------|
| `logs/`                      | Per‑IMEI serial communication logs         |
| `results/login_packets.json` | Captured login packets (raw JSON list)     |
| `results/fota_audit.csv`     | Upgrade audit trail (cycle-by-cycle)       |
| `output/`                    | Generated CSVs for portal batch uploads    |
| `screenshots/`               | Selenium screenshots taken during runs     |

---

## 🛰 Device Serial Log Format

The parser understands several common patterns:

* `STATE=STABLE` or `VERSION: 5.2.8_REL24` — typical status messages
* `.  statewise prtcl    |  SWEMP     MH` — extracts `MH` abbreviation
* `55AA,0,0,0,IMEI,ICCID,UIN,VERSION,VIN` — login packet format

State abbreviations are resolved back to full names using
`servers.json` automatically.

---

## 🏗 Architecture Overview

```
Launcher
  ↓
Orchestrator (main loop)
    ├─ SerialReader        (reads/raw logs)
    ├─ MessageParser       (extracts IMEI, state, version)
    ├─ FirmwareResolver    (chooses next firmware file)
    ├─ FotaWebClient       (Selenium-based portal automation)
    └─ FotaFileGenerator   (CSV/audit output)
```

* The orchestrator treats the **first valid login packet** as the start of a
  FOTA cycle and ignores subsequent packets until the cycle completes.
* After download reaches 100 %, it waits through any number of reboot/login
  cycles and only continues when the **target version** is confirmed; this
  avoids aborting on intermediate firmware numbers.

---

## ⭐ Features

* Dual verification using serial log parsing and portal batch status
* Automatic mapping of short state codes (e.g. `MH` → `Maharashtra`)
* Flexible log parsing for multiple message formats
* IMEI‑based logging for individual device traces
* Comprehensive audit trail for every upgrade attempt
* Built‑in retry and error handling for robustness

---

## 🛠 Troubleshooting

**Serial port not found**
: Check Device Manager and set `SERIAL_PORT` appropriately (or leave blank to
  auto‑detect).

**Login packet shows default state**
: Ensure the device outputs a state message before the login packet and that
  `servers.json` includes the corresponding `stateAbbreviation` if necessary.

**Firmware version not resolved**
: Confirm that the binary filename matches
  `ATCU_X.X.X_RELMM.bin` and that `servers.json` lists the correct
  `firmwareVersion` entry.

---

*Last updated: March 2026 – aligned with current source code.*
