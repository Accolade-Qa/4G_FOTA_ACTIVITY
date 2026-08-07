"""Continuous FOTA Utility Application Entry Point."""

import os
import sys
from pathlib import Path

# Ensure repo root directory is at the top of sys.path
REPO_ROOT = str(Path(__file__).resolve().parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ui.app import main

if __name__ == "__main__":
    main()
