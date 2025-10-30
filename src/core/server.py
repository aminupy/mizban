import logging
import sys
from http.server import ThreadingHTTPServer

from .handlers import MizbanHandler
from config import settings


for d in (settings.MIZBAN_SHARED_DIR, settings.THUMBNAIL_DIR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        print(f"Cannot create {d!r}: {exc}")
        sys.exit(1)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger("mizban")
logger.setLevel(logging.ERROR)


def _handler_factory(*args, **kwargs):
    return MizbanHandler(
        *args,
        shared_dir=settings.MIZBAN_SHARED_DIR,
        thumb_dir=settings.THUMBNAIL_DIR,
        directory=settings.FRONTEND_DIR,
        **kwargs,
    )


def create_server() -> ThreadingHTTPServer:
    """Create the HTTP server instance, raising OSError on bind failures."""
    try:
        server = ThreadingHTTPServer((settings.HOST, settings.PORT), _handler_factory)
    except OSError as exc:
        logger.error(
            "Failed to start Mizban server on %s:%s: %s",
            settings.HOST,
            settings.PORT,
            exc,
        )
        raise
    return server


def serve_forever(server: ThreadingHTTPServer) -> None:
    """Run the HTTP server until shutdown is requested."""
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.server_close()


def start_server() -> None:
    """Backward compatible helper to create and run the server."""
    http_server = create_server()
    serve_forever(http_server)
