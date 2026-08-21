"""Device Session Log File Manager Module.

Handles dynamic filename generation ({IMEI}_{REL_FETCHED}_TO_{REL_UPDATE}.log),
dual continuous stream writing (terminal_session.log + dedicated session log),
and prepends high-precision millisecond timestamps:
Format: [2026-08-21 15:10:27.861] <raw_line>
"""

import os
import re
import datetime
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


def sanitize_filename_part(part: Optional[str]) -> str:
    """Sanitize string for Windows filename safety."""
    if not part:
        return ""
    clean = re.sub(r'[\\/*?:"<>|]', "_", str(part).strip()).replace(" ", "_")
    return clean if clean not in ("UNKNOWN", "PENDING", "Latest", "---") else ""


class SessionLogger:
    """Manages dedicated per-device session log files and master terminal_session.log with millisecond timestamps."""

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.imei: Optional[str] = None
        self.rel_fetched: Optional[str] = None
        self.rel_update: Optional[str] = None

        self.master_log_path: Path = self.logs_dir / "terminal_session.log"
        self.device_log_path: Optional[Path] = None

    def reset_session(self) -> None:
        """Reset session metadata for a new device connection cycle."""
        self.imei = None
        self.rel_fetched = None
        self.rel_update = None
        self.device_log_path = None

    def update_session_info(self, imei: Optional[str], rel_fetched: Optional[str], rel_update: Optional[str] = None) -> None:
        """Update telemetry parameters and set active dedicated device log file path."""
        c_imei = sanitize_filename_part(imei)
        c_fetched = sanitize_filename_part(rel_fetched)
        c_update = sanitize_filename_part(rel_update)

        if c_imei:
            self.imei = c_imei
        if c_fetched:
            self.rel_fetched = c_fetched
        if c_update:
            self.rel_update = c_update

        # Determine target filename based on available telemetry
        if self.imei and self.rel_fetched and self.rel_update:
            target_fname = f"{self.imei}_{self.rel_fetched}_TO_{self.rel_update}.log"
        elif self.imei and self.rel_fetched:
            target_fname = f"{self.imei}_{self.rel_fetched}.log"
        else:
            target_fname = None

        if target_fname:
            new_path = self.logs_dir / target_fname
            if new_path != self.device_log_path:
                old_path = self.device_log_path
                if old_path and old_path.exists() and old_path != new_path:
                    try:
                        with open(old_path, "r", encoding="utf-8") as src, open(new_path, "a", encoding="utf-8") as dst:
                            dst.write(src.read())
                        old_path.unlink(missing_ok=True)
                    except Exception as err:
                        logger.warning("Failed migrating old device log file %s: %s", old_path.name, err)

                self.device_log_path = new_path
                logger.info("Updated active device log file path: %s", self.device_log_path.name)

    def write_lines(self, lines: List[str]) -> None:
        """Write batch of raw serial lines to terminal_session.log AND dedicated device log file with millisecond timestamps [YYYY-MM-DD HH:MM:SS.fff]."""
        if not lines:
            return

        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"

        formatted_chunk = "".join(f"[{timestamp_str}] {line}\n" for line in lines if line)
        if not formatted_chunk:
            return

        # 1. ALWAYS write to master terminal_session.log (never stops logging!)
        try:
            with open(self.master_log_path, "a", encoding="utf-8") as f:
                f.write(formatted_chunk)
        except Exception as err:
            logger.debug("Error writing to master terminal log %s: %s", self.master_log_path, err)

        # 2. ALSO write to dedicated device log file if telemetry is available!
        if self.device_log_path:
            try:
                with open(self.device_log_path, "a", encoding="utf-8") as f:
                    f.write(formatted_chunk)
            except Exception as err:
                logger.debug("Error writing to device log %s: %s", self.device_log_path, err)
