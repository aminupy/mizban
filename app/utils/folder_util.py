import os
import sys


def initialize_shared_folder(path):
    try:
        # Ensure the directory exists
        if not os.path.exists(path):
            os.makedirs(path)
    except PermissionError:
        print("Permission denied. Please run the program with elevated permissions.")
        sys.exit(1)
