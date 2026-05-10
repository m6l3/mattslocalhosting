from __future__ import annotations

import time

import shiboken6
from PySide6.QtCore import QObject, Signal, Slot

from app.core.config import PROXY_PORT
from app.core.proxy import proxy, warmup_udp_tunnel
from app.core.studio import generate_guid, launch_client, launch_server

SETUP_WAIT_SECONDS = 20


class HostSessionWorker(QObject):
    log = Signal(str, str)
    status = Signal(str, str)
    progress = Signal(int, str)
    finished = Signal()

    def __init__(self, studio: str, user_id: str, port: str, place_path: str = "") -> None:
        super().__init__()
        self.studio = studio
        self.user_id = user_id
        self.port = port
        self.place_path = place_path
        self.parent_guid = generate_guid()
        self.play_guid = generate_guid()
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            self.status.emit("Setting up", "warn")
            self.progress.emit(5, "Preparing")
            if self.place_path:
                self.log.emit(f"Selected map: {self.place_path}", "info")
                self.log.emit("Copying map to Roblox local server runtime", "info")

            self.progress.emit(30, "Starting local server")
            launch_server(
                self.studio,
                self.port,
                self.user_id,
                self.parent_guid,
                self.play_guid,
                self.place_path,
                startup_players=1,
                use_runtime_place=bool(self.place_path),
                session_key="create",
            )
            self.log.emit(f"Local server + 1 client start command sent on port {self.port}", "info")
            for step in range(180):
                if self._cancelled:
                    self.finished.emit()
                    return
                time.sleep(0.1)
                self.progress.emit(30 + int((step / 179) * 65), "Initializing server and client")
            self.status.emit("Server live", "ok")
            self.status.emit("Server + client live", "ok")
            self.progress.emit(100, "Server and clients launched")
            self.log.emit("Server and client launched", "success")
        except Exception as exc:
            self.status.emit("Launch failed", "err")
            self.progress.emit(100, "Erreur")
            self.log.emit(f"ERROR: {exc}", "error")
        finally:
            self.finished.emit()

    @Slot()
    def stop(self) -> None:
        self._cancelled = True


class JoinSessionWorker(QObject):
    log = Signal(str, str)
    status = Signal(str, str)
    info_changed = Signal(str, str)
    finished = Signal()

    def __init__(self, studio: str, dst_host: str, dst_port: int) -> None:
        super().__init__()
        self.studio = studio
        self.dst_host = dst_host
        self.dst_port = dst_port
        self.parent_guid = generate_guid()
        self.play_guid = generate_guid()
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit("Preparing tunnel connection", "info")
            warmup_udp_tunnel(self.dst_host, self.dst_port, self._emit_log)
            if self._cancelled:
                self.finished.emit()
                return

            self.log.emit(f"Binding proxy from port {PROXY_PORT}", "info")
            success, actual_port = proxy.start(self.dst_host, self.dst_port, self._emit_log)
            if not success:
                self.status.emit("Proxy failed", "err")
                self.log.emit("Proxy failed to bind. Aborting", "error")
                return

            self.info_changed.emit("Local proxy", f"127.0.0.1:{actual_port}")
            self.info_changed.emit("Status", "Proxy active")
            self.log.emit(f"Proxy active on 127.0.0.1:{actual_port}", "success")
            self.log.emit("Launching Studio client", "info")
            launch_client(
                self.studio,
                "127.0.0.1",
                actual_port,
                self.parent_guid,
                self.play_guid,
                "StudioPlayer_Proxy",
                session_key="join",
            )
            self.status.emit(f"Connected :{actual_port}", "ok")
            self.log.emit("Studio client launched", "success")
        except Exception as exc:
            proxy.stop(wait=False)
            self.status.emit("Client failed", "err")
            self.log.emit(f"ERROR: {exc}", "error")
        finally:
            self.finished.emit()

    def _emit_log(self, message: str, level: str = "info") -> None:
        try:
            if shiboken6.isValid(self):
                self.log.emit(message, level)
        except RuntimeError:
            pass

    @Slot()
    def stop(self) -> None:
        self._cancelled = True
        proxy.stop(wait=False)
