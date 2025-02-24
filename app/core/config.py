import os
import sys
from pathlib import Path


class Settings:
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    ASYNC_LOOP: str = "uvloop" if sys.platform == "linux" else "asyncio"
    HTTP_METHOD: str = "httptools"
    LOG_LEVEL: str = "critical"

    @property
    def FRONTEND_DIR(self):
        if getattr(sys, "frozen", False):  # If bundled by PyInstaller
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, "clients/frontend")

    @property
    def UPLOAD_DIR(self):
        try:
            home = Path.home()
            # Define the desktop path
            desktop = home / "Desktop"

            # Check if Desktop exists; if not, handle accordingly
            if not desktop.exists():
                if sys.platform.startswith("win"):
                    import os

                    desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))

            return desktop / "MizbanShared"

        except Exception as e:
            print(f"An error occurred: {e}")

    @property
    def THUMBNAIL_DIR(self):
        return self.UPLOAD_DIR / ".thumbnails"


settings = Settings()
