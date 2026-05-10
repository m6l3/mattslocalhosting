from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import DATA_FILE


@dataclass(slots=True)
class AppSettings:
    user_id: str = ""
    host_tunnel: str = ""
    join_tunnel: str = ""
    server_port: str = "55555"
    place_path: str = ""
    studio_path: str = ""


class SettingsStore:
    def __init__(self, path: Path = DATA_FILE) -> None:
        self.path = path

    def load(self) -> AppSettings:
        defaults = asdict(AppSettings())
        try:
            if self.path.exists():
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return AppSettings(**{**defaults, **payload})
        except Exception:
            pass
        return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.write_text(
            json.dumps(asdict(settings), indent=2),
            encoding="utf-8",
        )

    def update(self, settings: AppSettings, **values: Any) -> AppSettings:
        payload = asdict(settings)
        payload.update(values)
        next_settings = AppSettings(**payload)
        self.save(next_settings)
        return next_settings
