import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket
import threading
import time
import subprocess
import uuid
import os
import atexit
import json

# ==================== CONSTANTS ====================
PROXY_PORT  = 55555
DATA_FILE   = "mattslocalhost_data.json"

BG_COLOR    = "#1a1a2e"
CARD_COLOR  = "#16213e"
ACCENT_COLOR = "#0f3460"
BTN_CREATE  = "#2ecc71"
BTN_JOIN    = "#3498db"
BTN_DANGER  = "#e74c3c"
BTN_WARN    = "#f39c12"
TEXT_COLOR  = "#eaeaea"
MUTED_COLOR = "#95a5a6"
FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_SUB    = ("Segoe UI", 10)
FONT_LABEL  = ("Segoe UI", 10, "bold")
FONT_LOG    = ("Consolas", 9)

# ==================== PERSISTENCE ====================

def load_data() -> dict:
    """Load saved user data from JSON file. Returns defaults if missing or corrupt."""
    defaults = {
        "user_id": "123456789",
        "host_tunnel": "",
        "join_tunnel": "",
        "server_port": "55555",
    }
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            # Merge: keep defaults for any missing keys
            return {**defaults, **stored}
    except Exception:
        pass
    return defaults


def save_data(data: dict):
    """Persist user data to JSON file, silently ignore errors."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ==================== GLOBAL PROXY STATE ====================
_proxy_running  = threading.Event()   # set = proxy should run
_proxy_stopped  = threading.Event()   # set = worker thread has exited
_udp_sockets    = []
_proxy_lock     = threading.Lock()
_proxy_thread   = None
_active_port    = None  # Stores the actual port being used


# ==================== HELPERS ====================
def get_studio_path() -> str:
    """Locate RobloxStudioBeta.exe via PowerShell (blocking, call in thread)."""
    try:
        cmd = (
            'powershell -Command "'
            'Get-ChildItem -Path $env:LOCALAPPDATA\\Roblox\\Versions '
            '-Filter RobloxStudioBeta.exe -Recurse | '
            'Select-Object -First 1 -ExpandProperty FullName"'
        )
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        result = subprocess.check_output(
            cmd, shell=True, creationflags=flags
        ).decode(errors="ignore").strip()
        return result
    except Exception:
        return ""


def generate_guid() -> str:
    return str(uuid.uuid4()).upper()


def ts() -> str:
    return time.strftime("%H:%M:%S")


def find_free_port(start_port: int, max_attempts: int = 100) -> int:
    """
    Find a free port starting from start_port.
    Returns the free port number or -1 if none found.
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.bind(("127.0.0.1", port))
            test_sock.close()
            return port
        except OSError:
            continue
    return -1


