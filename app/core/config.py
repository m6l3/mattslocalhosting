from __future__ import annotations

from pathlib import Path

APP_NAME = "LocalHost"
PROXY_PORT = 55555

WINDOW_W = 1080
WINDOW_H = 700
WINDOW_MIN_W = 780
WINDOW_MIN_H = 540

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT_DIR / "mattslocalhost_data.json"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
