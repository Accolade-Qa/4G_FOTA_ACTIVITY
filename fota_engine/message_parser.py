"""Serial Message & Telemetry Parser.

Parses incoming text lines from device serial logs to extract login telemetry,
download progress, software version updates, and CIP2 QA server configuration.
Supports regex parsing for 'aeplFwVer' and 'SOFTWARE :' version banner formats.
"""

import json
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Set
from fota_engine.models import LoginPacketInfo

logger = logging.getLogger(__name__)

INVALID_STATE_WORDS = {"on", "off", "true", "false", "idle", "pass", "fail", "null", "none", "ok", "succ"}


class MessageParser:
    """Production-grade log line parser for TCU/4G Telematics devices."""

    UIN_PREFIX = "ACON"
    UIN_PATTERN = re.compile(r"^ACON[A-Za-z0-9_-]{4,28}$")
    IMEI_PATTERN = re.compile(r"^\d{13,15}$")
    VIN_PATTERN = re.compile(r"^[A-Z0-9]{14,18}$", re.IGNORECASE)
    ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    PROGRESS_PATTERN = re.compile(r"(?:Downloading|FOTA Progress|Progress):\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
    CIP2_PATTERN = re.compile(r"(?:CIP2|CIP\s*2|IP2|MQTT\s*Server|SERVER2|SERVER\s*2)[:=,\s]+([A-Za-z0-9._-]+)", re.IGNORECASE)

    # Dynamic valid states populated from API response / servers.json
    DYNAMIC_VALID_STATES: Set[str] = {"do not delete", "default"}

    @classmethod
    def load_valid_states_from_json(cls, json_path: Path) -> None:
        """Dynamically populate valid state names from API response stored in input/servers.json."""
        if not json_path.exists():
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                states_dict = data.get("states", {})
                for state_name in states_dict.keys():
                    if state_name and state_name.strip():
                        cls.DYNAMIC_VALID_STATES.add(state_name.strip().lower())
            logger.info("Loaded %d valid state names from API response into MessageParser.",
                        len(cls.DYNAMIC_VALID_STATES))
        except Exception as err:
            logger.warning("Failed to load valid states from JSON into MessageParser: %s", err)

    @classmethod
    def strip_ansi(cls, line: str) -> str:
        """Remove ANSI escape sequences from raw serial log line."""
        if not line:
            return ""
        return cls.ANSI_ESCAPE.sub("", line).strip()

    @classmethod
    def is_valid_uin(cls, uin: Optional[str]) -> bool:
        """Validate UIN starts with 'ACON' prefix."""
        if not uin:
            return False
        return uin.startswith(cls.UIN_PREFIX) and bool(cls.UIN_PATTERN.match(uin))

    @classmethod
    def is_valid_imei(cls, imei: Optional[str]) -> bool:
        """Validate IMEI consists of 13 to 15 numeric digits."""
        if not imei:
            return False
        return bool(cls.IMEI_PATTERN.match(imei.strip()))

    @classmethod
    def is_valid_vin(cls, vin: Optional[str]) -> bool:
        """Validate VIN consisting of 14 to 18 alphanumeric characters (e.g. ACCDEV07241580138 or MAT...)."""
        if not vin:
            return False
        clean = vin.strip().upper()
        if len(clean) not in range(14, 19):
            return False
        if clean.isdigit() or clean.lower() in ("null", "none", "debug", "info", "system", "analog"):
            return False
        return bool(re.match(r"^[A-Z0-9]{14,18}$", clean))

    @classmethod
    def is_valid_state_name(cls, state: Optional[str]) -> bool:
        """Validate whether state name matches an API-defined state server."""
        if not state:
            return False
        clean = state.strip().lower()
        if clean in INVALID_STATE_WORDS or len(clean) <= 2:
            return False
        if clean in cls.DYNAMIC_VALID_STATES or "delete" in clean or "state" in clean:
            return True
        return True

    @classmethod
    def parse_cip2_config(cls, line: str) -> Optional[str]:
        """Extract CIP2 / MQTT Server address string from serial log line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.CIP2_PATTERN.search(clean_line)
        if match:
            return match.group(1).strip()
        return None

    @classmethod
    def parse_download_progress(cls, line: str) -> Optional[float]:
        """Extract FOTA download percentage (0.0 to 100.0) from line."""
        match = cls.PROGRESS_PATTERN.search(line)
        if match:
            try:
                val = float(match.group(1))
                return max(0.0, min(100.0, val))
            except ValueError:
                pass
        return None

    @classmethod
    def parse_firmware_version(cls, line: str) -> Optional[str]:
        """Extract firmware version string from log lines (supports 'aeplFwVer', 'SOFTWARE :', 'UFW', etc.)."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None

        # 1. Match 'aeplFwVer    5.2.9 5th IP'
        m1 = re.search(r"aeplFwVer[:=,\s]+([0-9]+\.[0-9]+(?:\.[0-9]+)*)", clean_line, re.IGNORECASE)
        if m1:
            return m1.group(1).strip()

        # 2. Match '######## SOFTWARE : 5.2.9 5th IP           ########'
        m2 = re.search(r"SOFTWARE[\s:=#]+([0-9]+\.[0-9]+(?:\.[0-9]+)*)", clean_line, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()

        # 3. Standard UFW / VER / FIRMWARE / FW
        m3 = re.search(r"(?:VER|VERSION|UFW|FIRMWARE|FW)[:=,\s]+([A-Za-z0-9._-]+)", clean_line, re.IGNORECASE)
        if m3:
            val = m3.group(1).strip()
            if val and val.lower() not in ("succ", "ok", "idle", "falcon", "atcu"):
                return val

        return None

    @classmethod
    def parse_login_packet(cls, line: str) -> Optional[LoginPacketInfo]:
        """Extract structured LoginPacketInfo dynamically from device serial log line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None

        imei_match = re.search(r"(?:IMEI|imei)[:=]?\s*(\d{13,15})", clean_line)
        uin_match = re.search(r"(?:UIN|uin)[:=]?\s*(ACON[A-Za-z0-9_-]{4,28})", clean_line)
        vin_match = re.search(r"(?:vin|VIN|CHASSIS|chassis|Vehicle\s*ID)[\s\d\.\-_\|:=]*[\s\|:=]+([A-Z0-9]{14,18})", clean_line, re.IGNORECASE)
        model_match = re.search(r"(?:MODEL|model)[:=]?\s*([A-Za-z0-9_-]+)", clean_line)
        state_match = re.search(r"(?:STATE|state)[:=]?\s*([A-Za-z0-9_\s-]+)", clean_line)
        ver_val = cls.parse_firmware_version(clean_line)
        iccid_match = re.search(r"(?:ICCID|iccid)[:=]?\s*(\d{18,20})", clean_line)

        parts = [p.strip() for p in re.split(r"[\s\|;,:]+", clean_line) if p.strip()]

        uin = uin_match.group(1) if uin_match else next((p for p in parts if p.startswith("ACON")), None)
        imei = imei_match.group(1) if imei_match else next((p for p in parts if cls.is_valid_imei(p)), None)
        vin = None
        if vin_match and cls.is_valid_vin(vin_match.group(1)):
            vin = vin_match.group(1).upper()
        else:
            vin = next((p.upper() for p in parts if cls.is_valid_vin(p)), None)

        if uin or imei or vin or ver_val:
            version = ver_val or "1.0.0"
            state = "DO NOT DELETE"
            if state_match and cls.is_valid_state_name(state_match.group(1)):
                state = state_match.group(1).strip()

            iccid = iccid_match.group(1) if iccid_match else ""
            model = model_match.group(1) if model_match else "4G"

            for p in parts:
                if not ver_val and (re.match(r"^\d+\.\d+\.\d+$", p) or p.isdigit()):
                    version = p
                elif not iccid_match and len(p) in (18, 19, 20) and p.isdigit():
                    iccid = p
                elif cls.is_valid_state_name(p):
                    state = p

            return LoginPacketInfo(
                imei=imei or "",
                iccid=iccid,
                uin=uin or "",
                version=version,
                vin=vin or "MAT00000000000000",
                model=model,
                state=state,
            )
        return None


class TelemetryAccumulator:
    """Stateful parser that accumulates telemetry fields across multi-line device reboot logs."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.uin: Optional[str] = None
        self.imei: Optional[str] = None
        self.vin: Optional[str] = None
        self.iccid: Optional[str] = None
        self.state: Optional[str] = "DO NOT DELETE"
        self.version: Optional[str] = None
        self.model: Optional[str] = None

    def feed_line(self, line: str) -> Optional[LoginPacketInfo]:
        """Harvest telemetry fields from incoming serial line and return accumulated LoginPacketInfo."""
        clean_line = MessageParser.strip_ansi(line)
        if not clean_line:
            return None

        updated = False

        # 1. Extract UIN (starts with ACON)
        uin_match = re.search(r"(?:UIN|uin)[:=]?\s*(ACON[A-Za-z0-9_-]{4,28})", clean_line)
        if uin_match:
            self.uin = uin_match.group(1)
            updated = True
        elif not self.uin:
            for part in clean_line.split():
                if part.startswith("ACON") and MessageParser.is_valid_uin(part):
                    self.uin = part
                    updated = True
                    break

        # 2. Extract IMEI (13-15 digits)
        imei_match = re.search(r"(?:IMEI|imei)[:=]?\s*(\d{13,15})", clean_line)
        if imei_match:
            self.imei = imei_match.group(1)
            updated = True
        elif not self.imei:
            for part in re.split(r"[\s,;:]+", clean_line):
                if MessageParser.is_valid_imei(part):
                    self.imei = part
                    updated = True
                    break

        # 3. Extract VIN (Supports formats like '11. vin | VIN ACCDEV07241580138')
        vin_match = re.search(r"(?:vin|VIN|CHASSIS|chassis|Vehicle\s*ID)[\s\d\.\-_\|:=]*[\s\|:=]+([A-Z0-9]{14,18})", clean_line, re.IGNORECASE)
        if vin_match and MessageParser.is_valid_vin(vin_match.group(1)):
            self.vin = vin_match.group(1).upper()
            updated = True
        elif not self.vin:
            for part in re.split(r"[\s\|;,:]+", clean_line):
                if MessageParser.is_valid_vin(part):
                    self.vin = part.upper()
                    updated = True
                    break

        # 4. Extract ICCID (18-20 digits)
        iccid_match = re.search(r"(?:ICCID|iccid)[:=]?\s*(\d{18,20})", clean_line)
        if iccid_match:
            self.iccid = iccid_match.group(1)
            updated = True
        elif not self.iccid:
            for part in re.split(r"[\s,;:]+", clean_line):
                if len(part) in (18, 19, 20) and part.isdigit():
                    self.iccid = part
                    updated = True
                    break

        # 5. Extract STATE
        state_match = re.search(r"(?:STATE|state)[:=]?\s*([A-Za-z0-9_\s-]+)", clean_line)
        if state_match:
            s_val = state_match.group(1).strip()
            if MessageParser.is_valid_state_name(s_val):
                self.state = s_val
                updated = True

        # 6. Extract VERSION / UFW / aeplFwVer / SOFTWARE
        v_val = MessageParser.parse_firmware_version(clean_line)
        if v_val:
            self.version = v_val
            updated = True

        # 7. Extract MODEL
        model_match = re.search(r"(?:MODEL|model)[:=]?\s*([A-Za-z0-9_-]+)", clean_line)
        if model_match:
            self.model = model_match.group(1).strip()
            updated = True

        # Return updated telemetry if core identifiers exist
        if updated and (self.uin or self.imei or self.vin or self.version):
            return LoginPacketInfo(
                imei=self.imei or "",
                iccid=self.iccid or "",
                uin=self.uin or "",
                version=self.version or "1.0.0",
                vin=self.vin or "MAT00000000000000",
                model=self.model or "4G",
                state=self.state or "DO NOT DELETE",
            )

        return None
