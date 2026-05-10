from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QFrame

from app.widgets.status import StatusDot


class Toast(QFrame):
    COLORS = {
        "info": "#ededed",
        "success": "#4ade80",
        "warning": "#eab308",
        "error": "#f87171",
    }

    def __init__(self, text: str, tone: str = "info", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 14, 8)
        layout.setSpacing(8)
        layout.addWidget(StatusDot(self.COLORS.get(tone, self.COLORS["info"]), 7))
        label = QLabel(text)
        label.setObjectName("toastLabel")
        layout.addWidget(label)

        self._dismiss_started = False

    def show_animated(self, duration: int = 2800) -> None:
        self.show()
        QTimer.singleShot(duration, self.dismiss)

    def dismiss(self) -> None:
        if self._dismiss_started:
            return
        self._dismiss_started = True
        self.hide()
        self.deleteLater()
