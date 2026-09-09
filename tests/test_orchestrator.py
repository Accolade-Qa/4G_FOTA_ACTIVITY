"""Unit tests for FotaOrchestrator module."""

import sys
import unittest
from PyQt6.QtCore import QCoreApplication
from backend.orchestrator import FotaOrchestrator
from backend.models import LoginPacketInfo


def get_qapp():
    """Get or create QCoreApplication instance."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


class TestFotaOrchestratorTelemetryValidation(unittest.TestCase):
    """Test suite verifying telemetry completeness check and state machine triggers."""

    def setUp(self):
        self.app = get_qapp()

    def test_is_complete_telemetry_valid(self):
        orchestrator = FotaOrchestrator()
        info = LoginPacketInfo(
            imei="861564069210428",
            iccid="8991000000000000000",
            uin="ACON4NA082300010428",
            version="5.2.9_REL13",
            vin="MAT00000000000000",
            model="4G",
            state="DO NOT DELETE"
        )
        self.assertTrue(orchestrator.is_complete_telemetry(info, selected_state="DO NOT DELETE"))

    def test_is_complete_telemetry_missing_fields(self):
        orchestrator = FotaOrchestrator()
        info = LoginPacketInfo(
            imei="",  # Missing IMEI
            iccid="",
            uin="ACON4NA082300010428",
            version="5.2.9_REL13",
            vin="MAT00000000000000",
            model="4G",
            state="DO NOT DELETE"
        )
        self.assertFalse(orchestrator.is_complete_telemetry(info, selected_state="DO NOT DELETE"))


class TestLineAutomationPhaseRecovery(unittest.TestCase):
    """Test suite verifying Line Automation phase consecutive $HW and $FW detection and staggered recovery command sequence."""

    def setUp(self):
        self.app = get_qapp()

    def test_line_automation_consecutive_hw_fw_triggers_recovery(self):
        orchestrator = FotaOrchestrator()
        commands_emitted = []
        orchestrator.request_command_signal.connect(lambda cmd: commands_emitted.append(cmd))

        # Line 1: $HW
        orchestrator.process_log_line("$HW,V1.0.,ATCU")
        self.assertIsNotNone(orchestrator._pending_hw_line)
        self.assertEqual(len(commands_emitted), 0)

        # Line 2: $FW (Immediate consecutive)
        orchestrator.process_log_line("$FW,5.2.9_REL13,L89HANR01A07S,EC20CEHDLGR06A10M1G")

        self.assertIsNone(orchestrator._pending_hw_line)
        self.assertTrue(orchestrator.is_line_automation_phase)
        self.assertTrue(orchestrator.line_automation_recovering)

        # Step 1 command $CONFIG_UIN fired immediately
        self.assertEqual(len(commands_emitted), 1)
        self.assertTrue(commands_emitted[0].startswith("$CONFIG_UIN,"))

        # Step 2 command $REBOOT fired after 2s NVM delay
        orchestrator._fire_line_automation_reboot_command()
        self.assertEqual(len(commands_emitted), 2)
        self.assertEqual(commands_emitted[1], "$REBOOT")

        # Step 4 command *SET#LOGFLTR#65535# fired after 60s post-reboot delay
        orchestrator._fire_line_automation_logfltr_command()
        self.assertEqual(len(commands_emitted), 3)
        self.assertEqual(commands_emitted[2], "*SET#LOGFLTR#65535#")
        self.assertFalse(orchestrator.is_line_automation_phase)
        self.assertFalse(orchestrator.line_automation_recovering)

    def test_normal_logging_phase_when_fw_not_consecutive(self):
        orchestrator = FotaOrchestrator()
        commands_emitted = []
        orchestrator.request_command_signal.connect(lambda cmd: commands_emitted.append(cmd))

        # Line 1: $HW
        orchestrator.process_log_line("$HW,V1.0.,ATCU")
        self.assertIsNotNone(orchestrator._pending_hw_line)

        # Line 2: Non-FW log line
        orchestrator.process_log_line("System Booting...")
        self.assertIsNone(orchestrator._pending_hw_line)
        self.assertFalse(orchestrator.is_line_automation_phase)
        self.assertEqual(len(commands_emitted), 0)


class TestStage10FirmwareComparison(unittest.TestCase):
    """Test suite verifying Stage 10 post-upgrade firmware version matching logic."""

    def setUp(self):
        self.app = get_qapp()

    def test_stage10_passes_when_target_version_matches(self):
        orchestrator = FotaOrchestrator()
        orchestrator.current_device = LoginPacketInfo(
            imei="861564069210428",
            iccid="8991000000000000000",
            uin="ACON4NA082300010428",
            version="5.2.8",
            vin="MAT00000000000000",
            model="4G",
            state="DO NOT DELETE"
        )
        orchestrator.target_version = "5.2.9_REL13"
        orchestrator.ip2_verified = True
        orchestrator.reboot_detected = True
        orchestrator.prncfg_response_received = True

        stage_events = []
        orchestrator.stage_signal.connect(lambda s, state, msg: stage_events.append((s, state, msg)))

        # Process log line with matching firmware version
        orchestrator._evaluate_stage10_completion("######## SOFTWARE : 5.2.9_REL13 ########")

        self.assertTrue(orchestrator.config_verified)
        self.assertEqual(orchestrator.stage_states[10], "PASSED")
        self.assertTrue(any(s == 10 and state == "PASSED" for s, state, _ in stage_events))


if __name__ == "__main__":
    unittest.main()
