from __future__ import annotations

import time

from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PySide6.QtWidgets import QTextEdit


class LogConsole(QTextEdit):
    COLORS = {
        "info": "#a1a1a1",
        "success": "#4ade80",
        "warning": "#eab308",
        "error": "#f87171",
        "ts": "#4a4a4a",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setObjectName("logConsole")
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFont("Cascadia Mono", 9))

    def append_log(self, message: str, level: str = "info") -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self._insert(f"[{time.strftime('%H:%M:%S')}] ", "ts")
        self._insert(f"{message}\n", level)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def _insert(self, text: str, level: str) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.COLORS.get(level, self.COLORS["info"])))
        cursor = self.textCursor()
        cursor.setCharFormat(fmt)
        cursor.insertText(text)

