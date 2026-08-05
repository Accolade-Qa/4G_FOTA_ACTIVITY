"""Extension & Plugin Framework Module.

Provides hook listeners for custom user routines (e.g. AT command tests,
GPS/CAN bus diagnostic checks, MQTT ping, custom log exporters).
Keeps the architecture modular and open for custom expansion.
"""

import logging
from typing import Callable, List, Dict, Any
from fota_engine.models import LoginPacketInfo

logger = logging.getLogger(__name__)


class ExtensionHook:
    """Base plugin extension hook interface."""

    def on_login_packet_received(self, info: LoginPacketInfo) -> None:
        """Called when a new device login packet is captured."""
        pass

    def on_fota_started(self, uin: str, target_version: str) -> None:
        """Called before FOTA upgrade trigger is submitted."""
        pass

    def on_fota_completed(self, uin: str, final_version: str) -> None:
        """Called when device reaches 100% download and completes upgrade."""
        pass


class ExtensionManager:
    """Manages active plugin hooks and executes callbacks during FOTA lifecycle events."""

    def __init__(self) -> None:
        self.hooks: List[ExtensionHook] = []

    def register_hook(self, hook: ExtensionHook) -> None:
        """Register a custom user extension hook."""
        self.hooks.append(hook)
        logger.info("Registered custom extension hook: %s", hook.__class__.__name__)

    def trigger_login_packet(self, info: LoginPacketInfo) -> None:
        for h in self.hooks:
            try:
                h.on_login_packet_received(info)
            except Exception as err:
                logger.error("Error executing plugin hook %s: %s", h.__class__.__name__, err)

    def trigger_fota_started(self, uin: str, target_version: str) -> None:
        for h in self.hooks:
            try:
                h.on_fota_started(uin, target_version)
            except Exception as err:
                logger.error("Error executing plugin hook %s: %s", h.__class__.__name__, err)

    def trigger_fota_completed(self, uin: str, final_version: str) -> None:
        for h in self.hooks:
            try:
                h.on_fota_completed(uin, final_version)
            except Exception as err:
                logger.error("Error executing plugin hook %s: %s", h.__class__.__name__, err)
