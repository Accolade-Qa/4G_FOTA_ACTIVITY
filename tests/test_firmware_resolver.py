"""Unit tests for FirmwareResolver module."""

import json
import unittest
import tempfile
import shutil
from pathlib import Path
from backend.firmware_resolver import FirmwareResolver


class TestFirmwareResolverMatching(unittest.TestCase):
    """Test suite verifying hierarchical matching (exact, filename, substring) and target version resolution."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_json_path = Path(self.temp_dir) / "servers.json"

        data = {
            "states": {
                "SingleVersionState": {
                    "stateAbbreviation": "SV",
                    "firmwares": [
                        {
                            "version": "5.2.9_REL13",
                            "expectedFirmwareVersion": "5.2.9_REL13_FINAL",
                            "fileName": "ATCU_5.2.9_REL13.bin",
                            "description": "Single version test"
                        }
                    ]
                },
                "MultiVersionState": {
                    "stateAbbreviation": "MV",
                    "firmwares": [
                        {
                            "version": "5.2.8",
                            "expectedFirmwareVersion": "5.2.8_BASE",
                            "fileName": "ATCU_5.2.8.bin",
                            "description": "Base release"
                        },
                        {
                            "version": "5.2.9_REL12",
                            "expectedFirmwareVersion": "5.2.9_REL12",
                            "fileName": "ATCU_5.2.9_REL12.bin",
                            "description": "Intermediate release"
                        },
                        {
                            "version": "5.2.9_REL13",
                            "expectedFirmwareVersion": "5.2.9_REL13",
                            "fileName": "ATCU_5.2.9_REL13.bin",
                            "description": "Target release"
                        }
                    ]
                }
            }
        }
        with open(self.mock_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.resolver = FirmwareResolver(self.mock_json_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_version_exists(self):
        self.assertTrue(self.resolver.validate_version_exists("MultiVersionState", "5.2.8"))
        self.assertTrue(self.resolver.validate_version_exists("MultiVersionState", "5.2.9_REL12"))
        self.assertFalse(self.resolver.validate_version_exists("MultiVersionState", "9.9.9_UNKNOWN"))

    def test_resolve_single_version_state(self):
        target = self.resolver.resolve_next_version("SingleVersionState", "5.2.9_REL13")
        # Single object state resolves to expected target version
        self.assertEqual(target, "5.2.9_REL13_FINAL")

    def test_resolve_next_version_multi_version_step(self):
        # Step 1: 5.2.8 -> 5.2.9_REL12
        next_ver = self.resolver.resolve_next_version("MultiVersionState", "5.2.8")
        self.assertEqual(next_ver, "5.2.9_REL12")

        # Step 2: 5.2.9_REL12 -> 5.2.9_REL13
        next_ver2 = self.resolver.resolve_next_version("MultiVersionState", "5.2.9_REL12")
        self.assertEqual(next_ver2, "5.2.9_REL13")

    def test_resolve_next_version_at_latest_returns_none(self):
        # Device is at last object in matrix -> returns None (no further upgrade)
        target = self.resolver.resolve_next_version("MultiVersionState", "5.2.9_REL13")
        self.assertIsNone(target)

    def test_validation_barrier_blocks_unlisted_version(self):
        target = self.resolver.resolve_next_version("MultiVersionState", "7.7.7_UNLISTED")
        self.assertIsNone(target)

    def test_resolve_next_version_after_aborted(self):
        # Aborted at 5.2.8 -> resolves next step 5.2.9_REL12
        next_ver = self.resolver.resolve_next_version_after_aborted("MultiVersionState", "5.2.8", "5.2.8")
        self.assertEqual(next_ver, "5.2.9_REL12")


if __name__ == "__main__":
    unittest.main()
