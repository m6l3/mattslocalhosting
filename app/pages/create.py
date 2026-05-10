from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from app.core.config import ROOT_DIR
from app.pages.base import Page
from app.widgets.buttons import AppButton
from app.widgets.fields import FormField


class CreatePage(Page):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.add_header(
            "Create session",
            "Launch a local Studio server. Other clients can connect locally or through a tunnel.",
        )

        form = QVBoxLayout()
        form.setSpacing(16)
        self.user_id = FormField(
            "User ID",
            window.settings.user_id,
            "Creator ID used to authenticate the local session.",
            icon="user",
            validator=lambda v: None if v.isdigit() else "Must be numeric",
        )
        self.tunnel = FormField(
            "Tunnel address",
            window.settings.host_tunnel,
            "Optional. Format host:port, e.g. your.tunnel.gg:1234.",
            icon="globe",
        )
        self.port = FormField(
            "TeamTest port",
            window.settings.server_port,
            "Local port the Studio server will listen on.",
            icon="network",
            validator=lambda v: None if v.isdigit() and 1 <= int(v) <= 65535 else "Invalid port",
        )
        self.place_path = FormField(
            "Map file",
            window.settings.place_path,
            "Local .rbxl or .rbxlx file to load when creating the session.",
            icon="folder",
            validator=self._validate_place_path,
        )
        form.addWidget(self.user_id)
        form.addWidget(self.tunnel)
        form.addWidget(self.port)
        place_row = QHBoxLayout()
        place_row.setSpacing(10)
        browse = AppButton("Choose map", "folder", "secondary")
        browse.clicked.connect(self._browse_place)
        place_row.addWidget(self.place_path, 1)
        place_row.addWidget(browse)
        form.addLayout(place_row)
        form.addStretch()
        self.root.addLayout(form, 1)

        actions = QHBoxLayout()
        back = AppButton("Back", "back", "ghost")
        create = AppButton("Launch server", "play", "primary")
        back.clicked.connect(lambda: window.navigate("overview"))
        create.clicked.connect(self._create)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(create)
        self.root.addLayout(actions)

    def _create(self) -> None:
        valid = self.user_id.validate() and self.port.validate() and self.place_path.validate()
        if not self.user_id.value() or not self.port.value():
            self.window.toast("User ID and port are required.", "warning")
            return
        if not valid:
            self.window.toast("Fix the highlighted fields.", "error")
            return
        self.window.create_session(self.user_id.value(), self.tunnel.value(), self.port.value(), self.place_path.value())

    def _browse_place(self) -> None:
        current = Path(self.place_path.value()) if self.place_path.value() else ROOT_DIR
        if not current.is_absolute():
            current = ROOT_DIR / current
        condo_dir = ROOT_DIR.parent
        if current.is_file():
            start_dir = str(current.parent)
        elif condo_dir.is_dir():
            start_dir = str(condo_dir)
        else:
            start_dir = str(ROOT_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose map",
            start_dir,
            "Place (*.rbxl *.rbxlx);;All files (*.*)",
        )
        if path:
            self.place_path.edit.setText(path)
            self._create()

    def _validate_place_path(self, value: str) -> str | None:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT_DIR / path
        if not path.is_file():
            return "File not found"
        if path.suffix.lower() not in {".rbxl", ".rbxlx"}:
            return "Use .rbxl/.rbxlx"
        return None
