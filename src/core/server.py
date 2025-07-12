import os
import sys
import logging
from http.server import ThreadingHTTPServer
from pathlib import Path

from .handlers import MizbanHandler
from config import settings


for d in [settings.MIZBAN_SHARED_DIR, settings.THUMBNAIL_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        print(f"Cannot create {d!r}: {e}")
        sys.exit(1)

logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mizban")


def start_server():
    os.chdir(settings.FRONTEND_DIR)

    def handler(*args, **kwargs):
        MizbanHandler(*args, shared_dir=settings.MIZBAN_SHARED_DIR, thumb_dir=settings.THUMBNAIL_DIR, **kwargs)

    server = ThreadingHTTPServer((settings.HOST, settings.PORT), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.server_close()
