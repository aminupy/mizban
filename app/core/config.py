import os
import sys
import logging


class Settings:

    @property
    def UPLOAD_DIR(self):
        if getattr(sys, 'frozen', False):  # Running as a PyInstaller bundle
            base_dir = os.path.dirname(sys.executable)
        else:  # Running as a regular script
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

        return os.path.join(base_dir, "MizbanShared")

settings = Settings()
