"""Configuration Management Module.

Loads runtime parameters from environment variables (.env file) with sensible default fallbacks.
Built following PEP 8 standards and explicit type hinting.
"""

import os
from pathlib import Path
from typing import Dict, Any

try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback inline loader if python-dotenv is not yet installed in local environment
    def load_dotenv(dotenv_path: Path) -> bool:
        if not dotenv_path.exists():
            return False
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        return True


class Config:
    """Central configuration store reading from .env and filesystem paths."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.cwd()
        self.env_path = self.base_dir / ".env"
        load_dotenv(self.env_path)

        # Paths
        self.input_dir = self.base_dir / "input"
        self.output_dir = self.base_dir / "output"
        self.results_dir = self.base_dir / "results"
        self.logs_dir = self.base_dir / "logs"

        self.firmware_json_path = self.input_dir / "servers.json"
        self.audit_csv_path = self.results_dir / "fota_audit.csv"
        self.login_json_path = self.results_dir / "login_packets.json"
        self._ensure_directories()

    @property
    def audit_log_path(self) -> Path:
        """Alias for audit_csv_path."""
        return self.audit_csv_path

    def _ensure_directories(self) -> None:
        """Ensure all required workspace output directories exist."""
        for d in [self.input_dir, self.output_dir, self.results_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def portal_url(self) -> str:
        return os.getenv("PORTAL_URL", "https://aepl-tcu4g-qa.accoladeelectronics.com/login")

    @property
    def portal_user(self) -> str:
        return os.getenv("PORTAL_USER", "suraj.bhalerao@accoladeelectronics.com")

    @property
    def portal_pass(self) -> str:
        return os.getenv("PORTAL_PASS", "6xwn8zg4")

    @property
    def serial_port(self) -> str:
        return os.getenv("SERIAL_PORT", "")

    @property
    def serial_baud(self) -> int:
        val = os.getenv("SERIAL_BAUD", "115200")
        try:
            return int(val)
        except ValueError:
            return 115200

    @property
    def default_state(self) -> str:
        return os.getenv("DEFAULT_STATE", "Bihar")

    @property
    def fetch_servers_api_url(self) -> str:
        return os.getenv(
            "FETCH_SERVERS_API_URL",
            "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerData?page=1&size=50&search="
        )

    @property
    def fetch_server_data_by_id_url(self) -> str:
        return os.getenv(
            "FETCH_SERVER_DATA_BY_ID",
            "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerDataByUId?id={id}"
        )

    @property
    def user_id(self) -> str:
        return os.getenv("USER_ID", "64116e41c56760941baea6ac")

    @property
    def fota_trigger_api_url(self) -> str:
        return os.getenv(
            "FOTA_TRIGGER_API_URL",
            "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/fota/createManualFota"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export current settings as dictionary for UI display."""
        return {
            "portal_url": self.portal_url,
            "portal_user": self.portal_user,
            "serial_port": self.serial_port,
            "serial_baud": self.serial_baud,
            "default_state": self.default_state,
        }
