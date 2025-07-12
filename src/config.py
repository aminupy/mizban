import json
from pathlib import Path

DEFAULT_CONFIG = {
    "mizban_shared_dir": str(Path.home() / "Desktop" / "MizbanShared"),
    "port": 8000
}

CONFIG_DIR = Path.home() / ".config" / "Mizban"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "Mizban"


class Settings:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load_from_file()

    def _load_from_file(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    file_config = json.load(f)
                    self._config.update(file_config)
            except Exception as e:
                print(f"[WARN] Failed to load config: {e}")
        else:
            self.save()

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._config, f, indent=4)

    @property
    def MIZBAN_SHARED_DIR(self):
        return Path(self._config["mizban_shared_dir"])

    @MIZBAN_SHARED_DIR.setter
    def MIZBAN_SHARED_DIR(self, value: Path):
        self._config["mizban_shared_dir"] = str(value)

    @property
    def PORT(self):
        return int(self._config["port"])

    @PORT.setter
    def PORT(self, value: int):
        self._config["port"] = value

    @property
    def HOST(self):
        return "0.0.0.0"

    @property
    def THUMBNAIL_DIR(self):
        return CACHE_DIR / ".thumbnails"

    @property
    def FRONTEND_DIR(self):
        return Path(__file__).parent.parent / "clients" / "frontend"


# Create a singleton-style shared settings instance
settings = Settings()
