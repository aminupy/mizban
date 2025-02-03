import os
import sys
from typing import Iterable


def initialize_shared_folders(paths: Iterable):
    try:
        for path in paths:
            # Ensure the directory exists
            if not os.path.exists(path):
                os.makedirs(path)
    except PermissionError:
        print("Permission denied. Please run the program with elevated permissions.")
        sys.exit(1)
