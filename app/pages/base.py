from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.widgets.buttons import IconButton


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    return line


class Page(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(32, 24, 32, 24)
        self.root.setSpacing(18)

    def add_header(self, title: str, subtitle: str = "", actions: QHBoxLayout | None = None) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        left.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("pageSubtitle")
            sub.setWordWrap(True)
            left.addWidget(sub)
        row.addLayout(left, 1)
        if actions:
            row.addLayout(actions)
        self.root.addLayout(row)
        self.root.addWidget(divider())


class Metric(QFrame):
    def __init__(self, label: str, value: str, hint: str, value_color: str = "#ededed") -> None:
        super().__init__()
        self.setObjectName("metric")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        label_w = QLabel(label)
        label_w.setObjectName("metricLabel")
        value_w = QLabel(value)
        value_w.setObjectName("metricValue")
        value_w.setStyleSheet(f"color: {value_color};")
        hint_w = QLabel(hint)
        hint_w.setObjectName("metricHint")
        hint_w.setWordWrap(True)
        layout.addWidget(label_w)
        layout.addWidget(value_w)
        layout.addWidget(hint_w)
        layout.addStretch()


class InfoRows(QWidget):
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self.labels: dict[str, QLabel] = {}
        self.row_layouts: dict[str, QVBoxLayout] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel("Session")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        for key, value in rows:
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(2)
            key_label = QLabel(key)
            key_label.setObjectName("metricLabel")
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setObjectName("pathLabel")
            value_label.setWordWrap(True)
            row.addWidget(key_label)
            row.addWidget(value_label)
            layout.addLayout(row)
            self.labels[key] = value_label
            self.row_layouts[key] = row
        layout.addStretch()

    def set_value(self, key: str, value: str, color: str | None = None) -> None:
        label = self.labels.get(key)
        if not label:
            return
        label.setText(value)
        if color:
            label.setStyleSheet(f"color: {color};")

    def add_inline_action(self, key: str, icon: str, tooltip: str, callback) -> None:
        label = self.labels.get(key)
        if not label:
            return
        row_layout = self.row_layouts.get(key)
        if not row_layout:
            return

        row_layout.removeWidget(label)
        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(6)
        value_row.addWidget(label, 1)
        button = IconButton(icon, tooltip, "inline")
        button.clicked.connect(callback)
        value_row.addWidget(button)
        row_layout.addLayout(value_row)
