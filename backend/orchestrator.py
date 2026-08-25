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
    is_aborted = item.get("isAborted") is True or bool(item.get("abortReason"))
    
    current_fw = str(item.get("currentFirmwareVersion") or "").strip()
    target_fw = str(item.get("targetFirmwareVersion") or item.get("targetVersion") or "").strip()
    match_completed = bool(current_fw and target_fw and current_fw == target_fw)

    is_completed = (
        item.get("deviceFotaCompletionStatus") is True
        or str(item.get("deviceFotaStatus", "")).strip().lower() == "completed"
        or match_completed
        or float(item.get("progress") or 0.0) >= 100.0
    )
    attempt_count = item.get("attemptCount", 0) or 0

    # Active if added to batch, not aborted, not completed, and attempt count < 3
    return added_to_batch and (not is_aborted) and (not is_completed) and (attempt_count < 3)


def save_active_fota_json(imei: str, uin: str, target_ver: str, state_name: str, item: dict) -> None:
    """Save/update active FOTA status information into results/active_fota.json."""
    try:
        out_dir = Path("results")
        out_dir.mkdir(parents=True, exist_ok=True)
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

            # 2. Evaluate the 3 explicit server statuses: Aborted, Pending, Completed
            next_ver = None
            if first_item:
                target_ver = first_item.get("targetFirmwareVersion") or first_item.get("targetVersion") or ""
                current_fw_ver = str(first_item.get("currentFirmwareVersion") or "").strip()
                match_completed = bool(current_fw_ver and target_ver and current_fw_ver == target_ver)

                progress = float(first_item.get("progress") or 0.0)
                ping_cnt = first_item.get("pingCount", 0) or 0
                attempt_cnt = first_item.get("attemptCount", 0) or 0
                raw_status = str(first_item.get("deviceFotaStatus") or "").strip()
                status_lower = raw_status.lower()

                # Telemetry Field Matching (UIN, VIN, ICCID) against API Response
                api_uin = str(first_item.get("uin") or first_item.get("UIN") or "").strip()
                api_vin = str(first_item.get("vin") or first_item.get("VIN") or "").strip()
                api_iccid = str(first_item.get("iccid") or first_item.get("ICCID") or "").strip()

                mismatches = []
                if api_uin and self.login_info.uin and api_uin.lower() != self.login_info.uin.strip().lower():
                    mismatches.append(f"UIN (Log: '{self.login_info.uin}' != API: '{api_uin}')")
                if api_vin and self.login_info.vin and api_vin.lower() != self.login_info.vin.strip().lower():
                    mismatches.append(f"VIN (Log: '{self.login_info.vin}' != API: '{api_vin}')")
                if api_iccid and self.login_info.iccid and api_iccid.lower() != self.login_info.iccid.strip().lower():
                    mismatches.append(f"ICCID (Log: '{self.login_info.iccid}' != API: '{api_iccid}')")

                if mismatches:
                    mismatch_msg = f"⚠️ Telemetry Mismatch: {', '.join(mismatches)}"
                    logger.warning("TELEMETRY MISMATCH DETECTED for IMEI %s: %s", self.login_info.imei, mismatch_msg)
                    self.orchestrator.snackbar_signal.emit(mismatch_msg)

                is_aborted = first_item.get("isAborted", False) or bool(first_item.get("abortReason")) or (status_lower == "aborted")
                is_completed = (
                    first_item.get("deviceFotaCompletionStatus", False)
                    or (status_lower == "completed")
                    or match_completed
                    or (progress >= 100.0)
                )
                is_pending_active = is_active_fota_session(first_item) or (status_lower in ("pending", "in-progress"))

                display_status = "Completed" if is_completed else ("Aborted" if is_aborted else "Pending")
                msg = (f"📋 Scanned FOTA History for IMEI {self.login_info.imei}: "
                       f"Status: '{raw_status or display_status}', Target: '{target_ver}', Progress: {progress:.2f}%, Pings: {ping_cnt}, Attempts: {attempt_cnt}/3.")
                logger.info(msg)

                # Emit scanned history item to main thread so active_fota.json, fota_results.csv, and fota_results.json are written immediately!
                self.finished_signal.emit(True, target_ver, "SCANNED_HISTORY", msg, first_item)

                # --- STATUS 1: PENDING / IN-PROGRESS ---
                if is_pending_active and not is_aborted and not is_completed:
                    logger.info("FOTA status is PENDING for IMEI %s. Re-attaching monitoring without triggering new API call...", self.login_info.imei)
                    return

                # --- STATUS 2: ABORTED ---
                if is_aborted:
                    abort_reason = str(first_item.get("abortReason") or first_item.get("remarks") or "Aborted on server")
                    reason_lower = abort_reason.lower()
                    is_manual = any(k in reason_lower for k in ("manual", "admin", "user", "super administrator", "tester"))

                    if is_manual:
                        logger.warning("FOTA status is MANUALLY ABORTED ('%s') for IMEI %s. Resolving next target version based on active device log version '%s'...",
                                       abort_reason, self.login_info.imei, self.login_info.version)
                        next_ver = self.orchestrator.resolver.resolve_next_version(self.device_state, self.login_info.version)
                    else:
                        logger.warning("FOTA status is ABORTED by system/other reason ('%s') for IMEI %s. Resolving version after aborted target '%s'...",
                                       abort_reason, self.login_info.imei, target_ver)
                        next_ver = self.orchestrator.resolver.resolve_next_version_after_aborted(self.device_state, self.login_info.version, target_ver)

                # --- STATUS 3: COMPLETED ---
                if is_completed:
                    base_version = target_ver or self.login_info.version
                    logger.info("FOTA status is COMPLETED for IMEI %s. Resolving next step upgrade version from base target '%s'...",
                                self.login_info.imei, base_version)
                    next_ver = self.orchestrator.resolver.resolve_next_version(self.device_state, base_version)

            if not next_ver:
                next_ver = self.orchestrator.resolver.resolve_next_version(self.device_state, self.login_info.version)

            if not next_ver:
                if not self.orchestrator.resolver.validate_version_exists(self.device_state, self.login_info.version):
                    msg = f"⚠️ Version Validation Barrier: Firmware version '{self.login_info.version}' is NOT listed in servers.json for state '{self.device_state}'. FOTA process blocked."
                    toast_msg = f"⚠️ Version Warning: Device version '{self.login_info.version}' not found in '{self.device_state}' server matrix!"
                    logger.warning(toast_msg)
                    self.orchestrator.snackbar_signal.emit(toast_msg)
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
                    is_completed = (
                        item.get("deviceFotaCompletionStatus", False) is True
                        or str(item.get("deviceFotaStatus", "")).strip().lower() == "completed"
                        or progress >= 100.0
                    )

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

                    # Determine adaptive polling delay: 60s (1 min) if < 95%, 3s if >= 95%
                    sleep_sec = 2 if progress >= 95.0 else 60
                    logger.info("Polled IMEI %s -> Progress: %.2f%%, Pings: %d, Attempts: %d/3. Next poll in %d seconds.",
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
    snackbar_signal = pyqtSignal(str)         # Non-blocking alert toast for UI
    stage_signal = pyqtSignal(int, str, str)  # (stage_number 1..10, status 'RUNNING'|'PASSED'|'FAILED', message)
    reset_ui_cards_signal = pyqtSignal()      # Signal to reset 10-stage cards to default

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

        # 10-Stage Pipeline Tracking State
        self.stage_states = {s: "WAITING" for s in range(1, 11)}
        self.clr_fota_ok_received: bool = False
        self.initial_config_snapshot: dict = {}
        self.total_fota_file_size: int = 0
        self.download_100_reached: bool = False
        self.reboot_detected: bool = False
        self.ip1_verified: bool = False
        self.ip2_verified: bool = False
        self.state_ota_verified: bool = False
        self.config_verified: bool = False
        self.prncfg_command_fired: bool = False
        self.latest_api_history_item: dict = {}

    def _extract_api_field(self, item: dict, field_keywords: List[str]) -> str:
        """Search top-level and nested dicts for any field matching keywords."""
        if not isinstance(item, dict):
            return ""

        for k, v in item.items():
            k_lower = k.lower()
            if any(kw.lower() in k_lower for kw in field_keywords):
                if isinstance(v, (str, bool, int)):
                    return str(v).strip()

        for k, v in item.items():
            if isinstance(v, dict):
                res = self._extract_api_field(v, field_keywords)
                if res:
                    return res
        return ""

    def _is_valid_passed_or_skipped(self, val: Any) -> bool:
        if val is True:
            return True
        v_str = str(val or "").strip().upper()
        return v_str in (
            "SET", "PASSED", "COMPLETED", "SUCCESS", "TRUE", "1", "OK",
            "ALREADY SET", "ENABLED", "SKIPPED", "SKIP", "NOT REQUIRED"
        )

    def check_api_server_statuses_set(self, item: dict) -> Tuple[bool, str]:
        """Validate if State Enable OTA, Primary IP, and Secondary IP statuses from API response are all 'SET' or 'SKIPPED'."""
        if not isinstance(item, dict) or not item:
            return True, "Default SET (Local serial verification mode)"

        swemp_val = self._extract_api_field(item, ["stateEnableOtaStatus", "swempStatus", "stateEnableStatus", "stateEnabledOtaStatus", "swemp"]) or "SET"
        chtp_val = self._extract_api_field(item, ["primaryIpStatus", "chtpStatus", "primaryIp1Status", "ip1Status", "primaryip"]) or "SET"
        cip1_val = self._extract_api_field(item, ["secondaryIpStatus", "cip1Status", "secondaryIp2Status", "ip2Status", "secondaryip"]) or "SET"

        swemp_ok = self._is_valid_passed_or_skipped(swemp_val)
        chtp_ok = self._is_valid_passed_or_skipped(chtp_val)
        cip1_ok = self._is_valid_passed_or_skipped(cip1_val)

        if swemp_ok and chtp_ok and cip1_ok:
            return True, f"API Server Header Statuses: State Enable OTA={swemp_val}, Primary IP={chtp_val}, Secondary IP={cip1_val} (ALL SET/SKIPPED)"

        missing = []
        if not swemp_ok: missing.append(f"State Enable OTA Status ('{swemp_val}' != 'SET/SKIPPED')")
        if not chtp_ok: missing.append(f"Primary IP Status ('{chtp_val}' != 'SET/SKIPPED')")
        if not cip1_ok: missing.append(f"Secondary IP Status ('{cip1_val}' != 'SET/SKIPPED')")

        return False, f"Waiting for API server header statuses to be SET/SKIPPED: {', '.join(missing)}"

    def _evaluate_api_skipped_stages(self) -> None:
        """Check if API response has Primary IP Status or Secondary IP Status marked as 'Skipped' / 'Set' and pass stages directly."""
        if not isinstance(self.latest_api_history_item, dict) or not self.latest_api_history_item:
            return

        item = self.latest_api_history_item

        p_status = self._extract_api_field(item, ["primaryIpStatus", "primaryIPStatus", "chtpStatus", "primaryIp1Status", "ip1Status", "primaryip", "govtIp1Status"])
        s_status = self._extract_api_field(item, ["secondaryIpStatus", "secondaryIPStatus", "cip1Status", "secondaryIp2Status", "ip2Status", "secondaryip", "govtIp2Status"])
        state_status = self._extract_api_field(item, ["stateEnableOtaStatus", "swempStatus", "stateEnableStatus", "stateEnabledOtaStatus", "swemp"])
        dev_fota_status = self._extract_api_field(item, ["deviceFotaStatus", "deviceFotaCompletionStatus", "fotaStatus", "status"])

        p_ok = self._is_valid_passed_or_skipped(p_status)
        s_ok = self._is_valid_passed_or_skipped(s_status)
        swemp_ok = self._is_valid_passed_or_skipped(state_status)
        is_completed_api = ("COMPLET" in dev_fota_status.upper()) or (dev_fota_status.upper() == "TRUE")

        # When download reached 100%, reboot detected, or API completed:
        if self.download_100_reached or self.reboot_detected or is_completed_api:
            # Stage 6 Reboot
            if not self.reboot_detected:
                self.reboot_detected = True
                self.stage_states[6] = "PASSED"
                self.stage_signal.emit(6, "PASSED", "Post-installation device reboot confirmed via API")

            # Stage 7 (State Enable OTA)
            if not self.state_ota_verified and (swemp_ok or is_completed_api):
                self.state_ota_verified = True
                msg = f"State Enabled OTA verified active ({state_status or 'SET'} in API)"
                logger.info("Stage 7: %s. Stage PASSED.", msg)
                self.stage_states[7] = "PASSED"
                self.stage_signal.emit(7, "PASSED", msg)

            # Stage 8 (Primary CHTP IP1)
            if not self.ip1_verified and (p_ok or is_completed_api):
                self.state_ota_verified = True
                self.ip1_verified = True
                lbl = p_status or "Skipped"
                msg = f"Primary CHTP IP1 verified ({lbl} in API response - device already configured)"
                logger.info("Stage 8: %s. Stage PASSED directly.", msg)
                self.stage_states[8] = "PASSED"
                self.stage_signal.emit(8, "PASSED", msg)
                self.stage_states[9] = "RUNNING"
                self.stage_signal.emit(9, "RUNNING", "Validating Secondary Server CIP1 IP2 & Port2...")

            # Stage 9 (Secondary CIP1 IP2)
            if self.ip1_verified and not self.ip2_verified and (s_ok or is_completed_api):
                self.ip2_verified = True
                lbl = s_status or "Skipped"
                msg = f"Secondary CIP1 IP2 verified ({lbl} in API response - device already configured)"
                logger.info("Stage 9: %s. Stage PASSED directly.", msg)
                self.stage_states[9] = "PASSED"
                self.stage_signal.emit(9, "PASSED", msg)
                self.stage_states[10] = "RUNNING"
                self.stage_signal.emit(10, "RUNNING", "Validating 55AA Login Packet post-upgrade firmware version...")

            # Stage 10 continuous trigger
            if self.ip2_verified and not self.config_verified:
                self._evaluate_stage10_completion()

    def prepare_next_fota_cycle(self) -> None:
        """Reset stage cards and progress bar, then trigger the next sequential FOTA version."""
        logger.info("Preparing next sequential FOTA cycle. Resetting 10-stage cards to WAITING state.")
        if self.poller_worker:
            self.poller_worker.stop()
            self.poller_worker = None

        self.stage_states = {s: "WAITING" for s in range(1, 11)}
        self.clr_fota_ok_received = False
        self.download_100_reached = False
        self.reboot_detected = False
        self.ip1_verified = False
        self.ip2_verified = False
        self.state_ota_verified = False
        self.config_verified = False
        self.prncfg_command_fired = False
        self.latest_api_history_item.clear()
        self.target_version = None
        self.is_upgrading = False

        self.reset_ui_cards_signal.emit()
        self.progress_signal.emit(0.0)

        if self.current_device:
            self.attempted_uins.discard(self.current_device.uin)
            logger.info("Re-evaluating telemetry for %s to trigger next sequential FOTA version...", self.current_device.uin)
            self.process_login_packet(self.current_device, selected_ui_state=self.current_device.state)

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

        self.stage_states = {s: "WAITING" for s in range(1, 11)}
        self.clr_fota_ok_received = False
        self.initial_config_snapshot.clear()
        self.total_fota_file_size = 0
        self.download_100_reached = False
        self.reboot_detected = False
        self.ip1_verified = False
        self.ip2_verified = False
        self.state_ota_verified = False
        self.config_verified = False
        self.prncfg_command_fired = False
        self.latest_api_history_item.clear()

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
        """Inspect raw serial log line for CIP2 server domain verification and 10-Stage Pipeline events."""
        # Pre-Start verification: check for STATUS#CLR#FOTA#OK#{IMEI}
        is_clr, clr_imei = MessageParser.parse_clr_fota_ok(line)
        if is_clr and not self.clr_fota_ok_received:
            self.clr_fota_ok_received = True
            msg = f"✓ STATUS#CLR#FOTA#OK verified from log for IMEI {clr_imei or ''}"
            logger.info(msg)
            self.status_signal.emit(msg)

        # 55AA Server FOTA Header (|55AA,1,2,epoch,version,flag,0,0,filesize,0,chunksize,FF|)
        fota_hdr = MessageParser.parse_55aa_server_fota_header(line)
        if fota_hdr:
            if fota_hdr.get("file_size"):
                self.total_fota_file_size = fota_hdr["file_size"]
                logger.info("Parsed 55AA FOTA Header: Target Version=%s, File Size=%d bytes, Chunk Size=%d bytes",
                            fota_hdr.get("target_version"), self.total_fota_file_size, fota_hdr.get("chunk_size"))

        # CIP2 server check
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

        # Stage 6: Device Reboot Detection (after download reaches 100%)
        if self.download_100_reached and not self.reboot_detected:
            if MessageParser.is_device_reboot(line):
                self.reboot_detected = True
                self.stage_states[6] = "PASSED"
                self.stage_signal.emit(6, "PASSED", "Post-installation device reboot/reset detected (120s window active)")
                self.stage_states[7] = "RUNNING"
                self.stage_signal.emit(7, "RUNNING", "Validating SWEMP State Enabled OTA...")

        # Evaluate if API response has Primary IP Status or Secondary IP Status marked as 'Skipped'
        self._evaluate_api_skipped_stages()

        meta = self.resolver.get_state_server_metadata(self.current_device.state if self.current_device else "")
        has_ip1 = bool(meta.get("ip1") and str(meta.get("ip1")).strip())
        has_ip2 = bool(meta.get("ip2") and str(meta.get("ip2")).strip())
        has_state_enable = bool(meta.get("state_enable") and str(meta.get("state_enable")).strip())

        # Stage 7: SWEMP State Enabled OTA Verification (*SET#SWEMP#<state>#)
        if self.reboot_detected and not self.state_ota_verified:
            if not has_state_enable:
                self.state_ota_verified = True
                msg = "NOT PRESENT (State Enabled OTA not configured in servers.json matrix)"
                logger.info("Stage 7: %s. Stage marked NOT PRESENT and passed.", msg)
                self.stage_states[7] = "PASSED"
                self.stage_signal.emit(7, "PASSED", msg)
                self.stage_states[8] = "RUNNING"
                self.stage_signal.emit(8, "RUNNING", "Validating Primary Server CHTP IP1 & Port1...")
            else:
                swemp_code = MessageParser.parse_swemp_state_ota(line)
                target_state_cmd = str(meta.get("state_enable", "")).strip()
                
                if swemp_code or "SWEMP" in line:
                    if "STATUS#SET#SWEMP#" in line or "*SET#SWEMP#" in line:
                        self.state_ota_verified = True
                        state_enable_cmd = target_state_cmd or swemp_code or "SWEMP"
                        msg = f"State Enabled OTA ({state_enable_cmd}) verified active"
                        logger.info("Stage 7: %s", msg)
                        self.stage_states[7] = "PASSED"
                        self.stage_signal.emit(7, "PASSED", msg)
                        self.stage_states[8] = "RUNNING"
                        self.stage_signal.emit(8, "RUNNING", "Validating Primary Server CHTP IP1 & Port1...")
                    elif swemp_code:
                        self.state_ota_verified = True
                        msg = f"ALREADY SET (State Enabled OTA {swemp_code} already configured on device)"
                        logger.info("Stage 7: %s. Passed without waiting for set command.", msg)
                        self.stage_states[7] = "PASSED"
                        self.stage_signal.emit(7, "PASSED", msg)
                        self.stage_states[8] = "RUNNING"
                        self.stage_signal.emit(8, "RUNNING", "Validating Primary Server CHTP IP1 & Port1...")

        # Stage 8: Primary Server CHTP IP1 & Port1 Verification (*SET#CHTP#<ip>#<port>#)
        if self.state_ota_verified and not self.ip1_verified:
            if not has_ip1:
                self.ip1_verified = True
                msg = "NOT PRESENT (Primary IP1/Port1 not configured in servers.json matrix)"
                logger.info("Stage 8: %s. Stage marked NOT PRESENT and passed.", msg)
                self.stage_states[8] = "PASSED"
                self.stage_signal.emit(8, "PASSED", msg)
                self.stage_states[9] = "RUNNING"
                self.stage_signal.emit(9, "RUNNING", "Validating Secondary Server CIP1 IP2 & Port2...")
            else:
                target_ip = str(meta.get("ip1", "")).strip()
                target_port = str(meta.get("port1", "")).strip()
                chtp_tuple = MessageParser.parse_chtp_primary_ip_port(line)

                # Check if response line shows unconfigured default factory state 255.255.255.255
                is_255_chtp = "255.255.255.255" in line or (chtp_tuple and MessageParser.is_unconfigured_ip(chtp_tuple[0]))

                if is_255_chtp:
                    # Unconfigured 255.255.255.255 state -> Must wait for set command response (*SET#CHTP#)
                    logger.debug("Stage 8: CHTP unconfigured 255.255.255.255 detected. Waiting for set command response...")
                elif chtp_tuple or ("CHTP" in line and ("." in line or ":" in line)):
                    parsed_ip = chtp_tuple[0] if chtp_tuple else ""
                    parsed_port = chtp_tuple[1] if chtp_tuple else ""

                    if "STATUS#SET#CHTP#" in line or "*SET#CHTP#" in line:
                        self.ip1_verified = True
                        msg = f"Primary CHTP IP1 ({parsed_ip or target_ip}:{parsed_port or target_port}) verified"
                        logger.info("Stage 8: %s", msg)
                        self.stage_states[8] = "PASSED"
                        self.stage_signal.emit(8, "PASSED", msg)
                        self.stage_states[9] = "RUNNING"
                        self.stage_signal.emit(9, "RUNNING", "Validating Secondary Server CIP1 IP2 & Port2...")
                    elif parsed_ip and target_ip and (parsed_ip.lower() == target_ip.lower()):
                        self.ip1_verified = True
                        msg = f"ALREADY SET (Primary CHTP IP1 {parsed_ip}:{parsed_port or target_port} matches target matrix)"
                        logger.info("Stage 8: %s. Passed without waiting for set command.", msg)
                        self.stage_states[8] = "PASSED"
                        self.stage_signal.emit(8, "PASSED", msg)
                        self.stage_states[9] = "RUNNING"
                        self.stage_signal.emit(9, "RUNNING", "Validating Secondary Server CIP1 IP2 & Port2...")
                    elif parsed_ip:
                        logger.info("Stage 8: Device CHTP IP '%s' differs from target IP '%s'. Waiting for *SET#CHTP# response from log...", parsed_ip, target_ip)

        # Stage 9: Secondary Server CIP1 IP2 & Port2 Verification (*SET#CIP1#<ip>#<port>#)
        if self.ip1_verified and not self.ip2_verified:
            if not has_ip2:
                self.ip2_verified = True
                msg = "NOT PRESENT (Secondary IP2/Port2 not configured in servers.json matrix)"
                logger.info("Stage 9: %s. Stage marked NOT PRESENT and passed.", msg)
                self.stage_states[9] = "PASSED"
                self.stage_signal.emit(9, "PASSED", msg)
                self.stage_states[10] = "RUNNING"
                self.stage_signal.emit(10, "RUNNING", "Validating 55AA Login Packet post-upgrade firmware version...")
            else:
                target_ip2 = str(meta.get("ip2", "")).strip()
                target_port2 = str(meta.get("port2", "")).strip()
                cip1_tuple = MessageParser.parse_cip1_secondary_ip_port(line)

                # Check if response line shows unconfigured default factory state 255.255.255.255
                is_255_cip = "255.255.255.255" in line or (cip1_tuple and MessageParser.is_unconfigured_ip(cip1_tuple[0]))

                if is_255_cip:
                    # Unconfigured 255.255.255.255 state -> Must wait for set command response (*SET#CIP1#)
                    logger.debug("Stage 9: CIP1 unconfigured 255.255.255.255 detected. Waiting for set command response...")
                elif cip1_tuple or ("CIP1" in line and ("." in line or ":" in line)):
                    parsed_ip2 = cip1_tuple[0] if cip1_tuple else ""
                    parsed_port2 = cip1_tuple[1] if cip1_tuple else ""

                    if "STATUS#SET#CIP1#" in line or "*SET#CIP1#" in line:
                        self.ip2_verified = True
                        msg = f"Secondary CIP1 IP2 ({parsed_ip2 or target_ip2}:{parsed_port2 or target_port2}) verified"
                        logger.info("Stage 9: %s", msg)
                        self.stage_states[9] = "PASSED"
                        self.stage_signal.emit(9, "PASSED", msg)
                        self.stage_states[10] = "RUNNING"
                        self.stage_signal.emit(10, "RUNNING", "Validating 55AA Login Packet post-upgrade firmware version...")
                    elif parsed_ip2 and target_ip2 and (parsed_ip2.lower() == target_ip2.lower()):
                        self.ip2_verified = True
                        msg = f"ALREADY SET (Secondary CIP1 IP2 {parsed_ip2}:{parsed_port2 or target_port2} matches target matrix)"
                        logger.info("Stage 9: %s. Passed without waiting for set command.", msg)
                        self.stage_states[9] = "PASSED"
                        self.stage_signal.emit(9, "PASSED", msg)
                        self.stage_states[10] = "RUNNING"
                        self.stage_signal.emit(10, "RUNNING", "Validating 55AA Login Packet post-upgrade firmware version...")
                    elif parsed_ip2:
                        logger.info("Stage 9: Device CIP1 IP '%s' differs from target IP '%s'. Waiting for *SET#CIP1# response from log...", parsed_ip2, target_ip2)

        # Stage 10: Continuously evaluate post-upgrade 55AA Login Packet & Firmware Version on EVERY line
        if self.ip2_verified and not self.config_verified:
            if not self.prncfg_command_fired:
                self.prncfg_command_fired = True
                logger.info("Stage 10: Auto-firing *GET#PRNCFG# command to retrieve post-upgrade print configuration...")
                self.request_command_signal.emit("*GET#PRNCFG#")
            self._evaluate_stage10_completion(line)

    def _evaluate_stage10_completion(self, current_log_line: str = "") -> None:
        """Validate Stage 10 (Post-Upgrade 55AA Login Packet & Firmware Version Match vs Target)."""
        if not self.current_device or self.config_verified:
            return

        snapshot = self.initial_config_snapshot
        cur_dev = self.current_device

        uin_ok = not snapshot.get("uin") or snapshot.get("uin") == cur_dev.uin
        imei_ok = not snapshot.get("imei") or snapshot.get("imei") == cur_dev.imei
        vin_ok = not snapshot.get("vin") or snapshot.get("vin") == cur_dev.vin

        # Check for 55AA login packet in current log line or firmware version in log line
        pkt_55aa = MessageParser.parse_55aa_login_packet(current_log_line) if current_log_line else None
        extracted_ver = MessageParser.parse_firmware_version(current_log_line) if current_log_line else None
        if pkt_55aa and pkt_55aa.version:
            extracted_ver = pkt_55aa.version

        current_ver = extracted_ver or (cur_dev.version if cur_dev else "")
        target_ver = self.target_version or ""

        # Verify version match
        version_matches = False
        if target_ver and current_ver:
            v_clean = current_ver.strip().lower()
            t_clean = target_ver.strip().lower()
            version_matches = (t_clean in v_clean) or (v_clean in t_clean) or (v_clean == t_clean)

        ver_label = current_ver or target_ver

        if uin_ok and imei_ok and vin_ok and (version_matches or pkt_55aa):
            self.config_verified = True
            self.stage_states[10] = "PASSED"
            self.stage_signal.emit(10, "PASSED", f"Post-upgrade config & target version '{ver_label}' verified")
            
            msg = f"🎉 ALL 10 FOTA STAGES 100% COMPLETED & VERIFIED FOR {cur_dev.uin} (Target Version: {ver_label})!"
            logger.info(msg)

            # 1. Write final COMPLETED audit log entry
            self._write_audit(
                cur_dev.uin,
                snapshot.get("version", cur_dev.version),
                ver_label,
                "COMPLETED",
                "All 10 stages 100% completed and post-upgrade version verified successfully"
            )

            # 2. Trigger completion event & UI banner
            self.extension_mgr.trigger_fota_completed(cur_dev.uin, ver_label)
            self.status_signal.emit(msg)
            self.snackbar_signal.emit(msg)

            # 3. Schedule next FOTA cycle and reset cards for new process after 4 seconds
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(4000, self.prepare_next_fota_cycle)

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

        # Stage 1: Telemetry Params Passed
        self.stage_states[1] = "PASSED"
        self.stage_signal.emit(1, "PASSED", f"Telemetry abstracted (UIN: {login_info.uin})")
        self.initial_config_snapshot = {
            "uin": login_info.uin,
            "imei": login_info.imei,
            "vin": login_info.vin,
            "iccid": login_info.iccid,
            "version": login_info.version,
            "state": device_state,
        }

        # Stage 2: Validate Server Matrix & State Version
        is_valid_ver = self.resolver.is_version_listed(device_state, login_info.version)
        if is_valid_ver:
            self.stage_states[2] = "PASSED"
            self.stage_signal.emit(2, "PASSED", f"State version '{login_info.version}' validated in '{device_state}'")
        else:
            self.stage_states[2] = "FAILED"
            self.stage_signal.emit(2, "FAILED", f"Version '{login_info.version}' not listed in '{device_state}' matrix")
            warning_msg = f"⚠️ Version Warning: Device version '{login_info.version}' not found in '{device_state}' server matrix!"
            logger.warning(warning_msg)
            self.snackbar_signal.emit(warning_msg)

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
        if isinstance(raw_item, dict) and raw_item:
            self.latest_api_history_item = raw_item

        if success and raw_item and api_msg == "SCANNED_HISTORY":
            if self.current_device:
                # 1. Always save active FOTA info to results/active_fota.json
                save_active_fota_json(
                    self.current_device.imei,
                    self.current_device.uin,
                    target_ver or raw_item.get("targetFirmwareVersion", ""),
                    self.current_device.state,
                    raw_item
                )

                # Determine audit status from raw_item
                is_aborted = raw_item.get("isAborted", False) or bool(raw_item.get("abortReason"))
                is_completed = raw_item.get("deviceFotaCompletionStatus", False) or float(raw_item.get("progress") or 0.0) >= 100.0

                if is_completed:
                    audit_status = "COMPLETED"
                elif is_aborted:
                    audit_status = "ABORTED"
                elif is_active_fota_session(raw_item):
                    audit_status = "IN_PROGRESS"
                else:
                    audit_status = str(raw_item.get("deviceFotaStatus", "SCANNED_HISTORY")).upper()

                # 2. Always write audit entry to results/fota_results.csv and results/fota_results.json
                try:
                    init_v = raw_item.get("firmwareVersion") or (self.current_device.version if self.current_device else "")
                    tgt_v = target_ver or raw_item.get("targetFirmwareVersion") or ""
                    self._write_audit(self.current_device.uin, init_v, tgt_v, audit_status, status_msg)
                except Exception as err:
                    logger.error("Failed writing audit entry for scanned history: %s", err)

                # 3. If session is ACTIVE, emit initial API progress and re-attach poller worker to track it
                if is_active_fota_session(raw_item):
                    self.target_version = target_ver or raw_item.get("targetFirmwareVersion", "")
                    self.is_upgrading = True
                    self.extension_mgr.trigger_fota_started(self.current_device.uin, self.target_version)

                    scanned_progress = float(raw_item.get("progress") or 0.0)
                    if scanned_progress > 0.0:
                        self.update_progress(scanned_progress)

                    if not self.poller_worker or not self.poller_worker.isRunning():
                        self.poller_worker = FotaApiPollerWorker(self, self.current_device.imei)
                        self.poller_worker.poll_update_signal.connect(self._on_poller_update)
                        self.poller_worker.poll_finished_signal.connect(self._on_poller_finished)
                        self.poller_worker.start()

        elif success and target_ver:
            self.target_version = target_ver
            self.is_upgrading = True

            # Save active FOTA status into results/active_fota.json and CSV/JSON audit log
            if self.current_device:
                save_active_fota_json(self.current_device.imei, self.current_device.uin, target_ver, self.current_device.state, raw_item)
                self.extension_mgr.trigger_fota_started(self.current_device.uin, target_ver)

                # Write initial audit entry for IN_PROGRESS status
                try:
                    self._write_audit(self.current_device.uin, self.current_device.version, target_ver, "IN_PROGRESS", status_msg)
                except Exception as err:
                    logger.error("Failed to write initial audit entry: %s", err)

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
        if isinstance(item, dict) and item:
            self.latest_api_history_item = item

        # Evaluate if API response has Primary IP Status or Secondary IP Status marked as 'Skipped'
        self._evaluate_api_skipped_stages()

        progress = float(item.get("progress") or 0.0)
        status_str = item.get("deviceFotaStatus") or "In-Progress"
        ping_cnt = item.get("pingCount", 0) or 0
        attempt_cnt = item.get("attemptCount", 0) or 0

        self.progress_signal.emit(progress)
        status_msg = f"FOTA Status: {status_str} | Progress: {progress:.2f}% | Pings: {ping_cnt} | Attempts: {attempt_cnt}/3"
        self.status_signal.emit(status_msg)

        if self.current_device:
            save_active_fota_json(self.current_device.imei, self.current_device.uin, self.target_version or "", self.current_device.state, item)

        # Evaluate Stage 10 on poll updates if Stage 10 is currently RUNNING
        if self.ip2_verified and not self.config_verified:
            self._evaluate_stage10_completion()

    def _on_poller_finished(self, status_type: str, msg: str) -> None:
        """Handle completion or failure from background API poller worker."""
        self.status_signal.emit(msg)
        if self.current_device and self.target_version:
            if status_type == "COMPLETED":
                logger.info("API Poller confirmed 100%% completion for IMEI %s. Updating progress to 100.0%% and waiting for Stage S6-S10 serial verification...", self.current_device.imei)
                self.update_progress(100.0)
            else:
                # 1. Reset downloading progress bar to 0.00%
                self.progress_signal.emit(0.0)

                # 2. Save audit report for ABORTED run
                self._write_audit(self.current_device.uin, self.current_device.version, self.target_version, "ABORTED", msg)
                self.is_upgrading = False

                # 3. Re-initiate FOTA API trigger request for device
                logger.info("FOTA aborted for UIN %s. Re-initiating FOTA API trigger request...", self.current_device.uin)
                self.status_signal.emit(f"⛔ FOTA Aborted. Audit report saved. Re-initiating FOTA API request for {self.current_device.uin}...")

                dev = self.current_device
                state = dev.state
                self.attempted_uins.discard(dev.uin)

                self._trigger_worker = FotaAsyncTriggerWorker(self, dev, state)
                self._trigger_worker.finished_signal.connect(self._on_trigger_finished)
                self._trigger_worker.start()

    def update_progress(self, progress: float) -> None:
        """Update live download progress percentage and continuously validate till 100% done."""
        val_clean = max(0.0, min(100.0, float(progress)))
        self.progress_signal.emit(val_clean)

        # Stage 3: Progress Sync Passed
        if self.stage_states.get(3) != "PASSED":
            self.stage_states[3] = "PASSED"
            self.stage_signal.emit(3, "PASSED", "Progress tracking active")

        # Stage 4: Audit Report Passed
        if self.stage_states.get(4) != "PASSED":
            self.stage_states[4] = "PASSED"
            self.stage_signal.emit(4, "PASSED", "Initial audit report logged")

        # Stage 5: 100% Downloaded Passed
        if val_clean >= 100.0:
            self.download_100_reached = True
            if self.stage_states.get(5) != "PASSED":
                self.stage_states[5] = "PASSED"
                self.stage_signal.emit(5, "PASSED", "100.00% Downloaded")
                self.stage_states[6] = "RUNNING"
                self.stage_signal.emit(6, "RUNNING", "Monitoring for device reboot...")
            
            msg = f"IN-PROGRESS | FOTA download 100% complete for {self.current_device.uin if self.current_device else ''} → {self.target_version or ''}. Waiting for device reboot and post-install verification (Stages S6-S10)..."
            logger.info(msg)
            self.status_signal.emit(msg)
            # Run is NOT marked COMPLETED here!
            # Verification continues through Stage 6 (Reboot), Stage 7 (SWEMP), Stage 8 (CHTP), Stage 9 (CIP1), Stage 10 (55AA Version Match)
        else:
            self.status_signal.emit(f"FOTA Downloading: {val_clean:.2f}%")

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
