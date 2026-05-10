from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable

from app.core.config import PROXY_PORT

LogFn = Callable[[str, str], None]


def find_free_port(start_port: int, max_attempts: int = 100) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return -1


def warmup_udp_tunnel(dst_host: str, dst_port: int, log: LogFn, packets: int = 10, delay: float = 0.05) -> None:
    log(f"Warming tunnel {dst_host}:{dst_port} ({packets} packets)", "info")
    try:
        dst_ip = socket.gethostbyname(dst_host)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            payload = b"\x00" * 64
            for _ in range(packets):
                try:
                    sock.sendto(payload, (dst_ip, dst_port))
                except OSError:
                    pass
                time.sleep(delay)
        log("Tunnel warm-up complete", "success")
    except Exception as exc:
        log(f"Warm-up warning: {exc}", "warning")


class UdpProxy:
    def __init__(self, base_port: int = PROXY_PORT) -> None:
        self.base_port = base_port
        self.active_port: int | None = None
        self._running = threading.Event()
        self._stopped = threading.Event()
        self._sockets: list[socket.socket] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self, dst_host: str, dst_port: int, log: LogFn) -> tuple[bool, int]:
        if self.is_running:
            self.stop()

        self._running.set()
        self._stopped.clear()
        ready = threading.Event()
        error: list[str | None] = [None]
        port_box: list[int | None] = [None]

        def worker() -> None:
            sessions: dict[tuple[str, int], socket.socket] = {}
            local_sock: socket.socket | None = None
            try:
                dst_ip = socket.gethostbyname(dst_host)
                log(f"Resolved {dst_host} -> {dst_ip}", "info")

                bound_port = find_free_port(self.base_port)
                if bound_port == -1:
                    raise OSError(f"No free UDP ports starting at {self.base_port}")
                port_box[0] = bound_port
                if bound_port != self.base_port:
                    log(f"Port {self.base_port} busy, using {bound_port}", "warning")

                local_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                local_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                local_sock.bind(("127.0.0.1", bound_port))
                local_sock.settimeout(0.3)
                with self._lock:
                    self._sockets.append(local_sock)

                log(f"UDP proxy bound on 127.0.0.1:{bound_port}", "success")
                ready.set()

                while self._running.is_set():
                    try:
                        data, addr = local_sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    except OSError:
                        break

                    if addr not in sessions:
                        log(f"New session: {addr[0]}:{addr[1]}", "info")
                        session_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        session_sock.settimeout(0.3)
                        sessions[addr] = session_sock

                        def listen(sock: socket.socket, client_addr: tuple[str, int]) -> None:
                            while self._running.is_set() and client_addr in sessions:
                                try:
                                    resp, _ = sock.recvfrom(65535)
                                    local_sock.sendto(resp, client_addr)
                                except socket.timeout:
                                    continue
                                except OSError:
                                    break
                            try:
                                sock.close()
                            except Exception:
                                pass
                            sessions.pop(client_addr, None)

                        threading.Thread(target=listen, args=(session_sock, addr), daemon=True).start()

                    try:
                        sessions[addr].sendto(data, (dst_ip, dst_port))
                    except OSError as exc:
                        log(f"Send error: {exc}", "error")
            except Exception as exc:
                error[0] = str(exc)
                ready.set()
            finally:
                for sock in list(sessions.values()):
                    try:
                        sock.close()
                    except Exception:
                        pass
                sessions.clear()
                if local_sock:
                    with self._lock:
                        try:
                            self._sockets.remove(local_sock)
                        except ValueError:
                            pass
                    try:
                        local_sock.close()
                    except Exception:
                        pass
                self.active_port = None
                self._stopped.set()
                log("UDP proxy stopped", "info")

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        ready.wait(timeout=5)
        if error[0]:
            log(f"Proxy error: {error[0]}", "error")
            self._running.clear()
            return False, -1

        self.active_port = port_box[0]
        return True, port_box[0] or -1

    def stop(self, wait: bool = True) -> None:
        if not self.is_running:
            return
        self._running.clear()
        with self._lock:
            for sock in list(self._sockets):
                try:
                    sock.close()
                except Exception:
                    pass
            self._sockets.clear()
        if wait and self._thread and self._thread.is_alive():
            self._stopped.wait(timeout=3)
        self._thread = None
        self.active_port = None


proxy = UdpProxy()

