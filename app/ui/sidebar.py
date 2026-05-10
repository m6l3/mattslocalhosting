from __future__ import annotations

from PySide6.QtCore import Signal, QSize
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from app.widgets.icons import app_icon


class NavButton(QPushButton):
    def __init__(self, key: str, text: str, icon: str) -> None:
        super().__init__(text)
        self.key = key
        self.icon_name = icon
        self.default_text = text
        self.default_icon = icon
        self.setProperty("nav", True)
        self.setProperty("active", False)
        self.setIcon(app_icon(icon, "#a1a1a1"))
        self.setIconSize(QSize(15, 15))
        self.setMinimumHeight(32)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.setIcon(app_icon(self.icon_name, "#ededed" if active else "#a1a1a1"))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_content(self, text: str, icon: str) -> None:
        self.icon_name = icon
        self.setText(text)
        self.setIcon(app_icon(icon, "#ededed" if self.property("active") else "#a1a1a1"))

    def reset_content(self) -> None:
        self.set_content(self.default_text, self.default_icon)


class Sidebar(QFrame):
    navigate = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self._buttons: dict[str, NavButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 12)
        root.setSpacing(4)

        caption = QLabel("Workspace")
        caption.setObjectName("sidebarCaption")
        root.addWidget(caption)

        title = QLabel("LocalHost")
        title.setObjectName("windowTitle")
        root.addWidget(title)
        root.addSpacing(12)

        for key, label, icon in (
            ("overview", "Overview", "home"),
            ("create", "Create", "create"),
            ("join", "Join", "join"),
        ):
            self._add_nav(root, key, label, icon)

        divider = QFrame()
        divider.setObjectName("divider")
        root.addSpacing(12)
        root.addWidget(divider)
        root.addSpacing(8)
        self._add_nav(root, "settings", "Settings", "settings")
        self._add_nav(root, "support", "Support", "globe")

        root.addStretch()
        self.set_session(False)

    def _add_nav(self, layout: QVBoxLayout, key: str, label: str, icon: str) -> None:
        button = NavButton(key, label, icon)
        button.clicked.connect(lambda checked=False, k=key: self.navigate.emit(k))
        self._buttons[key] = button
        layout.addWidget(button)

    def set_current(self, key: str) -> None:
        for nav_key, button in self._buttons.items():
            button.set_active(nav_key == key)

    def set_session(
        self,
        active: bool,
        text: str = "No session",
        mode: str | None = None,
        active_modes: set[str] | None = None,
    ) -> None:
        self._buttons["create"].reset_content()
        self._buttons["join"].reset_content()
        modes = active_modes or ({mode} if mode else set())
        if active and "create" in modes:
            self._buttons["create"].set_content("Server", "play")
        if active and "join" in modes:
            self._buttons["join"].set_content("Connection", "join")
