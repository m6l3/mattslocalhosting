from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

from app.core.config import ICONS_DIR

ICON_MAP = {
    "home": "house",
    "create": "plus",
    "join": "arrow-left-right",
    "settings": "settings",
    "play": "play",
    "stop": "square",
    "back": "arrow-left",
    "next": "arrow-right",
    "minimize": "minus",
    "close": "x",
    "folder": "folder",
    "copy": "copy",
    "refresh": "refresh-cw",
    "user": "user",
    "globe": "globe",
    "network": "network",
    "search": "search",
}


def icon_path(name: str) -> Path:
    filename = ICON_MAP.get(name, name)
    return ICONS_DIR / f"{filename}.svg"


def app_icon(name: str, color: str = "#a1a1a1", size: int = 20) -> QIcon:
    path = icon_path(name)
    if not path.exists():
        return QIcon()
    try:
        svg = path.read_text(encoding="utf-8").replace("currentColor", color)
        pixmap = QPixmap()
        if pixmap.loadFromData(svg.encode("utf-8"), "SVG"):
            return QIcon(pixmap.scaled(size, size))
    except Exception:
        pass
    return QIcon(str(path))


def icon_size(size: int = 16) -> QSize:
    return QSize(size, size)
