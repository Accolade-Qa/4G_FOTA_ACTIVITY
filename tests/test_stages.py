"""Comprehensive test suite for testing the 10 FOTA Pipeline Stages using actual real-world serial telemetry and state matrix data."""

import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from PyQt6.QtCore import QCoreApplication

from backend.orchestrator import FotaOrchestrator
from backend.message_parser import MessageParser
from backend.models import LoginPacketInfo
from backend.firmware_resolver import FirmwareResolver


def get_qapp():
    """Get or create QCoreApplication instance."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


class ActualFotaStageTestData:
    """Real-world sample telemetry data, genuine 55AA login packets, and serial log streams."""

    IMEI = "861564069210428"
    UIN = "ACON4NA082300010428"
    VIN = "MAT00000000000000"
    ICCID = "8991000000000000000"
    INITIAL_VERSION = "5.2.8"
    TARGET_VERSION = "5.2.9_REL13"
    STATE_NAME = "Aishwarya"

    # Genuine 55AA GSM Login Packet
    PACKET_55AA_LOGIN = (
        f"|55AA,1,2,1786521830,{IMEI},{ICCID},{UIN},{INITIAL_VERSION},{VIN},4G,{STATE_NAME},FF|"
    )

    # Genuine 55AA Post-Upgrade Login Packet
    PACKET_55AA_POST_UPGRADE = (
        f"|55AA,1,2,1786521830,{IMEI},{ICCID},{UIN},{TARGET_VERSION},{VIN},4G,{STATE_NAME},FF|"
    )

    # Real-world serial response lines
    LOG_PROGRESS_25 = "[FOT] downloading 25.43%"
    LOG_PROGRESS_100 = "[FOT] downloading 100.00%"
    LOG_REBOOT_CLR_OK = f"STATUS#CLR#FOTA#OK#{IMEI}"
    LOG_REBOOT_SYS_BOOT = "System Booting... BOOTLOADER INIT"
    LOG_SWEMP = "STATUS#SET#SWEMP#MH#"
    LOG_CHTP = "STATUS#SET#CHTP#data.vahanshakti.in#4030#"
    LOG_CIP1 = "STATUS#SET#CIP1#data.vahanshakti.in#4040#"
    LOG_PRNCFG_SOFTWARE = f"######## SOFTWARE : {TARGET_VERSION} ########"
    LOG_PRNCFG_AEPL = f"aeplFwVer    {TARGET_VERSION}"

    # Real API history response item with skipped IP statuses
    API_ITEM_SKIPPED_IPS = {
        "imei": IMEI,
        "uin": UIN,
        "currentFirmwareVersion": TARGET_VERSION,
        "targetFirmwareVersion": TARGET_VERSION,
        "deviceFotaStatus": "Completed",
        "deviceFotaCompletionStatus": True,
        "progress": 100.0,
        "primaryIpStatus": "Skipped",
        "secondaryIpStatus": "Skipped",
        "stateEnableOtaStatus": "Set",
        "attemptCount": 1,
        "pingCount": 12
    }


class TestFota10StagesActualData(unittest.TestCase):
    """Integration test suite executing actual data test cases for all 10 FOTA Stages."""

    def setUp(self):
        self.app = get_qapp()
        self.temp_dir = tempfile.mkdtemp()
        self.mock_json_path = Path(self.temp_dir) / "servers.json"

        # Create realistic servers.json matrix matching production schema
        data = {
            "states": {
                ActualFotaStageTestData.STATE_NAME: {
                    "stateAbbreviation": "MH",
                    "govtIp1": "data.vahanshakti.in",
                    "port1": "4030",
                    "govtIp2": "data.vahanshakti.in",
                    "port2": "4040",
                    "stateEnable": "*SET#SWEMP#MH#",
                    "firmwares": [
                        {
                            "version": "5.2.8",
                            "expectedFirmwareVersion": "5.2.8",
                            "fileName": "ATCU_5.2.8.bin",
                            "description": "Initial Base Firmware"
                        },
                        {
                            "version": "5.2.9_REL13",
                            "expectedFirmwareVersion": "5.2.9_REL13",
                            "fileName": "ATCU_5.2.9_REL13.bin",
                            "description": "Target Upgrade Firmware"
                        }
                    ]
                }
            }
        }
        with open(self.mock_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.orchestrator = FotaOrchestrator()
        self.orchestrator.config.firmware_json_path = self.mock_json_path
        self.orchestrator.resolver = FirmwareResolver(self.mock_json_path)

        self.emitted_stages = []
        self.orchestrator.stage_signal.connect(
            lambda stage, status, msg: self.emitted_stages.append((stage, status, msg))
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_stage_1_telemetry_params_abstracted_from_55aa_packet(self):
        """Test Stage 1: Abstract all 5 telemetry fields (UIN, IMEI, VIN, Version, State) from genuine 55AA packet."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.uin, ActualFotaStageTestData.UIN)
        self.assertEqual(pkt.imei, ActualFotaStageTestData.IMEI)
        self.assertEqual(pkt.vin, ActualFotaStageTestData.VIN)
        self.assertEqual(pkt.version, ActualFotaStageTestData.INITIAL_VERSION)

        success = self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.assertTrue(success)
        self.assertEqual(self.orchestrator.stage_states[1], "PASSED")
        self.assertTrue(any(s == 1 and status == "PASSED" for s, status, _ in self.emitted_stages))

    def test_stage_2_validate_server_matrix_version_in_json(self):
        """Test Stage 2: Validate state server matrix and current version existence in servers.json."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)

        self.assertEqual(self.orchestrator.stage_states[2], "PASSED")
        self.assertTrue(any(s == 2 and status == "PASSED" for s, status, _ in self.emitted_stages))

    def test_stage_3_progress_sync_tracking_active(self):
        """Test Stage 3: Progress Sync tracking activates when serial log outputs download percentage."""
        prog = MessageParser.parse_download_progress(ActualFotaStageTestData.LOG_PROGRESS_25)
        self.assertAlmostEqual(prog, 25.43, places=2)

        self.orchestrator.update_progress(prog)
        self.assertEqual(self.orchestrator.stage_states[3], "PASSED")
        self.assertTrue(any(s == 3 and status == "PASSED" for s, status, _ in self.emitted_stages))

    def test_stage_4_initial_audit_report_logged(self):
        """Test Stage 4: Initial Audit Report logged when FOTA progress starts."""
        self.orchestrator.update_progress(10.0)
        self.assertEqual(self.orchestrator.stage_states[4], "PASSED")
        self.assertTrue(any(s == 4 and status == "PASSED" for s, status, _ in self.emitted_stages))

    def test_stage_5_100_percent_download_completed(self):
        """Test Stage 5: 100.0% Downloaded milestone reached."""
        self.orchestrator.update_progress(100.0)
        self.assertEqual(self.orchestrator.stage_states[5], "PASSED")
        self.assertTrue(self.orchestrator.download_100_reached)
        self.assertEqual(self.orchestrator.stage_states[6], "RUNNING")

    def test_stage_6_device_reboot_detected_from_clr_fota_ok(self):
        """Test Stage 6: Post-installation device reboot confirmed via STATUS#CLR#FOTA#OK log."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.download_100_reached = True

        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_REBOOT_CLR_OK)
        self.assertTrue(self.orchestrator.clr_fota_ok_received)
        self.assertTrue(self.orchestrator.reboot_detected)
        self.assertEqual(self.orchestrator.stage_states[6], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[7], "RUNNING")

    def test_stage_7_swemp_state_enabled_ota_verified(self):
        """Test Stage 7: SWEMP State Enabled OTA (*SET#SWEMP#MH#) verified from serial response."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.download_100_reached = True
        self.orchestrator.reboot_detected = True

        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_SWEMP)
        self.assertTrue(self.orchestrator.state_ota_verified)
        self.assertEqual(self.orchestrator.stage_states[7], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[8], "RUNNING")

    def test_stage_8_primary_chtp_ip1_and_port_verified(self):
        """Test Stage 8: Primary Server CHTP IP1 & Port1 verified from STATUS#SET#CHTP log."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.download_100_reached = True
        self.orchestrator.reboot_detected = True
        self.orchestrator.state_ota_verified = True

        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_CHTP)
        self.assertTrue(self.orchestrator.ip1_verified)
        self.assertEqual(self.orchestrator.stage_states[8], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[9], "RUNNING")

    def test_stage_9_secondary_cip1_ip2_and_port_verified(self):
        """Test Stage 9: Secondary Server CIP1 IP2 & Port2 verified from STATUS#SET#CIP1 log."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.download_100_reached = True
        self.orchestrator.reboot_detected = True
        self.orchestrator.state_ota_verified = True
        self.orchestrator.ip1_verified = True

        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_CIP1)
        self.assertTrue(self.orchestrator.ip2_verified)
        self.assertEqual(self.orchestrator.stage_states[9], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[10], "RUNNING")

    def test_stage_10_post_upgrade_firmware_version_match(self):
        """Test Stage 10: Post-upgrade firmware version in serial log matches target version."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.target_version = ActualFotaStageTestData.TARGET_VERSION
        self.orchestrator.download_100_reached = True
        self.orchestrator.reboot_detected = True
        self.orchestrator.state_ota_verified = True
        self.orchestrator.ip1_verified = True
        self.orchestrator.ip2_verified = True

        # Process post-upgrade log line
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_PRNCFG_SOFTWARE)
        self.assertTrue(self.orchestrator.config_verified)
        self.assertEqual(self.orchestrator.stage_states[10], "PASSED")

    def test_api_skipped_stages_auto_passes_stages_6_to_10(self):
        """Test that API history returning Primary/Secondary IP status as 'Skipped' passes Stages 6-9 directly."""
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.orchestrator.latest_api_history_item = ActualFotaStageTestData.API_ITEM_SKIPPED_IPS

        self.orchestrator._evaluate_api_skipped_stages()

        self.assertEqual(self.orchestrator.stage_states[6], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[7], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[8], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[9], "PASSED")

    def test_end_to_end_full_10_stages_execution_flow(self):
        """Test full sequential progression from Stage 1 through Stage 10 using actual data."""
        # 1. Capture 55AA Login Packet (Stage 1 & Stage 2)
        pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_LOGIN)
        self.orchestrator.process_login_packet(pkt, selected_ui_state=ActualFotaStageTestData.STATE_NAME)
        self.assertEqual(self.orchestrator.stage_states[1], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[2], "PASSED")

        # 2. Download progress updates (Stage 3 & Stage 4)
        prog25 = MessageParser.parse_download_progress(ActualFotaStageTestData.LOG_PROGRESS_25)
        self.orchestrator.update_progress(prog25)
        self.assertEqual(self.orchestrator.stage_states[3], "PASSED")
        self.assertEqual(self.orchestrator.stage_states[4], "PASSED")

        # 3. Download reaches 100% (Stage 5)
        prog100 = MessageParser.parse_download_progress(ActualFotaStageTestData.LOG_PROGRESS_100)
        self.orchestrator.update_progress(prog100)
        self.assertEqual(self.orchestrator.stage_states[5], "PASSED")
        self.assertTrue(self.orchestrator.download_100_reached)

        # 4. Device reboots post-install (Stage 6)
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_REBOOT_CLR_OK)
        self.assertEqual(self.orchestrator.stage_states[6], "PASSED")

        # 5. SWEMP State OTA response (Stage 7)
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_SWEMP)
        self.assertEqual(self.orchestrator.stage_states[7], "PASSED")

        # 6. Primary CHTP IP1 response (Stage 8)
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_CHTP)
        self.assertEqual(self.orchestrator.stage_states[8], "PASSED")

        # 7. Secondary CIP1 IP2 response (Stage 9)
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_CIP1)
        self.assertEqual(self.orchestrator.stage_states[9], "PASSED")

        # 8. Post-upgrade 55AA login packet / PRNCFG response (Stage 10)
        self.orchestrator.target_version = ActualFotaStageTestData.TARGET_VERSION
        post_pkt = MessageParser.parse_55aa_login_packet(ActualFotaStageTestData.PACKET_55AA_POST_UPGRADE)
        self.orchestrator.latest_55aa_login_packet = post_pkt
        self.orchestrator.process_log_line(ActualFotaStageTestData.LOG_PRNCFG_SOFTWARE)

        self.assertTrue(self.orchestrator.config_verified)
        self.assertEqual(self.orchestrator.stage_states[10], "PASSED")


if __name__ == "__main__":
    unittest.main()
