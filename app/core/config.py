import os
import sys
import logging
from pathlib import Path
import sys

class Settings:

    @property
    def UPLOAD_DIR(self):
        # if getattr(sys, 'frozen', False):  # Running as a PyInstaller bundle
        #     base_dir = os.path.dirname(sys.executable)
        # else:  # Running as a regular script
        #     base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        #
        # return os.path.join(base_dir, "MizbanShared")
        # Get the home directory

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
