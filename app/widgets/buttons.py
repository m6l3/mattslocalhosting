from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton

from app.widgets.icons import app_icon


class AppButton(QPushButton):
    def __init__(self, text: str, icon: str | None = None, variant: str = "secondary") -> None:
        super().__init__(text)
        self.setProperty("variant", variant)
        self.setCursor(QtCursor.pointing_hand())
        self.setMinimumHeight(32)
        if icon:
            color = {
                "primary": "#0a0a0a",
                "danger": "#f87171",
                "ghost": "#a1a1a1",
            }.get(variant, "#ededed")
            self.setIcon(app_icon(icon, color))
            self.setIconSize(QSize(15, 15))


class IconButton(QPushButton):
    def __init__(self, icon: str, tooltip: str, variant: str = "chrome") -> None:
        super().__init__()
        self.setProperty("variant", variant)
        self.setCursor(QtCursor.pointing_hand())
        self.setIcon(app_icon(icon, "#ededed" if variant == "chromeDanger" else "#a1a1a1"))
        self.setIconSize(QSize(13, 13))
        self.setToolTip(tooltip)
        self.setFixedSize(28 if variant == "inline" else 42, 28 if variant == "inline" else 34)


class QtCursor:
    @staticmethod
    def pointing_hand():
        from PySide6.QtCore import Qt

        return Qt.CursorShape.PointingHandCursor
