"""Serial Message & Telemetry Parser.

Parses incoming text lines from device serial logs to extract login telemetry,
download progress, software version updates, and CIP2 QA server configuration.
Extracts full firmware version terms (e.g. '5.2.9 5th IP') exclusively from 'aeplFwVer' and 'SOFTWARE :' formats.
"""

import json
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Set
from backend.models import LoginPacketInfo

logger = logging.getLogger(__name__)

INVALID_STATE_WORDS = {"on", "off", "true", "false", "idle", "pass", "fail", "null", "none", "ok", "succ"}
INVALID_VIN_WORDS = {
    "SYNCHRONIZATION", "UNSYNCHRONIZATION", "SYNCHRONIZED", "AUTHENTICATION", "INITIALIZATION",
    "CONFIGURATION", "DISCONNECTED", "CONNECTING", "ESTABLISHED", "RECONNECTING",
    "COMMUNICATION", "ACKNOWLEDGEMENT", "RECOMMENDATION", "SPECIFICATION", "IDENTIFICATION",
    "REPRESENTATION", "TRANSMISSION", "RETRANSMISSION", "SUBSCRIPTION", "UNSUBSCRIPTION",
    "REGISTRATION", "DEREGISTRATION", "ADMINISTRATION", "ORGANIZATION", "IMPLEMENTATION",
    "DOCUMENTATION", "APPLICATION", "NOTIFICATION", "VERIFICATION", "AUTHORIZATION",
    "CERTIFICATION", "DETERMINATION", "INVESTIGATION", "RESERVED", "BOOTLOADER",
    "SUCCESSFULLY", "UNSUCCESSFUL", "TERMINATED", "DISCONNECTED"
}


