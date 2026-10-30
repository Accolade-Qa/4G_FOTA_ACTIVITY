"""Data Models Module.

Defines domain entities and telemetry records used across the FOTA automation system.
Enforces strict type safety and field validation.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class LoginPacketInfo:
    """Represents device telemetry received in a boot/login packet over Serial COM."""
    imei: str
    iccid: str
    uin: str
    version: str
    vin: str
    model: str
    state: str
    raw_packet: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoginPacketInfo":
        """Construct model instance from dictionary."""
        return cls(
            imei=data.get("imei", ""),
            iccid=data.get("iccid", ""),
            uin=data.get("uin", ""),
            version=data.get("version", ""),
            vin=data.get("vin", ""),
            model=data.get("model", ""),
            state=data.get("state", "Default"),
            raw_packet=data.get("raw_packet", ""),
            timestamp=data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]),
        )


@dataclass
class FotaAuditRecord:
    """Represents an audit entry written to fota_audit.csv upon FOTA completion or rejection."""
    uin: str
    initial_version: str
    final_version: str
    status: str  # e.g., 'COMPLETED', 'REJECTED', 'FAILED'
    remarks: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_csv_row(self) -> list[str]:
        return [self.timestamp, self.uin, self.initial_version, self.final_version, self.status, self.remarks]


@dataclass
class FotaTriggerPayload:
    """Payload data structure sent to createManualFota REST API to trigger single device FOTA upgrade."""
    imei: str
    model: str
    state: str
    ufw: str
    uin: str
    ais140: bool = True
    created_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "IMEI": self.imei,
            "MODEL": self.model or "4G",
            "STATE": self.state,
            "UFW": self.ufw,
            "UIN": self.uin,
            "ais140": self.ais140,
            "createdBy": self.created_by
        }
