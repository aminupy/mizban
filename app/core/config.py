import os
import sys
import logging


class Settings:
    _BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

    @property
    def UPLOAD_DIR(self):
        upload_dir = os.path.abspath(os.path.join(self._BASE_DIR, "../../MizbanShared"))

        try:
            # Ensure the directory exists
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
        except OSError as e:
            logging.error(f"Failed to create directory {upload_dir}: {e}")
            raise e

        return upload_dir


settings = Settings()
