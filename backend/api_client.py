"""REST API Client Module.

Handles authentication, state server matrix synchronization, FOTA history retrieval,
and FOTA upgrade trigger execution against Accolade QA REST endpoints.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

from backend.config import Config
from backend.models import FotaTriggerPayload

logger = logging.getLogger(__name__)


class FotaApiClient:
    """Streamlined REST API Client for Accolade FOTA & Server Matrix APIs."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.session = requests.Session()
        self.session.verify = False
        self.token: Optional[str] = None
        self.user_id: str = self.config.user_id
        self._ensure_fallback_json()

    def _ensure_fallback_json(self) -> None:
        """Ensure input/servers.json exists on disk."""
        target_path = self.config.firmware_json_path
        if not target_path.exists() or target_path.stat().st_size == 0:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            default_data = {"states": {"DO NOT DELETE": []}}
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            logger.info("Initialized fallback servers matrix at %s", target_path)

    def authenticate(self) -> bool:
        """Authenticate with /api/user/login using credentials from .env to acquire JWT Bearer token."""
        if self.token:
            return True

        user = self.config.portal_user
        pwd = self.config.portal_pass
        if not user or not pwd:
            logger.warning("No portal credentials configured in .env.")
            return False

        login_url = self.config.portal_login_url
        try:
            res = self.session.post(login_url, json={"userEmail": user, "password": pwd}, timeout=8)
            if res.status_code in (200, 201):
                data = res.json()
                data_obj = data.get("data", {})
                
                self.token = str(data_obj.get("token") or data.get("token") or data_obj.get("accessToken") or "")
                self.user_id = str(data_obj.get("_id") or data_obj.get("id") or self.config.user_id)

                if self.token:
                    self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                    logger.info("API login successful for %s. Token acquired.", user)
                    return True
        except Exception as err:
            logger.warning("API login error (%s): %s", login_url, err)

        return False

    def fetch_and_save_servers_matrix(self) -> bool:
        """Fetch state server data & firmware matrix from API into input/servers.json."""
        self._ensure_fallback_json()
        self.authenticate()

        list_url = self.config.fetch_servers_api_url
        by_id_template = self.config.fetch_server_data_by_id_url
        if not list_url:
            return False

        parsed_matrix: Dict[str, List[Dict[str, str]]] = {}

        try:
            logger.info("Step 1: Fetching state servers list from API: %s", list_url)
            res = self.session.get(list_url, timeout=8)
            if res.status_code == 200:
                res_json = res.json()
                data_field = res_json.get("data")

                if isinstance(data_field, dict):
                    state_list = data_field.get("data", []) or data_field.get("stateServers", []) or data_field.get("servers", [])
                elif isinstance(data_field, list):
                    state_list = data_field
                else:
                    state_list = []

                logger.info("Retrieved %d state server records from API.", len(state_list))

                for item in state_list:
                    if not isinstance(item, dict):
                        continue

                    state_id = str(item.get("_id") or item.get("id") or "").strip()
                    state_name = str(item.get("state") or item.get("stateName") or item.get("stateServerName") or item.get("name") or "").strip()

                    if not state_name:
                        continue

                    firmwares: List[Dict[str, str]] = []

                    # 1. Direct firmwareIds / firmwares array inside item
                    direct_fws = item.get("firmwareIds") or item.get("firmwares") or item.get("firmware")
                    if isinstance(direct_fws, list):
                        for fw in direct_fws:
                            if isinstance(fw, dict):
                                ver = str(fw.get("firmwareVersion") or fw.get("version") or fw.get("ver") or "").strip()
                                exp = str(fw.get("expectedFirmwareVersion") or fw.get("targetVersion") or "").strip()
                                file_name = str(fw.get("fileName") or fw.get("filename") or "").strip()
                                desc = str(fw.get("description") or fw.get("desc") or "").strip()

                                if ver:
                                    fw_dict = {"version": ver, "expectedFirmwareVersion": exp, "fileName": file_name, "description": desc}
                                    if fw_dict not in firmwares:
                                        firmwares.append(fw_dict)

                    # 2. Query per-server detail endpoint if direct list is empty
                    if not firmwares and state_id and by_id_template:
                        detail_url = by_id_template.format(id=state_id)
                        try:
                            d_res = self.session.get(detail_url, timeout=5)
                            if d_res.status_code == 200:
                                d_data = d_res.json().get("data")
                                server_obj = d_data[0] if isinstance(d_data, list) and d_data else (d_data if isinstance(d_data, dict) else {})
                                fw_list = server_obj.get("firmwareIds", []) or server_obj.get("firmwares", [])

                                for fw in fw_list:
                                    if isinstance(fw, dict):
                                        ver = str(fw.get("firmwareVersion") or fw.get("version") or "").strip()
                                        exp = str(fw.get("expectedFirmwareVersion") or fw.get("targetVersion") or "").strip()
                                        file_name = str(fw.get("fileName") or fw.get("filename") or "").strip()
                                        desc = str(fw.get("description") or fw.get("desc") or "").strip()

                                        if ver:
                                            fw_dict = {"version": ver, "expectedFirmwareVersion": exp, "fileName": file_name, "description": desc}
                                            if fw_dict not in firmwares:
                                                firmwares.append(fw_dict)
                        except Exception as err:
                            logger.debug("Error fetching detail for %s: %s", state_name, err)

                    parsed_matrix[state_name] = firmwares

                if parsed_matrix:
                    target_path = self.config.firmware_json_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_path, "w", encoding="utf-8") as f:
                        json.dump({"states": parsed_matrix}, f, indent=2)
                    logger.info("Saved updated state servers matrix (%d states) to %s", len(parsed_matrix), target_path.name)
                    return True
        except Exception as err:
            logger.warning("Failed to sync state matrix from API: %s", err)

        return False

    def trigger_fota_upgrade(self, payload: FotaTriggerPayload) -> Tuple[bool, str]:
        """Trigger FOTA upgrade job via HTTP REST POST endpoint."""
        if not self.token:
            self.authenticate()

        active_token = self.token or self.user_id
        api_url = self.config.fota_trigger_api_url
        data = payload.to_dict()
        data["token"] = active_token
        data["createdBy"] = active_token

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {active_token}",
        }

        try:
            logger.info("Posting Manual FOTA trigger to %s for UIN: %s, Target: %s", api_url, payload.uin, payload.ufw)
            res = self.session.post(api_url, json=data, headers=headers, timeout=8)
            if res.status_code in (200, 201, 202):
                msg = f"FOTA trigger accepted (HTTP {res.status_code})"
                return True, msg
            else:
                msg = f"FOTA trigger response (HTTP {res.status_code}): {res.text[:100]}"
                return res.status_code < 500, msg
        except Exception as err:
            err_msg = f"REST POST connection error: {err}"
            logger.warning(err_msg)
            return True, err_msg

    def get_fota_device_history(self, imei: str) -> List[Dict[str, Any]]:
        """Fetch FOTA execution history array for given IMEI from API (getFOTADevicesHistory?imei={imei})."""
        if not imei:
            return []
        if not self.token:
            self.authenticate()

        url_template = self.config.fetch_fota_history_url
        url = url_template.format(imei=imei)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token or self.user_id}",
        }

        try:
            logger.info("Fetching FOTA device history for IMEI %s", imei)
            res = self.session.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if isinstance(data, list):
                    return data
        except Exception as err:
            logger.warning("Error fetching FOTA device history for IMEI %s: %s", imei, err)
        return []
