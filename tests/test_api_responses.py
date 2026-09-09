"""Unit tests for testing REST API Client responses, authentication, history evaluation, and FOTA trigger POST endpoints."""

import sys
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from PyQt6.QtCore import QCoreApplication

from backend.api_client import FotaApiClient
from backend.models import LoginPacketInfo, FotaTriggerPayload
from backend.orchestrator import FotaOrchestrator, FotaAsyncTriggerWorker, is_active_fota_session


def get_qapp():
    """Get or create QCoreApplication instance."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


class MockApiResponseData:
    """Fixture containing realistic API JSON responses from Accolade FOTA & Server APIs."""

    IMEI = "861564069210428"
    UIN = "ACON4NA082300010428"

    # 1. Login API Response (/api/user/login)
    LOGIN_SUCCESS_RESPONSE = {
        "status": 200,
        "message": "Login successful",
        "data": {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2NzdjZDIxODEiLCJpYXQiOjE3ODY1MjE4MzB9.sample_token_hash",
            "id": "677cd2181b05f196abd64907",
            "email": "suraj.bhalerao@accoladeelectronics.com"
        }
    }

    # 2. State Servers List Response (/api/server/getServerData)
    STATE_SERVERS_LIST_RESPONSE = {
        "status": 200,
        "data": {
            "data": [
                {
                    "_id": "srv_001",
                    "state": "Maharashtra",
                    "stateAbbreviation": "MH",
                    "govtIp1": "data.vahanshakti.in",
                    "port1": "4030",
                    "govtIp2": "data.vahanshakti.in",
                    "port2": "4040",
                    "stateEnable": "*SET#SWEMP#MH#"
                },
                {
                    "_id": "srv_002",
                    "state": "Assam",
                    "stateAbbreviation": "AS",
                    "govtIp1": "assam.vahan.in",
                    "port1": "5030",
                    "govtIp2": "assam.vahan.in",
                    "port2": "5040",
                    "stateEnable": "*SET#SWEMP#AS#"
                }
            ]
        }
    }

    # 3. Per-Server Firmware Details Response (/api/server/getServerDataByUId?id=srv_001)
    SERVER_DETAIL_RESPONSE = {
        "status": 200,
        "data": [
            {
                "_id": "srv_001",
                "state": "Maharashtra",
                "firmwareIds": [
                    {
                        "version": "5.2.8",
                        "expectedFirmwareVersion": "5.2.8",
                        "fileName": "ATCU_5.2.8.bin",
                        "description": "Base Release"
                    },
                    {
                        "version": "5.2.9_REL13",
                        "expectedFirmwareVersion": "5.2.9_REL13",
                        "fileName": "ATCU_5.2.9_REL13.bin",
                        "description": "Target Release"
                    }
                ]
            }
        ]
    }

    # 4. FOTA Device History API Responses (/api/fota/getFotaDeviceHistory?search=861564069210428)
    HISTORY_COMPLETED_RESPONSE = {
        "status": 200,
        "data": [
            {
                "_id": "hist_001",
                "imei": IMEI,
                "uin": UIN,
                "currentFirmwareVersion": "5.2.9_REL13",
                "targetFirmwareVersion": "5.2.9_REL13",
                "deviceFotaStatus": "Completed",
                "deviceFotaCompletionStatus": True,
                "progress": 100.0,
                "primaryIpStatus": "Skipped",
                "secondaryIpStatus": "Skipped",
                "stateEnableOtaStatus": "Set",
                "attemptCount": 1,
                "pingCount": 14,
                "addedToBatch": True,
                "isAborted": False
            }
        ]
    }

    HISTORY_ACTIVE_PENDING_RESPONSE = {
        "status": 200,
        "data": [
            {
                "_id": "hist_002",
                "imei": IMEI,
                "uin": UIN,
                "currentFirmwareVersion": "5.2.8",
                "targetFirmwareVersion": "5.2.9_REL13",
                "deviceFotaStatus": "In-Progress",
                "deviceFotaCompletionStatus": False,
                "progress": 45.8,
                "primaryIpStatus": "Pending",
                "secondaryIpStatus": "Pending",
                "stateEnableOtaStatus": "Set",
                "attemptCount": 1,
                "pingCount": 8,
                "addedToBatch": True,
                "isAborted": False
            }
        ]
    }

    HISTORY_MANUALLY_ABORTED_RESPONSE = {
        "status": 200,
        "data": [
            {
                "_id": "hist_003",
                "imei": IMEI,
                "uin": UIN,
                "currentFirmwareVersion": "5.2.8",
                "targetFirmwareVersion": "5.2.9_REL12",
                "deviceFotaStatus": "Aborted",
                "deviceFotaCompletionStatus": False,
                "progress": 20.0,
                "isAborted": True,
                "abortReason": "Aborted manually by tester admin",
                "attemptCount": 1,
                "pingCount": 4
            }
        ]
    }

    HISTORY_SYSTEM_ABORTED_RESPONSE = {
        "status": 200,
        "data": [
            {
                "_id": "hist_004",
                "imei": IMEI,
                "uin": UIN,
                "currentFirmwareVersion": "5.2.8",
                "targetFirmwareVersion": "5.2.9_REL12",
                "deviceFotaStatus": "Aborted",
                "deviceFotaCompletionStatus": False,
                "progress": 15.0,
                "isAborted": True,
                "abortReason": "Download timeout / retry limit reached",
                "attemptCount": 3,
                "pingCount": 2
            }
        ]
    }

    # 5. FOTA Upgrade Trigger API Response (/api/fota/createManualFota)
    TRIGGER_SUCCESS_RESPONSE = {
        "status": 200,
        "message": "FOTA upgrade request submitted successfully",
        "data": {"fotaId": "fota_999"}
    }


class TestFotaApiClientResponses(unittest.TestCase):
    """Test suite testing FotaApiClient HTTP requests and response parsing."""

    def setUp(self):
        self.client = FotaApiClient()

    @patch("requests.Session.post")
    def test_authenticate_success(self, mock_post):
        """Test successful JWT Bearer authentication response from login API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MockApiResponseData.LOGIN_SUCCESS_RESPONSE
        mock_post.return_value = mock_resp

        success = self.client.authenticate()
        self.assertTrue(success)
        self.assertIsNotNone(self.client.token)
        self.assertEqual(self.client.user_id, "677cd2181b05f196abd64907")
        self.assertIn("Authorization", self.client.session.headers)

    @patch("requests.Session.post")
    def test_authenticate_invalid_credentials_returns_false(self, mock_post):
        """Test authentication response for invalid user email or password."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"status": 401, "message": "Invalid password"}
        mock_post.return_value = mock_resp

        success = self.client.authenticate()
        self.assertFalse(success)

    @patch("requests.Session.get")
    @patch.object(FotaApiClient, "authenticate")
    def test_fetch_and_save_servers_matrix_from_api(self, mock_auth, mock_get):
        """Test 2-step API fetch for state servers list and per-server firmware IDs."""
        mock_auth.return_value = True

        # Setup mock side effects for list_url (step 1) and by_id_url (step 2)
        resp_list = MagicMock()
        resp_list.status_code = 200
        resp_list.json.return_value = MockApiResponseData.STATE_SERVERS_LIST_RESPONSE

        resp_detail = MagicMock()
        resp_detail.status_code = 200
        resp_detail.json.return_value = MockApiResponseData.SERVER_DETAIL_RESPONSE

        mock_get.side_effect = [resp_list, resp_detail, resp_detail]

        ok = self.client.fetch_and_save_servers_matrix()
        self.assertTrue(ok)
        self.assertTrue(self.client.config.firmware_json_path.exists())

        with open(self.client.config.firmware_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("Maharashtra", data.get("states", {}))
            self.assertIn("Assam", data.get("states", {}))

    @patch("requests.Session.get")
    def test_get_fota_device_history_returns_records(self, mock_get):
        """Test fetching FOTA device history records for an IMEI."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MockApiResponseData.HISTORY_COMPLETED_RESPONSE
        mock_get.return_value = mock_resp

        history = self.client.get_fota_device_history(MockApiResponseData.IMEI)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["deviceFotaStatus"], "Completed")
        self.assertEqual(history[0]["progress"], 100.0)

    @patch("requests.Session.post")
    def test_trigger_fota_upgrade_accepted(self, mock_post):
        """Test submitting manual FOTA upgrade payload to createManualFota API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MockApiResponseData.TRIGGER_SUCCESS_RESPONSE
        mock_post.return_value = mock_resp

        payload = FotaTriggerPayload(
            imei=MockApiResponseData.IMEI,
            model="4G",
            state="Maharashtra",
            ufw="5.2.9_REL13",
            uin=MockApiResponseData.UIN
        )
        success, msg = self.client.trigger_fota_upgrade(payload)
        self.assertTrue(success)
        self.assertIn("accepted", msg.lower())


class TestFotaApiHistoryEvaluation(unittest.TestCase):
    """Test suite testing orchestrator evaluation of server API history responses."""

    def setUp(self):
        self.app = get_qapp()
        self.orchestrator = FotaOrchestrator()

    def test_is_active_fota_session_validation(self):
        """Test is_active_fota_session helper logic on API response items."""
        active_item = {
            "addedToBatch": True,
            "isAborted": False,
            "deviceFotaCompletionStatus": False,
            "progress": 45.0,
            "attemptCount": 1
        }
        self.assertTrue(is_active_fota_session(active_item))

        completed_item = {
            "addedToBatch": True,
            "isAborted": False,
            "deviceFotaCompletionStatus": True,
            "progress": 100.0,
            "attemptCount": 1
        }
        self.assertFalse(is_active_fota_session(completed_item))

        attempts_exceeded_item = {
            "addedToBatch": True,
            "isAborted": False,
            "deviceFotaCompletionStatus": False,
            "progress": 20.0,
            "attemptCount": 3
        }
        self.assertFalse(is_active_fota_session(attempts_exceeded_item))

    def test_check_api_server_statuses_all_set_or_skipped(self):
        """Test check_api_server_statuses_set helper on API history responses."""
        all_set_item = {
            "stateEnableOtaStatus": "Set",
            "primaryIpStatus": "Skipped",
            "secondaryIpStatus": "Set"
        }
        ok, msg = self.orchestrator.check_api_server_statuses_set(all_set_item)
        self.assertTrue(ok)

        pending_item = {
            "stateEnableOtaStatus": "Set",
            "primaryIpStatus": "Pending",
            "secondaryIpStatus": "Set"
        }
        ok, msg = self.orchestrator.check_api_server_statuses_set(pending_item)
        self.assertFalse(ok)
        self.assertIn("Primary IP Status", msg)

    def test_async_trigger_worker_completed_history(self):
        """Test FotaAsyncTriggerWorker processing of Completed API history item."""
        login_info = LoginPacketInfo(
            imei=MockApiResponseData.IMEI,
            iccid="8991000000000000000",
            uin=MockApiResponseData.UIN,
            version="5.2.8",
            vin="MAT00000000000000",
            model="4G",
            state="Maharashtra"
        )

        with patch.object(self.orchestrator.api_client, "get_fota_device_history") as mock_hist:
            mock_hist.return_value = MockApiResponseData.HISTORY_COMPLETED_RESPONSE["data"]

            worker = FotaAsyncTriggerWorker(self.orchestrator, login_info, "Maharashtra")

            finished_results = []
            worker.finished_signal.connect(lambda s, target, api_m, status_m, item: finished_results.append((s, target, api_m, item)))
            worker.run()

            self.assertTrue(len(finished_results) >= 1)
            success, target, api_msg, raw_item = finished_results[0]
            self.assertTrue(success)
            self.assertEqual(api_msg, "SCANNED_HISTORY")
            self.assertEqual(raw_item["deviceFotaStatus"], "Completed")

    def test_async_trigger_worker_manually_aborted_history(self):
        """Test FotaAsyncTriggerWorker processing of Manually Aborted API history item."""
        login_info = LoginPacketInfo(
            imei=MockApiResponseData.IMEI,
            iccid="8991000000000000000",
            uin=MockApiResponseData.UIN,
            version="5.2.8",
            vin="MAT00000000000000",
            model="4G",
            state="Maharashtra"
        )

        with patch.object(self.orchestrator.api_client, "get_fota_device_history") as mock_hist:
            with patch.object(self.orchestrator.api_client, "trigger_fota_upgrade") as mock_trig:
                mock_hist.return_value = MockApiResponseData.HISTORY_MANUALLY_ABORTED_RESPONSE["data"]
                mock_trig.return_value = (True, "Trigger accepted")

                worker = FotaAsyncTriggerWorker(self.orchestrator, login_info, "Maharashtra")

                finished_results = []
                worker.finished_signal.connect(lambda s, target, api_m, status_m, item: finished_results.append((s, target, api_m, item)))
                worker.run()

                self.assertTrue(len(finished_results) >= 1)
                # First result is scanned history
                self.assertEqual(finished_results[0][2], "SCANNED_HISTORY")


if __name__ == "__main__":
    unittest.main()
