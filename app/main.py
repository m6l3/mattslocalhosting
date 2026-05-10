from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.settings import SettingsStore
from app.core.studio import generate_guid, get_studio_path, launch_server
from app.styles.theme import apply_theme
from app.ui.splash import StartupSplash
from app.ui.window import MainWindow


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith((".rbxl", ".rbxlx")):
        settings = SettingsStore().load()
        studio = settings.studio_path if settings.studio_path else get_studio_path()
        parent_guid = generate_guid()
        play_guid = generate_guid()
        launch_server(
            studio,
            settings.server_port,
            settings.user_id,
            parent_guid,
            play_guid,
            sys.argv[1],
            startup_players=1,
            use_runtime_place=True,
        )
        return 0

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("LocalHost")
    qt_app.setOrganizationName("LocalHost")
    apply_theme(qt_app)

    state: dict[str, MainWindow | StartupSplash | None] = {"window": None, "splash": None}
    splash = StartupSplash()
    state["splash"] = splash

    def show_main() -> None:
        window = MainWindow()
        state["window"] = window
        window.show()
        splash.close()
        state["splash"] = None

    splash.finished.connect(show_main)
    splash.start()
    return qt_app.exec()