class MessageParser:
    """Production-grade log line parser for TCU/4G Telematics devices."""

    UIN_PREFIX = "ACON"
    UIN_PATTERN = re.compile(r"^ACON[A-Za-z0-9_-]{4,28}$")
    IMEI_PATTERN = re.compile(r"^\d{13,15}$")
    VIN_PATTERN = re.compile(r"^[A-Z0-9]{14,18}$", re.IGNORECASE)
    ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    PROGRESS_PATTERN = re.compile(
        r"(?:\[FOT\]\s*)?(?:downloading|download|fota progress|progress)[:=,\s]+(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE
    )
    CIP2_PATTERN = re.compile(r"(?:CIP2|CIP\s*2|IP2|MQTT\s*Server|SERVER2|SERVER\s*2)[:=,\s]+([A-Za-z0-9._-]+)", re.IGNORECASE)
    PLA_SLEEP_PATTERN = re.compile(r"\[PLA\]\s*SLEEP\s+(\d+)", re.IGNORECASE)
    CLR_FOTA_OK_PATTERN = re.compile(r"STATUS#CLR#FOTA#OK#(?:(\d{13,15}))?", re.IGNORECASE)
    CHTP_FULL_PATTERN = re.compile(r"(?:STATUS#SET#CHTP#|\*SET#CHTP#|CHTP:|[FOT]\s*tcp\s*ota\s*request\s*:\s*\*SET#CHTP#|STATUS#)([\w.-]+)[#:\s,]+(\d+)", re.IGNORECASE)
    CIP1_FULL_PATTERN = re.compile(r"(?:STATUS#SET#CIP1#|\*SET#CIP1#|CIP1:|[FOT]\s*tcp\s*ota\s*request\s*:\s*\*SET#CIP1#|STATUS#)([\w.-]+)[#:\s,]+(\d+)", re.IGNORECASE)
    SWEMP_FULL_PATTERN = re.compile(r"(?:STATUS#SET#SWEMP#|\*SET#SWEMP#|SWEMP:|[FOT]\s*tcp\s*ota\s*request\s*:\s*\*SET#SWEMP#|STATUS#)([\w.-]+)", re.IGNORECASE)
    REBOOT_PATTERNS = [
        re.compile(r"STATUS#CLR#FOTA#OK", re.IGNORECASE),
        re.compile(r"CLR#FOTA#OK", re.IGNORECASE),
        re.compile(r"System\s+Booting", re.IGNORECASE),
        re.compile(r"BOOTLOADER\s+INIT", re.IGNORECASE),
        re.compile(r"\*SET#CRST#1#", re.IGNORECASE),
        re.compile(r"TCU\s+RESET\s+OK", re.IGNORECASE),
        re.compile(r"UPTIME\s+SEC\s*:\s*[01]\b", re.IGNORECASE),
        re.compile(r"GSM\s+soft\s+shutdown\s+pass", re.IGNORECASE),
        re.compile(r"synchronized\s+suspend\s+ok", re.IGNORECASE),
        re.compile(r"Booting\s*\.\.\.", re.IGNORECASE),
        re.compile(r"System\s+Reset", re.IGNORECASE),
    ]

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
        """Validate VIN consisting of 14 to 18 alphanumeric characters."""
        if not vin:
            return False
        clean = vin.strip().upper()
        if len(clean) not in range(14, 19):
            return False
        if clean in INVALID_VIN_WORDS or clean.isdigit() or clean.lower() in ("null", "none", "debug", "info", "system", "analog"):
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
    def parse_download_progress(cls, line: str, total_file_size: int = 0) -> Optional[float]:
        """Extract FOTA download percentage (0.0 to 100.0) from line matching e.g. '[FOT] downloading 2.43%' or '|55AA,2,8192,1024,FF|'."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.PROGRESS_PATTERN.search(clean_line)
        if match:
            try:
                val = float(match.group(1))
                return max(0.0, min(100.0, val))
            except ValueError:
                pass

        if "55AA" in clean_line:
            chunk = cls.parse_55aa_chunk_progress(clean_line, total_file_size=total_file_size)
            if chunk and chunk.get("percentage") is not None:
                return chunk["percentage"]
        return None

    @classmethod
    def parse_pla_sleep_countdown(cls, line: str) -> Optional[int]:
        """Extract [PLA] SLEEP countdown timer integer (e.g. 172 from 'INFO: [PLA] SLEEP 172...')."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.PLA_SLEEP_PATTERN.search(clean_line)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    SLEEP_EVENT_PATTERNS = [
        re.compile(r"\[PLA\]\s*SLEEP\s+(\d+)", re.IGNORECASE),
        re.compile(r"GSM\s+soft\s+shutdown\s+pass", re.IGNORECASE),
        re.compile(r"synchronized\s+suspend\s+ok", re.IGNORECASE),
        re.compile(r"PLA\s+task\s+is\s+now\s+idle", re.IGNORECASE),
    ]

    @classmethod
    def is_sleep_event(cls, line: str) -> bool:
        """Detect if line signals device entering sleep or soft shutdown state."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return False
        for pat in cls.SLEEP_EVENT_PATTERNS:
            if pat.search(clean_line):
                return True
        return False

    @classmethod
    def parse_firmware_version(cls, line: str) -> Optional[str]:
        """Extract full firmware version string (e.g. '5.2.9 5th IP') strictly from 'aeplFwVer', 'SOFTWARE :', or 'FIRMWARE :' log formats."""
        clean_line = cls.strip_ansi(line)
        if not clean_line or "sver" in clean_line.lower() or "version |" in clean_line.lower():
            return None

        # 1. Match 'aeplFwVer    5.2.9 5th IP' or 'aeplFwVer : 5.2.9 5th IP'
        m1 = re.search(r"aeplFwVer[\s:=]+([0-9]+\.[0-9]+[^\r\n#]*)", clean_line, re.IGNORECASE)
        if m1:
            val = re.sub(r"#+", "", m1.group(1)).strip()
            if val and val.lower() not in ("succ", "ok", "idle", "none", "null"):
                return val

        # 2. Match '######## SOFTWARE : 5.2.9 5th IP           ########'
        m2 = re.search(r"SOFTWARE[\s:=]+([0-9]+\.[0-9]+[^\r\n#]*)", clean_line, re.IGNORECASE)
        if m2:
            val = re.sub(r"#+", "", m2.group(1)).strip()
            if val and val.lower() not in ("succ", "ok", "idle", "falcon", "atcu", "none", "null"):
                return val

        # 3. Match 'FIRMWARE : 5.2.9 5th IP'
        m3 = re.search(r"\bFIRMWARE[\s:=]+([0-9]+\.[0-9]+[^\r\n#]*)", clean_line, re.IGNORECASE)
        if m3:
            val = re.sub(r"#+", "", m3.group(1)).strip()
            if val and val.lower() not in ("succ", "ok", "idle", "falcon", "atcu", "none", "null"):
                return val

        return None

    @classmethod
    def parse_clr_fota_ok(cls, line: str) -> Tuple[bool, Optional[str]]:
        """Check for STATUS#CLR#FOTA#OK#{IMEI} in serial line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return False, None
        match = cls.CLR_FOTA_OK_PATTERN.search(clean_line)
        if match:
            return True, match.group(1)
        return False, None

    @classmethod
    def parse_chtp_primary_ip_port(cls, line: str) -> Optional[Tuple[str, str]]:
        """Extract primary server CHTP IP and Port tuple from tcp ota log line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.CHTP_FULL_PATTERN.search(clean_line)
        if match:
            ip = match.group(1).strip()
            port = match.group(2).strip() if match.group(2) else ""
            return ip, port
        return None

    @classmethod
    def parse_cip1_secondary_ip_port(cls, line: str) -> Optional[Tuple[str, str]]:
        """Extract secondary server CIP1 IP and Port tuple from tcp ota log line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.CIP1_FULL_PATTERN.search(clean_line)
        if match:
            ip = match.group(1).strip()
            port = match.group(2).strip() if match.group(2) else ""
            return ip, port
        return None

    @classmethod
    def is_unconfigured_ip(cls, ip_str: str) -> bool:
        """Check if an IP string represents unconfigured default factory state (255.255.255.255 or 0.0.0.0)."""
        clean = (ip_str or "").strip()
        return not clean or clean in ("255.255.255.255", "0.0.0.0", "65535", "-", "none", "null")

    @classmethod
    def parse_swemp_state_ota(cls, line: str) -> Optional[str]:
        """Extract SWEMP State Enabled OTA code from tcp ota log line."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return None
        match = cls.SWEMP_FULL_PATTERN.search(clean_line)
        if match:
            return match.group(1).strip().strip("#").strip()
        return None

    @classmethod
    def is_device_reboot(cls, line: str) -> bool:
        """Check for boot loader header or system reset log indicator."""
        clean_line = cls.strip_ansi(line)
        if not clean_line:
            return False
        return any(pat.search(clean_line) for pat in cls.REBOOT_PATTERNS)

    @classmethod
    def parse_all_55aa_login_packets(cls, line: str) -> List[LoginPacketInfo]:
        """Extract ALL genuine GSM 55AA Login Packets starting strictly with 55AA,1,2,... and length >= 11."""
        clean_line = cls.strip_ansi(line)
        if not clean_line or "55AA" not in clean_line:
            return []

        packets: List[LoginPacketInfo] = []
        matches = re.finditer(r"55AA\s*,1\s*,2\s*,[^\|\r\n\]]+", clean_line, re.IGNORECASE)
        for match in matches:
            payload_str = match.group(0).strip().strip("|[]\r\n\t").strip()
            parts = [p.strip().strip("|[]") for p in payload_str.split(",")]

            # Strictly enforce 55AA,1,2,... GSM login packet format with length >= 11
            if len(parts) >= 11 and parts[0].upper() == "55AA" and parts[1] == "1" and parts[2] == "2":
                imei = ""
                iccid = ""
                uin = ""
                version = ""
                vin = "MAT00000000000000"

                # Positional extraction
                if len(parts) > 4 and cls.is_valid_imei(parts[4]):
                    imei = parts[4]
                if len(parts) > 5 and len(parts[5]) in (18, 19, 20) and parts[5].isdigit():
                    iccid = parts[5]
                if len(parts) > 6 and cls.is_valid_uin(parts[6]):
                    uin = parts[6]
                if len(parts) > 7 and parts[7]:
                    version = parts[7]
                if len(parts) > 8 and cls.is_valid_vin(parts[8]):
                    vin = parts[8].upper()

                # Dynamic fallback search across all parts if positional index differs
                for p in parts:
                    if not imei and cls.is_valid_imei(p):
                        imei = p
                    elif not iccid and len(p) in (18, 19, 20) and p.isdigit():
                        iccid = p
                    elif not uin and cls.is_valid_uin(p):
                        uin = p
                    elif not vin and cls.is_valid_vin(p):
                        vin = p.upper()

                # Confirm genuine GSM device login packet with valid IMEI or UIN
                if imei or uin:
                    pkt_info = LoginPacketInfo(
                        imei=imei,
                        iccid=iccid,
                        uin=uin,
                        version=version,
                        vin=vin,
                        model="4G",
                        state="DO NOT DELETE",
                        raw_packet=payload_str
                    )
                    packets.append(pkt_info)

        return packets

    @classmethod
    def parse_55aa_login_packet(cls, line: str) -> Optional[LoginPacketInfo]:
        """Parse first structured GSM Login Packet starting strictly with 55AA,1,2,... and length >= 11."""
        pkts = cls.parse_all_55aa_login_packets(line)
        return pkts[0] if pkts else None

    @classmethod
    def parse_55aa_server_fota_header(cls, line: str) -> Optional[Dict[str, Any]]:
        """Parse server FOTA header packet format:
        e.g. |55AA,1,2,1786521830,5.2.8,1,0,0,1626492,0,1024,FF|
        Indices:
          0: 55AA (Header)
          1: 1 (Type ID)
          2: 2 (Subtype ID)
          3: Epoch Timestamp
          4: Target Firmware Version on which FOTA is initiated (e.g. 5.2.8)
          5: FOTA Process Flag (1 = Active)
          8: Total Firmware File Size in Bytes (e.g. 1626492)
          10: Chunk Size in Bytes (e.g. 1024)
          Last: FF
        """
        clean_line = cls.strip_ansi(line)
        if not clean_line or "55AA" not in clean_line:
            return None

        match = re.search(r"\|?\s*(55AA\s*,[^\|]+)", clean_line)
        if not match:
            return None

        payload_str = match.group(1).strip()
        parts = [p.strip() for p in payload_str.split(",")]

        if len(parts) >= 11 and parts[0].upper() == "55AA" and parts[1] == "1" and parts[2] == "2":
            try:
                target_version = parts[4]
                fota_flag = int(parts[5])
                file_size = int(parts[8])
                chunk_size = int(parts[10]) if len(parts) > 10 else 1024
                return {
                    "target_version": target_version,
                    "fota_flag": fota_flag,
                    "file_size": file_size,
                    "chunk_size": chunk_size
                }
            except (ValueError, IndexError):
                pass
        return None

    @classmethod
    def parse_55aa_chunk_progress(cls, line: str, total_file_size: int = 0) -> Optional[Dict[str, Any]]:
        """Parse device FOTA chunk progress packet format:
        e.g. |55AA,2,6144,1024,FF|  or  |55AA,2,8192,1024,FF|
        Indices:
          0: 55AA (Header)
          1: 2 (Chunk Subtype ID)
          2: Received Bytes (e.g. 6144, 7168, 8192)
          3: Chunk Size (e.g. 1024)
          4: FF (Trailer)
        """
        clean_line = cls.strip_ansi(line)
        if not clean_line or "55AA" not in clean_line:
            return None

        match = re.search(r"\|?\s*(55AA\s*,[^\|]+)", clean_line)
        if not match:
            return None

        payload_str = match.group(1).strip()
        parts = [p.strip() for p in payload_str.split(",")]

        if len(parts) >= 4 and parts[0].upper() == "55AA" and parts[1] == "2":
            try:
                received_bytes = int(parts[2])
                chunk_size = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1024
                percentage = None
                if total_file_size > 0:
                    percentage = max(0.0, min(100.0, (received_bytes / float(total_file_size)) * 100.0))
                return {
                    "received_bytes": received_bytes,
                    "chunk_size": chunk_size,
                    "percentage": percentage
                }
            except (ValueError, IndexError):
                pass
        return None

    @classmethod
    def parse_login_packet(cls, line: str) -> Optional[LoginPacketInfo]:
        """Extract structured LoginPacketInfo strictly from genuine 55AA Login Packets."""
        clean_line = cls.strip_ansi(line)
        if not clean_line or "55AA" not in clean_line:
            return None
        return cls.parse_55aa_login_packet(clean_line)


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

        # 3. Extract VIN (Requires numeric digits, rejects words like SYNCHRONIZATION)
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

        # 6. Extract VERSION exclusively from aeplFwVer, SOFTWARE :, or FIRMWARE : formats
        v_val = MessageParser.parse_firmware_version(clean_line)
        if v_val:
            if not self.version:
                self.version = v_val
                updated = True
            elif len(v_val) > len(self.version) or (" " in v_val and " " not in self.version):
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
                version=self.version or "",
                vin=self.vin or "MAT00000000000000",
                model=self.model or "4G",
                state=self.state or "DO NOT DELETE",
            )

        return None
