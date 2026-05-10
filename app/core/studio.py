from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from app.core.config import ROOT_DIR

_roblox_processes: list[subprocess.Popen] = []
_roblox_processes_by_key: dict[str, list[subprocess.Popen]] = {}
SERVER_PLACE_DIR = ROOT_DIR / ".localhost_cache" / "places"
RUNTIME_SERVER_PLACE = Path(os.environ.get("LOCALAPPDATA", "")) / "Roblox" / "server.rbxl"


def generate_guid() -> str:
    return str(uuid.uuid4()).upper()


def validate_studio_path(studio: str) -> None:
    if not studio:
        raise FileNotFoundError("RobloxStudioBeta.exe path is empty.")
    if not Path(studio).is_file():
        raise FileNotFoundError(f"RobloxStudioBeta.exe not found at: {studio}")


def validate_place_path(place_path: str) -> str:
    if not place_path:
        return ""
    path = Path(place_path).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Map file not found at: {path}")
    if path.suffix.lower() not in {".rbxl", ".rbxlx"}:
        raise ValueError("Map file must be a .rbxl or .rbxlx file.")
    return str(path)


def open_place_file(place_path: str) -> None:
    path = validate_place_path(place_path)
    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", "start", "", path],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    subprocess.Popen([path])


def start_server_and_clients_hotkey() -> None:
    if os.name != "nt":
        raise RuntimeError("Server & Clients hotkey launch is only supported on Windows.")

    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    script = r"""
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32Focus {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }
}
'@
$ws = New-Object -ComObject WScript.Shell
$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004
function Click-Point([int]$x, [int]$y) {
  [void][Win32Focus]::SetCursorPos($x, $y)
  Start-Sleep -Milliseconds 80
  [Win32Focus]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 80
  [Win32Focus]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  $script:target = [IntPtr]::Zero
  [Win32Focus]::EnumWindows({
    param($h, $l)
    if ([Win32Focus]::IsWindowVisible($h)) {
      $sb = New-Object System.Text.StringBuilder 512
      [void][Win32Focus]::GetWindowText($h, $sb, $sb.Capacity)
      $title = $sb.ToString()
      [uint32]$pidValue = 0
      [void][Win32Focus]::GetWindowThreadProcessId($h, [ref]$pidValue)
      $procName = ''
      try { $procName = (Get-Process -Id $pidValue -ErrorAction Stop).ProcessName } catch {}
      if (
        $procName -eq 'RobloxStudioBeta' -or
        $title -like '*Roblox Studio*' -or
        $title -like '*.rbxl*' -or
        $title -like '*.rbxlx*'
      ) {
        $script:target = $h
        return $false
      }
    }
    return $true
  }, [IntPtr]::Zero) | Out-Null
  if ($script:target -ne [IntPtr]::Zero) {
    [void][Win32Focus]::ShowWindow($script:target, 9)
    [void][Win32Focus]::SetForegroundWindow($script:target)
    Start-Sleep -Milliseconds 800

    $rect = New-Object Win32Focus+RECT
    if (-not [Win32Focus]::GetWindowRect($script:target, [ref]$rect)) {
      $ws.SendKeys('{F7}')
      exit 0
    }

    # Roblox Studio starts Server & Clients only when that test mode is selected.
    # The mode selector and Play button sit at fixed offsets in Studio's top-left mezzanine.
    Click-Point ($rect.Left + 42) ($rect.Top + 29)
    Start-Sleep -Milliseconds 450
    Click-Point ($rect.Left + 64) ($rect.Top + 137)
    Start-Sleep -Milliseconds 550
    Click-Point ($rect.Left + 105) ($rect.Top + 29)
    Start-Sleep -Milliseconds 500
    $ws.SendKeys('{F7}')
    exit 0
  }
  Start-Sleep -Milliseconds 500
}
exit 1
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    if result.returncode != 0:
        raise RuntimeError("Could not focus Roblox Studio to start Server & Clients.")


def prepare_server_place_file(place_path: str) -> str:
    source = Path(validate_place_path(place_path))
    SERVER_PLACE_DIR.mkdir(parents=True, exist_ok=True)
    target = SERVER_PLACE_DIR / f"server_launch_{uuid.uuid4().hex}.rbxl"
    shutil.copyfile(source, target)
    return str(target.resolve())


def prepare_runtime_server_place_file(place_path: str) -> str:
    source = Path(validate_place_path(place_path))
    if not RUNTIME_SERVER_PLACE.parent.is_dir():
        RUNTIME_SERVER_PLACE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, RUNTIME_SERVER_PLACE)
    return str(RUNTIME_SERVER_PLACE.resolve())


def get_studio_path() -> str:
    candidates: list[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    roots = []
    if local:
        roots.append(Path(local) / "Roblox" / "Versions")
    roots.extend([Path(r"C:\Program Files (x86)\Roblox"), Path(r"C:\Program Files\Roblox")])

    for base in roots:
        if base.is_dir():
            for path in base.rglob("RobloxStudioBeta.exe"):
                candidates.append(str(path))

    for path in candidates:
        if Path(path).is_file():
            return path

    if os.name == "nt":
        try:
            flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            result = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    (
                        "Get-ChildItem -Path $env:LOCALAPPDATA\\Roblox\\Versions "
                        "-Filter RobloxStudioBeta.exe -Recurse -ErrorAction SilentlyContinue | "
                        "Select-Object -First 1 -ExpandProperty FullName"
                    ),
                ],
                creationflags=flags,
            ).decode(errors="ignore").strip()
            if result and Path(result).is_file():
                return result
        except Exception:
            pass
    return ""


def _studio_command(studio: str) -> list[str]:
    validate_studio_path(studio)
    return [studio]


def build_server_command(
    studio: str,
    port: str,
    user_id: str,
    parent_guid: str,
    play_guid: str,
    place_path: str = "",
    startup_players: int = 0,
    use_runtime_place: bool = False,
) -> list[str]:
    command = _studio_command(studio)
    selected_place = "" if use_runtime_place else (prepare_server_place_file(place_path) if place_path else "")
    if use_runtime_place and place_path:
        prepare_runtime_server_place_file(place_path)
    command.extend(["-task", "StartServer"])
    if selected_place:
        command.extend(["-localPlaceFile", selected_place, "-port", str(port)])
        return command
    else:
        command.extend(["-placeId", "0", "-universeId", "0", "-placeVersion", "0"])
    command.extend(
        [
            "-port",
            str(port),
            "-creatorId",
            str(user_id),
            "-creatorType",
            "0",
            "-userid",
            str(user_id),
            "-numTestServerPlayersUponStartup",
            str(startup_players),
            "-parentSessionGuid",
            parent_guid,
            "-playTestSessionGuid",
            play_guid,
            "-instanceId",
            "StudioServer",
        ]
    )
    return command


def launch_server(
    studio: str,
    port: str,
    user_id: str,
    parent_guid: str,
    play_guid: str,
    place_path: str = "",
    startup_players: int = 0,
    use_runtime_place: bool = False,
    session_key: str | None = None,
) -> subprocess.Popen:
    command = build_server_command(
        studio,
        port,
        user_id,
        parent_guid,
        play_guid,
        place_path,
        startup_players=startup_players,
        use_runtime_place=use_runtime_place,
    )
    return launch_server_command(studio, command, session_key=session_key)


def launch_server_command(
    studio: str,
    command: list[str],
    session_key: str | None = None,
) -> subprocess.Popen:
    proc = subprocess.Popen(
        command,
    )
    _track_roblox_process(proc, session_key)
    return proc


def launch_client(
    studio: str,
    server_ip: str,
    server_port: str | int,
    parent_guid: str,
    play_guid: str,
    instance_id: str,
    session_key: str | None = None,
) -> subprocess.Popen:
    command = _studio_command(studio)
    command.extend(
        [
            "-task",
            "StartClient",
            "-placeId",
            "0",
            "-universeId",
            "0",
            "-placeVersion",
            "0",
            "-server",
            server_ip,
            "-port",
            str(server_port),
            "-parentSessionGuid",
            parent_guid,
            "-playTestSessionGuid",
            play_guid,
            "-instanceId",
            instance_id,
        ]
    )
    proc = subprocess.Popen(
        command
    )
    _track_roblox_process(proc, session_key)
    return proc


def _track_roblox_process(proc: subprocess.Popen, session_key: str | None = None) -> None:
    _roblox_processes.append(proc)
    if session_key:
        _roblox_processes_by_key.setdefault(session_key, []).append(proc)


def _kill_process_tree(proc: subprocess.Popen) -> bool:
    try:
        if proc.poll() is not None:
            return False
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            return result.returncode == 0
        proc.kill()
        return True
    except Exception:
        return False


def stop_roblox_processes(session_key: str) -> int:
    killed = 0
    procs = _roblox_processes_by_key.pop(session_key, [])
    for proc in list(procs):
        if _kill_process_tree(proc):
            killed += 1
        try:
            _roblox_processes.remove(proc)
        except ValueError:
            pass
    return killed


def has_running_processes() -> bool:
    for proc in list(_roblox_processes):
        try:
            if proc.poll() is None:
                return True
        except Exception:
            pass
    return False


def stop_all_roblox_processes() -> int:
    killed = 0
    for proc in list(_roblox_processes):
        if _kill_process_tree(proc):
            killed += 1
    _roblox_processes.clear()
    _roblox_processes_by_key.clear()

    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        for target in ("RobloxStudioBeta.exe", "RobloxPlayerBeta.exe"):
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
                if result.returncode == 0:
                    killed += 1
            except Exception:
                pass
    return killed
