# src/config.py

import sys
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    "mizban_shared_dir": str(Path.home() / "Desktop" / "MizbanShared"),
    "port": 8000
}

CONFIG_DIR = Path.home() / ".config" / "Mizban"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "Mizban"


def _ensure_dirs():
    for d in [CONFIG_DIR, CACHE_DIR]:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            print(f"Cannot create {d!r}: {e}")
            sys.exit(1)


def load_config() -> Dict[str, Any]:
    _ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        settings.MIZBAN_SHARED_DIR = config["mizban_shared_dir"]
        settings.PORT = config["port"]
    except Exception as e:
        print(f"[ERROR] Could not save config: {e}")
        sys.exit(1)


# Load config from disk
_cfg = load_config()

class Settings:
    HOST = "0.0.0.0"
    PORT = int(_cfg["port"])
    MIZBAN_SHARED_DIR = Path(_cfg["shared_folder"])
    THUMBNAIL_DIR = CACHE_DIR / ".thumbnails"
    FRONTEND_DIR = Path(__file__).parent.parent / "clients" / "frontend"

settings = Settings()