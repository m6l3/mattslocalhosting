from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

STYLE_PATH = Path(__file__).with_name("dark.qss")


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE_PATH.read_text(encoding="utf-8"))

