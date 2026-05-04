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
import math

# ==================== CONSTANTS ====================
PROXY_PORT   = 55555
DATA_FILE    = "mattslocalhost_data.json"

# Color palette — deep navy + electric cyan + neon accents
BG_COLOR     = "#0d1117"
BG2_COLOR    = "#161b22"
CARD_COLOR   = "#1c2333"
BORDER_COLOR = "#30363d"
GLOW_COLOR   = "#00d4ff"

BTN_CREATE   = "#00c853"
BTN_JOIN     = "#00b4d8"
BTN_DANGER   = "#f44336"
BTN_WARN     = "#ff9800"
BTN_BACK     = "#3d4451"

TEXT_COLOR   = "#e6edf3"
MUTED_COLOR  = "#8b949e"
DIM_COLOR    = "#484f58"

ACCENT_GREEN = "#39d353"
ACCENT_CYAN  = "#00d4ff"
ACCENT_RED   = "#f44336"

FONT_TITLE   = ("Consolas", 22, "bold")
FONT_SUB     = ("Consolas", 9)
FONT_LABEL   = ("Consolas", 10, "bold")
FONT_LOG     = ("Consolas", 9)
FONT_BTN     = ("Consolas", 10, "bold")
FONT_SMALL   = ("Consolas", 8)

# ==================== PERSISTENCE ====================

def load_data() -> dict:
    defaults = {
        "user_id":     "123456789",
        "host_tunnel": "",
        "join_tunnel": "",
        "server_port": "55555",
    }
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            return {**defaults, **stored}
    except Exception:
        pass
    return defaults


