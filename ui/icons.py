"""Icon Utility Helper Module.

Provides get_icon(name) function to load Google Material Vector Icons (SVG)
from the assets/icons directory for PyQt6 UI components.
"""

import os
from typing import Dict
from PyQt6.QtGui import QIcon

_ICON_CACHE: Dict[str, QIcon] = {}
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ICONS_DIR = os.path.join(_BASE_DIR, "assets", "icons")


def get_icon(name: str) -> QIcon:
    """Retrieve QIcon for the given material icon name from assets/icons directory."""
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]

    icon_path = os.path.join(_ICONS_DIR, f"{name}.svg")
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
    else:
        # Fallback to base icon name if specific colored SVG file is missing
        base_name = name.split("_")[0]
        fallback_path = os.path.join(_ICONS_DIR, f"{base_name}.svg")
        if os.path.exists(fallback_path):
            icon = QIcon(fallback_path)
        else:
            icon = QIcon()

    _ICON_CACHE[name] = icon
    return icon
