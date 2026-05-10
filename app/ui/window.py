from __future__ import annotations

import ctypes
import os
from pathlib import Path
from ctypes import wintypes

import shiboken6
from PySide6.QtCore import QMetaObject, QPoint, Qt, QThread, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config import WINDOW_H, WINDOW_MIN_H, WINDOW_MIN_W, WINDOW_W
from app.core.proxy import proxy
from app.core.settings import AppSettings, SettingsStore
from app.core.studio import (
    get_studio_path,
    has_running_processes,
    launch_client,
    open_place_file,
    stop_all_roblox_processes,
    stop_roblox_processes,
)
from app.core.tasks import HostSessionWorker, JoinSessionWorker
from app.pages.create import CreatePage
from app.pages.join import JoinPage
from app.pages.overview import OverviewPage
from app.pages.session import SessionPage
from app.pages.settings import SettingsPage
from app.pages.support import SupportPage
from app.ui.sidebar import Sidebar
from app.ui.title_bar import TitleBar
from app.widgets.toast import Toast


class MainWindow(QMainWindow):
    BORDER = 8

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LocalHost")
        self.resize(WINDOW_W, WINDOW_H)
        self.setMinimumSize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)

        self.store = SettingsStore()
        self.settings: AppSettings = self.store.load()
        self.studio_path = self._initial_studio_path()
        self.mode: str | None = None
        self.running = False
        self.current_key = "overview"
        self.active_modes: set[str] = set()
        self.session_pages: dict[str, SessionPage] = {}
        self.host_session_guids: tuple[str, str] | None = None
        self.workers: dict[str, object] = {}
        self.worker_threads: dict[str, QThread] = {}
        self._toast: Toast | None = None

        self._build_shell()
        self.navigate("overview")
        self.update_session_status()

    def _build_shell(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self.toggle_maximize)
        self.title_bar.close_requested.connect(self.close)
        outer.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("contentRoot")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigate)
        body_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._enable_windows_backdrop()

    def _initial_studio_path(self) -> str:
        saved = self.settings.studio_path
        if saved and Path(saved).is_file():
            return saved
        path = get_studio_path()
        if path:
            self.settings = self.store.update(self.settings, studio_path=path)
        return path

    def navigate(self, key: str) -> None:
        if key == "create" and key in self.session_pages:
            self._show_session_page(key)
            return
        if key == "join" and key in self.session_pages:
            self._show_session_page(key)
            return

        self.current_key = key
        self.sidebar.set_current(key)
        builders = {
            "overview": lambda: OverviewPage(self),
            "create": lambda: CreatePage(self),
            "join": lambda: JoinPage(self),
            "settings": lambda: SettingsPage(self),
            "support": lambda: SupportPage(self),
        }
        builder = builders.get(key, builders["overview"])
        self._set_page(builder())

    def _set_page(self, page: QWidget) -> None:
        old = self.stack.currentWidget()
        if self.stack.indexOf(page) == -1:
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        if old and old not in self.session_pages.values():
            self.stack.removeWidget(old)
            old.deleteLater()

    def _show_session_page(self, nav_key: str) -> None:
        page = self.session_pages.get(nav_key)
        if not page:
            return
        self.current_key = nav_key
        self.sidebar.set_current(nav_key)
        self._set_page(page)

    def update_session_status(self) -> None:
        active = self.session_active()
        if active:
            if {"create", "join"}.issubset(self.active_modes):
                text = "Server + proxy active"
            elif "create" in self.active_modes:
                text = "Server live"
            elif "join" in self.active_modes:
                text = "Proxy active"
            else:
                text = "Active"
            self.title_bar.set_status(text, "#4ade80", True)
            self.sidebar.set_session(True, text, self.mode, self.active_modes)
        elif self.studio_path and Path(self.studio_path).is_file():
            self.title_bar.set_status("Ready", "#6e6e6e")
            self.sidebar.set_session(False, mode=self.mode)
        else:
            self.title_bar.set_status("Studio not configured", "#eab308")
            self.sidebar.set_session(False, mode=self.mode)

    def session_active(self) -> bool:
        return bool(self.active_modes) or proxy.is_running or has_running_processes()

    def ensure_studio_path(self) -> str:
        if self.studio_path and Path(self.studio_path).is_file():
            return self.studio_path
        path = get_studio_path()
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select RobloxStudioBeta.exe",
                "",
                "Studio (RobloxStudioBeta.exe);;Executable (*.exe);;All files (*.*)",
            )
        if path and Path(path).is_file():
            self.set_studio_path(path, navigate=False)
            return path
        return ""

    def set_studio_path(self, path: str, navigate: bool = True) -> None:
        candidate = Path(path)
        if not candidate.is_file():
            self.toast("Selected Studio path does not exist.", "error")
            return
        if candidate.name.lower() != "robloxstudiobeta.exe":
            self.toast("Choose RobloxStudioBeta.exe, not another executable.", "error")
            return
        self.studio_path = str(candidate)
        self.settings = self.store.update(self.settings, studio_path=str(candidate))
        self.toast("Studio path saved.", "success")
        self.update_session_status()
        if navigate:
            self.navigate("settings")

    def clear_studio_path(self) -> None:
        self.studio_path = ""
        self.settings = self.store.update(self.settings, studio_path="")
        self.toast("Studio path cleared.", "info")
        self.update_session_status()
        self.navigate("settings")

    def auto_detect_studio(self) -> None:
        path = get_studio_path()
        if path:
            self.set_studio_path(path)
        else:
            self.toast("Studio not found. Use Browse instead.", "warning")

    def create_session(self, user_id: str, tunnel: str, port: str, place_path: str = "") -> None:
        if "create" in self.session_pages:
            self.toast("Server is already active.", "warning")
            return
        studio = self.ensure_studio_path()
        if not studio:
            self.toast("Cannot locate RobloxStudioBeta.exe.", "error")
            return
        self.settings = self.store.update(
            self.settings,
            user_id=user_id,
            host_tunnel=tunnel,
            server_port=port,
            place_path=place_path,
        )
        self.mode = "create"
        self.running = True
        self.active_modes.add("create")
        info = [
            ("Mode", "Server (host)"),
            ("User ID", user_id),
            ("Port", port),
            ("Tunnel", tunnel or "-"),
            ("Map", Path(place_path).name if place_path else "-"),
        ]
        page = SessionPage(self, "Server", "Local Studio server.", info, lambda: self.stop_session("create"))
        self.session_pages["create"] = page
        page.set_loading_visible(True)
        page.set_console_visible(False)
        self._set_page(page)
        if tunnel:
            page.add_copy_tunnel(
                lambda checked=False, value=tunnel: self.copy_to_clipboard(value, "Tunnel copied.")
            )
        self.sidebar.set_current("create")
        self.update_session_status()

        worker = HostSessionWorker(
            studio,
            user_id,
            port,
            place_path,
        )
        self.host_session_guids = (worker.parent_guid, worker.play_guid)
        worker.log.connect(self._worker_log)
        worker.status.connect(self._worker_status)
        worker.progress.connect(self._worker_progress)
        self._start_worker("create", worker)

    def open_place_file(self, place_path: str) -> None:
        try:
            open_place_file(place_path)
            self.settings = self.store.update(self.settings, place_path=place_path)
            self.toast("Map launched in Roblox Studio.", "success")
        except Exception as exc:
            self.toast(f"Map launch failed: {exc}", "error")

    def join_session(self, host: str, port: int, raw: str) -> None:
        if "join" in self.session_pages:
            self.toast("Connection is already active.", "warning")
            return
        studio = self.ensure_studio_path()
        if not studio:
            self.toast("Cannot locate RobloxStudioBeta.exe.", "error")
            return
        self.settings = self.store.update(self.settings, join_tunnel=raw)

        if self._matches_active_host_tunnel(host, port, raw):
            self._join_active_host_locally(studio, raw)
            return

        self.mode = "join"
        self.running = True
        self.active_modes.add("join")
        info = [
            ("Mode", "Client (join)"),
            ("Target host", host),
            ("Target port", str(port)),
            ("Local proxy", "127.0.0.1:pending"),
            ("Status", "Initializing"),
        ]
        page = SessionPage(self, "Connection", "UDP proxy and Studio client.", info, lambda: self.stop_session("join"))
        self.session_pages["join"] = page
        self._set_page(page)
        self.sidebar.set_current("join")
        self.update_session_status()

        worker = JoinSessionWorker(studio, host, port)
        worker.log.connect(self._worker_log)
        worker.status.connect(self._worker_status)
        worker.info_changed.connect(self._worker_info)
        self._start_worker("join", worker)

    def _matches_active_host_tunnel(self, host: str, port: int, raw: str) -> bool:
        if "create" not in self.active_modes or not self.host_session_guids:
            return False
        host_tunnel = self.settings.host_tunnel.strip()
        if not host_tunnel:
            return False
        if raw.strip().lower() == host_tunnel.lower():
            return True
        if ":" not in host_tunnel:
            return False
        active_host, active_port = host_tunnel.rsplit(":", 1)
        return host.strip().lower() == active_host.strip().lower() and str(port) == active_port.strip()

    def _join_active_host_locally(self, studio: str, raw: str) -> None:
        if not self.host_session_guids:
            self.toast("Local server session is not ready.", "error")
            return
        parent_guid, play_guid = self.host_session_guids
        server_port = self.settings.server_port

        self.mode = "join"
        self.running = True
        self.active_modes.add("join")
        info = [
            ("Mode", "Client (local host)"),
            ("Target host", "127.0.0.1"),
            ("Target port", server_port),
            ("Local proxy", "not used"),
            ("Status", "Launching"),
        ]
        page = SessionPage(
            self,
            "Connection",
            "Direct client to active local server.",
            info,
            lambda: self.stop_session("join"),
        )
        self.session_pages["join"] = page
        self._set_page(page)
        self.sidebar.set_current("join")
        self.update_session_status()

        try:
            page.append_log(f"Detected active host tunnel {raw}; using local server", "info")
            launch_client(
                studio,
                "127.0.0.1",
                server_port,
                parent_guid,
                play_guid,
                "StudioPlayer_Host",
                session_key="join",
            )
            page.set_info("Status", "Connected locally", "#4ade80")
            page.set_status("Connected locally", "ok")
            page.append_log("Studio client launched", "success")
            self.toast("Local client launched.", "success")
        except Exception as exc:
            self.active_modes.discard("join")
            self.session_pages.pop("join", None)
            self.stack.removeWidget(page)
            page.deleteLater()
            self.update_session_status()
            self.toast(f"Launch error: {exc}", "error")

    def _start_worker(self, mode: str, worker) -> None:
        existing = self.worker_threads.get(mode)
        if existing and shiboken6.isValid(existing):
            existing.quit()
            existing.wait(500)
        self.worker_threads.pop(mode, None)
        self.workers.pop(mode, None)

        thread = QThread(self)
        thread.setProperty("sessionMode", mode)
        worker.setProperty("sessionMode", mode)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._worker_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self.workers[mode] = worker
        self.worker_threads[mode] = thread

    @Slot()
    def _worker_thread_finished(self, mode: str | None = None) -> None:
        if not mode:
            mode = self._sender_mode()
        if not mode:
            return
        page = self.session_pages.get(mode)
        if page and page.loading_visible:
            page.set_progress(100, "Ready")
            page.set_loading_visible(False)
            page.set_console_visible(True)
        self.worker_threads.pop(mode, None)
        self.workers.pop(mode, None)

    def _sender_mode(self) -> str | None:
        sender = self.sender()
        if sender is None:
            return None
        mode = sender.property("sessionMode")
        return str(mode) if mode else None

    @Slot(str, str)
    def _worker_log(self, message: str, level: str) -> None:
        mode = self._sender_mode()
        if mode:
            self._session_log(mode, message, level)

    @Slot(str, str)
    def _worker_status(self, text: str, tone: str) -> None:
        mode = self._sender_mode()
        if mode:
            self._session_status(mode, text, tone)

    @Slot(str, str)
    def _worker_info(self, key: str, value: str) -> None:
        mode = self._sender_mode()
        if mode:
            self._session_info(mode, key, value)

    @Slot(int, str)
    def _worker_progress(self, value: int, text: str) -> None:
        mode = self._sender_mode()
        if mode:
            self._session_progress(mode, value, text)

    def _session_log(self, mode: str, message: str, level: str) -> None:
        page = self.session_pages.get(mode)
        if page:
            page.append_log(message, level)

    def _session_status(self, mode: str, text: str, tone: str) -> None:
        if tone == "err":
            self.active_modes.discard(mode)
            if mode == "create":
                self.host_session_guids = None
            if not self.active_modes:
                self.running = False
        page = self.session_pages.get(mode)
        if page:
            page.set_status(text, tone)
            if tone in {"ok", "err"} and page.loading_visible:
                page.set_progress(100, text)
                page.set_loading_visible(False)
                page.set_console_visible(True)
        self.update_session_status()

    def _session_info(self, mode: str, key: str, value: str) -> None:
        page = self.session_pages.get(mode)
        if page:
            page.set_info(key, value, "#4ade80" if key == "Status" else None)

    def _session_progress(self, mode: str, value: int, text: str) -> None:
        page = self.session_pages.get(mode)
        if page:
            page.set_progress(value, text)
            if value >= 100:
                page.set_loading_visible(False)
                page.set_console_visible(True)

    def _add_local_join(self, port: str, parent_guid: str, play_guid: str) -> None:
        page = self.session_pages.get("create")
        if page:
            page.add_local_join(lambda: self.join_local(port, parent_guid, play_guid))

    def join_local(self, port: str, parent_guid: str, play_guid: str) -> None:
        try:
            studio = self.ensure_studio_path()
            if not studio:
                self.toast("Cannot locate RobloxStudioBeta.exe.", "error")
                return
            launch_client(
                studio,
                "127.0.0.1",
                port,
                parent_guid,
                play_guid,
                "StudioPlayer_Host",
                session_key="create",
            )
            self.toast("Local client launched.", "success")
        except Exception as exc:
            self.toast(f"Launch error: {exc}", "error")

    def stop_session(self, mode: str) -> None:
        worker = self.workers.get(mode)
        if worker and shiboken6.isValid(worker) and hasattr(worker, "stop"):
            QMetaObject.invokeMethod(worker, "stop", Qt.ConnectionType.QueuedConnection)
        if mode == "join":
            proxy.stop(wait=False)
        if mode == "create":
            self.host_session_guids = None

        killed = stop_roblox_processes(mode)
        self.active_modes.discard(mode)
        self.running = bool(self.active_modes)
        self.mode = next(iter(self.active_modes), None)

        page = self.session_pages.pop(mode, None)
        if page:
            self.stack.removeWidget(page)
            page.deleteLater()

        self.toast(f"Session stopped. {killed} process(es) terminated.", "success")
        self.update_session_status()
        next_mode = next(iter(self.active_modes), None)
        if next_mode and next_mode in self.session_pages:
            self._show_session_page(next_mode)
        else:
            self.navigate("overview")

    def stop_everything(self) -> None:
        for worker in list(self.workers.values()):
            if shiboken6.isValid(worker) and hasattr(worker, "stop"):
                QMetaObject.invokeMethod(worker, "stop", Qt.ConnectionType.QueuedConnection)
        proxy.stop(wait=False)
        killed = stop_all_roblox_processes()
        self.running = False
        self.mode = None
        self.active_modes.clear()
        self.host_session_guids = None
        for page in list(self.session_pages.values()):
            self.stack.removeWidget(page)
            page.deleteLater()
        self.session_pages.clear()
        self.toast(f"Session stopped. {killed} process(es) terminated.", "success")
        self.update_session_status()
        self.navigate("overview")

    def toast(self, text: str, tone: str = "info") -> None:
        if self._toast:
            try:
                self._toast.deleteLater()
            except RuntimeError:
                pass
            self._toast = None
        self._toast = Toast(text, tone, self)
        toast = self._toast
        toast.destroyed.connect(lambda: self._clear_toast_ref(toast))
        self._position_toast()
        self._toast.show_animated()

    def copy_to_clipboard(self, text: str, message: str = "Copied.") -> None:
        QApplication.clipboard().setText(text)
        self.toast(message, "success")

    def _clear_toast_ref(self, toast: Toast) -> None:
        if self._toast is toast:
            self._toast = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_toast()

    def _position_toast(self) -> None:
        if not self._toast:
            return
        self._toast.adjustSize()
        x = (self.width() - self._toast.width()) // 2
        y = self.height() - self._toast.height() - 22
        self._toast.move(max(12, x), max(12, y))

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def nativeEvent(self, event_type, message):
        if os.name != "nt":
            return False, 0
        if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        WM_NCHITTEST = 0x0084
        if msg.message != WM_NCHITTEST:
            return False, 0

        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        pos = self.mapFromGlobal(QPoint(x, y))
        width = self.width()
        height = self.height()
        border = 0 if self.isMaximized() else self.BORDER

        HTCLIENT = 1
        HTCAPTION = 2
        HTLEFT = 10
        HTRIGHT = 11
        HTTOP = 12
        HTTOPLEFT = 13
        HTTOPRIGHT = 14
        HTBOTTOM = 15
        HTBOTTOMLEFT = 16
        HTBOTTOMRIGHT = 17

        if border:
            left = pos.x() < border
            right = pos.x() >= width - border
            top = pos.y() < border
            bottom = pos.y() >= height - border
            if top and left:
                return True, HTTOPLEFT
            if top and right:
                return True, HTTOPRIGHT
            if bottom and left:
                return True, HTBOTTOMLEFT
            if bottom and right:
                return True, HTBOTTOMRIGHT
            if left:
                return True, HTLEFT
            if right:
                return True, HTRIGHT
            if top:
                return True, HTTOP
            if bottom:
                return True, HTBOTTOM

        if 0 <= pos.y() <= self.title_bar.height() and not self.title_bar.is_control_at(QPoint(x, y)):
            return True, HTCAPTION
        return False, HTCLIENT

    def _enable_windows_backdrop(self) -> None:
        if os.name != "nt":
            return
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            value = ctypes.c_int(1)
            for attr in (20, 19):
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
            backdrop = ctypes.c_int(2)
            dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        except Exception:
            pass

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.session_active():
            reply = QMessageBox.question(
                self,
                "Quit LocalHost",
                "Stop active sessions and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        proxy.stop(wait=False)
        stop_all_roblox_processes()
        event.accept()
