import errno
import logging
import socket
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


class MizbanHTTPServer(ThreadingHTTPServer):
    """HTTP server with larger socket buffers for improved throughput."""

    SOCKET_BUFFER = 4 * 1024 * 1024

    def server_bind(self) -> None:
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.SOCKET_BUFFER)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.SOCKET_BUFFER)
        except OSError as exc:
            logger.debug("Unable to adjust socket buffer sizes: %s", exc)
        try:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            logger.debug("Unable to disable Nagle algorithm: %s", exc)
        super().server_bind()


def _handler_factory(*args, **kwargs):
    return MizbanHandler(
        *args,
        shared_dir=settings.MIZBAN_SHARED_DIR,
        thumb_dir=settings.THUMBNAIL_DIR,
        directory=settings.FRONTEND_DIR,
        **kwargs,
    )


def create_server() -> ThreadingHTTPServer:
    """Create the HTTP server, retrying on port conflicts until one is free."""
    host = settings.HOST
    initial_port = settings.PORT
    port = initial_port
    retryable_errno = {errno.EADDRINUSE, errno.EACCES, errno.EPERM}

    while port <= 65535:
        try:
            server = MizbanHTTPServer((host, port), _handler_factory)
        except OSError as exc:
            if exc.errno not in retryable_errno or port == 65535:
                logger.error(
                    "Failed to start Mizban server on %s:%s: %s", host, port, exc
                )
                raise
            if exc.errno in (errno.EACCES, errno.EPERM):
                next_port = max(port + 1, 1024)
                logger.warning(
                    "Port %s requires elevated privileges. Retrying with %s.",
                    port,
                    next_port,
                )
                port = next_port
            else:
                next_port = port + 1
                logger.warning(
                    "Port %s is already in use. Retrying with %s.", port, next_port
                )
                port = next_port
            continue

        if port != initial_port:
            settings.PORT = port
            try:
                settings.save()
            except Exception as save_exc:
                logger.error("Failed to persist new port %s: %s", port, save_exc)
            else:
                logger.info(
                    "Configured port updated from %s to %s to match bound server port.",
                    initial_port,
                    port,
                )
        return server

    raise OSError(f"No available port found in range {initial_port}-65535")


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
