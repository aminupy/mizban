import os
import sys

from pathlib import Path


class Settings:
    @property
    def FRONTEND_DIR(self):
        if getattr(sys, 'frozen', False):  # If bundled by PyInstaller
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, "clients/frontend")

    @property
    def UPLOAD_DIR(self):
        try:
            home = Path.home()
            # Define the desktop path
            desktop = home / 'Desktop'

            # Check if Desktop exists; if not, handle accordingly
            if not desktop.exists():
                # On some systems, 'Desktop' might be localized or in a different location
                # For Windows, you can use environment variables or other methods to find the Desktop path
                if sys.platform.startswith('win'):
                    import os
                    desktop = Path(os.path.join(os.environ['USERPROFILE'], 'Desktop'))

            return desktop / "MizbanShared"

        except Exception as e:
            print(f"An error occurred: {e}")



settings = Settings()
