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
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Set

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from backend.config import Config
from backend.api_client import FotaApiClient
from backend.firmware_resolver import FirmwareResolver
from backend.message_parser import MessageParser
from backend.models import LoginPacketInfo, FotaAuditRecord, FotaTriggerPayload
from backend.extensions import ExtensionManager

logger = logging.getLogger(__name__)


def is_active_fota_session(item: dict) -> bool:
    """Validate if FOTA history record represents an active running FOTA session on the backend server."""
    if not isinstance(item, dict):
        return False

    added_to_batch = item.get("addedToBatch") is True
    is_aborted = item.get("isAborted") is True
    is_completed = item.get("deviceFotaCompletionStatus") is True
    attempt_count = item.get("attemptCount", 0) or 0

    # Active if added to batch, not aborted, not completed, and attempt count < 3
    return added_to_batch and (not is_aborted) and (not is_completed) and (attempt_count < 3)


def save_active_fota_json(imei: str, uin: str, target_ver: str, state_name: str, item: dict) -> None:
    """Save/update active FOTA status information into results/active_fota.json."""
    try:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / "active_fota.json"

        data = {
            "imei": imei,
            "uin": uin,
            "targetFirmwareVersion": target_ver or item.get("targetFirmwareVersion"),
            "state": state_name or item.get("state"),
            "addedToBatch": item.get("addedToBatch", True),
            "isFotaInitiated": item.get("isFotaInitiated", True),
            "isAborted": item.get("isAborted", False),
            "abortReason": item.get("abortReason"),
            "deviceFotaStatus": item.get("deviceFotaStatus", "In-Progress"),
            "progress": item.get("progress", 0),
            "pingCount": item.get("pingCount", 0),
            "attemptCount": item.get("attemptCount", 0),
            "deviceFotaCompletionStatus": item.get("deviceFotaCompletionStatus", False),
            "lastUpdated": datetime.now().isoformat()
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved active FOTA info to %s", out_file)
    except Exception as err:
        logger.warning("Failed writing active_fota.json: %s", err)


class FotaAsyncTriggerWorker(QThread):
    """Background worker thread for non-blocking FOTA history check & REST API trigger execution."""

    finished_signal = pyqtSignal(bool, str, str, str, dict)  # (success, target_ver, api_msg, status_msg, raw_item)

    def __init__(self, orchestrator: "FotaOrchestrator", login_info: LoginPacketInfo, device_state: str, parent=None) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.login_info = login_info
        self.device_state = device_state

    def run(self) -> None:
        try:
            # 1. Non-blocking background API hit for FOTA Device History
            history = self.orchestrator.api_client.get_fota_device_history(self.login_info.imei)
            first_item = history[0] if (history and isinstance(history, list) and len(history) > 0) else {}

            # 2. Check if a FOTA session is ALREADY ACTIVE on the backend server
            if first_item and is_active_fota_session(first_item):
                target_ver = first_item.get("targetFirmwareVersion") or ""
                progress = float(first_item.get("progress") or 0.0)
                ping_cnt = first_item.get("pingCount", 0) or 0
                attempt_cnt = first_item.get("attemptCount", 0) or 0
                status_str = first_item.get("deviceFotaStatus") or "In-Progress"

                msg = (f"🔄 Active FOTA already running on server for IMEI {self.login_info.imei} "
                       f"(Target: {target_ver}, Status: {status_str}, Progress: {progress}%, Pings: {ping_cnt}, Attempts: {attempt_cnt}/3). "
                       f"Skipping new API trigger & re-attaching monitoring.")
                logger.info(msg)
                self.finished_signal.emit(True, target_ver, "ALREADY_ACTIVE", msg, first_item)
                return

            next_ver = None

            # 3. Check if previous FOTA was aborted
            if first_item:
                is_aborted = first_item.get("isAborted", False)
                abort_reason = first_item.get("abortReason") or ""
                aborted_target = first_item.get("targetFirmwareVersion") or ""

                if is_aborted or abort_reason:
                    logger.warning("Background FOTA History check for IMEI %s shows ABORTED ('%s'). Resolving next step version...",
                                   self.login_info.imei, abort_reason)
                    next_ver = self.orchestrator.resolver.resolve_next_version_after_aborted(self.device_state, self.login_info.version, aborted_target)

            if not next_ver:
                next_ver = self.orchestrator.resolver.resolve_next_version(self.device_state, self.login_info.version)

            if not next_ver:
                if not self.orchestrator.resolver.validate_version_exists(self.device_state, self.login_info.version):
                    msg = f"⚠️ Version Validation Barrier: Firmware version '{self.login_info.version}' is NOT listed in servers.json for state '{self.device_state}'. FOTA process blocked."
                else:
                    msg = f"Device {self.login_info.uin} is already at the latest firmware level ({self.login_info.version}) for state '{self.device_state}'."
                self.finished_signal.emit(False, "", "BLOCKED", msg, {})
                return

            # 4. Trigger new Manual FOTA REST API hit
            payload = FotaTriggerPayload(
                imei=self.login_info.imei,
                model=self.login_info.model or "4G",
                state=self.device_state,
                ufw=next_ver,
                uin=self.login_info.uin,
                ais140=True,
                created_by=self.orchestrator.api_client.user_id or self.orchestrator.config.user_id
            )

            success, api_msg = self.orchestrator.api_client.trigger_fota_upgrade(payload)
            msg = f"FOTA trigger accepted for {self.login_info.uin} → Target {next_ver}. Monitoring progress till 100%..." if success else f"API FOTA Trigger Error: {api_msg}"
            self.finished_signal.emit(success, next_ver, api_msg, msg, {})

        except Exception as err:
            logger.error("Async FOTA trigger worker exception: %s", err)
            self.finished_signal.emit(False, "", "ERROR", str(err), {})


class FotaApiPollerWorker(QThread):
    """Background polling thread that monitors active FOTA status from API.
    Polling frequency:
    - 10 minutes (600s) when progress < 95%
    - 2 minutes (120s) when progress >= 95% till 100% or completion/abort
    """

    poll_update_signal = pyqtSignal(dict)       # Emits raw history item dict
    poll_finished_signal = pyqtSignal(str, str)  # (status_type: "COMPLETED" | "ABORTED" | "ATTEMPTS_EXCEEDED", message)

    def __init__(self, orchestrator: "FotaOrchestrator", imei: str, parent=None) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.imei = imei
        self.running = True

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        logger.info("Started background FOTA API poller worker for IMEI %s", self.imei)

        while self.running:
            try:
                history = self.orchestrator.api_client.get_fota_device_history(self.imei)
                if history and isinstance(history, list) and len(history) > 0:
                    item = history[0]
                    self.poll_update_signal.emit(item)

                    progress = float(item.get("progress") or 0.0)
                    is_aborted = item.get("isAborted", False)
                    abort_reason = item.get("abortReason") or ""
                    attempt_count = item.get("attemptCount", 0) or 0
                    ping_count = item.get("pingCount", 0) or 0
                    is_completed = item.get("deviceFotaCompletionStatus", False)

                    # 1. Check if Aborted
                    if is_aborted or abort_reason:
                        msg = f"⛔ FOTA Aborted on server. Reason: '{abort_reason}'. Pings: {ping_count}, Attempts: {attempt_count}/3."
                        logger.warning(msg)
                        self.poll_finished_signal.emit("ABORTED", msg)
                        break

                    # 2. Check if Attempt Count Exceeded
                    if attempt_count >= 3:
                        msg = f"⛔ FOTA Aborted automatically on server: Attempt count reached limit ({attempt_count}/3). Pings: {ping_count}."
                        logger.warning(msg)
                        self.poll_finished_signal.emit("ATTEMPTS_EXCEEDED", msg)
                        break

                    # 3. Check if Completed
                    if is_completed or progress >= 100.0:
                        msg = f"🎉 FOTA completed successfully (100%). Pings: {ping_count}, Attempts: {attempt_count}/3."
                        logger.info(msg)
                        self.poll_finished_signal.emit("COMPLETED", msg)
                        break

                    # Determine adaptive polling delay: 600s (10 min) if < 95%, 120s (2 min) if >= 95%
                    sleep_sec = 120 if progress >= 95.0 else 600
                    logger.info("Polled IMEI %s -> Progress: %.1f%%, Pings: %d, Attempts: %d/3. Next poll in %d seconds.",
                                self.imei, progress, ping_count, attempt_count, sleep_sec)

                    for _ in range(sleep_sec):
                        if not self.running:
                            break
                        self.msleep(1000)

                else:
                    self.msleep(10000)

            except Exception as err:
                logger.error("FotaApiPollerWorker error for IMEI %s: %s", self.imei, err)
                self.msleep(10000)


class FotaOrchestrator(QObject):
    """Main Orchestrator Controller for the Continuous FOTA process."""

    # PyQt Signals for UI Updates
    status_signal = pyqtSignal(str)           # System status message
    progress_signal = pyqtSignal(float)        # Download percentage (0-100)
    device_info_signal = pyqtSignal(object)   # LoginPacketInfo entity
    audit_signal = pyqtSignal(object)         # FotaAuditRecord entity
    request_command_signal = pyqtSignal(str)  # Auto-execute serial AT command request

    def __init__(self, config: Optional[Config] = None) -> None:
        super().__init__()
        self.config = config or Config()
        self.api_client = FotaApiClient(self.config)
        self.resolver = FirmwareResolver(self.config.firmware_json_path)
        self.extension_mgr = ExtensionManager(self.config)

        self.current_device: Optional[LoginPacketInfo] = None
        self.target_version: Optional[str] = None
        self.is_upgrading: bool = False
        self.attempted_uins: Set[str] = set()
        self.cip2_validated: bool = False
        self.target_qa_domain = "aepl-tcu4g-qa.accoladeelectronics.com"
        self._trigger_worker: Optional[FotaAsyncTriggerWorker] = None
        self.poller_worker: Optional[FotaApiPollerWorker] = None

    def reset_orchestrator(self) -> None:
        """Reset orchestrator state upon manual UI telemetry clearing."""
        if self.poller_worker:
            self.poller_worker.stop()
            self.poller_worker = None
        self.current_device = None
        self.target_version = None
        self.is_upgrading = False
        self.attempted_uins.clear()
        self.cip2_validated = False

    def initialize_system(self) -> bool:
        """Synchronize State Server Matrix & Firmware IDs from REST API on startup."""
        logger.info("Initializing Continuous FOTA Orchestrator...")
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

    def is_complete_telemetry(self, info: LoginPacketInfo, selected_state: str = "") -> bool:
        """Check if all 5 required device fields (UIN, IMEI, VIN, Version, State) have been provided/abstracted."""
        has_uin = MessageParser.is_valid_uin(info.uin)
        has_imei = MessageParser.is_valid_imei(info.imei)
        has_vin = MessageParser.is_valid_vin(info.vin)
        has_version = bool(info.version and info.version.strip())

        target_state = selected_state or info.state
        has_state = bool(target_state and target_state.strip() and target_state.lower() not in ("no states", "---", ""))

        return has_uin and has_imei and has_vin and has_version and has_state

    def process_login_packet(self, login_info: LoginPacketInfo, selected_ui_state: str = "") -> bool:
        """Evaluate captured device login packet and initiate upgrade once per UIN (Asynchronous Non-Blocking)."""
        self.current_device = login_info

        if selected_ui_state and selected_ui_state.strip():
            login_info.state = selected_ui_state.strip()

        self.device_info_signal.emit(login_info)
        self.extension_mgr.trigger_login_packet(login_info)

        # 1. FOTA batch MUST NOT start until ALL 5 required fields are available
        if not self.is_complete_telemetry(login_info, selected_ui_state):
            missing = []
            if not MessageParser.is_valid_uin(login_info.uin): missing.append("UIN")
            if not MessageParser.is_valid_imei(login_info.imei): missing.append("IMEI")
            if not MessageParser.is_valid_vin(login_info.vin): missing.append("VIN")
            if not login_info.version: missing.append("Version")
            if not selected_ui_state: missing.append("Selected State")
            msg = f"Waiting for complete telemetry fields: missing ({', '.join(missing)})"
            self.status_signal.emit(msg)
            return False

        if login_info.uin in self.attempted_uins:
            return True

        if self.is_upgrading:
            logger.info("Upgrade already in progress for UIN %s. Skipping re-trigger.", login_info.uin)
            return True

        self.attempted_uins.add(login_info.uin)
        device_state = login_info.state

        logger.info("All 5 required fields abstracted -> UIN: %s, IMEI: %s, VIN: %s, Model: %s, State: %s, Version: %s",
                    login_info.uin, login_info.imei, login_info.vin, login_info.model, device_state, login_info.version)
        self.status_signal.emit(f"Abstracted all 5 telemetry fields! Checking active FOTA history in background...")

        self._trigger_worker = FotaAsyncTriggerWorker(self, login_info, device_state)
        self._trigger_worker.finished_signal.connect(self._on_trigger_finished)
        self._trigger_worker.start()
        return True

    def _on_trigger_finished(self, success: bool, target_ver: str, api_msg: str, status_msg: str, raw_item: dict) -> None:
        """Callback executed on Qt main thread when async trigger worker completes."""
        self.status_signal.emit(status_msg)
        if success and target_ver:
            self.target_version = target_ver
            self.is_upgrading = True

            # Save active FOTA status into results/active_fota.json
            if self.current_device:
                save_active_fota_json(self.current_device.imei, self.current_device.uin, target_ver, self.current_device.state, raw_item)
                self.extension_mgr.trigger_fota_started(self.current_device.uin, target_ver)

                # Launch adaptive API poller worker thread (10min <95%, 2min >=95%)
                if not self.poller_worker or not self.poller_worker.isRunning():
                    self.poller_worker = FotaApiPollerWorker(self, self.current_device.imei)
                    self.poller_worker.poll_update_signal.connect(self._on_poller_update)
                    self.poller_worker.poll_finished_signal.connect(self._on_poller_finished)
                    self.poller_worker.start()

        else:
            self.is_upgrading = False
            if self.current_device and api_msg != "BLOCKED":
                self._write_audit(self.current_device.uin, self.current_device.version, target_ver, "FAILED", status_msg)
            elif self.current_device and api_msg == "BLOCKED":
                self._write_audit(self.current_device.uin, self.current_device.version, "", "BLOCKED_VERSION_NOT_FOUND", status_msg)

    def _on_poller_update(self, item: dict) -> None:
        """Handle live FOTA history API poll updates."""
        progress = float(item.get("progress") or 0.0)
        status_str = item.get("deviceFotaStatus") or "In-Progress"
        ping_cnt = item.get("pingCount", 0) or 0
        attempt_cnt = item.get("attemptCount", 0) or 0

        self.progress_signal.emit(progress)
        status_msg = f"FOTA Status: {status_str} | Progress: {progress:.1f}% | Pings: {ping_cnt} | Attempts: {attempt_cnt}/3"
        self.status_signal.emit(status_msg)

        if self.current_device:
            save_active_fota_json(self.current_device.imei, self.current_device.uin, self.target_version or "", self.current_device.state, item)

    def _on_poller_finished(self, status_type: str, msg: str) -> None:
        """Handle completion or failure from background API poller worker."""
        self.status_signal.emit(msg)
        if self.current_device and self.target_version:
            if status_type == "COMPLETED":
                self.extension_mgr.trigger_fota_completed(self.current_device.uin, self.target_version)
                self._write_audit(self.current_device.uin, self.current_device.version, self.target_version, "COMPLETED", msg)
            else:
                self._write_audit(self.current_device.uin, self.current_device.version, self.target_version, "ABORTED", msg)
        self.is_upgrading = False

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
        """Write audit log entry to results/fota_results.csv and results/fota_results.json."""
        record = FotaAuditRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            uin=uin,
            initial_version=initial_ver,
            final_version=final_ver,
            status=status,
            remarks=remarks,
        )
        self.audit_signal.emit(record)

        # 1. Write to results/fota_results.csv
        csv_path = self.config.results_dir / "fota_results.csv"
        try:
            write_header = not csv_path.exists() or csv_path.stat().st_size == 0
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(["Timestamp", "UIN", "IMEI", "VIN", "InitialVersion", "TargetVersion", "State", "Status", "Remarks"])
                imei_str = self.current_device.imei if self.current_device else ""
                vin_str = self.current_device.vin if self.current_device else ""
                state_str = self.current_device.state if self.current_device else ""
                writer.writerow([
                    record.timestamp,
                    record.uin,
                    imei_str,
                    vin_str,
                    record.initial_version,
                    record.final_version,
                    state_str,
                    record.status,
                    record.remarks,
                ])
            logger.info("Recorded audit entry to CSV for UIN %s: %s", uin, status)
        except Exception as err:
            logger.error("Failed to write audit CSV entry: %s", err)

        # 2. Write to results/fota_results.json
        json_path = self.config.results_dir / "fota_results.json"
        try:
            results_data = []
            if json_path.exists() and json_path.stat().st_size > 0:
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        results_data = json.load(f)
                except Exception:
                    results_data = []

            results_data.append({
                "timestamp": record.timestamp,
                "uin": record.uin,
                "imei": self.current_device.imei if self.current_device else "",
                "vin": self.current_device.vin if self.current_device else "",
                "initialVersion": record.initial_version,
                "targetVersion": record.final_version,
                "state": self.current_device.state if self.current_device else "",
                "status": record.status,
                "remarks": record.remarks,
            })

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results_data, f, indent=2)
            logger.info("Recorded audit entry to JSON for UIN %s: %s", uin, status)
        except Exception as err:
            logger.error("Failed to write audit JSON entry: %s", err)