# ==================== UDP PROXY ====================
def start_udp_proxy(dst_host: str, dst_port: int, log_fn) -> tuple:
    """
    Start a UDP proxy on 127.0.0.1 -> dst_host:dst_port.
    Automatically finds a free port starting from PROXY_PORT.
    Returns (success: bool, actual_port: int).
    Guarantees the worker thread exits when _proxy_running is cleared.
    """
    global _proxy_thread, _active_port

    # Safety: stop any existing proxy first
    if _proxy_running.is_set():
        stop_udp_proxy()

    _proxy_running.set()
    _proxy_stopped.clear()

    ready_event = threading.Event()
    error_box   = [None]
    port_box    = [None]

    def worker():
        client_sessions: dict = {}
        local_sock = None
        bound_port = None
        
        try:
            dst_ip = socket.gethostbyname(dst_host)
            log_fn(f"Resolved {dst_host} -> {dst_ip}")

            # Find a free port
            bound_port = find_free_port(PROXY_PORT)
            if bound_port == -1:
                raise OSError(f"No free ports available starting from {PROXY_PORT}")
            
            port_box[0] = bound_port
            
            if bound_port != PROXY_PORT:
                log_fn(f"Port {PROXY_PORT} is busy, using port {bound_port} instead")

            local_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            local_sock.bind(("127.0.0.1", bound_port))
            local_sock.settimeout(0.3)

            with _proxy_lock:
                _udp_sockets.append(local_sock)

            log_fn(f"UDP Proxy bound on 127.0.0.1:{bound_port}")
            ready_event.set()

            while _proxy_running.is_set():
                try:
                    data, addr = local_sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break

                if addr not in client_sessions:
                    log_fn(f"New session from {addr[0]}:{addr[1]}")
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.settimeout(0.3)
                    client_sessions[addr] = s

                    def _listen(sock, client_addr, _ls=local_sock):
                        while _proxy_running.is_set() and client_addr in client_sessions:
                            try:
                                resp, _ = sock.recvfrom(65535)
                                _ls.sendto(resp, client_addr)
                            except socket.timeout:
                                continue
                            except OSError:
                                break
                        try:
                            sock.close()
                        except Exception:
                            pass
                        client_sessions.pop(client_addr, None)

                    threading.Thread(
                        target=_listen, args=(s, addr), daemon=True
                    ).start()

                try:
                    client_sessions[addr].sendto(data, (dst_ip, dst_port))
                except OSError as e:
                    log_fn(f"Send error: {e}")

        except OSError as e:
            error_box[0] = str(e)
            ready_event.set()
        except Exception as e:
            error_box[0] = str(e)
            ready_event.set()
        finally:
            # Close all back-channel sockets
            for s in list(client_sessions.values()):
                try:
                    s.close()
                except Exception:
                    pass
            client_sessions.clear()

            # Remove and close the main socket
            if local_sock:
                with _proxy_lock:
                    try:
                        _udp_sockets.remove(local_sock)
                    except ValueError:
                        pass
                try:
                    local_sock.close()
                except Exception:
                    pass

            log_fn("UDP Proxy stopped.")
            _proxy_stopped.set()

    _proxy_thread = threading.Thread(target=worker, daemon=True)
    _proxy_thread.start()

    ready_event.wait(timeout=5)

    if error_box[0]:
        log_fn(f"Proxy error: {error_box[0]}")
        _proxy_running.clear()
        return (False, -1)
    
    _active_port = port_box[0]
    return (True, port_box[0])


def stop_udp_proxy(wait: bool = True):
    """
    Signal the proxy loop to exit, force-close all sockets,
    and optionally wait for the worker thread to finish.
    Safe to call multiple times.
    """
    global _proxy_thread, _active_port

    if not _proxy_running.is_set():
        return

    _proxy_running.clear()

    # Force-close sockets so recvfrom() unblocks immediately
    with _proxy_lock:
        for s in _udp_sockets:
            try:
                s.close()
            except Exception:
                pass
        _udp_sockets.clear()

    if wait and _proxy_thread and _proxy_thread.is_alive():
        _proxy_stopped.wait(timeout=3)

    _proxy_thread = None
    _active_port = None


# Register cleanup on interpreter exit
atexit.register(lambda: stop_udp_proxy(wait=False))


# ==================== STUDIO LAUNCHER ====================
def launch_server(studio: str, port: str, user_id: str,
                  parent_guid: str, play_guid: str):
    args = [
        studio,
        "-task", "StartServer",
        "-placeId", "0",
        "-universeId", "0",
        "-placeVersion", "0",
        "-port", port,
        "-creatorId", user_id,
        "-creatorType", "0",
        "-userid", user_id,
        "-numTestServerPlayersUponStartup", "0",
        "-parentSessionGuid", parent_guid,
        "-playTestSessionGuid", play_guid,
        "-instanceId", "StudioServer",
    ]
    subprocess.Popen(args)


def launch_client(studio: str, server_ip: str, server_port: str,
                  parent_guid: str, play_guid: str, instance_id: str):
    args = [
        studio,
        "-task", "StartClient",
        "-placeId", "0",
        "-universeId", "0",
        "-placeVersion", "0",
        "-server", server_ip,
        "-port", server_port,
        "-parentSessionGuid", parent_guid,
        "-playTestSessionGuid", play_guid,
        "-instanceId", instance_id,
    ]
    subprocess.Popen(args)


