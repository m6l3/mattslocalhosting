from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from app.pages.base import Page
from app.widgets.buttons import AppButton
from app.widgets.fields import FormField


def validate_tunnel(value: str) -> str | None:
    if ":" not in value:
        return "Format must be host:port"
    host, port = value.rsplit(":", 1)
    if not host:
        return "Missing host"
    if not port.isdigit():
        return "Port must be numeric"
    return None


class JoinPage(Page):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.add_header(
            "Join tunnel",
            "Open a UDP proxy locally and launch a Studio client through the tunnel address.",
        )

        form = QVBoxLayout()
        self.tunnel = FormField(
            "Tunnel address",
            window.settings.join_tunnel,
            "Format host:port, e.g. therefore-protocol.tunnel.gg:2842.",
            placeholder="therefore-protocol.tunnel.gg:2842",
            icon="globe",
            validator=validate_tunnel,
        )
        form.addWidget(self.tunnel)
        form.addStretch()
        self.root.addLayout(form, 1)

        actions = QHBoxLayout()
        back = AppButton("Back", "back", "ghost")
        join = AppButton("Join tunnel", "next", "primary")
        back.clicked.connect(lambda: window.navigate("overview"))
        join.clicked.connect(self._join)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(join)
        self.root.addLayout(actions)

    def _join(self) -> None:
        if not self.tunnel.validate() or not self.tunnel.value():
            self.window.toast("Fix the tunnel address.", "error")
            return
        host, port = self.tunnel.value().rsplit(":", 1)
        self.window.join_session(host, int(port), self.tunnel.value())

