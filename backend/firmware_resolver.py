"""Firmware Matrix & Version Resolver Module.

Evaluates state-specific firmware lists in input/servers.json (synced from API)
and enforces strict version validation before resolving target upgrade versions.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class FirmwareResolver:
    """Evaluates firmware progression matrix per state with strict validation barrier."""

    DEFAULT_VERSIONS = ["1.0.0", "1.0.1", "1.0.2"]

    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path
        self.matrix: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> bool:
        """Reload firmware matrix from JSON file."""
        if not self.json_path.exists():
            logger.error("Firmware matrix JSON not found at %s", self.json_path)
            return False
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.matrix = json.load(f)
            logger.info("Loaded firmware matrix from %s with %d states",
                        self.json_path.name, len(self.matrix.get("states", {})))
            return True
        except Exception as err:
            logger.error("Failed to parse firmware JSON: %s", err)
            return False

    def is_version_listed(self, state_name: str, version: str) -> bool:
        """Check whether version exists in state configuration."""
        return self.validate_version_exists(state_name, version)

    def get_state_server_metadata(self, state_name: str) -> Dict[str, Any]:
        """Retrieve server IP, port, and state OTA metadata for a given state server."""
        states = self.matrix.get("states", {})
        state_entry = states.get(state_name) or states.get("Default") or {}
        if isinstance(state_entry, dict):
            return {
                "ip1": str(state_entry.get("govtIp1", "") or state_entry.get("ip1", "") or state_entry.get("primaryIp", "")),
                "port1": str(state_entry.get("port1", "") or state_entry.get("primaryPort", "")),
                "ip2": str(state_entry.get("govtIp2", "") or state_entry.get("ip2", "") or state_entry.get("secondaryIp", "")),
                "port2": str(state_entry.get("port2", "") or state_entry.get("secondaryPort", "")),
                "state_enable": str(state_entry.get("stateEnable", "") or state_entry.get("state_enabled_ota", "")),
            }
        return {"ip1": "", "port1": "", "ip2": "", "port2": "", "state_enable": ""}

    def _get_raw_versions_list(self, state_name: str) -> List[Any]:
        states = self.matrix.get("states", {})
        state_entry = states.get(state_name)
        if state_entry is None:
            state_entry = states.get("Default", [])
        if isinstance(state_entry, dict):
            return state_entry.get("firmwares", []) or state_entry.get("firmwareIds", []) or []
        if isinstance(state_entry, list):
            return state_entry
        return []

    def get_state_firmware_objects(self, state_name: str) -> List[Dict[str, Any]]:
        """Retrieve full firmware metadata objects for a given state including expectedFirmwareVersion."""
        versions_raw = self._get_raw_versions_list(state_name)
        result = []
        for item in versions_raw:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append({"version": item, "expectedFirmwareVersion": "", "fileName": "", "description": ""})
        return result

    def get_state_versions(self, state_name: str) -> List[str]:
        """Retrieve ordered list of firmware versions for a given state."""
        versions_raw = self._get_raw_versions_list(state_name)
        
        versions = []
        for item in versions_raw:
            if isinstance(item, dict) and "version" in item:
                versions.append(str(item["version"]))
            elif isinstance(item, str):
                versions.append(item)
        return versions

    def _object_matches_version(self, obj: Dict[str, Any], current_ver: str) -> bool:
        """Check if an object in servers.json matches current device version via fileName, description, expectedFirmwareVersion, or version."""
        clean_curr = str(current_ver).strip()
        if not clean_curr:
            return False

        file_name = str(obj.get("fileName", "")).strip()
        desc = str(obj.get("description", "")).strip()
        exp_ver = str(obj.get("expectedFirmwareVersion", "")).strip()
        ver = str(obj.get("version", "")).strip()

        # 1. Match fileName (e.g. '5.2.8_REL25' inside '5.2.8_REL25.bin' or 'ATCU_5.2.8_REL25.bin')
        if file_name and clean_curr in file_name:
            return True

        # 2. Match description (e.g. '5.2.8_REL25' == '5.2.8_REL25')
        if desc and (clean_curr == desc or clean_curr in desc or desc in clean_curr):
            return True

        # 3. Match expectedFirmwareVersion
        if exp_ver and (clean_curr == exp_ver or clean_curr in exp_ver or exp_ver in clean_curr):
            return True

        # 4. Match version field
        if ver and (clean_curr == ver or ver.startswith(clean_curr) or clean_curr.startswith(ver) or ver in clean_curr or clean_curr in ver):
            return True

        return False

    def validate_version_exists(self, state_name: str, version: str) -> bool:
        """Check whether current device firmware version exists in state configuration."""
        objects = self.get_state_firmware_objects(state_name)
        if not objects:
            return False
        if len(objects) == 1:
            return True
        if not version:
            return False
        for obj in objects:
            if self._object_matches_version(obj, version):
                return True
        return False

    def resolve_next_version(self, state_name: str, current_version: str) -> Optional[str]:
        """Determine the next firmware version to upgrade to.

        - Single Object Logic: If state JSON contains ONLY 1 object, start FOTA on that same version/expected target.
        - Multi-Object Logic: Match current_version against fileName / description / expectedFirmwareVersion / version
          of objects in servers.json, locate its index, and take the version of the NEXT object.
        """
        objects = self.get_state_firmware_objects(state_name)

        if not objects:
            logger.warning("No firmware versions configured in servers.json for state '%s'", state_name)
            return None

        # 1. Single Object Check: If state has only 1 object, start FOTA on that same version/expected target!
        if len(objects) == 1:
            obj = objects[0]
            v_ver = str(obj.get("version", "")).strip()
            v_exp = str(obj.get("expectedFirmwareVersion", "")).strip()
            clean_curr = str(current_version).strip()

            target = v_ver
            if clean_curr and v_ver and (clean_curr == v_ver or clean_curr.startswith(v_ver) or v_ver.startswith(clean_curr)):
                if v_exp and v_exp != v_ver:
                    target = v_exp

            if target:
                logger.info("Single object found in state '%s'. Starting FOTA on target version from json: %s", state_name, target)
                return target

        clean_curr = str(current_version).strip()

        # 2. Match current_version against objects by fileName / description / expectedFirmwareVersion / version
        matched_idx = -1
        for idx, obj in enumerate(objects):
            if self._object_matches_version(obj, clean_curr):
                matched_idx = idx
                logger.info("Matched device version '%s' against object index %d (fileName: '%s', desc: '%s', version: '%s') under state '%s'.",
                            clean_curr, idx, obj.get("fileName"), obj.get("description"), obj.get("version"), state_name)
                break

        if matched_idx != -1:
            if matched_idx + 1 < len(objects):
                next_obj = objects[matched_idx + 1]
                next_ver = str(next_obj.get("version", "")).strip()
                if not next_ver or next_ver in ("-", ""):
                    next_ver = str(next_obj.get("expectedFirmwareVersion", "")).strip()
                logger.info("Resolved next step target version from next object (index %d): %s", matched_idx + 1, next_ver)
                return next_ver
            else:
                logger.info("Device version '%s' (matched index %d) is at the last object for state '%s'. No further upgrade step.",
                            clean_curr, matched_idx, state_name)
                return None

        # 3. STRICT Barrier: Do NOT trigger FOTA if version is not in servers.json
        logger.warning("VALIDATION BARRIER: Current device version '%s' is NOT listed under state '%s' in servers.json. FOTA process blocked.",
                       clean_curr, state_name)
        return None

    def resolve_next_version_after_aborted(self, state_name: str, current_version: str, aborted_target_version: str) -> Optional[str]:
        """Resolve next step firmware version when previous attempt for aborted_target_version was aborted."""
        objects = self.get_state_firmware_objects(state_name)
        if not objects:
            return None
        if len(objects) == 1:
            return self.resolve_next_version(state_name, current_version)

        clean_aborted = str(aborted_target_version).strip()
        aborted_idx = -1

        for idx, obj in enumerate(objects):
            if self._object_matches_version(obj, clean_aborted):
                aborted_idx = idx
                break

        if aborted_idx != -1 and aborted_idx + 1 < len(objects):
            next_obj = objects[aborted_idx + 1]
            next_ver = str(next_obj.get("version", "")).strip() or str(next_obj.get("expectedFirmwareVersion", "")).strip()
            logger.info("Previous FOTA target '%s' (matched index %d) was aborted for state '%s'. Resolved next step version from json: %s",
                        clean_aborted, aborted_idx, state_name, next_ver)
            return next_ver
        return None
