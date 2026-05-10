from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from app.pages.base import Page, divider
from app.widgets.buttons import AppButton

CREATOR_NAME = "s0m3thing_matters"
DISCORD_URL = "https://discord.gg/H3K2xeU96A"


class SupportPage(Page):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.add_header("Support", "Contact, credits, and community links.")

        content = QVBoxLayout()
        content.setSpacing(14)

        creator_title = QLabel("Creator")
        creator_title.setObjectName("sectionTitle")
        content.addWidget(creator_title)

        creator = QLabel(CREATOR_NAME)
        creator.setObjectName("supportName")
        content.addWidget(creator)

        content.addWidget(divider())

        discord_title = QLabel("Discord")
        discord_title.setObjectName("sectionTitle")
        content.addWidget(discord_title)

        discord_link = QLabel(DISCORD_URL)
        discord_link.setObjectName("supportLink")
        discord_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(discord_link)

        actions = QHBoxLayout()
        open_discord = AppButton("Open Discord", "globe", "primary")
        open_discord.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)))
        actions.addWidget(open_discord)
        actions.addStretch()
        content.addLayout(actions)
        content.addStretch()

        self.root.addLayout(content, 1)
