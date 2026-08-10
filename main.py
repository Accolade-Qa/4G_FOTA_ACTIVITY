"""Continuous FOTA Utility Application Entry Point."""

import os
import sys
import logging
from pathlib import Path

# Ensure repo root directory is at the top of sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Setup logging to write terminal logs to logs/fota_activity.log
logs_dir = REPO_ROOT / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
log_file = logs_dir / "fota_activity.log"

file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)

from ui.app import main

if __name__ == "__main__":
    main()