# ==================== WIDGETS ====================
def make_button(parent, text, color, command, width=22):
    return tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activebackground=color,
        font=("Segoe UI", 10, "bold"),
        relief="flat", bd=0, cursor="hand2",
        width=width, pady=8,
    )


def make_entry(parent, placeholder="", width=38):
    e = tk.Entry(
        parent, width=width,
        font=FONT_SUB,
        bg="#0d1b2a", fg=TEXT_COLOR,
        insertbackground=TEXT_COLOR,
        relief="flat", bd=4,
    )
    e.insert(0, placeholder)
    return e


def make_log(parent, height=14):
    return scrolledtext.ScrolledText(
        parent, height=height,
        font=FONT_LOG,
        bg="#0a0a1a", fg="#00ff88",
        insertbackground=TEXT_COLOR,
        relief="flat", bd=0,
        state="normal",
    )


# ==================== SPLASH SCREEN ====================
class SplashScreen(tk.Toplevel):
    """
    Animated loading splash while Studio path is resolved.
    Shows a pulsing status line and rotating dot animation.
    """
    _DOT_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.overrideredirect(True)          # borderless
        self.configure(bg=BG_COLOR)
        self.attributes("-topmost", True)

        w, h = 380, 200
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # ── border frame ──────────────────────────────────────
        border = tk.Frame(self, bg="#0f3460", padx=2, pady=2)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=BG_COLOR)
        inner.pack(fill="both", expand=True)

        # ── title ─────────────────────────────────────────────
        tk.Label(
            inner, text="Matt's LocalHost",
            font=("Segoe UI", 15, "bold"),
            bg=BG_COLOR, fg=TEXT_COLOR
        ).pack(pady=(28, 4))

        # ── spinner + status ──────────────────────────────────
        spin_row = tk.Frame(inner, bg=BG_COLOR)
        spin_row.pack(pady=(10, 0))

        self._spin_lbl = tk.Label(
            spin_row, text=self._DOT_FRAMES[0],
            font=("Segoe UI", 14), bg=BG_COLOR, fg=BTN_JOIN, width=2
        )
        self._spin_lbl.pack(side="left")

        self._status_lbl = tk.Label(
            spin_row, text="Locating Studio...",
            font=("Segoe UI", 10), bg=BG_COLOR, fg=MUTED_COLOR
        )
        self._status_lbl.pack(side="left", padx=(6, 0))

        # ── subtle progress bar ───────────────────────────────
        bar_bg = tk.Frame(inner, bg="#0d1b2a", height=4, width=300)
        bar_bg.pack(pady=(18, 0))
        bar_bg.pack_propagate(False)

        self._bar = tk.Frame(bar_bg, bg=BTN_JOIN, height=4, width=0)
        self._bar.place(x=0, y=0, height=4)

        self._frame_idx  = 0
        self._bar_width  = 0
        self._bar_target = 0
        self._animating  = True
        self._animate()

    # ── animation loop ────────────────────────────────────────
    def _animate(self):
        if not self._animating:
            return
        self._frame_idx = (self._frame_idx + 1) % len(self._DOT_FRAMES)
        self._spin_lbl.config(text=self._DOT_FRAMES[self._frame_idx])

        # Ease bar toward target
        diff = self._bar_target - self._bar_width
        step = max(1, int(diff * 0.08))
        if diff > 0:
            self._bar_width = min(self._bar_width + step, self._bar_target)
            self._bar.place_configure(width=self._bar_width)

        self.after(80, self._animate)

    def set_status(self, text: str, progress: int = 0):
        """Update status text and progress bar (0-300)."""
        self._status_lbl.config(text=text)
        self._bar_target = progress

    def close(self):
        self._animating = False
        self.destroy()


