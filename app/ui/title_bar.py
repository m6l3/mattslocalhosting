from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.widgets.buttons import IconButton
from app.widgets.status import StatusDot


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("titleBar")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("LocalHost")
        title.setObjectName("windowTitle")
        layout.addWidget(title)

        self.status_dot = StatusDot("#6e6e6e", 6)
        layout.addWidget(self.status_dot)
        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("muted")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.min_button = IconButton("minimize", "Minimize")
        self.max_button = IconButton("square", "Maximize")
        self.close_button = IconButton("close", "Close", "chromeDanger")
        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

        self.min_button.clicked.connect(self.minimize_requested)
        self.max_button.clicked.connect(self.maximize_requested)
        self.close_button.clicked.connect(self.close_requested)

    def set_status(self, text: str, color: str, strong: bool = False) -> None:
        self.status_dot.set_color(color)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {'#ededed' if strong else '#a1a1a1'};")

    def is_control_at(self, global_pos) -> bool:
        widget = self.childAt(self.mapFromGlobal(global_pos))
        return widget in {self.min_button, self.max_button, self.close_button}

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)

