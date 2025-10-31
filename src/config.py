import json
from pathlib import Path
import sys

# User-specific configuration paths remain the same
DEFAULT_CONFIG = {
    "mizban_shared_dir": str(Path.home() / "Desktop" / "MizbanShared"),
    # Default to an unprivileged port to avoid admin/root requirements.
    "port": 8000,
}

CONFIG_DIR = Path.home() / ".config" / "Mizban"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "Mizban"


def get_base_dir() -> Path:
    """
    Returns the correct base directory whether running from source or as a
    frozen (Nuitka) executable.
    """
    # This robust check works for Nuitka and other tools like PyInstaller.
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        # ✨ We are running in a bundle (Nuitka executable).
        # In --onefile mode, the base path is the temp folder where the
        # script is extracted, which is the parent of __file__.
        return Path(__file__).parent
    else:
        # We are running in a normal Python environment.
        # The base dir is the project root (up two levels from this file).
        return Path(__file__).parent.parent.resolve()


class Settings:
    # BASE_DIR is now correct for both development and --onefile builds
    BASE_DIR: Path = get_base_dir()

    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load_from_file()

    # The _load_from_file and save methods are unchanged...
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

    # All other properties are also unchanged...
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
        # ✨ This path now works for both environments because BASE_DIR is correct
        return self.BASE_DIR / "clients" / "frontend"


# Create a singleton-style shared settings instance
settings = Settings()
