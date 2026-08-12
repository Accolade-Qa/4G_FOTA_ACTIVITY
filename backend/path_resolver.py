"""Path resolution utility for PyInstaller bundles.

This module provides a reliable way to get the application base directory,
whether running as a PyInstaller exe or from source.
"""

import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Get the application base directory.
    
    When running as a PyInstaller bundle (.exe), returns the directory containing the exe.
    When running from source, returns the project root directory.
    
    Returns:
        Path: The base directory where the application should store data.
    """
    # Check if running as PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller executable
        # sys.executable points to the .exe file
        base_path = Path(sys.executable).parent
    else:
        # Running from source - use the project root
        # Walk up from this file to project root
        base_path = Path(__file__).resolve().parent.parent
    
    return base_path