def save_data(data: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ==================== GLOBAL PROXY STATE ====================
_proxy_running = threading.Event()
_proxy_stopped = threading.Event()
_udp_sockets   = []
_proxy_lock    = threading.Lock()
_proxy_thread  = None
_active_port   = None


# ==================== HELPERS ====================
def get_studio_path() -> str:
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
    for port in range(start_port, start_port + max_attempts):
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.bind(("127.0.0.1", port))
            test_sock.close()
            return port
        except OSError:
            continue
    return -1


# ==================== UDP PROXY WARM-UP ====================
def warmup_udp_tunnel(dst_host: str, dst_port: int, log_fn,
                      packets: int = 10, delay: float = 0.05):
    """
    Send a handful of throwaway UDP packets to the tunnel endpoint so that
    any stateful NAT / proxy on the remote side learns the return path before
    Roblox Studio sends its first real packet.

    UDP has no handshake, so the first real packet can be silently dropped if
    the remote proxy hasn't recorded our source address yet.  Priming the path
    with cheap dummy data gives it a valid mapping to work with.
    """
    log_fn(f"Warming up tunnel {dst_host}:{dst_port} ({packets} packets)...")
    try:
        dst_ip = socket.gethostbyname(dst_host)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        # 64 bytes of zeros — small enough to be cheap, big enough to matter
        payload = b"\x00" * 64
        for i in range(packets):
            try:
                sock.sendto(payload, (dst_ip, dst_port))
            except OSError:
                pass
            time.sleep(delay)
        sock.close()
        log_fn("Tunnel warm-up done.")
    except Exception as e:
        log_fn(f"Warm-up warning (non-fatal): {e}")


# ==================== UDP PROXY ====================
def start_udp_proxy(dst_host: str, dst_port: int, log_fn) -> tuple:
    global _proxy_thread, _active_port
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
            log_fn(f"Resolved {dst_host} → {dst_ip}")
            bound_port = find_free_port(PROXY_PORT)
            if bound_port == -1:
                raise OSError(f"No free ports starting from {PROXY_PORT}")
            port_box[0] = bound_port
            if bound_port != PROXY_PORT:
                log_fn(f"Port {PROXY_PORT} busy, using {bound_port}")

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
                    log_fn(f"New session: {addr[0]}:{addr[1]}")
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

                    threading.Thread(target=_listen, args=(s, addr), daemon=True).start()

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
            for s in list(client_sessions.values()):
                try:
                    s.close()
                except Exception:
                    pass
            client_sessions.clear()
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
    global _proxy_thread, _active_port
    if not _proxy_running.is_set():
        return
    _proxy_running.clear()
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


atexit.register(lambda: stop_udp_proxy(wait=False))


# ==================== STUDIO LAUNCHER ====================
def launch_server(studio, port, user_id, parent_guid, play_guid):
    subprocess.Popen([
        studio,
        "-task", "StartServer",
        "-placeId", "0", "-universeId", "0", "-placeVersion", "0",
        "-port", port, "-creatorId", user_id, "-creatorType", "0",
        "-userid", user_id,
        "-numTestServerPlayersUponStartup", "0",
        "-parentSessionGuid", parent_guid,
        "-playTestSessionGuid", play_guid,
        "-instanceId", "StudioServer",
    ])


def launch_client(studio, server_ip, server_port, parent_guid, play_guid, instance_id):
    subprocess.Popen([
        studio,
        "-task", "StartClient",
        "-placeId", "0", "-universeId", "0", "-placeVersion", "0",
        "-server", server_ip, "-port", server_port,
        "-parentSessionGuid", parent_guid,
        "-playTestSessionGuid", play_guid,
        "-instanceId", instance_id,
    ])


# ==================== COLOUR HELPERS ====================
def _hex_blend(c1: str, c2: str, t: float) -> str:
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

def _lighten(color: str, amount: float) -> str:
    return _hex_blend(color, "#ffffff", amount)

def _darken(color: str, amount: float) -> str:
    return _hex_blend(color, "#000000", amount)


# ==================== ANIMATED BUTTON (factory) ====================
def AnimButton(parent, text, color, command,
               width=160, height=40, font=FONT_BTN, **kw):
    normal_bg = color
    hover_bg  = _lighten(color, 0.18)
    press_bg  = _darken(color,  0.15)
    char_w    = max(1, width // 8)

    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=normal_bg,
        fg=TEXT_COLOR,
        activebackground=press_bg,
        activeforeground=TEXT_COLOR,
        font=font,
        relief="flat",
        bd=0,
        cursor="hand2",
        width=char_w,
        pady=max(4, height // 8),
        highlightthickness=1,
        highlightbackground=_lighten(color, 0.15),
        highlightcolor=_lighten(color, 0.4),
        **kw
    )
    btn.bind("<Enter>",           lambda e: btn.config(bg=hover_bg,  highlightbackground=_lighten(color, 0.4)))
    btn.bind("<Leave>",           lambda e: btn.config(bg=normal_bg, highlightbackground=_lighten(color, 0.15)))
    btn.bind("<ButtonPress-1>",   lambda e: btn.config(bg=press_bg))
    btn.bind("<ButtonRelease-1>", lambda e: btn.config(bg=hover_bg))
    return btn


# ==================== ANIMATED ENTRY (factory) ====================
def AnimEntry(parent, placeholder="", width=38, **kw):
    border = tk.Frame(parent, bg=BORDER_COLOR, padx=1, pady=1, **kw)
    entry = tk.Entry(
        border,
        width=width,
        font=FONT_SUB,
        bg="#0d1b2a",
        fg=TEXT_COLOR,
        insertbackground=ACCENT_CYAN,
        relief="flat", bd=6,
        highlightthickness=0,
    )
    entry.pack(fill="x")
    entry.insert(0, placeholder)
    entry.bind("<FocusIn>",  lambda e: border.config(bg=ACCENT_CYAN))
    entry.bind("<FocusOut>", lambda e: border.config(bg=BORDER_COLOR))
    border.get = entry.get
    return border


# ==================== LOG WIDGET ====================
def make_log(parent, height=14):
    frm = tk.Frame(parent, bg=BORDER_COLOR, padx=1, pady=1)
    frm.pack(padx=16, fill="both", expand=True)
    log = scrolledtext.ScrolledText(
        frm, height=height,
        font=FONT_LOG,
        bg="#080d12",
        fg="#39d353",
        insertbackground=TEXT_COLOR,
        relief="flat", bd=0,
        state="normal",
        selectbackground=ACCENT_CYAN,
    )
    log.pack(fill="both", expand=True)
    return log


# ==================== SPLASH SCREEN ====================
class SplashScreen(tk.Toplevel):
    _DOT_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=BG_COLOR)
        self.attributes("-topmost", True)

        w, h = 400, 220
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._canvas = tk.Canvas(self, width=w, height=h,
                                 bg=BG_COLOR, highlightthickness=0)
        self._canvas.place(x=0, y=0)

        inner = tk.Frame(self, bg=BG_COLOR)
        inner.place(x=2, y=2, width=w-4, height=h-4)

        tk.Label(inner, text="MATT'S  LOCALHOST",
                 font=("Consolas", 16, "bold"),
                 bg=BG_COLOR, fg=ACCENT_CYAN).pack(pady=(32, 2))

        tk.Label(inner, text="Studio lan tool",
                 font=("Consolas", 9),
                 bg=BG_COLOR, fg=MUTED_COLOR).pack()

        spin_row = tk.Frame(inner, bg=BG_COLOR)
        spin_row.pack(pady=(22, 0))
        self._spin_lbl = tk.Label(spin_row, text=self._DOT_FRAMES[0],
                                  font=("Consolas", 13), bg=BG_COLOR, fg=ACCENT_CYAN, width=2)
        self._spin_lbl.pack(side="left")
        self._status_lbl = tk.Label(spin_row, text="Locating Studio...",
                                    font=("Consolas", 9), bg=BG_COLOR, fg=MUTED_COLOR)
        self._status_lbl.pack(side="left", padx=(8, 0))

        bar_bg = tk.Frame(inner, bg="#0d1b2a", height=3, width=340)
        bar_bg.pack(pady=(20, 0))
        bar_bg.pack_propagate(False)
        self._bar = tk.Frame(bar_bg, bg=ACCENT_CYAN, height=3, width=0)
        self._bar.place(x=0, y=0, height=3)

        self._frame_idx  = 0
        self._bar_width  = 0
        self._bar_target = 0
        self._border_t   = 0
        self._animating  = True
        self._anim_border()
        self._anim()

    def _anim_border(self):
        if not self._animating:
            return
        c = self._canvas
        w, h = 400, 220
        c.delete("border")
        t = self._border_t
        clr = f"#{int(0+80*(0.5+0.5*math.sin(t))):02x}{int(180+50*(0.5+0.5*math.sin(t+1))):02x}{int(200+55*(0.5+0.5*math.sin(t+2))):02x}"
        c.create_rectangle(0, 0, w-1, h-1, outline=clr, width=2, tags="border")
        self._border_t += 0.06
        self.after(30, self._anim_border)

    def _anim(self):
        if not self._animating:
            return
        self._frame_idx = (self._frame_idx + 1) % len(self._DOT_FRAMES)
        self._spin_lbl.config(text=self._DOT_FRAMES[self._frame_idx])
        diff = self._bar_target - self._bar_width
        step = max(1, int(diff * 0.1))
        if diff > 0:
            self._bar_width = min(self._bar_width + step, self._bar_target)
            self._bar.place_configure(width=self._bar_width)
        self.after(80, self._anim)

    def set_status(self, text, progress=0):
        self._status_lbl.config(text=text)
        self._bar_target = progress

    def close(self):
        self._animating = False
        self.destroy()


# ==================== TRANSITION ENGINE ====================
class TransitionManager:
    def __init__(self, root: tk.Tk):
        self._root  = root
        self._frame = None
        self._busy  = False

    def swap(self, builder, direction="right"):
        old_frame = self._frame
        w = self._root.winfo_width() or 560

        new_frame = tk.Frame(self._root, bg=BG_COLOR)
        new_frame.place(x=w, y=0, relwidth=1, relheight=1)
        builder(new_frame)
        self._frame = new_frame

        if old_frame is None:
            new_frame.place(x=0, y=0)
            return

        steps  = 12
        offset = w if direction == "right" else -w
        dx_new = -offset / steps
        dx_old = offset / steps

        positions_new = [int(offset + dx_new * i) for i in range(1, steps + 1)]
        positions_old = [int(dx_old * i) for i in range(1, steps + 1)]

        def step(i):
            if i >= steps:
                new_frame.place(x=0, y=0)
                if old_frame.winfo_exists():
                    old_frame.destroy()
                return
            new_frame.place(x=positions_new[i])
            if old_frame.winfo_exists():
                old_frame.place(x=positions_old[i])
            self._root.after(14, lambda: step(i + 1))

        step(0)


# ==================== MAIN APPLICATION ====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Matt's LocalHost")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(bg=BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.studio_path = ""
        self._data       = load_data()
        self._tm         = TransitionManager(self)

        self._show_splash()

    def _on_close(self):
        stop_udp_proxy(wait=True)
        self.destroy()

    def _update_title(self):
        if self.studio_path:
            self.title(f"Matt's LocalHost  —  Studio found: {self.studio_path}")
        else:
            self.title("Matt's LocalHost  —  Studio NOT found")

    # ──────────────────────────────────────────────────────────
    # SPLASH
    # ──────────────────────────────────────────────────────────
    def _show_splash(self):
        self.withdraw()
        splash = SplashScreen(self)

        def lookup():
            splash.set_status("Running PowerShell query...", 100)
            path = get_studio_path()
            self.after(0, lambda: _done(path))

        def _done(path):
            splash.set_status("Studio found!" if path else "Studio not found.", 340)
            self.studio_path = path
            self.after(700, lambda: _finish(path))

        def _finish(path):
            splash.close()
            self.deiconify()
            self._update_title()
            if not path:
                messagebox.showwarning(
                    "Studio Not Found",
                    "RobloxStudioBeta.exe was not found.\n"
                    "Make sure Studio is installed."
                )
            self._show_welcome()

        threading.Thread(target=lookup, daemon=True).start()

    # ──────────────────────────────────────────────────────────
    # LOG HELPER
    # ──────────────────────────────────────────────────────────
    def _write_log(self, widget, msg):
        def _do():
            widget.insert(tk.END, f"[{ts()}] {msg}\n")
            widget.see(tk.END)
        self.after(0, _do)

    # ──────────────────────────────────────────────────────────
    # HEADER WIDGET
    # ──────────────────────────────────────────────────────────
    def _make_header(self, parent, title, subtitle=""):
        hdr = tk.Frame(parent, bg=BG_COLOR)
        hdr.pack(fill="x", pady=(20, 0))

        bar = tk.Frame(hdr, bg=ACCENT_CYAN, height=2)
        bar.pack(fill="x", padx=20)

        tk.Label(hdr, text=title,
                 font=("Consolas", 16, "bold"),
                 bg=BG_COLOR, fg=ACCENT_CYAN).pack(pady=(10, 0))
        if subtitle:
            tk.Label(hdr, text=subtitle,
                     font=("Consolas", 8),
                     bg=BG_COLOR, fg=MUTED_COLOR).pack(pady=(2, 0))

        bar2 = tk.Frame(hdr, bg=BORDER_COLOR, height=1)
        bar2.pack(fill="x", padx=20, pady=(10, 0))

    # ──────────────────────────────────────────────────────────
    # WELCOME SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_welcome(self):
        stop_udp_proxy(wait=False)

        def build(f):
            tk.Frame(f, bg=ACCENT_CYAN, height=2).pack(fill="x")

            title_area = tk.Frame(f, bg=BG_COLOR)
            title_area.pack(fill="x", pady=(30, 0))

            tk.Label(title_area,
                     text="MATT'S  LOCALHOST",
                     font=("Consolas", 24, "bold"),
                     bg=BG_COLOR, fg=TEXT_COLOR).pack()

            tk.Label(title_area,
                     text="▸  Studio LAN / Tunnel Tool",
                     font=("Consolas", 9),
                     bg=BG_COLOR, fg=MUTED_COLOR).pack(pady=(4, 0))

            status_color = ACCENT_GREEN if self.studio_path else ACCENT_RED
            status_text  = "● STUDIO READY" if self.studio_path else "● STUDIO NOT FOUND"
            pill = tk.Frame(f, bg=BG2_COLOR)
            pill.pack(pady=(16, 0))
            tk.Label(pill, text=status_text,
                     font=("Consolas", 8, "bold"),
                     bg=BG2_COLOR, fg=status_color,
                     padx=12, pady=4).pack()

            tk.Frame(f, bg=BORDER_COLOR, height=1).pack(fill="x", padx=40, pady=24)

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack()

            AnimButton(
                btn_row, "  ▶  CREATE SERVER", BTN_CREATE,
                self._show_host_menu, width=190, height=46
            ).pack(side="left", padx=16)

            AnimButton(
                btn_row, "  ▶  JOIN SERVER", BTN_JOIN,
                self._show_join_menu, width=190, height=46
            ).pack(side="left", padx=16)

            tk.Frame(f, bg=BORDER_COLOR, height=1).pack(fill="x", padx=20, side="bottom", pady=(0, 4))
            tk.Label(f, text="by @s0m3thing_matters  •  discord.gg/H3K2xeU96A",
                     font=("Consolas", 12),
                     bg=BG_COLOR, fg=DIM_COLOR).pack(side="bottom")

        self._tm.swap(build, direction="left")

    # ──────────────────────────────────────────────────────────
    # HOST / CREATE MENU
    # ──────────────────────────────────────────────────────────
    def _show_host_menu(self):
        def build(f):
            self._make_header(f, "CREATE SERVER", "host a local studio session")

            card = tk.Frame(f, bg=CARD_COLOR)
            card.pack(padx=30, pady=16, fill="x")
            tk.Frame(card, bg=ACCENT_CYAN, height=1).pack(fill="x")
            inner = tk.Frame(card, bg=CARD_COLOR, padx=20, pady=16)
            inner.pack(fill="x")

            def row(lbl, placeholder, key):
                tk.Label(inner, text=lbl, font=FONT_LABEL,
                         bg=CARD_COLOR, fg=MUTED_COLOR,
                         anchor="w").pack(fill="x", pady=(6, 1))
                e = AnimEntry(inner, self._data.get(key, placeholder))
                e.pack(fill="x")
                return e

            ent_uid    = row("USER ID", "123456789", "user_id")
            ent_tunnel = row("TUNNEL ADDRESS  (host:port, optional)", "", "host_tunnel")
            ent_port   = row("TEAMTEST PORT", "55555", "server_port")

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=18)

            def on_create():
                uid    = ent_uid.get().strip()
                tunnel = ent_tunnel.get().strip()
                port   = ent_port.get().strip()
                if not uid or not port:
                    messagebox.showwarning("Missing Fields", "User ID and Port are required.")
                    return
                if not port.isdigit():
                    messagebox.showerror("Invalid Port", "Port must be a number.")
                    return
                if not self.studio_path:
                    messagebox.showerror("Studio Not Found", "Cannot locate RobloxStudioBeta.exe.")
                    return
                self._data.update({"user_id": uid, "host_tunnel": tunnel, "server_port": port})
                save_data(self._data)
                self._show_host_running(uid, tunnel, port)

            AnimButton(btn_row, "▶  CREATE", BTN_CREATE, on_create, width=140, height=40).pack(side="left", padx=8)
            AnimButton(btn_row, "← BACK", BTN_BACK, self._show_welcome, width=100, height=40).pack(side="left", padx=8)

        self._tm.swap(build, direction="right")

    # ──────────────────────────────────────────────────────────
    # HOST RUNNING SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_host_running(self, user_id, tunnel_addr, port):
        p_guid = generate_guid()
        t_guid = generate_guid()

        def build(f):
            self._make_header(f, "SERVER CONSOLE")
            log_area = make_log(f, height=14)

            def log(msg):
                self._write_log(log_area, msg)

            status_var = tk.StringVar(value="● INITIALIZING...")
            sl = tk.Label(f, textvariable=status_var,
                          font=("Consolas", 10, "bold"),
                          bg=BG_COLOR, fg=MUTED_COLOR)
            sl.pack(pady=(6, 0))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=10)

            join_btn = AnimButton(
                btn_row, "▶ JOIN (local)",
                BTN_WARN,
                lambda: self._join_local(port, p_guid, t_guid),
                width=170, height=38
            )
            AnimButton(btn_row, "← BACK", BTN_BACK,
                       self._show_welcome, width=110, height=38).pack(side="left", padx=8)

            def launch():
                log(f"Studio  : {self.studio_path}")
                log(f"PGUID   : {p_guid}")
                log(f"TGUID   : {t_guid}")
                log(f"Port    : {port}")
                log(f"UserID  : {user_id}")
                if tunnel_addr:
                    log(f"Tunnel  : {tunnel_addr}")
                log("Launching server process...")
                try:
                    launch_server(self.studio_path, port, user_id, p_guid, t_guid)
                    log("Server started. Waiting ~5s for init...")
                    time.sleep(5)
                    self.after(0, lambda: [
                        status_var.set("● SERVER LIVE"),
                        sl.config(fg=ACCENT_GREEN),
                        join_btn.pack(side="left", padx=8)
                    ])
                    log("Ready! Click JOIN to connect.")
                except Exception as e:
                    log(f"ERROR: {e}")
                    self.after(0, lambda: [
                        status_var.set("● LAUNCH FAILED"),
                        sl.config(fg=ACCENT_RED)
                    ])

            threading.Thread(target=launch, daemon=True).start()

        self._tm.swap(build, direction="right")

    def _join_local(self, port, p_guid, t_guid):
        try:
            launch_client(self.studio_path, "127.0.0.1", port, p_guid, t_guid, "StudioPlayer_Host")
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))

    # ──────────────────────────────────────────────────────────
    # JOIN MENU
    # ──────────────────────────────────────────────────────────
    def _show_join_menu(self):
        def build(f):
            self._make_header(f, "JOIN SERVER", "connect via tunnel address")

            card = tk.Frame(f, bg=CARD_COLOR)
            card.pack(padx=30, pady=20, fill="x")
            tk.Frame(card, bg=BTN_JOIN, height=1).pack(fill="x")
            inner = tk.Frame(card, bg=CARD_COLOR, padx=20, pady=16)
            inner.pack(fill="x")

            tk.Label(inner, text="TUNNEL ADDRESS  (host:port)",
                     font=FONT_LABEL, bg=CARD_COLOR, fg=MUTED_COLOR,
                     anchor="w").pack(fill="x", pady=(6, 1))
            ent_addr = AnimEntry(inner, self._data.get("join_tunnel", ""))
            ent_addr.pack(fill="x")

            tk.Label(inner, text="e.g.  my.tunnel.net:6767",
                     font=("Consolas", 8),
                     bg=CARD_COLOR, fg=DIM_COLOR).pack(anchor="w", pady=(2, 0))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=20)

            def on_join():
                raw = ent_addr.get().strip()
                if ":" not in raw:
                    messagebox.showerror("Invalid Address", "Format: host:port")
                    return
                if not self.studio_path:
                    messagebox.showerror("Studio Not Found", "Cannot locate RobloxStudioBeta.exe.")
                    return
                host, port_str = raw.rsplit(":", 1)
                if not port_str.isdigit():
                    messagebox.showerror("Invalid Port", "Port must be a number.")
                    return
                self._data["join_tunnel"] = raw
                save_data(self._data)
                self._show_join_running(host, int(port_str))

            AnimButton(btn_row, "⟶  JOIN", BTN_JOIN, on_join, width=140, height=40).pack(side="left", padx=8)
            AnimButton(btn_row, "← BACK", BTN_BACK, self._show_welcome, width=100, height=40).pack(side="left", padx=8)

        self._tm.swap(build, direction="right")

    # ──────────────────────────────────────────────────────────
    # JOIN RUNNING SCREEN
    # ──────────────────────────────────────────────────────────
    def _show_join_running(self, dst_host, dst_port):
        def build(f):
            self._make_header(f, "CONNECTION CONSOLE")
            log_area = make_log(f, height=14)

            def log(msg):
                self._write_log(log_area, msg)

            status_var = tk.StringVar(value="● CONNECTING...")
            sl = tk.Label(f, textvariable=status_var,
                          font=("Consolas", 10, "bold"),
                          bg=BG_COLOR, fg=MUTED_COLOR)
            sl.pack(pady=(6, 0))

            btn_row = tk.Frame(f, bg=BG_COLOR)
            btn_row.pack(pady=10)

            def on_stop():
                log("Disconnecting...")
                stop_udp_proxy(wait=True)
                log("Proxy stopped.")
                self.after(200, self._show_welcome)

            AnimButton(btn_row, "✕  DISCONNECT", BTN_DANGER, on_stop, width=160, height=38).pack()

            def run():
                log(f"Target : {dst_host}:{dst_port}")
                # ── WARM-UP: prime the tunnel path before starting the proxy ──
                # UDP has no handshake, so the remote proxy won't know where to
                # route replies until it sees our first outbound packet.  If that
                # first packet gets dropped (common on cheaper tunnel setups) the
                # whole session silently fails.  Sending a few dummy packets first
                # gives the remote side a valid return mapping before Roblox's
                # real traffic arrives.
                warmup_udp_tunnel(dst_host, dst_port, log)
                # ─────────────────────────────────────────────────────────────
                log(f"Binding proxy from port {PROXY_PORT}...")
                success, actual_port = start_udp_proxy(dst_host, dst_port, log)
                if not success:
                    self.after(0, lambda: [
                        status_var.set("● PROXY FAILED"),
                        sl.config(fg=ACCENT_RED)
                    ])
                    return
                log(f"Proxy active on 127.0.0.1:{actual_port}")
                log("Launching Studio client...")
                p_guid = generate_guid()
                t_guid = generate_guid()
                log(f"PGUID : {p_guid}")
                log(f"TGUID : {t_guid}")
                try:
                    launch_client(
                        self.studio_path,
                        "127.0.0.1", str(actual_port),
                        p_guid, t_guid,
                        "StudioPlayer_Proxy"
                    )
                    self.after(0, lambda: [
                        status_var.set(f"● CONNECTED  —  port {actual_port}"),
                        sl.config(fg=ACCENT_GREEN)
                    ])
                except Exception as e:
                    log(f"ERROR: {e}")
                    self.after(0, lambda: [
                        status_var.set("● STUDIO LAUNCH FAILED"),
                        sl.config(fg=ACCENT_RED)
                    ])
                    stop_udp_proxy(wait=False)

            threading.Thread(target=run, daemon=True).start()

        self._tm.swap(build, direction="right")


# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    app = App()
    app.mainloop()
    stop_udp_proxy(wait=True)
