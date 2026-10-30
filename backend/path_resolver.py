"""Path resolution utility for PyInstaller bundles.

This module provides a reliable way to get the application base directory,
whether running as a PyInstaller exe or from source.
"""

import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Get the application base directory for user data, logs, and results.
    
    When running as a PyInstaller bundle (.exe), returns the directory containing the exe.
    When running from source, returns the project root directory.
    
    Returns:
        Path: The base directory where the application should store runtime data.
    """
    # Check if running as PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller executable
        base_path = Path(sys.executable).parent
    else:
        # Running from source - use the project root
        base_path = Path(__file__).resolve().parent.parent
    
    return base_path


def get_asset_path(relative_path: str = "") -> Path:
    """
    Get the resolved path for bundled assets/resources.
    
    When running in PyInstaller bundle mode, checks sys._MEIPASS first.
    Falls back to executable directory, then source directory.
    
    Args:
        relative_path: Path relative to assets/project root.
        
    Returns:
        Path: The resolved absolute path.
    """
    rel_p = Path(relative_path)
    
    # 1. Check inside PyInstaller temporary bundle directory (sys._MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_path = Path(sys._MEIPASS) / rel_p
        if meipass_path.exists():
            return meipass_path

    # 2. Check directory containing executable (e.g. dist/)
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).parent / rel_p
        if exe_path.exists():
            return exe_path

    # 3. Check relative to project root (source mode)
    root_path = Path(__file__).resolve().parent.parent / rel_p
    return root_path

