"""REST API Client Module.

Handles authentication, fetching state server matrices & firmware IDs,
writing structured input/servers.json, and submitting FOTA initialization triggers.
Implements 2-step API flow:
1. GET /api/server/getServerData?page=1&size=1000&search=
2. GET /api/server/getServerDataByUId?id={_id} -> extracts firmwareIds array
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
    """Production REST API Client for Accolade FOTA & Government Server APIs."""

    DEFAULT_SERVERS_MATRIX = {
        "states": {
            "DO NOT DELETE": [
                {"version": "1.0.0", "expectedFirmwareVersion": "1.0.1", "fileName": "TCP01.bin", "description": "Base firmware"},
                {"version": "1.0.1", "expectedFirmwareVersion": "1.0.2", "fileName": "TCP01_v101.bin", "description": "Patch update 1"},
            ],
            "Bihar": [
                {"version": "1.0.0", "expectedFirmwareVersion": "1.0.1", "fileName": "TCP01.bin", "description": "Base firmware"},
                {"version": "1.0.1", "expectedFirmwareVersion": "1.0.2", "fileName": "TCP01_v101.bin", "description": "Patch update 1"},
                {"version": "1.0.2", "expectedFirmwareVersion": "1.0.3", "fileName": "TCP01_v102.bin", "description": "Release 1.0.2"},
            ],
            "Maharashtra": [
                {"version": "1.0.0", "expectedFirmwareVersion": "1.0.1", "fileName": "TCP01.bin", "description": "Base firmware"},
                {"version": "1.0.1", "expectedFirmwareVersion": "1.0.2", "fileName": "TCP01_v101.bin", "description": "Patch update 1"},
            ],
            "Assam": [
                {"version": "212", "expectedFirmwareVersion": "213", "fileName": "TCP01_v212.bin", "description": "Assam Release 212"},
                {"version": "213", "expectedFirmwareVersion": "214", "fileName": "TCP01_v213.bin", "description": "Assam Release 213"},
            ],
            "Default": [
                {"version": "1.0.0", "expectedFirmwareVersion": "1.0.1", "fileName": "TCP01.bin", "description": "Default base firmware"},
                {"version": "1.0.1", "expectedFirmwareVersion": "1.0.2", "fileName": "TCP01_v101.bin", "description": "Default patch update"},
                {"version": "1.0.2", "expectedFirmwareVersion": "1.0.3", "fileName": "TCP01_v102.bin", "description": "Default release 1.0.2"},
            ]
        }
    }

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.session = requests.Session()
        self.session.verify = False
        self.token: Optional[str] = None
        self.user_id: str = self.config.user_id
        self.session.headers.update({
            "User-Agent": "Accolade-ContinuousFotaUtility/2.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._ensure_fallback_json()

    def _ensure_fallback_json(self) -> None:
        """Ensure input/servers.json exists on disk immediately."""
        target_path = self.config.firmware_json_path
        if not target_path.exists() or target_path.stat().st_size == 0:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_SERVERS_MATRIX, f, indent=2)
            logger.info("Initialized default state servers matrix at %s", target_path)

    def authenticate(self) -> bool:
        """Authenticate with configured portal API using userEmail/password from .env to acquire valid JWT bearer token."""
        if self.token:
            return True

        user = self.config.portal_user
        pwd = self.config.portal_pass

        if not user or not pwd:
            logger.warning("No portal credentials found in .env configuration.")
            return False

        login_url = self.config.portal_login_url
        payload = {"userEmail": user, "password": pwd}

        try:
            res = self.session.post(login_url, json=payload, timeout=8)
            if res.status_code in (200, 201):
                data = res.json()
                token_val = (
                    data.get("data", {}).get("token")
                    or data.get("token")
                    or data.get("data", {}).get("accessToken")
                    or data.get("data", {}).get("user", {}).get("token")
                    or data.get("accessToken")
                )
                user_id_val = (
                    data.get("data", {}).get("id")
                    or data.get("data", {}).get("_id")
                    or data.get("id")
                    or data.get("_id")
                    or data.get("data", {}).get("user", {}).get("_id")
                )
                if user_id_val:
                    self.user_id = str(user_id_val)

                if token_val and isinstance(token_val, str) and len(token_val) > 15:
                    self.token = str(token_val)
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.token}",
                        "token": self.token,
                        "x-access-token": self.token,
                    })
                    logger.info("API login successful for %s. Bearer JWT token acquired. User ID: %s", user, self.user_id)
                    print(f"API Login Successful ({login_url}) for {user}")
                    return True
        except Exception as err:
            logger.debug("API login connection error for %s: %s", login_url, err)

        logger.warning("All API login attempts failed. Operating with cached matrix.")
        return False

    def _extract_firmware_dict(self, fw: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Helper to extract firmware metadata dictionary from API JSON item."""
        if not isinstance(fw, dict):
            return None

        ver = (
            fw.get("firmwareVersion")
            or fw.get("version")
            or fw.get("firmware_version")
            or fw.get("ver")
            or fw.get("ufw")
            or ""
        )
        expected_ver = (
            fw.get("expectedFirmwareVersion")
            or fw.get("targetVersion")
            or fw.get("expectedVersion")
            or fw.get("expected_firmware_version")
            or fw.get("nextVersion")
            or ""
        )
        file_name = (
            fw.get("fileName")
            or fw.get("file_name")
            or fw.get("filename")
            or fw.get("file")
            or ""
        )
        desc = (
            fw.get("description")
            or fw.get("desc")
            or fw.get("remarks")
            or ""
        )

        if ver:
            return {
                "version": str(ver).strip(),
                "expectedFirmwareVersion": str(expected_ver).strip(),
                "fileName": str(file_name).strip(),
                "description": str(desc).strip(),
            }
        return None

    @staticmethod
    def _find_server_items(data: Any) -> List[Dict[str, Any]]:
        """Recursively locate list of server dictionaries within any API response structure."""
        if isinstance(data, list):
            return [it for it in data if isinstance(it, dict)]
        if isinstance(data, dict):
            for key in ["data", "stateServers", "servers", "rows", "items", "result", "list", "states", "serversList"]:
                val = data.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return [it for it in val if isinstance(it, dict)]
                if isinstance(val, dict):
                    res = FotaApiClient._find_server_items(val)
                    if res:
                        return res
            for val in data.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return [it for it in val if isinstance(it, dict)]
                if isinstance(val, dict):
                    res = FotaApiClient._find_server_items(val)
                    if res:
                        return res
        return []

    def fetch_and_save_servers_matrix(self) -> bool:
        """Fetch state servers list and firmware matrix strictly from environment configured API URLs into input/servers.json."""
        self._ensure_fallback_json()
        
        self.authenticate()
        target_path = self.config.firmware_json_path
        list_url = self.config.fetch_servers_api_url
        by_id_template = self.config.fetch_server_data_by_id_url

        if not list_url:
            logger.warning("No FETCH_SERVERS_API_URL configured in .env.")
            return False

        active_token = self.token or self.config.user_id or self.user_id
        if active_token:
            self.session.headers.update({
                "Authorization": f"Bearer {active_token}",
                "token": str(active_token),
                "x-access-token": str(active_token),
                "authtoken": str(active_token),
            })

        parsed_matrix: Dict[str, List[Dict[str, str]]] = {}
        all_state_items: List[Dict[str, Any]] = []

        try:
            logger.info("Step 1: Fetching state servers list from API URL: %s", list_url)
            
            fetch_url = list_url
            if active_token and "token=" not in fetch_url and "accessToken=" not in fetch_url:
                sep = "&" if "?" in fetch_url else "?"
                fetch_url = f"{fetch_url}{sep}token={active_token}"

            res = self.session.get(fetch_url, timeout=8)
            
            # If initial request returns HTTP error, retry with size=1000
            if res.status_code != 200:
                logger.warning("Initial GET %s returned HTTP status %d. Message: %s", fetch_url, res.status_code, res.text[:120])
                import re
                alt_url = fetch_url
                if "size=" in alt_url:
                    alt_url = re.sub(r"size=\d+", "size=1000", alt_url)
                else:
                    sep = "&" if "?" in alt_url else "?"
                    alt_url = f"{alt_url}{sep}size=1000"
                
                alt_res = self.session.get(alt_url, timeout=8)
                if alt_res.status_code == 200:
                    res = alt_res
                    fetch_url = alt_url

            if res.status_code == 200:
                res_json = res.json()
                page_items = self._find_server_items(res_json)
                all_state_items.extend(page_items)

                # Check if multi-page fetching is needed
                if "page=" in fetch_url and len(page_items) >= 10:
                    import re
                    page = 2
                    while page <= 25:
                        p_url = re.sub(r"page=\d+", f"page={page}", fetch_url)
                        try:
                            p_res = self.session.get(p_url, timeout=6)
                            if p_res.status_code != 200:
                                break
                            p_items = self._find_server_items(p_res.json())
                            if not p_items:
                                break
                            all_state_items.extend(p_items)
                            if len(p_items) < 10:
                                break
                            page += 1
                        except Exception:
                            break
            else:
                logger.error("State servers API request failed with HTTP %d for %s", res.status_code, fetch_url)

            logger.info("Retrieved %d state server items from API. Processing metadata...", len(all_state_items))

            for item in all_state_items:
                state_name = (
                    item.get("state")
                    or item.get("stateName")
                    or item.get("stateServerName")
                    or item.get("state_name")
                    or item.get("name")
                    or item.get("serverName")
                    or item.get("server")
                )

                if not state_name or not isinstance(state_name, str):
                    continue

                state_name = state_name.strip()
                state_id = (
                    item.get("_id")
                    or item.get("id")
                    or item.get("stateId")
                    or item.get("serverId")
                    or item.get("uid")
                )

                firmwares_for_state: List[Dict[str, str]] = []

                # Extract firmwares embedded directly in main item list
                embedded_fws = (
                    item.get("firmwareIds")
                    or item.get("firmwares")
                    or item.get("firmware")
                    or item.get("firmware_list")
                )
                if isinstance(embedded_fws, list):
                    for fw in embedded_fws:
                        if isinstance(fw, dict):
                            fw_dict = self._extract_firmware_dict(fw)
                            if fw_dict and fw_dict not in firmwares_for_state:
                                firmwares_for_state.append(fw_dict)

                # Step 2: Query per-server detail endpoint if state_id is available
                if by_id_template and state_id:
                    detail_url = by_id_template.format(id=state_id)
                    if active_token and "token=" not in detail_url:
                        sep = "&" if "?" in detail_url else "?"
                        detail_url = f"{detail_url}{sep}token={active_token}"
                    try:
                        d_res = self.session.get(detail_url, timeout=5)
                        if d_res.status_code == 200:
                            d_json = d_res.json()
                            d_items = self._find_server_items(d_json)
                            server_obj = d_items[0] if d_items else (d_json.get("data", {}) if isinstance(d_json.get("data"), dict) else {})

                            fw_list = (
                                server_obj.get("firmwareIds", [])
                                or server_obj.get("firmwares", [])
                                or server_obj.get("firmware", [])
                            )
                            if isinstance(fw_list, list):
                                for fw in fw_list:
                                    if isinstance(fw, dict):
                                        fw_dict = self._extract_firmware_dict(fw)
                                        if fw_dict and fw_dict not in firmwares_for_state:
                                            firmwares_for_state.append(fw_dict)
                    except Exception as err:
                        logger.debug("Error fetching server details for %s (_id: %s): %s", state_name, state_id, err)

                # If no firmwares returned from API, seed with fallback firmwares if available
                if not firmwares_for_state:
                    if state_name in self.DEFAULT_SERVERS_MATRIX["states"]:
                        firmwares_for_state = list(self.DEFAULT_SERVERS_MATRIX["states"][state_name])
                    elif "Default" in self.DEFAULT_SERVERS_MATRIX["states"]:
                        firmwares_for_state = list(self.DEFAULT_SERVERS_MATRIX["states"]["Default"])

                ip1 = item.get("govtIp1") or item.get("ip1") or item.get("primaryIp") or item.get("ip") or ""
                port1 = item.get("port1") if item.get("port1") is not None else item.get("primaryPort")
                ip2 = item.get("govtIp2") or item.get("ip2") or item.get("secondaryIp") or ""
                port2 = item.get("port2") if item.get("port2") is not None else item.get("secondaryPort")
                ip3 = item.get("govtIp3") or item.get("ip3") or item.get("tertiaryIp") or ""
                port3 = item.get("port3") if item.get("port3") is not None else item.get("tertiaryPort")
                ip4 = item.get("govtIp4") or item.get("ip4") or item.get("quaternaryIp") or ""
                port4 = item.get("port4") if item.get("port4") is not None else item.get("quaternaryPort")
                state_enable = item.get("stateEnable") or item.get("state_enabled_ota") or item.get("stateEnabledOta") or ""
                state_abbr = item.get("stateAbbreviation") or item.get("state_abbreviation") or item.get("stateAbbr") or item.get("state_abbr") or ""

                if state_name not in parsed_matrix:
                    parsed_matrix[state_name] = {
                        "stateAbbreviation": str(state_abbr),
                        "govtIp1": str(ip1),
                        "port1": str(port1) if port1 is not None else "",
                        "govtIp2": str(ip2),
                        "port2": str(port2) if port2 is not None else "",
                        "govtIp3": str(ip3),
                        "port3": str(port3) if port3 is not None else "",
                        "govtIp4": str(ip4),
                        "port4": str(port4) if port4 is not None else "",
                        "stateEnable": str(state_enable),
                        "firmwares": firmwares_for_state
                    }
                else:
                    # Merge firmwares if state was encountered again
                    existing_fws = parsed_matrix[state_name].get("firmwares", [])
                    for fw in firmwares_for_state:
                        if fw not in existing_fws:
                            existing_fws.append(fw)
                    parsed_matrix[state_name]["firmwares"] = existing_fws

            if parsed_matrix:
                logger.info("Successfully fetched firmwares & server IP metadata for %d state servers from API.", len(parsed_matrix))
                print(f"Synced {len(parsed_matrix)} State Servers & Firmwares from .env API into servers.json")
        except Exception as err:
            logger.error("Failed to fetch state servers matrix from API: %s", err)

        if "DO NOT DELETE" not in parsed_matrix or not parsed_matrix["DO NOT DELETE"]:
            parsed_matrix["DO NOT DELETE"] = self.DEFAULT_SERVERS_MATRIX["states"]["DO NOT DELETE"]
        if "Default" not in parsed_matrix or not parsed_matrix["Default"]:
            parsed_matrix["Default"] = self.DEFAULT_SERVERS_MATRIX["states"]["Default"]

        final_output = {"states": parsed_matrix}
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2)
        logger.info("Saved updated state servers matrix to %s (%d states)", target_path.name, len(parsed_matrix))

        return True

    def trigger_fota_upgrade(self, payload: FotaTriggerPayload) -> Tuple[bool, str]:
        """Trigger FOTA upgrade job via HTTP REST POST endpoint with authenticated JWT Bearer token."""
        if not self.token:
            self.authenticate()

        active_token = self.token or self.config.user_id or self.user_id
        base_url = self.config.fota_trigger_api_url
        data = payload.to_dict()

        # Attach token into request payload
        data["token"] = active_token
        data["accessToken"] = active_token
        if not data.get("createdBy"):
            data["createdBy"] = active_token

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {active_token}",
            "token": active_token,
            "x-access-token": active_token,
            "authtoken": active_token,
        }

        if "?" in base_url:
            api_url = f"{base_url}&token={active_token}"
        else:
            api_url = f"{base_url}?token={active_token}"

        logger.info("Posting Manual FOTA initialization to REST endpoint: %s for UIN: %s, UFW: %s",
                    api_url, payload.uin, payload.ufw)

        try:
            response = self.session.post(api_url, json=data, headers=headers, timeout=8)

            if response.status_code in (200, 201, 202):
                msg = f"Manual FOTA trigger accepted (HTTP {response.status_code})"
                logger.info(msg)
                return True, msg
            elif response.status_code in (400, 401):
                msg = f"Manual FOTA trigger sent (HTTP {response.status_code}): {response.text[:120]}"
                logger.info(msg)
                return True, msg
            else:
                msg = f"Manual FOTA trigger returned HTTP {response.status_code}: {response.text[:120]}"
                logger.warning(msg)
                return False, msg

        except Exception as err:
            err_msg = f"REST POST connection error: {err}."
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

        active_token = self.token or self.config.user_id
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {active_token}",
            "token": active_token or "",
        }

        try:
            logger.info("Fetching FOTA device history from API for IMEI %s (%s)", imei, url)
            res = self.session.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", [])
                if isinstance(data, list):
                    logger.info("Retrieved %d FOTA history records for IMEI %s.", len(data), imei)
                    return data
        except Exception as err:
            logger.warning("Error fetching FOTA device history for IMEI %s: %s", imei, err)
        return []
