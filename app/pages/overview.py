from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from app.core.config import PROXY_PORT
from app.pages.base import Metric, Page, divider
from app.widgets.buttons import AppButton
from app.widgets.status import StatusDot


class OverviewPage(Page):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        active = window.session_active()
        server_active = "create" in getattr(window, "active_modes", set())
        connection_active = "join" in getattr(window, "active_modes", set())
        actions = QHBoxLayout()
        actions.setSpacing(8)
        create_text = "Open server" if server_active else "New server"
        join_text = "Open connection" if connection_active else "Join"
        create = AppButton(create_text, "play" if server_active else "create", "primary")
        join = AppButton(join_text, "join", "secondary")
        create.clicked.connect(lambda: window.navigate("create"))
        join.clicked.connect(lambda: window.navigate("join"))
        actions.addWidget(create)
        actions.addWidget(join)
        self.add_header("Overview", "TeamTest launcher and tunnel proxy.", actions)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(24)
        metrics.setVerticalSpacing(12)
        if server_active and connection_active:
            session_value = "Server + Tunnel"
        elif server_active:
            session_value = "Server"
        elif connection_active:
            session_value = "Tunnel"
        else:
            session_value = "Idle"
        session_hint = "Open the active panel from the sidebar" if active else "No Studio process managed by LocalHost"
        metrics.addWidget(
            Metric(
                "Session",
                session_value,
                session_hint,
                "#4ade80" if active else "#6e6e6e",
            ),
            0,
            0,
        )
        studio_name = Path(window.studio_path).name if window.studio_path else "Missing"
        metrics.addWidget(
            Metric(
                "Studio",
                "Ready" if window.studio_path else "Missing",
                studio_name,
                "#ededed" if window.studio_path else "#eab308",
            ),
            0,
            1,
        )
        metrics.addWidget(Metric("Proxy", f"UDP {PROXY_PORT}", "127.0.0.1", "#ededed"), 0, 2)
        metrics.setColumnStretch(0, 1)
        metrics.setColumnStretch(1, 1)
        metrics.setColumnStretch(2, 1)
        self.root.addLayout(metrics)
        self.root.addWidget(divider())

        body = QGridLayout()
        body.setHorizontalSpacing(34)
        body.setColumnStretch(0, 2)
        body.setColumnStretch(1, 1)

        activity = QVBoxLayout()
        heading = QLabel("System")
        heading.setObjectName("sectionTitle")
        activity.addWidget(heading)
        rows = [
            ("#4ade80" if window.studio_path else "#eab308", "Studio configured" if window.studio_path else "Studio path required"),
            ("#6e6e6e", f"Proxy base port {PROXY_PORT}"),
            ("#4ade80" if active else "#6e6e6e", "Session is running" if active else "Ready to create or join"),
        ]
        for color, text in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(StatusDot(color, 6))
            label = QLabel(text)
            label.setObjectName("pageSubtitle")
            row.addWidget(label)
            row.addStretch()
            activity.addLayout(row)
        activity.addStretch()

        action_shell = QFrame()
        action_shell.setObjectName("overviewActions")
        quick = QVBoxLayout()
        quick.setContentsMargins(18, 0, 0, 0)
        quick.setSpacing(10)
        action_shell.setLayout(quick)
        quick_title = QLabel("Actions")
        quick_title.setObjectName("sectionTitle")
        quick.addWidget(quick_title)
        quick.addSpacing(4)
        quick_create = AppButton(create_text, "play" if server_active else "create", "secondary")
        quick_join = AppButton(join_text, "join", "secondary")
        quick_settings = AppButton("Configure", "settings", "ghost")
        quick_create.clicked.connect(lambda: window.navigate("create"))
        quick_join.clicked.connect(lambda: window.navigate("join"))
        quick_settings.clicked.connect(lambda: window.navigate("settings"))
        quick.addWidget(quick_create)
        quick.addWidget(quick_join)
        if active:
            quick_stop = AppButton("Stop all sessions", "stop", "danger")
            quick_stop.clicked.connect(window.stop_everything)
            quick.addWidget(quick_stop)
            quick.addSpacing(6)
        quick.addWidget(quick_settings)
        quick.addStretch()

        body.addLayout(activity, 0, 0)
        body.addWidget(action_shell, 0, 1)
        self.root.addLayout(body, 1)
