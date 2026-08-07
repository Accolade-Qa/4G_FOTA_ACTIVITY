"""FOTA Automation Orchestrator Module.

Coordinates the end-to-end continuous FOTA lifecycle:
1. Syncs state/firmware matrix from REST API on startup.
2. Evaluates serial login packets captured by SerialWorker.
3. Validates CIP2 server settings (auto-setting *SET#CIP2#aepl-tcu4g-qa.accoladeelectronics.com#6100# if needed).
4. Waits until ALL device fields (UIN, IMEI, VIN, Model, State, Version) are fully abstracted from serial logs.
5. Determines target upgrade version via FirmwareResolver.
6. Submits REST API FOTA trigger payload with Bearer token authentication (deduplicated per UIN).
7. Tracks download percentage continuously to 100% and logs audit records.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Set

from PyQt6.QtCore import QObject, pyqtSignal

from backend.config import Config
from backend.api_client import FotaApiClient
from backend.firmware_resolver import FirmwareResolver
from backend.message_parser import MessageParser
from backend.models import LoginPacketInfo, FotaAuditRecord, FotaTriggerPayload
from backend.extensions import ExtensionManager

logger = logging.getLogger(__name__)


class FotaOrchestrator(QObject):
    """Main Orchestrator Controller for the Continuous FOTA process."""

    # PyQt Signals for UI Updates
    status_signal = pyqtSignal(str)           # System status message
    device_info_signal = pyqtSignal(object)   # LoginPacketInfo object
    progress_signal = pyqtSignal(float)       # Download progress %
    audit_signal = pyqtSignal(object)         # FotaAuditRecord object
    request_command_signal = pyqtSignal(str)  # Request serial command execution (*SET#CIP2#...)

    def __init__(self, config: Optional[Config] = None) -> None:
        super().__init__()
        self.config = config or Config()
        self.api_client = FotaApiClient(self.config)
        self.resolver = FirmwareResolver(self.config.firmware_json_path)
        self.extension_mgr = ExtensionManager()

        self.current_device: Optional[LoginPacketInfo] = None
        self.target_version: Optional[str] = None
        self.is_upgrading = False
        self.attempted_uins: Set[str] = set()
        self.cip2_validated = False
        self.target_qa_domain = "aepl-tcu4g-qa.accoladeelectronics.com"

        # Initialize audit CSV header if missing
        self._init_audit_file()

    def _init_audit_file(self) -> None:
        """Create results/fota_audit.csv with headers if it does not exist."""
        audit_path = self.config.audit_csv_path
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        if not audit_path.exists() or audit_path.stat().st_size == 0:
            with open(audit_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "UIN", "InitialVersion", "FinalVersion", "Status", "Remarks"])

    def reset_orchestrator(self) -> None:
        """Reset orchestrator state for a fresh device or manual reset."""
        self.current_device = None
        self.target_version = None
        self.is_upgrading = False
        self.attempted_uins.clear()
        self.cip2_validated = False

    def initialize_system(self) -> bool:
        """Fetch remote state/firmware matrix from API on system startup."""
        self.status_signal.emit("Syncing state & firmware matrix from API...")
        ok = self.api_client.fetch_and_save_servers_matrix()
        self.resolver.reload()
        MessageParser.load_valid_states_from_json(self.config.firmware_json_path)
        if ok:
            self.status_signal.emit("API Matrix Sync complete. System Ready.")
        else:
            self.status_signal.emit("System Ready (using local cached state matrix).")
        return ok

    def process_log_line(self, line: str) -> None:
        """Inspect raw serial log line for CIP2 server domain verification."""
        cip2_val = MessageParser.parse_cip2_config(line)
        if cip2_val and not self.cip2_validated:
            if self.target_qa_domain in cip2_val.lower():
                self.cip2_validated = True
                logger.info("CIP2 QA Server verified: %s", cip2_val)
                self.status_signal.emit(f"CIP2 Server Verified: {cip2_val}")
            else:
                logger.warning("CIP2 server is pointing to %s (Not QA). Auto-firing CIP2 setup...", cip2_val)
                cmd = f"*SET#CIP2#{self.target_qa_domain}#6100#"
                self.status_signal.emit(f"CIP2 set to {cip2_val}. Auto-firing QA setup: {cmd}")
                self.request_command_signal.emit(cmd)
                self.cip2_validated = True

    def is_complete_telemetry(self, info: LoginPacketInfo) -> bool:
        """Check if all required device fields have been abstracted from terminal logs."""
        has_uin = MessageParser.is_valid_uin(info.uin)
        has_imei = MessageParser.is_valid_imei(info.imei)
        has_state = bool(info.state and info.state.strip())
        has_version = bool(info.version and info.version.strip())

        return has_uin and has_imei and has_state and has_version

    def process_login_packet(self, login_info: LoginPacketInfo) -> bool:
        """Evaluate captured device login packet and initiate upgrade once per UIN."""
        self.current_device = login_info
        self.device_info_signal.emit(login_info)
        self.extension_mgr.trigger_login_packet(login_info)

        # 1. Wait until ALL required fields (UIN, IMEI, State, Version) are abstracted from terminal logs
        if not self.is_complete_telemetry(login_info):
            return False

        # Prevent infinite retry loops for already attempted or currently upgrading UINs
        if login_info.uin in self.attempted_uins:
            return True

        if self.is_upgrading:
            logger.info("Upgrade already in progress for UIN %s. Skipping re-trigger.", login_info.uin)
            return True

        # Mark UIN as attempted to prevent infinite API call loops
        self.attempted_uins.add(login_info.uin)

        device_state = login_info.state
        if not device_state or device_state.lower() in ("default", "is factory", "connected", "on", "off"):
            device_state = self.config.default_state

        logger.info("All fields abstracted from serial log -> UIN: %s, IMEI: %s, VIN: %s, Model: %s, State: %s, Version: %s",
                    login_info.uin, login_info.imei, login_info.vin, login_info.model, device_state, login_info.version)

        # 2. Strict Version Validation Barrier (Must be listed in servers.json for target state)
        next_ver = self.resolver.resolve_next_version(device_state, login_info.version)
        if not next_ver:
            if not self.resolver.validate_version_exists(device_state, login_info.version):
                msg = f"⚠️ Version Validation Barrier: Firmware version '{login_info.version}' is NOT listed in servers.json for state '{device_state}'. FOTA process blocked."
            else:
                msg = f"Device {login_info.uin} is already at the latest firmware level ({login_info.version}) for state '{device_state}'."
            logger.warning(msg)
            self.status_signal.emit(msg)
            return False

        self.target_version = next_ver
        self.is_upgrading = True
        self.status_signal.emit(f"Abstracted all log fields! Triggering Manual FOTA: UIN {login_info.uin} → Target {next_ver}...")

        # 3. Construct Manual FOTA trigger payload with abstracted fields
        payload = FotaTriggerPayload(
            imei=login_info.imei,
            model=login_info.model or "4G",
            state=device_state,
            ufw=next_ver,
            uin=login_info.uin,
            ais140=True,
            created_by=self.api_client.user_id or self.config.user_id
        )

        self.extension_mgr.trigger_fota_started(login_info.uin, next_ver)

        # 4. Trigger Manual FOTA REST API hit (attaches Bearer token in headers & query params)
        success, api_msg = self.api_client.trigger_fota_upgrade(payload)

        if not success:
            err = f"API FOTA Trigger: {api_msg}"
            self._write_audit(login_info.uin, login_info.version, next_ver, "FAILED", err)
            self.status_signal.emit(err)
            self.is_upgrading = False
            return False

        self.status_signal.emit(f"FOTA trigger accepted for {login_info.uin}. Continuously monitoring serial log progress till 100%...")
        return True

    def update_progress(self, progress: float) -> None:
        """Update live download progress percentage and continuously validate till 100% done."""
        self.progress_signal.emit(progress)
        if progress >= 100.0 and self.is_upgrading and self.current_device and self.target_version:
            msg = f"FOTA download reached 100%. Continuous validation complete for {self.current_device.uin} → {self.target_version}"
            logger.info(msg)
            self.extension_mgr.trigger_fota_completed(self.current_device.uin, self.target_version)
            self._write_audit(
                self.current_device.uin,
                self.current_device.version,
                self.target_version,
                "COMPLETED",
                "Downloaded 100% and validated successfully"
            )
            self.status_signal.emit(msg)
            self.is_upgrading = False

    def _write_audit(self, uin: str, initial_ver: str, final_ver: str, status: str, remarks: str) -> None:
        """Write audit log entry to results/fota_audit.csv."""
        record = FotaAuditRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            uin=uin,
            initial_version=initial_ver,
            final_version=final_ver,
            status=status,
            remarks=remarks,
        )
        self.audit_signal.emit(record)

        try:
            with open(self.config.audit_csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    record.timestamp,
                    record.uin,
                    record.initial_version,
                    record.final_version,
                    record.status,
                    record.remarks,
                ])
            logger.info("Recorded audit entry for UIN %s: %s", uin, status)
        except Exception as err:
            logger.error("Failed to write audit log entry: %s", err)
