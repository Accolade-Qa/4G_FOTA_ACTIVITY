# Continuous FOTA Automation Utility (4G TCU / Telematics)

A multi-threaded Windows Desktop Utility for continuous FOTA (Firmware Over-The-Air) upgrade testing, serial boot log telemetry abstraction, state matrix validation, and automated REST API job triggering for Accolade 4G TCU hardware units.

---

## 🌟 Key Features

- **3-Tab Enterprise Architecture**:
  - `🖥️ Live Serial Console & Control`: Maximized live serial log terminal, 5-field hardware telemetry card, 2-decimal precision visual progress bar, status banner card, and AT command bar.
  - `📊 Audit Log History`: Execution audit table with 4 metric cards, live search filter (`🔍`), status filter dropdown, and single-click `📥 Export CSV`.
  - `📈 Analytics & Reporting`: Executive analytics dashboard breaking down state matrix distribution and firmware version progression.
- **Pure Crisp White Log Text**: Monospace terminal log output rendered in high-contrast white text (`#f8fafc`) against dark obsidian background.
- **Dedicated Clear Log Button & Keyboard Shortcuts**:
  - `Clear Log` button on main screen.
  - `Ctrl+K` / `Ctrl+L`: Clear live terminal console.
  - `Ctrl+R`: Refresh COM ports list.
  - `Ctrl+T`: Toggle between Light and Cyber-Dark themes.
  - `Esc`: Clear AT command input bar.
- **Visual Progress Bar (`QProgressBar`)**: 2-decimal precision (`0-100.00%`) progress indicator chunk-filled with QSS gradients.
- **Dynamic Status Banner Card**: Dynamic stage badges (`📋 SCANNING`, `⚡ IN-PROGRESS`, `🎉 COMPLETED`, `⛔ ABORTED`, `⚠️ WARNING`, `🌙 DEVICE SLEEP`).
- **Automated Telemetry Abstraction**: Regex engine parsing UIN (`ACON...`), IMEI, VIN, Firmware Version, and State across multi-line boot logs.
- **3 Server Status Execution Engine**:
  - **`Pending` / `In-Progress`**: SKIPS issuing new API POST calls to prevent server task cancellations; re-attaches poller.
  - **`Aborted`**: Resolves next version after aborted target and submits new API trigger.
  - **`Completed`**: Resolves next sequential version (`idx + 1`) after completed version and submits new API trigger.
- **PyInstaller Executable Packaging**: Bundles `.env`, `input/servers.json`, and assets into a single standalone `.exe`.

---

## 🚀 Quickstart Guide

### 1. Requirements & Setup
- Windows 10/11
- Python 3.10+
- Installed Dependencies:
  ```bash
  pip install PyQt6 pyserial requests urllib3 python-dotenv
  ```

### 2. Run Application from Source
```bash
python main.py
```

### 3. Build Standalone Executable (`Continuos_Fota.exe`)
```powershell
pyinstaller --noconfirm --noconsole --onefile --icon="assets/logo.ico" --name "Continuos_Fota" --add-data ".env;." --add-data "input;input" --add-data "assets;assets" --hidden-import PyQt6 --hidden-import serial --hidden-import serial.tools.list_ports --hidden-import requests --hidden-import urllib3 --hidden-import dotenv main.py
```
Generated binary located at `dist/Continuos_Fota.exe`.

---

## 📁 Repository Structure

```text
FOTA_ACTIVITY/
├── backend/
│   ├── api_client.py           # REST API authentication & endpoint client
│   ├── config.py               # Multi-candidate .env & path loader
│   ├── firmware_resolver.py    # Multi-field version matching & idx+1 resolver
│   ├── message_parser.py       # Regex telemetry & boot log parser
│   ├── models.py               # FotaTriggerPayload & LoginPacketInfo dataclasses
│   ├── orchestrator.py         # 3-status logic engine & audit logger
│   ├── path_resolver.py        # PyInstaller sys.frozen base directory resolver
│   └── serial_worker.py        # PySerial QThread background reader
├── input/
│   └── servers.json            # Cached API state server matrix
├── logs/
│   └── fota_activity.log       # Application execution logs
├── results/
│   ├── active_fota.json        # Real-time active FOTA session state
│   ├── fota_results.csv        # CSV audit log
│   └── fota_results.json       # JSON audit log
├── ui/
│   ├── app.py                  # PyQt6 Main Window & 3-Tab controller
│   ├── styles.py               # Light & Cyber-Dark QSS theme stylesheets
│   └── widgets.py              # Custom widgets (Audit Table, Analytics Dashboard, Terminal)
├── main.py                     # Entry point & logging setup
├── sop.md                      # Standard Operating Procedure (SOP)
├── README.md                   # Repository documentation
└── fota_utility.spec           # PyInstaller spec build file
```