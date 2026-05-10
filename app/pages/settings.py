from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout

from app.pages.base import Page
from app.widgets.buttons import AppButton
from app.widgets.fields import ReadOnlyPath


class SettingsPage(Page):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.add_header("Settings", "Configure the launcher.")

        form = QVBoxLayout()
        form.setSpacing(10)

        label = QLabel("Studio executable")
        label.setObjectName("fieldLabel")
        form.addWidget(label)
        form.addWidget(ReadOnlyPath(window.studio_path))

        file_name = Path(window.studio_path).name if window.studio_path else "Not selected"
        status = QLabel(f"Selected file: {file_name}")
        status.setObjectName("settingsStatusOk" if file_name == "RobloxStudioBeta.exe" else "settingsStatusWarn")
        form.addWidget(status)

        hint = QLabel(
            "Choose the Studio binary named RobloxStudioBeta.exe. "
            "It is usually inside AppData\\Local\\Roblox\\Versions\\version-*."
        )
        hint.setObjectName("fieldHint")
        hint.setWordWrap(True)
        form.addWidget(hint)

        path_actions = QHBoxLayout()
        detect = AppButton("Detect automatically", "refresh", "secondary")
        browse = AppButton("Choose file", "folder", "primary")
        clear = AppButton("Clear", "close", "ghost")
        detect.clicked.connect(window.auto_detect_studio)
        browse.clicked.connect(self._browse)
        path_actions.addWidget(browse)
        path_actions.addWidget(detect)
        path_actions.addWidget(clear)
        clear.clicked.connect(window.clear_studio_path)
        path_actions.addStretch()
        form.addLayout(path_actions)

        form.addStretch()
        self.root.addLayout(form, 1)

        actions = QHBoxLayout()
        back = AppButton("Back", "back", "ghost")
        back.clicked.connect(lambda: window.navigate("overview"))
        actions.addWidget(back)
        actions.addStretch()
        self.root.addLayout(actions)

    def _browse(self) -> None:
        start_dir = ""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        versions_dir = Path(local_appdata) / "Roblox" / "Versions" if local_appdata else None
        if versions_dir and versions_dir.is_dir():
            start_dir = str(versions_dir)

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose RobloxStudioBeta.exe",
            start_dir,
            "Studio executable (RobloxStudioBeta.exe);;Executable (*.exe)",
        )
        if path:
            self.window.set_studio_path(path)