# ==================== MAIN APPLICATION ====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Matt's LocalHost")
        self.geometry("560x480")
        self.resizable(False, False)
        self.configure(bg=BG_COLOR)

        # Handle window close: stop proxy before exit
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.studio_path = ""
        self._frame      = None

        # Load persisted user data on startup
        self._data = load_data()

        # Show splash immediately, resolve Studio in background
        self._show_splash()

    def _on_close(self):
        """Cleanly shut down proxy and exit."""
        stop_udp_proxy(wait=True)
        self.destroy()

    # ──────────────────────────────────────────────────────────
    # SPLASH — async Studio lookup
    # ──────────────────────────────────────────────────────────
    def _show_splash(self):
        # Hide main window during splash
        self.withdraw()
        splash = SplashScreen(self)

        def lookup():
            splash.set_status("Running PowerShell query...", 80)
            path = get_studio_path()
            self.after(0, lambda: _done(path))

        def _done(path):
            splash.set_status(
                "Studio found!" if path else "Studio not found.",
                300
            )
            self.studio_path = path
            self.after(600, lambda: _finish(path))

        def _finish(path):
            splash.close()
            self.deiconify()
            if not path:
                messagebox.showwarning(
                    "Studio Not Found",
                    "RobloxStudioBeta.exe was not found.\n"
                    "Make sure Studio is installed."
                )
            self._show_welcome()

        threading.Thread(target=lookup, daemon=True).start()

    # ──────────────────────────────────────────────────────────
    # FRAME MANAGEMENT
    # ──────────────────────────────────────────────────────────
    def _swap(self, builder):
        if self._frame:
            self._frame.destroy()
        self._frame = tk.Frame(self, bg=BG_COLOR)
        self._frame.pack(fill="both", expand=True)
        builder(self._frame)

    def _write_log(self, widget: scrolledtext.ScrolledText, msg: str):
        def _do():
            widget.insert(tk.END, f"[{ts()}] {msg}\n")
            widget.see(tk.END)
        self.after(0, _do)

    # ──────────────────────────────────────────────────────────
    # WELCOME SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_welcome(self):
        # Always stop proxy when returning to welcome
        stop_udp_proxy(wait=False)

        def build(f):
            tk.Label(
                f, text="Matt's LocalHost",
                font=FONT_TITLE, bg=BG_COLOR, fg=TEXT_COLOR
            ).pack(pady=(60, 6))

            tk.Label(
                f, text="author discord: @s0m3thing_matters\ndiscord server: discord.gg/H3K2xeU96A",
                font=FONT_SUB, bg=BG_COLOR, fg=MUTED_COLOR
            ).pack(pady=(0, 40))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack()

            make_button(btn_row, "  CREATE SERVER  ", BTN_CREATE,
                        self._show_host_menu, width=18).pack(side="left", padx=12)
            make_button(btn_row, "  JOIN SERVER  ", BTN_JOIN,
                        self._show_join_menu, width=18).pack(side="left", padx=12)

        self._swap(build)

    # ──────────────────────────────────────────────────────────
    # HOST / CREATE MENU
    # ──────────────────────────────────────────────────────────
    def _show_host_menu(self):
        def build(f):
            tk.Label(f, text="Create Server", font=("Segoe UI", 14, "bold"),
                     bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(30, 20))

            card = tk.Frame(f, bg=CARD_COLOR, padx=24, pady=20)
            card.pack(padx=40, fill="x")

            tk.Label(card, text="User ID:", font=FONT_LABEL,
                     bg=CARD_COLOR, fg=TEXT_COLOR).pack(anchor="w")
            ent_uid = make_entry(card, self._data.get("user_id", "123456789"))
            ent_uid.pack(fill="x", pady=(2, 10))

            tk.Label(card, text="Tunnel Address (host:port):",
                     font=FONT_LABEL, bg=CARD_COLOR, fg=TEXT_COLOR).pack(anchor="w")
            ent_tunnel = make_entry(card, self._data.get("host_tunnel", ""))
            ent_tunnel.pack(fill="x", pady=(2, 10))

            tk.Label(card, text="TeamTest Server Port:",
                     font=FONT_LABEL, bg=CARD_COLOR, fg=TEXT_COLOR).pack(anchor="w")
            ent_port = make_entry(card, self._data.get("server_port", "55555"))
            ent_port.pack(fill="x", pady=(2, 4))

            def on_create():
                uid    = ent_uid.get().strip()
                tunnel = ent_tunnel.get().strip()
                port   = ent_port.get().strip()
                if not uid or not port:
                    messagebox.showwarning("Missing fields",
                                           "Please fill in User ID and Port.")
                    return
                if not port.isdigit():
                    messagebox.showerror("Invalid port", "Port must be a number.")
                    return
                if not self.studio_path:
                    messagebox.showerror("Studio not found",
                                         "Could not locate RobloxStudioBeta.exe.")
                    return

                # Persist entered values before launching
                self._data["user_id"]     = uid
                self._data["host_tunnel"] = tunnel
                self._data["server_port"] = port
                save_data(self._data)

                self._show_host_running(uid, tunnel, port)

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=18)
            make_button(btn_row, "CREATE", BTN_CREATE, on_create, width=16).pack(
                side="left", padx=8)
            make_button(btn_row, "Back", ACCENT_COLOR,
                        self._show_welcome, width=10).pack(side="left", padx=8)

        self._swap(build)

    # ──────────────────────────────────────────────────────────
    # HOST RUNNING SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_host_running(self, user_id: str, tunnel_addr: str, port: str):
        p_guid = generate_guid()
        t_guid = generate_guid()

        def build(f):
            tk.Label(f, text="Server Console", font=("Segoe UI", 13, "bold"),
                     bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(14, 6))

            log_area = make_log(f, height=16)
            log_area.pack(padx=16, fill="both", expand=True)

            def log(msg):
                self._write_log(log_area, msg)

            status_var = tk.StringVar(value="")
            status_lbl = tk.Label(f, textvariable=status_var,
                                  font=("Segoe UI", 10, "bold"),
                                  bg=BG_COLOR, fg="#2ecc71")
            status_lbl.pack(pady=(6, 0))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=8)

            join_btn = make_button(
                btn_row, "JOIN THIS SERVER (local)",
                BTN_WARN,
                lambda: self._join_local(port, p_guid, t_guid),
                width=26
            )

            def back_to_menu():
                # No proxy running on host side — just go back
                self._show_welcome()

            make_button(btn_row, "Back to Menu", ACCENT_COLOR,
                        back_to_menu, width=14).pack(side="left", padx=8)

            def launch():
                log("Locating Studio...")
                log(f"Studio path : {self.studio_path}")
                log(f"Parent GUID : {p_guid}")
                log(f"Play GUID   : {t_guid}")
                log(f"Port        : {port}")
                log(f"User ID     : {user_id}")
                if tunnel_addr:
                    log(f"Tunnel addr : {tunnel_addr}")
                log("Launching server process...")
                try:
                    launch_server(self.studio_path, port, user_id, p_guid, t_guid)
                    log("Server process started successfully.")
                    log("Waiting for Studio to initialize (~5 s)...")
                    time.sleep(5)
                    self.after(0, lambda: status_var.set("● SERVER IS LIVE"))
                    self.after(0, lambda: join_btn.pack(side="left", padx=8))
                    log("Ready! You can now join the server.")
                except Exception as e:
                    log(f"ERROR: {e}")
                    self.after(0, lambda: status_var.set("● LAUNCH FAILED"))
                    self.after(0, lambda: status_lbl.config(fg=BTN_DANGER))

            threading.Thread(target=launch, daemon=True).start()

        self._swap(build)

    def _join_local(self, port: str, p_guid: str, t_guid: str):
        try:
            launch_client(
                self.studio_path,
                "127.0.0.1", port,
                p_guid, t_guid,
                "StudioPlayer_Host"
            )
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))

    # ──────────────────────────────────────────────────────────
    # JOIN MENU
    # ──────────────────────────────────────────────────────────
    def _show_join_menu(self):
        def build(f):
            tk.Label(f, text="Join via Tunnel",
                     font=("Segoe UI", 14, "bold"),
                     bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(40, 20))

            card = tk.Frame(f, bg=CARD_COLOR, padx=24, pady=20)
            card.pack(padx=40, fill="x")

            tk.Label(card, text="Tunnel Address (host:port):",
                     font=FONT_LABEL, bg=CARD_COLOR, fg=TEXT_COLOR).pack(anchor="w")
            ent_addr = make_entry(card, self._data.get("join_tunnel", ""))
            ent_addr.pack(fill="x", pady=(2, 4))

            def on_join():
                raw = ent_addr.get().strip()
                if ":" not in raw:
                    messagebox.showerror(
                        "Invalid address",
                        "Format must be  host:port\n"
                        "e.g. my.tunnel.example.com:6767"
                    )
                    return
                if not self.studio_path:
                    messagebox.showerror("Studio not found",
                                         "Could not locate RobloxStudioBeta.exe.")
                    return
                parts = raw.rsplit(":", 1)
                dst_host, dst_port_str = parts[0], parts[1]
                if not dst_port_str.isdigit():
                    messagebox.showerror("Invalid port", "Port must be a number.")
                    return

                # Persist the tunnel address before launching
                self._data["join_tunnel"] = raw
                save_data(self._data)

                self._show_join_running(dst_host, int(dst_port_str))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=20)
            make_button(btn_row, "JOIN", BTN_JOIN, on_join, width=16).pack(
                side="left", padx=8)
            make_button(btn_row, "Back", ACCENT_COLOR,
                        self._show_welcome, width=10).pack(side="left", padx=8)

        self._swap(build)

    # ──────────────────────────────────────────────────────────
    # JOIN RUNNING SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_join_running(self, dst_host: str, dst_port: int):
        def build(f):
            tk.Label(f, text="Connection Console",
                     font=("Segoe UI", 13, "bold"),
                     bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(14, 6))

            log_area = make_log(f, height=16)
            log_area.pack(padx=16, fill="both", expand=True)

            def log(msg):
                self._write_log(log_area, msg)

            status_var = tk.StringVar(value="")
            tk.Label(f, textvariable=status_var,
                     font=("Segoe UI", 10, "bold"),
                     bg=BG_COLOR, fg="#2ecc71").pack(pady=(6, 0))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=8)

            def on_stop():
                log("Disconnecting...")
                stop_udp_proxy(wait=True)
                log("Proxy stopped. Returning to menu.")
                self.after(200, self._show_welcome)

            make_button(btn_row, "Disconnect & Back",
                        BTN_DANGER, on_stop, width=20).pack()

            def run():
                log(f"Target      : {dst_host}:{dst_port}")
                log(f"Attempting to bind proxy starting from port {PROXY_PORT}...")

                success, actual_port = start_udp_proxy(dst_host, dst_port, log)

                if not success:
                    self.after(0, lambda: status_var.set(
                        "● PROXY FAILED — check log"))
                    log("Could not bind proxy. No free ports available.")
                    return

                log(f"Proxy is active on 127.0.0.1:{actual_port}")
                log("Launching Studio client...")

                p_guid = generate_guid()
                t_guid = generate_guid()
                log(f"Parent GUID : {p_guid}")
                log(f"Play GUID   : {t_guid}")

                try:
                    launch_client(
                        self.studio_path,
                        "127.0.0.1", str(actual_port),
                        p_guid, t_guid,
                        "StudioPlayer_Proxy"
                    )
                    self.after(0, lambda: status_var.set(
                        f"● CONNECTED — Studio launched (port {actual_port})"))
                except Exception as e:
                    log(f"ERROR launching Studio: {e}")
                    self.after(0, lambda: status_var.set(
                        "● STUDIO LAUNCH FAILED"))
                    stop_udp_proxy(wait=False)

            threading.Thread(target=run, daemon=True).start()

        self._swap(build)


# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    app = App()
    app.mainloop()
    # Final safety net on normal exit
    stop_udp_proxy(wait=True)
