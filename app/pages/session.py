from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QStackedLayout, QVBoxLayout, QWidget

from app.pages.base import InfoRows, Page
from app.widgets.buttons import AppButton
from app.widgets.log_console import LogConsole
from app.widgets.status import StatusDot


class SessionPage(Page):
    def __init__(
        self,
        window,
        title: str,
        subtitle: str,
        info_pairs: list[tuple[str, str]],
        stop_callback=None,
    ) -> None:
        super().__init__()
        self.window = window
        self.stop_callback = stop_callback or window.stop_everything
        self.info_rows: InfoRows | None = None
        self.local_join_button: AppButton | None = None
        self.loading_visible = False

        status = QHBoxLayout()
        status.setSpacing(8)
        self.status_dot = StatusDot("#6e6e6e", 8)
        self.status_label = QLabel("Initializing")
        self.status_label.setObjectName("pageSubtitle")
        status.addWidget(self.status_dot)
        status.addWidget(self.status_label)
        self.add_header(title, subtitle, status)

        self.content_stack = QStackedLayout()
        self.content_stack.setContentsMargins(0, 0, 0, 0)
        self.content_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self.loader_page = QWidget()
        loader = QVBoxLayout(self.loader_page)
        loader.setContentsMargins(0, 0, 0, 0)
        loader.setSpacing(14)
        loader.addStretch()
        self.loader_title = QLabel("Setting up")
        self.loader_title.setObjectName("loaderTitle")
        self.loader_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loader_status = QLabel("Preparing")
        self.loader_status.setObjectName("loaderStatus")
        self.loader_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loader_progress = QProgressBar()
        self.loader_progress.setObjectName("loaderProgress")
        self.loader_progress.setRange(0, 100)
        self.loader_progress.setValue(0)
        self.loader_progress.setTextVisible(False)
        loader.addWidget(self.loader_title)
        loader.addWidget(self.loader_status)
        loader.addWidget(self.loader_progress, 0, Qt.AlignmentFlag.AlignCenter)
        loader.addStretch()
        loader_actions = QHBoxLayout()
        loader_actions.addStretch()
        loader_stop = AppButton("Stop session", "stop", "danger")
        loader_stop.clicked.connect(self.stop_callback)
        loader_actions.addWidget(loader_stop)
        loader.addLayout(loader_actions)

        self.session_view = QWidget()
        session_root = QVBoxLayout(self.session_view)
        session_root.setContentsMargins(0, 0, 0, 0)
        session_root.setSpacing(18)

        body = QGridLayout()
        body.setHorizontalSpacing(28)
        body.setColumnMinimumWidth(0, 260)
        body.setColumnStretch(0, 0)
        body.setColumnStretch(1, 1)

        left = QVBoxLayout()
        self.info_rows = InfoRows(info_pairs)
        left.addWidget(self.info_rows)

        self.progress_panel = QWidget()
        progress_layout = QVBoxLayout(self.progress_panel)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(6)
        progress_label = QLabel("Setup")
        progress_label.setObjectName("sectionTitle")
        self.progress_status = QLabel("Waiting")
        self.progress_status.setObjectName("fieldHint")
        self.progress = QProgressBar()
        self.progress.setObjectName("sessionProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_status)
        progress_layout.addWidget(self.progress)
        self.progress_panel.setVisible(False)
        left.addWidget(self.progress_panel)

        self.post_actions = QVBoxLayout()
        self.post_actions.setSpacing(8)
        left.addLayout(self.post_actions)
        left.addStretch()

        self.console_area = QWidget()
        right = QVBoxLayout(self.console_area)
        right.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        console_label = QLabel("Console")
        console_label.setObjectName("sectionTitle")
        header.addWidget(console_label)
        header.addStretch()
        header.addWidget(StatusDot("#4ade80", 6))
        streaming = QLabel("Streaming")
        streaming.setObjectName("fieldHint")
        header.addWidget(streaming)
        right.addLayout(header)
        self.console = LogConsole()
        right.addWidget(self.console, 1)

        body.addLayout(left, 0, 0)
        body.addWidget(self.console_area, 0, 1)
        session_root.addLayout(body, 1)

        actions = QHBoxLayout()
        back = AppButton("Back", "back", "ghost")
        stop = AppButton("Stop session", "stop", "danger")
        back.clicked.connect(lambda: window.navigate("overview"))
        stop.clicked.connect(self.stop_callback)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(stop)
        session_root.addLayout(actions)

        self.content_stack.addWidget(self.loader_page)
        self.content_stack.addWidget(self.session_view)
        self.content_stack.setCurrentWidget(self.session_view)
        self.root.addLayout(self.content_stack, 1)

    def append_log(self, message: str, level: str = "info") -> None:
        self.console.append_log(message, level)

    def set_status(self, text: str, tone: str) -> None:
        colors = {"ok": "#4ade80", "info": "#6e6e6e", "warn": "#eab308", "err": "#f87171"}
        self.status_dot.set_color(colors.get(tone, "#6e6e6e"))
        self.status_label.setText(text)

    def set_info(self, key: str, value: str, color: str | None = None) -> None:
        if self.info_rows:
            self.info_rows.set_value(key, value, color)

    def set_progress(self, value: int, text: str) -> None:
        safe_value = max(0, min(100, value))
        self.progress.setValue(safe_value)
        self.loader_progress.setValue(safe_value)
        self.progress_status.setText(text)
        self.loader_status.setText(text)

    def set_console_visible(self, visible: bool) -> None:
        self.console_area.setVisible(visible)

    def set_loading_visible(self, visible: bool) -> None:
        self.loading_visible = visible
        self.content_stack.setCurrentWidget(self.loader_page if visible else self.session_view)
        self.progress_panel.setVisible(False)

    def add_local_join(self, callback) -> None:
        if self.local_join_button:
            return
        self.local_join_button = AppButton("Join local server", "play", "primary")
        self.local_join_button.clicked.connect(callback)
        self.post_actions.addWidget(self.local_join_button)

    def add_copy_tunnel(self, callback) -> None:
        if self.info_rows:
            self.info_rows.add_inline_action("Tunnel", "copy", "Copy tunnel", callback)
