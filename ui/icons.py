"""Icon Utility Helper Module.

Provides get_icon(name) function to load Google Material Vector Icons (SVG)
from the assets/icons directory for PyQt6 UI components.
"""

import os
from typing import Dict
from pathlib import Path
from PyQt6.QtGui import QIcon

from backend.path_resolver import get_asset_path

_ICON_CACHE: Dict[str, QIcon] = {}


def get_icons_dir() -> Path:
    return get_asset_path("assets/icons")


def get_icon(name: str) -> QIcon:
    """Retrieve QIcon for the given material icon name from assets/icons directory."""
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]

    icons_dir = get_icons_dir()
    icon_path = icons_dir / f"{name}.svg"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
    else:
        # Fallback to base icon name if specific colored SVG file is missing
        base_name = name.split("_")[0]
        fallback_path = icons_dir / f"{base_name}.svg"
        if fallback_path.exists():
            icon = QIcon(str(fallback_path))
        else:
            icon = QIcon()

    _ICON_CACHE[name] = icon
    return icon

