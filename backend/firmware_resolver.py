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

    def get_state_firmware_objects(self, state_name: str) -> List[Dict[str, Any]]:
        """Retrieve full firmware metadata objects for a given state including expectedFirmwareVersion."""
        states = self.matrix.get("states", {})
        versions_raw = states.get(state_name) or states.get("Default") or []
        result = []
        for item in versions_raw:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append({"version": item, "expectedFirmwareVersion": "", "fileName": "", "description": ""})
        return result

    def get_state_versions(self, state_name: str) -> List[str]:
        """Retrieve ordered list of firmware versions for a given state."""
        states = self.matrix.get("states", {})
        versions_raw = states.get(state_name) or states.get("Default") or []
        
        versions = []
        for item in versions_raw:
            if isinstance(item, dict) and "version" in item:
                versions.append(str(item["version"]))
            elif isinstance(item, str):
                versions.append(item)
        return versions

    def validate_version_exists(self, state_name: str, version: str) -> bool:
        """Check whether current device firmware version exists in state configuration."""
        available = self.get_state_versions(state_name)
        if not version or not available:
            return False
        clean_v = str(version).strip()
        for v in available:
            if v == clean_v or v.startswith(clean_v) or clean_v.startswith(v):
                return True
        return False

    def resolve_next_version(self, state_name: str, current_version: str) -> Optional[str]:
        """Determine the next firmware version to upgrade to.

        STRICT VALIDATION BARRIER:
        Current version MUST exist in servers.json for state_name.
        If current_version is not listed in servers.json, return None (FOTA blocked).
        """
        objects = self.get_state_firmware_objects(state_name)
        versions = [str(obj.get("version", "")) for obj in objects if obj.get("version")]

        if not versions:
            logger.warning("No firmware versions configured in servers.json for state '%s'", state_name)
            return None

        clean_curr = str(current_version).strip()

        # 1. Exact Version Match
        if clean_curr in versions:
            idx = versions.index(clean_curr)
            exp = objects[idx].get("expectedFirmwareVersion")
            if exp and str(exp).strip():
                logger.info("Validated version '%s' in state '%s'. Target expected version: %s",
                            clean_curr, state_name, exp)
                return str(exp).strip()
            if idx + 1 < len(versions):
                next_ver = versions[idx + 1]
                logger.info("Validated version '%s' in state '%s'. Resolved next step version: %s",
                            clean_curr, state_name, next_ver)
                return str(next_ver).strip()
            logger.info("Device version '%s' is already at the latest firmware level for state '%s'.",
                        clean_curr, state_name)
            return None

        # 2. Fuzzy / Prefix Match
        for idx, obj in enumerate(objects):
            ver = str(obj.get("version", "")).strip()
            if ver and (ver == clean_curr or ver.startswith(clean_curr) or clean_curr.startswith(ver)):
                exp = obj.get("expectedFirmwareVersion")
                if exp and str(exp).strip():
                    return str(exp).strip()
                if idx + 1 < len(versions):
                    return str(versions[idx + 1]).strip()
                return None

        # 3. STRICT Barrier: Do NOT trigger FOTA if version is not in servers.json
        logger.warning("VALIDATION BARRIER: Current device version '%s' is NOT listed under state '%s' in servers.json. FOTA process blocked.",
                       clean_curr, state_name)
        return None
