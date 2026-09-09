"""Unit tests for MessageParser and TelemetryAccumulator modules."""

import unittest
from backend.message_parser import MessageParser, TelemetryAccumulator
from backend.models import LoginPacketInfo


class TestMessageParserValidation(unittest.TestCase):
    """Test suite verifying validation functions for UIN, IMEI, VIN, and State names."""

    def test_valid_uin_format(self):
        self.assertTrue(MessageParser.is_valid_uin("ACON4NA082300010428"))
        self.assertTrue(MessageParser.is_valid_uin("ACON1234567"))

    def test_invalid_uin_format(self):
        self.assertFalse(MessageParser.is_valid_uin("INVALID_PREFIX_123"))
        self.assertFalse(MessageParser.is_valid_uin("ACON"))
        self.assertFalse(MessageParser.is_valid_uin(""))
        self.assertFalse(MessageParser.is_valid_uin(None))

    def test_valid_imei_format(self):
        self.assertTrue(MessageParser.is_valid_imei("861564069210428"))
        self.assertTrue(MessageParser.is_valid_imei("123456789012345"))

    def test_invalid_imei_format(self):
        self.assertFalse(MessageParser.is_valid_imei("1234"))
        self.assertFalse(MessageParser.is_valid_imei("8615640692104289999"))
        self.assertFalse(MessageParser.is_valid_imei("ABC12345678901"))
        self.assertFalse(MessageParser.is_valid_imei(None))

    def test_valid_vin_format(self):
        self.assertTrue(MessageParser.is_valid_vin("MAT00000000000000"))
        self.assertTrue(MessageParser.is_valid_vin("MA1XY2ZB3CD4EF567"))

    def test_invalid_vin_format(self):
        self.assertFalse(MessageParser.is_valid_vin("SYNCHRONIZATION"))
        self.assertFalse(MessageParser.is_valid_vin("AUTHENTICATION"))
        self.assertFalse(MessageParser.is_valid_vin("123456789012345"))
        self.assertFalse(MessageParser.is_valid_vin("SHORT"))
        self.assertFalse(MessageParser.is_valid_vin(None))


class TestFirmwareVersionParsing(unittest.TestCase):
    """Test suite verifying firmware version string extraction across multiple log formats."""

    def test_parse_firmware_version_from_line_automation_fw_header(self):
        line = "$FW,5.2.9_REL13,L89HANR01A07S,EC20CEHDLGR06A10M1G"
        ver = MessageParser.parse_firmware_version(line)
        self.assertEqual(ver, "5.2.9_REL13")

    def test_parse_firmware_version_from_aepl_fw_ver_format(self):
        line = "aeplFwVer    5.2.9 5th IP"
        ver = MessageParser.parse_firmware_version(line)
        self.assertEqual(ver, "5.2.9 5th IP")

    def test_parse_firmware_version_from_software_header(self):
        line = "######## SOFTWARE : 5.2.9_REL12           ########"
        ver = MessageParser.parse_firmware_version(line)
        self.assertEqual(ver, "5.2.9_REL12")

    def test_parse_firmware_version_from_firmware_header(self):
        line = "FIRMWARE : 5.2.8_MHBEST04"
        ver = MessageParser.parse_firmware_version(line)
        self.assertEqual(ver, "5.2.8_MHBEST04")

    def test_parse_firmware_version_returns_none_for_unrelated_logs(self):
        self.assertIsNone(MessageParser.parse_firmware_version("System Booting..."))
        self.assertIsNone(MessageParser.parse_firmware_version("GSM soft shutdown pass"))


class TestLineAutomationDetection(unittest.TestCase):
    """Test suite verifying $HW, and $FW, line automation detection helpers."""

    def test_is_hw_line_detection(self):
        self.assertTrue(MessageParser.is_hw_line("$HW,V1.0.,ATCU"))
        self.assertTrue(MessageParser.is_hw_line("  $HW,V2.0.,TCU  "))
        self.assertFalse(MessageParser.is_hw_line("System Booting..."))

    def test_is_fw_line_detection(self):
        self.assertTrue(MessageParser.is_fw_line("$FW,5.2.9_REL13,L89HANR01A07S,EC20CEHDLGR06A10M1G"))
        self.assertTrue(MessageParser.is_fw_line("  $FW,1.0.0,TEST  "))
        self.assertFalse(MessageParser.is_fw_line("System Booting..."))


class TestLoginPacketParsing(unittest.TestCase):
    """Test suite for parsing 55AA Login Packets."""

    def test_parse_55aa_login_packet(self):
        raw_log = "|55AA,1,2,1786521830,861564069210428,8991000000000000000,ACON4NA082300010428,5.2.9_REL13,MAT00000000000000,4G,DO NOT DELETE,FF|"
        pkt = MessageParser.parse_55aa_login_packet(raw_log)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.imei, "861564069210428")
        self.assertEqual(pkt.uin, "ACON4NA082300010428")
        self.assertEqual(pkt.version, "5.2.9_REL13")
        self.assertEqual(pkt.vin, "MAT00000000000000")

    def test_parse_55aa_login_packet_returns_none_for_invalid_log(self):
        self.assertIsNone(MessageParser.parse_55aa_login_packet("Invalid log payload"))


class TestTelemetryAccumulator(unittest.TestCase):
    """Test suite for TelemetryAccumulator multi-line harvesting."""

    def test_feed_line_accumulates_telemetry_fields(self):
        acc = TelemetryAccumulator()

        acc.feed_line("UIN: ACON4NA082300010428")
        acc.feed_line("IMEI: 861564069210428")
        acc.feed_line("VIN: MAT00000000000000")
        info = acc.feed_line("FIRMWARE : 5.2.9_REL13")

        self.assertIsNotNone(info)
        self.assertEqual(info.uin, "ACON4NA082300010428")
        self.assertEqual(info.imei, "861564069210428")
        self.assertEqual(info.vin, "MAT00000000000000")
        self.assertEqual(info.version, "5.2.9_REL13")


class TestIpPortParsing(unittest.TestCase):
    """Test suite for primary, secondary, tertiary, and quaternary IP/Port log parsing."""

    def test_parse_chtp_ip1_and_port(self):
        res = MessageParser.parse_chtp_primary_ip_port("*SET#CHTP#10.2.1.5#6100#")
        self.assertEqual(res, ("10.2.1.5", "6100"))

    def test_parse_cip1_ip2_and_port(self):
        res = MessageParser.parse_cip1_secondary_ip_port("STATUS#SET#CIP1#10.2.1.6#6101#")
        self.assertEqual(res, ("10.2.1.6", "6101"))

    def test_parse_cip2_ip3_and_port(self):
        res = MessageParser.parse_cip2_tertiary_ip_port("STATUS#SET#CIP2#10.2.1.7#6102#")
        self.assertEqual(res, ("10.2.1.7", "6102"))

    def test_parse_cip3_ip4_and_port(self):
        res = MessageParser.parse_cip3_quaternary_ip_port("STATUS#SET#CIP3#10.2.1.8#6103#")
        self.assertEqual(res, ("10.2.1.8", "6103"))


if __name__ == "__main__":
    unittest.main()
