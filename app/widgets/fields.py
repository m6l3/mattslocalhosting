from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.widgets.icons import app_icon

Validator = Callable[[str], str | None]


class FormField(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "",
        hint: str = "",
        placeholder: str = "",
        icon: str | None = None,
        validator: Validator | None = None,
    ) -> None:
        super().__init__()
        self.validator = validator
        self.setObjectName("formField")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.label.setObjectName("fieldLabel")
        self.error = QLabel("")
        self.error.setObjectName("fieldError")
        head.addWidget(self.label)
        head.addStretch()
        head.addWidget(self.error)
        root.addLayout(head)

        self.input_shell = QFrame()
        self.input_shell.setObjectName("inputShell")
        input_layout = QHBoxLayout(self.input_shell)
        input_layout.setContentsMargins(12, 0, 12, 0)
        input_layout.setSpacing(9)

        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(app_icon(icon, "#6e6e6e").pixmap(15, 15))
            icon_label.setObjectName("fieldIcon")
            input_layout.addWidget(icon_label)

        self.edit = QLineEdit()
        self.edit.setText(value)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setObjectName("lineEdit")
        self.edit.textChanged.connect(lambda _: self.validate())
        input_layout.addWidget(self.edit)
        root.addWidget(self.input_shell)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("fieldHint")
            hint_label.setWordWrap(True)
            root.addWidget(hint_label)

    def value(self) -> str:
        return self.edit.text().strip()

    def validate(self) -> bool:
        if not self.validator:
            self._set_error("")
            return True
        value = self.value()
        if not value:
            self._set_error("")
            return True
        error = self.validator(value)
        self._set_error(error or "")
        return error is None

    def _set_error(self, text: str) -> None:
        self.error.setText(text)
        self.input_shell.setProperty("error", bool(text))
        self.input_shell.style().unpolish(self.input_shell)
        self.input_shell.style().polish(self.input_shell)


class ReadOnlyPath(QFrame):
    def __init__(self, path: str, icon: str = "folder") -> None:
        super().__init__()
        self.setObjectName("inputShell")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(9)

        icon_label = QLabel()
        icon_label.setPixmap(app_icon(icon, "#6e6e6e").pixmap(15, 15))
        layout.addWidget(icon_label)

        label = QLabel(path or "Not configured")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("pathLabel")
        layout.addWidget(label, 1)
