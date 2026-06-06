"""KUMA Guard configuration loader.

Loads JSON config files from backend/config/ and exposes a single Settings
object. Everything is plain dict-backed so configs stay human-editable and
diffable. No secrets live here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# backend/ root, resolved relative to this file so it works from any cwd.
BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = BACKEND_DIR / "data"

SETTINGS_FILE = CONFIG_DIR / "kuma_settings.json"
TRUSTED_FILE = CONFIG_DIR / "trusted_networks.json"
LAB_TARGETS_FILE = CONFIG_DIR / "lab_targets.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class Settings:
    """Thin wrapper over the JSON config files.

    Reloadable at runtime via ``reload()`` so config edits don't require a
    restart once we wire a settings endpoint in a later sprint.
    """

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.settings: dict = _load_json(SETTINGS_FILE, {})
        self.trusted: dict = _load_json(TRUSTED_FILE, {"networks": []})
        self.lab_targets: dict = _load_json(
            LAB_TARGETS_FILE, {"lab_mode": False, "approved_targets": []}
        )

    # Convenience accessors with sane fallbacks ---------------------------
    @property
    def device_name(self) -> str:
        return self.settings.get("device_name", "KUMA Guard")

    @property
    def version(self) -> str:
        return self.settings.get("version", "0.0.1")

    @property
    def default_mode(self) -> str:
        return self.settings.get("default_mode", "sentinel")

    @property
    def lab_mode(self) -> bool:
        return bool(self.settings.get("lab_mode", False))

    @property
    def wifi_interface(self) -> str:
        return self.settings.get("wifi_interface", "wlan1")

    @property
    def monitor_interface(self) -> str:
        return self.settings.get("monitor_interface", "wlan1mon")

    @property
    def api_host(self) -> str:
        return self.settings.get("api_host", "0.0.0.0")

    @property
    def api_port(self) -> int:
        return int(self.settings.get("api_port", 8080))

    @property
    def thresholds(self) -> dict:
        return self.settings.get(
            "threat_thresholds",
            {"low": 25, "medium": 50, "high": 75, "critical": 90},
        )

    def trusted_networks(self) -> list[dict]:
        return self.trusted.get("networks", [])


# Module-level singleton; import this everywhere.
settings = Settings()
