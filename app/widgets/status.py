from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel


class StatusDot(QLabel):
    def __init__(self, color: str = "#6e6e6e", size: int = 8) -> None:
        super().__init__()
        self._size = size
        self.setFixedSize(QSize(size, size))
        self.set_color(color)

    def set_color(self, color: str) -> None:
        radius = self._size // 2
        self.setStyleSheet(
            f"background: {color}; border-radius: {radius}px; min-width: {self._size}px; min-height: {self._size}px;"
        )

